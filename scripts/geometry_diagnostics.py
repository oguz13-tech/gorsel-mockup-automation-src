"""EPIC-3 geometry accuracy diagnostics.

This script does NOT change production selection behavior. It uses the real golden
benchmark dataset to answer one question:

    Is low IoU caused primarily by candidate generation, or by scoring/selection?

For each sample it evaluates the same bounded candidate set that current
TemplateAnalyzer can actually select (including production de-duplication and
the 180-candidate runtime pre-rank), then compares the oracle-best runtime
candidate with the candidate selected by TemplateAnalyzer.
"""

import argparse
import json
import os
import sys
from collections import Counter
from typing import Dict, List, Tuple

import cv2
import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "SABLON_V2_MIMARI"))
sys.path.insert(0, BASE_DIR)

from core.template_intelligence import CandidateGenerators, GeometryValidator, TemplateAnalyzer
from scripts.benchmark import CATEGORIES, calculate_iou, validate_gt_quad

IOU_TARGET = 0.50


def _canonical_candidate(candidate, w: int, h: int):
    try:
        arr = np.asarray(candidate, dtype=np.float32)
    except (TypeError, ValueError):
        return None
    if arr.shape != (4, 2) or not np.isfinite(arr).all():
        return None
    valid, _ = GeometryValidator.is_valid_quad(arr, w, h)
    if not valid:
        return None
    return GeometryValidator.canonical_sort(arr).astype(float).tolist()


def collect_candidates(image: np.ndarray) -> List[Dict]:
    """Return de-duplicated valid candidates with generator provenance."""
    h, w = image.shape[:2]
    generators = (
        ("canny", CandidateGenerators.generate_canny_contours),
        ("hough", CandidateGenerators.generate_hough_lines_quad),
        ("color_region", CandidateGenerators.generate_color_region_quad),
    )

    by_key: Dict[Tuple, Dict] = {}
    for source, generator in generators:
        try:
            raw_candidates = generator(image) or []
        except Exception as exc:
            raw_candidates = []
            # Generator exceptions are evidence too, but they must not abort the
            # whole diagnostic run. The source-level error is carried below.
            error = str(exc)
        else:
            error = None

        if error is not None:
            key = ("__error__", source, error)
            by_key[key] = {
                "quad": None,
                "sources": [source],
                "generator_error": error,
            }
            continue

        for raw in raw_candidates:
            canonical = _canonical_candidate(raw, w, h)
            if canonical is None:
                continue
            key = tuple(
                int(round(float(value)))
                for point in canonical
                for value in point
            )
            if key not in by_key:
                by_key[key] = {
                    "quad": canonical,
                    "sources": [source],
                    "generator_error": None,
                }
            elif source not in by_key[key]["sources"]:
                by_key[key]["sources"].append(source)

    return list(by_key.values())


def prepare_runtime_candidates(
    analyzer: TemplateAnalyzer,
    image: np.ndarray,
    candidates: List[Dict],
    max_candidates: int = 180,
) -> List[Dict]:
    """Mirror TemplateAnalyzer's runtime pre-rank/candidate cap exactly."""
    prepared = [item for item in candidates if item.get("quad") is not None]
    if len(prepared) <= max_candidates:
        return prepared

    h, w = image.shape[:2]
    ranked = []
    for item in prepared:
        quad = np.asarray(item["quad"], dtype=np.float32)
        area = float(abs(cv2.contourArea(quad)))
        area_ratio = min(1.0, area / float(w * h))
        line_score = analyzer.measure_edge_contrast(image, quad)
        pre_score = (
            analyzer.score_area_plausibility(area_ratio) * 0.35
            + line_score * 0.65
        )
        ranked.append((float(pre_score), item))

    ranked.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in ranked[:max_candidates]]


def classify_sample(candidate_count: int, selected_iou: float, oracle_iou: float) -> str:
    if candidate_count == 0:
        return "NO_VALID_CANDIDATE"
    if selected_iou >= IOU_TARGET:
        return "GOOD_SELECTED"
    if oracle_iou >= IOU_TARGET:
        return "SCORER_LIMITED"
    return "GENERATOR_LIMITED"


def _summarize(records: List[Dict]) -> Dict:
    if not records:
        return {
            "valid_evaluated": 0,
            "selected_median_iou": 0.0,
            "oracle_median_iou": 0.0,
            "selected_recall_at_50": 0.0,
            "oracle_recall_at_50": 0.0,
            "median_selection_gap": 0.0,
            "classification_counts": {},
            "oracle_generator_wins": {},
        }

    selected_ious = [float(r["selected_iou"]) for r in records]
    oracle_ious = [float(r["oracle_iou"]) for r in records]
    gaps = [float(r["selection_gap"]) for r in records]

    classes = Counter(r["classification"] for r in records)
    winners = Counter()
    for record in records:
        for source in record.get("oracle_sources", []):
            winners[source] += 1

    total = len(records)
    return {
        "valid_evaluated": total,
        "selected_median_iou": float(np.median(selected_ious)),
        "oracle_median_iou": float(np.median(oracle_ious)),
        "selected_recall_at_50": float(sum(v >= IOU_TARGET for v in selected_ious) / total),
        "oracle_recall_at_50": float(sum(v >= IOU_TARGET for v in oracle_ious) / total),
        "median_selection_gap": float(np.median(gaps)),
        "classification_counts": dict(classes),
        "oracle_generator_wins": dict(winners),
    }


def diagnose_dataset(dataset_path: str, output_json: str) -> Dict:
    gt_path = os.path.join(dataset_path, "ground_truth.json")
    if not os.path.exists(gt_path):
        raise ValueError("ground_truth.json missing")

    with open(gt_path, "r", encoding="utf-8") as handle:
        dataset = json.load(handle)
    if not isinstance(dataset, dict):
        raise ValueError("ground_truth.json must be an object")

    analyzer = TemplateAnalyzer()
    result = {
        "iou_target": IOU_TARGET,
        "attempted_total": 0,
        "valid_evaluated": 0,
        "excluded_count": 0,
        "exclusions": [],
        "categories": {},
        "records": [],
    }

    for category in CATEGORIES:
        sample_names = [
            name
            for name, metadata in dataset.items()
            if isinstance(metadata, dict) and metadata.get("category") == category
        ]
        if not sample_names:
            raise ValueError(f"Missing samples for required category {category}")

        category_records = []
        category_excluded = 0

        for sample_name in sample_names:
            result["attempted_total"] += 1
            sample_path = os.path.join(dataset_path, sample_name)
            image = cv2.imread(sample_path)
            if image is None:
                raise ValueError(f"Unreadable or missing image: {sample_path}")
            h, w = image.shape[:2]

            gt_valid, gt_reason, gt_quad = validate_gt_quad(
                dataset[sample_name].get("quad"), w, h
            )
            if not gt_valid:
                category_excluded += 1
                result["excluded_count"] += 1
                result["exclusions"].append(
                    {
                        "sample": sample_name,
                        "category": category,
                        "reason": gt_reason,
                    }
                )
                continue

            candidates = collect_candidates(image)
            valid_candidates = [
                candidate
                for candidate in candidates
                if candidate.get("quad") is not None
            ]
            runtime_candidates = prepare_runtime_candidates(
                analyzer,
                image,
                valid_candidates,
            )

            evaluated_candidates = []
            for candidate in runtime_candidates:
                iou = calculate_iou(candidate["quad"], gt_quad, w, h)
                evaluated_candidates.append(
                    {
                        "quad": candidate["quad"],
                        "sources": candidate["sources"],
                        "iou": float(iou),
                    }
                )

            if evaluated_candidates:
                oracle = max(evaluated_candidates, key=lambda item: item["iou"])
                oracle_iou = float(oracle["iou"])
                oracle_sources = list(oracle["sources"])
                oracle_quad = oracle["quad"]
            else:
                oracle_iou = 0.0
                oracle_sources = []
                oracle_quad = None

            selected_quad = None
            selected_confidence = 0.0
            analyzer_error = None
            try:
                analysis = analyzer.analyze(sample_path, category)
                selected_quad = analysis.get("surface_quad")
                selected_confidence = float(analysis.get("confidence_total", 0.0) or 0.0)
            except Exception as exc:
                analyzer_error = str(exc)

            selected_iou = calculate_iou(selected_quad, gt_quad, w, h)
            candidate_count = len(evaluated_candidates)
            classification = classify_sample(candidate_count, selected_iou, oracle_iou)

            record = {
                "sample": sample_name,
                "category": category,
                "candidate_count_raw": len(valid_candidates),
                "candidate_count_runtime": candidate_count,
                "candidate_count": candidate_count,
                "selected_iou": float(selected_iou),
                "oracle_iou": float(oracle_iou),
                "selection_gap": float(max(0.0, oracle_iou - selected_iou)),
                "selected_confidence": selected_confidence,
                "classification": classification,
                "oracle_sources": oracle_sources,
                "selected_quad": selected_quad,
                "oracle_quad": oracle_quad,
                "analyzer_error": analyzer_error,
            }
            result["records"].append(record)
            category_records.append(record)
            result["valid_evaluated"] += 1

        summary = _summarize(category_records)
        summary.update(
            {
                "attempted": len(sample_names),
                "excluded": category_excluded,
            }
        )
        result["categories"][category] = summary

    result["global"] = _summarize(result["records"])

    with open(output_json, "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, ensure_ascii=False)

    print(
        "Geometry diagnostics finished: "
        f"{result['attempted_total']} attempted, "
        f"{result['valid_evaluated']} valid, "
        f"{result['excluded_count']} excluded."
    )
    print(
        "Selected median IoU="
        f"{result['global']['selected_median_iou']:.3f}; "
        "oracle median IoU="
        f"{result['global']['oracle_median_iou']:.3f}"
    )
    print(f"Diagnostics saved to {output_json}")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    diagnose_dataset(args.dataset, args.output)
