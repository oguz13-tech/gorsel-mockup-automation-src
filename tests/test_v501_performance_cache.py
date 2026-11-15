import json
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'MERKEZ'))

from PETEK_V3.geometry_cache import cache_key, load, store
from PETEK_V3.petek_slot_geometry_vnext import measure_real_vents
from URETIM_V4.performance_v501 import planning_summary, summarize_reports, machine_key
from URETIM_V4.unified_batch import recommended_render_workers, production_render_workers


def test_geometry_cache_round_trip_is_immutable(tmp_path):
    source = np.full((180, 280, 3), 220, dtype=np.uint8)
    mask = np.full((180, 280), 255, dtype=np.uint8)
    quad = [[10, 10], [270, 10], [270, 170], [10, 170]]
    key = cache_key('source', 'mask', quad, 'recipe')
    measured = {'count': 1, 'homography': np.eye(3, dtype=np.float32)}
    slots = [{'center': 10.0, 'effect_eligible': True}]
    store(tmp_path, key, slots, measured)
    loaded = load(tmp_path, key)
    loaded[0][0]['center'] = 999
    loaded_again = load(tmp_path, key)
    assert loaded_again[0][0]['center'] == 10.0


def test_geometry_measurement_cache_reuses_verified_key(tmp_path, monkeypatch):
    source = np.full((520, 480, 3), 220, dtype=np.uint8)
    quad = np.float32([[45, 80], [435, 80], [435, 440], [45, 440]])
    from PETEK_V3 import engine
    mask = engine.polygon_mask((520, 480, 3), quad)
    for x in range(85, 405, 25):
        cv2.rectangle(source, (x, 165), (x + 6, 380), (22, 24, 28), -1)
        cv2.rectangle(mask, (x, 165), (x + 6, 380), 0, -1)
    first, qa = measure_real_vents(source, mask, quad, cache_root=tmp_path)
    assert qa['count'] >= 5
    source_copy = source.copy()
    second, qa2 = measure_real_vents(source_copy, mask.copy(), quad, cache_root=tmp_path)
    assert qa2['count'] == qa['count']
    assert second == first
    assert list(Path(tmp_path).glob('*.json'))


def test_planning_summary_has_disk_guard(tmp_path):
    report_dir = tmp_path / 'reports'
    report_dir.mkdir()
    (report_dir / 'ISLEM_RAPORU_x.json').write_text(json.dumps({
        'operation_id': 'x', 'counts': {'successful': 10, 'failed': 0},
        'performance': {'render_workers': 2,
                        'stage_timings': {'total_wall_seconds': 100}},
    }), encoding='utf-8')
    summary = planning_summary(output_root=tmp_path, jobs=10, templates=2,
                               designs=5, workers=2, report_dir=report_dir)
    assert summary['disk_budget_ok'] is True
    assert summary['estimated_seconds'] == 100.0


def test_worker_profile_requires_same_machine_and_equivalence(tmp_path):
    profile = tmp_path / 'render_worker_profile.json'
    profile.write_text(json.dumps({'recommended_workers': 4,
                                   'machine_key': machine_key(),
                                   'pixel_equivalence_verified': False}), encoding='utf-8')
    value, reason = recommended_render_workers(tmp_path)
    assert value in (1, 2)
    assert reason == 'conservative_cpu_fallback'
    profile.write_text(json.dumps({'recommended_workers': 4,
                                   'machine_key': machine_key(),
                                   'pixel_equivalence_verified': True}), encoding='utf-8')
    assert recommended_render_workers(tmp_path) == (4, 'persisted_benchmark_profile')


def test_production_worker_count_is_fixed_at_two(monkeypatch, tmp_path):
    monkeypatch.setenv('V4_RENDER_WORKERS', '8')
    profile = tmp_path / 'render_worker_profile.json'
    profile.write_text(json.dumps({'recommended_workers': 6,
                                   'machine_key': machine_key(),
                                   'pixel_equivalence_verified': True}), encoding='utf-8')
    assert production_render_workers() == (2, 'FIXED_SAFE_PROFILE_2')
