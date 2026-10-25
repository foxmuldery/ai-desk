"""Local-first HTTP coordinator for AI Desk's dry-run MVP."""
from __future__ import annotations

import json
import os
import queue
import secrets
import ssl
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from .adapters import run_adapter
from .policy import adapter_allowed, validate_profile
from .store import TaskStore

ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = ROOT / "web"
DB_PATH = os.environ.get("AI_DESK_DB", str(ROOT / "data" / "ai-desk.sqlite3"))
BIND = os.environ.get("AI_DESK_BIND", "127.0.0.1")
PORT = int(os.environ.get("AI_DESK_PORT", "8765"))
TOKEN = os.environ.get("AI_DESK_TOKEN", "")
PROFILE = os.environ.get("AI_DESK_EXECUTION_PROFILE", "local")
TLS_CERT = os.environ.get("AI_DESK_TLS_CERT", "")
TLS_KEY = os.environ.get("AI_DESK_TLS_KEY", "")
store = TaskStore(DB_PATH)
task_queue: queue.Queue[str] = queue.Queue()


def process_task(task_id: str) -> None:
    """Run one registered adapter outside the request thread."""
    task = store.get_task(task_id)
    if not task or task["status"] != "queued":
        return
    # Defense in depth: even old persisted tasks cannot run a real adapter
    # under the phone-dry-run profile, regardless of reverse proxy headers.
    if not adapter_allowed(PROFILE, task["adapter"]):
        store.add_event(task_id, "policy.blocked", {"adapter": task["adapter"]})
        store.set_status(
            task_id, "failed",
            summary="Execution profile blocked the adapter.",
            error_code="EXECUTION_PROFILE_BLOCKED",
        )
        return
    try:
        task = store.set_status(task_id, "accepted", summary="Persisted by coordinator; waiting for worker.")
        task = store.set_status(task_id, "running", summary="Dry-run adapter is running.")
        result = run_adapter(task["adapter"], task)
        store.add_event(task_id, "adapter.result", result)
        store.set_status(task_id, result["status"], summary=result["summary"])
    except Exception as exc:
        current = store.get_task(task_id)
        if current and current["status"] in ("queued", "accepted", "running", "needs_input", "unknown"):
            store.set_status(
                task_id, "failed", summary="Task adapter failed.",
                error_code=type(exc).__name__,
            )
            store.add_event(task_id, "task.exception", {"type": type(exc).__name__})


def worker_loop() -> None:
    while True:
        task_id = task_queue.get()
        try:
            process_task(task_id)
        except Exception as exc:
            # Keep the worker alive if a storage/transition error escapes task handling.
            print(f"Worker error for {task_id}: {type(exc).__name__}")
        finally:
            task_queue.task_done()


def recover_tasks() -> None:
    # Queued work is safe to enqueue again. In-flight work cannot be assumed safe to replay.
    for task in store.list_tasks(limit=1000):
        if task["status"] in ("accepted", "running"):
            store.set_status(
                task["id"], "unknown",
                summary="Coordinator restarted while task was in flight; reconciliation required.",
                error_code="COORDINATOR_RESTART",
            )
        elif task["status"] == "queued":
            task_queue.put(task["id"])


class Handler(BaseHTTPRequestHandler):
    server_version = "AIDesk/0.1"

    def log_message(self, fmt: str, *args: object) -> None:
        # Avoid logging request bodies or auth headers.
        print("%s - %s" % (self.address_string(), fmt % args))

    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def _send_static(self, path: str) -> bool:
        assets = {
            "/app.js": (WEB_DIR / "app.js", "application/javascript; charset=utf-8"),
            "/styles.css": (WEB_DIR / "styles.css", "text/css; charset=utf-8"),
        }
        asset = assets.get(path)
        if asset is None:
            return False
        file_path, content_type = asset
        if not file_path.is_file():
            self._json(404, {"error": {"code": "ASSET_NOT_FOUND", "message": "Static asset not found"}})
            return True
        body = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)
        return True

    def _authorized(self) -> bool:
        # Health and the static UI shell are public; task data and writes require a bearer token.
        if self.path.split("?")[0] in ("/api/v1/health", "/"):
            return True
        if not TOKEN:
            self._json(503, {"error": {"code": "TOKEN_NOT_CONFIGURED",
                                      "message": "Set AI_DESK_TOKEN before using the API."}})
            return False
        supplied = self.headers.get("Authorization", "")
        expected = "Bearer " + TOKEN
        if not secrets.compare_digest(supplied, expected):
            self._json(401, {"error": {"code": "UNAUTHENTICATED",
                                      "message": "A valid bearer token is required."}})
            return False
        return True

    def _read_json(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise ValueError("invalid Content-Length")
        if length < 2 or length > 64_000:
            raise ValueError("request body must be between 2 and 64000 bytes")
        raw = self.rfile.read(length)
        try:
            value = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("body must be valid JSON") from exc
        if not isinstance(value, dict):
            raise ValueError("JSON body must be an object")
        return value

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        if self._send_static(path):
            return
        if path == "/":
            content = (WEB_DIR / "index.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(content)
            return
        if path == "/api/v1/health":
            self._json(200, {
                "ok": True, "service": "ai-desk",
                "mode": "phone-dry-run" if PROFILE == "phone-dry-run" else "dry-run",
            })
            return
        if not self._authorized():
            return
        if path == "/api/v1/capabilities":
            self._json(200, {"adapters": [
                {"id": "dry-run", "label": "Dry-run（仅模拟）", "directory_id": "demo"}
            ]})
            return
        if path == "/api/v1/tasks":
            try:
                limit = int(parse_qs(parsed.query).get("limit", ["50"])[0])
                limit = max(1, min(limit, 100))
            except ValueError:
                self._json(400, {"error": {"code": "INVALID_REQUEST", "message": "limit must be an integer"}})
                return
            # Filter at the storage layer: a phone never receives records from
            # a prior CLI/Codex profile even if DB_PATH was misconfigured.
            allowed_adapter = "dry-run" if PROFILE == "phone-dry-run" else None
            self._json(200, {"tasks": store.list_tasks(limit, adapter=allowed_adapter)})
            return
        if path.startswith("/api/v1/tasks/"):
            parts = path.strip("/").split("/")
            task_id = parts[3] if len(parts) >= 4 else ""
            task = store.get_task(task_id)
            if not task or not adapter_allowed(PROFILE, task["adapter"]):
                # Intentionally use the same response as an unknown ID.
                self._json(404, {"error": {"code": "TASK_NOT_FOUND", "message": "Task not found"}})
                return
            if len(parts) == 5 and parts[4] == "events":
                self._json(200, {"events": store.list_events(task_id)})
            elif len(parts) == 4:
                self._json(200, {"task": task})
            else:
                self._json(404, {"error": {"code": "NOT_FOUND", "message": "Route not found"}})
            return
        self._json(404, {"error": {"code": "NOT_FOUND", "message": "Route not found"}})

    def do_POST(self) -> None:
        if not self._authorized():
            return
        path = urlparse(self.path).path
        if path != "/api/v1/tasks":
            self._json(404, {"error": {"code": "NOT_FOUND", "message": "Route not found"}})
            return
        try:
            body = self._read_json()
        except ValueError as exc:
            self._json(400, {"error": {"code": "INVALID_REQUEST", "message": str(exc)}})
            return

        instruction = body.get("instruction")
        target = body.get("target_device_id", "mac-studio")
        adapter = body.get("adapter", "dry-run")
        directory_id = body.get("working_directory_id", "demo")
        idem = self.headers.get("Idempotency-Key", "")

        if not isinstance(instruction, str) or not instruction.strip() or len(instruction) > 4000:
            self._json(400, {"error": {"code": "INVALID_REQUEST", "message": "instruction must be 1-4000 characters"}})
            return
        if not isinstance(target, str) or target not in ("mac-studio",):
            self._json(400, {"error": {"code": "TARGET_NOT_ALLOWED", "message": "MVP only registers mac-studio"}})
            return
        if not isinstance(adapter, str) or not adapter_allowed(PROFILE, adapter):
            self._json(403, {"error": {
                "code": "EXECUTION_PROFILE_BLOCKED",
                "message": "Phone dry-run mode does not allow this adapter."
            }})
            return
        if adapter not in ("dry-run",):
            self._json(400, {"error": {"code": "ADAPTER_NOT_ALLOWED", "message": "MVP only enables dry-run"}})
            return
        if not isinstance(directory_id, str) or directory_id != "demo":
            self._json(400, {"error": {"code": "DIRECTORY_NOT_ALLOWED", "message": "MVP only enables the demo directory ID"}})
            return
        if not idem or len(idem) > 128:
            self._json(400, {"error": {"code": "IDEMPOTENCY_KEY_REQUIRED", "message": "Send a unique Idempotency-Key header"}})
            return

        task, created = store.create_task(
            instruction=instruction.strip(),
            target_device_id=target,
            adapter=adapter,
            working_directory_id=directory_id,
            idempotency_key=idem,
        )
        if not created and (
            task["instruction"] != instruction.strip()
            or task["target_device_id"] != target
            or task["adapter"] != adapter
            or task["working_directory_id"] != directory_id
        ):
            self._json(409, {"error": {
                "code": "IDEMPOTENCY_KEY_CONFLICT",
                "message": "This Idempotency-Key was already used for a different request."
            }})
            return

        if created:
            task_queue.put(task["id"])
        self._json(201 if created else 200, {"accepted": True, "created": created, "task": task})

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Allow", "GET, POST, OPTIONS")
        self.send_header("Content-Length", "0")
        self.end_headers()


def main() -> None:
    try:
        validate_profile(
            PROFILE, BIND, TOKEN, os.environ.get("AI_DESK_ENABLE_CODEX_READONLY", "")
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    is_loopback = BIND in ("127.0.0.1", "localhost", "::1")
    if not is_loopback:
        if len(TOKEN) < 32:
            raise SystemExit("Refusing non-loopback bind without a strong AI_DESK_TOKEN (at least 32 characters).")
        if not TLS_CERT or not TLS_KEY or not Path(TLS_CERT).is_file() or not Path(TLS_KEY).is_file():
            raise SystemExit("Refusing non-loopback bind without valid AI_DESK_TLS_CERT and AI_DESK_TLS_KEY files.")
    recover_tasks()
    worker = threading.Thread(target=worker_loop, name="ai-desk-worker", daemon=True)
    worker.start()
    server = ThreadingHTTPServer((BIND, PORT), Handler)
    scheme = "http"
    if not is_loopback:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(certfile=TLS_CERT, keyfile=TLS_KEY)
        server.socket = context.wrap_socket(server.socket, server_side=True)
        scheme = "https"
    print(f"AI Desk dry-run coordinator listening on {scheme}://{BIND}:{PORT}")
    print(f"Database: {DB_PATH}")
    server.serve_forever()


if __name__ == "__main__":
    main()
