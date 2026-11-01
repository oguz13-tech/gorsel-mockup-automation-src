"""Reproduce a valid store assignment rejected by stale GUI production selection."""
from pathlib import Path
import hashlib
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'MERKEZ'))
from URETIM_V4.store_profiles_v47 import StoreProfiles, key_for
from URETIM_V4.store_selection_diagnostic_vnext import (compare_store_selection,
                                                        format_store_diagnostic)


def t(uid, sha='a', category='06_Petek_Kapama'):
    return {'uid': uid, 'source_sha': sha * 64, 'category': category}


def test_reproduces_user_error_when_store_has_one_but_production_keeps_other(tmp_path):
    mgr=StoreProfiles(tmp_path)
    a,b=t('correct', 'a'),t('previously_selected','b')
    mgr.add_store('wudie')
    mgr.assign('wudie',[a],all_approved=[a,b])
    with pytest.raises(ValueError,match='Seçili şablonlar mağazanın özel grubunda yok'):
        mgr.plan(['wudie'],[a,b],selected_uids=['previously_selected'])
    found=compare_store_selection(['wudie'], ['previously_selected'],[a,b],mgr.load())
    assert not found['ready']
    assert found['details'][0]['status']=='NO_COMMON_UID'
    text=format_store_diagnostic(found,state_path=mgr.path)
    assert 'correct' in text and 'previously_selected' in text
    assert 'Mağazaya Atananları Üretime Seç' in text


def test_one_match_means_the_production_plan_can_run(tmp_path):
    mgr=StoreProfiles(tmp_path)
    a,b=t('correct','a'),t('old','b')
    mgr.add_store('wudie');mgr.assign('wudie',[a],all_approved=[a,b])
    diagnostic=compare_store_selection(['wudie'],['correct'],[a,b],mgr.load())
    assert diagnostic['ready']
    assert diagnostic['union_uids']==['correct']
    plan=mgr.plan(['wudie'],[a,b],selected_uids=['correct'])
    assert len(plan)==1 and plan[0][1]==[a]


def test_changed_approval_source_sha_does_not_auto_rekey(tmp_path):
    mgr=StoreProfiles(tmp_path);mgr.add_store('wudie')
    old,new=t('correct','a'),t('correct','b')
    mgr.assign('wudie',[old])
    original=mgr.path.read_bytes()
    r=compare_store_selection(['wudie'],['correct'],[new],mgr.load())
    assert not r['ready']
    assert r['details'][0]['status']=='STALE_APPROVAL_OR_SHA'
    assert 'STALE' in format_store_diagnostic(r)
    assert mgr.path.read_bytes()==original


def test_bulk_reassignment_does_not_automatically_refresh_production_selection(tmp_path):
    mgr=StoreProfiles(tmp_path);mgr.add_store('wudie')
    a,b=t('a','a'),t('b','b')
    mgr.assign('wudie',[a]);mgr.unassign_keys('wudie',[key_for(a)])
    mgr.assign('wudie',[b])
    # Existing GUI selection can still be old 'a', independently of store config.
    r=compare_store_selection(['wudie'],['a'],[a,b],mgr.load())
    assert r['details'][0]['status']=='NO_COMMON_UID'
    assert r['union_uids']==['b']


def test_invalid_or_missing_store_diagnosed_without_mutations(tmp_path):
    mgr=StoreProfiles(tmp_path);mgr.add_store('wudie')
    a=t('a')
    prior=hashlib.sha256(mgr.path.read_bytes()).hexdigest()
    r=compare_store_selection(['wudie','other'],['a'],[a],mgr.load())
    assert [x['status'] for x in r['details']]==['NO_ASSIGNMENT','STORE_NOT_FOUND']
    assert hashlib.sha256(mgr.path.read_bytes()).hexdigest()==prior


def test_two_stores_require_overlap_in_each_store(tmp_path):
    mgr=StoreProfiles(tmp_path);mgr.add_store('AA');mgr.add_store('BB')
    a,b=t('a','a'),t('b','b')
    mgr.assign('AA',[a]);mgr.assign('BB',[b])
    r=compare_store_selection(['AA','BB'],['a'],[a,b],mgr.load())
    assert not r['ready']
    assert [x['status'] for x in r['details']]==['READY','NO_COMMON_UID']
    r=compare_store_selection(['AA','BB'],['a','b'],[a,b],mgr.load())
    assert r['ready']


def test_explicit_ui_selection_protects_against_filter_callbacks(monkeypatch,tmp_path):
    """A filter trace that captures old list selection must not erase new choice."""
    from URETIM_V4.gui_v4 import UnifiedV4BatchWindow
    from tkinter import messagebox
    mgr=StoreProfiles(tmp_path);mgr.add_store('wudie')
    a,b=t('assigned','a'),t('old','b')
    mgr.assign('wudie',[a])
    class Var:
        def __init__(self,callback=None):self.callback=callback;self.value=''
        def set(self,val):
            self.value=val
            if self.callback:self.callback()
        def get(self):return self.value
    class FakeWindow:
        pass
    view=UnifiedV4BatchWindow.__new__(UnifiedV4BatchWindow)
    view.chosen_uids=lambda: ['old']
    view._store_selection_snapshot=lambda: (compare_store_selection(['wudie'],['old'],[a,b],mgr.load()),mgr.path)
    def capture_previous():
        view.selected_uids={'old'}
    view.category_filter=Var(capture_previous)
    view.search_filter=Var(capture_previous)
    view.apply_filters=lambda capture=False:None
    view.window=FakeWindow()
    messages=[]
    monkeypatch.setattr(messagebox,'showinfo',lambda *args,**kw: messages.append((args,kw)))
    view.select_store_assigned_templates()
    assert view.selected_uids=={'assigned'}
    assert view.category_filter.get()=='Tümü'
    assert view.search_filter.get()==''
    assert messages
    assert mgr.load()['stores']['wudie']['templates']==[key_for(a)]
