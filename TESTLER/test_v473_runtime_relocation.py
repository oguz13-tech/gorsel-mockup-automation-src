"""Two-phase OneDrive risk mitigation: SHA copy, no source mutation and explicit approval."""
import hashlib
import json
import sqlite3
from pathlib import Path
import sys
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'MERKEZ'))
import runtime_relocate_v473 as migration
import legacy_manager


def make_workspace(root):
    db=root/'SABLON_V2_MIMARI'/'ayarlar.db'
    db.parent.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(db) as c:
        c.execute('CREATE TABLE template_profiles (template_uid TEXT PRIMARY KEY)')
        c.execute("INSERT INTO template_profiles VALUES ('approved_001')")
    image=root/'2_SABLON_HAVUZU'/'03_Ahsap_Tablo'/'Ahsap_001.png'
    image.parent.mkdir(parents=True)
    image.write_bytes(b'original-work-image')
    original=root/'2_SABLON_HAVUZU_ORIJINAL_YEDEK'/'03_Ahsap_Tablo'/'Ahsap_001.png'
    original.parent.mkdir(parents=True)
    original.write_bytes(b'old-source-immutable')
    return db,image,original


def test_runtime_copy_integrity_and_explicit_activation(tmp_path,monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA',str(tmp_path/'AppData'))
    monkeypatch.setattr(migration,'state_root',lambda:tmp_path/'LocalProduction')
    source=tmp_path/'OneDrive'/'Gorsel_Ana'
    db,image,original=make_workspace(source)
    before=(migration.digest(db),migration.digest(image),migration.digest(original))
    newroot=tmp_path/'verified_live'
    result=migration.stage(source,newroot)
    assert result['count']==3 and result['activated'] is False
    assert migration.digest(image)==before[1] and migration.digest(original)==before[2]
    with sqlite3.connect(newroot/'SABLON_V2_MIMARI'/'ayarlar.db') as c:
        assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert c.execute('SELECT COUNT(*) FROM template_profiles').fetchone()[0]==1
    assert not (legacy_manager.local_state_dir()/'workspace.json').exists()
    with pytest.raises(PermissionError):
        migration.activate(newroot,'wrong')
    activation=migration.activate(newroot,migration.CONFIRM)
    assert activation['files_verified']==3
    # CI may deliberately set MOCKUP_RUNTIME_WORKSPACE globally to isolate tests.
    # A fresh Windows launch without that override reads the saved workspace.json.
    assert legacy_manager.preferred_runtime(env={'LOCALAPPDATA':str(tmp_path/'AppData')})==newroot
    assert migration.digest(image)==before[1] and migration.digest(original)==before[2]
    assert (newroot/migration.RECEIPT).is_file()
    assert source.is_dir()


def test_stale_original_prevents_activation(tmp_path,monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA',str(tmp_path/'AppData'))
    monkeypatch.setattr(migration,'state_root',lambda:tmp_path/'LocalProduction')
    root=tmp_path/'OneDrive'/'Gorsel_Ana'
    _,image,_=make_workspace(root)
    dest=tmp_path/'outside'
    migration.stage(root,dest)
    image.write_bytes(b'changed after staging')
    with pytest.raises(RuntimeError,match='LIVE_SOURCE_CHANGED_AFTER_STAGING'):
        migration.activate(dest,migration.CONFIRM)
    assert not (legacy_manager.local_state_dir()/'workspace.json').exists()


def test_missing_or_partial_copy_not_activatable(tmp_path,monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA',str(tmp_path/'AppData'))
    monkeypatch.setattr(migration,'state_root',lambda:tmp_path/'LocalProduction')
    root=tmp_path/'OneDrive'/'Gorsel_Ana'
    make_workspace(root)
    dest=tmp_path/'outside'
    migration.stage(root,dest)
    (dest/'2_SABLON_HAVUZU'/'03_Ahsap_Tablo'/'Ahsap_001.png').write_bytes(b'tampered')
    with pytest.raises(RuntimeError,match='STAGED_COPY_TAMPERED'):
        migration.activate(dest,migration.CONFIRM)
    (dest/'.INCOMPLETE_RUNTIME_MIGRATION').write_text('resume required')
    with pytest.raises(RuntimeError,match='RUNTIME_MIGRATION_INCOMPLETE'):
        migration.activate(dest,migration.CONFIRM)


def test_runtime_activation_fails_when_editor_is_running(tmp_path,monkeypatch):
    monkeypatch.setattr(migration.socket,'create_connection',lambda *_args,**_kw: _reject())
    with pytest.raises(RuntimeError,match='STOP_FLASK_SERVER'):
        migration.check_stopped(tmp_path)

def _reject():
    raise RuntimeError('STOP_FLASK_SERVER_BEFORE_MIGRATION')


def test_secondary_sqlite_wal_rows_are_in_staged_copy(tmp_path,monkeypatch):
    """P0: SQLite databases other than ayarlar.db must not lose their WAL."""
    monkeypatch.setenv('LOCALAPPDATA',str(tmp_path/'AppData'))
    monkeypatch.setattr(migration,'state_root',lambda:tmp_path/'LocalProduction')
    root=tmp_path/'OneDrive'/'Gorsel_Ana'
    make_workspace(root)
    second=root/'EXTRA'/'work_history.sqlite3'
    second.parent.mkdir()
    con=sqlite3.connect(second)
    try:
        con.execute('PRAGMA journal_mode=WAL')
        con.execute('PRAGMA wal_autocheckpoint=0')
        con.execute('CREATE TABLE events(value TEXT)')
        con.execute("INSERT INTO events VALUES('committed_wal_record')")
        con.commit()
        assert second.with_name(second.name+'-wal').is_file()
        target=tmp_path/'outside'
        migration.stage(root,target)
        with sqlite3.connect(target/'EXTRA'/'work_history.sqlite3') as read:
            assert read.execute('SELECT value FROM events').fetchall()==[
                ('committed_wal_record',)]
        migration.activate(target,migration.CONFIRM)
        assert second.is_file()
    finally:
        con.close()


def test_source_wal_commit_after_stage_rejects_activation(tmp_path,monkeypatch):
    """P0: source main .db may stay byte-identical while WAL changes."""
    monkeypatch.setenv('LOCALAPPDATA',str(tmp_path/'AppData'))
    monkeypatch.setattr(migration,'state_root',lambda:tmp_path/'LocalProduction')
    root=tmp_path/'OneDrive'/'Gorsel_Ana'
    db,_,_=make_workspace(root)
    conn=sqlite3.connect(db)
    try:
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA wal_autocheckpoint=0')
        conn.commit()
        target=tmp_path/'outside'
        migration.stage(root,target)
        db_before=migration.digest(db)
        conn.execute("INSERT INTO template_profiles VALUES('AFTER_STAGING')")
        conn.commit()
        assert db_before==migration.digest(db), 'WAL-only mutation fixture failed'
        with pytest.raises(RuntimeError,match='LIVE_SOURCE_CHANGED_AFTER_STAGING'):
            migration.activate(target,migration.CONFIRM)
        assert not (legacy_manager.local_state_dir()/'workspace.json').exists()
    finally:
        conn.close()


def test_extra_target_files_cannot_be_silently_activated(tmp_path,monkeypatch):
    """P1: exact target inventory must match the saved SHA manifest."""
    monkeypatch.setenv('LOCALAPPDATA',str(tmp_path/'AppData'))
    monkeypatch.setattr(migration,'state_root',lambda:tmp_path/'LocalProduction')
    root=tmp_path/'OneDrive'/'Gorsel_Ana'
    make_workspace(root)
    target=tmp_path/'outside'
    migration.stage(root,target)
    (target/'stray_legacy_script.py').write_text('print("unsafe")',encoding='utf-8')
    with pytest.raises(RuntimeError,match='STAGED_EXTRA_OR_MISSING_FILES'):
        migration.activate(target,migration.CONFIRM)
    assert not (legacy_manager.local_state_dir()/'workspace.json').exists()


def test_old_v473_manifest_must_be_restaged(tmp_path,monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA',str(tmp_path/'AppData'))
    monkeypatch.setattr(migration,'state_root',lambda:tmp_path/'LocalProduction')
    root=tmp_path/'OneDrive'/'Gorsel_Ana'
    make_workspace(root)
    target=tmp_path/'outside'
    migration.stage(root,target)
    receipt=target/migration.RECEIPT
    data=json.loads(receipt.read_text('utf-8'))
    data['schema']=1
    receipt.write_text(json.dumps(data),encoding='utf-8')
    with pytest.raises(RuntimeError,match='RUNTIME_RESTAGE_REQUIRED'):
        migration.activate(target,migration.CONFIRM)


def test_fallback_review_port_blocks_runtime_move(tmp_path,monkeypatch):
    monkeypatch.setattr(migration,'state_root',lambda:tmp_path/'LocalProduction')
    class Connected:
        def __enter__(self):return self
        def __exit__(self,*args):return None
    def fake(addr,timeout=None):
        if addr[1]==8088:return Connected()
        raise ConnectionRefusedError()
    monkeypatch.setattr(migration.socket,'create_connection',fake)
    with pytest.raises(RuntimeError,match='STOP_FLASK_SERVER'):
        migration.check_stopped(tmp_path)
