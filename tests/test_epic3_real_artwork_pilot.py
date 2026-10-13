"""Actual-design pilot safety tests, using only disposable DB/templates/artwork."""
from __future__ import annotations

from contextlib import closing
import io
import json
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import cv2
import numpy as np

from scripts import epic3_six_template_smoke as base
from scripts import epic3_real_artwork_pilot as pilot


class TestRealArtworkPilot(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="epic3-real-art-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.runtime = self.root / "fake-user-runtime"
        self.pool = self.runtime / "2_SABLON_HAVUZU"
        self.db = self.runtime / "SABLON_V2_MIMARI" / "ayarlar.db"
        self.db.parent.mkdir(parents=True)
        self.artwork = self.root / "user-designed-artworks"
        self.artwork.mkdir()
        self.horizontal = self.artwork / "H.png"
        self.vertical = self.artwork / "V.png"
        self._write_art(self.horizontal, width=1000, height=750)
        self._write_art(self.vertical, width=500, height=700)
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
            for cat, orientation, nominal in (
                ("01_Wifi_Kutusu", "H", 4/3),
                ("02_Cam_Tablo_Dikey", "V", 5/7),
            ):
                uid = base.CATEGORY_UIDS[cat]
                filename = uid.removeprefix(cat + "_")
                source = self.pool / cat / filename
                source.parent.mkdir(parents=True, exist_ok=True)
                self._write_art(source, width=400, height=300)
                self.fixtures[cat] = source
                conn.execute(
                    "INSERT INTO template_profiles VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                    (uid, cat, f"{cat}/{filename}", base._sha256_file(source),
                     json.dumps([[35,35],[365,35],[365,265],[35,265]]),
                     orientation, nominal, "APPROVED", 1, 1, 0,
                     json.dumps({"physical_orientation_verified":True})),
                )
                conn.execute(
                    "INSERT INTO templates VALUES(?,?,?)",
                    (cat, filename, "{}"),
                )

    def _write_art(self, path: Path, width: int, height: int):
        y, x = np.indices((height, width), dtype=np.int32)
        data = np.stack([
            ((x*3 + y*9) % 200 + 35).astype(np.uint8),
            ((x*11 + y*2) % 190 + 45).astype(np.uint8),
            ((x*7 + y*5) % 180 + 55).astype(np.uint8),
        ], axis=-1)
        self.assertTrue(cv2.imwrite(str(path), data))

    def _fake_renderer(self, calls: list):
        def render(art_path, template_path, config, is_glass,
                   output_path, **kwargs):
            self.assertEqual(config["output_width"], 1200)
            self.assertEqual(config["output_height"], 1600)
            self.assertFalse(config["auto_foreground"])
            self.assertTrue(art_path.resolve().is_relative_to(self.root.resolve()))
            self.assertIn("user_artwork_copies", str(art_path))
            self.assertTrue(template_path.resolve().is_relative_to(self.pool.resolve()))
            self.assertEqual(config["profile_orientation"],
                             "H" if "Wifi" in str(template_path) else "V")
            output_path.parent.mkdir(parents=True, exist_ok=True)
            img = np.full((1600,1200,3), 123, dtype=np.uint8)
            self.assertTrue(cv2.imwrite(str(output_path), img))
            calls.append((str(art_path), str(template_path)))
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
            MockupRenderer=SimpleNamespace(process_mockup=render),
            PRODUCT_CATALOG={
                category: SimpleNamespace(
                    orientation=("V" if category=="02_Cam_Tablo_Dikey" else "H"),
                    is_glass=category != "01_Wifi_Kutusu",
                ) for category in base.CATEGORY_UIDS
            },
            physical_orientation_verified=lambda x: True,
            USER_WORKSPACE_DIR=self.root/"temp-engine-runtime",
            RECIPE_VERSION="fixture-r01",
        )

    def _run(self, categories=("01_Wifi_Kutusu","02_Cam_Tablo_Dikey"),
             h=None, v=None, overrides=None, *, preview_pad=False):
        output = self.root / ("output-" + str(len(list(self.root.glob("output-*")))))
        output.mkdir()
        calls = []
        fake = self._fake_renderer(calls)
        with patch.object(base, "_load_renderer", return_value=fake):
            result = pilot.run(
                self.runtime,output,self.root,list(categories),
                h if h is not None else self.horizontal,
                v if v is not None else self.vertical,
                overrides or {}, preview_pad=preview_pad,
            )
        return result,calls

    def test_real_hv_artwork_copy_only_and_1200x1600(self):
        original_bytes = {
            str(p):p.read_bytes()
            for p in [self.db,self.horizontal,self.vertical,*self.fixtures.values()]
        }
        result,calls = self._run()
        self.assertEqual(result["pass_count"],2,result)
        self.assertEqual(len(calls),2)
        self.assertTrue(result["source_hash_stable"])
        self.assertTrue(result["no_cloud_excel_or_seo"])
        self.assertTrue(Path(result["contact_sheet"]).is_file())
        self.assertEqual(result["selected_categories"],
                         ["01_Wifi_Kutusu","02_Cam_Tablo_Dikey"])
        self.assertTrue(all(x["synthetic_art_only"] is False
                            for x in result["results"]))
        for r in result["results"]:
            preview = cv2.imread(r["output"])
            self.assertIsNotNone(preview)
            self.assertEqual(preview.shape[:2],(1600,1200))
        self.assertEqual(original_bytes,{
            str(p):p.read_bytes()
            for p in [self.db,self.horizontal,self.vertical,*self.fixtures.values()]
        })
        self.assertFalse((self.runtime/"3_URETILEN_MOCKUPLAR").exists())
        self.assertFalse((self.runtime/"4_EXCEL_YUKLEME_LISTELERI").exists())

    def test_original_backup_remains_readonly_during_real_pilot(self):
        source = self.fixtures["01_Wifi_Kutusu"]
        archive = (
            self.runtime / "2_SABLON_HAVUZU_ORIJINAL_YEDEK"
            / "01_Wifi_Kutusu" / source.name
        )
        archive.parent.mkdir(parents=True, exist_ok=True)
        archive.write_bytes(source.read_bytes())
        before = archive.read_bytes()
        result, calls = self._run(categories=("01_Wifi_Kutusu",))
        self.assertEqual(result["pass_count"], 1, result)
        self.assertTrue(result["source_hash_stable"])
        self.assertEqual(archive.read_bytes(), before)
        self.assertEqual(len(calls), 1)

    def test_any_nontrivial_ratio_mismatch_is_blocked_before_crop(self):
        self._write_art(self.horizontal,width=1000,height=744)
        result,calls = self._run(categories=("01_Wifi_Kutusu",))
        self.assertEqual(result["pass_count"],0)
        self.assertEqual(len(calls),0)
        self.assertIn("ARTWORK_RATIO_WOULD_CROP_OR_SYNTHESIZE",
                      result["results"][0]["reason"])

    def test_opt_in_preview_pad_preserves_all_design_pixels_and_source_bytes(self):
        self._write_art(self.horizontal, width=1000, height=680)
        original_art_sha = base._sha256_file(self.horizontal)
        original_db_sha = base._sha256_file(self.db)
        result, calls = self._run(
            categories=("01_Wifi_Kutusu",), preview_pad=True,
        )
        self.assertEqual(result["pass_count"], 1, result)
        self.assertEqual(len(calls), 1)
        self.assertEqual(result["results"][0]["artwork_fit_mode"],
                         "BLURRED_BORDER_PREVIEW_REQUIRES_HUMAN_REVIEW")
        pad = result["results"][0]["preview_pad"]
        self.assertTrue(pad["original_pixels_unchanged"])
        self.assertTrue(pad["preview_only_not_sale_approved"])
        self.assertFalse(result["results"][0]["commercial_release_approved"])
        original_img = cv2.imread(str(self.horizontal))
        prepared = cv2.imread(calls[0][0])
        l,t,r,b = pad["original_design_bounds"]
        self.assertTrue(np.array_equal(original_img, prepared[t:b,l:r]))
        self.assertGreater(prepared.shape[1]*prepared.shape[0],
                           original_img.shape[1]*original_img.shape[0])
        self.assertAlmostEqual(prepared.shape[1] / prepared.shape[0], 4/3,
                               delta=0.005)
        self.assertEqual(base._sha256_file(self.horizontal), original_art_sha)
        self.assertEqual(base._sha256_file(self.db), original_db_sha)
        self.assertTrue(result["source_hash_stable"])

    def test_preview_pad_still_refuses_severe_mismatch_and_does_not_render(self):
        self._write_art(self.horizontal, width=1000, height=500)
        result, calls = self._run(
            categories=("01_Wifi_Kutusu",), preview_pad=True,
        )
        self.assertEqual(len(calls), 0)
        self.assertEqual(result["blocked_count"], 1)
        self.assertIn("ARTWORK_RATIO_WOULD_CROP_OR_SYNTHESIZE",
                      result["results"][0]["reason"])

    def test_preview_pad_opt_in_keeps_matching_artwork_unaltered(self):
        before = base._sha256_file(self.horizontal)
        result, calls = self._run(
            categories=("01_Wifi_Kutusu",), preview_pad=True,
        )
        self.assertEqual(result["pass_count"], 1, result)
        self.assertEqual(result["results"][0]["artwork_fit_mode"],
                         "ORIGINAL_ASPECT_MATCH")
        self.assertFalse("preview_pad" in result["results"][0])
        self.assertEqual(base._sha256_file(self.horizontal), before)
        self.assertTrue(Path(calls[0][0]).is_file())

    def test_wrong_orientation_is_blocked(self):
        result,calls = self._run(
            categories=("01_Wifi_Kutusu",),
            overrides={"01_Wifi_Kutusu":self.vertical},
        )
        self.assertEqual(len(calls),0)
        self.assertEqual(result["blocked_count"],1)
        self.assertEqual(result["results"][0]["reason"],
                         "ARTWORK_PHYSICAL_ORIENTATION_MISMATCH")

    def test_template_pool_is_not_accepted_as_artwork_source(self):
        result,calls = self._run(
            categories=("01_Wifi_Kutusu",),
            overrides={"01_Wifi_Kutusu":self.fixtures["01_Wifi_Kutusu"]},
        )
        self.assertEqual(len(calls),0)
        self.assertEqual(result["results"][0]["reason"],
                         "ARTWORK_PATH_POINTS_TO_PROTECTED_TEMPLATE_OR_OUTPUT")

    def test_missing_real_artwork_is_blocked(self):
        self.horizontal.unlink()
        result,calls = self._run(categories=("01_Wifi_Kutusu",))
        self.assertEqual(result["pass_count"],0)
        self.assertEqual(len(calls),0)
        self.assertEqual(result["results"][0]["reason"],"ARTWORK_NOT_FOUND")

    def test_occluded_template_is_blocked_no_ai_fallback(self):
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute(
                "UPDATE template_profiles SET has_occlusion=1 WHERE category=?",
                ("01_Wifi_Kutusu",),
            )
        result,calls = self._run(categories=("01_Wifi_Kutusu",))
        self.assertEqual(len(calls),0)
        self.assertEqual(result["results"][0]["reason"],
                         "OCCLUSION_REQUIRES_VERIFIED_MASK")

    def test_manual_foreground_plan_is_blocked(self):
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute(
                "UPDATE templates SET data=? WHERE category_id=?",
                (json.dumps({"on_plan":{"object_boxes":[[2,2,20,20]]}}),
                 "01_Wifi_Kutusu"),
            )
        result,calls = self._run(categories=("01_Wifi_Kutusu",))
        self.assertEqual(len(calls),0)
        self.assertEqual(result["results"][0]["reason"],
                         "LEGACY_MASK_PLAN_REQUIRES_REVIEW")

    def test_source_changed_from_approval_is_blocked(self):
        source = self.fixtures["01_Wifi_Kutusu"]
        source.write_bytes(b"TAMPERED")
        result,calls = self._run(categories=("01_Wifi_Kutusu",))
        self.assertEqual(result["pass_count"],0)
        self.assertEqual(len(calls),0)
        self.assertEqual(result["results"][0]["reason"],
                         "STALE_SOURCE_CHANGED")

    def test_category_artwork_override_allows_distinct_master(self):
        self._write_art(self.horizontal,width=1000,height=742)
        new_art = self.artwork/"exact-wifi.png"
        self._write_art(new_art,width=1000,height=750)
        result,calls = self._run(
            categories=("01_Wifi_Kutusu",),
            overrides={"01_Wifi_Kutusu":new_art},
        )
        self.assertEqual(result["pass_count"],1)
        self.assertEqual(len(calls),1)

    def test_corrupt_artwork_is_blocked_before_renderer(self):
        self.horizontal.write_bytes(b"THIS_IS_NOT_AN_IMAGE")
        result,calls = self._run(categories=("01_Wifi_Kutusu",))
        self.assertEqual(len(calls),0)
        self.assertEqual(result["results"][0]["reason"],"ARTWORK_UNREADABLE")

    def test_plan_mode_does_not_touch_runtime(self):
        absent=self.root/"does-not-exist"
        with patch("sys.stdout",new_callable=io.StringIO) as output:
            exitcode=pilot.main([
                "--runtime-root",str(absent),
                "--artwork-h",str(self.horizontal),
            ])
        self.assertEqual(exitcode,0)
        self.assertFalse(absent.exists())
        self.assertIn("PLAN_ONLY",output.getvalue())

    def test_cli_no_artwork_and_duplicate_override_rejected(self):
        ns=SimpleNamespace(artwork_for=[],artwork_h=None,artwork_v=None)
        with self.assertRaises(pilot.PilotBlocked):
            pilot._requested_sources(ns)
        ns.artwork_for=[
            "01_Wifi_Kutusu=x.png",
            "01_Wifi_Kutusu=y.png",
        ]
        with self.assertRaises(pilot.PilotBlocked):
            pilot._requested_sources(ns)

    def test_invalid_source_size_and_unsupported_extension_blocked(self):
        tiny=self.artwork/"tiny.png"
        self._write_art(tiny,width=120,height=90)
        result,calls=self._run(categories=("01_Wifi_Kutusu",),
                               overrides={"01_Wifi_Kutusu":tiny})
        self.assertEqual(len(calls),0)
        self.assertEqual(result["results"][0]["reason"],
                         "ARTWORK_RESOLUTION_TOO_LOW")
        other=self.artwork/"file.txt"
        other.write_bytes(self.horizontal.read_bytes())
        result,calls=self._run(categories=("01_Wifi_Kutusu",),
                               overrides={"01_Wifi_Kutusu":other})
        self.assertEqual(len(calls),0)
        self.assertEqual(result["results"][0]["reason"],
                         "ARTWORK_EXTENSION_UNSUPPORTED")


if __name__ == "__main__":
    unittest.main()
