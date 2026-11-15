import tempfile
import unittest
from pathlib import Path

from SABLON_V2_MIMARI.core.template_identity import (
    TemplateIdentityConflictError,
    assert_identity_available,
    canonical_identity,
    collect_identity_conflicts,
    format_identity_conflict,
    same_identity,
)


class TestTemplateIdentityExtensions(unittest.TestCase):
    def test_identity_ignores_extension_and_case(self):
        self.assertEqual(
            canonical_identity("AhsapTablo_015.PNG"),
            "ahsaptablo_015",
        )
        self.assertTrue(
            same_identity(
                "AhsapTablo_015.png",
                "ahsaptablo_015.JPEG",
            )
        )

    def test_same_name_different_extension_reports_explicit_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            category = "03_Ahsap_Tablo"
            raw = (
                root
                / "2_SABLON_HAVUZU_ORIJINAL_YEDEK"
                / category
            )
            raw.mkdir(parents=True)
            (raw / "AhsapTablo_015.png").write_bytes(b"png")

            report = collect_identity_conflicts(
                root,
                category,
                "AhsapTablo_015.jpg",
            )

            self.assertTrue(report["conflict"])
            self.assertTrue(report["different_extension_present"])
            self.assertFalse(report["same_extension_present"])
            self.assertEqual(
                report["existing_extensions"],
                [".png"],
            )
            message = format_identity_conflict(report)
            self.assertIn("AYNI İSİM, FARKLI UZANTI", message)
            self.assertIn("AhsapTablo_015.jpg", message)
            self.assertIn("AhsapTablo_015.png", message)
            self.assertIn("ORIGINAL_ARCHIVE", message)

            with self.assertRaises(TemplateIdentityConflictError):
                assert_identity_available(
                    root,
                    category,
                    "AhsapTablo_015.jpg",
                )

    def test_same_name_same_extension_is_reported_separately(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            category = "03_Ahsap_Tablo"
            working = root / "2_SABLON_HAVUZU" / category
            working.mkdir(parents=True)
            (working / "AhsapTablo_015.png").write_bytes(b"png")

            report = collect_identity_conflicts(
                root,
                category,
                "AhsapTablo_015.png",
            )
            self.assertTrue(report["same_extension_present"])
            self.assertFalse(report["different_extension_present"])
            self.assertIn(
                "AYNI İSİM / AYNI UZANTI",
                format_identity_conflict(report),
            )

    def test_same_filename_in_another_category_does_not_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            category_a = "01_Wifi_Kutusu"
            category_b = "03_Ahsap_Tablo"
            raw_a = (
                root
                / "2_SABLON_HAVUZU_ORIJINAL_YEDEK"
                / category_a
            )
            raw_a.mkdir(parents=True)
            (raw_a / "Shared_015.png").write_bytes(b"png")

            report = collect_identity_conflicts(
                root,
                category_b,
                "Shared_015.jpg",
            )
            self.assertFalse(report["conflict"])


if __name__ == "__main__":
    unittest.main()
