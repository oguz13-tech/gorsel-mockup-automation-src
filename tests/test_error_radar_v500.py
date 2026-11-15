"""Local Error Radar contract: structured, bounded and credential-safe."""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'MERKEZ'))

import error_advisor_v498 as radar


def test_compare_masks_reports_count_coordinates_and_stage():
    import numpy as np
    expected = np.zeros((4, 5), dtype=np.uint8)
    actual = expected.copy()
    actual[1, 2] = 255
    actual[3, 4] = 255
    result = radar.compare_masks(expected, actual, stage='PRINT_COMPOSITE')
    assert result['status'] == 'FAIL'
    assert result['mismatched_pixels'] == 2
    assert result['coordinates'] == [[2, 1], [4, 3]]
    assert result['bounding_box'] == [2, 1, 4, 3]
    assert result['stage'] == 'PRINT_COMPOSITE'


def test_qa_context_is_promoted_to_common_error_contract(tmp_path, monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    report = radar.record_error(
        'Koruma ihlali', 'protected pixel changed',
        context={
            'processing_stage': 'SOURCE_PROTECTION',
            'qa': {
                'changed_outside_print_mask': 4,
                'first_protected_coordinates': [[12, 9]],
                'mask_qa': {'remaining_pixels': 2},
            },
        },
    )
    assert report['processing_stage'] == 'SOURCE_PROTECTION'
    assert report['pixel_error_count'] == 4
    assert report['error_locations'] == [[12, 9]]
    assert report['mask_comparison']['mismatched_pixels'] == 2


def test_codex_bundle_contains_diagnostics_file(tmp_path, monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    report = radar.record_error('x', 'bad', diagnostics={
        'pixel_errors': {'mismatched_pixels': 3, 'coordinates': [[1, 2]]},
        'mask_comparison': {'mismatched_pixels': 1},
    })
    import zipfile
    with zipfile.ZipFile(radar.prepare_codex_bundle(report)) as archive:
        diagnostics = json.loads(archive.read('diagnostics.json'))
    assert diagnostics['processing_stage'] == 'x'
    assert diagnostics['pixel_errors']['mismatched_pixels'] == 3


def test_record_error_masks_secrets_and_creates_codex_bundle(tmp_path, monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    report = radar.record_error(
        'PETEK render hatası',
        'Bearer sk-abcdefghijklmnop token=secret-value',
        stage='preview',
        context={'category': '06_Petek_Kapama', 'api_key': 'do-not-write'},
    )
    assert report['error_code'].startswith('GFX-')
    payload = json.loads(Path(report['json_path']).read_text(encoding='utf-8'))
    assert payload['context']['api_key'] == '[REDACTED]'
    assert 'secret-value' not in payload['message']
    bundle = Path(radar.prepare_codex_bundle(report))
    assert bundle.is_file()
    assert bundle.stat().st_size < 200_000


def test_retention_is_bounded(tmp_path, monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    monkeypatch.setattr(radar, '_MAX_REPORTS', 3)
    for index in range(6):
        radar.record_error('test', f'failure-{index}')
    files = list((tmp_path / 'GorselMockup' / 'ErrorReports').glob('*.json'))
    assert len(files) <= 3


def test_dashboard_exposes_error_actions_and_search():
    source = (ROOT / 'MERKEZ' / 'premium_dashboard_v489.py').read_text(encoding='utf-8')
    for text in ('Raporu Aç', 'Raporu Kopyala', 'Codex İçin Rapor Hazırla', 'dashboard_query'):
        assert text in source


def test_fetch_perf_wrapper_is_idempotent_and_tracks_p95():
    source = (ROOT / 'SABLON_V2_MIMARI' / 'static' / 'js' / 'main.js').read_text(encoding='utf-8')
    assert '__gorselPerfWrapped' in source
    assert 'p95' in source
