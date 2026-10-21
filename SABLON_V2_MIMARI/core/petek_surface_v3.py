# -*- coding: utf-8 -*-
"""PETEK V3: immutable-source compositing; never draw synthetic vents.

An approved, source-hash-bound grayscale mask identifies *only* printable
wood. Holes, top/bottom arches, interior shadows, floor and room all remain
original pixels. Candidate masks are NOT approvals. No network/model required.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

CATEGORY = "06_Petek_Dolabi"
RECIPE = "petek_v3_original_detail_mask_20261021"
LOGGER = logging.getLogger("petek.v3")


class PetekSafetyError(ValueError):
    """Denote rejection without modifying source files or existing outputs."""


@dataclass(frozen=True)
class PetekLimits:
    """Centralize resource, confidence and geometric safety limits."""
    max_file_bytes: int = 70 * 1024 * 1024
    max_image_pixels: int = 32_000_000
    minimum_quad_area_fraction: float = 0.012
    minimum_print_fraction: float = 0.12
    maximum_print_fraction: float = 0.94
    min_component_area_fraction: float = 0.00007
    minimum_candidate_confidence: float = 0.60
    max_edge_feather_px: float = 0.65
    candidate_luminance_delta: int = 24
    mask_inside_tolerance: int = 2
    maximum_working_edge: int = 6000
    storage_chunk_bytes: int = 1024 * 1024
    minimum_dimension: int = 128
    output_width: int = 1200
    output_height: int = 1600


LIMITS = PetekLimits()


def sha256_file(path: Path) -> str:
    """Stream a file digest without loading a whole image into RAM."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(LIMITS.storage_chunk_bytes), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_safe_file(path: Path, root: Path | None = None) -> Path:
    """Reject symlinks, missing files, giant files and traversal outside root."""
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise PetekSafetyError("SOURCE_NOT_REGULAR_FILE")
    resolved = path.resolve(strict=True)
    if root is not None:
        base = Path(root).resolve(strict=True)
        if resolved == base or base not in resolved.parents:
            raise PetekSafetyError("PATH_OUTSIDE_ALLOWED_ROOT")
    size = resolved.stat().st_size
    if size <= 0 or size > LIMITS.max_file_bytes:
        raise PetekSafetyError("UNSAFE_FILE_SIZE")
    return resolved


def read_image(path: Path, mode: int = cv2.IMREAD_COLOR) -> np.ndarray:
    """Read Unicode paths and reject oversized or corrupted encoded images."""
    path = require_safe_file(path)
    # cv2 has codec size checks; the post-decode pixel cap is a further guard.
    arr = np.fromfile(str(path), dtype=np.uint8)
    try:
        image = cv2.imdecode(arr, mode)
    except cv2.error as exc:
        raise PetekSafetyError("IMAGE_DECODE_FAILED") from exc
    if image is None or image.ndim not in (2, 3):
        raise PetekSafetyError("IMAGE_UNREADABLE")
    h, w = image.shape[:2]
    if h < LIMITS.minimum_dimension or w < LIMITS.minimum_dimension:
        raise PetekSafetyError("IMAGE_TOO_SMALL")
    if h * w > LIMITS.max_image_pixels:
        raise PetekSafetyError("IMAGE_TOO_LARGE")
    return image


def validate_quad(quad: object, width: int, height: int) -> np.ndarray:
    """Accept only explicit TL/TR/BR/BL, nonfolded, finite in-image geometry."""
    try:
        pts = np.asarray(quad, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise PetekSafetyError("QUAD_NOT_NUMERIC") from exc
    if pts.shape != (4, 2) or not np.isfinite(pts).all():
        raise PetekSafetyError("QUAD_INVALID_SHAPE_OR_NAN")
    if (pts[:, 0].min() < 0 or pts[:, 1].min() < 0 or
            pts[:, 0].max() > width - 1 or pts[:, 1].max() > height - 1):
        raise PetekSafetyError("QUAD_OUTSIDE_IMAGE")
    edges = np.roll(pts, -1, axis=0) - pts
    turns = edges[:, 0] * np.roll(edges[:, 1], -1) - edges[:, 1] * np.roll(edges[:, 0], -1)
    if not np.all(turns > 1e-5):
        raise PetekSafetyError("QUAD_WRONG_ORDER_OR_CONCAVE")
    if np.min(np.linalg.norm(edges, axis=1)) < 8:
        raise PetekSafetyError("QUAD_DEGENERATE")
    area = float(cv2.contourArea(pts.astype(np.float32)))
    if area < width * height * LIMITS.minimum_quad_area_fraction:
        raise PetekSafetyError("QUAD_TOO_SMALL")
    return pts.astype(np.float32)


def quad_mask(shape: tuple[int, int], quad: np.ndarray) -> np.ndarray:
    """Construct a precise full-scene bounding mask in original coordinates."""
    h, w = shape
    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.fillConvexPoly(mask, np.round(quad).astype(np.int32), 255, lineType=cv2.LINE_8)
    return mask


def validate_print_mask(mask: np.ndarray, scene_shape: tuple[int, int],
                        quad: np.ndarray) -> dict:
    """Fail closed for leaked, tiny, empty or full-quad masks."""
    h, w = scene_shape
    if mask.dtype != np.uint8 or mask.shape != (h, w):
        raise PetekSafetyError("MASK_MUST_BE_FULL_SCENE_GRAYSCALE_U8")
    support = quad_mask((h, w), quad)
    allowed = cv2.dilate(support, np.ones((3, 3), np.uint8))
    leakage = int(np.count_nonzero((mask > LIMITS.mask_inside_tolerance) & (allowed == 0)))
    if leakage:
        raise PetekSafetyError(f"MASK_LEAK_OUTSIDE_PANEL:{leakage}")
    panel_size = int(np.count_nonzero(support))
    print_size = int(np.count_nonzero(mask > 127))
    coverage = print_size / max(panel_size, 1)
    if not LIMITS.minimum_print_fraction <= coverage <= LIMITS.maximum_print_fraction:
        raise PetekSafetyError(f"MASK_IMPLAUSIBLE_COVERAGE:{coverage:.4f}")
    return {"print_fraction": round(coverage, 6),
            "original_preserved_pixels": int(mask.size - np.count_nonzero(mask))}


def candidate_print_mask(scene: np.ndarray, quad: object) -> tuple[np.ndarray, dict]:
    """Generate a conservative DRAFT wood mask; NEVER auto-approve its result.

    CIELAB luminance + low-chroma seeds within reviewed quad. Dark vent
    interiors, black arches and most exposed floors are excluded. Colors that
    resemble wood outside the surface require human mask inspection.
    """
    h, w = scene.shape[:2]
    points = validate_quad(quad, w, h)
    region = quad_mask((h, w), points)
    lab = cv2.cvtColor(scene, cv2.COLOR_BGR2LAB)
    lum = lab[..., 0]
    a = lab[..., 1].astype(np.int16) - 128
    b = lab[..., 2].astype(np.int16) - 128
    yy, xx = np.where(region > 0)
    if yy.size < 100:
        raise PetekSafetyError("PANEL_EMPTY")
    high_ref = float(np.percentile(lum[yy, xx], 85))
    brightness = max(110.0, high_ref - LIMITS.candidate_luminance_delta)
    chroma = np.sqrt(a.astype(np.float32) ** 2 + b.astype(np.float32) ** 2)
    # Candidate mask deliberately conservative. This is a preview, not truth.
    valid = (region > 0) & (lum >= brightness) & (chroma <= 34.0)
    proposed = np.where(valid, 255, 0).astype(np.uint8)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    proposed = cv2.morphologyEx(proposed, cv2.MORPH_OPEN, kernel)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(proposed, 8)
    min_area = max(3, int(np.count_nonzero(region) * LIMITS.min_component_area_fraction))
    for component in range(1, n):
        if int(stats[component, cv2.CC_STAT_AREA]) < min_area:
            proposed[labels == component] = 0
    ratio = float(np.count_nonzero(proposed) / max(np.count_nonzero(region), 1))
    contrast = max(0.0, min(1.0, (high_ref - float(np.percentile(lum[yy, xx], 12))) / 110.0))
    confidence = max(0.0, min(0.82, contrast * 0.6 + min(ratio, 0.75) * 0.25))
    return proposed, {"review_status": "DRAFT", "candidate_confidence": round(confidence, 4),
                      "candidate_print_fraction": round(ratio, 5),
                      "warning": "Candidate is never an automatic approval"}


def prepare_contain_artwork(art: np.ndarray, canvas_width: int, canvas_height: int) -> np.ndarray:
    """Fit artwork exactly once without cropping or stretching meaningful content."""
    if canvas_width < 2 or canvas_height < 2:
        raise PetekSafetyError("ARTWORK_CANVAS_INVALID")
    h, w = art.shape[:2]
    scale = min(canvas_width / w, canvas_height / h)
    tw, th = max(1, round(w * scale)), max(1, round(h * scale))
    interpolation = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_CUBIC
    resized = cv2.resize(art, (tw, th), interpolation=interpolation)
    canvas = np.full((canvas_height, canvas_width, 3), 255, dtype=np.uint8)
    x, y = (canvas_width - tw) // 2, (canvas_height - th) // 2
    canvas[y:y + th, x:x + tw] = resized
    return canvas


def project_print(art: np.ndarray, scene_shape: tuple[int, int],
                  quad: np.ndarray, aspect: float) -> np.ndarray:
    """Project art once from a normalized virtual panel to original pixels."""
    if not np.isfinite(aspect) or aspect <= 0 or aspect > 12:
        raise PetekSafetyError("INVALID_PHYSICAL_ASPECT")
    virtual_edge = min(
        LIMITS.maximum_working_edge,
        max(1024, int(max(art.shape[:2]) * 1.4)),
    )
    if aspect >= 1:
        width, height = virtual_edge, round(virtual_edge / aspect)
    else:
        height, width = virtual_edge, round(virtual_edge * aspect)
    width, height = max(2, width), max(2, height)
    page = prepare_contain_artwork(art, width, height)
    source = np.float32([[0, 0], [width-1, 0], [width-1, height-1], [0, height-1]])
    transform = cv2.getPerspectiveTransform(source, quad.astype(np.float32))
    if not np.isfinite(transform).all() or abs(np.linalg.det(transform)) < 1e-12:
        raise PetekSafetyError("UNSTABLE_HOMOGRAPHY")
    h, w = scene_shape
    return cv2.warpPerspective(page, transform, (w, h),
                               flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT,
                               borderValue=(255, 255, 255))


def composite_original_details(scene: np.ndarray, projected: np.ndarray,
                               mask: np.ndarray, quad: np.ndarray) -> tuple[np.ndarray, dict]:
    """Replace only printable wood; every mask-zero source pixel stays byte-identical."""
    h, w = scene.shape[:2]
    qa = validate_print_mask(mask, (h, w), quad)
    if projected.shape != scene.shape or scene.dtype != np.uint8:
        raise PetekSafetyError("COMPOSITING_SHAPE_MISMATCH")
    # Feather is capped and restricted to the already-reviewed mask boundary.
    # Do not blur artwork, source, dark slots, arches, floor or global output.
    radius = LIMITS.max_edge_feather_px
    if radius:
        alpha_u8 = cv2.GaussianBlur(mask, (3, 3), radius)
        # No newly printable pixels outside approved nonzero mask.
        alpha_u8[mask == 0] = 0
    else:
        alpha_u8 = mask
    result = scene.copy()
    full = alpha_u8 == 255
    partial = (alpha_u8 > 0) & ~full
    result[full] = projected[full]
    if np.any(partial):
        alpha = alpha_u8[partial].astype(np.uint16)[:, None]
        # Integer compositing avoids hidden whole-image color/blur changes.
        mixed = ((projected[partial].astype(np.uint16) * alpha
                  + scene[partial].astype(np.uint16) * (255-alpha) + 127) // 255)
        result[partial] = mixed.astype(np.uint8)
    if not np.array_equal(scene[mask == 0], result[mask == 0]):
        raise PetekSafetyError("ORIGINAL_DETAIL_PIXEL_GUARD_FAILED")
    qa["source_preservation_exact"] = True
    qa["mask_applied_pixels"] = int(np.count_nonzero(mask))
    return result, qa


def contain_marketplace(scene: np.ndarray, width: int = LIMITS.output_width,
                        height: int = LIMITS.output_height) -> np.ndarray:
    """3:4 output without scene crop, global blur or geometric stretching."""
    if width <= 0 or height <= 0 or width * height > LIMITS.max_image_pixels:
        raise PetekSafetyError("MARKETPLACE_CANVAS_UNSAFE")
    h, w = scene.shape[:2]
    scale = min(width / w, height / h)
    iw, ih = max(1, round(w * scale)), max(1, round(h * scale))
    resized = cv2.resize(scene, (iw, ih),
                         interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LANCZOS4)
    # Neutral surround is predictable, non-deceptive and never blurs printing.
    canvas = np.full((height, width, 3), (246, 246, 246), dtype=np.uint8)
    x, y = (width-iw)//2, (height-ih)//2
    canvas[y:y+ih, x:x+iw] = resized
    return canvas


def publish_image_create_only(image: np.ndarray, destination: Path) -> str:
    """Atomically publish PNG without ever replacing an existing artifact."""
    destination = Path(destination)
    if destination.exists() or destination.is_symlink():
        raise PetekSafetyError("OUTPUT_EXISTS_NO_OVERWRITE")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.parent.is_symlink():
        raise PetekSafetyError("OUTPUT_DIRECTORY_SYMLINK")
    ok, data = cv2.imencode(".png", image, [cv2.IMWRITE_PNG_COMPRESSION, 3])
    if not ok:
        raise PetekSafetyError("PNG_ENCODE_FAILED")
    fd, name = tempfile.mkstemp(prefix=".petek-", suffix=".tmp", dir=str(destination.parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data.tobytes())
            stream.flush()
            os.fsync(stream.fileno())
        os.link(name, destination)  # exclusive hard link, never overwrite
        return sha256_file(destination)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def make_artifact_key(source_sha: str, art_sha: str, mask_sha: str,
                      template_uid: str) -> str:
    """Version immutable artifact identity by all visual inputs."""
    joined = "|".join((RECIPE, CATEGORY, template_uid, source_sha, art_sha, mask_sha))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:24]


def render_approved(art_path: Path, source_path: Path, profile: dict,
                    printable_mask: np.ndarray, output_path: Path,
                    marketplace: bool = True) -> dict:
    """Fail closed unless reviewed mask and exact template bytes agree."""
    if profile.get("category") != CATEGORY or profile.get("review_status") != "APPROVED":
        raise PetekSafetyError("PETEK_PROFILE_NOT_HUMAN_APPROVED")
    if profile.get("recipe") != RECIPE:
        raise PetekSafetyError("PETEK_RECIPE_MISMATCH")
    source_path, art_path = require_safe_file(source_path), require_safe_file(art_path)
    source_sha, art_sha = sha256_file(source_path), sha256_file(art_path)
    if source_sha != profile.get("source_sha256"):
        raise PetekSafetyError("SOURCE_CHANGED_APPROVAL_STALE")
    scene = read_image(source_path)
    artwork = read_image(art_path)
    h, w = scene.shape[:2]
    if [w, h] != profile.get("source_dimensions"):
        raise PetekSafetyError("SOURCE_DIMENSIONS_CHANGED")
    quad = validate_quad(profile.get("front_quad"), w, h)
    mask_sha = hashlib.sha256(printable_mask.tobytes()).hexdigest()
    if mask_sha != profile.get("mask_sha256"):
        raise PetekSafetyError("REVIEWED_MASK_TAMPERED")
    projected = project_print(artwork, (h,w), quad, float(profile["physical_aspect"]))
    output, qa = composite_original_details(scene, projected, printable_mask, quad)
    if marketplace:
        output = contain_marketplace(output)
    result_sha = publish_image_create_only(output, output_path)
    LOGGER.info("PETEK_RENDER %s %s %s", profile["template_uid"], output_path, result_sha)
    return {"output_sha256": result_sha,
            "artifact_key": make_artifact_key(source_sha, art_sha, mask_sha,
                                              profile["template_uid"]),
            "quality": qa, "recipe": RECIPE}
