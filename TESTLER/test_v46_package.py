from pathlib import Path
import sys,zipfile,json,hashlib
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.build_v46_candidate import allowed,build

def test_private_data_excluded():
    for p in ['ayarlar.json','MERKEZ/settings.json','MERKEZ/ayarlar.db','2_SABLON_HAVUZU/p.png',
              'artifacts/v46/REVIEW_SELECTION_LOCAL.json','MERKEZ/.venv/a.py','TESTLER/gercek_10_ornek_qa.py']:
        assert not allowed(p),p

def test_candidate_manifest_matches_every_byte(tmp_path):
    zpath=build(tmp_path)
    with zipfile.ZipFile(zpath) as z:
        prefix='GORSEL_V46_CANDIDATE/'
        manifest=json.loads(z.read(prefix+'SHA256_MANIFEST.json'))
        assert manifest['acceptance']=='WINDOWS_NOT_VERIFIED'
        assert len(z.namelist())==len(manifest['files'])+1
        for item in manifest['files']:
            assert allowed(item['path'])
            b=z.read(prefix+item['path'])
            assert len(b)==item['bytes'] and hashlib.sha256(b).hexdigest()==item['sha256']
