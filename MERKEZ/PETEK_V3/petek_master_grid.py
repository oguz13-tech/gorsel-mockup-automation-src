"""Source-measured PETEK master grille overlay.

The overlay is an explicitly selected review artifact. It is never enabled
implicitly by the normal renderer and cannot authorize pixels outside measured
source vent regions.
"""
from __future__ import annotations

import hashlib
import cv2
import numpy as np

from . import engine
from .petek_render_contract_v1 import RECT_H, RECT_W, digest_frame
from .petek_slot_geometry_vnext import measure_real_vents


MASTER_COLOR_BGR = (27, 25, 23)  # #17191B


def build_master_grid(scene, mask, quad):
    if (not isinstance(scene, np.ndarray) or scene.dtype != np.uint8 or
            scene.ndim != 3 or scene.shape[2] != 3 or
            not isinstance(mask, np.ndarray) or mask.shape != scene.shape[:2]):
        raise engine.MaskError('PETEK_MASTER_GRID_INPUT_INVALID')
    q = engine.validated_quad(quad, scene.shape)
    engine.mask_check(mask, scene, q)
    slots, qa = measure_real_vents(scene, mask, q)
    if len(slots) not in (14, 15, 16):
        raise engine.MaskError('PETEK_MASTER_GRID_VENT_COUNT_UNCERTAIN')

    target = np.float32([[0, 0], [RECT_W - 1, 0],
                         [RECT_W - 1, RECT_H - 1], [0, RECT_H - 1]])
    transform = cv2.getPerspectiveTransform(np.float32(q), target)
    photo = cv2.warpPerspective(scene, transform, (RECT_W, RECT_H),
                                 flags=cv2.INTER_LINEAR,
                                 borderValue=(230, 230, 230))
    rect_mask = cv2.warpPerspective(mask, transform, (RECT_W, RECT_H),
                                     flags=cv2.INTER_NEAREST, borderValue=255)
    gray = cv2.cvtColor(photo, cv2.COLOR_BGR2GRAY)
    blackhat = cv2.morphologyEx(
        gray, cv2.MORPH_BLACKHAT,
        cv2.getStructuringElement(cv2.MORPH_RECT, (31, 3)))
    rect_alpha = np.zeros((RECT_H, RECT_W), dtype=np.uint8)
    for slot in slots:
        x = int(round(slot['center']))
        half = max(2, int(round(float(slot['width']) / 2.0)))
        y0 = max(0, int(slot['y0']))
        y1 = min(RECT_H - 1, int(slot['y1']))
        if y1 - y0 < int(RECT_H * .28):
            raise engine.MaskError('PETEK_MASTER_GRID_SLOT_SPAN_UNCERTAIN')
        # A geometry rectangle alone is not authorization. Each selected
        # pixel must also be dark evidence from the source photo.
        evidence = (gray[y0:y1 + 1,
                          max(0, x - half):min(RECT_W, x + half + 1)] < 125)
        evidence |= blackhat[y0:y1 + 1,
                             max(0, x - half):min(RECT_W, x + half + 1)] > 8
        rect_alpha[y0:y1 + 1,
                   max(0, x - half):min(RECT_W, x + half + 1)] = (
            evidence.astype(np.uint8) * 255)
    rect_alpha[rect_mask > 0] = 0
    inverse = cv2.getPerspectiveTransform(target, np.float32(q))
    alpha = cv2.warpPerspective(rect_alpha, inverse,
                                (scene.shape[1], scene.shape[0]),
                                flags=cv2.INTER_NEAREST, borderValue=0)
    # The physical mask remains authoritative: the overlay can only target
    # protected source pixels, never printable artwork.
    alpha[mask > 0] = 0
    if int(np.count_nonzero(alpha)) < len(slots) * 20:
        raise engine.MaskError('PETEK_MASTER_GRID_EVIDENCE_TOO_WEAK')
    overlay = np.zeros((scene.shape[0], scene.shape[1], 4), dtype=np.uint8)
    overlay[:, :, :3] = np.asarray(MASTER_COLOR_BGR, dtype=np.uint8)
    overlay[:, :, 3] = alpha
    return overlay, {
        'status': 'SOURCE_MEASURED_MASTER_GRID',
        'source_vent_count': len(slots),
        'authorized_pixels': int(np.count_nonzero(alpha)),
        'mask_protected_pixels_only': True,
        'vent_measurement_qa': qa,
        'overlay_sha256': hashlib.sha256(overlay.tobytes()).hexdigest(),
    }


def apply_master_grid(scene, picture, mask, overlay):
    if (overlay.shape[:2] != picture.shape[:2] or overlay.shape[2] != 4 or
            picture.dtype != np.uint8 or scene.shape != picture.shape):
        raise engine.MaskError('PETEK_MASTER_GRID_SHAPE_INVALID')
    alpha = overlay[:, :, 3] > 0
    if np.any(alpha & (mask > 0)):
        raise engine.MaskError('PETEK_MASTER_GRID_PRINTABLE_PIXEL_FORBIDDEN')
    gray = cv2.cvtColor(scene, cv2.COLOR_BGR2GRAY)
    blackhat = cv2.morphologyEx(
        gray, cv2.MORPH_BLACKHAT,
        cv2.getStructuringElement(cv2.MORPH_RECT, (31, 3)))
    dark_evidence = (gray < 125) | (blackhat > 8)
    # Perspective rasterization can move a rectified edge by one source pixel;
    # verify against a tiny source neighborhood, not an unrestricted region.
    dark_evidence = cv2.dilate(
        dark_evidence.astype(np.uint8),
        cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))) > 0
    if np.any(alpha & ~dark_evidence):
        raise engine.MaskError('PETEK_MASTER_GRID_SOURCE_DARK_PIXEL_REQUIRED')
    result = picture.copy()
    result[alpha] = overlay[alpha, :3]
    return result, {
        'status': 'PASS',
        'changed_pixels': int(np.count_nonzero(alpha)),
        'expected_bgr': list(MASTER_COLOR_BGR),
        'overlay_sha256': hashlib.sha256(overlay.tobytes()).hexdigest(),
    }


def verify_master_grid(scene, picture, mask, overlay):
    alpha = overlay[:, :, 3] > 0
    if np.any(alpha & (mask > 0)):
        raise engine.MaskError('PETEK_MASTER_GRID_PRINTABLE_PIXEL_FORBIDDEN')
    expected_color = np.asarray(MASTER_COLOR_BGR, dtype=np.uint8)
    if np.any(np.any(picture[alpha] != expected_color, axis=1)):
        raise engine.MaskError('PETEK_MASTER_GRID_OUTPUT_NOT_BLACK')
    return {
        'status': 'PASS',
        'authorized_pixels': int(np.count_nonzero(alpha)),
        'output_sha256': digest_frame(picture),
    }
