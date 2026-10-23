import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).resolve().parents[1]


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class CoordinatorHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.port = free_port()
        cls.token = "test-token-for-local-suite-only"
        env = os.environ.copy()
        env["PYTHONPATH"] = str(REPO_ROOT / "server")
        env["AI_DESK_BIND"] = "127.0.0.1"
        env["AI_DESK_PORT"] = str(cls.port)
        env["AI_DESK_DB"] = str(Path(cls.temp.name) / "http-test.sqlite3")
        env["AI_DESK_TOKEN"] = cls.token
        cls.process = subprocess.Popen(
            [sys.executable, "-m", "ai_desk.server"],
            cwd=REPO_ROOT,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        cls.base = f"http://127.0.0.1:{cls.port}"
        deadline = time.time() + 8
        while time.time() < deadline:
            if cls.process.poll() is not None:
                raise RuntimeError("Coordinator exited before becoming healthy")
            try:
                with urlopen(cls.base + "/api/v1/health", timeout=0.5) as response:
                    if response.status == 200:
                        return
            except Exception:
                time.sleep(0.1)
        cls.process.terminate()
        raise RuntimeError("Coordinator did not become healthy")

    @classmethod
    def tearDownClass(cls):
        cls.process.terminate()
        try:
            cls.process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            cls.process.kill()
            cls.process.wait(timeout=3)
        cls.temp.cleanup()

    def request_json(self, path, *, method="GET", body=None, token=None, idem=None):
        headers = {}
        if token is not None:
            headers["Authorization"] = "Bearer " + token
        if body is not None:
            headers["Content-Type"] = "application/json"
        if idem is not None:
            headers["Idempotency-Key"] = idem
        data = json.dumps(body).encode() if body is not None else None
        req = Request(self.base + path, data=data, headers=headers, method=method)
        try:
            with urlopen(req, timeout=3) as response:
                return response.status, json.loads(response.read())
        except HTTPError as exc:
            return exc.code, json.loads(exc.read())

    def test_create_task_runs_only_dry_run(self):
        status, payload = self.request_json(
            "/api/v1/tasks",
            method="POST",
            token=self.token,
            idem="http-test-1",
            body={
                "instruction": "Check demo task",
                "target_device_id": "mac-studio",
                "adapter": "dry-run",
                "working_directory_id": "demo",
            },
        )
        self.assertEqual(status, 201)
        self.assertTrue(payload["accepted"])
        self.assertEqual(payload["task"]["status"], "queued")
        task_id = payload["task"]["id"]
        deadline = time.time() + 3
        final_task = None
        while time.time() < deadline:
            task_status, current = self.request_json(
                "/api/v1/tasks/" + task_id, token=self.token
            )
            self.assertEqual(task_status, 200)
            final_task = current["task"]
            if final_task["status"] in ("succeeded", "failed"):
                break
            time.sleep(0.02)
        self.assertIsNotNone(final_task)
        self.assertEqual(final_task["status"], "succeeded")
        self.assertIn("Dry-run accepted task", final_task["summary"])

    def test_missing_token_is_rejected(self):
        status, payload = self.request_json("/api/v1/tasks")
        self.assertEqual(status, 401)
        self.assertEqual(payload["error"]["code"], "UNAUTHENTICATED")

    def test_unknown_adapter_is_rejected(self):
        status, payload = self.request_json(
            "/api/v1/tasks",
            method="POST",
            token=self.token,
            idem="http-test-unknown-adapter",
            body={
                "instruction": "Do not execute this",
                "target_device_id": "mac-studio",
                "adapter": "shell",
                "working_directory_id": "demo",
            },
        )
        self.assertEqual(status, 400)
        self.assertEqual(payload["error"]["code"], "ADAPTER_NOT_ALLOWED")

    def test_idempotency_key_conflict_is_rejected(self):
        base = {
            "instruction": "First task",
            "target_device_id": "mac-studio",
            "adapter": "dry-run",
            "working_directory_id": "demo",
        }
        self.request_json("/api/v1/tasks", method="POST", token=self.token,
                          idem="conflict-key", body=base)
        changed = dict(base, instruction="Different task")
        status, payload = self.request_json(
            "/api/v1/tasks", method="POST", token=self.token,
            idem="conflict-key", body=changed,
        )
        self.assertEqual(status, 409)
        self.assertEqual(payload["error"]["code"], "IDEMPOTENCY_KEY_CONFLICT")

    def test_idempotency_does_not_duplicate(self):
        body = {
            "instruction": "Idempotency check",
            "target_device_id": "mac-studio",
            "adapter": "dry-run",
            "working_directory_id": "demo",
        }
        first_status, first = self.request_json(
            "/api/v1/tasks", method="POST", token=self.token,
            idem="same-http-key", body=body,
        )
        second_status, second = self.request_json(
            "/api/v1/tasks", method="POST", token=self.token,
            idem="same-http-key", body=body,
        )
        self.assertEqual(first_status, 201)
        self.assertEqual(second_status, 200)
        self.assertEqual(first["task"]["id"], second["task"]["id"])
        status, listing = self.request_json("/api/v1/tasks", token=self.token)
        self.assertEqual(status, 200)
        self.assertEqual(sum(t["id"] == first["task"]["id"] for t in listing["tasks"]), 1)


if __name__ == "__main__":
    unittest.main()
