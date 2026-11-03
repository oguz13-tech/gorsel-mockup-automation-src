"""V4.9.9 extracted file manifest verifier; read-only, no user data touched."""
from pathlib import Path
import hashlib,json,sys
ROOT=Path(__file__).resolve().parents[1]

def main():
    try:
        obj=json.loads((ROOT/'SHA256_MANIFEST.json').read_text('utf-8'))
        if obj.get('version')!='V4.9.9':raise ValueError('Version mismatch')
        records=obj['files'];names=set();faults=[]
        for row in records:
            rel=row['path']
            if not isinstance(rel,str) or rel.startswith('/') or '..' in Path(rel).parts or rel in names:
                faults.append((rel,'path/duplicate'));continue
            names.add(rel)
            target=ROOT/rel
            if target.is_symlink() or not target.is_file():faults.append((rel,'missing/symlink'));continue
            if target.stat().st_size!=row['bytes'] or hashlib.sha256(target.read_bytes()).hexdigest()!=row['sha256']:
                faults.append((rel,'SHA256/size mismatch'))
        print('V4.9.9 manifest:',len(records),'file, error:',len(faults))
        for row in faults[:15]:print('ERROR',row)
        return 0 if not faults else 1
    except (OSError,ValueError,TypeError,KeyError) as e:
        print('MANIFEST ERROR:',str(e));return 1
if __name__=='__main__':sys.exit(main())
