import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


def run_probe(code: str, runtime: Path) -> dict:
    env = os.environ.copy()
    env["MOCKUP_RUNTIME_WORKSPACE"] = str(runtime)
    env["MOCKUP_NO_AUTO_BROWSER"] = "1"
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
    )
    if proc.returncode != 0:
        raise AssertionError(
            f"probe failed={proc.returncode}\n"
            f"stdout:\n{proc.stdout}\n"
            f"stderr:\n{proc.stderr}"
        )
    lines = [
        line
        for line in (proc.stdout or "").splitlines()
        if line.strip()
    ]
    return json.loads(lines[-1])


class TestRuntimeInfrastructure(unittest.TestCase):
    def test_schema_contains_jobs_locks_and_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_probe(
                """
import json, sys
from pathlib import Path
root = Path.cwd()
sys.path.insert(0, str(root / "SABLON_V2_MIMARI"))
from core import db
db.init_db()
conn = db.get_db_connection()
names = {
    row["name"]
    for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
}
conn.close()
print(json.dumps({
    "jobs": "jobs" in names,
    "locks": "template_operation_locks" in names,
    "cache": "analysis_cache" in names,
}))
""",
                Path(tmp),
            )
            self.assertTrue(result["jobs"])
            self.assertTrue(result["locks"])
            self.assertTrue(result["cache"])

    def test_backend_template_lock_blocks_second_owner(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_probe(
                """
import json, sys
from pathlib import Path
root = Path.cwd()
sys.path.insert(0, str(root / "SABLON_V2_MIMARI"))
from core import db
from core.operation_lock import (
    TemplateBusyError,
    acquire_template_lock,
    release_template_lock,
)
db.init_db()
first = acquire_template_lock("cat", "tmpl.png", "first")
blocked = False
try:
    acquire_template_lock(
        "cat",
        "tmpl.png",
        "second",
        wait_seconds=0,
    )
except TemplateBusyError:
    blocked = True
release_template_lock("cat", "tmpl.png", first)
third = acquire_template_lock("cat", "tmpl.png", "third")
release_template_lock("cat", "tmpl.png", third)
print(json.dumps({
    "blocked": blocked,
    "reacquired": bool(third),
}))
""",
                Path(tmp),
            )
            self.assertTrue(result["blocked"])
            self.assertTrue(result["reacquired"])

    def test_analysis_cache_is_keyed_by_source_and_analyzer_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_probe(
                """
import json, sys
from pathlib import Path
root = Path.cwd()
sys.path.insert(0, str(root / "SABLON_V2_MIMARI"))
from core import db
from core.analysis_cache import (
    load_analysis_cache,
    save_analysis_cache,
    cache_stats,
)
db.init_db()
payload = {
    "source_asset_sha256": "abc",
    "analyzer_version": "v2.8",
    "surface_quad": [[1,1],[2,1],[2,2],[1,2]],
}
save_analysis_cache("cat", "abc", "v2.8", payload)
hit1 = load_analysis_cache("cat", "abc", "v2.8")
hit2 = load_analysis_cache("cat", "abc", "v2.8")
miss_version = load_analysis_cache("cat", "abc", "v2.9")
miss_source = load_analysis_cache("cat", "def", "v2.8")
stats = cache_stats()
print(json.dumps({
    "hit1": bool(hit1 and hit1.get("_cache_hit")),
    "hit2": bool(hit2 and hit2.get("_cache_hit")),
    "miss_version": miss_version is None,
    "miss_source": miss_source is None,
    "entries": stats["entry_count"],
    "hits": stats["hit_count"],
}))
""",
                Path(tmp),
            )
            self.assertTrue(result["hit1"])
            self.assertTrue(result["hit2"])
            self.assertTrue(result["miss_version"])
            self.assertTrue(result["miss_source"])
            self.assertEqual(result["entries"], 1)
            self.assertEqual(result["hits"], 2)

    def test_app_auto_analysis_reuses_cache_without_second_analyzer_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_probe(
                """
import json, os, sys
from pathlib import Path
import cv2
import numpy as np
root = Path.cwd()
sys.path.insert(0, str(root / "SABLON_V2_MIMARI"))
import app

runtime = Path(os.environ["MOCKUP_RUNTIME_WORKSPACE"])
img_dir = runtime / "2_SABLON_HAVUZU" / "cat"
img_dir.mkdir(parents=True, exist_ok=True)
img_path = img_dir / "a.png"
cv2.imwrite(str(img_path), np.full((24, 32, 3), 90, dtype=np.uint8))

class FakeAnalyzer:
    calls = 0
    def __init__(self):
        self.version = "vcache-test"
    def analyze(self, filepath, category, manual_geometry_prior=None):
        type(self).calls += 1
        return {
            "source_asset_sha256": app._sha256_file(filepath),
            "analyzer_version": self.version,
            "surface_quad": [[1,1],[30,1],[30,22],[1,22]],
            "review_status": "REVIEW_REQUIRED",
            "rule": {},
            "orientation": "H",
            "nominal_aspect": "1.0",
            "confidence_total": 0.5,
            "component_confidences": {},
        }

app.TemplateAnalyzer = FakeAnalyzer
first, first_hit = app._analyze_auto_cached("cat", str(img_path))
second, second_hit = app._analyze_auto_cached("cat", str(img_path))
print(json.dumps({
    "calls": FakeAnalyzer.calls,
    "first_hit": first_hit,
    "second_hit": second_hit,
    "same_quad": first["surface_quad"] == second["surface_quad"],
}))
""",
                Path(tmp),
            )
            self.assertEqual(result["calls"], 1)
            self.assertFalse(result["first_hit"])
            self.assertTrue(result["second_hit"])
            self.assertTrue(result["same_quad"])

    def test_interrupted_job_recovers_with_progress_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_probe(
                """
import json, sys
from pathlib import Path
root = Path.cwd()
sys.path.insert(0, str(root / "SABLON_V2_MIMARI"))
from core import db
from core.job_engine import (
    create_job,
    get_job,
    recover_interrupted_jobs,
)
db.init_db()
job_id = create_job(
    "BATCH_CORNER_SCAN",
    {"category": "cat", "templates": ["1","2","3"]},
    progress_total=3,
)
conn = db.get_db_connection()
conn.execute(
    "UPDATE jobs SET status='RUNNING', progress_current=2 WHERE id=?",
    (job_id,),
)
conn.commit()
conn.close()
recover_interrupted_jobs()
job = get_job(job_id)
print(json.dumps({
    "status": job["status"],
    "current": job["progress_current"],
    "total": job["progress_total"],
}))
""",
                Path(tmp),
            )
            self.assertEqual(result["status"], "PENDING")
            self.assertEqual(result["current"], 2)
            self.assertEqual(result["total"], 3)

    def test_persistent_job_engine_executes_and_finishes(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_probe(
                """
import json, sys, time
from pathlib import Path
root = Path.cwd()
sys.path.insert(0, str(root / "SABLON_V2_MIMARI"))
from core import db
from core.job_engine import (
    PersistentJobEngine,
    create_job,
    get_job,
)
db.init_db()

def handler(job_id, payload, progress, should_stop):
    progress(1, 2, "half")
    progress(2, 2, "done")
    return {"completed": True, "value": payload["value"]}

job_id = create_job("TEST", {"value": 7}, progress_total=2)
engine = PersistentJobEngine({"TEST": handler}, max_workers=1)
engine.start()
deadline = time.time() + 5
job = None
while time.time() < deadline:
    job = get_job(job_id)
    if job and job["status"] in {"SUCCEEDED", "FAILED", "CANCELLED"}:
        break
    time.sleep(0.05)
engine.stop(wait=True)
print(json.dumps({
    "status": job["status"],
    "current": job["progress_current"],
    "result": job["result"],
}))
""",
                Path(tmp),
            )
            self.assertEqual(result["status"], "SUCCEEDED")
            self.assertEqual(result["current"], 2)
            self.assertEqual(result["result"]["value"], 7)

    def test_runtime_lock_and_model_revisions_are_pinned(self):
        lock = json.loads(
            (
                ROOT
                / "SABLON_V2_MIMARI"
                / "runtime_lock.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(lock["python"], "3.11")
        self.assertEqual(
            lock["analyzer_contract"],
            "v2.8",
        )
        self.assertEqual(
            lock["ai_models"]["grounding_dino"]["revision"],
            "a2bb814",
        )
        self.assertEqual(
            lock["ai_models"]["sam2_1"]["revision"],
            "ee5bba1",
        )

        foreground = (
            ROOT
            / "99_SISTEM_MOTORLARI_VE_KODLAR"
            / "SISTEM_MOTORU"
            / "foreground_ai.py"
        ).read_text(encoding="utf-8")
        self.assertIn('dino_revision = "a2bb814"', foreground)
        self.assertIn('sam_revision = "ee5bba1"', foreground)

    def test_frontend_uses_persistent_jobs(self):
        js = (
            ROOT
            / "SABLON_V2_MIMARI"
            / "static"
            / "js"
            / "main.js"
        ).read_text(encoding="utf-8")
        self.assertIn("BATCH_CORNER_SCAN", js)
        self.assertIn("RAW_HEALTH_SCAN", js)
        self.assertIn("resumePersistentJobs", js)
        self.assertIn("/api/jobs/", js)


if __name__ == "__main__":
    unittest.main()
