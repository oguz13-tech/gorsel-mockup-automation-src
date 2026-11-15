"""Browser regression: brush diameter is visible and wood paint respects curves only."""
import base64
import re
from pathlib import Path
import cv2
import numpy as np
import pytest

playwright=pytest.importorskip('playwright.sync_api')
ROOT=Path(__file__).resolve().parents[1]/'SABLON_V2_MIMARI'


def as_png(array):
    ok,p=cv2.imencode('.png',array)
    assert ok
    return 'data:image/png;base64,'+base64.b64encode(p).decode('ascii')


def test_brush_visual_diameter_and_curve_only_clipping():
    white=as_png(np.full((160,200,3),220,np.uint8))
    black=as_png(np.zeros((160,200),np.uint8))
    src=(ROOT/'templates/index.html').read_text('utf-8')
    src=re.sub(r'<script\s+src=[^>]+></script>','',src)
    src=re.sub(r'<link\s+rel="stylesheet"[^>]+>','',src)
    with playwright.sync_playwright() as p:
        try:
            browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
        except Exception as exc:
            pytest.skip(str(exc))
        try:
            page=browser.new_page(viewport={'width':1440,'height':900})
            page.set_content(src,wait_until='domcontentloaded')
            page.add_style_tag(content=(ROOT/'static/css/petek_editor_v477.css').read_text('utf-8'))
            page.evaluate('''([white,black])=>{
              window.confirm=()=>true;
              window.alert=()=>{};
              const OrigImage=window.Image;
              window.Image=class extends OrigImage{
                set src(url){super.src=String(url).startsWith('/api/petek/photo/')?white:url;}
              };
              window.fetch=async(url,opt={})=>{
                let data={success:true};
                if(url==='/api/petek/templates')data={success:true,
                  items:[{name:'PETEK_test.png',uid:'T001',status:'DRAFT',approved:false,mask_verified:true,source_sha:'a'.repeat(64),backup_status:'MATCH',working_ok:true}],
                  scanned_photos:1,matched_approved_records:0,registry_approved_total:0,unmatched_approved_records:0};
                else if(url.startsWith('/api/petek/detail/'))data={success:true,
                  name:'PETEK_test.png',uid:'T001',status:'DRAFT',approved:false,source_sha:'a'.repeat(64),
                  width:200,height:160,mask:black,base_mask:null,
                  quad:[[10,10],[190,10],[190,150],[10,150]],
                  curve_points:{top:[[20,30],[100,60],[180,30]],bottom:[[20,125],[100,105],[180,125]]},physical_aspect:1.1};
                return {ok:true,json:async()=>data};
              };
            }''',[white,black])
            page.add_style_tag(content=(ROOT/'static/css/petek_editor_v477.css').read_text('utf-8'))
            page.add_script_tag(content=(ROOT/'static/js/petek_quad_drag_v481.js').read_text('utf-8'))
            page.add_script_tag(content=(ROOT/'static/js/petek_editor_v477.js').read_text('utf-8'))
            page.locator('#petekV477Nav').click()
            page.wait_for_function("document.getElementById('petekV477Name').textContent.includes('T001')")
            page.locator('[data-petek-mode="wood"]').click()
            canvas=page.locator('#petekV477Canvas')
            def at(x,y):
                rect=canvas.bounding_box()
                return rect['x']+x*rect['width']/200,rect['y']+y*rect['height']/160
            x,y=at(100,80)
            page.mouse.move(x,y)
            page.wait_for_function("!document.getElementById('petekV477BrushCursor').hidden")
            diag=page.evaluate("""()=>({
              w:document.getElementById('petekV477BrushCursor').getBoundingClientRect().width,
              canvas:document.getElementById('petekV477Canvas').getBoundingClientRect().width,
              label:document.getElementById('petekV477BrushSize').textContent
            })""")
            assert diag['label']=='24 px'
            assert abs(diag['w'] - 24 * diag['canvas']/200) < 3
            page.locator('#petekV477Brush').fill('40')
            page.mouse.move(*at(100,80))
            diag2=page.evaluate("document.getElementById('petekV477BrushCursor').getBoundingClientRect().width")
            assert diag2>diag['w']*1.55
            # Make a 12px brush for precise curve tests, then inspect the
            # rasterized green tint without accessing the private JS state.
            page.locator('#petekV477Brush').fill('12')
            for xx,yy in [(100,42),(100,80),(100,118),(14,40)]:
                px,py=at(xx,yy)
                page.mouse.click(px,py)
            def rgb(xx,yy):
                return page.evaluate('''([x,y])=>{
                    const c=document.getElementById('petekV477Canvas');
                    const k=c.width/200;
                    return Array.from(c.getContext('2d').getImageData(Math.round(x*k),Math.round(y*k),1,1).data).slice(0,3);
                }''',[xx,yy])
            inside=rgb(100,80)
            excluded_top=rgb(100,42)
            excluded_bottom=rgb(100,118)
            outside_curve_segment=rgb(14,40)
            assert inside[0]<160, ('inside',inside)
            assert excluded_top[0]>195, ('top should remain unpainted',excluded_top)
            assert excluded_bottom[0]>195, ('bottom should remain unpainted',excluded_bottom)
            assert outside_curve_segment[0]<180, ('straight side must still paint',outside_curve_segment)
            page.mouse.move(*at(100,80))
            page.locator('#petekV477ZoomIn').click()
            canvas.scroll_into_view_if_needed()
            page.mouse.move(*at(100,80))
            assert page.locator('#petekV477BrushCursor').is_visible()
            page.mouse.move(1,1)
            assert not page.locator('#petekV477BrushCursor').is_visible()
        finally:
            browser.close()
