"""Read-only inventory of disposable Windows candidate/lab directories.

Does not pretend archived scripts are active integrations. Differences are
identified by exact file bytes and copied (if separately approved) only into
quarantined staging INSIDE the canonical workspace, never into active app code,
SQLite, output receipts, PETEK registry or approved original photos.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
from datetime import datetime,timezone
import uuid
import sqlite3

SKIP={'.git','.venv','venv','node_modules','__pycache__','.pytest_cache','tmp',
      'logs','LOG','KARANTINA','test-results','outputs','output'}
CODE_EXT={'.py','.js','.html','.css','.bat','.ps1','.cjs','.json','.yaml','.yml'}
STATE_NAMES={'ayarlar.db','v4_ortak_uretim.sqlite3','petek_v3.sqlite3',
             'store_profiles_v47.json','PETEK_REGISTRY.sqlite3'}
LIMIT=50000
SUSPECT_EXT={'.py','.bat','.ps1','.exe','.dll','.onnx','.pth','.safetensors','.zip','.7z'}
SUSPECT_HINTS=('gorsel','görsel','mockup','sablon','şablon','petek','chroma','esrgan','jarvis','v46','v47')
CONFIRM='YALNIZ EKSİK FARKLI KODU KARANTİNAYA KOPYALA'
def checksum(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1048576),b''):h.update(chunk)
    return h.hexdigest()
def visit_folders(roots,max_depth=8):
    seen=set(); discovered=[]; states=[]; suspects=[]
    for root in roots:
        root=Path(root).expanduser().resolve()
        if not root.is_dir():continue
        base_depth=len(root.parts)
        for directory,dirs,files in os.walk(root,followlinks=False):
            d=Path(directory)
            if len(seen)>LIMIT:raise RuntimeError('SCAN_LIMIT_REACHED_SELECT_NARROWER_ROOTS')
            dirs[:]=[x for x in dirs if x not in SKIP and not (d/x).is_symlink()]
            if len(d.parts)-base_depth>=max_depth:dirs[:]=[]
            marker=(d/'MERKEZ'/'merkez.py')
            if not marker.is_file():
                marker=(d/'SABLON_V2_MIMARI'/'app.py')
            if marker.is_file() and not marker.is_symlink() and str(d).casefold() not in seen:
                discovered.append(d)
                seen.add(str(d).casefold())
                # Nested copies are unrelated test folders; do not recursively
                # discover an identical inner root as if it were active.
            for filename in files:
                p=d/filename
                if p.is_symlink():continue
                if filename in STATE_NAMES or (filename=='SHA256_MANIFEST.json'):
                    states.append(p)
                if (p.suffix.lower() in SUSPECT_EXT
                        and len(suspects)<10000
                        and any(hint in str(d).casefold() for hint in SUSPECT_HINTS)):
                    suspects.append(p)
    return discovered,states,suspects
def db_counts(path):
    if path.name not in {'ayarlar.db','v4_ortak_uretim.sqlite3'}:return None
    try:
        with sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=2) as con:
            if con.execute('PRAGMA quick_check').fetchone()[0]!='ok':return {'integrity':'BAD'}
            tables={r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            counted={}
            for table in ('categories','templates','template_profiles','artifact'):
                if table in tables:counted[table]=con.execute('SELECT COUNT(*) FROM '+table).fetchone()[0]
            return {'integrity':'OK','counts':counted}
    except (sqlite3.Error,OSError) as e:
        return {'integrity':'NOT_READABLE','reason':str(e)[:200]}
def local_area():
    root=Path(os.environ.get('LOCALAPPDATA') or Path.home())/'GorselMockup'/'UnifiedCenter'/'EXTERNAL_INVENTORY'
    root.mkdir(parents=True,exist_ok=True)
    return root
def inspect_active_templates(workspace: Path) -> dict:
    """Identity + SHA-only scan of ACTIVE working images, no removal/copying.

    Archives, laboratory previews, historical deleted numbers, and approved
    originals are intentionally not counted as active duplicates.
    """
    import unicodedata
    from collections import defaultdict
    workspace=Path(workspace)
    active=workspace/'2_SABLON_HAVUZU'
    suffixes={'.jpg','.jpeg','.png','.webp'}
    by_identity=defaultdict(list)
    by_content=defaultdict(list)
    files=[]
    if active.is_dir():
        for category in sorted(active.iterdir()):
            if category.is_symlink() or not category.is_dir():continue
            for file in sorted(category.iterdir()):
                if not file.is_file() or file.is_symlink() or file.suffix.lower() not in suffixes:
                    continue
                identity=unicodedata.normalize('NFC',file.stem).casefold()
                sha=checksum(file)
                record={'file':str(file),'category':category.name,
                        'identity':identity,'sha256':sha}
                files.append(record)
                by_identity[(category.name,identity)].append(record)
                by_content[sha].append(record)
    identity_duplicates=[
        {'category':key[0],'identity':key[1],'files':[x['file'] for x in rows]}
        for key,rows in by_identity.items() if len(rows)>1
    ]
    content_duplicates=[
        {'sha256':hashvalue,'files':[x['file'] for x in rows],
         'distinct_identities':len({(x['category'],x['identity']) for x in rows})}
        for hashvalue,rows in by_content.items()
        if len({(x['category'],x['identity']) for x in rows})>1
    ]
    # Read-only validation of legacy SQLite active profiles. The PETEK
    # registry is separate; do not fabricate a SQLite row for PETEK.
    registered=set()
    stale=[]
    db=workspace/'SABLON_V2_MIMARI'/'ayarlar.db'
    if db.is_file() and not db.is_symlink():
        try:
            with sqlite3.connect(db.resolve().as_uri()+'?mode=ro',uri=True,timeout=3) as connection:
                connection.row_factory=sqlite3.Row
                columns={r[1] for r in connection.execute('PRAGMA table_info(template_profiles)')}
                if {'category','source_relative_path','source_asset_sha256','is_active'}.issubset(columns):
                    for row in connection.execute(
                        'SELECT category,source_relative_path,source_asset_sha256 '
                        'FROM template_profiles WHERE is_active=1'):
                        category=str(row['category'])
                        rel=str(row['source_relative_path'] or '').replace('\\','/')
                        parts=rel.split('/')
                        if len(parts)!=2 or parts[0]!=category:continue
                        identity=unicodedata.normalize('NFC',Path(parts[1]).stem).casefold()
                        key=(category,identity)
                        registered.add(key)
                        current=by_identity.get(key,[])
                        if len(current)!=1 or current[0]['sha256']!=row['source_asset_sha256']:
                            stale.append({'category':category,'identity':identity,
                                          'relative_path':rel,'status':'ACTIVE_PROFILE_SHA_OR_FILE_MISMATCH'})
        except sqlite3.Error as exc:
            stale.append({'status':'SQLITE_READONLY_CHECK_FAILED','reason':str(exc)[:200]})
    extras=[r['file'] for r in files if (r['category'],r['identity']) not in registered
            and r['category'] not in ('Petek_Dolabi','06_Petek_Kapama')]
    return {'active_images':len(files),
            'same_identity_different_files':identity_duplicates,
            'same_bytes_different_identities':content_duplicates,
            'db_active_profile_mismatches':stale,
            'working_without_legacy_db_profile':extras,
            'photos_deleted_by_this_scan':0,
            'note':'PETEK mask registry separately maintained; raw original archive is not an active duplicate.'}


def build(code_root,workspace,roots):
    code_root=Path(code_root).resolve();workspace=Path(workspace).resolve()
    if not (code_root/'MERKEZ'/'merkez.py').is_file():
        raise ValueError('ACTIVE_CODE_ROOT_INVALID')
    if not (workspace/'SABLON_V2_MIMARI'/'ayarlar.db').is_file():
        raise ValueError('ACTIVE_WORKSPACE_DB_INVALID')
    found,states,suspects=visit_folders(roots)
    components=[]; diff=[]
    for candidate in found:
        if candidate==code_root or candidate==workspace:continue
        if workspace in candidate.parents or code_root in candidate.parents:
            # Installed active files are NOT obsolete candidates.
            continue
        counts={'same':0,'changed':0,'missing':0}
        for base,dirs,files in os.walk(candidate,followlinks=False):
            here=Path(base)
            dirs[:]=[x for x in dirs if x not in SKIP and not (here/x).is_symlink()]
            for filename in files:
                src=here/filename
                if src.is_symlink() or src.suffix.lower() not in CODE_EXT:continue
                rel=src.relative_to(candidate)
                dst=code_root/rel
                if dst.is_symlink():status='UNSAFE_CANONICAL_SYMLINK'
                elif not dst.is_file():status='ONLY_IN_TEST_FOLDER'
                elif checksum(src)==checksum(dst):status='BYTE_IDENTICAL'
                else:status='DIFFERENT_FROM_ACTIVE_CODE'
                counts[{'BYTE_IDENTICAL':'same',
                        'ONLY_IN_TEST_FOLDER':'missing'}.get(status,'changed')]+=1
                if status!='BYTE_IDENTICAL':
                    diff.append({'source':str(src),'relative':rel.as_posix(),
                                 'candidate':str(candidate),'source_sha256':checksum(src),
                                 'active':str(dst),'status':status,
                                 'active_sha256':checksum(dst) if dst.is_file() and not dst.is_symlink() else None})
        components.append({'root':str(candidate),'counts':counts,
                           'safe_to_delete_without_manual_review':counts['changed']==0 and counts['missing']==0})
    state_list=[]
    for p in states:
        if code_root in p.parents or workspace in p.parents:continue
        state_list.append({'path':str(p),'size':p.stat().st_size,
                           'sha256':checksum(p) if p.stat().st_size<1024*1024*350 else None,
                           'read_only_sqlite':db_counts(p),
                           'decision':'REVIEW_EXTERNAL_STATE_NO_AUTOMATIC_MERGE'})
    # Source scripts, model binaries and ZIPs in experiment-only directories
    # can matter even when they are not inside a complete app checkout.
    known_code=[Path(x['root']) for x in components]
    orphan=[]
    for item in suspects:
        if (code_root in item.parents or workspace in item.parents
                or any(parent in item.parents for parent in known_code)):
            continue
        if item.name in STATE_NAMES:continue
        orphan.append({'path':str(item),'size':item.stat().st_size,
                       'sha256':checksum(item) if item.stat().st_size<1024*1024*350 else None,
                       'status':'STANDALONE_TOOL_OR_MODEL_REVIEW_BEFORE_DELETE'})
    local=os.environ.get('LOCALAPPDATA') or str(Path.home())
    report={'schema':1,'timestamp':datetime.now(timezone.utc).isoformat(),
            'workspace':str(workspace),'active_code':str(code_root),
            'scan_roots':[str(Path(r)) for r in roots],
            'candidate_code_roots':components,'different_code_files':diff,
            'external_state_files':state_list,
            'active_template_identity_audit':inspect_active_templates(workspace),
            'standalone_tool_or_model_suspects':orphan,
            'known_active_external_state':[
                str(Path(local)/'GorselMockup'/'UnifiedV4'),
                str(Path(local)/'GorselMockup'/'PetekV3'),
                str(Path(local)/'GorselMockup'/'UnifiedCenter')],
            'status':'REVIEW_REQUIRED_BEFORE_ANY_TEST_FOLDER_DELETION'}
    return report
def save(report):
    path=local_area()/('EXTERNAL_SCAN_'+uuid.uuid4().hex[:12]+'.json')
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return path
def stage(report_path,phrase):
    if phrase!=CONFIRM:raise PermissionError('EXPLICIT_STAGING_CONFIRMATION_REQUIRED')
    report_path=Path(report_path)
    plan=json.loads(report_path.read_text(encoding='utf-8'))
    if plan.get('schema')!=1:raise ValueError('BAD_INVENTORY')
    refreshed=build(plan['active_code'],plan['workspace'],plan['scan_roots'])
    original={r['source']:r for r in plan['different_code_files']}
    for row in refreshed['different_code_files']:
        prior=original.get(row['source'])
        if prior is None or prior['source_sha256']!=row['source_sha256'] or prior['active_sha256']!=row['active_sha256']:
            raise RuntimeError('CODE_CHANGED_RESCAN_REQUIRED')
    folder=Path(plan['workspace'])/'KURTARMA_ON_INCELEME'/('kod_'+uuid.uuid4().hex[:10])
    if folder.exists():raise RuntimeError('STAGING_COLLISION')
    folder.mkdir(parents=True)
    result=[]
    for row in refreshed['different_code_files']:
        if row['status']=='UNSAFE_CANONICAL_SYMLINK':continue
        # Never activate candidates; recovery stage is forensic only. Move
        # into app only after code review/CI, not with a filesystem copy.
        candidate=Path(row['candidate'])
        dest=folder/candidate.name/row['relative']
        # Candidate names may repeat; disambiguate by hash of full root.
        dest=folder/(hashlib.sha256(str(candidate).encode()).hexdigest()[:12])/row['relative']
        dest.parent.mkdir(parents=True,exist_ok=True)
        if dest.exists():raise RuntimeError('STAGING_COLLISION')
        shutil.copy2(row['source'],dest)
        if checksum(dest)!=row['source_sha256']:raise RuntimeError('STAGED_SHA_MISMATCH')
        result.append({'source':row['source'],'staged':str(dest),
                       'sha256':row['source_sha256'],'integrated_into_active_code':False})
    # Scripts outside recognized code roots may be important. Preserve only
    # small SHA-verifiable source scripts; binaries/models remain review-only
    # and are not silently copied into executable folders.
    for suspect in refreshed.get('standalone_tool_or_model_suspects',[]):
        src=Path(suspect['path'])
        if (src.suffix.lower() not in CODE_EXT or not suspect.get('sha256')
                or src.stat().st_size>20*1024*1024):
            continue
        dest=folder/'standalone'/hashlib.sha256(str(src).encode()).hexdigest()[:12]/src.name
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(src,dest)
        if checksum(dest)!=suspect['sha256']:raise RuntimeError('STANDALONE_STAGE_SHA_CHANGED')
        result.append({'source':str(src),'staged':str(dest),'sha256':suspect['sha256'],
                       'integrated_into_active_code':False})
    receipt={'staged_count':len(result),'items':result,
             'meaning':'ARCHIVED_FOR_HUMAN_CODE_REVIEW_NOT_ACTIVE',
             'external_folders_deleted':0}
    (folder/'STAGING_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    return folder
def main():
    p=argparse.ArgumentParser()
    p.add_argument('--workspace',required=True)
    p.add_argument('--code-root',required=True)
    p.add_argument('--root',action='append',default=[])
    p.add_argument('--stage-report')
    p.add_argument('--confirm',default='')
    a=p.parse_args()
    if a.stage_report:
        print('REVIEW_STAGING='+str(stage(a.stage_report,a.confirm)))
    else:
        roots=a.root or [r'C:\AI_WORK',str(Path.home()/'Downloads')]
        dest=save(build(a.code_root,a.workspace,roots))
        print('EXTERNAL_INVENTORY_READ_ONLY='+str(dest))
        print('No files copied, moved, deleted or activated.')
if __name__=='__main__':main()
