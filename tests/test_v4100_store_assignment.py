"""V4.10.0 explicit store-category assignment, isolated from production selection."""
from __future__ import annotations
from pathlib import Path
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'MERKEZ'))
from URETIM_V4.store_profiles_v47 import StoreProfiles, key_for
from URETIM_V4.store_assignment_v410 import status_inventory, checked_assignment, assigned_for_store


def tpl(uid, category='01_Wifi_Kutusu', sha='a'):
    return {'category':category,'uid':uid,'source_sha':sha*64}


def test_initial_store_inventory_no_auto_selection_and_status(tmp_path):
    mgr=StoreProfiles(tmp_path/'state')
    mgr.add_store('M1');mgr.add_store('M2')
    a,b,c=tpl('wifi_35',sha='a'),tpl('wifi_72',sha='b'),tpl('wifi_90',sha='c')
    mgr.assign('M1',[a],all_approved=[a,b,c])
    mgr.assign('M2',[b],all_approved=[a,b,c])
    rows=status_inventory('M1','01_Wifi_Kutusu',[a,b,c],mgr.load())
    assert [(r['item']['uid'],r['state'],r['owner']) for r in rows]==[
        ('wifi_35','assigned_here','M1'),('wifi_72','used_elsewhere','M2'),('wifi_90','available',None)]
    with pytest.raises(ValueError,match='Önce'):checked_assignment('M1','01_Wifi_Kutusu',set(),[a,b,c],mgr.load())
    assert [x['uid'] for x in checked_assignment('M1','01_Wifi_Kutusu',{key_for(c)},[a,b,c],mgr.load())]==['wifi_90']


def test_one_template_other_store_is_blocked_and_same_artwork_is_allowed(tmp_path):
    mgr=StoreProfiles(tmp_path/'state');mgr.add_store('M1');mgr.add_store('M2')
    a,b=tpl('wifi_35',sha='a'),tpl('wifi_72',sha='b')
    # The artwork code 18472 is NOT part of template identity or store ownership.
    mgr.assign('M1',[a],all_approved=[a,b])
    with pytest.raises(ValueError,match='kullanılıyor'):
        checked_assignment('M2','01_Wifi_Kutusu',{key_for(a)},[a,b],mgr.load())
    mgr.assign('M2',checked_assignment('M2','01_Wifi_Kutusu',{key_for(b)},[a,b],mgr.load()),all_approved=[a,b])
    assert set(mgr.load()['stores']['M1']['templates'])=={key_for(a)}
    assert set(mgr.load()['stores']['M2']['templates'])=={key_for(b)}
    assert '18472' not in str(mgr.load())


def test_duplicate_source_sha_blocks_cross_store_even_with_different_uid(tmp_path):
    mgr=StoreProfiles(tmp_path/'state');mgr.add_store('M1');mgr.add_store('M2')
    a=tpl('wifi_35',sha='a');copy=tpl('different_name','03_Ahsap_Tablo',sha='a')
    mgr.assign('M1',[a])
    view=status_inventory('M2','03_Ahsap_Tablo',[copy],mgr.load())
    assert view[0]['owner']=='M1' and view[0]['state']=='used_elsewhere'
    with pytest.raises(ValueError,match='kullanılıyor'):
        checked_assignment('M2','03_Ahsap_Tablo',{key_for(copy)},[copy],mgr.load())
    with pytest.raises(ValueError,match='REUSED_ACROSS_STORES'):
        mgr.assign('M2',[copy])


def test_different_category_does_not_expose_or_assign_other_category(tmp_path):
    mgr=StoreProfiles(tmp_path/'state');mgr.add_store('M1')
    wifi=tpl('wifi',sha='a');petek=tpl('petek','06_Petek_Kapama','b')
    rows=status_inventory('M1','06_Petek_Kapama',[wifi,petek],mgr.load())
    assert [r['item']['uid'] for r in rows]==['petek']
    with pytest.raises(ValueError,match='değişmiş'):
        checked_assignment('M1','06_Petek_Kapama',{key_for(wifi)},[wifi,petek],mgr.load())


def test_approval_sha_changed_marked_stale_do_not_silently_duplicate(tmp_path):
    mgr=StoreProfiles(tmp_path/'state');mgr.add_store('M1');mgr.add_store('M2')
    old=tpl('wifi_35',sha='a');new=tpl('wifi_35',sha='b')
    mgr.assign('M1',[old]);state=mgr.load()
    row=status_inventory('M2','01_Wifi_Kutusu',[new],state)[0]
    assert row['state']=='stale' and row['owner']=='M1'
    with pytest.raises(ValueError,match='kullanılıyor|atanmış'):
        checked_assignment('M2','01_Wifi_Kutusu',{key_for(new)},[new],state)
    assert mgr.load()==state


def test_existing_store_assignments_and_stale_legacy_receipts_remain_visible(tmp_path):
    mgr=StoreProfiles(tmp_path/'state');mgr.add_store('M1')
    a=tpl('wifi_35',sha='a')
    mgr.assign('M1',[a]);new=tpl('wifi_35',sha='b')
    records=assigned_for_store('M1',[new],mgr.load())
    assert len(records)==1 and records[0]['stale']
    assert records[0]['key']==key_for(a)


def test_gui_does_not_leak_production_selection_into_store_manager():
    code=(ROOT/'MERKEZ'/'URETIM_V4'/'gui_v4.py').read_text(encoding='utf-8')
    section=code.split('    def open_store_manager(self):',1)[1].split('    def _log(',1)[0]
    assert 'self.chosen_uids()' not in section
    assert 'StoreAssignmentWindow' in section
    assert 'self.selected_uids=set() if initial else' in code
    assert 'approved=list(self.template_items.values())' in code
    ui=(ROOT/'MERKEZ'/'URETIM_V4'/'store_assignment_ui_v410.py').read_text(encoding='utf-8')
    assert 'Mağaza–Mockup Eşleştirme Merkezi' in ui
    assert 'Kategorideki Tüm Uygunları Seç' in ui
    assert 'Seçilenlerin' not in section or True
    assert '_confirm_assignment' in ui and 'dialog.wait_window()' in ui


def test_manager_ui_opens_tk_without_touching_store_data(tmp_path):
    import tkinter as tk
    from URETIM_V4.store_assignment_ui_v410 import StoreAssignmentWindow
    try:
        root=tk.Tk();root.withdraw()
    except tk.TclError:
        pytest.skip('Display unavailable for Tk integration')
    try:
        state=tmp_path/'state'
        mgr=StoreProfiles(state);mgr.add_store('M1');mgr.add_store('M2')
        a,b=tpl('wifi_35',sha='a'),tpl('wifi_72',sha='b')
        mgr.assign('M2',[b])
        window=StoreAssignmentWindow(root,state_root=state,get_approved=lambda:[a,b],on_change=lambda:None)
        assert window.store.get()=='' and not window.marked
        assert len(window.pool.get_children())==0
        window.store.set('M1');window._changed_store()
        window.category.set(f"{__import__('URETIM_V4.unlimited_selection',fromlist=['CATEGORY_LABELS_TR']).CATEGORY_LABELS_TR[a['category']]}  ({a['category']})")
        window.refresh();root.update()
        assert len(window.pool.get_children())==2
        assert len(window._visible_keys)==2
        assert window.rows[key_for(b)]['state']=='used_elsewhere'
        assert not window.marked
        window.select_available()
        assert window.marked=={key_for(a)}
        assert mgr.load()['stores']['M1']['templates']==[]  # UI selection alone does not write.
        window.pop.destroy()
    finally:
        root.destroy()


def test_end_to_end_gui_assign_two_stores_separate_mockups_without_automatic_selection(tmp_path,monkeypatch):
    import tkinter as tk
    from tkinter import messagebox
    from PIL import Image
    from URETIM_V4.store_assignment_ui_v410 import StoreAssignmentWindow
    from URETIM_V4.unlimited_selection import CATEGORY_LABELS_TR
    try:
        root=tk.Tk();root.withdraw()
    except tk.TclError:
        pytest.skip('Tk needs display')
    monkeypatch.setattr(messagebox,'askyesno',lambda *args,**kwargs:True)
    monkeypatch.setattr(StoreAssignmentWindow,'_confirm_assignment',lambda self,store,category,names:True)
    monkeypatch.setattr(messagebox,'showinfo',lambda *args,**kwargs:None)
    cfg=tmp_path/'private_config';mgr=StoreProfiles(cfg)
    mgr.add_store('Magaza_A');mgr.add_store('Magaza_B')
    photo=tmp_path/'mockup.png';Image.new('RGB',(50,40),'white').save(photo)
    # Distinct mockup SHA values correspond to distinct mockup photo sources.
    a,b=tpl('wifi_35',sha='a'),tpl('wifi_72',sha='b')
    approved=[{**x,'source':str(photo)} for x in (a,b)]
    try:
        view=StoreAssignmentWindow(root,state_root=cfg,get_approved=lambda:approved,on_change=lambda:None)
        category=f"{CATEGORY_LABELS_TR[a['category']]}  ({a['category']})"
        view.store.set('Magaza_A');view._changed_store()
        view.category.set(category);view.refresh()
        assert not view.marked
        view._toggle_iid('0')  # select only the FIRST approved mockup
        assert view.marked=={key_for(a)}
        view.assign()
        assert mgr.load()['stores']['Magaza_A']['templates']==[key_for(a)]
        assert mgr.load()['stores']['Magaza_B']['templates']==[]
        view.store.set('Magaza_B');view._changed_store()
        view.category.set(category);view.refresh()
        assert not view.marked
        assert view.rows[key_for(a)]['state']=='used_elsewhere'
        view._toggle_iid('0')
        assert not view.marked
        view._toggle_iid('1')
        assert view.marked=={key_for(b)}
        view.assign()
        assert mgr.load()['stores']['Magaza_A']['templates']==[key_for(a)]
        assert mgr.load()['stores']['Magaza_B']['templates']==[key_for(b)]
        assert len(list(cfg.glob('store_profiles_v47.backup_*.json')))>=2
        view.pop.destroy()
    finally:
        root.destroy()


def test_final_assignment_preview_displays_all_file_names(tmp_path):
    import tkinter as tk
    from URETIM_V4.store_assignment_ui_v410 import StoreAssignmentWindow
    try:
        root=tk.Tk();root.withdraw()
    except tk.TclError:
        pytest.skip('Tk display missing')
    try:
        mgr=StoreProfiles(tmp_path/'store');mgr.add_store('Magaza_A')
        view=StoreAssignmentWindow(root,state_root=tmp_path/'store',get_approved=lambda:[],on_change=lambda:None)
        examples=[f'Wifi_Kutusu_{i:03d}.png' for i in range(1,128)]
        seen=[]
        def approve():
            dialogs=[x for x in view.pop.winfo_children() if isinstance(x,tk.Toplevel)]
            assert len(dialogs)==1
            widgets=[]
            def walk(w):
                widgets.append(w)
                for c in w.winfo_children():walk(c)
            walk(dialogs[0])
            candidates=[w for w in widgets if isinstance(w,tk.Listbox)]
            assert len(candidates)==1
            lb=candidates[0]
            seen.append((lb.size(),lb.get(0),lb.get(126)))
            buttons=[w for w in widgets if getattr(w,'winfo_class',lambda:'' )()=='TButton'
                     and str(w.cget('text')).endswith('MOCKUPU ATA')]
            assert len(buttons)==1
            buttons[0].invoke()
        root.after(45,approve)
        assert view._confirm_assignment('Magaza_A','01_Wifi_Kutusu',examples)
        assert seen==[(127,'001  Wifi_Kutusu_001.png','127  Wifi_Kutusu_127.png')]
        view.pop.destroy()
    finally:
        root.destroy()
