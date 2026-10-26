"""Durable, fail-closed STOPPED -> RESUME cursor for the real unified batch.

A checkpoint contains only a frozen recipe, selected approved UIDs, SHA-256
inventory, random seed and safe progress counters. It NEVER modifies the
legacy user workspace, approved profiles, images, or production ledger.
On resume, the engine repeats the same deterministic job order and relies on
the existing create-only, SHA-verified ledger to skip completed outputs.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import tempfile

SCHEMA = 1
BASENAME = 'v47_last_batch_resume.json'
ALLOWED_STATES = {'RUNNING', 'STOPPED', 'COMPLETED', 'INTERRUPTED'}
MAX_BYTES = 8 * 1024 * 1024


def _canonical(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


def _wrap(payload):
    return {
        'format': 'V47_SAFE_BATCH_CHECKPOINT',
        'sha256': hashlib.sha256(_canonical(payload)).hexdigest(),
        'payload': payload,
    }


def checkpoint_path(root: Path) -> Path:
    root = Path(root)
    if root.is_symlink():
        raise ValueError('CHECKPOINT_ROOT_SYMLINK')
    path = root / BASENAME
    if path.is_symlink():
        raise ValueError('CHECKPOINT_SYMLINK')
    return path


def read_checkpoint(root: Path) -> dict | None:
    path = checkpoint_path(root)
    if not path.exists():
        return None
    if not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise ValueError('CHECKPOINT_UNSAFE_SIZE')
    envelope = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(envelope,dict) or envelope.get('format') != 'V47_SAFE_BATCH_CHECKPOINT':
        raise ValueError('CHECKPOINT_FORMAT_INVALID')
    payload=envelope.get('payload')
    if not isinstance(payload,dict) or payload.get('schema')!=SCHEMA:
        raise ValueError('CHECKPOINT_SCHEMA_INVALID')
    digest=hashlib.sha256(_canonical(payload)).hexdigest()
    if envelope.get('sha256')!=digest:
        raise ValueError('CHECKPOINT_SHA_MISMATCH')
    if payload.get('status') not in ALLOWED_STATES:
        raise ValueError('CHECKPOINT_STATUS_INVALID')
    if not isinstance(payload.get('config'),dict) or not isinstance(payload.get('inventory'),dict):
        raise ValueError('CHECKPOINT_FIELDS_INVALID')
    return payload


def write_checkpoint(root: Path, payload: dict) -> Path:
    path=checkpoint_path(root)
    root=path.parent
    root.mkdir(parents=True,exist_ok=True)
    raw=_canonical(_wrap(payload))
    if len(raw)>MAX_BYTES:
        raise ValueError('CHECKPOINT_TOO_LARGE')
    fd, temp_name=tempfile.mkstemp(prefix='.v47-resume-',suffix='.tmp',dir=root)
    temp=Path(temp_name)
    try:
        with os.fdopen(fd,'wb') as out:
            out.write(raw)
            out.flush()
            os.fsync(out.fileno())
        if path.is_symlink():
            raise ValueError('CHECKPOINT_SYMLINK')
        os.replace(temp,path)
    finally:
        temp.unlink(missing_ok=True)
    return path


def snapshot_inputs(design_paths: list[Path], production_plan: list[tuple[str,list[dict]]]):
    from .store_profiles_v47 import key_for
    def sha(path):
        h=hashlib.sha256()
        with Path(path).open('rb') as fh:
            for block in iter(lambda: fh.read(1024*1024),b''):
                h.update(block)
        return h.hexdigest()
    arts={}
    for art in design_paths:
        path=Path(art)
        if path.is_symlink() or not path.is_file():
            raise ValueError('CHECKPOINT_DESIGN_INVALID')
        arts[str(path.resolve())]=sha(path)
    template_groups={}
    for store,templates in production_plan:
        template_groups[store]=sorted(key_for(item) for item in templates)
    return {'designs':arts,'groups':template_groups}


def same_inputs(a: dict, b: dict) -> bool:
    return a == b
