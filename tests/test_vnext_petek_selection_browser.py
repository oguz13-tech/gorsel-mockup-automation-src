"""Browser UI selection stays on same PETEK after save/approve under filters."""
import re
from pathlib import Path
import pytest

playwright=pytest.importorskip('playwright.sync_api')
ROOT=Path(__file__).resolve().parents[1]/'SABLON_V2_MIMARI'

# 1x1 opaque gray PNG, used for image and mask. No real user files.
PNG='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9WK+Q3kAAAAASUVORK5CYII='


def test_selection_stays_with_current_uid_during_draft_and_approval():
    source=(ROOT/'templates/index.html').read_text('utf8')
    source=re.sub(r'<script\s+src=[^>]+></script>','',source)
    source=re.sub(r'<link\s+rel="stylesheet"[^>]+>','',source)
    with playwright.sync_playwright() as p:
        try:browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
        except Exception as exc:pytest.skip(str(exc))
        try:
            page=browser.new_page(viewport={'width':1366,'height':768})
            page.set_content(source,wait_until='domcontentloaded')
            page.evaluate('''(png)=>{
              window.confirm=()=>true;
              window.alert=()=>{};
              const OrigImage=window.Image;
              window.Image=class extends OrigImage{
                set src(_url){super.src=png;}
              };
              window.calls=[];
              window.records=[
                {name:'Petek_A.png',uid:'uid_A',status:'APPROVED',approved:true,mask_verified:true,source_sha:'a'.repeat(64),backup_status:'MATCH',working_ok:true},
                {name:'Petek_B.png',uid:'uid_B',status:'NEW',approved:false,mask_verified:false,source_sha:'b'.repeat(64),backup_status:'MATCH',working_ok:true},
                {name:'Petek_C.png',uid:'uid_C',status:'NEW',approved:false,mask_verified:false,source_sha:'c'.repeat(64),backup_status:'MATCH',working_ok:true}
              ];
              window.fetch=async(url,opt={})=>{
                window.calls.push([url,opt.method||'GET']);
                let data={success:true};
                if(url==='/api/petek/templates')data={success:true,items:window.records,scanned_photos:3,matched_approved_records:1,registry_approved_total:1,unmatched_approved_records:0};
                else if(url.startsWith('/api/petek/detail/')){
                  const name=decodeURIComponent(url.split('/detail/')[1].split('?')[0]);
                  const item=window.records.find(x=>x.name===name);
                  data={success:true,...item,quad:[[0,0],[0.9,0],[0.9,0.9],[0,0.9]],width:1,height:1,mask:png,base_mask:null,curve_points:{top:[],bottom:[]},physical_aspect:1.1,is_current:true};
                }else if(url==='/api/petek/save-draft'){
                  const body=JSON.parse(opt.body);data={success:true,uid:body.uid,status:'DRAFT',mask_sha:'d'.repeat(64)};
                }else if(url==='/api/petek/approve')data={success:true,uid:'uid_B',mask_sha:'d'.repeat(64)};
                return {ok:true,json:async()=>data};
              };
            }''',PNG)
            page.add_script_tag(content=(ROOT/'static/js/petek_quad_drag_v481.js').read_text('utf8'))
            page.add_script_tag(content=(ROOT/'static/js/petek_editor_v477.js').read_text('utf8'))
            page.locator('#petekV477Nav').click()
            page.wait_for_function("document.getElementById('petekV477Select').options.length===3")
            page.locator('.petek-v477-list-item').filter(has_text='Petek_B').click()
            page.wait_for_function("document.getElementById('petekV477Name').textContent.includes('uid_B')")
            # Select has a reviewed quad; draft save should not re-fetch the template pool.
            before=page.evaluate("window.calls.filter(x=>x[0]==='/api/petek/templates').length")
            page.locator('#petekV477Save').click()
            page.wait_for_function("document.getElementById('petekV477Name').textContent.includes('DRAFT')")
            after=page.evaluate("window.calls.filter(x=>x[0]==='/api/petek/templates').length")
            assert before==after
            assert 'uid_B' in page.locator('#petekV477Name').inner_text()
            assert 'uid_B' in page.locator('#petekV477Select').input_value()
            page.locator('#petekV477Approve').click()
            page.wait_for_function("document.getElementById('petekV477Name').textContent.includes('APPROVED')")
            assert 'uid_B' in page.locator('#petekV477Name').inner_text()
            assert page.evaluate("window.calls.filter(x=>x[0]==='/api/petek/templates').length")==before
            # Status-filter now hides current APPROVED record: next arrow may not jump to first.
            page.evaluate("window.V499StatusFilters={allowed:status=>status!=='APPROVED'}; document.dispatchEvent(new Event('v499:status-filter'));")
            page.locator('#petekV477Next').click()
            assert 'uid_B' in page.locator('#petekV477Name').inner_text()
        finally:browser.close()
