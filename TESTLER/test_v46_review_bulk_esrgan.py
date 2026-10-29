"""V4.6 independent regression: drafts must never change approved geometry."""
from __future__ import annotations
import hashlib
import os
import sys
from contextlib import nullcontext
from pathlib import Path

import cv2
import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'SABLON_V2_MIMARI'))
sys.path.insert(0,str(ROOT/'MERKEZ'))
from URETIM_V4.finish_v42 import subdued_reflection


def test_editor_approval_is_sticky_and_bulk_detect_is_review_only():
    html=(ROOT/'SABLON_V2_MIMARI/templates/index.html').read_text(encoding='utf-8')
    css=(ROOT/'SABLON_V2_MIMARI/static/css/style.css').read_text(encoding='utf-8')
    js=(ROOT/'SABLON_V2_MIMARI/static/js/review_v46.js').read_text(encoding='utf-8')
    assert 'v46QuickApproval' in html and 'v46ApproveQuick' in html
    assert html.index('id="v46ApproveQuick"') < html.index('id="btnAutoCorner"')
    assert 'position: sticky' in css and 'v46-quick-approval' in css
    assert 'bulkDetectSelectedCorners()' in html
    assert 'save_as_draft:true' in js
    assert 'v46ApplyCornerDraft' in js and 'source_sha256' in js
    assert 'stopBulkCornerDetect' in js and 'v46BulkAlignmentReport' in js
    assert 'if (!confirm(' in js
    assert 'APPROVED' in js


def test_drafts_source_sha_and_identity_are_enforced(tmp_path,monkeypatch):
    pytest.importorskip("flask",reason="Flask not installed in isolated Linux test runtime")
    import app as m
    monkeypatch.setenv('LOCALAPPDATA',str(tmp_path/'local'))
    template=tmp_path/'input.png'
    assert cv2.imwrite(str(template),np.full((200,240,3),190,np.uint8))
    monkeypatch.setattr(m,'_safe_template_path',lambda category,tmpl: str(template))
    category,tmpl='02_Cam_Tablo_Dikey','001.png'
    quad=[[18,19],[211,19],[211,177],[18,177]]
    oldsha=hashlib.sha256(template.read_bytes()).hexdigest()
    m._v46_store_draft(category,tmpl,quad,oldsha,'WHITE')
    file=m._v46_draft_path(category,tmpl)
    assert file.exists()
    client=m.app.test_client()
    good=client.get('/api/v46/corner_draft',query_string={'category':category,'template':tmpl}).json
    if good.get('code') == 'DB_STARTUP_BLOCKED':
        pytest.skip('İzole ortamda üretim DB koruması endpoint testini bloke ediyor')
    assert good['available'] and good['corners']==quad and good['approved'] is False
    assert good['source_sha256']==oldsha
    assert m._v46_draft_path(category,'002.png') != file
    assert client.get('/api/v46/corner_draft',query_string={'category':category,'template':'002.png'}).json['available'] is False
    assert cv2.imwrite(str(template),np.full((200,240,3),172,np.uint8))
    stale=client.get('/api/v46/corner_draft',query_string={'category':category,'template':tmpl}).json
    assert stale['available'] is False and stale['stale'] is True
    assert file.is_file() # stale draft is preserved for audit, never applied


def test_bulk_post_uses_existing_single_detector_without_approval(tmp_path,monkeypatch):
    pytest.importorskip("flask",reason="Flask not installed in isolated Linux test runtime")
    import app as m
    monkeypatch.setenv('LOCALAPPDATA',str(tmp_path/'local'))
    src=tmp_path/'source.png'
    cv2.imwrite(str(src),np.full((280,300,3),215,np.uint8))
    before=hashlib.sha256(src.read_bytes()).hexdigest()
    monkeypatch.setattr(m,'_safe_template_path',lambda cat,tmpl: str(src))
    monkeypatch.setattr(m,'_analyze_auto_cached',lambda cat,path: ({
        'surface_quad':[[30,20],[260,20],[260,255],[30,255]],
        'confidence_total':.9,'surface_mode':'WHITE','surface_mode_confidence':.8,
        'component_confidences':{},'nominal_aspect':'V'},True))
    monkeypatch.setattr(m,'detect_occlusion_boxes',lambda *args: [])
    monkeypatch.setattr(m,'template_operation_lock',lambda *args,**kwargs:nullcontext())
    c=m.app.test_client()
    rv=c.post('/api/auto_detect_corners',
         headers={'X-Active-Category':'02_Cam_Tablo_Dikey','X-Active-Template':'source.png'},
         json={'save_as_draft':True})
    if rv.status_code == 503 and rv.json.get('code') == 'DB_STARTUP_BLOCKED':
        pytest.skip('İzole ortamda üretim DB koruması endpoint testini bloke ediyor')
    assert rv.status_code==200 and rv.json['success']
    assert rv.json['surface_priority_hint']=='BEYAZ_CAM_ADAYI_KATEGORI_TAHMINI'
    assert m._v46_draft_path('02_Cam_Tablo_Dikey','source.png').is_file()
    assert hashlib.sha256(src.read_bytes()).hexdigest()==before


def test_window_mullion_vs_spot_are_distinct_and_mask_safe():
    scene=np.full((400,520,3),120,np.uint8)
    art=np.full_like(scene,60)
    quad=[[50,40],[460,40],[460,355],[50,355]]
    mask=np.zeros(scene.shape[:2],np.uint8)
    cv2.fillConvexPoly(mask,np.asarray(quad,np.int32),255)
    window=subdued_reflection(scene,art,mask,quad,'02_Cam_Tablo_Yatay','strong')
    spot=subdued_reflection(scene,art,mask,quad,'04_Cam_Dograma','strong')
    off=subdued_reflection(scene,art,mask,quad,'02_Cam_Tablo_Yatay','off')
    assert np.array_equal(window[mask==0],art[mask==0])
    assert np.array_equal(spot[mask==0],art[mask==0])
    assert np.array_equal(off,art)
    assert not np.array_equal(window,spot)
    assert int(np.max(window.astype(np.int16)-art.astype(np.int16)))>=12
    # The reflection remains a broad gradient, not a hard cross or mullion.
    horizontal_steps=np.abs(np.diff(window[:,:,0].astype(np.int16),axis=1))
    assert int(horizontal_steps.max()) < 45


def test_real_esrgan_official_installer_is_opt_in_and_non_destructive():
    cmd=(ROOT/'KUR_REAL_ESRGAN_4K_WINDOWS.bat').read_text(encoding='utf-8')
    script=(ROOT/'KUR_REAL_ESRGAN_4K_WINDOWS.ps1').read_text(encoding='utf-8')
    assert 'ExecutionPolicy Bypass' in cmd
    assert 'github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/' in script
    assert 'realesrgan-ncnn-vulkan-20220424-windows.zip' in script
    assert "realesrgan-x4plus.bin" in script and "realesrgan-x4plus.param" in script
    assert 'GPU_SMOKE_PASS' in script and 'Get-FileHash' in script
    for prohibited in ['approved_geometry','ayarlar.db','v4_ortak_uretim.sqlite3', 'Remove-Item -LiteralPath $repo']:
        assert prohibited not in script


def test_port_transition_allowlist_safeguards():
    sys.path.insert(0,str(ROOT/'MERKEZ'))
    from port_transition_v46 import classify_owner
    me=ROOT/'SABLON_V2_MIMARI'/'app.py'
    old={'Name':'python.exe','CommandLine':r'python.exe -B C:\GorselMockup_V43\SABLON_V2_MIMARI\app.py'}
    other={'Name':'python.exe','CommandLine':r'python.exe -B C:\OtherProject\SABLON_V2_MIMARI\app.py'}
    node={'Name':'node.exe','CommandLine':r'node server.js'}
    assert classify_owner(old,me)=='old_review'
    assert classify_owner(other,me)=='unknown'
    assert classify_owner(node,me)=='unknown'
    assert classify_owner({'Name':'python.exe','CommandLine':r'python.exe -B C:\GorselMockup_V46\SABLON_V2_MIMARI\app.py'},me)=='unknown'
    assert classify_owner({'Name':'python.exe','CommandLine':str(me)},me)=='same_code'
