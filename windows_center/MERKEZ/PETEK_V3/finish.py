"""V3.8 optional print-edge experiments; no changes to underlying approved mask.

WHITE BORDER is white PRINT in the allowed mask, not automatic mask repair.
BLEED is an extra artwork crop, not a way to print into protected source pixels.
Neither option is enabled for regular production until a user accepts A/B tests.
"""
from __future__ import annotations
import cv2
import numpy as np

FRAMES=(0,5,10)  # nominal mm only if a real front width in cm is supplied


def white_border(projected:np.ndarray, quad, mask:np.ndarray, *, frame_mm=0,
                 panel_width_cm=None, physical_aspect=1.1163):
    if frame_mm not in FRAMES:
        raise ValueError('Beyaz sınır seçeneği 0, 5 veya 10 mm olmalı')
    if frame_mm==0:
        return projected.copy()
    if mask.shape!=projected.shape[:2]:
        raise ValueError('Maske ile baskı boyutları farklı')
    if not .12 <= float(physical_aspect) <= 12:
        raise ValueError('En-boy oranı geçersiz')
    if panel_width_cm is None:
        # Reference-only; UI MUST label this as *approximate*.
        panel_width_cm=96.
    if not 20 <= float(panel_width_cm) <= 400:
        raise ValueError('Fiziksel genişlik cm olarak 20-400 aralığında olmalı')
    # Rectified full panel with physically proportional horizontal & vertical mm.
    width_mm=float(panel_width_cm)*10
    height_mm=width_mm/float(physical_aspect)
    bw=min(.1,frame_mm/width_mm)
    bh=min(.1,frame_mm/height_mm)
    rw=1000; rh=max(100,round(rw/physical_aspect))
    tx=max(1,round(bw*rw));ty=max(1,round(bh*rh))
    ring=np.full((rh,rw),255,np.uint8)
    ring[ty:rh-ty,tx:rw-tx]=0
    source=np.float32([[0,0],[rw-1,0],[rw-1,rh-1],[0,rh-1]])
    target=np.asarray(quad,np.float32)
    projected_ring=cv2.warpPerspective(ring,cv2.getPerspectiveTransform(source,target),
             (projected.shape[1],projected.shape[0]),flags=cv2.INTER_LINEAR,
             borderMode=cv2.BORDER_CONSTANT,borderValue=0)
    # Never print outside approved mask: original vents/arch/floor preserved.
    opacity=(projected_ring.astype(np.float32)/255.)*(mask.astype(np.float32)/255.)
    print_white=np.full_like(projected,245)
    out=projected.astype(np.float32)*(1.-opacity[:,:,None])+print_white.astype(np.float32)*opacity[:,:,None]
    return np.uint8(np.clip(out+.5,0,255))
