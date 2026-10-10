"""Actual OpenCV smoke integration on synthetic 6-category fixtures only.

Runs the real process_mockup in a clean child interpreter, from a cloned
source tree, with live-like but disposable SQLite and images. Never reads
the user's actual Windows workspace.
"""
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest

import cv2
import numpy as np

from scripts.epic3_six_template_smoke import CATEGORY_UIDS, _sha256_file


class TestRealRendererSmokeSyntheticFixtures(unittest.TestCase):
    def test_real_pipeline_six_categories_no_live_mutations(self):
        repo = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix="epic3-fixture-") as tmp:
            base = Path(tmp)
            runtime = base / "mock-live-runtime"
            pool = runtime / "2_SABLON_HAVUZU"
            db = runtime / "SABLON_V2_MIMARI" / "ayarlar.db"
            db.parent.mkdir(parents=True, exist_ok=True)
            height, width = 1200, 900
            y, x = np.indices((height, width), dtype=np.int32)
            textured = np.stack([
                (25 + (x * 19 + y * 3) % 190).astype(np.uint8),
                (38 + (x * 7 + y * 13) % 190).astype(np.uint8),
                (52 + (x * 5 + y * 17) % 185).astype(np.uint8),
            ], axis=-1)
            cv2.rectangle(textured, (140, 220), (770, 870),
                          (190, 210, 221), 10)
            for i in range(0, 900, 50):
                cv2.line(textured, (i, 0), (i // 3, 1199),
                         (80, 90, 105), 1, cv2.LINE_AA)
            ok, png = cv2.imencode(".png", textured)
            self.assertTrue(ok)
            image_bytes = png.tobytes()
            files = {}
            with closing(sqlite3.connect(db)) as conn, conn:
                conn.execute("""CREATE TABLE template_profiles(
                    template_uid TEXT, category TEXT,
                    source_relative_path TEXT, source_asset_sha256 TEXT,
                    surface_quad TEXT, orientation TEXT, nominal_aspect REAL,
                    review_status TEXT, is_active INTEGER, manually_verified INTEGER,
                    has_occlusion INTEGER, component_confidences TEXT)""")
                conn.execute("""CREATE TABLE templates(
                    category_id TEXT, filename TEXT, data TEXT)""")
                for cat, uid in CATEGORY_UIDS.items():
                    basename = uid.removeprefix(cat + "_")
                    source = pool / cat / basename
                    source.parent.mkdir(parents=True, exist_ok=True)
                    source.write_bytes(image_bytes)
                    files[cat] = source
                    orient = (
                        "V" if cat in ("02_Cam_Tablo_Dikey", "03_Ahsap_Tablo")
                        else "H"
                    )
                    ratio = (
                        5/7 if cat == "02_Cam_Tablo_Dikey"
                        else 2/3 if cat == "03_Ahsap_Tablo"
                        else 10/7 if cat == "02_Cam_Tablo_Yatay"
                        else 4/3
                    )
                    conn.execute(
                        "INSERT INTO template_profiles VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                        (
                            uid, cat, f"{cat}/{basename}", _sha256_file(source),
                            json.dumps([[210,260],[680,220],[710,790],[200,850]]),
                            orient, ratio, "APPROVED", 1, 1, 0,
                            json.dumps({"physical_orientation_verified": True}),
                        ),
                    )
                    conn.execute(
                        "INSERT INTO templates VALUES(?,?,?)",
                        (cat, basename, "{}"),
                    )
            before_db = _sha256_file(db)
            before_files = {name: _sha256_file(path) for name, path in files.items()}
            child_env = os.environ.copy()
            child_env["PYTHONDONTWRITEBYTECODE"] = "1"
            child_env.pop("MOCKUP_RUNTIME_WORKSPACE", None)
            cmd = [
                sys.executable,
                str(repo / "scripts" / "epic3_six_template_smoke.py"),
                "--runtime-root", str(runtime), "--execute",
            ]
            completed = subprocess.run(
                cmd, cwd=repo, env=child_env,
                text=True, encoding="utf-8", errors="replace",
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=240,
            )
            report_lines = [
                line.partition("REPORT_PATH ")[2].strip()
                for line in completed.stdout.splitlines()
                if line.startswith("REPORT_PATH ")
            ]
            self.assertTrue(
                report_lines, "Smoke did not emit report path:\n"
                + completed.stdout[-8000:] + completed.stderr[-4000:],
            )
            report_file = Path(report_lines[-1])
            self.addCleanup(shutil.rmtree, report_file.parent, ignore_errors=True)
            report = json.loads(report_file.read_text(encoding="utf-8"))
            self.assertEqual(
                completed.returncode, 0,
                "Actual renderer failed:\n"
                + json.dumps(report, ensure_ascii=False) + "\n"
                + completed.stdout[-8000:] + "\n" + completed.stderr[-4000:],
            )
            self.assertEqual(report["pass_count"], 6, report)
            sheet_path = Path(report["contact_sheet"])
            self.assertTrue(sheet_path.is_file())
            self.assertEqual(cv2.imread(str(sheet_path)).shape[1], 960)
            self.assertEqual(_sha256_file(db), before_db)
            self.assertEqual(
                {name: _sha256_file(path) for name, path in files.items()},
                before_files,
            )
            self.assertFalse((runtime / "3_URETILEN_MOCKUPLAR").exists())
            self.assertFalse((
                runtime / "99_SISTEM_MOTORLARI_VE_KODLAR"
                / "SISTEM_MOTORU" / "logs"
            ).exists())
            for record in report["results"]:
                image = cv2.imread(record["output"])
                self.assertIsNotNone(image)
                self.assertEqual(image.shape[:2], (1600, 1200))


if __name__ == "__main__":
    unittest.main()
