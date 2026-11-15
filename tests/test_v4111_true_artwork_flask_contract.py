"""Real Flask preview integration, when Flask is installed on Windows.

Temporary synthetic source and Registry ONLY. No user files are touched.
"""
from __future__ import annotations
import base64
import cv2
import numpy as np
import pytest

pytest.importorskip('flask')
from MERKEZ.PETEK_V3 import engine
from TESTLER.test_v477_petek_browser_integration import fixture, png_as_browser
from tests.test_vnext_petek_dynamic_photo_count import scene_with_count


def test_http_geometry_conflict_shows_real_artwork_with_temp_mask(tmp_path, monkeypatch):
    client, photo, registry, _ = fixture(tmp_path, monkeypatch)
    source, wrong_mask, quad, _ = scene_with_count(14)
    assert cv2.imwrite(str(photo), source)
    art = np.full((260, 360, 3), (12, 92, 230), np.uint8)
    cv2.circle(art, (180, 130), 75, (222, 40, 60), -1)
    original_bytes = photo.read_bytes()
    result = client.post('/api/petek/preview-artwork', json={
        'name':photo.name, 'uid':photo.stem, 'source_sha':engine.digest(photo),
        'quad':quad.tolist(), 'mask':png_as_browser(wrong_mask),
        'physical_aspect':1.1163,
        'artwork_png':'data:image/png;base64,' + base64.b64encode(
            cv2.imencode('.png', art)[1].tobytes()).decode('ascii'),
        'realism_profile':'belirgin','material_effect':True,
        'pink_cleanup':True, 'preview_slot_mode':'orta'
    })
    assert result.status_code == 200, result.get_json()
    data = result.get_json()
    assert data['diagnostic_preview'] is True
    assert data['diagnostic_artwork_applied'] is True
    assert data['production_allowed'] is False
    assert data['diagnostic_mask_qa']['source_vent_count'] == 14
    image = cv2.imdecode(np.frombuffer(base64.b64decode(
        data['preview'].partition(',')[2]), np.uint8), cv2.IMREAD_COLOR)
    assert image.shape == source.shape
    assert np.count_nonzero(np.any(image != source, axis=2)) > 10000
    assert photo.read_bytes() == original_bytes
    assert not list(registry.profiles.glob('*.json'))


def test_service_announces_real_artwork_backend_revision(tmp_path, monkeypatch):
    client, _, _, _ = fixture(tmp_path, monkeypatch)
    result = client.get('/api/petek/service-status')
    assert result.status_code == 200
    assert result.get_json()['preview_ui_revision'] == 'PETEK_REAL_ARTWORK_PREVIEW_V4112'
