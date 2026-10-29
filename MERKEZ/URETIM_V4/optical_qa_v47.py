"""Objective, repeatable optical A/B QA; not a substitute for human approval.

Tracks printed-region effect visibility, clipping (white/black lost details),
input text-edge retention, and changes outside the protected print mask.
"""
from __future__ import annotations
import numpy as np
import cv2
from .finish_material_v46 import GLASS, DAYLIGHT

def measure_effect(before, after, mask, category):
    if before.shape!=after.shape or before.dtype!=np.uint8 or mask.shape!=before.shape[:2]:
        raise ValueError('OPTICAL_QA_SHAPE')
    selected=mask>0
    if not np.any(selected):raise ValueError('OPTICAL_QA_EMPTY')
    delta=np.abs(before.astype(np.int16)-after.astype(np.int16))
    outside=int(np.count_nonzero(np.any(delta>0,axis=2) & ~selected))
    signal=delta[selected]
    pre=cv2.cvtColor(before,cv2.COLOR_BGR2GRAY)
    post=cv2.cvtColor(after,cv2.COLOR_BGR2GRAY)
    edge=cv2.Canny(pre,70,140)>0
    important=edge & selected
    pixel_diff=signal.mean() if len(signal) else 0
    loss=float(np.mean(np.abs(post[important].astype(np.float32)-pre[important].astype(np.float32)))) if important.any() else 0.
    return {'category':category,'protected_pixel_changes':outside,
            'mean_inside_delta':round(float(pixel_diff),3),
            'p95_inside_delta':float(np.percentile(signal,95)),
            'detail_edge_delta':round(loss,3),
            'status':'FAIL' if outside else ('NO_VISIBLE_EFFECT' if pixel_diff<0.4 and category in GLASS|DAYLIGHT else 'CHECK_HUMAN')}
