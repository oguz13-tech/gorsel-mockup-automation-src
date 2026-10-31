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
# 15 is a product invariant, not a count estimated from arbitrary dark artwork.
FIFTEEN_RECIPE = 'petek-15-slot-perspective-v493-1'

def draw_fifteen_slots(source, rendered, mask, quad, *, mode='orta', geometry=None):
    """Render 15 visually recessed vents in the 4-corner print projection.

    For a valid quadrilateral EXACTLY 15 positions are constructed, even if
    pixel recognition of existing vents fails. Protected physical holes, the
    white side wall, curves, floor and all out-of-quad pixels are byte-identical.
    Perceptual success on a real user's image still requires visual review.
    """
    q=_validate(source,rendered,mask,quad)
    if mode not in STRENGTH:raise ValueError('Invalid 15-slot mode')
    if mode=='off':return rendered.copy(),{'status':'KAPALI','count':0,'changed_pixels':0}
    # Rectified canonical face, mapped back with the same quad used by renderer.
    gw,gh=900,690
    src=np.float32([[0,0],[gw-1,0],[gw-1,gh-1],[0,gh-1]])
    H=cv2.getPerspectiveTransform(src,np.float32(q))
    outer=np.zeros((gh,gw),dtype=np.uint8)
    inner=np.zeros_like(outer)
    rim=np.zeros_like(outer)
    # Restrict to central face: keep shallow top vent arch and lower cut-out.
    slot_y0=int(gh*.15);slot_y1=int(gh*.82)
    slot_w=max(5,round(gw*.011))
    # 15 slots with constant rhythm. No external object detection needed.
    # Prefer source-authored physical openings: in approved masks protected
    # vent pixels are 0. Rectify the mask, inspect vertical center-region
    # occupancy, and align to 15 genuine openings instead of doubling them.
    inv=cv2.getPerspectiveTransform(np.float32(q),src)
    rect=cv2.warpPerspective(mask,inv,(gw,gh),flags=cv2.INTER_NEAREST,borderValue=255)
    vent_band=rect[int(gh*.27):int(gh*.71),:]
    occupancy=(vent_band<128).mean(axis=0)
    run_mask=occupancy>.33
    evidence=[]
    starts=np.flatnonzero(run_mask & ~np.r_[False,run_mask[:-1]])
    ends=np.flatnonzero(run_mask & ~np.r_[run_mask[1:],False])
    for a,b in zip(starts,ends):
        if gw*.025<=a<=gw*.967 and 2<=b-a+1<=gw*.05:
            evidence.append(float(a+b)/2)
    evidence=np.array(evidence,dtype=float)
    centers=np.linspace(gw*.078,gw*.922,15)
    alignment='PANEL_PERSPECTIVE'
    if len(evidence)==15 and 2 < np.median(np.diff(evidence)) and \
            np.std(np.diff(evidence))/np.mean(np.diff(evidence))<.36:
        centers=evidence
        alignment='EXISTING_MASK_15'
    elif 8<=len(evidence)<15:
        gaps=np.diff(evidence)
        good=gaps[(gaps>gw*.025)&(gaps<gw*.12)]
        if len(good)>3:
            pitch=float(np.median(good[good<=np.percentile(good,65)]))
            best=None
            for step in np.linspace(pitch*.92,pitch*1.08,11):
                for match in evidence:
                    for index in range(15):
                        first=float(match-index*step)
                        if first<gw*.025 or first+step*14>gw*.975:continue
                        grid=first+np.arange(15)*step
                        delta=np.min(np.abs(evidence[:,None]-grid[None,:]),axis=1)
                        if np.any(delta>step*.35):continue
                        # Prefer alignment of real slots, then similar overall
                        # panel margins; never invent a hole count from artwork.
                        score=float(np.sum(delta*delta)+.001*(first-gw*.078)**2)
                        if best is None or score<best[0]:best=(score,grid)
            if best is not None:
                centers=best[1]
                alignment='PARTIAL_MASK_15_FIT'
    for cx in centers:
        x=int(round(cx));r=max(3,int(slot_w//2))
        # Soft cast shadow, rounded physical opening, gentle lip highlight.
        cv2.rectangle(outer,(x-r-3,slot_y0-4),(x+r+3,slot_y1+4),255,-1)
        cv2.circle(outer,(x,slot_y0-4),r+3,255,-1)
        cv2.circle(outer,(x,slot_y1+4),r+3,255,-1)
        cv2.rectangle(inner,(x-r,slot_y0),(x+r,slot_y1),255,-1)
        cv2.circle(inner,(x,slot_y0),r,255,-1)
        cv2.circle(inner,(x,slot_y1),r,255,-1)
        cv2.line(rim,(x-r-1,slot_y0),(x-r-1,slot_y1),170,2)
    # A single warp keeps the original perspective. Never stretch source art.
    w,h=source.shape[1],source.shape[0]
    outskirts=cv2.warpPerspective(outer,H,(w,h),flags=cv2.INTER_LINEAR)
    cores=cv2.warpPerspective(inner,H,(w,h),flags=cv2.INTER_LINEAR)
    left_lip=cv2.warpPerspective(rim,H,(w,h),flags=cv2.INTER_LINEAR)
    panel=engine.polygon_mask(source.shape,q)>0
    # Only printable pixels can change. Dark REAL holes remain real image data.
    allowed=(mask>0)&panel
    intensity=STRENGTH[mode]
    alpha=(outskirts.astype(np.float32)/255*.18 +
           cores.astype(np.float32)/255*.83)*intensity/.60
    alpha=np.clip(alpha,0,.96)
    alpha[~allowed]=0
    out=rendered.copy()
    active=alpha>.002
    if np.any(active):
        # Slightly warm dark volume instead of artificial pure-black stripes.
        target=np.array([20,22,25],dtype=np.float32)
        blended=out[active].astype(np.float32)*(1-alpha[active,None])+target[None,:]*alpha[active,None]
        out[active]=np.clip(np.round(blended),0,255).astype(np.uint8)
        # Very narrow sidewall rim, dimmed by painted artwork; stays within panel.
        highlight=np.minimum(left_lip.astype(np.float32)/255*.13, .13)*intensity/.60
        highlight[~allowed]=0
        active_lip=highlight>.001
        out[active_lip]=np.uint8(np.clip(out[active_lip].astype(np.float32)* (1-highlight[active_lip,None])+
                                         np.array([104,103,102])[None,:]*highlight[active_lip,None],0,255))
    if not np.array_equal(out[~allowed],rendered[~allowed]):
        raise engine.MaskError('PETEK_15_SLOT_OUTSIDE_PANEL_CHANGED')
    return out, {'status':'15_IZGARA_UYGULANDI', 'count':15,
                 'changed_pixels':int(np.count_nonzero(np.any(out!=rendered,axis=2))),
                 'recipe':FIFTEEN_RECIPE,'mode':mode,
                 'alignment':alignment,'mask_evidence_count':len(evidence),
                 'centers_rectified_900':[round(float(cx),3) for cx in centers],
                 'note':'Perspektif geometrisi: 15 slot. Gerçek fotoğrafı insan incelemeli.'}


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
