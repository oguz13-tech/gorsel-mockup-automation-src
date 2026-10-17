# -*- coding: utf-8 -*-
"""Read-only source-bound review gate for the independent manual factory.

This deliberately DOES NOT perform migrations, auto-approval or implicit
repair. It rejects ambiguous profiles, stale source hashes, masks needing
additional verification, invalid quads, and missing database/schema.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path


class SourceApprovalBlocked(RuntimeError):
    pass


def verify_approved_source(runtime_root: Path, category: str, image: Path) -> dict:
    root = Path(runtime_root).resolve()
    image = Path(image).resolve()
    pool = (root / "2_SABLON_HAVUZU").resolve()
    if image.is_symlink() or not image.is_file():
        raise SourceApprovalBlocked("SOURCE_MISSING_OR_SYMLINK")
    try:
        rel = image.relative_to(pool).as_posix()
    except ValueError as exc:
        raise SourceApprovalBlocked("SOURCE_OUTSIDE_WORKING_POOL") from exc
    if image.parent.name != category or image.suffix.casefold() != ".png":
        raise SourceApprovalBlocked("UNEXPECTED_SOURCE_IDENTITY")
    db = root / "SABLON_V2_MIMARI" / "ayarlar.db"
    if not db.is_file():
        raise SourceApprovalBlocked("APPROVAL_DATABASE_MISSING")
    digest = hashlib.sha256(image.read_bytes()).hexdigest()
    conn = sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        conn.execute("PRAGMA query_only=ON")
        rows = conn.execute(
            """SELECT source_asset_sha256, review_status,
                      manually_verified, surface_quad, orientation,
                      nominal_aspect, has_occlusion
               FROM template_profiles
               WHERE category=? AND source_relative_path=? AND is_active=1""",
            (category, rel),
        ).fetchall()
    except sqlite3.Error as exc:
        raise SourceApprovalBlocked("APPROVAL_SCHEMA_UNAVAILABLE") from exc
    finally:
        conn.close()
    if len(rows) != 1:
        raise SourceApprovalBlocked("AMBIGUOUS_OR_MISSING_ACTIVE_PROFILE")
    actual_sha,status,manual,quad,orientation,aspect,occlusion = rows[0]
    if status != "APPROVED" or int(manual or 0) != 1:
        raise SourceApprovalBlocked("NOT_HUMAN_APPROVED")
    if digest != str(actual_sha or ""):
        raise SourceApprovalBlocked("APPROVED_SOURCE_SHA_CHANGED")
    if bool(occlusion):
        raise SourceApprovalBlocked("OCCLUSION_REQUIRES_SEPARATE_QA")
    try:
        q = json.loads(quad)
        valid = (len(q) == 4 and all(
            isinstance(p, list) and len(p) == 2
            and all(isinstance(v, (int,float)) for v in p) for p in q
        ))
        nominal = float(aspect)
        if not valid or not 0 < nominal < 10:
            raise ValueError()
        if orientation not in ("H", "V"):
            raise ValueError()
    except (TypeError, ValueError, OverflowError, json.JSONDecodeError) as exc:
        raise SourceApprovalBlocked("INVALID_APPROVED_GEOMETRY") from exc
    return {
        "status": "APPROVED", "quad": q,
        "orientation": orientation, "nominal_aspect": nominal,
        "source_sha256": digest,
    }
