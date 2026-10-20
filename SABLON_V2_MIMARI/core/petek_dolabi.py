"""PETEK DOLABI — full-front print followed by 13 procedural visual recesses.

Source slots are neither counted nor used. Opaque printing covers old marks.
Curved edges require reviewed template-specific midpoint geometry.
No filesystem, database or network side effects.
"""
from __future__ import annotations
from dataclasses import dataclass
import math
import cv2
import numpy as np

CATEGORY = "06_Petek_Dolabi"
SLOT_COUNT = 13
RECIPE = "petek_front_13slots_v1"

class PetekGeometryError(ValueError):
    pass

@dataclass(frozen=True)
class SlotSpec:
    side_margin: float = .085
    top_margin: float = .145
    bottom_margin: float = .125
    slot_width: float = .007
    bottom_curve: float = 0.
    top_sag: float = 0.
    length_variation: float = .012

    def validate(self):
        for field in self.__dataclass_fields__:
            if not math.isfinite(getattr(self, field)):
                raise PetekGeometryError("NONFINITE_SLOT_SETTING")
        if not (.04 <= self.side_margin <= .20 and .07 <= self.top_margin <= .28
                and .07 <= self.bottom_margin <= .28 and .003 <= self.slot_width <= .018
                and 0 <= self.bottom_curve <= .16 and 0 <= self.top_sag <= .12
                and 0 <= self.length_variation <= .03):
            raise PetekGeometryError("INVALID_SLOT_SETTING")
        if 2*self.side_margin + SLOT_COUNT*self.slot_width >= .9:
            raise PetekGeometryError("SLOTS_DO_NOT_FIT")
        if self.top_margin+self.bottom_margin+self.bottom_curve+self.top_sag+2*self.length_variation > .70:
            raise PetekGeometryError("SLOTS_TOO_SHORT")

def normalized_slot_geometry(spec: SlotSpec):
    spec.validate()
    gap = (1-2*spec.side_margin-SLOT_COUNT*spec.slot_width)/(SLOT_COUNT-1)
    if gap <= 0: raise PetekGeometryError("NEGATIVE_SLOT_GAP")
    result = []
    for i in range(SLOT_COUNT):
        u = spec.side_margin + spec.slot_width/2 + i*(spec.slot_width+gap)
        arch = 4*u*(1-u)
        variation = spec.length_variation*(1-abs((i-6)/6))
        top = spec.top_sag*arch+spec.top_margin+variation/2
        bottom = 1-spec.bottom_curve*arch-spec.bottom_margin-variation/2
        if bottom-top < .20: raise PetekGeometryError("COLLAPSED_SLOT")
        result.append((u,top,bottom))
    return result

def _validate_quad(quad, shape):
    pts=np.asarray(quad,dtype=np.float64)
    if pts.shape != (4,2) or not np.isfinite(pts).all():
        raise PetekGeometryError("INVALID_QUAD")
    h,w=shape[:2]
    if np.any(pts<0) or np.any(pts[:,0]>=w) or np.any(pts[:,1]>=h):
        raise PetekGeometryError("QUAD_OUTSIDE_IMAGE")
    if (abs(cv2.contourArea(pts.astype(np.float32)))<.015*h*w
            or not cv2.isContourConvex(pts.astype(np.float32))):
        raise PetekGeometryError("DEGENERATE_QUAD")
    edges=np.roll(pts,-1,axis=0)-pts
    if np.min(np.linalg.norm(edges,axis=1))<30:
        raise PetekGeometryError("QUAD_EDGE_TOO_SHORT")
    if float(edges[0,0]*edges[1,1]-edges[0,1]*edges[1,0])<=0:
        raise PetekGeometryError("EXPECTED_TL_TR_BR_BL")
    return pts.astype(np.float32)

def _make_front(art:np.ndarray,w:int,h:int,spec:SlotSpec):
    if (art is None or art.ndim != 3 or art.shape[2] != 3
            or art.dtype != np.uint8 or min(art.shape[:2])<32):
        raise PetekGeometryError("INVALID_ARTWORK")
    ah,aw=art.shape[:2]
    scale=min(w/aw,h/ah)
    rw,rh=max(1,round(aw*scale)),max(1,round(ah*scale))
    inner=cv2.resize(art,(rw,rh),interpolation=cv2.INTER_AREA if scale<1 else cv2.INTER_CUBIC)
    # Aspect-preserving contain on an opaque, softly extended background.
    paper=cv2.resize(art,(w,h))
    kernel=max(5,int(min(w,h)*.12)//2*2+1)
    paper=cv2.GaussianBlur(paper,(kernel,kernel),0)
    ox,oy=(w-rw)//2,(h-rh)//2
    paper[oy:oy+rh,ox:ox+rw]=inner
    supersample=3
    mask=np.zeros((h*supersample,w*supersample),np.uint8)
    thickness=max(2,round(spec.slot_width*w*supersample))
    radius=max(1,thickness//2)
    for u,v0,v1 in normalized_slot_geometry(spec):
        cx=round(u*(w-1)*supersample)
        a=round(v0*(h-1)*supersample)
        b=round(v1*(h-1)*supersample)
        cv2.line(mask,(cx,a+radius),(cx,b-radius),255,thickness,cv2.LINE_AA)
        cv2.circle(mask,(cx,a+radius),radius,255,-1,cv2.LINE_AA)
        cv2.circle(mask,(cx,b-radius),radius,255,-1,cv2.LINE_AA)
    slots=cv2.resize(mask,(w,h),interpolation=cv2.INTER_AREA).astype(np.float32)/255
    coverage=cv2.GaussianBlur(slots,(0,0),.5)
    yy=np.arange(h,dtype=np.float32)[:,None]
    graphite=np.zeros((h,w,3),np.float32)
    for channel,value in enumerate((53.,56.,61.)):
        graphite[:,:,channel]=value+4*(1-yy/max(1,h))
    front=paper.astype(np.float32)*(1-coverage[:,:,None])+graphite*coverage[:,:,None]
    edge=cv2.GaussianBlur(slots,(0,0),1.7)
    bevel=np.roll(edge,1,axis=1)-np.roll(edge,-1,axis=1)
    front+=bevel[:,:,None]*9
    return np.clip(front,0,255).astype(np.uint8),slots

def _curved_project(front, pts, scene_shape, midpoints):
    """Review-required quadratic top/bottom boundary; inverse image warp."""
    ih,iw=scene_shape[:2]
    w,h=front.shape[1],front.shape[0]
    top=np.asarray(midpoints.get("top"),np.float32)
    bottom=np.asarray(midpoints.get("bottom"),np.float32)
    if top.shape!=(2,) or bottom.shape!=(2,) or not (np.isfinite(top).all() and np.isfinite(bottom).all()):
        raise PetekGeometryError("UNREVIEWED_CURVE")
    dt=top-(pts[0]+pts[1])*.5
    db=bottom-(pts[3]+pts[2])*.5
    if max(np.linalg.norm(dt),np.linalg.norm(db))>.14*w:
        raise PetekGeometryError("CURVE_OUT_OF_RANGE")
    pad=max(np.linalg.norm(dt),np.linalg.norm(db))+4
    x0=max(0,int(np.floor(pts[:,0].min()-pad)))
    y0=max(0,int(np.floor(pts[:,1].min()-pad)))
    x1=min(iw,int(np.ceil(pts[:,0].max()+pad)))
    y1=min(ih,int(np.ceil(pts[:,1].max()+pad)))
    if x1<=x0 or y1<=y0: raise PetekGeometryError("EMPTY_CURVE_REGION")
    Y,X=np.mgrid[y0:y1,x0:x1].astype(np.float32)
    inverse=cv2.getPerspectiveTransform(pts,np.array([[0,0],[1,0],[1,1],[0,1]],np.float32))
    uv=cv2.perspectiveTransform(np.stack((X.ravel(),Y.ravel()),axis=1).reshape(1,-1,2),inverse)
    u=uv[0,:,0].reshape(X.shape).clip(-.3,1.3)
    v=uv[0,:,1].reshape(X.shape).clip(-.3,1.3)
    for _ in range(7):
        arch=4*u*(1-u)
        darch=4-8*u
        t=pts[0]+u[...,None]*(pts[1]-pts[0])+arch[...,None]*dt
        b=pts[3]+u[...,None]*(pts[2]-pts[3])+arch[...,None]*db
        tu=(pts[1]-pts[0])+darch[...,None]*dt
        bu=(pts[2]-pts[3])+darch[...,None]*db
        pred=t+v[...,None]*(b-t)
        p_u=tu+v[...,None]*(bu-tu)
        p_v=b-t
        ex=pred[...,0]-X
        ey=pred[...,1]-Y
        det=p_u[...,0]*p_v[...,1]-p_u[...,1]*p_v[...,0]
        safe=np.where(np.abs(det)<.001,np.where(det<0,-.001,.001),det)
        u=(u-(ex*p_v[...,1]-ey*p_v[...,0])/safe).clip(-.5,1.5)
        v=(v-(p_u[...,0]*ey-p_u[...,1]*ex)/safe).clip(-.5,1.5)
    coverage=np.clip(np.minimum.reduce((u,v,1-u,1-v))*180,0,1).astype(np.float32)
    color=cv2.remap(front,(u*(w-1)).astype(np.float32),(v*(h-1)).astype(np.float32),cv2.INTER_LINEAR)
    return (x0,y0,x1,y1),color,coverage

def render_front(artwork,scene,quad,*,spec=None,edge_midpoints=None,return_debug=False):
    """Full face print, then 13 dark recessed slots. Side/background untouched."""
    if scene is None or scene.ndim!=3 or scene.shape[2]!=3 or scene.dtype!=np.uint8:
        raise PetekGeometryError("INVALID_SCENE")
    spec=spec or SlotSpec()
    spec.validate()
    pts=_validate_quad(quad,scene.shape)
    width=max(256,round((np.linalg.norm(pts[1]-pts[0])+np.linalg.norm(pts[2]-pts[3]))/2))
    height=max(256,round((np.linalg.norm(pts[3]-pts[0])+np.linalg.norm(pts[2]-pts[1]))/2))
    if max(width,height)>4000: raise PetekGeometryError("PANEL_TOO_LARGE")
    front,slots=_make_front(artwork,width,height,spec)
    if edge_midpoints is not None:
        region,projected,alpha=_curved_project(front,pts,scene.shape,edge_midpoints)
        x0,y0,x1,y1=region
        result=scene.copy()
        a=alpha[...,None]
        result[y0:y1,x0:x1]=np.clip(scene[y0:y1,x0:x1].astype(np.float32)*(1-a)+projected*a,0,255).astype(np.uint8)
        surface_mask=np.zeros(scene.shape[:2],np.float32)
        surface_mask[y0:y1,x0:x1]=alpha
    else:
        src=np.array([[0,0],[width-1,0],[width-1,height-1],[0,height-1]],np.float32)
        H=cv2.getPerspectiveTransform(src,pts)
        projected=cv2.warpPerspective(front,H,(scene.shape[1],scene.shape[0]))
        xx=np.arange(width,dtype=np.float32)/max(width-1,1)
        arch=4*xx*(1-xx)
        y=np.arange(height,dtype=np.float32)[:,None]+.5
        mask=((y>=spec.top_sag*arch*height)&(y<(1-spec.bottom_curve*arch)*height)).astype(np.float32)
        surface_mask=cv2.warpPerspective(mask,H,(scene.shape[1],scene.shape[0]),flags=cv2.INTER_LINEAR)
        a=np.clip(surface_mask,0,1)[...,None]
        result=np.clip(scene.astype(np.float32)*(1-a)+projected*a,0,255).astype(np.uint8)
    if return_debug:
        return result,{"slot_count":SLOT_COUNT,"slot_geometry":normalized_slot_geometry(spec),
                       "flat_slot_mask":slots,"projected_surface_mask":surface_mask,"recipe":RECIPE}
    return result
