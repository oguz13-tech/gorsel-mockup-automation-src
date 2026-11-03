from pathlib import Path
import sys
import numpy as np
import cv2

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'MERKEZ'))
from PETEK_V3.realism import apply, _magenta_pixels
from PETEK_V3.engine import composite


def fixture():
    h,w=240,400
    scene=np.empty((h,w,3),np.uint8)
    scene[:]=(207,216,228)
    scene[:,80:365]=(255,0,255)
    mask=np.zeros((h,w),np.uint8)
    mask[25:210,82:363]=255
    for x in range(110,345,18):mask[60:173,x:x+4]=0
    art=np.full_like(scene,255)
    art[70:150,225:227]=(48,44,39)
    return scene,art,mask


def test_bat_path_contains_real_backslash_not_vertical_tab():
    bat=(ROOT/'PETEK_DOGAL_BEYAZ_DOGRULA.bat').read_bytes()
    assert b'scripts\\v4102_verify_package.py' in bat
    assert all(c not in bat for c in (b'\x0b',b'\x08',b'\x00'))
    for p in ROOT.glob('*.bat'):
        assert all(c not in p.read_bytes() for c in (b'\x0b',b'\x08',b'\x00')), p


def test_belirgin_no_magenta_or_damage_to_protected_pixels():
    scene,art,mask=fixture()
    quad=np.float32([[82,25],[362,25],[362,209],[82,209]])
    result,report=composite(scene,art,mask,quad,lighting='strong',edge_feather_px=0)
    assert np.array_equal(result[mask==0],scene[mask==0])
    assert not _magenta_pixels(result[mask>0].reshape(-1,1,3)).any()
    assert result[110,190].max()<245
    strong=apply(scene,art,mask,'strong')
    natural=apply(scene,art,mask,'natural')
    # The stronger profile has a measurable, non-destructive shadow pattern.
    assert float(strong[mask>0].astype(float).std())>2
    assert np.any(strong!=natural)


def test_selected_petek_profile_is_wired_only_through_petek_branch():
    gui=(ROOT/'MERKEZ'/'URETIM_V4'/'gui_v4.py').read_text('utf-8')
    batch=(ROOT/'MERKEZ'/'URETIM_V4'/'unified_batch.py').read_text('utf-8')
    assert "self.petek_nature_profile=tk.StringVar(value='Belirgin')" in gui
    assert "petek_realism_profile=petek_realism_profile" in gui
    assert "petek_realism_profile: str = 'dogal'" in batch
    assert "lighting=('strong' if lighting != 'off' and petek_realism_profile == 'belirgin' else lighting)" in batch
    assert 'lighting=lighting,\n                                    category=cat' in batch
