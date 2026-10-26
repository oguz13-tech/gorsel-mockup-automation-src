"""Restore legacy architectural/spot glass reflections and matte daylight.

Derived from historical MockupRenderer window_reflection/kitchen_sheen algorithms,
but applied exclusively inside the actual approved print mask.  Never edits
quads, metadata, sources, PETEK vents/holes or background. Deterministic.
"""
from __future__ import annotations
import cv2
import numpy as np

GLASS = frozenset(('02_Cam_Tablo_Dikey','02_Cam_Tablo_Yatay',
                   '04_Cam_Dograma','05_Ocak_Arkasi'))
DAYLIGHT = frozenset(('03_Ahsap_Tablo','06_Petek_Kapama'))
RECIPE = 'material-optics-window-mullion-daylight-v47-20261027'


def _local_layers(category, width=400, height=400):
    y,x = np.mgrid[0:height,0:width].astype(np.float32)
    u=x/max(width-1,1);v=y/max(height-1,1)
    bright=np.zeros((height,width),np.float32)
    dark=np.zeros_like(bright)
    if category in ('02_Cam_Tablo_Dikey','02_Cam_Tablo_Yatay'):
        # Recovered 2x2/3x2 historic architectural window: pane reflections
        # visibly separated by dark mullions even on already-white designs.
        cx,cy=.72,.32
        theta=np.radians(-6.0)
        xr=(u-cx)*np.cos(theta)-(v-cy)*np.sin(theta)
        yr=(u-cx)*np.sin(theta)+(v-cy)*np.cos(theta)
        envelope=np.clip(1-(np.abs(xr)/.375)**2.5,0,1)*np.clip(1-(np.abs(yr)/.325)**2.5,0,1)
        envelope=cv2.GaussianBlur(envelope,(0,0),3)
        # Keep bars aligned to projected window, not screen axes.
        bar_v=np.exp(-.5*(xr/.014)**2)
        bar_h=np.exp(-.5*(yr/.015)**2)
        bar_h2=np.exp(-.5*((yr-.12)/.014)**2)
        bars=np.clip(bar_v+bar_h+bar_h2,0,1)
        bright=np.clip(envelope*(1-.85*bars)*.78,0,1)
        dark=np.clip(envelope*bars*.80,0,1)
    elif category=='04_Cam_Dograma':
        # Countertop and overhead spot + narrow glossy streak.
        bright=np.exp(-1.8*(((u-.50)/.45)**2+((v-.34)/.27)**2))
        bright+=.4*np.exp(-.5*(((u-.73)/.27)**2+((v-.19)/.035)**2))
        bright=np.clip(bright*.75,0,1)
    elif category=='05_Ocak_Arkasi':
        # Ambient kitchen window/under-cabinet light.
        bright=.80*np.exp(-1.4*(((u-.62)/.40)**2+((v-.20)/.22)**2))
        bright+=.45*np.exp(-1.8*(((u-.20)/.20)**2+((v-.72)/.35)**2))
        dark=.25*np.exp(-2*((u-.43)/.05)**2)*np.exp(-.8*((v-.33)/.40)**2)
        bright=np.clip(bright,0,1)
    elif category in DAYLIGHT:
        # User reference: broad diagonal *matte* shafts of window daylight;
        # no hard glass bars, no shiny specular white band.
        slanted = u + .60*v
        for c,amp,width_band in ((.23,.85,.10),(.55,.75,.13),(.88,.65,.11)):
            bright+=amp*np.exp(-.5*((slanted-c)/width_band)**2)
        for c in (.37,.73):
            dark+=.40*np.exp(-.5*((slanted-c)/.085)**2)
        bright=np.clip(cv2.GaussianBlur(bright,(0,0),6)*.72,0,1)
        dark=np.clip(cv2.GaussianBlur(dark,(0,0),7)*.43,0,1)
    return bright,dark


def apply_material_finish(scene, printed, mask, quad, category, *, enabled=True):
    """Return full-size BGR image, preserving all pixels where mask==0 byte-exact."""
    if not enabled or category not in GLASS|DAYLIGHT:
        return printed
    if (printed.dtype!=np.uint8 or scene.shape!=printed.shape
            or mask.shape!=printed.shape[:2] or len(quad)!=4):
        raise ValueError('MATERIAL_FINISH_INVALID_GEOMETRY')
    if not np.any(mask>0):
        raise ValueError('MATERIAL_FINISH_EMPTY_MASK')
    H,W=mask.shape
    sw=sh=400
    light,shade=_local_layers(category,sw,sh)
    transform=cv2.getPerspectiveTransform(
        np.float32([[0,0],[sw-1,0],[sw-1,sh-1],[0,sh-1]]),
        np.asarray(quad,dtype=np.float32),
    )
    def warp(layer):
        return cv2.warpPerspective(layer,transform,(W,H),flags=cv2.INTER_LINEAR,
                                   borderMode=cv2.BORDER_CONSTANT,borderValue=0)
    glow,shadow=warp(light),warp(shade)
    # Artwork edge/detail protection derived from legacy Sobel-based attenuation.
    gray=cv2.cvtColor(printed,cv2.COLOR_BGR2GRAY).astype(np.float32)
    gx=cv2.Sobel(gray,cv2.CV_32F,1,0,ksize=3)
    gy=cv2.Sobel(gray,cv2.CV_32F,0,1,ksize=3)
    magnitude=cv2.magnitude(gx,gy)
    positive=magnitude[(mask>0)&(magnitude>1)]
    reference=max(float(np.percentile(positive,82)) if positive.size else 1.,1.)
    detail=cv2.GaussianBlur(np.clip(magnitude/reference,0,1),(0,0),1.5)
    protect=1.0-.66*detail
    base=printed.astype(np.float32)
    if category in GLASS:
        # Screen-style illumination and dark mullions on white panels.
        inc=(glow*protect*.26)[:,:,None]*(255.-base)
        dec=(shadow*protect*.28)[:,:,None]*base
    else:
        # Diffuse warm daylight and gentle matte shadow; low contrast.
        inc=(glow*protect*.13)[:,:,None]*(np.float32([250,249,245])-base)
        dec=(shadow*protect*.09)[:,:,None]*base
    effect=np.uint8(np.clip(base+inc-dec+.5,0,255))
    out=printed.copy()
    out[mask>0]=effect[mask>0]
    return out
