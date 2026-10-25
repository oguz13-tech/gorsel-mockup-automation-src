import numpy as np
import cv2
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'MERKEZ'))
from PETEK_V3.brush_tools import apply_stroke,brush_radius_screen

def allowed_fixture():
    allowed=np.zeros((240,360),np.uint8)
    cv2.fillConvexPoly(allowed,np.int32([[55,30],[320,45],[300,200],[70,210]]),255)
    return allowed

def test_brush_only_changes_polygon():
    allowed=allowed_fixture(); mask=np.zeros_like(allowed)
    apply_stroke(mask,allowed,(58,40),130,255)
    assert np.count_nonzero(mask)>0
    assert not np.any(mask[allowed==0])

def test_continuous_fast_drag_no_gaps():
    a=allowed_fixture();m=np.zeros_like(a)
    apply_stroke(m,a,(120,100),11,255)
    apply_stroke(m,a,(290,100),11,255,previous=(120,100))
    assert np.all(m[100,120:291]==255)

def test_outside_anchor_does_not_paint():
    a=allowed_fixture();m=np.zeros_like(a)
    assert apply_stroke(m,a,(5,5),100,255)==0
    assert not m.any()

def test_hard_coverage_and_erasing():
    a=allowed_fixture();m=np.zeros_like(a)
    apply_stroke(m,a,(170,100),70,255)
    assert set(np.unique(m)).issubset({0,255})
    apply_stroke(m,a,(170,100),14,0)
    assert m[100,170]==0
    assert not np.any(m[a==0])

def test_cursor_zoom_mapping():
    assert brush_radius_screen(40,.5)==10
    assert brush_radius_screen(40,2)==40

def test_reject_invalid_mask():
    a=allowed_fixture();m=np.zeros((10,10),np.uint8)
    try: apply_stroke(m,a,(1,1),20,255)
    except ValueError: pass
    else: assert False
