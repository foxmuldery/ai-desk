"""Hermetic tests for the real Codex adapter (never use a real login/network)."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ai_desk.codex_adapter import (
    CodexConfigurationError,
    WORKSPACE_ID,
    run_codex_readonly,
    workspace_for,
)


FAKE_CLI = '''#!/usr/bin/env python3
import json
import os
import pathlib
import sys

args = sys.argv[1:]
# Mimic codex-cli argument parser: approval flag is global and must
# precede exec. Old smoke/adapter code accidentally placed it after exec.
if (len(args) < 4 or args[0:3] != ["--ask-for-approval", "never", "exec"]):
    print("error: unexpected argument '--ask-for-approval' found", file=sys.stderr)
    sys.exit(2)
prompt = sys.stdin.read()
pathlib.Path(__CAPTURE_PATH__).write_text(
    json.dumps({
        "args": args,
        "prompt": prompt,
        "coordinator_token_visible": "AI_DESK_TOKEN" in os.environ,
        "provider_key_visible": "OPENAI_API_KEY" in os.environ,
    }),
    encoding="utf-8",
)
if "--output-last-message" not in args:
    sys.exit(2)
outpath = pathlib.Path(args[args.index("--output-last-message") + 1])
outpath.write_text("检查完成，没有修改任何文件。", encoding="utf-8")
print(json.dumps({"type": __EVENT_TYPE__}), flush=True)
sys.exit(__EXIT_CODE__)
'''


class CodexReadOnlyAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.workspace = self.root / "ai-desk-sandbox"
        self.workspace.mkdir()
        (self.workspace / ".git").mkdir()
        self.fake_cli = self.root / "codex"
        self.capture = self.root / "capture.json"
        self._write_cli()
        self.original_env = patch.dict(os.environ, {
            "AI_DESK_ENABLE_CODEX_READONLY": "1",
            "AI_DESK_CODEX_READONLY_ROOT": str(self.workspace),
            "AI_DESK_CODEX_BIN": str(self.fake_cli),
            "AI_DESK_CODEX_TIMEOUT": "30",
            "AI_DESK_TOKEN": "must-not-inherit-this-secret",
            "OPENAI_API_KEY": "must-not-inherit-provider-secret",
        })
        self.original_env.start()

    def _write_cli(self, *, event="turn.completed", exit_code=0):
        self.fake_cli.write_text(
            FAKE_CLI.replace("__CAPTURE_PATH__", repr(str(self.capture)))
                    .replace("__EVENT_TYPE__", repr(event))
                    .replace("__EXIT_CODE__", str(exit_code)),
            encoding="utf-8",
        )
        self.fake_cli.chmod(0o700)

    def tearDown(self):
        self.original_env.stop()
        self.temp.cleanup()

    def task(self):
        return {
            "instruction": "请检查测试仓库有哪些文件。",
            "target_device_id": "mac-studio",
            "working_directory_id": WORKSPACE_ID,
            "adapter": "codex-readonly",
        }

    def test_disabled_without_explicit_opt_in(self):
        with patch.dict(os.environ, {"AI_DESK_ENABLE_CODEX_READONLY": "0"}):
            result = run_codex_readonly(self.task())
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["error_code"], "CODEX_CONFIG")

    def test_workspace_id_and_git_repository_are_required(self):
        with self.assertRaises(CodexConfigurationError):
            workspace_for("../other-directory")
        (self.workspace / ".git").rmdir()
        with self.assertRaises(CodexConfigurationError):
            workspace_for(WORKSPACE_ID)

    def test_invokes_codex_via_stdin_with_readonly_sandbox(self):
        result = run_codex_readonly(self.task())
        self.assertEqual(result["status"], "succeeded")
        self.assertIn("检查完成", result["summary"])
        capture = json.loads(self.capture.read_text(encoding="utf-8"))
        args = capture["args"]
        self.assertEqual(args[:3], ["--ask-for-approval", "never", "exec"])
        self.assertIn("--ignore-user-config", args)
        self.assertIn("--ephemeral", args)
        self.assertEqual(args[args.index("--sandbox") + 1], "read-only")
        self.assertEqual(args[args.index("--ask-for-approval") + 1], "never")
        self.assertEqual(args[args.index("--cd") + 1], str(self.workspace))
        self.assertEqual(args[-1], "-")
        self.assertIn("请检查测试仓库有哪些文件。", capture["prompt"])
        self.assertNotIn("请检查测试仓库有哪些文件。", args)
        self.assertFalse(capture["coordinator_token_visible"])
        self.assertFalse(capture["provider_key_visible"])

    def test_nonzero_cli_exit_is_failure(self):
        self._write_cli(exit_code=1)
        result = run_codex_readonly(self.task())
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["error_code"], "CODEX_EXIT_NONZERO")

    def test_turn_failure_is_not_success_even_with_exit_zero(self):
        self._write_cli(event="turn.failed")
        result = run_codex_readonly(self.task())
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["error_code"], "CODEX_TURN_FAILED")

    def test_unregistered_computer_is_rejected(self):
        task = dict(self.task(), target_device_id="mac-mini")
        result = run_codex_readonly(task)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["error_code"], "CODEX_CONFIG")


if __name__ == "__main__":
    unittest.main()
