"""Grup 2 optik bitiriş, Excel hyperlinks, source protection, and UI safety."""
from pathlib import Path
import hashlib
import sys
import cv2
import numpy as np
import pytest
from openpyxl import load_workbook

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'MERKEZ'))
from URETIM_V4.finish_v42 import projected_rounded_alpha, subdued_reflection
from URETIM_V4.unified_batch import _render_legacy_six_cover, UnifiedV4Batch
from PETEK_V3.batch import Batch


def make_sample(tmp_path):
    scene = np.full((340, 280, 3), (135, 142, 158), dtype=np.uint8)
    art = np.full((260, 200, 3), (10, 50, 175), dtype=np.uint8)
    cv2.putText(art, 'TEST', (40, 110), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (245, 245, 245), 3)
    scene_file=tmp_path/'source.png'; art_file=tmp_path/'art.png'
    cv2.imwrite(str(scene_file), scene); cv2.imwrite(str(art_file), art)
    quad=[[52,42],[234,52],[224,279],[48,280]]
    mask=np.zeros(scene.shape[:2], dtype=np.uint8)
    cv2.fillConvexPoly(mask,np.asarray(quad,dtype=np.int32),255)
    return scene,art,quad,mask,scene_file,art_file


@pytest.mark.parametrize('category', ['02_Cam_Tablo_Dikey','02_Cam_Tablo_Yatay','04_Cam_Dograma','05_Ocak_Arkasi','01_Wifi_Kutusu','03_Ahsap_Tablo'])
def test_render_with_category_finish_preserves_background(category,tmp_path):
    scene,art,quad,mask,source,design=make_sample(tmp_path)
    output,qa=_render_legacy_six_cover(source,design,quad,mask, .71,
                    category=category,corner_radius=.008, marketplace=False)
    assert np.array_equal(output[mask==0],scene[mask==0])
    assert np.mean(np.abs(output[mask>0].astype(float)-scene[mask>0]))>8
    assert qa['source_pixels_unchanged'] is True
    assert qa['corner_radius']==(.008 if category in {'02_Cam_Tablo_Dikey','02_Cam_Tablo_Yatay','04_Cam_Dograma','05_Ocak_Arkasi'} else 0.0)


def test_glass_off_does_not_add_fake_glare(tmp_path):
    scene,art,quad,mask,source,design=make_sample(tmp_path)
    printed=np.full_like(scene,90)
    out=subdued_reflection(scene,printed,mask,quad,'05_Ocak_Arkasi','off')
    assert np.array_equal(out,printed)


def test_rounded_alpha_does_not_edit_corners_and_is_disableable(tmp_path):
    scene,_,quad,mask,_,_=make_sample(tmp_path)
    saved=[point[:] for point in quad]
    flat=projected_rounded_alpha(scene.shape,quad,0)
    slight=projected_rounded_alpha(scene.shape,quad,.015)
    assert np.all(flat==1)
    assert np.all((slight>=0)&(slight<=1))
    assert slight[0,0]==0
    assert slight[145,140]>.99
    assert quad==saved
    with pytest.raises(ValueError): projected_rounded_alpha(scene.shape,quad,.15)


def fake_render_row(tmp_path, petek):
    p=tmp_path/'ÜRÜN_501.png';p.write_bytes(b'generated_png_test')
    sha=hashlib.sha256(p.read_bytes()).hexdigest()
    return dict(key='x',sku='PDK-LOCAL-001',category='06_Petek_Kapama',art_name='baski.png',uid='Petek_02',output=str(p),output_sha=sha)


@pytest.mark.parametrize('engine_name', ['petek','unified'])
def test_xlsx_file_hyperlink_is_clickable_and_csv_independent(engine_name,tmp_path):
    row=fake_render_row(tmp_path,engine_name=='petek')
    class FakeLedger:
        def successful(self): return [row]
    class FakeRegistry:
        reports=tmp_path/'PETEK_RAPOR';
    if engine_name=='petek':
        batch=Batch.__new__(Batch)
        batch.ledger=FakeLedger(); batch.registry=FakeRegistry()
        batch.registry.reports.mkdir()
        csvpath,xlsxpath,n=batch.export()
    else:
        batch=UnifiedV4Batch.__new__(UnifiedV4Batch)
        batch.ledger=FakeLedger(); batch.reports=tmp_path/'ORTAK_RAPOR'
        batch.reports.mkdir()
        csvpath,xlsxpath,n=batch.export()
    assert n==1 and csvpath.is_file()
    assert xlsxpath.name.endswith('_LINKLI.xlsx')
    wb=load_workbook(xlsxpath)
    c=wb.active['I2']
    assert c.value==str(Path(row['output']))
    assert c.hyperlink.target == Path(row['output']).resolve().as_uri()
    assert c.hyperlink.target.startswith('file:///')
    wb.close()
    # Exact export replay never silently overwrites existing Excel.
    before=xlsxpath.read_bytes()
    if engine_name=='petek': batch.export()
    else: batch.export()
    assert xlsxpath.read_bytes()==before


def test_js_preserves_approved_v_and_uses_H_for_new_templates():
    js=(ROOT/'SABLON_V2_MIMARI/static/js/main.js').read_text()
    assert "(value === 'H' || value === 'V') ? value : ((mixed && !approved) ? 'H' : '')" in js
    assert 'requestToken !== templateLoadToken' in js
    assert 'approvedCat === currentCat && approvedName === currentTmpl' in js


def test_guaranteed_no_embedded_live_db():
    assert not list(ROOT.rglob('ayarlar.db'))
    assert not list(ROOT.rglob('*.sqlite3'))
