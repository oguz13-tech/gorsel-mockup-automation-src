"""Restrained category-aware photo finish within the human-approved print mask.

The historical 99_SISTEM_MOTORLARI code informed the reflected window/sheen
shapes, but its large synthetic white glows and background edits are NOT copied.
The source image is unchanged outside original mask, quad coordinates untouched.
"""
from __future__ import annotations
import cv2
import numpy as np

GLASS = {'02_Cam_Tablo_Dikey', '02_Cam_Tablo_Yatay', '04_Cam_Dograma', '05_Ocak_Arkasi'}


def projected_rounded_alpha(shape, quad, radius_fraction: float = .008):
    """Projected soft corner rounding without modifying human approved quad coordinates."""
    h, w = shape[:2]
    r = float(radius_fraction)
    if not 0 <= r <= .04:
        raise ValueError('Köşe yuvarlatma 0 ile %4 arasında olmalı')
    if r == 0:
        return np.ones((h, w), dtype=np.float32)
    sw, sh, upscale = 400, 500, 2
    mw, mh = sw * upscale, sh * upscale
    radius = max(2, int(round(min(mw, mh) * r)))
    mask = np.zeros((mh, mw), np.uint8)
    cv2.rectangle(mask, (radius, 0), (mw-1-radius, mh-1), 255, -1)
    cv2.rectangle(mask, (0, radius), (mw-1, mh-1-radius), 255, -1)
    for x in (radius, mw-1-radius):
        for y in (radius, mh-1-radius):
            cv2.circle(mask, (x, y), radius, 255, -1, lineType=cv2.LINE_AA)
    mask = cv2.resize(mask, (sw, sh), interpolation=cv2.INTER_AREA)
    src = np.float32([[0, 0], [sw-1, 0], [sw-1, sh-1], [0, sh-1]])
    dst = np.asarray(quad, dtype=np.float32)
    H = cv2.getPerspectiveTransform(src, dst)
    projected = cv2.warpPerspective(mask, H, (w, h), flags=cv2.INTER_LINEAR,
                                    borderMode=cv2.BORDER_CONSTANT, borderValue=0).astype(np.float32)/255.0
    return np.clip(projected, 0, 1)


def subdued_reflection(scene, printed, mask, quad, category, lighting='natural'):
    """Cam/ocak shimmer: weak scene-balanced specular reflection, clipped to mask.

    Reflection contributes <6% to any channel; keeps lettering legible and
    doesn't fabricate rigid bars/windows not present in the original room.
    """
    if category not in GLASS or lighting == 'off':
        return printed
    h, w = mask.shape
    # Construct a broad diffuse local highlight in panel coordinates, then project.
    sw, sh = 220, 280
    y, x = np.mgrid[0:sh, 0:sw].astype(np.float32)
    u, v = x / max(sw-1, 1), y / max(sh-1, 1)
    if category == '04_Cam_Dograma':
        envelope = np.exp(-(((u-.56)/.55)**2 + ((v-.28)/.29)**2)*2.1)
    elif category == '05_Ocak_Arkasi':
        envelope = np.exp(-(((u-.72)/.51)**2 + ((v-.23)/.43)**2)*1.7)
    else:
        envelope = np.exp(-(((u-.73)/.52)**2 + ((v-.29)/.53)**2)*1.6)
    envelope = np.float32(envelope)
    H = cv2.getPerspectiveTransform(
        np.float32([[0,0],[sw-1,0],[sw-1,sh-1],[0,sh-1]]), np.asarray(quad,dtype=np.float32))
    reflection = cv2.warpPerspective(envelope, H, (w,h), flags=cv2.INTER_LINEAR,
                                     borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    # Scene-aware: dark ambient scenes should not gain an artificial white bulb.
    scene_luma = cv2.cvtColor(scene, cv2.COLOR_BGR2GRAY).astype(np.float32)/255
    ambient = float(np.median(scene_luma[mask > 220])) if (mask>220).any() else .5
    strength = (.043 if lighting == 'natural' else .058) * np.clip(ambient/.65, .42, 1.0)
    blend = np.float32(reflection * strength)[:, :, None]
    result = np.uint8(np.clip(printed.astype(np.float32)*(1.-blend)+245.*blend+.5,0,255))
    out = printed.copy()
    out[mask>0] = result[mask>0]
    return out
