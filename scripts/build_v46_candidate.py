"""Rebuild a code-only Windows candidate from tracked public source.

Never traverses a runtime or packages images, DBs, config JSON or local files.
"""
from pathlib import Path, PurePosixPath
import hashlib,json,subprocess,zipfile,argparse
ROOT=Path(__file__).resolve().parents[1]
DIRS={'MERKEZ','SABLON_V2_MIMARI','99_SISTEM_MOTORLARI_VE_KODLAR','BAGIMSIZ_ARACLAR',
      'AI_Kalite_Artirici','scripts','TESTLER','tests','LEGACY_REFERANS_KOD'}
EXT={'.py','.js','.cjs','.html','.css','.bat','.ps1','.txt','.md'}
TOP={'BASLAT_V47_WINDOWS.bat','BASLAT_V46_WINDOWS.bat','KUR_REAL_ESRGAN_4K_WINDOWS.bat','KUR_REAL_ESRGAN_4K_WINDOWS.ps1'}
DOCS={'docs/V47_P1_P2_QA_RUNBOOK.md','docs/V46_CANDIDATE_RUNBOOK.md','docs/V46_ACCEPTANCE_CURRENT.md','docs/V46_LIVE_CHECKPOINTS.md'}

def allowed(name):
    p=PurePosixPath(name)
    return (name in TOP or name in DOCS or
            (p.parts[0] in DIRS and p.suffix in EXT and
             not any(x in {'.venv','__pycache__','logs','output','artifacts'} for x in p.parts) and
             p.name!='gercek_10_ornek_qa.py'))

def build(destination,source=ROOT):
    source=Path(source);destination=Path(destination);destination.mkdir(parents=True,exist_ok=True)
    paths=subprocess.check_output(['git','ls-files','-z'],cwd=source).decode().split('\0')
    sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip()
    files={n:(source/n).read_bytes() for n in sorted(paths) if n and allowed(n) and not (source/n).is_symlink()}
    for required in ['BASLAT_V47_WINDOWS.bat','BASLAT_V46_WINDOWS.bat','MERKEZ/merkez.py','SABLON_V2_MIMARI/app.py','SABLON_V2_MIMARI/static/js/edge_angles_v46.js']:
        if required not in files:raise ValueError('Missing required code: '+required)
    manifest={'release':'V4.7.1 CANDIDATE','acceptance':'WINDOWS_NOT_VERIFIED','source_commit':sha,
              'files':[{ 'path':n,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()} for n,b in files.items()]}
    files['SHA256_MANIFEST.json']=json.dumps(manifest,ensure_ascii=False,indent=2).encode()
    target=destination/('GORSEL_V47_WINDOWS_CANDIDATE_'+sha[:12]+'.zip')
    with target.open('xb') as f:
        with zipfile.ZipFile(f,'w',compression=zipfile.ZIP_DEFLATED) as z:
            for name,data in files.items():
                info=zipfile.ZipInfo('GORSEL_V46_CANDIDATE/'+name,date_time=(2026,10,26,0,0,0))
                info.compress_type=zipfile.ZIP_DEFLATED;z.writestr(info,data)
    digest=hashlib.sha256(target.read_bytes()).hexdigest()
    target.with_suffix('.zip.sha256').write_text(digest+'  '+target.name+'\n')
    print(json.dumps({'zip':str(target),'sha256':digest,'source_commit':sha,'files':len(files)}))
    return target
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);build(p.parse_args().output)
