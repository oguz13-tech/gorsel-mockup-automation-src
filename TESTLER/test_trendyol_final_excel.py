"""Offline acceptance tests for the final store-isolated Trendyol export."""
from pathlib import Path
import sys
from openpyxl import Workbook, load_workbook
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'MERKEZ'))
from URETIM_V4.unified_batch import UnifiedV4Ledger
from URETIM_V4.cloud_excel_v43 import CloudExcel
from URETIM_V4.store_excel_v485 import export_store_upload
from URETIM_V4.store_identity_v485 import trendyol_codes
from PETEK_V3 import engine


def _template(path):
    wb = Workbook(); ws = wb.active
    ws.append(['Stok Kodu', 'Barkod', 'Model Kodu', 'Kategori', 'Görsel 1', 'Görsel 2',
               'Tasarım Dosyası', 'Mockup Dosyası', 'Şablon', 'Yerel Dosya'])
    wb.save(path); wb.close()


def _receipt(state, ledger, cloud, store, category, art, uid, url):
    code = trendyol_codes(art, store, category)
    out = state / 'uretilen_gorseller' / store / category / f'{uid}.png'
    out.parent.mkdir(parents=True, exist_ok=True); out.write_bytes((store + uid).encode())
    sha = engine.digest(out)
    fields = {'key': store + uid, 'sku': code['sku'], 'category': category,
              'art_sha': 'a' * 64, 'template_sha': 'b' * 64, 'mask_sha': 'c' * 64,
              'art_name': art, 'uid': uid, 'output': str(out)}
    ledger.reserve(fields); ledger.complete(fields['key'], sha)
    with cloud.connect() as db:
        db.execute('INSERT INTO cloud_link(artifact_key,output_sha,url) VALUES(?,?,?)',
                   (fields['key'], sha, url))


def test_three_stores_are_three_workbooks_and_same_design_isolated(tmp_path):
    state = tmp_path / 'state'; state.mkdir()
    ledger = UnifiedV4Ledger(state); cloud = CloudExcel(state, state / 'reports')
    for store in ('OmzHome', 'Adeno', 'Wudie'):
        _receipt(state, ledger, cloud, store, '01_Wifi_Kutusu', 'Yatay_Tasarim001.png',
                 store, f'https://cdn.example/{store}.png')
    template = tmp_path / 'template.xlsx'; _template(template)
    outputs = [export_store_upload(template, state, store_id=s, report_root=state / 'reports')
               for s in ('OmzHome', 'Adeno', 'Wudie')]
    assert len({Path(x['output']).parent for x in outputs}) == 3
    assert all(Path(x['output']).parent.name == 'excel çıktıları' for x in outputs)
    assert all(Path(x['output']).parts[-3] == '01_Wifi_Kutusu' for x in outputs)
    wb = load_workbook(outputs[1]['output']); row = [c.value for c in wb.active[2]]
    assert row[:3] == ['Yatay_Tasarim001_Wifi_Adeno', 'Yatay_Tasarim001_Wifi_ADN',
                       'Yatay_Tasarim001_ADN_Wifi']
    assert wb.active['E2'].hyperlink.target.startswith('https://')
    wb.close()


def test_length_error_is_reported_without_truncation(tmp_path):
    state = tmp_path / 'state'; state.mkdir()
    ledger = UnifiedV4Ledger(state); cloud = CloudExcel(state, state / 'reports')
    _receipt(state, ledger, cloud, 'Wudie', '01_Wifi_Kutusu', 'A' * 80 + '.png', 'too-long',
             'https://cdn.example/long.png')
    template = tmp_path / 'template.xlsx'; _template(template)
    with pytest.raises(ValueError, match='Hata raporu'):
        export_store_upload(template, state, store_id='Wudie', report_root=state / 'reports')
    reports = list((state / 'reports').glob('TRENDYOL_EXCEL_HATA_RAPORU_*.json'))
    assert reports and '89/40' in reports[0].read_text(encoding='utf-8')
