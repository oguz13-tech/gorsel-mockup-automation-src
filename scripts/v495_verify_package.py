"""Read-only full SHA256 verifier for V4.9.5 distributable; no database or image writes."""
from pathlib import Path
import hashlib, json, sys
ROOT=Path(__file__).resolve().parents[1]
def main():
    manifest=json.loads((ROOT/'SHA256_MANIFEST.json').read_text(encoding='utf8'))
    if manifest.get('version')!='V4.9.5':print('WRONG VERSION');return 1
    files=manifest['files'];problems=[];names=set()
    for entry in files:
        rel=entry['path']
        if rel in names or rel.startswith('/') or '..' in Path(rel).parts:
            problems.append((rel,'unsafe or duplicate path'));continue
        names.add(rel)
        file=ROOT/rel
        if file.is_symlink() or not file.is_file():problems.append((rel,'missing or symlink'));continue
        digest=hashlib.sha256(file.read_bytes()).hexdigest()
        if digest!=entry['sha256'] or file.stat().st_size!=entry['bytes']:
            problems.append((rel,'SHA256/size mismatch'))
    actual={str(p.relative_to(ROOT)).replace('\\','/') for p in ROOT.rglob('*')
            if p.is_file() and p.name!='SHA256_MANIFEST.json' and not '__pycache__' in p.parts}
    # The installer creates .venv and legitimate runtime receipts later.
    # Verify every shipped file, but do not fail because of newly installed
    # models, user reports, Python caches or unrelated local files.
    unexpected=actual-names
    print(f'V4.9.5 SHA256: {len(files)} doğrulandı; {len(problems)} sorun; '
          f'{len(unexpected)} sonradan eklenen dosya (manifest dışı)')
    for file,why in problems[:40]:print('HATA:',file,why)
    return 0 if not problems else 1
if __name__=='__main__':sys.exit(main())
