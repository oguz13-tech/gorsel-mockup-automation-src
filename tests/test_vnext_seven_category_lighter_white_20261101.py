"""Mild, photo-neutral white recovery on all seven categories.

The actual seven-category render path calls PETEK_V3.realism.apply. The
photometric change must not alter printed black ink, vivid artwork, two
scene-spanning shadow bands, source magenta or approved ventilation holes.
"""
import numpy as np
import pytest

from MERKEZ.PETEK_V3.realism import apply, _diffuse_window_shadows
from URETIM_V4.scene_daylight_vnext import CATEGORIES, apply_scene_daylight, RECIPE


def fixture():
    h,w=460,770
    scene=np.full((h,w,3),(198,207,214),np.uint8)
    mask=np.zeros((h,w),np.uint8)
    mask[50:410,115:700]=255
    scene[mask>0]=(255,0,255)
    art=np.full_like(scene,255)
    art[140:170,385:420]=(12,13,13)  # intentional dark lettering
    art[290:315,350:385]=(45,115,228)  # intentional coloured drawing
    return scene,mask,art


def test_lighter_but_not_white_clipped_and_genuine_left_to_centre_transition():
    scene,mask,art=fixture()
    src=scene.copy();approved=mask.copy();design=art.copy()
    a=apply(scene,art,mask,'strong')
    assert np.array_equal(a,apply(scene,art,mask,'strong'))
    # White centre median was 212.7 before the subtle daylight lift.
    center=np.mean(a[90:400,435:460],axis=2)
    assert 214 < float(np.median(center)) < 248, float(np.median(center))
    # True photographed side should still anchor the left seam.
    left=np.mean(a[90:400,125:142],axis=2)
    assert float(np.median(center))>float(np.median(left))+12
    # Do not wash out dark ink or add a magenta chroma-key cast.
    assert float(a[150,390].mean())<26
    assert a[120,450].max()<=252
    face=a[mask>0].astype(np.int16)
    assert not np.any((face[:,0]>face[:,1]+25)&(face[:,2]>face[:,1]+25))
    assert np.array_equal(scene,src) and np.array_equal(mask,approved) and np.array_equal(art,design)


def test_two_horizontally_spanning_shadow_bands_still_visible_after_lift():
    scene,mask,art=fixture()
    out=apply(scene,art,mask,'strong')
    # Two long horizontal shadows, not a full-face gray overlay.
    values=np.mean(out[95:397,465].astype(np.float32),axis=1)
    assert float(np.quantile(values,.90)-np.quantile(values,.10))>42
    shadow=_diffuse_window_shadows(scene.shape,mask,.60)
    assert (shadow[145,200]>.08) and (shadow[280,200]>.08)
    assert not np.any(shadow[mask==0])


def test_brightening_is_neutral_artwork_only_and_off_is_identity():
    scene,mask,art=fixture()
    printed=apply(scene,art,mask,'strong')
    assert float(printed[300,365].max()-printed[300,365].min())>70
    assert float(printed[150,390].mean())<26
    assert np.array_equal(apply(scene,art,mask,'off'),art)
    assert RECIPE.endswith('V2_LIGHTER_WHITE_20261101')


@pytest.mark.parametrize('category', sorted(CATEGORIES))
def test_all_seven_scene_daylight_renders_keep_photographed_areas(category):
    scene,mask,art=fixture()
    q=np.float32([[115,50],[699,50],[699,409],[115,409]])
    print_area=apply(scene,art,mask,'strong')
    rendered=scene.copy();rendered[mask>0]=print_area[mask>0]
    result,qa=apply_scene_daylight(scene,rendered,mask,q,category,profile='dogal')
    assert qa['profile']=='dogal'
    assert np.array_equal(result[mask==0],scene[mask==0])
    assert float(result[150,390].mean())<30
    assert float(result[120,450].mean())>195
