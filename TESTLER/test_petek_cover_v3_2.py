"""PETEK V3.2: synthetic FIT-COVER regression and identity/approval preservation."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys

import cv2
import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'MERKEZ'))
from PETEK_V3 import engine
from PETEK_V3.registry import Registry
from PETEK_V3.batch import Batch


def write_image(path,arr):
    path.parent.mkdir(parents=True,exist_ok=True)
    assert cv2.imwrite(str(path),arr)
    return path


@pytest.fixture
def sample(tmp_path):
    scene=np.full((750,950,3),(112,135,160),dtype=np.uint8)
    quad=np.float32([[110,160],[820,143],[832,656],[103,686]])
    mask=engine.polygon_mask(scene.shape,quad)
    scene[mask>0]=(242,243,244)
    # Actual unpaintable shapes are preserved via the approved mask.
    cv2.ellipse(scene,(475,181),(240,37),0,0,180,(21,23,24),-1)
    for x in range(190,770,39):
        cv2.rectangle(scene,(x,295),(x+8,580),(32,35,38),-1)
    cv2.ellipse(scene,(475,663),(275,40),0,180,360,(112,135,160),-1)
    mask=np.where(np.all(scene==(242,243,244),axis=2),255,0).astype(np.uint8)
    engine.mask_check(mask,scene,quad)
    art_dir=tmp_path/'GELEN';art_dir.mkdir()
    scene_path=write_image(tmp_path/'TEMPLATES'/'rad.png',scene)
    portrait=np.zeros((480,190,3),np.uint8);portrait[:]=(25,50,220)
    portrait[:, :40]=(180,10,10)
    portrait[:, 150:]=(10,180,10)
    landscape=np.zeros((150,800,3),np.uint8);landscape[:]=(10,170,230)
    landscape[:,:100]=(140,15,10)
    landscape[:,-100:]=(15,140,10)
    portrait_path=write_image(art_dir/'portrait.png',portrait)
    landscape_path=write_image(art_dir/'landscape.png',landscape)
    return scene_path,portrait_path,landscape_path,scene,quad,mask


@pytest.mark.parametrize('kind',[1,2])
def test_cover_fills_entire_mask_without_synthetic_white_bands(sample,kind):
    src,p,l,scene,quad,mask=sample
    art=[p,l][kind-1]
    final,receipt=engine.render(src,art,quad,mask,1.2,marketplace=False,
                                shading=False,placement='cover')
    assert receipt['artwork_placement']=='cover'
    assert receipt['source_pixels_unchanged'] is True
    np.testing.assert_array_equal(final[mask==0],scene[mask==0])
    # A white wood panel must not show up as white outside a design with no white.
    allowed=final[mask>0]
    white=np.all(allowed>230,axis=1)
    assert np.count_nonzero(white)/len(allowed)<.002
    # All perimeter wood strips are printed, not reserved for letterbox padding.
    for x,y in [(120,350),(805,350),(430,235),(430,624)]:
        if mask[y,x]>0: assert not np.all(final[y,x]>230)


def test_opt_in_contain_still_possible(sample):
    src,p,l,scene,quad,mask=sample
    cover,_=engine.render(src,p,quad,mask,1.2,marketplace=False,
                          shading=False,placement='cover')
    contain,_=engine.render(src,p,quad,mask,1.2,marketplace=False,
                            shading=False,placement='contain')
    assert np.count_nonzero(np.all(contain[mask>0]>230,axis=1))>100
    assert np.count_nonzero(np.all(cover[mask>0]>230,axis=1))<100
    np.testing.assert_array_equal(contain[mask==0],scene[mask==0])


def test_invalid_mode_rejected(sample):
    src,p,l,scene,quad,mask=sample
    with pytest.raises(engine.MaskError):
        engine.render(src,p,quad,mask,1.2,placement='fit-stretch')


def test_legacy_approved_mask_keeps_status_but_new_recipe_uses_new_identity(tmp_path,sample):
    src,p,l,scene,quad,mask=sample
    reg=Registry(tmp_path/'STATE')
    reg.save('rad_test',src,quad,mask,1.2)
    reg.approve('rad_test','QA reviewer','I_VISUALLY_CHECKED_VENTS_ARCHES_FLOOR')
    path=reg.profiles/'rad_test.json'
    profile=json.loads(path.read_text('utf-8'))
    profile['recipe']='petek-v3-original-pixel-mask-shadows-v2'
    path.write_text(json.dumps(profile),encoding='utf-8')
    # This is an already-reviewed source mask; no unauthorized reapproval needed.
    old,_=reg.get('rad_test',require_approved=True)
    assert old['status']=='APPROVED'
    batch=Batch(reg)
    first=batch.run(p.parent,['rad_test'],max_jobs=1,placement='cover')
    assert first['rendered']==1
    second=batch.run(p.parent,['rad_test'],max_jobs=1,placement='cover')
    assert second['reused']==1
    third=batch.run(p.parent,['rad_test'],max_jobs=1,placement='contain')
    assert third['rendered']==1
    with batch.ledger.connect() as db:
        rows=db.execute('SELECT key,output FROM artifact ORDER BY key').fetchall()
    assert len(rows)==2 and rows[0]['key']!=rows[1]['key']
    assert all(Path(record['output']).is_file() for record in rows)
    assert json.loads(path.read_text('utf-8'))['recipe']==profile['recipe']


def test_no_synthetic_slot_numbers_or_changed_source(sample):
    src,p,l,scene,quad,mask=sample
    before=engine.digest(src)
    output,_=engine.render(src,p,quad,mask,1.2,marketplace=True,placement='cover')
    assert output.shape==(1600,1200,3)
    assert engine.digest(src)==before
    assert engine.RECIPE.endswith('cover')


def test_no_content_geometry_stretch_in_cover(sample):
    src,p,l,scene,quad,mask=sample
    # Direct projected samples: cropped artwork only, native-aspect and
    # uninterrupted x-gradient rather than a resized letterbox.
    art=np.zeros((200,800,3),np.uint8)
    for x in range(800): art[:,x]=(min(255,x//4),18,52)
    mapped=engine.warp_artwork(art,quad,scene.shape,physical_aspect=1.2,placement='cover')
    centre=int(quad[:,0].mean());cy=int(quad[:,1].mean())
    assert mapped[cy,centre,0] in range(88,115)
    assert np.isfinite(mapped).all()
