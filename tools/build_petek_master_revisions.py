"""Build four review-only PETEK master-grid revisions and pilot renders."""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

import cv2
import numpy as np

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "MERKEZ"))

from PETEK_V3 import engine
from PETEK_V3.registry import Registry
from PETEK_V3.petek_master_grid import build_master_grid
from PETEK_V3.petek_render_contract_v1 import (
    digest_frame, temporary_photo_protected_preview_mask,
)
from PETEK_V3.petek_visual_pipeline_vnext import render_petek_visual


LIVE_PROFILES = Path(r"C:\Users\oguzc\AppData\Local\GorselMockup\PetekV3\profiles")
LIVE_MASKS = Path(r"C:\Users\oguzc\AppData\Local\GorselMockup\PetekV3\masks")
INPUTS = Path(r"C:\AI_WORK\PETEK_GERCEK_TEST_VERILERI")
ARTWORK = INPUTS / "ts1.jpg"
ROOT = Path(r"C:\AI_WORK\PETEK_MASTER_REVISIONS_20261101")

SOURCE_NAMES = [
    "50fa3951-3ba1-4aba-bfc2-c26527cc076b.png",
    "79ffa43d-baba-4f8c-944a-1efa3e85a198.png",
    "8fa31037-654d-4d5c-bc9a-556a7b49c170.png",
    "Gemini_Generated_Image_65hptp65hptp65hp-devam-yeni-varyasyon.jpg",
]


def _json_default(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.integer, np.floating)):
        return value.item()
    raise TypeError(type(value).__name__)


def _profile_for(source):
    source_sha = engine.digest(source)
    for path in LIVE_PROFILES.glob("*.json"):
        try:
            profile = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if profile.get("status") == "APPROVED" and profile.get("source_sha") == source_sha:
            return profile
    raise RuntimeError(f"No approved profile matches {source.name}")


def _copy_closeup(image, alpha, path):
    ys, xs = np.where(alpha > 0)
    if not len(xs):
        raise RuntimeError("empty master overlay")
    pad = 30
    x0, x1 = max(0, int(xs.min()) - pad), min(image.shape[1], int(xs.max()) + pad + 1)
    y0, y1 = max(0, int(ys.min()) - pad), min(image.shape[0], int(ys.max()) + pad + 1)
    if not cv2.imwrite(str(path), image[y0:y1, x0:x1]):
        raise RuntimeError(f"cannot write {path}")


def main():
    if ROOT.exists():
        shutil.rmtree(ROOT)
    state = ROOT / "state"
    outputs = ROOT / "outputs"
    (state / "profiles").mkdir(parents=True)
    (state / "masks").mkdir()
    outputs.mkdir()
    registry = Registry(state)
    artwork = engine.read_bgr(ARTWORK)
    entries = []

    for index, name in enumerate(SOURCE_NAMES, 1):
        source = INPUTS / name
        profile = _profile_for(source)
        old_mask_path = LIVE_MASKS / (profile["mask_sha"] + ".png")
        shutil.copy2(old_mask_path, state / "masks" / old_mask_path.name)
        shutil.copy2(
            LIVE_PROFILES / (profile["uid"] + ".json"),
            state / "profiles" / (profile["uid"] + ".json"),
        )
        scene = engine.read_bgr(source)
        approved, old_mask = registry.get(
            profile["uid"], require_approved=True, source_override=str(source)
        )
        revised_mask, revision_proof = temporary_photo_protected_preview_mask(
            scene, old_mask, approved["quad"]
        )
        revision_uid = approved["uid"][:70] + "_r_mastergrid_20261101"
        revision = registry.save(
            revision_uid, source, approved["quad"], revised_mask,
            approved["physical_aspect"], reviewer="", approved=False
        )
        registry.link_draft_revision(
            approved["uid"], revision_uid, source_override=str(source)
        )
        master, master_proof = build_master_grid(
            scene, revised_mask, approved["quad"]
        )
        stem = f"{index:02d}_{approved['uid'][:8]}"
        cv2.imwrite(str(outputs / f"{stem}_master_grid.png"), master)
        baseline, baseline_qa = render_petek_visual(
            scene, artwork, approved["quad"], revised_mask,
            approved["physical_aspect"], lighting="natural",
            material_effect=True, slot_mode="off", pink_cleanup=True
        )
        classic, classic_qa = render_petek_visual(
            scene, artwork, approved["quad"], revised_mask,
            approved["physical_aspect"], lighting="strong",
            material_effect=True, slot_mode="off", pink_cleanup=True,
            master_grid=master
        )
        cv2.imwrite(str(outputs / f"{stem}_baseline.png"), baseline)
        cv2.imwrite(str(outputs / f"{stem}_classic_master.png"), classic)
        _copy_closeup(classic, master[:, :, 3], outputs / f"{stem}_grid_closeup.png")
        entries.append({
            "approved_uid": approved["uid"],
            "revision_uid": revision_uid,
            "source": str(source),
            "source_sha256": approved["source_sha"],
            "approved_mask_sha256": approved["mask_sha"],
            "revision_mask_sha256": revision["mask_sha"],
            "quad_sha256": hashlib.sha256(
                np.asarray(approved["quad"], dtype=np.float32).tobytes()
            ).hexdigest(),
            "master_overlay_sha256": master_proof["overlay_sha256"],
            "source_vent_count": master_proof["source_vent_count"],
            "authorized_pixels": master_proof["authorized_pixels"],
            "revision_proof": revision_proof,
            "baseline_qa": baseline_qa,
            "classic_shadow_qa": classic_qa,
            "revision_status": "DRAFT_REVIEW_ONLY",
            "active": False,
            "approved": False,
        })

    manifest = {
        "status": "REVIEW_ONLY_NOT_ACTIVE",
        "artwork": str(ARTWORK),
        "artwork_sha256": digest_frame(artwork),
        "shadow_mode": "classic_two_long_soft_bands",
        "experimental_assets": {"G3": False, "Y3": False, "L1": False},
        "active_revisions_changed": False,
        "live_data_changed": False,
        "entries": entries,
    }
    (ROOT / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, default=_json_default),
        encoding="utf-8",
    )
    print(json.dumps(manifest, indent=2, ensure_ascii=False, default=_json_default))


if __name__ == "__main__":
    main()
