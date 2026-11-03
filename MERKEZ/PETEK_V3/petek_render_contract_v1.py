"""PETEK V4.11: photo-anchored repair contract, physical vent safety and render receipts.

All work is performed on memory copies. Nothing in this module persists approved
masks, corner points, artwork, photographs, or SQLite records.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import cv2
import numpy as np

from . import engine
from .petek_finish_v492 import despill_lower_left_geometry_v493
from .petek_source_marker_fringe_vnext import (marker_fringe_candidates,
                                               restore_source_marker_fringe,
                                               restore_source_marker_vent_interiors)
from .petek_slot_geometry_vnext import (RECT_H, RECT_W, _fit_source_vents,
    _source_peaks, measure_real_vents)


def digest_frame(frame):
    return hashlib.sha256(np.ascontiguousarray(frame).tobytes()).hexdigest()


@dataclass(frozen=True)
class RenderPlan:
    placement: str
    lighting: str
    material_effect: bool
    slot_mode: str
    pink_cleanup: bool
    physical_aspect: float
    source_raster_sha256: str = ''
    mask_raster_sha256: str = ''
    quad_sha256: str = ''
    artwork_raster_sha256: str = ''

    def manifest(self):
        return {'placement':self.placement,'lighting':self.lighting,
                'material_effect':self.material_effect,'slot_mode':self.slot_mode,
                'pink_cleanup':self.pink_cleanup,
                'physical_aspect':self.physical_aspect,'recipe':'petek-v411-contract-1',
                'source_raster_sha256':self.source_raster_sha256,
                'mask_raster_sha256':self.mask_raster_sha256,
                'quad_sha256':self.quad_sha256,
                'artwork_raster_sha256':self.artwork_raster_sha256}

    def digest(self):
        return hashlib.sha256(json.dumps(self.manifest(),sort_keys=True,
                            separators=(',',':'),allow_nan=False).encode()).hexdigest()


@dataclass
class StageAudit:
    source: np.ndarray
    mask: np.ndarray
    receipts: list = field(default_factory=list)

    def record(self, stage, before, after, *, allow_outside=False):
        if (not isinstance(after,np.ndarray) or before.shape!=after.shape or
                before.dtype!=after.dtype or after.dtype!=np.uint8):
            raise engine.MaskError('PETEK_STAGE_SHAPE_INVALID:'+stage)
        changed=np.any(before!=after,axis=2)
        outside=changed&(self.mask==0)
        if np.any(outside) and not allow_outside:
            raise engine.MaskError('PETEK_PROTECTED_PIXELS_CHANGED:'+stage)
        ys,xs=np.where(outside)
        self.receipts.append({
          'stage_id':stage,'before_sha256':digest_frame(before),
          'after_sha256':digest_frame(after),
          'changed_pixels':int(changed.sum()),
          'changed_protected_pixels':int(outside.sum()),
          'first_protected_coordinates':[[int(x),int(y)] for y,x in zip(ys[:6],xs[:6])],
        })


def source_repair_reference(scene, printed_inside, mask, quad, *,
                            pink_cleanup, lighting, material_effect,
                            shadow_style='classic',corner_side='right',include_pre=True,
                            g3_asset=False):
    """Replay exact *authorized* outside-mask photo processing independently.

    Reconstruct outside from the original source, not from the possibly-tampered
    output. The unprotected print provides legitimate inpaint donor context.
    A green pixel substituted into an allowed magenta location cannot PASS.
    """
    if (scene.shape!=printed_inside.shape or scene.shape[:2]!=mask.shape or
            scene.dtype!=np.uint8 or printed_inside.dtype!=np.uint8):
        raise engine.MaskError('PETEK_PROTECTION_SHAPE_MISMATCH')
    expected,preqa=despill_lower_left_geometry_v493(scene,mask,quad,enabled=bool(pink_cleanup and include_pre))
    before=expected.copy()
    expected=before.copy()
    expected[mask>0]=printed_inside[mask>0]
    expected,fringeqa=restore_source_marker_fringe(scene,expected,mask,quad,
                                                    enabled=pink_cleanup)
    before_vent=expected.copy()
    expected,ventqa=restore_source_marker_vent_interiors(
        scene,expected,mask,quad,enabled=pink_cleanup)
    ventchanges=np.any(expected!=before_vent,axis=2)&(mask==0)
    prechanges=np.any(before!=scene,axis=2)&(mask==0)
    if pink_cleanup:
        # 14px ordinary fringe OR exact 3..19px source-derived pre-repair.
        ordinary=marker_fringe_candidates(scene,mask,quad)
        allowed=ordinary|prechanges|ventchanges
    else:
        allowed=np.zeros(mask.shape,bool)
    beforewall=expected.copy()
    if material_effect and lighting=='strong' and not g3_asset:
        from .wall_window_shadows_vnext import apply_wall_window_shadows
        expected,_=apply_wall_window_shadows(scene,expected,mask,quad,lighting='strong',
                          shadow_style=shadow_style,corner_side=corner_side)
    wallchanges=np.any(expected!=beforewall,axis=2)&(mask==0)
    if material_effect and lighting=='strong' and g3_asset:
        from .petek_effect_assets import apply_g3_wall_asset
        expected,_=apply_g3_wall_asset(scene,expected,mask,quad)
        wallchanges=np.any(expected!=beforewall,axis=2)&(mask==0)
    repairchanges=np.any(beforewall!=scene,axis=2)&(mask==0)
    if np.any(repairchanges&~allowed):
        raise engine.MaskError('PETEK_SOURCE_REPAIR_OUTSIDE_POLICY')
    return expected,{
        'authorized_marker_fringe_pixels':int(repairchanges.sum()),
        'authorized_wall_shadow_pixels':int(wallchanges.sum()),
        'pre_despill_pixels':int(prechanges.sum()),
        'fringe_repair_pixels':int(fringeqa.get('repaired_pixels',0)),
        'vent_repair_pixels':int(ventqa.get('repaired_pixels',0)),
        'pre_despill_status':preqa.get('status'),
    }


def ensure_source_vent_mask_consensus(scene,mask,quad):
    """Protect photographed slits *even when visual grille effect is OFF*.

    Only an independently observed 10..16-line photo group may establish
    a physical core. If no source geometry is defensible, this check abstains;
    the normal geometry renderer and manual-review approval rules remain.
    """
    q=engine.validated_quad(quad,scene.shape)
    engine.mask_check(mask,scene,q)
    target=np.float32([[0,0],[RECT_W-1,0],[RECT_W-1,RECT_H-1],[0,RECT_H-1]])
    M=cv2.getPerspectiveTransform(np.float32(q),target)
    photo=cv2.warpPerspective(scene,M,(RECT_W,RECT_H),flags=cv2.INTER_LINEAR,
                             borderValue=(230,230,230))
    maskrect=cv2.warpPerspective(mask,M,(RECT_W,RECT_H),flags=cv2.INTER_NEAREST,
                                borderValue=255)
    gray=cv2.cvtColor(photo,cv2.COLOR_BGR2GRAY)
    blackhat=cv2.morphologyEx(gray,cv2.MORPH_BLACKHAT,
                     cv2.getStructuringElement(cv2.MORPH_RECT,(31,3)))
    profile=blackhat[int(RECT_H*.25):int(RECT_H*.74)].mean(axis=0)
    peaks=_source_peaks(profile)
    centers,_=_fit_source_vents(peaks,profile)
    if centers is None:
        # A regularity model can reject 14 real dark strokes when their pitch
        # is outside its 36..76px search window. Do not call that 'no vents'
        # and then paint over them merely because slot_mode='off'.
        from .petek_slot_geometry_vnext import _mask_peaks
        mask_centers=_mask_peaks(maskrect)
        if 12<=len(peaks)<=28 and len(mask_centers)<13:
            raise engine.MaskError('PETEK_SOURCE_MASK_VENT_CONFLICT_REVIEW: '
                 f'kaynak_aday={len(peaks)};maske_delik={len(mask_centers)};'
                 'kaynak_araligi_belirsiz')
        return {'status':'SOURCE_GEOMETRY_UNCONFIRMED',
                'source_candidates':len(peaks),'source_verified':False}
    line_proofs=[]
    y0,y1=int(RECT_H*.28),int(RECT_H*.70)
    for center in centers:
        x=int(round(center))
        if x<3 or x>=RECT_W-3:continue
        # A centre must be a long, source-visible, dark valley rather than a
        # single isolated black pixel or hypothetical evenly spaced marker.
        line=blackhat[y0:y1,x-2:x+3]
        supported=float(np.mean(line.max(axis=1)>max(8.,float(profile[x])*.23)))
        kept=float(np.mean(maskrect[y0:y1,x-2:x+3]<128))
        line_proofs.append((round(float(center),2),round(supported,3),round(kept,3)))
    if len(line_proofs)!=len(centers):
        raise engine.MaskError('PETEK_SOURCE_MASK_VENT_CONFLICT_REVIEW')
    # Observe geometry and mask independently: if most true photo lines have
    # a long dark source run, each must have a corresponding excluded core.
    source_good=sum(s>.38 for _,s,_ in line_proofs)
    if source_good<max(9,len(centers)-2):
        from .petek_slot_geometry_vnext import _mask_peaks
        if len(_mask_peaks(maskrect))<13:
            raise engine.MaskError('PETEK_SOURCE_MASK_VENT_CONFLICT_REVIEW: '
                   f'kaynak={len(centers)};kaynak_uzunluk_kaniti_yetersiz')
    if source_good>=max(9,len(centers)-2):
        invalid=[entry for entry in line_proofs if entry[1]>.38 and entry[2]<.48]
        if invalid:
            raise engine.MaskError('PETEK_SOURCE_MASK_VENT_CONFLICT_REVIEW: '
                 f'foto={len(centers)};mask_uyusmazligi={len(invalid)};'
                 f'ilk_merkez={invalid[0][0]}')
    return {'status':'SOURCE_MASK_CONSISTENT' if source_good>=9 else 'SOURCE_GEOMETRY_UNCONFIRMED',
            'source_candidates':len(peaks),'source_count':len(centers),
            'source_verified':bool(source_good>=9),
            'minimum_center_mask_coverage':min(p[2] for p in line_proofs),
            'independent_core_check':True}


def _source_protected_preview_mask(scene, mask, quad):
    """Build an unsaved mask from independently measured dark source cores."""
    q=engine.validated_quad(quad,scene.shape)
    engine.mask_check(mask,scene,q)
    target=np.float32([[0,0],[RECT_W-1,0],[RECT_W-1,RECT_H-1],[0,RECT_H-1]])
    M=cv2.getPerspectiveTransform(np.float32(q),target)
    photo=cv2.warpPerspective(scene,M,(RECT_W,RECT_H),flags=cv2.INTER_LINEAR,
                              borderValue=(230,230,230))
    rect_mask=cv2.warpPerspective(mask,M,(RECT_W,RECT_H),
                                  flags=cv2.INTER_NEAREST,borderValue=255)
    slots, vent_qa=measure_real_vents(scene,mask,q)
    if not (10 <= len(slots) <= 16):
        raise engine.MaskError('PETEK_DIAGNOSTIC_PHYSICAL_VENTS_UNCERTAIN')
    protected=rect_mask.copy()
    for slot in slots:
        x=int(round(slot['center']))
        half=max(2,int(round(float(slot['width'])/2.0)))
        if slot.get('effect_eligible'):
            y0=int(slot['y0'])
            y1=int(slot['y1'])
        else:
            # A single source trace can include the upper curved edge. Use
            # the measured slot consensus endpoints, never that outlier.
            y0=int(round(vent_qa['median_top_rectified_690']))
            y1=int(round(vent_qa['median_bottom_rectified_690']))
        y0=max(0,y0)
        y1=min(RECT_H-1,y1)
        if y1-y0 < int(RECT_H*.28):
            raise engine.MaskError('PETEK_DIAGNOSTIC_PHYSICAL_VENTS_UNCERTAIN')
        protected[y0:y1+1,max(0,x-half):min(RECT_W,x+half+1)]=0
    if np.count_nonzero(protected==0) <= 0:
        raise engine.MaskError('PETEK_DIAGNOSTIC_PHYSICAL_VENTS_UNCERTAIN')
    inverse=cv2.getPerspectiveTransform(target,np.float32(q))
    source_protected=cv2.warpPerspective(protected,inverse,
                                         (scene.shape[1],scene.shape[0]),
                                         flags=cv2.INTER_NEAREST,borderValue=255)
    temporary_mask=cv2.min(mask,source_protected)
    proof=ensure_source_vent_mask_consensus(scene,temporary_mask,q)
    if proof.get('status')!='SOURCE_MASK_CONSISTENT':
        raise engine.MaskError('PETEK_DIAGNOSTIC_PHYSICAL_VENTS_UNCERTAIN')
    return temporary_mask,{
        'kind':'TEMPORARY_SOURCE_EVIDENCE_PRINT_MASK',
        'source_vent_count':len(slots),
        'source_verified':True,
        'removed_unsafe_print_pixels':int(np.count_nonzero(
            (mask>0)&(temporary_mask==0))),
        'measured_slot_widths':[float(slot['width']) for slot in slots],
        'measured_slot_spans':[[int(slot['y0']),int(slot['y1'])] for slot in slots],
        'vent_measurement_qa':vent_qa,
        'mask_raster_sha256':digest_frame(temporary_mask),
        **proof,
    }


def temporary_photo_protected_preview_mask(scene, mask, quad):
    """Conservative, unsaved print mask for a *diagnostic artwork preview*.

    Intersection can ONLY revoke the incoming mask's printing permission.
    Real photographed dark openings are carried from the photo candidate,
    never drawn, extrapolated or automatically approved. If photo evidence is
    weak, refuse this preview rather than displaying a fake finished product.
    """
    if (not isinstance(scene, np.ndarray) or not isinstance(mask, np.ndarray) or
            scene.dtype != np.uint8 or mask.dtype != np.uint8 or
            scene.ndim != 3 or scene.shape[2] != 3 or mask.shape != scene.shape[:2]):
        raise engine.MaskError('PETEK_DIAGNOSTIC_INPUT_SHAPE_INVALID')
    try:
        temporary_mask,proof=_source_protected_preview_mask(scene,mask,quad)
    except engine.MaskError as exc:
        raise engine.MaskError('PETEK_DIAGNOSTIC_PHYSICAL_VENTS_UNCERTAIN: '
                               + str(exc)) from exc
    original_print = int(np.count_nonzero(mask > 0))
    remaining_print = int(np.count_nonzero(temporary_mask > 0))
    if (original_print == 0 or remaining_print < original_print * .55 or
            remaining_print < 100):
        raise engine.MaskError('PETEK_DIAGNOSTIC_PRINT_AREA_UNCERTAIN')
    return temporary_mask, {
        'kind':'TEMPORARY_PHOTO_PROTECTED_PRINT_MASK',
        'removed_unsafe_print_pixels':int(np.count_nonzero(
            (mask > 0) & (temporary_mask == 0))),
        'print_area_retained_fraction':round(remaining_print/original_print,4),
        'source_vent_count':int(proof['source_count']),
        'source_verified':True,
        'auto_mask_status':'SOURCE_EVIDENCE',
        'not_saved':True,
        'not_approved':True,
    }
