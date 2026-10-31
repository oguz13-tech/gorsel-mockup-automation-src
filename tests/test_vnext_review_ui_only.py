"""Review layout stores UI preferences separately from production assets.

The module's pure functions are tested without a live Flask web server; the
HTTP route and Windows UAT gates remain separate acceptance requirements.
"""
import importlib.util
import json
import os
from pathlib import Path
import sys
import types
import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT/'SABLON_V2_MIMARI/core/review_layout_vnext.py'


def backend(monkeypatch):
    stub=types.ModuleType('flask')
    class Blueprint:
        def __init__(self,*args,**kwargs):pass
        def get(self, route):return lambda handler:handler
        def post(self, route):return lambda handler:handler
    stub.Blueprint=Blueprint
    stub.jsonify=lambda payload:payload
    stub.request=types.SimpleNamespace(get_json=lambda silent:None)
    monkeypatch.setitem(sys.modules,'flask',stub)
    spec=importlib.util.spec_from_file_location('review_layout_ui_only_test',MODULE)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_default_theme_contrast_and_review_sections(monkeypatch):
    m=backend(monkeypatch)
    data=m.validate(m.default())
    assert data['colors']['accent']=='#7A4DFA'
    assert m.contrast(data['colors']['text'],data['colors']['panel'])>=4.5
    assert 'petek-approval' in m.PINNED['petek']
    assert data['tabs']['review']==['Tümü']
    assert data['paneOrder']=='photo-first'


@pytest.mark.parametrize('change',[
    {'widths':{'left':0,'right':330}},
    {'colors':{'text':'#1D2638'}},
    {'colors':{'accent':'#FFFFFF'}},
    {'tabs':{'petek':['Tümü','X','X']}},
    {'assignments':{'petek':{'petek-approval':'Maske'}},
     'tabs':{'petek':['Tümü','Maske']}},
    {'order':{'review':['review-quick']}},
    {'order':{'review':[{'bad': 'input'}] + list(range(5))}},
    {'paneOrder':'invalid'},
])
def test_reject_unsafe_layout(monkeypatch,change):
    m=backend(monkeypatch)
    candidate=m.default()
    for key,value in change.items():
        if isinstance(value,dict):candidate[key].update(value)
        else:candidate[key]=value
    with pytest.raises(ValueError):m.validate(candidate)


def test_json_only_save_backup_and_corruption_recovery(tmp_path,monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA',str(tmp_path/'ui_root'))
    m=backend(monkeypatch)
    user_data=tmp_path/'production'/'approved_mask.png'
    user_data.parent.mkdir(parents=True)
    user_data.write_bytes(b'approved-mask-retained')
    cfg=m.default()
    cfg['widths']['left']=350
    m.save(cfg)
    assert m.path().is_file()
    assert m.path().parent==tmp_path/'ui_root/GorselMockup/UI_VNEXT'
    assert m.load()['widths']['left']==350
    cfg['widths']['left']=260
    m.save(cfg)
    assert m.load()['widths']['left']==260
    prior=json.loads(m.path().with_suffix('.backup.json').read_text(encoding='utf-8'))
    assert prior['widths']['left']==350
    m.path().write_text('{BROKEN',encoding='utf-8')
    assert m.load()['widths']['left']==260  # last-good copy
    assert user_data.read_bytes()==b'approved-mask-retained'


def test_symlink_prevents_write(tmp_path,monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA',str(tmp_path))
    m=backend(monkeypatch)
    p=m.path()
    p.parent.mkdir(parents=True)
    forbidden=tmp_path/'unrelated.txt';forbidden.write_text('SENSITIVE')
    try:p.symlink_to(forbidden)
    except OSError:pytest.skip('Symlinks not available')
    with pytest.raises(OSError,match='SYMLINK'):
        m.save(m.default())
    assert forbidden.read_text()=='SENSITIVE'


def test_layout_no_mask_or_production_imports():
    source=MODULE.read_text(encoding='utf-8')
    assert 'petek_web_v477' not in source
    assert 'sqlite3' not in source
    assert 'mask_registry' not in source
    assert 'MOCKUP_RUNTIME_WORKSPACE' not in source
    assert 'os.replace' in source
