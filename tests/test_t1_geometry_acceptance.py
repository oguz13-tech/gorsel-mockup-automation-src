import os
import tempfile
import shutil
import unittest
from pathlib import Path
import numpy as np
import cv2
import sqlite3
import json

from unittest.mock import patch

class TestT1GeometryAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create temp environment
        cls.tmp_dir = tempfile.mkdtemp()
        cls.db_path = Path(cls.tmp_dir) / "test_geometry.db"
        cls.sablon_dir = Path(cls.tmp_dir) / "2_SABLON_HAVUZU"
        cls.sablon_dir.mkdir(parents=True)
        
        # Initialize test DB schema for template_profiles
        conn = sqlite3.connect(str(cls.db_path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS template_profiles (
                template_uid TEXT PRIMARY KEY,
                category TEXT,
                source_relative_path TEXT,
                source_asset_sha256 TEXT,
                profile_version TEXT,
                analyzer_version TEXT,
                product_class TEXT,
                orientation TEXT,
                geometry_type TEXT,
                print_policy TEXT,
                surface_quad TEXT,
                outer_quad TEXT,
                surface_mask_path TEXT,
                material TEXT,
                has_frame BOOLEAN,
                has_mat BOOLEAN,
                has_reflection BOOLEAN,
                has_occlusion BOOLEAN,
                confidence_total REAL,
                component_confidences TEXT,
                review_status TEXT,
                manually_verified BOOLEAN,
                updated_at TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp_dir, ignore_errors=True)

    def setUp(self):
        # Set up a fake image in SABLON_HAVUZU
        self.cat_name = "02_Cam_Tablo_Dikey"
        self.tmpl_name = "test_tmpl.png"
        
        self.cat_dir = self.sablon_dir / self.cat_name
        self.cat_dir.mkdir(exist_ok=True)
        self.img_path = self.cat_dir / self.tmpl_name
        
        # Create a simple image with a clear inner rectangle to simulate a template
        # 100x100 image
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        # Draw a white rectangle from (10,10) to (90,90)
        cv2.rectangle(img, (10, 10), (90, 90), (255, 255, 255), -1)
        cv2.imwrite(str(self.img_path), img)
        
    def test_t1_endpoint_geometry_analysis(self):
        # We will test the TemplateAnalyzer directly or via a mock Flask client.
        # Given we want to test TemplateAnalyzer features (manual prior, confidence, normalization, homography)
        # we'll test the core component that would be called by the T1 workflow.
        from SABLON_V2_MIMARI.core.template_intelligence import TemplateAnalyzer
        
        analyzer = TemplateAnalyzer()
        
        # 1. Test standard analysis
        result = analyzer.analyze(str(self.img_path), self.cat_name)
        
        self.assertIsNotNone(result["surface_quad"])
        # Should be normalized TL, TR, BR, BL
        quad = result["surface_quad"]
        # Basic check for ordering
        self.assertTrue(quad[0][0] < 50 and quad[0][1] < 50) # TL
        self.assertTrue(quad[1][0] > 50 and quad[1][1] < 50) # TR
        self.assertTrue(quad[2][0] > 50 and quad[2][1] > 50) # BR
        self.assertTrue(quad[3][0] < 50 and quad[3][1] > 50) # BL
        
        # Check confidences
        self.assertIn("component_confidences", result)
        self.assertIn("candidate_agreement", result["component_confidences"])
        
        # 2. Test manual geometry prior override
        manual_prior = {
            "surface_quad": [[0,0], [100,0], [100,100], [0,100]]
        }
        result_manual = analyzer.analyze(str(self.img_path), self.cat_name, manual_geometry_prior=manual_prior)
        
        self.assertEqual(result_manual["surface_quad"], manual_prior["surface_quad"])
        self.assertEqual(result_manual["confidence_total"], 1.0)
        
        # 3. Test Homography Condition Testing (Invalid collinear points)
        collinear_prior = {
            "surface_quad": [[10,10], [20,20], [30,30], [40,40]]
        }
        result_invalid = analyzer.analyze(str(self.img_path), self.cat_name, manual_geometry_prior=collinear_prior)
        # It should reject it and fallback to auto-detect
        self.assertNotEqual(result_invalid["surface_quad"], collinear_prior["surface_quad"])
        
    def test_t1_endpoint_db_saving(self):
        from SABLON_V2_MIMARI.core.template_intelligence import save_template_profile
        
        profile_data = {
            "template_uid": "test_uid_123",
            "category": self.cat_name,
            "source_relative_path": f"{self.cat_name}/{self.tmpl_name}",
            "source_asset_sha256": "fake_sha",
            "profile_version": "v1.0",
            "analyzer_version": "v1.0",
            "product_class": "Cam Tablo Dikey",
            "orientation": "V",
            "geometry_type": "QUAD",
            "print_policy": "full_bleed",
            "surface_quad": [[10,10], [90,10], [90,90], [10,90]],
            "confidence_total": 0.95,
            "review_status": "APPROVED",
            "manually_verified": True
        }
        
        save_template_profile(str(self.db_path), profile_data)
        
        # Verify
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM template_profiles WHERE template_uid = 'test_uid_123'").fetchone()
        conn.close()
        
        self.assertIsNotNone(row)
        self.assertEqual(row["review_status"], "APPROVED")
        self.assertEqual(row["orientation"], "V")
        
        quad = json.loads(row["surface_quad"])
        self.assertEqual(len(quad), 4)

if __name__ == "__main__":
    unittest.main()
