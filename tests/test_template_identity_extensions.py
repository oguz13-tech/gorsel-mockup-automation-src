import sqlite3
import tempfile
import unittest
from pathlib import Path

from SABLON_V2_MIMARI.core.template_identity import (
    TemplateIdentityConflictError,
    assert_identity_available,
    canonical_identity,
    collect_identity_conflicts,
    same_identity,
)


class TestTemplateIdentityExtensions(unittest.TestCase):
    def _runtime(self, root: Path) -> Path:
        runtime = root / "runtime"
        arch = runtime / "SABLON_V2_MIMARI"
        arch.mkdir(parents=True)
        conn = sqlite3.connect(arch / "ayarlar.db")
        conn.execute(
            """CREATE TABLE templates (
                category_id TEXT,
                filename TEXT
            )"""
        )
        conn.execute(
            """CREATE TABLE template_profiles (
                category TEXT,
                source_relative_path TEXT
            )"""
        )
        conn.commit()
        conn.close()
        return runtime

    def test_identity_ignores_extension_and_case(self):
        self.assertEqual(
            canonical_identity("AhsapTablo_015.PNG"),
            "ahsaptablo_015",
        )
        self.assertTrue(
            same_identity(
                "AhsapTablo_015.jpeg",
                "ahsaptablo_015.PNG",
            )
        )

    def test_same_name_different_extension_reports_both_extensions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime = self._runtime(root)
            category = "03_Ahsap_Tablo"
            working = runtime / "2_SABLON_HAVUZU" / category
            raw = (
                runtime
                / "2_SABLON_HAVUZU_ORIJINAL_YEDEK"
                / category
            )
            working.mkdir(parents=True)
            raw.mkdir(parents=True)
            (working / "AhsapTablo_015.png").write_bytes(b"work")
            (raw / "AhsapTablo_015.png").write_bytes(b"raw")

            report = collect_identity_conflicts(
                runtime,
                category,
                "AhsapTablo_015.jpeg",
            )

            self.assertTrue(report["conflict"])
            self.assertTrue(report["different_extension_present"])
            self.assertEqual(report["incoming_extension"], ".jpeg")
            self.assertEqual(report["existing_extensions"], [".png"])
            self.assertEqual(
                {row["location"] for row in report["matches"]},
                {"WORKING", "ORIGINAL_ARCHIVE"},
            )

            with self.assertRaises(TemplateIdentityConflictError) as ctx:
                assert_identity_available(
                    runtime,
                    category,
                    "AhsapTablo_015.jpeg",
                )
            self.assertIn(
                "AYNI İSİM, FARKLI UZANTI",
                str(ctx.exception),
            )

    def test_same_name_same_extension_is_reported_separately(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime = self._runtime(root)
            category = "03_Ahsap_Tablo"
            working = runtime / "2_SABLON_HAVUZU" / category
            working.mkdir(parents=True)
            (working / "AhsapTablo_015.png").write_bytes(b"work")

            report = collect_identity_conflicts(
                runtime,
                category,
                "AhsapTablo_015.png",
            )
            self.assertTrue(report["conflict"])
            self.assertTrue(report["same_extension_present"])
            self.assertFalse(report["different_extension_present"])

    def test_same_numeric_suffix_in_another_category_is_not_identity_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime = self._runtime(root)
            other = (
                runtime
                / "2_SABLON_HAVUZU"
                / "01_Wifi_Kutusu"
            )
            other.mkdir(parents=True)
            (other / "Wifi_Kutusu_015.png").write_bytes(b"other")

            report = collect_identity_conflicts(
                runtime,
                "03_Ahsap_Tablo",
                "AhsapTablo_015.jpg",
            )
            self.assertFalse(report["conflict"])

    def test_db_history_alone_blocks_reuse_even_when_files_are_gone(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime = self._runtime(root)
            db = runtime / "SABLON_V2_MIMARI" / "ayarlar.db"
            conn = sqlite3.connect(db)
            conn.execute(
                "INSERT INTO templates(category_id, filename) VALUES (?, ?)",
                ("03_Ahsap_Tablo", "AhsapTablo_015.png"),
            )
            conn.commit()
            conn.close()

            report = collect_identity_conflicts(
                runtime,
                "03_Ahsap_Tablo",
                "AhsapTablo_015.webp",
            )
            self.assertTrue(report["conflict"])
            self.assertTrue(report["different_extension_present"])
            self.assertIn(
                "DB_ACTIVE",
                {row["location"] for row in report["matches"]},
            )


if __name__ == "__main__":
    unittest.main()
