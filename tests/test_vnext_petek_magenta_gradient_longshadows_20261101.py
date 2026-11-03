"""Regression for 1 Nov protected marker, tonal gradient and uninterrupted shadows."""
import cv2
import numpy as np
import pytest

from MERKEZ.PETEK_V3 import engine
from MERKEZ.PETEK_V3.realism import apply,_diffuse_window_shadows
from MERKEZ.PETEK_V3.petek_source_marker_fringe_vnext import (marker_fringe_candidates,restore_source_marker_fringe)
from MERKEZ.PETEK_V3.petek_visual_pipeline_vnext import render_petek_visual, verify_petek_source_protection


def scene_with_marker_lips():
    h,w=450,670
    scene=np.full((h,w,3),(205,214,223),np.uint8)
    q=np.float32([[61,52],[601,52],[601,409],[61,409]])
    mask=np.zeros((h,w),np.uint8)
    mask[52:410,61:602]=255
    scene[52:410,61:602]=(255,0,255)
    for x in range(110,575,32):
        # original black physical vent protected region
        mask[112:353,x-3:x+4]=0
        scene[112:353,x-3:x+4]=(18,20,21)
    # Real magenta marker leakage OUTSIDE mask: top, left, bottom, right.
    scene[70:380,55:61]=(255,0,255)
    scene[47:52,105:580]=(255,0,255)
    scene[410:414,105:580]=(255,0,255)
    scene[75:350,602:606]=(255,0,255)
    # vent lip: one magenta source edge pixel is marked as protected
    mask[112:353,110]=0
    scene[112:353,110]=(255,0,255)
    art=np.full((350,550,3),247,np.uint8)
    cv2.putText(art,'DESEN',(130,190),cv2.FONT_HERSHEY_SIMPLEX,2,(42,42,42),3)
    return scene,mask,q,art


def test_marker_seam_all_four_edges_and_vent_lip_no_unrelated_pixels():
    src,mask,q,_=scene_with_marker_lips()
    original=src.copy(); approved=mask.copy()
    allowed=marker_fringe_candidates(src,mask,q)
    assert np.count_nonzero(allowed & (mask==0))>1000
    printed=src.copy()
    printed[mask>0]=(215,222,229)
    out,qa=restore_source_marker_fringe(src,printed,mask,q,enabled=True)
    assert qa['repaired_pixels']>1000
    for roi in [(slice(100,120),slice(55,61)),
                (slice(47,52),slice(250,280)),
                (slice(410,414),slice(250,280)),
                (slice(150,170),slice(602,606)),
                (slice(130,160),slice(110,111))]:
        original_mag=src[roi]
        after=out[roi]
        assert not np.array_equal(after,original_mag)
        hsv=cv2.cvtColor(np.ascontiguousarray(after),cv2.COLOR_BGR2HSV)
        assert float((hsv[:,:,1]>100).mean())<.40
    changed=np.any(out!=printed,axis=2)
    assert not np.any(changed & ~allowed)
    assert np.array_equal(out[100:130,300:305],printed[100:130,300:305])
    assert np.array_equal(src,original) and np.array_equal(mask,approved)
    assert verify_petek_source_protection(src,out,mask,q,pink_cleanup=True)['status']=='PASS'
    with pytest.raises(engine.MaskError):
        verify_petek_source_protection(src,out,mask,q,pink_cleanup=False)


def test_end_to_end_no_pink_lips_and_approved_holes_exact():
    src,mask,q,art=scene_with_marker_lips()
    out,report=render_petek_visual(src,art,q,mask,1.1163,
                    lighting='strong',slot_mode='off',pink_cleanup=True)
    assert report['fringe_qa']['repaired_pixels']>500
    black_core=(src[:,:,0]<30)&(src[:,:,1]<30)&(mask==0)
    assert np.array_equal(src[black_core],out[black_core])
    assert verify_petek_source_protection(src,out,mask,q,pink_cleanup=True)['status']=='PASS'
    assert report['source_protection_qa']['authorized_marker_fringe_pixels']>500


def test_black_hole_and_nonmarker_outside_change_is_rejected():
    src,mask,q,_=scene_with_marker_lips()
    v=src.copy();v[130,112]=(255,255,255)
    with pytest.raises(engine.MaskError,match='PETEK_PREVIEW_PROTECTED_PIXELS_CHANGED'):
        verify_petek_source_protection(src,v,mask,q,pink_cleanup=True)


def test_long_shadow_spans_full_width_and_avoids_vents():
    _,mask,_,_=scene_with_marker_lips()
    shadows=_diffuse_window_shadows((450,670,3),mask,.60)
    # Most of the width of one sunlit horizontal band remains continuous.
    probe=shadows[250,75:595]
    assert np.count_nonzero(probe>.20)>360
    assert np.all(shadows[mask==0]==0)
    assert shadows.max()>.30


def test_gradient_matte_no_clipped_white_and_reproducible():
    src,mask,_,_=scene_with_marker_lips()
    design=np.full_like(src,255)
    a=apply(src,design,mask,'strong')
    b=apply(src,design,mask,'strong')
    assert np.array_equal(a,b)
    assert np.array_equal(src,src.copy())
    assert np.quantile(a[mask>0],.99)<253
    # Long shadows and gentle tone direction produce measurable variation.
    assert np.std(a[mask>0].astype(float))>10
    assert abs(np.mean(a[mask>0])-np.mean(apply(src,design,mask,'natural')[mask>0]))>1
