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
            nominal_aspect TEXT,orientation TEXT,component_confidences TEXT)""")
        db.execute("""INSERT INTO template_profiles VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
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
        con.execute("""INSERT INTO template_profiles SELECT 'second_uid',category,source_relative_path,
                  source_asset_sha256,review_status,manually_verified,is_active,surface_quad,
                  outer_quad,nominal_aspect,orientation,component_confidences FROM template_profiles""")
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
