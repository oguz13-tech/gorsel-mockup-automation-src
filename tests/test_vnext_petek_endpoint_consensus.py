"""Regression: individual radiators cannot grow to follow artwork or random dark pixels.
Uses synthetic photos only; no user mask, template or store profile writes.
"""
from pathlib import Path
import sys
import numpy as np
import cv2
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from MERKEZ.PETEK_V3.petek_slot_geometry_vnext import measure_real_vents,RECT_H,RECT_W
from MERKEZ.PETEK_V3.petek_finish_v492 import draw_fifteen_slots


def physical_fixture(n=15, bad_photo=False, bad_mask=False):
    src=np.full((RECT_H,RECT_W,3),(203,209,218),np.uint8)
    mask=np.full((RECT_H,RECT_W),255,np.uint8)
    xs=np.linspace(95,800,n).astype(int)
    for i,x in enumerate(xs):
        y0=105+i%3*2; y1=554-i%4*3
        cv2.line(src,(x,y0),(x,y1),(28,29,30),8,cv2.LINE_AA)
        cv2.line(mask,(x,y0),(x,y1),0,8,cv2.LINE_AA)
        if bad_photo and i in (2,9):
            cv2.line(src,(x,37),(x,615),(24,24,25),7,cv2.LINE_AA)
        if bad_mask and i==6:
            cv2.line(mask,(x,40),(x,660),0,8,cv2.LINE_AA)
    quad=np.float32([[1,1],[RECT_W-2,1],[RECT_W-2,RECT_H-2],[1,RECT_H-2]])
    # The printable region never extends outside the approved four-corner face.
    from MERKEZ.PETEK_V3.engine import polygon_mask
    mask[polygon_mask(src.shape,quad)==0]=0
    return src,mask,quad


@pytest.mark.parametrize('count',[13,14,15,16])
def test_interrupted_and_overlong_dark_illustration_cannot_lengthen_real_slots(count):
    src,mask,q=physical_fixture(count,bad_photo=True)
    src0=src.copy(); mask0=mask.copy()
    slots,qa=measure_real_vents(src,mask,q)
    assert len(slots)==count
    assert qa['endpoint_reference']=='REVIEWED_MASK'
    assert qa['max_endpoint_spread_rectified_690']<=25
    assert all(96<=slot['y0']<=120 and 535<=slot['y1']<=565 for slot in slots)
    out,report=draw_fifteen_slots(src,np.full_like(src,(231,236,243)),mask,q)
    assert report['count']==count
    assert np.array_equal(src,src0)
    assert np.array_equal(mask,mask0)
    assert np.array_equal(out[mask==0],np.full_like(src,(231,236,243))[mask==0])


def test_unreliable_reviewed_mask_hole_end_is_rescued_by_original_photo():
    src,mask,q=physical_fixture(15,bad_mask=True)
    before=src.copy(),mask.copy()
    slots,qa=measure_real_vents(src,mask,q)
    assert qa['count']==15
    assert qa['endpoint_photo_recovered_count']>=1
    assert qa['endpoint_effect_suppressed_count']==0
    assert slots[6]['endpoint_evidence']=='SOURCE_PHOTO'
    assert slots[6]['y0']>=92 and slots[6]['y1']<=570
    assert qa['max_endpoint_spread_rectified_690']<25
    assert np.array_equal(src,before[0]) and np.array_equal(mask,before[1])
