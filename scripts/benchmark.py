import os
import sys
import json
import time
import tempfile
import subprocess
import importlib.util
import shutil
from pathlib import Path

import cv2
import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "SABLON_V2_MIMARI"))

from core.template_intelligence import TemplateAnalyzer, GeometryValidator

BASELINE_SHA = "b638203db97e262dd75d17766ec796a996c28686"
CATEGORIES = [
    "01_Wifi_Kutusu",
    "02_Cam_Tablo_Dikey",
    "02_Cam_Tablo_Yatay",
    "03_Ahsap_Tablo",
    "04_Cam_Dograma",
    "05_Ocak_Arkasi",
]


def calculate_iou(quad1, quad2, w, h):
    """Calculate Intersection over Union for two quads."""
    if quad1 is None or quad2 is None:
        return 0.0

    mask1 = np.zeros((h, w), dtype=np.uint8)
    mask2 = np.zeros((h, w), dtype=np.uint8)
    cv2.fillPoly(mask1, [np.array(quad1, dtype=np.int32)], 255)
    cv2.fillPoly(mask2, [np.array(quad2, dtype=np.int32)], 255)

    intersection = np.logical_and(mask1, mask2).sum()
    union = np.logical_or(mask1, mask2).sum()
    return 0.0 if union == 0 else float(intersection / union)


def calculate_corner_error(quad_pred, quad_gt, w, h):
    """Mean corner error normalized by image diagonal. Detection failure = 1.0."""
    if quad_pred is None or quad_gt is None:
        return 1.0

    diag = float(np.sqrt(w ** 2 + h ** 2))
    if diag <= 0:
        return 1.0
    p1 = np.asarray(quad_pred, dtype=np.float64)
    p2 = np.asarray(quad_gt, dtype=np.float64)
    if p1.shape != (4, 2) or p2.shape != (4, 2):
        return 1.0
    return float(np.mean(np.linalg.norm(p1 - p2, axis=1)) / diag)


def validate_gt_quad(quad, w, h):
    """Strict dataset GT validation. Returns (valid, reason, canonical_quad)."""
    if not isinstance(quad, (list, tuple)) or len(quad) != 4:
        return False, "GT must contain exactly 4 points", None

    try:
        arr = np.asarray(quad, dtype=np.float64)
    except (TypeError, ValueError):
        return False, "GT points must be numeric", None

    if arr.shape != (4, 2):
        return False, "GT must be four numeric 2D points", None
    if not np.isfinite(arr).all():
        return False, "GT contains non-finite coordinates", None
    if w <= 0 or h <= 0:
        return False, "Invalid image dimensions", None

    # A tiny half-pixel tolerance avoids rejecting coordinates serialized at the border.
    tol = 0.5
    if (
        np.any(arr[:, 0] < -tol)
        or np.any(arr[:, 0] > (w - 1) + tol)
        or np.any(arr[:, 1] < -tol)
        or np.any(arr[:, 1] > (h - 1) + tol)
    ):
        return False, "GT coordinate outside image bounds", None

    canonical = GeometryValidator.canonical_sort(arr.astype(np.float32))
    area = float(abs(cv2.contourArea(canonical)))
    if area <= 1.0:
        return False, "GT quad is degenerate", None
    if not cv2.isContourConvex(canonical.astype(np.int32)):
        return False, "GT quad is non-convex or self-intersecting", None

    edges = [
        float(np.linalg.norm(canonical[(i + 1) % 4] - canonical[i]))
        for i in range(4)
    ]
    if min(edges) <= 1.0:
        return False, "GT quad has degenerate edge", None

    return True, "Valid", canonical.astype(float).tolist()


def _prediction_is_valid(quad, w, h):
    if quad is None:
        return False
    try:
        arr = np.asarray(quad, dtype=np.float32)
        if arr.shape != (4, 2) or not np.isfinite(arr).all():
            return False
        valid, _ = GeometryValidator.is_valid_quad(arr, w, h)
        return bool(valid)
    except Exception:
        return False


def load_old_analyzer():
    """Load the exact historical analyzer from git into an isolated temp directory."""
    tmp_dir = tempfile.mkdtemp(prefix="bench_old_")
    old_path = os.path.join(tmp_dir, "template_intelligence.py")
    try:
        cmd = [
            "git",
            "show",
            f"{BASELINE_SHA}:SABLON_V2_MIMARI/core/template_intelligence.py",
        ]
        result = subprocess.run(cmd, capture_output=True, check=True)
        try:
            source = result.stdout.decode("utf-8")
        except UnicodeDecodeError:
            source = result.stdout.decode("utf-16")

        with open(old_path, "w", encoding="utf-8") as handle:
            handle.write(source)

        spec = importlib.util.spec_from_file_location("old_template_intelligence", old_path)
        if spec is None or spec.loader is None:
            raise RuntimeError("Unable to create OLD analyzer module spec")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module, tmp_dir
    except Exception:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise


def _metric_summary(records, prefix):
    total = len(records)
    detected = sum(1 for record in records if record[f"{prefix}_detected"])
    failures = total - detected
    ious = [float(record[f"{prefix}_iou"]) for record in records]
    errors = [float(record[f"{prefix}_corner_error"]) for record in records]

    return {
        "detection_rate": float(detected / total) if total else 0.0,
        "median_iou": float(np.median(ious)) if ious else 0.0,
        "median_corner_error": float(np.median(errors)) if errors else 0.0,
        "p95_corner_error": float(np.percentile(errors, 95)) if errors else 0.0,
        "detection_failure_count": int(failures),
        "detection_failure_rate": float(failures / total) if total else 0.0,
    }


def _with_new_aliases(container):
    """Keep existing NEW metric names while exposing explicit OLD/NEW groups."""
    new = container["new"]
    container["detection_rate"] = new["detection_rate"]
    container["median_iou"] = new["median_iou"]
    container["median_corner_error"] = new["median_corner_error"]
    container["p95_corner_error"] = new["p95_corner_error"]
    container["detection_failure_count"] = new["detection_failure_count"]
    container["detection_failure_rate"] = new["detection_failure_rate"]
    return container


def run_benchmark(dataset_path: str, output_json: str):
    """
    Compare exact OLD baseline vs NEW on the same valid GT samples.
    Invalid/missing GT is excluded. Analyzer failure on valid GT is a detection
    failure and remains in the metric denominator.
    """
    analyzer = TemplateAnalyzer()
    old_tmp_dir = None

    try:
        try:
            old_module, old_tmp_dir = load_old_analyzer()
            old_analyzer = old_module.TemplateAnalyzer()
        except Exception as exc:
            raise ValueError(
                f"CRITICAL: Failed to load OLD algorithm adapter. Exception: {exc}. Benchmark blocked."
            ) from exc

        gt_file = os.path.join(dataset_path, "ground_truth.json")
        if not os.path.exists(gt_file):
            raise ValueError("CRITICAL: ground_truth.json missing. Benchmark blocked.")

        with open(gt_file, "r", encoding="utf-8") as handle:
            dataset = json.load(handle)
        if not isinstance(dataset, dict):
            raise ValueError("CRITICAL: ground_truth.json must be an object. Benchmark blocked.")

        results = {
            "timestamp": time.time(),
            "baseline_sha": BASELINE_SHA,
            "attempted_total": 0,
            "total_samples": 0,
            "valid_evaluated_count": 0,
            "excluded_count": 0,
            "exclusion_rate": 0.0,
            "categories": {},
            "global_metrics": {
                "baseline_sha": BASELINE_SHA,
                "new": {},
                "old": {},
                "high_confidence_bad": 0,
            },
            "exclusions": [],
            "raw_evidence": [],
        }

        for category in CATEGORIES:
            samples = [
                name
                for name, metadata in dataset.items()
                if isinstance(metadata, dict) and metadata.get("category") == category
            ]
            if not samples:
                raise ValueError(
                    f"CRITICAL: Missing real samples for category {category}. Benchmark blocked."
                )

            category_records = []
            category_exclusions = 0

            for sample in samples:
                results["attempted_total"] += 1
                results["total_samples"] += 1

                sample_path = os.path.join(dataset_path, sample)
                if not os.path.exists(sample_path):
                    raise ValueError(
                        f"CRITICAL: Missing sample file {sample_path}. Benchmark blocked."
                    )

                image = cv2.imread(sample_path)
                if image is None:
                    raise ValueError(
                        f"CRITICAL: Unreadable image {sample_path}. Benchmark blocked."
                    )
                h, w = image.shape[:2]

                gt_quad = dataset[sample].get("quad")
                gt_valid, gt_reason, canonical_gt = validate_gt_quad(gt_quad, w, h)
                if not gt_valid:
                    category_exclusions += 1
                    results["excluded_count"] += 1
                    results["exclusions"].append(
                        {
                            "sample": sample,
                            "category": category,
                            "reason_type": "INVALID_GT",
                            "reason": gt_reason,
                        }
                    )
                    continue

                new_pred = None
                new_conf = 0.0
                new_error_text = None
                try:
                    new_result = analyzer.analyze(sample_path, category)
                    new_pred = new_result.get("surface_quad")
                    new_conf = float(new_result.get("confidence_total", 0.0) or 0.0)
                except Exception as exc:
                    new_error_text = str(exc)

                old_pred = None
                old_error_text = None
                try:
                    old_result = old_analyzer.analyze(sample_path, category)
                    old_pred = old_result.get("surface_quad")
                except Exception as exc:
                    old_error_text = str(exc)

                new_detected = _prediction_is_valid(new_pred, w, h)
                old_detected = _prediction_is_valid(old_pred, w, h)
                if not new_detected:
                    new_pred = None
                if not old_detected:
                    old_pred = None

                record = {
                    "sample": sample,
                    "category": category,
                    "new_detected": new_detected,
                    "old_detected": old_detected,
                    "new_iou": calculate_iou(new_pred, canonical_gt, w, h),
                    "old_iou": calculate_iou(old_pred, canonical_gt, w, h),
                    "new_corner_error": calculate_corner_error(new_pred, canonical_gt, w, h),
                    "old_corner_error": calculate_corner_error(old_pred, canonical_gt, w, h),
                    "new_conf": new_conf,
                    "new_error": new_error_text,
                    "old_error": old_error_text,
                }
                results["raw_evidence"].append(record)
                category_records.append(record)
                results["valid_evaluated_count"] += 1

                if new_conf > 0.85 and record["new_iou"] < 0.5:
                    results["global_metrics"]["high_confidence_bad"] += 1

            category_result = {
                "attempted": len(samples),
                "valid_evaluated": len(category_records),
                "valid_denominator": len(category_records),
                "excluded": category_exclusions,
                "exclusion_rate": float(category_exclusions / len(samples)) if samples else 0.0,
                "new": _metric_summary(category_records, "new"),
                "old": _metric_summary(category_records, "old"),
            }
            results["categories"][category] = _with_new_aliases(category_result)

        all_records = results["raw_evidence"]
        results["global_metrics"]["new"] = _metric_summary(all_records, "new")
        results["global_metrics"]["old"] = _metric_summary(all_records, "old")
        _with_new_aliases(results["global_metrics"])

        if results["attempted_total"]:
            results["exclusion_rate"] = float(
                results["excluded_count"] / results["attempted_total"]
            )
        results["global_metrics"]["excluded_count"] = results["excluded_count"]
        results["global_metrics"]["exclusion_rate"] = results["exclusion_rate"]

        with open(output_json, "w", encoding="utf-8") as handle:
            json.dump(results, handle, indent=2, ensure_ascii=False)

        print(
            "Benchmark finished on "
            f"{results['attempted_total']} attempted, "
            f"{results['valid_evaluated_count']} valid evaluated, "
            f"{results['excluded_count']} excluded."
        )
        print(f"Metrics saved to {output_json}")
        return results
    finally:
        if old_tmp_dir:
            shutil.rmtree(old_tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=str, default="benchmark_dataset")
    parser.add_argument("--output", type=str, default="benchmark_results_v4.json")
    args = parser.parse_args()
    run_benchmark(args.dataset, args.output)
