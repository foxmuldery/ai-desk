#!/bin/sh
set -eu
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT/server${PYTHONPATH:+:$PYTHONPATH}"
export AI_DESK_BIND="${AI_DESK_BIND:-127.0.0.1}"
export AI_DESK_PORT="${AI_DESK_PORT:-8765}"
export AI_DESK_DB="${AI_DESK_DB:-$ROOT/data/ai-desk.sqlite3}"
if [ -z "${AI_DESK_TOKEN:-}" ]; then
  AI_DESK_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
  export AI_DESK_TOKEN
  printf '\nTemporary AI_DESK_TOKEN (save it for this session):\n%s\n\n' "$AI_DESK_TOKEN"
fi
printf 'Starting AI Desk in dry-run mode at http://%s:%s\n' "$AI_DESK_BIND" "$AI_DESK_PORT"
printf 'Default bind is loopback only. Do not expose this HTTP service to the Internet.\n'
exec python3 -m ai_desk.server
