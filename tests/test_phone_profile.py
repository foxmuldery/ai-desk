"""Regression gates for mobile dry-run profile and proxy-safe backend authorization."""
from __future__ import annotations

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

from ai_desk.policy import adapter_allowed, validate_profile
from ai_desk.store import TaskStore

REPO = Path(__file__).resolve().parents[1]
TOKEN = "test-only-phone-dryrun-token-32-characters"


def available_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def request_json(base, path, *, token=None, body=None, key=None, headers=None):
    headers = dict(headers or {})
    if token is not None:
        headers["Authorization"] = "Bearer " + token
    if key is not None:
        headers["Idempotency-Key"] = key
    if body is not None:
        headers["Content-Type"] = "application/json"
    payload = json.dumps(body).encode("utf-8") if body is not None else None
    request = Request(
        base + path, data=payload,
        headers=headers, method="POST" if payload is not None else "GET"
    )
    try:
        with urlopen(request, timeout=3) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        return error.code, json.load(error)


class PhonePolicyUnitTests(unittest.TestCase):
    def test_phone_profile_only_allows_dry_run(self):
        self.assertTrue(adapter_allowed("phone-dry-run", "dry-run"))
        for adapter in ("codex-readonly", "shell", "codex-write", "other"):
            self.assertFalse(adapter_allowed("phone-dry-run", adapter))

    def test_proxy_client_ip_does_not_enter_policy(self):
        # This policy ignores the apparent IP / X-Forwarded-For / URL origin;
        # even requests forwarded onto loopback cannot run Codex.
        self.assertFalse(adapter_allowed("phone-dry-run", "codex-readonly"))

    def test_phone_profile_is_fail_closed_for_untrusted_settings(self):
        for profile, bind, token, codex_opt_in in (
            ("wrong-profile", "127.0.0.1", TOKEN, "0"),
            ("phone-dry-run", "0.0.0.0", TOKEN, "0"),
            ("phone-dry-run", "127.0.0.1", "short", "0"),
            ("phone-dry-run", "127.0.0.1", TOKEN, "1"),
        ):
            with self.subTest(profile=profile, bind=bind, codex_opt_in=codex_opt_in):
                with self.assertRaises(ValueError):
                    validate_profile(profile, bind, token, codex_opt_in)

        validate_profile("phone-dry-run", "127.0.0.1", TOKEN, "0")


class PhoneProfileHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.database = Path(cls.temp.name) / "phone-test.sqlite3"
        cls.port = available_port()
        cls.base = "http://127.0.0.1:" + str(cls.port)

        # Pre-existing queued work from a different execution profile must
        # never run merely because this mobile service recovers the database.
        store = TaskStore(cls.database)
        cls.blocked_task, _ = store.create_task(
            instruction="Attempt Codex call from old persisted queue",
            target_device_id="mac-studio",
            adapter="codex-readonly",
            working_directory_id="codex-lab",
            idempotency_key="seeded-disabled-task",
        )

        env = os.environ.copy()
        env.update({
            "PYTHONPATH": str(REPO / "server"),
            "AI_DESK_BIND": "127.0.0.1",
            "AI_DESK_PORT": str(cls.port),
            "AI_DESK_DB": str(cls.database),
            "AI_DESK_TOKEN": TOKEN,
            "AI_DESK_EXECUTION_PROFILE": "phone-dry-run",
            "AI_DESK_ENABLE_CODEX_READONLY": "0",
        })
        env.pop("AI_DESK_TLS_CERT", None)
        env.pop("AI_DESK_TLS_KEY", None)
        cls.process = subprocess.Popen(
            [sys.executable, "-m", "ai_desk.server"],
            cwd=REPO, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        deadline = time.monotonic() + 6
        while time.monotonic() < deadline:
            if cls.process.poll() is not None:
                raise RuntimeError("Phone dry-run coordinator exited during startup")
            try:
                response = request_json(cls.base, "/api/v1/health")
                if response[0] == 200:
                    break
            except OSError:
                time.sleep(0.05)
        else:
            cls.process.terminate()
            cls.process.wait(timeout=3)
            raise RuntimeError("Phone dry-run service did not become healthy")

    @classmethod
    def tearDownClass(cls):
        cls.process.terminate()
        try:
            cls.process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            cls.process.kill()
            cls.process.wait(timeout=3)
        cls.temp.cleanup()

    def test_profile_report_and_capabilities(self):
        status, health = request_json(self.base, "/api/v1/health")
        self.assertEqual(status, 200)
        self.assertEqual(health["mode"], "phone-dry-run")
        status, capabilities = request_json(self.base, "/api/v1/capabilities", token=TOKEN)
        self.assertEqual(status, 200)
        self.assertEqual([x["id"] for x in capabilities["adapters"]], ["dry-run"])

    def test_capabilities_require_authentication(self):
        status, error = request_json(self.base, "/api/v1/capabilities")
        self.assertEqual(status, 401)
        self.assertEqual(error["error"]["code"], "UNAUTHENTICATED")

    def test_dry_run_task_completes(self):
        status, accepted = request_json(
            self.base, "/api/v1/tasks", token=TOKEN, key="phone-dryrun-test",
            body={
                "instruction": "Phone check: harmless simulated task",
                "target_device_id": "mac-studio",
                "adapter": "dry-run",
                "working_directory_id": "demo",
            },
        )
        self.assertEqual(status, 201)
        task_id = accepted["task"]["id"]
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            _, result = request_json(self.base, "/api/v1/tasks/" + task_id, token=TOKEN)
            if result["task"]["status"] in ("succeeded", "failed"):
                break
            time.sleep(0.02)
        self.assertEqual(result["task"]["status"], "succeeded")
        self.assertEqual(result["task"]["adapter"], "dry-run")

    def test_spoofed_proxy_request_cannot_run_codex(self):
        status, result = request_json(
            self.base, "/api/v1/tasks", token=TOKEN, key="phone-codex-denied",
            headers={
                "X-Forwarded-For": "127.0.0.1",
                "X-Forwarded-Proto": "https",
                "X-Real-IP": "127.0.0.1",
            },
            body={
                "instruction": "Do a forbidden real Codex task",
                "target_device_id": "mac-studio",
                "adapter": "codex-readonly",
                "working_directory_id": "codex-lab",
            },
        )
        self.assertEqual(status, 403)
        self.assertEqual(result["error"]["code"], "EXECUTION_PROFILE_BLOCKED")

    def test_recovered_old_task_is_blocked_before_execution(self):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            _, result = request_json(
                self.base, "/api/v1/tasks/" + self.blocked_task["id"], token=TOKEN
            )
            if result["task"]["status"] != "queued":
                break
            time.sleep(0.02)
        self.assertEqual(result["task"]["status"], "failed")
        self.assertEqual(result["task"]["error_code"], "EXECUTION_PROFILE_BLOCKED")
        _, audit = request_json(
            self.base, "/api/v1/tasks/" + self.blocked_task["id"] + "/events",
            token=TOKEN,
        )
        self.assertIn("policy.blocked", [x["event_type"] for x in audit["events"]])


if __name__ == "__main__":
    unittest.main()
