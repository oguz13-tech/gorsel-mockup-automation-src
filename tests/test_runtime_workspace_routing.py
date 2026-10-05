import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


def _run_probe(code: str, runtime_root: Path) -> dict:
    env = os.environ.copy()
    env["MOCKUP_RUNTIME_WORKSPACE"] = str(runtime_root)
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        raise AssertionError(
            f"Probe failed (exit={proc.returncode})\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )
    line = (proc.stdout or "").strip().splitlines()[-1]
    return json.loads(line)


class TestRuntimeWorkspaceRouting(unittest.TestCase):
    def test_template_db_routes_to_runtime_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Path(tmp).resolve()
            result = _run_probe(
                """
import json, os, sys
from pathlib import Path
root = Path.cwd()
sys.path.insert(0, str(root / "SABLON_V2_MIMARI"))
from core import db
print(json.dumps({"db_path": os.path.abspath(db.DB_PATH)}))
""",
                runtime,
            )
            expected = runtime / "SABLON_V2_MIMARI" / "ayarlar.db"
            self.assertEqual(
                os.path.normcase(result["db_path"]),
                os.path.normcase(str(expected)),
            )

    def test_review_app_uses_runtime_data_but_source_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Path(tmp).resolve()
            result = _run_probe(
                """
import json, os, sys
from pathlib import Path
root = Path.cwd()
sys.path.insert(0, str(root / "SABLON_V2_MIMARI"))
import app
print(json.dumps({
    "base_dir": os.path.abspath(app.BASE_DIR),
    "source_root": os.path.abspath(app.SOURCE_ROOT),
}))
""",
                runtime,
            )
            self.assertEqual(
                os.path.normcase(result["base_dir"]),
                os.path.normcase(str(runtime)),
            )
            self.assertEqual(
                os.path.normcase(result["source_root"]),
                os.path.normcase(str(ROOT)),
            )
            self.assertNotEqual(
                os.path.normcase(result["base_dir"]),
                os.path.normcase(result["source_root"]),
            )

    def test_legacy_migration_routes_mutable_paths_to_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Path(tmp).resolve()
            result = _run_probe(
                """
import importlib.util, json, os
from pathlib import Path
root = Path.cwd()
path = root / "scripts" / "migrate_legacy_geometry_profiles.py"
spec = importlib.util.spec_from_file_location("migration_runtime_probe", path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
print(json.dumps({
    "source_root": os.path.abspath(str(mod.SOURCE_ROOT)),
    "runtime_root": os.path.abspath(str(mod.RUNTIME_ROOT)),
    "db_path": os.path.abspath(str(mod.DB_PATH)),
    "template_root": os.path.abspath(str(mod.TEMPLATE_ROOT)),
}))
""",
                runtime,
            )
            self.assertEqual(
                os.path.normcase(result["source_root"]),
                os.path.normcase(str(ROOT)),
            )
            self.assertEqual(
                os.path.normcase(result["runtime_root"]),
                os.path.normcase(str(runtime)),
            )
            self.assertEqual(
                os.path.normcase(result["db_path"]),
                os.path.normcase(
                    str(runtime / "SABLON_V2_MIMARI" / "ayarlar.db")
                ),
            )
            self.assertEqual(
                os.path.normcase(result["template_root"]),
                os.path.normcase(str(runtime / "2_SABLON_HAVUZU")),
            )

    def test_factory_readonly_sqlite_connection_blocks_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Path(tmp).resolve()
            result = _run_probe(
                """
import importlib.util, json, os, sqlite3
from pathlib import Path
root = Path.cwd()
factory_path = (
    root
    / "99_SISTEM_MOTORLARI_VE_KODLAR"
    / "SISTEM_MOTORU"
    / "pc_master_factory.py"
)
spec = importlib.util.spec_from_file_location("factory_readonly_probe", factory_path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

db_path = Path(os.environ["MOCKUP_RUNTIME_WORKSPACE"]) / "readonly_probe.db"
writer = sqlite3.connect(str(db_path))
writer.execute("CREATE TABLE sample(value INTEGER)")
writer.commit()
writer.close()

reader = mod.open_sqlite_readonly(db_path)
blocked = False
try:
    reader.execute("INSERT INTO sample(value) VALUES (1)")
    reader.commit()
except sqlite3.OperationalError:
    blocked = True
finally:
    reader.close()

check = sqlite3.connect(str(db_path))
count = check.execute("SELECT COUNT(*) FROM sample").fetchone()[0]
check.close()
print(json.dumps({"blocked": blocked, "count": count}))
""",
                runtime,
            )
            self.assertTrue(result["blocked"])
            self.assertEqual(result["count"], 0)

    def test_control_center_uses_source_scripts_and_runtime_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Path(tmp).resolve()
            result = _run_probe(
                """
import importlib.util, json, os
from pathlib import Path
root = Path.cwd()
path = root / "V2_KONTROL_MERKEZI" / "app.py"
spec = importlib.util.spec_from_file_location("control_runtime_probe", path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
print(json.dumps({
    "base_dir": os.path.abspath(mod.BASE_DIR),
    "source_root": os.path.abspath(mod.SOURCE_ROOT),
    "sys_motors": os.path.abspath(mod.SYS_MOTORS_DIR),
    "template_center": os.path.abspath(mod.TEMPLATE_CENTER_DIR),
    "runtime_template_center": os.path.abspath(mod.RUNTIME_TEMPLATE_CENTER_DIR),
}))
""",
                runtime,
            )
            self.assertEqual(
                os.path.normcase(result["base_dir"]),
                os.path.normcase(str(runtime)),
            )
            self.assertEqual(
                os.path.normcase(result["source_root"]),
                os.path.normcase(str(ROOT)),
            )
            self.assertTrue(
                os.path.normcase(result["sys_motors"]).startswith(
                    os.path.normcase(str(ROOT))
                )
            )
            self.assertTrue(
                os.path.normcase(result["template_center"]).startswith(
                    os.path.normcase(str(ROOT))
                )
            )
            self.assertEqual(
                os.path.normcase(result["runtime_template_center"]),
                os.path.normcase(str(runtime / "SABLON_V2_MIMARI")),
            )


if __name__ == "__main__":
    unittest.main()
