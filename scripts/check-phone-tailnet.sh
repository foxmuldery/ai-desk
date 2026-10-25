#!/bin/sh
# Read-only Tailscale readiness check for AI Desk S22 Ultra dry-run.
# Does not install software, change VPN/Serve settings or show private names/IPs.
set -eu

if command -v tailscale >/dev/null 2>&1; then
    TS_BIN="$(command -v tailscale)"
elif [ -x "/Applications/Tailscale.app/Contents/MacOS/Tailscale" ]; then
    TS_BIN="/Applications/Tailscale.app/Contents/MacOS/Tailscale"
else
    printf '%s\n' 'TAILNET_CLIENT_MISSING: Tailscale CLI is not installed or not available.'
    exit 2
fi

# The macOS App Store binary may otherwise open its UI instead of acting as CLI.
export TAILSCALE_BE_CLI=1

if ! "$TS_BIN" version >/dev/null 2>&1; then
    printf '%s\n' 'TAILNET_CLI_UNAVAILABLE: inspect the Mac Tailscale app locally.'
    exit 2
fi
printf '%s\n' 'TAILNET_CLI_OK'

if ! command -v python3 >/dev/null 2>&1; then
    printf '%s\n' 'TAILNET_PYTHON_MISSING: Python3 is required for private JSON checks.'
    exit 2
fi

if ! STATUS_JSON="$("$TS_BIN" status --json 2>/dev/null)"; then
    printf '%s\n' 'TAILNET_NOT_CONNECTED: sign in to Tailscale on this Mac.'
    exit 3
fi
BACKEND_RESULT="$(printf '%s\n' "$STATUS_JSON" | python3 -c '
import json, sys
try:
    result = json.load(sys.stdin)
    ready = (result.get("BackendState") == "Running"
             and result.get("Self", {}).get("Online", False))
except (ValueError, TypeError, AttributeError):
    ready = False
print("TAILNET_READY" if ready else "TAILNET_NOT_CONNECTED")
')"

if [ "$BACKEND_RESULT" != "TAILNET_READY" ]; then
    printf '%s\n' 'TAILNET_NOT_CONNECTED: check the local Tailscale app.'
    exit 3
fi
printf '%s\n' "$BACKEND_RESULT"

if SERVE_JSON="$("$TS_BIN" serve status --json 2>/dev/null)"; then
    SERVE_RESULT="$(printf '%s\n' "$SERVE_JSON" | python3 -c '
import json, sys
try:
    data = json.load(sys.stdin)
    if not data:
        print("SERVE_PORT_FREE_TO_REVIEW")
    elif isinstance(data, dict) and not any(
            bool(data.get(name)) for name in ("TCP", "Web", "Services")):
        # Unknown nonempty formats must be reviewed, not treated as empty.
        print("SERVE_CONFIG_REVIEW_REQUIRED")
    else:
        print("SERVE_CONFIG_REVIEW_REQUIRED")
except (ValueError, TypeError):
    print("SERVE_CONFIG_REVIEW_REQUIRED")
')"
else
    SERVE_RESULT="SERVE_STATUS_UNAVAILABLE"
fi

printf '%s\n' "$SERVE_RESULT"
printf '%s\n' 'No Tailscale configuration has been changed.'
printf '%s\n' 'Never paste full tailscale status output, machine names, internal IPs or login URLs.'
