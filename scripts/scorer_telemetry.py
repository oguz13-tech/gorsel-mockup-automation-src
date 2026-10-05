"""EPIC-3 scorer telemetry for real golden data.

Diagnostic-only tool. It never changes production code and never writes into the
source dataset. Ground truth is used only to label selected/oracle candidates
offline; the runtime scorer itself remains GT-free.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
ARCH = ROOT / "SABLON_V2_MIMARI"
sys.path.insert(0, str(ARCH))
sys.path.insert(0, str(ROOT))

from core.template_intelligence import (
    CategoryRuleEngine,
    TemplateAnalyzer,
)
from scripts.geometry_diagnostics import (
    collect_candidates,
    prepare_runtime_candidates,
)
from scripts.benchmark import calculate_iou, validate_gt_quad

SCORER_CATEGORIES = (
    "02_Cam_Tablo_Dikey",
    "02_Cam_Tablo_Yatay",
    "03_Ahsap_Tablo",
    "05_Ocak_Arkasi",
)


def _orientation_score(quad: np.ndarray, category: str) -> float:
    rule = CategoryRuleEngine.get_rule_by_folder(category)
    top = float(np.linalg.norm(quad[1] - quad[0]))
    bottom = float(np.linalg.norm(quad[2] - quad[3]))
    left = float(np.linalg.norm(quad[3] - quad[0]))
    right = float(np.linalg.norm(quad[2] - quad[1]))
    avg_w = (top + bottom) * 0.5
    avg_h = (left + right) * 0.5
    if avg_w <= 0 or avg_h <= 0:
        return 0.5
    ratio = avg_w / avg_h
    orientation = "H" if ratio > 1.05 else ("V" if ratio < 0.95 else "SQUARE")
    expected = rule.get("expected_orientation", "ANY")
    if expected == "ANY":
        return 1.0
    return 1.0 if orientation == expected else 0.0


def _components(
    analyzer: TemplateAnalyzer,
    image: np.ndarray,
    candidates: List[Dict],
    index: int,
    category: str,
):
    h, w = image.shape[:2]
    quad = np.asarray(candidates[index]["quad"], dtype=np.float32)
    stack = np.stack([item["quad"] for item in candidates]).astype(np.float32)
    diffs = stack - quad
    distances = (
        np.sqrt(np.sum(diffs * diffs, axis=(1, 2))) / max(float(w), 1.0)
    )
    agreement_count = int(np.count_nonzero(distances < 0.05))

    # Production TemplateAnalyzer uses a local-consensus signal saturated at
    # four votes (singleton=.25, pair=.50, three=.75, four+=1.0). Using
    # agreement_count / len(candidates) here previously made telemetry diverge
    # from the real scorer as multi-scale recall grew.
    agreement = min(1.0, agreement_count / 4.0)

    area = float(abs(cv2.contourArea(quad.astype(np.float32))))
    area_ratio = min(1.0, area / float(w * h))
    line_score = analyzer.measure_edge_contrast(image, quad)
    orientation_score = _orientation_score(quad, category)

    current_conf, current_components = analyzer.score_candidate(
        area_ratio=area_ratio,
        line_score=line_score,
        candidate_agreement=agreement,
        orientation_score=orientation_score,
    )

    legacy_conf = (
        area_ratio * 0.30
        + line_score * 0.40
        + agreement * 0.20
        + orientation_score * 0.10
    )

    return {
        "area_ratio": float(area_ratio),
        "line_score": float(line_score),
        "candidate_agreement": float(agreement),
        "orientation_score": float(orientation_score),
        "legacy_confidence": float(legacy_conf),
        "current_confidence": float(current_conf),
        "current_components": current_components,
        "sources": candidates[index]["sources"],
    }


def _median_component(records: List[Dict], key: str) -> float:
    vals = [float(row[key]) for row in records if row.get(key) is not None]
    return float(np.median(vals)) if vals else 0.0


def run(dataset: Path, diagnostic_json: Path, output: Path, top_n: int) -> Dict:
    gt_path = dataset / "ground_truth.json"
    if not gt_path.is_file():
        raise ValueError(f"ground_truth.json missing: {gt_path}")
    if not diagnostic_json.is_file():
        raise ValueError(f"diagnostic JSON missing: {diagnostic_json}")

    gt = json.loads(gt_path.read_text(encoding="utf-8"))
    diagnostic = json.loads(diagnostic_json.read_text(encoding="utf-8"))
    candidate_records = [
        row
        for row in diagnostic.get("records", [])
        if row.get("category") in SCORER_CATEGORIES
        and float(row.get("selection_gap", 0.0)) > 0
    ]
    candidate_records.sort(
        key=lambda row: float(row.get("selection_gap", 0.0)),
        reverse=True,
    )
    candidate_records = candidate_records[: max(1, int(top_n))]

    analyzer = TemplateAnalyzer()
    rows = []

    for diagnostic_row in candidate_records:
        name = diagnostic_row["sample"]
        category = diagnostic_row["category"]
        image_path = dataset / name
        image = cv2.imread(str(image_path))
        if image is None:
            raise ValueError(f"Unreadable sample: {image_path}")
        h, w = image.shape[:2]

        gt_ok, gt_reason, gt_quad = validate_gt_quad(
            gt[name].get("quad"), w, h
        )
        if not gt_ok:
            continue

        raw_candidates = [
            item
            for item in collect_candidates(image)
            if item.get("quad") is not None
        ]
        if not raw_candidates:
            continue

        candidates = prepare_runtime_candidates(
            analyzer,
            image,
            raw_candidates,
        )
        if not candidates:
            continue

        evaluated = []
        for idx, item in enumerate(candidates):
            iou = calculate_iou(item["quad"], gt_quad, w, h)
            comp = _components(analyzer, image, candidates, idx, category)
            evaluated.append({"index": idx, "iou": float(iou), **comp})

        oracle = max(evaluated, key=lambda item: item["iou"])
        legacy_selected = max(evaluated, key=lambda item: item["legacy_confidence"])
        current_selected = max(evaluated, key=lambda item: item["current_confidence"])

        rows.append(
            {
                "sample": name,
                "category": category,
                "candidate_count_raw": len(raw_candidates),
                "candidate_count_runtime": len(evaluated),
                "oracle": oracle,
                "legacy_selected": legacy_selected,
                "current_selected": current_selected,
                "legacy_gap": float(oracle["iou"] - legacy_selected["iou"]),
                "current_gap": float(oracle["iou"] - current_selected["iou"]),
            }
        )

    by_category = defaultdict(list)
    for row in rows:
        by_category[row["category"]].append(row)

    category_summary = {}
    for category, group in by_category.items():
        legacy = [row["legacy_selected"] for row in group]
        current = [row["current_selected"] for row in group]
        oracle = [row["oracle"] for row in group]
        category_summary[category] = {
            "sample_count": len(group),
            "legacy_selected_median_iou": float(
                np.median([r["iou"] for r in legacy])
            ),
            "current_selected_median_iou": float(
                np.median([r["iou"] for r in current])
            ),
            "oracle_median_iou": float(np.median([r["iou"] for r in oracle])),
            "legacy_median_gap": float(
                np.median([row["legacy_gap"] for row in group])
            ),
            "current_median_gap": float(
                np.median([row["current_gap"] for row in group])
            ),
            "legacy_selected_medians": {
                key: _median_component(legacy, key)
                for key in (
                    "area_ratio",
                    "line_score",
                    "candidate_agreement",
                    "orientation_score",
                    "legacy_confidence",
                )
            },
            "current_selected_medians": {
                key: _median_component(current, key)
                for key in (
                    "area_ratio",
                    "line_score",
                    "candidate_agreement",
                    "orientation_score",
                    "current_confidence",
                )
            },
            "oracle_medians": {
                key: _median_component(oracle, key)
                for key in (
                    "area_ratio",
                    "line_score",
                    "candidate_agreement",
                    "orientation_score",
                    "current_confidence",
                )
            },
            "oracle_sources": dict(
                Counter(
                    source
                    for record in oracle
                    for source in record.get("sources", [])
                )
            ),
        }

    result = {
        "top_n_requested": int(top_n),
        "sample_count": len(rows),
        "categories": category_summary,
        "records": rows,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Scorer telemetry finished: {len(rows)} samples")
    print(f"Saved: {output}")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--diag-json", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--top-n", type=int, default=40)
    args = parser.parse_args()
    run(
        args.dataset.resolve(),
        args.diag_json.resolve(),
        args.output.resolve(),
        args.top_n,
    )


if __name__ == "__main__":
    main()
