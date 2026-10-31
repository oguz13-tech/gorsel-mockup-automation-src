"""Non-destructive PETEK vent fail-closed and selected-UID review guard."""
from pathlib import Path
import sys
import pytest
import numpy as np
import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'MERKEZ')]
from MERKEZ.PETEK_V3 import engine
from MERKEZ.PETEK_V3.petek_finish_v492 import draw_fifteen_slots


def _scene(count=15):
    scene=np.full((540,700,3),225,np.uint8)
    q=np.array([[94,63],[621,80],[593,466],[73,445]],np.float32)
    mask=np.zeros(scene.shape[:2],np.uint8)
    cv2.fillConvexPoly(mask,q.astype(np.int32),255)
    xs=np.linspace(130,565,count).astype(int)
    for x in xs:cv2.rectangle(mask,(x,175),(x+6,345),0,-1)
    cv2.rectangle(mask,(240,435),(450,465),0,-1)
    return scene,mask,q


def test_exact_fifteen_real_holes_keep_trusted_output():
    scene,mask,q=_scene(15)
    snapshot=[v.copy() for v in (scene,mask,q)]
    rendered=np.copy(scene)
    out,qa=draw_fifteen_slots(scene,rendered,mask,q,mode='orta')
    assert qa['count']==15
    assert qa['alignment']=='EXISTING_MASK_15'
    assert qa['changed_pixels']>0
    assert np.array_equal(out[mask==0],rendered[mask==0])
    assert all(np.array_equal(a,b) for a,b in zip((scene,mask,q),snapshot))


@pytest.mark.parametrize('n',[5,10,18])
def test_uncorroborated_hole_count_is_not_fabricated(n):
    scene,mask,q=_scene(n)
    original=[v.copy() for v in (scene,mask,q)]
    with pytest.raises(engine.MaskError,match='PETEK_IZGARA_KONUMU_BELIRSIZ'):
        draw_fifteen_slots(scene,scene.copy(),mask,q,mode='orta')
    assert all(np.array_equal(a,b) for a,b in zip((scene,mask,q),original))


def test_petek_ui_saves_and_approves_current_selection_without_full_reload():
    js=(ROOT/'SABLON_V2_MIMARI/static/js/petek_editor_v477.js').read_text('utf8')
    save=js.split('async function save(){',1)[1].split('function applyApprovedInPlace(',1)[0]
    assert 'applyDraftInPlace(identity.name,identity.uid,data.mask_sha)' in save
    assert 'await reload()' not in save
    assert "if(idx<0){notice('Seçili PETEK bu filtrede gizli." in js
    assert 'const target=list[idx+delta]' in js
    assert 'const target=list[idx+delta] || (idx<0?list[0]:null)' not in js


@pytest.mark.parametrize('n',[13,14,15,16])
def test_real_mask_count_used_without_fabricating_to_fifteen(n):
    scene,mask,q=_scene(n)
    unchanged=(scene.copy(),mask.copy(),q.copy())
    output,qa=draw_fifteen_slots(scene,scene.copy(),mask,q,mode='orta')
    assert qa['count']==n
    assert qa['alignment']==f'EXISTING_MASK_{n}'
    assert qa['status']==f'{n}_IZGARA_UYGULANDI'
    assert len(qa['centers_rectified_900'])==n
    assert len(qa['spacings_rectified_900'])==n-1
    assert qa['changed_pixels']>0
    assert np.array_equal(output[mask==0],scene[mask==0])
    assert all(np.array_equal(x,y) for x,y in zip(unchanged,(scene,mask,q)))
