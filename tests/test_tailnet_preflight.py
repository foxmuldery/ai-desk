"""Verify Tailscale preflight never changes config or prints sensitive network names."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAKE_TAILSCALE = '''#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
if args == ["version"]:
    print("1.90.0")
elif args == ["status", "--json"]:
    online = os.getenv("FAKE_ONLINE", "1") == "1"
    print(json.dumps({
        "BackendState": "Running" if online else "Stopped",
        "Self": {"Online": online, "DNSName": "very-private.example-tailnet.ts.net"},
        "Peer": {"100.1.1.1": {"DNSName": "other-private-machine.ts.net"}}
    }))
elif args == ["serve", "status", "--json"]:
    if os.getenv("FAKE_SERVE", "0") == "1":
        print(json.dumps({"TCP": {"443": {"HTTPS": True}},
                          "Web": {"secret.example.ts.net:443": {}}}))
    else:
        print("{}")
else:
    print("UNEXPECTED_TAILSCALE_COMMAND", file=sys.stderr)
    sys.exit(5)
'''


class TailnetPreflightTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.bin_dir = Path(self.temporary.name)
        tailscale = self.bin_dir / "tailscale"
        tailscale.write_text(FAKE_TAILSCALE, encoding="utf-8")
        tailscale.chmod(0o700)

    def tearDown(self):
        self.temporary.cleanup()

    def run_preflight(self, *, online="1", serve="0"):
        env = os.environ.copy()
        env.update({
            "PATH": str(self.bin_dir) + os.pathsep + env.get("PATH", ""),
            "FAKE_ONLINE": online,
            "FAKE_SERVE": serve,
        })
        return subprocess.run(
            ["sh", str(ROOT / "scripts/check-phone-tailnet.sh")],
            cwd=ROOT, env=env, capture_output=True, text=True, timeout=10,
        )

    def test_connected_empty_serve(self):
        r = self.run_preflight()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("TAILNET_READY", r.stdout)
        self.assertIn("SERVE_PORT_FREE_TO_REVIEW", r.stdout)
        self.assertNotIn("very-private", r.stdout)
        self.assertNotIn("100.1.1.1", r.stdout)

    def test_connected_existing_serve_requires_review(self):
        r = self.run_preflight(serve="1")
        self.assertEqual(r.returncode, 0)
        self.assertIn("SERVE_CONFIG_REVIEW_REQUIRED", r.stdout)
        self.assertNotIn("secret.example", r.stdout)

    def test_disconnected_does_not_claim_ready(self):
        r = self.run_preflight(online="0")
        self.assertEqual(r.returncode, 3)
        self.assertIn("TAILNET_NOT_CONNECTED", r.stdout)
        self.assertNotIn("TAILNET_READY", r.stdout)


if __name__ == "__main__":
    unittest.main()
