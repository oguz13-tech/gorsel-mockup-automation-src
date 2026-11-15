"""Explicit repair authorization: only source-photo magenta marker can change outside mask."""
import cv2
import numpy as np
import pytest
from MERKEZ.PETEK_V3 import engine
from MERKEZ.PETEK_V3.realism import apply
from MERKEZ.PETEK_V3.petek_visual_pipeline_vnext import (render_petek_visual,
    verify_petek_source_protection)


def test_restore_and_fail_closed_against_nonmagenta_changes():
    from tests.test_vnext_petek_protected_409_original_source_20261101 import sample
    scene,mask,quad,artwork=sample()
    output,qa=render_petek_visual(scene,artwork,quad,mask,1.1163,
        lighting='strong',slot_mode='off',pink_cleanup=True)
    assert qa['source_protection_qa']['authorized_marker_fringe_pixels']==90
    assert np.any(output[381:384,105:135]!=scene[381:384,105:135])
    assert np.array_equal(output[0:25],scene[0:25])
    bad=output.copy();bad[4,4]=(0,0,0)
    with pytest.raises(engine.MaskError,match='PETEK_PREVIEW_PROTECTED_PIXELS_CHANGED'):
        verify_petek_source_protection(scene,bad,mask,quad,pink_cleanup=True)
    with pytest.raises(engine.MaskError,match='PETEK_PREVIEW_PROTECTED_PIXELS_CHANGED'):
        verify_petek_source_protection(scene,output,mask,quad,pink_cleanup=False)


def test_strong_window_shadows_visible_relative_to_natural_without_magenta_bleed():
    scene=np.full((450,650,3),(218,224,233),np.uint8)
    mask=np.zeros((450,650),np.uint8)
    mask[40:415,65:615]=255
    scene[mask>0]=(255,0,255)
    artwork=np.full_like(scene,244)
    natural=apply(scene,artwork,mask,'natural')
    strong=apply(scene,artwork,mask,'strong')
    reg=(mask>0)
    # A real visible difference, not a no-op or an undetectable 1-level change.
    assert np.mean(np.abs(strong[reg].astype(np.int16)-natural[reg].astype(np.int16)))>4
    assert np.all(natural[reg,1]>0)
    assert np.array_equal(scene[:,:65],np.full((450,65,3),(218,224,233),np.uint8))
