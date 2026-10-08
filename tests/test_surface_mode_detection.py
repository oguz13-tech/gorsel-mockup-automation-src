import os
import tempfile
import unittest

import cv2
import numpy as np

from core.template_intelligence import CandidateGenerators, GeometryValidator, TemplateAnalyzer


class SurfaceModeDetectionTests(unittest.TestCase):
    def setUp(self):
        self.h = 240
        self.w = 320
        self.quad = np.array(
            [[60, 45], [260, 45], [260, 195], [60, 195]],
            dtype=np.float32,
        )

    def _base_image(self):
        image = np.full((self.h, self.w, 3), 128, dtype=np.uint8)
        cv2.rectangle(image, (58, 43), (262, 197), (70, 70, 70), 3)
        return image

    def test_quad_outside_source_image_is_rejected(self):
        outside = np.array(
            [[-8, 45], [260, 45], [260, 195], [60, 195]],
            dtype=np.float32,
        )
        valid, reason = GeometryValidator.is_valid_quad(
            outside,
            self.w,
            self.h,
        )
        self.assertFalse(valid)
        self.assertEqual(reason, "Outside source image bounds")

    def test_strong_dark_glass_evidence_precedes_black(self):
        image = np.full(
            (self.h, self.w, 3),
            (30, 30, 30),
            dtype=np.uint8,
        )
        cv2.fillConvexPoly(
            image,
            self.quad.astype(np.int32),
            (28, 28, 28),
        )
        cv2.polylines(
            image,
            [self.quad.astype(np.int32)],
            True,
            (24, 24, 24),
            2,
        )

        mode, confidence, metrics = (
            TemplateAnalyzer.classify_candidate_surface(
                image,
                self.quad,
                category_folder="05_Ocak_Arkasi",
            )
        )

        self.assertEqual(mode, "TRANSPARENT_GLASS")
        self.assertGreaterEqual(confidence, 0.70)
        self.assertGreaterEqual(
            metrics["transparent_optical_score"],
            0.72,
        )

    def test_black_surface_is_classified(self):
        image = self._base_image()
        cv2.fillConvexPoly(
            image,
            self.quad.astype(np.int32),
            (12, 12, 12),
        )
        mode, confidence, _ = TemplateAnalyzer.classify_candidate_surface(
            image,
            self.quad,
            category_folder="02_Cam_Tablo_Dikey",
        )
        self.assertEqual(mode, "BLACK")
        self.assertGreaterEqual(confidence, 0.60)

    def test_white_surface_is_classified(self):
        image = self._base_image()
        cv2.fillConvexPoly(
            image,
            self.quad.astype(np.int32),
            (245, 245, 245),
        )
        mode, confidence, _ = TemplateAnalyzer.classify_candidate_surface(
            image,
            self.quad,
            category_folder="02_Cam_Tablo_Dikey",
        )
        self.assertEqual(mode, "WHITE")
        self.assertGreaterEqual(confidence, 0.60)

    def test_optical_clear_glass_on_light_wall_precedes_white(self):
        image = np.full(
            (self.h, self.w, 3),
            (222, 222, 222),
            dtype=np.uint8,
        )
        # Clear glass keeps the wall visible: interior tone is intentionally
        # close to the immediate outside, with only a subtle glass border.
        cv2.fillConvexPoly(
            image,
            self.quad.astype(np.int32),
            (216, 216, 216),
        )
        cv2.polylines(
            image,
            [self.quad.astype(np.int32)],
            True,
            (192, 192, 192),
            3,
        )

        mode, confidence, metrics = (
            TemplateAnalyzer.classify_candidate_surface(
                image,
                self.quad,
                category_folder="05_Ocak_Arkasi",
            )
        )

        self.assertEqual(mode, "TRANSPARENT_GLASS")
        self.assertGreaterEqual(confidence, 0.60)
        self.assertGreaterEqual(
            metrics["transparent_optical_score"],
            0.52,
        )

    def test_ocak_arkasi_prior_prefers_back_wall_over_lower_cabinet(self):
        glass_quad = np.array(
            [[85, 55], [235, 55], [235, 135], [85, 135]],
            dtype=np.float32,
        )
        cabinet_quad = np.array(
            [[20, 165], [300, 165], [300, 230], [20, 230]],
            dtype=np.float32,
        )

        glass_score = TemplateAnalyzer.score_category_spatial_prior(
            "05_Ocak_Arkasi",
            glass_quad,
            self.w,
            self.h,
        )
        cabinet_score = TemplateAnalyzer.score_category_spatial_prior(
            "05_Ocak_Arkasi",
            cabinet_quad,
            self.w,
            self.h,
        )

        self.assertGreater(glass_score, cabinet_score)
        self.assertGreaterEqual(glass_score - cabinet_score, 0.35)

    def test_true_alpha_surface_is_classified_as_transparent(self):
        image = self._base_image()
        alpha = np.full((self.h, self.w), 255, dtype=np.uint8)
        cv2.fillConvexPoly(
            alpha,
            self.quad.astype(np.int32),
            128,
        )
        mode, confidence, metrics = (
            TemplateAnalyzer.classify_candidate_surface(
                image,
                self.quad,
                alpha_channel=alpha,
                category_folder="02_Cam_Tablo_Dikey",
            )
        )
        self.assertEqual(mode, "TRANSPARENT_GLASS")
        self.assertGreaterEqual(confidence, 0.70)
        self.assertGreater(metrics["alpha_partial_ratio"], 0.50)

    def test_patterned_surface_is_classified_as_designed(self):
        image = self._base_image()
        x1, y1 = 60, 45
        x2, y2 = 260, 195
        tile = 12
        for y in range(y1, y2, tile):
            for x in range(x1, x2, tile):
                value = 35 if ((x // tile) + (y // tile)) % 2 == 0 else 220
                cv2.rectangle(
                    image,
                    (x, y),
                    (min(x + tile - 1, x2), min(y + tile - 1, y2)),
                    (value, 90, 255 - value),
                    -1,
                )

        mode, confidence, _ = TemplateAnalyzer.classify_candidate_surface(
            image,
            self.quad,
            category_folder="03_Ahsap_Tablo",
        )
        self.assertEqual(mode, "DESIGNED_TEXTURED")
        self.assertGreaterEqual(confidence, 0.50)

    def test_ocak_special_selector_prefers_white_panel_over_room_rectangle(self):
        h, w = 600, 480
        image = np.full((h, w, 3), 220, dtype=np.uint8)

        # Quiet wall / room background.
        cv2.rectangle(image, (0, 0), (479, 599), (214, 214, 214), -1)

        # Real white glass panel in the backsplash zone.
        panel = np.array(
            [[150, 180], [390, 180], [390, 330], [150, 330]],
            dtype=np.int32,
        )
        cv2.fillConvexPoly(image, panel, (238, 238, 238))
        cv2.polylines(image, [panel], True, (188, 188, 188), 3)

        # Reflection cues inside the panel.
        cv2.rectangle(image, (170, 195), (195, 310), (226, 226, 226), -1)
        cv2.line(image, (180, 200), (180, 305), (250, 250, 250), 2)

        # Strong upper cabinets / wall rectangle distractor.
        cv2.rectangle(image, (15, 35), (465, 170), (135, 125, 115), 5)
        for x in (100, 220, 340):
            cv2.line(image, (x, 35), (x, 170), (70, 70, 70), 3)

        # Strong lower cabinet distractor.
        cv2.rectangle(image, (20, 390), (460, 585), (110, 85, 65), -1)
        cv2.rectangle(image, (20, 390), (460, 585), (35, 35, 35), 4)
        for x in (130, 260, 370):
            cv2.line(image, (x, 392), (x, 582), (45, 45, 45), 3)

        candidates = CandidateGenerators.generate_low_contrast_glass_quads(
            image,
            "05_Ocak_Arkasi",
        )
        self.assertTrue(candidates)

        analyzer = TemplateAnalyzer()
        chosen = analyzer.select_ocak_arkasi_special_candidate(
            image,
            candidates,
        )
        self.assertIsNotNone(chosen)

        quad = np.asarray(chosen["quad"], dtype=np.float32)
        center = np.mean(quad, axis=0)
        self.assertLess(
            float(np.linalg.norm(center - np.array([270.0, 255.0]))),
            95.0,
        )
        self.assertLess(chosen["area_ratio"], 0.42)
        self.assertGreaterEqual(chosen["surface_score"], 0.42)

    def test_non_ocak_categories_do_not_use_ocak_special_provenance(self):
        h, w = 320, 240
        image = np.full((h, w, 3), 180, dtype=np.uint8)
        cv2.rectangle(image, (45, 55), (195, 270), (12, 12, 12), -1)

        fd, path = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        try:
            self.assertTrue(cv2.imwrite(path, image))
            result = TemplateAnalyzer().analyze(
                path,
                "02_Cam_Tablo_Dikey",
            )
        finally:
            try:
                os.remove(path)
            except OSError:
                pass

        self.assertNotEqual(
            result["provenance"],
            "AUTO_OCAK_ARKASI_SPECIAL",
        )

    def test_ocak_arkasi_rejects_full_scene_and_lower_cabinet_auto_quads(self):
        full_scene = np.array(
            [[10, 20], [310, 20], [310, 220], [10, 220]],
            dtype=np.float32,
        )
        lower_cabinet = np.array(
            [[20, 165], [300, 165], [300, 230], [20, 230]],
            dtype=np.float32,
        )
        real_panel = np.array(
            [[85, 55], [235, 55], [235, 135], [85, 135]],
            dtype=np.float32,
        )

        full_ok, full_reason = (
            TemplateAnalyzer.is_category_auto_candidate_plausible(
                "05_Ocak_Arkasi",
                full_scene,
                self.w,
                self.h,
            )
        )
        cabinet_ok, cabinet_reason = (
            TemplateAnalyzer.is_category_auto_candidate_plausible(
                "05_Ocak_Arkasi",
                lower_cabinet,
                self.w,
                self.h,
            )
        )
        panel_ok, panel_reason = (
            TemplateAnalyzer.is_category_auto_candidate_plausible(
                "05_Ocak_Arkasi",
                real_panel,
                self.w,
                self.h,
            )
        )

        self.assertFalse(full_ok, full_reason)
        self.assertFalse(cabinet_ok, cabinet_reason)
        self.assertTrue(panel_ok, panel_reason)

    def test_low_contrast_glass_beats_strong_lower_cabinet(self):
        h, w = 600, 480
        image = np.full((h, w, 3), 222, dtype=np.uint8)

        # Faint clear glass panel on a similarly bright wall.
        glass = np.array(
            [[128, 180], [360, 180], [360, 338], [128, 338]],
            dtype=np.int32,
        )
        cv2.fillConvexPoly(image, glass, (216, 216, 216))
        cv2.polylines(image, [glass], True, (191, 191, 191), 2)

        # Strong lower cabinet distractor: much stronger edges than the glass.
        cv2.rectangle(image, (28, 402), (452, 548), (112, 92, 72), -1)
        cv2.rectangle(image, (28, 402), (452, 548), (35, 35, 35), 4)
        for x in (110, 210, 320, 410):
            cv2.line(image, (x, 404), (x, 546), (45, 45, 45), 3)
        for y in (445, 492):
            cv2.line(image, (30, y), (450, y), (55, 55, 55), 3)

        glass_candidates = (
            CandidateGenerators.generate_low_contrast_glass_quads(
                image,
                "05_Ocak_Arkasi",
            )
        )
        self.assertTrue(glass_candidates)

        def center_distance(quad):
            center = np.mean(np.asarray(quad, dtype=np.float32), axis=0)
            return float(np.linalg.norm(center - np.array([244.0, 259.0])))

        self.assertLess(
            min(center_distance(quad) for quad in glass_candidates),
            55.0,
        )

        fd, path = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        try:
            self.assertTrue(cv2.imwrite(path, image))
            result = TemplateAnalyzer().analyze(
                path,
                "05_Ocak_Arkasi",
            )
        finally:
            try:
                os.remove(path)
            except OSError:
                pass

        self.assertEqual(
            result["surface_mode"],
            "TRANSPARENT_GLASS",
        )
        selected = np.asarray(result["surface_quad"], dtype=np.float32)
        center = np.mean(selected, axis=0)
        self.assertLess(float(center[1]) / float(h), 0.67)
        self.assertEqual(
            result["component_confidences"].get(
                "glass_priority_selected"
            ),
            1.0,
        )

    def test_specialized_generators_emit_candidates(self):
        black = np.full((self.h, self.w, 3), 170, dtype=np.uint8)
        cv2.fillConvexPoly(
            black,
            self.quad.astype(np.int32),
            (10, 10, 10),
        )
        self.assertTrue(
            CandidateGenerators.generate_extreme_tone_quads(black)
        )

        alpha = np.zeros((self.h, self.w), dtype=np.uint8)
        cv2.fillConvexPoly(
            alpha,
            self.quad.astype(np.int32),
            128,
        )
        self.assertTrue(
            CandidateGenerators.generate_alpha_quads(alpha)
        )

        designed = np.full((self.h, self.w, 3), 125, dtype=np.uint8)
        cv2.rectangle(
            designed,
            (60, 45),
            (260, 195),
            (245, 245, 245),
            5,
        )
        for x in range(70, 255, 10):
            cv2.line(
                designed,
                (x, 55),
                (250 - (x - 70), 185),
                (20, 20, 20),
                2,
            )
        self.assertTrue(
            CandidateGenerators.generate_texture_robust_quads(designed)
        )


if __name__ == "__main__":
    unittest.main()
