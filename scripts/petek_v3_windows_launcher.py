# -*- coding: utf-8 -*-
"""PETEK V3 Windows staging launcher for the existing factory UI.

Never executes the legacy app.py __main__ startup migrations/backfill. It
imports the Flask app, then exposes only localhost for safe candidate review.
No live installation, merge or user DB migration happens here.
"""
from __future__ import annotations

import argparse
import logging
import os
import sqlite3
import sys
import threading
import webbrowser
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[1]
LOGGER = logging.getLogger("petek.windows")


class LaunchRejected(RuntimeError):
    """Identify unsafe or incomplete Windows staging preflight."""


def choose_workspace() -> Path:
    """Use existing runtime environment or native Windows folder picker."""
    requested = str(os.environ.get("MOCKUP_RUNTIME_WORKSPACE") or "").strip()
    if requested:
        return Path(requested).expanduser().resolve()
    try:
        import tkinter as tk
        from tkinter import filedialog
        root=tk.Tk()
        root.withdraw()
        root.attributes("-topmost",True)
        location=filedialog.askdirectory(
            title="Var olan Görsel Üretim ve Mockup Otomasyonu çalışma klasörünü seç",
            mustexist=True)
        root.destroy()
    except Exception as exc:
        raise LaunchRejected("WINDOWS_FOLDER_PICKER_UNAVAILABLE") from exc
    if not location:
        raise LaunchRejected("WORKSPACE_SELECTION_CANCELLED")
    return Path(location).resolve()


def readonly_runtime_audit(workspace: Path) -> dict:
    """Check existing runtime without creating or migrating its legacy DB."""
    workspace=Path(workspace).resolve(strict=True)
    pool=workspace/"2_SABLON_HAVUZU"
    db_path=workspace/"SABLON_V2_MIMARI"/"ayarlar.db"
    if not pool.is_dir() or pool.is_symlink():
        raise LaunchRejected("TEMPLATE_POOL_MISSING_OR_UNSAFE")
    if not db_path.is_file() or db_path.is_symlink():
        raise LaunchRejected("LEGACY_REVIEW_DB_MISSING_OR_UNSAFE")
    try:
        conn=sqlite3.connect(db_path.resolve().as_uri()+"?mode=ro",
                             uri=True,timeout=8)
        try:
            conn.execute("PRAGMA query_only=ON")
            integrity=conn.execute("PRAGMA quick_check(1)").fetchone()
            if not integrity or integrity[0]!="ok":
                raise LaunchRejected("LEGACY_DB_INTEGRITY_FAILED")
            names={row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
            if "template_profiles" not in names:
                raise LaunchRejected("LEGACY_PROFILE_TABLE_MISSING")
        finally:conn.close()
    except sqlite3.Error as exc:
        raise LaunchRejected("LEGACY_DB_READONLY_AUDIT_FAILED") from exc
    return {"runtime":str(workspace),"legacy_database":"READ_ONLY_OK",
            "petek_folder_exists":(pool/"06_Petek_Dolabi").is_dir()}


def launch(stage: bool = True) -> int:
    """Start the original Flask application in an isolated no-migration mode."""
    workspace=choose_workspace()
    status=readonly_runtime_audit(workspace)
    os.environ["MOCKUP_RUNTIME_WORKSPACE"]=str(workspace)
    os.environ["MOCKUP_NO_AUTO_BROWSER"]="1"
    os.environ["MOCKUP_FLASK_DEBUG"]="0"
    if not stage:
        raise LaunchRejected("ONLY_STAGING_MODE_IS_AUTHORIZED")
    code_dir=SOURCE_ROOT/"SABLON_V2_MIMARI"
    if str(code_dir) not in sys.path:
        sys.path.insert(0,str(code_dir))
    from app import app
    LOGGER.info("Source tree: %s",SOURCE_ROOT)
    LOGGER.info("Workspace read-only audit: %s",status)
    threading.Timer(1.5,lambda:webbrowser.open(
        "http://127.0.0.1:8080/petek-v3/")).start()
    app.run(host="127.0.0.1",port=8080,debug=False,use_reloader=False)
    return 0


def main() -> int:
    """Provide safe candidate launch, never an implicit live migration."""
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage",action="store_true")
    parser.add_argument("--live",action="store_true")
    args=parser.parse_args()
    logging.basicConfig(level=logging.INFO,format="%(asctime)s %(levelname)s %(message)s")
    try:
        if args.live:
            raise LaunchRejected("LIVE_RELEASE_REQUIRES_SEPARATE_ACCEPTANCE")
        return launch(stage=True)
    except (LaunchRejected,FileNotFoundError,OSError) as exc:
        LOGGER.error("PETEK_WINDOWS_STAGE_REJECTED: %s",exc)
        return 2
    except Exception:
        LOGGER.exception("Unexpected Windows launcher failure")
        return 3


if __name__=="__main__":
    raise SystemExit(main())
