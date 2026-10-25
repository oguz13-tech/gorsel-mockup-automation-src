#!/usr/bin/env python3
"""EPIC-3 six-template, offline 3:4 smoke render.

Only reads the user's real template pool, original archive and SQLite database.
Every output, synthetic artwork and renderer cache belongs to a fresh TEMP
directory. The factory's normal CLI, production DB, uploader and Excel paths
are never invoked. No automatic approval or source restoration is possible.

Example:
    python scripts/epic3_six_template_smoke.py --runtime-root "C:\path" --execute

With --execute omitted, this script only prints a plan and creates no files.
Requires Python 3.11 and the repository's requirements-core.lock.txt.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import traceback
from typing import Any


CATEGORY_UIDS: dict[str, str] = {
    "01_Wifi_Kutusu": "01_Wifi_Kutusu_Wifi_Kutusu_048.png",
    "02_Cam_Tablo_Dikey": "02_Cam_Tablo_Dikey_CamTabloDikey_013.png",
    "02_Cam_Tablo_Yatay": "02_Cam_Tablo_Yatay_CamTabloYatay_001.png",
    "03_Ahsap_Tablo": "03_Ahsap_Tablo_AhsapTablo_001.png",
    "04_Cam_Dograma": "04_Cam_Dograma_CamDograma_001.png",
    "05_Ocak_Arkasi": "05_Ocak_Arkasi_OcakArkasi_066.png",
}
TARGET_WIDTH, TARGET_HEIGHT = 1200, 1600


class SmokeBlocked(RuntimeError):
    """Unsafe or unverified source: do not render."""


def _read_only_db(db_path: Path) -> sqlite3.Connection:
    if not db_path.is_file():
        raise SmokeBlocked("RUNTIME_DB_MISSING")
    conn = sqlite3.connect(
        db_path.resolve().as_uri() + "?mode=ro", uri=True, timeout=5
    )
    try:
        conn.execute("PRAGMA query_only=ON")
        conn.row_factory = sqlite3.Row
        return conn
    except BaseException:
        conn.close()
        raise


def _inside(root: Path, path: Path) -> Path:
    resolved_root = root.resolve()
    resolved = path.resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise SmokeBlocked("SOURCE_OUTSIDE_APPROVED_POOL") from exc
    return resolved


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_reviewed_rows(conn: sqlite3.Connection, pool: Path) -> dict[str, dict]:
    required = {
        "template_uid", "category", "source_relative_path",
        "source_asset_sha256", "surface_quad", "orientation",
        "nominal_aspect", "review_status", "is_active", "manually_verified",
        "has_occlusion", "component_confidences",
    }
    existing = {r[1] for r in conn.execute("PRAGMA table_info(template_profiles)")}
    if not required.issubset(existing):
        raise SmokeBlocked(
            "REQUIRED_REVIEW_COLUMNS_MISSING:" + ",".join(sorted(required - existing))
        )

    records: dict[str, dict] = {}
    for category, uid in CATEGORY_UIDS.items():
        candidates = conn.execute(
            """SELECT template_uid,category,source_relative_path,
                      source_asset_sha256,surface_quad,orientation,nominal_aspect,
                      review_status,is_active,manually_verified,has_occlusion,
                      component_confidences
               FROM template_profiles WHERE template_uid=? AND is_active=1""",
            (uid,),
        ).fetchall()
        if len(candidates) != 1:
            records[category] = {
                "status": "BLOCKED", "reason": f"ACTIVE_PROFILE_COUNT_{len(candidates)}",
                "uid": uid,
            }
            continue
        row = dict(candidates[0])
        if (
            row["category"] != category
            or row["review_status"] != "APPROVED"
            or row["manually_verified"] != 1
        ):
            records[category] = {
                "status": "BLOCKED", "reason": "NOT_HUMAN_APPROVED", "uid": uid,
            }
            continue

        rel = str(row.get("source_relative_path") or "")
        if not rel or not row.get("source_asset_sha256"):
            records[category] = {
                "status": "BLOCKED", "reason": "NO_SOURCE_IDENTITY", "uid": uid,
            }
            continue
        try:
            source = _inside(pool, pool / rel)
            if not source.is_file():
                raise SmokeBlocked("SOURCE_FILE_MISSING")
            if source.parent.name != category or source.suffix.lower() != ".png":
                raise SmokeBlocked("UNEXPECTED_SOURCE_PATH")
            actual_sha = _sha256_file(source)
            if actual_sha != str(row["source_asset_sha256"]):
                raise SmokeBlocked("STALE_SOURCE_CHANGED")
            row["resolved_source"] = source
            row["source_sha256_verified"] = actual_sha
            records[category] = row
        except (OSError, SmokeBlocked) as exc:
            records[category] = {
                "status": "BLOCKED", "reason": str(exc), "uid": uid,
            }
    return records


def _legacy_plan(conn: sqlite3.Connection, category: str, filename: str) -> Any:
    """Fail closed when source-linked manual occlusion evidence may exist."""
    try:
        rows = conn.execute(
            "SELECT data FROM templates WHERE category_id=? AND filename=?",
            (category, filename),
        ).fetchall()
    except sqlite3.Error as exc:
        raise SmokeBlocked("LEGACY_TEMPLATE_QUERY_FAILED") from exc
    if len(rows) > 1:
        raise SmokeBlocked("DUPLICATE_LEGACY_ROWS")
    if not rows:
        return None
    try:
        data = json.loads(rows[0][0])
    except (TypeError, ValueError) as exc:
        raise SmokeBlocked("INVALID_LEGACY_DATA") from exc
    if not isinstance(data, dict):
        raise SmokeBlocked("INVALID_LEGACY_DATA")
    return data.get("on_plan")


def _load_renderer(temp_runtime: Path, repo_root: Path):
    """Prevent the render module's import from writing to the live runtime."""
    if not temp_runtime.resolve().is_relative_to(
        Path(tempfile.gettempdir()).resolve()
    ):
        raise SmokeBlocked("RENDER_RUNTIME_MUST_BE_IN_TEMP")
    engine_parent = repo_root / "99_SISTEM_MOTORLARI_VE_KODLAR"
    engine_file = engine_parent / "SISTEM_MOTORU" / "pc_master_factory.py"
    if not engine_file.is_file():
        raise SmokeBlocked("FACTORY_SOURCE_NOT_FOUND")
    os.environ["MOCKUP_RUNTIME_WORKSPACE"] = str(temp_runtime)
    # No bytecode/cache writes to the checked-out source tree.
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(engine_parent))
    # Factory checks --preflight at import to suppress directory/log creation.
    # Append only within this short-lived child process; never run factory CLI.
    if "--preflight" not in sys.argv:
        sys.argv.append("--preflight")
    module = importlib.import_module("SISTEM_MOTORU.pc_master_factory")
    if not module.PREFLIGHT_MODE:
        raise SmokeBlocked("FACTORY_IMPORT_NOT_READ_ONLY")
    if Path(module.USER_WORKSPACE_DIR).resolve() != temp_runtime.resolve():
        raise SmokeBlocked("FACTORY_RUNTIME_ESCAPED_TEMP")
    return module


def _synthetic_artwork(numpy, cv2, category: str, ratio: float, image_path: Path):
    """Synthetic color/line/detail target. No customer artwork is read."""
    if not 0.2 < ratio < 5:
        raise SmokeBlocked("INVALID_NOMINAL_ASPECT")
    if ratio >= 1:
        width, height = 960, round(960 / ratio)
    else:
        width, height = round(960 * ratio), 960
    if width < 150 or height < 150:
        raise SmokeBlocked("INVALID_ARTWORK_DIMENSIONS")
    yy, xx = numpy.indices((height, width), dtype=numpy.int32)
    image = numpy.stack((
        (45 + xx * 145 // width + yy * 31 // height) % 255,
        (82 + yy * 113 // height + xx * 39 // width) % 255,
        (161 + (xx // 13 + yy // 17) % 38),
    ), axis=-1).astype(numpy.uint8)
    cv2.rectangle(
        image, (width // 18, height // 18),
        (width - width // 18, height - height // 18),
        (255, 255, 255), max(2, width // 125),
    )
    cv2.line(image, (0, 0), (width - 1, height - 1), (255, 255, 255), 4)
    cv2.line(image, (width - 1, 0), (0, height - 1), (255, 255, 255), 4)
    cv2.putText(
        image, "TEST - NOT FOR SALE",
        (width // 11, height // 2), cv2.FONT_HERSHEY_SIMPLEX,
        max(0.45, width / 1600), (245, 245, 245), 2, cv2.LINE_AA,
    )
    ok, encoded = cv2.imencode(".png", image)
    if not ok:
        raise SmokeBlocked("SYNTHETIC_IMAGE_ENCODING_FAILED")
    image_path.parent.mkdir(parents=True, exist_ok=True)
    image_path.write_bytes(encoded.tobytes())
    return hashlib.sha256(encoded.tobytes()).hexdigest()


def _safe_original_copy(
    source_root: Path, category: str, basename: str, temp_runtime: Path,
) -> bool:
    """Optional archive read copied exclusively to test TEMP, never to source."""
    archive = source_root / "2_SABLON_HAVUZU_ORIJINAL_YEDEK"
    source = _inside(archive, archive / category / basename)
    if not source.is_file():
        return False
    dest = (
        temp_runtime / "2_SABLON_HAVUZU_ORIJINAL_YEDEK" / category / basename
    )
    dest.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as inp, dest.open("xb") as out:
        shutil.copyfileobj(inp, out, length=1024 * 1024)
    return True


def _render_one(
    row: dict, category: str, module, cv2, numpy,
    conn: sqlite3.Connection, temp: Path, real_runtime: Path,
    *, prepared_artwork_path: Path | None = None,
) -> dict:
    uid = CATEGORY_UIDS[category]
    if row.get("status") == "BLOCKED":
        return row
    if row.get("has_occlusion"):
        return {"uid": uid, "status": "BLOCKED", "reason": "OCCLUSION_REQUIRES_AI"}
    if _legacy_plan(conn, category, row["resolved_source"].name):
        return {"uid": uid, "status": "BLOCKED", "reason": "MANUAL_MASK_PLAN_REQUIRES_REVIEW"}
    product = module.PRODUCT_CATALOG[category]
    orient = str(row["orientation"] or "").upper()
    if orient not in {"H", "V"}:
        return {"uid": uid, "status": "BLOCKED", "reason": "UNKNOWN_PHYSICAL_ORIENTATION"}
    if category == "04_Cam_Dograma":
        if not module.physical_orientation_verified(row["component_confidences"]):
            return {"uid": uid, "status": "BLOCKED", "reason": "PHYSICAL_ORIENTATION_UNVERIFIED"}
    elif orient != product.orientation:
        return {"uid": uid, "status": "BLOCKED", "reason": "PHYSICAL_ORIENTATION_MISMATCH"}
    image = cv2.imdecode(
        numpy.fromfile(str(row["resolved_source"]), dtype=numpy.uint8),
        cv2.IMREAD_COLOR,
    )
    if image is None:
        return {"uid": uid, "status": "BLOCKED", "reason": "SOURCE_NOT_DECODABLE"}
    h, w = image.shape[:2]
    try:
        quad = numpy.asarray(json.loads(row["surface_quad"]), dtype=numpy.float32)
        valid, why = module.ApprovedGeometryValidator.is_valid_quad(quad, w, h)
        if not valid:
            return {"uid": uid, "status": "BLOCKED", "reason": f"INVALID_QUAD:{why}"}
        quad = module.ApprovedGeometryValidator.canonical_sort(quad).tolist()
        nominal = float(row["nominal_aspect"])
        if not numpy.isfinite(nominal) or nominal <= 0:
            raise ValueError("nominal aspect not positive/finite")
    except (TypeError, ValueError, OverflowError) as exc:
        return {"uid": uid, "status": "BLOCKED", "reason": f"INVALID_APPROVED_PROFILE:{exc}"}

    safe_name = category + "__" + row["resolved_source"].stem
    result_path = temp / "previews_1200x1600" / (safe_name + ".jpg")
    if prepared_artwork_path is None:
        art_path = temp / "synthetic_artwork" / (safe_name + ".png")
        artwork_sha = _synthetic_artwork(numpy, cv2, category, nominal, art_path)
        synthetic_only = True
    else:
        # Only a caller-validated, immutable copy under our isolated TEMP may
        # enter the real-artwork pilot; no user artwork is ever rewritten.
        art_path = _inside(temp, Path(prepared_artwork_path))
        if not art_path.is_file():
            raise SmokeBlocked("PREPARED_ARTWORK_COPY_MISSING")
        artwork_sha = _sha256_file(art_path)
        synthetic_only = False
    archive_used = _safe_original_copy(
        real_runtime, category, row["resolved_source"].name,
        Path(module.USER_WORKSPACE_DIR),
    )
    config = {
        "tip": "perspektif",
        "koseler": quad,
        "profile_orientation": orient,
        "nominal_aspect": nominal,
        "has_occlusion": False,
        "auto_foreground": False,
        "on_plan": None,
        "output_width": TARGET_WIDTH,
        "output_height": TARGET_HEIGHT,
        "marketplace_ready": True,
        "smart_product_focus": category == "05_Ocak_Arkasi",
        "camera_artifacts": False,
        "max_render_scale": 1.25,
        "scene_realism_enabled": True,
        "master_quality_strength": 0.34,
    }
    try:
        rendered = module.MockupRenderer.process_mockup(
            art_path, row["resolved_source"], config, product.is_glass,
            result_path, source_design_identity=artwork_sha,
            template_identity=uid, recipe_version=module.RECIPE_VERSION,
            template_sha=row["source_sha256_verified"],
        )
    except Exception as exc:
        return {"uid": uid, "status": "FAIL", "reason": f"RENDER_EXCEPTION:{type(exc).__name__}:{exc}"}
    if not rendered or not result_path.is_file():
        return {"uid": uid, "status": "FAIL", "reason": "RENDER_OR_FINAL_QA_REJECTED"}
    final = cv2.imdecode(
        numpy.fromfile(str(result_path), dtype=numpy.uint8), cv2.IMREAD_COLOR
    )
    if final is None or final.shape[:2] != (TARGET_HEIGHT, TARGET_WIDTH):
        return {"uid": uid, "status": "FAIL", "reason": "PERSISTED_JPEG_WRONG_DIMENSIONS"}
    return {
        "uid": uid, "status": "PASS",
        "output": str(result_path),
        "output_sha256": _sha256_file(result_path),
        "dimensions": f"{TARGET_WIDTH}x{TARGET_HEIGHT}",
        "original_archive_copy_in_temp": archive_used,
        "synthetic_art_only": synthetic_only,
        "local_pilot_no_cloud_or_excel": True,
        "foreground_ai_disabled": True,
    }


def _build_contact_sheet(cv2, np, results: list[dict], temp: Path) -> str:
    """Compare six disposable 3:4 previews at a glance, including blockers."""
    cell_w, cell_h, top = 320, 452, 48
    sheet = np.full(
        (top + cell_h * 2, cell_w * 3, 3), 239, dtype=np.uint8,
    )
    cv2.putText(
        sheet, "EPIC-3 SIX TEMPLATES - TEST ONLY",
        (16, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.75,
        (33, 33, 33), 2, cv2.LINE_AA,
    )
    for i, category in enumerate(CATEGORY_UIDS):
        row, col = divmod(i, 3)
        x0, y0 = col * cell_w, top + row * cell_h
        record = results[i]
        output = record.get("output")
        preview = None
        if output:
            candidate = _inside(temp, Path(output))
            if candidate.is_file():
                preview = cv2.imread(str(candidate), cv2.IMREAD_COLOR)
        cv2.rectangle(
            sheet, (x0 + 6, y0 + 7),
            (x0 + cell_w - 7, y0 + cell_h - 8),
            (206, 206, 206), 1,
        )
        cv2.putText(
            sheet, category, (x0 + 12, y0 + 27),
            cv2.FONT_HERSHEY_SIMPLEX, 0.46,
            (30, 30, 30), 1, cv2.LINE_AA,
        )
        cv2.putText(
            sheet, "STATUS: " + str(record.get("status", "UNKNOWN")),
            (x0 + 12, y0 + 48),
            cv2.FONT_HERSHEY_SIMPLEX, 0.46,
            (28, 90, 45) if record.get("status") == "PASS"
            else (25, 25, 180), 1, cv2.LINE_AA,
        )
        if preview is not None:
            small = cv2.resize(
                preview, (270, 360), interpolation=cv2.INTER_AREA,
            )
            sheet[y0 + 62:y0 + 422, x0 + 25:x0 + 295] = small
        else:
            reason = str(record.get("reason") or "No rendered preview")
            cv2.putText(
                sheet, reason[:36], (x0 + 18, y0 + 100),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42,
                (15, 15, 160), 1, cv2.LINE_AA,
            )
    output_path = temp / "CONTACT_SHEET_TEST_ONLY.jpg"
    ok, encoded = cv2.imencode(
        ".jpg", sheet, [int(cv2.IMWRITE_JPEG_QUALITY), 92],
    )
    if not ok:
        raise SmokeBlocked("CONTACT_SHEET_ENCODING_FAILED")
    output_path.write_bytes(encoded.tobytes())
    return str(output_path)


def smoke(runtime_root: Path, temp: Path, repo_root: Path) -> dict:
    db = runtime_root / "SABLON_V2_MIMARI" / "ayarlar.db"
    pool = runtime_root / "2_SABLON_HAVUZU"
    if not pool.is_dir():
        raise SmokeBlocked("WORKING_POOL_MISSING")
    conn = _read_only_db(db)
    try:
        reviewed = _read_reviewed_rows(conn, pool)
        module = _load_renderer(temp / "isolated_engine_runtime", repo_root)
        import cv2
        import numpy as np
        results = []
        for category in CATEGORY_UIDS:
            print("START_TEMPLATE", category, flush=True)
            try:
                result = _render_one(
                    reviewed[category], category, module, cv2, np,
                    conn, temp, runtime_root,
                )
            except Exception as exc:
                result = {
                    "uid": CATEGORY_UIDS[category],
                    "status": "FAIL",
                    "reason": f"UNEXPECTED:{type(exc).__name__}:{exc}",
                }
                traceback.print_exc(file=sys.stderr)
            results.append(result)
            print("TEMPLATE_RESULT", json.dumps(result, ensure_ascii=False), flush=True)
    finally:
        conn.close()
    contact_sheet = _build_contact_sheet(cv2, np, results, temp)
    return {
        "contact_sheet": contact_sheet,
        "mode": "ISOLATED_SIX_TEMPLATE_SMOKE",
        "runtime_readonly_root": str(runtime_root),
        "test_output_root": str(temp),
        "output_size": [TARGET_WIDTH, TARGET_HEIGHT],
        "read_only_live_db_and_sources": True,
        "synthetic_artwork_only": True,
        "not_a_full_foreground_ai_or_production_release_test": True,
        "results": results,
        "pass_count": sum(1 for r in results if r["status"] == "PASS"),
        "blocked_count": sum(1 for r in results if r["status"] == "BLOCKED"),
        "fail_count": sum(1 for r in results if r["status"] == "FAIL"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument(
        "--execute", action="store_true",
        help="Write only to a brand-new OS temp directory; no live writes",
    )
    args = parser.parse_args(argv)
    runtime_root = args.runtime_root.expanduser().resolve()
    if not args.execute:
        print(json.dumps({
            "status": "PLAN_ONLY",
            "runtime": str(runtime_root),
            "categories": list(CATEGORY_UIDS),
            "action": "No files were read or written. Add --execute to run.",
        }, ensure_ascii=False, indent=2))
        return 0

    temp = Path(tempfile.mkdtemp(prefix="epic3-six-template-smoke-")).resolve()
    print("ISOLATED_OUTPUT_ROOT", str(temp), flush=True)
    try:
        report = smoke(runtime_root, temp, Path(__file__).resolve().parents[1])
        code = 0 if report["pass_count"] == len(CATEGORY_UIDS) else 2
    except Exception as exc:
        traceback.print_exc(file=sys.stderr)
        report = {"status": "BLOCKED", "reason": f"{type(exc).__name__}:{exc}",
                  "test_output_root": str(temp)}
        code = 2
    report_path = temp / "smoke-report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print("REPORT_PATH", str(report_path), flush=True)
    print("SMOKE_EXIT_CODE", code, flush=True)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
