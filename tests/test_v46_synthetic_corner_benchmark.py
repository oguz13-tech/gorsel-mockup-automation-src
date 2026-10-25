import json

from scripts.v46_synthetic_corner_benchmark import run


def test_synthetic_corner_benchmark_isolated_and_measured(tmp_path):
    output = tmp_path / "corner-benchmark.json"
    result = run(output, sample_count=4)
    assert output.is_file()
    assert result["dataset"] == "synthetic_only"
    assert result["acceptance"] == "INSUFFICIENT_GOLDEN_HUMAN_REVIEW_REQUIRED"
    assert set(result["summary"]) == {"canny_contour", "hough_hull", "bright_region"}
    for metrics in result["summary"].values():
        assert metrics["true_panel_count"] == 4
        assert metrics["mean_elapsed_ms"] >= 0
        assert 0 <= metrics["median_iou"] <= 1
        assert metrics["false_positive_no_panel"] >= 0
    assert json.loads(output.read_text(encoding="utf-8"))["no_panel_count"] == 3
