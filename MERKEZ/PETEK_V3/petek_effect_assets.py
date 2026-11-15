"""Bundled PETEK effect assets.

The files are release-local, deterministic PNG fields. They are loaded from
this source tree, never from the live runtime or an internet URL.
"""
from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np


ASSET_DIR = Path(__file__).resolve().parents[2] / "ASSETS" / "PETEK"
ASSET_FILES = {
    "G3": ASSET_DIR / "g3_window_frame_shadow.png",
    "Y3": ASSET_DIR / "y3_white_mdf_texture.png",
    "L1": ASSET_DIR / "l1_window_sunlight.png",
    # User-supplied, transparent PNG-32 window/blinds shadow.  It is a
    # render-only field; never baked into a source photograph or mask.
    "WINDOW_SHADOW": ASSET_DIR / "window_shadow_overlay_rgba.png",
}


@lru_cache(maxsize=8)
def _read_cached(name: str) -> np.ndarray:
    path = ASSET_FILES[name]
    # Some Windows delivery bundles retain the lossless fields as .jpg due to
    # an earlier packaging rename.  Accept that sibling without changing the
    # manifest's canonical asset key or touching either file.
    if not path.is_file() and path.suffix.lower() == ".png":
        sibling = path.with_suffix(".jpg")
        if sibling.is_file():
            path = sibling
    if not path.is_file():
        raise FileNotFoundError(f"PETEK_EFFECT_ASSET_MISSING:{path}")
    image = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    if image is None or image.dtype != np.uint8:
        raise ValueError(f"PETEK_EFFECT_ASSET_INVALID:{path}")
    # Delivery-safe fields may be encoded as RGBA PNG/JPEG with the grayscale
    # field in alpha and zero RGB.  Normalize that representation in memory.
    if image.ndim == 3 and image.shape[2] == 4:
        if not np.all(image[:, :, :3] == 0):
            raise ValueError(f"PETEK_EFFECT_ASSET_INVALID:{path}")
        image = image[:, :, 3]
    elif image.ndim == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    if image.ndim != 2:
        raise ValueError(f"PETEK_EFFECT_ASSET_INVALID:{path}")
    image.setflags(write=False)
    return image


def _read(name: str) -> np.ndarray:
    # Return the immutable release-local field from the bounded cache.  The
    # public helper preserves the old API while avoiding repeated disk decode.
    return _read_cached(name)


@lru_cache(maxsize=4)
def _read_window_shadow() -> np.ndarray:
    path = ASSET_FILES["WINDOW_SHADOW"]
    if not path.is_file():
        raise FileNotFoundError(f"PETEK_EFFECT_ASSET_MISSING:{path}")
    image = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    if image is None or image.ndim != 3 or image.shape[2] != 4 or image.dtype != np.uint8:
        raise ValueError("PETEK_WINDOW_SHADOW_RGBA_REQUIRED")
    # The supplied overlay is a black silhouette with transparency. Reject
    # accidental white/RGB backgrounds or opaque matte exports.
    alpha = image[:, :, 3]
    rgb = image[:, :, :3]
    if np.any((alpha == 0) & np.any(rgb != 0, axis=2)):
        raise ValueError("PETEK_WINDOW_SHADOW_NONTRANSPARENT_RGB")
    if int(np.count_nonzero(alpha)) == 0 or int(alpha.max()) >= 245:
        raise ValueError("PETEK_WINDOW_SHADOW_ALPHA_INVALID")
    alpha.setflags(write=False)
    return alpha


@lru_cache(maxsize=8)
def _load_fields_cached(size: tuple[int, int]) -> tuple[tuple[str, np.ndarray], ...]:
    """Load all fields and resize them to (width, height) with linear sampling."""
    width, height = size
    fields = []
    for name in ("G3", "Y3", "L1"):
        field = _read(name)
        resized = cv2.resize(field, (width, height), interpolation=cv2.INTER_LINEAR)
        resized.setflags(write=False)
        fields.append((name, resized))
    return tuple(fields)


def load_fields(size: tuple[int, int]) -> dict[str, np.ndarray]:
    return dict(_load_fields_cached(tuple(size)))


@lru_cache(maxsize=8)
def load_window_shadow(size: tuple[int, int]) -> np.ndarray:
    """Return the validated alpha field resized to ``(width, height)``."""
    width, height = size
    result = cv2.resize(_read_window_shadow(), (width, height), interpolation=cv2.INTER_LINEAR)
    result.setflags(write=False)
    return result


def _place_window_shadow_on_face(shape: tuple[int, int], quad) -> np.ndarray:
    """Place the supplied field on the measured right-upper face quadrant.

    The shadow asset is authored in its own image coordinates.  Placing it in an
    axis-aligned bounding box makes its upper edge drift on a perspective panel,
    especially at the PETEK right-top corner.  Warp the complete field directly
    to the perspective-correct ``[top-mid, right-top, right-mid, face-centre]``
    quadrilateral instead.  The approved print mask still provides the final
    safety clip in the caller, so this function never changes panel geometry.
    """
    h, w = shape[:2]
    source = _read_window_shadow()
    q = np.asarray(quad, np.float32).reshape(4, 2)
    if not np.isfinite(q).all():
        raise ValueError("PETEK_WINDOW_SHADOW_QUAD_INVALID")
    # q order is TL, TR, BR, BL.  These are the same bilinear midpoints used
    # by right_upper_quarter_mask, so the shadow's top edge terminates exactly
    # on the measured TR corner instead of on a bounding-box approximation.
    target = np.asarray([
        (q[0] + q[1]) * .5,
        q[1],
        (q[1] + q[2]) * .5,
        (q[0] + q[1] + q[2] + q[3]) * .25,
    ], np.float32)
    if abs(float(cv2.contourArea(target))) < 1.0:
        return np.zeros((h, w), np.uint8)
    src_h, src_w = source.shape
    src_corners = np.float32([
        [0, 0], [src_w - 1, 0], [src_w - 1, src_h - 1], [0, src_h - 1]
    ])
    transform = cv2.getPerspectiveTransform(src_corners, target)
    # Constant-zero borders ensure no shadow is synthesized outside the target
    # face polygon; the caller additionally intersects with the approved mask.
    return cv2.warpPerspective(
        source, transform, (w, h), flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT, borderValue=0,
    )


@lru_cache(maxsize=1)
def _manifest_cached() -> tuple[tuple[str, tuple[tuple[str, str], ...]], ...]:
    result = {}
    for name, path in ASSET_FILES.items():
        if not path.is_file() and path.suffix.lower() == ".png" and path.with_suffix(".jpg").is_file():
            path = path.with_suffix(".jpg")
        data = path.read_bytes()
        result[name] = {
            "path": str(path),
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": str(len(data)),
        }
    return tuple((name, tuple(sorted(values.items()))) for name, values in result.items())


def manifest() -> dict[str, dict[str, str]]:
    return {name: dict(values) for name, values in _manifest_cached()}


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


def apply_window_shadow_overlay(scene: np.ndarray, rendered: np.ndarray,
                                mask: np.ndarray, quad, *, strength=0.72):
    """Apply the supplied alpha shadow to the output copy only.

    The supplied field is fitted uniformly into the PETEK right-upper face
    quadrant, then clipped by the approved print mask.  Wall pixels require the
    trusted adjacent wall detector and matching upper-quarter continuation band.
    No source, mask or quad is modified, and all other pixels are byte-identical
    to ``rendered``.
    """
    from .realism import right_upper_quarter_mask, right_upper_continuation_band
    from .wall_window_shadows_vnext import wall_region

    if scene.shape != rendered.shape or scene.shape[:2] != mask.shape:
        raise ValueError("PETEK_WINDOW_SHADOW_SHAPE_MISMATCH")
    if scene.dtype != np.uint8 or rendered.dtype != np.uint8:
        raise ValueError("PETEK_WINDOW_SHADOW_UINT8_REQUIRED")
    q = np.asarray(quad, np.float32).reshape(4, 2)
    alpha = _place_window_shadow_on_face(scene.shape[:2], q).astype(np.float32) / 255.0
    front = (mask > 0) & right_upper_quarter_mask(mask.shape, q)
    wall = wall_region(scene, mask, q, corner_shadow=True)
    yy, xx = np.ogrid[:scene.shape[0], :scene.shape[1]]
    wall &= right_upper_continuation_band(scene.shape, q)
    wall &= xx > float(np.max(q[:, 0]))
    active = front | wall
    amount = np.clip(alpha * float(strength), 0.0, 0.45)
    active &= amount > 0.004
    out = rendered.copy()
    out[active] = np.uint8(np.clip(
        rendered[active].astype(np.float32) * (1.0 - amount[active, None]) + 0.5,
        0, 255))
    changed = np.any(out != rendered, axis=2)
    return out, {
        "status": "APPLIED" if int(np.count_nonzero(changed)) else "NO_INTERSECTION",
        "front_shadow_pixels": int(np.count_nonzero(changed & front)),
        "wall_shadow_pixels": int(np.count_nonzero(changed & wall)),
        "changed_pixels": int(np.count_nonzero(changed)),
        "unauthorized_changed_pixels": int(np.count_nonzero(changed & ~active)),
        "effect_scope": "RIGHT_UPPER_QUARTER_PLUS_TRUSTED_ADJACENT_WALL",
        "asset": "WINDOW_SHADOW",
        "asset_path": str(ASSET_FILES["WINDOW_SHADOW"].resolve()),
        "asset_sha256": hashlib.sha256(ASSET_FILES["WINDOW_SHADOW"].read_bytes()).hexdigest(),
        "asset_shape": list(_read_window_shadow().shape),
        "asset_format": "RGBA-uint8-alpha-only",
        "strength": float(strength),
        "render_only": True,
        "source_pixels_untouched": True,
        "visible_field_ratio": float(np.count_nonzero((alpha > (1.0 / 255.0)) & front) /
                                      max(1, np.count_nonzero(alpha > (1.0 / 255.0)))),
    }
