"""Contract tests for the supplied transparent window-shadow overlay."""
import cv2
import numpy as np
from pathlib import Path

from MERKEZ.PETEK_V3.petek_effect_assets import (
    ASSET_FILES, _read_window_shadow, apply_window_shadow_overlay,
)
from MERKEZ.PETEK_V3.realism import right_upper_quarter_mask
from MERKEZ.PETEK_V3.wall_window_shadows_vnext import wall_region


def _scene():
    h, w = 360, 620
    yy, xx = np.mgrid[:h, :w]
    scene = np.zeros((h, w, 3), np.uint8)
    tone = (188 + 2*np.sin(xx/19.) + 2*np.cos(yy/23.)).astype(np.uint8)
    scene[:] = tone[:, :, None]
    scene[300:] = (70, 90, 110)  # floor
    q = np.float32([[130, 45], [390, 52], [382, 285], [124, 278]])
    mask = np.zeros((h, w), np.uint8)
    cv2.fillConvexPoly(mask, q.astype(np.int32), 255)
    # A real narrow physical opening must not receive the overlay.
    mask[105:250, 245:252] = 0
    scene[105:250, 245:252] = (18, 18, 18)
    # Keep the adjacent wall coherent but non-flat so wall_region is trusted.
    return scene, mask, q


def test_overlay_is_rgba_alpha_only_asset():
    path = ASSET_FILES["WINDOW_SHADOW"]
    raw = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    assert raw is not None and raw.ndim == 3 and raw.shape[2] == 4
    assert raw.dtype == np.uint8
    assert np.count_nonzero(raw[:, :, 3]) > 0
    assert int(raw[:, :, 3].max()) < 245
    assert not np.any((raw[:, :, 3] == 0) & np.any(raw[:, :, :3] != 0, axis=2))
    assert _read_window_shadow().ndim == 2


def test_overlay_is_split_right_upper_quarter_and_trusted_wall_only():
    scene, mask, quad = _scene()
    rendered = np.full_like(scene, 220)
    out, qa = apply_window_shadow_overlay(scene, rendered, mask, quad)
    changed = np.any(out != rendered, axis=2)
    front_quarter = right_upper_quarter_mask(mask.shape, quad)
    assert qa["render_only"] and qa["source_pixels_untouched"]
    assert qa["effect_scope"] == "RIGHT_UPPER_QUARTER_PLUS_TRUSTED_ADJACENT_WALL"
    # Every PETEK pixel changed by the overlay belongs to the approved mask
    # and its perspective-correct right-upper quadrant.
    assert not np.any(changed & (mask > 0) & ~front_quarter)
    # The lower three quadrants and the physical opening stay byte-identical.
    trusted_wall = wall_region(scene, mask, quad, corner_shadow=True)
    assert not np.any(changed & (mask == 0) & ~trusted_wall)
    assert np.array_equal(out[105:250, 245:252], rendered[105:250, 245:252])
    assert qa["unauthorized_changed_pixels"] == 0
    assert qa["front_shadow_pixels"] > 0
