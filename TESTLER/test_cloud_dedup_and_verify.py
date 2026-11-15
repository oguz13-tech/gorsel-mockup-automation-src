"""T03 API'siz testleri: sağlayıcı geçişi + aynı-SHA yeniden kullanım.

Hiçbir ağ çağrısı yapılmaz; requests/post/get ve upload fonksiyonları
monkeypatch ile taklit edilir.
"""
import hashlib
import json
import sys
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'MERKEZ'))
from URETIM_V4 import cloud_excel_v43 as cloud_mod


def _png(path: Path, color=(20, 80, 130)) -> bytes:
    Image.new('RGB', (37, 29), color).save(path, format='PNG')
    return path.read_bytes()


def _runtime(tmp_path, bulut: dict) -> Path:
    runtime = tmp_path / 'runtime'; runtime.mkdir()
    (runtime / 'ayarlar.local.json').write_text(
        json.dumps({'bulut_ayarlari': bulut}), encoding='utf-8')
    return runtime


def _state(tmp_path, *names: str):
    state = tmp_path / 'state'
    out = state / 'uretilen_gorseller' / 'LOCAL' / 'batch'
    out.mkdir(parents=True)
    rows = []
    for n, name in enumerate(names):
        src = out / name
        payload = _png(src, (20, 80, 130 + n) if len(names) > 1 else (20, 80, 130))
        rows.append({'key': f'k{n}', 'sku': f'SKU-{n}', 'category': 'LOCAL',
                     'art_name': src.name, 'output': str(src),
                     'output_sha': hashlib.sha256(payload).hexdigest()})
    return state, rows


def _receipt(url, provider, sha):
    return url, {'sha256': sha, 'width': 37, 'height': 29, 'format': 'PNG'}


def test_identical_bytes_upload_once_and_reuse_receipt(tmp_path, monkeypatch):
    """Aynı SHA'lı iki farklı anahtar: tek yükleme, iki makbuz, aynı URL."""
    runtime = _runtime(tmp_path, {'provider': 'imagekit', 'imagekit_private_key': 'ik'})
    state = tmp_path / 'state'
    out = state / 'uretilen_gorseller' / 'LOCAL' / '07_Other' / 'store'
    out.mkdir(parents=True)
    src = out / 'same.png'
    payload = _png(src)  # iki anahtar da aynı dosyayı referans alır
    sha = hashlib.sha256(payload).hexdigest()
    rows = [{'key': 'a', 'sku': 'SKU-A', 'category': 'LOCAL', 'art_name': 'same.png',
             'output': str(src), 'output_sha': sha},
            {'key': 'b', 'sku': 'SKU-B', 'category': 'LOCAL', 'art_name': 'same.png',
             'output': str(src), 'output_sha': sha}]
    calls = []

    def fake_upload(path, key):
        calls.append(path.name)
        return _receipt('https://ik.imagekit.io/gorseluretimerkezi/same.png?tr=orig-true',
                        'imagekit', hashlib.sha256(path.read_bytes()).hexdigest())

    monkeypatch.setattr(cloud_mod, 'upload_to_imagekit', fake_upload)
    monkeypatch.setattr(cloud_mod, '_head_check', lambda url, timeout=8.0: (True, 'head_ok'))
    result = cloud_mod.CloudExcel(state, tmp_path / 'reports', runtime).publish_existing(rows)
    assert result['failed'] == 0
    assert result['uploaded'] == 1
    assert result['reused'] == 1
    assert len(calls) == 1
    with cloud_mod.CloudExcel(state, tmp_path / 'reports', runtime).connect() as db:
        urls = [r[0] for r in db.execute('select url from cloud_link order by artifact_key')]
        n = db.execute('select count(*) from cloud_link').fetchone()[0]
    assert n == 2 and urls[0] == urls[1]
    assert urls[0].endswith('?tr=orig-true')


def test_upload_one_borrows_verified_receipt_for_same_sha(tmp_path, monkeypatch):
    """upload_one: aynı SHA için doğrulanmış makbuz varsa ağa çıkmaz."""
    runtime = _runtime(tmp_path, {'provider': 'imagekit', 'imagekit_private_key': 'ik'})
    state, rows = _state(tmp_path, 'one.png')
    row = rows[0]
    cloud = cloud_mod.CloudExcel(state, tmp_path / 'reports', runtime)
    with cloud.connect() as db:
        db.execute('INSERT INTO cloud_link(artifact_key, output_sha, url, provider, remote_sha) VALUES(?,?,?,?,?)',
                   ('eski', row['output_sha'],
                    'https://ik.imagekit.io/gorseluretimerkezi/one.png?tr=orig-true',
                    'imagekit', row['output_sha']))
    monkeypatch.setattr(cloud_mod, 'upload_to_imagekit', lambda *_: pytest.fail('aynı SHA yeniden yüklenmemeli'))
    monkeypatch.setattr(cloud_mod, '_head_check', lambda url, timeout=8.0: (True, 'head_ok'))
    assert cloud.upload_one(row) == 'reused'
    with cloud.connect() as db:
        saved = db.execute('select url, provider, remote_sha from cloud_link where artifact_key=?', (row['key'],)).fetchone()
    assert saved['url'].endswith('?tr=orig-true')
    assert saved['remote_sha'] == row['output_sha']


def test_legacy_unverified_imgbb_receipt_is_not_borrowed(tmp_path, monkeypatch):
    """remote_sha'sız eski ImgBB makbuzu başka anahtara körlemesine kopyalanmaz."""
    runtime = _runtime(tmp_path, {'provider': 'imagekit', 'imagekit_private_key': 'ik'})
    state, rows = _state(tmp_path, 'two.png')
    row = rows[0]
    cloud = cloud_mod.CloudExcel(state, tmp_path / 'reports', runtime)
    with cloud.connect() as db:
        db.execute('INSERT INTO cloud_link(artifact_key, output_sha, url, provider, remote_sha) VALUES(?,?,?,?,?)',
                   ('eski', row['output_sha'], 'https://i.ibb.co/x/two.png', 'imgbb', None))
    monkeypatch.setattr(cloud_mod, 'upload_to_imagekit',
                        lambda path, key: _receipt('https://ik.imagekit.io/gorseluretimerkezi/two.png?tr=orig-true',
                                                   'imagekit', hashlib.sha256(path.read_bytes()).hexdigest()))
    monkeypatch.setattr(cloud_mod, '_head_check', lambda url, timeout=8.0: (True, 'head_ok'))
    assert cloud.upload_one(row) == 'uploaded'


class _Resp:
    def __init__(self, url, status=200, content=b'', payload=None):
        self.url = url; self.status_code = status; self.content = content
        self._payload = payload or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError('HTTP ' + str(self.status_code))


def test_imgbb_remote_mismatch_falls_back_to_freeimage(tmp_path, monkeypatch):
    """ImgBB uzak baytı uyuşmazsa failover FreeImage'e geçer; kötü link yazılmaz."""
    runtime = _runtime(tmp_path, {'provider': 'imagekit', 'imagekit_private_keys': ['bad'],
                                  'imgbb_keys': ['ib'], 'freeimage_keys': ['fi']})
    state, rows = _state(tmp_path, 'three.png')
    row = rows[0]
    payload = Path(row['output']).read_bytes()
    monkeypatch.setattr(cloud_mod, 'upload_to_imagekit',
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError('quota')))

    def fake_post(url, *args, **kwargs):
        if 'imgbb.com' in url:
            return _Resp(url, 200, payload={'data': {'url': 'https://i.ibb.co/deadbeef/three.png'}})
        if 'freeimage.host' in url:
            return _Resp(url, 200, payload={'image': {'url': 'https://iili.io/ok/three.png'}})
        raise AssertionError('beklenmeyen post: ' + url)

    def fake_get(url, *args, **kwargs):
        if url == 'https://i.ibb.co/deadbeef/three.png':
            return _Resp(url, 200, content=b'BOZUK-BAYTLAR')
        return _Resp(url, 200, content=payload)

    monkeypatch.setattr(cloud_mod.requests, 'post', fake_post)
    monkeypatch.setattr(cloud_mod.requests, 'get', fake_get)
    monkeypatch.setattr(cloud_mod, '_head_check', lambda url, timeout=8.0: (True, 'head_ok'))
    result = cloud_mod.CloudExcel(state, tmp_path / 'reports', runtime).upload_one(row)
    assert result == 'uploaded'
    with cloud_mod.CloudExcel(state, tmp_path / 'reports', runtime).connect() as db:
        saved = db.execute('select url, provider, remote_sha from cloud_link where artifact_key=?', (row['key'],)).fetchone()
    assert saved['provider'] == 'freeimage'
    assert saved['url'] == 'https://iili.io/ok/three.png'
    assert saved['remote_sha'] == row['output_sha']


def test_imgbb_verified_receipt_records_remote_sha(tmp_path, monkeypatch):
    """ImgBB yolu da SHA-256 doğrulaması geçirir ve makbuza remote_sha yazar."""
    runtime = _runtime(tmp_path, {'provider': 'imgbb', 'imgbb_keys': ['ib']})
    state, rows = _state(tmp_path, 'four.png')
    row = rows[0]
    payload = Path(row['output']).read_bytes()

    def fake_post(url, *args, **kwargs):
        return _Resp(url, 200, payload={'data': {'url': 'https://i.ibb.co/ok/four.png'}})

    monkeypatch.setattr(cloud_mod.requests, 'post', fake_post)
    monkeypatch.setattr(cloud_mod.requests, 'get', lambda url, *a, **k: _Resp(url, 200, content=payload))
    monkeypatch.setattr(cloud_mod, '_head_check', lambda url, timeout=8.0: (True, 'head_ok'))
    result = cloud_mod.CloudExcel(state, tmp_path / 'reports', runtime).upload_one(row)
    assert result == 'uploaded'
    with cloud_mod.CloudExcel(state, tmp_path / 'reports', runtime).connect() as db:
        saved = db.execute('select url, provider, remote_sha from cloud_link where artifact_key=?', (row['key'],)).fetchone()
    assert saved['provider'] == 'imgbb'
    assert saved['remote_sha'] == row['output_sha']


def test_dead_receipt_is_reuploaded_instead_of_reused(tmp_path, monkeypatch):
    """Kayıtlı link ölüyse kullanıcı zarar görmez: aynı dosya yeniden yüklenir."""
    runtime = _runtime(tmp_path, {'provider': 'imagekit', 'imagekit_private_key': 'ik'})
    state, rows = _state(tmp_path, 'five.png')
    row = rows[0]
    cloud = cloud_mod.CloudExcel(state, tmp_path / 'reports', runtime)
    with cloud.connect() as db:
        db.execute('INSERT INTO cloud_link(artifact_key, output_sha, url, provider, remote_sha) VALUES(?,?,?,?,?)',
                   (row['key'], row['output_sha'],
                    'https://ik.imagekit.io/gorseluretimerkezi/five.png?tr=orig-true',
                    'imagekit', row['output_sha']))
    calls = []

    def fake_upload(path, key):
        calls.append(path.name)
        return _receipt('https://ik.imagekit.io/gorseluretimerkezi/five-fresh.png?tr=orig-true',
                        'imagekit', hashlib.sha256(path.read_bytes()).hexdigest())

    monkeypatch.setattr(cloud_mod, 'upload_to_imagekit', fake_upload)
    monkeypatch.setattr(cloud_mod, '_head_check', lambda url, timeout=8.0: (False, 'dead_404'))
    assert cloud.upload_one(row) == 'uploaded'
    assert calls == [row['art_name']]
    with cloud.connect() as db:
        saved = db.execute('select url from cloud_link where artifact_key=?', (row['key'],)).fetchone()
    assert saved['url'].endswith('five-fresh.png?tr=orig-true')


def test_dead_receipt_in_publish_existing_triggers_reupload_and_reports(tmp_path, monkeypatch):
    runtime = _runtime(tmp_path, {'provider': 'imagekit', 'imagekit_private_key': 'ik'})
    state, rows = _state(tmp_path, 'six.png')
    row = rows[0]
    cloud = cloud_mod.CloudExcel(state, tmp_path / 'reports', runtime)
    with cloud.connect() as db:
        db.execute('INSERT INTO cloud_link(artifact_key, output_sha, url, provider, remote_sha) VALUES(?,?,?,?,?)',
                   (row['key'], row['output_sha'],
                    'https://ik.imagekit.io/gorseluretimerkezi/six.png?tr=orig-true',
                    'imagekit', row['output_sha']))

    def fake_upload(path, key):
        return _receipt('https://ik.imagekit.io/gorseluretimerkezi/six-fresh.png?tr=orig-true',
                        'imagekit', hashlib.sha256(path.read_bytes()).hexdigest())

    monkeypatch.setattr(cloud_mod, 'upload_to_imagekit', fake_upload)
    monkeypatch.setattr(cloud_mod, '_head_check', lambda url, timeout=8.0: (False, 'dead_404'))
    result = cloud.publish_existing(rows)
    assert result['uploaded'] == 1
    assert result['failed'] == 0
    stale = [e for e in result['errors'] if e.get('kind') == 'STALE_LINK_REUPLOADING']
    assert stale and stale[0]['kind'] == 'STALE_LINK_REUPLOADING'


def test_head_check_fallback_and_not_image(tmp_path, monkeypatch):
    class R:
        status_code = 200
        headers = {'Content-Type': 'image/png'}
    monkeypatch.setattr(cloud_mod.requests, 'head', lambda *a, **k: R())
    ok, reason = cloud_mod._head_check('https://i.ibb.co/example/img.png')
    assert ok and reason == 'head_ok'

    class R2(R):
        status_code = 405
        headers = {'Content-Type': 'text/html'}
    class G:
        status_code = 206
        headers = {'Content-Type': 'image/png', 'Content-Length': '1'}
        raw = None

        def close(self):
            pass
    monkeypatch.setattr(cloud_mod.requests, 'head', lambda *a, **k: R2())
    monkeypatch.setattr(cloud_mod.requests, 'get', lambda *a, **k: G())
    ok, reason = cloud_mod._head_check('https://i.ibb.co/example/img.png')
    assert ok and reason == 'range_ok'
    """ImgBB yolu da SHA-256 doğrulaması geçirir ve makbuza remote_sha yazar."""
    runtime = _runtime(tmp_path, {'provider': 'imgbb', 'imgbb_keys': ['ib']})
    state, rows = _state(tmp_path, 'four.png')
    row = rows[0]
    payload = Path(row['output']).read_bytes()

    def fake_post(url, *args, **kwargs):
        return _Resp(url, 200, payload={'data': {'url': 'https://i.ibb.co/ok/four.png'}})

    monkeypatch.setattr(cloud_mod.requests, 'post', fake_post)
    monkeypatch.setattr(cloud_mod.requests, 'get', lambda url, *a, **k: _Resp(url, 200, content=payload))
    monkeypatch.setattr(cloud_mod, '_head_check', lambda url, timeout=8.0: (True, 'head_ok'))
    result = cloud_mod.CloudExcel(state, tmp_path / 'reports', runtime).upload_one(row)
    assert result == 'uploaded'
    with cloud_mod.CloudExcel(state, tmp_path / 'reports', runtime).connect() as db:
        saved = db.execute('select url, provider, remote_sha from cloud_link where artifact_key=?', (row['key'],)).fetchone()
    assert saved['provider'] == 'imgbb'
    assert saved['remote_sha'] == row['output_sha']
