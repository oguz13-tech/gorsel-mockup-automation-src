"""Safely migrate trusted legacy manual template corners into template_profiles.

Default mode is DRY-RUN. Pass --apply only after reviewing the report.

Safety invariants:
- legacy JSON and source images are read-only;
- exact category/filename matching only (no scan/rematch/renumber);
- every quad is validated against the exact source image;
- source SHA-256 is bound to the approved profile;
- existing source-valid manually-approved profiles are preserved;
- the SQLite database is backed up before the first mutation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import time
from pathlib import Path
from typing import Dict, Optional, Tuple

import cv2
import numpy as np

SOURCE_ROOT = Path(__file__).resolve().parents[1]
_runtime_override = str(os.environ.get("MOCKUP_RUNTIME_WORKSPACE") or "").strip()
RUNTIME_ROOT = (
    Path(_runtime_override).expanduser().resolve()
    if _runtime_override
    else SOURCE_ROOT.resolve()
)

ARCH_DIR = SOURCE_ROOT / "SABLON_V2_MIMARI"
DB_PATH = RUNTIME_ROOT / "SABLON_V2_MIMARI" / "ayarlar.db"
DEFAULT_LEGACY_JSON = RUNTIME_ROOT / "ayarlar.json"
TEMPLATE_ROOT = RUNTIME_ROOT / "2_SABLON_HAVUZU"

sys.path.insert(0, str(ARCH_DIR))

from core.db import init_db
from core.template_intelligence import CategoryRuleEngine, GeometryValidator


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def derive_orientation(quad: np.ndarray) -> str:
    top = float(np.linalg.norm(quad[1] - quad[0]))
    bottom = float(np.linalg.norm(quad[2] - quad[3]))
    left = float(np.linalg.norm(quad[3] - quad[0]))
    right = float(np.linalg.norm(quad[2] - quad[1]))
    avg_w = (top + bottom) * 0.5
    avg_h = (left + right) * 0.5
    if avg_w <= 0 or avg_h <= 0:
        return "UNKNOWN"
    ratio = avg_w / avg_h
    if ratio > 1.05:
        return "H"
    if ratio < 0.95:
        return "V"
    return "SQUARE"


def validate_quad(raw_quad, image: np.ndarray) -> Tuple[Optional[np.ndarray], str]:
    try:
        quad = np.asarray(raw_quad, dtype=np.float32)
    except (TypeError, ValueError):
        return None, "NON_NUMERIC_QUAD"

    if quad.shape != (4, 2) or not np.isfinite(quad).all():
        return None, "INVALID_QUAD_SHAPE"

    h, w = image.shape[:2]
    valid, reason = GeometryValidator.is_valid_quad(quad, w, h)
    if not valid:
        return None, f"INVALID_GEOMETRY:{reason}"

    return GeometryValidator.canonical_sort(quad).astype(np.float32), "OK"


def valid_optional_outer(raw_outer, image: np.ndarray):
    if raw_outer is None:
        return None
    outer, reason = validate_quad(raw_outer, image)
    if outer is None:
        return None
    return outer.astype(float).tolist()


def backup_database(db_path: Path) -> Path:
    stamp = time.strftime("%Y%m%d_%H%M%S")
    backup_path = db_path.with_name(f"{db_path.stem}.pre_legacy_profile_migration_{stamp}.bak")
    source = sqlite3.connect(str(db_path))
    target = sqlite3.connect(str(backup_path))
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()
    return backup_path


def _ensure_profile_schema_for_dry_run(conn: sqlite3.Connection) -> None:
    """Prepare only the in-memory dry-run copy; never mutate the real DB."""
    conn.execute(
        """CREATE TABLE IF NOT EXISTS template_profiles (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               template_uid TEXT,
               category TEXT,
               source_relative_path TEXT,
               source_asset_sha256 TEXT,
               profile_version TEXT,
               analyzer_version TEXT,
               product_class TEXT,
               orientation TEXT,
               nominal_aspect TEXT,
               geometry_type TEXT,
               print_policy TEXT,
               surface_quad TEXT,
               outer_quad TEXT,
               surface_mask_path TEXT,
               material TEXT,
               has_frame INTEGER,
               has_mat INTEGER,
               has_reflection INTEGER,
               has_occlusion INTEGER,
               confidence_total REAL,
               component_confidences TEXT,
               review_status TEXT,
               manually_verified INTEGER,
               is_active INTEGER DEFAULT 1,
               updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
           )"""
    )
    columns = {
        str(row[1])
        for row in conn.execute("PRAGMA table_info(template_profiles)").fetchall()
    }
    if "nominal_aspect" not in columns:
        conn.execute("ALTER TABLE template_profiles ADD COLUMN nominal_aspect TEXT")
    if "is_active" not in columns:
        conn.execute(
            "ALTER TABLE template_profiles ADD COLUMN is_active INTEGER DEFAULT 1"
        )


def _open_migration_connection(
    apply: bool,
) -> Tuple[sqlite3.Connection, Optional[Path]]:
    """Open the target DB safely.

    APPLY backs up existing bytes before *any* schema/data mutation. DRY-RUN
    works on an in-memory copy, including schema upgrades, so its promise of
    leaving the user's real ayarlar.db untouched is literal.
    """
    if apply:
        backup_path = backup_database(DB_PATH) if DB_PATH.exists() else None
        if backup_path is not None:
            print(f"DB BACKUP: {backup_path}")
        init_db()
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        return conn, backup_path

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    if DB_PATH.exists():
        source = sqlite3.connect(str(DB_PATH))
        try:
            source.backup(conn)
        finally:
            source.close()
    _ensure_profile_schema_for_dry_run(conn)
    return conn, None


def migrate(legacy_json: Path, apply: bool = False) -> Dict[str, int]:
    if not legacy_json.exists():
        raise FileNotFoundError(f"Legacy JSON not found: {legacy_json}")

    with legacy_json.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    categories = payload.get("kategoriler")
    if not isinstance(categories, dict):
        raise ValueError("Legacy JSON has no valid 'kategoriler' object")

    summary = {
        "seen": 0,
        "valid_manual": 0,
        "would_insert": 0,
        "would_update": 0,
        "preserved": 0,
        "missing_source": 0,
        "invalid_geometry": 0,
        "unknown_category": 0,
        "missing_physical_orientation": 0,
    }

    conn, backup_path = _open_migration_connection(apply)

    try:
        for category, category_data in categories.items():
            if not isinstance(category_data, dict):
                continue
            templates = category_data.get("sablonlar", {})
            if not isinstance(templates, dict):
                continue

            try:
                rule = CategoryRuleEngine.get_rule_by_folder(category)
            except ValueError:
                rule = None

            for filename, template_data in templates.items():
                summary["seen"] += 1
                if not isinstance(template_data, dict):
                    summary["invalid_geometry"] += 1
                    continue

                raw_quad = template_data.get("koseler")
                if raw_quad is None:
                    summary["invalid_geometry"] += 1
                    continue

                if rule is None:
                    summary["unknown_category"] += 1
                    continue

                # Exact filename match only. Never guess or rematch a legacy
                # geometry record to a different source asset.
                source_path = TEMPLATE_ROOT / category / filename
                if not source_path.is_file():
                    summary["missing_source"] += 1
                    continue

                image = cv2.imdecode(
                    np.fromfile(str(source_path), dtype=np.uint8),
                    cv2.IMREAD_COLOR,
                )
                if image is None:
                    summary["missing_source"] += 1
                    continue

                canonical, reason = validate_quad(raw_quad, image)
                if canonical is None:
                    summary["invalid_geometry"] += 1
                    print(f"SKIP {category}/{filename}: {reason}")
                    continue

                physical_rule_orientation = str(
                    rule.get("physical_orientation") or "ANY"
                ).upper()
                if physical_rule_orientation in ("H", "V"):
                    orientation = physical_rule_orientation
                else:
                    explicit_orientation = str(
                        template_data.get("physical_orientation") or ""
                    ).upper()
                    if explicit_orientation not in ("H", "V"):
                        summary["missing_physical_orientation"] += 1
                        print(
                            f"SKIP {category}/{filename}: explicit physical_orientation "
                            "H/V required; projected koseler are not physical metadata"
                        )
                        continue
                    orientation = explicit_orientation

                summary["valid_manual"] += 1
                source_hash = sha256_file(source_path)
                uid = f"{category}_{filename}"
                nominal_aspect = CategoryRuleEngine.get_nominal_aspect(
                    category,
                    orientation,
                )
                nominal_aspect_text = (
                    f"{nominal_aspect:.8f}".rstrip("0").rstrip(".")
                    if nominal_aspect is not None
                    else "UNKNOWN"
                )
                outer_quad = valid_optional_outer(
                    template_data.get("outer_quad")
                    or template_data.get("dis_koseler"),
                    image,
                )

                active_rows = conn.execute(
                    """SELECT id, source_asset_sha256, review_status,
                              manually_verified
                       FROM template_profiles
                       WHERE template_uid=? AND is_active=1
                       ORDER BY updated_at DESC, id DESC""",
                    (uid,),
                ).fetchall()

                already_preserved = next(
                    (
                        row
                        for row in active_rows
                        if row["source_asset_sha256"] == source_hash
                        and row["review_status"] == "APPROVED"
                        and int(row["manually_verified"] or 0) == 1
                    ),
                    None,
                )
                if already_preserved is not None:
                    summary["preserved"] += 1
                    continue

                same_source = next(
                    (
                        row
                        for row in active_rows
                        if row["source_asset_sha256"] == source_hash
                    ),
                    None,
                )

                component_confidences = {
                    "manual_prior": 1.0,
                    "legacy_trusted_migration": 1.0,
                    "orientation_score": 1.0,
                    "candidate_agreement": 1.0,
                    "line_score": 1.0,
                    "physical_orientation_verified": 1.0,
                    "physical_orientation_source": (
                        "category_contract"
                        if physical_rule_orientation in ("H", "V")
                        else "legacy_explicit_metadata"
                    ),
                }
                profile_values = {
                    "template_uid": uid,
                    "category": category,
                    "source_relative_path": f"{category}/{filename}",
                    "source_asset_sha256": source_hash,
                    "profile_version": "v2",
                    "analyzer_version": "legacy_manual_v1",
                    "product_class": rule.get("product_class", "Unknown"),
                    "orientation": orientation,
                    "nominal_aspect": nominal_aspect_text,
                    "geometry_type": "quad",
                    "print_policy": rule.get("print_policy", "full_bleed"),
                    "surface_quad": json.dumps(
                        canonical.astype(float).tolist(),
                        ensure_ascii=False,
                    ),
                    "outer_quad": (
                        json.dumps(outer_quad, ensure_ascii=False)
                        if outer_quad is not None
                        else None
                    ),
                    "material": "glass" if rule.get("has_reflection") else "default",
                    "has_frame": int(bool(rule.get("has_frame"))),
                    "has_mat": int(bool(rule.get("has_mat"))),
                    "has_reflection": int(bool(rule.get("has_reflection"))),
                    "has_occlusion": int(bool(template_data.get("on_plan"))),
                    "confidence_total": 1.0,
                    "component_confidences": json.dumps(
                        component_confidences,
                        ensure_ascii=False,
                    ),
                    "review_status": "APPROVED",
                    "manually_verified": 1,
                }

                if same_source is not None:
                    summary["would_update"] += 1
                    if apply:
                        conn.execute(
                            """UPDATE template_profiles SET
                                category=?, source_relative_path=?,
                                source_asset_sha256=?, profile_version=?,
                                analyzer_version=?, product_class=?,
                                orientation=?, nominal_aspect=?, geometry_type=?, print_policy=?,
                                surface_quad=?, outer_quad=?, material=?,
                                has_frame=?, has_mat=?, has_reflection=?,
                                has_occlusion=?, confidence_total=?,
                                component_confidences=?,
                                review_status='APPROVED',
                                manually_verified=1, is_active=1,
                                updated_at=CURRENT_TIMESTAMP
                               WHERE id=?""",
                            (
                                profile_values["category"],
                                profile_values["source_relative_path"],
                                profile_values["source_asset_sha256"],
                                profile_values["profile_version"],
                                profile_values["analyzer_version"],
                                profile_values["product_class"],
                                profile_values["orientation"],
                                profile_values["nominal_aspect"],
                                profile_values["geometry_type"],
                                profile_values["print_policy"],
                                profile_values["surface_quad"],
                                profile_values["outer_quad"],
                                profile_values["material"],
                                profile_values["has_frame"],
                                profile_values["has_mat"],
                                profile_values["has_reflection"],
                                profile_values["has_occlusion"],
                                profile_values["confidence_total"],
                                profile_values["component_confidences"],
                                same_source["id"],
                            ),
                        )
                        conn.execute(
                            """UPDATE template_profiles
                               SET is_active=0
                               WHERE template_uid=? AND is_active=1 AND id<>?""",
                            (uid, same_source["id"]),
                        )
                else:
                    summary["would_insert"] += 1
                    if apply:
                        conn.execute(
                            """UPDATE template_profiles
                               SET is_active=0,
                                   review_status=CASE
                                       WHEN source_asset_sha256<>?
                                       THEN 'STALE_SOURCE_CHANGED'
                                       ELSE review_status
                                   END,
                                   updated_at=CURRENT_TIMESTAMP
                               WHERE template_uid=? AND is_active=1""",
                            (source_hash, uid),
                        )
                        conn.execute(
                            """INSERT INTO template_profiles (
                                template_uid, category, source_relative_path,
                                source_asset_sha256, profile_version,
                                analyzer_version, product_class, orientation,
                                nominal_aspect, geometry_type, print_policy, surface_quad,
                                outer_quad, material, has_frame, has_mat,
                                has_reflection, has_occlusion, confidence_total,
                                component_confidences, review_status,
                                manually_verified, is_active
                            ) VALUES (
                                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                                ?, ?, ?, ?, 'APPROVED', 1, 1
                            )""",
                            (
                                profile_values["template_uid"],
                                profile_values["category"],
                                profile_values["source_relative_path"],
                                profile_values["source_asset_sha256"],
                                profile_values["profile_version"],
                                profile_values["analyzer_version"],
                                profile_values["product_class"],
                                profile_values["orientation"],
                                profile_values["nominal_aspect"],
                                profile_values["geometry_type"],
                                profile_values["print_policy"],
                                profile_values["surface_quad"],
                                profile_values["outer_quad"],
                                profile_values["material"],
                                profile_values["has_frame"],
                                profile_values["has_mat"],
                                profile_values["has_reflection"],
                                profile_values["has_occlusion"],
                                profile_values["confidence_total"],
                                profile_values["component_confidences"],
                            ),
                        )

        if apply:
            conn.commit()
        else:
            conn.rollback()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print("MODE:", "APPLY" if apply else "DRY-RUN")
    for key, value in summary.items():
        print(f"{key}: {value}")
    if not apply:
        print("No files or database rows were changed. Re-run with --apply to migrate.")

    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--legacy-json",
        type=Path,
        default=DEFAULT_LEGACY_JSON,
        help="Trusted legacy ayarlar.json path",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply migration after creating a database backup",
    )
    args = parser.parse_args()
    migrate(args.legacy_json.resolve(), apply=args.apply)


if __name__ == "__main__":
    main()
