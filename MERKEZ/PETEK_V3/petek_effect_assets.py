"""Bundled PETEK effect assets.

The files are release-local, deterministic PNG fields. They are loaded from
this source tree, never from the live runtime or an internet URL.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import cv2
import numpy as np


ASSET_DIR = Path(__file__).resolve().parents[2] / "ASSETS" / "PETEK"
ASSET_FILES = {
    "G3": ASSET_DIR / "g3_window_frame_shadow.png",
    "Y3": ASSET_DIR / "y3_white_mdf_texture.png",
    "L1": ASSET_DIR / "l1_window_sunlight.png",
}


def _read(name: str) -> np.ndarray:
    path = ASSET_FILES[name]
    if not path.is_file():
        raise FileNotFoundError(f"PETEK_EFFECT_ASSET_MISSING:{path}")
    image = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    if image is None or image.ndim != 2 or image.dtype != np.uint8:
        raise ValueError(f"PETEK_EFFECT_ASSET_INVALID:{path}")
    return image


def load_fields(size: tuple[int, int]) -> dict[str, np.ndarray]:
    """Load all fields and resize them to (width, height) with linear sampling."""
    width, height = size
    fields = {}
    for name in ASSET_FILES:
        field = _read(name)
        fields[name] = cv2.resize(field, (width, height), interpolation=cv2.INTER_LINEAR)
    return fields


def manifest() -> dict[str, dict[str, str]]:
    result = {}
    for name, path in ASSET_FILES.items():
        data = path.read_bytes()
        result[name] = {
            "path": str(path),
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": str(len(data)),
        }
    return result


def apply_g3_wall_asset(scene: np.ndarray, rendered: np.ndarray,
                        mask: np.ndarray, quad) -> tuple[np.ndarray, dict]:
    """Apply the bundled G3 field only to a confidently detected wall."""
    from .wall_window_shadows_vnext import wall_region

    wall = wall_region(scene, mask, quad, corner_shadow=True)
    if not np.any(wall):
        return rendered.copy(), {"status": "WALL_NOT_CONFIDENT", "pixels": 0}
    field = load_fields((scene.shape[1], scene.shape[0]))["G3"].astype(np.float32) / 255.0
    active = wall & (field > 0.02)
    out = rendered.copy()
    amount = np.clip(field * 0.18, 0.0, 0.18)
    out[active] = np.uint8(np.clip(
        scene[active].astype(np.float32) * (1.0 - amount[active, None]) + 0.5,
        0, 255))
    changed = int(np.count_nonzero(np.any(out != rendered, axis=2) & active))
    return out, {"status": "APPLIED" if changed else "NO_INTERSECTION", "pixels": changed}
