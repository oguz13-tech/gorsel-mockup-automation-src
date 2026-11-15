"""Synthetic-only full six-category editor bridge and zero-migration checks."""
import hashlib
import os
import sqlite3
import sys
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'MERKEZ'))
import legacy_manager as mgr

TABLES={
 'categories':'id INTEGER PRIMARY KEY',
 'templates':'id INTEGER PRIMARY KEY',
 'settings':'id INTEGER PRIMARY KEY',
 'template_profiles':'id INTEGER PRIMARY KEY, nominal_aspect TEXT, is_active INTEGER',
 'jobs':'id INTEGER PRIMARY KEY',
 'template_operation_locks':'id INTEGER PRIMARY KEY',
 'template_number_registry':'id INTEGER PRIMARY KEY',
 'analysis_cache':'id INTEGER PRIMARY KEY',
}

def runtime(tmp_path):
    root=tmp_path/'GörselÜretme-ve-Mockup Otomasyonu'
    for name in ['2_SABLON_HAVUZU','2_SABLON_HAVUZU_ORIJINAL_YEDEK','SABLON_V2_MIMARI']:
        (root/name).mkdir(parents=True)
    db=root/'SABLON_V2_MIMARI'/'ayarlar.db'
    with sqlite3.connect(db) as conn:
        for t,shape in TABLES.items():conn.execute('CREATE TABLE "'+t+'" ('+shape+')')
        conn.execute('INSERT INTO categories(id) VALUES(1)')
        conn.execute('INSERT INTO template_profiles(nominal_aspect,is_active) VALUES(?,?)',('1.1',1))
    return root


def test_reference_editor_and_professional_tools_bundled():
    p=ROOT/'LEGACY_REFERANS_KOD'/'SABLON_V2_MIMARI'
    assert (p/'app.py').is_file()
    assert (p/'tools_runner.py').is_file()
    assert (p/'templates'/'index.html').is_file()
    assert (p/'templates'/'tools.html').is_file()
    assert (p/'static'/'js'/'main.js').is_file()


def test_first_start_backups_to_external_folder_without_mutating_runtime(tmp_path):
    root=runtime(tmp_path)
    code=ROOT/'LEGACY_REFERANS_KOD'
    original=root/'SABLON_V2_MIMARI'/'ayarlar.db'
    before=hashlib.sha256(original.read_bytes()).hexdigest()
    status=mgr.inspect(root,code)
    assert status['ready'],status
    env={'LOCALAPPDATA':str(tmp_path/'AppData')}
    p=mgr.backup_database(root,env=env)
    assert p.exists() and p.parent.is_relative_to(tmp_path/'AppData')
    assert p!=original
    assert p.with_suffix('.sha256').is_file()
    assert p.with_suffix('.sha256').read_text().split()[0]==hashlib.sha256(p.read_bytes()).hexdigest()
    assert before==hashlib.sha256(original.read_bytes()).hexdigest()
    with sqlite3.connect(p) as conn:
        assert conn.execute('SELECT COUNT(*) FROM template_profiles').fetchone()[0]==1
    assert p!=mgr.backup_database(root,env=env)


def test_fail_closed_for_missing_schema_and_no_auto_migration(tmp_path):
    root=runtime(tmp_path)
    db=root/'SABLON_V2_MIMARI'/'ayarlar.db'
    with sqlite3.connect(db) as conn:conn.execute('DROP TABLE analysis_cache')
    before=hashlib.sha256(db.read_bytes()).hexdigest()
    got=mgr.inspect(root,ROOT/'LEGACY_REFERANS_KOD')
    assert not got['ready']
    assert any('analysis_cache' in s for s in got['problems'])
    with pytest.raises(mgr.LegacyLaunchError):mgr.launch_spec(root,ROOT/'LEGACY_REFERANS_KOD')
    assert hashlib.sha256(db.read_bytes()).hexdigest()==before


def test_spec_uses_original_workspace_without_exposing_network(tmp_path):
    root=runtime(tmp_path)
    cmd,env,cwd=mgr.launch_spec(root,ROOT/'LEGACY_REFERANS_KOD')
    assert Path(cmd[-1]).name=='app.py'
    assert env['MOCKUP_RUNTIME_WORKSPACE']==str(root.absolute())
    assert env['MOCKUP_NO_AUTO_BROWSER']=='1'
    assert env['MOCKUP_FLASK_DEBUG']=='0'
    assert str(ROOT/'LEGACY_REFERANS_KOD')==cwd


def test_workspace_choice_is_user_local_and_keeps_live_db(tmp_path):
    root=runtime(tmp_path)
    config={'LOCALAPPDATA':str(tmp_path/'local')}
    db=root/'SABLON_V2_MIMARI'/'ayarlar.db'
    before=db.read_bytes()
    selected=mgr.store_runtime_choice(root,env=config)
    assert selected==root
    assert mgr.preferred_runtime(env=config)==root
    assert db.read_bytes()==before
    with pytest.raises(mgr.LegacyLaunchError):mgr.store_runtime_choice(tmp_path/'missing',env=config)


def test_source_prefers_latest_install_then_fallback(tmp_path):
    dir=tmp_path/'custom-code'
    (dir/'SABLON_V2_MIMARI'/'core').mkdir(parents=True)
    (dir/'SABLON_V2_MIMARI'/'app.py').write_text('')
    (dir/'SABLON_V2_MIMARI'/'core'/'db.py').write_text('')
    assert mgr.preferred_code(env={'MOCKUP_LEGACY_SOURCE_ROOT':str(dir)})==dir
    assert mgr.preferred_code(env={'MOCKUP_LEGACY_SOURCE_ROOT':str(tmp_path/'missing')}).is_dir()
