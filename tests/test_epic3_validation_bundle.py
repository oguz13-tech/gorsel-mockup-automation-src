import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "epic3_validation_bundle.py"
SPEC = importlib.util.spec_from_file_location("epic3_validation_bundle", MODULE_PATH)
bundle = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(bundle)


def _benchmark(valid_counts):
    categories = {}
    total = 0
    for category, valid in valid_counts.items():
        valid = int(valid)
        total += valid
        categories[category] = {
            "attempted": valid,
            "excluded": 0,
            "epic2": {"median_iou": 0.1, "recall_at_50": 0.1},
            "epic3": {"median_iou": 0.2, "recall_at_50": 0.2},
        }
    return {
        "attempted": total,
        "valid_evaluated": total,
        "excluded": 0,
        "global": {
            "epic2": {"median_iou": 0.1, "recall_at_50": 0.1},
            "epic3": {"median_iou": 0.2, "recall_at_50": 0.2},
        },
        "categories": categories,
    }


class TestEpic3ValidationGoldenCoverage(unittest.TestCase):
    def test_canonical_baseline_passes(self):
        bench = _benchmark(bundle.MIN_GOLDEN_VALID_COUNTS)
        result = bundle._golden_coverage_check(bench)
        self.assertTrue(result["ok"])
        self.assertEqual(result["reported_global_valid"], 336)
        self.assertEqual(result["category_valid_total"], 336)

    def test_truncated_category_is_blocked(self):
        counts = dict(bundle.MIN_GOLDEN_VALID_COUNTS)
        counts["04_Cam_Dograma"] -= 1
        result = bundle._golden_coverage_check(_benchmark(counts))
        self.assertFalse(result["ok"])
        self.assertFalse(
            result["per_category"]["04_Cam_Dograma"]["meets_minimum"]
        )

    def test_global_category_total_mismatch_is_blocked(self):
        bench = _benchmark(bundle.MIN_GOLDEN_VALID_COUNTS)
        bench["valid_evaluated"] += 1
        result = bundle._golden_coverage_check(bench)
        self.assertFalse(result["ok"])
        self.assertFalse(result["global_matches_category_total"])

    def test_review_readiness_requires_unit_tests(self):
        common = {
            "commands_ok": True,
            "diagnostic_ok": True,
            "benchmark_ok": True,
            "golden_coverage_ok": True,
            "integrity_ok": True,
        }
        self.assertFalse(
            bundle._review_readiness(
                unit_tests_executed=False,
                **common,
            )
        )
        self.assertTrue(
            bundle._review_readiness(
                unit_tests_executed=True,
                **common,
            )
        )

    def test_expanded_dataset_is_allowed(self):
        counts = {
            category: minimum + 3
            for category, minimum in bundle.MIN_GOLDEN_VALID_COUNTS.items()
        }
        result = bundle._golden_coverage_check(_benchmark(counts))
        self.assertTrue(result["ok"])


if __name__ == "__main__":
    unittest.main()
