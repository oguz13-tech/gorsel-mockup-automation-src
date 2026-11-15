"""Verify tool launch cannot falsely claim GUI readiness and keeps CSRF."""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'SABLON_V2_MIMARI'))
from SABLON_V2_MIMARI import app as mod


class FakeProcess:
    pid = 54321
    def __init__(self, code=None): self.code = code
    def poll(self): return self.code


def client():
    mod.app.config['TESTING'] = False
    mod.DB_STARTUP_AUDIT = {'ready':False, 'reason':'DB_NOT_READY'}
    return mod.app.test_client()


def test_csrf_available_even_if_factory_db_unavailable():
    c = client()
    resp = c.get('/api/session/csrf', base_url='http://127.0.0.1:8080')
    assert resp.status_code == 200 and resp.json['csrf']
    denied = c.post('/api/tools/launch/orientation_sort', base_url='http://127.0.0.1:8080')
    assert denied.status_code == 403
    factory = c.get('/api/ayarlar', base_url='http://127.0.0.1:8080')
    assert factory.status_code == 503


def test_async_launch_starting_ready_and_failed(monkeypatch):
    c = client()
    seen = {}
    proc = FakeProcess()
    def popen(args, **kwargs):
        seen['ready'] = Path(kwargs['env']['MOCKUP_TOOL_READY_FILE'])
        return proc
    monkeypatch.setattr(mod.subprocess, 'Popen', popen)
    csrf = c.get('/api/session/csrf', base_url='http://127.0.0.1:8080').json['csrf']
    resp = c.post('/api/tools/launch/orientation_sort', base_url='http://127.0.0.1:8080', headers={'X-V47-CSRF':csrf})
    assert resp.status_code == 202
    assert resp.json['status'] == 'STARTING'
    assert 'açıldı' not in resp.json['message']
    launch = resp.json['launch_id']
    started = c.get('/api/tools/status/'+launch, base_url='http://127.0.0.1:8080')
    assert started.status_code == 200 and started.json['status'] == 'STARTING'
    seen['ready'].write_text('READY')
    ready = c.get('/api/tools/status/'+launch, base_url='http://127.0.0.1:8080')
    assert ready.json['status'] == 'READY'
    proc.code = 1
    failed = c.get('/api/tools/status/'+launch, base_url='http://127.0.0.1:8080')
    assert failed.status_code == 500 and failed.json['status'] == 'FAILED'


def test_tool_launch_unknown_tool_rejected(monkeypatch):
    c = client()
    csrf=c.get('/api/session/csrf', base_url='http://127.0.0.1:8080').json['csrf']
    bad = c.post('/api/tools/launch/not_a_tool', base_url='http://127.0.0.1:8080',headers={'X-V47-CSRF':csrf})
    assert bad.status_code == 404
    assert not bad.json['success']
