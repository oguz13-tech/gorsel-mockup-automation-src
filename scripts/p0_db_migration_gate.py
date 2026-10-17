# -*- coding: utf-8 -*-
"""Explicit, simulation-first SQLite schema migration gate.

Default PLAN is read-only. SIMULATE snapshots SQLite using backup API then
runs the real schema initializer ONLY on a disposable copy outside runtime.
LIVE APPLY is intentionally a separate user-authorized acceptance action;
this module does not silently migrate a production DB on GUI startup.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
import uuid
from pathlib import Path


class MigrationBlocked(RuntimeError):
    pass


def _sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _no_active_ui():
    for port in (8080, 8999):
        with socket.socket() as s:
            s.settimeout(0.15)
            if s.connect_ex(("127.0.0.1",port)) == 0:
                raise MigrationBlocked("UI_STILL_RUNNING_ON_PORT_" + str(port))


def _database_counts(conn):
    rows = {}
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    for table in ("categories", "templates", "template_profiles", "jobs",
                  "template_number_registry", "analysis_cache"):
        if table in tables:
            rows[table] = int(conn.execute('SELECT count(*) FROM "' + table + '"').fetchone()[0])
    return rows


def _validate_dirs(runtime, vault):
    root, target = Path(runtime).resolve(), Path(vault).resolve()
    if not root.is_dir():
        raise MigrationBlocked("RUNTIME_DIRECTORY_MISSING")
    if target == root or root in target.parents or target in root.parents:
        raise MigrationBlocked("EXTERNAL_SNAPSHOT_VAULT_REQUIRED")
    if any(part.casefold()=="onedrive" for part in target.parts):
        raise MigrationBlocked("BACKUP_VAULT_CANNOT_BE_IN_ONEDRIVE")
    db = root / "SABLON_V2_MIMARI" / "ayarlar.db"
    if db.is_symlink() or not db.is_file():
        raise MigrationBlocked("RUNTIME_SQLITE_MISSING_OR_UNSAFE")
    return db, target


def simulate(runtime: Path, vault: Path, source_root: Path):
    _no_active_ui()
    original, target = _validate_dirs(runtime, vault)
    source = Path(source_root).resolve()
    if not (source / "SABLON_V2_MIMARI" / "core" / "db.py").is_file():
        raise MigrationBlocked("SOURCE_SCHEMA_MODULE_MISSING")
    target.mkdir(parents=True, exist_ok=True)
    base = target / ("P0_DB_SIM_" + time.strftime("%Y%m%d_%H%M%S") +
                     "_" + uuid.uuid4().hex[:10])
    fake_db = base / "FAKE_RUNTIME" / "SABLON_V2_MIMARI" / "ayarlar.db"
    fake_db.parent.mkdir(parents=True)
    before = None
    source_conn = sqlite3.connect(original.resolve().as_uri() + "?mode=ro",
                                  uri=True, timeout=30)
    dest_conn = sqlite3.connect(fake_db)
    try:
        before = _database_counts(source_conn)
        source_conn.backup(dest_conn)
        row = dest_conn.execute("PRAGMA integrity_check").fetchone()
        if not row or row[0] != "ok":
            raise MigrationBlocked("SNAPSHOT_SQLITE_INTEGRITY_FAILURE")
    finally:
        dest_conn.close()
        source_conn.close()
    before_hash = _sha(fake_db)
    script = (
        "import os,sys;sys.path.insert(0,sys.argv[1]);"
        "from core.db import init_db,inspect_startup_schema;"
        "init_db();assert inspect_startup_schema()['ready']"
    )
    env = {**os.environ, "MOCKUP_RUNTIME_WORKSPACE":str(fake_db.parents[1]),
           "PYTHONIOENCODING":"utf-8"}
    p = subprocess.run(
        [sys.executable, "-B", "-c", script,
         str(source / "SABLON_V2_MIMARI")], cwd=source,
        env=env, capture_output=True, text=True, timeout=120,
    )
    if p.returncode:
        raise MigrationBlocked("FAKE_MIGRATION_FAILED:" + p.stderr[-700:])
    conn = sqlite3.connect(fake_db)
    try:
        row = conn.execute("PRAGMA integrity_check").fetchone()
        after = _database_counts(conn)
        if not row or row[0] != "ok":
            raise MigrationBlocked("MIGRATED_DB_INTEGRITY_FAILURE")
        if any(after.get(name,0) < count for name,count in before.items()):
            raise MigrationBlocked("MIGRATION_ROW_LOSS_DETECTED")
    finally:
        conn.close()
    evidence = {
        "status":"SIMULATED_SCHEMA_MIGRATION_PASS_NOT_LIVE_APPROVAL",
        "runtime":str(Path(runtime).resolve()),
        "snapshot":str(fake_db), "before_counts":before,
        "after_counts":after, "source_snapshot_sha256":before_hash,
        "migrated_copy_sha256":_sha(fake_db),
        "production_db_modified":False,
    }
    proof = base / "report.json"
    proof.write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding="utf-8")
    return evidence


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mode",choices=("plan","simulate"),default="plan")
    p.add_argument("--runtime",type=Path)
    p.add_argument("--vault",type=Path)
    p.add_argument("--source",type=Path,default=Path(__file__).resolve().parents[1])
    args=p.parse_args(argv)
    try:
        if not args.runtime or not args.vault:
            raise MigrationBlocked("RUNTIME_AND_EXTERNAL_VAULT_REQUIRED")
        db, target = _validate_dirs(args.runtime,args.vault)
        result = (
            {"status":"PLAN_ONLY_NOT_APPLIED","db":str(db),"vault":str(target)}
            if args.mode=="plan" else simulate(args.runtime,args.vault,args.source)
        )
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 0
    except (MigrationBlocked,OSError,sqlite3.DatabaseError) as e:
        print(json.dumps({"status":"BLOCKED","error":str(e)},ensure_ascii=False))
        return 2


if __name__=="__main__":
    raise SystemExit(main())
