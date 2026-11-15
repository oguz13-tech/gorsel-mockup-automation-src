import json
import os
import shutil
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import cv2
import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from scripts import benchmark


class _NewAnalyzer:
    def analyze(self, sample_path, category):
        if category == benchmark.CATEGORIES[0]:
            raise RuntimeError("synthetic new detection failure")
        return {
            "surface_quad": [[10, 10], [90, 10], [90, 90], [10, 90]],
            "confidence_total": 0.5,
        }


class _OldAnalyzer:
    def analyze(self, sample_path, category):
        return {
            "surface_quad": [[15, 15], [85, 15], [85, 85], [15, 85]],
            "confidence_total": 0.0,
        }


class BenchmarkFixtureTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.output_json = os.path.join(self.temp_dir, "benchmark_out.json")
        self.gt = {}

        for index, category in enumerate(benchmark.CATEGORIES):
            name = f"sample_{index}.png"
            path = os.path.join(self.temp_dir, name)
            cv2.imwrite(path, np.zeros((100, 100, 3), dtype=np.uint8))
            self.gt[name] = {
                "category": category,
                "quad": [[10, 10], [90, 10], [90, 90], [10, 90]],
            }

        invalid_name = "invalid_gt.png"
        cv2.imwrite(
            os.path.join(self.temp_dir, invalid_name),
            np.zeros((100, 100, 3), dtype=np.uint8),
        )
        self.gt[invalid_name] = {
            "category": benchmark.CATEGORIES[0],
            "quad": [[1, 1], [2, 2], [3, 3]],
        }

        with open(
            os.path.join(self.temp_dir, "ground_truth.json"),
            "w",
            encoding="utf-8",
        ) as handle:
            json.dump(self.gt, handle)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_run_benchmark_separates_exclusions_and_detection_failures(self):
        old_tmp = tempfile.mkdtemp(prefix="fake_old_adapter_")
        old_module = SimpleNamespace(TemplateAnalyzer=_OldAnalyzer)

        with patch.object(benchmark, "TemplateAnalyzer", _NewAnalyzer), patch.object(
            benchmark,
            "load_old_analyzer",
            return_value=(old_module, old_tmp),
        ):
            results = benchmark.run_benchmark(self.temp_dir, self.output_json)

        self.assertTrue(os.path.exists(self.output_json))
        self.assertFalse(
            os.path.exists(old_tmp),
            "OLD analyzer temp directory must be removed after successful benchmark",
        )

        self.assertEqual(results["attempted_total"], 7)
        self.assertEqual(results["valid_evaluated_count"], 6)
        self.assertEqual(results["excluded_count"], 1)
        self.assertEqual(results["exclusions"][0]["reason_type"], "INVALID_GT")

        new_metrics = results["global_metrics"]["new"]
        old_metrics = results["global_metrics"]["old"]
        self.assertEqual(new_metrics["detection_failure_count"], 1)
        self.assertAlmostEqual(new_metrics["detection_failure_rate"], 1 / 6)
        self.assertEqual(old_metrics["detection_failure_count"], 0)
        self.assertEqual(old_metrics["detection_rate"], 1.0)

        self.assertGreater(
            old_metrics["median_corner_error"],
            new_metrics["median_corner_error"],
        )
        self.assertNotEqual(
            old_metrics["median_iou"],
            new_metrics["median_iou"],
        )

        first_cat = results["categories"][benchmark.CATEGORIES[0]]
        self.assertEqual(first_cat["excluded"], 1)
        self.assertEqual(first_cat["new"]["detection_failure_count"], 1)
        self.assertEqual(first_cat["old"]["detection_failure_count"], 0)

    def test_validate_gt_quad_rejects_bad_shapes_and_nonfinite_values(self):
        valid, reason, normalized = benchmark.validate_gt_quad(
            [[1, 1], [2, 2], [3, 3]],
            100,
            100,
        )
        self.assertFalse(valid)
        self.assertIsNone(normalized)
        self.assertIn("exactly 4", reason)

        valid, reason, normalized = benchmark.validate_gt_quad(
            [[10, 10], [90, 10], [90, float("nan")], [10, 90]],
            100,
            100,
        )
        self.assertFalse(valid)
        self.assertIsNone(normalized)
        self.assertIn("non-finite", reason)

        valid, reason, normalized = benchmark.validate_gt_quad(
            [[10, 10], [120, 10], [90, 90], [10, 90]],
            100,
            100,
        )
        self.assertFalse(valid)
        self.assertIsNone(normalized)
        self.assertIn("outside image bounds", reason)


if __name__ == "__main__":
    unittest.main()
