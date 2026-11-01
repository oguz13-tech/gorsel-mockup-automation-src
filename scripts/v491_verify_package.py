"""Verify all V4.9.1 package files using SHA-256; read-only."""
from __future__ import annotations
import json
import hashlib
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def main():
    manifest=json.loads((ROOT/'SHA256_MANIFEST.json').read_text(encoding='utf-8'))
    fails=[]
    for entry in manifest['files']:
        path=ROOT/entry['path']
        if not path.is_file():
            fails.append(entry['path']+': NOT FOUND')
            continue
        h=hashlib.sha256()
        with path.open('rb') as f:
            for b in iter(lambda:f.read(1024*1024),b''):
                h.update(b)
        if path.stat().st_size!=entry['bytes'] or h.hexdigest()!=entry['sha256']:
            fails.append(entry['path']+': HASH/SIZE MISMATCH')
    print(f"V4.9.1 SHA256: checked={len(manifest['files'])}, errors={len(fails)}")
    for f in fails[:30]:print('HATA:',f)
    return 0 if not fails else 1

if __name__=='__main__':
    raise SystemExit(main())
