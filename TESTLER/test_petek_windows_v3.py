"""PETEK V3 local acceptance tests; synthetic assets only, no user runtime writes."""
from __future__ import annotations
import hashlib
import json
import sys
from pathlib import Path
import cv2
import numpy as np
import pytest
from PIL import Image

BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE/'MERKEZ'))
from PETEK_V3 import engine
from PETEK_V3.registry import Registry
from PETEK_V3.batch import Batch,HEADERS,_escape


def write_png(path,arr):
    path.parent.mkdir(parents=True,exist_ok=True)
    ok,buffer=cv2.imencode('.png',arr)
    assert ok
    path.write_bytes(buffer.tobytes())
    return path


@pytest.fixture
def scene_fixture(tmp_path):
    h,w=660,500
    scene=np.full((h,w,3),(96,143,161),dtype=np.uint8)
    quad=np.float32([[58,132],[440,122],[444,544],[61,582]])
    polygon=engine.polygon_mask(scene.shape,quad)
    scene[polygon>0]=(218,233,248)
    # Back-of-unit top black gap, naturally curved lower photo background.
    cv2.ellipse(scene,(249,152),(125,28),0,0,180,(21,22,26),-1)
    for x in range(120,420,29):
        cv2.rectangle(scene,(x,245),(x+6,475),(24,26,29),-1)
        cv2.line(scene,(x+1,247),(x+1,468),(54,58,64),1)
    cv2.ellipse(scene,(252,564),(170,27),0,180,360,(96,143,161),-1)
    original=write_png(tmp_path/'ORIGINAL_PETEK'/'PetekTest_001.png',scene)
    art=np.zeros((270,360,3),np.uint8)
    art[:]=(33,93,193)
    cv2.putText(art,'ABCD 123',(15,130),cv2.FONT_HERSHEY_SIMPLEX,1.6,(250,240,235),3,cv2.LINE_AA)
    designs=tmp_path/'GELEN_TASARIMLAR';designs.mkdir()
    artwork=write_png(designs/'art01.png',art)
    wood=np.where((polygon>0)&(np.all(scene==[218,233,248],axis=2)),255,0).astype(np.uint8)
    assert engine.mask_check(wood,scene,quad)
    return original,artwork,scene,quad,wood


@pytest.fixture
def approved(tmp_path,scene_fixture):
    source,art,scene,quad,mask=scene_fixture
    registry=Registry(tmp_path/'state')
    registry.save('PetekTest_001',source,quad,mask,1.1163)
    registry.approve('PetekTest_001','Test Operator','I_VISUALLY_CHECKED_VENTS_ARCHES_FLOOR')
    return registry


def test_quad_order(scene_fixture):
    src,art,scene,q,mask=scene_fixture
    np.testing.assert_array_equal(engine.validated_quad(q,scene.shape),q)
    with pytest.raises(engine.MaskError):engine.validated_quad(q[::-1],scene.shape)
    with pytest.raises(engine.MaskError):engine.validated_quad([[0,0],[2,0],[2,2],[0,2]],scene.shape)


def test_mask_does_not_leak(scene_fixture):
    _,_,scene,q,mask=scene_fixture
    modified=mask.copy();modified[1,1]=255
    with pytest.raises(engine.MaskError):engine.mask_check(modified,scene,q)


def test_original_vents_top_bottom_pixels_are_unchanged(scene_fixture):
    src,art,scene,q,mask=scene_fixture
    out,qa=engine.render(src,art,q,mask,marketplace=False)
    assert qa['source_pixels_unchanged']
    np.testing.assert_array_equal(out[mask==0],scene[mask==0])
    assert np.any(out[mask>0] != scene[mask>0])
    for y,x in ((275,122),(166,249),(560,249),(10,10)):
        assert mask[y,x]==0
        np.testing.assert_array_equal(out[y,x],scene[y,x])


def test_no_forced_slot_count(scene_fixture):
    _,art,scene,q,_=scene_fixture
    for count in (3,11,18):
        im=scene.copy();poly=engine.polygon_mask(scene.shape,q)
        im[poly>0]=(218,233,248)
        for x in np.linspace(95,425,count,dtype=int):
            cv2.rectangle(im,(int(x),235),(int(x+4),470),(18,22,25),-1)
        mask=np.where(np.all(im==[218,233,248],axis=2),255,0).astype(np.uint8)
        output,qa=engine.render(im,engine.read_bgr(art),q,mask,marketplace=False)
        assert qa['source_pixels_unchanged']
        assert np.array_equal(im[mask==0],output[mask==0])


def test_source_draft_requires_human_review(tmp_path,scene_fixture):
    source,art,scene,q,mask=scene_fixture
    registry=Registry(tmp_path/'state')
    registry.save('PetekTest_001',source,q,mask,1.1163)
    with pytest.raises(engine.MaskError):registry.get('PetekTest_001',require_approved=True)
    with pytest.raises(engine.MaskError):registry.approve('PetekTest_001','Tester','AUTO')
    with pytest.raises(engine.MaskError):registry.approve('PetekTest_001','','I_VISUALLY_CHECKED_VENTS_ARCHES_FLOOR')


def test_approved_immutable(tmp_path,scene_fixture,approved):
    source,art,scene,q,mask=scene_fixture
    profile,loaded=approved.get('PetekTest_001',require_approved=True)
    assert profile['status']=='APPROVED'
    np.testing.assert_array_equal(loaded,mask)
    with pytest.raises(engine.MaskError):approved.save('PetekTest_001',source,q,mask,1.1163)


def test_stale_source_blocked(scene_fixture,approved):
    src,art,scene,q,mask=scene_fixture
    scene=scene.copy();scene[250,190]=[10,20,30];write_png(src,scene)
    with pytest.raises(engine.MaskError):approved.get('PetekTest_001',require_approved=True)


def test_marketplace_output_shape(scene_fixture):
    src,art,scene,q,mask=scene_fixture
    result,_=engine.render(src,art,q,mask,marketplace=True)
    assert result.shape==(1600,1200,3)
    assert np.array_equal(result[0,0],(245,245,245))


def test_auto_is_always_candidate(scene_fixture):
    source,art,scene,q,mask=scene_fixture
    candidate,details=engine.auto_mask_candidate(scene,q)
    assert details['status']=='TASLAK'
    assert candidate.shape==mask.shape
    assert np.count_nonzero(candidate)>0


def test_no_overwrite(scene_fixture,tmp_path):
    p=tmp_path/'same.png'
    engine.atomic_new_file(p,b'abc')
    with pytest.raises(engine.MaskError):engine.atomic_new_file(p,b'new')
    assert p.read_bytes()==b'abc'


def test_batch_produces_excel_and_csv(scene_fixture,approved):
    source,art,scene,q,mask=scene_fixture
    batch=Batch(approved)
    res=batch.run(art.parent,['PetekTest_001'],group='SHOP_A',max_jobs=10)
    assert res['status']=='LOCAL_READY' and res['rendered']==1
    assert res['reused']==0 and res['total_registry_outputs']==1
    assert Path(res['csv']).is_file() and Path(res['xlsx']).is_file()
    assert not res['marketplace_published']
    with Path(res['csv']).open(encoding='utf-8-sig',newline='') as fh:
        import csv
        data=list(csv.reader(fh))
        assert data[0]==HEADERS and len(data)==2
    second=batch.run(art.parent,['PetekTest_001'],group='SHOP_A',max_jobs=10)
    assert second['rendered']==0 and second['reused']==1
    assert second['csv']==res['csv']


def test_tampered_output_never_overwritten(scene_fixture,approved):
    source,art,scene,q,mask=scene_fixture
    job=Batch(approved)
    first=job.run(art.parent,['PetekTest_001'],group='SHOP_B')
    with job.ledger.connect() as conn:
        stored=dict(conn.execute('SELECT * FROM artifact LIMIT 1').fetchone())
    out=Path(stored['output'])
    with out.open('ab') as f:f.write(b'extra')
    with pytest.raises(engine.MaskError):job.run(art.parent,['PetekTest_001'],group='SHOP_B')
    assert out.read_bytes().endswith(b'extra')


def test_export_formula_injection():
    assert _escape('=HYPERLINK("evil")').startswith("'")
    assert _escape('+cmd').startswith("'")
    assert _escape('normal')=='normal'


def test_output_root_no_designs_nested(approved,scene_fixture):
    with pytest.raises(engine.MaskError):Batch(approved).run(approved.root,['PetekTest_001'])


def test_daily_v2_source_not_modified():
    import zipfile
    original=Path('/mnt/data/GORSEL_MOCKUP_MERKEZ_V2(1).zip')
    if not original.exists():pytest.skip('Upstream source ZIP not available')
    prefix='GORSEL_MOCKUP_MERKEZ_V2/GORSEL_MOCKUP_MERKEZ_V2/MERKEZ/GUNLUK/'
    with zipfile.ZipFile(original) as z:
        for name in z.namelist():
            if name.startswith(prefix) and not name.endswith('/'):
                relative=name[len(prefix):]
                copy=BASE/'MERKEZ'/'GUNLUK'/relative
                assert copy.read_bytes()==z.read(name),f'Daily V2 regression: {relative}'


def test_center_is_free_of_procedural_thirteen_slots():
    center=(BASE/'MERKEZ'/'merkez.py').read_text(encoding='utf-8')
    assert 'PETEK_V3.gui' in center
    assert 'petek_entry' not in center
    assert 'PETEK_V3' in center
    assert not (BASE/'MERKEZ'/'petek_entry.py').exists()
