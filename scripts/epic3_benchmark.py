"""EPIC-3 release benchmark: compare current geometry against merged EPIC-2.

This is an evidence tool, not a production dependency. It must be run against the
real local golden dataset. Dataset images/results stay outside Git.

The benchmark deliberately loads the exact merged EPIC-2 analyzer from Git so
baseline and current code are evaluated on the same valid ground-truth samples.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Dict, List

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
ARCH = ROOT / "SABLON_V2_MIMARI"
sys.path.insert(0, str(ARCH))
sys.path.insert(0, str(ROOT))

from core.template_intelligence import TemplateAnalyzer
from scripts.benchmark import CATEGORIES, calculate_corner_error, calculate_iou

EPIC2_BASELINE_SHA = "97cd5cbad562ffff8904d13b28516f4390430d8b"
IOU_TARGET = 0.50


def _load_analyzer_from_git(commit_sha: str):
    tmp_dir = Path(tempfile.mkdtemp(prefix="epic3_baseline_"))
    module_path = tmp_dir / "template_intelligence.py"
    try:
        proc = subprocess.run(
            [
                "git",
                "show",
                f"{commit_sha}:SABLON_V2_MIMARI/core/template_intelligence.py",
            ],
            cwd=str(ROOT),
            capture_output=True,
            check=True,
        )
        source = proc.stdout.decode("utf-8")
        module_path.write_text(source, encoding="utf-8")
        spec = importlib.util.spec_from_file_location(
            "epic2_template_intelligence", str(module_path)
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("Could not build EPIC-2 analyzer module spec")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.TemplateAnalyzer(), tmp_dir
    except Exception:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise


def _canonical_eval_quad(quad: np.ndarray) -> np.ndarray:
    """Benchmark-owned deterministic TL/TR/BR/BL ordering.

    Release evidence must not change merely because production geometry helpers
    evolve. Keep evaluator ordering local and version-stable.
    """
    arr = np.asarray(quad, dtype=np.float64)
    center = np.mean(arr, axis=0)
    angles = np.arctan2(arr[:, 1] - center[1], arr[:, 0] - center[0])
    cycle = arr[np.argsort(angles)]

    signed_twice_area = float(
        np.sum(
            cycle[:, 0] * np.roll(cycle[:, 1], -1)
            - np.roll(cycle[:, 0], -1) * cycle[:, 1]
        )
    )
    if signed_twice_area < 0:
        cycle = cycle[::-1]

    sums = cycle[:, 0] + cycle[:, 1]
    min_sum = float(np.min(sums))
    tied = np.flatnonzero(np.isclose(sums, min_sum, rtol=0.0, atol=1e-6))
    if len(tied) == 1:
        start = int(tied[0])
    else:
        start = min(
            (int(i) for i in tied),
            key=lambda i: (cycle[i, 1], cycle[i, 0]),
        )
    return np.roll(cycle, -start, axis=0).astype(np.float32)


def _evaluate_quad(quad, width: int, height: int, *, gt: bool = False):
    """Frozen evaluator contract shared by EPIC-2 and EPIC-3 predictions."""
    if quad is None or width <= 0 or height <= 0:
        return None
    try:
        arr = np.asarray(quad, dtype=np.float32)
    except (TypeError, ValueError):
        return None
    if arr.shape != (4, 2) or not np.isfinite(arr).all():
        return None

    if gt:
        tol = 0.5
        if (
            np.any(arr[:, 0] < -tol)
            or np.any(arr[:, 0] > (width - 1) + tol)
            or np.any(arr[:, 1] < -tol)
            or np.any(arr[:, 1] > (height - 1) + tol)
        ):
            return None
    else:
        if (
            np.any(arr[:, 0] < -width * 0.5)
            or np.any(arr[:, 0] > width * 1.5)
            or np.any(arr[:, 1] < -height * 0.5)
            or np.any(arr[:, 1] > height * 1.5)
        ):
            return None

    canonical = _canonical_eval_quad(arr)
    area = float(abs(cv2.contourArea(canonical)))
    if gt:
        if area <= 1.0:
            return None
    elif area < float(width * height) * 0.05:
        return None

    if not cv2.isContourConvex(canonical.astype(np.int32)):
        return None

    edges = [
        float(np.linalg.norm(canonical[(i + 1) % 4] - canonical[i]))
        for i in range(4)
    ]
    minimum_edge = 1.0 if gt else 10.0
    if min(edges) <= minimum_edge:
        return None

    if not gt:
        avg_w = (edges[0] + edges[2]) * 0.5
        avg_h = (edges[1] + edges[3]) * 0.5
        if avg_w <= 0 or avg_h <= 0:
            return None
        if avg_w / avg_h > 10.0 or avg_h / avg_w > 10.0:
            return None
        target = np.array(
            [[0, 0], [100, 0], [100, 100], [0, 100]],
            dtype=np.float32,
        )
        matrix, _ = cv2.findHomography(canonical, target)
        if matrix is None or np.linalg.cond(matrix) > 1e6:
            return None

    return canonical.astype(float).tolist()


def _valid_prediction(quad, width: int, height: int):
    return _evaluate_quad(quad, width, height, gt=False)


def _valid_gt(quad, width: int, height: int):
    normalized = _evaluate_quad(quad, width, height, gt=True)
    if normalized is None:
        return False, "GT quad failed frozen benchmark validation", None
    return True, "Valid", normalized


def _summarize(records: List[Dict], prefix: str) -> Dict:
    if not records:
        return {
            "count": 0,
            "detection_rate": 0.0,
            "median_iou": 0.0,
            "recall_at_50": 0.0,
            "median_corner_error": 0.0,
            "p95_corner_error": 0.0,
            "high_confidence_bad": 0,
        }

    detected = [bool(row[f"{prefix}_detected"]) for row in records]
    ious = [float(row[f"{prefix}_iou"]) for row in records]
    errors = [float(row[f"{prefix}_corner_error"]) for row in records]
    high_bad = sum(
        1
        for row in records
        if float(row.get(f"{prefix}_confidence", 0.0) or 0.0) >= 0.85
        and float(row[f"{prefix}_iou"]) < IOU_TARGET
    )
    total = len(records)
    return {
        "count": total,
        "detection_rate": float(sum(detected) / total),
        "median_iou": float(np.median(ious)),
        "recall_at_50": float(sum(v >= IOU_TARGET for v in ious) / total),
        "median_corner_error": float(np.median(errors)),
        "p95_corner_error": float(np.percentile(errors, 95)),
        "detection_failure_count": int(total - sum(detected)),
        "high_confidence_bad": int(high_bad),
    }


def run(dataset_path: Path, output_path: Path) -> Dict:
    gt_path = dataset_path / "ground_truth.json"
    if not gt_path.is_file():
        raise ValueError(f"ground_truth.json missing: {gt_path}")

    dataset = json.loads(gt_path.read_text(encoding="utf-8"))
    if not isinstance(dataset, dict):
        raise ValueError("ground_truth.json must contain an object")

    current = TemplateAnalyzer()
    baseline = None
    baseline_tmp = None

    result = {
        "epic2_baseline_sha": EPIC2_BASELINE_SHA,
        "iou_target": IOU_TARGET,
        "attempted": 0,
        "valid_evaluated": 0,
        "excluded": 0,
        "exclusions": [],
        "categories": {},
        "records": [],
    }

    try:
        baseline, baseline_tmp = _load_analyzer_from_git(EPIC2_BASELINE_SHA)

        for category in CATEGORIES:
            names = [
                name
                for name, meta in dataset.items()
                if isinstance(meta, dict) and meta.get("category") == category
            ]
            if not names:
                raise ValueError(f"Required category has no samples: {category}")

            category_records = []
            category_excluded = 0

            for name in names:
                result["attempted"] += 1
                image_path = dataset_path / name
                image = cv2.imread(str(image_path))
                if image is None:
                    raise ValueError(f"Unreadable sample: {image_path}")
                h, w = image.shape[:2]

                gt_ok, gt_reason, gt_quad = _valid_gt(
                    dataset[name].get("quad"), w, h
                )
                if not gt_ok:
                    result["excluded"] += 1
                    category_excluded += 1
                    result["exclusions"].append(
                        {"sample": name, "category": category, "reason": gt_reason}
                    )
                    continue

                row = {"sample": name, "category": category}

                for prefix, analyzer in (("epic2", baseline), ("epic3", current)):
                    pred = None
                    confidence = 0.0
                    error = None
                    try:
                        analysis = analyzer.analyze(str(image_path), category)
                        pred = _valid_prediction(
                            analysis.get("surface_quad"), w, h
                        )
                        confidence = float(
                            analysis.get("confidence_total", 0.0) or 0.0
                        )
                    except Exception as exc:
                        error = str(exc)

                    row[f"{prefix}_detected"] = pred is not None
                    row[f"{prefix}_iou"] = calculate_iou(
                        pred, gt_quad, w, h
                    )
                    row[f"{prefix}_corner_error"] = calculate_corner_error(
                        pred, gt_quad, w, h
                    )
                    row[f"{prefix}_confidence"] = confidence
                    row[f"{prefix}_error"] = error

                row["iou_delta"] = float(row["epic3_iou"] - row["epic2_iou"])
                row["corner_error_delta"] = float(
                    row["epic3_corner_error"] - row["epic2_corner_error"]
                )
                result["records"].append(row)
                category_records.append(row)
                result["valid_evaluated"] += 1

            result["categories"][category] = {
                "attempted": len(names),
                "excluded": category_excluded,
                "epic2": _summarize(category_records, "epic2"),
                "epic3": _summarize(category_records, "epic3"),
                "regressed_iou_count": sum(
                    1 for row in category_records if row["iou_delta"] < -0.05
                ),
                "improved_iou_count": sum(
                    1 for row in category_records if row["iou_delta"] > 0.05
                ),
            }

        result["global"] = {
            "epic2": _summarize(result["records"], "epic2"),
            "epic3": _summarize(result["records"], "epic3"),
            "regressed_iou_count": sum(
                1 for row in result["records"] if row["iou_delta"] < -0.05
            ),
            "improved_iou_count": sum(
                1 for row in result["records"] if row["iou_delta"] > 0.05
            ),
            "category_wins_by_median_iou": dict(
                Counter(
                    "epic3"
                    if result["categories"][category]["epic3"]["median_iou"]
                    > result["categories"][category]["epic2"]["median_iou"]
                    else "epic2_or_tie"
                    for category in CATEGORIES
                )
            ),
        }

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        print(
            "EPIC-3 benchmark finished: "
            f"{result['attempted']} attempted, "
            f"{result['valid_evaluated']} valid, "
            f"{result['excluded']} excluded."
        )
        print(
            "Median IoU EPIC-2 -> EPIC-3: "
            f"{result['global']['epic2']['median_iou']:.3f} -> "
            f"{result['global']['epic3']['median_iou']:.3f}"
        )
        print(f"Saved: {output_path}")
        return result
    finally:
        if baseline_tmp is not None:
            shutil.rmtree(baseline_tmp, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    run(args.dataset.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()
