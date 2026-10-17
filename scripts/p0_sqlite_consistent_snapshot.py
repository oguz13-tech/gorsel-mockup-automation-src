# -*- coding: utf-8 -*-
"""SQLite consistent snapshot to an OUT-OF-RUNTIME destination. No migration.

Must be explicitly invoked with --execute. Source SQLite read-only URI;
SQLite Backup API captures WAL-consistent bytes, never unsafe file copy.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import sqlite3
import time
import uuid
from pathlib import Path


def digest(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def snapshot(runtime_root: Path, destination_root: Path) -> dict:
    root=Path(runtime_root).resolve()
    dest=Path(destination_root).resolve()
    db=root/"SABLON_V2_MIMARI"/"ayarlar.db"
    if not root.is_dir() or not db.is_file() or db.is_symlink():
        raise RuntimeError("RUNTIME_DB_NOT_AVAILABLE")
    if dest==root or dest.is_relative_to(root) or root.is_relative_to(dest):
        raise RuntimeError("SNAPSHOT_DESTINATION_MUST_BE_SEPARATE")
    if dest.is_symlink():
        raise RuntimeError("SNAPSHOT_DESTINATION_SYMLINK_BLOCKED")
    dest.mkdir(parents=True,exist_ok=True)
    outdir=dest/("p0_before_migration_"+time.strftime("%Y%m%d_%H%M%S")+"_"+uuid.uuid4().hex)
    outdir.mkdir(mode=0o700)
    outdb=outdir/"ayarlar.db"
    conn=sqlite3.connect(db.resolve().as_uri()+"?mode=ro",uri=True,timeout=30)
    backup=sqlite3.connect(outdb)
    try:
        conn.execute("PRAGMA query_only=ON")
        conn.backup(backup,pages=100,sleep=0.1)
        if backup.execute("PRAGMA quick_check").fetchone()[0]!="ok":
            raise RuntimeError("SNAPSHOT_SQLITE_QUICK_CHECK_FAILED")
    finally:
        backup.close();conn.close()
    manifest={"original_database":str(db),"database_backup":str(outdb),
              "sqlite_backup_sha256":digest(outdb),"json_snapshots":[],
              "source_modified":False,"installation_authorized":False}
    for index,p in enumerate((root/"ayarlar.json",root/"99_SISTEM_MOTORLARI_VE_KODLAR"/"SISTEM_MOTORU"/"ayarlar.json")):
        if not p.is_file() or p.is_symlink():
            continue
        raw=p.read_bytes()
        target=outdir/("ayarlar_"+str(index)+".json")
        with target.open("xb") as writer:
            writer.write(raw)
        manifest["json_snapshots"].append({"original":str(p),"snapshot":str(target),"sha256":digest(target)})
    receipt=outdir/"snapshot_manifest.json"
    with receipt.open("x",encoding="utf-8") as f:
        json.dump(manifest,f,ensure_ascii=False,indent=2)
    return manifest


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--runtime-root",required=True,type=Path)
    p.add_argument("--destination-root",required=True,type=Path)
    p.add_argument("--execute",action="store_true")
    a=p.parse_args(argv)
    if not a.execute:
        print("PLAN_ONLY: no SQLite or JSON touched; no snapshot created.")
        return 0
    print(json.dumps(snapshot(a.runtime_root,a.destination_root),ensure_ascii=False,indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
