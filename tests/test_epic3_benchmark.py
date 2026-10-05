import unittest
from unittest.mock import patch

import numpy as np

from scripts import epic3_benchmark
from SABLON_V2_MIMARI.core import template_intelligence


class TestEpic3FrozenEvaluator(unittest.TestCase):
    def test_valid_prediction_is_independent_of_production_validator(self):
        quad = [[10, 10], [90, 10], [90, 90], [10, 90]]
        with patch.object(
            template_intelligence.GeometryValidator,
            "is_valid_quad",
            side_effect=RuntimeError("production validator must not be used"),
        ):
            normalized = epic3_benchmark._valid_prediction(quad, 100, 100)

        self.assertIsNotNone(normalized)
        self.assertEqual(np.asarray(normalized).shape, (4, 2))

    def test_prediction_contract_rejects_tiny_quad(self):
        quad = [[1, 1], [5, 1], [5, 5], [1, 5]]
        self.assertIsNone(epic3_benchmark._valid_prediction(quad, 100, 100))

    def test_gt_contract_rejects_out_of_bounds(self):
        ok, _, normalized = epic3_benchmark._valid_gt(
            [[10, 10], [110, 10], [90, 90], [10, 90]],
            100,
            100,
        )
        self.assertFalse(ok)
        self.assertIsNone(normalized)

    def test_tie_safe_ordering_preserves_four_unique_vertices(self):
        diamond = np.array(
            [[50, 10], [90, 50], [50, 90], [10, 50]],
            dtype=np.float32,
        )
        ordered = epic3_benchmark._canonical_eval_quad(diamond)
        self.assertEqual(ordered.shape, (4, 2))
        self.assertEqual(len({tuple(map(float, p)) for p in ordered}), 4)


if __name__ == "__main__":
    unittest.main()
