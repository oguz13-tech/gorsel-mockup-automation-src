"""Read-only V4.11.2 integrity: exact manifest member set + SHA256."""
import hashlib
from pathlib import Path

def verify():
    root=Path(__file__).resolve().parents[1]
    manifest=root/'V4112_SHA256_MANIFEST.txt'
    expected={}
    for row in manifest.read_text('utf-8').splitlines():
        if not row or row.startswith('#'):continue
        sha,rel=row.split('  ',1)
        if rel in expected:raise SystemExit('DUPLICATE MANIFEST ENTRY: '+rel)
        expected[rel]=sha
    actual={p.relative_to(root).as_posix() for p in root.rglob('*')
            if p.is_file() and '__pycache__' not in p.parts and '.pytest_cache' not in p.parts
            and p.suffix not in ('.pyc',) and p.name!=manifest.name}
    # Users may create runtime files in their test directory; only enforce the
    # inclusion of the original package files, not runtime-generated outputs.
    missing=set(expected)-actual
    if missing:raise SystemExit('MISSING FILES: '+repr(sorted(missing)[:10]))
    for rel,sha in expected.items():
        if hashlib.sha256((root/rel).read_bytes()).hexdigest()!=sha:
            raise SystemExit('SHA256 MISMATCH: '+rel)
    print('PETEK V4.11.2 SHA256 PASS:',len(expected),'files')

if __name__=='__main__':verify()
