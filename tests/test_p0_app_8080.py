# -*- coding: utf-8 -*-
"""Flask 8080 workflow in a DISPOSABLE child process: never touch real runtime."""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
CAT = "01_Wifi_Kutusu"
NAME = "Wifi_Kutusu_001.png"

# Running in a child process is intentional: legacy Flask imports register
# Windows file log handlers, and process exit releases their handles cleanly.
CHILD = r"""
import json
from pathlib import Path
import os
import sys
# Running app.py as a script normally sets its own directory on sys.path.
sys.path.insert(0, str(Path.cwd() / "SABLON_V2_MIMARI"))
from SABLON_V2_MIMARI import app as webapp
root = Path(os.environ["MOCKUP_RUNTIME_WORKSPACE"])
cat = "01_Wifi_Kutusu"
name = "Wifi_Kutusu_001.png"
work = root / "2_SABLON_HAVUZU" / cat / name
backup = root / "2_SABLON_HAVUZU_ORIJINAL_YEDEK" / cat / name
old = work.read_bytes()
expected = backup.read_bytes()
# Import alone must NOT touch the database. This synthetic acceptance
# explicitly initializes its own disposable SQLite and refreshes audit.
assert not (root / "SABLON_V2_MIMARI" / "ayarlar.db").exists()
webapp.init_db()
webapp.DB_STARTUP_AUDIT = webapp.inspect_startup_schema()
assert webapp.DB_STARTUP_AUDIT["ready"], webapp.DB_STARTUP_AUDIT
client = webapp.app.test_client()
index = client.get("/")
print("INDEX_STATUS", index.status_code)
read = client.get("/api/ayarlar")
print("GET_SETTINGS_STATUS", read.status_code)
assert work.read_bytes() == old
csrf = client.get('/api/session/csrf').get_json()['csrf']
headers = {"X-Active-Category": cat, "X-Active-Template": name,
           "X-V47-CSRF": csrf}
res = client.post("/api/orijinal_yukle", headers=headers)
print("ORIGINAL_RESTORE", res.status_code, res.get_json())
assert res.status_code == 200, res.get_json()
assert work.read_bytes() == expected
assert backup.read_bytes() == expected
trash = root / "SILINEN_SABLONLAR_COP_KUTUSU"
trash.mkdir()
(trash / "a_meta.json").write_text(json.dumps({"kategori":cat,"sablon":name}), encoding="utf-8")
conflict = client.post("/api/sablon_sil_geri_al", json={}, headers={"X-V47-CSRF": csrf})
print("TRASH_COLLISION_STATUS", conflict.status_code)
assert conflict.status_code == 409
assert work.read_bytes() == expected
assert backup.read_bytes() == expected
assert (root / "_P0_WORKING_REVISIONS").is_dir()
print("P0_8080_FAKE_RUNTIME_PASS")
"""


def test_flask_8080_get_restore_and_trash_conflict_are_safe():
    with tempfile.TemporaryDirectory(prefix="p0-flask-8080-fake-") as tmp:
        runtime = Path(tmp) / "fake-runtime"
        p = runtime / "2_SABLON_HAVUZU" / CAT / NAME
        b = runtime / "2_SABLON_HAVUZU_ORIJINAL_YEDEK" / CAT / NAME
        p.parent.mkdir(parents=True)
        b.parent.mkdir(parents=True)
        for dest, value in ((p, 25), (b, 95)):
            arr = np.full((70, 90, 4), (value, 10, 75, 140), dtype=np.uint8)
            ok, buf = cv2.imencode(".png", arr)
            assert ok
            dest.write_bytes(buf.tobytes())
        env = os.environ.copy()
        env["MOCKUP_RUNTIME_WORKSPACE"] = str(runtime)
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
        result = subprocess.run(
            [sys.executable, "-B", "-c", CHILD],
            cwd=str(ROOT), env=env, text=True, capture_output=True, timeout=90,
        )
        assert result.returncode == 0, result.stdout + "\n" + result.stderr
        assert "P0_8080_FAKE_RUNTIME_PASS" in result.stdout
