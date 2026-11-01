"""V4.11.1: a geometry conflict must not masquerade as a successful source preview.

Run with real PETEK renderer and synthetic photo-masks; no Registry or user data.
"""
import cv2
import numpy as np
import pytest

from MERKEZ.PETEK_V3 import engine
from MERKEZ.PETEK_V3.petek_render_contract_v1 import (
    temporary_photo_protected_preview_mask, ensure_source_vent_mask_consensus)
from MERKEZ.PETEK_V3.petek_visual_pipeline_vnext import render_petek_visual
from tests.test_vnext_petek_dynamic_photo_count import scene_with_count


@pytest.mark.parametrize('count', [13, 14, 15, 16])
def test_conflicting_mask_real_artwork_preview_uses_unsaved_protective_mask(count):
    source, wrong_mask, quad, _ = scene_with_count(count)
    original_photo, original_mask = source.copy(), wrong_mask.copy()
    with pytest.raises(engine.MaskError, match='PETEK_SOURCE_MASK_VENT_CONFLICT_REVIEW'):
        ensure_source_vent_mask_consensus(source, wrong_mask, quad)

    draft, qa = temporary_photo_protected_preview_mask(source, wrong_mask, quad)
    assert qa['source_verified'] and qa['source_vent_count'] == count
    assert qa['removed_unsafe_print_pixels'] > 0
    assert not np.any((draft > 0) & (wrong_mask == 0))
    art = np.full((300, 440, 3), (14, 95, 242), np.uint8)
    cv2.rectangle(art, (70, 55), (320, 240), (226, 41, 70), -1)
    rendered, render_qa = render_petek_visual(
        source, art, quad, draft, 1.1163,
        lighting='off', material_effect=False,
        slot_mode='off', pink_cleanup=False)
    assert render_qa['source_protection_qa']['status'] == 'PASS'
    assert np.count_nonzero(np.any(rendered != source, axis=2) & (draft > 0)) > 10_000
    assert np.array_equal(rendered[draft == 0], source[draft == 0])
    assert np.array_equal(source, original_photo)
    assert np.array_equal(wrong_mask, original_mask)


def test_source_without_confirmed_vents_cannot_be_falsely_labeled_as_real_artwork():
    h, w = 520, 700
    scene = np.full((h, w, 3), (255, 0, 255), np.uint8)
    mask = np.zeros((h, w), np.uint8)
    mask[50:475, 90:615] = 255
    quad = np.float32([[90, 50], [614, 50], [614, 474], [90, 474]])
    old_scene, old_mask = scene.copy(), mask.copy()
    with pytest.raises(engine.MaskError, match='PETEK_DIAGNOSTIC_PHYSICAL_VENTS_UNCERTAIN'):
        temporary_photo_protected_preview_mask(scene, mask, quad)
    assert np.array_equal(scene, old_scene) and np.array_equal(mask, old_mask)


def test_browser_cannot_hide_mask_and_label_plain_source_as_artwork():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    js = (root/'SABLON_V2_MIMARI/static/js/petek_editor_v477.js').read_text('utf-8')
    web = (root/'SABLON_V2_MIMARI/core/petek_web_v477.py').read_text('utf-8')
    assert 'data.diagnostic_artwork_applied && data.preview' in js
    assert 's.preview=null;s.previewMode=false' in js
    assert "'diagnostic_artwork_applied':True" in web
    assert "'diagnostic_artwork_applied':False" in web
    assert "'production_allowed':False" in web
