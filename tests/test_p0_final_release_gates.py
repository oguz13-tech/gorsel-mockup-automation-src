# -*- coding: utf-8 -*-
"""Last release blockers: SQLite imports and receipt intake are non-destructive."""
import hashlib
import importlib
import json
import sqlite3
import tempfile
from pathlib import Path

import pytest
from SABLON_V2_MIMARI.core.db import inspect_startup_schema
from SABLON_V2_MIMARI.tools_runner import stage_incoming_safely

CATEGORY = "01_Wifi_Kutusu"


def test_readonly_startup_audit_does_not_create_or_upgrade_database():
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "ayarlar.db"
        assert inspect_startup_schema(path)["ready"] is False
        assert not path.exists()
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE template_profiles(template_uid TEXT UNIQUE)")
        conn.commit(); conn.close()
        original = path.read_bytes()
        report = inspect_startup_schema(path)
        assert report["ready"] is False
        assert report["migration_required"] is True
        assert path.read_bytes() == original


def test_intake_separates_same_named_external_sources_without_modification():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "FAKE_RUNTIME"
        reg = root / "SABLON_V2_MIMARI" / "ayarlar.db"
        reg.parent.mkdir(parents=True)
        sqlite3.connect(reg).close()
        a = Path(td) / "A" / "Wifi_Kutusu_005.jpg"
        b = Path(td) / "B" / "Wifi_Kutusu_005.jpg"
        a.parent.mkdir(); b.parent.mkdir()
        a.write_bytes(b"UNIQUE_CONTENT_A")
        b.write_bytes(b"UNIQUE_CONTENT_B")
        before = [hashlib.sha256(p.read_bytes()).hexdigest() for p in (a,b)]
        result = stage_incoming_safely([a,b], CATEGORY, runtime_root=root)
        assert result["staged_count"] == 2
        assert len({item["staged_name"] for item in result["receipts"]}) == 2
        stage = root / "YENI-BOS MOCKUP SABLON HAVUZU" / CATEGORY
        for entry in result["receipts"]:
            staged_file = stage / entry["staged_name"]
            assert staged_file.is_file()
            assert hashlib.sha256(staged_file.read_bytes()).hexdigest() == entry["sha256"]
            assert (root / "SABLON_V2_MIMARI" / "recovery" / "intake_receipts"
                    / (entry["receipt_id"] + ".json")).is_file()
        assert [hashlib.sha256(p.read_bytes()).hexdigest() for p in (a,b)] == before
        assert not list(stage.glob("*.p0tmp"))


def test_stage_rejects_symlink_and_runtime_existing_sources():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "FAKE_RUNTIME"
        reg = root / "SABLON_V2_MIMARI" / "ayarlar.db"
        reg.parent.mkdir(parents=True)
        sqlite3.connect(reg).close()
        inner = root / "source.jpg"
        inner.write_bytes(b"DO_NOT_REINGEST")
        with pytest.raises(ValueError, match="ONLY_EXTERNAL"):
            stage_incoming_safely([inner], CATEGORY, root)
        external = Path(td) / "external.jpg"
        external.write_bytes(b"EXTERNAL")
        link = Path(td) / "link.jpg"
        try:
            link.symlink_to(external)
        except (OSError, NotImplementedError):
            return
        with pytest.raises(ValueError, match="SYMLINK"):
            stage_incoming_safely([link], CATEGORY, root)
