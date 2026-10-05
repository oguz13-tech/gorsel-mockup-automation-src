"""
T1 Test: Delete -> Undo -> SHA Integrity Check
Tests the actual Flask delete/undo flow with SHA hash verification.
"""
import os
import sys
import json
import hashlib
import unittest
import tempfile
import shutil

# Add parent to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "SABLON_V2_MIMARI")))

from app import app
import core.db as db_core

class TestT1DeleteUndoIntegrity(unittest.TestCase):
    """Test that deleting and undoing a template preserves data integrity."""

    def setUp(self):
        """Set up a test DB and Flask client."""
        app.config['TESTING'] = True
        self.client = app.test_client()
        
        # We need to temporarily mock the DB path in db_core to point to a temp file
        self.test_dir = tempfile.mkdtemp()
        self.test_db = os.path.join(self.test_dir, "ayarlar.db")
        
        # Patch the db connection string in db_core
        self.original_db_path = getattr(db_core, "DB_PATH", None)
        db_core.DB_PATH = self.test_db
        
        # A bit hacky: we override get_db_connection
        self.original_get_db_connection = db_core.get_db_connection
        
        def mock_get_db_connection():
            import sqlite3
            conn = sqlite3.connect(self.test_db)
            conn.row_factory = sqlite3.Row
            return conn
            
        db_core.get_db_connection = mock_get_db_connection
        
        # Initialize schema
        db_core.init_db()

        # Insert a test template with known data
        import sqlite3
        conn = mock_get_db_connection()
        c = conn.cursor()
        self.test_data = {
            "tip": "perspektif",
            "koseler": [[100,200],[300,200],[300,400],[100,400]],
            "x": 100, "y": 200, "w": 200, "h": 200
        }
        self.test_data_json = json.dumps(self.test_data, ensure_ascii=False)
        self.test_data_sha = hashlib.sha256(self.test_data_json.encode()).hexdigest()
        
        c.execute("INSERT INTO categories (id, label) VALUES (?, ?)", ("test_cat", "Test Category"))

        c.execute("INSERT INTO templates (category_id, filename, data) VALUES (?, ?, ?)",
                  ("test_cat", "test_tmpl.png", self.test_data_json))
        conn.commit()
        conn.close()
        
        # Create physical test image
        self.img_dir = os.path.join(self.test_dir, "2_SABLON_HAVUZU", "test_cat")
        os.makedirs(self.img_dir, exist_ok=True)
        self.img_path = os.path.join(self.img_dir, "test_tmpl.png")
        
        # Write dummy image data
        with open(self.img_path, "wb") as f:
            f.write(b"dummy image data for SHA test")
            
        with open(self.img_path, "rb") as f:
            self.file_sha = hashlib.sha256(f.read()).hexdigest()
        
        # Mock app.py's direct sqlite3 connections to use our temp DB
        self.app_sqlite3_connect = sqlite3.connect
        def mock_app_sqlite3_connect(db_path, *args, **kwargs):
            if "ayarlar.db" in db_path:
                return self.app_sqlite3_connect(self.test_db, *args, **kwargs)
            return self.app_sqlite3_connect(db_path, *args, **kwargs)
            
        import app as app_module
        app_module.sqlite3.connect = mock_app_sqlite3_connect
        self.original_app_base_dir = getattr(app_module, "BASE_DIR", None)
        app_module.BASE_DIR = self.test_dir

    def tearDown(self):
        db_core.get_db_connection = self.original_get_db_connection
        if hasattr(self, 'original_db_path'):
            db_core.DB_PATH = self.original_db_path
            
        import app as app_module
        app_module.sqlite3.connect = self.app_sqlite3_connect
        if hasattr(self, 'original_app_base_dir'):
            app_module.BASE_DIR = self.original_app_base_dir
            
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_delete_preserves_data_for_undo(self):
        """Simulate delete -> verify data gone -> undo -> verify SHA matches."""
        # Step 1: Read original
        conn = db_core.get_db_connection()
        row = conn.execute(
            "SELECT data FROM templates WHERE category_id=? AND filename=?",
            ("test_cat", "test_tmpl.png")
        ).fetchone()
        original_sha = hashlib.sha256(row["data"].encode()).hexdigest()
        self.assertEqual(original_sha, self.test_data_sha)

        # Step 2: Delete via Flask Endpoint
        res = self.client.post('/api/sablon_sil', headers={
            "X-Active-Category": "test_cat",
            "X-Active-Template": "test_tmpl.png"
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])

        # Verify deleted in DB
        row = conn.execute(
            "SELECT data FROM templates WHERE category_id=? AND filename=?",
            ("test_cat", "test_tmpl.png")
        ).fetchone()
        self.assertIsNone(row, "Template should be deleted")
        
        # Verify physical file is gone
        self.assertFalse(os.path.exists(self.img_path), "Physical image file should be moved/deleted")
        
        # Verify physical file is in trash through the durable recovery
        # metadata returned by the endpoint. Trash filenames are intentionally
        # collision-safe and therefore are not the original filename.
        trash_dir = os.path.join(
            self.test_dir,
            "SILINEN_SABLONLAR_COP_KUTUSU",
        )
        trash_record = data.get("trash_record")
        self.assertTrue(trash_record, "Delete must return a recovery record")
        meta_path = os.path.join(trash_dir, trash_record)
        self.assertTrue(os.path.isfile(meta_path), "Recovery metadata should exist")
        with open(meta_path, "r", encoding="utf-8") as handle:
            recovery = json.load(handle)
        trash_path = os.path.join(trash_dir, recovery["trash_image_name"])
        self.assertTrue(os.path.exists(trash_path), "Physical file should be in trash")

        # Step 3: Undo via Flask Endpoint (re-insert with original data)
        res = self.client.post('/api/sablon_sil_geri_al')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json()["success"])

        # Step 4: Verify SHA integrity
        row = conn.execute(
            "SELECT data FROM templates WHERE category_id=? AND filename=?",
            ("test_cat", "test_tmpl.png")
        ).fetchone()
        restored_sha = hashlib.sha256(row["data"].encode()).hexdigest()
        self.assertEqual(restored_sha, self.test_data_sha,
                         "SHA mismatch after undo! Data corruption detected.")
                         
        # Verify physical file restored
        self.assertTrue(os.path.exists(self.img_path), "Physical image file should be restored")
        with open(self.img_path, "rb") as f:
            restored_file_sha = hashlib.sha256(f.read()).hexdigest()
        self.assertEqual(restored_file_sha, self.file_sha, "Physical file SHA mismatch after undo!")
        
        conn.close()

    def test_delete_blocks_when_source_image_is_missing(self):
        os.remove(self.img_path)

        res = self.client.post('/api/sablon_sil', headers={
            "X-Active-Category": "test_cat",
            "X-Active-Template": "test_tmpl.png",
        })

        self.assertEqual(res.status_code, 409)
        self.assertEqual(res.get_json().get("code"), "SOURCE_IMAGE_MISSING")

        conn = db_core.get_db_connection()
        try:
            row = conn.execute(
                "SELECT data FROM templates WHERE category_id=? AND filename=?",
                ("test_cat", "test_tmpl.png"),
            ).fetchone()
            self.assertIsNotNone(
                row,
                "DB row must remain when reversible delete cannot preserve image",
            )
        finally:
            conn.close()

    def test_undo_blocks_when_trash_image_is_missing(self):
        deleted = self.client.post('/api/sablon_sil', headers={
            "X-Active-Category": "test_cat",
            "X-Active-Template": "test_tmpl.png",
        })
        self.assertEqual(deleted.status_code, 200)
        body = deleted.get_json()
        trash_dir = os.path.join(
            self.test_dir,
            "SILINEN_SABLONLAR_COP_KUTUSU",
        )
        meta_path = os.path.join(trash_dir, body["trash_record"])
        with open(meta_path, "r", encoding="utf-8") as handle:
            recovery = json.load(handle)
        trash_path = os.path.join(trash_dir, recovery["trash_image_name"])
        os.remove(trash_path)

        restored = self.client.post('/api/sablon_sil_geri_al')
        self.assertEqual(restored.status_code, 409)
        self.assertEqual(
            restored.get_json().get("code"),
            "TRASH_IMAGE_MISSING",
        )
        self.assertTrue(
            os.path.isfile(meta_path),
            "Recovery metadata must remain for investigation/manual recovery",
        )

        conn = db_core.get_db_connection()
        try:
            row = conn.execute(
                "SELECT data FROM templates WHERE category_id=? AND filename=?",
                ("test_cat", "test_tmpl.png"),
            ).fetchone()
            self.assertIsNone(
                row,
                "Undo must not recreate a DB row without its source image",
            )
        finally:
            conn.close()

    def test_undo_marks_old_approval_stale_if_trash_bytes_changed(self):
        conn = db_core.get_db_connection()
        try:
            conn.execute(
                """INSERT INTO template_profiles (
                       template_uid, category, source_relative_path,
                       source_asset_sha256, review_status,
                       manually_verified, is_active
                   ) VALUES (?, ?, ?, ?, 'APPROVED', 1, 1)""",
                (
                    "test_cat_test_tmpl.png",
                    "test_cat",
                    "test_cat/test_tmpl.png",
                    self.file_sha,
                ),
            )
            conn.commit()
        finally:
            conn.close()

        deleted = self.client.post('/api/sablon_sil', headers={
            "X-Active-Category": "test_cat",
            "X-Active-Template": "test_tmpl.png",
        })
        self.assertEqual(deleted.status_code, 200)
        body = deleted.get_json()
        trash_dir = os.path.join(
            self.test_dir,
            "SILINEN_SABLONLAR_COP_KUTUSU",
        )
        meta_path = os.path.join(trash_dir, body["trash_record"])
        with open(meta_path, "r", encoding="utf-8") as handle:
            recovery = json.load(handle)
        trash_path = os.path.join(trash_dir, recovery["trash_image_name"])

        with open(trash_path, "ab") as handle:
            handle.write(b"-modified-after-delete")

        restored = self.client.post('/api/sablon_sil_geri_al')
        self.assertEqual(restored.status_code, 200)

        conn = db_core.get_db_connection()
        try:
            row = conn.execute(
                """SELECT review_status, manually_verified
                   FROM template_profiles
                   WHERE template_uid=? AND is_active=1""",
                ("test_cat_test_tmpl.png",),
            ).fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row["review_status"], "STALE_SOURCE_CHANGED")
            self.assertEqual(row["manually_verified"], 0)
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
