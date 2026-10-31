"""V4.9.9: test isolated PETEK approval revisions / UI safety without Windows user data."""
import ast
import hashlib
from pathlib import Path
import pytest
from TESTLER.test_petek_windows_v3 import scene_fixture
from MERKEZ.PETEK_V3 import engine
from MERKEZ.PETEK_V3.registry import Registry

ROOT=Path(__file__).resolve().parents[1]
UI=ROOT/'SABLON_V2_MIMARI'

def test_approved_revision_active_switch_preserves_old_source_mask(tmp_path,scene_fixture):
    source,_,_,quad,mask=scene_fixture
    reg=Registry(tmp_path/'state')
    old=reg.save('PetekOriginal_001',source,quad,mask,1.1163)
    reg.approve('PetekOriginal_001','Can','I_VISUALLY_CHECKED_VENTS_ARCHES_FLOOR')
    original_profile=(reg.profiles/'PetekOriginal_001.json').read_bytes()
    original_mask=(reg.masks/(old['mask_sha']+'.png')).read_bytes()
    reg.save('PetekOriginal_001_r2',source,quad,mask,1.1163)
    reg.link_draft_revision('PetekOriginal_001','PetekOriginal_001_r2')
    draft,_=reg.get('PetekOriginal_001_r2')
    assert draft['base_uid']=='PetekOriginal_001'
    # Re-saving after the user repaints must keep the parent link.
    reg.save('PetekOriginal_001_r2',source,quad,mask,1.1163)
    assert reg.get('PetekOriginal_001_r2')[0]['revises_uid']=='PetekOriginal_001'
    assert reg.is_current('PetekOriginal_001')
    with pytest.raises(engine.MaskError,match='CONFIRM'):
        reg.activate_revision('PetekOriginal_001','PetekOriginal_001_r2','NO')
    reg.approve('PetekOriginal_001_r2','Can','I_VISUALLY_CHECKED_VENTS_ARCHES_FLOOR')
    assert not reg.is_current('PetekOriginal_001_r2')  # Not auto-published
    new=reg.activate_revision('PetekOriginal_001','PetekOriginal_001_r2',
                              'ACTIVATE_REVISED_PETEK_AND_KEEP_OLD')
    assert new['previous_uid']=='PetekOriginal_001'
    assert reg.is_current('PetekOriginal_001_r2')
    assert not reg.is_current('PetekOriginal_001')
    assert (reg.profiles/'PetekOriginal_001.json').read_bytes()==original_profile
    assert (reg.masks/(old['mask_sha']+'.png')).read_bytes()==original_mask
    assert reg.get('PetekOriginal_001',require_approved=True)[0]['mask_sha']==old['mask_sha']
    entries={x['uid']:x['is_current'] for x in reg.list()}
    assert entries['PetekOriginal_001'] is False and entries['PetekOriginal_001_r2'] is True
    reg.restore_revision('PetekOriginal_001','PetekOriginal_001',
                         'RESTORE_PREVIOUS_APPROVED_PETEK')
    assert reg.is_current('PetekOriginal_001')
    assert not reg.is_current('PetekOriginal_001_r2')


def test_revision_rejects_source_conflict_and_bad_active_index(tmp_path,scene_fixture):
    source,_,_,quad,mask=scene_fixture
    reg=Registry(tmp_path/'state')
    reg.save('PetekOriginal_001',source,quad,mask,1.1163)
    reg.approve('PetekOriginal_001','Can','I_VISUALLY_CHECKED_VENTS_ARCHES_FLOOR')
    with pytest.raises(engine.MaskError):
        reg.link_draft_revision('PetekOriginal_001','PetekOriginal_001_r2')
    idx=reg.root/'active_revisions.json'
    idx.write_text('{bad-json',encoding='utf8')
    with pytest.raises((ValueError,engine.MaskError)):
        reg.list()  # fail closed; never silently select stale masks


def test_v499_bulk_no_tick_no_eight_user_approval_and_fixed_list_width():
    js=(UI/'static/js/petek_editor_v477.js').read_text('utf-8')
    html=(UI/'templates/index.html').read_text('utf-8')
    css=(UI/'static/css/v499_anthracite.css').read_text('utf-8')
    be=(UI/'core/petek_web_v477.py').read_text('utf-8')
    fn=js[js.index('async function beginBulkPetekApproval(){'):js.index('function petekState(')]
    assert 'visiblePetekItems().filter(x=>x.status===\'DRAFT\'' in fn
    assert fn.count('if(!confirm(')==1
    assert 'x.checked' not in fn and 'reviewCursor' not in fn
    assert 'I_APPROVE_ALL_VALID_PETEK_DRAFTS_IN_THIS_SELECTION' in fn
    assert 'bulk-approve-confirmed' in fn and "offset+=8" in fn
    assert 'width:17px!important' in (UI/'static/css/v4101_unified.css').read_text('utf8')
    assert 'Tikleme Yok' in html and 'petekV498ReviewDialog' not in html and 'showNextReviewPage' not in js
    assert "@petek_web.post('/api/petek/bulk-approve-confirmed')" in be
    assert "profile.get('status')!='DRAFT'" in be
    assert "profile.get('revises_uid')" in be  # revised approved profile not bulk activated by accident


def test_v499_active_category_keyboard_and_eraser_not_photo_delete():
    main=(UI/'static/js/main.js').read_text('utf8')
    petek=(UI/'static/js/petek_editor_v477.js').read_text('utf8')
    assert 'PetekV477.isActive()' in main
    assert 'stopImmediatePropagation()' in petek
    assert 'erasewood' in petek and 'data-petek-mode="erasewood"' in (UI/'templates/index.html').read_text('utf8')
    assert "s.mode==='wood'||s.mode==='protect'||s.mode==='erasewood'" in petek
    assert "s.mode==='wood'?'#ffffff':'#000000'" in petek


def test_v499_no_production_motor_modified():
    # Independent integration scripts target the registry + GUI presentation only.
    for name in ('petek_finish_v492.py','final_cleanup_v495.py'):
        assert (ROOT/'MERKEZ/PETEK_V3'/name).is_file()
