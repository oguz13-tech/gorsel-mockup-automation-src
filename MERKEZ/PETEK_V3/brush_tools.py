"""Solid full-resolution brush stamps with polygon safety and continuous strokes.

No source photograph modifications. The editor owns mask undo snapshots.
"""
from __future__ import annotations
import cv2
import numpy as np

def brush_radius_screen(diameter_source_px:int,zoom:float)->float:
    return max(1.0,float(diameter_source_px)*float(zoom)/2.0)

def apply_stroke(mask:np.ndarray, allowed:np.ndarray, position:tuple[int,int],
                 diameter_px:int, value:int, *, previous:tuple[int,int]|None=None)->int:
    """Apply connected full-opacity capsule inside the authorized quad.

    A brush dab or line is clipped by the polygon independently of path endpoints.
    Only mask pixels inside allowed can change; preserved holes must be
    protected by the caller's separate source/wood candidate constraints.
    """
    if mask.dtype!=np.uint8 or mask.ndim!=2 or allowed.shape!=mask.shape:
        raise ValueError('Mask format must be a full-resolution uint8 plane')
    if diameter_px<1 or diameter_px>500 or value not in (0,255):
        raise ValueError('Invalid brush size or coverage')
    x,y=map(int,position)
    h,w=mask.shape
    if not (0<=x<w and 0<=y<h) or allowed[y,x]==0:
        return 0
    r=max(1,int(round(diameter_px/2)))
    tmp=np.zeros_like(mask)
    if previous is not None:
        px,py=map(int,previous)
        if 0<=px<w and 0<=py<h and allowed[py,px]!=0:
            cv2.line(tmp,(px,py),(x,y),255,thickness=2*r+1,lineType=cv2.LINE_8)
    cv2.circle(tmp,(x,y),r,255,-1,lineType=cv2.LINE_8)
    modify=(tmp>0)&(allowed>0)
    changed=int(np.count_nonzero(modify & (mask != value)))
    mask[modify]=value
    return changed
