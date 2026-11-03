"""Synthetic regression tests for PETEK source/mask photo rescue and exact preview parity."""
from pathlib import Path
import sys
import numpy as np
import cv2
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'MERKEZ'))
from MERKEZ.PETEK_V3.petek_visual_pipeline_vnext import render_petek_visual
from MERKEZ.PETEK_V3.petek_slot_geometry_vnext import measure_real_vents
from MERKEZ.PETEK_V3.realism import _magenta_pixels


def sample(n=15,bad_mask=False,bad_photo=False):
    h,w=690,900
    scene=np.full((h,w,3),(255,0,255),np.uint8)
    scene[:,:65]=(209,217,229)  # real white-painted left body
    mask=np.zeros((h,w),np.uint8)
    mask[40:650,66:850]=255
    xx=np.linspace(105,810,n).round().astype(int)
    for i,x in enumerate(xx):
        y0=120+i%3*2;y1=555-i%4*3
        cv2.line(scene,(x,y0),(x,y1),(18,20,22),8,cv2.LINE_AA)
        cv2.line(mask,(x,y0),(x,y1),0,9,cv2.LINE_AA)
        if bad_mask and i==6:
            cv2.line(mask,(x,55),(x,630),0,9,cv2.LINE_AA)
        if bad_photo and i==3:
            cv2.line(scene,(x,43),(x,635),(18,20,22),7,cv2.LINE_AA)
    quad=np.float32([[66,40],[849,40],[849,649],[66,649]])
    art=np.full_like(scene,255)
    cv2.putText(art,'DEMO',(310,340),cv2.FONT_HERSHEY_SIMPLEX,2.1,(30,38,40),4,cv2.LINE_AA)
    return scene,mask,quad,art


@pytest.mark.parametrize('n',[13,14,15,16])
def test_real_13_16_slot_recovery_from_wrong_mask_length_without_error(n):
    scene,mask,quad,art=sample(n,bad_mask=True)
    original_scene=scene.copy();original_mask=mask.copy()
    slots,geom=measure_real_vents(scene,mask,quad)
    assert geom['count']==n
    assert geom['endpoint_photo_recovered_count']>=1
    assert geom['endpoint_effect_suppressed_count']==0
    assert geom['max_endpoint_spread_rectified_690']<=25
    pic,qa=render_petek_visual(scene,art,quad,mask,1.1163,
        placement='cover',lighting='strong',material_effect=True,
        slot_mode='orta',pink_cleanup=False)
    assert qa['slot_qa']['count']==n
    assert np.array_equal(pic[mask==0],scene[mask==0])
    assert np.array_equal(scene,original_scene) and np.array_equal(mask,original_mask)
    printable=pic[(mask>0)&(art[:,:,0]>245)]
    assert printable.shape[0]>100
    # White ink must not become pink even on an original magenta template.
    assert not np.any(_magenta_pixels(printable.reshape(-1,1,3)))


def test_same_pipeline_yields_byte_identical_preview_and_batch_frames():
    scene,mask,quad,art=sample(15,bad_mask=True)
    opts=dict(placement='cover',lighting='strong',material_effect=True,
              slot_mode='orta',pink_cleanup=False)
    preview,preview_qa=render_petek_visual(scene,art,quad,mask,1.1163,**opts)
    batch,batch_qa=render_petek_visual(scene,art,quad,mask,1.1163,**opts)
    assert np.array_equal(preview,batch)
    assert preview_qa['lighting']==batch_qa['lighting']=='strong'
    assert preview_qa['slot_qa']['count']==batch_qa['slot_qa']['count']==15
    assert np.any(preview!=scene)


def test_web_and_tk_preview_explicitly_use_same_production_renderer():
    b=(ROOT/'MERKEZ/URETIM_V4/unified_batch.py').read_text('utf-8')
    t=(ROOT/'MERKEZ/URETIM_V4/gui_v4.py').read_text('utf-8')
    w=(ROOT/'SABLON_V2_MIMARI/core/petek_web_v477.py').read_text('utf-8')
    j=(ROOT/'SABLON_V2_MIMARI/static/js/petek_editor_v477.js').read_text('utf-8')
    assert 'render_petek_visual(' in b
    assert 'render_petek_visual(' in t
    assert 'render_petek_visual(' in w
    assert "effective_light='strong'" in t
    assert "realism_profile:'belirgin'" in j
    assert 'preview_slot_mode:' in j


def test_when_both_independent_endpoint_sources_bad_only_that_effect_is_skipped():
    scene,mask,quad,art=sample(15,bad_mask=True)
    # A source photograph may also have black artwork extending slot 6.
    x=int(np.linspace(105,810,15).round().astype(int)[6])
    cv2.line(scene,(x,55),(x,630),(17,18,19),8,cv2.LINE_AA)
    orig=scene.copy(),mask.copy()
    slots,qa=measure_real_vents(scene,mask,quad)
    assert len(slots)==15
    assert qa['endpoint_effect_suppressed_count']>=1
    assert 6 in qa['endpoint_effect_suppressed_indexes']
    assert not slots[6]['effect_eligible']
    result,qa2=render_petek_visual(scene,art,quad,mask,1.1163,
        lighting='strong',material_effect=True,slot_mode='orta',pink_cleanup=False)
    assert qa2['slot_qa']['count']==15
    assert qa2['slot_qa']['endpoint_effect_suppressed_count']>=1
    assert np.array_equal(result[mask==0],scene[mask==0])
    assert np.array_equal(scene,orig[0]) and np.array_equal(mask,orig[1])
