# -*- coding: utf-8 -*-
"""Synthetic-only P0 collision/identity stress; never accesses Windows user data."""
import importlib.util
import os
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
WATCHER = ROOT / "99_SISTEM_MOTORLARI_VE_KODLAR/SISTEM_MOTORU/sablon_oto_izleyici.py"
CAT = "01_Wifi_Kutusu"


def load():
    spec = importlib.util.spec_from_file_location("watcher_number_stress", WATCHER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class NumberingAndLossRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.w = load()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.stage = self.root / "YENI-BOS MOCKUP SABLON HAVUZU" / CAT
        self.backup = self.root / "2_SABLON_HAVUZU_ORIJINAL_YEDEK" / CAT
        self.work = self.root / "2_SABLON_HAVUZU" / CAT
        for p in (self.stage, self.backup, self.work): p.mkdir(parents=True)
        db = self.root / "SABLON_V2_MIMARI/ayarlar.db"
        db.parent.mkdir(parents=True)
        sqlite3.connect(db).close()
        self.saved = (self.w.BASE_DIR, self.w.STAGING_DIR, self.w.YEDEK_DIR, self.w.SABLON_DIR)
        self.w.BASE_DIR = self.root
        self.w.STAGING_DIR = self.stage.parent
        self.w.YEDEK_DIR = self.backup.parent
        self.w.SABLON_DIR = self.work.parent
        self.addCleanup(self.restore)
        e = patch.dict(os.environ, {"MOCKUP_STAGING_IMPORT_APPROVED": "I_REVIEWED_AND_APPROVED_STAGING_IMPORT"})
        e.start(); self.addCleanup(e.stop)
        for p in (
            patch.object(self.w, "save_template"),
            patch.object(self.w, "save_template_profile"),
            patch.object(self.w, "analyze_new_template_once", side_effect=self.proposal),
        ):
            p.start(); self.addCleanup(p.stop)

    def restore(self):
        self.w.BASE_DIR, self.w.STAGING_DIR, self.w.YEDEK_DIR, self.w.SABLON_DIR = self.saved

    @staticmethod
    def proposal(src, category, image):
        quad = [[1,1],[100,1],[100,90],[1,90]]
        return (
            {"tip": "perspektif", "koseler": quad, "review_status": "REVIEW_REQUIRED"},
            {"template_uid": category + "_" + src.name, "category": category,
             "source_relative_path": category + "/" + src.name,
             "source_asset_sha256": "synthetic", "review_status": "REVIEW_REQUIRED",
             "manually_verified": False, "surface_quad": quad},
        )

    def incoming(self, name, color):
        img = np.full((100, 120, 3), color, dtype=np.uint8)
        suffix = Path(name).suffix.lower()
        ok, buf = cv2.imencode(suffix if suffix in (".jpeg", ".jpg", ".png") else ".png", img)
        self.assertTrue(ok)
        p = self.stage / name
        p.write_bytes(buf.tobytes())
        return p

    def test_100_collisions_unique_targets_and_exact_raw_archive(self):
        original = self.backup / "Wifi_Kutusu_005.png"
        original.write_bytes(b"DO_NOT_OVERWRITE_005")
        all_raw = []
        for i in range(100):
            # Different emails may reuse visible names with different contents.
            name = ("Wifi_Kutusu_%03d.jpeg" % (i % 25) if i % 2 else "Gemini_%03d.png" % i)
            src = self.incoming(name, i + 1)
            all_raw.append(src.read_bytes())
            self.assertTrue(self.w.process_from_staging(src), "failed at %d" % i)
        self.assertEqual(original.read_bytes(), b"DO_NOT_OVERWRITE_005")
        self.assertEqual(len(list(self.work.glob("*.png"))), 100)
        raw = [p.read_bytes() for p in (self.root / "_GUVENLI_GELEN_HAM_GORSELLER" / CAT).rglob("*") if p.is_file()]
        self.assertCountEqual(raw, all_raw)
        # sqlite3.Connection context managers commit/rollback but DO NOT close.
        # On Windows a leaked test handle locks the temp DB against cleanup.
        db = sqlite3.connect(self.root / "SABLON_V2_MIMARI/ayarlar.db")
        try:
            rows = db.execute(
                "SELECT template_number FROM template_number_registry WHERE category=?",
                (CAT,),
            ).fetchall()
        finally:
            db.close()
        self.assertEqual(len(rows), 100)
        self.assertEqual(len(set(rows)), 100)

    def test_legacy_number_and_extension_collision_auto_renumber(self):
        self.backup.joinpath("Wifi_Kutusu_135.png").write_bytes(b"KEEP_135")
        self.work.joinpath("Wifi_Kutusu_136.png").write_bytes(b"KEEP_136")
        src = self.incoming("Wifi_Kutusu_135.jpeg", 42)
        raw = src.read_bytes()
        self.assertTrue(self.w.process_from_staging(src))
        self.assertEqual(self.backup.joinpath("Wifi_Kutusu_135.png").read_bytes(), b"KEEP_135")
        self.assertTrue(self.work.joinpath("Wifi_Kutusu_137.png").exists())
        archived = list((self.root / "_GUVENLI_GELEN_HAM_GORSELLER").rglob("Wifi_Kutusu_135.jpeg"))
        self.assertEqual(len(archived), 1)
        self.assertEqual(archived[0].read_bytes(), raw)

    def test_parallel_inputs_cannot_claim_same_number(self):
        srcs = [self.incoming("a.jpg", 41), self.incoming("b.jpg", 42)]
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(list(pool.map(self.w.process_from_staging, srcs)), [True, True])
        self.assertEqual(sorted(p.name for p in self.work.glob("*.png")),
                         ["Wifi_Kutusu_001.png", "Wifi_Kutusu_002.png"])

    def test_missing_database_or_disabled_watcher_fails_closed(self):
        src = self.incoming("safe.jpg", 1)
        original = src.read_bytes()
        (self.root / "SABLON_V2_MIMARI/ayarlar.db").unlink()
        self.assertFalse(self.w.process_from_staging(src))
        self.assertEqual(src.read_bytes(), original)
        with patch.dict(os.environ, {"MOCKUP_STAGING_IMPORT_APPROVED": ""}):
            self.assertFalse(self.w.process_from_staging(src))
            self.assertEqual(src.read_bytes(), original)

    def test_create_only_writer_never_replaces_racing_destination(self):
        dest = self.backup / "Wifi_Kutusu_005.png"
        dest.write_bytes(b"ORIGINAL")
        self.assertFalse(self.w._write_png_atomic(dest, np.zeros((20,20,3),dtype=np.uint8)))
        self.assertEqual(dest.read_bytes(), b"ORIGINAL")

    def test_get_and_startup_must_not_trigger_watcher_or_autoheal(self):
        for p in (ROOT / "SABLON_DUZELTICI.py", ROOT / "SABLON_V2_MIMARI/core/vision.py"):
            txt = p.read_text(encoding="utf-8")
            start = txt.index("elif req_path == '/api/ayarlar':")
            end = txt.index("elif req_path == '/favicon.ico':", start)
            self.assertNotIn("process_from_staging", txt[start:end])
        src = (ROOT / "SABLON_DUZELTICI.py").read_text(encoding="utf-8")
        self.assertNotIn("subprocess.run(", src[src.index("if __name__ == '__main__':"):])


if __name__ == "__main__":
    unittest.main()
