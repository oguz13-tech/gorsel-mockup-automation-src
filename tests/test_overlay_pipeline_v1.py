"""Klasik PETEK overlay: render ile eş zamanlı (pipeline) çalışma — tamamen izole (tmp) testler."""
from __future__ import annotations

import hashlib
import sys
import threading
import time
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'MERKEZ'))

from URETIM_V4 import unified_batch as ub  # noqa: E402
from URETIM_V4.store_profiles_v47 import StoreProfiles  # noqa: E402

MEASUREMENTS = ('76CM', '96CM', '116CM', '136CM')


def _png(path: Path, color, size=(1200, 1600)):
    arr = np.zeros((size[1], size[0], 3), np.uint8)
    arr[:] = color
    arr[::7, ::5] = (255 - color[0], color[1], 200)
    Image.fromarray(arr).save(path)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _template(tmp: Path, uid: str, color):
    src = tmp / 'pool' / f'{uid}.png'
    src.parent.mkdir(exist_ok=True)
    sha = _png(src, color)
    return {'uid': uid, 'category': '06_Petek_Kapama', 'source': str(src), 'source_sha': sha,
            'mask_sha': 'm' * 64, 'engine_type': 'LEGACY', 'orientation': 'D',
            'quad': [[0, 0], [1, 0], [1, 1], [0, 1]], 'physical_aspect': 0.75, 'legacy_data': {}}


@pytest.fixture
def world(tmp_path, monkeypatch):
    state = tmp_path / 'state'
    engine = ub.UnifiedV4Batch(state)
    colors = [(30, 60, 90), (60, 90, 30), (90, 30, 60), (120, 120, 40), (10, 200, 80)]
    templates = [_template(tmp_path, f'wudie_t{i}', colors[i]) for i in range(5)]
    mgr = StoreProfiles(state)
    mgr.add_store('Adeno')
    mgr.assign('Adeno', templates, all_approved=templates)
    monkeypatch.setattr(engine, 'discover_templates',
                        lambda **kw: (list(templates), {'per_category_counts': {}, 'skipped': []}))
    monkeypatch.setattr(ub, '_build_legacy_category_mask',
                        lambda scene, quad, data: np.zeros(scene.shape[:2], np.uint8))
    monkeypatch.setattr(ub, 'validate_overlay_folder',
                        lambda root: {'ready': True, 'errors': [], 'warnings': [],
                                      'invalid_groups': [], 'group_counts': {}})
    log = {'render_end': [], 'overlay_start': [], 'overlay_threads': set(), 'fail_for': set()}

    def fake_render(**kw):
        time.sleep(0.3)
        log['render_end'].append(time.monotonic())
        return np.array(kw['source_scene']), {}, 'legacy'

    def fake_overlay(source_row, validation, output_root, *, source_sha=None, **kw):
        log['overlay_start'].append(time.monotonic())
        log['overlay_threads'].add(threading.current_thread().name)
        if source_row['art_name'] in log['fail_for']:
            raise RuntimeError('OVERLAY_NO_SAFE_GROUP: test')
        results = []
        for cm in MEASUREMENTS:
            out = Path(output_root) / cm / Path(source_row['art_name']).stem / f'{source_row["key"]}_{cm}.png'
            out.parent.mkdir(parents=True, exist_ok=True)
            sha = _png(out, (5, 5, 5), size=(1200, 1800))
            results.append({'cm': cm, 'output': str(out), 'output_sha': sha,
                            'manifest': {'group_name': 'G', 'cm': cm, 'src': source_row['key']},
                            'selection': None})
        return {'source': source_row['output'], 'results': results, 'selection_attempts': {},
                'selection_warning': None}

    monkeypatch.setattr(ub, '_render_job_picture', fake_render)
    monkeypatch.setattr(ub, 'process_petek_overlay_source', fake_overlay)
    designs = tmp_path / 'designs'
    designs.mkdir()
    for i in range(1, 4):
        _png(designs / f'Ham{i}.png', (i * 40, 80, 120))
    return {'engine': engine, 'designs': designs, 'state': state, 'log': log}


def _run(w, **kw):
    stored = StoreProfiles(w['state']).load()['stores']
    uids = sorted({k.split(':', 1)[1].split('@', 1)[0] for k in stored['Adeno']['templates']})
    ready = []
    res = w['engine'].run(w['designs'], selected_uids=uids, selected_stores=['Adeno'], group='LOCAL',
                          petek_overlay_enabled=True, output_ready=lambda row: ready.append(dict(row)), **kw)
    return res, ready


def test_overlay_runs_while_renders_continue_and_all_derivatives_are_recorded(world):
    res, ready = _run(world)
    log = world['log']
    assert res['rendered'] == 3
    assert min(log['overlay_start']) < max(log['render_end']), 'overlay render bitmeden başlamadı'
    assert all(name.startswith('v4-overlay') for name in log['overlay_threads'])
    overlay_rows = [r for r in world['engine'].ledger.successful() if r['artifact_kind'] == 'overlay']
    assert len(overlay_rows) == 12
    assert all(len(r['output_sha']) == 64 for r in overlay_rows)
    assert res['overlay']['planned'] == 12 and res['overlay']['successful'] == 12
    assert res['overlay']['failed'] == 0 and res['overlay']['completed'] == 12


def test_only_overlay_derivatives_reach_the_link_queue_never_clean_petek(world):
    _res, ready = _run(world)
    assert len(ready) == 12
    assert all(r.get('artifact_kind') == 'overlay' and r.get('overlay_cm') in MEASUREMENTS for r in ready)
    assert all(len(r['output_sha']) == 64 for r in ready)


def test_one_overlay_failure_does_not_stop_other_designs(world):
    world['log']['fail_for'].add('Ham2.png')
    res, ready = _run(world)
    assert res['rendered'] == 3
    assert res['overlay']['failed'] == 4 and res['overlay']['successful'] == 8
    assert res['overlay']['completed'] == res['overlay']['planned'] == 12
    assert len(ready) == 8
    assert any(e.get('processing_stage') == 'PETEK_OVERLAY' for e in res['errors'])

