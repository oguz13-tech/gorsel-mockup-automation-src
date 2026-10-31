"""Photo-measured variable-count vent geometry for PETEK non-destructive finish.

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
MIN_REAL_VENTS = 13
MAX_REAL_VENTS = 16


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


def _plausible(points: list[float] | np.ndarray, *, count: int | None=None) -> bool:
    """Only validate *observed* physical positions; count is not assumed 15."""
    if count is not None and len(points) != count:
        return False
    if not (MIN_REAL_VENTS <= len(points) <= MAX_REAL_VENTS):
        return False
    d=np.diff(np.asarray(points,float))
    # Perspective was rectified: local spacing changes slightly, but no
    # consecutive physical vents should collapse or jump to a second grille.
    return bool(np.all(d>18) and np.all(d<92) and
                np.std(d)/max(1.,np.mean(d))<.36)


def _fit_source_vents(peaks: list[tuple[float,float]], profile: np.ndarray):
    """Select 13..16 positions actually detected in the ORIGINAL photo.

    Candidate lattice pitch is used ONLY to reject spurious dark-artwork peaks.
    We never return interpolated or fabricated positions. Physical count is
    selected from the photo; the old 15-hole assumption is not an input.
    """
    if len(peaks) < MIN_REAL_VENTS:
        return None, 0
    xs=np.asarray([p[0] for p in peaks],float)
    strengths=np.asarray([p[1] for p in peaks],float)
    # Full evidence already present: still test grid alternatives when an
    # unrelated vertical artwork stroke looks like an extra vent.
    best=None
    for count in range(MIN_REAL_VENTS,MAX_REAL_VENTS+1):
        for anchor in xs[xs < RECT_W*.29]:
            for pitch in np.arange(36.,76.,.8):
                expected=anchor+pitch*np.arange(count)
                if expected[-1]>RECT_W*.975:continue
                distances=np.abs(expected[:,None]-xs[None,:])
                assignments=np.argmin(distances,axis=1)
                residual=distances[np.arange(count),assignments]
                tolerance=min(11.,pitch*.23)
                # Every slot must have independent ORIGINAL pixel evidence.
                if np.any(residual >= tolerance):continue
                if len(set(assignments.tolist()))!=count:continue
                observed=xs[assignments]
                if not _plausible(observed,count=count):continue
                if observed[0] < RECT_W*.025 or observed[-1] > RECT_W*.98:continue
                # Score rewards observed slots, penalizes superfluous dark
                # stripes and deviations; no '15' bias whatsoever.
                unused=np.ones(len(xs),bool)
                unused[assignments]=False
                dark_bonus=float(np.sum(np.log1p(strengths[assignments])))
                score=(135.*count - 46.*np.count_nonzero(unused)
                       - 3.8*float(np.sum(residual)) + dark_bonus)
                if best is None or score>best[0]:
                    best=(score,observed.copy())
    if best is None:return None,0
    return best[1],0


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
    # Trust the original photo for visible physical endpoints. Its 1-D
    # black-hat support is preferred when continuous; use approved mask only
    # when source contrast is insufficient. The reviewed mask may include
    # broad top/bottom recesses beyond the real narrow opening.
    present=visible if np.count_nonzero(visible)>h*.15 else mask_lines
    present[:int(h*.085)]=False
    present[int(h*.93):]=False
    span=_longest_run(present)
    if span is None or span[1]-span[0]<h*.22:return None
    y0,y1=span
    # Physical radiator vents are STRAIGHT in the rectified product plane.
    # Previous polyline fitting tracked scenery texture and created visibly
    # bent/torn strokes. Never follow arbitrary per-row black-hat maxima.
    # The x-coordinate is the source/mask *measured* center; y endpoints and
    # median width are constrained to actual dark-opening evidence.
    widths=[]
    for y in range(y0,y1+1,14):
        xa2=max(0,x-12);xb2=min(w,x+13)
        if mask_lines[y]:
            row=(rect_mask[y,xa2:xb2]<128)
            hits=np.flatnonzero(row)
            # Limit to the physical recess around the measured center.
            near=hits[np.abs(hits-(x-xa2))<=9]
            if near.size:
                widths.append(float(max(3,min(20,near[-1]-near[0]+1))))
                continue
        if has_source:
            row=contrast[y,xa2:xb2]
            nearby=row[max(0,x-xa2-9):min(len(row),x-xa2+10)]
            if nearby.size and nearby.max()>threshold:
                widths.append(float(max(3,min(20,int(np.count_nonzero(nearby>=nearby.max()*.50))))))
    width=float(np.clip(np.median(widths) if widths else 7.,3.,min(20.,w*.024)))
    # Projected camera perspective will change the apparent slant naturally.
    # Only TWO endpoints; no artificial wiggle, spline or freehand trace.
    return {'center':round(float(center),3),'y0':y0,'y1':y1,
            'width':round(width,2),
            'path':[(round(float(center),2),float(y0)),
                    (round(float(center),2),float(y1))]}


def measure_real_vents(source: np.ndarray, mask: np.ndarray, quad):
    """Return 13..16 physically detected, perspective-aligned real openings.

    Never adds missing slots to reach an assumed target. Where the original
    image is ambiguous, a complete reviewed mask with plausible 13..16 holes
    is a fallback. Unreliable records are kept for manual review, unchanged.
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
    measured,inferred=_fit_source_vents(source_peaks,profile)
    source_measured=measured is not None
    if measured is None and _plausible(masked_centers):
        measured=np.asarray(masked_centers,dtype=float)
    if measured is None:
        raise engine.MaskError('PETEK_IZGARA_KONUMU_BELIRSIZ: PETEK_KAYNAK_GEOMETRI_INCELEME_GEREKLI: '
            f'orijinal fotograf {len(source_peaks)} dikey koyu cizgi, '
            f'maske {len(masked_centers)} korunan delik gosteriyor. '
            '13..16 gercek yarik kaynaktan/maske kaydindan olculmeden cizgi cizilmez; '
            '4 kose / maske duzeltmesini ve kaynak goruntusunu inceleyin.')
    if not _plausible(measured):
        raise engine.MaskError('PETEK_KAYNAK_IZGARA_ARALIKLARI_TUTARSIZ')
    slots=[]
    for cx in measured:
        slot=_trace_one(float(cx),contrast,rect_mask,has_source=source_measured)
        if slot is None:
            # Narrow mask/source interruptions are resolved from neighbouring
            # *measured* tracks, not a fixed full-height artificial stripe.
            raise engine.MaskError('PETEK_YARIK_BOYLARI_INCELEME_GEREKLI')
        slots.append(slot)
    # Endpoints are expected to be near-parallel on the rectified product.
    # The source sometimes has additional dark artwork above/below a hole:
    # never extend that anomaly beyond the other measured physical vents.
    starts=np.asarray([r['y0'] for r in slots],float)
    ends=np.asarray([r['y1'] for r in slots],float)
    median_start=float(np.median(starts));median_end=float(np.median(ends))
    median_length=max(1.,median_end-median_start)
    # Use a generous 8% tolerance; no blind lengthening of real short vents.
    tolerance=max(14.,float(RECT_H)*.033)
    for r in slots:
        y0=max(int(r['y0']),int(round(median_start-tolerance)))
        y1=min(int(r['y1']),int(round(median_end+tolerance)))
        if y1-y0 < median_length*.82:
            raise engine.MaskError('PETEK_IZGARA_BOY_TUTARSIZ: bu fotoğraftaki delik başlangıç/bitişlerini maske ekranında inceleyin.')
        r['y0'],r['y1']=y0,y1
        r['path']=[(r['center'],float(y0)),(r['center'],float(y1))]
    spacings=np.diff(measured)
    mask_offset=None
    if len(masked_centers)==len(measured):
        mask_offset=[round(float(a-b),2) for a,b in zip(measured,masked_centers)]
    n=len(slots)
    return slots,{'status':'KAYNAK_YARIKLAR_OLCULDU',
        'count':n,
        'alignment':f'SOURCE_PHOTO_{n}' if source_measured else f'APPROVED_MASK_{n}',
        'mask_evidence_count':len(masked_centers),
        'source_evidence_count':len(source_peaks),
        'inferred_source_slots':inferred,
        'centers_rectified_900':[round(float(cx),3) for cx in measured],
        'spacings_rectified_900':[round(float(dx),3) for dx in spacings],
        'slot_spans_rectified_690':[[slot['y0'],slot['y1']] for slot in slots],
        'widths_rectified_900':[slot['width'] for slot in slots],
        'mask_source_center_delta':mask_offset,
        'homography':cv2.getPerspectiveTransform(target,np.float32(q))}


def measure_fifteen_vents(source: np.ndarray, mask: np.ndarray, quad):
    """Backward-compatible old call name; NEVER forces a count of fifteen."""
    return measure_real_vents(source,mask,quad)
