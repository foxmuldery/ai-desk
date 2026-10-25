"""Fake-CLI tests for the operator's read-only Mac smoke script.

No real Codex authentication, network, or user files are accessed.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

FAKE_CODEX = r'''#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys

args = sys.argv[1:]
# Stand in for the real Codex CLI parser. Global flags after "exec"
# are rejected with exit code 2 on the user's reported CLI version.
if args[:3] != ["--ask-for-approval", "never", "exec"]:
    print("error: unexpected argument '--ask-for-approval' found", file=sys.stderr)
    sys.exit(2)
sys.stdin.read()
mode = os.environ.get("FAKE_MODE", "success")
if mode == "exit":
    sys.exit(7)
if mode == "modify":
    # Emulate Codex's --cd behavior, rather than writing in the test runner cwd.
    workspace = Path(args[args.index("--cd") + 1])
    workspace.joinpath("README.md").write_text("Modified!", encoding="utf-8")
out_path = Path(args[args.index("--output-last-message") + 1])
out_path.write_text("仅用于测试的中文总结。", encoding="utf-8")
print(json.dumps({"type": "turn.failed" if mode == "failed-event" else "turn.completed"}))
'''


class ReadOnlySmokeScriptTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.lab = self.root / "lab"
        self.lab.mkdir()
        subprocess.run(
            ["git", "-C", str(self.lab), "init", "-q"],
            check=True, capture_output=True,
        )
        (self.lab / "README.md").write_text("Harmless test content.\n", encoding="utf-8")
        self.bin_dir = self.root / "bin"
        self.bin_dir.mkdir()
        self.fake_codex = self.bin_dir / "codex"
        self.fake_codex.write_text(FAKE_CODEX, encoding="utf-8")
        self.fake_codex.chmod(0o700)

    def tearDown(self):
        self.tmp.cleanup()

    def run_script(self, mode="success"):
        env = os.environ.copy()
        env.update({
            "PATH": str(self.bin_dir) + os.pathsep + env.get("PATH", ""),
            "AI_DESK_CODEX_READONLY_ROOT": str(self.lab),
            "FAKE_MODE": mode,
        })
        return subprocess.run(
            ["sh", str(ROOT / "scripts" / "smoke-codex-readonly.sh")],
            cwd=ROOT, env=env, capture_output=True, text=True, timeout=10,
        )

    def test_succeeds_with_valid_completion_without_edits(self):
        result = self.run_script("success")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("SMOKE_OK", result.stdout)
        self.assertIn("GIT_UNCHANGED", result.stdout)

    def test_fails_when_codex_attempts_to_modify_lab(self):
        result = self.run_script("modify")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("test repository changed", result.stdout)

    def test_fails_without_completion(self):
        result = self.run_script("failed-event")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("SMOKE_FAIL", result.stdout)

    def test_fails_for_nonzero_codex_exit(self):
        result = self.run_script("exit")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("CODEX_EXIT_7", result.stdout)


if __name__ == "__main__":
    unittest.main()
