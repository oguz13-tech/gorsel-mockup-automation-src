# -*- coding: utf-8 -*-
"""Non-destructive EPIC-3 visual QA gate adapted from Argon observations.

Never auto-approves a commercial template. SHA-bound known defects are hard
blocks; geometry/pixel heuristics produce review findings. Human acceptance
remains mandatory, especially glass/occlusion categories.
"""
from __future__ import annotations

import math
from typing import Any
import cv2
import numpy as np

ERROR_CODES = (
    "ARTWORK_CROPPED", "TEMPLATE_RESIDUE", "GEOMETRY_MISALIGNMENT",
    "MASK_EDGE_ARTIFACT", "OCCLUSION_FAILURE", "SCENE_PRODUCT_MISMATCH",
    "WATERMARK_OR_LICENSE_RISK", "FRAME_OR_MATERIAL_ERROR",
    "MARKETPLACE_FRAMING_FAILURE", "VISUAL_REVIEW_REQUIRED",
)

# Entries are bound to exact defective source image bytes. The names are
# informational; only an exact source SHA may trigger the known-defect block.
KNOWN_BLOCKED_TEMPLATE_SHAS = {
    "a9e171c72e7c471d0f46b3e11216c9d1765f17c17863718d362ff126cf676385":
        ("01_Wifi_Kutusu", "WATERMARK_OR_LICENSE_RISK", "MASK_EDGE_ARTIFACT"),
    "06d1d0e43a4909f09f2a58376942a1a1d88bc12b1710726b0786c08f0284086b":
        ("02_Cam_Tablo_Dikey", "TEMPLATE_RESIDUE", "GEOMETRY_MISALIGNMENT"),
    "2b49a2964760999a31932757410085100f88e3088c8c0018a9614a35361868f6":
        ("02_Cam_Tablo_Yatay", "TEMPLATE_RESIDUE", "VISUAL_REVIEW_REQUIRED"),
    "30e0a1126ab202646c501207c2e2d4f0c207a855c92b0e0f7d7b89c136f41553":
        ("03_Ahsap_Tablo", "MASK_EDGE_ARTIFACT", "FRAME_OR_MATERIAL_ERROR"),
    "f85ce0987e24d45d05a2777a222a740e553b959a24b3d4a448697c52e75b5c0c":
        ("04_Cam_Dograma", "SCENE_PRODUCT_MISMATCH", "OCCLUSION_FAILURE"),
    "2981dd06a6ad3ae62666d4a5a055436e5d0690546050606b6b59546205239895":
        ("05_Ocak_Arkasi", "GEOMETRY_MISALIGNMENT", "MARKETPLACE_FRAMING_FAILURE"),
}


def visual_qa_report(category: str, source_image: np.ndarray, quad,
                     *, nominal_aspect: float = 4/3,
                     source_sha256: str = "", render_output: np.ndarray | None = None) -> dict[str, Any]:
    """Advisory pixel checks; no file writes, no auto-approval."""
    failures, review = [], []
    if source_sha256 in KNOWN_BLOCKED_TEMPLATE_SHAS:
        category_seen, *known = KNOWN_BLOCKED_TEMPLATE_SHAS[source_sha256]
        if category_seen == category:
            failures.extend(known)
    if source_image is None or not getattr(source_image, "size", 0):
        failures.append("GEOMETRY_MISALIGNMENT")
        return {"status":"BLOCKED","blocking_defects":failures,"review_findings":review}
    height,width=source_image.shape[:2]
    try:
        q=np.asarray(quad, dtype=np.float64)
        if q.shape != (4,2) or not np.isfinite(q).all():
            raise ValueError("BAD_POINTS")
        if (q[:,0]<0).any() or (q[:,1]<0).any() or (q[:,0]>=width).any() or (q[:,1]>=height).any():
            raise ValueError("POINT_OUTSIDE_SOURCE")
        contour=q.astype(np.float32)
        if not cv2.isContourConvex(contour.astype(np.int32)):
            raise ValueError("NON_CONVEX")
        if abs(cv2.contourArea(contour)) < width*height*0.02:
            raise ValueError("TOO_SMALL")
        ab=(np.linalg.norm(q[1]-q[0])+np.linalg.norm(q[2]-q[3]))/2.0
        bc=(np.linalg.norm(q[2]-q[1])+np.linalg.norm(q[3]-q[0]))/2.0
        if bc<=0 or not 0<float(nominal_aspect)<10:
            raise ValueError("INVALID_ASPECT")
        apparent=ab/bc
        if abs(apparent/float(nominal_aspect)-1)>0.24:
            review.append("GEOMETRY_MISALIGNMENT")
    except (TypeError,ValueError,OverflowError):
        failures.append("GEOMETRY_MISALIGNMENT")
    if render_output is not None:
        if getattr(render_output,"shape",(0,0))[:2] != (1600,1200):
            failures.append("MARKETPLACE_FRAMING_FAILURE")
        else:
            # Extreme low-content borders can be letterboxing. The heuristic
            # is ADVISORY only, since valid lifestyle scenes may be dark.
            edges=[render_output[:30],render_output[-30:],
                   render_output[:,:25],render_output[:,-25:]]
            if all(float(np.std(x))<2 for x in edges):
                review.append("MARKETPLACE_FRAMING_FAILURE")
    return {
        "category":category, "status":"BLOCKED" if failures else "VISUAL_REVIEW_REQUIRED",
        "blocking_defects":sorted(set(failures)),
        "review_findings":sorted(set(review)),
        "human_approval_required":True,
    }
