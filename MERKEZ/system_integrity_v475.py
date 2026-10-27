"""Comprehensive *read-only* multi-system integrity and code dependency audit.

No Registry() / UnifiedV4Batch() construction: those constructors create
state files. No SQLite writes or workspace backup creation during inspection.
Historical rendered images remain valid after a current template is changed.
"""
from __future__ import annotations
from collections import Counter,defaultdict
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import sqlite3
from typing import Any

from PETEK_V3 import engine as petek_engine
from PETEK_V3.registry import store_root as petek_store_root
from URETIM_V4.final_guard_v44 import inspect_workspaces,store_v4_root
from URETIM_V4.store_profiles_v47 import StoreProfiles
from URETIM_V4.unlimited_selection import LEGACY_SIX_CATEGORIES
from external_inventory_v472 import inspect_active_templates

REQUIRED_CODE=(
    'MERKEZ/merkez.py',
    'MERKEZ/GUNLUK/INSTALLED_NUMBER_SPEC.json',
    'MERKEZ/URETIM_V4/unified_batch.py',
    'MERKEZ/URETIM_V4/store_profiles_v47.py',
    'MERKEZ/URETIM_V4/upscale4k_v44.py',
    'MERKEZ/URETIM_V4/cloud_excel_v43.py',
    'MERKEZ/PETEK_V3/engine.py',
    'MERKEZ/PETEK_V3/registry.py',
    'MERKEZ/magenta_reconcile_v472.py',
    'MERKEZ/external_inventory_v472.py',
    'MERKEZ/runtime_relocate_v473.py',
    'MERKEZ/URETIM_V4/deleted_receipts_v474.py',
    'SABLON_V2_MIMARI/app.py',
    'SABLON_V2_MIMARI/core/db.py',
    'SABLON_V2_MIMARI/static/js/loopback_csrf_v47.js',
    'BASLAT_V47_WINDOWS.bat',
    'BAKIM_V472_MAGENTA_KLASOR_DENETIM_WINDOWS.bat',
)

def _sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for part in iter(lambda:f.read(1048576),b''):h.update(part)
    return h.hexdigest()

def _problem(issues,kind,**details):
    issues.append({'code':kind,**details})

def _db_connect(path):
    if path.is_symlink() or not path.is_file():
        raise FileNotFoundError('READONLY_SQLITE_MISSING_OR_SYMLINK: '+str(path))
    result=sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=8)
    result.row_factory=sqlite3.Row
    return result

def _legacy_profiles(runtime, problems):
    db=runtime/'SABLON_V2_MIMARI'/'ayarlar.db'
    known={}
    details={'active':0,'approved':0,'review_required':0,'invalid':0,
             'recorded_numbers':None,'legacy_templates':None}
    if not db.is_file() or db.is_symlink():
        _problem(problems,'LEGACY_SQLITE_MISSING',path=str(db))
        return known,details
    try:
        with _db_connect(db) as c:
            if c.execute('PRAGMA quick_check').fetchone()[0]!='ok':
                _problem(problems,'LEGACY_SQLITE_INTEGRITY')
                return known,details
            tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            for optional,field in [('templates','legacy_templates'),('template_number_registry','recorded_numbers')]:
                if optional in tables:
                    details[field]=c.execute('SELECT COUNT(*) FROM "'+optional+'"').fetchone()[0]
            if 'template_profiles' not in tables:
                _problem(problems,'LEGACY_PROFILES_TABLE_MISSING')
                return known,details
            rows=[dict(r) for r in c.execute('SELECT * FROM template_profiles WHERE is_active=1')]
        details['active']=len(rows)
        seen={}
        for row in rows:
            cat=str(row.get('category') or '')
            if cat not in LEGACY_SIX_CATEGORIES:continue
            uid=str(row.get('template_uid') or '')
            rel=str(row.get('source_relative_path') or '').replace('\\','/')
            parts=PurePosixPath(rel).parts
            if len(parts)!=2 or parts[0]!=cat or any(x in ('.','..') for x in parts):
                _problem(problems,'PROFILE_UNSAFE_RELATIVE_PATH',uid=uid,relative=rel)
                details['invalid']+=1
                continue
            key=(cat,uid)
            if key in seen:
                _problem(problems,'DUPLICATE_ACTIVE_TEMPLATE_UID',category=cat,uid=uid)
                details['invalid']+=1
                continue
            seen[key]=True
            approved=row.get('review_status')=='APPROVED' and int(row.get('manually_verified') or 0)==1
            if approved:details['approved']+=1
            else:details['review_required']+=1
            expected=str(row.get('source_asset_sha256') or '').lower()
            working=runtime/'2_SABLON_HAVUZU'/rel
            archived=runtime/'2_SABLON_HAVUZU_ORIJINAL_YEDEK'/rel
            images=[]
            for name,path in [('working',working),('archive',archived)]:
                if path.is_symlink():
                    _problem(problems,'TEMPLATE_SYMLINK',uid=uid,source=name)
                elif path.is_file():
                    images.append((name,path,_sha(path)))
            working_matches=any(kind=='working' and digest==expected for kind,_,digest in images)
            archive_matches=any(kind=='archive' and digest==expected for kind,_,digest in images)
            if approved and not working_matches and not archive_matches:
                _problem(problems,'APPROVED_IMAGE_SHA_NOT_FOUND',uid=uid,category=cat,relative=rel)
            if approved and not working_matches and archive_matches:
                _problem(problems,'APPROVED_ONLY_IN_ARCHIVE',uid=uid,category=cat,relative=rel)
            # Unapproved staging/DRAFT templates are intentionally incomplete.
            # They must not turn a healthy production into a false P0 blocker.
            if approved and not working.is_file():
                _problem(problems,'APPROVED_WORKING_IMAGE_MISSING',uid=uid,category=cat,relative=rel)
            if approved and working.is_file() and not working.is_symlink() and not working_matches:
                _problem(problems,'APPROVED_WORKING_SHA_DIFFERS_FROM_PROFILE',uid=uid,category=cat,relative=rel)
            known[f'{cat}:{uid}@{expected}']={'approved':approved,'category':cat,'uid':uid,'source_sha':expected}
    except (sqlite3.Error,OSError,ValueError,TypeError) as exc:
        _problem(problems,'LEGACY_SQLITE_AUDIT_ERROR',error=str(exc)[:250])
    return known,details

def _petek_profiles(root, problems, workspace=None):
    root=Path(root).absolute()
    profiles=root/'profiles'
    masks=root/'masks'
    details={'count':0,'approved':0,'invalid':0,'source_outside_expected_roots':[]}
    known={}
    if not profiles.is_dir():
        _problem(problems,'PETEK_PROFILES_DIRECTORY_MISSING',path=str(profiles))
        return known,details
    for path in sorted(profiles.glob('*.json')):
        details['count']+=1
        try:
            if path.is_symlink():raise ValueError('PETEK_PROFILE_SYMLINK')
            record=json.loads(path.read_text('utf-8'))
            uid=record['uid']
            if path.stem!=uid:raise ValueError('PETEK_UID_FILENAME_MISMATCH')
            source=Path(record['source'])
            if source.is_symlink() or not source.is_file():raise ValueError('PETEK_SOURCE_UNAVAILABLE')
            expected=record['source_sha']
            if petek_engine.digest(source)!=expected:raise ValueError('PETEK_SOURCE_SHA_CHANGED')
            if workspace is not None:
                # Profiles can legitimately refer to older LAB paths. Before
                # deleting that experiment folder, it must be rehomed with an
                # explicit source+mask migration. Surface the dependency.
                approved_roots=[Path(workspace).resolve(),root.resolve()]
                if not any(base==source.resolve() or base in source.resolve().parents
                           for base in approved_roots):
                    details['source_outside_expected_roots'].append(str(source))
            mask_sha=record['mask_sha']
            mask_path=masks/(mask_sha+'.png')
            if mask_path.is_symlink() or not mask_path.is_file():
                raise ValueError('PETEK_MASK_FILE_MISSING')
            mask=petek_engine.decode_mask(mask_path)
            if petek_engine.mask_hash(mask)!=mask_sha:
                raise ValueError('PETEK_MASK_SHA_CHANGED')
            image=petek_engine.read_bgr(source)
            petek_engine.mask_check(mask,image,record['quad'])
            if record.get('status')=='APPROVED':
                details['approved']+=1
            identifier='06_Petek_Kapama:'+uid+'@'+expected
            if identifier in known:raise ValueError('PETEK_UID_COLLISION')
            known[identifier]={'approved':record.get('status')=='APPROVED',
                               'category':'06_Petek_Kapama','uid':uid,'source_sha':expected}
        except (OSError,ValueError,KeyError,TypeError,petek_engine.MaskError) as exc:
            details['invalid']+=1
            _problem(problems,'PETEK_PROFILE_OR_MASK_INVALID',profile=path.name,error=str(exc)[:200])
    return known,details

def _store_integrity(root,known,issues):
    path=Path(root)/'store_profiles_v47.json'
    report={'stores':0,'memberships':0,'stale':0}
    if not path.exists():return report
    try:
        raw=StoreProfiles(root).load()
        report['stores']=len(raw['stores'])
        for name,store in raw['stores'].items():
            for key in store['templates']:
                report['memberships']+=1
                if key not in known:
                    report['stale']+=1
                    _problem(issues,'STORE_MEMBERSHIP_SOURCE_MISMATCH',store=name,template=key)
                elif not known[key]['approved']:
                    # A human-review-pending source is retained as an intentional
                    # assignment, but must be excluded from production discovery.
                    report.setdefault('waiting_for_human_approval',0)
                    report['waiting_for_human_approval']+=1
    except (ValueError,OSError,TypeError,KeyError) as exc:
        _problem(issues,'STORE_PROFILE_INVALID',error=str(exc)[:200])
    return report

def _package_integrity(root,issues):
    root=Path(root)
    result={'files_checked':0,'manifest_found':False,'source_commit':None}
    for rel in REQUIRED_CODE:
        file=root/rel
        if file.is_symlink() or not file.is_file():
            _problem(issues,'REQUIRED_CODE_MISSING',path=rel)
    manifest=root/'SHA256_MANIFEST.json'
    # Legacy Daily V2 is NOT the modern seven-category renderer. Its pinned
    # BATCH_SELECTION.json is user-/backup-dependent and must never be made
    # up just to make the old executable load. Keep the dependency explicit.
    daily_selection=root/'MERKEZ'/'GUNLUK'/'BATCH_SELECTION.json'
    result['legacy_daily_v2'] = (
        'PINNED_BACKUP_AND_SELECTION_MANUAL_DEPENDENCY'
        if not daily_selection.is_file() else 'PINNED_BACKUP_STILL_MUST_BE_VERIFIED')
    if not manifest.is_file():return result
    try:
        info=json.loads(manifest.read_text('utf-8'))
        result['manifest_found']=True
        result['source_commit']=info.get('source_commit')
        for row in info['files']:
            rel=PurePosixPath(row['path'])
            if rel.is_absolute() or '..' in rel.parts:
                raise ValueError('UNSAFE_MANIFEST_PATH')
            file=root/str(rel)
            if file.is_symlink() or not file.is_file():
                _problem(issues,'PACKAGE_FILE_MISSING',path=str(rel))
            elif _sha(file)!=row['sha256'] or file.stat().st_size!=row['bytes']:
                _problem(issues,'PACKAGE_FILE_SHA_MISMATCH',path=str(rel))
            else:result['files_checked']+=1
    except (ValueError,KeyError,OSError,TypeError) as exc:
        _problem(issues,'PACKAGE_MANIFEST_INVALID',error=str(exc)[:200])
    return result

def examine(workspace,code_root,*,production_root=None,petek_root=None,external_scan=None):
    """Return independent findings without creating or modifying user files."""
    workspace=Path(workspace).absolute()
    code_root=Path(code_root).absolute()
    production_root=Path(production_root or store_v4_root()).absolute()
    petek_root=Path(petek_root or petek_store_root()).absolute()
    blockers=[]
    warnings=[]
    known={}
    legacy,legacy_stats=_legacy_profiles(workspace,blockers)
    known.update(legacy)
    petek,petek_stats=_petek_profiles(petek_root,blockers,workspace=workspace)
    if petek_stats['source_outside_expected_roots']:
        _problem(warnings,'PETEK_SOURCE_DEPENDS_ON_EXTERNAL_DIRECTORY',
                 count=len(petek_stats['source_outside_expected_roots']))
    known.update(petek)
    stores=_store_integrity(production_root,known,blockers)
    candidates=inspect_active_templates(workspace)
    if candidates['same_identity_different_files']:
        _problem(blockers,'ACTIVE_IMAGE_DUPLICATE_IDENTITY',
                 count=len(candidates['same_identity_different_files']))
    if candidates['same_bytes_different_identities']:
        _problem(warnings,'SAME_PIXELS_DIFFERENT_TEMPLATE_IDS',
                 count=len(candidates['same_bytes_different_identities']))
    if candidates['db_active_profile_mismatches']:
        _problem(blockers,'ACTIVE_IMAGE_DB_MISMATCH',count=len(candidates['db_active_profile_mismatches']))
    if candidates['working_without_legacy_db_profile']:
        _problem(warnings,'UNREGISTERED_WORKING_TEMPLATE',count=len(candidates['working_without_legacy_db_profile']))
    g3=inspect_workspaces(workspace,production_root)
    for alert in g3['alerts']:
        _problem(warnings,'G3_INSPECTION_ALERT',detail=alert)
    production=g3['production']
    if any(production.get(x,0) for x in ('missing','sha_mismatch','path_unsafe')):
        _problem(blockers,'OUTPUT_LEDGER_INTEGRITY_FAILED',
                 missing=production.get('missing',0),
                 sha_mismatch=production.get('sha_mismatch',0),
                 unsafe=production.get('path_unsafe',0))
    if production.get('unfinished',0):
        _problem(warnings,'UNFINISHED_RENDER_RECEIPTS',
                 count=production['unfinished'])
    package=_package_integrity(code_root,blockers)
    # Local model binaries and public HTTPS endpoints require hardware/account
    # confirmation: absence cannot be called a finished production acceptance.
    if not external_scan:
        _problem(warnings,'OLD_TEST_FOLDERS_NOT_SCANNED')
        external='NEEDS_REAL_WINDOWS_INVENTORY'
    else:
        try:
            inv=json.loads(Path(external_scan).read_text('utf-8'))
            if Path(inv['workspace']).resolve()!=workspace.resolve():
                raise ValueError('INVENTORY_WORKSPACE_MISMATCH')
            remaining=len(inv.get('different_code_files',[]))
            remaining+=len(inv.get('standalone_tool_or_model_suspects',[]))
            remaining+=len(inv.get('external_state_files',[]))
            external={'remaining_review':remaining}
            if remaining:_problem(warnings,'EXTERNAL_CODE_OR_STATE_NEEDS_REVIEW',count=remaining)
        except (OSError,ValueError,KeyError,TypeError) as exc:
            external='INVALID_OR_STALE'
            _problem(blockers,'EXTERNAL_SCAN_INVALID',error=str(exc)[:180])
    if 'onedrive' in str(workspace).lower():
        _problem(warnings,'ONEDRIVE_LIVE_SQLITE_RISK')
    return {'schema':1,'mode':'READ_ONLY','created_utc':datetime.now(timezone.utc).isoformat(),
            'paths':{'workspace':str(workspace),'code':str(code_root),
                     'production_state':str(production_root),'petek_state':str(petek_root)},
            'legacy_templates':legacy_stats,'petek':petek_stats,'stores':stores,
            'active_pool':candidates,'production':production,'g3_database':g3['db'],
            'package':package,'external_inventory':external,
            'blockers':blockers,'warnings':warnings,
            'status':'BLOCKED' if blockers else ('REVIEW_PENDING' if warnings else 'CODE_DATA_INTEGRITY_PASS'),
            'safe_to_delete_old_test_folders':False,
            'can_claim_final_live_windows':False,
            'does_not_modify_source_or_ledgers':True}

def write_report(data,path):
    """Explicit caller action: writes ONLY a new report JSON, never workspace data."""
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as out:
        json.dump(data,out,ensure_ascii=False,indent=2)
    return path

def main():
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument('--workspace',required=True)
    p.add_argument('--code-root',required=True)
    p.add_argument('--production-root')
    p.add_argument('--petek-root')
    p.add_argument('--external-scan')
    p.add_argument('--report')
    args=p.parse_args()
    report=examine(args.workspace,args.code_root,production_root=args.production_root,
                   petek_root=args.petek_root,external_scan=args.external_scan)
    if args.report:
        write_report(report,args.report)
    print(json.dumps({k:report[k] for k in (
        'status','legacy_templates','petek','stores','package','blockers','warnings')},
                     ensure_ascii=False,indent=2))

if __name__=='__main__':main()
