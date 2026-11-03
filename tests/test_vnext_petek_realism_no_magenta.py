"""Safety regression tests: magenta screen must not make white artwork pink."""
from pathlib import Path
import sys
import numpy as np
import cv2

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'MERKEZ'))
from PETEK_V3.realism import apply,_neutral_white,_magenta_pixels,light_map
from PETEK_V3.engine import composite


def _fixture():
    h,w=240,400
    scene=np.empty((h,w,3),np.uint8)
    scene[:]=(205,216,223)  # original warm white body in BGR
    scene[:,85:360]=(255,0,255)  # saturated chroma-key magenta panel
    mask=np.zeros((h,w),np.uint8)
    mask[24:212,87:358]=255
    # Actual ventilator holes are excluded from printable mask.
    for x in range(110,345,19):mask[55:181,x:x+3]=0
    artwork=np.full_like(scene,255)
    artwork[80:180,235:239]=(35,35,35)
    return scene,artwork,mask


def test_neutral_white_excludes_chroma_reference():
    scene,art,mask=_fixture()
    ref,available=_neutral_white(scene,mask)
    assert available
    assert max(ref)-min(ref)<.10,ref
    assert not _magenta_pixels(scene[:,:85]).any()
    light=light_map(scene,mask)
    assert np.max(light[90:160,150:180])-np.min(light[90:160,150:180])<.15


def test_pure_white_print_does_not_pink_and_protected_pixels_stay_exact():
    scene,art,mask=_fixture()
    quad=np.float32([[86,24],[358,24],[358,211],[86,211]])
    result,meta=composite(scene,art,mask,quad,preserve_shading=True,
                           lighting='natural',edge_feather_px=0)
    assert np.array_equal(result[mask==0],scene[mask==0])
    sample=result[120,180].astype(int)
    assert sample.max()-sample.min()<35,sample
    assert np.max(sample)<245,sample
    assert np.min(sample)>160,sample
    assert not _magenta_pixels(result[mask>0].reshape(-1,1,3)).any()
    assert result[115,125].max()<245


def test_window_and_leaf_shadows_are_visible_without_blurring_artwork():
    scene,art,mask=_fixture()
    lit=apply(scene,art,mask,mode='natural')
    white=lit[80:180,145:235].astype(np.int16)
    assert white.std()>1.0,white.std()
    assert lit[90,237].mean()<90 # ink detail stays dark/sharp
    assert np.array_equal(apply(scene,art,mask,mode='off'),art)


def test_magenta_edge_cannot_bleed_into_white_at_mask_transition():
    scene,art,mask=_fixture()
    lit=apply(scene,art,mask,'natural')
    for y,x in [(120,87),(120,88),(120,95),(120,355)]:
        pixel=lit[y,x].astype(int)
        assert max(pixel)-min(pixel)<42,((y,x),pixel)
        assert pixel[1]>150
