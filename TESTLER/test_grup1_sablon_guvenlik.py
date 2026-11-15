"""Group 1 acceptance tests: synthetic assets only; NEVER touch user's live data."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import time
from unittest.mock import patch

import cv2
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'MERKEZ'))
from inbox_auto_v42 import CATEGORIES, DONE, CONFLICT, REVIEW, AutoInboxWatcher, ingest_one
from SABLON_V2_MIMARI.core.template_intelligence import GeometryValidator


def write_png(p: Path, color=(25, 70, 145)) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    image = np.full((160, 220, 3), color, dtype=np.uint8)
    ok, data = cv2.imencode('.png', image)
    assert ok
    p.write_bytes(data.tobytes())
    return p


def digest(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


@pytest.fixture
def store(tmp_path):
    db_path = tmp_path / 'SABLON_V2_MIMARI' / 'ayarlar.db'
    db_path.parent.mkdir(parents=True)
    con = sqlite3.connect(db_path)
    try:
        with con:
            con.execute('CREATE TABLE categories (id TEXT PRIMARY KEY, label TEXT)')
            con.execute('CREATE TABLE templates (category_id TEXT, filename TEXT, data TEXT, PRIMARY KEY(category_id,filename))')
            con.execute('CREATE TABLE template_profiles (template_uid TEXT PRIMARY KEY, category TEXT, review_status TEXT, manually_verified INTEGER, surface_quad TEXT)')
            for cat in CATEGORIES:
                con.execute('INSERT INTO categories VALUES (?,?)', (cat, cat))
    finally:
        # sqlite3.Connection.__exit__ commits, but DOES NOT close the handle.
        # Windows cannot unlink the fixture DB while the generator keeps con
        # alive. Close it before yielding the path (real runtime untouched).
        con.close()
    with patch.dict(os.environ, {'LOCALAPPDATA': str(tmp_path / 'LOCAL_STATE')}):
        yield tmp_path


def paths(root: Path, cat: str, filename: str):
    physical = 'Petek_Dolabi' if cat == '06_Petek_Kapama' else cat
    inbox = root / 'YENI-BOS MOCKUP SABLON HAVUZU' / physical / filename
    working = root / '2_SABLON_HAVUZU' / physical / filename
    archive = root / '2_SABLON_HAVUZU_ORIJINAL_YEDEK' / physical / filename
    return inbox, working, archive


@pytest.mark.parametrize('category', CATEGORIES)
def test_new_file_all_seven_categories(store, category):
    inbox, working, archive = paths(store, category, 'fresh.png')
    write_png(inbox)
    original_digest = digest(inbox)
    result = ingest_one(store, category, inbox)
    assert result['status'] == 'IMPORTED_NEEDS_CORNERS'
    assert digest(working) == digest(archive) == original_digest
    assert (inbox.parent / REVIEW / inbox.name).exists()
    with sqlite3.connect(store / 'SABLON_V2_MIMARI' / 'ayarlar.db') as con:
        count = con.execute('SELECT COUNT(*) FROM templates WHERE category_id=?', (category,)).fetchone()[0]
        if category == '06_Petek_Kapama':
            assert count == 0, 'PETEK must not be automatically approved/registered in six-category schema'
        else:
            assert count == 1
            content = json.loads(con.execute('SELECT data FROM templates WHERE category_id=?', (category,)).fetchone()[0])
            assert content['review_status'] == 'REVIEW_REQUIRED'
            assert not content['koseler']


def test_exact_duplicate_is_segregated_without_overwrite(store):
    cat = CATEGORIES[0]
    inbox, working, archive = paths(store, cat, 'Wifi_Kutusu_175.png')
    write_png(working)
    write_png(archive)
    before = digest(working)
    write_png(inbox)
    result = ingest_one(store, cat, inbox)
    assert result['status'] == 'ALREADY_WORKING'
    assert digest(working) == before and digest(archive) == before
    assert (inbox.parent / DONE / inbox.name).exists()


def test_same_stem_different_content_is_manual_review(store):
    cat = CATEGORIES[0]
    inbox, working, archive = paths(store, cat, 'Wifi_Kutusu_175.jpeg')
    working = working.with_suffix('.png')
    archive = archive.with_suffix('.png')
    write_png(working, (100, 100, 100))
    write_png(archive, (100, 100, 100))
    write_png(inbox, (12, 100, 190))
    old = digest(working)
    result = ingest_one(store, cat, inbox)
    assert result['status'] == 'CONFLICT_REVIEW'
    assert digest(working) == old and digest(archive) == old
    assert (inbox.parent / CONFLICT / inbox.name).exists()


def test_restores_missing_working_without_overwriting_backup(store):
    cat = CATEGORIES[0]
    inbox, working, archive = paths(store, cat, 'Wifi_Kutusu_175.png')
    write_png(archive)
    write_png(inbox)
    before = digest(archive)
    result = ingest_one(store, cat, inbox)
    assert result['status'] == 'IMPORTED_NEEDS_CORNERS'
    assert digest(working) == digest(archive) == before


def test_invalid_image_quarantined_without_registration(store):
    cat = CATEGORIES[0]
    inbox, working, archive = paths(store, cat, 'tampered.png')
    inbox.parent.mkdir(parents=True)
    inbox.write_bytes(b'NOT AN IMAGE')
    result = ingest_one(store, cat, inbox)
    assert result['status'] == 'INVALID_IMAGE_REVIEW'
    assert not working.exists() and not archive.exists()
    assert (inbox.parent / CONFLICT / inbox.name).exists()


def test_source_or_approved_geometry_never_auto_modified(store):
    cat = CATEGORIES[0]
    inbox, working, archive = paths(store, cat, 'keep.png')
    write_png(working)
    write_png(archive)
    db = store / 'SABLON_V2_MIMARI' / 'ayarlar.db'
    profile = '[[2,3],[4,3],[4,5],[2,5]]'
    with sqlite3.connect(db) as con:
        con.execute('INSERT INTO template_profiles VALUES(?,?,?,?,?)', ('keep', cat, 'APPROVED', 1, profile))
        con.execute('INSERT INTO templates VALUES (?,?,?)', (cat, 'keep.png', json.dumps({'koseler': json.loads(profile)})))
    write_png(inbox)
    before = digest(working)
    assert ingest_one(store, cat, inbox)['status'] == 'ALREADY_WORKING'
    assert digest(working) == before
    with sqlite3.connect(db) as con:
        assert con.execute('SELECT surface_quad FROM template_profiles').fetchone()[0] == profile
        assert con.execute('SELECT data FROM templates').fetchone()[0] == json.dumps({'koseler': json.loads(profile)})


def test_missing_database_fails_without_moving_file(store):
    cat = CATEGORIES[0]
    inbox, working, archive = paths(store, cat, 'new.png')
    write_png(inbox)
    (store / 'SABLON_V2_MIMARI' / 'ayarlar.db').unlink()
    with pytest.raises(FileNotFoundError):
        ingest_one(store, cat, inbox)
    assert inbox.exists() and not working.exists() and not archive.exists()


def test_automatic_watcher_waits_for_stable_bytes(store):
    cat = CATEGORIES[0]
    inbox, working, archive = paths(store, cat, 'stable.png')
    write_png(inbox)
    watcher = AutoInboxWatcher(store, interval=1)
    assert watcher.sweep() == []
    os.utime(inbox, (time.time()-6, time.time()-6))
    assert watcher.sweep() == []
    assert watcher.sweep()[0]['status'] == 'IMPORTED_NEEDS_CORNERS'
    assert working.exists()


def test_manual_small_quad_allowed_but_invalid_rejected():
    small = np.float32([[200, 220], [285, 220], [285, 285], [200, 285]])
    assert not GeometryValidator.is_valid_quad(small, 1600, 1200)[0]
    assert GeometryValidator.is_valid_quad(small, 1600, 1200, manual=True)[0]
    invalid = np.float32([[200, 220], [200, 220], [285, 285], [200, 285]])
    assert not GeometryValidator.is_valid_quad(invalid, 1600, 1200, manual=True)[0]


def test_bulk_approval_cannot_bypass_occlusion_and_stale_source():
    js=(ROOT/'SABLON_V2_MIMARI'/'static/js/main.js').read_text('utf-8')
    api=(ROOT/'SABLON_V2_MIMARI'/'app.py').read_text('utf-8')
    assert 'function bulkApproveSelected()' in js
    assert 'bulk_approval:true, occlusion_reviewed:false' in js
    assert 'if bulk_approval and row and bool(row["has_occlusion"])' in api
    assert 'if bulk_approval:' in api and 'STALE_SOURCE_CHANGED' in api
    assert 'bulkApproveButton' in (ROOT/'SABLON_V2_MIMARI'/'templates/index.html').read_text('utf-8')


def test_archived_same_stem_other_extension_requires_review(store):
    cat = CATEGORIES[0]
    inbox, working, archive = paths(store, cat, 'Wifi_Kutusu_175.jpeg')
    backup_png = archive.with_suffix('.png')
    write_png(backup_png)
    inbox.parent.mkdir(parents=True, exist_ok=True)
    inbox.write_bytes(backup_png.read_bytes())  # same bytes, different extension
    assert ingest_one(store, cat, inbox)['status'] == 'CONFLICT_REVIEW'
    assert not working.exists()
    assert digest(backup_png) == digest(inbox.parent / CONFLICT / inbox.name)


def test_tiny_manually_approved_legacy_quad_can_be_rendered(tmp_path):
    # Old PETEK auto-candidate cutoff is intentionally NOT used for legacy
    # human-reviewed geometry inside large room photographs.
    import sys
    sys.path.insert(0, str(ROOT / 'MERKEZ'))
    from URETIM_V4.manual_geometry import validated_legacy_manual_quad
    from URETIM_V4.unified_batch import _build_legacy_category_mask, _render_legacy_six_cover
    from PETEK_V3 import engine as petek_engine
    scene_path = write_png(tmp_path / 'living-room.png', (168, 180, 195))
    art_path = write_png(tmp_path / 'art.png', (25, 175, 78))
    scene = cv2.imread(str(scene_path))
    h, w = scene.shape[:2]
    # 22x16 is under 1.8% of 160x220 but has nondegenerate 4 corners.
    quad = [[105., 100.], [135., 100.], [135., 120.], [105., 120.]]
    with pytest.raises(petek_engine.MaskError):
        petek_engine.validated_quad(quad, scene.shape)
    q = validated_legacy_manual_quad(quad, scene.shape)
    mask = _build_legacy_category_mask(scene, quad, {})
    out, qa = _render_legacy_six_cover(scene_path, art_path, quad, mask, 1.5, marketplace=False)
    assert out.shape == scene.shape
    assert np.array_equal(out[mask == 0], scene[mask == 0])
    assert qa['source_pixels_unchanged']
