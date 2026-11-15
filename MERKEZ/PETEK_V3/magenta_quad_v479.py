"""Magenta (#FF00FF) PETEK front-panel four-corner DRAFT detector.

Only computes a proposal in photo pixel coordinates. No changes to source,
approved mask registry, template DB or production. Black ventilation slots
and curved top/bottom voids must still be reviewed in PETEK mask editor.
"""
from __future__ import annotations
import cv2
import numpy as np
from . import engine


def detect_magenta_quad(scene):
    if not isinstance(scene,np.ndarray) or scene.dtype!=np.uint8 or scene.ndim!=3 or scene.shape[2]!=3:
        raise engine.MaskError('PETEK_MAGENTA_INVALID_IMAGE')
    h,w=scene.shape[:2]
    scale=min(1.0,1400/max(h,w))
    working=cv2.resize(scene,(max(1,round(w*scale)),max(1,round(h*scale))),
                       interpolation=cv2.INTER_AREA) if scale<1 else scene
    sh,sw=working.shape[:2]
    hsv=cv2.cvtColor(working,cv2.COLOR_BGR2HSV)
    # High-saturation pink-magenta, tolerant of natural lighting/shadows.
    # Avoid near-white reflections, unrelated red décor and black vent gaps.
    raw=cv2.inRange(hsv,(130,67,90),(177,255,255))
    k=max(5,min(71,round(sw*.04)|1))
    closed=cv2.morphologyEx(raw,cv2.MORPH_CLOSE,
             cv2.getStructuringElement(cv2.MORPH_RECT,(k,7)))
    contours,_=cv2.findContours(closed,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    contours=sorted(contours,key=cv2.contourArea,reverse=True)
    if not contours:
        raise engine.MaskError('PETEK_MAGENTA_YUZEY_BULUNAMADI')
    target=contours[0]
    area=cv2.contourArea(target)
    if area<sh*sw*.012:
        raise engine.MaskError('PETEK_MAGENTA_ALAN_COK_KUCUK')
    if len(contours)>1 and cv2.contourArea(contours[1])>area*.36:
        raise engine.MaskError('PETEK_MAGENTA_BIRDEN_COK_ADAY')
    x,y,bw,bh=cv2.boundingRect(target)
    if bw<sw*.12 or bh<sh*.12 or bw*bh>sw*sh*.82:
        raise engine.MaskError('PETEK_MAGENTA_GEOMETRI_SUPHELI')
    if np.count_nonzero(raw[y:y+bh,x:x+bw])<bw*bh*.21:
        raise engine.MaskError('PETEK_MAGENTA_YOGUNLUGU_YETERSIZ')
    hull=cv2.convexHull(target)
    perimeter=cv2.arcLength(hull,True)
    proposal=None
    method='HULL_4'
    for eps in (.014,.020,.028,.037,.05,.065):
        candidate=cv2.approxPolyDP(hull,perimeter*eps,True).reshape(-1,2)
        if len(candidate)==4 and cv2.isContourConvex(candidate.astype(np.float32)):
            proposal=candidate.astype(float)
            break
    if proposal is None:
        proposal=cv2.boxPoints(cv2.minAreaRect(hull)).astype(float)
        method='MIN_AREA_RECT_REVIEW'
    # Angular sorting in image coordinates is clockwise; begin at top-left.
    center=proposal.mean(axis=0)
    order=np.argsort(np.arctan2(proposal[:,1]-center[1],proposal[:,0]-center[0]))
    proposal=proposal[order]
    proposal=np.roll(proposal,-int(np.argmin(proposal.sum(axis=1))),axis=0)
    proposal[:,0]=np.clip(proposal[:,0]/scale,0,w-1)
    proposal[:,1]=np.clip(proposal[:,1]/scale,0,h-1)
    q=engine.validated_quad(proposal,scene.shape)
    cover=area/max(1.0,cv2.contourArea(q.astype(np.float32))*scale*scale)
    if cover<.27:
        raise engine.MaskError('PETEK_MAGENTA_KOSE_GUVENI_YETERSIZ')
    return {'quad':np.round(q.astype(np.float64),2).tolist(),
            'method':method,
            'coverage':round(float(min(1.0,cover)),3),
            'draft_only':True,
            'warning':'Dört köşeyi gözle kontrol et. Delikler ve üst-alt kavisler otomatik onaylanmaz.'}
