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
CONFIRM='YALNIZ EKSİK FARKLI KODU KARANTİNAYA KOPYALA'
def checksum(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1048576),b''):h.update(chunk)
    return h.hexdigest()
def visit_folders(roots,max_depth=8):
    seen=set(); discovered=[]; states=[]
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
    return discovered,states
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
def build(code_root,workspace,roots):
    code_root=Path(code_root).resolve();workspace=Path(workspace).resolve()
    if not (code_root/'MERKEZ'/'merkez.py').is_file():
        raise ValueError('ACTIVE_CODE_ROOT_INVALID')
    if not (workspace/'SABLON_V2_MIMARI'/'ayarlar.db').is_file():
        raise ValueError('ACTIVE_WORKSPACE_DB_INVALID')
    found,states=visit_folders(roots)
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
    local=os.environ.get('LOCALAPPDATA') or str(Path.home())
    report={'schema':1,'timestamp':datetime.now(timezone.utc).isoformat(),
            'workspace':str(workspace),'active_code':str(code_root),
            'scan_roots':[str(Path(r)) for r in roots],
            'candidate_code_roots':components,'different_code_files':diff,
            'external_state_files':state_list,
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
