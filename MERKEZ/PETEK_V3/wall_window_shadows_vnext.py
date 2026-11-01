"""Scene-space daylight continuation: two horizontal bands, print -> wall.

Conservative and non-destructive. Only the returned output can change. A
photographed wall must be identifiable as a coherent, frame-edge-connected,
low-detail region OUTSIDE the cabinet's physical silhouette. Never treat the
cabinet side, room floor, decor, original vents or magenta pixels as wall.
"""
from __future__ import annotations
import cv2
import numpy as np
from .realism import _window_shadow_field, _magenta_pixels


def _border_component(binary, side, min_area):
    """Discard individual pixels / unrelated objects: retain real wall patch."""
    h,w=binary.shape
    filtered=cv2.morphologyEx(binary.astype(np.uint8),cv2.MORPH_OPEN,
                               cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(5,5)))
    filtered=cv2.morphologyEx(filtered,cv2.MORPH_CLOSE,
                               cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(9,9)))
    number, labels, stats, _=cv2.connectedComponentsWithStats(filtered,8)
    result=np.zeros((h,w),bool)
    edge_index=0 if side=='left' else w-1
    for lab in range(1,number):
        if stats[lab,cv2.CC_STAT_AREA]<min_area:continue
        if not np.any(labels[:,edge_index]==lab):continue
        result|=(labels==lab)
    return result


def wall_region(scene:np.ndarray, mask:np.ndarray, quad, *, corner_shadow=False) -> np.ndarray:
    """Only coherent neutral walls at photo's left/right edges.

    The 4-point quad represents the FRONT PRINT, not the cabinet outer box.
    Reserve room for the painted side panel on the left; this is never
    automatically called a wall even when its color resembles plaster.
    """
    h,w=mask.shape
    if scene.shape[:2]!=(h,w) or scene.dtype!=np.uint8:
        raise ValueError('PETEK_WALL_SOURCE_SHAPE_MISMATCH')
    q=np.asarray(quad,np.float32).reshape(4,2)
    x0,x1=float(q[:,0].min()),float(q[:,0].max())
    y0,y1=float(q[:,1].min()),float(q[:,1].max())
    pw,ph=max(1.,x1-x0),max(1.,y1-y0)
    yy,xx=np.ogrid[:h,:w]
    # Do not darken the floor or object props on top of the cabinet.
    ylo=max(0,round(y0-ph*(.48 if corner_shadow else .08)))
    yhi=min(h,round(y1-ph*.13))
    eligible_rows=(yy>=ylo)&(yy<yhi)
    if yhi-ylo<30:return np.zeros((h,w),bool)
    # Keep ~13.5% of front width as a protective buffer for visible side panel.
    left_max=max(0,round(x0-max(13.,pw*.135)))
    right_min=min(w,round(x1+max(9.,pw*.02)))
    out=np.zeros((h,w),bool)
    hsv=cv2.cvtColor(scene,cv2.COLOR_BGR2HSV)
    lab=cv2.cvtColor(scene,cv2.COLOR_BGR2LAB)
    lab_smooth=cv2.GaussianBlur(lab,(13,13),0).astype(np.float32)
    neutral=(hsv[:,:,1]<105)&(hsv[:,:,2]>80)&~_magenta_pixels(scene)&(mask==0)
    gray=cv2.cvtColor(scene,cv2.COLOR_BGR2GRAY)
    gray_smooth=cv2.GaussianBlur(gray,(9,9),0)
    g1=cv2.Sobel(gray_smooth,cv2.CV_32F,1,0,ksize=3)
    g2=cv2.Sobel(gray_smooth,cv2.CV_32F,0,1,ksize=3)
    flat=(np.abs(g1)+np.abs(g2)<64.)
    for side in ('left','right'):
        if side=='left':
            width=left_max
            strip=(xx<width)
            probe=(xx<max(8,width//3))
        else:
            width=w-right_min
            strip=(xx>=right_min)
            probe=(xx>=w-max(8,width//3))
        if width<max(21,round(w*.036)):continue
        samples=probe&eligible_rows&neutral&flat
        if np.count_nonzero(samples)<90:continue
        # In a flat synthetic or blank white/solid-colour canvas we cannot
        # distinguish actual plaster from an object. Require a tiny amount
        # of real photographic luminance variation, not a perfect flat fill.
        if float(np.std(gray[samples].astype(np.float32)))<.38:continue
        # Region-specific photographed plaster reference. Different wall sides
        # can have distinct colors and illumination; avoid generic gray fills.
        ref=np.median(lab_smooth[samples],axis=0)
        distance=np.abs(lab_smooth-ref[None,None,:])
        similar=(distance[:,:,0]<29)&(distance[:,:,1]<13)&(distance[:,:,2]<15)
        region=strip&eligible_rows&neutral&similar&flat
        continuous=_border_component(region,side,min_area=max(100,round(width*(yhi-ylo)*.09)))
        # Stay strictly outside the actual painted cabinet silhouette.
        # Morphological close can reintroduce excluded one-pixel dark features.
        out |= (continuous & region & neutral & flat)
    return out


def choose_corner_side(scene,mask,quad):
    """Prefer the corner beside the largest photographic wall patch.

    Fall back to right when the photo offers no safely detectable wall. This
    selector never edits the source, mask, or panel geometry.
    """
    wall=wall_region(scene,mask,quad,corner_shadow=True)
    xmid=float(np.asarray(quad,np.float32)[:,0].mean())
    left=int(np.count_nonzero(wall[:,:max(0,int(xmid))]))
    right=int(np.count_nonzero(wall[:,max(0,int(xmid)):]))
    return 'left' if left>right else 'right'


def apply_wall_window_shadows(scene,rendered,mask,quad,*,lighting='strong',
                              shadow_style='classic',corner_side='right'):

    """Apply matching two-band light only on confidently classified wall."""
    if lighting!='strong':
        return rendered.copy(),{'status':'OFF','wall_shadow_pixels':0,'shadow_bands':2}
    wall=wall_region(scene,mask,quad,corner_shadow=shadow_style=='corner')
    if not np.any(wall):
        return rendered.copy(),{'status':'WALL_NOT_CONFIDENT','wall_shadow_pixels':0,'shadow_bands':2}
    # Same field and screen coordinates as _diffuse_window_shadows on print.
    illumination=_window_shadow_field(scene.shape,mask,shadow_style=shadow_style,corner_side=corner_side)
    amount=np.clip(illumination*.33,0,.33)
    active=wall&(amount>.005)
    out=rendered.copy()
    out[active]=np.uint8(np.clip(scene[active].astype(np.float32)*(1.-amount[active,None])+.5,0,255))
    count=int(np.count_nonzero(np.any(out!=rendered,axis=2)&active))
    return out,{'status':'APPLIED' if count else 'NO_SHADOW_INTERSECTION',
                'wall_shadow_pixels':count,'shadow_bands':2,
                'source_pixels_untouched':True}
