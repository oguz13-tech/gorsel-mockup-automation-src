# -*- coding: utf-8 -*-
"""Legacy HTTP safety probe, now opt-in ONLY against isolated fake server.

Importing this module and running without arguments MUST NOT send any request.
Never point the probe at normal 8080/8999 development/production ports.
"""
import argparse
import json
import os
import urllib.request
import urllib.error
from urllib.parse import urlparse


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--execute", action="store_true")
    p.add_argument("--url", default="")
    args = p.parse_args(argv)
    if not args.execute:
        print("PLAN_ONLY: no server contacted.")
        return 0
    uri = urlparse(args.url)
    if (
        os.environ.get("MOCKUP_P0_TEST_ISOLATED") != "1"
        or uri.hostname not in ("127.0.0.1", "localhost")
        or uri.port in (8080, 8999, None)
        or uri.path != "/api/ayarlar"
    ):
        print("BLOCKED: only explicit isolated test server with nonproduction port.")
        return 2
    payload = json.dumps({
        "kategoriler": {
            "01_Wifi_Kutusu": {"sablonlar": {"Wifi_Kutusu_001.png": {}}}
        }
    }).encode("utf-8")
    req = urllib.request.Request(args.url, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Content-Length", str(len(payload)))
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            print("UNEXPECTED_SUCCESS:", response.status)
            return 2
    except urllib.error.HTTPError as exc:
        print("TEST_HTTP_REJECTION:", exc.code)
        return 0 if exc.code >= 400 else 2
    except OSError as exc:
        print("ISOLATED_SERVER_NOT_AVAILABLE:", type(exc).__name__)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
