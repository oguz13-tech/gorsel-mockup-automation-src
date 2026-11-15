"""GÖREV 06 onarım testleri — Tasarım Yönetimi + Mağaza Profilleri.

Hiçbir test canlı veriye dokunmaz: HAM klasörü, kayıt veritabanı ve
store_profiles_v47.json yalnız geçici (tmp) klasörlerde üretilir.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'MERKEZ'))

import tasarim_yonetimi_v1 as designs  # noqa: E402
import magaza_profilleri_v1 as stores  # noqa: E402
from URETIM_V4.store_profiles_v47 import StoreProfiles, key_for  # noqa: E402

SHA_A = 'a' * 64
SHA_B = 'b' * 64
SHA_C = 'c' * 64


def _png(path: Path) -> Path:
    from PIL import Image
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new('RGB', (8, 8), (33, 160, 90)).save(path)
    return path


def _make_registry(db: Path, high: int = 0, active_paths: tuple[str, ...] = ()) -> Path:
    db.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db)
    con.executescript("""CREATE TABLE meta(id INTEGER PRIMARY KEY CHECK(id=1),
                          high INTEGER NOT NULL CHECK(high>=0), initialized INTEGER NOT NULL);
                       CREATE TABLE history(number INTEGER PRIMARY KEY, path TEXT NOT NULL,
                          source_name TEXT NOT NULL, sha TEXT NOT NULL, size INTEGER NOT NULL,
                          mtime_ns INTEGER NOT NULL, status TEXT NOT NULL,
                          created_at TEXT DEFAULT CURRENT_TIMESTAMP);""")
    con.execute('INSERT INTO meta(id, high, initialized) VALUES (1, ?, 1)', (high,))
    for i, rel in enumerate(active_paths, start=1):
        con.execute("INSERT INTO history VALUES (?, ?, 'src.png', 'x', 1, 1, 'ACTIVE', 'now')",
                    (i, rel))
    con.commit()
    con.close()
    return db


# ----------------------------------------------------------------- tasarım

def test_summarize_readable_empty_registry_is_zero_not_none(tmp_path):
    runtime = tmp_path / 'runtime'
    _png(runtime / designs.FOLDER / 'Ham5.png')
    _make_registry(designs.registry_path(runtime, tmp_path / 'state'), high=42)
    rows = designs.list_designs(runtime)
    registry = designs.read_registry(runtime, tmp_path / 'state')
    assert registry is not None and registry['active'] == 0
    summary = designs.summarize(rows, registry, None)
    assert summary['registered'] == 0
    assert summary['unregistered'] == 1
    assert summary['pool_high'] == 42


def test_summarize_missing_registry_reports_unknown(tmp_path):
    runtime = tmp_path / 'runtime'
    _png(runtime / designs.FOLDER / 'Ham5.png')
    rows = designs.list_designs(runtime)
    summary = designs.summarize(rows, None, None)
    assert summary['registered'] is None
    assert summary['unregistered'] is None


def test_summarize_partial_registry_counts_matches(tmp_path):
    runtime = tmp_path / 'runtime'
    _png(runtime / designs.FOLDER / 'Ham1.png')
    _png(runtime / designs.FOLDER / 'Ham2.png')
    _make_registry(designs.registry_path(runtime, tmp_path / 'state'),
                   high=7, active_paths=('Ham1.png',))
    rows = designs.list_designs(runtime)
    registry = designs.read_registry(runtime, tmp_path / 'state')
    summary = designs.summarize(rows, registry, None)
    assert summary['registered'] == 1
    assert summary['unregistered'] == 1


def test_designs_refresh_preserves_selection(tmp_path):
    import tkinter as tk
    try:
        root_win = tk.Tk()
        root_win.withdraw()
    except tk.TclError:
        pytest.skip('Tk ekranı bu ortamda kullanılamıyor')
    try:
        runtime = tmp_path / 'runtime'
        _png(runtime / designs.FOLDER / 'Ham1.png')
        _png(runtime / designs.FOLDER / 'Ham2.png')
        _png(runtime / designs.FOLDER / 'Ham3.png')

        class FakeApp:
            pass

        app = FakeApp()
        app.runtime = runtime
        app.status = type('S', (), {'set': staticmethod(lambda _t: None)})()
        app.open_ham_design_folder = lambda: None
        app.show_ham_design_audit = lambda: None

        parent = tk.Frame(root_win)
        parent.pack()
        shell = designs.build_designs_workspace(app, parent, runtime=runtime,
                                                local_state=tmp_path / 'state')
        root_win.update_idletasks()
        tree = shell.designs_tree
        iid = tree.get_children()[1]
        tree.selection_set(iid)
        selected_before = tree.item(iid, 'values')[0]
        shell.refresh_designs()
        root_win.update_idletasks()
        selection = tree.selection()
        assert selection, 'seçim yenilemede korunmalıydı'
        assert tree.item(selection[0], 'values')[0] == selected_before
    finally:
        root_win.destroy()


# ------------------------------------------------------------------ mağaza

def _config_with(store_map: dict[str, list[str]]) -> dict:
    return {'schema': 1, 'stores':
            {name: {'templates': list(keys)} for name, keys in store_map.items()}}


def test_set_short_code_keeps_other_store_pool_byte_identical(tmp_path):
    state = tmp_path / 'state'
    mgr = StoreProfiles(state)
    mgr.add_store('alpha')
    mgr.add_store('bravo')
    item_a = {'uid': 'Petek_Dolabi_001', 'category': '06_Petek_Kapama', 'source_sha': SHA_A}
    item_b = {'uid': 'Petek_Dolabi_002', 'category': '06_Petek_Kapama', 'source_sha': SHA_B}
    mgr.assign('alpha', [item_a], all_approved=[item_a, item_b])
    mgr.assign('bravo', [item_b], all_approved=[item_a, item_b])
    before = StoreProfiles(state).load()['stores']['bravo']['templates']
    mgr.set_short_code('alpha', 'ALP')
    after_cfg = StoreProfiles(state).load()
    assert after_cfg['stores']['bravo']['templates'] == before
    assert after_cfg['stores']['alpha']['templates'] == [key_for(item_a)]
    assert after_cfg['stores']['alpha']['short_code'] == 'ALP'


def test_reopen_after_edit_roundtrip_preserves_pool(tmp_path):
    state = tmp_path / 'state'
    mgr = StoreProfiles(state)
    mgr.add_store('kobold')
    item = {'uid': 'Petek_Dolabi_037', 'category': '06_Petek_Kapama', 'source_sha': SHA_C}
    mgr.assign('kobold', [item], all_approved=[item])
    mgr.set_short_code('kobold', 'KBD')
    fresh = StoreProfiles(state).load()
    assert fresh['stores']['kobold']['templates'] == [key_for(item)]
    assert fresh['stores']['kobold']['short_code'] == 'KBD'
    assert list(state.glob('store_profiles_v47.backup_*.json')), 'yedek oluşmalı'


def test_cross_store_same_template_rejected_and_flagged(tmp_path):
    state = tmp_path / 'state'
    mgr = StoreProfiles(state)
    mgr.add_store('magaza1')
    mgr.add_store('magaza2')
    item = {'uid': 'Petek_Dolabi_037', 'category': '06_Petek_Kapama', 'source_sha': SHA_A}
    mgr.assign('magaza1', [item], all_approved=[item])
    with pytest.raises(ValueError):
        mgr.assign('magaza2', [item], all_approved=[item])
    key = key_for(item)
    config = _config_with({'magaza1': [key], 'magaza2': [key]})
    result = stores.validate_store_profiles(config, None)
    assert any(p['kind'] == 'STORE_TEMPLATE_ASSIGNED_TO_MULTIPLE_STORES'
               for p in result['problems'])
    assert not result['ok']


def test_cross_store_short_code_case_insensitive_conflict(tmp_path):
    state = tmp_path / 'state'
    mgr = StoreProfiles(state)
    mgr.add_store('magaza1')
    mgr.add_store('magaza2')
    mgr.set_short_code('magaza1', 'ABC')
    with pytest.raises(ValueError, match='CAKISMASI'):
        mgr.set_short_code('magaza2', 'abc')


def test_add_store_then_reopen_shows_empty_pool_and_no_code(tmp_path):
    state = tmp_path / 'state'
    mgr = StoreProfiles(state)
    mgr.add_store('yeni_magaza_1')
    fresh = StoreProfiles(state).load()
    assert fresh['stores']['yeni_magaza_1']['templates'] == []
    status = stores.short_code_status('yeni_magaza_1', fresh['stores']['yeni_magaza_1'])
    assert status['defined'] is False  # bilinmeyen mağaza için kod uydurulmaz
