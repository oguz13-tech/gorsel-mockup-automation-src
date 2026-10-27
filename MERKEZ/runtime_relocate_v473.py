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
from legacy_manager import store_runtime_choice, local_state_dir

CONFIRM='ONAYLIYORUM: ONEDRIVE DIŞINDAKİ DOĞRULANMIŞ ÇALIŞMA ALANINI ETKİNLEŞTİR'
RECEIPT='.V473_RUNTIME_MIGRATION_RECEIPT.json'

def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as src:
        for part in iter(lambda:src.read(1024*1024),b''):h.update(part)
    return h.hexdigest()

def check_stopped(state_root):
    try:
        with socket.create_connection(('127.0.0.1',8080),timeout=.4):
            raise RuntimeError('STOP_FLASK_SERVER_BEFORE_MIGRATION')
    except (ConnectionError,OSError):
        pass
    if (state_root/'V4_ORTAK_FABRIKA.lock').exists():
        raise RuntimeError('STOP_RENDER_BEFORE_MIGRATION')
    if (state_root/'V43_BULUT_LINKLEME.lock').exists():
        raise RuntimeError('STOP_CLOUD_BEFORE_MIGRATION')

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
            rows.append({'rel':p.relative_to(root).as_posix(),
                         'sha256':digest(p),'bytes':p.stat().st_size})
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
        if rel==db_rel:
            # Snapshot includes committed WAL pages without copying live WAL.
            with sqlite3.connect(source/rel,timeout=30) as connection:
                with sqlite3.connect(dst) as clone:
                    connection.backup(clone,pages=256,sleep=.05)
                    if clone.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
                        raise RuntimeError('SNAPSHOT_INTEGRITY_FAILED')
        else:
            with (source/rel).open('rb') as src, dst.open('xb') as out:
                shutil.copyfileobj(src,out,length=1024*1024)
                out.flush();os.fsync(out.fileno())
            if digest(dst)!=row['sha256']:
                raise RuntimeError('COPIED_IMAGE_SHA_CHANGED: '+rel)
        copies.append({'rel':rel,'sha256':digest(dst),'source_sha256':row['sha256'],
                       'bytes':dst.stat().st_size})
    if inspect_source(source)!=entries:
        raise RuntimeError('SOURCE_CHANGED_DURING_MIGRATION_RESTAGE')
    manifest={'schema':1,'origin':str(source),'target':str(target),
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
    if record.get('schema')!=1 or record.get('target')!=str(target):
        raise RuntimeError('RUNTIME_RECEIPT_INVALID')
    source=Path(record['origin'])
    rows=inspect_source(source)
    if len(rows)!=record['source_file_count']:
        raise RuntimeError('LIVE_SOURCE_FILE_SET_CHANGED_AFTER_STAGING')
    expected={r['rel']:r for r in rows}
    for item in record['files']:
        rel=item['rel']
        if rel not in expected or item['source_sha256']!=expected[rel]['sha256']:
            raise RuntimeError('LIVE_SOURCE_CHANGED_AFTER_STAGING: '+rel)
        if digest(target/rel)!=item['sha256']:
            raise RuntimeError('STAGED_COPY_TAMPERED: '+rel)
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

