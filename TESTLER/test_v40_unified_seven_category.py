"""V4.0 Acceptance Tests:
1. Unlimited (>10) human-approved template discovery across all 7 categories.
2. Unified 7-category persistent batch production, unique SKUs, SHA-256 CSV/XLSX parity,
   zero-blur cover placement, and Cut-and-Paste hole/curve/floor preservation.
3. Explicit user-approved crash & stale-lock recovery (quarantining partial files
   into KARANTINA_KESINTI without deleting user files, then resuming from checkpoint).
"""
from __future__ import annotations

import csv
import json
import sqlite3
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "MERKEZ"))

from PETEK_V3 import engine as petek_engine
from PETEK_V3.cutout_paste import extract_cutout_overlay_rgba, render_with_cutout_paste
from PETEK_V3.registry import Registry as PetekRegistry
from URETIM_V4 import (
    ALL_SEVEN_CATEGORIES,
    CATEGORY_SKU_PREFIXES,
    LEGACY_SIX_CATEGORIES,
    UNIFIED_HEADERS,
    UnifiedV4Batch,
    discover_all_approved_seven_categories,
)


def _write_png(path: Path, arr: np.ndarray) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, buf = cv2.imencode(".png", arr)
    assert ok
    path.write_bytes(buf.tobytes())
    return path


def _build_seven_category_workspace(tmp_path: Path, per_cat_count: int = 3):
    """Create a synthetic workspace with `per_cat_count` approved templates in each of the 7 categories."""
    runtime = tmp_path / "RuntimeWorkspace"
    (runtime / "SABLON_V2_MIMARI").mkdir(parents=True)
    db_path = runtime / "SABLON_V2_MIMARI" / "ayarlar.db"

    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE categories (id TEXT PRIMARY KEY, name TEXT)")
        conn.execute(
            "CREATE TABLE templates (id INTEGER PRIMARY KEY AUTOINCREMENT, category_id TEXT, filename TEXT, data TEXT)"
        )
        conn.execute("CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT)")
        conn.execute(
            """CREATE TABLE template_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                template_uid TEXT,
                category TEXT,
                source_relative_path TEXT,
                source_asset_sha256 TEXT,
                orientation TEXT,
                nominal_aspect REAL,
                surface_quad TEXT,
                review_status TEXT,
                manually_verified INTEGER,
                has_occlusion INTEGER,
                component_confidences TEXT,
                is_active INTEGER
            )"""
        )
        conn.execute("CREATE TABLE jobs (id TEXT PRIMARY KEY)")
        conn.execute("CREATE TABLE template_operation_locks (id TEXT PRIMARY KEY)")
        conn.execute("CREATE TABLE template_number_registry (id INTEGER PRIMARY KEY)")
        conn.execute("CREATE TABLE analysis_cache (id INTEGER PRIMARY KEY)")

        for cat in LEGACY_SIX_CATEGORIES:
            conn.execute("INSERT INTO categories(id, name) VALUES (?, ?)", (cat, cat))
            is_vertical = cat in ("02_Cam_Tablo_Dikey", "03_Ahsap_Tablo")
            orient = "V" if is_vertical else "H"
            nominal = 0.75 if is_vertical else 1.333333
            h, w = (520, 420) if is_vertical else (420, 520)
            quad = [[40.0, 40.0], [w - 40.0, 40.0], [w - 40.0, h - 40.0], [40.0, h - 40.0]]

            for idx in range(1, per_cat_count + 1):
                fname = f"{cat}_Sablon_{idx:03d}.png"
                rel = f"{cat}/{fname}"
                scene = np.full((h, w, 3), (185 + idx * 5, 195, 205), dtype=np.uint8)
                work_file = _write_png(runtime / "2_SABLON_HAVUZU" / cat / fname, scene)
                _write_png(runtime / "2_SABLON_HAVUZU_ORIJINAL_YEDEK" / cat / fname, scene)
                sha = petek_engine.digest(work_file)
                uid = f"{cat}_UID_{idx:03d}"

                legacy_data = {"noktalar": quad}
                if cat == "04_Cam_Dograma":
                    # Add a central window mullion bar to verify frame mask preservation
                    legacy_data["pencere_maskesi"] = [[[245, 40], [265, 40], [265, h - 40], [245, h - 40]]]

                conn.execute(
                    "INSERT INTO templates(category_id, filename, data) VALUES (?, ?, ?)",
                    (cat, fname, json.dumps(legacy_data)),
                )
                conf = {"physical_orientation_verified": True} if cat == "04_Cam_Dograma" else {}
                conn.execute(
                    """INSERT INTO template_profiles(
                        template_uid, category, source_relative_path, source_asset_sha256,
                        orientation, nominal_aspect, surface_quad, review_status,
                        manually_verified, has_occlusion, component_confidences, is_active
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'APPROVED', 1, 0, ?, 1)""",
                    (uid, cat, rel, sha, orient, nominal, json.dumps(quad), json.dumps(conf)),
                )

        # Also insert one unapproved DRAFT row to verify it is never selected
        conn.execute(
            """INSERT INTO template_profiles(
                template_uid, category, source_relative_path, source_asset_sha256,
                orientation, nominal_aspect, surface_quad, review_status,
                manually_verified, has_occlusion, component_confidences, is_active
            ) VALUES ('DRAFT_NEVER_SELECT', '01_Wifi_Kutusu', '01_Wifi_Kutusu/missing.png',
                      '00', 'H', 1.33, '[[0,0],[10,0],[10,10],[0,10]]', 'DRAFT', 0, 0, '{}', 1)"""
        )

    # Create 3 approved PETEK templates in PetekRegistry
    petek_reg = PetekRegistry(tmp_path / "petek_state")
    petek_sources = tmp_path / "petek_sources"
    for idx in range(1, per_cat_count + 1):
        h, w = 520, 480
        scene = np.full((h, w, 3), (110, 145, 165), dtype=np.uint8)
        quad = np.float32([[45, 80], [435, 80], [435, 440], [45, 440]])
        poly = petek_engine.polygon_mask(scene.shape, quad)
        scene[poly > 0] = (225, 235, 245)
        # Top curved black gap
        cv2.ellipse(scene, (240, 95), (120, 22), 0, 0, 180, (20, 22, 25), -1)
        # 13 vertical slots
        for x in range(85, 405, 25):
            cv2.rectangle(scene, (x, 165), (x + 6, 380), (22, 24, 28), -1)
        # Bottom parquet gap
        cv2.ellipse(scene, (240, 430), (135, 20), 0, 180, 360, (95, 130, 155), -1)
        src_path = _write_png(petek_sources / f"PetekSablon_{idx:03d}.png", scene)
        wood_mask = np.where((poly > 0) & np.all(scene == [225, 235, 245], axis=2), 255, 0).astype(np.uint8)
        uid = f"PetekKapama_UID_{idx:03d}"
        petek_reg.save(uid, src_path, quad, wood_mask, 1.1163)
        petek_reg.approve(uid, "Argon V4 Tester", "I_VISUALLY_CHECKED_VENTS_ARCHES_FLOOR")

    return runtime, petek_reg


def test_v40_unlimited_discovery_exceeds_10_templates_across_all_7_categories(tmp_path):
    runtime, petek_reg = _build_seven_category_workspace(tmp_path, per_cat_count=3)
    selected, audit = discover_all_approved_seven_categories(
        runtime,
        petek_registry=petek_reg,
        per_category_limit=None,
    )
    assert audit["unlimited_mode"] is True
    assert len(selected) == 21  # 3 approved templates * 7 categories = 21 (> 10 limit!)
    assert set(audit["per_category_counts"].keys()) == set(ALL_SEVEN_CATEGORIES)
    assert all(count == 3 for count in audit["per_category_counts"].values())
    assert "DRAFT_NEVER_SELECT" not in audit["eligible_uids"]


def test_v40_unified_batch_renders_all_7_categories_zero_blur_and_cutout_preserved(tmp_path):
    runtime, petek_reg = _build_seven_category_workspace(tmp_path, per_cat_count=3)
    designs_dir = tmp_path / "TASARIMLAR"
    for i in range(2):
        art = np.full((360, 480, 3), (40 + i * 70, 95, 185), dtype=np.uint8)
        cv2.putText(art, f"V4-{i}", (30, 180), cv2.FONT_HERSHEY_SIMPLEX, 1.8, (245, 245, 245), 3)
        _write_png(designs_dir / f"tasarim_{i:02d}.png", art)

    batch = UnifiedV4Batch(
        tmp_path / "v4_store",
        runtime_root=runtime,
        petek_registry=petek_reg,
    )
    res = batch.run(designs_dir, group="MAGAZA1", max_jobs=5000, placement="cover", lighting="natural")
    assert res["status"] == "LOCAL_READY"
    assert res["approved_template_count"] == 21
    assert res["rendered"] == 42  # 21 templates across 7 categories * 2 designs = 42 outputs
    assert res["reused"] == 0
    assert res["rejected"] == 0
    assert res["total_registry_outputs"] == 42

    csv_path = Path(res["csv"])
    xlsx_path = Path(res["xlsx"])
    assert csv_path.is_file() and xlsx_path.is_file()
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    assert rows[0] == UNIFIED_HEADERS
    assert len(rows) == 43  # header + 42 rows
    prefixes_seen = {r[0].split("-")[0] for r in rows[1:]}
    assert prefixes_seen == set(CATEGORY_SKU_PREFIXES.values())

    # Second run must reuse all 42 verified outputs without re-rendering or overwriting
    second = batch.run(designs_dir, group="MAGAZA1", max_jobs=5000, placement="cover", lighting="natural")
    assert second["rendered"] == 0
    assert second["reused"] == 42
    assert second["csv"] == res["csv"]

    # Verify Cut-and-Paste RGBA overlay extraction & 0.00 pixel diff on Petek holes/curves
    p_profile, p_mask = petek_reg.get("PetekKapama_UID_001", require_approved=True)
    scene = petek_engine.read_bgr(Path(p_profile["source"]))
    art_bgr = petek_engine.read_bgr(designs_dir / "tasarim_00.png")
    rgba, meta = extract_cutout_overlay_rgba(scene, p_mask, p_profile["quad"])
    assert rgba.shape == (scene.shape[0], scene.shape[1], 4)
    assert meta["detected_vertical_slots"] >= 10
    assert meta["detected_curved_openings"] >= 2
    rendered_native, _, qa = render_with_cutout_paste(
        scene, art_bgr, p_profile["quad"], p_mask, p_profile["physical_aspect"], marketplace=False
    )
    assert qa["cut_and_paste_verified"] is True
    assert qa["zero_blur_padding"] is True
    np.testing.assert_array_equal(rendered_native[p_mask == 0], scene[p_mask == 0])


def test_v40_crash_and_stale_lock_recovery_quarantines_partial_and_resumes(tmp_path):
    runtime, petek_reg = _build_seven_category_workspace(tmp_path, per_cat_count=1)
    designs_dir = tmp_path / "TASARIMLAR"
    art = np.full((360, 480, 3), (60, 120, 210), dtype=np.uint8)
    _write_png(designs_dir / "art.png", art)

    batch = UnifiedV4Batch(
        tmp_path / "v4_crash_store",
        runtime_root=runtime,
        petek_registry=petek_reg,
    )
    # Run first with only 3 categories so 3 outputs are RENDERED
    initial = batch.run(
        designs_dir,
        categories=("01_Wifi_Kutusu", "02_Cam_Tablo_Dikey", "06_Petek_Kapama"),
        group="RECOVERY_TEST",
    )
    assert initial["rendered"] == 3

    # Simulate an interrupted PENDING job + partial output file + dead-PID lock file
    partial_out = batch.output / "RECOVERY_TEST" / "03_Ahsap_Tablo" / "PARTIAL_CRASH.png"
    partial_out.parent.mkdir(parents=True, exist_ok=True)
    partial_out.write_bytes(b"corrupt_partial_bytes")
    batch.ledger.reserve(
        {
            "key": "interrupted_key_00000001",
            "sku": "AHT-RECOVERY_TEST-INTERRUPTED",
            "category": "03_Ahsap_Tablo",
            "art_sha": "a" * 64,
            "template_sha": "b" * 64,
            "mask_sha": "c" * 64,
            "art_name": "art.png",
            "uid": "03_Ahsap_Tablo_UID_001",
            "output": str(partial_out),
        }
    )
    batch.lock_path.write_text("999999\n", encoding="utf-8")

    # Must fail closed while stale lock & interrupted PENDING row exist
    with pytest.raises(petek_engine.MaskError):
        batch.run(designs_dir, group="RECOVERY_TEST")

    diag = batch.inspect_recovery()
    assert diag["recovery_needed"] is True
    assert diag["can_recover_safely"] is True
    assert diag["lock"]["stale_lock"] is True
    assert diag["interrupted_pending_count"] == 1
    assert diag["rendered_verified_count"] == 3

    # Recovery without explicit confirmation token must fail closed
    with pytest.raises(petek_engine.MaskError):
        batch.recover(reviewer="Oguz", confirm="WRONG")

    receipt = batch.recover(reviewer="Oguz", confirm="I_APPROVE_SAFE_CRASH_RECOVERY")
    assert receipt["lock_removed"] is True
    assert receipt["cleared_interrupted_keys"] == ["interrupted_key_00000001"]
    assert len(receipt["quarantined_partial_files"]) == 1
    quarantined_path = Path(receipt["quarantined_partial_files"][0]["quarantined_to"])
    assert quarantined_path.is_file()
    assert quarantined_path.read_bytes() == b"corrupt_partial_bytes"
    assert not partial_out.exists()

    # Now running across all 7 categories reuses the 3 previously RENDERED outputs and renders the remaining 4!
    resumed = batch.run(designs_dir, group="RECOVERY_TEST")
    assert resumed["reused"] == 3
    assert resumed["rendered"] == 4
    assert resumed["total_registry_outputs"] == 7
