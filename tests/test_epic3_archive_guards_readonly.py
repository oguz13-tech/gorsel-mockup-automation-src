"""Sentetik çalışma alanında EPIC-3 arşiv/kimlik güvenliği regresyonları.

Gerçek runtime workspace'e, görsellere veya veritabanına dokunmaz.
"""
import json
import sqlite3
from contextlib import closing
import tempfile
import unicodedata
import unittest
from pathlib import Path

from SABLON_V2_MIMARI.core.template_identity import (
    TemplateIdentityConflictError,
    TemplateNumberConflictError,
    _connect_read_only,
    assert_identity_available,
    canonical_identity,
    collect_identity_conflicts,
    collect_reserved_numbers,
    ensure_registry_table,
    reserve_number,
    validate_number_block,
)

CATEGORY = "01_Wifi_Kutusu"
ALT_CATEGORY = "03_Ahsap_Tablo"


def make_db(root: Path, *, with_registry=False):
    target = root / "SABLON_V2_MIMARI" / "ayarlar.db"
    target.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(str(target))) as conn, conn:
        conn.execute(
            "CREATE TABLE templates(category_id TEXT, filename TEXT)"
        )
        conn.execute(
            "CREATE TABLE template_profiles("
            "category TEXT, source_relative_path TEXT, template_uid TEXT)"
        )
        if with_registry:
            conn.execute(
                "CREATE TABLE template_number_registry("
                "category TEXT, template_number INTEGER, canonical_name TEXT)"
            )
    return target


def names_in(db: Path):
    with closing(sqlite3.connect(str(db))) as conn, conn:
        return tuple(sorted(row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )))


class TestEpic3ArchiveGuards(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def path(self, base, category, filename, body=b"image"):
        directory = self.root / base / category
        directory.mkdir(parents=True, exist_ok=True)
        dest = directory / filename
        dest.write_bytes(body)
        return dest

    def test_01_readonly_identity_does_not_bootstrap_legacy_db(self):
        db = make_db(self.root)
        with closing(sqlite3.connect(str(db))) as conn, conn:
            conn.execute(
                "INSERT INTO templates VALUES (?, ?)",
                (CATEGORY, "Wifi_Kutusu_001.png"),
            )
        old_data, old_schema = db.read_bytes(), names_in(db)
        report = collect_identity_conflicts(
            self.root, CATEGORY, "Wifi_Kutusu_001.jpeg"
        )
        self.assertTrue(report["conflict"])
        self.assertIn("DB_ACTIVE", [x["location"] for x in report["matches"]])
        self.assertEqual(names_in(db), old_schema)
        self.assertEqual(db.read_bytes(), old_data)
        self.assertNotIn("template_number_registry", names_in(db))

    def test_02_readonly_reserved_numbers_does_not_bootstrap_db(self):
        db = make_db(self.root)
        with closing(sqlite3.connect(str(db))) as conn, conn:
            conn.execute(
                "INSERT INTO templates VALUES (?, ?)",
                (CATEGORY, "Wifi_Kutusu_042.png"),
            )
        old_data = db.read_bytes()
        found = collect_reserved_numbers(self.root, CATEGORY)
        self.assertIn(42, found)
        self.assertEqual(db.read_bytes(), old_data)
        self.assertNotIn("template_number_registry", names_in(db))

    def test_03_legacy_profile_is_respected_without_registry(self):
        db = make_db(self.root)
        with closing(sqlite3.connect(str(db))) as conn, conn:
            conn.execute(
                "INSERT INTO template_profiles VALUES (?, ?, ?)",
                (CATEGORY, "01_Wifi_Kutusu/Wifi_Kutusu_017.jpeg", ""),
            )
        before = db.read_bytes()
        self.assertIn(17, collect_reserved_numbers(self.root, CATEGORY))
        self.assertEqual(db.read_bytes(), before)

    def test_04_existing_registry_is_read_without_write(self):
        db = make_db(self.root, with_registry=True)
        with closing(sqlite3.connect(str(db))) as conn, conn:
            conn.execute(
                "INSERT INTO template_number_registry VALUES (?, ?, ?)",
                (CATEGORY, 71, "Wifi_Kutusu_071.png"),
            )
        before = db.read_bytes()
        self.assertIn(71, collect_reserved_numbers(self.root, CATEGORY))
        self.assertEqual(db.read_bytes(), before)

    def test_05_registry_creation_only_in_explicit_writer(self):
        db = make_db(self.root)
        collect_reserved_numbers(self.root, CATEGORY)
        self.assertNotIn("template_number_registry", names_in(db))
        ensure_registry_table(self.root)
        self.assertIn("template_number_registry", names_in(db))
        reserve_number(self.root, CATEGORY, 79, source="unit_test")
        self.assertIn(79, collect_reserved_numbers(self.root, CATEGORY))

    def test_06_readonly_sqlite_connection_cannot_create_table(self):
        db = make_db(self.root)
        before = db.read_bytes()
        conn = _connect_read_only(db)
        try:
            with self.assertRaises(sqlite3.OperationalError):
                conn.execute("CREATE TABLE forbidden_write (v INTEGER)")
        finally:
            conn.close()
        self.assertEqual(db.read_bytes(), before)

    def test_07_without_existing_db_lookup_does_not_create_it(self):
        target = self.root / "SABLON_V2_MIMARI" / "ayarlar.db"
        collect_reserved_numbers(self.root, CATEGORY)
        self.assertFalse(collect_identity_conflicts(
            self.root, CATEGORY, "Wifi_Kutusu_093.png"
        )["conflict"])
        self.assertFalse(target.exists())

    def test_08_same_stem_different_extension_is_blocked(self):
        existing = self.path(
            "2_SABLON_HAVUZU_ORIJINAL_YEDEK",
            CATEGORY, "Wifi_Kutusu_175.png", b"unmodified",
        )
        incoming = self.path(
            "YENI-BOS MOCKUP SABLON HAVUZU",
            CATEGORY, "Wifi_Kutusu_175.jpeg", b"staging",
        )
        # Existing staging file is ignored only for the inbound candidate itself.
        with self.assertRaises(TemplateIdentityConflictError) as exc:
            assert_identity_available(
                self.root, CATEGORY, incoming.name, ignore_paths=[incoming],
            )
        self.assertIn("AYNI İSİM, FARKLI UZANTI", str(exc.exception))
        self.assertEqual(existing.read_bytes(), b"unmodified")
        self.assertEqual(incoming.read_bytes(), b"staging")

    def test_09_same_stem_same_extension_is_blocked(self):
        self.path("2_SABLON_HAVUZU", CATEGORY, "Wifi_Kutusu_175.png")
        with self.assertRaises(TemplateIdentityConflictError) as exc:
            assert_identity_available(
                self.root, CATEGORY, "Wifi_Kutusu_175.PNG",
            )
        self.assertIn("AYNI İSİM / AYNI UZANTI", str(exc.exception))

    def test_10_same_stem_in_other_category_is_allowed(self):
        self.path("2_SABLON_HAVUZU", CATEGORY, "Shared_042.png")
        result = assert_identity_available(
            self.root, ALT_CATEGORY, "Shared_042.jpeg",
        )
        self.assertFalse(result["conflict"])

    def test_11_staging_collision_is_visible_and_preserved(self):
        staged = self.path(
            "YENI-BOS MOCKUP SABLON HAVUZU",
            CATEGORY, "Wifi_Kutusu_090.jpeg", b"pending",
        )
        with self.assertRaises(TemplateIdentityConflictError):
            assert_identity_available(
                self.root, CATEGORY, "Wifi_Kutusu_090.png",
            )
        self.assertEqual(staged.read_bytes(), b"pending")

    def test_12_composed_and_decomposed_unicode_are_same_identity(self):
        composed = "Örnek_007.png"
        decomposed = unicodedata.normalize("NFD", "Örnek_007.jpeg")
        self.assertEqual(
            canonical_identity(composed), canonical_identity(decomposed)
        )
        self.path("2_SABLON_HAVUZU", CATEGORY, composed)
        with self.assertRaises(TemplateIdentityConflictError):
            assert_identity_available(self.root, CATEGORY, decomposed)

    def test_13_reused_number_in_trash_history_is_blocked(self):
        trash = self.root / "SILINEN_SABLONLAR_COP_KUTUSU"
        trash.mkdir()
        (trash / "01_Wifi_Kutusu__Wifi_Kutusu_055__20261010.png").write_bytes(
            b"historical"
        )
        with self.assertRaises(TemplateNumberConflictError):
            validate_number_block(self.root, CATEGORY, 55, 1)

    def test_14_database_history_cannot_be_reused(self):
        db = make_db(self.root, with_registry=True)
        with closing(sqlite3.connect(str(db))) as conn, conn:
            conn.execute(
                "INSERT INTO template_number_registry VALUES (?, ?, ?)",
                (CATEGORY, 55, "Wifi_Kutusu_055.png"),
            )
        with self.assertRaises(TemplateNumberConflictError):
            validate_number_block(self.root, CATEGORY, 55, 1)


if __name__ == "__main__":
    unittest.main()
