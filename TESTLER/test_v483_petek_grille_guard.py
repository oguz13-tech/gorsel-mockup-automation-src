"""Synthetic PETEK vent/grille regression: no pink at printed lips.

Photos, approved masks, SQLite and production ledgers are never written.
"""
from __future__ import annotations
import base64
from pathlib import Path
import sys
import cv2
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'MERKEZ'))
from MERKEZ.PETEK_V3 import engine
from MERKEZ.PETEK_V3.cutout_paste import render_with_cutout_paste
from MERKEZ.PETEK_V3.grille_guard_v482 import (
    magenta_reference,refine_magenta_draft_mask,recommended_edge_feather,
    magenta_residue_report)
from TESTLER.test_v477_petek_browser_integration import fixture,params,valid_mask


def scene_and_quad():
    scene=np.full((320,500,3),205,dtype=np.uint8)
    quad=[[70,65],[430,65],[430,275],[70,275]]
    cv2.rectangle(scene,(70,65),(430,275),(255,0,255),-1)
    # Magenta colored 1px lip is printable; dark vertical hole is not.
    for x in range(112,414,28):
        cv2.rectangle(scene,(x,95),(x+9,248),(15,13,12),-1)
    cv2.rectangle(scene,(150,65),(350,76),(8,8,8),-1) # top recess
    cv2.rectangle(scene,(150,265),(350,275),(8,8,8),-1) # bottom recess
    return scene,quad


def test_auto_magenta_mask_preserves_all_dark_grille_openings_and_side_faces():
    scene,quad=scene_and_quad()
    assert magenta_reference(scene,quad)
    mask,qa=engine.auto_mask_candidate(scene,quad)
    assert qa['mode']=='MAGENTA_BASKI_YUZEYI'
    assert qa['enabled'] is True
    for x in range(112,414,28):
        assert mask[160,x+4]==0,('Vent must remain black',x)
        assert mask[160,x-1]==255,('Print up to the left lip',x)
        assert mask[160,x+10]==255,('Print up to the right lip',x)
    assert mask[170,35]==0 and mask[170,470]==0
    assert mask[70,220]==0 and mask[270,220]==0
    assert recommended_edge_feather(scene,quad)==0.0


def test_draft_repair_touches_only_magenta_original_lip_not_dark_vent():
    scene,quad=scene_and_quad()
    mask,qa=engine.auto_mask_candidate(scene,quad)
    mask[160,111]=0
    mask[160,116]=0 # black slit
    repaired,more=refine_magenta_draft_mask(scene,quad,mask)
    assert more['added_magenta_edge_pixels']>=1
    assert repaired[160,111]==255
    assert repaired[160,116]==0
    assert np.array_equal(repaired[30,30:60],mask[30,30:60])
    assert mask[160,111]==0, 'Input draft must remain untouched'


def test_zero_grille_feather_avoids_pink_halo_but_old_feather_causes_it():
    scene,quad=scene_and_quad()
    mask,_=engine.auto_mask_candidate(scene,quad)
    art=np.full((180,260,3),(235,32,27),np.uint8)
    hard,_,_ =render_with_cutout_paste(scene,art,quad,mask,lighting='off',
              marketplace=False,edge_feather_px=recommended_edge_feather(scene,quad))
    soft,_,_ =render_with_cutout_paste(scene,art,quad,mask,lighting='off',
              marketplace=False,edge_feather_px=1.4)
    # At the 1-pixel wood lip, original magenta can bleed from feathering.
    assert mask[160,111]==255 and scene[160,111,2]==255
    assert int(hard[160,111,2]) < int(soft[160,111,2]), 'Pink channel must no longer bleed'
    assert np.array_equal(hard[mask==0],scene[mask==0]),'Exact protected pixels'
    assert np.array_equal(hard[160,116],scene[160,116]),'Real black vent'


def test_legacy_white_petek_gets_unchanged_feather_and_no_auto_repair():
    scene,quad=scene_and_quad()
    scene[scene[:,:,0]==255]=230
    assert not magenta_reference(scene,quad)
    mask=np.zeros(scene.shape[:2],dtype=np.uint8)
    mask[80:250,80:420]=255
    assert recommended_edge_feather(scene,quad)==1.4
    candidate,qa=refine_magenta_draft_mask(scene,quad,mask)
    assert not qa['enabled']
    assert np.array_equal(candidate,mask)


def test_preview_and_actual_petek_batch_renderer_use_same_grille_edge(tmp_path,monkeypatch):
    client,photo,registry,_=fixture(tmp_path,monkeypatch)
    scene=engine.read_bgr(photo)
    scene[25:276,25:376]=(255,0,255)
    for x in range(60,351,24):
        scene[52:252,x:x+8]=(12,12,12)
    assert cv2.imwrite(str(photo),scene)
    assert recommended_edge_feather(scene,params(photo)['quad'])==0
    art=np.full((160,230,3),(235,24,19),dtype=np.uint8)
    png=cv2.imencode('.png',art)[1].tobytes()
    payload={**params(photo),'uid':photo.stem,
             'artwork_png':'data:image/png;base64,'+base64.b64encode(png).decode('ascii')}
    untouched=photo.read_bytes()
    res=client.post('/api/petek/preview-artwork',json=payload)
    assert res.status_code==200,res.get_json()
    data=res.get_json()
    assert data['mask_qa']['edge_feather_px']==0.0
    rendered=cv2.imdecode(np.frombuffer(base64.b64decode(data['preview'].partition(',')[2]),
                          dtype=np.uint8),cv2.IMREAD_COLOR)
    direct,_,_=render_with_cutout_paste(scene,art,payload['quad'],valid_mask(),
                physical_aspect=1.1163,lighting='natural',placement='cover',
                edge_feather_px=0.0,marketplace=False)
    assert np.array_equal(rendered,direct),'Preview must match batch engine source-resolution'
    assert np.array_equal(rendered[valid_mask()==0],scene[valid_mask()==0])
    assert photo.read_bytes()==untouched
    assert not list(registry.profiles.glob('*.json'))


def test_physical_aspect_preserved_but_no_editable_user_control():
    html=(ROOT/'SABLON_V2_MIMARI/templates/index.html').read_text('utf-8')
    js=(ROOT/'SABLON_V2_MIMARI/static/js/petek_editor_v477.js').read_text('utf-8')
    assert 'id="petekV477Aspect" type="hidden"' in html
    assert "physical_aspect:Number($('petekV477Aspect').value)" in js
    assert "magenta_grille" not in html  # No experimental public toggle.
