"""P0 Regression Tests - Real assertions, not stubs."""
import os
import sys
import json
import glob
import unittest
import py_compile
import tempfile
import sqlite3
import shutil
from pathlib import Path
from unittest.mock import patch

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "99_SISTEM_MOTORLARI_VE_KODLAR"))

try:
    from SISTEM_MOTORU.pc_master_factory import StateManager, AsyncCloudUploader, FastExcelManager
    IMPORT_SUCCESS = True
except ImportError as e:
    IMPORT_SUCCESS = False
    IMPORT_ERROR = str(e)


class TestProductionModuleCompiles(unittest.TestCase):
    """Verify that the production module has no SyntaxErrors."""

    def test_pc_master_factory_compiles(self):
        pc_path = os.path.join(BASE_DIR, "99_SISTEM_MOTORLARI_VE_KODLAR",
                               "SISTEM_MOTORU", "pc_master_factory.py")
        try:
            py_compile.compile(pc_path, doraise=True)
        except py_compile.PyCompileError as e:
            self.fail(f"SyntaxError in pc_master_factory.py: {e}")
            
    def test_module_imports(self):
        self.assertTrue(IMPORT_SUCCESS, f"Could not import pc_master_factory: {globals().get('IMPORT_ERROR')}")

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


@unittest.skipIf(not IMPORT_SUCCESS, "Production module failed to import")
class TestSQLiteBootstrap(unittest.TestCase):
    """Verify production module can bootstrap a temp SQLite DB."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db_path = Path(self.tmp) / "test_state.db"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_state_manager_creates_db(self):
        sm = StateManager(db_path=self.db_path)
        
        # Insert a failed artifact
        with sm.conn:
            sm.conn.execute(
                "INSERT INTO render_artifacts (artifact_key, status) VALUES (?, ?)", 
                ("art-001", "UPLOAD_FAILED")
            )
        
        # Verify UPLOAD_FAILED is NOT considered completed
        is_completed = sm.is_artifact_completed("art-001")
        self.assertFalse(is_completed, "UPLOAD_FAILED must not be treated as completed by StateManager")
        
        # Simulate successful upload
        sm.save_render_artifact({
            "artifact_key": "art-001",
            "upload_url": "http://test.url",
            "status": "UPLOADED"
        })
        is_completed2 = sm.is_artifact_completed("art-001")
        self.assertTrue(is_completed2, "UPLOADED should be treated as completed")


@unittest.skipIf(not IMPORT_SUCCESS, "Production module failed to import")
class TestENVFallbackBehavior(unittest.TestCase):
    """Test that AsyncCloudUploader config values correctly fall through to ENV."""

    def test_imgbb_empty_list_filters_blanks(self):
        with patch.dict(os.environ, {"IMGBB_KEYS": ""}):
            with patch("SISTEM_MOTORU.pc_master_factory.AYARLAR", {"bulut_ayarlari": {"imgbb_keys": []}}):
                uploader = AsyncCloudUploader()
                self.assertEqual(uploader.imgbb_keys, [], "Empty env should produce empty list, not ['']")

    def test_imgbb_valid_keys_parsed(self):
        with patch.dict(os.environ, {"IMGBB_KEYS": "key1,key2"}):
            with patch("SISTEM_MOTORU.pc_master_factory.AYARLAR", {"bulut_ayarlari": {"imgbb_keys": []}}):
                uploader = AsyncCloudUploader()
                self.assertEqual(uploader.imgbb_keys, ["key1", "key2"])

    def test_freeimage_fallback(self):
        with patch.dict(os.environ, {"FREEIMAGE_KEY": "env_freeimage"}):
            with patch("SISTEM_MOTORU.pc_master_factory.AYARLAR", {"bulut_ayarlari": {"freeimage_key": ""}}):
                uploader = AsyncCloudUploader()
                self.assertEqual(uploader.freeimage_key, "env_freeimage")


@unittest.skipIf(not IMPORT_SUCCESS, "Production module failed to import")
class TestExcelFlushNoDeadlock(unittest.TestCase):
    """Verify real Excel write operations don't deadlock with threading."""

    def setUp(self):
        self.tmp = tempfile.mktemp(suffix=".xlsx")

    def tearDown(self):
        if os.path.exists(self.tmp):
            os.remove(self.tmp)

    def test_50_row_excel_flush(self):
        import threading
        
        manager = FastExcelManager(file_path=Path(self.tmp))
        
        def write_rows(start, count):
            for i in range(start, start+count):
                row_data = {
                    "Stok Kodu": f"SKU-{i:04d}",
                    "Barkod": f"BRK-{i}",
                    "Model Kodu": "MODEL1",
                    "Kategori": "TestKategori",
                    "Ham Baskı Dosyası": "a.jpg",
                    "Mağaza Grubu": "GRUP",
                    "Ürün Adı": "Urun",
                    "Açıklama": "Aciklama",
                    "Mockup Dosya Adı": "m.jpg",
                    "Resim Linki": "http://x",
                    "Eklenme Zamanı": "now"
                }
                manager.append_row(row_data)
                
        threads = []
        # Create 5 threads, each writing 10 rows
        for i in range(5):
            t = threading.Thread(target=write_rows, args=(i*10, 10))
            threads.append(t)
            t.start()
            
        for t in threads:
            t.join(timeout=5.0)
            self.assertFalse(t.is_alive(), "Thread deadlocked during Excel append")
            
        # Verify file has 51 rows (header + 50 data)
        import openpyxl
        wb2 = openpyxl.load_workbook(self.tmp)
        ws2 = wb2.active
        self.assertEqual(ws2.max_row, 51, f"Expected 51 rows, got {ws2.max_row}")
        wb2.close()


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
