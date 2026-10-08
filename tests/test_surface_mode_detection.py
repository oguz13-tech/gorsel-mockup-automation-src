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
