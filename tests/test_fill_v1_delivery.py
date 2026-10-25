"""Regression: accepted mismatches are cropped, never stretched or gray-padded."""
import sys
from pathlib import Path
import numpy as np
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'99_SISTEM_MOTORLARI_VE_KODLAR'))
from SISTEM_MOTORU.pc_master_factory import MockupRenderer

@pytest.mark.parametrize('shape,ratio', [((100,140,3),4/3),((110,140,3),4/3),((140,100,3),3/4)])
def test_fill_contains_only_original_center_pixels(shape,ratio):
    source=np.arange(np.prod(shape),dtype=np.uint8).reshape(shape)
    before=source.copy();out=MockupRenderer.fit_artwork_fill(source,ratio)
    y=(shape[0]-out.shape[0])//2;x=(shape[1]-out.shape[1])//2
    np.testing.assert_array_equal(out,source[y:y+out.shape[0],x:x+out.shape[1]])
    np.testing.assert_array_equal(source,before)
    assert abs(out.shape[1]/out.shape[0]-ratio)<=1/min(out.shape[:2])
    assert not np.shares_memory(out,source)

@pytest.mark.parametrize('ratio',[0,-1,float('nan'),float('inf'),None,3])
def test_invalid_or_excessive_mismatch_is_blocked(ratio):
    with pytest.raises(ValueError):MockupRenderer.fit_artwork_fill(np.zeros((100,140,3),dtype=np.uint8),ratio)
