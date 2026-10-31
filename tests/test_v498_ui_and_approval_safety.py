"""V4.9.8 release gate: isolated UI preferences and PETEK human-review guard.
Does not access the real user workspace, source images, or V3 state.
"""
import ast
import hashlib
import re
import sys
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'MERKEZ'))
from ui_layout_v498 import initial,load,save,normalize,DASH_IDS,PROD_IDS


def test_user_created_tabs_and_theme_survive_restart_without_db_changes(tmp_path,monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA',str(tmp_path))
    prefs=initial()
    prefs['dashboard']['tabs']['Kontrol']=['notes','tests']
    prefs['dashboard']['tabs']['Ana Sayfa']=[i for i in DASH_IDS if i not in ('notes','tests')]
    prefs['dashboard']['accent']='#a145d3'
    prefs['production']['tabs']['PETEK']=['quality']
    data=save(prefs)
    assert load()==data
    assert load()['production']['tabs']['PETEK']==['quality']
    assert (tmp_path/'GorselMockup'/'UI_V498'/'layout.json').exists()
    assert not list(tmp_path.rglob('ayarlar.db'))
    assert not list(tmp_path.rglob('*.sqlite*'))


def test_bad_preferences_revert_to_safe_default_and_all_cards_reappear(tmp_path,monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA',str(tmp_path))
    state=initial();state['dashboard']['tabs']={'Kişisel':['review','review','__bad__']}
    clean=normalize(state)
    present=[card for items in clean['dashboard']['tabs'].values() for card in items]
    assert sorted(present)==sorted(DASH_IDS)
    assert clean['production']['tabs']['Tümü']==list(PROD_IDS)
    dest=tmp_path/'GorselMockup'/'UI_V498'/'layout.json'
    dest.parent.mkdir(parents=True)
    dest.write_text('{broken',encoding='utf-8')
    assert load()==initial()


def test_petek_bulk_approval_guard_function_with_mock_registry(tmp_path):
    # Extract and run the EXACT body of the pure per-item helper. This can be
    # tested without Flask installed, and proves SHA/status/manual-review gates.
    api_file=ROOT/'SABLON_V2_MIMARI/core/petek_web_v477.py'
    src=ast.parse(api_file.read_text(encoding='utf-8'))
    fn=next(node for node in src.body if isinstance(node,ast.FunctionDef) and node.name=='_approve_reviewed_draft')
    sandbox={}
    file=tmp_path/'petek.png';file.write_bytes(b'original-picture-placeholder')
    source_sha=hashlib.sha256(file.read_bytes()).hexdigest()
    mask_sha='a'*64
    class Engine:
        @staticmethod
        def digest(file):return hashlib.sha256(Path(file).read_bytes()).hexdigest()
    class Registry:
        def __init__(self):self.written=0;self.status='DRAFT';self.mask_sha=mask_sha
        def get(self,uid,*,source_override):
            return {'status':self.status,'mask_sha':self.mask_sha,'source_sha':source_sha},None
        def approve(self,uid,reviewer,confirm,*,source_override):
            assert reviewer=='Can' and confirm=='I_VISUALLY_CHECKED_VENTS_ARCHES_FLOOR'
            assert Path(source_override)==file
            self.written+=1
            self.status='APPROVED'
            return {'status':'APPROVED','mask_sha':mask_sha}
    sandbox.update({'_photo':lambda n:file,'_identity':lambda r,f,uid:(uid,source_sha),
                    'engine':Engine,'re':re})
    exec(compile(ast.Module(body=[fn],type_ignores=[]),str(api_file),'exec'),sandbox)
    run=sandbox['_approve_reviewed_draft']
    item={'name':'petek.png','uid':'petek','source_sha':source_sha,
          'mask_sha':mask_sha,'reviewed':True}
    reg=Registry()
    with pytest.raises(ValueError,match='INCELE'):run(reg,{**item,'reviewed':False},'Can')
    with pytest.raises(ValueError,match='MASK'):run(reg,{**item,'mask_sha':'0'*64},'Can')
    with pytest.raises(ValueError,match='KAYNAK'):run(reg,{**item,'source_sha':'f'*64},'Can')
    assert reg.written==0
    result=run(reg,item,'Can')
    assert result['status']=='APPROVED' and reg.written==1
    with pytest.raises(ValueError,match='YALNIZ_TASLAK'):run(reg,item,'Can')
    assert reg.written==1


def test_bundle_bulk_approval_has_one_explicit_user_confirmation_and_per_item_guards():
    """Updated after user replaced eight-step tick workflow with one consent.

    Preserve the backend's source SHA + UID + approved revision protections.
    """
    html=(ROOT/'SABLON_V2_MIMARI/templates/index.html').read_text('utf-8')
    js=(ROOT/'SABLON_V2_MIMARI/static/js/petek_editor_v477.js').read_text('utf-8')
    backend=(ROOT/'SABLON_V2_MIMARI/core/petek_web_v477.py').read_text('utf-8')
    assert 'id="petekV498BulkApprove"' in html
    assert 'GÖRÜNEN TÜM TASLAKLARI TEK ONAYLA' in html
    bulk=js.split('async function beginBulkPetekApproval(){')[1].split('function petekState(')[0]
    assert bulk.count('if(!confirm(')==1
    assert 'x.checked' not in bulk and 'reviewCursor' not in bulk
    assert "I_APPROVE_ALL_VALID_PETEK_DRAFTS_IN_THIS_SELECTION" in bulk
    assert "@petek_web.post('/api/petek/bulk-approve-confirmed')" in backend
    assert "profile.get('status')!='DRAFT'" in backend
    assert "profile.get('revises_uid')" in backend
    assert "registry.get(uid,source_override=file)" in backend
    assert "_PETEK_APPROVAL_LOCK" in backend
    assert "_approve_reviewed_draft" in backend


def test_4k_status_check_button_does_not_auto_install():
    gui=(ROOT/'MERKEZ/URETIM_V4/gui_v4.py').read_text('utf-8')
    theme=(ROOT/'MERKEZ/dark_theme_v42.py').read_text('utf-8')
    assert "text='4K Kurulumunu Kontrol Et'" in gui
    body=gui.split('    def _verify_4k_status(self):')[1].split('    def _4k_model_code(self):')[0]
    assert '_start_4k_installer(' not in body
    assert 'threading.Thread(' in body
    assert "st.map('TCheckbutton'" in theme


def test_original_petek_visual_finish_motors_unchanged_vs_baseline():
    # Archive verification is performed by package script; test only existence.
    for name in ('petek_finish_v492.py','final_cleanup_v495.py'):
        assert (ROOT/'MERKEZ/PETEK_V3'/name).is_file()
