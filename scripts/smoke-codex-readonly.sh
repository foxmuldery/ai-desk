#!/bin/sh
# Safe, disposable read-only smoke test of the user's existing Codex CLI.
# Run only on the user's Mac Studio after checking the isolated test repository.
# Never runs a shell command from untrusted user input.
set -eu
umask 077

ROOT="${AI_DESK_CODEX_READONLY_ROOT:-$HOME/AI-Desk-Sandbox}"
case "$ROOT" in
    /*) ;;
    *) printf '%s\n' 'PREFLIGHT_FAIL: workspace path must be absolute'; exit 2 ;;
esac

if ! command -v codex >/dev/null 2>&1; then
    printf '%s\n' 'PREFLIGHT_FAIL: codex executable not found'; exit 2
fi
if ! command -v python3 >/dev/null 2>&1; then
    printf '%s\n' 'PREFLIGHT_FAIL: python3 executable not found'; exit 2
fi
if ! command -v git >/dev/null 2>&1; then
    printf '%s\n' 'PREFLIGHT_FAIL: git executable not found'; exit 2
fi
if [ ! -e "$ROOT/.git" ] || [ ! -f "$ROOT/README.md" ]; then
    printf '%s\n' 'PREFLIGHT_FAIL: use a separate initialized Git lab with a harmless README.md'; exit 2
fi

# Compare both Git status and README checksum before/after the CLI turn.
before_status="$(git -C "$ROOT" status --porcelain --untracked-files=all)"
before_hash="$(shasum -a 256 "$ROOT/README.md" | awk '{print $1}')"
tmp="$(mktemp -d "${TMPDIR:-/tmp}/ai-desk-readonly.XXXXXXXX")"
trap 'rm -rf "$tmp"' EXIT HUP INT TERM

printf '%s\n' 'SMOKE_START: Codex read-only inspection of isolated test README.'
printf '%s\n' 'This calls the logged-in Codex service once; no project edits are authorized.'

if printf '%s\n' '只阅读当前测试 Git 仓库中的 README.md，写一句简短中文总结。不要创建、删除或修改文件，不要访问其他目录，不要执行部署，也不要输出任何密钥或用户个人信息。' |
    codex exec \
        --ignore-user-config \
        --ephemeral \
        --sandbox read-only \
        --ask-for-approval never \
        --json \
        --cd "$ROOT" \
        --output-last-message "$tmp/final.txt" \
        - >"$tmp/events.jsonl" 2>"$tmp/stderr.log"
then
    cli_exit=0
else
    cli_exit=$?
fi

after_status="$(git -C "$ROOT" status --porcelain --untracked-files=all)"
after_hash="$(shasum -a 256 "$ROOT/README.md" | awk '{print $1}')"

if [ "$before_status" != "$after_status" ] || [ "$before_hash" != "$after_hash" ]; then
    printf '%s\n' 'SMOKE_FAIL: test repository changed; stop and inspect locally'
    exit 1
fi
printf '%s\n' 'GIT_UNCHANGED'

if [ "$cli_exit" -ne 0 ]; then
    printf 'SMOKE_FAIL: CODEX_EXIT_%s (inspect CLI/network locally; never post credentials)\n' "$cli_exit"
    exit 1
fi

if python3 - "$tmp/events.jsonl" "$tmp/final.txt" <<'PY'
import json
import pathlib
import sys

events_path = pathlib.Path(sys.argv[1])
last_path = pathlib.Path(sys.argv[2])
if not events_path.exists() or events_path.stat().st_size > 1_048_576:
    sys.exit(1)
if not last_path.exists() or not (0 < last_path.stat().st_size <= 8192):
    sys.exit(1)
event_types = []
try:
    for line in events_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            event = json.loads(line)
            if not isinstance(event, dict):
                sys.exit(1)
            event_types.append(event.get("type"))
except (ValueError, UnicodeError):
    sys.exit(1)

if "turn.completed" not in event_types:
    sys.exit(1)
if "turn.failed" in event_types or "error" in event_types:
    sys.exit(1)
if not last_path.read_text(encoding="utf-8").strip():
    sys.exit(1)
PY
then
    printf '%s\n' 'CODEX_TURN_COMPLETED'
    printf '%s\n' 'SMOKE_OK: real Codex read-only CLI turn completed; lab Git state unchanged.'
else
    printf '%s\n' 'SMOKE_FAIL: missing completion event or final response'
    exit 1
fi
