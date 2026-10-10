"""Fully synthetic contract tests; no user archive or real runtime is opened."""
from __future__ import annotations

from contextlib import closing
import io
import json
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch, MagicMock

import cv2
import numpy as np

from scripts import epic3_six_template_smoke as runner


class TestSixTemplateSmokeIsolation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.live = self.base / "fake-user-runtime"
        self.pool = self.live / "2_SABLON_HAVUZU"
        self.archive = self.live / "2_SABLON_HAVUZU_ORIJINAL_YEDEK"
        self.db = self.live / "SABLON_V2_MIMARI" / "ayarlar.db"
        self.db.parent.mkdir(parents=True)
        self.image = np.full((300, 400, 3), 150, dtype=np.uint8)
        ok, encoded = cv2.imencode(".png", self.image)
        self.assertTrue(ok)
        self.encoded = encoded.tobytes()
        self.fixtures = {}
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute("""CREATE TABLE template_profiles(
                template_uid TEXT,category TEXT,source_relative_path TEXT,
                source_asset_sha256 TEXT,surface_quad TEXT,orientation TEXT,
                nominal_aspect REAL,review_status TEXT,is_active INTEGER,
                manually_verified INTEGER,has_occlusion INTEGER,
                component_confidences TEXT)""")
            conn.execute("""CREATE TABLE templates(
                category_id TEXT,filename TEXT,data TEXT)""")
            for category, uid in runner.CATEGORY_UIDS.items():
                basename = uid.removeprefix(category + "_")
                folder = self.pool / category
                folder.mkdir(parents=True, exist_ok=True)
                source = folder / basename
                source.write_bytes(self.encoded)
                self.fixtures[category] = source
                orient = "V" if category in (
                    "02_Cam_Tablo_Dikey", "03_Ahsap_Tablo",
                ) else "H"
                nominal = (0.71428571 if category == "02_Cam_Tablo_Dikey"
                           else 0.66666667 if category == "03_Ahsap_Tablo"
                           else 1.33333333)
                conn.execute(
                    """INSERT INTO template_profiles VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (uid, category, f"{category}/{basename}",
                     runner._sha256_file(source),
                     json.dumps([[35,35],[355,35],[355,265],[35,265]]),
                     orient, nominal, "APPROVED", 1, 1, 0,
                     json.dumps({"physical_orientation_verified": True})),
                )
                conn.execute(
                    "INSERT INTO templates VALUES(?,?,?)",
                    (category, basename, "{}"),
                )

    def _fake_module(self, render_calls):
        def produce(art_path, template_path, config, is_glass,
                    output_path, **kwargs):
            self.assertTrue(art_path.is_file())
            self.assertTrue(template_path.is_file())
            self.assertEqual(config["output_width"], 1200)
            self.assertEqual(config["output_height"], 1600)
            self.assertEqual(config["auto_foreground"], False)
            self.assertTrue(str(output_path).startswith(str(self.base)))
            output_path.parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(output_path),
                        np.full((1600, 1200, 3), 117, np.uint8))
            render_calls.append(template_path.name)
            return True

        class Validator:
            @staticmethod
            def is_valid_quad(quad, w, h):
                return True, "ok"

            @staticmethod
            def canonical_sort(quad):
                return quad

        return SimpleNamespace(
            ApprovedGeometryValidator=Validator,
            MockupRenderer=SimpleNamespace(process_mockup=produce),
            PRODUCT_CATALOG={
                cat: SimpleNamespace(
                    is_glass=cat not in {"01_Wifi_Kutusu", "03_Ahsap_Tablo"},
                    orientation=("V" if cat in {"02_Cam_Tablo_Dikey", "03_Ahsap_Tablo"}
                                 else "H"),
                )
                for cat in runner.CATEGORY_UIDS
            },
            physical_orientation_verified=lambda marker: True,
            USER_WORKSPACE_DIR=self.base / "engine-isolated-runtime",
            RECIPE_VERSION="synthetic-fixture",
        )

    def _run_fixture(self):
        render_calls = []
        fake = self._fake_module(render_calls)
        before_db = runner._sha256_file(self.db)
        before_images = {
            cat: runner._sha256_file(p) for cat, p in self.fixtures.items()
        }
        output = self.base / "separate-output"
        with patch.object(runner, "_load_renderer", return_value=fake):
            result = runner.smoke(self.live, output, self.base)
        self.assertEqual(runner._sha256_file(self.db), before_db)
        self.assertEqual(
            {cat: runner._sha256_file(p) for cat,p in self.fixtures.items()},
            before_images,
        )
        return result, render_calls

    def test_all_six_output_files_are_isolated_1200x1600(self):
        result, calls = self._run_fixture()
        self.assertEqual(result["pass_count"], 6, result["results"])
        self.assertEqual(len(calls), 6)
        self.assertTrue(all(r["status"] == "PASS" for r in result["results"]))
        self.assertTrue(all(r["dimensions"] == "1200x1600"
                            for r in result["results"]))
        self.assertTrue(all(Path(r["output"]).is_relative_to(self.base)
                            for r in result["results"]))
        self.assertFalse((self.live / "3_URETILEN_MOCKUPLAR").exists())

    def test_source_mismatch_is_blocked_before_renderer(self):
        tampered = self.fixtures["01_Wifi_Kutusu"]
        tampered.write_bytes(b"CHANGED")
        result, calls = self._run_fixture()
        self.assertEqual(result["pass_count"], 5)
        self.assertEqual(len(calls), 5)
        blocked = result["results"][0]
        self.assertEqual(blocked["reason"], "STALE_SOURCE_CHANGED")

    def test_occluded_templates_are_not_rendered_without_ai(self):
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute(
                "UPDATE template_profiles SET has_occlusion=1 WHERE category=?",
                ("04_Cam_Dograma",),
            )
        result, calls = self._run_fixture()
        self.assertEqual(result["pass_count"], 5)
        self.assertEqual(len(calls), 5)
        self.assertEqual(result["results"][4]["reason"], "OCCLUSION_REQUIRES_AI")

    def test_legacy_manual_plan_is_not_silently_skipped(self):
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute(
                "UPDATE templates SET data=? WHERE category_id=?",
                (json.dumps({"on_plan":{"object_boxes":[[5,5,20,20]]}}),
                 "03_Ahsap_Tablo"),
            )
        result, calls = self._run_fixture()
        self.assertEqual(result["pass_count"], 5)
        self.assertEqual(len(calls), 5)
        self.assertEqual(
            result["results"][3]["reason"], "MANUAL_MASK_PLAN_REQUIRES_REVIEW",
        )

    def test_source_path_escape_rejected(self):
        external = self.base / "outside.png"
        external.write_bytes(b"EXTERNAL")
        with self.assertRaises(runner.SmokeBlocked):
            runner._inside(self.pool, external)
        self.assertEqual(external.read_bytes(), b"EXTERNAL")

    def test_plan_mode_has_no_io_side_effect(self):
        absent = self.base / "no-runtime-created"
        with patch("sys.stdout", new_callable=io.StringIO) as capture:
            result = runner.main(["--runtime-root", str(absent)])
        self.assertEqual(result, 0)
        self.assertIn("PLAN_ONLY", capture.getvalue())
        self.assertFalse(absent.exists())

    def test_duplicate_approved_records_are_rejected(self):
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute("""INSERT INTO template_profiles
                SELECT * FROM template_profiles WHERE category=?""",
                ("05_Ocak_Arkasi",))
        result, calls = self._run_fixture()
        self.assertEqual(result["pass_count"], 5)
        self.assertEqual(len(calls), 5)
        self.assertEqual(
            result["results"][5]["reason"], "ACTIVE_PROFILE_COUNT_2",
        )


if __name__ == "__main__":
    unittest.main()
