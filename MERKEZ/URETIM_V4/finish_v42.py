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


def subdued_reflection(scene, printed, mask, quad, category, lighting="strong"):
    """Controlled broad softbox/ambient reflection in PRINTABLE glass only.

    Inspired by edge- and reflected-light product photography: a large diffuse
    softbox and a softer secondary bounce, not white hard lines or fake windows.
    Human quad, frame/occlusion and all outside-mask pixels remain untouched.
    """
    if category not in GLASS or lighting == "off":
        return printed
    h, w = mask.shape
    sw, sh = 256, 320
    y, x = np.mgrid[0:sh, 0:sw].astype(np.float32)
    u, v = x / (sw - 1), y / (sh - 1)
    # Two offset, broad *soft* reflections with visible tonal gradients.
    main = np.exp(-(((u - .76) / .23) ** 2 + ((v - .26) / .66) ** 2) * .75)
    bounce = np.exp(-(((u - .16) / .34) ** 2 + ((v - .83) / .30) ** 2) * 1.4)
    edge = np.exp(-(((u - .975) / .085) ** 2)) * .60
    envelope = np.clip(main * .80 + bounce * .32 + edge * .55, 0, 1).astype(np.float32)
    H = cv2.getPerspectiveTransform(
        np.float32([[0, 0], [sw-1, 0], [sw-1, sh-1], [0, sh-1]]),
        np.asarray(quad, dtype=np.float32),
    )
    reflection = cv2.warpPerspective(envelope, H, (w, h), flags=cv2.INTER_LINEAR,
                                     borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    # Restrict to approved pixels; adapt to the already-printed brightness so
    # light letters aren't washed out while dark artwork still has a glass sheen.
    luma = cv2.cvtColor(printed, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
    # Glass shows both pale reflected softboxes on dark artwork and softly
    # darker surrounding-room reflections on white print; a fixed-white
    # overlay is invisible on an already-white panel.
    reflectivity = np.float32(.15 + .12 * (1.0 - luma))
    blend = np.clip(reflection * reflectivity, 0, .27)[:, :, None]
    target = np.where(luma[:, :, None] > .76, 175.0, 248.0)
    result = np.uint8(np.clip(printed.astype(np.float32) * (1.0 - blend)
                              + target * blend + .5, 0, 255))
    out = printed.copy()
    out[mask > 0] = result[mask > 0]
    return out