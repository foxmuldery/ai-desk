"""Explicitly enabled, read-only Codex CLI adapter.

This is a *local* operator-controlled integration, not a general remote shell.
It deliberately accepts no workspace paths or command-line flags from tasks.
"""
from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import tempfile
from pathlib import Path
from typing import Any


WORKSPACE_ID = "codex-lab"
MAX_EVENT_BYTES = 1_048_576
MAX_FINAL_BYTES = 8_192


class CodexConfigurationError(ValueError):
    """Invalid, missing or disabled local Codex configuration."""


def enabled() -> bool:
    return os.getenv("AI_DESK_ENABLE_CODEX_READONLY") == "1"


def workspace_for(workspace_id: str) -> Path:
    """Resolve only the operator-configured lab directory, never a task-supplied path."""
    if not enabled():
        raise CodexConfigurationError("Codex read-only adapter is disabled")
    if workspace_id != WORKSPACE_ID:
        raise CodexConfigurationError("Unregistered Codex workspace ID")
    raw = os.getenv("AI_DESK_CODEX_READONLY_ROOT", "")
    candidate = Path(raw).expanduser()
    if not raw or not candidate.is_absolute() or not candidate.is_dir():
        raise CodexConfigurationError("AI_DESK_CODEX_READONLY_ROOT must be an existing absolute directory")
    resolved = candidate.resolve(strict=True)
    if not (resolved / ".git").exists():
        raise CodexConfigurationError("Codex workspace must be an initialized Git repository")
    return resolved


def codex_binary() -> str:
    """Use the local CLI installed for the logged-in user."""
    override = os.getenv("AI_DESK_CODEX_BIN")
    cli = override if override else shutil.which("codex")
    if not cli:
        raise CodexConfigurationError("Codex CLI not found in PATH")
    if override and not Path(override).is_absolute():
        raise CodexConfigurationError("AI_DESK_CODEX_BIN must be an absolute path")
    if not os.access(cli, os.X_OK):
        raise CodexConfigurationError("Codex CLI path is not executable")
    return str(cli)


def _text_bytes(path: Path, maximum: int) -> str | None:
    """Read a bounded file; return None if the command produced too much text."""
    if not path.exists() or path.stat().st_size > maximum:
        return None
    return path.read_bytes().decode("utf-8", errors="replace")


def _exit_result(code: str, summary: str) -> dict[str, Any]:
    return {
        "status": "failed",
        "error_code": code,
        "summary": summary,
        "checks": [{"name": "codex_readonly_execution", "status": "failed"}],
    }


def run_codex_readonly(task: dict[str, Any]) -> dict[str, Any]:
    """Run one bounded noninteractive Codex turn; never request write access.

    Success requires a zero exit status, a JSONL turn.completed event and a
    nonempty bounded final message. Nothing in stdout/stderr is included in the
    task record except this brief final summary.
    """
    try:
        if task.get("target_device_id") != "mac-studio":
            raise CodexConfigurationError("Codex adapter is available only on Mac Studio")
        workspace = workspace_for(str(task.get("working_directory_id", "")))
        binary = codex_binary()
        prompt = task.get("instruction")
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 4000:
            raise CodexConfigurationError("Invalid instruction length")
        timeout = max(30, min(600, int(os.getenv("AI_DESK_CODEX_TIMEOUT", "180"))))
    except (CodexConfigurationError, ValueError) as exc:
        return _exit_result("CODEX_CONFIG", str(exc))

    instruction = (
        "You are assisting in an explicitly READ-ONLY inspection task. "
        "Do not modify, delete or create project files, run deployments, "
        "push commits, access unrelated files, or transmit secrets. "
        "If the user asks for changes, explain how you would make them "
        "rather than performing them. Return a concise Chinese summary.\n\n"
        "User request:\n" + prompt.strip()
    )

    with tempfile.TemporaryDirectory(prefix="ai-desk-codex-") as directory:
        artifacts = Path(directory)
        output_file = artifacts / "final.txt"
        stdout_file = artifacts / "events.jsonl"
        stderr_file = artifacts / "stderr.txt"
        argv = [
            binary,
            "exec",
            "--ignore-user-config",
            "--ephemeral",
            "--sandbox", "read-only",
            "--ask-for-approval", "never",
            "--json",
            "--cd", str(workspace),
            "--output-last-message", str(output_file),
            "-",
        ]

        try:
            with stdout_file.open("wb") as out, stderr_file.open("wb") as err:
                process = subprocess.Popen(
                    argv,
                    cwd=workspace,
                    stdin=subprocess.PIPE,
                    stdout=out,
                    stderr=err,
                    shell=False,
                    start_new_session=True,
                )
                try:
                    process.communicate(input=instruction.encode("utf-8"), timeout=timeout)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    process.communicate()
                    return _exit_result("CODEX_TIMEOUT", "Codex 超过允许执行时间，任务已终止。")
        except (OSError, subprocess.SubprocessError):
            return _exit_result("CODEX_START_FAILED", "Codex CLI 无法启动，请检查本机安装与权限。")

        if process.returncode != 0:
            return _exit_result("CODEX_EXIT_NONZERO", "Codex 执行失败。请在 Mac Studio 本地检查运行环境。")

        events = _text_bytes(stdout_file, MAX_EVENT_BYTES)
        summary = _text_bytes(output_file, MAX_FINAL_BYTES)
        if events is None or summary is None:
            return _exit_result("CODEX_OUTPUT_LIMIT", "Codex 输出超出安全长度限制。")

        event_types: list[str] = []
        try:
            for line in events.splitlines():
                if line.strip():
                    value = json.loads(line)
                    if not isinstance(value, dict):
                        raise ValueError("Unexpected JSONL event")
                    event_types.append(str(value.get("type", "")))
        except (ValueError, json.JSONDecodeError):
            return _exit_result("CODEX_INVALID_JSONL", "Codex 没有产生有效的结构化执行事件。")

        if "turn.failed" in event_types or "error" in event_types:
            return _exit_result("CODEX_TURN_FAILED", "Codex 报告执行失败。")
        if "turn.completed" not in event_types:
            return _exit_result("CODEX_INCOMPLETE", "Codex 未确认任务已正常完成。")
        if not summary or not summary.strip():
            return _exit_result("CODEX_EMPTY_RESULT", "Codex 没有返回可以核对的任务总结。")

        # Summaries are intentionally capped; event logs and stderr are never
        # forwarded to the phone. Authentication stays in the local Codex CLI.
        return {
            "status": "succeeded",
            "summary": summary.strip()[:1200],
            "checks": [
                {"name": "process_exit", "status": "passed"},
                {"name": "codex_turn_completed", "status": "passed"},
            ],
            "warnings": ["Read-only Codex task; no project edits were authorized."],
        }
