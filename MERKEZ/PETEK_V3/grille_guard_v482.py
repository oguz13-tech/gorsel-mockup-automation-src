"""PETEK magenta grille-edge guard; source-pixel-only, immutable registry.

Targets red/pink remnants next to *dark* vertical ventilation slots. Tight
hard print edges replace magenta on approved printable pixels while keeping
each hole/curve and all white furniture as original source pixels.
"""
from __future__ import annotations
import cv2
import numpy as np
from . import engine


def magenta_reference(scene: np.ndarray,quad) -> bool:
    """High-confidence saturated-magenta PANEL, not a colorful decoration."""
    q=engine.validated_quad(quad,scene.shape)
    poly=engine.polygon_mask(scene.shape,q)
    hsv=cv2.cvtColor(scene,cv2.COLOR_BGR2HSV)
    strong=cv2.inRange(hsv,(130,75,105),(176,255,255))
    numerator=int(np.count_nonzero(strong[poly>0]))
    denominator=max(1,int(np.count_nonzero(poly)))
    return numerator / denominator >= .13


def refine_magenta_draft_mask(scene: np.ndarray, quad, base:np.ndarray):
    """Cover near-magenta fringe pixels adjacent to printable wood, NOT slots.

    Called ONLY on unsaved automatic draft; never alter APPROVED registry masks.
    A candidate must be true pink-purple in the original photo, be in the
    four-corner polygon and adjacent to original printable magenta. Preserve
    dark recesses (V < 90), gray vent shadows, top/bottom black curves.
    """
    engine.mask_check(base,scene,quad)
    if not magenta_reference(scene,quad):
        return base,{'enabled':False,'added_magenta_edge_pixels':0}
    hsv=cv2.cvtColor(scene,cv2.COLOR_BGR2HSV)
    relaxed=cv2.inRange(hsv,(125,35,90),(178,255,255))
    near=cv2.dilate(np.uint8(base>0),cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(5,5)))>0
    poly=engine.polygon_mask(scene.shape,engine.validated_quad(quad,scene.shape))>0
    add=(relaxed>0)&near&poly&(base==0)
    out=base.copy()
    out[add]=255
    # Only actual original magenta colored pixels can be newly printed.
    # Preserve black slots, neutral inner shadows, side faces, curves & floor.
    engine.mask_check(out,scene,quad)
    return out,{'enabled':True,'added_magenta_edge_pixels':int(np.count_nonzero(add))}


def recommended_edge_feather(scene: np.ndarray,quad)->float:
    """Do not blend pink BACK into printed design along vertical grille lips.

    Non-magenta legacy material continues to use the existing 1.4-px feather.
    This is a RENDER parameter, not a modification of a saved mask.
    """
    return 0.0 if magenta_reference(scene,quad) else 1.4


def magenta_residue_report(scene,quad,mask):
    """Read-only warning: protected pink pixels remain for manual review."""
    engine.mask_check(mask,scene,quad)
    hsv=cv2.cvtColor(scene,cv2.COLOR_BGR2HSV)
    magenta=cv2.inRange(hsv,(125,40,95),(178,255,255))>0
    poly=engine.polygon_mask(scene.shape,engine.validated_quad(quad,scene.shape))>0
    remaining=int(np.count_nonzero(magenta&poly&(mask==0)))
    return {'protected_magenta_pixels':remaining,
            'print_edge_feather_px':recommended_edge_feather(scene,quad),
            'manual_review_if_pink_vents':remaining>0}
