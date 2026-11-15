"""V4.8.5 user-locked store identities and NO-extra-Excel contract tests.

Entirely synthetic and offline, no network calls and no user file access.
"""
from pathlib import Path
import sqlite3
import sys
import pytest
from openpyxl import Workbook,load_workbook

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'MERKEZ'))
from URETIM_V4.store_identity_v485 import (store_codes,codes_from_sku,
                                            filename,design_number,
                                            trendyol_codes,petek_measurement_codes)
from URETIM_V4.store_profiles_v47 import StoreProfiles
from URETIM_V4.unified_batch import UnifiedV4Ledger
from URETIM_V4.cloud_excel_v43 import CloudExcel
from URETIM_V4.store_excel_v485 import export_store_upload
from PETEK_V3 import engine


def test_same_print_design_number_in_five_stores_with_different_mockups():
    sources=[]
    for index in range(1,6):
        store=f'M{index}'
        code=store_codes('18472',store,'01_Wifi_Kutusu')
        assert code['sku']==f'18472-WifiKutusu-{store}'
        assert code['barcode']==code['sku']
        assert code['model']==f'18472-{store}-WifiKutusu'
        assert codes_from_sku(code['sku'])==code
        mockup=filename('18472',store,'01_Wifi_Kutusu',f'Wifi_Kutusu_{35+index}')
        assert mockup==f'18472__{store}__WifiKutusu__TPL{35+index:03d}__V01.png'
        sources.append(mockup)
    assert len(set(sources))==5
    assert design_number('18472.png')=='18472'
    assert design_number('00018472.png')=='00018472'
    assert filename('18472','M5','01_Wifi_Kutusu','Wifi_35',extension='.jpg')==(
            '18472__M5__WifiKutusu__TPL035__V01.jpg')
    with pytest.raises(ValueError):design_number('18472 tasarım.png')
    with pytest.raises(ValueError):store_codes('18472','M5','UNSUPPORTED')


def _receipt(ledger,cloud,state,store,art,uid,number):
    category='01_Wifi_Kutusu'
    ident=store_codes(number,store,category)
    folder=state/'uretilen_gorseller'/store/category
    folder.mkdir(parents=True,exist_ok=True)
    path=folder/filename(number,store,category,uid)
    path.write_bytes(b'synthetic fixture '+store.encode()+uid.encode())
    fields={
        'key':store+'-'+uid+'-'+number,'sku':ident['sku'],'category':category,
        'art_sha':'a'*64,'template_sha':'b'*64,'mask_sha':'c'*64,
        'art_name':art,'uid':uid,'output':str(path),
    }
    ledger.reserve(fields)
    digest=engine.digest(path)
    ledger.complete(fields['key'],digest)
    with cloud.connect() as conn:
        conn.execute('INSERT INTO cloud_link(artifact_key,output_sha,url) VALUES(?,?,?)',
            (fields['key'],digest,'https://images.example.org/'+path.name))
    return fields


def _blank_template(path,multiple=True):
    wb=Workbook();sh=wb.active;sh.title='Ürün Yükleme'
    labels=['Stok Kodu','Barkod','Model Kodu','Kategori','Görsel 1']
    if multiple:labels.extend(['Görsel 2','Görsel 3'])
    sh.append(labels)
    wb.save(path)
    wb.close()


def test_selected_store_excel_not_extra_report_and_one_row_many_mockups(tmp_path):
    state=tmp_path/'GorselMockup';state.mkdir()
    ledger=UnifiedV4Ledger(state)
    cloud=CloudExcel(state,state/'raporlar')
    _receipt(ledger,cloud,state,'M5','18472.png','Wifi_Kutusu_035','18472')
    _receipt(ledger,cloud,state,'M5','18472.png','Wifi_Kutusu_036','18472')
    _receipt(ledger,cloud,state,'M4','18472.png','Wifi_Kutusu_044','18472')
    original=tmp_path/'blank.xlsx'
    _blank_template(original)
    original_bytes=original.read_bytes()
    # Cloud URLs for new store codes already exist: no second generic xlsx/csv.
    csv_path,xlsx_path,count=cloud.export(ledger.successful())
    assert csv_path is None and xlsx_path is None and count==3
    assert list((state/'raporlar').glob('*.xlsx'))==[]
    out5=export_store_upload(original,state,store_id='M5',report_root=state/'raporlar')
    out4=export_store_upload(original,state,store_id='M4',report_root=state/'raporlar')
    assert out5['rows']==1 and out5['images']==2
    assert out4['rows']==1 and out4['images']==1
    assert out5['output']!=out4['output']
    assert original.read_bytes()==original_bytes
    wb=load_workbook(out5['output'])
    sheet=wb.active
    assert sheet.cell(2,1).value=='18472-WifiKutusu-M5'
    assert sheet.cell(2,2).value=='18472-WifiKutusu-M5'
    assert sheet.cell(2,3).value=='18472-M5-WifiKutusu'
    assert sheet.cell(2,5).hyperlink.target.startswith('https://')
    assert sheet.cell(2,6).hyperlink.target.startswith('https://')
    assert sheet.max_row==2
    wb.close()
    wb=load_workbook(out4['output'])
    assert wb.active.cell(2,1).value=='18472-WifiKutusu-M4'
    assert wb.active.cell(2,6).value is None
    wb.close()


def test_store_excel_never_silently_drops_extra_images(tmp_path):
    state=tmp_path/'state';state.mkdir()
    ledger=UnifiedV4Ledger(state)
    cloud=CloudExcel(state,state/'raporlar')
    _receipt(ledger,cloud,state,'M5','18472.png','Wifi_035','18472')
    _receipt(ledger,cloud,state,'M5','18472.png','Wifi_036','18472')
    original=tmp_path/'one_image.xlsx';_blank_template(original,multiple=False)
    with pytest.raises(ValueError,match='SUTUNLARI_YETERSIZ'):
        export_store_upload(original,state,store_id='M5',report_root=state/'raporlar')
    assert list((state/'raporlar').glob('*.xlsx'))==[]


def test_store_excel_preserves_nonempty_template_and_refuses_wrong_url(tmp_path):
    state=tmp_path/'state';state.mkdir()
    ledger=UnifiedV4Ledger(state)
    cloud=CloudExcel(state,state/'raporlar')
    _receipt(ledger,cloud,state,'M5','18472.png','Wifi_035','18472')
    template=tmp_path/'template.xlsx';_blank_template(template)
    wb=load_workbook(template);wb.active.cell(2,1,'EXISTING PRODUCT');wb.save(template);wb.close()
    with pytest.raises(ValueError,match='DOLU_SABLON'):
        export_store_upload(template,state,store_id='M5',report_root=state/'raporlar')
    assert template.exists()


def test_petek_store_excel_fixed_measurement_order_keeps_complete_rows(tmp_path):
    """PETEK size order is fixed, while each row keeps its own URL/codes."""
    state = tmp_path / 'state'; state.mkdir()
    ledger = UnifiedV4Ledger(state)
    cloud = CloudExcel(state, state / 'raporlar')
    category = '06_Petek_Kapama'
    # Insert in the historical lexical-problem order deliberately.
    for size in ('116', '136', '76', '96'):
        art = 'pexels-artbovich-6434617.png'
        base = trendyol_codes(art, 'Wudie', category)
        code = petek_measurement_codes(base, size)
        folder = state / 'uretilen_gorseller' / 'Wudie' / category
        folder.mkdir(parents=True, exist_ok=True)
        output = folder / f'{size}-pexels-artbovich-6434617_Petek_Wudie.png'
        output.write_bytes((size + '-linked-row').encode())
        fields = {
            'key': f'Wudie-{size}', 'sku': code['sku'], 'category': category,
            'art_sha': 'a' * 64, 'template_sha': 'b' * 64,
            'mask_sha': 'c' * 64, 'art_name': art, 'uid': size,
            'output': str(output), 'artifact_kind': 'overlay',
            'overlay_cm': size,
        }
        ledger.reserve(fields)
        digest = engine.digest(output)
        ledger.complete(fields['key'], digest)
        with cloud.connect() as db:
            db.execute('INSERT INTO cloud_link(artifact_key,output_sha,url) VALUES(?,?,?)',
                       (fields['key'], digest, f'https://cdn.example/{size}.png'))

    template = tmp_path / 'petek.xlsx'
    wb = Workbook(); ws = wb.active
    ws.append(['Stok Kodu', 'Barkod', 'Model Kodu', 'Kategori', 'Ölçü', 'Görsel 1'])
    wb.save(template); wb.close()
    result = export_store_upload(template, state, store_id='Wudie', report_root=state / 'raporlar')

    exported = load_workbook(result['output']); sheet = exported.active
    assert [sheet.cell(row, 5).value for row in range(2, 6)] == [
        '76 santimetre', '96 santimetre', '116 santimetre', '136 santimetre'
    ]
    for row, size in zip(range(2, 6), ('76', '96', '116', '136')):
        # Codes and the URL are read from the same complete row identity.
        assert sheet.cell(row, 1).value.startswith(size + '-')
        assert sheet.cell(row, 2).value.startswith(size + '-')
        assert sheet.cell(row, 3).value.endswith('_WUD_Pet')
        assert sheet.cell(row, 6).hyperlink.target == f'https://cdn.example/{size}.png'
    exported.close()


def test_petek_store_excel_groups_each_design_then_measurement(tmp_path):
    """Two designs must export as 76/96/116/136, then 76/96/116/136.

    The fixture deliberately inserts the eight ledger rows in a mixed order.
    Every row carries a design-specific URL and the assertions verify that
    the complete product identity, measurement, and link move together.
    """
    state = tmp_path / 'state'; state.mkdir()
    ledger = UnifiedV4Ledger(state)
    cloud = CloudExcel(state, state / 'raporlar')
    category = '06_Petek_Kapama'
    designs = ('Yatay_Tasarim100', 'Yatay_Tasarim200')
    insertion = [
        ('116', designs[1]), ('76', designs[0]), ('136', designs[1]),
        ('96', designs[0]), ('76', designs[1]), ('136', designs[0]),
        ('96', designs[1]), ('116', designs[0]),
    ]
    for index, (size, design) in enumerate(insertion):
        art = design + '.png'
        base = trendyol_codes(art, 'OmzHome', category)
        code = petek_measurement_codes(base, size)
        folder = state / 'uretilen_gorseller' / 'OmzHome' / category
        folder.mkdir(parents=True, exist_ok=True)
        output = folder / f'{size}-{design}-Petek.png'
        output.write_bytes(f'{design}-{size}'.encode())
        fields = {
            'key': f'OmzHome-{index}', 'sku': code['sku'], 'category': category,
            'art_sha': 'a' * 64, 'template_sha': 'b' * 64,
            'mask_sha': 'c' * 64, 'art_name': art, 'uid': str(index),
            'output': str(output), 'artifact_kind': 'overlay',
            'overlay_cm': size,
        }
        ledger.reserve(fields)
        digest = engine.digest(output)
        ledger.complete(fields['key'], digest)
        with cloud.connect() as db:
            db.execute(
                'INSERT INTO cloud_link(artifact_key,output_sha,url) VALUES(?,?,?)',
                (fields['key'], digest, f'https://cdn.example/{design}-{size}.png'),
            )

    template = tmp_path / 'petek-two-designs.xlsx'
    wb = Workbook(); ws = wb.active
    ws.append(['Stok Kodu', 'Barkod', 'Model Kodu', 'Kategori', 'Ölçü', 'Görsel 1'])
    wb.save(template); wb.close()
    result = export_store_upload(template, state, store_id='OmzHome', report_root=state / 'raporlar')

    exported = load_workbook(result['output']); sheet = exported.active
    expected_sizes = ['76 santimetre', '96 santimetre', '116 santimetre', '136 santimetre'] * 2
    expected_designs = [designs[0]] * 4 + [designs[1]] * 4
    assert [sheet.cell(row, 5).value for row in range(2, 10)] == expected_sizes
    assert [sheet.cell(row, 1).value.split('-', 1)[1].rsplit('_Petek_OmzHome', 1)[0]
            for row in range(2, 10)] == expected_designs
    for row, (design, size) in enumerate(
        ((design, size) for design in designs for size in ('76', '96', '116', '136')), 2
    ):
        assert sheet.cell(row, 6).hyperlink.target == f'https://cdn.example/{design}-{size}.png'
    exported.close()


def test_store_assignment_no_phash_image_decoding(tmp_path,monkeypatch):
    manager=StoreProfiles(tmp_path/'state')
    manager.add_store('M4');manager.add_store('M5')
    a={'category':'01_Wifi_Kutusu','uid':'Wifi_035','source_sha':'a'*64}
    b={'category':'01_Wifi_Kutusu','uid':'Wifi_036','source_sha':'b'*64}
    import URETIM_V4.store_profiles_v47 as module
    monkeypatch.setattr(module,'perceptual_fingerprint',lambda _: (_ for _ in ()).throw(
        AssertionError('NO pHash checks requested by operator')))
    manager.assign('M4',[a],all_approved=[a,b])
    manager.assign('M5',[b],all_approved=[a,b])
    with pytest.raises(ValueError,match='başka|REUSED_ACROSS_STORES'):
        manager.assign('M4',[b],all_approved=[a,b])
