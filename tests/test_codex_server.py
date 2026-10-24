"""Full Coordinator -> fake Codex subprocess integration; no real Codex/network."""
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
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]

FAKE_CODEX = '''#!/usr/bin/env python3
import json
import pathlib
import sys

args = sys.argv[1:]
message = pathlib.Path(args[args.index("--output-last-message") + 1])
request = sys.stdin.read()
message.write_text("真实适配器流程测试：" + ("通过" if "README" in request else "失败"), encoding="utf-8")
print(json.dumps({"type": "turn.started"}))
print(json.dumps({"type": "turn.completed"}))
'''


class CodexCoordinatorTests(unittest.TestCase):
    def test_local_only_codex_route_uses_fake_cli(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "ai-desk-sandbox"
            workspace.mkdir()
            (workspace / ".git").mkdir()
            (workspace / "README.md").write_text("Harmless sandbox", encoding="utf-8")

            codex = root / "codex"
            codex.write_text(FAKE_CODEX, encoding="utf-8")
            codex.chmod(0o700)

            with socket.socket() as candidate:
                candidate.bind(("127.0.0.1", 0))
                port = candidate.getsockname()[1]

            token = "integration-test-token-only"
            env = os.environ.copy()
            env.update({
                "PYTHONPATH": str(ROOT / "server"),
                "AI_DESK_BIND": "127.0.0.1",
                "AI_DESK_PORT": str(port),
                "AI_DESK_DB": str(root / "test.sqlite3"),
                "AI_DESK_TOKEN": token,
                "AI_DESK_ENABLE_CODEX_READONLY": "1",
                "AI_DESK_CODEX_READONLY_ROOT": str(workspace),
                "AI_DESK_CODEX_BIN": str(codex),
            })
            process = subprocess.Popen(
                [sys.executable, "-m", "ai_desk.server"],
                cwd=ROOT,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            base = f"http://127.0.0.1:{port}"
            headers = {"Authorization": "Bearer " + token}
            try:
                until = time.time() + 8
                while time.time() < until:
                    if process.poll() is not None:
                        self.fail("Coordinator stopped before the health endpoint responded")
                    try:
                        with urlopen(base + "/api/v1/health", timeout=0.25) as response:
                            if response.status == 200:
                                break
                    except OSError:
                        time.sleep(0.05)
                else:
                    self.fail("Coordinator did not become healthy")

                caps = Request(base + "/api/v1/capabilities", headers=headers)
                with urlopen(caps, timeout=3) as response:
                    capabilities = json.load(response)
                self.assertIn("codex-readonly", [a["id"] for a in capabilities["adapters"]])
                payload = json.dumps({
                    "instruction": "请只读检查 README。",
                    "target_device_id": "mac-studio",
                    "adapter": "codex-readonly",
                    "working_directory_id": "codex-lab",
                }).encode("utf-8")
                req = Request(
                    base + "/api/v1/tasks",
                    data=payload,
                    method="POST",
                    headers={
                        **headers,
                        "Content-Type": "application/json",
                        "Idempotency-Key": "fake-codex-integration-1",
                    },
                )
                with urlopen(req, timeout=3) as response:
                    self.assertEqual(response.status, 201)
                    accepted = json.load(response)
                self.assertEqual(accepted["task"]["status"], "queued")
                task_id = accepted["task"]["id"]

                until = time.time() + 5
                while time.time() < until:
                    detail = Request(base + "/api/v1/tasks/" + task_id, headers=headers)
                    with urlopen(detail, timeout=3) as response:
                        task = json.load(response)["task"]
                    if task["status"] in ("succeeded", "failed"):
                        break
                    time.sleep(0.05)
                self.assertEqual(task["status"], "succeeded", task)
                self.assertIn("真实适配器流程测试", task["summary"])
                self.assertEqual(task["adapter"], "codex-readonly")
            finally:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3)


if __name__ == "__main__":
    unittest.main()
