import json
import unittest
from pathlib import Path


LAB = Path(__file__).resolve().parent
REPORTS = LAB / "reports"
REVIEW = LAB / "phase3" / "visual_review"


class Phase3ABExperimentTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(
            (REPORTS / "PHASE3_AB_EXPERIMENT.json").read_text(encoding="utf-8")
        )

    def test_existing_evidence_covers_all_categories(self):
        self.assertEqual(self.data["summary"]["tested_images"], 170)
        self.assertEqual(len(self.data["summary"]["category_counts"]), 7)
        self.assertEqual(self.data["summary"]["ground_truth"], "UNKNOWN_GT")
        self.assertIsNone(self.data["summary"]["accuracy_claim"])

    def test_review_sets_are_exact_and_unapproved(self):
        self.assertEqual(len(self.data["glass_review"]), 20)
        self.assertEqual(len(self.data["category_review"]), 28)
        self.assertTrue(
            all(row["production_decision"] == "REVIEW_REQUIRED" for row in self.data["rows"])
        )

    def test_public_reports_do_not_claim_accuracy(self):
        matrix = json.loads(
            (REPORTS / "PHASE3_VALIDATION_MATRIX.json").read_text(encoding="utf-8")
        )
        self.assertEqual(matrix["status"], "PARTIAL_BLOCKED")
        self.assertIsNone(matrix["metrics"]["mask_iou"])
        self.assertEqual(matrix["privacy"]["public_full_dataset"], False)

    def test_visual_review_index_and_cards_exist(self):
        self.assertTrue((REVIEW / "INDEX.html").exists())
        self.assertGreaterEqual(len(list(REVIEW.glob("*.jpg"))), 40)


if __name__ == "__main__":
    unittest.main()
