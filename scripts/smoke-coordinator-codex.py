#!/usr/bin/env python3
"""Mac Studio local-only Coordinator -> real Codex read-only smoke test.

Operator-run only. Does not expose an external interface, modify project files,
or print credentials, raw Codex transcripts or private workspace paths.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


REPO = Path(__file__).resolve().parents[1]
LAB_ID = "codex-lab"
PROMPT = (
    "只读检查当前独立 Git 测试仓库的 README.md，"
    "用一句中文概括其内容。不要修改、创建或删除文件；"
    "不要读取测试仓库以外的内容，也不要输出任何凭据。"
)


def report(code: str, *, success: bool = False) -> int:
    print("COORDINATOR_SMOKE_OK" if success else f"COORDINATOR_SMOKE_FAIL: {code}")
    return 0 if success else 1


def snapshot(root: Path) -> tuple[str, str]:
    status = subprocess.check_output(
        ["git", "-C", str(root), "status", "--porcelain", "--untracked-files=all"],
        text=True, stderr=subprocess.DEVNULL, timeout=5,
    )
    data = (root / "README.md").read_bytes()
    return status, hashlib.sha256(data).hexdigest()


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def get_json(base: str, endpoint: str, token: str | None = None,
             *, data: dict | None = None, idem: str | None = None) -> tuple[int, dict]:
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if idem:
        headers["Idempotency-Key"] = idem
    raw = json.dumps(data, ensure_ascii=False).encode("utf-8") if data is not None else None
    if raw is not None:
        headers["Content-Type"] = "application/json"
    request = Request(
        base + endpoint, data=raw, method="POST" if raw is not None else "GET",
        headers=headers,
    )
    try:
        with urlopen(request, timeout=5) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        return error.code, json.loads(error.read().decode("utf-8"))


def main() -> int:
    path = os.environ.get("AI_DESK_CODEX_READONLY_ROOT", "").strip()
    root = Path(path).expanduser() if path else Path.home() / "AI-Desk-Sandbox"
    if not root.is_dir() or not (root / ".git").exists() or not (root / "README.md").is_file():
        return report("LAB_REPO_MISSING")
    try:
        before = snapshot(root)
    except (OSError, subprocess.SubprocessError):
        return report("LAB_SNAPSHOT_FAILED")

    port = free_port()
    base = f"http://127.0.0.1:{port}"
    token = secrets.token_urlsafe(32)
    # Never inherit a caller-configured public bind, TLS endpoint or API token.
    env = os.environ.copy()
    env.update({
        "PYTHONPATH": str(REPO / "server"),
        "AI_DESK_BIND": "127.0.0.1",
        "AI_DESK_PORT": str(port),
        "AI_DESK_ENABLE_CODEX_READONLY": "1",
        "AI_DESK_CODEX_READONLY_ROOT": str(root.resolve()),
        "AI_DESK_CODEX_TIMEOUT": "120",
        "AI_DESK_TOKEN": token,
    })
    env.pop("AI_DESK_TLS_CERT", None)
    env.pop("AI_DESK_TLS_KEY", None)
    print("COORDINATOR_SMOKE_START: loopback-only service with temporary database")
    print("Only the isolated lab is used. No task details or tokens will be printed.")

    with tempfile.TemporaryDirectory(prefix="ai-desk-integration-") as tmp:
        env["AI_DESK_DB"] = str(Path(tmp) / "coordinator.sqlite3")
        with open(os.devnull, "wb") as sink:
            process = subprocess.Popen(
                [sys.executable, "-m", "ai_desk.server"],
                cwd=REPO, env=env, stdin=subprocess.DEVNULL,
                stdout=sink, stderr=sink, start_new_session=True,
            )
            task: dict | None = None
            failure: str | None = None
            try:
                deadline = time.monotonic() + 12
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        failure = "COORDINATOR_START_FAILED"
                        break
                    try:
                        status, health = get_json(base, "/api/v1/health")
                        if status == 200 and health.get("ok"):
                            break
                    except (OSError, ValueError):
                        time.sleep(0.10)
                else:
                    failure = "COORDINATOR_HEALTH_TIMEOUT"

                if not failure:
                    status, caps = get_json(base, "/api/v1/capabilities", token)
                    enabled = status == 200 and any(
                        x.get("id") == "codex-readonly" and x.get("directory_id") == LAB_ID
                        for x in caps.get("adapters", [])
                    )
                    if not enabled:
                        failure = "CODEX_ADAPTER_NOT_ADVERTISED"

                if not failure:
                    status, accepted = get_json(
                        base, "/api/v1/tasks", token,
                        data={
                            "instruction": PROMPT,
                            "target_device_id": "mac-studio",
                            "adapter": "codex-readonly",
                            "working_directory_id": LAB_ID,
                        },
                        idem=secrets.token_hex(20),
                    )
                    if status != 201 or not accepted.get("accepted"):
                        failure = "TASK_NOT_ACCEPTED"
                    else:
                        task_id = accepted["task"]["id"]
                        deadline = time.monotonic() + 145
                        while time.monotonic() < deadline:
                            _, response = get_json(base, "/api/v1/tasks/" + task_id, token)
                            task = response.get("task")
                            if isinstance(task, dict) and task.get("status") in (
                                "succeeded", "failed", "unknown", "cancelled"
                            ):
                                break
                            time.sleep(0.30)
                        else:
                            failure = "TASK_POLL_TIMEOUT"

                if not failure and (not task or task.get("status") != "succeeded"):
                    raw_code = task.get("error_code") if isinstance(task, dict) else None
                    safe_code = re.sub("[^A-Z0-9_]", "_", str(raw_code or "UNKNOWN"))[:64]
                    failure = "TASK_" + safe_code
                if not failure and task:
                    status, data = get_json(
                        base, "/api/v1/tasks/" + task["id"] + "/events", token
                    )
                    types = [x.get("event_type") for x in data.get("events", [])]
                    if status != 200 or "adapter.result" not in types:
                        failure = "AUDIT_EVENT_MISSING"
            except (OSError, URLError, ValueError, KeyError, TimeoutError):
                failure = "HTTP_OR_PROTOCOL_ERROR"
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=8)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)

    try:
        after = snapshot(root)
    except (OSError, subprocess.SubprocessError):
        return report("LAB_RECHECK_FAILED")

    if before != after:
        return report("LAB_CONTENT_CHANGED")
    print("GIT_UNCHANGED")
    return report(failure or "", success=failure is None)


if __name__ == "__main__":
    raise SystemExit(main())
