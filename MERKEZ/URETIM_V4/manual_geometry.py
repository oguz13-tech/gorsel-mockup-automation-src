"""Small user-approved legacy quads may cover <1.8% of a photographed room.

The PETEK detector deliberately rejects implausibly small panels. That
heuristic must not override manual approval in the six original categories.
Keep PETEK's independent review/mask constraints unchanged.
"""
from __future__ import annotations

import cv2
import numpy as np


def validated_legacy_manual_quad(points, image_shape):
    from PETEK_V3.engine import MaskError

    try:
        q = np.asarray(points, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise MaskError('Manuel dört köşe sayısal olmalı.') from exc
    if q.shape != (4, 2) or not np.isfinite(q).all():
        raise MaskError('Manuel olarak 4 geçerli köşe seçilmelidir.')
    h, w = image_shape[:2]
    if w < 2 or h < 2 or (q[:, 0] < 0).any() or (q[:, 0] > w - 1).any() or (q[:, 1] < 0).any() or (q[:, 1] > h - 1).any():
        raise MaskError('Dört köşe görüntünün gerçek piksel sınırları içinde olmalı.')
    v = np.roll(q, -1, axis=0) - q
    lengths = np.linalg.norm(v, axis=1)
    if np.min(lengths) < 3.0:
        raise MaskError('Manuel dört köşenin kenarı en az 3 piksel olmalıdır.')
    cross = v[:, 0] * np.roll(v[:, 1], -1) - v[:, 1] * np.roll(v[:, 0], -1)
    if not (np.all(cross > 1e-3) or np.all(cross < -1e-3)):
        raise MaskError('Dört köşe kendi içinde kesişemez; dışbükey bir yüzey seçilmeli.')
    q32 = q.astype(np.float32)
    area = abs(float(cv2.contourArea(q32)))
    if area < 16.0:
        raise MaskError('Sıfır alanlı veya bozuk dört köşe.')
    # Mirror the original manual UI aspect/homography safeguards, not its
    # automatic 5% or PETEK 1.8%-of-scene area cutoff.
    avg_w = float((lengths[0] + lengths[2]) * 0.5)
    avg_h = float((lengths[1] + lengths[3]) * 0.5)
    if max(avg_w / avg_h, avg_h / avg_w) > 10:
        raise MaskError('Manuel yüzeyin en-boy oranı geçersiz.')
    target = np.array([[0, 0], [100, 0], [100, 100], [0, 100]], dtype=np.float32)
    homography, _ = cv2.findHomography(q32, target)
    if homography is None or not np.isfinite(homography).all() or np.linalg.cond(homography) > 1e6:
        raise MaskError('Manuel perspektif hesabı kararsız; köşeleri kontrol edin.')
    return q32
