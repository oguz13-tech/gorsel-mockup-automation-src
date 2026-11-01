"""Synthetic physical-slot geometry and immutable source/approval regressions.

Never commit real user PETEK photos: test pattern is procedurally generated.
"""
from pathlib import Path
import sys
import cv2
import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from MERKEZ.PETEK_V3.petek_finish_v492 import draw_fifteen_slots
from MERKEZ.PETEK_V3.petek_slot_geometry_vnext import measure_fifteen_vents


def physical_source(*,mask_missing=(1,6,9,12),noise=False):
    gw,gh=900,690
    centers=np.asarray([83,136,187,241,294,344,396,450,503,556,608,659,712,765,819],int)
    rect=np.full((gh,gw,3),(188,201,216),dtype=np.uint8)
    maskrect=np.full((gh,gw),255,np.uint8)
    for i,cx in enumerate(centers):
        y0=110+(i%3)*4
        y1=571-(i%4)*5
        width=7+(i%4)
        cv2.line(rect,(int(cx),y0),(int(cx),y1),(23,25,30),width,cv2.LINE_AA)
        if i not in mask_missing:
            cv2.line(maskrect,(int(cx),y0),(int(cx),y1),0,width+1,cv2.LINE_AA)
    # Actual dark photographic artwork can also contain unrelated dark strokes.
    if noise:
        cv2.line(rect,(218,170),(218,480),(35,45,58),6,cv2.LINE_AA)
    cv2.ellipse(maskrect,(450,-115),(480,210),0,0,180,0,-1)
    cv2.ellipse(maskrect,(450,760),(430,115),0,180,360,0,-1)
    out_h,out_w=540,700
    q=np.float32([[79,63],[626,77],[596,448],[73,481]])
    dst=np.float32([[0,0],[gw-1,0],[gw-1,gh-1],[0,gh-1]])
    transform=cv2.getPerspectiveTransform(dst,q)
    source=np.full((out_h,out_w,3),(238,233,229),dtype=np.uint8)
    projected=cv2.warpPerspective(rect,transform,(out_w,out_h))
    panel=np.zeros((out_h,out_w),np.uint8)
    cv2.fillConvexPoly(panel,q.astype(np.int32),255)
    source[panel>0]=projected[panel>0]
    warped_mask=cv2.warpPerspective(maskrect,transform,(out_w,out_h),flags=cv2.INTER_NEAREST)
    warped_mask[panel==0]=0
    return source,warped_mask,q,centers


@pytest.mark.parametrize('noise',[False,True])
def test_fifteen_photo_measured_centers_even_if_four_mask_holes_missing(noise):
    source,mask,q,expected=physical_source(noise=noise)
    before=(source.copy(),mask.copy(),q.copy())
    rendered=np.full_like(source,(170,160,220))
    out,qa=draw_fifteen_slots(source,rendered,mask,q,mode='orta')
    assert qa['count']==15
    assert qa['alignment']=='SOURCE_PHOTO_15'
    assert qa['inferred_source_slots']<=1
    assert len(qa['spacings_rectified_900'])==14
    assert np.max(np.abs(np.asarray(qa['centers_rectified_900'])-expected))<5
    assert all(395 <= (b-a) <= 480 for a,b in qa['slot_spans_rectified_690'])
    assert qa['changed_pixels']>200
    assert np.array_equal(out[mask==0],rendered[mask==0])
    for original,unchanged in zip(before,(source,mask,q)):
        assert np.array_equal(original,unchanged)


def test_photo_geometry_does_not_replace_irregular_real_intervals_with_linspace():
    source,mask,q,expected=physical_source(mask_missing=())
    _,qa=measure_fifteen_vents(source,mask,q)
    assert qa['alignment']=='SOURCE_PHOTO_15'
    measured=np.asarray(qa['centers_rectified_900'])
    assert np.max(np.abs(measured-expected))<5
    assert np.std(np.diff(measured))>1.0  # preserve measured, not uniform grid.
    assert qa['widths_rectified_900'][0]!=qa['widths_rectified_900'][-1]


def test_ambiguous_source_and_mask_require_review_not_fabricate_15():
    source,mask,q,expected=physical_source(mask_missing=tuple(range(15)))
    # Erase source vents too: no evidence of physical holes exists.
    panel=np.zeros(mask.shape,np.uint8)
    cv2.fillConvexPoly(panel,q.astype(np.int32),255)
    source[panel>0]=210
    with pytest.raises(Exception,match='PETEK_IZGARA_KONUMU_BELIRSIZ'):
        measure_fifteen_vents(source,mask,q)
