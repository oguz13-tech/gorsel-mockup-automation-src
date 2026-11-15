"""EPIC-3 template preview audit tests with disposable SQLite/images only."""
from __future__ import annotations

from contextlib import closing
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from scripts import epic3_visual_candidate_sheets as tool


class TestCandidateSheets(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.runtime = self.base / "mock-live"
        self.pool = self.runtime / "2_SABLON_HAVUZU"
        self.db = self.runtime / "SABLON_V2_MIMARI" / "ayarlar.db"
        self.db.parent.mkdir(parents=True, exist_ok=True)
        self.pool.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute("""CREATE TABLE template_profiles(
              template_uid TEXT,category TEXT,source_relative_path TEXT,
              review_status TEXT,is_active INTEGER,manually_verified INTEGER)""")
            for cat, count in (("01_Wifi_Kutusu",31),("04_Cam_Dograma",1)):
                for index in range(count):
                    filename = f"Sample_{index:03d}.png"
                    source = self.pool / cat / filename
                    source.parent.mkdir(parents=True, exist_ok=True)
                    Image.new("RGB",(140+index%2*110,240),(120,170,215)).save(source)
                    conn.execute(
                        "INSERT INTO template_profiles VALUES(?,?,?,?,?,?)",
                        (f"{cat}_{filename}",cat,f"{cat}/{filename}","APPROVED",1,1),
                    )
        # Physical cam-doğrama candidates missing from DB are still previewed.
        for index in range(28):
            target = self.pool/"04_Cam_Dograma"/f"UNAPPROVED_{index:03d}.png"
            Image.new("RGB",(220,150),(140,105,85)).save(target)

    def test_contact_sheets_count_all_files_without_live_writes(self):
        before_db = self.db.read_bytes()
        before_files = {
            str(p):p.read_bytes() for p in self.pool.rglob("*.png")
        }
        dest = self.base/"isolated-output"
        dest.mkdir()
        report = tool.run(self.runtime,dest)
        wifi = report["categories"]["01_Wifi_Kutusu"]
        cam = report["categories"]["04_Cam_Dograma"]
        self.assertEqual((wifi["approved_profile_rows"], wifi["physical_image_count"],
                          len(wifi["items"]),wifi["sheet_count"]),(31,31,31,3))
        self.assertEqual((cam["approved_profile_rows"],cam["physical_image_count"],
                          len(cam["items"]),cam["sheet_count"]),(1,29,29,2))
        self.assertEqual(sum(x["status"]=="APPROVED" for x in cam["items"]),1)
        self.assertEqual(self.db.read_bytes(), before_db)
        self.assertEqual({
            str(p):p.read_bytes() for p in self.pool.rglob("*.png")
        },before_files)
        self.assertFalse((self.runtime/"3_URETILEN_MOCKUPLAR").exists())
        self.assertTrue(all(Path(p).is_file() for p in wifi["sheet_paths"]))
        self.assertTrue(all(Path(p).is_file() for p in cam["sheet_paths"]))

    def test_preview_preserves_aspect_ratio(self):
        dest=self.base/"out"
        dest.mkdir()
        records=[{"source":self.pool/"01_Wifi_Kutusu"/"Sample_000.png",
                  "relative":"01_Wifi_Kutusu/Sample_000.png","status":"APPROVED"}]
        pages,items=tool._render_sheet(
            Image,__import__("PIL.ImageDraw",fromlist=["ImageDraw"]),
            __import__("PIL.ImageFont",fromlist=["ImageFont"]),
            "WIFI",records,dest,
        )
        self.assertEqual(len(pages),1)
        self.assertEqual(items[0]["size"],[140,240])
        with Image.open(pages[0]) as sheet:
            self.assertEqual(sheet.size,(960,1862))

    def test_plan_only_does_not_touch_files(self):
        absent=self.base/"absent"
        with patch("sys.stdout",new_callable=io.StringIO) as out:
            rc=tool.main(["--runtime-root",str(absent)])
        self.assertEqual(rc,0)
        self.assertIn("PLAN_ONLY",out.getvalue())
        self.assertFalse(absent.exists())

    def test_traversal_is_rejected(self):
        outside=self.base/"outside.png"
        outside.write_bytes(b"DO-NOT-TOUCH")
        with self.assertRaises(tool.AuditBlocked):
            tool._within(self.pool,outside)
        self.assertEqual(outside.read_bytes(),b"DO-NOT-TOUCH")

    def test_missing_approved_file_is_explicitly_reported(self):
        missing=self.pool/"01_Wifi_Kutusu"/"Sample_003.png"
        missing.unlink()
        dest=self.base/"out"
        dest.mkdir()
        report=tool.run(self.runtime,dest)
        self.assertIn("01_Wifi_Kutusu/Sample_003.png",
                      report["categories"]["01_Wifi_Kutusu"]["approved_sources_missing"])

    def test_only_full_manual_approved_records_select(self):
        with closing(sqlite3.connect(self.db)) as conn,conn:
            conn.execute(
                "UPDATE template_profiles SET manually_verified=0 "
                "WHERE category=? AND source_relative_path=?",
                ("01_Wifi_Kutusu","01_Wifi_Kutusu/Sample_001.png"),
            )
        data=tool._load_approved(self.db,self.pool)
        self.assertEqual(len(data["01_Wifi_Kutusu"]),30)

if __name__=="__main__":
    unittest.main()
