"""Rebuild a code-only Windows candidate from tracked public source.

Never traverses a runtime or packages images, DBs, config JSON or local files.
"""
from pathlib import Path, PurePosixPath
import hashlib,json,subprocess,zipfile,argparse
ROOT=Path(__file__).resolve().parents[1]
DIRS={'MERKEZ','SABLON_V2_MIMARI','99_SISTEM_MOTORLARI_VE_KODLAR','BAGIMSIZ_ARACLAR',
      'AI_Kalite_Artirici','scripts','TESTLER','tests','LEGACY_REFERANS_KOD'}
EXT={'.py','.js','.cjs','.html','.css','.bat','.ps1','.txt','.md'}
TOP={'BAKIM_V472_MAGENTA_KLASOR_DENETIM_WINDOWS.bat','BASLAT_V47_WINDOWS.bat','BASLAT_V46_WINDOWS.bat','KUR_REAL_ESRGAN_4K_WINDOWS.bat','KUR_REAL_ESRGAN_4K_WINDOWS.ps1'}
DOCS={'docs/V475_FINAL_CODE_DELIVERY.md','docs/V473_FINAL_SAFE_HANDOFF.md','docs/V472_MAGENTA_AND_EXTERNAL_INVENTORY.md','docs/V47_P1_P2_QA_RUNBOOK.md','docs/V46_CANDIDATE_RUNBOOK.md','docs/V46_ACCEPTANCE_CURRENT.md','docs/V46_LIVE_CHECKPOINTS.md'}

PINNED_PUBLIC_DATA={'MERKEZ/GUNLUK/INSTALLED_NUMBER_SPEC.json'}
def allowed(name):
    p=PurePosixPath(name)
    # Generated references are .txt, never runnable .bat/.ps1/.py files.
    if len(p.parts)==2 and (
            (p.parts[0]=='LEGACY_LAUNCHERS_REFERENCE'
             and p.name.lower().endswith(('.bat.reference.txt','.ps1.reference.txt')))
            or (p.parts[0]=='LEGACY_TOOLS_REFERENCE'
                and p.name.lower().endswith('.py.reference.txt'))):
        return True
    return (name in TOP or name in DOCS or name in PINNED_PUBLIC_DATA or
            (p.parts[0] in DIRS and p.suffix in EXT and
             not any(x in {'.venv','__pycache__','logs','output','artifacts'} for x in p.parts) and
             p.name!='gercek_10_ornek_qa.py'))

def build(destination,source=ROOT):
    source=Path(source);destination=Path(destination);destination.mkdir(parents=True,exist_ok=True)
    paths=subprocess.check_output(['git','ls-files','-z'],cwd=source).decode().split('\0')
    sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip()
    files={n:(source/n).read_bytes() for n in sorted(paths) if n and allowed(n) and not (source/n).is_symlink()}
    # Preserve every older standalone Windows entry point as NONEXECUTABLE
    # documentation, never as a second active launcher. Former installers and
    # rollback scripts may contain stale absolute workspace paths.
    legacy_launchers=[n for n in paths if n and '/' not in n and
                      n.lower().endswith(('.bat','.ps1')) and n not in TOP]
    for original in sorted(legacy_launchers):
        source_path=source/original
        if source_path.is_symlink():raise ValueError('Legacy launcher symlink refused')
        files['LEGACY_LAUNCHERS_REFERENCE/'+original+'.reference.txt']=source_path.read_bytes()
    # Independent pre-consolidation Python tools at repository root are
    # preserved byte-for-byte but never implicitly executed: many still
    # contain historic absolute Windows paths or act on live directories.
    legacy_tools=[n for n in paths if n and '/' not in n and
                  n.lower().endswith('.py')]
    for original in sorted(legacy_tools):
        source_path=source/original
        if source_path.is_symlink():raise ValueError('Legacy Python tool symlink refused')
        files['LEGACY_TOOLS_REFERENCE/'+original+'.reference.txt']=source_path.read_bytes()
    for required in ['BASLAT_V47_WINDOWS.bat','BASLAT_V46_WINDOWS.bat',
                     'MERKEZ/GUNLUK/INSTALLED_NUMBER_SPEC.json','MERKEZ/system_integrity_v475.py',
                     'MERKEZ/merkez.py','SABLON_V2_MIMARI/app.py','SABLON_V2_MIMARI/static/js/edge_angles_v46.js']:
        if required not in files:raise ValueError('Missing required code: '+required)
    manifest={'release':'V4.7.5 CODE_FINAL_CANDIDATE','acceptance':'WINDOWS_NOT_VERIFIED','live_user_acceptance':'PENDING',
              'source_commit':sha,'legacy_launchers_archived_as_text':legacy_launchers,
              'legacy_source_tools_archived_as_text':legacy_tools,
              'missing_untracked_external_files':'REQUIRES_USER_WINDOWS_INVENTORY',
              'files':[{ 'path':n,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()} for n,b in files.items()]}
    files['SHA256_MANIFEST.json']=json.dumps(manifest,ensure_ascii=False,indent=2).encode()
    target=destination/('GORSEL_V475_WINDOWS_CODE_FINAL_ADAY_'+sha[:12]+'.zip')
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
