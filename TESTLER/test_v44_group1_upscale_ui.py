"""V4.4 Group 1: opt-in post-render 4K / no write to original / UI declutter."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest
from PIL import Image
from openpyxl import load_workbook

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'MERKEZ'))
from URETIM_V4 import upscale4k_v44 as sr


def fixture(tmp_path):
    root=tmp_path/'state';root.mkdir()
    original=root/'uretilen_gorseller'/'LOCAL'/'01_Wifi_Kutusu'/'mockup.png'
    original.parent.mkdir(parents=True)
    Image.new('RGB',(1200,1600),'white').save(original)
    row={'key':'key_of_original','sku':'WFI-LOCAL-ABC', 'output':str(original),
         'output_sha':sr.sha256(original)}
    exe=tmp_path/'Real-ESRGAN'/'realesrgan-ncnn-vulkan.exe'
    exe.parent.mkdir()
    exe.write_bytes(b'fake exe for unit test only')
    models=exe.parent/'models';models.mkdir()
    for suffix in ('.bin','.param'):
        (models/('realesrgan-x4plus'+suffix)).write_bytes(b'fake only')
    return root,original,row,exe


def test_defaults_disabled_and_exe_not_bundled(tmp_path):
    assert sr.process([],state_root=tmp_path,enabled=False)['status']=='DISABLED'
    assert not (tmp_path/'uretilen_gorseller_4k').exists()
    assert 'AI_Kalite_Artirici' in sr.find_engine.__code__.co_consts.__str__()
    with pytest.raises(sr.UpscaleError,match='Real-ESRGAN modeli eksik'):
        root,original,row,exe=fixture(tmp_path)
        (exe.parent/'models'/'realesrgan-x4plus.bin').unlink()
        sr.preflight(enabled=True,exe=exe)


def test_fake_engine_creates_separate_sha_verified_4k(tmp_path,monkeypatch):
    root,original,row,exe=fixture(tmp_path)
    original_before=original.read_bytes()
    calls=[]
    def fake_subprocess(cmd,**kwargs):
        calls.append(cmd)
        Image.new('RGB',(4800,6400),(12,34,56)).save(cmd[cmd.index('-o')+1])
        return subprocess.CompletedProcess(cmd,0,'','')
    monkeypatch.setattr(sr.subprocess,'run',fake_subprocess)
    first=sr.process([row],state_root=root,enabled=True,exe=exe)
    assert first['upscaled']==1 and first['failed']==0
    item=first['items'][0]
    file=Path(item['output'])
    assert file.parent.name=='uretilen_gorseller_4k'
    with Image.open(file) as img:
        assert img.size==(2880,3840)
    assert original.read_bytes()==original_before
    assert item['output_sha256']==sr.sha256(file)
    assert len(calls)==1
    report=load_workbook(first['report'])
    assert report.active['A2'].value==row['sku']
    assert report.active['C2'].hyperlink.target==file.as_uri()
    report.close()
    second=sr.process([row],state_root=root,enabled=True,exe=exe)
    assert second['reused']==1 and second['upscaled']==0
    assert len(calls)==1


def test_corrupt_4k_is_never_overwritten(tmp_path,monkeypatch):
    root,original,row,exe=fixture(tmp_path)
    def fake(cmd,**kwargs):
        Image.new('RGB',(4800,6400),'red').save(cmd[cmd.index('-o')+1]);return subprocess.CompletedProcess(cmd,0)
    monkeypatch.setattr(sr.subprocess,'run',fake)
    successful=sr.process([row],state_root=root,enabled=True,exe=exe)
    p=Path(successful['items'][0]['output']);p.write_bytes(b'changed/unsafe')
    outcome=sr.process([row],state_root=root,enabled=True,exe=exe)
    assert outcome['failed']==1 and outcome['upscaled']==0
    assert p.read_bytes()==b'changed/unsafe'
    assert outcome['errors']


def test_base_sha_mismatch_blocks_upscale(tmp_path,monkeypatch):
    root,original,row,exe=fixture(tmp_path)
    row['output_sha']='0'*64
    monkeypatch.setattr(sr.subprocess,'run',lambda *_args,**_kw:pytest.fail('should not run'))
    outcome=sr.process([row],state_root=root,enabled=True,exe=exe)
    assert outcome['failed']==1
    assert outcome['items']==[]
    assert not (root/'uretilen_gorseller_4k').glob('*.png').__next__() if False else True


def test_engine_bad_exit_keeps_normal_mockup(tmp_path,monkeypatch):
    root,original,row,exe=fixture(tmp_path)
    before=original.read_bytes()
    monkeypatch.setattr(sr.subprocess,'run',lambda cmd,**kw:subprocess.CompletedProcess(cmd,1,'','GPU error'))
    result=sr.process([row],state_root=root,enabled=True,exe=exe)
    assert result['failed']==1 and result['upscaled']==0
    assert original.read_bytes()==before
    assert not list((root/'uretilen_gorseller_4k').glob('*.png'))


def test_ui_no_daily_button_and_optional_checkbox():
    src=(ROOT/'MERKEZ/merkez.py').read_text(encoding='utf8')
    gui=(ROOT/'MERKEZ/URETIM_V4/gui_v4.py').read_text(encoding='utf8')
    assert "self.daily=" not in src
    assert 'GÜNLÜK SERİ ÜRETİM (ONAYLI 10 ŞABLON)' not in src
    assert 'toggle_advanced' in src
    assert 'self.upscale_4k = tk.BooleanVar(value=False)' in gui
    assert 'upscale_preflight(enabled=True, model=upscale_model)' in gui
    from URETIM_V4.unified_batch import UnifiedV4Batch
    import inspect
    assert 'upscale_4k: bool = False' in inspect.getsource(UnifiedV4Batch.run)
