"""Read-only SHA256 consistency test for V4.11.1."""
import hashlib
from pathlib import Path

def verify():
    root = Path(__file__).resolve().parents[1]
    manifest = root / 'V4111_SHA256_MANIFEST.txt'
    total = 0
    for row in manifest.read_text('utf-8').splitlines():
        if not row or row.startswith('#'): continue
        expected, rel = row.split('  ', 1)
        path = root / rel
        if not path.is_file(): raise SystemExit('MISSING: ' + rel)
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise SystemExit('SHA256 MISMATCH: ' + rel)
        total += 1
    print('PETEK V4.11.1 SHA256 PASS:', total, 'files')

if __name__ == '__main__': verify()
