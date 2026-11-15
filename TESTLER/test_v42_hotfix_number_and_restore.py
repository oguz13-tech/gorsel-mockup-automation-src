# -*- coding: utf-8 -*-
"""V4.2 hotfix isolation tests; never read or write a real user's runtime."""
from __future__ import annotations
import json
import sqlite3
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from SABLON_V2_MIMARI.core.template_identity import (
    CATEGORY_PREFIXES,
    RENAMER_CATEGORY_PREFIXES,
    TemplateNumberConflictError,
    extract_number,
    collect_reserved_numbers,
)
from SABLON_V2_MIMARI.core.safe_working_revision import (
    WorkingRevisionBlocked,
    recreate_missing_working_png,
    working_png_revision,
)
from SABLON_V2_MIMARI.tools_runner import (
    RENAME_CATEGORIES, rename_images, last_used_template_number,
)


def png_bytes(level=50):
    data = np.full((23, 31, 4), (level, 90, 120, 175), dtype=np.uint8)
    ok, b = cv2.imencode('.png', data)
    assert ok
    return b.tobytes()


def runtime(tmp_path):
    root = tmp_path / 'runtime'
    (root / '2_SABLON_HAVUZU').mkdir(parents=True)
    (root / '2_SABLON_HAVUZU_ORIJINAL_YEDEK').mkdir(parents=True)
    (root / 'SABLON_V2_MIMARI').mkdir(parents=True)
    sqlite3.connect(root / 'SABLON_V2_MIMARI/ayarlar.db').close()
    return root


@pytest.mark.parametrize('category,label', RENAME_CATEGORIES)
def test_all_seven_labels_have_prefix_and_numbers(category, label):
    prefix = RENAMER_CATEGORY_PREFIXES[category]
    assert extract_number(category, f'{prefix}_135.jpg') == 135
    assert extract_number(category, f'{prefix}_135.png') == 135
    assert label


def test_petek_legacy_turkish_name_parsing():
    assert extract_number('06_Petek_Kapama', 'Petek_Dolabı_057.jpeg') == 57
    assert extract_number('06_Petek_Kapama', 'Petek_Dolabi_057.png') == 57
    assert '06_Petek_Kapama' not in CATEGORY_PREFIXES  # legacy editor unchanged


def test_history_combines_existing_files_and_durable_registry(tmp_path):
    root = runtime(tmp_path)
    category = '05_Ocak_Arkasi'
    backup = root / '2_SABLON_HAVUZU_ORIJINAL_YEDEK' / category
    backup.mkdir()
    (backup / 'OcakArkasi_124.jpg').write_bytes(b'old-picture')
    external = tmp_path / 'source'
    external.mkdir()
    (external / 'OcakArkasi_138.webp').write_bytes(b'old-file')
    assert last_used_template_number(root, category, external) == 138
    # In-window numbering starts after the highest visible number.
    (external / 'new.jpg').write_bytes(b'new-image')
    with pytest.raises(TemplateNumberConflictError):
        rename_images([external / 'new.jpg'], 'OcakArkasi_', root, start_number=125)
    assert (external / 'new.jpg').is_file()
    renamed = rename_images([external / 'new.jpg'], 'OcakArkasi_', root, start_number=139)
    assert renamed[0].name == 'OcakArkasi_139.jpg'
    renamed[0].unlink()
    (external / 'OcakArkasi_138.webp').unlink()
    (backup / 'OcakArkasi_124.jpg').unlink()
    # Claimed registry is durable even after old images leave every folder.
    assert last_used_template_number(root, category, external) == 139
    another = external / 'next.jpg'
    another.write_bytes(b'n')
    with pytest.raises(TemplateNumberConflictError):
        rename_images([another], 'OcakArkasi_', root, start_number=139)
    assert another.read_bytes() == b'n'


def test_petek_claim_after_rename_is_durable(tmp_path):
    root = runtime(tmp_path)
    external = tmp_path / 'input'
    external.mkdir()
    source = external / 'photo.jpg'
    source.write_bytes(b'image')
    assert last_used_template_number(root, '06_Petek_Kapama', external) == 0
    new_name = rename_images([source], 'Petek_Dolabi_', root, start_number=15)[0]
    assert new_name.name == 'Petek_Dolabi_015.jpg'
    new_name.unlink()
    assert last_used_template_number(root, '06_Petek_Kapama', external) == 15


def test_restores_missing_with_sha_preserved_and_audit(tmp_path):
    root = runtime(tmp_path)
    category, name = '05_Ocak_Arkasi', 'OcakArkasi_055.png'
    backup_dir = root / '2_SABLON_HAVUZU_ORIJINAL_YEDEK' / category
    backup_dir.mkdir()
    backup = backup_dir / name
    raw = png_bytes(80)
    backup.write_bytes(raw)
    output = root / '2_SABLON_HAVUZU' / category / name
    assert not output.exists()
    with recreate_missing_working_png(root, category, name, backup.read_bytes()):
        assert output.read_bytes() == raw
    assert output.read_bytes() == raw
    assert backup.read_bytes() == raw
    logs = list((root / '_P0_WORKING_REVISIONS').glob('*/manifest.json'))
    assert len(logs) == 1
    record = json.loads(logs[0].read_text('utf-8'))
    assert record['state'] == 'COMMITTED'
    assert record['operation'] == 'CREATE_MISSING_FROM_IMMUTABLE_ORIGINAL'


def test_old_working_revision_rejects_missing(tmp_path):
    root = runtime(tmp_path)
    with pytest.raises(WorkingRevisionBlocked, match='NOT_FOUND'):
        with working_png_revision(root, '05_Ocak_Arkasi', 'OcakArkasi_010.png', png_bytes()):
            pass


def test_conflicting_other_extension_blocks_creation(tmp_path):
    root = runtime(tmp_path)
    category, name = '05_Ocak_Arkasi', 'OcakArkasi_090.png'
    directory = root / '2_SABLON_HAVUZU' / category
    directory.mkdir()
    existing = directory / 'OcakArkasi_090.jpg'
    existing.write_bytes(b'keep-existing')
    with pytest.raises(WorkingRevisionBlocked, match='NAME_ALREADY_EXISTS'):
        with recreate_missing_working_png(root, category, name, png_bytes()):
            pass
    assert existing.read_bytes() == b'keep-existing'
    assert not (directory / name).exists()


def test_existing_png_is_never_overwritten(tmp_path):
    root = runtime(tmp_path)
    category, name = '05_Ocak_Arkasi', 'OcakArkasi_091.png'
    existing = root / '2_SABLON_HAVUZU' / category / name
    existing.parent.mkdir()
    existing.write_bytes(png_bytes(5))
    before = existing.read_bytes()
    with pytest.raises(WorkingRevisionBlocked, match='NAME_ALREADY_EXISTS'):
        with recreate_missing_working_png(root, category, name, png_bytes(19)):
            pass
    assert existing.read_bytes() == before


def test_db_failure_rolls_back_only_new_file(tmp_path):
    root = runtime(tmp_path)
    category, name = '05_Ocak_Arkasi', 'OcakArkasi_105.png'
    file = root / '2_SABLON_HAVUZU' / category / name
    with pytest.raises(RuntimeError, match='DB_ROLLBACK'):
        with recreate_missing_working_png(root, category, name, png_bytes()):
            raise RuntimeError('DB_ROLLBACK')
    assert not file.exists()
    logs = list((root / '_P0_WORKING_REVISIONS').glob('*/manifest.json'))
    assert len(logs) == 1
    assert json.loads(logs[0].read_text('utf-8'))['state'] == 'ROLLED_BACK'


def test_invalid_source_bytes_not_published(tmp_path):
    root = runtime(tmp_path)
    with pytest.raises(WorkingRevisionBlocked, match='INVALID_PNG_BYTES'):
        with recreate_missing_working_png(root, '05_Ocak_Arkasi', 'OcakArkasi_003.png', b'broken'):
            pass
