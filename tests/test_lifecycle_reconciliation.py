import json
import sys
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "SABLON_V2_MIMARI"))

from core.lifecycle_reconciliation import (
    LifecycleSafetyError,
    archive_duplicate_variants,
    archive_working_orphan,
    lifecycle_center_report,
    replace_original_and_working,
    rollback_replace_original,
    sha256_file,
    undo_lifecycle_operation,
)


def _write_image(path: Path, value: int, ext: str = ".png") -> bytes:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = np.full((48, 64, 4), value, dtype=np.uint8)
    image[:, :, 3] = 200
    ok, encoded = cv2.imencode(ext, image)
    if not ok:
        raise AssertionError(f"Could not encode {ext}")
    payload = encoded.tobytes()
    path.write_bytes(payload)
    return payload


def _settings(category: str, *templates: str) -> dict:
    return {
        "kategoriler": {
            category: {
                "sablonlar": {
                    name: {}
                    for name in templates
                }
            }
        }
    }


class TestLifecycleReconciliation(unittest.TestCase):
    def test_duplicate_archive_preserves_active_exact_file_and_is_undoable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            category = "03_Ahsap_Tablo"
            working = root / "2_SABLON_HAVUZU" / category
            keep = working / "AhsapTablo_015.png"
            duplicate = working / "AhsapTablo_015.jpeg"
            _write_image(keep, 40, ".png")
            _write_image(duplicate, 90, ".jpg")
            duplicate_sha = sha256_file(duplicate)

            settings = _settings(category, "AhsapTablo_015.png")
            report = lifecycle_center_report(root, settings)
            rows = [
                row for row in report["duplicates"]
                if row["area"] == "WORKING"
                and row["category"] == category
                and row["identity"] == "ahsaptablo_015"
            ]
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertTrue(row["safe_recommendation"])
            self.assertEqual(
                row["recommended_keep"],
                "AhsapTablo_015.png",
            )

            operation = archive_duplicate_variants(
                root,
                settings,
                area="WORKING",
                category=category,
                identity="ahsaptablo_015",
                keep_filename="AhsapTablo_015.png",
            )
            self.assertEqual(operation["state"], "COMMITTED")
            self.assertTrue(keep.is_file())
            self.assertFalse(duplicate.exists())
            self.assertEqual(len(operation["moved"]), 1)
            archived = Path(operation["moved"][0]["to"])
            self.assertTrue(archived.is_file())
            self.assertEqual(sha256_file(archived), duplicate_sha)

            undone = undo_lifecycle_operation(
                root,
                operation_id=operation["operation_id"],
            )
            self.assertEqual(undone["state"], "UNDONE")
            self.assertTrue(keep.is_file())
            self.assertTrue(duplicate.is_file())
            self.assertEqual(sha256_file(duplicate), duplicate_sha)

    def test_duplicate_archive_rejects_replacing_active_exact_choice(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            category = "03_Ahsap_Tablo"
            working = root / "2_SABLON_HAVUZU" / category
            _write_image(working / "AhsapTablo_015.png", 10, ".png")
            _write_image(working / "AhsapTablo_015.jpeg", 20, ".jpg")
            settings = _settings(category, "AhsapTablo_015.png")

            with self.assertRaises(LifecycleSafetyError):
                archive_duplicate_variants(
                    root,
                    settings,
                    area="WORKING",
                    category=category,
                    identity="ahsaptablo_015",
                    keep_filename="AhsapTablo_015.jpeg",
                )

            self.assertTrue(
                (working / "AhsapTablo_015.png").is_file()
            )
            self.assertTrue(
                (working / "AhsapTablo_015.jpeg").is_file()
            )

    def test_replace_original_archives_old_bytes_and_writes_new_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            category = "03_Ahsap_Tablo"
            backup = (
                root
                / "2_SABLON_HAVUZU_ORIJINAL_YEDEK"
                / category
            )
            working = root / "2_SABLON_HAVUZU" / category

            old_backup_png = backup / "AhsapTablo_015.png"
            old_backup_jpeg = backup / "AhsapTablo_015.jpeg"
            old_working = working / "AhsapTablo_015.png"
            _write_image(old_backup_png, 30, ".png")
            _write_image(old_backup_jpeg, 31, ".jpg")
            _write_image(old_working, 32, ".png")

            old_hashes = {
                old_backup_png.name: sha256_file(old_backup_png),
                old_backup_jpeg.name: sha256_file(old_backup_jpeg),
                "working:" + old_working.name: sha256_file(old_working),
            }

            upload_image = np.full((55, 70, 3), 180, dtype=np.uint8)
            ok, encoded = cv2.imencode(".jpg", upload_image)
            self.assertTrue(ok)
            upload_bytes = encoded.tobytes()

            result = replace_original_and_working(
                root,
                category=category,
                template="AhsapTablo_015.png",
                upload_filename="clean-source.jpg",
                upload_bytes=upload_bytes,
            )

            self.assertEqual(result["state"], "COMMITTED")
            self.assertFalse(old_backup_png.exists())
            self.assertFalse(old_backup_jpeg.exists())

            new_backup = backup / "AhsapTablo_015.jpg"
            new_working = working / "AhsapTablo_015.png"
            self.assertEqual(new_backup.read_bytes(), upload_bytes)
            self.assertEqual(
                sha256_file(new_backup),
                result["new_backup_sha256"],
            )
            self.assertEqual(
                sha256_file(new_working),
                result["new_working_sha256"],
            )

            decoded = cv2.imdecode(
                np.fromfile(str(new_working), dtype=np.uint8),
                cv2.IMREAD_UNCHANGED,
            )
            self.assertIsNotNone(decoded)
            self.assertEqual(decoded.shape[:2], upload_image.shape[:2])

            moved = result["moved"]
            self.assertEqual(len(moved), 3)
            moved_by_role_name = {
                (item["role"], item["name"]): item
                for item in moved
            }
            self.assertEqual(
                moved_by_role_name[
                    ("original_before", "AhsapTablo_015.png")
                ]["sha256"],
                old_hashes["AhsapTablo_015.png"],
            )
            self.assertEqual(
                moved_by_role_name[
                    ("original_before", "AhsapTablo_015.jpeg")
                ]["sha256"],
                old_hashes["AhsapTablo_015.jpeg"],
            )
            self.assertEqual(
                moved_by_role_name[
                    ("working_before", "AhsapTablo_015.png")
                ]["sha256"],
                old_hashes["working:AhsapTablo_015.png"],
            )
            for item in moved:
                self.assertTrue(Path(item["to"]).is_file())

            center = lifecycle_center_report(
                root,
                _settings(category, "AhsapTablo_015.png"),
            )
            self.assertEqual(
                center["summary"]["lifecycle_recovery_count"],
                1,
            )
            self.assertEqual(
                center["lifecycle_recovery"][0]["kind"],
                "REPLACE_ORIGINAL",
            )

    def test_replace_original_can_rollback_to_exact_previous_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            category = "03_Ahsap_Tablo"
            backup = (
                root
                / "2_SABLON_HAVUZU_ORIJINAL_YEDEK"
                / category
            )
            working = root / "2_SABLON_HAVUZU" / category

            old_backup = backup / "AhsapTablo_015.png"
            old_working = working / "AhsapTablo_015.png"
            _write_image(old_backup, 21, ".png")
            _write_image(old_working, 22, ".png")
            old_backup_sha = sha256_file(old_backup)
            old_working_sha = sha256_file(old_working)

            upload_image = np.full((40, 50, 3), 155, dtype=np.uint8)
            ok, encoded = cv2.imencode(".jpg", upload_image)
            self.assertTrue(ok)

            result = replace_original_and_working(
                root,
                category=category,
                template="AhsapTablo_015.png",
                upload_filename="replacement.jpg",
                upload_bytes=encoded.tobytes(),
            )
            self.assertEqual(result["state"], "COMMITTED")
            self.assertTrue((backup / "AhsapTablo_015.jpg").is_file())

            rolled = rollback_replace_original(
                root,
                result["operation_id"],
            )
            self.assertEqual(
                rolled["state"],
                "ROLLED_BACK_AFTER_DB_FAILURE",
            )
            self.assertTrue(old_backup.is_file())
            self.assertTrue(old_working.is_file())
            self.assertEqual(sha256_file(old_backup), old_backup_sha)
            self.assertEqual(sha256_file(old_working), old_working_sha)
            self.assertFalse((backup / "AhsapTablo_015.jpg").exists())

            replacement_after = (
                root
                / "SABLON_V2_MIMARI"
                / "recovery"
                / "lifecycle"
                / result["operation_id"]
                / "replacement_after"
            )
            self.assertTrue(replacement_after.is_dir())
            self.assertGreaterEqual(
                len(list(replacement_after.iterdir())),
                2,
            )

    def test_working_orphan_archive_is_recoverable_and_active_identity_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            category = "04_Cam_Dograma"
            working = root / "2_SABLON_HAVUZU" / category
            orphan = working / "CamDograma_old.png"
            _write_image(orphan, 70, ".png")
            orphan_sha = sha256_file(orphan)

            settings = _settings(category, "CamDograma_001.png")
            result = archive_working_orphan(
                root,
                settings,
                category=category,
                identity="camdograma_old",
            )
            self.assertEqual(result["state"], "COMMITTED")
            self.assertFalse(orphan.exists())
            self.assertEqual(
                sha256_file(Path(result["moved"][0]["to"])),
                orphan_sha,
            )

            undo_lifecycle_operation(
                root,
                operation_id=result["operation_id"],
            )
            self.assertTrue(orphan.is_file())
            self.assertEqual(sha256_file(orphan), orphan_sha)

            active = working / "CamDograma_001.png"
            _write_image(active, 80, ".png")
            with self.assertRaises(LifecycleSafetyError):
                archive_working_orphan(
                    root,
                    settings,
                    category=category,
                    identity="camdograma_001",
                )

    def test_lifecycle_center_separates_duplicate_orphan_missing_trash_and_staging_txn(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            category = "05_Ocak_Arkasi"
            working = root / "2_SABLON_HAVUZU" / category
            backup = (
                root
                / "2_SABLON_HAVUZU_ORIJINAL_YEDEK"
                / category
            )
            _write_image(working / "OcakArkasi_001.png", 10, ".png")
            _write_image(working / "OcakArkasi_001.jpeg", 11, ".jpg")
            _write_image(backup / "OcakArkasi_001.png", 12, ".png")
            _write_image(working / "orphan.png", 13, ".png")

            txn_dir = (
                root
                / "SABLON_V2_MIMARI"
                / "recovery"
                / "staging_transactions"
            )
            txn_dir.mkdir(parents=True)
            (txn_dir / "tx1.json").write_text(
                json.dumps({
                    "transaction_id": "tx1",
                    "state": "RECOVERY_REQUIRED",
                    "category": category,
                    "canonical_name": "OcakArkasi_999.png",
                }),
                encoding="utf-8",
            )

            trash = root / "SILINEN_SABLONLAR_COP_KUTUSU"
            trash.mkdir(parents=True)
            (trash / "x_meta.json").write_text(
                json.dumps({
                    "kategori": category,
                    "sablon": "OcakArkasi_010.png",
                }),
                encoding="utf-8",
            )

            settings = _settings(
                category,
                "OcakArkasi_001.png",
                "OcakArkasi_002.png",
            )
            center = lifecycle_center_report(root, settings)
            summary = center["summary"]

            self.assertEqual(summary["duplicate_identity_count"], 1)
            self.assertEqual(summary["working_orphan_count"], 1)
            self.assertEqual(summary["active_missing_count"], 1)
            self.assertEqual(summary["trash_record_count"], 1)
            self.assertEqual(summary["staging_transaction_count"], 1)
            self.assertEqual(
                summary["staging_recovery_required_count"],
                1,
            )
            self.assertFalse(
                center["policy"]["automatic_permanent_delete"]
            )

    def test_backend_and_ui_expose_safe_group2_contract(self):
        app_source = (
            ROOT / "SABLON_V2_MIMARI" / "app.py"
        ).read_text(encoding="utf-8")
        js = (
            ROOT
            / "SABLON_V2_MIMARI"
            / "static"
            / "js"
            / "main.js"
        ).read_text(encoding="utf-8")
        html = (
            ROOT
            / "SABLON_V2_MIMARI"
            / "templates"
            / "index.html"
        ).read_text(encoding="utf-8")
        watcher = (
            ROOT
            / "99_SISTEM_MOTORLARI_VE_KODLAR"
            / "SISTEM_MOTORU"
            / "sablon_oto_izleyici.py"
        ).read_text(encoding="utf-8")

        self.assertIn("/api/lifecycle/center", app_source)
        self.assertIn(
            "/api/lifecycle/resolve-duplicate",
            app_source,
        )
        self.assertIn(
            "/api/templates/replace-original",
            app_source,
        )
        self.assertIn("/api/lifecycle/undo", app_source)

        self.assertNotIn("alert(", js)
        self.assertIn("function showMessage", js)
        self.assertIn("resolveCurrentTemplateDuplicates", js)
        self.assertIn("replaceOriginalSelectedFile", js)
        self.assertIn("openLifecycleCenter", js)
        self.assertIn("undoLastLifecycleOperation", js)

        self.assertIn(
            "🆕 Ham Dosyayı Yenisiyle Değiştir",
            html,
        )
        self.assertIn("🧭 Güvenli Eşitleme Merkezi", html)
        self.assertIn("🗂️ Trash / Recovery Merkezi", html)

        self.assertIn("PROCESSING_OWNED", watcher)
        self.assertIn("BACKUP_WRITTEN", watcher)
        self.assertIn("WORKING_WRITTEN", watcher)
        self.assertIn("DB_REGISTERED", watcher)
        self.assertIn("COMMITTED", watcher)
        self.assertIn("RECOVERY_REQUIRED", watcher)


if __name__ == "__main__":
    unittest.main()
