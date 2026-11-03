"""Regression for false 'Tam 15 ızgara ...' on legitimate 13/14/16 previews.

Real Chromium UI click with an isolated read-only API stub; production files
and Flask registry are never touched. The Flask response contract is retained.
"""
from pathlib import Path
import base64
import re

import cv2
import numpy as np
import pytest

pytest.importorskip('playwright.sync_api')
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1] / 'SABLON_V2_MIMARI'


def data_png(rgb=225):
    image = np.full((160, 200, 3), rgb, dtype=np.uint8)
    ok, compressed = cv2.imencode('.png', image)
    assert ok
    return compressed.tobytes(), 'data:image/png;base64,' + base64.b64encode(compressed).decode()


@pytest.mark.parametrize('count',[13, 14, 15, 16])
def test_real_vent_count_preview_is_displayed_instead_of_false_15_error(count):
    artwork_bytes, photo = data_png(200)
    _, printable_mask = data_png(255)
    html = (ROOT / 'templates/index.html').read_text('utf-8')
    assert 'petek_editor_v477.js?v=20261101-' in html
    html = re.sub(r'<script\s+src=[^>]+></script>', '', html)
    html = re.sub(r'<link\s+rel="stylesheet"[^>]+>', '', html)
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(
                headless=True, executable_path='/usr/bin/chromium', args=['--no-sandbox'])
        except Exception as exc:
            pytest.skip(str(exc))
        try:
            page = browser.new_page(viewport={'width':1440, 'height':900})
            page.set_content(html, wait_until='domcontentloaded')
            page.evaluate('''([photo, mask, count]) => {
                window.confirm=()=>true;
                window.alert=()=>{};
                window.previewRequestCount=0;
                window.previewErrorCount=0;
                const NativeImage=window.Image;
                window.Image=class extends NativeImage {
                    set src(value){super.src=String(value).startsWith('/api/petek/photo/')?photo:value;}
                };
                window.fetch=async(path, opts={})=>{
                    let result={success:true};
                    if(path==='/api/petek/templates') {
                        result={success:true,items:[{
                            name:'petek_13_16.png',uid:'uid_test',source_sha:'a'.repeat(64),
                            status:'DRAFT',approved:false,working_ok:true,mask_verified:true,
                            backup_status:'MATCH'}], scanned_photos:1,matched_approved_records:0,
                            registry_approved_total:0,unmatched_approved_records:0};
                    } else if(path.startsWith('/api/petek/detail/')) {
                        result={success:true,name:'petek_13_16.png',uid:'uid_test',
                            status:'DRAFT',approved:false,source_sha:'a'.repeat(64),
                            width:200,height:160,mask:mask,base_mask:null,
                            quad:[[10,10],[190,10],[190,150],[10,150]],
                            curve_points:{top:[],bottom:[]}, physical_aspect:1.1};
                    } else if(path==='/api/petek/service-status') {
                        result={success:true,contract:'PETEK_PREVIEW_API_VNEXT_JSON_20261101',preview_ui_revision:'PETEK_REAL_ARTWORK_PREVIEW_V4112',code_root:'TEST'};
                    } else if(path==='/api/petek/preview-artwork') {
                        window.previewRequestCount++;
                        let body=JSON.parse(opts.body);
                        if(body.fifteen_slot_ab!==true || body.fifteen_slot_strength!=='orta'){
                            window.previewErrorCount++;
                        }
                        result={success:true,preview:photo,after:photo,
                            slot_qa:{count:count,changed_pixels:95,
                                alignment:'SOURCE_PHOTO_'+count,
                                spacings_rectified_900:Array(count-1).fill(45)},
                            pink_qa:{status:'TEMIZ',remaining_pixels:0},mask_qa:{protected_magenta_pixels:0}};
                    }
                    return {ok:true,json:async()=>result};
                };
            }''', [photo, printable_mask, count])
            page.add_script_tag(content=(ROOT/'static/js/petek_quad_drag_v481.js').read_text('utf-8'))
            page.add_script_tag(content=(ROOT/'static/js/petek_editor_v477.js').read_text('utf-8'))
            page.locator('#petekV477Nav').click()
            page.wait_for_function("document.getElementById('petekV477Name').textContent.includes('uid_test')")
            page.locator('#petekV477Artwork').set_input_files({
                'name':'ornek_tasarim.png', 'mimeType':'image/png', 'buffer':artwork_bytes})
            page.locator('#petekV493Preview').click()
            page.wait_for_function("document.getElementById('petekV493After').disabled===false", timeout=20000)
            assert page.evaluate('window.previewRequestCount') == 1
            assert page.evaluate('window.previewErrorCount') == 0
            assert f'{count} / {count} gerçek yarık' in page.locator('#petekV493Result').inner_text()
            assert f'{count} GERÇEK IZGARA A/B' in page.locator('#petekV477Status').inner_text()
            assert 'Tam 15' not in page.locator('#petekV477Status').inner_text()
            page.locator('#petekV493Before').click()
            assert page.locator('#petekV493After').is_enabled()
            page.locator('#petekV493After').click()
            assert page.locator('#petekV493Before').is_enabled()
        finally:
            browser.close()


def test_missing_backend_geometry_is_not_pretended_success():
    script=(ROOT / 'static/js/petek_editor_v477.js').read_text('utf-8')
    assert 'detectedCount<13 || detectedCount>16' in script
    assert "data.slot_qa?.count!==15" not in script
    assert '13–16 yarık' in script
