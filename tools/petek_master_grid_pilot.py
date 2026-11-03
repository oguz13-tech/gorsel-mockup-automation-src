"""Build and render one isolated PETEK master-grid review candidate."""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

import cv2
import numpy as np

PACKAGE_ROOT = Path(__file__).resolve().parents[1] / "MERKEZ"
sys.path.insert(0, str(PACKAGE_ROOT))

from PETEK_V3 import engine
from PETEK_V3.registry import Registry
from PETEK_V3.petek_render_contract_v1 import (
    digest_frame, temporary_photo_protected_preview_mask,
)
from PETEK_V3.petek_master_grid import build_master_grid
from PETEK_V3.petek_visual_pipeline_vnext import render_petek_visual


ROOT = Path(r"C:\AI_WORK\PETEK_MASTER_GRID_PILOT_20261101")
SOURCE = Path(r"C:\AI_WORK\PETEK_GERCEK_TEST_VERILERI\50fa3951-3ba1-4aba-bfc2-c26527cc076b.png")
ARTWORK = Path(r"C:\AI_WORK\PETEK_GERCEK_TEST_VERILERI\ts1.jpg")
LIVE_PROFILE = Path(
    r"C:\Users\oguzc\AppData\Local\GorselMockup\PetekV3\profiles"
    r"\50fa3951-3ba1-4aba-bfc2-c26527cc076b.json"
)
LIVE_MASK_DIR = Path(r"C:\Users\oguzc\AppData\Local\GorselMockup\PetekV3\masks")
APPROVED_UID = "50fa3951-3ba1-4aba-bfc2-c26527cc076b"
REVISION_UID = APPROVED_UID + "_r_mastergrid_20261101"


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _json_default(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.integer, np.floating)):
        return value.item()
    raise TypeError(f"Unsupported manifest value: {type(value).__name__}")


def _closeup(image, alpha, path):
    ys, xs = np.where(alpha > 0)
    if len(xs) == 0:
        raise RuntimeError("Master grid has no authorized pixels")
    pad = 30
    x0, x1 = max(0, int(xs.min()) - pad), min(image.shape[1], int(xs.max()) + pad + 1)
    y0, y1 = max(0, int(ys.min()) - pad), min(image.shape[0], int(ys.max()) + pad + 1)
    crop = image[y0:y1, x0:x1]
    if not cv2.imwrite(str(path), crop):
        raise RuntimeError(f"Unable to write {path}")


def main():
    if not SOURCE.is_file() or not ARTWORK.is_file() or not LIVE_PROFILE.is_file():
        raise FileNotFoundError("Required isolated pilot input is missing")
    if ROOT.exists():
        shutil.rmtree(ROOT)
    state = ROOT / "state"
    out = ROOT / "outputs"
    (state / "profiles").mkdir(parents=True)
    (state / "masks").mkdir()
    out.mkdir(parents=True)

    profile = json.loads(LIVE_PROFILE.read_text(encoding="utf-8"))
    if profile["source_sha"] != engine.digest(SOURCE):
        raise RuntimeError("Source SHA does not match approved profile")
    old_mask_path = LIVE_MASK_DIR / (profile["mask_sha"] + ".png")
    shutil.copy2(LIVE_PROFILE, state / "profiles" / (APPROVED_UID + ".json"))
    shutil.copy2(old_mask_path, state / "masks" / old_mask_path.name)

    scene = engine.read_bgr(SOURCE)
    artwork = engine.read_bgr(ARTWORK)
    registry = Registry(state)
    approved, old_mask = registry.get(APPROVED_UID, require_approved=True,
                                      source_override=str(SOURCE))
    revision_mask, revision_proof = temporary_photo_protected_preview_mask(
        scene, old_mask, approved["quad"])
    revision = registry.save(
        REVISION_UID, SOURCE, approved["quad"], revision_mask,
        approved["physical_aspect"], reviewer="", approved=False)
    registry.link_draft_revision(APPROVED_UID, REVISION_UID,
                                  source_override=str(SOURCE))
    master, master_proof = build_master_grid(scene, revision_mask, approved["quad"])
    cv2.imwrite(str(out / "master_grid.png"), master)

    old_error = None
    try:
        baseline, baseline_qa = render_petek_visual(
            scene, artwork, approved["quad"], old_mask, approved["physical_aspect"],
            placement="cover", lighting="natural", material_effect=True,
            slot_mode="off", pink_cleanup=True)
        cv2.imwrite(str(out / "old_output.png"), baseline)
    except Exception as exc:
        old_error = str(exc)
        historical = Path(
            r"C:\Users\oguzc\Downloads\GORSEL_7_KATEGORI_PETEK_V4112_HTTP_422_ONIZLEME_GUVENLI_WINDOWS_20261101"
            r"\GORSEL_V4102_WINDOWS\GORSEL_V46_CANDIDATE\ISOLATED_PETEK_FIX_20261101"
            r"\REAL_PETEK_GORSEL_INCELEME"
            r"\50fa3951-3ba1-4aba-bfc2-c26527cc076b_ts1_baseline.png"
        )
        if historical.is_file():
            shutil.copy2(historical, out / "old_output_historical.png")
            baseline_qa = {"status": "HISTORICAL_REFERENCE", "path": str(historical)}
        else:
            baseline_qa = {"status": "BLOCKED", "error": old_error}

    result, new_qa = render_petek_visual(
        scene, artwork, revision["quad"], revision_mask,
        revision["physical_aspect"], placement="cover", lighting="natural",
        material_effect=True, slot_mode="off", pink_cleanup=True,
        master_grid=master)
    cv2.imwrite(str(out / "new_master_grid_output.png"), result)
    _closeup(result, master[:, :, 3], out / "grid_closeup.png")
    manifest = {
        "status": "REVIEW_ONLY_NOT_ACTIVE",
        "approved_uid": APPROVED_UID,
        "revision_uid": REVISION_UID,
        "source_sha256": approved["source_sha"],
        "approved_mask_sha256": approved["mask_sha"],
        "revision_mask_sha256": revision["mask_sha"],
        "quad_sha256": hashlib.sha256(
            np.asarray(approved["quad"], dtype=np.float32).tobytes()).hexdigest(),
        "master_overlay_sha256": master_proof["overlay_sha256"],
        "artwork_sha256": digest_frame(artwork),
        "revision_proof": revision_proof,
        "master_proof": master_proof,
        "old_output": baseline_qa,
        "old_render_error": old_error,
        "new_output": new_qa,
        "registry_active_revision_changed": False,
        "approval_changed": False,
        "live_data_changed": False,
    }
    (ROOT / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False,
                   default=_json_default), encoding="utf-8")
    print(json.dumps(manifest, indent=2, ensure_ascii=False,
                     default=_json_default))


if __name__ == "__main__":
    main()
