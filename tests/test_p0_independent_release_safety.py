# -*- coding: utf-8 -*-
"""P0 independent regression: never touches the user's Windows workspace."""
import importlib.util
import json
import os
import sqlite3
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cv2
import numpy as np
import pytest

from SABLON_V2_MIMARI.core.template_identity import (
    TemplateNumberConflictError, validate_number_block,
)
from SABLON_V2_MIMARI.core.safe_working_revision import (
    WorkingRevisionBlocked, working_png_revision, save_preview_only,
)

CAT = "01_Wifi_Kutusu"


def setup_root(root):
    working = root / "2_SABLON_HAVUZU" / CAT
    backup = root / "2_SABLON_HAVUZU_ORIJINAL_YEDEK" / CAT
    working.mkdir(parents=True)
    backup.mkdir(parents=True)
    database = root / "SABLON_V2_MIMARI" / "ayarlar.db"
    database.parent.mkdir(parents=True)
    sqlite3.connect(database).close()
    return working, backup


def sample(seed):
    return np.full((72, 92, 4), (seed, 100, 200, 110), dtype=np.uint8)


def png_file(path, image):
    ok, buf = cv2.imencode(".png", image)
    assert ok
    path.write_bytes(buf.tobytes())


def test_high_water_rejects_disappeared_identity():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        working, backup = setup_root(root)
        png_file(backup / "Wifi_Kutusu_137.png", sample(1))
        for number in (5, 135, 137):
            with pytest.raises(TemplateNumberConflictError) as caught:
                validate_number_block(root, CAT, number, 1)
            assert caught.value.suggested_start == 138
        assert validate_number_block(root, CAT, 138, 3) == {138, 139, 140}


def test_safe_working_revision_snapshots_and_rolls_back():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        working, backup = setup_root(root)
        p = working / "Wifi_Kutusu_001.png"
        o = backup / "Wifi_Kutusu_001.png"
        png_file(p, sample(1)); png_file(o, sample(3))
        old = p.read_bytes(); immutable = o.read_bytes()
        with working_png_revision(root, CAT, p.name, sample(50)) as claim:
            assert p.read_bytes() != old
            assert claim["before_sha256"] != claim["after_sha256"]
        assert o.read_bytes() == immutable
        new = p.read_bytes()
        with pytest.raises(RuntimeError, match="SIMULATED_DB_FAIL"):
            with working_png_revision(root, CAT, p.name, sample(70)):
                raise RuntimeError("SIMULATED_DB_FAIL")
        assert p.read_bytes() == new
        assert o.read_bytes() == immutable
        revs = [d for d in (root / "_P0_WORKING_REVISIONS").iterdir() if d.is_dir() and d.name != "locks"]
        assert len(revs) == 2
        assert {json.loads((d / "manifest.json").read_text())["state"] for d in revs} == {"COMMITTED", "ROLLED_BACK"}


def test_preview_is_preview_only():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        working, backup = setup_root(root)
        staging = root / "_ONIZLEME_SABLONLAR" / CAT
        staging.mkdir(parents=True)
        path = working / "Wifi_Kutusu_001.png"
        png_file(path, sample(7))
        raw = path.read_bytes()
        preview = save_preview_only(root, CAT, path.name, sample(22))
        assert preview.name.endswith("-beyazlatilmis-onizleme.png")
        assert preview.is_file()
        assert path.read_bytes() == raw
        save_preview_only(root, CAT, path.name, sample(23))
        assert path.read_bytes() == raw


def test_missing_working_and_originals_are_immutable():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        working, backup = setup_root(root)
        backup.joinpath("Wifi_Kutusu_001.png").write_bytes(b"ORIGINAL")
        with pytest.raises(WorkingRevisionBlocked):
            with working_png_revision(root, CAT, "Wifi_Kutusu_001.png", sample(5)):
                pass
        assert backup.joinpath("Wifi_Kutusu_001.png").read_bytes() == b"ORIGINAL"


def test_parallel_namespaces_and_durable_number_claims():
    # Different folders must not both receive the same template number.
    import importlib
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        setup_root(root)
        from SABLON_V2_MIMARI.tools_runner import rename_images
        first = root / "input-a"; first.mkdir()
        second = root / "input-b"; second.mkdir()
        a = first / "art1.jpg"; a.write_bytes(b"A")
        b = second / "art2.jpg"; b.write_bytes(b"B")
        def go(file):
            try:
                return rename_images([file], "Wifi_Kutusu_", runtime_root=root, start_number=300)
            except TemplateNumberConflictError:
                return None
        with ThreadPoolExecutor(max_workers=2) as ex:
            r = list(ex.map(go, [a, b]))
        assert len([x for x in r if x]) == 1
        assert len([x for x in r if x is None]) == 1
        assert sum(int(p.name == "Wifi_Kutusu_300.jpg") for p in (first.iterdir())) + sum(int(p.name == "Wifi_Kutusu_300.jpg") for p in (second.iterdir())) == 1
        conn = sqlite3.connect(root / "SABLON_V2_MIMARI" / "ayarlar.db")
        try:
            rows = conn.execute("SELECT template_number FROM template_number_registry WHERE category=?", (CAT,)).fetchall()
        finally:
            conn.close()
        assert rows == [(300,)]


def test_legacy_migration_fails_closed():
    path = Path(__file__).parents[1] / "99_SISTEM_MOTORLARI_VE_KODLAR" / "SISTEM_MOTORU" / "migrate_to_png.py"
    spec = importlib.util.spec_from_file_location("test_legacy_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / "old.jpg"
        source.write_bytes(b"KEEP")
        with pytest.raises(module.UnsafeLegacyMigrationBlocked):
            module.convert_file(source, Path(directory) / "new.png")
        assert source.read_bytes() == b"KEEP"


def test_cleaner_read_only_when_missing():
    path = Path(__file__).parents[1] / "99_SISTEM_MOTORLARI_VE_KODLAR" / "SISTEM_MOTORU" / "temizlik_motoru.py"
    spec = importlib.util.spec_from_file_location("test_cleaner", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        cfg = root / "ayarlar.json"
        raw = json.dumps({"kategoriler": {CAT: {"sablonlar": {"Wifi_Kutusu_005.png": {"manually_verified": True}}}}}).encode()
        cfg.write_bytes(raw)
        mod.AYARLAR_PATH = cfg
        mod.SABLON_DIR = root / "2_SABLON_HAVUZU"
        result = mod.clean_ayarlar()
        assert result["mutated"] is False
        assert len(result["missing"]) == 1
        assert cfg.read_bytes() == raw
