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
case "$AI_DESK_BIND" in
  127.0.0.1|localhost|::1)
    SCHEME="http"
    ;;
  *)
    SCHEME="https"
    if [ -z "${AI_DESK_TLS_CERT:-}" ] || [ -z "${AI_DESK_TLS_KEY:-}" ]; then
      printf 'LAN bind requires AI_DESK_TLS_CERT and AI_DESK_TLS_KEY.\n' >&2
      exit 1
    fi
    ;;
esac
printf 'Starting AI Desk in dry-run mode at %s://%s:%s\n' "$SCHEME" "$AI_DESK_BIND" "$AI_DESK_PORT"
printf 'Do not expose this service directly to the public Internet.\n'
exec python3 -m ai_desk.server
