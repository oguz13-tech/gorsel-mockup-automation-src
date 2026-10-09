import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
WATCHER_PATH = (
    ROOT
    / "99_SISTEM_MOTORLARI_VE_KODLAR"
    / "SISTEM_MOTORU"
    / "sablon_oto_izleyici.py"
)


def _load_watcher():
    spec = importlib.util.spec_from_file_location(
        "watcher_safety_under_test",
        WATCHER_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestWatcherSafety(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.watcher = _load_watcher()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.category = "01_Wifi_Kutusu"
        self.staging_dir = (
            self.root
            / "YENI-BOS MOCKUP SABLON HAVUZU"
            / self.category
        )
        self.backup_dir = (
            self.root
            / "2_SABLON_HAVUZU_ORIJINAL_YEDEK"
            / self.category
        )
        self.working_dir = (
            self.root
            / "2_SABLON_HAVUZU"
            / self.category
        )
        self.staging_dir.mkdir(parents=True)
        self.backup_dir.mkdir(parents=True)
        self.working_dir.mkdir(parents=True)

        self.old_base_dir = self.watcher.BASE_DIR
        self.old_staging_dir = self.watcher.STAGING_DIR
        self.old_sablon_dir = self.watcher.SABLON_DIR
        self.old_yedek_dir = self.watcher.YEDEK_DIR
        self.watcher.BASE_DIR = self.root
        self.watcher.STAGING_DIR = (
            self.root / "YENI-BOS MOCKUP SABLON HAVUZU"
        )
        self.watcher.SABLON_DIR = self.root / "2_SABLON_HAVUZU"
        self.watcher.YEDEK_DIR = (
            self.root / "2_SABLON_HAVUZU_ORIJINAL_YEDEK"
        )

    def tearDown(self):
        self.watcher.BASE_DIR = self.old_base_dir
        self.watcher.STAGING_DIR = self.old_staging_dir
        self.watcher.SABLON_DIR = self.old_sablon_dir
        self.watcher.YEDEK_DIR = self.old_yedek_dir
        self.tmp.cleanup()

    def _write_input(self, name="incoming.jpg"):
        image = np.zeros((140, 180, 3), dtype=np.uint8)
        image[20:120, 30:150] = (40, 120, 220)
        path = self.staging_dir / name
        ok, encoded = cv2.imencode(".jpg", image)
        self.assertTrue(ok)
        encoded.tofile(str(path))
        decoded = cv2.imdecode(
            np.fromfile(str(path), dtype=np.uint8),
            cv2.IMREAD_COLOR,
        )
        return path, decoded

    def _review_proposal(self, _image):
        return {
            "tip": "perspektif",
            "koseler": [[20, 20], [160, 20], [160, 120], [20, 120]],
            "supheli": True,
        }

    def _first_pass_result(self, working_path, category, _image):
        corners = [[20, 20], [160, 20], [160, 120], [20, 120]]
        legacy = {
            "tip": "perspektif",
            "koseler": corners,
            "supheli": False,
            "review_status": "REVIEW_REQUIRED",
            "ingest_source": "staging_watcher",
            "auto_corner_once": True,
            "auto_corner_engine": "template_analyzer",
            "auto_corner_confidence": 0.81,
        }
        profile = {
            "template_uid": f"{category}_{Path(working_path).name}",
            "category": category,
            "source_relative_path": f"{category}/{Path(working_path).name}",
            "source_asset_sha256": "test-sha",
            "profile_version": "v2",
            "analyzer_version": "test",
            "product_class": "Test",
            "orientation": "H",
            "nominal_aspect": "1.333333",
            "print_policy": "full_bleed",
            "surface_quad": corners,
            "outer_quad": None,
            "confidence_total": 0.81,
            "component_confidences": {"first_pass_auto": 1.0},
            "review_status": "REVIEW_REQUIRED",
            "manually_verified": False,
        }
        return legacy, profile

    def test_first_pass_auto_analysis_is_review_only_and_runs_once(self):
        source, _ = self._write_input()
        working = self.working_dir / "Wifi_Kutusu_001.png"
        working.write_bytes(source.read_bytes())

        fake_result = {
            "source_asset_sha256": "abc123",
            "surface_quad": [[20, 20], [160, 20], [160, 120], [20, 120]],
            "outer_quad": None,
            "confidence_total": 0.82,
            "component_confidences": {"line_score": 0.9},
            "review_status": "REVIEW_REQUIRED",
            "rule": {
                "product_class": "wifi",
                "print_policy": "full_bleed",
            },
            "orientation": "H",
            "nominal_aspect": "1.333333",
            "analyzer_version": "test-analyzer",
        }

        class FakeAnalyzer:
            calls = 0

            def analyze(self, *args, **kwargs):
                FakeAnalyzer.calls += 1
                return dict(fake_result)

        with patch.object(
            self.watcher,
            "TemplateAnalyzer",
            FakeAnalyzer,
        ), patch.object(
            self.watcher,
            "detect_frame_auto",
            side_effect=AssertionError(
                "legacy fallback should not run when analyzer found corners"
            ),
        ):
            legacy, profile = self.watcher.analyze_new_template_once(
                working,
                self.category,
                cv2.imdecode(
                    np.fromfile(str(working), dtype=np.uint8),
                    cv2.IMREAD_COLOR,
                ),
            )

        self.assertEqual(FakeAnalyzer.calls, 1)
        self.assertTrue(legacy["auto_corner_once"])
        self.assertEqual(legacy["auto_corner_engine"], "template_analyzer")
        self.assertEqual(legacy["review_status"], "REVIEW_REQUIRED")
        self.assertEqual(profile["review_status"], "REVIEW_REQUIRED")
        self.assertFalse(profile["manually_verified"])
        self.assertEqual(profile["surface_quad"], fake_result["surface_quad"])

    def test_successful_ingest_creates_backup_working_and_review_row(self):
        source, decoded = self._write_input()
        saved = {}

        def fake_save_template(category, name, data):
            saved["category"] = category
            saved["name"] = name
            saved["data"] = dict(data)

        saved_profiles = []
        with patch.object(
            self.watcher,
            "get_all_ayarlar",
            return_value={"kategoriler": {self.category: {"sablonlar": {}}}},
        ), patch.object(
            self.watcher,
            "save_template",
            side_effect=fake_save_template,
        ), patch.object(
            self.watcher,
            "save_template_profile",
            side_effect=lambda _db, data: saved_profiles.append(dict(data)),
        ), patch.object(
            self.watcher,
            "analyze_new_template_once",
            side_effect=self._first_pass_result,
        ) as first_pass:
            ok = self.watcher.process_from_staging(source)

        self.assertTrue(ok)
        self.assertFalse(source.exists())
        self.assertEqual(saved["category"], self.category)
        self.assertEqual(saved["name"], "Wifi_Kutusu_001.png")
        self.assertEqual(saved["data"]["review_status"], "REVIEW_REQUIRED")
        self.assertTrue(saved["data"]["auto_corner_once"])
        self.assertEqual(saved["data"]["auto_corner_engine"], "template_analyzer")
        self.assertEqual(len(saved_profiles), 1)
        self.assertEqual(saved_profiles[0]["review_status"], "REVIEW_REQUIRED")
        self.assertEqual(saved_profiles[0]["surface_quad"], saved["data"]["koseler"])
        self.assertEqual(first_pass.call_count, 1)

        backup = self.backup_dir / "Wifi_Kutusu_001.png"
        working = self.working_dir / "Wifi_Kutusu_001.png"
        self.assertTrue(backup.is_file())
        self.assertTrue(working.is_file())

        backup_cv = cv2.imdecode(
            np.fromfile(str(backup), dtype=np.uint8),
            cv2.IMREAD_COLOR,
        )
        working_cv = cv2.imdecode(
            np.fromfile(str(working), dtype=np.uint8),
            cv2.IMREAD_COLOR,
        )
        self.assertTrue(np.array_equal(backup_cv, decoded))
        self.assertTrue(np.array_equal(working_cv, decoded))

        txn_dir = (
            self.root
            / "SABLON_V2_MIMARI"
            / "recovery"
            / "staging_transactions"
        )
        txn_files = list(txn_dir.glob("*.json"))
        self.assertEqual(len(txn_files), 1)
        txn = json.loads(txn_files[0].read_text(encoding="utf-8"))
        self.assertEqual(txn["state"], "COMMITTED")
        self.assertEqual(txn["canonical_name"], "Wifi_Kutusu_001.png")
        self.assertTrue(txn["backup_path"].endswith("Wifi_Kutusu_001.png"))
        self.assertTrue(txn["working_path"].endswith("Wifi_Kutusu_001.png"))

    def test_backup_failure_restores_original_staging_file(self):
        source, _ = self._write_input()

        with patch.object(
            self.watcher,
            "get_all_ayarlar",
            return_value={"kategoriler": {self.category: {"sablonlar": {}}}},
        ), patch.object(
            self.watcher,
            "detect_frame_auto",
            side_effect=self._review_proposal,
        ), patch.object(
            self.watcher,
            "_write_png_atomic",
            return_value=False,
        ):
            ok = self.watcher.process_from_staging(source)

        self.assertFalse(ok)
        self.assertTrue(source.is_file())
        self.assertFalse(
            source.with_suffix(source.suffix + ".processing").exists()
        )

        txn_dir = (
            self.root
            / "SABLON_V2_MIMARI"
            / "recovery"
            / "staging_transactions"
        )
        txn_files = list(txn_dir.glob("*.json"))
        self.assertEqual(len(txn_files), 1)
        txn = json.loads(txn_files[0].read_text(encoding="utf-8"))
        self.assertEqual(txn["state"], "ROLLED_BACK")
        self.assertTrue(txn["rollback_original_restored"])
        self.assertFalse(txn["rollback_processing_left"])

    def test_existing_template_number_forces_user_to_rename(self):
        existing = self.backup_dir / "Wifi_Kutusu_001.png"
        existing_bytes = b"DO_NOT_OVERWRITE"
        existing.write_bytes(existing_bytes)
        source, _ = self._write_input("Wifi_Kutusu_001.jpg")
        saved_names = []

        with patch.object(
            self.watcher,
            "save_template",
            side_effect=lambda _cat, name, _data: saved_names.append(name),
        ):
            ok = self.watcher.process_from_staging(source)

        self.assertFalse(ok)
        self.assertEqual(existing.read_bytes(), existing_bytes)
        self.assertEqual(saved_names, [])
        self.assertTrue(source.is_file())
        self.assertFalse(
            (self.backup_dir / "Wifi_Kutusu_002.png").exists()
        )

    def test_deleted_trash_number_also_forces_user_to_rename(self):
        trash = self.root / "SILINEN_SABLONLAR_COP_KUTUSU"
        trash.mkdir(parents=True)
        (trash / "old_meta.json").write_text(
            '{"kategori":"01_Wifi_Kutusu",'
            '"sablon":"Wifi_Kutusu_135.png"}',
            encoding="utf-8",
        )
        source, _ = self._write_input("Wifi_Kutusu_135.jpg")

        ok = self.watcher.process_from_staging(source)

        self.assertFalse(ok)
        self.assertTrue(source.is_file())
        self.assertFalse(
            (self.backup_dir / "Wifi_Kutusu_136.png").exists()
        )

    def test_db_failure_restores_staging_and_removes_created_files(self):
        source, _ = self._write_input()

        with patch.object(
            self.watcher,
            "get_all_ayarlar",
            return_value={"kategoriler": {self.category: {"sablonlar": {}}}},
        ), patch.object(
            self.watcher,
            "save_template",
            side_effect=RuntimeError("db unavailable"),
        ), patch.object(
            self.watcher,
            "delete_template",
            return_value=None,
        ), patch.object(
            self.watcher,
            "analyze_new_template_once",
            side_effect=self._first_pass_result,
        ):
            ok = self.watcher.process_from_staging(source)

        self.assertFalse(ok)
        self.assertTrue(source.is_file())
        self.assertFalse(
            (self.backup_dir / "Wifi_Kutusu_001.png").exists()
        )
        self.assertFalse(
            (self.working_dir / "Wifi_Kutusu_001.png").exists()
        )

    def test_stale_processing_is_restored_when_original_missing(self):
        processing = self.staging_dir / "Wifi_Kutusu_135.png.processing"
        processing.write_bytes(b"recover-me")
        os.utime(processing, (1, 1))

        result = self.watcher.recover_stale_processing_files(
            stale_seconds=0
        )

        original = self.staging_dir / "Wifi_Kutusu_135.png"
        self.assertTrue(original.is_file())
        self.assertEqual(original.read_bytes(), b"recover-me")
        self.assertFalse(processing.exists())
        self.assertIn(str(original), result["restored"])

    def test_stale_processing_collision_preserves_both_different_files(self):
        original = self.staging_dir / "Wifi_Kutusu_135.png"
        processing = self.staging_dir / "Wifi_Kutusu_135.png.processing"
        original.write_bytes(b"active-copy")
        processing.write_bytes(b"orphan-copy")
        os.utime(processing, (1, 1))

        result = self.watcher.recover_stale_processing_files(
            stale_seconds=0
        )

        self.assertEqual(original.read_bytes(), b"active-copy")
        self.assertFalse(processing.exists())
        self.assertEqual(len(result["quarantined"]), 1)
        recovered = Path(result["quarantined"][0])
        self.assertTrue(recovered.is_file())
        self.assertEqual(recovered.read_bytes(), b"orphan-copy")

    def test_stale_processing_identical_duplicate_is_removed(self):
        original = self.staging_dir / "Wifi_Kutusu_135.png"
        processing = self.staging_dir / "Wifi_Kutusu_135.png.processing"
        original.write_bytes(b"same-bytes")
        processing.write_bytes(b"same-bytes")
        os.utime(processing, (1, 1))

        result = self.watcher.recover_stale_processing_files(
            stale_seconds=0
        )

        self.assertTrue(original.is_file())
        self.assertFalse(processing.exists())
        self.assertEqual(len(result["deduplicated"]), 1)

    def test_unknown_category_is_rejected_without_data_loss(self):
        unknown_dir = (
            self.root
            / "YENI-BOS MOCKUP SABLON HAVUZU"
            / "UNKNOWN"
        )
        unknown_dir.mkdir(parents=True)
        source = unknown_dir / "template.jpg"
        ok, encoded = cv2.imencode(
            ".jpg",
            np.zeros((80, 100, 3), dtype=np.uint8),
        )
        self.assertTrue(ok)
        encoded.tofile(str(source))

        result = self.watcher.process_from_staging(source)
        self.assertFalse(result)
        self.assertTrue(source.is_file())


class TestWatcherRuntimeRouting(unittest.TestCase):
    def test_watcher_respects_runtime_workspace_environment(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Path(tmp)
            env = os.environ.copy()
            env["MOCKUP_RUNTIME_WORKSPACE"] = str(runtime)
            code = f"""
import importlib.util, json
from pathlib import Path
path = Path(r"{WATCHER_PATH}")
spec = importlib.util.spec_from_file_location("watcher_runtime_probe", path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
print(json.dumps({{
    "base": str(mod.BASE_DIR),
    "staging": str(mod.STAGING_DIR),
    "backup": str(mod.YEDEK_DIR),
}}))
"""
            proc = subprocess.run(
                [sys.executable, "-c", code],
                cwd=str(ROOT),
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            import json
            data = json.loads(proc.stdout.strip().splitlines()[-1])
            self.assertEqual(
                os.path.normcase(data["base"]),
                os.path.normcase(str(runtime.resolve())),
            )
            self.assertTrue(
                os.path.normcase(data["staging"]).startswith(
                    os.path.normcase(str(runtime.resolve()))
                )
            )
            self.assertTrue(
                os.path.normcase(data["backup"]).startswith(
                    os.path.normcase(str(runtime.resolve()))
                )
            )


if __name__ == "__main__":
    unittest.main()
