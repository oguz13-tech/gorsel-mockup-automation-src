"""Regression: real photo's protected pixels must not be compared to a despilled copy.

The old pipeline 'successfully' modified pixel strips under a printable mask,
then Flask compared against original and returned HTTP409. Tests below reproduce
this exact conflict and ensure all preview/batch frames use source originals.
"""
import numpy as np
import pytest
from MERKEZ.PETEK_V3 import engine
from MERKEZ.PETEK_V3.petek_finish_v492 import despill_lower_left_geometry_v493
from MERKEZ.PETEK_V3.petek_visual_pipeline_vnext import render_petek_visual, verify_petek_source_protection


def sample():
    scene = np.full((420,600,3),(215,221,228),np.uint8)
    quad = np.float32([[60,40],[539,40],[539,379],[60,379]])
    mask = np.zeros((420,600),np.uint8)
    mask[40:380,60:540] = 255
    scene[40:380,60:540] = (255,0,255)
    for x in range(90,515,28):
        mask[115:310,x-2:x+3]=0
        scene[115:310,x-2:x+3]=(18,22,24)
    # Only protected pixels immediately BELOW lower left panel edge are neon.
    # Legacy pre-render despill edited this explicitly non-printable corridor.
    scene[381:384,105:135]=(255,0,255)
    artwork=np.full((350,500,3),240,np.uint8)
    return scene,mask,quad,artwork


def test_legacy_narrow_source_magenta_fringe_is_repaired_without_touching_real_holes():
    scene,mask,quad,art=sample()
    source=scene.copy();approved=mask.copy()
    pre,info=despill_lower_left_geometry_v493(scene,mask,quad,enabled=True)
    assert info['repaired_pixels']==90
    assert np.count_nonzero(np.any(pre!=scene,axis=2)&(mask==0))==90
    result,qa=render_petek_visual(scene,art,quad,mask,1.1163,
         slot_mode='off',pink_cleanup=True,lighting='strong',material_effect=True)
    assert qa['pre_pink_qa']['authorized_marker_fringe_pixels']==90
    assert qa['pre_pink_qa']['repaired_pixels']==90
    assert qa['protected_nonfringe_pixels_unchanged'] is True
    assert qa['protected_pixels_unchanged'] is False  # authorized 90 magenta ONLY
    assert np.array_equal(result[mask==0],pre[mask==0])
    assert np.array_equal(result[115:310,90:515][mask[115:310,90:515]==0],
                          source[115:310,90:515][mask[115:310,90:515]==0])
    assert np.array_equal(scene,source) and np.array_equal(mask,approved)
    assert np.any(result[mask>0]!=source[mask>0])


@pytest.mark.parametrize('lighting,material,pink',[
    ('strong',True,True),('natural',True,True),('off',False,True),
    ('strong',True,False),
])
def test_web_and_batch_must_use_original_source_guard(lighting,material,pink):
    scene,mask,quad,art=sample()
    pic,qa=render_petek_visual(scene,art,quad,mask,1.1163,
        slot_mode='off',lighting=lighting,material_effect=material,pink_cleanup=pink)
    expected,_=despill_lower_left_geometry_v493(scene,mask,quad,enabled=pink)
    assert np.array_equal(pic[mask==0],expected[mask==0])
    assert qa['protected_nonfringe_pixels_unchanged']
    if not pink:
        assert qa['pre_pink_qa']['status']=='KAPALI'


def test_other_stages_still_cannot_change_vent_or_arch_pixels():
    scene,mask,quad,art=sample()
    def bad_material(working_scene,printed,mask_arg,quad_arg,category,*,enabled):
        output=printed.copy()
        output[2,2]=[1,2,3]  # outside approved mask and original photograph
        return output
    with pytest.raises(engine.MaskError,match='PETEK_PROTECTED_PIXELS_CHANGED'):
        render_petek_visual(scene,art,quad,mask,1.1163,slot_mode='off',
          pink_cleanup=True,lighting='strong',material_effect=True,
          material_fn=bad_material)
    assert np.array_equal(scene[2,2],[215,221,228])


def test_web_endpoint_uses_exact_same_original_protection_contract():
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    api=(root/'SABLON_V2_MIMARI/core/petek_web_v477.py').read_text('utf-8')
    core=(root/'MERKEZ/PETEK_V3/petek_visual_pipeline_vnext.py').read_text('utf-8')
    assert 'verify_petek_source_protection' in api
    assert 'verify_petek_source_protection' in core
    assert 'protection=safety_fn(render_scene,picture,mask,quad)' in core
    assert 'allowed_marker_fringe_pixels' not in core  # whitelist is never blanket
    assert "placement='cover',lighting='off',material_effect=False" in api
