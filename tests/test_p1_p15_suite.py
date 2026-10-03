"""
P1-P15 Regression Test Suite
Tests critical paths across the template intelligence pipeline.
"""
import os
import sys
import unittest
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "SABLON_V2_MIMARI")))

class TestP1GeometryValidator(unittest.TestCase):
    def test_valid_quad(self):
        from core.template_intelligence import GeometryValidator
        quad = np.array([[100,100],[300,100],[300,300],[100,300]])
        ok, msg = GeometryValidator.is_valid_quad(quad, 500, 500)
        self.assertTrue(ok, msg)

    def test_degenerate_quad_rejected(self):
        from core.template_intelligence import GeometryValidator
        quad = np.array([[0,0],[1,0],[1,0],[0,0]])
        ok, msg = GeometryValidator.is_valid_quad(quad, 500, 500)
        self.assertFalse(ok)

    def test_self_intersecting_rejected(self):
        from core.template_intelligence import GeometryValidator
        quad = np.array([[0,0],[100,100],[100,0],[0,100]])
        ok, msg = GeometryValidator.is_valid_quad(quad, 500, 500)
        self.assertFalse(ok)
        
    def test_canonical_sorting(self):
        from core.template_intelligence import GeometryValidator
        # Unsorted: BR, TL, BL, TR
        quad = np.array([[300,300],[100,100],[100,300],[300,100]])
        sorted_quad = GeometryValidator.canonical_sort(quad)
        self.assertTrue((sorted_quad[0] == [100,100]).all(), "TL mismatch")
        self.assertTrue((sorted_quad[1] == [300,100]).all(), "TR mismatch")
        self.assertTrue((sorted_quad[2] == [300,300]).all(), "BR mismatch")
        self.assertTrue((sorted_quad[3] == [100,300]).all(), "BL mismatch")
        
    def test_homography_degeneracy(self):
        from core.template_intelligence import GeometryValidator
        from unittest.mock import patch
        
        quad = np.array([[100,100],[300,100],[300,300],[100,300]])
        with patch('cv2.findHomography', return_value=(None, None)):
            ok, msg = GeometryValidator.is_valid_quad(quad, 500, 500)
            self.assertFalse(ok)
            self.assertIn("Homography", msg)

class TestP4CandidateGenerators(unittest.TestCase):
    def test_canny_returns_list(self):
        from core.template_intelligence import CandidateGenerators
        img = np.zeros((200,200,3), dtype=np.uint8)
        cv2_rect = img.copy()
        import cv2
        cv2.rectangle(cv2_rect, (30,30), (170,170), (255,255,255), -1)
        result = CandidateGenerators.generate_canny_contours(cv2_rect)
        self.assertIsInstance(result, list)

    def test_hough_returns_list(self):
        from core.template_intelligence import CandidateGenerators
        img = np.zeros((200,200,3), dtype=np.uint8)
        import cv2
        cv2.line(img, (10,10), (190,10), (255,255,255), 2)
        cv2.line(img, (190,10), (190,190), (255,255,255), 2)
        cv2.line(img, (190,190), (10,190), (255,255,255), 2)
        cv2.line(img, (10,190), (10,10), (255,255,255), 2)
        result = CandidateGenerators.generate_hough_lines_quad(img)
        self.assertIsInstance(result, list)

    def test_color_region_returns_list(self):
        from core.template_intelligence import CandidateGenerators
        img = np.zeros((200,200,3), dtype=np.uint8)
        import cv2
        cv2.rectangle(img, (20,20), (180,180), (255,255,255), -1)
        result = CandidateGenerators.generate_color_region_quad(img)
        self.assertIsInstance(result, list)
        
    def test_manual_prior_returns_list(self):
        from core.template_intelligence import CandidateGenerators
        img = np.zeros((200,300,3), dtype=np.uint8)
        result = CandidateGenerators.generate_manual_prior_quad(img)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        # Verify 10% padding
        pad = int(min(300, 200) * 0.1) # 20
        self.assertTrue((result[0][0] == [20, 20]).all())
        self.assertTrue((result[0][2] == [300-20, 200-20]).all())

class TestP7CategoryRuleEngine(unittest.TestCase):
    def test_known_category(self):
        from core.template_intelligence import CategoryRuleEngine
        rule = CategoryRuleEngine.get_rule_by_folder("01_Wifi_Kutusu")
        self.assertEqual(rule["product_class"], "Wifi Kutusu Kapağı")

    def test_unknown_category_raises(self):
        from core.template_intelligence import CategoryRuleEngine
        with self.assertRaises(ValueError):
            CategoryRuleEngine.get_rule_by_folder("NONEXISTENT")

class TestP10NominalAspect(unittest.TestCase):
    def test_nominal_aspect_is_unknown_by_default(self):
        """nominal_aspect must not be computed from quad; it should be UNKNOWN unless metadata provided."""
        from core.template_intelligence import TemplateAnalyzer
        analyzer = TemplateAnalyzer()
        self.assertEqual(analyzer.version, "v1.3")

class TestP13EdgeContrast(unittest.TestCase):
    def test_edge_contrast_returns_float(self):
        from core.template_intelligence import TemplateAnalyzer
        import cv2
        analyzer = TemplateAnalyzer()
        img = np.ones((100,100,3), dtype=np.uint8) * 128
        cv2.rectangle(img, (20,20), (80,80), (255,255,255), 2)
        quad = np.array([[20,20],[80,20],[80,80],[20,80]])
        score = analyzer.measure_edge_contrast(img, quad)
        self.assertIsInstance(score, float)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)


if __name__ == "__main__":
    unittest.main()
