import sys
from pathlib import Path
import cv2
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'MERKEZ'))
from PETEK_V3.petek_finish_v492 import darken_slot_lips, despill_lower_left, estimate_slots
from PETEK_V3 import engine
from URETIM_V4.template_filter_v492 import filtered_templates


def synthetic():
    h,w=800,760
    quad=[[70,70],[690,70],[690,710],[70,710]]
    src=np.full((h,w,3),(216,216,216),np.uint8)
    panel=engine.polygon_mask(src.shape,engine.validated_quad(quad,src.shape))
    src[panel>0]=(255,0,255)
    mask=panel.copy()
    for i in range(15):
        x=100+i*39
        src[145:590,x:x+7]=(25,25,25)
        mask[145:590,x+1:x+6]=0
    return src,mask,quad

def test_15_dark_openings_detected_and_protected():
    src,mask,quad=synthetic()
    slots,metadata=estimate_slots(src,mask,quad)
    assert len(slots)==15,metadata
    output=np.full_like(src,(200,220,240))
    out,report=darken_slot_lips(src,output,mask,quad,mode='orta')
    assert report['changed_pixels']>0,report
    assert np.array_equal(out[mask==0],output[mask==0])
    assert (out[300,100] < output[300,100]).any()

def test_low_confidence_is_noop():
    src,mask,quad=synthetic()
    # Keep only three slots; valid print ratio but insufficient evidence.
    for i in range(3,15):mask[145:590,100+i*39:107+i*39]=255
    base=np.full_like(src,127)
    out,info=darken_slot_lips(src,base,mask,quad,mode='guclu')
    assert np.array_equal(out,base)
    assert info['changed_pixels']==0

def test_default_off_and_invalid_mode():
    src,mask,quad=synthetic();b=np.full_like(src,177)
    out,info=darken_slot_lips(src,b,mask,quad,mode='off')
    assert np.array_equal(out,b)
    with pytest.raises(ValueError):darken_slot_lips(src,b,mask,quad,mode='invalid')

def test_pink_lower_left_source_only_not_written_to_file():
    src,mask,quad=synthetic()
    src[706:713,72:85]=(255,0,255)
    old=src.copy()
    out,qa=despill_lower_left(src,mask,quad,enabled=True)
    assert qa['repaired_pixels']>0,qa
    assert np.array_equal(src,old)
    assert np.array_equal(out[150:580,150:185],old[150:580,150:185])
    assert not np.array_equal(out[711:713,72:85],old[711:713,72:85])
    # Not only changed: visible magenta leak must actually disappear.
    pixels=out[711:713,72:85]
    assert np.all(np.max(pixels,axis=2)-np.min(pixels,axis=2)<25),pixels

def test_cleanup_disabled_never_changes_pixels():
    src,mask,quad=synthetic();src[707:713,70:90]=(255,0,255)
    out,qa=despill_lower_left(src,mask,quad,enabled=False)
    assert out is src and qa['repaired_pixels']==0

def test_cleanup_rejects_non_magenta_reference():
    src,mask,quad=synthetic();src[:]=(130,125,120)
    out,qa=despill_lower_left(src,mask,quad,enabled=True)
    assert np.array_equal(out,src) and qa['repaired_pixels']==0

def test_filter_is_read_only_and_stable():
    items=[{'uid':'T003','category':'Wifi','source':'x'}, {'uid':'T001','category':'Petek','source':'y'},
           {'uid':'T002','category':'Wifi','source':'z'}]
    before=[dict(x) for x in items]
    assert [x['uid'] for x in filtered_templates(items,'Wifi')]==['T002','T003']
    assert [x['uid'] for x in filtered_templates(items,'Tümü','t00','Ad (Z-A)')]==['T003','T002','T001']
    assert filtered_templates(items,'Tümü','no match')==[]
    assert items==before
