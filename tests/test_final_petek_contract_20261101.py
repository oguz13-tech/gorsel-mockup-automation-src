"""Fail-before/pass-after safety proofs for the real shared PETEK renderer.

These tests are deliberately intended to FAIL against the pristine 2026-11-01
package. Do not replace them with a prepopulated remaining_pixels=105 QA stub.
"""
import numpy as np
import pytest
from MERKEZ.PETEK_V3 import engine
from MERKEZ.PETEK_V3.petek_visual_pipeline_vnext import (
    render_petek_visual,verify_petek_source_protection)
from MERKEZ.PETEK_V3.petek_finish_v492 import despill_lower_left_geometry_v493
from MERKEZ.PETEK_V3.petek_source_marker_fringe_vnext import marker_fringe_candidates


def _nineteen_beyond_fourteen():
    h,w=1470,870
    scene=np.full((h,w,3),(207,219,231),np.uint8)
    quad=np.float32([[120,140],[749,140],[749,1220],[120,1220]])
    mask=np.zeros((h,w),np.uint8)
    mask[140:1221,120:750]=255
    scene[mask>0]=(255,0,255)
    for x in range(174,693,37):
        mask[380:1010,x-2:x+3]=0
        scene[380:1010,x-2:x+3]=(18,20,23)
    # 16..18px below the actual print, just beyond the 14px marker fringe.
    scene[1236:1239,180:210]=(255,0,255)
    art=np.full((420,630,3),240,np.uint8)
    return scene,mask,quad,art


def test_19_14_real_render_both_authorities_share_one_source_replay():
    scene,mask,quad,art=_nineteen_beyond_fourteen()
    pre,preqa=despill_lower_left_geometry_v493(scene,mask,quad,enabled=True)
    changed=np.any(pre!=scene,axis=2)&(mask==0)
    assert preqa['repaired_pixels']==90
    assert int(changed.sum())==90
    assert not np.any(changed & marker_fringe_candidates(scene,mask,quad))
    original,original_mask=scene.copy(),mask.copy()
    final,qa=render_petek_visual(scene,art,quad,mask,1.1163,
        slot_mode='off',lighting='off',material_effect=False,pink_cleanup=True)
    assert qa['source_protection_qa']['status']=='PASS'
    assert qa['source_protection_qa']['pre_despill_pixels']==90
    assert np.array_equal(final[mask==0],pre[mask==0])
    assert np.array_equal(scene,original) and np.array_equal(mask,original_mask)


def test_n1_arbitrary_color_on_approved_fringe_must_not_pass():
    from tests.test_vnext_petek_protected_409_original_source_20261101 import sample
    scene,mask,quad,art=sample()
    image,_=render_petek_visual(scene,art,quad,mask,1.1163,
        slot_mode='off',lighting='off',material_effect=False,pink_cleanup=True)
    image[381,105]=(1,2,3)
    with pytest.raises(engine.MaskError,match='PETEK_PREVIEW_PROTECTED_PIXELS_CHANGED'):
        verify_petek_source_protection(scene,image,mask,quad,pink_cleanup=True,
              shadow_style='corner')


def test_n2_material_inserts_105_new_pink_and_qa_must_detect_not_misreport_clean():
    from tests.test_vnext_petek_pink409_source_linked_20261101 import _sample
    scene,mask,quad=_sample(photo_magenta=False)
    art=np.full((350,500,3),240,np.uint8)
    def inject(scene_ref,printed,mask_ref,q_ref,category,*,enabled):
        out=printed.copy()
        out[55:90,62:65]=(255,0,255)  # 35*3=105, inside approved print
        assert np.all(mask_ref[55:90,62:65]>0)
        return out
    with pytest.raises(engine.MaskError,match='PETEK_PINK_CLEANUP_INCOMPLETE_REVIEW'):
        render_petek_visual(scene,art,quad,mask,1.1163,slot_mode='off',
             lighting='strong',material_effect=True,pink_cleanup=True,material_fn=inject)


@pytest.mark.parametrize('n',[14,15])
def test_n3_unprotected_photo_vents_refuse_even_with_slot_mode_off(n):
    from tests.test_vnext_petek_dynamic_photo_count import scene_with_count
    scene,mask,quad,_=scene_with_count(n)
    photo,approved=scene.copy(),mask.copy()
    art=np.full_like(scene,247)
    with pytest.raises(engine.MaskError,match='PETEK_SOURCE_MASK_VENT_CONFLICT_REVIEW'):
        render_petek_visual(scene,art,quad,mask,1.1163,slot_mode='off',
             lighting='off',material_effect=False,pink_cleanup=False)
    assert np.array_equal(scene,photo) and np.array_equal(mask,approved)


def test_verified_complete_masks_still_produce_true_art_and_preserve_vents():
    from tests.test_vnext_petek_dynamic_photo_count import scene_with_count
    scene,mask,quad,_=scene_with_count(15,complete_mask=True)
    art=np.full((450,700,3),(230,15,230),np.uint8)
    out,qa=render_petek_visual(scene,art,quad,mask,1.1163,
          slot_mode='orta',lighting='strong',material_effect=True,pink_cleanup=True)
    assert qa['slot_qa']['count']==15
    assert qa['source_protection_qa']['status']=='PASS'
    assert qa['pink_qa']['remaining_pixels']==0
    assert np.array_equal(out[mask==0],scene[mask==0])


def test_wall_does_not_invent_eligibility_on_excluded_black_pixel():
    from tests.test_vnext_petek_two_wall_shadows import photo
    from MERKEZ.PETEK_V3.wall_window_shadows_vnext import wall_region
    scene,mask,quad=photo()
    # Small excluded detail in an otherwise neutral wall field.
    y,x=160,32
    scene[y,x]=(10,10,10)
    assert not wall_region(scene,mask,quad)[y,x]


def test_mask_gray_value_one_outside_panel_is_not_silently_allowed():
    scene,mask,quad,art=_nineteen_beyond_fourteen()
    mask[5,5]=1
    with pytest.raises(engine.MaskError,match='Maske panel disina tasiyor'):
        engine.mask_check(mask,scene,quad)


def test_n3_dense_nonstandard_real_strokes_do_not_escape_off_mode_guard():
    # The photo fitter searches 36..76 canonical pixels; 30px real stroke
    # pitch must not silently become 'no real slots' if only 1 mask hole exists.
    h,w=690,900
    scene=np.full((h,w,3),(255,0,255),np.uint8)
    quad=np.float32([[0,0],[899,0],[899,689],[0,689]])
    mask=np.full((h,w),255,np.uint8)
    mask[:40,:]=0;mask[650:,:]=0
    for i,x in enumerate(range(90,481,30)):
        scene[130:550,x-3:x+4]=(18,20,22)
        if i==0:mask[130:550,x-3:x+4]=0
    art=np.full((300,500,3),240,np.uint8)
    with pytest.raises(engine.MaskError,match='PETEK_SOURCE_MASK_VENT_CONFLICT_REVIEW'):
        render_petek_visual(scene,art,quad,mask,1.1163,
             lighting='off',material_effect=False,slot_mode='off',pink_cleanup=False)
