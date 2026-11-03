"""V4.10.2 opt-in seven-category photographic daylight integration.

This module is NOT a learned image-relighting model. It shares the exact
PETEK two-band PHOTO-space field with legacy categories and conservatively
allows the matching pattern onto verified neutral wall regions. The scene,
approved mask, quad and artworks are immutable; only an output copy changes.
Never hallucinates background walls, never edits a dark vent, opening, floor,
frame or colored/magenta reference marker in the original photograph.
"""
from __future__ import annotations

import cv2
import numpy as np

from PETEK_V3.realism import _magenta_pixels
from PETEK_V3.wall_window_shadows_vnext import apply_wall_window_shadows, wall_region

RECIPE = 'SEVEN_CATEGORY_PHOTO_DAYLIGHT_V2_LIGHTER_WHITE_20261101'
PROFILES = ('off', 'dogal', 'belirgin')
CATEGORIES = frozenset({
    '01_Wifi_Kutusu', '02_Cam_Tablo_Dikey', '02_Cam_Tablo_Yatay',
    '03_Ahsap_Tablo', '04_Cam_Dograma', '05_Ocak_Arkasi',
    '06_Petek_Kapama',
})
GLASS = frozenset({'02_Cam_Tablo_Dikey', '02_Cam_Tablo_Yatay',
                   '04_Cam_Dograma', '05_Ocak_Arkasi'})


def daylight_lighting(base_lighting: str, profile: str) -> str:
    """Old global OFF always overrides new controls; PETEK remains opt-in."""
    if profile not in PROFILES:
        raise ValueError('SEVEN_CATEGORY_DAYLIGHT_PROFILE_INVALID')
    if base_lighting not in ('off', 'natural', 'strong'):
        raise ValueError('SEVEN_CATEGORY_BASE_LIGHTING_INVALID')
    if base_lighting == 'off' or profile == 'off':
        return base_lighting
    return 'strong' if profile == 'belirgin' else 'natural'


def apply_scene_daylight(scene: np.ndarray, rendered: np.ndarray,
                         mask: np.ndarray, quad, category: str, *,
                         profile: str = 'off') -> tuple[np.ndarray, dict]:
    """Light/material harmonization + verified wall continuity, in RAM.

    Renderer already applies the same PETEK sun field *inside* the printable
    front. We must NOT draw it a second time. For Belirgin, its exact field
    continues onto confident photo walls only. The rest is a conservative
    white-balance harmonization for neutral painted material.
    """
    if profile not in PROFILES or category not in CATEGORIES:
        raise ValueError('SEVEN_CATEGORY_DAYLIGHT_SETTINGS_INVALID')
    if (scene.dtype != np.uint8 or rendered.dtype != np.uint8 or
        scene.ndim != 3 or scene.shape[2] != 3 or scene.shape != rendered.shape or
        mask.dtype != np.uint8 or mask.shape != scene.shape[:2] or
        np.asarray(quad).shape != (4, 2)):
        raise ValueError('SEVEN_CATEGORY_DAYLIGHT_GEOMETRY_INVALID')
    before_scene = scene.copy()
    before_mask = mask.copy()
    out = rendered.copy()
    qa = {'status': 'OFF' if profile == 'off' else 'APPLIED',
          'profile': profile, 'category': category, 'recipe': RECIPE,
          'shadow_bands': 2, 'wall_shadow_pixels': 0,
          'neutral_harmony_pixels': 0, 'wall_status': 'OFF'}
    if profile == 'off':
        return out, qa
    active = mask > 0
    if np.count_nonzero(active) < 100:
        return out, {**qa, 'status': 'INSUFFICIENT_PRINT_AREA'}

    # Use real nearby neutral photo pixels to adjust print white slightly.
    # Source CHROMA markers must never enter the scene color estimate.
    hsv = cv2.cvtColor(scene, cv2.COLOR_BGR2HSV)
    safe = ((mask == 0) & (hsv[:, :, 1] < 58) &
            (hsv[:, :, 2] >= 125) & (hsv[:, :, 2] <= 250) &
            ~_magenta_pixels(scene))
    q = np.asarray(quad, dtype=np.float32)
    ymin, ymax = float(q[:, 1].min()), float(q[:, 1].max())
    xmin, xmax = float(q[:, 0].min()), float(q[:, 0].max())
    h, w = mask.shape
    yy, xx = np.ogrid[:h, :w]
    dx = max(16., (xmax - xmin) * .24)
    dy = max(12., (ymax - ymin) * .20)
    around = (xx >= xmin-dx) & (xx <= xmax+dx) & (yy >= ymin-dy) & (yy <= ymax+dy)
    nearby = safe & around
    if np.count_nonzero(nearby) > 120:
        photo_white = np.median(scene[nearby], axis=0).astype(np.float32)
        # Color CAST only; don't flatten artwork or turn legitimate dark
        # typography or saturated design into flat white/pink.
        chroma = photo_white / max(float(photo_white.mean()), 1.)
        chroma = np.clip(chroma, .965, 1.035)
        rhsv = cv2.cvtColor(out, cv2.COLOR_BGR2HSV)
        neutral = active & (rhsv[:, :, 1] < 52) & (rhsv[:, :, 2] > 125)
        amount = .22 if profile == 'dogal' else .40
        if np.any(neutral):
            v = out[neutral].astype(np.float32)
            out[neutral] = np.uint8(np.clip(v * (1. - amount + amount * chroma) + .5, 0, 255))
            qa['neutral_harmony_pixels'] = int(np.count_nonzero(neutral))
    else:
        qa['neutral_reference'] = 'NOT_CONFIDENT'

    if profile == 'belirgin':
        # The same shadow function and wall classifier as PETEK; its field is
        # computed from the original full photograph, never re-aligned to the
        # right/left side independently. Conservative false-negative is safer.
        out, wall_qa = apply_wall_window_shadows(scene, out, mask, quad, lighting='strong')
        qa['wall_status'] = wall_qa['status']
        qa['wall_shadow_pixels'] = int(wall_qa['wall_shadow_pixels'])
    if not np.array_equal(scene, before_scene) or not np.array_equal(mask, before_mask):
        raise ValueError('SEVEN_CATEGORY_DAYLIGHT_INPUT_MUTATION')
    # Only the printable front OR confidently identified wall may change.
    wall = wall_region(scene, mask, quad) if profile == 'belirgin' and qa['wall_shadow_pixels'] else np.zeros(mask.shape, bool)
    changed = np.any(rendered != out, axis=2)
    if np.any(changed & ~(active | wall)):
        raise ValueError('SEVEN_CATEGORY_DAYLIGHT_PROTECTED_REGION_CHANGED')
    if np.any(changed & wall):
        reference, _ = apply_wall_window_shadows(scene, rendered, mask, quad, lighting='strong')
        if not np.array_equal(out[changed & wall], reference[changed & wall]):
            raise ValueError('SEVEN_CATEGORY_DAYLIGHT_WALL_VERIFICATION_FAILED')
    return out, qa
