"""PETEK batch 2: real print preview, sidebar list/zoom and standalone renamer.

All images and databases are synthetic temporary fixtures. No real runtime.
"""
from __future__ import annotations
import base64
import inspect
from pathlib import Path
import sys
import cv2
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'MERKEZ'))
from MERKEZ.PETEK_V3 import engine
from SABLON_V2_MIMARI.core import petek_web_v477 as browser
from TESTLER.test_v477_petek_browser_integration import fixture,params,valid_mask,png_as_browser


def test_true_artwork_preview_matches_peteks_real_render_and_preserves_vents(tmp_path,monkeypatch):
    client,photo,registry,_=fixture(tmp_path,monkeypatch)
    scene=engine.read_bgr(photo)
    art=np.full((240,320,3),(15,30,220),np.uint8)
    cv2.rectangle(art,(55,40),(265,200),(240,50,25),-1)
    ok,png=cv2.imencode('.png',art)
    assert ok
    req={**params(photo),'uid':photo.stem,
         'artwork_png':'data:image/png;base64,'+base64.b64encode(png.tobytes()).decode('ascii')}
    original=photo.read_bytes()
    response=client.post('/api/petek/preview-artwork',json=req)
    assert response.status_code==200,response.get_json()
    data=response.get_json()
    assert data['unsaved'] and data['protected_pixels_unchanged']
    out=cv2.imdecode(np.frombuffer(base64.b64decode(data['preview'].partition(',')[2]),
                                       dtype=np.uint8),cv2.IMREAD_COLOR)
    mask=valid_mask()
    assert out.shape==scene.shape
    assert np.array_equal(out[mask==0],scene[mask==0])
    assert not np.array_equal(out[mask>0],scene[mask>0])
    assert photo.read_bytes()==original
    assert not list(registry.profiles.glob('*.json'))


def test_artwork_preview_source_sha_and_mask_fail_closed(tmp_path,monkeypatch):
    client,photo,registry,_=fixture(tmp_path,monkeypatch)
    art=np.full((150,150,3),140,np.uint8)
    png=cv2.imencode('.png',art)[1].tobytes()
    req={**params(photo),'uid':photo.stem,
         'artwork_png':'data:image/png;base64,'+base64.b64encode(png).decode('ascii')}
    for payload in ({**req,'source_sha':'f'*64},
                    {**req,'uid':'different'},
                    {**req,'artwork_png':'data:image/png;base64,'+base64.b64encode(b'x').decode('ascii')},
                    {**req,'mask':png_as_browser(np.zeros((300,400),np.uint8))}):
        bad=client.post('/api/petek/preview-artwork',json=payload)
        assert bad.status_code==409,bad.get_json()
    assert not list(registry.profiles.glob('*.json'))


def test_petek_sidebar_zoom_preview_review_defaults_are_in_same_editor():
    html=(ROOT/'SABLON_V2_MIMARI/templates/index.html').read_text('utf-8')
    js=(ROOT/'SABLON_V2_MIMARI/static/js/petek_editor_v477.js').read_text('utf-8')
    css=(ROOT/'SABLON_V2_MIMARI/static/css/petek_editor_v477.css').read_text('utf-8')
    assert 'class="petek-v477-list-pane"' in html
    assert html.index('id="petekV477List"')<html.index('id="petekV477Canvas"')
    assert 'id="petekV477Zoom"' in html
    assert 'id="petekV477Preview"' in html and 'id="petekV477Artwork"' in html
    assert 'value="Can"' in html
    assert 'id="petekV477Confirm" type="checkbox" checked' in html
    assert "'/api/petek/preview-artwork'" in js
    assert "previewMode" in js and "function setZoom(" in js
    assert "listVisual" in js and "petekV477List" in js
    assert "nav.after(list)" in js
    assert "const list=$('petekV477ListPane')||s.listHost" in js
    assert "function restoreListHost()" in js
    assert 'id="petekV477ListPane"' in html
    assert 'id="petekV477Undo"' in html
    assert 'id="petekV477ResetCorners"' in html
    assert 'petek_quad_drag_v481.js' in html
    assert 'PetekQuadDragV481.closest' in js and 'PetekQuadDragV481.moved' in js
    assert 'setPointerCapture' in js and 'releasePointerCapture' in js
    assert 's.mask=blank();s.base=null;s.curves={top:[],bottom:[]}' in js
    assert "Switching to corner mode must NEVER discard an auto-detected quad" in js
    assert 'function snapshot()' in js and 'async function undoLast()' in js
    assert "addEventListener('click',undoLast)" in js
    assert "overflow:auto;" in css


def test_independent_renamer_uses_packaged_python_and_visible_category_selector():
    batch=(ROOT/'BAGIMSIZ_ARACLAR/01_GORSEL_ISIMLENDIRICI.bat').read_text('utf-8')
    tool=(ROOT/'SABLON_V2_MIMARI/tools_runner.py').read_text('utf-8')
    assert r'MERKEZ\.venv\Scripts\python.exe' in batch
    assert 'py -3.11 -B' in batch
    assert 'pause' in batch
    assert 'dialog.transient(root)' not in inspect.getsource(
        __import__('SABLON_V2_MIMARI.tools_runner',fromlist=['choose_rename_category']).choose_rename_category)
    assert 'dialog.wait_visibility()' in tool
