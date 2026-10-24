#!/bin/sh
# Read-only Mac Studio preflight. Does not invoke an AI turn or modify Codex configuration.
set -u

missing=0
printf '%s\n' 'AI Desk / Codex local preflight'

if ! command -v codex >/dev/null 2>&1; then
    printf '%s\n' 'FAIL: Codex CLI is not in PATH.'
    exit 2
fi
printf '%s\n' 'Codex CLI:'
codex --version || missing=1

printf '%s\n' 'ChatGPT login status:'
codex login status || missing=1

global_help="$(codex --help 2>&1)" || missing=1
exec_help="$(codex exec --help 2>&1)" || missing=1
for flag in '--sandbox' '--ask-for-approval' '--json' '--output-last-message' '--ignore-user-config' '--ephemeral'; do
    if printf '%s\n%s\n' "$global_help" "$exec_help" | grep -F -- "$flag" >/dev/null 2>&1; then
        printf 'OK: %s available\n' "$flag"
    else
        printf 'FAIL: %s missing from CLI help\n' "$flag"
        missing=1
    fi
done

root="${AI_DESK_CODEX_READONLY_ROOT:-$HOME/AI-Desk-Sandbox}"
if [ -d "$root" ] && [ -e "$root/.git" ]; then
    printf '%s\n' 'OK: the configured lab Git repository exists.'
else
    printf '%s\n' 'FAIL: the lab directory must exist and have a .git entry.'
    printf '%s\n' 'Prepare with: mkdir -p "$HOME/AI-Desk-Sandbox" && cd "$HOME/AI-Desk-Sandbox" && git init'
    missing=1
fi

if [ "$missing" -eq 0 ]; then
    printf '%s\n' 'PREFLIGHT_OK (this does not mean a live Codex turn has been tested).'
else
    printf '%s\n' 'PREFLIGHT_INCOMPLETE: share only the status lines; never share credentials.'
fi
exit "$missing"
