"""Bulk unassignment must not remove template/source/production content."""
from pathlib import Path
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'MERKEZ'))
from URETIM_V4.store_profiles_v47 import StoreProfiles, key_for


def t(uid, category='01_Wifi_Kutusu', char='a'):
    return {'uid': uid, 'category': category, 'source_sha': char * 64}


def test_bulk_remove_only_selected_memberships_preserves_stores_and_backup(tmp_path):
    mgr = StoreProfiles(tmp_path / 'state')
    mgr.add_store('M1'); mgr.add_store('M2')
    a, b, c, d = t('a', char='a'), t('b', char='b'), t('c', char='c'), t('d', char='d')
    mgr.assign('M1', [a,b,c]); mgr.assign('M2', [d])
    old = mgr.load()
    assert mgr.unassign_keys('M1', [key_for(a),key_for(c)],
                             expected_current_keys=tuple(old['stores']['M1']['templates'])) == 2
    after = mgr.load()
    assert after['stores']['M1']['templates'] == [key_for(b)]
    assert after['stores']['M2'] == old['stores']['M2']
    backups = list((tmp_path / 'state').glob('store_profiles_v47.backup_*.json'))
    assert backups
    assert any(key_for(a) in b.read_text(encoding='utf-8') for b in backups)
    mgr.assign('M2',[a,c])  # Freed mockups can now be assigned elsewhere.
    assert set(mgr.load()['stores']['M2']['templates']) == {key_for(a),key_for(c),key_for(d)}


def test_bulk_remove_fails_closed_for_empty_duplicates_stale_and_other_store(tmp_path):
    mgr=StoreProfiles(tmp_path / 'state')
    mgr.add_store('M1'); mgr.add_store('M2')
    a,b=t('a',char='a'),t('b',char='b')
    mgr.assign('M1',[a]);mgr.assign('M2',[b])
    before=mgr.load()
    for keys, expected in [([], 'seçin'),([key_for(a),key_for(a)], 'seçin'),
                           ([key_for(b)], 'artık mağazada değil')]:
        with pytest.raises(ValueError,match=expected):
            mgr.unassign_keys('M1',keys)
    with pytest.raises(ValueError,match='değişti'):
        mgr.unassign_keys('M1',[key_for(a)], expected_current_keys=[])
    assert mgr.load()==before


def test_store_manager_ui_multi_select_and_single_confirm(tmp_path,monkeypatch):
    import tkinter as tk
    from tkinter import messagebox
    from URETIM_V4.store_assignment_ui_v410 import StoreAssignmentWindow
    from URETIM_V4.unlimited_selection import CATEGORY_LABELS_TR
    try:
        root=tk.Tk();root.withdraw()
    except tk.TclError:
        pytest.skip('Requires a graphical display')
    path=tmp_path/'state'
    mgr=StoreProfiles(path);mgr.add_store('Magaza_A')
    records=[t(f'item_{i:02d}',char=chr(97+i)) for i in range(5)]
    mgr.assign('Magaza_A',records)
    callbacks=[]; confirmed=[]
    monkeypatch.setattr(messagebox,'showinfo',lambda *args,**kw:None)
    monkeypatch.setattr(messagebox,'showwarning',lambda *args,**kw:None)
    monkeypatch.setattr(StoreAssignmentWindow,'_confirm_unassignment',
                       lambda self,store,names: confirmed.append((store,names)) or True)
    try:
        view=StoreAssignmentWindow(root,state_root=path,get_approved=lambda:records,
                                   on_change=lambda:callbacks.append('changed'))
        view.store.set('Magaza_A');view._changed_store()
        assert str(view.assigned.cget('selectmode')) == 'extended'
        assert not view.assigned.selection()
        view.assigned.selection_set('0','2')
        assert len(view.assigned.selection()) == 2
        view.unassign()
        assert len(confirmed)==1 and len(confirmed[0][1])==2
        assert len(mgr.load()['stores']['Magaza_A']['templates'])==3
        assert callbacks==['changed']
        view.select_all_assigned()
        assert len(view.assigned.selection())==3
        view.clear_assigned_selection()
        assert not view.assigned.selection()
        category = f"{CATEGORY_LABELS_TR[records[0]['category']]}  ({records[0]['category']})"
        view.category.set(category)
        view.select_category_assigned()
        assert len(view.assigned.selection())==3
        view.pop.destroy()
    finally:
        root.destroy()


def test_bulk_remove_full_confirmation_is_scrollable(tmp_path):
    import tkinter as tk
    from URETIM_V4.store_assignment_ui_v410 import StoreAssignmentWindow
    try:
        root=tk.Tk();root.withdraw()
    except tk.TclError:
        pytest.skip('Requires a graphical display')
    mgr=StoreProfiles(tmp_path/'state');mgr.add_store('M1')
    try:
        view=StoreAssignmentWindow(root,state_root=tmp_path/'state',
                                   get_approved=lambda:[],on_change=lambda:None)
        names=[f'01_Wifi_Kutusu:wifi_{i:03d}' for i in range(127)]
        captured=[]
        def inspect():
            children=[x for x in view.pop.winfo_children() if isinstance(x,tk.Toplevel)]
            assert len(children)==1
            widgets=[]
            def walk(w):
                widgets.append(w)
                for child in w.winfo_children():walk(child)
            walk(children[0])
            lbs=[w for w in widgets if isinstance(w,tk.Listbox)]
            assert len(lbs)==1
            captured.append((lbs[0].size(),lbs[0].get(0),lbs[0].get(126)))
            buttons=[w for w in widgets if w.winfo_class()=='TButton'
                     and str(w.cget('text'))=='127 ATAMAYI KALDIR']
            assert len(buttons)==1
            buttons[0].invoke()
        root.after(50,inspect)
        assert view._confirm_unassignment('M1',names)
        assert captured==[(127, '001  01_Wifi_Kutusu:wifi_000',
                           '127  01_Wifi_Kutusu:wifi_126')]
        view.pop.destroy()
    finally:
        root.destroy()
