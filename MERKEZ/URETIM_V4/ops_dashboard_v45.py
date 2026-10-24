"""Read-only production health summary. This module creates no DB or artifacts.

Only reports already-stored category/status/SHA evidence. A separate explicit
operator action is required for any repair or external cloud upload.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import hashlib
import shutil
import sqlite3


def _digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as fp:
        for data in iter(lambda: fp.read(1024 * 1024), b''):
            h.update(data)
    return h.hexdigest()


def summarize(state_root: Path, *, verify_files: bool = True) -> dict:
    root = Path(state_root).absolute()
    ledger = root / 'v4_ortak_uretim.sqlite3'
    if not ledger.is_file() or ledger.is_symlink():
        raise ValueError('Üretim kayıt veritabanı yok veya güvenli değil; yeni DB oluşturulmadı.')
    uri = ledger.resolve(strict=True).as_uri() + '?mode=ro'
    statuses, cats = Counter(), Counter()
    missing = mismatch = verified = unsafe = 0
    totals = 0
    with sqlite3.connect(uri, uri=True, timeout=15) as db:
        if db.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
            raise ValueError('Üretim DB SQLite quick_check başarısız.')
        cols = {r[1] for r in db.execute('PRAGMA table_info(artifact)')}
        if not {'status', 'category', 'output', 'output_sha'}.issubset(cols):
            raise ValueError('Üretim DB tablo şeması beklenenden farklı.')
        for category, status, output, expected in db.execute(
                'SELECT category,status,output,output_sha FROM artifact'):
            totals += 1
            statuses[str(status)] += 1
            cats[str(category)] += 1
            if status != 'RENDERED' or not verify_files:
                continue
            path = Path(str(output))
            if path.is_symlink() or (root / 'uretilen_gorseller').resolve(strict=False) not in path.resolve(strict=False).parents:
                unsafe += 1
            elif not path.is_file():
                missing += 1
            elif _digest(path) != expected:
                mismatch += 1
            else:
                verified += 1
    disk = shutil.disk_usage(root)
    return {'mode': 'READ_ONLY', 'total': totals, 'status_counts': dict(statuses),
            'categories': dict(cats), 'verified': verified, 'missing': missing,
            'sha_mismatch': mismatch, 'unsafe': unsafe,
            'disk_free_gb': round(disk.free / (1024 ** 3), 2),
            'actual_file_verification': bool(verify_files)}
