"""New operator requirement: two scene shadows, almost all on wall,
with only a small upper PETEK corner touched. Does not rewrite source pixels.
The six non-PETEK categories retain their previous two front-facing bands.
"""
import numpy as np
import cv2
import pytest

from MERKEZ.PETEK_V3 import engine
from MERKEZ.PETEK_V3.realism import _window_shadow_field, _diffuse_window_shadows, apply as apply_realism
from MERKEZ.PETEK_V3.wall_window_shadows_vnext import (
    apply_wall_window_shadows, choose_corner_side, wall_region,
)
from MERKEZ.PETEK_V3.petek_visual_pipeline_vnext import (
    render_petek_visual, verify_petek_source_protection,
)


def scene_fixture():
    h, w = 450, 790
    ys, xs = np.mgrid[:h, :w]
    tone = 2 * np.sin(xs / 47.) + 2 * np.cos(ys / 36.)
    scene = np.uint8(np.clip(np.full((h,w,3),(195,204,213),np.float32)+tone[:,:,None],0,255))
    scene[390:] = (68,92,125)       # real floor
    scene[65:390,80:138] = (210,215,225)  # cabinet white LEFT side
    mask = np.zeros((h,w),np.uint8)
    mask[58:385,138:667] = 255
    scene[mask>0] = (255,0,255)       # printed MAGENTA original
    # Black structural vents must never be painted.
    for xc in range(190,650,33):
        mask[116:340,xc:xc+6]=0
        scene[116:340,xc:xc+6]=(15,18,21)
    quad = np.float32([[138,58],[667,58],[667,384],[138,384]])
    return scene,mask,quad


def test_two_strips_mostly_on_background_graze_only_one_top_corner():
    scene,mask,q=scene_fixture()
    side=choose_corner_side(scene,mask,q)
    assert side=='right'  # more confident wall at right
    shadow=_window_shadow_field(scene.shape,mask,shadow_style='corner',corner_side=side)
    face=(mask>0)&(shadow>.20)
    assert 0.002 < np.count_nonzero(face)/np.count_nonzero(mask>0) < 0.04
    assert np.count_nonzero(face[:,138:330]) == 0
    assert np.count_nonzero(face[150:360,:]) == 0
    assert float(shadow[60,662])>.40
    assert float(shadow[210,380])<.001
    # Both window bars must be present in the visible right-hand wall.
    x=750
    peaks=np.where((shadow[1:-1,x]>shadow[:-2,x]) &
                   (shadow[1:-1,x]>shadow[2:,x]) & (shadow[1:-1,x]>.50))[0]
    assert len(peaks)==2,peaks
    # Scene-wide light field, but the printable part never changes vents.
    print_shadow=_diffuse_window_shadows(scene.shape,mask,.33,
                        shadow_style='corner',corner_side=side)
    assert np.count_nonzero(print_shadow[mask==0])==0
    assert float(np.max(print_shadow[200:350]))<.001


def test_wall_and_vent_protection_and_exact_source_guard():
    scene,mask,q=scene_fixture()
    origin=scene.copy(); approved=mask.copy(); side=choose_corner_side(scene,mask,q)
    wall=wall_region(scene,mask,q,corner_shadow=True)
    assert np.count_nonzero(wall)>5000
    printed=scene.copy(); printed[mask>0]=(224,226,229)
    out,qa=apply_wall_window_shadows(scene,printed,mask,q,shadow_style='corner',corner_side=side)
    assert qa['status']=='APPLIED' and qa['shadow_bands']==2
    assert qa['wall_shadow_pixels']>500
    assert np.array_equal(out[390:],printed[390:])
    assert np.array_equal(out[116:340,190:196],printed[116:340,190:196])
    assert np.array_equal(out[65:380,83:135],printed[65:380,83:135])
    assert verify_petek_source_protection(scene,out,mask,q,
             shadow_style='corner',corner_side=side)['status']=='PASS'
    assert np.array_equal(scene,origin) and np.array_equal(mask,approved)
    tampered=out.copy();tampered[420,40]=(0,0,0)
    with pytest.raises(engine.MaskError,match='PETEK_PREVIEW_PROTECTED_PIXELS_CHANGED'):
        verify_petek_source_protection(scene,tampered,mask,q,
             shadow_style='corner',corner_side=side)


def test_full_petek_pipeline_matches_corner_shadow_not_full_front_overlay():
    scene,mask,q=scene_fixture()
    src=scene.copy();approved=mask.copy()
    art=np.full((260,440,3),250,np.uint8)
    art[115:148,175:230]=(15,17,19)
    image,qa=render_petek_visual(scene,art,q,mask,1.25,
          lighting='strong',slot_mode='off',pink_cleanup=False)
    assert qa['shadow_style']=='corner'
    assert qa['wall_shadow_qa']['shadow_bands']==2
    assert qa['wall_shadow_qa']['wall_shadow_pixels']>500
    assert qa['source_protection_qa']['status']=='PASS'
    assert np.array_equal(scene,src) and np.array_equal(mask,approved)
    assert np.array_equal(image[116:340,190:196],scene[116:340,190:196])


def test_six_category_shadows_keep_original_position_and_white_remains_lifted():
    scene,mask,q=scene_fixture()
    art=np.full_like(scene,250)
    unchanged=apply_realism(scene,art,mask,'strong')
    explicit=apply_realism(scene,art,mask,'strong',shadow_style='classic')
    assert np.array_equal(unchanged,explicit)
    assert _window_shadow_field(scene.shape,mask)[210,350] > .02
    assert np.mean(unchanged[80:110,350])>195
