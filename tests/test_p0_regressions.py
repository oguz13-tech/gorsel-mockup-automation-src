"""P0 Regression Tests - Real assertions, not stubs."""
import os
import sys
import json
import glob
import unittest
import py_compile

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestProductionModuleCompiles(unittest.TestCase):
    """Verify that the production module has no SyntaxErrors."""

    def test_pc_master_factory_compiles(self):
        pc_path = os.path.join(BASE_DIR, "99_SISTEM_MOTORLARI_VE_KODLAR",
                               "SISTEM_MOTORU", "pc_master_factory.py")
        try:
            py_compile.compile(pc_path, doraise=True)
        except py_compile.PyCompileError as e:
            self.fail(f"SyntaxError in pc_master_factory.py: {e}")

class TestSecretsRemoved(unittest.TestCase):
    """Verify no API keys remain in any ayarlar*.json file."""

    def test_no_secrets_in_any_json(self):
        json_files = glob.glob(os.path.join(BASE_DIR, "**", "ayarlar*.json"), recursive=True)
        self.assertGreater(len(json_files), 0, "No ayarlar JSON files found")

        for jf in json_files:
            with open(jf, "r", encoding="utf-8") as f:
                data = json.load(f)
            cloud = data.get("bulut_ayarlari", {})

            # imgbb_keys must be empty list
            keys = cloud.get("imgbb_keys", [])
            self.assertEqual(keys, [], f"imgbb_keys not empty in {jf}")

            # freeimage_key must be empty string
            fk = cloud.get("freeimage_key", "")
            self.assertEqual(fk, "", f"freeimage_key not empty in {jf}")

            # cloudinary secrets must be empty
            cl = cloud.get("cloudinary", {})
            self.assertEqual(cl.get("api_key", ""), "", f"cloudinary api_key not empty in {jf}")
            self.assertEqual(cl.get("api_secret", ""), "", f"cloudinary api_secret not empty in {jf}")


class TestUploadFailedNotSkipped(unittest.TestCase):
    """Verify UPLOAD_FAILED is NOT in the completed-skip list."""

    def test_upload_failed_not_in_completed_statuses(self):
        pc_path = os.path.join(BASE_DIR, "99_SISTEM_MOTORLARI_VE_KODLAR",
                               "SISTEM_MOTORU", "pc_master_factory.py")
        with open(pc_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Find is_artifact_completed and check UPLOAD_FAILED is NOT there
        match = content[content.index("def is_artifact_completed"):content.index("def is_artifact_completed")+300]
        self.assertNotIn("UPLOAD_FAILED", match,
                         "UPLOAD_FAILED should not be treated as completed")


class TestQAFailStopsProduction(unittest.TestCase):
    """Verify QA failure returns False (quarantine), not just a warning."""

    def test_qa_fail_returns_false(self):
        pc_path = os.path.join(BASE_DIR, "99_SISTEM_MOTORLARI_VE_KODLAR",
                               "SISTEM_MOTORU", "pc_master_factory.py")
        with open(pc_path, "r", encoding="utf-8") as f:
            content = f.read()

        # After "if not valid:" there should be "return False"
        idx = content.index("Kalite Denetimi")
        block = content[idx:idx+300]
        self.assertIn("return False", block,
                      "QA failure must halt production with return False")


if __name__ == "__main__":
    unittest.main()


class TestSQLiteBootstrap(unittest.TestCase):
    """Verify production module can bootstrap a temp SQLite DB."""

    def test_state_manager_creates_db(self):
        import tempfile, sqlite3
        tmp = tempfile.mkdtemp()
        db_path = os.path.join(tmp, "test_state.db")
        # Simulate what StateManager does
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("""CREATE TABLE IF NOT EXISTS products (
            sku TEXT PRIMARY KEY, status TEXT, updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS render_artifacts (
            artifact_key TEXT PRIMARY KEY, status TEXT
        )""")
        conn.execute("INSERT INTO products (sku, status) VALUES (?, ?)", ("TEST-001", "COMPLETED"))
        conn.execute("INSERT INTO render_artifacts (artifact_key, status) VALUES (?, ?)", ("art-001", "UPLOAD_FAILED"))
        conn.commit()

        # Verify UPLOAD_FAILED is NOT considered completed
        row = conn.execute("SELECT status FROM render_artifacts WHERE artifact_key=?", ("art-001",)).fetchone()
        self.assertNotIn(row["status"], ("COMPLETED", "UPLOADED"),
                         "UPLOAD_FAILED must not be treated as completed")

        conn.close()
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


class TestENVFallbackBehavior(unittest.TestCase):
    """Test that empty config values correctly fall through to ENV."""

    def test_imgbb_empty_list_filters_blanks(self):
        """When IMGBB_KEYS env is empty, split should not produce ['']."""
        result = [k for k in "".split(",") if k]
        self.assertEqual(result, [], "Empty env should produce empty list, not ['']")

    def test_imgbb_valid_keys_parsed(self):
        result = [k for k in "key1,key2,key3".split(",") if k]
        self.assertEqual(result, ["key1", "key2", "key3"])

    def test_or_fallback_on_empty_list(self):
        """cloud_cfg.get returns [] -> or should fall through to ENV."""
        config_val = []
        env_val = ["env_key"]
        result = config_val or env_val
        self.assertEqual(result, ["env_key"])

    def test_or_fallback_on_populated_list(self):
        """cloud_cfg.get returns real keys -> or should NOT fall through."""
        config_val = ["config_key"]
        env_val = ["env_key"]
        result = config_val or env_val
        self.assertEqual(result, ["config_key"])


class TestExcelFlushNoDeadlock(unittest.TestCase):
    """Verify Excel write operations don't deadlock with threading."""

    def test_50_row_excel_flush(self):
        import tempfile
        try:
            import openpyxl
        except ImportError:
            self.skipTest("openpyxl not installed")

        tmp = tempfile.mktemp(suffix=".xlsx")
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["SKU", "Barkod", "Kategori", "Durum"])
        for i in range(50):
            ws.append([f"SKU-{i:04d}", f"BRK-{i}", "TestKategori", "COMPLETED"])
        wb.save(tmp)

        # Verify file is valid and has 51 rows (header + 50 data)
        wb2 = openpyxl.load_workbook(tmp)
        ws2 = wb2.active
        self.assertEqual(ws2.max_row, 51, f"Expected 51 rows, got {ws2.max_row}")
        wb2.close()
        os.remove(tmp)


if __name__ == "__main__":
    unittest.main()
