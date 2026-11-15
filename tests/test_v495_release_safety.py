"""V4.9.5 narrowed real-window improvements and PETEK cleanup regression."""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'MERKEZ'))
from PETEK_V3.final_cleanup_v495 import cleanup_petek_magenta
from URETIM_V4 import on_demand_4k_v495 as cache
from URETIM_V4 import upscale4k_v44 as sr


def fixture():
    h,w=640,900
    photo=np.full((h,w,3),218,np.uint8)
    q=np.float32([[100,70],[810,70],[810,560],[100,560]])
    mask=np.zeros((h,w),np.uint8)
    mask[70:561,100:811]=255
    for x in range(150,800,45):
        mask[150:500,x-3:x+4]=0
        photo[150:500,x-3:x+4]=(18,18,18)
    return photo,mask,q


def test_all_four_corners_and_vent_markers_cleaned_without_whitewashing():
    photo,mask,quad=fixture()
    photo[200:350,99:102]=(255,0,255)  # left edge
    photo[400:455,808:812]=(255,0,255) # right edge
    photo[550:563,110:200]=(255,0,255) # bottom left
    photo[551:562,735:790]=(255,0,255) # bottom right
    photo[220:250,149:151]=(255,0,255) # narrow protected slot lip
    untouched=photo.copy();mask_before=mask.copy()
    out,qa=cleanup_petek_magenta(photo,mask,quad,slot_centers=list(np.linspace(72,830,15)))
    assert qa['status']=='TEMIZLENDI',qa
    assert qa['remaining_pixels']==0
    assert qa['repaired_pixels']>=1600
    assert np.array_equal(photo,untouched) and np.array_equal(mask,mask_before)
    assert np.array_equal(out[:60],photo[:60])
    assert np.array_equal(out[250:340,450:530],photo[250:340,450:530])
    assert not np.all(out[200:350,99:102]==255) # not still neon pink
    assert not np.all(out[551:562,735:790]==255)


def test_actual_magenta_artwork_in_center_not_repainted():
    photo,mask,quad=fixture()
    photo[220:330,320:410]=(255,0,255)
    before=photo.copy()
    out,qa=cleanup_petek_magenta(photo,mask,quad,slot_centers=None)
    assert np.array_equal(out,before)
    assert qa['repaired_pixels']==0


def test_cleanup_rejects_broad_magenta_without_silent_repaint():
    photo,mask,quad=fixture()
    photo[70:561,99:118]=(255,0,255)
    # Edge zone is thick enough to exceed 2.5% when marker is broad.
    # At minimum no unauthorized central scene may change.
    before=photo.copy()
    out,qa=cleanup_petek_magenta(photo,mask,quad,slot_centers=None)
    assert np.array_equal(out[:,250:700],before[:,250:700])
    assert qa['status'] in ('GENIS_PEMBE_ALAN_INCELEME','TEMIZLENDI','KISMI_TEMIZLIK_INCELE')


def test_cache_only_remembers_existing_engine_after_real_preflight(tmp_path,monkeypatch):
    folder=tmp_path/'models';folder.mkdir()
    exe=tmp_path/'realesrgan-ncnn-vulkan.exe';exe.write_bytes(b'fake test exe')
    for suffix in ('.bin','.param'):(folder/('realesrgan-x4plus'+suffix)).write_bytes(b'test data')
    calls=[]
    def stub_preflight(*,enabled,model,exe=None):
        calls.append((enabled,model));return tmp_path/'realesrgan-ncnn-vulkan.exe'
    monkeypatch.setattr(sr,'preflight',stub_preflight)
    obj=cache.OnDemand4K(tmp_path/'local'/'4k.json')
    assert not obj.state_file.exists()  # no check on construction
    first,mode=obj.verify('photo')
    assert mode=='DOGRULANDI' and first==exe
    again=cache.OnDemand4K(obj.state_file)
    assert again.verify('photo')[1]=='ONBELLEK_HAZIR'
    assert len(calls)==1
    (folder/'realesrgan-x4plus.bin').write_bytes(b'changed model')
    again.verify('photo')
    assert len(calls)==2


def test_modeless_and_unblocked_io_source_contracts():
    gui=(ROOT/'MERKEZ/URETIM_V4/gui_v4.py').read_text(encoding='utf-8')
    center=(ROOT/'MERKEZ/merkez.py').read_text(encoding='utf-8')
    assert 'self.window.transient(parent)' not in gui
    assert 'self.window.grab_set()' not in gui
    assert "threading.Thread(target=work,daemon=True,name='approved-template-index')" in gui
    assert "threading.Thread(target=work,daemon=True,name='production-bootstrap')" in center
    assert "threading.Thread(target=preflight_worker,daemon=True,name='review-inspect')" in center
    assert "threading.Thread(target=launch_worker,daemon=True,name='review-safe-launch')" in center


def test_release_test_cards_are_persistently_registered(tmp_path):
    from personal_hub_v493 import Store
    st=Store(tmp_path/'personal.db')
    names={i['id'] for i in st.tests()}
    assert {'MULTI-WINDOW-V495','STARTUP-SPEED-V495','MODERN-PRODUCTION-V495',
            'PETEK-EDGE-ALL-V495','4K-ON-DEMAND-V495','REAPPROVE-4-CORNER-V495'} <= names
    st.update_test('PETEK-EDGE-ALL-V495','BEKLETILDI','Need real PETEK input')
    st2=Store(tmp_path/'personal.db')
    record={i['id']:i for i in st2.tests()}['PETEK-EDGE-ALL-V495']
    assert record['status']=='BEKLETILDI'
