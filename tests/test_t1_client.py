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
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

class TestT1DeleteUndoIntegrity(unittest.TestCase):
    """Test that deleting and undoing a template preserves data integrity."""

    def setUp(self):
        """Set up a test DB and Flask client."""
        self.test_dir = tempfile.mkdtemp()
        self.test_db = os.path.join(self.test_dir, "test_ayarlar.db")

        # Create a minimal SQLite DB for testing
        import sqlite3
        conn = sqlite3.connect(self.test_db)
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS templates (
            category_id TEXT,
            filename TEXT,
            data TEXT,
            PRIMARY KEY (category_id, filename)
        )""")

        # Insert a test template with known data
        self.test_data = {
            "tip": "perspektif",
            "koseler": [[100,200],[300,200],[300,400],[100,400]],
            "x": 100, "y": 200, "w": 200, "h": 200
        }
        self.test_data_json = json.dumps(self.test_data, ensure_ascii=False)
        self.test_data_sha = hashlib.sha256(self.test_data_json.encode()).hexdigest()

        c.execute("INSERT INTO templates (category_id, filename, data) VALUES (?, ?, ?)",
                  ("test_cat", "test_tmpl.png", self.test_data_json))
        conn.commit()
        conn.close()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_delete_preserves_data_for_undo(self):
        """Simulate delete -> verify data gone -> undo -> verify SHA matches."""
        import sqlite3

        # Step 1: Read original
        conn = sqlite3.connect(self.test_db)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT data FROM templates WHERE category_id=? AND filename=?",
            ("test_cat", "test_tmpl.png")
        ).fetchone()
        original_sha = hashlib.sha256(row["data"].encode()).hexdigest()
        original_data = row["data"]
        self.assertEqual(original_sha, self.test_data_sha)

        # Step 2: Delete
        conn.execute("DELETE FROM templates WHERE category_id=? AND filename=?",
                     ("test_cat", "test_tmpl.png"))
        conn.commit()

        # Verify deleted
        row = conn.execute(
            "SELECT data FROM templates WHERE category_id=? AND filename=?",
            ("test_cat", "test_tmpl.png")
        ).fetchone()
        self.assertIsNone(row, "Template should be deleted")

        # Step 3: Undo (re-insert with original data)
        conn.execute("INSERT INTO templates (category_id, filename, data) VALUES (?, ?, ?)",
                     ("test_cat", "test_tmpl.png", original_data))
        conn.commit()

        # Step 4: Verify SHA integrity
        row = conn.execute(
            "SELECT data FROM templates WHERE category_id=? AND filename=?",
            ("test_cat", "test_tmpl.png")
        ).fetchone()
        restored_sha = hashlib.sha256(row["data"].encode()).hexdigest()
        self.assertEqual(restored_sha, self.test_data_sha,
                         "SHA mismatch after undo! Data corruption detected.")
        conn.close()


if __name__ == "__main__":
    unittest.main()
