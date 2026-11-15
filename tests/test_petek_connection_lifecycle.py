from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from flask import Flask
from SABLON_V2_MIMARI.core.petek_web_v477 import petek_web


def test_service_status_and_client_diagnostic_are_read_only_json():
    app = Flask(__name__)
    app.config.update(TESTING=True, PETEK_WORKSPACE_V477=str(ROOT))
    app.register_blueprint(petek_web)
    client = app.test_client()

    status = client.get('/api/petek/service-status')
    assert status.status_code == 200
    body = status.get_json()
    assert body['success'] is True
    assert body['contract'] == 'PETEK_PREVIEW_API_VNEXT_JSON_20261101'
    assert body['read_only'] is True

    diagnostic = client.post('/api/petek/client-diagnostic', json={
        'path': '/api/petek/templates',
        'error': 'Failed to fetch',
        'href': 'http://127.0.0.1:8080/',
        'at': 'test',
    })
    assert diagnostic.status_code == 200
    assert diagnostic.get_json() == {
        'success': True, 'recorded': True, 'read_only': True,
    }


def test_editor_checks_service_on_open_and_has_reconnect_diagnostics():
    js = (ROOT / 'SABLON_V2_MIMARI/static/js/petek_editor_v477.js').read_text('utf-8')
    html = (ROOT / 'SABLON_V2_MIMARI/templates/index.html').read_text('utf-8')
    assert "fetch('/api/petek/service-status'" in js
    assert "setInterval(()=>{if(s.active)checkService({quiet:true});},15000)" in js
    assert "'/api/petek/client-diagnostic'" in js
    assert 'id="petekV477Reconnect"' in html
