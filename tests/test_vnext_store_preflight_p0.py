"""Issue #79: read-only evidence, strict production membership and explicit Tk UX."""
from __future__ import annotations
import hashlib
import sys
from pathlib import Path
from types import SimpleNamespace
import tkinter as tk
from tkinter import messagebox

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'MERKEZ'))
from URETIM_V4.store_profiles_v47 import StoreProfiles, key_for
from URETIM_V4.store_selection_diagnostic_vnext import (
    compare_store_selection, format_store_diagnostic, read_profile_identity)


def template(uid, sha='a', category='06_Petek_Kapama'):
    return {'uid':uid,'category':category,'source_sha':sha*64,
            'source':str(Path('/fake-pool')/(uid+'.jpg')),'orientation':'H'}


def config(tmp_path, *pairs):
    mgr=StoreProfiles(tmp_path/'state')
    for name,items in pairs:
        mgr.add_store(name)
        if items:mgr.assign(name,items,all_approved=[item for _,ls in pairs for item in ls])
    return mgr


def test_user_scenario_one_valid_assignment_old_selected_uid_no_match(tmp_path):
    a,b=template('wudie_assigned'),template('formerly_selected','b')
    mgr=config(tmp_path,('wudie',[a]))
    before=mgr.path.read_bytes()
    report=compare_store_selection(['wudie'],[b['uid']],[a,b],mgr.load())
    assert report['details'][0]['status']=='NO_COMMON_UID'
    assert report['outside_uids']==['formerly_selected']
    assert not report['ready']
    assert mgr.path.read_bytes()==before
    with pytest.raises(ValueError,match='özel grubunda yok'):
        mgr.plan(['wudie'],[a,b],selected_uids=['formerly_selected'])
    assert mgr.plan(['wudie'],[a,b],selected_uids=['wudie_assigned'])[0][1]==[a]


def test_engine_no_longer_silently_skips_unassigned_extra_selection(tmp_path):
    a,b=template('assigned'),template('unassigned','b')
    mgr=config(tmp_path,('wudie',[a]))
    with pytest.raises(ValueError,match='STORE_SELECTED_UID_NOT_ASSIGNED: unassigned'):
        mgr.plan(['wudie'],[a,b],selected_uids=['assigned','unassigned'])
    report=compare_store_selection(['wudie'],['assigned','unassigned'],[a,b],mgr.load())
    assert not report['ready']
    assert report['outside_uids']==['unassigned']
    assert any(r['filename']=='unassigned.jpg' for r in report['selected_details'])


def test_two_stores_lock_sources_not_artwork_and_multi_selection(tmp_path):
    a,b=template('a'),template('b','b')
    mgr=config(tmp_path,('wudie',[a]),('OmzHome',[b]))
    p=mgr.plan(['wudie','OmzHome'],[a,b],selected_uids=['a','b'])
    assert {n for n,_ in p}=={'wudie','OmzHome'}
    assert mgr.load()['stores']['wudie']['templates']==[key_for(a)]
    with pytest.raises(ValueError,match='atanmış'):
        mgr.assign('OmzHome',[a])
    # The printable artwork is not a property of template ownership. The same
    # design path is valid in both store plans with different physical mockups.
    shared_artwork=tmp_path/'designs'/'Ham1.jpg'
    assert len(p)==2 and shared_artwork==tmp_path/'designs'/'Ham1.jpg'


def test_sha_change_detected_and_does_not_auto_rekey_or_touch_original(tmp_path):
    old,new=template('petek','a'),template('petek','b')
    mgr=config(tmp_path,('wudie',[old]))
    profile_before=mgr.path.read_bytes()
    r=compare_store_selection(['wudie'],['petek'],[new],mgr.load())
    assert not r['ready']
    stale=r['details'][0]['stale_reasons'][0]
    assert stale['reason']=='SOURCE_SHA_CHANGED'
    assert stale['current'][0]['source_sha']==new['source_sha']
    with pytest.raises(ValueError,match='SHA değişmiş'):
        mgr.plan(['wudie'],[new],selected_uids=['petek'])
    assert mgr.path.read_bytes()==profile_before


def test_restart_uses_same_store_profile_and_reads_disk_fresh(tmp_path):
    a,b=template('a'),template('b','b')
    mgr=config(tmp_path,('wudie',[a]))
    first=read_profile_identity(mgr)
    reloaded=StoreProfiles(tmp_path/'state')
    assert reloaded.path==mgr.path and read_profile_identity(reloaded)==first
    mgr.assign('wudie',[b])
    new=read_profile_identity(reloaded)
    assert first['sha256']!=new['sha256']
    assert len(reloaded.load()['stores']['wudie']['templates'])==2


def test_diagnostic_records_exact_selected_identity_owner_and_profile_sha(tmp_path):
    a,b=template('a'),template('b','b')
    mgr=config(tmp_path,('wudie',[a]),('other',[b]))
    report=compare_store_selection(['wudie'],['a','b'],[a,b],mgr.load())
    text=format_store_diagnostic(report,profile_identity=read_profile_identity(mgr),
                                 visible_selected_uids=['b'],internal_selected_uids=['a','b'])
    assert str(mgr.path.resolve()) in text
    assert hashlib.sha256(mgr.path.read_bytes()).hexdigest() in text
    assert 'b.jpg' in text and '06_Petek_Kapama' in text
    assert b['source_sha'] in text and 'other' in text
    assert 'Motor planına gönderilen seçili UID: a, b' in text
    assert 'Ekran listesindeki işaretli UID: b' in text
    assert 'SEÇİLİ MAĞAZADA DEĞİL' in text


def test_diagnostic_distinguishes_missing_uid_and_wrong_category(tmp_path):
    a=template('petek','a')
    same_uid_other_category=template('petek','c','01_Wifi_Kutusu')
    mgr=config(tmp_path,('wudie',[a]))
    report=compare_store_selection(['wudie'],['petek'],[same_uid_other_category],mgr.load())
    assert report['details'][0]['status']=='STALE_APPROVAL_OR_SHA'
    assert report['details'][0]['stale_reasons'][0]['reason']=='APPROVAL_OR_UID_MISSING'
    assert report['outside_uids']==['petek']


def test_duplicate_uid_conflicts_fail_closed(tmp_path):
    a=template('same','a');b=template('same','b','01_Wifi_Kutusu')
    mgr=config(tmp_path,('wudie',[a]))
    r=compare_store_selection(['wudie'],['same'],[a,b],mgr.load())
    assert not r['ready'] and r['duplicate_uids']==['same']


def tk_root_or_skip():
    try:
        root=tk.Tk();root.withdraw();return root
    except tk.TclError:
        pytest.skip('Graphical Tk display required')


def test_contextual_assignment_selects_only_available_and_does_not_write(tmp_path):
    from URETIM_V4.store_assignment_ui_v410 import StoreAssignmentWindow
    root=tk_root_or_skip()
    a,b=template('a'),template('b','b')
    mgr=config(tmp_path,('wudie',[]),('another',[b]))
    sha_before=read_profile_identity(mgr)['sha256']
    try:
        w=StoreAssignmentWindow(root,state_root=tmp_path/'state',
              get_approved=lambda:[a,b],on_change=lambda:None,
              prefill_store='wudie',prefill_category='06_Petek_Kapama',prefill_uid='a')
        root.update()
        assert w.store.get()=='wudie'
        assert key_for(a) in w.marked
        assert w.assign_button.instate(['!disabled'])
        assert read_profile_identity(mgr)['sha256']==sha_before
        w.pop.destroy()
        w=StoreAssignmentWindow(root,state_root=tmp_path/'state',
              get_approved=lambda:[a,b],on_change=lambda:None,
              prefill_store='wudie',prefill_category='06_Petek_Kapama',prefill_uid='b')
        root.update()
        assert w.marked==set()
        assert w.assign_button.instate(['disabled'])
        assert read_profile_identity(mgr)['sha256']==sha_before
        w.pop.destroy()
    finally:
        root.destroy()


def test_left_empty_no_assign_button_and_right_selection_never_mutates(tmp_path):
    from URETIM_V4.store_assignment_ui_v410 import StoreAssignmentWindow
    root=tk_root_or_skip()
    a=template('a')
    mgr=config(tmp_path,('wudie',[a]))
    before=mgr.path.read_bytes()
    try:
        w=StoreAssignmentWindow(root,state_root=tmp_path/'state',
             get_approved=lambda:[a],on_change=lambda:None)
        w.store.set('wudie');w._changed_store();root.update()
        w.select_all_assigned()
        assert len(w.assigned.selection())==1
        assert not w.marked
        assert w.assign_button.instate(['disabled'])
        # Direct assign() call remains safe even if button is disabled.
        warnings=[]
        from tkinter import messagebox
        old=messagebox.showwarning
        messagebox.showwarning=lambda *args,**kw:warnings.append(str(args))
        try:w.assign()
        finally:messagebox.showwarning=old
        assert warnings and 'Soldaki' in warnings[0]
        assert mgr.path.read_bytes()==before
        w.pop.destroy()
    finally:
        root.destroy()


def test_store_only_filter_does_not_clear_in_memory_selected_uids(tmp_path):
    from URETIM_V4.gui_v4 import UnifiedV4BatchWindow
    root=tk_root_or_skip()
    a,b=template('a'),template('old','b')
    mgr=config(tmp_path,('wudie',[a]))
    class Var:
        def __init__(self,value):self.value=value
        def get(self):return self.value
        def set(self,value):self.value=value
    try:
        w=UnifiedV4BatchWindow.__new__(UnifiedV4BatchWindow)
        w.batch_engine=SimpleNamespace(root=tmp_path/'state')
        w.store_list=tk.Listbox(root,selectmode='extended',exportselection=False)
        w.store_list.insert('end','wudie (1 şablon)');w.store_list.selection_set(0)
        w.store_mapping=['wudie']
        w.listbox=tk.Listbox(root,selectmode='extended',exportselection=False)
        w.window=root
        w.selected_uids={'a','old'}
        w.all_templates=[a,b]
        w.template_items={x['uid']:x for x in [a,b]}
        w.category_filter=Var('Tümü');w.search_filter=Var('')
        w.sort_filter=Var('Kategori / Ad');w.filter_count=Var('')
        w.store_filter_label=Var('');w.store_only_view=False;w._filter_redrawing=False
        w.mapping=[];w._preview_selected=lambda:None
        w.apply_filters(capture=False)
        w.show_store_templates()
        assert w.mapping==['a']
        assert w.selected_uids=={'a','old'}
        assert 'mağazaya ait olmayan: 1' in w.store_filter_label.get()
        w.show_all_templates()
        assert set(w.mapping)=={'a','old'}
        assert w.selected_uids=={'a','old'}
        w.selected_uids={'a'}
        w.apply_filters(capture=False)
        report,identity=w._store_selection_snapshot(selected=['a'],stores=['wudie'])
        assert report['ready']
        assert identity['sha256']==read_profile_identity(mgr)['sha256']
    finally:
        root.destroy()


def test_three_wudie_assignments_do_not_imply_any_production_selection(tmp_path):
    a,b,c=template('a'),template('b','b'),template('c','c')
    old=template('not_in_wudie','d')
    mgr=config(tmp_path,('wudie',[a,b,c]))
    r=compare_store_selection(['wudie'],['not_in_wudie'],[a,b,c,old],mgr.load())
    assert len(r['details'][0]['assigned'])==3
    assert r['details'][0]['matched']==[]
    assert r['details'][0]['status']=='NO_COMMON_UID'
    assert r['union_uids']==['a','b','c']
    assert not r['ready']


def test_production_start_uses_exact_ui_selected_uids_and_store_snapshot(tmp_path,monkeypatch):
    """No Python/Tk worker may start if the displayed selection is not owned."""
    from URETIM_V4 import gui_v4
    a,old=template('a'),template('old','b')
    mgr=config(tmp_path,('wudie',[a]))
    class Var:
        def __init__(self,val):self.val=val
        def get(self):return self.val
    class FakeList:
        def curselection(self):return (0,)
    class FakeButton:
        def configure(self,**kwargs):raise AssertionError('Production must not start')
    view=gui_v4.UnifiedV4BatchWindow.__new__(gui_v4.UnifiedV4BatchWindow)
    view.worker=None
    view.chosen_uids=lambda:['old']
    view.store_mapping=['wudie']
    view.store_list=FakeList()
    view.template_items={i['uid']:i for i in (a,old)}
    view.all_templates=[a,old]
    view.runtime_root=None
    view.window=SimpleNamespace()
    view.design_folder=Var(str(tmp_path))
    view.group=Var('LOCAL')
    view.placement=Var('Tam Göster')
    view.lighting=Var(gui_v4.LIGHT_LABELS[1])
    view.upscale_4k=Var(False)
    view.auto_cloud_link=Var(False)
    view.upscale_model=Var('Hızlı')
    view.petek_slot_mode=Var('off')
    view.petek_pink_cleanup=Var(False)
    view.batch_engine=SimpleNamespace(root=tmp_path/'state')
    view.start_button=FakeButton()
    observed=[]
    def record_snapshot(*,selected=None,stores=None):
        observed.append(('snapshot',selected,stores))
        return (compare_store_selection(stores,selected,view.all_templates,mgr.load()),
                read_profile_identity(mgr))
    view._store_selection_snapshot=record_snapshot
    view._store_report_text=lambda report,identity:'test report'
    view._log=lambda msg:observed.append(('log',msg))
    view._store_preflight_error=lambda reason,report,identity:observed.append(('error',str(reason),report['outside_uids']))
    monkeypatch.setattr(gui_v4,'iter_designs',lambda _root:iter([tmp_path/'art.png']))
    view.start()
    assert ('snapshot',['old'],['wudie']) in observed
    assert ('error','Seçilen şablon(lar) ile mağaza üyeliği uyuşmuyor.',['old']) in observed
    assert mgr.load()['stores']['wudie']['templates']==[key_for(a)]
