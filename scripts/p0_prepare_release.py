# -*- coding: utf-8 -*-
"""P0 Windows pre-release acceptance. READ ONLY; no install/apply mode.

The only new file is a JSON report under OS TEMP. Source templates,
originals, SQLite, Git, Excel, cloud and registry are NEVER mutated.
"""
import argparse
import hashlib
import json
import os
import socket
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1]
BASELINES = {
    "005": "C75F3BC021BCFC7A6AE01B96D735B09BB4C7D6C8AC0D752CC8A9A6912532C6BE",
    "135": "375D85B4F098799C621C1EC24A6729D498B51B8451BDBD0F1F75B769D8D852FC",
    "137": "EBF1DA4BF5BD220E45FFD40311A8E5828CD95C4E4CE246F4CAF5793534284D7A",
    "188": "51957294704A6E266487CB18F38909CBF94C623F49199F6C9C2675946DD4F3D6",
}


def _hash(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as inp:
        for chunk in iter(lambda: inp.read(1024 * 1024), b""):
            sha.update(chunk)
    return sha.hexdigest().upper()


def discover():
    env = os.getenv("MOCKUP_RUNTIME_WORKSPACE")
    if env:
        return Path(env).expanduser()
    one = Path.home() / "OneDrive"
    for desktop in ("Masaüstü", "Desktop"):
        candidate = one / desktop / "GörselÜretme-ve-Mockup Otomasyonu"
        if candidate.is_dir():
            return candidate
    return Path.home() / "OneDrive" / "Masaüstü" / "GörselÜretme-ve-Mockup Otomasyonu"


def _port_listening(port: int) -> bool:
    with socket.socket() as sock:
        sock.settimeout(0.3)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def git(*args):
    try:
        p = subprocess.run(["git", "-C", str(SOURCE), *args],
                           capture_output=True, text=True, timeout=15, check=False)
        return p.stdout.strip() if p.returncode == 0 else "UNAVAILABLE"
    except (OSError, subprocess.TimeoutExpired):
        return "UNAVAILABLE"


def preflight(runtime: Path) -> dict:
    runtime = runtime.resolve()
    report = {
        "mode": "READ_ONLY_PRE_RELEASE",
        "time": datetime.now().isoformat(),
        "runtime_root": str(runtime),
        "runtime_exists": runtime.is_dir(),
        "repo_head": git("rev-parse", "HEAD"),
        "repo_branch": git("branch", "--show-current"),
        "repo_status": git("status", "--porcelain"),
        "ports_listening": {str(p): _port_listening(p) for p in (8999, 8080)},
        "backups": {}, "checks": {}, "release_approved": False,
        "installer_executed": False,
    }
    report["checks"]["immutable_backup_dir"] = (
        runtime / "2_SABLON_HAVUZU_ORIJINAL_YEDEK"
    ).is_dir()
    report["checks"]["sqlite_file_exists"] = (
        runtime / "SABLON_V2_MIMARI" / "ayarlar.db"
    ).is_file()
    backup = runtime / "2_SABLON_HAVUZU_ORIJINAL_YEDEK" / "01_Wifi_Kutusu"
    for number, baseline in BASELINES.items():
        path = backup / ("Wifi_Kutusu_" + number + ".png")
        try:
            sha = _hash(path)
            report["backups"][number] = {
                "exists": True, "sha256": sha, "matches_earlier_baseline": sha == baseline
            }
        except OSError as exc:
            report["backups"][number] = {"exists": False, "error": str(exc)}
    report["checks"]["source_is_not_runtime"] = SOURCE.resolve() != runtime
    report["checks"]["panels_both_closed"] = not any(report["ports_listening"].values())
    report["checks"]["backup_hash_matches"] = all(
        row.get("matches_earlier_baseline", False) for row in report["backups"].values()
    )
    report["status"] = (
        "READ_ONLY_PRECHECK_PASS_NOT_INSTALL_APPROVAL"
        if all(report["checks"].values())
        else "READ_ONLY_PRECHECK_BLOCKED"
    )
    return report


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-root", type=Path, default=None)
    args = parser.parse_args(argv)
    result = preflight(args.runtime_root or discover())
    print(json.dumps(result, indent=2, ensure_ascii=False))
    # Only JSON output is persisted and ONLY under TEMP, never the user runtime.
    dest = Path(tempfile.gettempdir()) / (
        "P0_RELEASE_PRECHECK_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".json"
    )
    try:
        with dest.open("x", encoding="utf-8") as outfile:
            json.dump(result, outfile, ensure_ascii=False, indent=2)
        print("TEMP_REPORT:", str(dest))
    except FileExistsError:
        print("TEMP_REPORT_SKIPPED_FILENAME_ALREADY_EXISTS")
    return 0 if result["status"].startswith("READ_ONLY_PRECHECK_PASS") else 2


if __name__ == "__main__":
    raise SystemExit(main())
