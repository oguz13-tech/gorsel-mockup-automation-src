"""V4.4 G3 -- read-only Windows production audit and explicitly approved SQLite backup.

The live legacy database / WAL, approved geometry and image pools are NEVER
modified here. An online SQLite snapshot is verified through an isolated
restore-copy before being marked usable. All outputs are create-only and local.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
from typing import Any

def store_v4_root() -> Path:
    override = os.getenv("V4_UNIFIED_LOCAL_STATE", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    base = os.getenv("LOCALAPPDATA")
    return (Path(base) if base else Path.home() / ".gorsel_mockup") / "GorselMockup" / "UnifiedV4"

BACKUP_CONFIRM = "YEDEK_AL_V44"
LEGACY_RELATIVE_DB = Path("SABLON_V2_MIMARI") / "ayarlar.db"
LEDGER_DB = "v4_ortak_uretim.sqlite3"


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _read_connection(path: Path) -> sqlite3.Connection:
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"SQLite dosyası bulunamadı veya sembolik bağlantı: {path.name}")
    con = sqlite3.connect(path.resolve(strict=True).as_uri() + "?mode=ro", uri=True, timeout=20)
    con.execute("PRAGMA busy_timeout=20000")
    return con


def _read_database(path: Path, *, role: str | None = None) -> dict[str, Any]:
    con = _read_connection(path)
    try:
        verdict = con.execute("PRAGMA quick_check").fetchone()[0]
        tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        wanted = ("categories", "templates", "template_profiles") if (role or path.name) in ("ayarlar.db", "approved_geometry") else ("artifact",)
        counts = {}
        for name in wanted:
            if name in tables:
                counts[name] = int(con.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0])
        return {"integrity": verdict, "counts": counts, "required_tables_missing": sorted(set(wanted) - tables)}
    finally:
        con.close()


def _output_audit(db: Path, output_root: Path) -> dict[str, Any]:
    report = {"status_counts": {}, "verified": 0, "missing": 0, "sha_mismatch": 0,
              "path_unsafe": 0, "unfinished": 0, "user_removed": 0, "problems": []}
    if not db.is_file():
        return report
    con = _read_connection(db)
    try:
        rows = con.execute("SELECT key,status,output,output_sha FROM artifact ORDER BY key")
        for key, status, output, expected in rows:
            report["status_counts"][status] = report["status_counts"].get(status, 0) + 1
            if status == "USER_REMOVED":
                # Intentionally deleted by the owner with archived DB evidence.
                # Not a missing render and never a candidate for auto-recovery.
                report["user_removed"] += 1
                continue
            if status != "RENDERED":
                report["unfinished"] += 1
                continue
            path = Path(output)
            if path.is_symlink():
                kind = "path_unsafe"
            else:
                try:
                    resolved = path.resolve(strict=False)
                    root = output_root.resolve(strict=False)
                    kind = "path_unsafe" if root not in resolved.parents else (
                        "missing" if not path.is_file() else (
                            "verified" if _sha(path) == expected else "sha_mismatch"))
                except (OSError, ValueError):
                    kind = "path_unsafe"
            report[kind] += 1
            if kind != "verified" and len(report["problems"]) < 40:
                report["problems"].append({"key": key, "reason": kind})
    finally:
        con.close()
    return report


def inspect_workspaces(runtime_root: Path, production_root: Path | None = None) -> dict[str, Any]:
    """Read-only, no mkdir, no database creation, no write or side effects."""
    runtime_root = Path(runtime_root).absolute()
    production_root = Path(production_root or store_v4_root()).absolute()
    if runtime_root.is_symlink() or production_root.is_symlink():
        raise ValueError("Sembolik bağlı çalışma alanı denetlenemez.")
    result: dict[str, Any] = {"mode": "READ_ONLY", "workspace_exists": runtime_root.is_dir(),
                              "db": {}, "alerts": [], "production": {}}
    for label, path in (("approved_geometry", runtime_root / LEGACY_RELATIVE_DB),
                        ("production_ledger", production_root / LEDGER_DB)):
        if not path.is_file() or path.is_symlink():
            result["db"][label] = {"present": False}
            result["alerts"].append("SQLite bulunamadı: " + label)
            continue
        try:
            data = _read_database(path)
            result["db"][label] = {"present": True, **data}
            if data["integrity"] != "ok" or data["required_tables_missing"]:
                result["alerts"].append("SQLite bütünlüğü / şema: " + label)
        except (sqlite3.Error, OSError, ValueError) as exc:
            result["db"][label] = {"present": True, "error": str(exc)}
            result["alerts"].append("SQLite salt-okunur kontrol başarısız: " + label)
    if result["db"].get("production_ledger", {}).get("present"):
        try:
            result["production"] = _output_audit(production_root / LEDGER_DB,
                                                  production_root / "uretilen_gorseller")
            if result["production"]["sha_mismatch"] or result["production"]["path_unsafe"]:
                result["alerts"].append("Üretim SHA veya dosya yolu uyuşmazlığı")
        except (sqlite3.Error, OSError, ValueError) as exc:
            result["alerts"].append("Çıktı audit başarısız: " + str(exc))
    if "onedrive" in str(runtime_root).lower():
        result["alerts"].append("OneDrive çalışma alanı: canlı SQLite için senkron riski; otomatik taşıma YOK")
    result["safe_to_claim_final"] = not result["alerts"] and result["production"].get("unfinished", 0) == 0
    return result


def _snapshot(source: Path, dest: Path, *, role: str) -> dict[str, Any]:
    """SQLite online backup including committed WAL changes; exclusive dest."""
    if dest.exists() or dest.is_symlink():
        raise FileExistsError("Yedek hedefi zaten mevcut.")
    src = _read_connection(source)
    target = None
    try:
        target = sqlite3.connect(str(dest), timeout=30)
        src.backup(target, pages=256, sleep=0.05)
        target.commit()
        if target.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Yedek integrity_check başarısız.")
    finally:
        if target is not None:
            target.close()
        src.close()
    if not dest.is_file():
        raise RuntimeError("SQLite snapshot oluşturulamadı.")
    # Restore rehearsal on a *third*, isolated temp file. The original remains untouched.
    with tempfile.TemporaryDirectory(prefix="g3-restore-") as td:
        restored = Path(td) / "restore_trial.db"
        shutil.copyfile(dest, restored)
        proof = _read_database(restored, role=role)
        if proof["integrity"] != "ok":
            raise ValueError("Geri yükleme provasındaki SQLite hatalı.")
    return {"backup_sha256": _sha(dest), "bytes": dest.stat().st_size,
            "restored_counts": proof["counts"], "integrity": "ok",
            "restore_trial": "PASS"}


def backup_and_restore_trial(runtime_root: Path, production_root: Path | None = None, *,
                             destination_root: Path | None = None, confirm: str = "") -> dict[str, Any]:
    """Explicit operator action: create-only snapshots OUTSIDE source/cloud; no auto DB migration."""
    if confirm != BACKUP_CONFIRM:
        raise PermissionError("Yedek için açık kullanıcı onayı gerekli.")
    runtime_root = Path(runtime_root).absolute()
    production_root = Path(production_root or store_v4_root()).absolute()
    output = Path(destination_root or (
        Path(os.getenv("LOCALAPPDATA") or (Path.home() / ".gorsel_mockup")) / "GorselMockup" / "G3_GUVENLI_YEDEK"
    )).absolute()
    if any(p.is_symlink() for p in (runtime_root, production_root, output)):
        raise ValueError("Sembolik bağlantı içeren kök dizin kabul edilmiyor.")
    if any(tag in str(output).lower() for tag in ("onedrive", "dropbox", "sharepoint")):
        raise ValueError("Yedek bulut senkron klasörüne kaydedilemez.")
    sources = {"approved_geometry": runtime_root / LEGACY_RELATIVE_DB,
               "production_ledger": production_root / LEDGER_DB}
    for source in sources.values():
        _read_database(source)  # fail before creating any backup folder
        if output == source.parent or output in source.parents or source in output.parents:
            raise ValueError("Yedek kaynağın içinde veya aynı yol üzerinde olamaz.")
    output.mkdir(parents=True, exist_ok=True)
    destination = output / ("V44_G3_" + dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%f")
                            + "_" + os.urandom(4).hex())
    destination.mkdir(mode=0o700)
    result: dict[str, Any] = {"mode": "EXPLICIT_BACKUP", "snapshots": {},
                              "restore_trial": "PENDING", "report_path": ""}
    try:
        for label, source in sources.items():
            dst = destination / (label + ".sqlite3")
            result["snapshots"][label] = {"filename": dst.name, **_snapshot(source, dst, role=label)}
        result["restore_trial"] = "PASS"
        report = destination / "G3_YEDEK_KANIT.json"
        with report.open("x", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, sort_keys=True, indent=2)
            f.flush()
            os.fsync(f.fileno())
        result["report_path"] = str(report)
        return result
    except Exception:
        # Do not delete partial backup evidence; never touch originals.
        raise


def backup_manifest_verify(manifest_path: Path) -> dict[str, Any]:
    """Read-only verification of an existing backup; never restores over live DB."""
    manifest_path = Path(manifest_path)
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise ValueError("Yedek manifesti güvenli değil.")
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if data.get("restore_trial") != "PASS":
        raise ValueError("Yedek daha önce geri yükleme provasını geçmemiş.")
    checks = {}
    for label in ("approved_geometry", "production_ledger"):
        entry = data["snapshots"][label]
        name = entry["filename"]
        if name != label + ".sqlite3":
            raise ValueError("Yedek ismi beklenenden farklı.")
        path = manifest_path.parent / name
        if path.is_symlink() or not path.is_file() or _sha(path) != entry["backup_sha256"]:
            raise ValueError("Yedek SHA doğrulanamadı: " + label)
        present = _read_database(path, role=label)
        if present["integrity"] != "ok" or present["counts"] != entry["restored_counts"]:
            raise ValueError("Yedek satır adetleri uyuşmuyor: " + label)
        checks[label] = "SHA_AND_SQLITE_VERIFIED"
    return checks
