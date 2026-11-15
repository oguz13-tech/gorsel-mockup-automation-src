"""Cross-system audit: byte-identical source, independent SQLite and PETEK.

All tests use synthetic temp directories. No user's Windows workspace access.
"""
from pathlib import Path
import json
import os
import sqlite3
import sys
import shutil
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'MERKEZ'))
sys.path.insert(0,str(ROOT/'TESTLER'))
from test_v40_unified_seven_category import _build_seven_category_workspace
from PETEK_V3 import engine as petek_engine
from URETIM_V4.unified_batch import UnifiedV4Batch
from URETIM_V4.store_profiles_v47 import StoreProfiles
from system_integrity_v475 import examine,REQUIRED_CODE,_package_integrity,_sha


def setup_system(tmp_path):
    runtime,registry=_build_seven_category_workspace(tmp_path,per_cat_count=1)
    state=tmp_path/'AppData'/'GorselMockup'/'UnifiedV4'
    batch=UnifiedV4Batch(state,runtime_root=runtime,petek_registry=registry)
    templates,_=batch.discover_templates()
    wood=next(item for item in templates if item['category']=='03_Ahsap_Tablo')
    stores=StoreProfiles(state)
    stores.add_store('Magaza_01')
    stores.assign('Magaza_01',[wood])
    return runtime,registry,state,wood,stores


def run_audit(runtime,registry,state):
    return examine(runtime,ROOT,production_root=state,petek_root=registry.root)


def test_all_seven_sha_readonly_no_false_errors_for_draft(tmp_path):
    runtime,registry,state,wood,_=setup_system(tmp_path)
    db=runtime/'SABLON_V2_MIMARI'/'ayarlar.db'
    before=(db.stat().st_mtime_ns,_sha(db),registry.root.stat().st_mtime_ns)
    audit=run_audit(runtime,registry,state)
    assert audit['schema']==1 and audit['mode']=='READ_ONLY'
    assert audit['legacy_templates']['approved']==6
    assert audit['legacy_templates']['review_required']==1
    assert audit['petek']['approved']==1
    assert audit['stores']['stores']==1 and audit['stores']['stale']==0
    assert audit['production']['missing']==0
    assert not audit['blockers'],audit['blockers']
    assert audit['status']=='REVIEW_PENDING'
    assert audit['safe_to_delete_old_test_folders'] is False
    assert audit['can_claim_final_live_windows'] is False
    assert (db.stat().st_mtime_ns,_sha(db),registry.root.stat().st_mtime_ns)==before


def test_applied_chroma_working_sha_requires_reapproval(tmp_path):
    runtime,registry,state,wood,_=setup_system(tmp_path)
    scene=Path(wood['source'])
    assert scene.is_file()
    assert '2_SABLON_HAVUZU' in str(scene) or 'ORIJINAL_YEDEK' in str(scene)
    working=runtime/'2_SABLON_HAVUZU'/wood['category']/(wood['uid'].replace('_UID_','_Sablon_')+'.png')
    if not working.is_file():
        rows=list((runtime/'2_SABLON_HAVUZU'/wood['category']).glob('*.png'))
        working=rows[0]
    working.write_bytes(b'magenta-replaced-before-reapproval')
    audit=run_audit(runtime,registry,state)
    codes={x['code'] for x in audit['blockers']}
    assert 'APPROVED_WORKING_SHA_DIFFERS_FROM_PROFILE' in codes
    assert audit['status']=='BLOCKED'


def test_store_stale_sha_becomes_blocker(tmp_path):
    runtime,registry,state,wood,store=setup_system(tmp_path)
    raw=store.load()
    raw['stores']['Magaza_01']['templates']=[
        wood['category']+':'+wood['uid']+'@'+'f'*64]
    store.save(raw)
    report=run_audit(runtime,registry,state)
    assert report['stores']['stale']==1
    assert 'STORE_MEMBERSHIP_SOURCE_MISMATCH' in {
        x['code'] for x in report['blockers']}


def test_petek_approved_mask_corruption_blocks_no_mutation(tmp_path):
    runtime,registry,state,_,_=setup_system(tmp_path)
    profile=json.loads(next(registry.profiles.glob('*.json')).read_text('utf-8'))
    mask=registry.masks/(profile['mask_sha']+'.png')
    mask.write_bytes(b'corrupted-mask')
    audit=run_audit(runtime,registry,state)
    assert audit['petek']['invalid']>=1
    assert 'PETEK_PROFILE_OR_MASK_INVALID' in {x['code'] for x in audit['blockers']}
    assert mask.read_bytes()==b'corrupted-mask'


def test_external_petek_reference_prevents_premature_cleanup(tmp_path):
    runtime,registry,state,_,_=setup_system(tmp_path)
    report=run_audit(runtime,registry,state)
    assert report['petek']['source_outside_expected_roots']
    assert 'PETEK_SOURCE_DEPENDS_ON_EXTERNAL_DIRECTORY' in {
        x['code'] for x in report['warnings']}
    assert report['safe_to_delete_old_test_folders'] is False


def test_user_removed_receipts_count_as_historic_not_missing(tmp_path):
    runtime,registry,state,_,_=setup_system(tmp_path)
    missing=(state/'uretilen_gorseller'/'LOCAL'/'03_Ahsap_Tablo'/'historic.png')
    missing.parent.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(state/'v4_ortak_uretim.sqlite3') as connection:
        connection.execute('''INSERT INTO artifact
        (key,sku,category,art_sha,template_sha,mask_sha,art_name,uid,output,
         output_sha,status) VALUES(?,?,?,?,?,?,?,?,?,?,?)''',
         ('key_1','SKU','03_Ahsap_Tablo','a'*64,'b'*64,'c'*64,'art.png',
          'wood_uid',str(missing),'d'*64,'USER_REMOVED'))
    report=run_audit(runtime,registry,state)
    assert report['production']['user_removed']==1
    assert report['production']['missing']==0
    assert not any(x['code']=='OUTPUT_LEDGER_INTEGRITY_FAILED' for x in report['blockers'])


def test_manifest_checks_required_code_and_tampered_hash(tmp_path):
    code=tmp_path/'signed_package'
    for relative in REQUIRED_CODE:
        file=code/relative
        file.parent.mkdir(parents=True,exist_ok=True)
        file.write_bytes((relative+'\n').encode('utf-8'))
    rows=[{'path':relative,'bytes':(code/relative).stat().st_size,
           'sha256':_sha(code/relative)} for relative in REQUIRED_CODE]
    (code/'SHA256_MANIFEST.json').write_text(json.dumps({
        'source_commit':'synthetic-test','files':rows}),encoding='utf-8')
    problems=[]
    good=_package_integrity(code,problems)
    assert good['files_checked']==len(REQUIRED_CODE)
    assert problems==[]
    (code/REQUIRED_CODE[1]).write_bytes(b'tampered')
    problems=[]
    _package_integrity(code,problems)
    assert 'PACKAGE_FILE_SHA_MISMATCH' in {x['code'] for x in problems}


def test_external_scan_without_real_report_never_claims_cleanup_safe(tmp_path):
    runtime,registry,state,_,_=setup_system(tmp_path)
    other=tmp_path/'bogus_scan.json'
    other.write_text(json.dumps({'workspace':str(tmp_path/'WRONG'),'different_code_files':[]}))
    report=examine(runtime,ROOT,production_root=state,petek_root=registry.root,
                   external_scan=other)
    assert report['status']=='BLOCKED'
    assert 'EXTERNAL_SCAN_INVALID' in {x['code'] for x in report['blockers']}
