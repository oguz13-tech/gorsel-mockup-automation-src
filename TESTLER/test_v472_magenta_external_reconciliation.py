"""V4.7.2 direct operator safeguards: image-by-image reconciliation + orphan code scan.
All tests build synthetic private Windows-style hierarchies under pytest tmp_path.
No user-provided photos, SQLite databases, existing program files are touched.
"""
from pathlib import Path
import hashlib
import json
import os
import sqlite3
import sys
from PIL import Image,ImageDraw
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'MERKEZ'))
from magenta_reconcile_v472 import (analyze,write_report,html_comparison,apply,CONFIRM,sha)
from external_inventory_v472 import (build,save,stage,CONFIRM as COPY_CONFIRM)

def _db(path, category='03_Ahsap_Tablo', name='Ahsap_001.png', src_hash=None,
        uid='Ahsap_UID_001', approved=True, new_quad=False):
    path.parent.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(path) as db:
        db.execute("""CREATE TABLE template_profiles(
            template_uid TEXT, category TEXT,source_relative_path TEXT,
            source_asset_sha256 TEXT,review_status TEXT,manually_verified INTEGER,
            is_active INTEGER,surface_quad TEXT,outer_quad TEXT,
            nominal_aspect TEXT,orientation TEXT,component_confidences TEXT,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP)""")
        db.execute("""INSERT INTO template_profiles
            (template_uid,category,source_relative_path,source_asset_sha256,
             review_status,manually_verified,is_active,surface_quad,outer_quad,
             nominal_aspect,orientation,component_confidences)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
           (uid,category,category+'/'+name,src_hash,
            'APPROVED' if approved else 'REVIEW_REQUIRED',int(approved),1,
            json.dumps([[15,15],[380,15],[380,278],[15,278]] if new_quad
                       else [[10,10],[390,10],[390,290],[10,290]]),
            None,'1.4','H','{}'))
        db.execute('CREATE TABLE templates(category_id TEXT, filename TEXT, data TEXT)')
        db.execute('INSERT INTO templates VALUES (?,?,?)',(category,name,'{}'))
def _image(path, magenta=False,dim=(400,300)):
    path.parent.mkdir(parents=True,exist_ok=True)
    im=Image.new('RGB',dim,'#eeeeee')
    if magenta:
        ImageDraw.Draw(im).rectangle([20,20,dim[0]-20,dim[1]-20],fill='#ff00ff')
    im.save(path)

def _fixture(tmp_path,lab_db=True,size=(400,300)):
    root=tmp_path/'GorselAna'
    work=root/'2_SABLON_HAVUZU'/'03_Ahsap_Tablo'/'Ahsap_001.png'
    original=root/'2_SABLON_HAVUZU_ORIJINAL_YEDEK'/'03_Ahsap_Tablo'/'Ahsap_001.png'
    _image(work);_image(original)
    _db(root/'SABLON_V2_MIMARI'/'ayarlar.db',src_hash=sha(work))
    labroot=tmp_path/'GORSEL_REFERENCE_LAB'/'approved_chroma_test_20261026_latest_db'
    incoming=labroot/'chroma_previews'/'Ahsap_001.png'
    _image(incoming,magenta=True,dim=size)
    if lab_db:
        _db(labroot/'SABLON_V2_MIMARI'/'ayarlar.db',src_hash=sha(incoming),new_quad=True)
    return root,incoming,work,original

def test_report_is_readonly_compares_exact_file_with_approval(tmp_path,monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA',str(tmp_path/'AppData'))
    root,src,work,original=_fixture(tmp_path)
    oldhash=sha(work)
    old_db=sha(root/'SABLON_V2_MIMARI'/'ayarlar.db')
    plan=analyze(root,src.parent)
    assert len(plan['jobs'])==1
    job=plan['jobs'][0]
    assert job['status']=='READY_APPROVED_TRANSFER'
    assert job['trusted_lab_approval']
    report=write_report(plan)
    html=html_comparison(report)
    assert html.is_file() and 'Ahsap_001.png' in html.read_text('utf-8')
    assert sha(work)==oldhash
    assert sha(root/'SABLON_V2_MIMARI'/'ayarlar.db')==old_db
    assert sha(original)==oldhash

def test_apply_exact_single_file_approval_and_rollback_evidence(tmp_path,monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA',str(tmp_path/'AppData'))
    monkeypatch.setattr('magenta_reconcile_v472.app_busy',lambda:False)
    root,src,work,original=_fixture(tmp_path)
    old=sha(work)
    plan=write_report(analyze(root,src.parent))
    with pytest.raises(PermissionError):
        apply(plan,'not approved')
    output=apply(plan,CONFIRM)
    assert output['status']=='APPLIED' and output['count']==1
    assert sha(work)==sha(src)
    assert sha(original)==old
    backup=Path(output['backup'])
    assert sha(backup/'working'/'03_Ahsap_Tablo'/'Ahsap_001.png')==old
    assert (backup/'APPLY_RECEIPT.json').is_file()
    with sqlite3.connect(root/'SABLON_V2_MIMARI'/'ayarlar.db') as conn:
        approval=conn.execute('SELECT source_asset_sha256,review_status,manually_verified,surface_quad FROM template_profiles').fetchone()
    assert approval[0]==sha(work) and approval[1:3]==('APPROVED',1)
    assert json.loads(approval[3])[0]==[15,15]

def test_without_lab_approval_blocks_until_explicit_manual_review(tmp_path,monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA',str(tmp_path/'AppData'))
    monkeypatch.setattr('magenta_reconcile_v472.app_busy',lambda:False)
    root,src,work,original=_fixture(tmp_path,lab_db=False)
    old=sha(work)
    plan=write_report(analyze(root,src.parent))
    assert json.loads(plan.read_text('utf-8'))['jobs'][0]['status']=='READY_REQUIRES_REAPPROVAL'
    assert apply(plan,CONFIRM)['status']=='NO_ELIGIBLE_IMAGES'
    assert sha(work)==old
    result=apply(plan,CONFIRM,allow_review=True)
    assert result['count']==1 and sha(work)==sha(src)
    with sqlite3.connect(root/'SABLON_V2_MIMARI'/'ayarlar.db') as conn:
        record=conn.execute('SELECT review_status,manually_verified FROM template_profiles').fetchone()
    assert record==('REVIEW_REQUIRED',0)
    assert sha(original)==old

def test_dimension_mismatch_keeps_old_geometry_and_file(tmp_path):
    root,src,work,_=_fixture(tmp_path,size=(200,100))
    old=sha(work)
    item=analyze(root,src.parent)['jobs'][0]
    assert item['status']=='DIMENSIONS_CHANGED_REVIEW_COORDINATES'
    assert sha(work)==old

def test_duplicate_template_stem_is_blocked_not_guessed(tmp_path):
    root,src,work,_=_fixture(tmp_path)
    with sqlite3.connect(root/'SABLON_V2_MIMARI'/'ayarlar.db') as con:
        con.execute("""INSERT INTO template_profiles
          (template_uid,category,source_relative_path,source_asset_sha256,
           review_status,manually_verified,is_active,surface_quad,outer_quad,
           nominal_aspect,orientation,component_confidences)
          SELECT 'second_uid',category,source_relative_path,source_asset_sha256,
            review_status,manually_verified,is_active,surface_quad,outer_quad,
            nominal_aspect,orientation,component_confidences FROM template_profiles""")
    item=analyze(root,src.parent)['jobs'][0]
    assert item['status']=='AMBIGUOUS_OR_NOT_REGISTERED'

def test_external_code_inventory_and_staging_never_change_live_code(tmp_path):
    canon=tmp_path/'CURRENT_VERSION'
    current=canon/'MERKEZ'/'merkez.py'
    current.parent.mkdir(parents=True)
    current.write_text('print("new live")',encoding='utf-8')
    workspace=tmp_path/'GorselAna'
    _db(workspace/'SABLON_V2_MIMARI'/'ayarlar.db',src_hash='a'*64)
    previous=tmp_path/'C_AI_WORK'/'OLD_V46'
    tool=previous/'MERKEZ'/'merkez.py'
    tool.parent.mkdir(parents=True)
    tool.write_text('print("old")',encoding='utf-8')
    (previous/'MERKEZ'/'forgotten_helper.py').write_text('print("helper")',encoding='utf-8')
    external_db=previous/'SABLON_V2_MIMARI'/'ayarlar.db'
    _db(external_db,src_hash='b'*64)
    scan=build(canon,workspace,[tmp_path/'C_AI_WORK'])
    assert len(scan['candidate_code_roots'])==1
    assert any(r['status']=='DIFFERENT_FROM_ACTIVE_CODE' for r in scan['different_code_files'])
    assert any(r['status']=='ONLY_IN_TEST_FOLDER' for r in scan['different_code_files'])
    assert any(r['path']==str(external_db) for r in scan['external_state_files'])
    report=save(scan)
    old_code=current.read_bytes()
    with pytest.raises(PermissionError):stage(report,'no')
    rescue=stage(report,COPY_CONFIRM)
    files=list(rescue.rglob('*.py'))
    assert len(files)==2
    assert current.read_bytes()==old_code
    assert (rescue/'STAGING_RECEIPT.json').is_file()
    assert tool.is_file()
    assert scan['candidate_code_roots'][0]['safe_to_delete_without_manual_review'] is False


def test_two_lab_previews_for_one_template_are_blocked(tmp_path):
    root,src,work,_=_fixture(tmp_path)
    duplicate=src.parent/'different_experiment'/'Ahsap_001.png'
    _image(duplicate,magenta=True)
    plan=analyze(root,src.parent)
    assert len(plan['jobs'])==2
    assert all(item['status']=='MULTIPLE_LAB_IMAGES_FOR_ONE_TEMPLATE' for item in plan['jobs'])
    assert sha(work)!=sha(src)

def test_preferred_editor_code_can_never_silently_revert_to_old_folder(tmp_path,monkeypatch):
    import legacy_manager as manager
    root=tmp_path/'tested_install'
    (root/'SABLON_V2_MIMARI'/'core').mkdir(parents=True)
    (root/'SABLON_V2_MIMARI'/'app.py').write_text('valid')
    (root/'SABLON_V2_MIMARI'/'core'/'db.py').write_text('valid')
    old=tmp_path/'old_version'
    (old/'SABLON_V2_MIMARI'/'core').mkdir(parents=True)
    (old/'SABLON_V2_MIMARI'/'app.py').write_text('old')
    (old/'SABLON_V2_MIMARI'/'core'/'db.py').write_text('old')
    monkeypatch.setattr(manager,'ROOT',root)
    assert manager.preferred_code(env={'MOCKUP_LEGACY_SOURCE_ROOT':str(old)})==root
    (root/'SABLON_V2_MIMARI'/'app.py').unlink()
    with pytest.raises(manager.LegacyLaunchError,match='TEST_EDILMIS_KOD_EKSIK'):
        manager.preferred_code(env={'MOCKUP_LEGACY_SOURCE_ROOT':str(old)})


def test_store_membership_rekey_after_approved_magenta_replace(tmp_path,monkeypatch):
    from URETIM_V4.store_profiles_v47 import StoreProfiles,key_for
    monkeypatch.setenv('LOCALAPPDATA',str(tmp_path/'AppData'))
    monkeypatch.setattr('magenta_reconcile_v472.app_busy',lambda:False)
    root,src,work,original=_fixture(tmp_path)
    store=StoreProfiles(tmp_path/'AppData'/'GorselMockup'/'UnifiedV4')
    store.add_store('Magaza_01')
    old_item={'category':'03_Ahsap_Tablo','uid':'Ahsap_UID_001','source_sha':sha(work)}
    store.assign('Magaza_01',[old_item])
    previous=key_for(old_item)
    plan=write_report(analyze(root,src.parent))
    receipt=apply(plan,CONFIRM)
    updated=store.load()['stores']['Magaza_01']['templates']
    assert receipt['store_assignments_rekeyed']==1
    assert previous not in updated
    assert updated==[key_for({**old_item,'source_sha':sha(src)})]
    assert len(updated)==len(set(updated))==1
    assert sha(work)==sha(src)
    assert (Path(receipt['backup'])/'store_profiles_v47.before.json').is_file()
    assert sha(original)!=sha(work)


def test_store_rekey_works_even_if_new_photo_needs_approval(tmp_path,monkeypatch):
    from URETIM_V4.store_profiles_v47 import StoreProfiles,key_for
    monkeypatch.setenv('LOCALAPPDATA',str(tmp_path/'AppData'))
    monkeypatch.setattr('magenta_reconcile_v472.app_busy',lambda:False)
    root,src,work,_=_fixture(tmp_path,lab_db=False)
    store=StoreProfiles(tmp_path/'AppData'/'GorselMockup'/'UnifiedV4')
    store.add_store('Magaza_01')
    item={'category':'03_Ahsap_Tablo','uid':'Ahsap_UID_001','source_sha':sha(work)}
    store.assign('Magaza_01',[item])
    result=apply(write_report(analyze(root,src.parent)),CONFIRM,allow_review=True)
    assert result['count']==1
    assert store.load()['stores']['Magaza_01']['templates']==[
        key_for({**item,'source_sha':sha(src)})]
    with sqlite3.connect(root/'SABLON_V2_MIMARI'/'ayarlar.db') as con:
        assert con.execute('SELECT review_status FROM template_profiles').fetchone()[0]=='REVIEW_REQUIRED'


def test_store_rekey_conflict_blocks_before_any_image_change(tmp_path,monkeypatch):
    from URETIM_V4.store_profiles_v47 import StoreProfiles
    monkeypatch.setenv('LOCALAPPDATA',str(tmp_path/'AppData'))
    monkeypatch.setattr('magenta_reconcile_v472.app_busy',lambda:False)
    root,src,work,_=_fixture(tmp_path)
    manager=StoreProfiles(tmp_path/'AppData'/'GorselMockup'/'UnifiedV4')
    manager.add_store('Magaza_01');manager.add_store('Magaza_02')
    manager.assign('Magaza_01',[{'category':'03_Ahsap_Tablo',
                                 'uid':'Ahsap_UID_001','source_sha':sha(work)}])
    manager.assign('Magaza_02',[{'category':'03_Ahsap_Tablo',
                                 'uid':'other_uid','source_sha':sha(src)}])
    before=sha(work)
    report=write_report(analyze(root,src.parent))
    with pytest.raises(ValueError,match='STORE_SOURCE_IMAGE_REUSED_ACROSS_STORES'):
        apply(report,CONFIRM)
    assert sha(work)==before


def test_duplicate_extension_in_active_pool_blocks_magenta_apply(tmp_path):
    root,src,work,_=_fixture(tmp_path)
    conflict=work.with_suffix('.jpeg')
    _image(conflict)
    job=analyze(root,src.parent)['jobs'][0]
    assert job['status']=='ACTIVE_SAME_NAME_DIFFERENT_EXTENSION'
    assert job['active_same_stem_variants']==[str(conflict)]


def test_recovery_after_store_save_failure_keeps_original_and_db(tmp_path,monkeypatch):
    from URETIM_V4.store_profiles_v47 import StoreProfiles
    monkeypatch.setenv('LOCALAPPDATA',str(tmp_path/'AppData'))
    monkeypatch.setattr('magenta_reconcile_v472.app_busy',lambda:False)
    root,src,work,orig=_fixture(tmp_path)
    manager=StoreProfiles(tmp_path/'AppData'/'GorselMockup'/'UnifiedV4')
    manager.add_store('Magaza_01')
    manager.assign('Magaza_01',[{'category':'03_Ahsap_Tablo',
                                 'uid':'Ahsap_UID_001','source_sha':sha(work)}])
    old=sha(work);db=root/'SABLON_V2_MIMARI'/'ayarlar.db'
    def broken(self,config):
        raise OSError('SYNTHETIC_STORE_WRITE_FAILURE')
    monkeypatch.setattr(StoreProfiles,'save',broken)
    with pytest.raises(OSError,match='SYNTHETIC_STORE_WRITE_FAILURE'):
        apply(write_report(analyze(root,src.parent)),CONFIRM)
    assert sha(work)==old and sha(orig)==old
    with sqlite3.connect(db) as con:
        assert con.execute('SELECT source_asset_sha256 FROM template_profiles').fetchone()[0]==old


def test_active_identity_report_distinguishes_real_duplication_from_original_backup(tmp_path):
    from external_inventory_v472 import inspect_active_templates
    root,src,work,archive=_fixture(tmp_path)
    # Working + ORIGINAL_ARCHIVE share expected old bytes. That is NOT a
    # duplicate active template; different extensions in working ARE.
    clean=inspect_active_templates(root)
    assert clean['same_identity_different_files']==[]
    assert clean['same_bytes_different_identities']==[]
    assert clean['db_active_profile_mismatches']==[]
    assert clean['working_without_legacy_db_profile']==[]
    other=work.with_suffix('.jpeg')
    _image(other)
    dup=inspect_active_templates(root)
    assert len(dup['same_identity_different_files'])==1
    assert len(dup['db_active_profile_mismatches'])==1
    assert dup['photos_deleted_by_this_scan']==0
    assert archive.is_file()


def test_store_rekey_many_stores_keeps_memberships_unique(tmp_path):
    from URETIM_V4.store_profiles_v47 import StoreProfiles
    manager=StoreProfiles(tmp_path/'private')
    manager.add_store('Magaza_01')
    manager.add_store('Magaza_03')
    one={'category':'03_Ahsap_Tablo','uid':'ahsap_1','source_sha':'a'*64}
    two={'category':'02_Cam_Tablo_Yatay','uid':'cam_7','source_sha':'b'*64}
    manager.assign('Magaza_01',[one])
    manager.assign('Magaza_03',[two])
    plan=manager.preview_rekey([
        {'category':one['category'],'uid':one['uid'],'old_sha':one['source_sha'],'new_sha':'c'*64},
        {'category':two['category'],'uid':two['uid'],'old_sha':two['source_sha'],'new_sha':'d'*64},
    ])
    assert plan['changed_count']==2
    assert manager.load()['stores']['Magaza_01']['templates']==['03_Ahsap_Tablo:ahsap_1@'+'a'*64]
    manager.save(plan['new'])
    assert manager.load()['stores']['Magaza_01']['templates']==['03_Ahsap_Tablo:ahsap_1@'+'c'*64]
    assert manager.load()['stores']['Magaza_03']['templates']==['02_Cam_Tablo_Yatay:cam_7@'+'d'*64]
