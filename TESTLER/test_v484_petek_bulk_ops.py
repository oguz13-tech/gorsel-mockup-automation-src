"""PETEK V4.8.4 grouped 4-corner automation; strict no-auto-approval tests."""
from __future__ import annotations
from pathlib import Path
import sys
import json
import cv2
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'MERKEZ'))
from TESTLER.test_v477_petek_browser_integration import fixture,params,valid_mask
from MERKEZ.PETEK_V3 import engine


def _magenta_photo(path):
    scene=np.full((360,520,3),185,np.uint8)
    cv2.rectangle(scene,(70,70),(445,305),(255,0,255),-1)
    for x in range(110,426,30):
        cv2.rectangle(scene,(x,110),(x+8,283),(10,10,10),-1)
    assert cv2.imwrite(str(path),scene)
    return {'name':path.name,'uid':path.stem,'source_sha':engine.digest(path)}


def test_seventh_category_status_rows_are_backed_by_real_files(tmp_path,monkeypatch):
    client,photo,registry,workspace=fixture(tmp_path,monkeypatch)
    archive=workspace/'2_SABLON_HAVUZU_ORIJINAL_YEDEK'/'Petek_Dolabi'
    archive.mkdir(parents=True)
    copied=archive/photo.name
    copied.write_bytes(photo.read_bytes())
    res=client.get('/api/petek/templates')
    assert res.status_code==200
    data=res.get_json()
    assert data['scanned_photos']==1
    assert data['items'][0]['backup_status']=='MATCH'
    assert data['items'][0]['working_ok'] is True
    assert data['items'][0]['mask_verified'] is False
    assert data['counts']['NEW']==1
    assert data['counts']['backup_missing']==0
    copied.write_bytes(copied.read_bytes()+b'changed')
    new=client.get('/api/petek/templates').get_json()['items'][0]
    assert new['backup_status']=='DIFFERENT'
    assert new['status']=='NEW'
    assert not list(registry.profiles.glob('*.json'))


def test_bulk_automatic_four_corner_detect_is_read_only_per_template(tmp_path,monkeypatch):
    client,photo,registry,_=fixture(tmp_path,monkeypatch)
    selected=_magenta_photo(photo)
    second=_magenta_photo(photo.parent/'Petek_Dolabi_002.png')
    original={p:p.read_bytes() for p in (photo,photo.parent/'Petek_Dolabi_002.png')}
    res=client.post('/api/petek/bulk-propose',json={'items':[selected,second]})
    assert res.status_code==200,res.get_json()
    data=res.get_json()
    assert data['read_only'] and data['human_approval_required']
    assert len(data['proposals'])==2
    assert not data['failed']
    for item in data['proposals']:
        assert len(item['quad'])==4 and item['coverage']>.25
        assert item['saved'] is False
    assert not list(registry.profiles.glob('*.json'))
    for path,source in original.items():assert path.read_bytes()==source


def test_bulk_new_only_draft_keeps_approval_manual_and_no_overwrite(tmp_path,monkeypatch):
    client,photo,registry,_=fixture(tmp_path,monkeypatch)
    selected=_magenta_photo(photo)
    before=photo.read_bytes()
    route='/api/petek/bulk-save-new-drafts'
    without=client.post(route,json={'items':[selected]})
    assert without.status_code==409
    request={'items':[selected],'confirm':'CREATE_NEW_DRAFTS_ONLY_NO_APPROVAL'}
    accepted=client.post(route,json=request)
    assert accepted.status_code==200,accepted.get_json()
    data=accepted.get_json()
    assert data['created_count']==1 and data['approved_count']==0
    p,mask=registry.get(photo.stem)
    assert p['status']=='DRAFT' and mask.dtype==np.uint8
    profile=registry.profiles/(photo.stem+'.json')
    saved_bytes=profile.read_bytes()
    again=client.post(route,json=request).get_json()
    assert again['created_count']==0 and len(again['failed'])==1
    assert profile.read_bytes()==saved_bytes and photo.read_bytes()==before


def test_bulk_per_item_failure_isolation_sha_mismatch_and_limit(tmp_path,monkeypatch):
    client,photo,registry,_=fixture(tmp_path,monkeypatch)
    good=_magenta_photo(photo)
    bad={**good,'source_sha':'f'*64,'name':'not_in_working.png','uid':'not_in_working'}
    res=client.post('/api/petek/bulk-propose',json={'items':[good,bad]})
    assert res.status_code==200,res.get_json()
    result=res.get_json()
    assert len(result['proposals'])==1 and len(result['failed'])==1
    huge=client.post('/api/petek/bulk-propose',json={'items':[good]*9})
    assert huge.status_code==409
    assert not list(registry.profiles.glob('*.json'))


def test_bulk_cannot_touch_existing_approved_registry(tmp_path,monkeypatch):
    client,photo,registry,_=fixture(tmp_path,monkeypatch)
    data=params(photo)
    old=registry.save(photo.stem,photo,data['quad'],valid_mask(),1.1163,
                       approved=True,reviewer='Human')
    before=(registry.profiles/(photo.stem+'.json')).read_bytes()
    selected={'name':photo.name,'uid':photo.stem,'source_sha':engine.digest(photo)}
    for route in ('/api/petek/bulk-propose','/api/petek/bulk-save-new-drafts'):
        body={'items':[selected],'confirm':'CREATE_NEW_DRAFTS_ONLY_NO_APPROVAL'}
        response=client.post(route,json=body)
        assert response.status_code==200
        assert response.get_json()['failed']
    assert (registry.profiles/(photo.stem+'.json')).read_bytes()==before
    assert registry.get(photo.stem,require_approved=True)[0]['mask_sha']==old['mask_sha']


def test_grouped_bulk_selection_controls_wired_with_stop_and_one_page(tmp_path):
    html=(ROOT/'SABLON_V2_MIMARI/templates/index.html').read_text('utf-8')
    js=(ROOT/'SABLON_V2_MIMARI/static/js/petek_editor_v477.js').read_text('utf-8')
    css=(ROOT/'SABLON_V2_MIMARI/static/css/petek_editor_v477.css').read_text('utf-8')
    assert 'TOPLU OTOMATİK 4 KÖŞE TESPİT ET' in html
    for identifier in ('petekV484BulkMode','petekV484BulkAll','petekV484BulkNew',
        'petekV484BulkDetect','petekV484BulkStop','petekV484BulkSave','petekV484BulkCount'):
        assert 'id="'+identifier+'"' in html and identifier in js
    assert "selected.slice(i,i+8)" in js
    assert "runBulkPetek(false)" in js and "runBulkPetek(true)" in js
    assert "bulk-propose" in js and "bulk-save-new-drafts" in js
    assert 'class="petek-v484-summary"' in html
    assert "petek-v484-pictos" in js
    assert '[hidden]{display:none!important;}' in css
