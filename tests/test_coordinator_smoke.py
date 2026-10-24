"""Integration-test operator smoke harness without real Codex or network."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]


def make_fake_cli(*, event: str = "turn.completed", edit_lab: bool = False) -> str:
    return f'''#!/usr/bin/env python3
import json
import pathlib
import sys
args = sys.argv[1:]
if args[:3] != ["--ask-for-approval", "never", "exec"]:
    sys.exit(2)
if args[args.index("--sandbox") + 1] != "read-only":
    sys.exit(3)
if args[args.index("--cd") + 1] != str(pathlib.Path.cwd()):
    sys.exit(4)
sys.stdin.read()
if {edit_lab!r}:
    pathlib.Path("README.md").write_text("Changed by fake CLI", encoding="utf-8")
out_file = pathlib.Path(args[args.index("--output-last-message") + 1])
out_file.write_text("这是不含秘密的检查总结。", encoding="utf-8")
print(json.dumps({{"type": "{event}"}}))
'''


class CoordinatorSmokeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.lab = self.base / "lab"
        self.lab.mkdir()
        (self.lab / "README.md").write_text("Harmless test lab\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.lab), "init", "-q"], check=True)
        self.fake_cli = self.base / "codex"

    def tearDown(self):
        self.temp.cleanup()

    def execute(self, *, event="turn.completed", edit_lab=False):
        self.fake_cli.write_text(
            make_fake_cli(event=event, edit_lab=edit_lab),
            encoding="utf-8"
        )
        self.fake_cli.chmod(0o700)
        env = os.environ.copy()
        env["AI_DESK_CODEX_READONLY_ROOT"] = str(self.lab)
        env["AI_DESK_CODEX_BIN"] = str(self.fake_cli)
        env["AI_DESK_ENABLE_CODEX_READONLY"] = "0"  # smoke must explicitly override this
        env["AI_DESK_BIND"] = "0.0.0.0"  # smoke must explicitly override this
        return subprocess.run(
            [sys.executable, str(REPO / "scripts" / "smoke-coordinator-codex.py")],
            cwd=REPO,
            env=env,
            capture_output=True,
            text=True,
            timeout=25,
        )

    def test_uses_loopback_and_returns_success_for_completed_turn(self):
        result = self.execute()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("GIT_UNCHANGED", result.stdout)
        self.assertIn("COORDINATOR_SMOKE_OK", result.stdout)
        self.assertNotIn("这是不含秘密的检查总结", result.stdout)

    def test_marks_failed_event_as_failed(self):
        result = self.execute(event="turn.failed")
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("COORDINATOR_SMOKE_FAIL: TASK_CODEX_TURN_FAILED", result.stdout)
        self.assertIn("GIT_UNCHANGED", result.stdout)

    def test_detects_modified_lab(self):
        result = self.execute(edit_lab=True)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("COORDINATOR_SMOKE_FAIL: LAB_CONTENT_CHANGED", result.stdout)


if __name__ == "__main__":
    unittest.main()
