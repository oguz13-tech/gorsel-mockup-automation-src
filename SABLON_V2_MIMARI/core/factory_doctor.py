"""Read-only integrity doctor for the mockup production workspace.

The doctor never edits templates, approvals, databases, outputs, or manifests.
It is intentionally separate from repair actions: first observe, then decide.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


PRODUCTION_CATEGORIES = (
    "01_Wifi_Kutusu",
    "02_Cam_Tablo_Dikey",
    "02_Cam_Tablo_Yatay",
    "03_Ahsap_Tablo",
    "04_Cam_Dograma",
    "05_Ocak_Arkasi",
)
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".avif")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _readonly_sqlite(path: Path) -> sqlite3.Connection:
    uri = f"file:{path.resolve().as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _safe_relative(root: Path, relative: str) -> Path | None:
    try:
        root_resolved = root.resolve()
        candidate = (root_resolved / str(relative)).resolve()
        if candidate == root_resolved or root_resolved in candidate.parents:
            return candidate
    except Exception:
        pass
    return None


def _backup_for_template(
    backup_root: Path,
    category: str,
    template_path: Path,
) -> Path | None:
    stem = template_path.stem
    cat_dir = backup_root / category
    for ext in IMAGE_EXTS:
        candidate = cat_dir / f"{stem}{ext}"
        if candidate.is_file():
            return candidate
    return None


def _json_dict(value: Any) -> dict:
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _positive_on_plan(plan: Any) -> bool:
    if not isinstance(plan, dict):
        return False
    return bool(plan.get("object_boxes") or plan.get("add_brush"))


def run_factory_doctor(
    runtime_root: str | os.PathLike,
    source_root: str | os.PathLike | None = None,
    *,
    deep: bool = True,
) -> dict:
    """Return a structured, read-only integrity report."""
    runtime = Path(runtime_root).expanduser().resolve()
    source = (
        Path(source_root).expanduser().resolve()
        if source_root is not None
        else runtime
    )

    errors: list[dict] = []
    warnings: list[dict] = []
    info: list[dict] = []
    checks: dict[str, Any] = {}

    def add_error(code: str, message: str, **details):
        errors.append({"code": code, "message": message, **details})

    def add_warning(code: str, message: str, **details):
        warnings.append({"code": code, "message": message, **details})

    def add_info(code: str, message: str, **details):
        info.append({"code": code, "message": message, **details})

    checks["runtime_root"] = str(runtime)
    checks["source_root"] = str(source)

    if not runtime.is_dir():
        add_error(
            "RUNTIME_MISSING",
            f"Runtime workspace bulunamadı: {runtime}",
        )
        return {
            "ready": False,
            "error_count": len(errors),
            "warning_count": len(warnings),
            "errors": errors,
            "warnings": warnings,
            "info": info,
            "checks": checks,
        }

    required_dirs = {
        "masters": runtime / "1_GELEN_KAGGLE_BASKILARI",
        "templates": runtime / "2_SABLON_HAVUZU",
        "template_backups": runtime / "2_SABLON_HAVUZU_ORIJINAL_YEDEK",
        "outputs": runtime / "3_URETILEN_MOCKUPLAR",
        "excel": runtime / "4_EXCEL_YUKLEME_LISTELERI",
        "review": runtime / "SABLON_V2_MIMARI",
    }
    dir_state = {}
    for key, path in required_dirs.items():
        exists = path.is_dir()
        dir_state[key] = {"path": str(path), "exists": exists}
        if not exists:
            severity = add_error if key in {
                "masters",
                "templates",
                "template_backups",
                "review",
            } else add_warning
            severity(
                "REQUIRED_DIR_MISSING",
                f"Gerekli klasör yok: {path}",
                component=key,
            )
    checks["directories"] = dir_state

    lowered = str(runtime).casefold()
    if any(token in lowered for token in (
        "onedrive",
        "dropbox",
        "google drive",
        "google\drive",
    )):
        add_warning(
            "SYNCED_RUNTIME_DB_RISK",
            "Runtime workspace senkronize bir bulut klasöründe görünüyor. "
            "Görseller burada kalabilir; ancak canlı SQLite DB/WAL dosyaları "
            "uzun vadede yerel senkronize-olmayan bir klasöre taşınırsa "
            "kilit/senkron çakışması riski azalır.",
        )

    try:
        usage = shutil.disk_usage(runtime)
        free_gb = usage.free / (1024 ** 3)
        checks["disk_free_gb"] = round(free_gb, 2)
        if free_gb < 2.0:
            add_error(
                "LOW_DISK_SPACE",
                f"Boş disk alanı kritik: {free_gb:.2f} GB",
            )
        elif free_gb < 10.0:
            add_warning(
                "LOW_DISK_SPACE",
                f"Boş disk alanı düşük: {free_gb:.2f} GB",
            )
    except Exception as exc:
        add_warning("DISK_CHECK_FAILED", f"Disk alanı okunamadı: {exc}")

    # ------------------------------------------------------------------
    # Manifest / master artwork
    # ------------------------------------------------------------------
    factory_dir = required_dirs["masters"]
    manifest_path = factory_dir / "manifest.json"
    manifest_summary = {
        "path": str(manifest_path),
        "item_count": 0,
        "missing_sources": [],
        "duplicate_master_ids": [],
    }
    if not manifest_path.is_file():
        add_error("MANIFEST_MISSING", f"manifest.json yok: {manifest_path}")
    else:
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            items = payload.get("items", []) if isinstance(payload, dict) else []
            if not isinstance(items, list) or not items:
                add_error("MANIFEST_EMPTY", "manifest items boş/geçersiz.")
                items = []
            manifest_summary["item_count"] = len(items)

            master_ids = [
                str(item.get("master_id") or "")
                for item in items
                if isinstance(item, dict)
            ]
            duplicate_ids = sorted([
                mid
                for mid, count in Counter(master_ids).items()
                if mid and count > 1
            ])
            manifest_summary["duplicate_master_ids"] = duplicate_ids
            if duplicate_ids:
                add_error(
                    "DUPLICATE_MASTER_ID",
                    "Manifest içinde tekrar eden master_id var: "
                    + ", ".join(duplicate_ids),
                )

            for index, item in enumerate(items, start=1):
                if not isinstance(item, dict):
                    add_error(
                        "MANIFEST_ITEM_INVALID",
                        f"Manifest item#{index} nesne değil.",
                    )
                    continue
                master_id = str(item.get("master_id") or f"item#{index}")
                for orientation, fallback_key in (
                    ("horizontal", "horizontal_path"),
                    ("vertical", "vertical_path"),
                ):
                    node = item.get(orientation)
                    raw = (
                        node.get("file", "")
                        if isinstance(node, dict)
                        else ""
                    ) or item.get(fallback_key, "")
                    if not raw:
                        manifest_summary["missing_sources"].append(
                            f"{master_id}:{orientation}"
                        )
                        continue
                    raw_path = Path(str(raw))
                    candidate = (
                        raw_path
                        if raw_path.is_absolute()
                        else factory_dir / raw_path
                    )
                    if not candidate.is_file() or candidate.stat().st_size <= 0:
                        manifest_summary["missing_sources"].append(
                            f"{master_id}:{orientation}:{candidate}"
                        )

            if manifest_summary["missing_sources"]:
                add_error(
                    "MASTER_SOURCE_MISSING",
                    "Manifestte eksik/boş H-V master kaynakları var.",
                    examples=manifest_summary["missing_sources"][:10],
                )
        except Exception as exc:
            add_error(
                "MANIFEST_UNREADABLE",
                f"manifest.json okunamadı: {exc}",
            )
    checks["manifest"] = manifest_summary

    # ------------------------------------------------------------------
    # Review DB / approved-template integrity
    # ------------------------------------------------------------------
    review_db = required_dirs["review"] / "ayarlar.db"
    template_root = required_dirs["templates"]
    backup_root = required_dirs["template_backups"]
    review_summary = {
        "path": str(review_db),
        "quick_check": None,
        "approved_by_category": {},
        "duplicate_active_approved_uids": [],
        "missing_sources": 0,
        "stale_hashes": 0,
        "missing_backups": 0,
        "invalid_geometry_records": 0,
        "stale_on_plan_records": 0,
    }

    if not review_db.is_file():
        add_error("REVIEW_DB_MISSING", f"Review DB yok: {review_db}")
    else:
        conn = None
        try:
            conn = _readonly_sqlite(review_db)
            quick = conn.execute("PRAGMA quick_check").fetchone()
            quick_value = str(quick[0] if quick else "unknown")
            review_summary["quick_check"] = quick_value
            if quick_value.lower() != "ok":
                add_error(
                    "REVIEW_DB_CORRUPT",
                    f"Review DB quick_check başarısız: {quick_value}",
                )

            table_names = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            needed = {"template_profiles", "templates", "categories"}
            missing_tables = sorted(needed - table_names)
            if missing_tables:
                add_error(
                    "REVIEW_DB_SCHEMA_MISSING",
                    "Review DB tabloları eksik: "
                    + ", ".join(missing_tables),
                )
            else:
                rows = conn.execute(
                    """SELECT rowid AS profile_rowid, template_uid, category,
                              source_relative_path, source_asset_sha256,
                              orientation, nominal_aspect, surface_quad,
                              has_occlusion, review_status, is_active
                       FROM template_profiles
                       WHERE review_status='APPROVED' AND is_active=1"""
                ).fetchall()

                by_category = Counter(str(row["category"]) for row in rows)
                review_summary["approved_by_category"] = dict(by_category)
                for category in PRODUCTION_CATEGORIES:
                    if by_category.get(category, 0) <= 0:
                        add_error(
                            "NO_APPROVED_TEMPLATE",
                            f"{category}: source-valid kontrolüne aday "
                            "aktif APPROVED profil yok.",
                            category=category,
                        )

                uid_counts = Counter(
                    str(row["template_uid"] or "") for row in rows
                )
                duplicate_uids = sorted([
                    uid
                    for uid, count in uid_counts.items()
                    if uid and count > 1
                ])
                review_summary[
                    "duplicate_active_approved_uids"
                ] = duplicate_uids
                if duplicate_uids:
                    add_error(
                        "DUPLICATE_APPROVED_UID",
                        "Birden fazla aktif APPROVED profile sahip UID var.",
                        examples=duplicate_uids[:10],
                    )

                legacy_rows = conn.execute(
                    "SELECT category_id, filename, data FROM templates"
                ).fetchall()
                legacy = {
                    (str(row["category_id"]), str(row["filename"])): _json_dict(
                        row["data"]
                    )
                    for row in legacy_rows
                }

                for row in rows:
                    category = str(row["category"] or "")
                    relative = str(row["source_relative_path"] or "")
                    source_path = _safe_relative(template_root, relative)
                    if source_path is None or not source_path.is_file():
                        review_summary["missing_sources"] += 1
                        add_error(
                            "APPROVED_SOURCE_MISSING",
                            f"APPROVED kaynak yok/güvensiz: {relative}",
                            template_uid=row["template_uid"],
                        )
                        continue

                    if deep:
                        try:
                            actual_sha = _sha256_file(source_path)
                        except Exception as exc:
                            add_error(
                                "APPROVED_HASH_READ_FAILED",
                                f"Şablon hash okunamadı: {source_path}: {exc}",
                            )
                            continue
                        expected_sha = str(
                            row["source_asset_sha256"] or ""
                        )
                        if not expected_sha or actual_sha != expected_sha:
                            review_summary["stale_hashes"] += 1
                            add_error(
                                "APPROVED_SOURCE_STALE",
                                "APPROVED profil farklı kaynak bytes'ına bağlı.",
                                template_uid=row["template_uid"],
                                path=str(source_path),
                            )

                    backup = _backup_for_template(
                        backup_root,
                        category,
                        source_path,
                    )
                    if backup is None:
                        review_summary["missing_backups"] += 1
                        add_warning(
                            "ORIGINAL_BACKUP_MISSING",
                            f"Orijinal yedek bulunamadı: "
                            f"{category}/{source_path.stem}",
                        )

                    try:
                        quad = json.loads(row["surface_quad"] or "null")
                        valid_quad = (
                            isinstance(quad, list)
                            and len(quad) == 4
                            and all(
                                isinstance(point, list)
                                and len(point) == 2
                                and all(
                                    isinstance(value, (int, float))
                                    for value in point
                                )
                                for point in quad
                            )
                        )
                    except Exception:
                        valid_quad = False
                    if not valid_quad:
                        review_summary["invalid_geometry_records"] += 1
                        add_error(
                            "APPROVED_GEOMETRY_INVALID",
                            f"APPROVED quad bozuk: {row['template_uid']}",
                        )

                    orientation = str(row["orientation"] or "").upper()
                    if orientation not in {"H", "V"}:
                        add_error(
                            "APPROVED_ORIENTATION_INVALID",
                            f"Fiziksel yön geçersiz: {row['template_uid']} "
                            f"({orientation or 'EMPTY'})",
                        )

                    try:
                        nominal = float(row["nominal_aspect"])
                        if nominal <= 0:
                            raise ValueError
                    except (TypeError, ValueError):
                        add_error(
                            "APPROVED_NOMINAL_ASPECT_INVALID",
                            f"Nominal aspect geçersiz: {row['template_uid']}",
                        )

                    legacy_cfg = legacy.get(
                        (category, source_path.name),
                        {},
                    )
                    plan = legacy_cfg.get("on_plan")
                    if _positive_on_plan(plan):
                        bound_sha = str(
                            legacy_cfg.get("on_plan_source_sha256")
                            or (
                                plan.get("source_asset_sha256")
                                if isinstance(plan, dict)
                                else ""
                            )
                            or ""
                        )
                        expected_sha = str(
                            row["source_asset_sha256"] or ""
                        )
                        if not bound_sha or bound_sha != expected_sha:
                            review_summary["stale_on_plan_records"] += 1
                            add_warning(
                                "STALE_ON_PLAN",
                                "Pozitif ön-plan maskesi kaynak hash'ine "
                                "bağlı değil veya stale.",
                                template_uid=row["template_uid"],
                            )
        except Exception as exc:
            add_error(
                "REVIEW_DB_READ_FAILED",
                f"Review DB taranamadı: {exc}",
            )
        finally:
            if conn is not None:
                conn.close()

    checks["review_db"] = review_summary

    # ------------------------------------------------------------------
    # Production state / artifact integrity
    # ------------------------------------------------------------------
    commerce_db = (
        runtime
        / "99_SISTEM_MOTORLARI_VE_KODLAR"
        / "SISTEM_MOTORU"
        / "commerce_state.db"
    )
    state_summary = {
        "path": str(commerce_db),
        "quick_check": None,
        "status_counts": {},
        "completed_missing_local_files": 0,
    }
    if commerce_db.is_file():
        conn = None
        try:
            conn = _readonly_sqlite(commerce_db)
            quick = conn.execute("PRAGMA quick_check").fetchone()
            quick_value = str(quick[0] if quick else "unknown")
            state_summary["quick_check"] = quick_value
            if quick_value.lower() != "ok":
                add_error(
                    "STATE_DB_CORRUPT",
                    f"Commerce DB quick_check başarısız: {quick_value}",
                )

            table_names = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            if "render_artifacts" in table_names:
                rows = conn.execute(
                    """SELECT artifact_key, local_output_path, status
                       FROM render_artifacts"""
                ).fetchall()
                state_summary["status_counts"] = dict(
                    Counter(str(row["status"] or "UNKNOWN") for row in rows)
                )
                missing_completed = []
                for row in rows:
                    if str(row["status"]) != "COMPLETED":
                        continue
                    local = Path(str(row["local_output_path"] or ""))
                    if not local.is_file():
                        missing_completed.append(str(row["artifact_key"]))
                state_summary[
                    "completed_missing_local_files"
                ] = len(missing_completed)
                if missing_completed:
                    add_warning(
                        "COMPLETED_ARTIFACT_FILE_MISSING",
                        f"{len(missing_completed)} COMPLETED artifact'ın "
                        "yerel dosyası yok. Yeni fabrika sürümü bunları "
                        "otomatik yeniden render eder.",
                        examples=missing_completed[:5],
                    )
        except Exception as exc:
            add_error(
                "STATE_DB_READ_FAILED",
                f"Commerce state DB taranamadı: {exc}",
            )
        finally:
            if conn is not None:
                conn.close()
    else:
        add_info(
            "STATE_DB_NOT_YET_CREATED",
            "commerce_state.db henüz yok; ilk üretimde oluşabilir.",
        )
    checks["commerce_state"] = state_summary

    # ------------------------------------------------------------------
    # Temp/crash residue and outputs
    # ------------------------------------------------------------------
    staging_root = runtime / "YENI-BOS MOCKUP SABLON HAVUZU"
    stale_processing = []
    if staging_root.is_dir():
        now = time.time()
        for path in staging_root.rglob("*.processing"):
            try:
                if now - path.stat().st_mtime > 300:
                    stale_processing.append(str(path))
            except OSError:
                continue
    checks["stale_processing_files"] = stale_processing
    if stale_processing:
        add_warning(
            "STALE_PROCESSING_FILE",
            "Yarım kalmış watcher .processing dosyaları bulundu.",
            examples=stale_processing[:10],
        )

    output_root = required_dirs["outputs"]
    partial_outputs = []
    zero_byte_outputs = []
    if output_root.is_dir():
        for path in output_root.rglob("*"):
            if not path.is_file():
                continue
            if path.name.endswith(".writing"):
                partial_outputs.append(str(path))
            elif path.suffix.lower() in {".jpg", ".jpeg", ".png"}:
                try:
                    if path.stat().st_size <= 0:
                        zero_byte_outputs.append(str(path))
                except OSError:
                    pass
    checks["partial_outputs"] = partial_outputs
    checks["zero_byte_outputs"] = zero_byte_outputs
    if partial_outputs:
        add_warning(
            "PARTIAL_OUTPUT_FILES",
            "Yarım kalmış .writing çıktı dosyaları bulundu.",
            examples=partial_outputs[:10],
        )
    if zero_byte_outputs:
        add_error(
            "ZERO_BYTE_OUTPUT",
            "0-byte üretim çıktıları bulundu.",
            examples=zero_byte_outputs[:10],
        )

    ready = not errors
    add_info(
        "DOCTOR_COMPLETE",
        (
            "Doctor kritik hata bulmadı."
            if ready
            else f"Doctor {len(errors)} kritik problem buldu."
        ),
    )
    return {
        "ready": ready,
        "deep": bool(deep),
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "info": info,
        "checks": checks,
    }
