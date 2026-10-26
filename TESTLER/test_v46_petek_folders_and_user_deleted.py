"""Realistic isolated tests. Never touch the user's Windows/OneDrive data."""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import time

import cv2
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'MERKEZ'))

from petek_folders_v46 import petek_directory, prepare_petek_folders, SECTIONS
from inbox_auto_v42 import ingest_one, AutoInboxWatcher
from URETIM_V4.unified_batch import UnifiedV4Ledger
from URETIM_V4.final_guard_v44 import _output_audit, inspect_workspaces
from URETIM_V4.user_removed_v46 import missing_user_candidates, acknowledge_user_deleted


def _photo(path):
    image = np.full((300, 250, 3), (255, 0, 255), np.uint8)
    ok, encoded = cv2.imencode('.png', image)
    assert ok
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encoded.tobytes())


def _workspace(tmp_path):
    runtime = tmp_path / 'workspace'
    db = runtime / 'SABLON_V2_MIMARI' / 'ayarlar.db'
    db.parent.mkdir(parents=True)
    with sqlite3.connect(db) as con:
        con.execute('CREATE TABLE categories (id TEXT PRIMARY KEY)')
        con.execute('CREATE TABLE templates (category_id TEXT, filename TEXT, data TEXT)')
        con.execute('CREATE TABLE template_profiles (template_uid TEXT, category TEXT)')
        con.execute('INSERT INTO categories VALUES (?)', ('01_Wifi_Kutusu',))
    return runtime, db


def test_petek_existing_friendly_inbox_creates_only_missing_folders(tmp_path):
    root, db = _workspace(tmp_path)
    original = root / SECTIONS[0] / 'Petek_Dolabi'
    image = original / 'PETEK_FIRST_601.png'
    _photo(image)
    old_sha = hashlib.sha256(image.read_bytes()).hexdigest()
    db_sha = hashlib.sha256(db.read_bytes()).hexdigest()
    result = prepare_petek_folders(root)
    assert result['logical_category'] == '06_Petek_Kapama'
    assert len(result['created']) == 2
    assert all(Path(path).name == 'Petek_Dolabi' for path in result['paths'].values())
    assert all(Path(path).is_dir() for path in result['paths'].values())
    assert hashlib.sha256(image.read_bytes()).hexdigest() == old_sha
    assert hashlib.sha256(db.read_bytes()).hexdigest() == db_sha
    assert prepare_petek_folders(root)['created'] == []


def test_petek_alias_conflict_fails_before_mkdir(tmp_path):
    root, _ = _workspace(tmp_path)
    for name in ('Petek_Dolabi', '06_Petek_Kapama'):
        _photo(root / SECTIONS[0] / name / (name+'.png'))
    with pytest.raises(ValueError, match='PETEK_ALIAS_CONFLICT'):
        prepare_petek_folders(root)
    assert not (root / SECTIONS[1]).exists()


def test_petek_auto_ingest_from_friendly_folder_no_db_write(tmp_path):
    root, db = _workspace(tmp_path)
    original_sha = hashlib.sha256(db.read_bytes()).hexdigest()
    input_file = root / SECTIONS[0] / 'Petek_Dolabi' / 'PetekDolabi_NEW_99.png'
    _photo(input_file)
    result = ingest_one(root, '06_Petek_Kapama', input_file)
    assert result['registration'] == 'PETEK_MASK_REVIEW'
    assert result['status'] == 'IMPORTED_NEEDS_CORNERS'
    work = root / SECTIONS[1] / 'Petek_Dolabi' / input_file.name
    archive = root / SECTIONS[2] / 'Petek_Dolabi' / input_file.name
    assert work.read_bytes() == archive.read_bytes()
    assert not input_file.exists()
    assert (input_file.parent / 'EKLENENLER_INCELEME_BEKLIYOR' / input_file.name).is_file()
    assert hashlib.sha256(db.read_bytes()).hexdigest() == original_sha


def test_petek_watcher_discovers_friendly_name(tmp_path):
    root, _ = _workspace(tmp_path)
    source = root / SECTIONS[0] / 'Petek_Dolabi' / 'PetekDolabi_WATCH_100.png'
    _photo(source)
    two_seconds_ago = time.time() - 4
    os.utime(source, (two_seconds_ago, two_seconds_ago))
    watcher = AutoInboxWatcher(root)
    assert watcher.sweep() == []
    outcome = watcher.sweep()
    assert len(outcome) == 1
    assert outcome[0]['status'] == 'IMPORTED_NEEDS_CORNERS'
    assert (root / SECTIONS[1] / 'Petek_Dolabi' / source.name).is_file()


def _ledger_fixture(tmp_path):
    runtime, _ = _workspace(tmp_path)
    state = tmp_path / 'state'
    ledger = UnifiedV4Ledger(state)
    output = state / 'uretilen_gorseller' / 'LOCAL' / '03_Ahsap_Tablo'
    output.mkdir(parents=True, exist_ok=True)
    with ledger.connect() as con:
        for i in range(4):
            path = output / f'{i}.png'
            sha = 'a'*64
            status = 'RENDERED' if i < 3 else 'REVIEW_REQUIRED'
            if i == 2:
                path.write_bytes(b'keep')
                sha = hashlib.sha256(b'keep').hexdigest()
            con.execute(
                """INSERT INTO artifact
                (key,sku,category,art_sha,template_sha,mask_sha,art_name,uid,
                output,output_sha,status) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (str(i),f'SKU{i}','03_Ahsap_Tablo','b'*64,'c'*64,'d'*64,
                 'art.png','tpl',str(path),sha,status),
            )
    return runtime, state, ledger


def test_user_removed_writes_no_images_and_preserves_history(tmp_path):
    runtime, state, ledger = _ledger_fixture(tmp_path)
    before = ledger.file.read_bytes()
    missing = missing_user_candidates(state)
    assert {x['key'] for x in missing} == {'0', '1'}
    with pytest.raises(PermissionError):
        acknowledge_user_deleted(state, runtime, expected_keys=['0','1'], confirm='wrong')
    assert ledger.file.read_bytes() == before
    result = acknowledge_user_deleted(
        state, runtime, expected_keys=['0','1'],
        confirm='I_CONFIRM_THESE_FILES_WERE_DELETED_BY_ME'
    )
    assert result['count'] == 2
    report = json.loads(Path(result['report_path']).read_text(encoding='utf-8'))
    assert report['files_deleted_by_this_action'] == 0
    assert Path(result['backup_path']).is_file()
    with ledger.connect() as con:
        rows = list(con.execute('SELECT key,status,output_sha FROM artifact ORDER BY key'))
    assert [(x['key'],x['status']) for x in rows] == [
        ('0','USER_REMOVED'),('1','USER_REMOVED'),
        ('2','RENDERED'),('3','REVIEW_REQUIRED'),
    ]
    assert [x['output_sha'] for x in rows[:2]] == ['a'*64,'a'*64]
    assert (state/'uretilen_gorseller'/'LOCAL'/'03_Ahsap_Tablo'/'2.png').read_bytes() == b'keep'
    audit = _output_audit(ledger.file, state/'uretilen_gorseller')
    assert audit['missing'] == 0
    assert audit['user_removed'] == 2
    assert audit['verified'] == 1
    assert audit['unfinished'] == 1
    assert missing_user_candidates(state) == []
    assert inspect_workspaces(runtime, state)['production']['user_removed'] == 2


def test_changed_missing_selection_fails_without_mutation(tmp_path):
    runtime, state, ledger = _ledger_fixture(tmp_path)
    with pytest.raises(RuntimeError, match='MISSING_SET_CHANGED'):
        acknowledge_user_deleted(
            state,runtime, expected_keys=['0'],
            confirm='I_CONFIRM_THESE_FILES_WERE_DELETED_BY_ME')
    with ledger.connect() as con:
        assert con.execute("SELECT count(*) FROM artifact WHERE status='USER_REMOVED'").fetchone()[0] == 0


def test_cloud_option_is_explicitly_opt_in_and_requires_second_approval():
    text = (ROOT/'MERKEZ'/'URETIM_V4'/'gui_v4.py').read_text(encoding='utf-8')
    assert 'self.auto_cloud_link = tk.BooleanVar(value=False)' in text
    assert text.index('self.upscale_4k =') < text.index('self.auto_cloud_link =')
    assert 'self.start_cloud_links(only_keys=self._auto_cloud_keys)' in text
    assert "rows = [row for row in rows if row['key'] in permitted]" in text
    batch = (ROOT/'MERKEZ'/'URETIM_V4'/'unified_batch.py').read_text(encoding='utf-8')
    assert '"current_batch_keys": []' in batch
    assert 'stats["current_batch_keys"].append(key)' in batch
    assert 'GERÇEK BULUT YÜKLEME ONAYI' in text
