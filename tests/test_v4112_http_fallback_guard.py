"""V4.11.2: protect the actual HTTP geometry-conflict recovery branch.

This test guards the Python 3 comprehension locals() scope trap, but it is
NOT a substitute for tests/test_v4111_true_artwork_flask_contract.py, which
executes the real Flask endpoint when Flask is installed.
"""
import ast
from pathlib import Path

import cv2
import numpy as np

from MERKEZ.PETEK_V3.petek_render_contract_v1 import (
    ensure_source_vent_mask_consensus, temporary_photo_protected_preview_mask)
from MERKEZ.PETEK_V3.petek_visual_pipeline_vnext import render_petek_visual
from MERKEZ.PETEK_V3 import engine
from tests.test_vnext_petek_dynamic_photo_count import scene_with_count
import pytest


def test_http_error_handler_uses_function_local_variables_not_generator_locals():
    path = Path(__file__).resolve().parents[1]/'SABLON_V2_MIMARI/core/petek_web_v477.py'
    module = ast.parse(path.read_text('utf-8'))
    endpoint = next(n for n in ast.walk(module) if isinstance(n, ast.FunctionDef) and n.name=='preview_artwork')
    generator_locals = [n for n in ast.walk(endpoint) if isinstance(n, ast.GeneratorExp)
                        and any(isinstance(x, ast.Call) and isinstance(x.func, ast.Name)
                        and x.func.id=='locals' for x in ast.walk(n))]
    assert not generator_locals, 'Generator-scoped locals() disables safe 422 recovery'
    # The real Flask test must additionally check HTTP 200, diagnostic status
    # and unchanged files; this static guard alone does not demonstrate that.


def test_same_windows_failure_scene_has_safe_preview_without_approval():
    scene, wrong_mask, quad, _ = scene_with_count(14)
    orig_scene,orig_mask=scene.copy(),wrong_mask.copy()
    with pytest.raises(engine.MaskError,match='PETEK_SOURCE_MASK_VENT_CONFLICT_REVIEW'):
        ensure_source_vent_mask_consensus(scene,wrong_mask,quad)
    safe_mask,proof=temporary_photo_protected_preview_mask(scene,wrong_mask,quad)
    art=np.full((260,360,3),(12,92,230),np.uint8)
    cv2.circle(art,(180,130),75,(222,40,60),-1)
    candidate,qa=render_petek_visual(scene,art,quad,safe_mask,1.1163,
        placement='cover',lighting='strong',material_effect=True,
        slot_mode='off',pink_cleanup=True)
    assert proof['source_vent_count']==14 and proof['source_verified']
    assert proof['not_saved'] and proof['not_approved']
    assert np.all(safe_mask <= wrong_mask)
    assert np.count_nonzero(np.any(candidate!=scene,axis=2))>10000
    assert qa['source_protection_qa']['status']=='PASS'
    assert np.array_equal(scene,orig_scene) and np.array_equal(wrong_mask,orig_mask)
