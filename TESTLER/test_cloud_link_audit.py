import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'MERKEZ'))
from URETIM_V4 import cloud_excel_v43 as cloud_mod


def _row(tmp_path, key='k1'):
    runtime = tmp_path / 'runtime'; runtime.mkdir()
    state = tmp_path / 'state'
    output = state / 'uretilen_gorseller' / 'LOCAL' / 'batch'
    output.mkdir(parents=True)
    image = output / 'original.png'
    image.write_bytes(b'original-bytes')
    sha = hashlib.sha256(image.read_bytes()).hexdigest()
    return runtime, state, image, {
        'key': key, 'sku': 'SKU-1', 'category': 'LOCAL',
        'art_name': image.name, 'output': str(image), 'output_sha': sha,
    }


def test_provider_routes_are_canonical_imagekit_imgbb_freeimage(tmp_path):
    runtime = tmp_path / 'runtime'; runtime.mkdir()
    (runtime / 'ayarlar.local.json').write_text(json.dumps({'bulut_ayarlari': {
        'provider': 'imgbb',
        'provider_order': ['freeimage', 'imgbb', 'imagekit'],
        'imagekit_private_keys': ['ik'], 'imgbb_keys': ['ib'],
        'freeimage_keys': ['fi'],
    }}), encoding='utf-8')
    routes = cloud_mod._provider_routes(runtime)
    assert [r['provider'] for r in routes] == ['imagekit', 'imgbb', 'freeimage']


def test_stale_remote_sha_is_reprocessed_without_touching_healthy_row(tmp_path, monkeypatch):
    runtime, state, image, row = _row(tmp_path)
    (runtime / 'ayarlar.local.json').write_text(json.dumps({'bulut_ayarlari': {
        'provider': 'imagekit', 'imagekit_private_key': 'ik',
    }}), encoding='utf-8')
    cloud = cloud_mod.CloudExcel(state, tmp_path / 'reports', runtime)
    with cloud.connect() as db:
        db.execute('INSERT INTO cloud_link(artifact_key,output_sha,url,provider,remote_sha) VALUES(?,?,?,?,?)',
                   (row['key'], row['output_sha'], 'https://ik.imagekit.io/gorseluretimerkezi/old.png?tr=orig-true',
                    'imagekit', 'f' * 64))
    calls = []
    monkeypatch.setattr(cloud_mod, '_head_check', lambda url, timeout=8.0: (True, 'head_ok'))
    monkeypatch.setattr(cloud_mod, 'upload_to_imagekit', lambda path, key: (
        calls.append(path.name) or (
            'https://ik.imagekit.io/gorseluretimerkezi/original.png?tr=orig-true',
            {'sha256': row['output_sha'], 'width': 1, 'height': 1, 'format': 'PNG'})))
    assert cloud.upload_one(row) == 'uploaded'
    assert calls == [image.name]
    with cloud.connect() as db:
        saved = db.execute('SELECT url,remote_sha FROM cloud_link WHERE artifact_key=?', (row['key'],)).fetchone()
    assert saved['url'].endswith('original.png?tr=orig-true')
    assert saved['remote_sha'] == row['output_sha']


def test_healthy_imagekit_receipt_is_reused_without_api_call(tmp_path, monkeypatch):
    runtime, state, image, row = _row(tmp_path)
    (runtime / 'ayarlar.local.json').write_text(json.dumps({'bulut_ayarlari': {
        'provider': 'imagekit', 'imagekit_private_key': 'ik',
    }}), encoding='utf-8')
    cloud = cloud_mod.CloudExcel(state, tmp_path / 'reports', runtime)
    with cloud.connect() as db:
        db.execute('INSERT INTO cloud_link(artifact_key,output_sha,url,provider,remote_sha) VALUES(?,?,?,?,?)',
                   (row['key'], row['output_sha'], 'https://ik.imagekit.io/gorseluretimerkezi/original.png?tr=orig-true',
                    'imagekit', row['output_sha']))
    monkeypatch.setattr(cloud_mod, '_head_check', lambda url, timeout=8.0: (True, 'head_ok'))
    monkeypatch.setattr(cloud_mod, 'upload_to_imagekit', lambda *_: pytest.fail('healthy link must not upload'))
    assert cloud.upload_one(row) == 'reused'
