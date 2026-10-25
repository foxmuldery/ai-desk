#!/bin/sh
# Phone connection experiment: explicitly dry-run only, even when proxied.
# No public bind, no Codex, no router changes and no default credential reuse.
set -eu
umask 077

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT"

if ! command -v python3 >/dev/null 2>&1; then
    printf '%s\n' 'PHONE_DRYRUN_FAIL: Python 3 not found' >&2
    exit 2
fi

# Fail closed for all future adapters; do not inherit a previous Codex opt-in.
export AI_DESK_EXECUTION_PROFILE="phone-dry-run"
export AI_DESK_ENABLE_CODEX_READONLY="0"
export AI_DESK_BIND="127.0.0.1"
export AI_DESK_PORT="${AI_DESK_PHONE_PORT:-8766}"
export AI_DESK_DB="$ROOT/data/ai-desk-phone-dryrun.sqlite3"
export AI_DESK_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
export PYTHONPATH="$ROOT/server${PYTHONPATH:+:$PYTHONPATH}"
unset AI_DESK_TLS_CERT AI_DESK_TLS_KEY AI_DESK_CODEX_READONLY_ROOT AI_DESK_CODEX_BIN

printf '\n%s\n' 'AI Desk PHONE DRY-RUN experiment (SIMULATED TASKS ONLY)'
printf 'Coordinator: http://127.0.0.1:%s (not exposed to LAN)\n' "$AI_DESK_PORT"
printf '%s\n' 'To access from an Android device, first set up a private Tailscale Serve HTTPS route.'
printf '%s\n' 'NEVER use tailscale funnel or open an internet port for this service.'
printf '\n%s\n' 'PRIVATE TEMPORARY TOKEN (keep on your own devices; never post in chat or GitHub):'
printf '%s\n' "$AI_DESK_TOKEN"
printf '\n%s\n' 'Keep this terminal open during the test. Press Ctrl+C to stop the Coordinator.'
exec python3 -m ai_desk.server
