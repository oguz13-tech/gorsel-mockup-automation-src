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


def test_legacy_missing_lab_source_is_read_only_rebound_by_exact_sha(tmp_path,monkeypatch):
    """A matching working copy must not disappear just because its LAB source moved."""
    client,photo,registry,workspace=fixture(tmp_path,monkeypatch)
    old_lab=tmp_path/'old-lab'/'old_petekkaynak.png'
    old_lab.parent.mkdir(parents=True)
    photo.rename(old_lab)
    data=params(old_lab)
    original=registry.save(old_lab.stem,old_lab,data['quad'],valid_mask(),1.1163,
                           approved=True,reviewer='Owner')
    profile_path=registry.profiles/(old_lab.stem+'.json')
    approved_bytes=profile_path.read_bytes()
    mask_file=registry.masks/(original['mask_sha']+'.png')
    mask_bytes=mask_file.read_bytes()
    old_lab.rename(photo)  # Original path is gone; working photo has exact same bytes.
    with pytest.raises(engine.MaskError):
        registry.get(old_lab.stem,require_approved=True)
    listing=client.get('/api/petek/templates')
    assert listing.status_code==200,listing.get_json()
    payload=listing.get_json()
    assert payload['scanned_photos']==1
    assert payload['working_path']==str(photo.parent)
    assert len(payload['items'])==1
    assert all(payload['items'][0][key]==value for key,value in {
        'name':photo.name,'uid':old_lab.stem,
        'source_sha':engine.digest(photo),'status':'APPROVED',
        'working_ok':True,'approved':True,'mask_verified':True}.items())
    detail=client.get('/api/petek/detail/'+photo.name+'?uid='+old_lab.stem)
    assert detail.status_code==200,detail.get_json()
    assert detail.get_json()['status']=='APPROVED'
    assert detail.get_json()['mask'].startswith('data:image/png;base64,')
    assert profile_path.read_bytes()==approved_bytes
    assert mask_file.read_bytes()==mask_bytes
    assert client.post('/api/petek/save-draft',json={**params(photo),'uid':old_lab.stem}).status_code==409


def test_existing_changed_old_source_must_not_be_hidden_by_new_valid_copy(tmp_path,monkeypatch):
    client,photo,registry,_=fixture(tmp_path,monkeypatch)
    source=tmp_path/'old-lab'/'petek_historic.png'
    source.parent.mkdir(parents=True)
    source.write_bytes(photo.read_bytes())
    data=params(source)
    registry.save(source.stem,source,data['quad'],valid_mask(),1.1163,
                  approved=True,reviewer='Human')
    # Explicitly existing but altered source must not fallback silently.
    source.write_bytes(source.read_bytes()+b'tampered')
    result=client.get('/api/petek/templates')
    assert result.status_code==200
    payload=result.get_json()
    assert payload['scanned_photos']==1
    assert payload['items'][0]['status']=='REVIEW_REQUIRED'
    assert payload['warnings']
    assert client.get('/api/petek/detail/'+photo.name+'?uid='+source.stem).status_code==409


def test_bad_legacy_profile_does_not_hide_new_petek_photo(tmp_path,monkeypatch):
    client,photo,registry,_=fixture(tmp_path,monkeypatch)
    other=photo.parent/'Petek_Dolabi_002.png'
    different=np.full((300,400,3),210,dtype=np.uint8)
    assert cv2.imwrite(str(other),different)
    registry.save(photo.stem,photo,params(photo)['quad'],valid_mask(),1.1163,
                  approved=True,reviewer='Human')
    profile_path=registry.profiles/(photo.stem+'.json')
    doc=json.loads(profile_path.read_text('utf-8'))
    doc['source']='/missing/old/lab/path.png'
    doc['mask_sha']='0'*64  # Broken legacy mask must be flagged, not hide other photo.
    profile_path.write_text(json.dumps(doc),encoding='utf-8')
    result=client.get('/api/petek/templates')
    assert result.status_code==200,result.get_json()
    data=result.get_json()
    assert data['scanned_photos']==2
    assert data['items'][0]['status']=='REVIEW_REQUIRED'
    assert any(p['name']==other.name and p['status']=='NEW' for p in data['items'])
    assert data['warnings']


def test_unified_discovery_reuses_approved_mask_with_verified_working_photo(tmp_path,monkeypatch):
    from MERKEZ.URETIM_V4.unlimited_selection import discover_all_approved_seven_categories
    client,photo,registry,workspace=fixture(tmp_path,monkeypatch)
    old_lab=tmp_path/'old-lab'/'approved_petekkaynak.png'
    old_lab.parent.mkdir(parents=True)
    photo.rename(old_lab)
    data=params(old_lab)
    approved=registry.save(old_lab.stem,old_lab,data['quad'],valid_mask(),1.1163,
                           approved=True,reviewer='Owner')
    stored_bytes=(registry.profiles/(old_lab.stem+'.json')).read_bytes()
    old_lab.rename(photo)
    selected,audit=discover_all_approved_seven_categories(
        workspace,petek_registry=registry,categories=['06_Petek_Kapama'])
    assert len(selected)==1,audit
    assert selected[0]['source']==str(photo.resolve())
    assert selected[0]['mask_sha']==approved['mask_sha']
    assert selected[0]['uid']==old_lab.stem
    assert (registry.profiles/(old_lab.stem+'.json')).read_bytes()==stored_bytes
    # If two working files share the SHA, do NOT choose one arbitrarily.
    duplicate=photo.parent/'second_approved.jpg'
    duplicate.write_bytes(photo.read_bytes())
    selected,audit=discover_all_approved_seven_categories(
        workspace,petek_registry=registry,categories=['06_Petek_Kapama'])
    assert not selected
    assert 'PETEK_ESKI_KAYNAK_ESLESMESI_GUVENSIZ' in audit['skipped'][0]['reason']


def test_petek_magenta_auto_corners_and_mask_keep_dark_vents_untouched(tmp_path,monkeypatch):
    from MERKEZ.PETEK_V3.magenta_quad_v479 import detect_magenta_quad
    client,photo,registry,_=fixture(tmp_path,monkeypatch)
    scene=np.full((360,520,3),np.array([175,180,185],np.uint8),dtype=np.uint8)
    target=np.asarray([[85,95],[435,85],[445,290],[80,305]],np.int32)
    cv2.fillConvexPoly(scene,target,(255,0,255))  # BGR magenta
    for col in range(120,421,30):
        cv2.rectangle(scene,(col,119),(col+9,274),(10,12,16),-1)
    assert cv2.imwrite(str(photo),scene)
    payload={'name':photo.name,'uid':photo.stem,'source_sha':engine.digest(photo)}
    answer=client.post('/api/petek/auto-corners',json=payload)
    assert answer.status_code==200,answer.get_json()
    data=answer.get_json()
    assert data['draft_only'] and data['source_sha']==engine.digest(photo)
    quad=engine.validated_quad(data['quad'],scene.shape)
    for found,expected in zip(quad,target):
        assert np.linalg.norm(found-expected)<24,(found,expected)
    assert not list(registry.profiles.glob('*.json'))  # Auto detect never saves.
    mask_reply=client.post('/api/petek/auto-mask',json={**payload,'quad':data['quad']})
    assert mask_reply.status_code==200,mask_reply.get_json()
    mask_data=mask_reply.get_json()
    assert mask_data['qa']['mode']=='MAGENTA_BASKI_YUZEYI'
    raw=base64.b64decode(mask_data['mask'].partition(',')[2])
    mask=cv2.imdecode(np.frombuffer(raw,dtype=np.uint8),cv2.IMREAD_GRAYSCALE)
    assert mask[190,155]==0  # the real black vertical vent stays protected
    assert mask[190,177]>200  # magenta printable wood
    assert mask[20,20]==0   # background never printed
    assert not list(registry.profiles.glob('*.json'))


def test_petek_auto_corners_no_magenta_or_wrong_sha_never_writes(tmp_path,monkeypatch):
    client,photo,registry,_=fixture(tmp_path,monkeypatch)
    payload={'name':photo.name,'uid':photo.stem,'source_sha':engine.digest(photo)}
    assert client.post('/api/petek/auto-corners',json=payload).status_code==409
    assert client.post('/api/petek/auto-corners',json={**payload,'source_sha':'f'*64}).status_code==409
    assert not list(registry.profiles.glob('*.json'))


def test_petek_auto_corners_approved_is_immutable(tmp_path,monkeypatch):
    client,photo,registry,_=fixture(tmp_path,monkeypatch)
    registry.save(photo.stem,photo,params(photo)['quad'],valid_mask(),1.1163,
                  approved=True,reviewer='Human')
    before=(registry.profiles/(photo.stem+'.json')).read_bytes()
    response=client.post('/api/petek/auto-corners',json={
        'name':photo.name,'uid':photo.stem,'source_sha':engine.digest(photo)})
    assert response.status_code==409
    assert (registry.profiles/(photo.stem+'.json')).read_bytes()==before


def test_petek_magenta_rejects_two_competing_panels():
    from MERKEZ.PETEK_V3.magenta_quad_v479 import detect_magenta_quad
    image=np.full((600,900,3),180,np.uint8)
    cv2.rectangle(image,(100,180),(350,460),(255,0,255),-1)
    cv2.rectangle(image,(520,180),(770,460),(255,0,255),-1)
    with pytest.raises(engine.MaskError,match='BIRDEN_COK_ADAY'):
        detect_magenta_quad(image)


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
    center=(ROOT/'MERKEZ'/'merkez.py').read_text('utf-8')
    assert '7 KATEGORİ — ŞABLON / 4 KÖŞE / PETEK MASKE İNCELE' in center
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


def test_petek_overlay_uses_grayscale_intensity_not_opaque_alpha():
    """Black vents in an opaque grayscale mask must remain visually untinted."""
    js=(ROOT/'SABLON_V2_MIMARI'/'static'/'js'/'petek_editor_v477.js').read_text('utf-8')
    assert 'const coverage=overlay.data[i]' in js
    assert 'Math.round(coverage*0.60)' in js
    assert "globalCompositeOperation='source-in'" not in js
    assert 't.putImageData(overlay,0,0)' in js
