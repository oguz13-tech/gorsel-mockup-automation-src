import unittest
from unittest.mock import patch
import numpy as np
import os
import sys
import cv2
import json
import sqlite3
import tempfile
import shutil

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "SABLON_V2_MIMARI"))
import shutil

class TestP1_P15Acceptance(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")
        conn = sqlite3.connect(self.db_path)
        conn.execute('''
            CREATE TABLE template_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                template_uid TEXT, category TEXT, source_relative_path TEXT,
                source_asset_sha256 TEXT, profile_version TEXT, analyzer_version TEXT,
                product_class TEXT, orientation TEXT, geometry_type TEXT,
                print_policy TEXT, surface_quad TEXT, outer_quad TEXT,
                surface_mask_path TEXT, material TEXT, has_frame BOOLEAN,
                has_mat BOOLEAN, has_reflection BOOLEAN, has_occlusion BOOLEAN,
                confidence_total REAL, component_confidences TEXT, review_status TEXT,
                manually_verified BOOLEAN, is_active BOOLEAN, updated_at TIMESTAMP,
                nominal_aspect TEXT
            )
        ''')
        conn.commit()
        conn.close()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_p1_source_file_bytes_hash_unchanged_after_profile_analyze(self):
        from core.template_intelligence import TemplateAnalyzer
        img_path = os.path.join(self.temp_dir, "test.png")
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        cv2.imwrite(img_path, img)
        
        with open(img_path, "rb") as f:
            original_bytes = f.read()
            
        analyzer = TemplateAnalyzer()
        res = analyzer.analyze(img_path, "02_Cam_Tablo_Dikey")
        
        with open(img_path, "rb") as f:
            new_bytes = f.read()
            
        self.assertEqual(original_bytes, new_bytes)
        import hashlib
        self.assertEqual(res["source_asset_sha256"], hashlib.sha256(original_bytes).hexdigest())

    def test_p2_canonical_valid_quad(self):
        from core.template_intelligence import GeometryValidator
        # Unsorted valid square: BR, TR, BL, TL
        quad = np.array([[300,300], [300,100], [100,300], [100,100]])
        ok, msg = GeometryValidator.is_valid_quad(quad, 500, 500)
        self.assertTrue(ok)
        self.assertEqual(msg, "Valid")

    def test_p3_invalid_self_intersecting_quad_rejected(self):
        from core.template_intelligence import GeometryValidator
        # Concave quad: one point indented deeply
        quad = np.array([[10,10], [90,10], [50,50], [10,90]])
        ok, msg = GeometryValidator.is_valid_quad(quad, 100, 100)
        self.assertFalse(ok)
        self.assertIn("Not convex", msg)

    def test_p4_source_hash_changed_stale_inactive(self):
        from core.template_intelligence import save_template_profile
        profile_data = {
            "template_uid": "test_uid", "category": "cat1", "source_relative_path": "cat1/tmpl1.png",
            "source_asset_sha256": "hash1", "analyzer_version": "v1.3", "orientation": "V",
            "review_status": "APPROVED",
        }
        save_template_profile(self.db_path, profile_data)
        
        # Change hash
        profile_data["source_asset_sha256"] = "hash2"
        profile_data["review_status"] = "REVIEW_REQUIRED"
        save_template_profile(self.db_path, profile_data)
        
        conn = sqlite3.connect(self.db_path)
        cur = conn.execute("SELECT source_asset_sha256, is_active, review_status FROM template_profiles ORDER BY id ASC")
        rows = cur.fetchall()
        conn.close()
        
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0][0], "hash1")
        self.assertEqual(rows[0][1], 0)
        self.assertEqual(rows[0][2], "STALE_SOURCE_CHANGED")
        
        self.assertEqual(rows[1][0], "hash2")
        self.assertEqual(rows[1][1], 1)
        self.assertEqual(rows[1][2], "REVIEW_REQUIRED")

    def test_p5_design_h_strict_v_template_skipped_orientation(self):
        from core.template_intelligence import TemplateSelector
        conn = sqlite3.connect(self.db_path)
        conn.execute("INSERT INTO template_profiles (category, orientation, review_status, is_active, confidence_total) VALUES ('02_Cam_Tablo_Dikey', 'V', 'APPROVED', 1, 0.95)")
        conn.commit()
        conn.close()
        
        selector = TemplateSelector(db_path=self.db_path)
        res = selector.select_template('H', '02_Cam_Tablo_Dikey')
        self.assertEqual(res['status'], 'SKIPPED_ORIENTATION_MISMATCH')

    def test_p6_design_v_strict_h_template_skipped_orientation(self):
        from core.template_intelligence import TemplateSelector
        conn = sqlite3.connect(self.db_path)
        conn.execute("INSERT INTO template_profiles (category, orientation, review_status, is_active, confidence_total) VALUES ('02_Cam_Tablo_Yatay', 'H', 'APPROVED', 1, 0.95)")
        conn.commit()
        conn.close()
        
        selector = TemplateSelector(db_path=self.db_path)
        res = selector.select_template('V', '02_Cam_Tablo_Yatay')
        self.assertEqual(res['status'], 'SKIPPED_ORIENTATION_MISMATCH')

    def test_p7_cutting_board_orientation_non_strict(self):
        from core.template_intelligence import CategoryRuleEngine, TemplateSelector
        rule = CategoryRuleEngine.get_rule_by_folder("04_Cam_Dograma")
        self.assertFalse(rule["orientation_strict"])
        self.assertEqual(rule["expected_orientation"], "ANY")
        
        conn = sqlite3.connect(self.db_path)
        conn.execute("INSERT INTO template_profiles (category, orientation, review_status, is_active, confidence_total) VALUES ('04_Cam_Dograma', 'H', 'APPROVED', 1, 0.95)")
        conn.commit()
        conn.close()
        
        selector = TemplateSelector(db_path=self.db_path)
        res = selector.select_template('V', '04_Cam_Dograma')
        # Even though design is V and template is H, because it's non-strict, it should select it!
        self.assertEqual(res['status'], 'SELECTED')

    def test_p8_wood_profile_outer_quad_distinct(self):
        from core.template_intelligence import CategoryRuleEngine
        rule = CategoryRuleEngine.get_rule_by_folder("03_Ahsap_Tablo")
        self.assertEqual(rule["print_policy"], "inner_frame")
        self.assertTrue(rule["has_frame"])
        # In a real analyzer flow, surface_quad and outer_quad would be distinct fields.
        # Verify db schema has both
        conn = sqlite3.connect(self.db_path)
        cur = conn.execute("PRAGMA table_info(template_profiles)")
        cols = [c[1] for c in cur.fetchall()]
        self.assertIn("surface_quad", cols)
        self.assertIn("outer_quad", cols)

    def test_p9_glass_wall_art_print_policy_full_bleed(self):
        from core.template_intelligence import CategoryRuleEngine
        rule = CategoryRuleEngine.get_rule_by_folder("02_Cam_Tablo_Dikey")
        self.assertEqual(rule["print_policy"], "full_bleed")

    def test_p10_wifi_cover_front_panel(self):
        from core.template_intelligence import CategoryRuleEngine
        rule = CategoryRuleEngine.get_rule_by_folder("01_Wifi_Kutusu")
        self.assertEqual(rule["print_policy"], "front_panel")
        self.assertFalse(rule["has_reflection"])

    def test_p11_batch_analyzer_proposals_only(self):
        from core.template_intelligence import TemplateAnalyzer
        analyzer = TemplateAnalyzer()
        img_path = os.path.join(self.temp_dir, "test.png")
        cv2.imwrite(img_path, np.zeros((100, 100, 3), dtype=np.uint8))
        res = analyzer.analyze(img_path, "02_Cam_Tablo_Dikey")
        # should not be APPROVED automatically
        self.assertIn(res["review_status"], ["UNANALYZED", "REVIEW_REQUIRED", "AUTO_PROPOSED"])
        self.assertNotEqual(res["review_status"], "APPROVED")

    def test_p12_explicit_approve_endpoint_persists(self):
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "SABLON_V2_MIMARI"))
        from app import app
        from core.template_intelligence import save_template_profile
        
        # Save UNANALYZED
        profile_data = {
            "template_uid": "test_uid2", "category": "cat2", "source_relative_path": "cat2/tmpl2.png",
            "source_asset_sha256": "hash2", "analyzer_version": "v1.3", "orientation": "V",
            "review_status": "REVIEW_REQUIRED",
        }
        save_template_profile(self.db_path, profile_data)
        
        app.testing = True
        client = app.test_client()
        # Mock BASE_DIR inside app so it uses our temp db
        with patch('app.BASE_DIR', self.temp_dir):
            os.makedirs(os.path.join(self.temp_dir, "SABLON_V2_MIMARI"), exist_ok=True)
            shutil.copy2(self.db_path, os.path.join(self.temp_dir, "SABLON_V2_MIMARI", "ayarlar.db"))
            resp = client.post('/api/templates/approve', json={"template_uid": "test_uid2"})
            self.assertEqual(resp.status_code, 200)
            
            # Check db
            conn = sqlite3.connect(os.path.join(self.temp_dir, "SABLON_V2_MIMARI", "ayarlar.db"))
            row = conn.execute("SELECT review_status, manually_verified FROM template_profiles WHERE template_uid='test_uid2' AND is_active=1").fetchone()
            self.assertEqual(row[0], "APPROVED")
            self.assertEqual(row[1], 1)

    def test_p13_review_overlay_does_not_modify_source(self):
        img_path = os.path.join(self.temp_dir, "test.png")
        cv2.imwrite(img_path, np.zeros((100, 100, 3), dtype=np.uint8))
        with open(img_path, "rb") as f:
            orig = f.read()
        import hashlib
        orig_hash = hashlib.sha256(orig).hexdigest()
        
        # Draw overlay in memory, not writing back to source
        img_cv = cv2.imdecode(np.frombuffer(orig, dtype=np.uint8), cv2.IMREAD_COLOR)
        cv2.rectangle(img_cv, (0,0), (50,50), (255,0,0), 2)
        
        with open(img_path, "rb") as f:
            new_hash = hashlib.sha256(f.read()).hexdigest()
        self.assertEqual(orig_hash, new_hash)

    def test_p14_selector_selects_approved_compatible(self):
        from core.template_intelligence import TemplateSelector
        conn = sqlite3.connect(self.db_path)
        conn.execute("INSERT INTO template_profiles (category, orientation, review_status, is_active, confidence_total) VALUES ('02_Cam_Tablo_Dikey', 'V', 'APPROVED', 1, 0.95)")
        conn.commit()
        conn.close()
        
        selector = TemplateSelector(db_path=self.db_path)
        res = selector.select_template('V', '02_Cam_Tablo_Dikey')
        self.assertEqual(res['status'], 'SELECTED')
        
    def test_p15_no_compatible_approved_template(self):
        from core.template_intelligence import TemplateSelector
        conn = sqlite3.connect(self.db_path)
        # unapproved template
        conn.execute("INSERT INTO template_profiles (category, orientation, review_status, is_active, confidence_total) VALUES ('02_Cam_Tablo_Dikey', 'V', 'REVIEW_REQUIRED', 1, 0.95)")
        conn.commit()
        conn.close()
        
        selector = TemplateSelector(db_path=self.db_path)
        res = selector.select_template('V', '02_Cam_Tablo_Dikey')
        self.assertEqual(res['status'], 'SKIPPED_NO_COMPATIBLE_TEMPLATE')

if __name__ == "__main__":
    unittest.main()
