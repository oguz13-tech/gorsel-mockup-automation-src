"""PETEK painted-front edge photometry; never composite original chroma-key pixels.

Render-only: harmonizes the printable face with real side-panel white and
adds very light silhouette contact shading. Does not change the source,
mask, physical vents, curves, pink cleanup, or slot geometry.
"""
from __future__ import annotations
import cv2
import numpy as np


def harmonize_petek_edges(scene: np.ndarray, printed: np.ndarray,
                          mask: np.ndarray, quad) -> np.ndarray:
    if (scene.shape != printed.shape or scene.shape[:2] != mask.shape or
            scene.dtype != np.uint8 or printed.dtype != np.uint8 or
            mask.dtype != np.uint8):
        raise ValueError('PETEK_EDGE_HARMONY_SHAPE_INVALID')
    q=np.asarray(quad,np.float32)
    if q.shape!=(4,2) or not np.isfinite(q).all():
        raise ValueError('PETEK_EDGE_HARMONY_QUAD_INVALID')
    active=mask>0
    if int(np.count_nonzero(active))<200:return printed.copy()
    result=printed.copy()
    h,w=mask.shape
    hsv=cv2.cvtColor(scene,cv2.COLOR_BGR2HSV)
    # Original magenta can never donate color for white furniture matching.
    neutral=(~active)&(hsv[:,:,1]<=42)&(hsv[:,:,2]>=130)&(hsv[:,:,2]<=252)
    face_width=float(max(np.linalg.norm(q[1]-q[0]),np.linalg.norm(q[2]-q[3]),1))
    face_height=float(max(np.linalg.norm(q[3]-q[0]),np.linalg.norm(q[2]-q[1]),1))
    from_top=float(q[0,1]);to_bottom=float(q[3,1]);den=to_bottom-from_top
    if abs(den)>8:
        y0=max(0,int(np.floor(min(from_top,to_bottom))))
        y1=min(h-1,int(np.ceil(max(from_top,to_bottom))))
        sampled=np.zeros((h,3),np.float32)
        valid=np.zeros(h,bool)
        for y in range(y0,y1+1):
            t=(y-from_top)/den
            if t<-.02 or t>1.02:continue
            xleft=float(q[0,0]+t*(q[3,0]-q[0,0]))
            # Only the photographed *left cabinet side*, not wall/floor.
            xa=max(0,int(round(xleft-31)))
            xb=min(w,int(round(xleft-3)))
            if xb-xa<6:continue
            choice=neutral[y,xa:xb]
            if np.count_nonzero(choice)<5:continue
            sampled[y]=np.median(scene[y,xa:xb][choice],axis=0)
            valid[y]=True
        # If the photographed side is missing, do not invent a white sample.
        if np.count_nonzero(valid)>=max(16,int((y1-y0+1)*.12)):
            ys=np.arange(h,dtype=np.float32)
            ref=np.stack([np.interp(ys,np.flatnonzero(valid),sampled[valid,c])
                          for c in range(3)],axis=1).astype(np.float32)
            # Smooth the reference illumination vertically, preserving broad
            # window lighting while rejecting individual bright/dark pixels.
            ref=cv2.GaussianBlur(ref.reshape(h,1,3),(1,0),sigmaX=0,sigmaY=13).reshape(h,3)
            bx0=max(0,int(np.floor(np.min(q[:,0])))-5)
            bx1=min(w,int(np.ceil(np.max(q[:,0])))+6)
            yy=np.arange(y0,y1+1,dtype=np.float32)[:,None]
            xx=np.arange(bx0,bx1,dtype=np.float32)[None,:]
            seam=(q[0,0]+((yy-from_top)/den)*(q[3,0]-q[0,0]))
            span=max(12.,min(42.,face_width*.070))
            t=np.clip((xx-seam)/span,0,1)
            # Cubic smoothstep. All transition occurs INSIDE printable face.
            ramp=1.-(t*t*(3.-2.*t))
            ramp=np.where(xx>=seam-.75,ramp,0.)
            roi=(slice(y0,y1+1),slice(bx0,bx1))
            current=result[roi].astype(np.float32)
            lum=current.mean(axis=2)
            chroma=current.max(axis=2)-current.min(axis=2)
            # Only light neutral print paint; coloured artwork and black ink
            # must not acquire a false pale/white seam.
            white=np.clip((lum-152.)/53.,0,1)*np.clip((40.-chroma)/30.,0,1)
            amount=(.83*ramp*white*active[roi]).astype(np.float32)
            source_ref=ref[y0:y1+1,None,:]
            # Bound corrections: scene-matching, never a flat painted stripe.
            desired=np.clip(source_ref,current-25.,current+25.)
            current=current*(1.-amount[:,:,None])+desired*amount[:,:,None]
            result[roi]=np.uint8(np.clip(current+.5,0,255))
    # Soft physical front-panel contact, not a blurred alpha boundary:
    # estimate EXTERNAL silhouette, excluding internal slotted vents.
    # Max 2% darkening within the first 7 px of the panel contour.
    mask_binary=active.astype(np.uint8)
    contours,_=cv2.findContours(mask_binary,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    if contours:
        largest=max(contours,key=cv2.contourArea)
        silhouette=np.zeros_like(mask_binary)
        cv2.drawContours(silhouette,[largest],-1,1,thickness=cv2.FILLED)
        dist=cv2.distanceTransform(silhouette,cv2.DIST_L2,3)
        edge=(active & (dist<=14))
        if np.any(edge):
            p=result[edge].astype(np.float32)
            lum=p.mean(axis=1);chroma=p.max(axis=1)-p.min(axis=1)
            pale=np.clip((lum-155.)/50.,0,1)*np.clip((40.-chroma)/30.,0,1)
            shade=(.018*np.exp(-np.maximum(dist[edge]-1.,0.)/4.5)*pale)
            result[edge]=np.uint8(np.clip(p*(1.-shade[:,None])+.5,0,255))
    # Non-printable source pixels are immutable even if an unexpected
    # numerical condition occurs in a shadow or colour transfer stage.
    result[~active]=printed[~active]
    return result
