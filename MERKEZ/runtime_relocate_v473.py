"""Offline-safe two-phase OneDrive runtime migration; never move/delete source.

Stage: copy each file create-only with SHA, take ONLINE SQLite snapshot of
ayarlar.db, verify restored copy. Activate ONLY with explicit operator phrase
after a second full SHA validation and an unchanged-source check. Code and
production/PETEK AppData are not moved. No auto-activation or cleanup.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import sqlite3
import uuid
import tempfile
from contextlib import closing
from legacy_manager import store_runtime_choice, local_state_dir

CONFIRM='ONAYLIYORUM: ONEDRIVE DIŞINDAKİ DOĞRULANMIŞ ÇALIŞMA ALANINI ETKİNLEŞTİR'
RECEIPT='.V473_RUNTIME_MIGRATION_RECEIPT.json'
SQLITE_EXT={'.db','.sqlite','.sqlite3','.db3'}

def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as src:
        for part in iter(lambda:src.read(1024*1024),b''):h.update(part)
    return h.hexdigest()

def check_stopped(state_root):
    # Review may have moved from 8080 to any free port up to 8090.
    for port in range(8080,8091):
        try:
            with socket.create_connection(('127.0.0.1',port),timeout=.15):
                raise RuntimeError('STOP_FLASK_SERVER_BEFORE_MIGRATION')
        except (ConnectionError,OSError):
            pass
    if (state_root/'V4_ORTAK_FABRIKA.lock').exists():
        raise RuntimeError('STOP_RENDER_BEFORE_MIGRATION')
    if (state_root/'V43_BULUT_LINKLEME.lock').exists():
        raise RuntimeError('STOP_CLOUD_BEFORE_MIGRATION')

def sqlite_state_digest(path):
    """Canonical physical snapshot includes committed WAL pages, not just the .db file.

    A short lived read-only connection takes a consistent SQLite online backup
    into an isolated local temp file. This detects changes that plain file SHA
    misses while WAL mode is active. The user's source is never checkpointed.
    """
    path=Path(path)
    with tempfile.TemporaryDirectory(prefix='gorsel-sqlite-check-') as folder:
        snapshot=Path(folder)/'snapshot.sqlite3'
        with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=30)) as src:
            with closing(sqlite3.connect(snapshot,timeout=30)) as dst:
                src.backup(dst,pages=256,sleep=.05)
                if dst.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
                    raise RuntimeError('SQLITE_SOURCE_INTEGRITY_FAILED: '+str(path))
        return digest(snapshot)

def is_sqlite(path):
    return Path(path).suffix.lower() in SQLITE_EXT

def state_root():
    from URETIM_V4.final_guard_v44 import store_v4_root
    return store_v4_root()

def inspect_source(root):
    root=Path(root).resolve(strict=True)
    if not (root/'SABLON_V2_MIMARI'/'ayarlar.db').is_file():
        raise RuntimeError('WORKSPACE_DB_MISSING')
    rows=[]
    for folder,dirs,files in os.walk(root,followlinks=False):
        parent=Path(folder)
        if parent.is_symlink():raise RuntimeError('SYMLINK_SOURCE_DIRECTORY')
        for child in dirs:
            if (parent/child).is_symlink():raise RuntimeError('SYMLINK_SOURCE_DIRECTORY')
        for child in files:
            p=parent/child
            if p.is_symlink():raise RuntimeError('SYMLINK_SOURCE_FILE')
            if p.name.endswith(('-wal','-shm','-journal')):
                continue
            if not p.is_file():raise RuntimeError('SOURCE_NOT_FILE: '+str(p))
            row={'rel':p.relative_to(root).as_posix(),
                 'sha256':digest(p),'bytes':p.stat().st_size}
            if is_sqlite(p):
                row['db_state_sha256']=sqlite_state_digest(p)
            rows.append(row)
    return sorted(rows,key=lambda row:row['rel'])

def stage(source, target):
    source=Path(source).resolve(strict=True)
    target=Path(target).absolute()
    state=state_root()
    check_stopped(state)
    if target.exists() or target.is_symlink():
        raise RuntimeError('TARGET_MUST_BE_NEW_EMPTY_PATH')
    if target==source or source in target.parents or target in source.parents:
        raise RuntimeError('SOURCE_TARGET_OVERLAP')
    if 'onedrive' in str(target).lower():
        raise RuntimeError('TARGET_MUST_BE_OUTSIDE_ONEDRIVE')
    entries=inspect_source(source)
    original={row['rel']:row for row in entries}
    db_rel='SABLON_V2_MIMARI/ayarlar.db'
    if db_rel not in original:raise RuntimeError('DB_NOT_IN_SOURCE')
    target.mkdir(parents=True,exist_ok=False)
    failed=target/'.INCOMPLETE_RUNTIME_MIGRATION'
    failed.write_text('INCOMPLETE; NEVER ACTIVATE',encoding='utf-8')
    copies=[]
    for row in entries:
        rel=row['rel']
        dst=target/rel
        dst.parent.mkdir(parents=True,exist_ok=True)
        if is_sqlite(rel):
            # Every SQLite database needs an online snapshot, not just ayarlar.db.
            # Copying the main file without WAL silently loses committed rows.
            with closing(sqlite3.connect((source/rel).resolve().as_uri()+'?mode=ro',uri=True,timeout=30)) as connection:
                with closing(sqlite3.connect(dst)) as clone:
                    connection.backup(clone,pages=256,sleep=.05)
                    if clone.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
                        raise RuntimeError('SNAPSHOT_INTEGRITY_FAILED: '+rel)
            if sqlite_state_digest(dst)!=row['db_state_sha256']:
                raise RuntimeError('SOURCE_SQLITE_CHANGED_DURING_MIGRATION: '+rel)
        else:
            with (source/rel).open('rb') as src, dst.open('xb') as out:
                shutil.copyfileobj(src,out,length=1024*1024)
                out.flush();os.fsync(out.fileno())
            if digest(dst)!=row['sha256']:
                raise RuntimeError('COPIED_IMAGE_SHA_CHANGED: '+rel)
        copies.append({'rel':rel,'sha256':digest(dst),'source_sha256':row['sha256'],
                       'source_db_state_sha256':row.get('db_state_sha256'),
                       'bytes':dst.stat().st_size})
    if inspect_source(source)!=entries:
        raise RuntimeError('SOURCE_CHANGED_DURING_MIGRATION_RESTAGE')
    manifest={'schema':2,'origin':str(source),'target':str(target),
              'files':copies,'source_file_count':len(entries),
              'source_unchanged':True,'source_was_deleted':False,
              'source_db_sha256':original[db_rel]['sha256'],
              'activation_requires_confirmation':True}
    receipt=target/RECEIPT
    receipt.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    failed.unlink()
    return {'target':str(target),'count':len(copies),'receipt':str(receipt),
            'activated':False}

def activate(target,phrase):
    if phrase!=CONFIRM:raise PermissionError('EXPLICIT_RUNTIME_ACTIVATION_REQUIRED')
    target=Path(target).resolve(strict=True)
    check_stopped(state_root())
    if (target/'.INCOMPLETE_RUNTIME_MIGRATION').exists():
        raise RuntimeError('RUNTIME_MIGRATION_INCOMPLETE')
    receipt=target/RECEIPT
    record=json.loads(receipt.read_text(encoding='utf-8'))
    if record.get('schema')!=2:
        raise RuntimeError('RUNTIME_RESTAGE_REQUIRED_OLD_UNSAFE_RECEIPT')
    if record.get('target')!=str(target):
        raise RuntimeError('RUNTIME_RECEIPT_INVALID')
    source=Path(record['origin'])
    rows=inspect_source(source)
    if len(rows)!=record['source_file_count']:
        raise RuntimeError('LIVE_SOURCE_FILE_SET_CHANGED_AFTER_STAGING')
    expected={r['rel']:r for r in rows}
    saved=record.get('files')
    if not isinstance(saved,list) or len(saved)!=len(expected):
        raise RuntimeError('RUNTIME_RECEIPT_FILESET_INVALID')
    saved_names=[item['rel'] for item in saved]
    if len(saved_names)!=len(set(saved_names)) or set(saved_names)!=set(expected):
        raise RuntimeError('RUNTIME_RECEIPT_FILESET_INVALID')
    # The target must be an exact copy, with no unmanifested files added later.
    actual_files=set()
    for folder,dirs,files in os.walk(target,followlinks=False):
        parent=Path(folder)
        if parent.is_symlink() or any((parent/name).is_symlink() for name in dirs+files):
            raise RuntimeError('STAGED_SYMLINK_FORBIDDEN')
        for name in files:
            p=parent/name
            if p==receipt:continue
            # A harmless read of a WAL-mode staged SQLite DB may create
            # -wal/-shm sidecars. They are not independent application files.
            # Only tolerate sidecars of a manifest-listed DB, then verify the
            # DB's full committed WAL state against the receipt below.
            if p.name.endswith(('-wal','-shm')):
                base=Path(str(p)[:-4])
                if (base.relative_to(target).as_posix() in saved_names
                        and is_sqlite(base)):
                    continue
            actual_files.add(p.relative_to(target).as_posix())
    if actual_files!=set(saved_names):
        raise RuntimeError('STAGED_EXTRA_OR_MISSING_FILES')
    for item in saved:
        rel=item['rel']
        if (item['source_sha256']!=expected[rel]['sha256'] or
                item.get('source_db_state_sha256')!=expected[rel].get('db_state_sha256')):
            raise RuntimeError('LIVE_SOURCE_CHANGED_AFTER_STAGING: '+rel)
        if digest(target/rel)!=item['sha256']:
            raise RuntimeError('STAGED_COPY_TAMPERED: '+rel)
        if is_sqlite(rel) and sqlite_state_digest(target/rel)!=item['source_db_state_sha256']:
            raise RuntimeError('STAGED_SQLITE_STATE_CHANGED: '+rel)
    with sqlite3.connect(target/'SABLON_V2_MIMARI'/'ayarlar.db') as con:
        if con.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
            raise RuntimeError('STAGED_SQLITE_BROKEN')
    before=local_state_dir()/'workspace.json'
    if before.exists():
        backup=local_state_dir()/('workspace.v473.previous_'+uuid.uuid4().hex+'.json')
        shutil.copy2(before,backup)
    store_runtime_choice(target)
    return {'active_workspace':str(target),'old_workspace_kept':str(source),
            'files_verified':len(record['files'])}

