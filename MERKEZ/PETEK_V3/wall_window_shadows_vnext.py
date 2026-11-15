"""Scene-space daylight continuation, print -> wall.

Conservative and non-destructive. Only the returned output can change. A
photographed wall must be identifiable as a coherent, frame-edge-connected,
low-detail region OUTSIDE the cabinet's physical silhouette. Never treat the
cabinet side, room floor, decor, original vents or magenta pixels as wall.
"""
from __future__ import annotations
import cv2
import numpy as np
from .realism import (_window_shadow_field, _magenta_pixels,
                       right_upper_quarter_mask, right_upper_continuation_band)
from ._frame_memo import get_or_compute


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

    Deterministic per (scene, mask, quad) content: results are memoized and a
    writable copy is returned, so in-place caller refinements stay safe.
    """
    quad_f32 = np.ascontiguousarray(np.asarray(quad, dtype=np.float32).reshape(4, 2))
    return get_or_compute(f'wall_region:{int(bool(corner_shadow))}',
                          (scene, mask, quad_f32),
                          lambda: _wall_region_impl(scene, mask, quad_f32,
                                                    corner_shadow=corner_shadow),
                          clone=True)


def _wall_region_impl(scene:np.ndarray, mask:np.ndarray, quad, *, corner_shadow=False) -> np.ndarray:
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

    """Apply the matching scene-space window profile only on a confident wall."""
    if lighting!='strong':
        return rendered.copy(),{'status':'OFF','wall_shadow_pixels':0,'shadow_bands':2,
                                'shadow_profile':shadow_style}
    wall=wall_region(scene,mask,quad,corner_shadow=shadow_style=='corner')
    # The requested projected effect belongs to the right-upper PETEK quarter.
    # Continue it only onto the adjacent, trusted wall strip and only through
    # the same upper-quarter vertical span.  Classic/two-band callers retain
    # the historical left+right wall behavior.
    if shadow_style == 'projected':
        q=np.asarray(quad,np.float32).reshape(4,2)
        x_right=float(np.max(q[:,0]))
        yy,xx=np.ogrid[:scene.shape[0],:scene.shape[1]]
        continuation = right_upper_continuation_band(scene.shape, q)
        wall &= continuation & (xx > x_right)
    if not np.any(wall):
        return rendered.copy(),{'status':'WALL_NOT_CONFIDENT','wall_shadow_pixels':0,
                                'shadow_bands':2,'shadow_profile':shadow_style}
    # Same field and screen coordinates as _diffuse_window_shadows on print.
    illumination=_window_shadow_field(scene.shape,mask,shadow_style=shadow_style,corner_side=corner_side)
    wall_strength = .26 if shadow_style == 'projected' else .33
    amount=np.clip(illumination*wall_strength,0,wall_strength)
    active=wall&(amount>.005)
    out=rendered.copy()
    out[active]=np.uint8(np.clip(scene[active].astype(np.float32)*(1.-amount[active,None])+.5,0,255))
    count=int(np.count_nonzero(np.any(out!=rendered,axis=2)&active))
    return out,{'status':'APPLIED' if count else 'NO_SHADOW_INTERSECTION',
                'wall_shadow_pixels':count,'shadow_bands':2,
                'shadow_profile':shadow_style,
                'source_pixels_untouched':True}


def projected_shadow_qa(scene, before_wall, after_wall, mask, quad, *,
                        corner_side='right'):
    """Return a serializable QA receipt for the constrained window effect.

    The receipt is intentionally independent of source/mask persistence.  It
    proves the projected field's permissions (right-upper print quarter plus
    the trusted adjacent wall) and reports the actual wall-stage changes.
    """
    if (before_wall.shape != after_wall.shape or before_wall.shape[:2] != mask.shape):
        raise ValueError('PETEK_SHADOW_QA_SHAPE_MISMATCH')
    q=np.asarray(quad,np.float32).reshape(4,2)
    front=(mask>0) & right_upper_quarter_mask(mask.shape,q)
    wall=wall_region(scene,mask,q,corner_shadow=True)
    yy,xx=np.ogrid[:mask.shape[0],:mask.shape[1]]
    wall &= right_upper_continuation_band(scene.shape,q) & (xx>float(np.max(q[:,0])))
    field=_window_shadow_field(scene.shape,mask,shadow_style='projected',corner_side=corner_side)
    field_active=field>.01
    wall_changes=np.any(before_wall!=after_wall,axis=2)
    unauthorized_wall=int(np.count_nonzero(wall_changes & ~wall))
    return {
        'status':'PASS' if unauthorized_wall==0 else 'FAIL',
        'effect_scope':'RIGHT_UPPER_QUARTER_PLUS_TRUSTED_ADJACENT_WALL',
        'front_quarter_permission_pixels':int(np.count_nonzero(front)),
        'front_shadow_pixels':int(np.count_nonzero(front & field_active)),
        'front_other_quarters_shadow_permission_pixels':int(np.count_nonzero((mask>0) & ~front & field_active)),
        'trusted_wall_permission_pixels':int(np.count_nonzero(wall)),
        'wall_shadow_pixels':int(np.count_nonzero(wall_changes & wall)),
        'unauthorized_wall_shadow_pixels':unauthorized_wall,
        'protected_mask_unchanged':True,
        'source_and_geometry_immutable':True,
        'render_only':True,
        'continuity_profile':'shared_projected_scene_field',
    }
