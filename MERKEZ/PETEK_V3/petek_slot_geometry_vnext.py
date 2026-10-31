"""Photo-measured 15-slot geometry for the PETEK VNext non-destructive finish.

MEASURE from the ORIGINAL source raster and the current approved/draft mask,
never from artwork or a fabricated regularly spaced grille. Rectify with the
reviewed four-corner homography, detect physical elongated recesses, measure
centers, gaps, upper/lower ends, widths and slight line trajectories, then
project the measured paths back to original camera perspective.

Does not save, mutate, or approve any user file/profile/mask.
"""
from __future__ import annotations

import cv2
import numpy as np

from . import engine

RECT_W = 900
RECT_H = 690


def _source_peaks(profile: np.ndarray) -> list[tuple[float, float]]:
    """Locate supported dark vertical strokes in the original-photo contrast."""
    w=len(profile)
    smoothed=cv2.GaussianBlur(profile[np.newaxis].astype(np.float32), (0,0), 2.0)[0]
    lo,hi=int(w*.035),int(w*.965)
    threshold=max(5.0,float(np.max(smoothed[lo:hi]))*.095)
    candidates=[]
    for x in range(lo+12,hi-12):
        v=float(smoothed[x])
        if v<threshold or not (v>=smoothed[x-1] and v>smoothed[x+1]):
            continue
        baseline=max(float(np.min(smoothed[x-12:x])),float(np.min(smoothed[x+1:x+13])))
        prominence=v-baseline
        if prominence<max(2.5,v*.15):
            continue
        candidates.append((x,v+prominence*.25))
    # Suppress duplicate detections of two lips of the same real slot.
    ordered=sorted(candidates,key=lambda p:-p[1]);chosen=[]
    for item in ordered:
        if all(abs(item[0]-prev[0])>=int(w*.025) for prev in chosen):
            chosen.append(item)
    return sorted(chosen)


def _mask_peaks(rect_mask: np.ndarray) -> list[float]:
    """Find reviewed 0-mask hole columns without counting broad top/bottom voids."""
    h,w=rect_mask.shape
    occupancy=np.mean(rect_mask[int(.27*h):int(.72*h)]<128,axis=0)
    band=occupancy>.27
    starts=np.flatnonzero(band & ~np.r_[False,band[:-1]])
    ends=np.flatnonzero(band & ~np.r_[band[1:],False])
    peaks=[]
    for a,b in zip(starts,ends):
        width=int(b-a+1)
        if w*.03<=a<=w*.965 and 2<=width<=w*.047:
            peaks.append(float(a+b)*.5)
    return peaks


def _plausible(points: list[float] | np.ndarray, *, count: int=15) -> bool:
    if len(points)!=count:return False
    d=np.diff(np.asarray(points,float))
    return bool(np.all(d>18) and np.all(d<92) and
                np.std(d)/max(1.,np.mean(d))<.36)


def _fit_source_fifteen(peaks: list[tuple[float,float]], profile: np.ndarray):
    """Choose exactly 15 *observed* peaks; a grid is only an outlier filter.

    The fitted pitch is never used to replace a measurable vent center. Only
    if a maximum of two detections are interrupted, interpolate from measured
    neighbours and check for local ORIGINAL source-line evidence.
    """
    if len(peaks)==15 and _plausible([p[0] for p in peaks]):
        return np.asarray([p[0] for p in peaks],float),0
    if len(peaks)<13:
        return None,0
    xs=np.asarray([p[0] for p in peaks],float)
    strengths=np.asarray([p[1] for p in peaks],float)
    best=None
    # A planar physical product has near-constant rectified pitch, but every
    # final position comes from the actual source dark-line response.
    for anchor in xs[xs < RECT_W*.29]:
        for pitch in np.arange(39.,66.,.8):
            expected=anchor+pitch*np.arange(15)
            if expected[-1]>RECT_W*.97:
                continue
            distances=np.abs(expected[:,None]-xs[None,:])
            assignments=np.argmin(distances,axis=1)
            residual=distances[np.arange(15),assignments]
            keep=residual<min(11.,pitch*.24)
            if len(set(assignments[keep].tolist()))!=int(np.count_nonzero(keep)):
                continue
            count=int(np.count_nonzero(keep))
            if count<13:continue
            # Use per-pixel evidence, not uniform spacing or the strongest
            # unrelated horse/woodgrain texture stripe.
            strength=float(np.sum(np.log1p(strengths[assignments[keep]])))
            score=100.*count - 3.*float(np.sum(residual[keep])) +strength
            if best is None or score>best[0]:
                best=(score,expected,assignments,keep)
    if best is None:return None,0
    _,expected,assignments,keep=best
    out=expected.copy()
    out[keep]=xs[assignments[keep]]
    # Missing source peaks must still have a small but REAL dark source trace.
    # No ungrounded empty-space construction is permitted.
    missing=np.flatnonzero(~keep)
    smooth=cv2.GaussianBlur(profile[None].astype(np.float32),(0,0),2.0)[0]
    for idx in missing:
        x=int(round(expected[idx]));a=max(0,x-8);b=min(RECT_W,x+9)
        patch=smooth[a:b]
        if len(patch)<3 or float(patch.max())<max(5.,float(np.median(smooth)) + 3.0):
            return None,0
        out[idx]=a+int(np.argmax(patch))
    if not _plausible(out):return None,0
    return out,len(missing)


def _longest_run(presence: np.ndarray):
    if not np.any(presence):return None
    # Real holes are long vertical features; join small occlusions/paint marks.
    merged=cv2.morphologyEx(np.uint8(presence[:,None]),cv2.MORPH_CLOSE,
                            np.ones((27,1),np.uint8))[:,0]>0
    starts=np.flatnonzero(merged & ~np.r_[False,merged[:-1]])
    ends=np.flatnonzero(merged & ~np.r_[merged[1:],False])
    if len(starts)==0:return None
    idx=int(np.argmax(ends-starts))
    return int(starts[idx]),int(ends[idx])


def _trace_one(center: float, contrast: np.ndarray, rect_mask: np.ndarray,
               has_source: bool) -> dict | None:
    h,w=contrast.shape
    x=int(round(center));xa=max(0,x-9);xb=min(w,x+10)
    # Only narrow isolated dark holes count: the top arch and bottom cutout
    # span many neighbouring columns and must not artificially extend vents.
    mask_lines=(rect_mask[:,xa:xb]<128).any(axis=1)
    neighbour=max(17,int(w*.024))
    mask_lines &= (rect_mask[:,max(0,x-neighbour)]>128) & \
                  (rect_mask[:,min(w-1,x+neighbour)]>128)
    contrast_line=contrast[:,xa:xb].max(axis=1)
    threshold=max(9.0,float(np.median(contrast_line[int(.23*h):int(.77*h)]))*.27)
    visible=(contrast_line>threshold) if has_source else np.zeros(h,bool)
    # Direct source evidence controls the physical ends whenever observable.
    # The approved mask is a fallback, not a reason to extend a source slot.
    present=visible if np.count_nonzero(visible)>h*.15 else mask_lines
    present[:int(h*.085)]=False
    present[int(h*.93):]=False
    span=_longest_run(present)
    if span is None or span[1]-span[0]<h*.22:return None
    y0,y1=span
    # Fitting is local, never move a vent across its measured neighbour.
    track=[];widths=[]
    for y in range(y0,y1+1,14):
        xx0=max(0,x-11);xx1=min(w,x+12)
        source_patch=contrast[max(0,y-3):min(h,y+4),xx0:xx1]
        local=source_patch.mean(axis=0)
        src_ok=bool(has_source and local.size and local.max()>max(7.,threshold*.80))
        if src_ok:
            peak_x=xx0+int(np.argmax(local))
            peak=float(local.max())
            area=np.flatnonzero(local>=max(7.,peak*.40))
            near=area[np.abs(area-(peak_x-xx0))<=7]
            width=float(max(3,len(near))) if len(near) else 6.
        else:
            region=(rect_mask[y,xx0:xx1]<128)
            good=np.flatnonzero(region)
            if len(good):
                mid=int(good[np.argmin(np.abs(good-(x-xx0)))])
                left=mid;right=mid
                while left>0 and region[left-1]:left-=1
                while right<len(region)-1 and region[right+1]:right+=1
                peak_x=xx0+round((left+right)*.5)
                width=float(right-left+1)
            else:
                peak_x=x;width=7.
        track.append((float(peak_x),float(y)))
        widths.append(width)
    if track[-1][1]<y1:
        track.append((track[-1][0],float(y1)))
    # Remove 1-row texture outliers, keep realistic subtle perspective drift.
    vals=np.asarray([p[0] for p in track],float)
    if len(vals)>=5:
        smooth=vals.copy()
        for k in range(1,len(vals)-1):smooth[k]=np.median(vals[max(0,k-2):min(len(vals),k+3)])
        vals=smooth
    track=[(round(float(v),2),p[1]) for v,p in zip(vals,track)]
    width=float(np.clip(np.median(widths),3.,min(25.,w*.028)))
    return {'center':round(float(center),3),'y0':y0,'y1':y1,
            'width':round(width,2),'path':track}


def measure_fifteen_vents(source: np.ndarray, mask: np.ndarray, quad):
    """Return *measured* source-coordinates of 15 real, perspective-aligned slots.

    If the source and approved mask together do not provide enough geometry,
    this requests a local/manual review rather than fabricating a second grille.
    In the normal case, it measures all 15 from the original photo, even when
    several protected holes are absent in the existing mask.
    """
    q=engine.validated_quad(quad,source.shape)
    engine.mask_check(mask,source,q)
    target=np.float32([[0,0],[RECT_W-1,0],[RECT_W-1,RECT_H-1],[0,RECT_H-1]])
    inverse=cv2.getPerspectiveTransform(np.float32(q),target)
    rect_source=cv2.warpPerspective(source,inverse,(RECT_W,RECT_H),
                                  flags=cv2.INTER_LINEAR,borderValue=(230,230,230))
    rect_mask=cv2.warpPerspective(mask,inverse,(RECT_W,RECT_H),
                                flags=cv2.INTER_NEAREST,borderValue=255)
    gray=cv2.cvtColor(rect_source,cv2.COLOR_BGR2GRAY)
    contrast=cv2.morphologyEx(gray,cv2.MORPH_BLACKHAT,
                             cv2.getStructuringElement(cv2.MORPH_RECT,(31,3)))
    profile=contrast[int(RECT_H*.25):int(RECT_H*.74)].mean(axis=0)
    source_peaks=_source_peaks(profile)
    masked_centers=_mask_peaks(rect_mask)
    measured,inferred=_fit_source_fifteen(source_peaks,profile)
    source_measured=measured is not None
    if measured is None and _plausible(masked_centers):
        measured=np.asarray(masked_centers,dtype=float)
    if measured is None:
        raise engine.MaskError('PETEK_IZGARA_KONUMU_BELIRSIZ: PETEK_15_KAYNAK_GEOMETRI_INCELEME_GEREKLI: '
            f'orijinal fotograf {len(source_peaks)} dikey koyu cizgi, '
            f'maske {len(masked_centers)} korunan delik gosteriyor. '
            '15 fiziksel izgara kaynaktan olculmeden tahmini cizgi cizilmez; '
            '4 kose / maske duzeltmesini ve kaynak goruntusunu inceleyin.')
    if not _plausible(measured):
        raise engine.MaskError('PETEK_15_KAYNAK_IZGARA_ARALIKLARI_TUTARSIZ')
    slots=[]
    for cx in measured:
        slot=_trace_one(float(cx),contrast,rect_mask,has_source=source_measured)
        if slot is None:
            # Narrow mask/source interruptions are resolved from neighbouring
            # *measured* tracks, not a fixed full-height artificial stripe.
            raise engine.MaskError('PETEK_15_YARIK_BOYLARI_INCELEME_GEREKLI')
        slots.append(slot)
    spacings=np.diff(measured)
    mask_offset=None
    if len(masked_centers)==15:
        mask_offset=[round(float(a-b),2) for a,b in zip(measured,masked_centers)]
    return slots,{'status':'KAYNAK_15_OLCULDU',
        'alignment':'SOURCE_PHOTO_15' if source_measured else 'APPROVED_MASK_15',
        'mask_evidence_count':len(masked_centers),
        'source_evidence_count':len(source_peaks),
        'inferred_source_slots':inferred,
        'centers_rectified_900':[round(float(cx),3) for cx in measured],
        'spacings_rectified_900':[round(float(dx),3) for dx in spacings],
        'slot_spans_rectified_690':[[slot['y0'],slot['y1']] for slot in slots],
        'widths_rectified_900':[slot['width'] for slot in slots],
        'mask_source_center_delta':mask_offset,
        'homography':cv2.getPerspectiveTransform(target,np.float32(q))}
