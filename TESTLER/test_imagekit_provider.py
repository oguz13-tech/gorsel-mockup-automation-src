import hashlib
import json
import sys
import time
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'MERKEZ'))
from URETIM_V4 import cloud_excel_v43 as cloud_mod


def _image(path: Path):
    Image.new('RGB', (37, 29), (20, 80, 130)).save(path, format='PNG')


def test_imagekit_orig_true_verifies_sha_dimensions_and_format(tmp_path, monkeypatch):
    source = tmp_path / 'original.png'
    _image(source)
    payload = source.read_bytes()

    class Response:
        status_code = 200
        content = payload
        url = 'https://ik.imagekit.io/gorseluretimerkezi/original.png?tr=orig-true'
        def raise_for_status(self): pass
        def json(self): return {'url': 'https://ik.imagekit.io/gorseluretimerkezi/original.png'}

    monkeypatch.setattr(cloud_mod.requests, 'post', lambda *a, **k: Response())
    monkeypatch.setattr(cloud_mod.requests, 'get', lambda *a, **k: Response())
    url, meta = cloud_mod.upload_to_imagekit(source, 'local-test-key')
    assert url.endswith('?tr=orig-true')
    assert meta['sha256'] == hashlib.sha256(payload).hexdigest()
    assert (meta['width'], meta['height'], meta['format']) == (37, 29, 'PNG')


def test_upload_one_falls_back_to_next_provider_route(tmp_path, monkeypatch):
    runtime = tmp_path / 'runtime'; runtime.mkdir()
    (runtime / 'ayarlar.local.json').write_text(json.dumps({'bulut_ayarlari': {
        'provider': 'imagekit',
        'provider_order': ['imagekit', 'imgbb'],
        'imagekit_private_keys': ['bad-imagekit-key'],
        'imgbb_keys': ['yedek-imgbb-key'],
    }}), encoding='utf-8')
    root = tmp_path / 'state'; out = root / 'uretilen_gorseller' / 'LOCAL' / 'batch'; out.mkdir(parents=True)
    source = out / 'yedek.png'; _image(source)
    sha = hashlib.sha256(source.read_bytes()).hexdigest()
    row = {'key': 'yedek-key', 'sku': 'yedek-1', 'category': 'LOCAL',
           'art_name': source.name, 'output': str(source), 'output_sha': sha}

    def fail_imagekit(*args, **kwargs):
        raise RuntimeError('quota')
    monkeypatch.setattr(cloud_mod, 'upload_to_imagekit', fail_imagekit)
    monkeypatch.setattr(cloud_mod, 'upload_https', lambda path, keys, freeimage:
                        f'https://i.ibb.co/{path.name}')
    result = cloud_mod.CloudExcel(root, tmp_path / 'reports', runtime).upload_one(row)
    assert result == 'uploaded'
    with cloud_mod.CloudExcel(root, tmp_path / 'reports', runtime).connect() as db:
        assert db.execute('select provider from cloud_link where artifact_key=?', ('yedek-key',)).fetchone()[0] == 'imgbb'


@pytest.mark.parametrize('count', [1, 10, 54])
def test_parallel_publish_counts_and_provider_receipt(tmp_path, monkeypatch, count):
    runtime = tmp_path / 'runtime'; runtime.mkdir()
    (runtime / 'ayarlar.json').write_text(json.dumps({'bulut_ayarlari': {'provider': 'imagekit', 'imagekit_private_key': 'test'}}), encoding='utf-8')
    root = tmp_path / 'state'; out = root / 'uretilen_gorseller' / 'LOCAL' / 'batch'; out.mkdir(parents=True)
    rows = []
    for n in range(count):
        path = out / f'item_{n}.png'
        # Distinct bytes per SKU: identical content is the dedup test's job.
        Image.new('RGB', (37, 29), (20, 80, 130 + n)).save(path, format='PNG')
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        rows.append({'key': f'k{n}', 'sku': f'SKU-{n}', 'category': 'LOCAL', 'art_name': path.name,
                     'output': str(path), 'output_sha': sha})

    def fake_upload(path, key):
        return f'https://ik.imagekit.io/gorseluretimerkezi/{path.name}?tr=orig-true', {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'width': 37, 'height': 29, 'format': 'PNG'}
    monkeypatch.setattr(cloud_mod, 'upload_to_imagekit', fake_upload)
    monkeypatch.setattr(cloud_mod, '_head_check', lambda url, timeout=8.0: (True, 'head_ok'))
    result = cloud_mod.CloudExcel(root, tmp_path / 'reports', runtime).publish_existing(rows)
    assert result['uploaded'] == count
    assert result['failed'] == 0
    assert result['provider'] if 'provider' in result else True
    with cloud_mod.CloudExcel(root, tmp_path / 'reports', runtime).connect() as db:
        assert db.execute('select count(*) from cloud_link where provider="imagekit"').fetchone()[0] == count
