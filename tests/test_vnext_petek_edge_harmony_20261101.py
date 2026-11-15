"""Optical edge continuity without changing confirmed PETEK geometry/pink code."""
import numpy as np
from MERKEZ.PETEK_V3.edge_harmony_vnext import harmonize_petek_edges
from MERKEZ.PETEK_V3.engine import composite
from MERKEZ.PETEK_V3.realism import apply


def fixture():
    h,w=380,610
    scene=np.full((h,w,3),(207,217,225),np.uint8)
    mask=np.zeros((h,w),np.uint8)
    mask[35:340,102:565]=255
    scene[35:340,102:565]=(255,0,255)
    # Actual source-magenta may be present at an external seam.
    scene[35:340,101]=(255,0,255)
    for x in range(152,535,29):mask[100:275,x:x+4]=0
    art=np.full_like(scene,248)
    art[140:265,265:301]=(16,17,18)  # printed dark calligraphy
    quad=np.float32([[102,35],[565,35],[565,339],[102,339]])
    return scene,mask,art,quad


def test_subtle_left_front_seam_matches_real_white_without_pink_or_bleed():
    scene,mask,art,q=fixture()
    lit=apply(scene,art,mask,'natural')
    fixed=harmonize_petek_edges(scene,lit,mask,q)
    assert np.array_equal(fixed[mask==0],lit[mask==0])
    assert np.array_equal(scene[150,120],np.array([255,0,255],np.uint8))
    assert np.max(np.abs(fixed.astype(np.int16)-lit.astype(np.int16)))<=26
    # Effect on white seam where photographed left panel is available.
    assert not np.array_equal(fixed[185,104],lit[185,104])
    # Middle of the printable panel remains unchanged (no full-face blur).
    assert np.array_equal(fixed[185,345],lit[185,345])
    assert np.array_equal(fixed[185,281],lit[185,281])
    px=fixed[185,104].astype(int)
    assert not (px[0]>px[1]+35 and px[2]>px[1]+35)


def test_quad_pink_physical_holes_and_original_photo_immutable():
    scene,mask,art,q=fixture()
    scene_copy=scene.copy();mask_copy=mask.copy()
    image,meta=composite(scene,art,mask,q,lighting='natural',edge_feather_px=0.)
    assert np.array_equal(scene,scene_copy)
    assert np.array_equal(mask,mask_copy)
    assert np.array_equal(image[mask==0],scene[mask==0])
    assert image[160,153].tolist()==scene[160,153].tolist()
    assert image[185,280].max()<70
    assert meta['source_pixels_unchanged']


def test_off_mode_unchanged_for_true_before_comparison():
    scene,mask,art,q=fixture()
    after=harmonize_petek_edges(scene,art,mask,q)
    before,_=composite(scene,art,mask,q,lighting='off',edge_feather_px=0.)
    assert np.array_equal(before[mask>0],art[mask>0])
    assert not np.array_equal(after[190,104],art[190,104])


def test_no_white_furniture_sample_no_invented_tint():
    scene,mask,art,q=fixture()
    scene[mask==0]=(42,90,20)  # no photographed white side
    lit=apply(scene,art,mask,'natural')
    fixed=harmonize_petek_edges(scene,lit,mask,q)
    assert np.array_equal(fixed[mask==0],lit[mask==0])
    assert np.max(np.abs(fixed.astype(np.int16)-lit.astype(np.int16)))<=6
