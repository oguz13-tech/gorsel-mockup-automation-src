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
        conn.execute('''
            CREATE TABLE templates (
                category_id TEXT,
                filename TEXT,
                data TEXT
            )
        ''')
        conn.commit()
        conn.close()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_path_within_root_rejects_prefix_collision(self):
        import app

        root = os.path.join(self.temp_dir, "safe")
        inside = os.path.join(root, "cat", "image.png")
        prefix_collision = os.path.join(self.temp_dir, "safe_evil", "image.png")

        self.assertTrue(app._path_within_root(root, inside))
        self.assertFalse(app._path_within_root(root, prefix_collision))
        self.assertFalse(app._path_within_root(root, os.path.join(root, "..", "escape.png")))

    def test_catch_all_route_does_not_serve_config_or_source_files(self):
        import app

        secret_path = os.path.join(self.temp_dir, "ayarlar.json")
        image_path = os.path.join(self.temp_dir, "preview.png")
        with open(secret_path, "w", encoding="utf-8") as handle:
            handle.write('{"secret": "do-not-serve"}')
        cv2.imwrite(image_path, np.zeros((8, 8, 3), dtype=np.uint8))

        app.app.config["TESTING"] = True
        client = app.app.test_client()
        with patch("app.BASE_DIR", self.temp_dir):
            blocked = client.get("/ayarlar.json")
            allowed = client.get("/preview.png")

        self.assertEqual(blocked.status_code, 403)
        self.assertEqual(allowed.status_code, 200)

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

    def test_p8_manual_geometry_distinct_surface_and_outer(self):
        from core.template_intelligence import TemplateAnalyzer
        img_path = os.path.join(self.temp_dir, "wood_manual.png")
        img = np.zeros((200, 200, 3), dtype=np.uint8)
        cv2.rectangle(img, (50, 50), (150, 150), (255, 255, 255), -1)
        cv2.imwrite(img_path, img)

        manual_prior = {
            "surface_quad": [[60, 60], [140, 60], [140, 140], [60, 140]],
            "outer_quad": [[40, 40], [160, 40], [160, 160], [40, 160]],
        }
        analyzer = TemplateAnalyzer()
        res = analyzer.analyze(
            img_path,
            "03_Ahsap_Tablo",
            manual_geometry_prior=manual_prior,
        )

        self.assertEqual(res["provenance"], "MANUAL_PRIOR")
        self.assertEqual(res["surface_quad"], manual_prior["surface_quad"])
        self.assertEqual(res["outer_quad"], manual_prior["outer_quad"])
        self.assertNotEqual(res["surface_quad"], res["outer_quad"])

    def test_p8b_invalid_manual_prior_falls_back_to_auto_candidates(self):
        from core.template_intelligence import CandidateGenerators, TemplateAnalyzer

        img_path = os.path.join(self.temp_dir, "invalid_prior_fallback.png")
        img = np.zeros((200, 200, 3), dtype=np.uint8)
        cv2.imwrite(img_path, img)

        auto_quad = np.array(
            [[40, 40], [160, 40], [160, 160], [40, 160]],
            dtype=np.float32,
        )
        invalid_prior = {
            "surface_quad": [[10, 10], [10, 10], [20, 20], [30, 30]],
            "outer_quad": [[20, 20], [180, 20], [180, 180], [20, 180]],
        }

        with patch.object(
            CandidateGenerators,
            "generate_canny_contours",
            return_value=[auto_quad],
        ), patch.object(
            CandidateGenerators,
            "generate_hough_lines_quad",
            return_value=[],
        ), patch.object(
            CandidateGenerators,
            "generate_color_region_quad",
            return_value=[],
        ):
            res = TemplateAnalyzer().analyze(
                img_path,
                "02_Cam_Tablo_Dikey",
                manual_geometry_prior=invalid_prior,
            )

        self.assertEqual(res["provenance"], "AUTO")
        self.assertEqual(res["review_status"], "REVIEW_REQUIRED")
        self.assertIsNotNone(res["surface_quad"])
        self.assertNotIn("outer_quad", res)
        self.assertEqual(
            np.asarray(res["surface_quad"], dtype=np.float32).tolist(),
            auto_quad.tolist(),
        )

    def test_p8c_fixed_category_uses_physical_orientation_not_projected_quad(self):
        from core.template_intelligence import TemplateAnalyzer

        img_path = os.path.join(self.temp_dir, "fixed_orientation.png")
        cv2.imwrite(img_path, np.zeros((220, 320, 3), dtype=np.uint8))

        # Deliberately wide projected quad for a physically vertical product.
        prior = {
            "surface_quad": [[20, 80], [300, 80], [280, 160], [40, 160]]
        }
        res = TemplateAnalyzer().analyze(
            img_path,
            "02_Cam_Tablo_Dikey",
            manual_geometry_prior=prior,
        )

        self.assertEqual(res["orientation"], "V")
        self.assertEqual(res["projected_orientation"], "H")
        self.assertAlmostEqual(float(res["nominal_aspect"]), 5.0 / 7.0, places=6)

    def test_p8d_mixed_category_does_not_infer_physical_orientation_from_quad(self):
        from core.template_intelligence import TemplateAnalyzer

        img_path = os.path.join(self.temp_dir, "mixed_orientation.png")
        cv2.imwrite(img_path, np.zeros((220, 320, 3), dtype=np.uint8))
        surface = [[20, 80], [300, 80], [280, 160], [40, 160]]

        without_physical = TemplateAnalyzer().analyze(
            img_path,
            "04_Cam_Dograma",
            manual_geometry_prior={"surface_quad": surface},
        )
        self.assertEqual(without_physical["orientation"], "UNKNOWN")
        self.assertEqual(without_physical["projected_orientation"], "H")
        self.assertEqual(without_physical["nominal_aspect"], "UNKNOWN")

        with_physical = TemplateAnalyzer().analyze(
            img_path,
            "04_Cam_Dograma",
            manual_geometry_prior={
                "surface_quad": surface,
                "physical_orientation": "V",
            },
        )
        self.assertEqual(with_physical["orientation"], "V")
        self.assertEqual(with_physical["projected_orientation"], "H")
        self.assertAlmostEqual(
            float(with_physical["nominal_aspect"]),
            3.0 / 4.0,
            places=6,
        )

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
        from app import app
        
        # Setup dummy template
        cat = "02_Cam_Tablo_Dikey"
        tmpl = "test_tmpl.png"
        img_dir = os.path.join(self.temp_dir, "2_SABLON_HAVUZU", cat)
        os.makedirs(img_dir, exist_ok=True)
        img_path = os.path.join(img_dir, tmpl)
        cv2.imwrite(img_path, np.zeros((100, 100, 3), dtype=np.uint8))
        
        # Dummy ayarlar
        ayarlar_data = {"kategoriler": {cat: {"sablonlar": {tmpl: {}}}}}
        
        app.testing = True
        client = app.test_client()
        with patch('app.BASE_DIR', self.temp_dir), \
             patch('app.get_all_ayarlar', return_value=ayarlar_data):
            os.makedirs(os.path.join(self.temp_dir, "SABLON_V2_MIMARI"), exist_ok=True)
            shutil.copy2(self.db_path, os.path.join(self.temp_dir, "SABLON_V2_MIMARI", "ayarlar.db"))
            
            resp = client.post('/api/templates/batch_analyze', json={"category": cat})
            self.assertEqual(resp.status_code, 200)
            
            # Check db
            conn = sqlite3.connect(os.path.join(self.temp_dir, "SABLON_V2_MIMARI", "ayarlar.db"))
            row = conn.execute("SELECT review_status FROM template_profiles WHERE template_uid=? AND is_active=1", (f"{cat}_{tmpl}",)).fetchone()
            self.assertIsNotNone(row)
            self.assertNotEqual(row[0], "APPROVED")

    def test_p12_explicit_approve_endpoint_persists(self):
        import hashlib
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "SABLON_V2_MIMARI"))
        from app import app
        from core.template_intelligence import save_template_profile

        category = "02_Cam_Tablo_Dikey"
        filename = "tmpl2.png"
        uid = f"{category}_{filename}"

        # Approval is source-hash-bound and requires real, valid geometry.
        img_dir = os.path.join(self.temp_dir, "2_SABLON_HAVUZU", category)
        os.makedirs(img_dir, exist_ok=True)
        img_path = os.path.join(img_dir, filename)
        cv2.imwrite(img_path, np.zeros((120, 100, 3), dtype=np.uint8))
        with open(img_path, "rb") as handle:
            source_hash = hashlib.sha256(handle.read()).hexdigest()

        profile_data = {
            "template_uid": uid,
            "category": category,
            "source_relative_path": f"{category}/{filename}",
            "source_asset_sha256": source_hash,
            "analyzer_version": "v2.3",
            "orientation": "V",
            "nominal_aspect": "0.71428571",
            "surface_quad": [[10, 10], [90, 10], [90, 110], [10, 110]],
            "review_status": "REVIEW_REQUIRED",
        }
        save_template_profile(self.db_path, profile_data)

        app.testing = True
        client = app.test_client()
        # Mock BASE_DIR inside app so approval resolves the exact test source.
        with patch('app.BASE_DIR', self.temp_dir):
            os.makedirs(os.path.join(self.temp_dir, "SABLON_V2_MIMARI"), exist_ok=True)
            shutil.copy2(
                self.db_path,
                os.path.join(self.temp_dir, "SABLON_V2_MIMARI", "ayarlar.db"),
            )
            resp = client.post('/api/templates/approve', json={"template_uid": uid})
            self.assertEqual(resp.status_code, 200)

            # Check db
            conn = sqlite3.connect(os.path.join(self.temp_dir, "SABLON_V2_MIMARI", "ayarlar.db"))
            row = conn.execute(
                "SELECT review_status, manually_verified, orientation "
                "FROM template_profiles WHERE template_uid=? AND is_active=1",
                (uid,),
            ).fetchone()
            self.assertEqual(row[0], "APPROVED")
            self.assertEqual(row[1], 1)
            self.assertEqual(row[2], "V")

    def test_p13_review_overlay_does_not_modify_source(self):
        from app import app
        import hashlib

        cat = "02_Cam_Tablo_Dikey"
        tmpl = "tmpl3.png"
        uid = f"{cat}_{tmpl}"
        img_dir = os.path.join(self.temp_dir, "2_SABLON_HAVUZU", cat)
        os.makedirs(img_dir, exist_ok=True)
        img_path = os.path.join(img_dir, tmpl)
        cv2.imwrite(img_path, np.zeros((100, 100, 3), dtype=np.uint8))
        with open(img_path, "rb") as f:
            orig = f.read()
        orig_hash = hashlib.sha256(orig).hexdigest()

        # Insert a realistic source-hash-bound active proposal.
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """INSERT INTO template_profiles (
                   template_uid, category, source_relative_path,
                   source_asset_sha256, orientation, nominal_aspect,
                   is_active, review_status
               ) VALUES (?, ?, ?, ?, ?, ?, 1, 'REVIEW_REQUIRED')""",
            (
                uid,
                cat,
                f"{cat}/{tmpl}",
                orig_hash,
                "V",
                str(5.0 / 7.0),
            ),
        )
        conn.execute(
            "INSERT INTO templates (category_id, filename, data) VALUES (?, ?, ?)",
            (cat, tmpl, json.dumps({"tip": "perspektif"})),
        )
        conn.commit()
        conn.close()

        app.testing = True
        client = app.test_client()
        with patch('app.BASE_DIR', self.temp_dir):
            os.makedirs(os.path.join(self.temp_dir, "SABLON_V2_MIMARI"), exist_ok=True)
            shutil.copy2(
                self.db_path,
                os.path.join(self.temp_dir, "SABLON_V2_MIMARI", "ayarlar.db"),
            )

            resp = client.post(
                '/api/templates/update_corners',
                json={
                    "template_uid": uid,
                    "corners": [[10,10],[90,10],[90,90],[10,90]],
                },
            )
            self.assertEqual(resp.status_code, 200)
        
        with open(img_path, "rb") as f:
            new_hash = hashlib.sha256(f.read()).hexdigest()
        self.assertEqual(orig_hash, new_hash, "Calibration/Update endpoint must not modify source file")

    def test_p13a_manual_corner_approval_preserves_known_occlusion(self):
        from app import app
        import hashlib

        cat = "02_Cam_Tablo_Dikey"
        tmpl = "occluded.png"
        uid = f"{cat}_{tmpl}"
        img_dir = os.path.join(self.temp_dir, "2_SABLON_HAVUZU", cat)
        os.makedirs(img_dir, exist_ok=True)
        img_path = os.path.join(img_dir, tmpl)
        cv2.imwrite(img_path, np.zeros((120, 100, 3), dtype=np.uint8))
        with open(img_path, "rb") as handle:
            source_hash = hashlib.sha256(handle.read()).hexdigest()

        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """INSERT INTO template_profiles (
                   template_uid, category, source_relative_path,
                   source_asset_sha256, is_active, review_status,
                   has_occlusion
               ) VALUES (?, ?, ?, ?, 1, 'REVIEW_REQUIRED', 1)""",
            (uid, cat, f"{cat}/{tmpl}", source_hash),
        )
        conn.execute(
            "INSERT INTO templates (category_id, filename, data) VALUES (?, ?, ?)",
            (cat, tmpl, json.dumps({"tip": "perspektif"})),
        )
        conn.commit()
        conn.close()

        target_db_dir = os.path.join(self.temp_dir, "SABLON_V2_MIMARI")
        os.makedirs(target_db_dir, exist_ok=True)
        target_db = os.path.join(target_db_dir, "ayarlar.db")
        shutil.copy2(self.db_path, target_db)

        app.testing = True
        client = app.test_client()
        with patch('app.BASE_DIR', self.temp_dir):
            approved = client.post(
                '/api/templates/update_corners',
                json={
                    "template_uid": uid,
                    "corners": [[10, 10], [90, 10], [90, 110], [10, 110]],
                },
            )
            self.assertEqual(approved.status_code, 200)

        conn = sqlite3.connect(target_db)
        try:
            row = conn.execute(
                """SELECT has_occlusion, review_status
                   FROM template_profiles
                   WHERE template_uid=? AND is_active=1""",
                (uid,),
            ).fetchone()
        finally:
            conn.close()

        self.assertEqual(row[0], 1)
        self.assertEqual(row[1], "APPROVED")

    def test_p13b_mixed_category_requires_explicit_physical_orientation(self):
        from app import app
        import hashlib

        cat = "04_Cam_Dograma"
        tmpl = "mixed.png"
        uid = f"{cat}_{tmpl}"
        img_dir = os.path.join(self.temp_dir, "2_SABLON_HAVUZU", cat)
        os.makedirs(img_dir, exist_ok=True)
        img_path = os.path.join(img_dir, tmpl)
        cv2.imwrite(img_path, np.zeros((120, 160, 3), dtype=np.uint8))
        with open(img_path, "rb") as handle:
            source_hash = hashlib.sha256(handle.read()).hexdigest()

        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """INSERT INTO template_profiles (
                   template_uid, category, source_relative_path,
                   source_asset_sha256, is_active, review_status
               ) VALUES (?, ?, ?, ?, 1, 'REVIEW_REQUIRED')""",
            (uid, cat, f"{cat}/{tmpl}", source_hash),
        )
        conn.execute(
            "INSERT INTO templates (category_id, filename, data) VALUES (?, ?, ?)",
            (cat, tmpl, json.dumps({"tip": "perspektif"})),
        )
        conn.commit()
        conn.close()

        target_db_dir = os.path.join(self.temp_dir, "SABLON_V2_MIMARI")
        os.makedirs(target_db_dir, exist_ok=True)
        target_db = os.path.join(target_db_dir, "ayarlar.db")
        shutil.copy2(self.db_path, target_db)

        app.testing = True
        client = app.test_client()
        payload = {
            "template_uid": uid,
            "category": cat,
            "template": tmpl,
            "corners": [[15, 40], [145, 40], [140, 90], [20, 90]],
        }
        with patch('app.BASE_DIR', self.temp_dir):
            missing = client.post('/api/templates/update_corners', json=payload)
            self.assertEqual(missing.status_code, 422)
            self.assertEqual(
                missing.get_json().get("code"),
                "PHYSICAL_ORIENTATION_REQUIRED",
            )

            payload["physical_orientation"] = "V"
            approved = client.post('/api/templates/update_corners', json=payload)
            self.assertEqual(approved.status_code, 200)
            body = approved.get_json()
            self.assertEqual(body["orientation"], "V")
            self.assertEqual(body["projected_orientation"], "H")

        conn = sqlite3.connect(target_db)
        row = conn.execute(
            """SELECT orientation, nominal_aspect, review_status,
                      manually_verified, component_confidences
               FROM template_profiles
               WHERE template_uid=? AND is_active=1""",
            (uid,),
        ).fetchone()
        conn.close()
        self.assertEqual(row[0], "V")
        self.assertAlmostEqual(float(row[1]), 3.0 / 4.0, places=6)
        self.assertEqual(row[2], "APPROVED")
        self.assertEqual(row[3], 1)
        evidence = json.loads(row[4])
        self.assertEqual(evidence["physical_orientation_verified"], 1.0)
        self.assertEqual(evidence["physical_orientation_source"], "human_review")

    def test_p14_selector_selects_approved_compatible(self):
        from core.template_intelligence import TemplateSelector
        conn = sqlite3.connect(self.db_path)
        conn.execute("INSERT INTO template_profiles (category, orientation, review_status, is_active, confidence_total) VALUES ('02_Cam_Tablo_Dikey', 'V', 'APPROVED', 1, 0.95)")
        conn.commit()
        conn.close()
        
        selector = TemplateSelector(db_path=self.db_path)
        res = selector.select_template('V', '02_Cam_Tablo_Dikey')
        self.assertEqual(res['status'], 'SELECTED')
        
    def test_p14b_strict_category_rejects_unknown_template_orientation(self):
        from core.template_intelligence import TemplateSelector
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """INSERT INTO template_profiles (
                   category, orientation, review_status, is_active,
                   confidence_total
               ) VALUES (
                   '02_Cam_Tablo_Dikey', 'UNKNOWN', 'APPROVED', 1, 0.99
               )"""
        )
        conn.commit()
        conn.close()

        selector = TemplateSelector(db_path=self.db_path)
        res = selector.select_template('V', '02_Cam_Tablo_Dikey')
        self.assertEqual(res['status'], 'SKIPPED_ORIENTATION_MISMATCH')

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

    def test_p16_regression_manual_geometry_preserved(self):
        from core.template_intelligence import save_template_profile
        
        profile_data = {
            "template_uid": "test_uid_p16", "category": "cat1", "source_relative_path": "cat1/tmpl1.png",
            "source_asset_sha256": "same_hash", "analyzer_version": "v1.3", "orientation": "V",
            "review_status": "APPROVED", "manually_verified": True,
            "surface_quad": [[1,1], [9,1], [9,9], [1,9]]
        }
        save_template_profile(self.db_path, profile_data)
        
        # New analysis with same hash, different quad
        new_data = {
            "template_uid": "test_uid_p16", "category": "cat1", "source_relative_path": "cat1/tmpl1.png",
            "source_asset_sha256": "same_hash", "analyzer_version": "v1.3", "orientation": "H",
            "review_status": "REVIEW_REQUIRED", "manually_verified": False,
            "surface_quad": [[0,0], [10,0], [10,10], [0,10]]
        }
        save_template_profile(self.db_path, new_data)
        
        conn = sqlite3.connect(self.db_path)
        row = conn.execute("SELECT review_status, surface_quad, manually_verified FROM template_profiles WHERE template_uid='test_uid_p16' AND is_active=1").fetchone()
        conn.close()
        
        self.assertEqual(row[0], "APPROVED")
        self.assertEqual(row[2], 1)
        import json
        saved_quad = json.loads(row[1])
        self.assertEqual(saved_quad, [[1,1], [9,1], [9,9], [1,9]])

    def test_p16b_duplicate_active_profiles_are_normalized_safely(self):
        from core.template_intelligence import save_template_profile

        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """INSERT INTO template_profiles (
                   template_uid, category, source_relative_path,
                   source_asset_sha256, analyzer_version, orientation,
                   review_status, manually_verified, is_active,
                   confidence_total, updated_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, CURRENT_TIMESTAMP)""",
            (
                "dup_uid",
                "cat1",
                "cat1/tmpl.png",
                "same_hash",
                "manual-v1",
                "V",
                "APPROVED",
                1,
                1.0,
            ),
        )
        conn.execute(
            """INSERT INTO template_profiles (
                   template_uid, category, source_relative_path,
                   source_asset_sha256, analyzer_version, orientation,
                   review_status, manually_verified, is_active,
                   confidence_total, updated_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, CURRENT_TIMESTAMP)""",
            (
                "dup_uid",
                "cat1",
                "cat1/tmpl.png",
                "old_hash",
                "v1.3",
                "H",
                "REVIEW_REQUIRED",
                0,
                0.5,
            ),
        )
        conn.commit()
        conn.close()

        save_template_profile(
            self.db_path,
            {
                "template_uid": "dup_uid",
                "category": "cat1",
                "source_relative_path": "cat1/tmpl.png",
                "source_asset_sha256": "same_hash",
                "analyzer_version": "v1.3",
                "orientation": "V",
                "review_status": "REVIEW_REQUIRED",
                "manually_verified": False,
                "surface_quad": [[1, 1], [9, 1], [9, 9], [1, 9]],
            },
        )

        conn = sqlite3.connect(self.db_path)
        rows = conn.execute(
            """SELECT source_asset_sha256, review_status,
                      manually_verified, is_active
               FROM template_profiles
               WHERE template_uid=?
               ORDER BY id""",
            ("dup_uid",),
        ).fetchall()
        conn.close()

        active = [row for row in rows if row[3] == 1]
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0][0], "same_hash")
        self.assertEqual(active[0][1], "APPROVED")
        self.assertEqual(active[0][2], 1)

    def test_p17_endpoint_uses_matching_persisted_manual_prior_without_overwrite(self):
        from app import app
        from core.template_intelligence import save_template_profile
        import hashlib

        cat = "03_Ahsap_Tablo"
        tmpl = "p17.png"
        uid = f"{cat}_{tmpl}"
        img_dir = os.path.join(self.temp_dir, "2_SABLON_HAVUZU", cat)
        os.makedirs(img_dir, exist_ok=True)
        img_path = os.path.join(img_dir, tmpl)
        cv2.imwrite(img_path, np.zeros((120, 120, 3), dtype=np.uint8))
        with open(img_path, "rb") as handle:
            source_hash = hashlib.sha256(handle.read()).hexdigest()

        manual_surface = [[10, 10], [110, 10], [110, 110], [10, 110]]
        manual_outer = [[5, 5], [115, 5], [115, 115], [5, 115]]
        save_template_profile(
            self.db_path,
            {
                "template_uid": uid,
                "category": cat,
                "source_relative_path": f"{cat}/{tmpl}",
                "source_asset_sha256": source_hash,
                "analyzer_version": "v1.3",
                "orientation": "SQUARE",
                "review_status": "APPROVED",
                "manually_verified": True,
                "surface_quad": manual_surface,
                "outer_quad": manual_outer,
            },
        )

        target_db_dir = os.path.join(self.temp_dir, "SABLON_V2_MIMARI")
        os.makedirs(target_db_dir, exist_ok=True)
        target_db = os.path.join(target_db_dir, "ayarlar.db")
        shutil.copy2(self.db_path, target_db)

        app.testing = True
        client = app.test_client()
        with patch("app.BASE_DIR", self.temp_dir):
            response = client.post(
                "/api/templates/analyze",
                headers={
                    "X-Active-Category": cat,
                    "X-Active-Template": tmpl,
                },
                json={},
            )

        self.assertEqual(response.status_code, 200)
        analysis = response.get_json()["analysis"]
        self.assertEqual(analysis["provenance"], "MANUAL_PRIOR")
        self.assertEqual(analysis["surface_quad"], manual_surface)
        self.assertEqual(analysis["outer_quad"], manual_outer)
        self.assertNotEqual(analysis["review_status"], "APPROVED")

        conn = sqlite3.connect(target_db)
        row = conn.execute(
            """SELECT review_status, manually_verified, surface_quad, outer_quad
               FROM template_profiles
               WHERE template_uid=? AND is_active=1""",
            (uid,),
        ).fetchone()
        conn.close()
        self.assertEqual(row[0], "APPROVED")
        self.assertEqual(row[1], 1)
        self.assertEqual(json.loads(row[2]), manual_surface)
        self.assertEqual(json.loads(row[3]), manual_outer)

    def test_p18_endpoint_does_not_reuse_manual_prior_after_source_hash_change(self):
        from app import app
        from core.template_intelligence import save_template_profile
        import hashlib

        cat = "03_Ahsap_Tablo"
        tmpl = "p18.png"
        uid = f"{cat}_{tmpl}"
        img_dir = os.path.join(self.temp_dir, "2_SABLON_HAVUZU", cat)
        os.makedirs(img_dir, exist_ok=True)
        img_path = os.path.join(img_dir, tmpl)

        old_img = np.zeros((120, 120, 3), dtype=np.uint8)
        cv2.imwrite(img_path, old_img)
        with open(img_path, "rb") as handle:
            old_hash = hashlib.sha256(handle.read()).hexdigest()

        save_template_profile(
            self.db_path,
            {
                "template_uid": uid,
                "category": cat,
                "source_relative_path": f"{cat}/{tmpl}",
                "source_asset_sha256": old_hash,
                "analyzer_version": "v1.3",
                "orientation": "SQUARE",
                "review_status": "APPROVED",
                "manually_verified": True,
                "surface_quad": [[10, 10], [110, 10], [110, 110], [10, 110]],
            },
        )

        changed_img = np.full((120, 120, 3), 255, dtype=np.uint8)
        cv2.rectangle(changed_img, (20, 20), (100, 100), (0, 0, 0), 3)
        cv2.imwrite(img_path, changed_img)
        with open(img_path, "rb") as handle:
            new_hash = hashlib.sha256(handle.read()).hexdigest()
        self.assertNotEqual(old_hash, new_hash)

        target_db_dir = os.path.join(self.temp_dir, "SABLON_V2_MIMARI")
        os.makedirs(target_db_dir, exist_ok=True)
        target_db = os.path.join(target_db_dir, "ayarlar.db")
        shutil.copy2(self.db_path, target_db)

        app.testing = True
        client = app.test_client()
        with patch("app.BASE_DIR", self.temp_dir):
            response = client.post(
                "/api/templates/analyze",
                headers={
                    "X-Active-Category": cat,
                    "X-Active-Template": tmpl,
                },
                json={},
            )

        self.assertEqual(response.status_code, 200)
        analysis = response.get_json()["analysis"]
        self.assertNotEqual(analysis["provenance"], "MANUAL_PRIOR")
        self.assertEqual(analysis["source_asset_sha256"], new_hash)

        conn = sqlite3.connect(target_db)
        rows = conn.execute(
            """SELECT source_asset_sha256, is_active, review_status, manually_verified
               FROM template_profiles
               WHERE template_uid=?
               ORDER BY id""",
            (uid,),
        ).fetchall()
        conn.close()

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0][0], old_hash)
        self.assertEqual(rows[0][1], 0)
        self.assertEqual(rows[0][2], "STALE_SOURCE_CHANGED")
        self.assertEqual(rows[1][0], new_hash)
        self.assertEqual(rows[1][1], 1)
        self.assertEqual(rows[1][3], 0)
        self.assertNotEqual(rows[1][2], "APPROVED")


    def test_legacy_profile_schema_without_id_supports_approval_flow(self):
        import hashlib
        from app import app
        from core.template_intelligence import save_template_profile

        runtime_root = os.path.join(self.temp_dir, 'legacy_runtime_no_id')
        db_dir = os.path.join(runtime_root, 'SABLON_V2_MIMARI')
        category = '02_Cam_Tablo_Dikey'
        filename = 'legacy_profile.png'
        uid = category + '_' + filename
        img_dir = os.path.join(runtime_root, '2_SABLON_HAVUZU', category)
        os.makedirs(db_dir, exist_ok=True)
        os.makedirs(img_dir, exist_ok=True)
        img_path = os.path.join(img_dir, filename)
        cv2.imwrite(img_path, np.zeros((120, 100, 3), dtype=np.uint8))
        with open(img_path, 'rb') as handle:
            source_hash = hashlib.sha256(handle.read()).hexdigest()

        legacy_db = os.path.join(db_dir, 'ayarlar.db')
        conn = sqlite3.connect(legacy_db)
        conn.execute('''CREATE TABLE templates (
            category_id TEXT, filename TEXT, data TEXT,
            PRIMARY KEY (category_id, filename)
        )''')
        conn.execute('''CREATE TABLE template_profiles (
            template_uid TEXT, category TEXT, source_relative_path TEXT,
            source_asset_sha256 TEXT, profile_version TEXT, analyzer_version TEXT,
            product_class TEXT, orientation TEXT, geometry_type TEXT,
            print_policy TEXT, surface_quad TEXT, outer_quad TEXT,
            surface_mask_path TEXT, material TEXT, has_frame INTEGER,
            has_mat INTEGER, has_reflection INTEGER, has_occlusion INTEGER,
            confidence_total REAL, component_confidences TEXT, review_status TEXT,
            manually_verified INTEGER, updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            nominal_aspect TEXT, is_active INTEGER DEFAULT 1
        )''')
        conn.execute(
            'INSERT INTO templates (category_id, filename, data) VALUES (?, ?, ?)',
            (category, filename, json.dumps({
                'tip': 'perspektif',
                'koseler': [[10, 10], [90, 10], [90, 110], [10, 110]],
            })),
        )
        conn.commit()
        columns = [row[1] for row in conn.execute(
            'PRAGMA table_info(template_profiles)'
        ).fetchall()]
        conn.close()
        self.assertNotIn('id', columns)

        app.testing = True
        client = app.test_client()
        payload = {
            'template_uid': uid,
            'category': category,
            'template': filename,
            'corners': [[10, 10], [90, 10], [90, 110], [10, 110]],
            'physical_orientation': '',
            'on_plan': {},
        }
        with patch('app.BASE_DIR', runtime_root):
            approved = client.post('/api/templates/update_corners', json=payload)
            self.assertEqual(approved.status_code, 200, approved.get_json())

            reapproved = client.post(
                '/api/templates/approve',
                json={'template_uid': uid},
            )
            self.assertEqual(reapproved.status_code, 200, reapproved.get_json())

            # Reject is intentionally no longer part of the end-user
            # workflow. Wrong proposals are corrected/re-detected instead.
            rejected = client.post(
                '/api/templates/reject',
                json={'template_uid': uid},
            )
            self.assertEqual(rejected.status_code, 405)

        # Exercise save_template_profile's existing-row path against the
        # same legacy schema: row identity must use SQLite rowid, not id.
        save_template_profile(legacy_db, {
            'template_uid': uid,
            'category': category,
            'source_relative_path': category + '/' + filename,
            'source_asset_sha256': 'new-hash-for-rowid-regression',
            'analyzer_version': 'legacy-rowid-test',
            'orientation': 'V',
            'nominal_aspect': str(5.0 / 7.0),
            'surface_quad': [[10, 10], [90, 10], [90, 110], [10, 110]],
            'review_status': 'REVIEW_REQUIRED',
            'manually_verified': False,
        })

        conn = sqlite3.connect(legacy_db)
        rows = conn.execute('''SELECT source_asset_sha256, review_status, is_active
                               FROM template_profiles
                               WHERE template_uid=?
                               ORDER BY rowid''', (uid,)).fetchall()
        conn.close()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0][1], 'STALE_SOURCE_CHANGED')
        self.assertEqual(rows[0][2], 0)
        self.assertEqual(rows[1][0], 'new-hash-for-rowid-regression')
        self.assertEqual(rows[1][1], 'REVIEW_REQUIRED')
        self.assertEqual(rows[1][2], 1)


class TestOrphanTemplateRetirement(unittest.TestCase):
    def test_missing_working_source_can_be_retired_and_undone_safely(self):
        import app

        with tempfile.TemporaryDirectory() as runtime_root:
            category = "02_Cam_Tablo_Dikey"
            filename = "CamTabloDikey_009.png"
            db_dir = os.path.join(runtime_root, "SABLON_V2_MIMARI")
            backup_dir = os.path.join(
                runtime_root,
                "2_SABLON_HAVUZU_ORIJINAL_YEDEK",
                category,
            )
            os.makedirs(db_dir, exist_ok=True)
            os.makedirs(backup_dir, exist_ok=True)

            backup_path = os.path.join(backup_dir, filename)
            cv2.imwrite(
                backup_path,
                np.full((24, 24, 3), 32, dtype=np.uint8),
            )

            db_path = os.path.join(db_dir, "ayarlar.db")
            conn = sqlite3.connect(db_path)
            conn.execute(
                """CREATE TABLE templates (
                    category_id TEXT,
                    filename TEXT,
                    data TEXT,
                    PRIMARY KEY (category_id, filename)
                )"""
            )
            conn.execute(
                """CREATE TABLE template_profiles (
                    template_uid TEXT,
                    category TEXT,
                    source_relative_path TEXT,
                    source_asset_sha256 TEXT,
                    review_status TEXT,
                    manually_verified INTEGER,
                    is_active INTEGER,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )"""
            )
            conf = {
                "tip": "perspektif",
                "koseler": [[1, 1], [20, 1], [20, 20], [1, 20]],
            }
            conn.execute(
                "INSERT INTO templates (category_id, filename, data) VALUES (?, ?, ?)",
                (category, filename, json.dumps(conf)),
            )
            conn.execute(
                """INSERT INTO template_profiles (
                    template_uid, category, source_relative_path,
                    source_asset_sha256, review_status,
                    manually_verified, is_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    category + "_" + filename,
                    category,
                    category + "/" + filename,
                    "missing-active-source-hash",
                    "REVIEW_REQUIRED",
                    0,
                    1,
                ),
            )
            conn.commit()
            conn.close()

            fake_settings = {
                "kategoriler": {
                    category: {
                        "sablonlar": {
                            filename: conf,
                        }
                    }
                }
            }

            with (
                patch("app.BASE_DIR", runtime_root),
                patch("app.get_all_ayarlar", return_value=fake_settings),
                patch("app.reserve_number"),
            ):
                retired = app._retire_template_safely(
                    category,
                    filename,
                )

                self.assertTrue(retired["source_was_missing"])
                self.assertTrue(retired["orphan_retired"])
                self.assertTrue(retired["backup_archived"])
                self.assertFalse(os.path.exists(backup_path))

                trash_dir = os.path.join(
                    runtime_root,
                    "SILINEN_SABLONLAR_COP_KUTUSU",
                )
                meta_files = [
                    name
                    for name in os.listdir(trash_dir)
                    if name.endswith("_meta.json")
                ]
                self.assertEqual(len(meta_files), 1)

                with open(
                    os.path.join(trash_dir, meta_files[0]),
                    "r",
                    encoding="utf-8",
                ) as handle:
                    meta = json.load(handle)
                self.assertTrue(meta["source_was_missing"])
                self.assertIsNone(meta["trash_image_name"])
                self.assertTrue(meta["backup_trash_name"])

                conn = sqlite3.connect(db_path)
                template_count = conn.execute(
                    "SELECT COUNT(*) FROM templates WHERE category_id=? AND filename=?",
                    (category, filename),
                ).fetchone()[0]
                active_profile_count = conn.execute(
                    "SELECT COUNT(*) FROM template_profiles WHERE category=? AND is_active=1",
                    (category,),
                ).fetchone()[0]
                conn.close()
                self.assertEqual(template_count, 0)
                self.assertEqual(active_profile_count, 0)

                app.app.config["TESTING"] = True
                client = app.app.test_client()
                undone = client.post("/api/sablon_sil_geri_al")
                self.assertEqual(
                    undone.status_code,
                    200,
                    undone.get_json(),
                )
                payload = undone.get_json()
                self.assertTrue(payload["restored_as_orphan"])
                self.assertFalse(payload["source_restored"])
                self.assertTrue(payload["backup_restored"])
                self.assertTrue(os.path.isfile(backup_path))

                working_path = os.path.join(
                    runtime_root,
                    "2_SABLON_HAVUZU",
                    category,
                    filename,
                )
                self.assertFalse(os.path.exists(working_path))

                conn = sqlite3.connect(db_path)
                template_count = conn.execute(
                    "SELECT COUNT(*) FROM templates WHERE category_id=? AND filename=?",
                    (category, filename),
                ).fetchone()[0]
                active_profile_count = conn.execute(
                    "SELECT COUNT(*) FROM template_profiles WHERE category=? AND is_active=1",
                    (category,),
                ).fetchone()[0]
                conn.close()
                self.assertEqual(template_count, 1)
                self.assertEqual(active_profile_count, 0)


if __name__ == "__main__":
    unittest.main()
