"""Choose a safe local port without stopping an unrelated V4.6 process."""
from __future__ import annotations

import os
import socket
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def available(port: int) -> bool:
    with socket.socket() as sock:
        sock.settimeout(0.2)
        return sock.connect_ex(("127.0.0.1", port)) != 0


def choose_port() -> int:
    requested = int(os.environ.get("MOCKUP_PORT", "8080"))
    if available(requested):
        return requested
    if requested == 8080 and available(8081):
        return 8081
    raise RuntimeError(f"Requested port {requested} and safe fallback are occupied")


def main() -> int:
    port = choose_port()
    env = os.environ.copy()
    env["MOCKUP_PORT"] = str(port)
    env.setdefault("MOCKUP_NO_AUTO_BROWSER", "1")
    app = ROOT / "SABLON_V2_MIMARI" / "app.py"
    print(f"Starting isolated V4.6 on http://127.0.0.1:{port}", flush=True)
    return subprocess.call([sys.executable, "-B", str(app)], cwd=str(ROOT), env=env)


if __name__ == "__main__":
    raise SystemExit(main())
