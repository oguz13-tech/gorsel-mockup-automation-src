import hashlib
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARCH_DIR = ROOT / "SABLON_V2_MIMARI"
if str(ARCH_DIR) not in sys.path:
    sys.path.insert(0, str(ARCH_DIR))

from core.factory_doctor import run_factory_doctor


class TestFactoryDoctor(unittest.TestCase):
    def test_missing_runtime_is_blocking_and_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "does-not-exist"
            report = run_factory_doctor(missing, ROOT)
            self.assertFalse(report["ready"])
            codes = {item["code"] for item in report["errors"]}
            self.assertIn("RUNTIME_MISSING", codes)
            self.assertFalse(missing.exists())

    def _base_runtime(self, root: Path):
        for rel in (
            "1_GELEN_KAGGLE_BASKILARI",
            "2_SABLON_HAVUZU",
            "2_SABLON_HAVUZU_ORIJINAL_YEDEK",
            "3_URETILEN_MOCKUPLAR",
            "4_EXCEL_YUKLEME_LISTELERI",
            "SABLON_V2_MIMARI",
            "99_SISTEM_MOTORLARI_VE_KODLAR/SISTEM_MOTORU",
        ):
            (root / rel).mkdir(parents=True, exist_ok=True)

        master_dir = root / "1_GELEN_KAGGLE_BASKILARI"
        (master_dir / "M000001_H.png").write_bytes(b"h")
        (master_dir / "M000001_V.png").write_bytes(b"v")
        (master_dir / "manifest.json").write_text(
            json.dumps({
                "items": [{
                    "master_id": "M000001",
                    "horizontal": {"file": "M000001_H.png"},
                    "vertical": {"file": "M000001_V.png"},
                }]
            }),
            encoding="utf-8",
        )

    def _create_review_db(self, root: Path, stale_hash=False):
        db_path = root / "SABLON_V2_MIMARI" / "ayarlar.db"
        conn = sqlite3.connect(db_path)
        conn.executescript("""
            CREATE TABLE categories (
                id TEXT PRIMARY KEY,
                label TEXT
            );
            CREATE TABLE templates (
                category_id TEXT,
                filename TEXT,
                data TEXT,
                UNIQUE(category_id, filename)
            );
            CREATE TABLE template_profiles (
                template_uid TEXT,
                category TEXT,
                source_relative_path TEXT,
                source_asset_sha256 TEXT,
                orientation TEXT,
                nominal_aspect TEXT,
                surface_quad TEXT,
                has_occlusion INTEGER DEFAULT 0,
                review_status TEXT,
                is_active INTEGER DEFAULT 1
            );
        """)
        category = "01_Wifi_Kutusu"
        template_name = "Wifi_Kutusu_001.png"
        template_path = (
            root / "2_SABLON_HAVUZU" / category / template_name
        )
        template_path.parent.mkdir(parents=True, exist_ok=True)
        template_path.write_bytes(b"template-bytes")
        backup_path = (
            root
            / "2_SABLON_HAVUZU_ORIJINAL_YEDEK"
            / category
            / template_name
        )
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        backup_path.write_bytes(b"template-bytes")
        actual_hash = hashlib.sha256(template_path.read_bytes()).hexdigest()
        stored_hash = "0" * 64 if stale_hash else actual_hash

        conn.execute(
            "INSERT INTO categories(id,label) VALUES (?,?)",
            (category, category),
        )
        conn.execute(
            "INSERT INTO templates(category_id,filename,data) VALUES (?,?,?)",
            (
                category,
                template_name,
                json.dumps({
                    "tip": "perspektif",
                    "koseler": [[1, 1], [10, 1], [10, 10], [1, 10]],
                }),
            ),
        )
        conn.execute(
            """INSERT INTO template_profiles(
                   template_uid, category, source_relative_path,
                   source_asset_sha256, orientation, nominal_aspect,
                   surface_quad, has_occlusion, review_status, is_active
               ) VALUES (?,?,?,?,?,?,?,?,?,1)""",
            (
                f"{category}_{template_name}",
                category,
                f"{category}/{template_name}",
                stored_hash,
                "H",
                "1.333333",
                json.dumps([[1, 1], [10, 1], [10, 10], [1, 10]]),
                0,
                "APPROVED",
            ),
        )
        conn.commit()
        conn.close()
        return db_path

    def test_deep_scan_detects_stale_approved_source_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._base_runtime(root)
            db_path = self._create_review_db(root, stale_hash=True)
            before_mtime = db_path.stat().st_mtime_ns

            report = run_factory_doctor(root, ROOT, deep=True)

            codes = {item["code"] for item in report["errors"]}
            self.assertIn("APPROVED_SOURCE_STALE", codes)
            self.assertEqual(db_path.stat().st_mtime_ns, before_mtime)

    def test_completed_artifact_with_missing_file_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._base_runtime(root)
            self._create_review_db(root, stale_hash=False)

            state_path = (
                root
                / "99_SISTEM_MOTORLARI_VE_KODLAR"
                / "SISTEM_MOTORU"
                / "commerce_state.db"
            )
            conn = sqlite3.connect(state_path)
            conn.execute(
                """CREATE TABLE render_artifacts(
                       artifact_key TEXT,
                       local_output_path TEXT,
                       status TEXT
                   )"""
            )
            conn.execute(
                "INSERT INTO render_artifacts VALUES (?,?,?)",
                ("artifact-1", str(root / "missing.jpg"), "COMPLETED"),
            )
            conn.commit()
            conn.close()

            report = run_factory_doctor(root, ROOT, deep=False)
            warning_codes = {
                item["code"] for item in report["warnings"]
            }
            self.assertIn(
                "COMPLETED_ARTIFACT_FILE_MISSING",
                warning_codes,
            )


if __name__ == "__main__":
    unittest.main()
