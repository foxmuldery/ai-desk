"""Approved adapter registry. This MVP intentionally does not run shell commands."""
from __future__ import annotations

from typing import Any

from .codex_adapter import run_codex_readonly


class AdapterError(ValueError):
    pass


def run_dry_run(task: dict[str, Any]) -> dict[str, Any]:
    instruction = task["instruction"].strip()
    if not instruction:
        raise AdapterError("instruction must not be empty")
    return {
        "status": "succeeded",
        "summary": f"Dry-run accepted task for {task['target_device_id']}: {instruction[:180]}",
        "checks": [{"name": "input_validation", "status": "passed"}],
        "warnings": ["Dry-run only: no application or command was executed."],
    }


ADAPTERS = {
    "dry-run": run_dry_run,
    "codex-readonly": run_codex_readonly,
}


def run_adapter(adapter_id: str, task: dict[str, Any]) -> dict[str, Any]:
    adapter = ADAPTERS.get(adapter_id)
    if adapter is None:
        raise AdapterError(f"adapter not allowed: {adapter_id}")
    return adapter(task)
