# -*- coding: utf-8 -*-
"""Offline integration with the actual MockupRenderer on a disposable runtime.

The test uses only synthetic, human-marked-for-test geometry, never promotes
its APPROVED label into any user/prod database. No cloud, Excel or 8080 server.
"""
import hashlib
import json
import os
import subprocess
import sys
import sqlite3
import tempfile
from pathlib import Path

import cv2
import numpy as np

from scripts.epic3_six_template_smoke import CATEGORY_UIDS

CATEGORY = "01_Wifi_Kutusu"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_factory_renders_approved_synthetic_wifi_template_3x4():
    with tempfile.TemporaryDirectory(prefix="p0-synthetic-render-") as tmp:
        base = Path(tmp)
        runtime = base / "fake-runtime"
        root = Path(__file__).resolve().parents[1]
        filename = "Wifi_Kutusu_048.png"
        scene = runtime / "2_SABLON_HAVUZU" / CATEGORY / filename
        scene.parent.mkdir(parents=True)
        arr = np.full((1600, 1200, 3), (186, 200, 212), dtype=np.uint8)
        cv2.rectangle(arr, (185, 500), (815, 1010), (140, 140, 140), 13)
        cv2.rectangle(arr, (200, 540), (800, 990), (248, 248, 248), -1)
        ok, encoded = cv2.imencode(".png", arr)
        assert ok
        scene.write_bytes(encoded.tobytes())

        db = runtime / "SABLON_V2_MIMARI" / "ayarlar.db"
        db.parent.mkdir(parents=True)
        conn = sqlite3.connect(db)
        try:
            conn.execute("""CREATE TABLE template_profiles (
              template_uid TEXT, category TEXT, source_relative_path TEXT,
              source_asset_sha256 TEXT, surface_quad TEXT,
              orientation TEXT, nominal_aspect REAL,
              review_status TEXT, is_active INTEGER, manually_verified INTEGER,
              has_occlusion INTEGER, component_confidences TEXT
            )""")
            conn.execute("CREATE TABLE templates(category_id TEXT, filename TEXT, data TEXT)")
            conn.execute(
              "INSERT INTO template_profiles VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
              (CATEGORY_UIDS[CATEGORY], CATEGORY, CATEGORY + "/" + filename,
               digest(scene), json.dumps([[200,540],[800,540],[800,990],[200,990]]),
               "H", 4/3, "APPROVED", 1, 1, 0, "{}")
            )
            conn.commit()
        finally:
            conn.close()

        original = digest(scene)
        original_db = digest(db)
        # Import the render engine only inside its own subprocess. A full
        # pytest run may already have imported pc_master_factory with normal
        # CLI flags; testing in-process would incorrectly reuse that module.
        env = os.environ.copy()
        env["MOCKUP_RUNTIME_WORKSPACE"] = str(base / "isolated-engine-runtime")
        env["PYTHONUTF8"] = "1"
        result = subprocess.run(
            [sys.executable, "-B", str(root / "scripts" / "epic3_six_template_smoke.py"),
             "--runtime-root", str(runtime), "--execute"],
            cwd=str(root), env=env, text=True, capture_output=True,
            encoding="utf-8", errors="replace", timeout=120,
        )
        report_line = next(
            (line for line in result.stdout.splitlines()
             if line.startswith("REPORT_PATH ")), None
        )
        assert report_line, result.stdout + "\\n" + result.stderr
        report_path = Path(report_line.split(" ", 1)[1])
        report = json.loads(report_path.read_text(encoding="utf-8"))
        assert result.returncode == 2  # Five intentionally blocked categories.
        records = {row["uid"]: row for row in report["results"]}
        wifi = records[CATEGORY_UIDS[CATEGORY]]
        assert wifi["status"] == "PASS", wifi
        assert wifi["dimensions"] == "1200x1600"
        assert Path(wifi["output"]).is_file()
        assert report["pass_count"] == 1
        assert report["blocked_count"] == 5  # Never bypass unapproved categories.
        assert digest(scene) == original
        assert digest(db) == original_db
