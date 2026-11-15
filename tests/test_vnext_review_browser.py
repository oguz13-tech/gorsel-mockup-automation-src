"""Offline Chromium DOM regression for the VNext review appearance editor.

Never runs an image engine, writes user data, or uses a production Flask port.
"""
from pathlib import Path
import json
import re
import pytest

playwright = pytest.importorskip('playwright.sync_api')
ROOT = Path(__file__).resolve().parents[1] / 'SABLON_V2_MIMARI'


def html():
    source=(ROOT/'templates/index.html').read_text(encoding='utf-8')
    source=re.sub(r'<script\s+src=[^>]+></script>','',source)
    source=re.sub(r'<link\s+rel="stylesheet"[^>]+>','',source)
    return source


def test_review_edit_blocks_engine_and_manages_tabs():
    with playwright.sync_playwright() as tool:
        try:
            browser=tool.chromium.launch(headless=True, executable_path='/usr/bin/chromium',
                                         args=['--no-sandbox'])
        except Exception as exc:
            pytest.skip(f'Chromium unavailable: {exc}')
        try:
            page=browser.new_page(viewport={'width':1366,'height':768})
            errors=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.set_content(html(),wait_until='domcontentloaded')
            for css in ['style.css','petek_editor_v477.css','mor_premium_vnext.css']:
                page.add_style_tag(content=(ROOT/'static/css'/css).read_text(encoding='utf-8'))
            # Endpoint is mocked: source/quad/mask APIs must never be contacted.
            model={
                'schema':1,'widths':{'left':290,'right':330},'paneOrder':'photo-first',
                'density':'normal','effect':'subtle',
                'colors':{'accent':'#7A4DFA','background':'#111827','panel':'#1D2638',
                          'border':'#384466','text':'#F4F6FF'},
                'tabs':{'review':['Tümü'],'petek':['Tümü']},
                'assignments':{'review':{},'petek':{}},
                'order':{'review':['review-quick','review-alignment','review-corners',
                                   'review-source','review-reports','review-approve'],
                         'petek':['petek-preview','petek-general','petek-corners',
                                  'petek-mask','petek-curves','petek-approval']}}
            page.evaluate("""(value) => {
              window.uiSaveCount = 0; window.savedUI = value;
              window.fetch = async (url, opts={}) => {
                if (url !== '/api/ui-layout/review') throw Error('ENGINE_API_CALLED');
                if (opts.method==='POST') {window.uiSaveCount++;
                   window.savedUI=JSON.parse(opts.body);}
                return {ok:true,json:async()=>({success:true,layout:window.savedUI})};
              };
            }""",model)
            page.add_script_tag(content=(ROOT/'static/js/review_layout_vnext.js').read_text(encoding='utf-8'))
            assert page.locator('[data-review-card]').count()==12
            page.locator('#uiLayoutLaunch').click()
            assert page.locator('body.ui-layout-editing').count()==1
            page.locator('.ui-layout-field input[type=range]').first.fill('350')
            assert round(page.evaluate("document.getElementById('sidebar').getBoundingClientRect().width"))==350
            # Original engine controls cannot run while this UI-only editor is active.
            page.evaluate('''() => {window.engineClickCount=0;
              document.getElementById('btnCorner').addEventListener('click',()=>window.engineClickCount++);
              document.getElementById('btnCorner').click();}''')
            assert page.evaluate('window.engineClickCount')==0
            page.once('dialog',lambda prompt: prompt.accept('Özel Maske'))
            page.get_by_role('button',name='Sekme Ekle').click()
            card=page.locator('[data-review-card="review-corners"]')
            card.locator('select.ui-card-tab-select').select_option('Özel Maske')
            page.get_by_role('button',name='Kaydet',exact=True).click()
            assert page.evaluate('window.uiSaveCount')==1
            assert page.locator('body.ui-layout-editing').count()==0
            page.locator('[data-review-tabs="review"] button',has_text='Tümü').click()
            assert card.is_hidden()
            page.locator('[data-review-tabs="review"] button',has_text='Özel Maske').click()
            assert card.is_visible()
            assert page.locator('[data-review-card="review-approve"]').is_visible()
            assert errors==[]
        finally:
            browser.close()
