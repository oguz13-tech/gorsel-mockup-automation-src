"""Explicitly acknowledge user-deleted outputs without losing production history.

Only RENDERED records whose output is genuinely missing and safely inside
this local production root can become USER_REMOVED. Nothing is unlinked from
disk. SHA, SKU, source hashes, and the original output path stay in SQLite.
"""
from __future__ import annotations
import datetime as dt
import json
import os
from pathlib import Path
import sqlite3
import uuid

from .final_guard_v44 import backup_and_restore_trial, BACKUP_CONFIRM


def missing_user_candidates(production_root: Path) -> list[dict]:
    root = Path(production_root).resolve()
    db = root / 'v4_ortak_uretim.sqlite3'
    if db.is_symlink() or not db.is_file():
        raise ValueError('URETIM_DB_NOT_FOUND')
    output_root = (root / 'uretilen_gorseller').resolve()
    with sqlite3.connect(db.resolve().as_uri() + '?mode=ro', uri=True) as con:
        if con.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
            raise ValueError('URETIM_DB_INTEGRITY')
        rows = con.execute(
            "SELECT key, output, output_sha, status FROM artifact WHERE status='RENDERED' ORDER BY key"
        ).fetchall()
    missing = []
    for key, output, sha, status in rows:
        path = Path(output)
        if path.is_symlink():
            continue
        resolved = path.resolve(strict=False)
        if output_root not in resolved.parents or path.is_file():
            continue
        if path.exists():
            continue  # A directory or inaccessible target is NOT a user deletion.
        if not isinstance(sha, str) or len(sha) != 64:
            continue
        missing.append({'key': key, 'output': str(path), 'output_sha': sha})
    return missing


def acknowledge_user_deleted(production_root: Path, runtime_root: Path, *,
                             expected_keys: list[str], confirm: str,
                             reviewer: str = 'Windows Operator') -> dict:
    if confirm != 'I_CONFIRM_THESE_FILES_WERE_DELETED_BY_ME':
        raise PermissionError('Kullanıcı tarafından silindiği açıkça onaylanmalı.')
    if not expected_keys or len(expected_keys) != len(set(expected_keys)):
        raise ValueError('INVALID_EXPECTED_KEYS')
    root = Path(production_root).resolve()
    ledger = root / 'v4_ortak_uretim.sqlite3'
    lock = root / 'V4_ORTAK_FABRIKA.lock'
    if root.is_symlink() or ledger.is_symlink() or lock.is_symlink():
        raise ValueError('UNSAFE_PATH')
    # Same create-only exclusive lock used by the batch producer.
    with lock.open('x', encoding='utf-8') as fp:
        fp.write(str(os.getpid()) + '\n')
        fp.flush()
        os.fsync(fp.fileno())
    try:
        previous = missing_user_candidates(root)
        by_key = {x['key']: x for x in previous}
        if set(expected_keys) != set(by_key):
            raise RuntimeError('MISSING_SET_CHANGED: Yeni raporu inceleyip tekrar onaylayın.')
        # New online SQLite snapshots + restore rehearsal, outside OneDrive.
        backup = backup_and_restore_trial(
            Path(runtime_root), root, confirm=BACKUP_CONFIRM
        )
        with sqlite3.connect(ledger, timeout=30) as con:
            con.execute('PRAGMA busy_timeout=30000')
            con.execute('BEGIN IMMEDIATE')
            current = missing_user_candidates(root)
            if set(x['key'] for x in current) != set(expected_keys):
                raise RuntimeError('CONCURRENT_OR_CHANGED_FILES')
            for record in current:
                key = record['key']
                found = con.execute(
                    "SELECT output,output_sha,status FROM artifact WHERE key=?", (key,)
                ).fetchone()
                if found != (record['output'], record['output_sha'], 'RENDERED'):
                    raise RuntimeError('ROW_CHANGED')
                result = con.execute(
                    """UPDATE artifact SET status='USER_REMOVED',
                       message='USER_CONFIRMED_REMOVAL', updated=CURRENT_TIMESTAMP
                       WHERE key=? AND output=? AND output_sha=? AND status='RENDERED'""",
                    (key, record['output'], record['output_sha']),
                )
                if result.rowcount != 1:
                    raise RuntimeError('ROW_UPDATE_CONFLICT')
            con.commit()
        # Keep an additional readable proof separate from the DB backup.
        report_dir = root / 'raporlar'
        report_dir.mkdir(parents=True, exist_ok=True)
        proof = report_dir / (
            'USER_REMOVED_' + dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
            + '_' + uuid.uuid4().hex[:10] + '.json')
        data = {'action': 'USER_CONFIRMED_REMOVAL', 'reviewer': reviewer,
                'count': len(previous), 'records': previous,
                'db_backup_proof': backup['report_path'],
                'files_deleted_by_this_action': 0}
        with proof.open('x', encoding='utf-8') as out:
            json.dump(data, out, ensure_ascii=False, indent=2)
        return {'status': 'USER_REMOVED_RECORDED', 'count': len(previous),
                'report_path': str(proof), 'backup_path': backup['report_path']}
    finally:
        # Lock is owned by this call; never unlink anyone else's lock.
        lock.unlink()
