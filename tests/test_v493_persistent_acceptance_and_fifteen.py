"""V4.9.3 functional regression; isolated temp paths, never user originals."""
import base64
import os
import sys
from pathlib import Path
import cv2
import numpy as np
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'MERKEZ')]
from MERKEZ.personal_hub_v493 import Store,ACCEPTANCE,TOOL_INDEX
from MERKEZ.PETEK_V3 import engine
from MERKEZ.PETEK_V3.petek_finish_v492 import draw_fifteen_slots


def test_acceptance_seeds_persist_and_approved_does_not_return(tmp_path):
    path=tmp_path/'data.sqlite'
    store=Store(path)
    assert len(store.tests())==len(ACCEPTANCE)
    store.update_test('PETEK-15-REAL','BEKLETILDI','Bunu sonraya al')
    assert any(x['id']=='PETEK-15-REAL' and x['notes']=='Bunu sonraya al' for x in Store(path).tests())
    store.update_test('PETEK-15-REAL','ONAYLANDI','Gerçek fotoğrafla doğruladım')
    assert not any(x['id']=='PETEK-15-REAL' for x in Store(path).tests())
    assert any(x['id']=='PETEK-15-REAL' and x['status']=='ONAYLANDI' for x in Store(path).tests(True))
    Store(path).seed()
    assert not any(x['id']=='PETEK-15-REAL' for x in Store(path).tests())


def test_acceptance_problem_remains_visible(tmp_path):
    db=Store(tmp_path/'s.sqlite')
    db.update_test('REAL-ESRGAN-4K','SORUN_VAR','Vulkan sürücüsü bekliyor')
    a=[x for x in Store(db.path).tests() if x['id']=='REAL-ESRGAN-4K'][0]
    assert a['status']=='SORUN_VAR' and 'Vulkan' in a['notes']


def test_personal_tasks_and_notes_survive_restart(tmp_path):
    db=Store(tmp_path/'s.sqlite')
    db.upsert_item('notes','Maske kenarı','Kontrol et')
    db.upsert_item('tasks','3K test','2 görsel üret')
    sid=Store(db.path).items('tasks')[0]['id']
    db.toggle_task(sid,True)
    reopened=Store(db.path)
    assert reopened.items('notes')[0]['title']=='Maske kenarı'
    assert reopened.items('tasks')[0]['done']==1
    assert reopened.items('notes')[0]['body']=='Kontrol et'


def test_all_indexed_buttons_have_real_existing_center_handler():
    from MERKEZ.merkez import Center
    missing=[fn for _,_,fn in TOOL_INDEX if not callable(getattr(Center,fn,None))]
    assert not missing,missing


def scene_mask_quad():
    scene=np.full((540,700,3),225,dtype=np.uint8)
    quad=np.array([[94,63],[621,80],[593,466],[73,445]],np.float32)
    mask=np.zeros(scene.shape[:2],dtype=np.uint8)
    cv2.fillConvexPoly(mask,np.int32(quad),255)
    # Physically protected existing holes plus upper & lower ventilations.
    for x in range(130,591,31):
        cv2.rectangle(mask,(x,175),(x+6,345),0,-1)
    cv2.rectangle(mask,(240,435),(450,465),0,-1)
    return scene,mask,quad


@pytest.mark.parametrize('mode',['hafif','orta','guclu'])
def test_15_slots_exactly_in_skewed_panel_no_protected_pixel_change(mode):
    scene,mask,quad=scene_mask_quad()
    saved=(scene.copy(),mask.copy(),quad.copy())
    result,qa=draw_fifteen_slots(scene,scene.copy(),mask,quad,mode=mode)
    assert qa['status']=='15_IZGARA_UYGULANDI' and qa['count']==15
    assert qa['changed_pixels']>500
    assert np.array_equal(result[mask==0],scene[mask==0])
    assert np.array_equal(mask,saved[1])
    assert np.array_equal(scene,saved[0])
    assert np.array_equal(quad,saved[2])


def test_fifteen_off_keeps_output_exact():
    a,m,q=scene_mask_quad()
    out,qa=draw_fifteen_slots(a,a,m,q,mode='off')
    assert np.array_equal(out,a) and qa['changed_pixels']==0


def test_invalid_whole_panel_mask_is_rejected():
    a,m,q=scene_mask_quad()
    cv2.fillConvexPoly(m,np.int32(q),255)
    with pytest.raises(engine.MaskError):draw_fifteen_slots(a,a,m,q)


def test_v493_web_ab_controls_appear_and_are_wired():
    html=(ROOT/'SABLON_V2_MIMARI/templates/index.html').read_text('utf8')
    js=(ROOT/'SABLON_V2_MIMARI/static/js/petek_editor_v477.js').read_text('utf8')
    for key in ('petekV493Strength','petekV493Pink','petekV493Preview','petekV493Before','petekV493After'):
        assert f'id="{key}"' in html
        assert key in js
    assert 'previewArtwork(true)' in js


def test_web_endpoint_read_only_15_slots(tmp_path,monkeypatch):
    from TESTLER.test_v477_petek_browser_integration import fixture,params,valid_mask
    client,photo,registry,_=fixture(tmp_path,monkeypatch)
    source_bytes=photo.read_bytes()
    artwork=np.full((180,280,3),[200,190,160],dtype=np.uint8)
    ok,data=cv2.imencode('.png',artwork); assert ok
    payload={**params(photo),'uid':photo.stem,
             'artwork_png':'data:image/png;base64,'+base64.b64encode(data).decode('ascii'),
             'fifteen_slot_ab':True,'fifteen_slot_strength':'orta',
             'pink_cleanup':False}
    response=client.post('/api/petek/preview-artwork',json=payload)
    assert response.status_code==200,response.get_json()
    obj=response.get_json()
    assert obj['read_only'] is True and obj['unsaved'] is True
    assert obj['slot_qa']['count']==15
    assert obj['after'].startswith('data:image/png;base64,')
    assert photo.read_bytes()==source_bytes
    assert not list(registry.profiles.glob('*.json'))


def test_real_slot_alignment_prevents_second_parallel_row():
    scene,mask,q=scene_mask_quad()
    _,qa=draw_fifteen_slots(scene,scene.copy(),mask,q,mode='orta')
    assert qa['count']==15
    assert qa['mask_evidence_count']==15
    assert qa['alignment']=='EXISTING_MASK_15'


def test_bright_pink_lower_left_is_cleaned_only_in_allowed_corridor():
    from MERKEZ.PETEK_V3.petek_finish_v492 import despill_lower_left_geometry_v493
    scene=np.full((500,700,3),[190,200,205],dtype=np.uint8)
    q=np.array([[100,65],[610,65],[610,445],[100,445]],dtype=np.float32)
    mask=np.zeros(scene.shape[:2],dtype=np.uint8)
    cv2.fillConvexPoly(mask,np.int32(q),255)
    for x in range(150,601,30):cv2.rectangle(mask,(x,170),(x+8,340),0,-1)
    cv2.line(scene,(103,448),(202,448),(255,0,255),3)
    before=scene.copy()
    fixed,qa=despill_lower_left_geometry_v493(scene,mask,q,enabled=True)
    assert qa['detected_pixels']>=100
    assert qa['remaining_pixels']==0
    assert np.array_equal(scene,before),'Original source not edited'
    assert np.array_equal(fixed[mask!=0],scene[mask!=0])
    assert np.count_nonzero(fixed!=scene)>0
