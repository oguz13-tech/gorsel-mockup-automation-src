# -*- coding: utf-8 -*-
"""Regression against BOTH legacy HTTP handlers in a fake runtime.

No web server, user Windows files, ports or real SQLite databases are touched.
"""
import contextlib
import importlib.util
import io
import json
import logging
import os
import sys
import types
import tempfile
from pathlib import Path

import cv2
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
CAT = "01_Wifi_Kutusu"
HANDLERS = ["SABLON_DUZELTICI.py", "SABLON_V2_MIMARI/core/vision.py"]


def image(value):
    return np.full((40, 60, 4), (value, 25, 35, 110), dtype=np.uint8)


def png(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(".png", data)
    assert ok
    path.write_bytes(encoded.tobytes())


def load_handler(monkeypatch, root, name):
    monkeypatch.setenv("MOCKUP_RUNTIME_WORKSPACE", str(root))
    path = ROOT / name
    spec = importlib.util.spec_from_file_location("p0_test_handler_" + name.replace("/", "_").replace(".", "_"), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # Legacy modules open a FileHandler during import. Windows locks open
    # log files even after a unit test exits; close immediately in this
    # HTTP-handler mock to avoid WinError 32 on TemporaryDirectory cleanup.
    for handler in list(mod.logger.handlers):
        if isinstance(handler, logging.FileHandler):
            mod.logger.removeHandler(handler)
            handler.close()
    mod.BASE_DIR = str(root)
    mod.YEDEK_IMG_DIR = str(root / "2_SABLON_HAVUZU_ORIJINAL_YEDEK")
    mod.AYARLAR_PATH = str(root / "99_SISTEM_MOTORLARI_VE_KODLAR" / "SISTEM_MOTORU" / "ayarlar.json")
    fake_whitener = types.ModuleType("sablon_beyazlatma_motoru")
    fake_whitener.imwrite_unicode = lambda *args, **kwargs: False
    fake_whitener.imread_unicode = lambda path: cv2.imdecode(
        np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_UNCHANGED
    )
    fake_whitener.whiten_canvas = lambda img, conf, is_frameless=False: image(91)
    monkeypatch.setitem(sys.modules, "sablon_beyazlatma_motoru", fake_whitener)
    return mod


class FakeRequest:
    def __init__(self, payload=None, category=CAT, template="Wifi_Kutusu_001.png"):
        buf = json.dumps(payload or {}).encode("utf-8")
        self.rfile = io.BytesIO(buf)
        self.wfile = io.BytesIO()
        self.headers = {
            "Content-Length": str(len(buf)),
            "X-Active-Category": category,
            "X-Active-Template": template,
        }
        self.status = None
    def send_response(self, value):
        self.status = value
    def send_header(self, name, value):
        pass
    def end_headers(self):
        pass
    def response(self):
        return json.loads(self.wfile.getvalue().decode("utf-8"))


def fixture_root(root):
    name = "Wifi_Kutusu_001.png"
    work = root / "2_SABLON_HAVUZU" / CAT / name
    backup = root / "2_SABLON_HAVUZU_ORIJINAL_YEDEK" / CAT / name
    png(work, image(11)); png(backup, image(22))
    config = root / "99_SISTEM_MOTORLARI_VE_KODLAR" / "SISTEM_MOTORU" / "ayarlar.json"
    config.parent.mkdir(parents=True)
    initial = {"kategoriler": {CAT: {"sablonlar": {name: {"koseler": [[1,1],[2,1],[2,2],[1,2]]}}}}}
    config.write_text(json.dumps(initial), encoding="utf-8")
    (root / "_ONIZLEME_SABLONLAR" / CAT).mkdir(parents=True)
    return work, backup, config, initial


@pytest.mark.parametrize("name", HANDLERS)
def test_instant_whiten_is_preview_only_and_no_false_success(monkeypatch, name):
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        work, backup, config, payload = fixture_root(root)
        mod = load_handler(monkeypatch, root, name)
        old_work, old_backup = work.read_bytes(), backup.read_bytes()
        request = FakeRequest(payload)
        mod.MockupHandler._handle_api_anlik_beyazlat(request)
        assert request.status == 200
        assert request.response()["preview_only"] is True
        assert (root / "_ONIZLEME_SABLONLAR" / CAT / "Wifi_Kutusu_001-beyazlatilmis-onizleme.png").is_file()
        assert work.read_bytes() == old_work and backup.read_bytes() == old_backup


@pytest.mark.parametrize("name", HANDLERS)
def test_settings_update_publishes_only_working_copy(monkeypatch, name):
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        work, backup, config, payload = fixture_root(root)
        mod = load_handler(monkeypatch, root, name)
        original = backup.read_bytes()
        request = FakeRequest(payload)
        mod.MockupHandler._handle_api_ayarlar(request)
        assert request.status == 200
        assert request.response()["success"] is True
        assert work.read_bytes() != original
        assert backup.read_bytes() == original
        assert list((root / "_P0_WORKING_REVISIONS").glob("*/working_before.png"))


@pytest.mark.parametrize("name", HANDLERS)
def test_settings_failure_rolls_back_working(monkeypatch, name):
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        work, backup, config, payload = fixture_root(root)
        mod = load_handler(monkeypatch, root, name)
        initial_work, initial_backup, initial_config = work.read_bytes(), backup.read_bytes(), config.read_bytes()
        @contextlib.contextmanager
        def bad_lock(*args, **kwargs):
            raise OSError("SIMULATED_SETTINGS_LOCK_FAILURE")
            yield
        monkeypatch.setattr(mod, "acquire_os_lock", bad_lock)
        request = FakeRequest(payload)
        mod.MockupHandler._handle_api_ayarlar(request)
        assert request.status == 500
        assert request.response()["success"] is False
        assert work.read_bytes() == initial_work
        assert backup.read_bytes() == initial_backup
        assert config.read_bytes() == initial_config


@pytest.mark.parametrize("name", HANDLERS)
def test_restore_preserves_original_alpha(monkeypatch, name):
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        work, backup, config, payload = fixture_root(root)
        mod = load_handler(monkeypatch, root, name)
        old_backup = backup.read_bytes()
        request = FakeRequest()
        mod.MockupHandler._handle_api_orijinal_yukle(request)
        assert request.status == 200
        actual = cv2.imdecode(np.frombuffer(work.read_bytes(), dtype=np.uint8), cv2.IMREAD_UNCHANGED)
        assert actual.shape[2] == 4 and np.all(actual[:,:,3] == 110)
        assert backup.read_bytes() == old_backup


@pytest.mark.parametrize("name", HANDLERS)
def test_restore_from_trash_rejects_existing_name(monkeypatch, name):
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        work, backup, config, payload = fixture_root(root)
        mod = load_handler(monkeypatch, root, name)
        trash = root / "_COP_KUTUSU"
        trash.mkdir()
        trashed = trash / "old.png"
        png(trashed, image(33))
        metadata = {"kategori": CAT, "sablon": work.name, "stem": work.stem,
                    "cop_png": str(trashed), "conf": {"review_status": "APPROVED"}}
        (trash / "999.meta.json").write_text(json.dumps(metadata))
        old_work, old_trash, old_backup = work.read_bytes(), trashed.read_bytes(), backup.read_bytes()
        request = FakeRequest()
        mod.MockupHandler._handle_api_sablon_sil_geri_al(request)
        assert request.status >= 400
        assert request.response()["success"] is False
        assert work.read_bytes() == old_work
        assert trashed.read_bytes() == old_trash
        assert backup.read_bytes() == old_backup


@pytest.mark.parametrize("name", HANDLERS)
def test_bulk_returns_conflict_for_failed_revisions(monkeypatch, name):
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        work, backup, config, payload = fixture_root(root)
        mod = load_handler(monkeypatch, root, name)
        work.unlink()
        original = backup.read_bytes()
        request = FakeRequest({"kategori": CAT}, category="", template="")
        mod.MockupHandler._handle_api_tumunu_beyazlat(request)
        assert request.status == 409
        assert request.response()["success"] is False
        assert backup.read_bytes() == original
