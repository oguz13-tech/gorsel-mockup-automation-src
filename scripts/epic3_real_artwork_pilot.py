#!/usr/bin/env python3
"""Read-only actual-design, approved-template 3:4 pilot with output in OS TEMP.

Different from the synthetic six-template smoke and the full commerce factory:
* Source artwork, source templates, archive and approval SQLite are READ ONLY.
* Outputs are written to a fresh OS TEMP directory, never the user's runtime.
* No uploader, Excel, SEO, state-manager, watcher, AI auto-approval or migrations.
* Foreground occlusion requiring AI/mask is BLOCKED, not painted over.
* Artwork which would trigger the existing renderer's automatic CROP or BLEED
  is explicitly blocked. Supply a dedicated correctly-proportioned master.
* This is an inspection pilot, NOT production deployment or sale approval.

Example (PowerShell, after explicit authorization):
    python scripts/epic3_real_artwork_pilot.py --runtime-root ROOT --artwork-h H.png --artwork-v V.png --execute
Optional: --only 03_Ahsap_Tablo --only 02_Cam_Tablo_Dikey
Optional: --artwork-for 03_Ahsap_Tablo=C:\\path\\to\\different_art.png

Without --execute this emits only a no-I/O plan.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import traceback
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts import epic3_six_template_smoke as base

EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".webp", ".bmp"})
MAX_ARTWORK_BYTES = 100 * 1024 * 1024
MAX_ARTWORK_PIXELS = 60_000_000
MIN_ARTWORK_SHORT_SIDE = 500
MAX_RELATIVE_ASPECT_ERROR = 0.005


class PilotBlocked(base.SmokeBlocked):
    """A requested operation is not safe for the selected design/template."""


def _orient(width: int, height: int) -> str:
    if width > height * 1.01:
        return "H"
    if height > width * 1.01:
        return "V"
    return "SQUARE"


def _protected_artwork_source(source: Path, runtime: Path) -> bool:
    runtime = runtime.resolve()
    source = source.resolve()
    protected = (
        "2_SABLON_HAVUZU",
        "2_SABLON_HAVUZU_ORIJINAL_YEDEK",
        "YENI-BOS MOCKUP SABLON HAVUZU",
        "_COP_KUTUSU",
        "3_URETILEN_MOCKUPLAR",
        "Mockup_Magaza_Klasorleri",
    )
    for name in protected:
        root = (runtime / name).resolve()
        if source == root or source.is_relative_to(root):
            return True
    return False


def _artwork_metadata(source: Path, orientation: str, nominal: float, runtime: Path,
                      cv2, np) -> dict[str, Any]:
    path = source.expanduser().resolve()
    if _protected_artwork_source(path, runtime):
        raise PilotBlocked("ARTWORK_PATH_POINTS_TO_PROTECTED_TEMPLATE_OR_OUTPUT")
    if not path.is_file():
        raise PilotBlocked("ARTWORK_NOT_FOUND")
    if path.suffix.casefold() not in EXTENSIONS:
        raise PilotBlocked("ARTWORK_EXTENSION_UNSUPPORTED")
    size = path.stat().st_size
    if size <= 0 or size > MAX_ARTWORK_BYTES:
        raise PilotBlocked("ARTWORK_FILE_SIZE_OUT_OF_BOUNDS")
    try:
        raw = cv2.imdecode(
            np.fromfile(str(path), dtype=np.uint8),
            cv2.IMREAD_UNCHANGED,
        )
    except (OSError, ValueError, cv2.error) as exc:
        raise PilotBlocked("ARTWORK_UNREADABLE") from exc
    if raw is None or raw.ndim not in (2, 3):
        raise PilotBlocked("ARTWORK_UNREADABLE")
    if raw.ndim == 3 and raw.shape[2] == 4:
        raise PilotBlocked("ARTWORK_ALPHA_REQUIRES_FLATTENED_MASTER")
    h, w = raw.shape[:2]
    if min(w, h) < MIN_ARTWORK_SHORT_SIDE:
        raise PilotBlocked("ARTWORK_RESOLUTION_TOO_LOW")
    if w * h > MAX_ARTWORK_PIXELS:
        raise PilotBlocked("ARTWORK_PIXEL_COUNT_TOO_LARGE")
    if _orient(w, h) != orientation:
        raise PilotBlocked("ARTWORK_PHYSICAL_ORIENTATION_MISMATCH")
    if not 0.2 < nominal < 5:
        raise PilotBlocked("APPROVED_NOMINAL_ASPECT_INVALID")
    actual_aspect = w / float(h)
    # The underlying production renderer CROPS for relative mismatch <=7.5%
    # and creates synthetic bleed for mismatch up to 15%. The isolated user
    # artwork pilot must not silently alter text/border pixels in either case.
    relative_error = abs(actual_aspect - nominal) / nominal
    if relative_error > MAX_RELATIVE_ASPECT_ERROR:
        raise PilotBlocked(
            "ARTWORK_RATIO_WOULD_CROP_OR_SYNTHESIZE:"
            f"actual={actual_aspect:.6f}:required={nominal:.6f}"
        )
    return {
        "path": path,
        "sha256": base._sha256_file(path),
        "width": w, "height": h,
        "orientation": orientation,
        "nominal_aspect": nominal,
        "relative_aspect_error": round(relative_error, 8),
    }


def _copy_artwork_into_temp(source: Path, target: Path, expected_sha: str) -> str:
    source = source.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as inp, target.open("xb") as out:
        shutil.copyfileobj(inp, out, length=1024 * 1024)
    before_after = base._sha256_file(source)
    copied = base._sha256_file(target)
    if before_after != expected_sha or copied != expected_sha:
        target.unlink(missing_ok=True)
        raise PilotBlocked("ARTWORK_CHANGED_DURING_COPY")
    return copied


def _requested_sources(args: argparse.Namespace) -> dict[str, Path]:
    result = {}
    for item in args.artwork_for or []:
        category, sep, value = item.partition("=")
        if not sep or category not in base.CATEGORY_UIDS or not value.strip():
            raise PilotBlocked("INVALID_ARTWORK_FOR_EXPECTED_CATEGORY_EQUALS_PATH")
        if category in result:
            raise PilotBlocked("DUPLICATE_ARTWORK_CATEGORY_OVERRIDE")
        result[category] = Path(value.strip())
    if not result and not args.artwork_h and not args.artwork_v:
        raise PilotBlocked("NO_REAL_ARTWORK_SOURCE_SPECIFIED")
    return result


def _selected_categories(args: argparse.Namespace) -> list[str]:
    categories = args.only or list(base.CATEGORY_UIDS)
    if len(categories) != len(set(categories)):
        raise PilotBlocked("DUPLICATE_CATEGORY_SELECTION")
    return categories


def run(runtime: Path, temp: Path, repo_root: Path,
        categories: list[str], artwork_h: Path | None, artwork_v: Path | None,
        overrides: dict[str, Path]) -> dict:
    import cv2
    import numpy as np

    runtime = runtime.resolve()
    temp = temp.resolve()
    if not temp.is_relative_to(Path(tempfile.gettempdir()).resolve()):
        raise PilotBlocked("PILOT_OUTPUT_MUST_BE_OS_TEMP")
    pool = runtime / "2_SABLON_HAVUZU"
    db_path = runtime / "SABLON_V2_MIMARI" / "ayarlar.db"
    if not pool.is_dir():
        raise PilotBlocked("WORKING_TEMPLATE_POOL_MISSING")
    initial_db_sha = base._sha256_file(db_path) if db_path.is_file() else None
    if initial_db_sha is None:
        raise PilotBlocked("RUNTIME_DB_MISSING")
    conn = base._read_only_db(db_path)
    try:
        rows = base._read_reviewed_rows(conn, pool)
        module = base._load_renderer(temp / "isolated_engine_runtime", repo_root)
        results = []
        read_sources: dict[str, str] = {str(db_path): initial_db_sha}
        for cat in categories:
            uid = base.CATEGORY_UIDS[cat]
            row = rows[cat]
            if row.get("status") == "BLOCKED":
                results.append(dict(row))
                continue
            src_path = row["resolved_source"]
            read_sources[str(src_path)] = row["source_sha256_verified"]
            try:
                orientation = str(row.get("orientation") or "").upper()
                if orientation not in ("H", "V"):
                    raise PilotBlocked("UNKNOWN_PROFILE_ORIENTATION")
                if cat == "04_Cam_Dograma":
                    if not module.physical_orientation_verified(
                        row.get("component_confidences")
                    ):
                        raise PilotBlocked("CAM_DOGRAMA_ORIENTATION_NOT_VERIFIED")
                elif orientation != module.PRODUCT_CATALOG[cat].orientation:
                    raise PilotBlocked("CATEGORY_ORIENTATION_MISMATCH")
                if row.get("has_occlusion"):
                    raise PilotBlocked("OCCLUSION_REQUIRES_VERIFIED_MASK")
                if base._legacy_plan(conn, cat, src_path.name):
                    raise PilotBlocked("LEGACY_MASK_PLAN_REQUIRES_REVIEW")
                source = overrides.get(cat) or (
                    artwork_h if orientation == "H" else artwork_v
                )
                if source is None:
                    raise PilotBlocked(f"MISSING_{orientation}_ARTWORK")
                nominal = float(row["nominal_aspect"])
                meta = _artwork_metadata(
                    Path(source), orientation, nominal, runtime, cv2, np,
                )
                read_sources[str(meta["path"])] = meta["sha256"]
                copied_path = temp / "user_artwork_copies" / (
                    cat + meta["path"].suffix.casefold()
                )
                _copy_artwork_into_temp(
                    meta["path"], copied_path, meta["sha256"],
                )
                item = base._render_one(
                    row, cat, module, cv2, np, conn, temp, runtime,
                    prepared_artwork_path=copied_path,
                )
                item["original_artwork_sha256"] = meta["sha256"]
                item["artwork_dimensions"] = [
                    meta["width"], meta["height"],
                ]
                results.append(item)
            except (PilotBlocked, ValueError, OSError, sqlite3.Error) as exc:
                results.append({
                    "uid": uid, "status": "BLOCKED",
                    "reason": str(exc),
                })
            except Exception as exc:
                results.append({
                    "uid": uid, "status": "FAIL",
                    "reason": f"UNEXPECTED:{type(exc).__name__}:{exc}",
                })
                traceback.print_exc(file=sys.stderr)
            print(
                "PILOT_RESULT",
                json.dumps(results[-1], ensure_ascii=False, default=str),
                flush=True,
            )
    finally:
        conn.close()

    # A concurrent external edit is not evidence of code mutation, but this
    # pilot must never claim acceptance when any observed live input changed.
    modified_inputs = []
    for path_str, expected in read_sources.items():
        path = Path(path_str)
        try:
            if base._sha256_file(path) != expected:
                modified_inputs.append(path_str)
        except OSError:
            modified_inputs.append(path_str)
    # Base sheet expects all six template records in static order; preserve
    # display order with explicit blocked placeholders for unselected ones.
    selected = {cat: res for cat, res in zip(categories, results)}
    contact_rows = [
        selected.get(cat, {
            "uid": base.CATEGORY_UIDS[cat],
            "status": "NOT_REQUESTED",
            "reason": "CATEGORY_NOT_SELECTED",
        })
        for cat in base.CATEGORY_UIDS
    ]
    sheet = base._build_contact_sheet(cv2, np, contact_rows, temp)
    passes = sum(r["status"] == "PASS" for r in results)
    return {
        "mode": "ISOLATED_REAL_ARTWORK_PILOT",
        "source_runtime_read_only": str(runtime),
        "isolated_output_root": str(temp),
        "contact_sheet": sheet,
        "selected_categories": categories,
        "results": results,
        "pass_count": passes,
        "blocked_count": sum(r["status"] == "BLOCKED" for r in results),
        "fail_count": sum(r["status"] == "FAIL" for r in results),
        "source_hash_stable": not modified_inputs,
        "changed_input_paths": modified_inputs,
        "output_dimensions": [base.TARGET_WIDTH, base.TARGET_HEIGHT],
        "only_local_preview": True,
        "no_cloud_excel_or_seo": True,
        "foreground_ai_disabled": True,
        "never_automatically_approved_for_sale": True,
        "not_proof_of_full_factory_release": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--artwork-h", type=Path)
    parser.add_argument("--artwork-v", type=Path)
    parser.add_argument(
        "--artwork-for", action="append", default=[],
        metavar="CATEGORY=FILE",
    )
    parser.add_argument(
        "--only", action="append", choices=tuple(base.CATEGORY_UIDS),
        help="Select a category; may be supplied repeatedly",
    )
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    if not args.execute:
        print(json.dumps({
            "status": "PLAN_ONLY",
            "selected_categories": args.only or list(base.CATEGORY_UIDS),
            "real_user_artwork": True,
            "writes": "NONE",
            "on_execute": "fresh OS TEMP previews only",
            "cloud_excel_approval": False,
        }, ensure_ascii=False, indent=2))
        return 0

    try:
        overrides = _requested_sources(args)
        categories = _selected_categories(args)
    except PilotBlocked as exc:
        print("BLOCKED", str(exc), flush=True)
        return 2
    temp = Path(tempfile.mkdtemp(prefix="epic3-real-artwork-pilot-")).resolve()
    print("ISOLATED_OUTPUT_ROOT", str(temp), flush=True)
    try:
        report = run(
            args.runtime_root.expanduser().resolve(), temp,
            ROOT, categories, args.artwork_h, args.artwork_v, overrides,
        )
        code = 0 if (
            report["pass_count"] == len(categories)
            and report["source_hash_stable"]
        ) else 2
    except Exception as exc:
        traceback.print_exc(file=sys.stderr)
        report = {
            "status": "BLOCKED",
            "reason": f"{type(exc).__name__}:{exc}",
            "isolated_output_root": str(temp),
        }
        code = 2
    path = temp / "real-artwork-pilot-report.json"
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print("PILOT_REPORT_PATH", path, flush=True)
    print("PILOT_EXIT_CODE", code, flush=True)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
