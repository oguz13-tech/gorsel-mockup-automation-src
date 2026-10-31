"""Optional *non-destructive* PETEK finishing for previewed print jobs.

Only source photograph copies are used. Approved mask, stored geometry, and
original disk assets are never modified. Default modes OFF. A low-confidence
slot estimate produces no strokes instead of fabricating geometry.
"""
from __future__ import annotations
import cv2
import numpy as np
from . import engine

STRENGTH = {'off':0.0, 'hafif':0.34, 'orta':0.60, 'guclu':0.78}
RECIPE = 'petek-finishing-v492-conservative-1'


def _validate(source, printed, mask, quad):
    engine.mask_check(mask, source, quad)
    if printed.shape != source.shape or printed.dtype != np.uint8:
        raise engine.MaskError('PETEK bitis katmani sekli gecersiz.')
    return engine.validated_quad(quad, source.shape)


def estimate_slots(source, mask, quad):
    """Find long, narrow DARK source openings from mask AND scene evidence.

    The operator-approved holes are the preferred signal. A full-row/arch
    connected component can never be counted as a narrow ventilation slot.
    """
    q=engine.validated_quad(quad, source.shape)
    core=engine.polygon_mask(source.shape,q)
    core=cv2.erode(core, np.ones((3,3),np.uint8))
    gray=cv2.cvtColor(source,cv2.COLOR_BGR2GRAY)
    panel_h=max(1.0,float(q[:,1].max()-q[:,1].min()))
    panel_w=max(1.0,float(q[:,0].max()-q[:,0].min()))
    # Dark, protected components; never infer slots from a printed artwork.
    dark=(gray < 125)
    candidate=np.uint8((mask==0)&(core>0)&dark)
    n,_,stats,_=cv2.connectedComponentsWithStats(candidate,8)
    slots=[]
    for idx in range(1,n):
        x,y,w,h,area=map(int,stats[idx])
        if (h >= panel_h*.16 and 1 <= w <= panel_w*.052 and
            8 <= area <= max(20,panel_w*panel_h*.016) and
            h/w >= 2.4):
            slots.append((x,y,w,h))
    # Over-segmented real openings are a warning, not permission to draw.
    slots=sorted(slots,key=lambda b:b[0]+b[2]/2)
    if not (10 <= len(slots) <= 16):
        return [], {'status':'ATLANDI_GUVEN_YETERSIZ', 'count':len(slots)}
    centers=np.array([x+w/2 for x,_,w,_ in slots],float)
    distances=np.diff(centers)
    if len(distances)<8 or np.median(distances)<2 or np.std(distances)/max(1,np.mean(distances))>.55:
        return [], {'status':'ATLANDI_DUZENSIZ_IZGARALAR', 'count':len(slots)}
    return slots, {'status':'TAHMIN_HAZIR', 'count':len(slots)}


def darken_slot_lips(source, rendered, mask, quad, *, mode='off'):
    """Darken only *PRINTABLE* fringe pixels adjacent to evidenced openings.

    Protected 0-mask slot interiors and every pixel outside the print mask stay
    byte-identical. The user chooses strength; no black straight lines are
    synthesized across an unrecognized scene.
    """
    _validate(source,rendered,mask,quad)
    if mode not in STRENGTH:
        raise ValueError('Gecersiz PETEK izgara yogunlugu.')
    out=rendered.copy()
    if mode=='off':return out, {'status':'KAPALI','changed_pixels':0,'count':0}
    slots, info=estimate_slots(source,mask,quad)
    if not slots:return out,dict(info, changed_pixels=0)
    h,w=mask.shape
    region=np.zeros((h,w),np.uint8)
    core=engine.polygon_mask(source.shape,engine.validated_quad(quad,source.shape))>0
    for x,y,bw,bh in slots:
        pad=max(1,min(3,int(round(bw*.20))))
        cv2.rectangle(region,(max(0,x-pad),max(0,y)),
            (min(w-1,x+bw+pad-1),min(h-1,y+bh-1)),255,-1)
    # Target only APPROVED printable pixels near source dark slot geometry.
    hsv=cv2.cvtColor(source,cv2.COLOR_BGR2HSV)
    dark=hsv[:,:,2]<155
    magenta=(hsv[:,:,0]>=130)&(hsv[:,:,0]<=176)&(hsv[:,:,1]>=110)&(hsv[:,:,2]>120)
    affected=(region>0)&(mask>0)&core&(dark|magenta)
    if not np.any(affected):return out,dict(info, changed_pixels=0, status='BOS_DEGISIKLIK')
    protected=(region>0)&(mask==0)&dark
    target=np.percentile(source[protected],42,axis=0) if np.any(protected) else np.array((34,34,34))
    # Neutral shadow, derived from actual hole pixels, not arbitrary pure black.
    target=np.minimum(np.asarray(target,float),[85,85,85])
    strength=STRENGTH[mode]
    new=np.clip(out[affected].astype(float)*(1-strength)+target[None,:]*strength+.5,0,255).astype(np.uint8)
    out[affected]=new
    if not np.array_equal(out[mask==0],rendered[mask==0]):
        raise engine.MaskError('PETEK ızgara guvenlik ihlali: korunan sahne degisti')
    return out,dict(info,changed_pixels=int(np.count_nonzero(affected)),strength=mode,status='UYGULANDI')


def despill_lower_left(source, mask, quad, *, enabled=False):
    """Conservative lower-left source-marker repair in RAM; never write source.

    Only a tiny, saturated magenta remnant on the lower-left approved-panel
    boundary is a candidate. No magenta artwork or unknown pastel is erased.
    """
    engine.mask_check(mask,source,quad)
    if not enabled:return source,{'status':'KAPALI','repaired_pixels':0}
    q=engine.validated_quad(quad,source.shape)
    poly=engine.polygon_mask(source.shape,q)>0
    panel_w=max(1.,float(np.max(q[:,0])-np.min(q[:,0])))
    panel_h=max(1.,float(np.max(q[:,1])-np.min(q[:,1])))
    # Require visible reference marker within panel; normal artwork/photo skipped.
    hsv=cv2.cvtColor(source,cv2.COLOR_BGR2HSV)
    strong=(hsv[:,:,0]>=135)&(hsv[:,:,0]<=173)&(hsv[:,:,1]>=155)&(hsv[:,:,2]>=155)
    if np.count_nonzero(strong & poly)<int(np.count_nonzero(poly)*.06):
        return source,{'status':'ATLANDI_MAGENTA_KAYNAK_DEGIL','repaired_pixels':0}
    edge=cv2.dilate(np.uint8(mask>0),cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(13,13)))>0
    yy,xx=np.indices(mask.shape)
    x_left=min(float(q[0,0]),float(q[3,0]))
    y_bottom=max(float(q[2,1]),float(q[3,1]))
    region=(xx>=x_left-max(5,panel_w*.05))&(xx<=x_left+panel_w*.27)&\
           (yy>=y_bottom-panel_h*.17)&(yy<=y_bottom+max(5,panel_h*.05))
    candidate=strong&region&edge&(mask==0)
    pixels=int(np.count_nonzero(candidate))
    cap=min(220,max(10,int(np.count_nonzero(poly)*.0012)))
    if pixels==0:return source,{'status':'TEMIZ','repaired_pixels':0}
    if pixels>cap:
        return source,{'status':'ATLANDI_COK_GENIS_KACAK','repaired_pixels':0,'detected_pixels':pixels}
    # Ordinary inpainting would sample the huge adjacent MAGENTA print face
    # and re-introduce pink. Instead borrow only nearby *original, neutral*
    # protected pixels outside the paint mask. If none are close, fail closed.
    out=source.copy()
    successes=0
    for y,x in zip(*np.where(candidate)):
        y0,y1=max(0,int(y)-14),min(source.shape[0],int(y)+15)
        x0,x1=max(0,int(x)-14),min(source.shape[1],int(x)+15)
        patch=source[y0:y1,x0:x1]
        neutral=(mask[y0:y1,x0:x1]==0)&(~strong[y0:y1,x0:x1])
        ys,xs=np.where(neutral)
        if len(ys)<4:
            continue
        distances=(ys+y0-int(y))**2+(xs+x0-int(x))**2
        idx=np.argsort(distances)[:min(12,len(ys))]
        if distances[idx[0]]>14**2:
            continue
        weights=1.0/(1.0+distances[idx].astype(float))
        vals=patch[ys[idx],xs[idx]].astype(float)
        color=np.uint8(np.clip(np.sum(vals*weights[:,None],axis=0)/np.sum(weights)+.5,0,255))
        # A nearby neutral source pixel cannot create new magenta.
        out[y,x]=color
        successes+=1
    if successes!=pixels:
        return source,{'status':'ATLANDI_YETERLI_TEMIZ_REFERANS_YOK',
                       'repaired_pixels':0,'detected_pixels':pixels}
    return out,{'status':'ONIZLEME_YAPILDI','repaired_pixels':successes}

# V4.9.3 controlled geometry-first option. This does NOT modify or reapprove a
# stored V3 mask; it adds visible, photo-perspective vents to a print output.
# Count is measured from original source (13..16), NEVER fabricated to 15.
FIFTEEN_RECIPE = 'petek-real-count-photo-measured-perspective-vnext-2'


def draw_fifteen_slots(source, rendered, mask, quad, *, mode='orta', geometry=None):
    """Align every observed real recess with its photographic opening.

    No equal-spaced fabricated layout or fixed-length slot strokes. The new
    geometry is measured independently in the *original photo* and in the
    immutable print mask, then rasterized at each opening's real x/y/width.
    The approved mask/source/quad are read-only; all changes are temporary
    pixels INSIDE the approved printable face, as before.
    """
    q=_validate(source,rendered,mask,quad)
    if mode not in STRENGTH:raise ValueError('Invalid PETEK vent mode')
    if mode=='off':return rendered.copy(),{'status':'KAPALI','count':0,'changed_pixels':0}
    from .petek_slot_geometry_vnext import measure_real_vents, RECT_W, RECT_H
    slots, measured=measure_real_vents(source,mask,q)
    if not (13 <= len(slots) <= 16):
        raise engine.MaskError('PETEK_IZGARA_GERCEK_SAYI_OLCULEMEDI')
    outer=np.zeros((RECT_H,RECT_W),np.uint8)
    inner=np.zeros_like(outer)
    rim=np.zeros_like(outer)
    for slot in slots:
        path=np.int32(np.round(slot['path'])).reshape(-1,1,2)
        width=max(3,int(round(slot['width'])))
        # Local top, bottom and subtle curvature are measured from the source.
        # A rounded stroke means real openings are never visibly extended.
        cv2.polylines(outer,[path],False,255,width+6,cv2.LINE_AA)
        cv2.polylines(inner,[path],False,255,width,cv2.LINE_AA)
        rim_path=path.copy()
        rim_path[:,:,0]-=max(1,width//2+1)
        cv2.polylines(rim,[rim_path],False,170,2,cv2.LINE_AA)
        cv2.circle(outer,tuple(path[0,0]),max(2,(width+6)//2),255,-1,cv2.LINE_AA)
        cv2.circle(outer,tuple(path[-1,0]),max(2,(width+6)//2),255,-1,cv2.LINE_AA)
        cv2.circle(inner,tuple(path[0,0]),max(1,width//2),255,-1,cv2.LINE_AA)
        cv2.circle(inner,tuple(path[-1,0]),max(1,width//2),255,-1,cv2.LINE_AA)
    H=measured['homography']
    w,h=source.shape[1],source.shape[0]
    outskirts=cv2.warpPerspective(outer,H,(w,h),flags=cv2.INTER_LINEAR)
    cores=cv2.warpPerspective(inner,H,(w,h),flags=cv2.INTER_LINEAR)
    left_lip=cv2.warpPerspective(rim,H,(w,h),flags=cv2.INTER_LINEAR)
    panel=engine.polygon_mask(source.shape,q)>0
    # The source and originally approved mask remain untouched. Original 0-mask
    # real physical holes and all corners/curves/white sides are sacrosanct.
    allowed=(mask>0)&panel
    intensity=STRENGTH[mode]
    alpha=(outskirts.astype(np.float32)/255*.18 +
           cores.astype(np.float32)/255*.83)*intensity/.60
    alpha=np.clip(alpha,0,.96)
    alpha[~allowed]=0
    out=rendered.copy()
    active=alpha>.002
    if np.any(active):
        target=np.array([20,22,25],dtype=np.float32)
        out[active]=np.uint8(np.clip(np.round(
            out[active].astype(np.float32)*(1-alpha[active,None])+
            target[None,:]*alpha[active,None]),0,255))
        highlight=np.minimum(left_lip.astype(np.float32)/255*.13,.13)*intensity/.60
        highlight[~allowed]=0
        lit=highlight>.001
        if np.any(lit):
            out[lit]=np.uint8(np.clip(np.round(
                out[lit].astype(np.float32)*(1-highlight[lit,None])+
                np.array([104,103,102])[None,:]*highlight[lit,None]),0,255))
    if not np.array_equal(out[~allowed],rendered[~allowed]):
        raise engine.MaskError('PETEK_15_SLOT_OUTSIDE_PANEL_CHANGED')
    report={key:value for key,value in measured.items() if key!='homography'}
    # The old enum remains supported only for old tests/records; the measured
    # status distinguishes new source measurements from trusted mask evidence.
    if report['alignment'].startswith('APPROVED_MASK_'):
        report['alignment']=report['alignment'].replace('APPROVED_MASK_','EXISTING_MASK_',1)
    count=len(slots)
    return out, {**report,'status':f'{count}_IZGARA_UYGULANDI','count':count,
                 'changed_pixels':int(np.count_nonzero(np.any(out!=rendered,axis=2))),
                 'recipe':FIFTEEN_RECIPE,'mode':mode,
                 'note':f'Gercek fotograf kaynakli {count} izgara: merkez, aralik, aciklik boyu ve genislik perspektifle olculdu.'}


def despill_lower_left_geometry_v493(source, mask, quad, *, enabled=False):
    """Correct neon-pink marker *only* along the left section of bottom edge.

    Avoid the old global-magenta prerequisite: a narrow stray strip may be a
    tiny fraction of panel pixels. Never edit original file or printed art;
    only return an in-memory revised scene. All changed pixels must be in a
    small geometric boundary corridor and outside the approved print mask.
    """
    engine.mask_check(mask,source,quad)
    if not enabled:return source,{'status':'KAPALI','repaired_pixels':0,'detected_pixels':0}
    q=engine.validated_quad(quad,source.shape)
    h,w=mask.shape[:2]
    bottom_left=q[3].astype(float);bottom_right=q[2].astype(float)
    vec=bottom_right-bottom_left
    length=max(1.,float(np.linalg.norm(vec)))
    ph=max(1.,float(np.linalg.norm(q[3]-q[0])))
    band=max(3.,min(19.,ph*.018))
    yy,xx=np.indices(mask.shape,dtype=np.float32)
    along=((xx-bottom_left[0])*vec[0]+(yy-bottom_left[1])*vec[1])/(length**2)
    cross=np.abs((xx-bottom_left[0])*vec[1]-(yy-bottom_left[1])*vec[0])/length
    corridor=(along>=-.035)&(along<=.27)&(cross<=band)&(mask==0)
    hsv=cv2.cvtColor(source,cv2.COLOR_BGR2HSV)
    marker=(hsv[:,:,0]>=129)&(hsv[:,:,0]<=178)&(hsv[:,:,1]>=125)&(hsv[:,:,2]>=132)
    # Refuse broad magenta scenery: a line should be slender relative to its
    # length; this is never a global color wipe or creative recolor operation.
    candidate=corridor&marker
    count=int(np.count_nonzero(candidate))
    if count==0:return source,{'status':'TEMIZ','repaired_pixels':0,'detected_pixels':0}
    candidates_y,candidates_x=np.where(candidate)
    ys=np.ptp(candidates_y)+1;xs=np.ptp(candidates_x)+1
    if count>5000 or (xs>20 and ys>max(5,band*3.3)):
        return source,{'status':'GUZELLIK_INCELEMESI_GEREKLI_GENIS_KACAK',
                       'repaired_pixels':0,'detected_pixels':count}
    out=source.copy();fixed=0
    protected=(mask==0)&(~marker)
    for y,x in zip(candidates_y,candidates_x):
        rad=int(max(12,min(28,band*1.8)))
        y0=max(0,int(y)-rad);y1=min(h,int(y)+rad+1)
        x0=max(0,int(x)-rad);x1=min(w,int(x)+rad+1)
        local=protected[y0:y1,x0:x1] & (~candidate[y0:y1,x0:x1])
        y_neut,x_neut=np.where(local)
        if len(y_neut)<5:continue
        d=(y_neut+y0-y)**2+(x_neut+x0-x)**2
        use=np.argsort(d)[:min(15,len(d))]
        if d[use[0]]>rad**2:continue
        vals=source[y0:y1,x0:x1][y_neut[use],x_neut[use]].astype(np.float64)
        weights=1/(1+d[use].astype(np.float64))
        color=np.sum(vals*weights[:,None],axis=0)/weights.sum()
        out[y,x]=np.uint8(np.clip(np.round(color),0,255));fixed+=1
    rest=count-fixed
    if not np.array_equal(out[~candidate],source[~candidate]):
        raise engine.MaskError('PETEK_PINK_REPAIR_OUTSIDE_CORRIDOR')
    return out,{'status':'TEMIZLENDI' if rest==0 else 'KISMI_TEMIZLIK',
                'repaired_pixels':fixed,'detected_pixels':count,'remaining_pixels':rest}
