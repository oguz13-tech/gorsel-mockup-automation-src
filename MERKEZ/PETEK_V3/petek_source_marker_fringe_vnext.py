"""PETEK source magenta marker removal at approved print boundaries.

Never edits source or approved mask; repairs only high-confidence chroma-key
pixels outside approved print, within a narrow 12-pixel edge/vent-lip band.
No structural black pixel, photographed cabinet, floor or other color can move.
"""
from __future__ import annotations
import cv2
import numpy as np
from . import engine

MAX_FRINGE_WIDTH_PX = 14


def _source_marker(scene: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    hsv=cv2.cvtColor(scene,cv2.COLOR_BGR2HSV)
    b,g,r=(scene[:,:,i].astype(np.int16) for i in range(3))
    strict=((hsv[:,:,0]>=124)&(hsv[:,:,0]<=178)&
            (hsv[:,:,1]>=72)&(hsv[:,:,2]>=75)&
            (b>g+15)&(r>g+16))
    loose=((hsv[:,:,0]>=121)&(hsv[:,:,0]<=179)&
           (hsv[:,:,1]>=24)&(hsv[:,:,2]>=67)&
           (b>g+5)&(r>g+7))
    return strict,loose


def marker_fringe_candidates(scene: np.ndarray, mask: np.ndarray, quad) -> np.ndarray:
    """Read-only geometric photo-marker evidence, never guess physical holes."""
    engine.mask_check(mask,scene,quad)
    strict,loose=_source_marker(scene)
    grown=cv2.dilate(strict.astype(np.uint8),
                     cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(9,9)))>0
    marker = strict | (loose & grown)
    # Buffer outside the precise original print only. Include source-magenta
    # thin lips beside actual holes, corners, top and bottom curves.
    near=cv2.dilate(np.uint8(mask>0),cv2.getStructuringElement(
         cv2.MORPH_ELLIPSE,(2*MAX_FRINGE_WIDTH_PX+1,)*2))>0
    panel=engine.polygon_mask(scene.shape,engine.validated_quad(quad,scene.shape))
    physical=cv2.dilate(np.uint8(panel>0),cv2.getStructuringElement(
         cv2.MORPH_ELLIPSE,(2*MAX_FRINGE_WIDTH_PX+1,)*2))>0
    # A source-protected vent is an enclosed zero island inside the printable
    # face. It is not an outside fringe and must never be treated as a repair
    # target merely because the RAM mask protects its full measured width.
    zero=(mask==0).astype(np.uint8)
    nlabels,labels=cv2.connectedComponents(zero, connectivity=8)
    border_labels=np.unique(np.concatenate((
        labels[0,:], labels[-1,:], labels[:,0], labels[:,-1])))
    exterior=np.isin(labels,border_labels[border_labels!=0])
    candidate=exterior&near&physical&marker
    # If source marker occupies an unusually broad area, fail closed: it may
    # indicate a bad human mask instead of an anti-aliased 1..8 px fringe.
    n=int(np.count_nonzero(candidate))
    if n>max(9000,int(np.count_nonzero(mask>0)*.065)):
        raise engine.MaskError('PETEK_GENIS_MAGENTA_SACAK_MASK_INCELE')
    return candidate


def restore_source_marker_fringe(scene, printed, mask, quad, *, enabled):
    """Photoshop-style narrow inpaint from nonmarker neighbors, on a COPY."""
    if scene.shape!=printed.shape or scene.dtype!=printed.dtype or scene.dtype!=np.uint8:
        raise engine.MaskError('PETEK_FRINGE_SOURCE_SHAPE_MISMATCH')
    if not enabled:return printed.copy(), {'status':'KAPALI','repaired_pixels':0}
    candidate=marker_fringe_candidates(scene,mask,quad)
    strict,loose=_source_marker(printed)
    # Repaired earlier in pipeline? Leave it alone. Only real residual marker
    # that survived rendering may be touched. Legitimate pink printed design
    # lies *inside* the original mask and is never a target.
    target=candidate&(strict|loose)
    count=int(np.count_nonzero(target))
    if not count:return printed.copy(),{'status':'TEMIZ','repaired_pixels':0,'marker_pixels_detected':int(candidate.sum())}
    # Surrounding context contains both the photographed side and printed
    # panel; the entire target region is excluded from donor pixels.
    inpainted=cv2.inpaint(printed,(target.astype(np.uint8)*255),4.,cv2.INPAINT_TELEA)
    out=printed.copy()
    out[target]=inpainted[target]
    # Only strictly identified magenta SOURCE markers, outside the print.
    if np.any(out[~target]!=printed[~target]):
        raise engine.MaskError('PETEK_FRINGE_REPAIR_OUTSIDE_CANDIDATE')
    return out, {'status':'DAR_SACAK_ONARILDI','repaired_pixels':count,
                 'marker_pixels_detected':int(candidate.sum()),
                 'protected_black_pictures_unchanged':True,'render_only':True}
