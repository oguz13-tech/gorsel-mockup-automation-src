import unittest

import numpy as np

from scripts.geometry_diagnostics import (
    IOU_TARGET,
    _summarize,
    classify_sample,
    prepare_runtime_candidates,
)


class GeometryDiagnosticUnitTests(unittest.TestCase):
    def test_classification_separates_generator_and_scorer_failures(self):
        self.assertEqual(
            classify_sample(0, selected_iou=0.0, oracle_iou=0.0),
            "NO_VALID_CANDIDATE",
        )
        self.assertEqual(
            classify_sample(3, selected_iou=0.65, oracle_iou=0.80),
            "GOOD_SELECTED",
        )
        self.assertEqual(
            classify_sample(3, selected_iou=0.20, oracle_iou=0.75),
            "SCORER_LIMITED",
        )
        self.assertEqual(
            classify_sample(3, selected_iou=0.20, oracle_iou=0.40),
            "GENERATOR_LIMITED",
        )

    def test_summary_uses_oracle_and_selected_independently(self):
        records = [
            {
                "selected_iou": 0.20,
                "oracle_iou": 0.80,
                "selection_gap": 0.60,
                "classification": "SCORER_LIMITED",
                "oracle_sources": ["canny"],
            },
            {
                "selected_iou": 0.60,
                "oracle_iou": 0.70,
                "selection_gap": 0.10,
                "classification": "GOOD_SELECTED",
                "oracle_sources": ["color_region"],
            },
        ]

        summary = _summarize(records)

        self.assertEqual(summary["valid_evaluated"], 2)
        self.assertAlmostEqual(summary["selected_median_iou"], 0.40)
        self.assertAlmostEqual(summary["oracle_median_iou"], 0.75)
        self.assertAlmostEqual(summary["selected_recall_at_50"], 0.5)
        self.assertAlmostEqual(summary["oracle_recall_at_50"], 1.0)
        self.assertEqual(summary["classification_counts"]["SCORER_LIMITED"], 1)
        self.assertEqual(summary["classification_counts"]["GOOD_SELECTED"], 1)
        self.assertEqual(summary["oracle_generator_wins"]["canny"], 1)
        self.assertEqual(summary["oracle_generator_wins"]["color_region"], 1)

    def test_runtime_candidate_preparation_enforces_production_cap(self):
        class FakeAnalyzer:
            @staticmethod
            def score_area_plausibility(area_ratio):
                return float(area_ratio)

            @staticmethod
            def measure_edge_contrast(image, quad):
                return float(quad[0][0]) / 1000.0

        image = np.zeros((1000, 1000, 3), dtype=np.uint8)
        candidates = []
        for idx in range(181):
            x = float(idx)
            candidates.append({
                "quad": [
                    [x, 10.0],
                    [x + 100.0, 10.0],
                    [x + 100.0, 110.0],
                    [x, 110.0],
                ],
                "sources": ["synthetic"],
            })

        prepared = prepare_runtime_candidates(
            FakeAnalyzer(),
            image,
            candidates,
        )

        self.assertEqual(len(prepared), 180)

    def test_iou_target_is_review_quality_diagnostic_not_auto_approval(self):
        self.assertEqual(IOU_TARGET, 0.50)


if __name__ == "__main__":
    unittest.main()
