from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
import uuid
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import cv2
import numpy as np


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".avif"}


class LifecycleSafetyError(RuntimeError):
    """Raised when a requested lifecycle operation is not provably safe."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _runtime(runtime_root: str | Path) -> Path:
    return Path(runtime_root).expanduser().resolve()


def _safe_under(root: Path, *parts: str) -> Path:
    root = root.resolve()
    candidate = root.joinpath(*(str(part) for part in parts)).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise LifecycleSafetyError("Güvensiz dosya yolu engellendi.") from exc
    return candidate


def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + f".{uuid.uuid4().hex}.tmp")
    try:
        with temp.open("wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        try:
            if temp.exists():
                temp.unlink()
        except OSError:
            pass


def _atomic_write_png(path: Path, image: np.ndarray) -> None:
    ok, encoded = cv2.imencode(".png", image)
    if not ok:
        raise LifecycleSafetyError("Yeni çalışma görseli PNG olarak kodlanamadı.")
    _atomic_write_bytes(path, encoded.tobytes())


def _image_files(category_dir: Path) -> Iterable[Path]:
    if not category_dir.is_dir():
        return []
    return sorted(
        (
            path
            for path in category_dir.iterdir()
            if path.is_file() and path.suffix.casefold() in IMAGE_EXTS
        ),
        key=lambda path: path.name.casefold(),
    )


def _active_templates(settings: dict) -> Dict[str, Dict[str, str]]:
    result: Dict[str, Dict[str, str]] = {}
    categories = (settings or {}).get("kategoriler", {})
    if not isinstance(categories, dict):
        return result
    for category, category_data in categories.items():
        templates = (
            category_data.get("sablonlar", {})
            if isinstance(category_data, dict)
            else {}
        )
        if not isinstance(templates, dict):
            templates = {}
        result[str(category)] = {
            Path(str(filename)).stem.casefold(): str(filename)
            for filename in templates.keys()
        }
    return result


def _same_stem_files(category_dir: Path, identity: str) -> List[Path]:
    identity = str(identity or "").casefold()
    return [
        path
        for path in _image_files(category_dir)
        if path.stem.casefold() == identity
    ]


def _group_by_stem(category_dir: Path) -> Dict[str, List[Path]]:
    grouped: Dict[str, List[Path]] = {}
    for path in _image_files(category_dir):
        grouped.setdefault(path.stem.casefold(), []).append(path)
    return grouped


def _recovery_root(runtime_root: str | Path) -> Path:
    return (
        _runtime(runtime_root)
        / "SABLON_V2_MIMARI"
        / "recovery"
        / "lifecycle"
    )


def _operation_dir(
    runtime_root: str | Path,
    *,
    kind: str,
    category: str,
    identity: str,
) -> tuple[str, Path]:
    stamp = time.strftime("%Y%m%d_%H%M%S")
    operation_id = (
        f"{stamp}_{kind}_{category}_{identity}_{uuid.uuid4().hex[:8]}"
    )
    safe_id = "".join(
        ch if ch.isalnum() or ch in "._-" else "_"
        for ch in operation_id
    )
    path = _recovery_root(runtime_root) / safe_id
    path.mkdir(parents=True, exist_ok=False)
    return safe_id, path


def _write_manifest(operation_dir: Path, manifest: dict) -> None:
    payload = json.dumps(
        manifest,
        ensure_ascii=False,
        indent=2,
    ).encode("utf-8")
    _atomic_write_bytes(operation_dir / "manifest.json", payload)


def _file_record(path: Path, root: Path) -> dict:
    return {
        "name": path.name,
        "absolute_path": str(path.resolve()),
        "relative_path": path.resolve().relative_to(root.resolve()).as_posix(),
        "size_bytes": int(path.stat().st_size),
        "sha256": sha256_file(path),
    }


def _duplicate_rows(
    runtime: Path,
    settings: dict,
    area: str,
    root_name: str,
) -> List[dict]:
    root = runtime / root_name
    active = _active_templates(settings)
    rows: List[dict] = []
    categories = sorted(
        set(active)
        | (
            {path.name for path in root.iterdir() if path.is_dir()}
            if root.is_dir()
            else set()
        ),
        key=str.casefold,
    )

    for category in categories:
        category_dir = root / category
        for identity, files in _group_by_stem(category_dir).items():
            if len(files) < 2:
                continue
            active_name = active.get(category, {}).get(identity)
            names = [path.name for path in files]
            recommended_keep = (
                active_name
                if active_name and active_name in names
                else None
            )
            rows.append({
                "area": area,
                "category": category,
                "identity": identity,
                "files": [
                    _file_record(path, root)
                    for path in files
                ],
                "active_template": active_name,
                "recommended_keep": recommended_keep,
                "safe_recommendation": bool(recommended_keep),
                "requires_manual_choice": not bool(recommended_keep),
                "destructive_delete": False,
                "action": "MOVE_NON_KEEP_TO_RECOVERY",
            })
    return rows


def _working_orphans(runtime: Path, settings: dict) -> List[dict]:
    root = runtime / "2_SABLON_HAVUZU"
    active = _active_templates(settings)
    rows = []
    if not root.is_dir():
        return rows
    for category_dir in sorted(
        (path for path in root.iterdir() if path.is_dir()),
        key=lambda path: path.name.casefold(),
    ):
        active_stems = set(active.get(category_dir.name, {}))
        grouped = _group_by_stem(category_dir)
        for identity, files in grouped.items():
            if identity in active_stems:
                continue
            rows.append({
                "category": category_dir.name,
                "identity": identity,
                "files": [_file_record(path, root) for path in files],
                "action": "MOVE_TO_RECOVERY_ONLY",
                "requires_approval": True,
                "destructive_delete": False,
            })
    return rows


def _active_missing(runtime: Path, settings: dict) -> List[dict]:
    active = _active_templates(settings)
    working_root = runtime / "2_SABLON_HAVUZU"
    backup_root = runtime / "2_SABLON_HAVUZU_ORIJINAL_YEDEK"
    rows = []
    for category, identities in active.items():
        for identity, template_name in identities.items():
            work = _same_stem_files(working_root / category, identity)
            backup = _same_stem_files(backup_root / category, identity)
            if work and backup:
                continue
            rows.append({
                "category": category,
                "template": template_name,
                "identity": identity,
                "working_exists": bool(work),
                "backup_exists": bool(backup),
                "recommended_action": (
                    "RETIRE_DB_ORPHAN"
                    if not work and not backup
                    else (
                        "RESTORE_WORKING_FROM_BACKUP"
                        if backup and not work
                        else "REPLACE_ORIGINAL_REQUIRED"
                    )
                ),
                "requires_approval": True,
            })
    return rows


def _trash_records(runtime: Path, limit: int) -> List[dict]:
    root = runtime / "SILINEN_SABLONLAR_COP_KUTUSU"
    if not root.is_dir():
        return []
    rows = []
    metas = sorted(
        root.glob("*_meta.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for path in metas[:limit]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            data = {}
        rows.append({
            "meta_file": path.name,
            "category": data.get("kategori"),
            "template": data.get("sablon"),
            "source_was_missing": bool(data.get("source_was_missing")),
            "trash_image_name": data.get("trash_image_name"),
            "backup_trash_name": data.get("backup_trash_name"),
            "created_at": time.strftime(
                "%Y-%m-%d %H:%M:%S",
                time.localtime(path.stat().st_mtime),
            ),
        })
    return rows


def _lifecycle_recovery_records(runtime: Path, limit: int) -> List[dict]:
    root = _recovery_root(runtime)
    if not root.is_dir():
        return []
    rows = []
    manifests = sorted(
        root.glob("*/manifest.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for path in manifests[:limit]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        rows.append({
            "operation_id": data.get("operation_id") or path.parent.name,
            "kind": data.get("kind"),
            "state": data.get("state"),
            "category": data.get("category"),
            "identity": data.get("identity"),
            "template": data.get("template"),
            "created_at": data.get("created_at"),
            "undo_supported": bool(data.get("undo_supported")),
            "moved_count": len(data.get("moved", []) or []),
        })
    return rows


def _processing_recovery_records(runtime: Path, limit: int) -> List[dict]:
    root = runtime / "_KURTARMA_PROCESSING"
    if not root.is_dir():
        return []
    files = sorted(
        (path for path in root.rglob("*") if path.is_file()),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return [
        {
            "relative_path": path.relative_to(root).as_posix(),
            "size_bytes": int(path.stat().st_size),
            "sha256": (
                sha256_file(path)
                if path.suffix.casefold() in IMAGE_EXTS
                else None
            ),
        }
        for path in files[:limit]
    ]


def _staging_transaction_records(runtime: Path, limit: int) -> List[dict]:
    root = (
        runtime
        / "SABLON_V2_MIMARI"
        / "recovery"
        / "staging_transactions"
    )
    if not root.is_dir():
        return []
    rows = []
    files = sorted(
        root.glob("*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for path in files[:limit]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        rows.append({
            "transaction_id": data.get("transaction_id") or path.stem,
            "state": data.get("state"),
            "created_at": data.get("created_at"),
            "updated_at": data.get("updated_at"),
            "category": data.get("category"),
            "canonical_name": data.get("canonical_name"),
            "original_staging_path": data.get("original_staging_path"),
            "processing_path": data.get("processing_path"),
            "backup_path": data.get("backup_path"),
            "working_path": data.get("working_path"),
            "error": data.get("error"),
        })
    return rows


def lifecycle_center_report(
    runtime_root: str | Path,
    settings: dict,
    *,
    limit: int = 50,
) -> dict:
    runtime = _runtime(runtime_root)
    duplicates = (
        _duplicate_rows(
            runtime,
            settings,
            "WORKING",
            "2_SABLON_HAVUZU",
        )
        + _duplicate_rows(
            runtime,
            settings,
            "ORIGINAL_ARCHIVE",
            "2_SABLON_HAVUZU_ORIJINAL_YEDEK",
        )
    )
    working_orphans = _working_orphans(runtime, settings)
    active_missing = _active_missing(runtime, settings)
    trash = _trash_records(runtime, limit)
    lifecycle_recovery = _lifecycle_recovery_records(runtime, limit)
    processing_recovery = _processing_recovery_records(runtime, limit)
    staging_transactions = _staging_transaction_records(runtime, limit)

    return {
        "success": True,
        "read_only": True,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "runtime_root": str(runtime),
        "policy": {
            "automatic_permanent_delete": False,
            "duplicate_action": "MOVE_TO_RECOVERY",
            "working_orphan_action": "MOVE_TO_RECOVERY",
            "active_missing_requires_approval": True,
            "original_replace_archives_previous_bytes": True,
        },
        "summary": {
            "duplicate_identity_count": len(duplicates),
            "safe_duplicate_count": sum(
                1 for row in duplicates if row["safe_recommendation"]
            ),
            "manual_duplicate_count": sum(
                1 for row in duplicates if row["requires_manual_choice"]
            ),
            "working_orphan_count": len(working_orphans),
            "active_missing_count": len(active_missing),
            "trash_record_count": len(trash),
            "lifecycle_recovery_count": len(lifecycle_recovery),
            "processing_recovery_count": len(processing_recovery),
            "staging_transaction_count": len(staging_transactions),
            "staging_recovery_required_count": sum(
                1 for row in staging_transactions
                if row.get("state") == "RECOVERY_REQUIRED"
            ),
        },
        "duplicates": duplicates,
        "working_orphans": working_orphans,
        "active_missing": active_missing,
        "trash_records": trash,
        "lifecycle_recovery": lifecycle_recovery,
        "processing_recovery": processing_recovery,
        "staging_transactions": staging_transactions,
    }


def archive_duplicate_variants(
    runtime_root: str | Path,
    settings: dict,
    *,
    area: str,
    category: str,
    identity: str,
    keep_filename: str,
) -> dict:
    runtime = _runtime(runtime_root)
    area = str(area or "").upper()
    roots = {
        "WORKING": runtime / "2_SABLON_HAVUZU",
        "ORIGINAL_ARCHIVE": runtime / "2_SABLON_HAVUZU_ORIJINAL_YEDEK",
    }
    if area not in roots:
        raise LifecycleSafetyError("Geçersiz duplicate alanı.")

    root = roots[area]
    category_dir = _safe_under(root, category)
    files = _same_stem_files(category_dir, identity)
    if len(files) < 2:
        raise LifecycleSafetyError(
            "Bu kimlikte çözülecek birden fazla dosya bulunamadı."
        )

    names = [path.name for path in files]
    if keep_filename not in names:
        raise LifecycleSafetyError("Korunacak dosya duplicate kümesinde yok.")

    active_name = _active_templates(settings).get(category, {}).get(
        str(identity).casefold()
    )
    if active_name and active_name in names and keep_filename != active_name:
        raise LifecycleSafetyError(
            "Aktif DB dosyası mevcutken farklı dosya korunamaz."
        )

    operation_id, op_dir = _operation_dir(
        runtime,
        kind="duplicate_archive",
        category=category,
        identity=identity,
    )
    moved = []
    manifest = {
        "operation_id": operation_id,
        "kind": "DUPLICATE_ARCHIVE",
        "state": "PENDING",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "category": category,
        "identity": identity,
        "area": area,
        "keep_filename": keep_filename,
        "active_template": active_name,
        "undo_supported": True,
        "moved": moved,
    }
    _write_manifest(op_dir, manifest)

    try:
        archive_dir = op_dir / "archived"
        archive_dir.mkdir(parents=True, exist_ok=True)
        for source in files:
            if source.name == keep_filename:
                continue
            target = archive_dir / source.name
            if target.exists():
                raise LifecycleSafetyError(
                    f"Recovery hedefi zaten var: {target.name}"
                )
            before = _file_record(source, runtime)
            shutil.move(str(source), str(target))
            moved.append({
                "from": str(source.resolve()),
                "to": str(target.resolve()),
                "name": source.name,
                "sha256": before["sha256"],
                "size_bytes": before["size_bytes"],
            })
            manifest["moved"] = moved
            _write_manifest(op_dir, manifest)

        manifest["state"] = "COMMITTED"
        manifest["completed_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        _write_manifest(op_dir, manifest)
        return manifest
    except Exception:
        for item in reversed(moved):
            src = Path(item["from"])
            dst = Path(item["to"])
            if dst.exists() and not src.exists():
                src.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(dst), str(src))
        manifest["state"] = "ROLLED_BACK"
        manifest["completed_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        _write_manifest(op_dir, manifest)
        raise


def archive_working_orphan(
    runtime_root: str | Path,
    settings: dict,
    *,
    category: str,
    identity: str,
) -> dict:
    runtime = _runtime(runtime_root)
    active = _active_templates(settings)
    if str(identity).casefold() in active.get(category, {}):
        raise LifecycleSafetyError(
            "Aktif DB kimliği çalışma yetimi olarak arşivlenemez."
        )

    root = runtime / "2_SABLON_HAVUZU"
    files = _same_stem_files(root / category, identity)
    if not files:
        raise LifecycleSafetyError("Arşivlenecek çalışma yetimi bulunamadı.")

    operation_id, op_dir = _operation_dir(
        runtime,
        kind="working_orphan",
        category=category,
        identity=identity,
    )
    moved = []
    manifest = {
        "operation_id": operation_id,
        "kind": "WORKING_ORPHAN_ARCHIVE",
        "state": "PENDING",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "category": category,
        "identity": identity,
        "undo_supported": True,
        "moved": moved,
    }
    _write_manifest(op_dir, manifest)

    try:
        archive_dir = op_dir / "archived"
        archive_dir.mkdir(parents=True, exist_ok=True)
        for source in files:
            target = archive_dir / source.name
            before = _file_record(source, runtime)
            shutil.move(str(source), str(target))
            moved.append({
                "from": str(source.resolve()),
                "to": str(target.resolve()),
                "name": source.name,
                "sha256": before["sha256"],
                "size_bytes": before["size_bytes"],
            })
            manifest["moved"] = moved
            _write_manifest(op_dir, manifest)

        manifest["state"] = "COMMITTED"
        manifest["completed_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        _write_manifest(op_dir, manifest)
        return manifest
    except Exception:
        for item in reversed(moved):
            src = Path(item["from"])
            dst = Path(item["to"])
            if dst.exists() and not src.exists():
                src.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(dst), str(src))
        manifest["state"] = "ROLLED_BACK"
        manifest["completed_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        _write_manifest(op_dir, manifest)
        raise


def replace_original_and_working(
    runtime_root: str | Path,
    *,
    category: str,
    template: str,
    upload_filename: str,
    upload_bytes: bytes,
) -> dict:
    runtime = _runtime(runtime_root)
    if not upload_bytes:
        raise LifecycleSafetyError("Seçilen yeni ham dosya boş.")

    suffix = Path(str(upload_filename or "")).suffix.casefold()
    if suffix not in IMAGE_EXTS:
        raise LifecycleSafetyError(
            "Desteklenmeyen görsel biçimi. PNG/JPG/JPEG/WEBP/AVIF kullanın."
        )

    image = cv2.imdecode(
        np.frombuffer(upload_bytes, dtype=np.uint8),
        cv2.IMREAD_UNCHANGED,
    )
    if image is None:
        raise LifecycleSafetyError("Seçilen yeni ham görsel okunamadı.")

    identity = Path(template).stem.casefold()
    backup_root = runtime / "2_SABLON_HAVUZU_ORIJINAL_YEDEK"
    working_root = runtime / "2_SABLON_HAVUZU"
    backup_cat = _safe_under(backup_root, category)
    working_cat = _safe_under(working_root, category)
    backup_cat.mkdir(parents=True, exist_ok=True)
    working_cat.mkdir(parents=True, exist_ok=True)

    old_backups = _same_stem_files(backup_cat, identity)
    old_working = _same_stem_files(working_cat, identity)
    working_filename = Path(template).stem + ".png"
    new_backup_filename = Path(template).stem + suffix
    new_backup = _safe_under(backup_cat, new_backup_filename)
    new_working = _safe_under(working_cat, working_filename)

    operation_id, op_dir = _operation_dir(
        runtime,
        kind="replace_original",
        category=category,
        identity=identity,
    )
    moved = []
    manifest = {
        "operation_id": operation_id,
        "kind": "REPLACE_ORIGINAL",
        "state": "PENDING",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "category": category,
        "identity": identity,
        "template": template,
        "upload_filename": upload_filename,
        "new_backup_filename": new_backup_filename,
        "new_working_filename": working_filename,
        "undo_supported": False,
        "moved": moved,
    }
    _write_manifest(op_dir, manifest)

    try:
        for label, paths in (
            ("original_before", old_backups),
            ("working_before", old_working),
        ):
            archive_dir = op_dir / label
            archive_dir.mkdir(parents=True, exist_ok=True)
            for source in paths:
                target = archive_dir / source.name
                before_hash = sha256_file(source)
                before_size = int(source.stat().st_size)
                shutil.move(str(source), str(target))
                moved.append({
                    "from": str(source.resolve()),
                    "to": str(target.resolve()),
                    "name": source.name,
                    "role": label,
                    "sha256": before_hash,
                    "size_bytes": before_size,
                })
                manifest["moved"] = moved
                _write_manifest(op_dir, manifest)

        _atomic_write_bytes(new_backup, upload_bytes)
        _atomic_write_png(new_working, image)

        manifest["new_backup_sha256"] = sha256_file(new_backup)
        manifest["new_working_sha256"] = sha256_file(new_working)
        manifest["new_backup_absolute"] = str(new_backup.resolve())
        manifest["new_working_absolute"] = str(new_working.resolve())
        manifest["state"] = "COMMITTED"
        manifest["completed_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        _write_manifest(op_dir, manifest)
        return manifest
    except Exception:
        for path in (new_backup, new_working):
            try:
                if path.exists():
                    path.unlink()
            except OSError:
                pass
        for item in reversed(moved):
            original = Path(item["from"])
            archived = Path(item["to"])
            if archived.exists() and not original.exists():
                original.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(archived), str(original))
        manifest["state"] = "ROLLED_BACK"
        manifest["completed_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        _write_manifest(op_dir, manifest)
        raise


def rollback_replace_original(
    runtime_root: str | Path,
    operation_id: str,
) -> dict:
    """Restore pre-replacement bytes when the surrounding DB transaction fails."""
    root = _recovery_root(runtime_root)
    manifest_path = root / str(operation_id) / "manifest.json"
    if not manifest_path.is_file():
        raise LifecycleSafetyError(
            "Kaynak değiştirme rollback manifesti bulunamadı."
        )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("kind") != "REPLACE_ORIGINAL":
        raise LifecycleSafetyError(
            "Bu recovery operasyonu kaynak değiştirme işlemi değil."
        )
    if manifest.get("state") != "COMMITTED":
        raise LifecycleSafetyError(
            "Kaynak değiştirme operasyonu rollback için COMMITTED durumda değil."
        )

    op_dir = manifest_path.parent
    replacement_after = op_dir / "replacement_after"
    replacement_after.mkdir(parents=True, exist_ok=True)

    new_paths = []
    for key, hash_key in (
        ("new_backup_absolute", "new_backup_sha256"),
        ("new_working_absolute", "new_working_sha256"),
    ):
        raw_path = manifest.get(key)
        if not raw_path:
            continue
        path = Path(raw_path)
        if not path.exists():
            continue
        expected_hash = str(manifest.get(hash_key) or "")
        if expected_hash and sha256_file(path) != expected_hash:
            raise LifecycleSafetyError(
                f"Rollback engellendi; yeni dosya işlemden sonra değişmiş: {path.name}"
            )
        target = replacement_after / path.name
        counter = 1
        while target.exists():
            target = replacement_after / (
                f"{path.stem}_{counter}{path.suffix}"
            )
            counter += 1
        shutil.move(str(path), str(target))
        new_paths.append({
            "from": str(path.resolve()),
            "to": str(target.resolve()),
            "sha256": expected_hash,
        })

    restored = []
    try:
        for item in reversed(list(manifest.get("moved", []) or [])):
            original = Path(item["from"])
            archived = Path(item["to"])
            if original.exists():
                raise LifecycleSafetyError(
                    f"Rollback hedefinde dosya zaten var: {original.name}"
                )
            if not archived.is_file():
                raise LifecycleSafetyError(
                    f"Rollback recovery dosyası bulunamadı: {archived.name}"
                )
            if sha256_file(archived) != item.get("sha256"):
                raise LifecycleSafetyError(
                    f"Rollback recovery SHA256 değişmiş: {archived.name}"
                )
            original.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(archived), str(original))
            restored.append(str(original.resolve()))
    except Exception:
        # Best-effort: put the new replacement bytes back if restoring old
        # files could not be completed.
        for item in new_paths:
            original_new = Path(item["from"])
            archived_new = Path(item["to"])
            if archived_new.exists() and not original_new.exists():
                original_new.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(archived_new), str(original_new))
        raise

    manifest["state"] = "ROLLED_BACK_AFTER_DB_FAILURE"
    manifest["rolled_back_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    manifest["rollback_restored"] = restored
    manifest["replacement_after"] = new_paths
    _write_manifest(op_dir, manifest)
    return manifest


def undo_lifecycle_operation(
    runtime_root: str | Path,
    operation_id: Optional[str] = None,
) -> dict:
    root = _recovery_root(runtime_root)
    if not root.is_dir():
        raise LifecycleSafetyError("Geri alınabilir lifecycle işlemi yok.")

    manifests = sorted(
        root.glob("*/manifest.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if operation_id:
        manifests = [
            path for path in manifests
            if path.parent.name == operation_id
        ]
    manifest_path = next(
        (
            path for path in manifests
            if json.loads(path.read_text(encoding="utf-8")).get(
                "undo_supported"
            )
            and json.loads(path.read_text(encoding="utf-8")).get("state")
            == "COMMITTED"
        ),
        None,
    )
    if manifest_path is None:
        raise LifecycleSafetyError(
            "Geri alınabilecek tamamlanmış lifecycle işlemi bulunamadı."
        )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    moved = list(manifest.get("moved", []) or [])
    for item in moved:
        original = Path(item["from"])
        archived = Path(item["to"])
        if original.exists():
            raise LifecycleSafetyError(
                f"Geri alma hedefinde dosya zaten var: {original.name}"
            )
        if not archived.is_file():
            raise LifecycleSafetyError(
                f"Recovery dosyası bulunamadı: {archived.name}"
            )
        if sha256_file(archived) != item.get("sha256"):
            raise LifecycleSafetyError(
                f"Recovery dosyasının SHA256 değeri değişmiş: {archived.name}"
            )

    restored = []
    try:
        for item in reversed(moved):
            original = Path(item["from"])
            archived = Path(item["to"])
            original.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(archived), str(original))
            restored.append({
                "name": original.name,
                "absolute_path": str(original.resolve()),
            })
    except Exception:
        for item in restored:
            original = Path(item["absolute_path"])
            archived_match = next(
                (
                    Path(row["to"])
                    for row in moved
                    if row["name"] == original.name
                ),
                None,
            )
            if (
                archived_match is not None
                and original.exists()
                and not archived_match.exists()
            ):
                archived_match.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(original), str(archived_match))
        raise

    manifest["state"] = "UNDONE"
    manifest["undone_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    manifest["restored"] = restored
    _write_manifest(manifest_path.parent, manifest)
    return manifest
