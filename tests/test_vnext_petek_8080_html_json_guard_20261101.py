"""PETEK 8080 API JSON contract, missing server and read-only diagnosis.

Browser tests mock localhost responses; they never access a real user runtime.
"""
from pathlib import Path
import base64
import re
import cv2
import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[1]
WEB=ROOT/'SABLON_V2_MIMARI'
pytest.importorskip('playwright.sync_api')
from playwright.sync_api import sync_playwright


def _png():
    a=np.full((160,200,3),255,np.uint8)
    ok,buf=cv2.imencode('.png',a)
    assert ok
    return buf.tobytes(),'data:image/png;base64,'+base64.b64encode(buf).decode()


@pytest.mark.parametrize('server_case',['html_404','html_500','wrong_contract'])
def test_preview_reports_stale_backend_not_unexpected_token(server_case):
    art, photo=_png()
    html=(WEB/'templates/index.html').read_text('utf-8')
    html=re.sub(r'<script\s+src=[^>]+></script>','',html)
    html=re.sub(r'<link\s+rel="stylesheet"[^>]+>','',html)
    with sync_playwright() as p:
        try:
            browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
        except Exception as exc:
            pytest.skip(str(exc))
        try:
            page=browser.new_page(viewport={'width':1400,'height':900})
            page.set_content(html)
            page.evaluate('''([image, caseName]) => {
                window.alert=()=>{};
                window.confirm=()=>true;
                window.previewPostCount=0;
                const NativeImage=window.Image;
                window.Image=class extends NativeImage {
                    set src(url){super.src=String(url).startsWith('/api/petek/photo/')?image:url;}
                };
                window.fetch=async (path, options={}) => {
                    if(path==='/api/petek/service-status') {
                        if(caseName==='wrong_contract')
                            return {ok:true,status:200,headers:{get:()=>"application/json"},
                                json:async()=>({success:true,contract:'OLD_PETEK_API',code_root:'C:/old'})};
                        return {ok:false,status:caseName==='html_404'?404:500,
                            headers:{get:()=>"text/html; charset=utf-8"},
                            json:async()=>{throw SyntaxError("Unexpected token '<'");}};
                    }
                    if(path==='/api/petek/templates')return {ok:true,
                        json:async()=>({success:true,items:[{name:'test.png',uid:'test_uid',
                           source_sha:'a'.repeat(64),status:'DRAFT',approved:false,
                           working_ok:true,mask_verified:true,backup_status:'MATCH'}],
                           scanned_photos:1,matched_approved_records:0,
                           registry_approved_total:0,unmatched_approved_records:0})};
                    if(path.startsWith('/api/petek/detail/'))return {ok:true,
                        json:async()=>({success:true,name:'test.png',uid:'test_uid',
                         status:'DRAFT',approved:false,source_sha:'a'.repeat(64),
                         width:200,height:160,mask:image,quad:[[10,10],[190,10],[190,150],[10,150]],
                         curve_points:{top:[],bottom:[]},physical_aspect:1.1})};
                    if(path==='/api/petek/preview-artwork')window.previewPostCount++;
                    return {ok:true,json:async()=>({success:true})};
                };
            }''',[photo,server_case])
            page.add_script_tag(content=(WEB/'static/js/petek_quad_drag_v481.js').read_text('utf-8'))
            page.add_script_tag(content=(WEB/'static/js/petek_editor_v477.js').read_text('utf-8'))
            page.locator('#petekV477Nav').click()
            page.wait_for_function("document.getElementById('petekV477Name').textContent.includes('test_uid')")
            page.locator('#petekV477Artwork').set_input_files({'name':'design.png','mimeType':'image/png','buffer':art})
            page.locator('#petekV477Preview').click()
            page.wait_for_function("document.getElementById('petekV477Status').textContent.includes('sunucusu eski/yanlış') || document.getElementById('petekV477Status').textContent.includes('JSON yerine HTML')", timeout=15000)
            msg=page.locator('#petekV477Status').inner_text()
            assert 'Unexpected token' not in msg
            assert '8080' in msg
            assert page.evaluate('window.previewPostCount')==0
        finally:
            browser.close()


def test_service_contract_and_preflight_remain_read_only():
    server=(WEB/'core/petek_web_v477.py').read_text('utf-8')
    app=(WEB/'app.py').read_text('utf-8')
    js=(WEB/'static/js/petek_editor_v477.js').read_text('utf-8')
    assert "@petek_web.get('/api/petek/service-status')" in server
    assert "PETEK_PREVIEW_API_VNEXT_JSON_20261101" in server
    assert 'read_only' in server
    assert 'request.path == "/api/petek/service-status"' in app
    assert 'app.errorhandler(404)' in app and 'app.errorhandler(500)' in app
    assert js.index("api('/api/petek/service-status')") < js.index("api('/api/petek/preview-artwork'")
    bat=(ROOT/'PETEK_8080_DOGRULA_WINDOWS.bat').read_bytes()
    assert b'v4102_verify_package.py' in bat
    assert b'\x0b' not in bat
