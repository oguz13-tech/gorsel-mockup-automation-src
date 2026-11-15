"""Operator-confirmed historical output deletions, never automatic repair.

An absent file is not evidence of intentional removal. The tool can only
change RENDERED -> USER_REMOVED after the operator selects exact ledger keys,
with a verified online SQLite backup, transactional compare-and-swap and a
read-only plan fingerprint. No working image or historic backup is touched.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import uuid
from .final_guard_v44 import store_v4_root

CONFIRM='35 ÇIKTIYI BEN SİLDİM, KAYITLARI USER_REMOVED OLARAK İŞARETLE'
DB_NAME='v4_ortak_uretim.sqlite3'

def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1048576),b''):h.update(chunk)
    return h.hexdigest()

def candidate_rows(root=None):
    """Read-only exact absence proof for RENDERED ledger rows only."""
    root=Path(root or store_v4_root()).resolve()
    db=root/DB_NAME
    if not db.is_file() or db.is_symlink():
        raise ValueError('LEDGER_DB_MISSING_OR_SYMLINK')
    outputs=(root/'uretilen_gorseller').resolve()
    with sqlite3.connect(db.resolve().as_uri()+'?mode=ro',uri=True,timeout=10) as c:
        c.row_factory=sqlite3.Row
        if c.execute('PRAGMA quick_check').fetchone()[0]!='ok':
            raise RuntimeError('LEDGER_INTEGRITY_FAILED')
        items=[]
        counts={}
        for item in c.execute(
            'SELECT key,sku,status,output,output_sha,category FROM artifact ORDER BY key'
        ):
            row=dict(item)
            status=row['status']
            counts[status]=counts.get(status,0)+1
            if status!='RENDERED':continue
            output=Path(row['output'])
            if output.is_symlink():continue
            resolved=output.resolve(strict=False)
            if outputs not in resolved.parents:continue
            if output.exists():continue
            items.append({k:row[k] for k in ('key','sku','category','output','output_sha','status')})
    return {'schema':1,'ledger':str(db),'ledger_sha':digest(db),
            'output_root':str(outputs),'rendered_missing_candidates':items,
            'status_counts':counts,'count':len(items),
            'warning':'Missing files become USER_REMOVED ONLY with explicit user selection.'}

def save_plan(plan,folder=None):
    folder=Path(folder or Path(os.environ.get('LOCALAPPDATA') or Path.home())/
                'GorselMockup'/'UnifiedCenter'/'USER_REMOVED_REVIEW')
    folder.mkdir(parents=True,exist_ok=True)
    p=folder/('USER_REMOVED_PLAN_'+uuid.uuid4().hex[:12]+'.json')
    with p.open('x',encoding='utf-8') as f:
        json.dump(plan,f,ensure_ascii=False,indent=2)
    return p

def mark_selected(plan_path,keys,phrase,*,expected_count=35):
    if phrase!=CONFIRM:raise PermissionError('EXPLICIT_USER_REMOVED_CONFIRMATION_REQUIRED')
    plan=json.loads(Path(plan_path).read_text(encoding='utf-8'))
    if plan.get('schema')!=1:raise ValueError('USER_REMOVED_PLAN_SCHEMA')
    fresh=candidate_rows(Path(plan['ledger']).parent)
    if (fresh['ledger']!=plan['ledger'] or
            fresh['ledger_sha']!=plan['ledger_sha'] or
            fresh['rendered_missing_candidates']!=plan['rendered_missing_candidates']):
        raise RuntimeError('LEDGER_OR_MISSING_OUTPUTS_CHANGED_SINCE_REPORT')
    selected=set(keys)
    if len(selected)!=len(keys) or not selected:
        raise ValueError('USER_REMOVED_SELECTED_KEYS_EMPTY_OR_DUPLICATE')
    available={row['key']:row for row in fresh['rendered_missing_candidates']}
    if not selected.issubset(available):
        raise ValueError('USER_REMOVED_SELECTED_KEY_NOT_MISSING')
    if expected_count is not None and len(selected)!=int(expected_count):
        raise ValueError('USER_REMOVED_COUNT_UNEXPECTED: '+str(len(selected)))
    db=Path(plan['ledger'])
    base=Path(os.environ.get('LOCALAPPDATA') or Path.home())/'GorselMockup'/'UserRemovedBackups'
    backup=base/('LEDGER_BEFORE_'+uuid.uuid4().hex)
    backup.mkdir(parents=True,exist_ok=False)
    backup_db=backup/'v4_ortak_uretim.before.sqlite3'
    with sqlite3.connect(db) as source:
        with sqlite3.connect(backup_db) as dest:
            source.backup(dest)
            if dest.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
                raise RuntimeError('USER_REMOVED_BACKUP_INTEGRITY_FAILED')
    # Late validation limits races; the CAS transaction changes only the exact
    # user-selected rows. The original stored SHA and file path are retained.
    with sqlite3.connect(db,timeout=30,isolation_level=None) as c:
        c.execute('BEGIN IMMEDIATE')
        try:
            for key in sorted(selected):
                row=available[key]
                output=Path(row['output'])
                if output.is_symlink() or output.exists():
                    raise RuntimeError('OUTPUT_REAPPEARED_ABORT: '+key)
                current=c.execute('SELECT status,output,output_sha FROM artifact WHERE key=?',
                                  (key,)).fetchone()
                if current != ('RENDERED',row['output'],row['output_sha']):
                    raise RuntimeError('LEDGER_ROW_CHANGED_ABORT: '+key)
            for key in sorted(selected):
                changed=c.execute(
                    "UPDATE artifact SET status='USER_REMOVED', "
                    "message='OWNER_CONFIRMED_INTENTIONAL_DELETION', "
                    "updated=CURRENT_TIMESTAMP WHERE key=? AND status='RENDERED'",
                    (key,))
                if changed.rowcount!=1:raise RuntimeError('LEDGER_STATUS_CHANGED_ABORT: '+key)
            c.execute('COMMIT')
        except BaseException:
            c.execute('ROLLBACK')
            raise
    result={'status':'USER_REMOVED_MARKED','keys':sorted(selected),
            'marked':len(selected),'backup':str(backup_db),
            'images_deleted':0,'historical_artifact_rows_deleted':0}
    (backup/'USER_REMOVED_RECEIPT.json').write_text(
        json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return result
