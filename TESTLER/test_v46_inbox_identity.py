"""Do not reuse historically approved or deleted template identities."""
import hashlib
import sqlite3
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "MERKEZ"))
from inbox_auto_v42 import CATEGORIES, CONFLICT, historical_db_identity_reserved, ingest_one


def make_root(tmp_path, category):
    db = tmp_path / "SABLON_V2_MIMARI" / "ayarlar.db"
    db.parent.mkdir(parents=True)
    with sqlite3.connect(db) as con:
        con.execute("CREATE TABLE templates (category_id TEXT, filename TEXT, data TEXT)")
        con.execute("CREATE TABLE template_profiles (template_uid TEXT, category TEXT, source_relative_path TEXT, review_status TEXT)")
        con.execute("CREATE TABLE template_number_registry (category TEXT, canonical_name TEXT)")
    inbox = tmp_path / "YENI-BOS MOCKUP SABLON HAVUZU" / category
    inbox.mkdir(parents=True)
    image = np.full((160, 220, 3), (255, 0, 255), np.uint8)
    ok, raw = cv2.imencode(".png", image)
    assert ok
    source = inbox / "Wifi_Kutusu_175.png"
    source.write_bytes(raw.tobytes())
    return db, source


@pytest.mark.parametrize("insert", [
    "INSERT INTO templates VALUES ('01_Wifi_Kutusu','Wifi_Kutusu_175.jpeg','{}')",
    "INSERT INTO template_profiles VALUES ('01_Wifi_Kutusu_Wifi_Kutusu_175.png','01_Wifi_Kutusu','01_Wifi_Kutusu/Wifi_Kutusu_175.png','APPROVED')",
    "INSERT INTO template_number_registry VALUES ('01_Wifi_Kutusu','Wifi_Kutusu_175.jpeg')",
])
def test_historical_identity_without_images_quarantined(tmp_path, insert):
    category = CATEGORIES[0]
    db, source = make_root(tmp_path, category)
    with sqlite3.connect(db) as con:
        con.execute(insert)
    db_before = hashlib.sha256(db.read_bytes()).hexdigest()
    assert historical_db_identity_reserved(tmp_path, category, source.name)
    response = ingest_one(tmp_path, category, source)
    assert response["status"] == "CONFLICT_REVIEW"
    assert response["reason"] == "DB_HISTORICAL_IDENTITY_RESERVED"
    assert (source.parent / CONFLICT / source.name).is_file()
    assert not (tmp_path / "2_SABLON_HAVUZU" / category / source.name).exists()
    assert not (tmp_path / "2_SABLON_HAVUZU_ORIJINAL_YEDEK" / category / source.name).exists()
    assert hashlib.sha256(db.read_bytes()).hexdigest() == db_before


def test_new_identity_allowed(tmp_path):
    db, source = make_root(tmp_path, CATEGORIES[0])
    assert historical_db_identity_reserved(tmp_path, CATEGORIES[0], source.name) is False


def test_bad_db_schema_fails_closed(tmp_path):
    db, source = make_root(tmp_path, CATEGORIES[0])
    with sqlite3.connect(db) as con:
        con.execute("DROP TABLE template_profiles")
    with pytest.raises(RuntimeError, match="UNRECOGNIZED_SCHEMA"):
        ingest_one(tmp_path, CATEGORIES[0], source)
    assert source.is_file()
