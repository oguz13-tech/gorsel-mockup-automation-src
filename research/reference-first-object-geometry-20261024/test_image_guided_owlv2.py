import json
import unittest
from pathlib import Path


LAB = Path(__file__).resolve().parent
REPORTS = LAB / "reports"
GALLERY = LAB / "phase3" / "image_guided_review"


class ImageGuidedEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(
            (REPORTS / "PHASE3_IMAGE_GUIDED_OWLV2.json").read_text(encoding="utf-8")
        )

    def test_real_image_guided_api_and_coverage(self):
        self.assertEqual(
            self.data["model_api"],
            "Owlv2ForObjectDetection.image_guided_detection",
        )
        self.assertEqual(len(self.data["rows"]), 528)
        self.assertEqual(
            len({(row["category"], row["target_image_id"]) for row in self.data["rows"]}),
            140,
        )

    def test_reference_counts_are_recorded(self):
        self.assertEqual(
            {row["reference_count"] for row in self.data["rows"]},
            {1, 3, 5, 10},
        )
        self.assertTrue(
            all(row["ground_truth"] == "UNKNOWN_GT" for row in self.data["rows"])
        )
        self.assertTrue(
            all(row["decision"] == "REVIEW_REQUIRED" for row in self.data["rows"])
        )

    def test_gallery_has_six_cards_per_available_category(self):
        self.assertTrue((GALLERY / "INDEX.html").exists())
        self.assertEqual(len(list(GALLERY.glob("*.jpg"))), 36)


if __name__ == "__main__":
    unittest.main()
