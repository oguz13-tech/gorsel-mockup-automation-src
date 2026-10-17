# -*- coding: utf-8 -*-
"""Opt-in, snapshot-first CODE-ONLY release and verified code rollback.

This file is never called during Flask import, watcher startup or rendering.
It never writes to the runtime SQLite, JSON, working templates or originals.
Backups are OUTSIDE the user's runtime and CODE checkout.
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

# Explicit audited CODE files. User artwork, data, caches and .git never qualify.
RELEASE_FILES = (
    "SABLON_V2_MIMARI/app.py",
    "SABLON_V2_MIMARI/core/db.py",
    "SABLON_V2_MIMARI/core/template_identity.py",
    "SABLON_V2_MIMARI/core/template_intelligence.py",
    "SABLON_V2_MIMARI/core/safe_working_revision.py",
    "SABLON_V2_MIMARI/core/manual_production_guard.py",
    "SABLON_V2_MIMARI/core/lifecycle_reconciliation.py",
    "SABLON_V2_MIMARI/core/vision.py",
    "SABLON_V2_MIMARI/tools_runner.py",
    "SABLON_V2_MIMARI/v2_baslat.bat",
    "SABLON_DUZELTICI.py",
    "INCELEME_MERKEZINI_AC.ps1",
    "MANUEL_GORSELLERDEN_MOCKUP_URET.bat",
    "BAGIMSIZ_ARACLAR/09_GUVENLI_YENI_SABLON_EKLE.bat",
    "00_KLASORLERI_VE_SABLONLARI_YENILE.bat",
    "99_SISTEM_MOTORLARI_VE_KODLAR/SISTEM_MOTORU/sablon_beyazlatma_motoru.py",
    "99_SISTEM_MOTORLARI_VE_KODLAR/SISTEM_MOTORU/sablon_oto_izleyici.py",
    "99_SISTEM_MOTORLARI_VE_KODLAR/SISTEM_MOTORU/temizlik_motoru.py",
    "99_SISTEM_MOTORLARI_VE_KODLAR/SISTEM_MOTORU/migrate_to_png.py",
    "99_SISTEM_MOTORLARI_VE_KODLAR/SISTEM_MOTORU/manuel_mockup_motoru.py",
    "99_SISTEM_MOTORLARI_VE_KODLAR/SISTEM_MOTORU/final_fix.py",
    "99_SISTEM_MOTORLARI_VE_KODLAR/SISTEM_MOTORU/ultimate_rescue.py",
    "99_SISTEM_MOTORLARI_VE_KODLAR/SISTEM_MOTORU/rollback.py",
    "99_SISTEM_MOTORLARI_VE_KODLAR/SISTEM_MOTORU/rescue_edits.py",
    "99_SISTEM_MOTORLARI_VE_KODLAR/SISTEM_MOTORU/rescue_edits_all.py",
    "99_SISTEM_MOTORLARI_VE_KODLAR/SISTEM_MOTORU/fix_json_keys.py",
    "99_SISTEM_MOTORLARI_VE_KODLAR/SISTEM_MOTORU/legacy_recovery_preview.py",
    "99_SISTEM_MOTORLARI_VE_KODLAR/SISTEM_MOTORU/test_safety.py",
    "99_SISTEM_MOTORLARI_VE_KODLAR/SISTEM_MOTORU/generate_test_13er_tane.py",
    "99_SISTEM_MOTORLARI_VE_KODLAR/SISTEM_MOTORU/test_effects/create_and_compare_effects.py",
    "99_SISTEM_MOTORLARI_VE_KODLAR/SISTEM_MOTORU/test_effects/render_peacock_match.py",
    "scripts/epic3_visual_candidate_sheets.py",
)
RUNTIME_DATA = (
    "SABLON_V2_MIMARI/ayarlar.db",
    "ayarlar.json",
    "99_SISTEM_MOTORLARI_VE_KODLAR/SISTEM_MOTORU/ayarlar.json",
)


class ReleaseBlocked(RuntimeError):
    pass


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for part in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(part)
    return h.hexdigest()


def _inside(p: Path, root: Path) -> bool:
    return p == root or root in p.parents


def _paths(source: Path, code: Path, runtime: Path, vault: Path):
    source, code, runtime, vault = (Path(x).resolve() for x in (source, code, runtime, vault))
    if len({str(x).casefold() for x in (source, code, runtime, vault)}) != 4:
        raise ReleaseBlocked("SOURCE_CODE_RUNTIME_VAULT_MUST_DIFFER")
    if any(_inside(vault, p) or _inside(p, vault) for p in (source, code, runtime)):
        raise ReleaseBlocked("BACKUP_VAULT_MUST_BE_SEPARATE")
    if _inside(runtime, code) or _inside(code, runtime):
        raise ReleaseBlocked("CODE_MUST_NOT_OVERLAP_RUNTIME")
    if not source.is_dir() or not code.is_dir() or not runtime.is_dir():
        raise ReleaseBlocked("INVALID_RELEASE_DIRECTORY")
    if not (runtime / "SABLON_V2_MIMARI" / "ayarlar.db").is_file():
        raise ReleaseBlocked("RUNTIME_DB_MISSING")
    if not (runtime / "2_SABLON_HAVUZU_ORIJINAL_YEDEK").is_dir():
        raise ReleaseBlocked("ORIGINAL_ARCHIVE_MISSING")
    for rel in RELEASE_FILES:
        if ".." in Path(rel).parts or not (source / rel).is_file():
            raise ReleaseBlocked("SOURCE_CODE_MISSING:" + rel)
        if (source / rel).is_symlink() or (code / rel).is_symlink():
            raise ReleaseBlocked("CODE_SYMLINK_BLOCKED:" + rel)
    return source, code, runtime, vault


def _check_ports():
    for port in (8080, 8999):
        with socket.socket() as sock:
            sock.settimeout(0.2)
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                raise ReleaseBlocked("UI_PORT_STILL_OPEN:" + str(port))


def _write_manifest(path: Path, data: dict):
    tmp = path.with_name("." + uuid.uuid4().hex + ".tmp")
    try:
        with tmp.open("xb") as fh:
            fh.write(json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"))
            fh.flush(); os.fsync(fh.fileno())
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def plan(source, code, runtime, vault):
    src, dst, user, backups = _paths(source, code, runtime, vault)
    _check_ports()
    return {
        "status": "READY_TO_BACKUP_NOT_APPROVED_TO_INSTALL",
        "source": str(src), "code": str(dst), "runtime": str(user),
        "vault": str(backups), "file_count": len(RELEASE_FILES),
        "runtime_mutation": False, "needs_explicit_approval": True,
    }


def create_snapshot(source, code, runtime, vault):
    src, dst, user, backups = _paths(source, code, runtime, vault)
    _check_ports()
    backups.mkdir(parents=True, exist_ok=True)
    snapshot = backups / ("P0_RELEASE_" + time.strftime("%Y%m%d_%H%M%S") +
                          "_" + uuid.uuid4().hex[:10])
    snapshot.mkdir(mode=0o700)
    m = {
        "state": "SNAPSHOT_IN_PROGRESS", "source": str(src),
        "code": str(dst), "runtime": str(user), "entries": [],
        "runtime_snapshot": [], "installer_changes_runtime": False,
    }
    _write_manifest(snapshot / "manifest.json", m)
    for rel in RELEASE_FILES:
        original = dst / rel
        entry = {"path": rel, "existed": original.is_file(),
                 "before": None, "installed": None}
        if original.is_file():
            out = snapshot / "code_before" / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            with original.open("rb") as fr, out.open("xb") as fw:
                shutil.copyfileobj(fr, fw)
                fw.flush(); os.fsync(fw.fileno())
            if sha(out) != sha(original):
                raise ReleaseBlocked("CODE_SNAPSHOT_HASH_MISMATCH:" + rel)
            entry["before"] = sha(out)
        m["entries"].append(entry)
        _write_manifest(snapshot / "manifest.json", m)
    for rel in RUNTIME_DATA:
        original = user / rel
        if not original.is_file():
            continue
        out = snapshot / "runtime_snapshot" / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        if rel.endswith(".db"):
            srcdb = sqlite3.connect(original.resolve().as_uri() + "?mode=ro",
                                    uri=True, timeout=30)
            dstdb = sqlite3.connect(str(out))
            try:
                srcdb.backup(dstdb)
                check = dstdb.execute("PRAGMA integrity_check").fetchone()
                if not check or check[0] != "ok":
                    raise ReleaseBlocked("SQLITE_BACKUP_INTEGRITY_FAIL")
            finally:
                dstdb.close(); srcdb.close()
        else:
            with original.open("rb") as fr, out.open("xb") as fw:
                shutil.copyfileobj(fr, fw)
                fw.flush(); os.fsync(fw.fileno())
        m["runtime_snapshot"].append({"path": rel, "sha256": sha(out)})
        _write_manifest(snapshot / "manifest.json", m)
    m["state"] = "SNAPSHOT_READY"
    _write_manifest(snapshot / "manifest.json", m)
    return {"status": m["state"], "snapshot": str(snapshot),
            "code_files": len(m["entries"]), "runtime_backups": len(m["runtime_snapshot"])}


def _load(snapshot: Path):
    mpath = Path(snapshot).resolve() / "manifest.json"
    if not mpath.is_file():
        raise ReleaseBlocked("SNAPSHOT_MANIFEST_MISSING")
    return mpath, json.loads(mpath.read_text(encoding="utf-8"))


def install(snapshot, *, approval: str):
    if approval != "INSTALL_CODE_ONLY":
        raise ReleaseBlocked("EXPLICIT_CODE_INSTALL_APPROVAL_REQUIRED")
    mpath, m = _load(snapshot)
    if m.get("state") != "SNAPSHOT_READY":
        raise ReleaseBlocked("SNAPSHOT_NOT_READY")
    src, code, runtime, _ = _paths(m["source"], m["code"], m["runtime"], mpath.parent.parent)
    _check_ports()
    # Validate the entire candidate state *before* any publication.
    for entry in m["entries"]:
        target = code / entry["path"]
        if entry["existed"]:
            if not target.is_file() or sha(target) != entry["before"]:
                raise ReleaseBlocked("CODE_CHANGED_SINCE_SNAPSHOT:" + entry["path"])
        elif target.exists():
            raise ReleaseBlocked("NEW_CODE_COLLISION:" + entry["path"])
    m["state"] = "INSTALL_IN_PROGRESS"
    _write_manifest(mpath, m)
    for entry in m["entries"]:
        rel = entry["path"]
        target = code / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        content = (src / rel).read_bytes()
        temp = target.with_name("." + target.name + "." + uuid.uuid4().hex + ".release")
        try:
            with temp.open("xb") as f:
                f.write(content); f.flush(); os.fsync(f.fileno())
            os.replace(temp, target)
        finally:
            temp.unlink(missing_ok=True)
        entry["installed"] = hashlib.sha256(content).hexdigest()
        _write_manifest(mpath, m)
    m["state"] = "INSTALLED_CODE_ONLY"
    _write_manifest(mpath, m)
    return {"status": m["state"], "code_files": len(m["entries"]),
            "runtime_unchanged": True, "snapshot": str(mpath.parent)}


def rollback(snapshot, *, approval: str):
    if approval != "ROLLBACK_CODE_ONLY":
        raise ReleaseBlocked("EXPLICIT_CODE_ROLLBACK_APPROVAL_REQUIRED")
    mpath, m = _load(snapshot)
    if m.get("state") not in ("INSTALL_IN_PROGRESS", "INSTALLED_CODE_ONLY",
                               "ROLLBACK_IN_PROGRESS"):
        raise ReleaseBlocked("NOT_AN_INSTALLED_SNAPSHOT")
    _, code, _, _ = _paths(m["source"], m["code"], m["runtime"], mpath.parent.parent)
    _check_ports()
    for entry in m["entries"]:
        installed = entry.get("installed")
        target = code / entry["path"]
        if installed and (not target.is_file() or sha(target) != installed):
            raise ReleaseBlocked("INSTALLED_CODE_CHANGED_REQUIRES_REVIEW:" + entry["path"])
    m["state"] = "ROLLBACK_IN_PROGRESS"
    _write_manifest(mpath, m)
    for entry in reversed(m["entries"]):
        if not entry.get("installed"):
            continue
        target = code / entry["path"]
        if entry["existed"]:
            backup = mpath.parent / "code_before" / entry["path"]
            if not backup.is_file() or sha(backup) != entry["before"]:
                raise ReleaseBlocked("CODE_BACKUP_HASH_MISMATCH:" + entry["path"])
            temp = target.with_name("." + target.name + "." + uuid.uuid4().hex + ".rollback")
            try:
                with backup.open("rb") as fr, temp.open("xb") as fw:
                    shutil.copyfileobj(fr, fw)
                    fw.flush(); os.fsync(fw.fileno())
                os.replace(temp, target)
            finally:
                temp.unlink(missing_ok=True)
        elif target.is_file() and sha(target) == entry["installed"]:
            # Delete ONLY code that this exact release created, never user data.
            target.unlink()
        entry["installed"] = None
        _write_manifest(mpath, m)
    m["state"] = "ROLLED_BACK_CODE_ONLY"
    _write_manifest(mpath, m)
    return {"status": m["state"], "runtime_unchanged": True}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mode", choices=("plan", "backup", "install", "rollback"),
                   default="plan")
    p.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument("--code", type=Path)
    p.add_argument("--runtime", type=Path)
    p.add_argument("--vault", type=Path)
    p.add_argument("--snapshot", type=Path)
    p.add_argument("--approval", default="")
    args = p.parse_args(argv)
    try:
        if args.mode in ("plan", "backup"):
            if not all((args.code, args.runtime, args.vault)):
                raise ReleaseBlocked("CODE_RUNTIME_EXTERNAL_VAULT_REQUIRED")
            fn = plan if args.mode == "plan" else create_snapshot
            result = fn(args.source, args.code, args.runtime, args.vault)
        elif args.mode == "install":
            result = install(args.snapshot, approval=args.approval)
        else:
            result = rollback(args.snapshot, approval=args.approval)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ReleaseBlocked, OSError, sqlite3.DatabaseError) as exc:
        print(json.dumps({"status":"BLOCKED","error":str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
