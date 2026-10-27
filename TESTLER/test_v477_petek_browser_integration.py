"""Native seventh-category PETEK routes are backed by the real mask registry.

Synthetic-only acceptance: no user files, no second PETEK database, no bypass
of locked approvals. A browser-supplied RGBA PNG must pass exact grayscale QA.
"""
from pathlib import Path
import base64
import io
import json
import sys
import numpy as np
import cv2
from PIL import Image
from flask import Flask
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'MERKEZ'))
from MERKEZ.PETEK_V3 import engine
from MERKEZ.PETEK_V3.registry import Registry
from SABLON_V2_MIMARI.core import petek_web_v477 as browser


def fixture(tmp_path,monkeypatch):
    workspace=tmp_path/'Ana'
    working=workspace/'2_SABLON_HAVUZU'/'Petek_Dolabi'
    incoming=workspace/'YENI-BOS MOCKUP SABLON HAVUZU'/'Petek_Dolabi'
    working.mkdir(parents=True);incoming.mkdir(parents=True)
    photo=working/'Petek_Dolabi_001.png'
    # Bright panel + dark vent slots: external background is untouched.
    scene=np.full((300,400,3),165,dtype=np.uint8)
    scene[25:276,25:376]=235
    for x in range(60,351,24):
        scene[52:252,x:x+8]=22
    cv2.imwrite(str(photo),scene)
    registry_root=tmp_path/'LocalAppData'/'GorselMockup'/'PetekV3'
    monkeypatch.setattr(browser,'Registry',lambda:Registry(registry_root))
    app=Flask(__name__)
    app.config['TESTING']=True
    app.config['PETEK_WORKSPACE_V477']=str(workspace)
    app.register_blueprint(browser.petek_web)
    return app.test_client(),photo,Registry(registry_root),workspace

def png_as_browser(mask,*,color=False,transparent=False):
    array=np.zeros((mask.shape[0],mask.shape[1],4),dtype=np.uint8)
    array[:,:,:3]=mask[:,:,None]
    array[:,:,3]=255
    if color:array[50,50,0]=120
    if transparent:array[50,50,3]=0
    ok,png=cv2.imencode('.png',array)
    assert ok
    return 'data:image/png;base64,'+base64.b64encode(png.tobytes()).decode('ascii')

def valid_mask():
    mask=np.zeros((300,400),dtype=np.uint8)
    mask[35:266,35:366]=255
    for x in range(60,351,24):
        mask[52:252,x:x+8]=0
    return mask

def params(photo):
    return {'name':photo.name,'source_sha':engine.digest(photo),
            'quad':[[25,25],[375,25],[375,275],[25,275]],
            'mask':png_as_browser(valid_mask()),
            'physical_aspect':1.1163,'curve_points':{'top':[],'bottom':[]}}

def test_browser_category_lists_physical_working_without_duplicate_alias(tmp_path,monkeypatch):
    client,photo,registry,workspace=fixture(tmp_path,monkeypatch)
    payload=client.get('/api/petek/templates').get_json()
    assert payload['category']=='06_Petek_Kapama'
    assert payload['folder']=='2_SABLON_HAVUZU/Petek_Dolabi'
    assert len(payload['items'])==1 and payload['items'][0]['status']=='NEW'
    assert not (workspace/'2_SABLON_HAVUZU'/'06_Petek_Kapama').exists()
    data=client.get('/api/petek/detail/'+photo.name).get_json()
    assert data['uid']==photo.stem and data['status']=='NEW'
    assert data['width']==400 and data['height']==300


def test_same_ui_save_draft_approve_and_immutable_mask_source_sha(tmp_path,monkeypatch):
    client,photo,r,_=fixture(tmp_path,monkeypatch)
    data=params(photo);data['uid']=photo.stem
    response=client.post('/api/petek/save-draft',json=data)
    assert response.status_code==200,response.get_json()
    assert response.get_json()['status']=='DRAFT'
    profile,mask=r.get(photo.stem)
    assert np.array_equal(mask,valid_mask())
    assert profile['source_sha']==engine.digest(photo)
    assert profile['status']=='DRAFT'
    unauthorized=client.post('/api/petek/approve',json={**data,'confirmed_sha':data['source_sha'],
        'reviewer':'','confirm':'I_VISUALLY_CHECKED_VENTS_ARCHES_FLOOR'})
    assert unauthorized.status_code==409
    approved=client.post('/api/petek/approve',json={**data,'confirmed_sha':data['source_sha'],
        'reviewer':'Manual Inspector','confirm':'I_VISUALLY_CHECKED_VENTS_ARCHES_FLOOR'})
    assert approved.status_code==200,approved.get_json()
    assert approved.get_json()['status']=='APPROVED'
    profile_after,mask_after=r.get(photo.stem,require_approved=True)
    assert profile_after['source_sha']==engine.digest(photo)
    assert np.array_equal(mask_after,valid_mask())
    blocked=client.post('/api/petek/save-draft',json=data)
    assert blocked.status_code==409
    assert r.get(photo.stem,require_approved=True)[0]['mask_sha']==profile_after['mask_sha']


def test_invalid_grayscale_and_outside_mask_block_before_save(tmp_path,monkeypatch):
    client,photo,r,_=fixture(tmp_path,monkeypatch)
    data=params(photo);data['uid']=photo.stem
    bad=client.post('/api/petek/save-draft',json={**data,'mask':png_as_browser(valid_mask(),color=True)})
    assert bad.status_code==409 and 'NOT_OPAQUE_GRAYSCALE' in bad.get_json()['error']
    bad_alpha=client.post('/api/petek/save-draft',json={**data,'mask':png_as_browser(valid_mask(),transparent=True)})
    assert bad_alpha.status_code==409
    outside=valid_mask();outside[0,0]=255
    failed=client.post('/api/petek/save-draft',json={**data,'mask':png_as_browser(outside)})
    assert failed.status_code==409
    assert not list(r.profiles.glob('*.json'))


def test_identity_prevents_wrong_photo_approval_and_path_traversal(tmp_path,monkeypatch):
    client,photo,r,_=fixture(tmp_path,monkeypatch)
    data=params(photo);data['uid']=photo.stem
    assert client.post('/api/petek/save-draft',json={**data,'source_sha':'a'*64}).status_code==409
    assert client.get('/api/petek/photo/%2e%2e%2fsecret.png').status_code in (404,409)
    assert client.post('/api/petek/save-draft',json={**data,'uid':'other_uid'}).status_code==409
    assert client.post('/api/petek/approve',json={**data,'confirmed_sha':'wrong',
        'reviewer':'X','confirm':'I_VISUALLY_CHECKED_VENTS_ARCHES_FLOOR'}).status_code==409
    assert not list(r.profiles.glob('*.json'))


def test_existing_petek_approved_is_native_ui_read_only(tmp_path,monkeypatch):
    client,photo,r,_=fixture(tmp_path,monkeypatch)
    data=params(photo)
    r.save(photo.stem,photo,data['quad'],valid_mask(),1.1163,
           reviewer='Human',approved=True)
    visible=client.get('/api/petek/detail/'+photo.name).get_json()
    assert visible['status']=='APPROVED' and visible['mask'].startswith('data:image/png;base64,')
    status=client.get('/api/petek/templates').get_json()['items'][0]
    assert status['status']=='APPROVED'
    assert client.post('/api/petek/save-draft',json={**data,'uid':photo.stem}).status_code==409


def test_ui_category_is_inside_existing_page_with_native_operations():
    html=(ROOT/'SABLON_V2_MIMARI'/'templates'/'index.html').read_text('utf-8')
    js=(ROOT/'SABLON_V2_MIMARI'/'static'/'js'/'petek_editor_v477.js').read_text('utf-8')
    app=(ROOT/'SABLON_V2_MIMARI'/'app.py').read_text('utf-8')
    assert '07_Petek_Dolabi — Şablon / Maske / Onay' in html
    assert 'id="petekV477Editor"' in html
    assert 'petek_editor_v477.js' in html
    assert 'app.register_blueprint(petek_web)' in app
    for op in ('/api/petek/templates','/api/petek/auto-mask',
               '/api/petek/curve-preview','/api/petek/save-draft','/api/petek/approve'):
        assert op in js or op in (ROOT/'SABLON_V2_MIMARI'/'core'/'petek_web_v477.py').read_text('utf-8')
    assert "window.open" not in js
    assert 'tkinter' not in js


def test_same_web_editor_creates_r2_draft_without_mutating_previous_approval(tmp_path,monkeypatch):
    client,photo,r,_=fixture(tmp_path,monkeypatch)
    data=params(photo)
    original=r.save(photo.stem,photo,data['quad'],valid_mask(),1.1163,
                    approved=True,reviewer='Owner')
    old_mask_sha=original['mask_sha']
    result=client.post('/api/petek/new-revision',json={
        'name':photo.name,'uid':photo.stem,
        'source_sha':engine.digest(photo),'confirmed_sha':engine.digest(photo)})
    assert result.status_code==200,result.get_json()
    newer=result.get_json()['uid']
    assert newer==photo.stem+'_r2'
    old,mask=r.get(photo.stem,require_approved=True)
    assert old['mask_sha']==old_mask_sha and old['status']=='APPROVED'
    draft,_=r.get(newer)
    assert draft['status']=='DRAFT' and draft['source_sha']==old['source_sha']
    items=client.get('/api/petek/templates').get_json()['items']
    assert len(items)==2
    assert {x['uid'] for x in items}=={photo.stem,newer}
    assert {x['status'] for x in items}=={'APPROVED','DRAFT'}
    detail=client.get('/api/petek/detail/'+photo.name+'?uid='+newer).get_json()
    assert detail['uid']==newer and detail['status']=='DRAFT'
    assert client.get('/api/petek/detail/'+photo.name+'?uid=wrong').status_code==409
    saved=client.post('/api/petek/save-draft',json={**data,'uid':newer})
    assert saved.status_code==200,saved.get_json()
    approved=client.post('/api/petek/approve',json={**data,'uid':newer,
        'reviewer':'Second Reviewer','confirmed_sha':engine.digest(photo),
        'confirm':'I_VISUALLY_CHECKED_VENTS_ARCHES_FLOOR'})
    assert approved.status_code==200,approved.get_json()
    assert r.get(photo.stem,require_approved=True)[0]['mask_sha']==old_mask_sha


def test_revision_requires_explicit_valid_sha_and_approved_original(tmp_path,monkeypatch):
    client,photo,r,_=fixture(tmp_path,monkeypatch)
    data=params(photo)
    invalid=client.post('/api/petek/new-revision',json={
       'name':photo.name,'uid':photo.stem,'source_sha':engine.digest(photo),
       'confirmed_sha':engine.digest(photo)})
    assert invalid.status_code==409
    r.save(photo.stem,photo,data['quad'],valid_mask(),1.1163,
           approved=True,reviewer='Manual')
    invalid=client.post('/api/petek/new-revision',json={
        'name':photo.name,'uid':photo.stem,'source_sha':engine.digest(photo),
        'confirmed_sha':'wrong'})
    assert invalid.status_code==409
    assert not (r.profiles/(photo.stem+'_r2.json')).exists()
