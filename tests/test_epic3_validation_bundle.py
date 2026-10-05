import importlib.util
from pathlib import Path
import tempfile
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

    def test_archive_evidence_artifacts_preserves_prior_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            owned_a = root / "epic3_benchmark.json"
            owned_b = root / "validation_manifest.json"
            unrelated = root / "keep_me.txt"
            owned_a.write_text("old-benchmark", encoding="utf-8")
            owned_b.write_text("old-manifest", encoding="utf-8")
            unrelated.write_text("keep", encoding="utf-8")

            archive_path = bundle._archive_evidence_artifacts(
                [owned_a, owned_b],
                root,
            )

            self.assertIsNotNone(archive_path)
            archive = Path(archive_path)
            self.assertFalse(owned_a.exists())
            self.assertFalse(owned_b.exists())
            self.assertEqual(
                (archive / owned_a.name).read_text(encoding="utf-8"),
                "old-benchmark",
            )
            self.assertEqual(
                (archive / owned_b.name).read_text(encoding="utf-8"),
                "old-manifest",
            )
            self.assertTrue(unrelated.exists())

    def test_command_succeeded_requires_current_run_success(self):
        commands = [
            {"name": "geometry_diagnostics", "ok": False},
            {"name": "epic3_benchmark", "ok": True},
        ]
        self.assertFalse(
            bundle._command_succeeded(commands, "geometry_diagnostics")
        )
        self.assertTrue(
            bundle._command_succeeded(commands, "epic3_benchmark")
        )
        self.assertFalse(
            bundle._command_succeeded(commands, "scorer_telemetry")
        )

    def test_review_readiness_requires_unit_tests(self):
        common = {
            "commands_ok": True,
            "diagnostic_ok": True,
            "benchmark_ok": True,
            "golden_coverage_ok": True,
            "telemetry_ok": True,
            "cross_evidence_ok": True,
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

    def test_cross_evidence_consistency_requires_matching_valid_counts(self):
        bench = bundle._benchmark_summary(
            _benchmark(bundle.MIN_GOLDEN_VALID_COUNTS)
        )
        diag_categories = {
            category: {
                "valid_evaluated": count,
                "classification_total": count,
                "counts_match": True,
            }
            for category, count in bundle.MIN_GOLDEN_VALID_COUNTS.items()
        }
        evidence = {
            "benchmark": bench,
            "diagnostic_invariants": {
                "global_valid_evaluated": sum(
                    bundle.MIN_GOLDEN_VALID_COUNTS.values()
                ),
                "global_counts_match": True,
                "all_category_counts_match": True,
                "categories": diag_categories,
            },
        }

        result = bundle._cross_evidence_consistency(evidence)
        self.assertTrue(result["ok"])

        evidence["diagnostic_invariants"]["categories"][
            "04_Cam_Dograma"
        ]["valid_evaluated"] -= 1
        result = bundle._cross_evidence_consistency(evidence)
        self.assertFalse(result["ok"])
        self.assertFalse(
            result["per_category"]["04_Cam_Dograma"]["match"]
        )

    def test_runtime_readonly_snapshot_detects_byte_and_path_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Path(tmp)
            template_dir = runtime / "2_SABLON_HAVUZU" / "01_Wifi_Kutusu"
            template_dir.mkdir(parents=True)
            template = template_dir / "sample.png"
            template.write_bytes(b"original")

            before = bundle._snapshot_runtime_readonly_inputs(runtime)
            template.write_bytes(b"changed")
            after = bundle._snapshot_runtime_readonly_inputs(runtime)
            self.assertNotEqual(before, after)

            template.write_bytes(b"original")
            restored = bundle._snapshot_runtime_readonly_inputs(runtime)
            self.assertEqual(before, restored)

            mask_dir = (
                runtime
                / "99_SISTEM_MOTORLARI_VE_KODLAR"
                / "SISTEM_MOTORU"
                / "masks"
            )
            mask_dir.mkdir(parents=True)
            directory_created = bundle._snapshot_runtime_readonly_inputs(runtime)
            self.assertNotEqual(before, directory_created)

    def test_review_readiness_requires_telemetry_and_cross_evidence(self):
        common = {
            "commands_ok": True,
            "unit_tests_executed": True,
            "diagnostic_ok": True,
            "benchmark_ok": True,
            "golden_coverage_ok": True,
            "integrity_ok": True,
        }
        self.assertFalse(
            bundle._review_readiness(
                telemetry_ok=False,
                cross_evidence_ok=True,
                **common,
            )
        )
        self.assertFalse(
            bundle._review_readiness(
                telemetry_ok=True,
                cross_evidence_ok=False,
                **common,
            )
        )
        self.assertTrue(
            bundle._review_readiness(
                telemetry_ok=True,
                cross_evidence_ok=True,
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
