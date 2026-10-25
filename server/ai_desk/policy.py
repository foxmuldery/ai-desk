"""Fail-closed execution profiles for AI Desk.

The phone profile is intentionally a non-executing experiment. Network reachability
(including traffic relayed through a loopback reverse proxy) never authorizes a
new adapter. Any future adapter integration must keep this policy check.
"""
from __future__ import annotations

LOOPBACK_HOSTS = frozenset(("127.0.0.1", "localhost", "::1"))
PROFILES = frozenset(("local", "phone-dry-run"))


def validate_profile(profile: str, bind: str, token: str, codex_opt_in: str) -> None:
    """Reject unsafe service configurations before handling requests."""
    if profile not in PROFILES:
        raise ValueError("Unrecognized AI_DESK_EXECUTION_PROFILE")
    if profile != "phone-dry-run":
        return
    if bind not in LOOPBACK_HOSTS:
        raise ValueError("phone-dry-run must bind only to loopback (Tailscale Serve can proxy it)")
    if len(token) < 32:
        raise ValueError("phone-dry-run requires an AI_DESK_TOKEN of at least 32 characters")
    if codex_opt_in == "1":
        raise ValueError("phone-dry-run refuses any Codex execution opt-in")


def adapter_allowed(profile: str, adapter: str) -> bool:
    """Independent of apparent client IP, TLS terminator, Host or Forwarded headers."""
    return profile != "phone-dry-run" or adapter == "dry-run"
