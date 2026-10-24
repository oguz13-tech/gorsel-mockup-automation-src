import json

from scripts.v46_all_category_geometry_benchmark import CATEGORIES, run


def test_all_categories_have_separate_synthetic_geometry_metrics(tmp_path):
    output = tmp_path / "all-categories.json"
    result = run(output, samples_per_category=2)
    assert result["real_golden_samples"] == 0
    assert set(result["categories"]) == set(CATEGORIES)
    assert output.is_file()
    for category, metrics in result["categories"].items():
        assert metrics["synthetic_samples"] == 2
        assert metrics["status"] == "HUMAN_REVIEW_REQUIRED"
        if category != "06_Petek_Kapama":
            assert 0 <= metrics["detection_rate"] <= 1
            assert 0 <= metrics["median_iou"] <= 1
        else:
            assert metrics["mask_outside_preserved"] is True
    assert json.loads(output.read_text(encoding="utf-8"))["dataset"] == "synthetic_only"
