from __future__ import annotations

import hashlib
import json
import os
from collections import Counter, defaultdict
from pathlib import Path

import cv2
import numpy as np


LAB = Path(__file__).resolve().parent
GEOMETRY = Path(os.environ.get("PHASE3_GEOMETRY_ROOT", LAB.parent / "GORSEL_GEOMETRY_LAB_20261024"))
REPORTS = LAB / "reports"
PHASE3 = LAB / "phase3"
OUT = REPORTS / "PHASE3_AB_EXPERIMENT.json"


def source_files():
    roots = [
        GEOMETRY / "source" / "TEST SABLONLARI",
        GEOMETRY / "source" / "PETEK",
    ]
    return sorted(
        p for root in roots for p in root.rglob("*")
        if p.suffix.lower() in {".png", ".jpg", ".jpeg"}
    )


def category(path: Path) -> str:
    if path.is_relative_to(GEOMETRY / "source" / "PETEK"):
        return "06_PETEK"
    return path.relative_to(GEOMETRY / "source" / "TEST SABLONLARI").parts[0]


def image_id(path: Path) -> str:
    return f"{category(path)}/{path.name}"


def clamp_box(box, width, height):
    if not isinstance(box, list) or len(box) != 4:
        return None
    x1, y1, x2, y2 = [float(value) for value in box]
    x1, x2 = sorted((max(0.0, min(width, x1)), max(0.0, min(width, x2))))
    y1, y2 = sorted((max(0.0, min(height, y1)), max(0.0, min(height, y2))))
    if x2 - x1 < 2 or y2 - y1 < 2:
        return None
    return [x1, y1, x2, y2]


def area(box):
    if not box:
        return 0.0
    return max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1])


def iou(left, right):
    if not left or not right:
        return 0.0
    intersection = [
        max(left[0], right[0]),
        max(left[1], right[1]),
        min(left[2], right[2]),
        min(left[3], right[3]),
    ]
    overlap = area(intersection)
    return overlap / max(1.0, area(left) + area(right) - overlap)


def load_rows(filename, key="image_id"):
    data = json.loads((REPORTS / filename).read_text(encoding="utf-8"))
    return {row[key]: row for row in data["rows"]}


def detector_score(row, name):
    detections = row.get(name, {}).get("detections", [])
    if not detections:
        return None
    return max(detections, key=lambda item: float(item.get("score", 0.0)))


def evaluate(path, detection, match, mask):
    image = cv2.imread(str(path))
    if image is None:
        raise RuntimeError(f"Cannot read local fixture: {path}")
    height, width = image.shape[:2]
    owl = detector_score(detection, "owlv2")
    dino = detector_score(detection, "grounding_dino")
    owl_box = clamp_box(owl.get("box") if owl else None, width, height)
    dino_box = clamp_box(dino.get("box") if dino else None, width, height)
    consensus = iou(owl_box, dino_box)
    mask_area_fraction = float(mask.get("mask_area_fraction", 0.0)) if mask else None
    ref_candidate = match.get("lineage_type", "UNKNOWN") if match else "UNKNOWN"
    reg_status = "REVIEW_REQUIRED_REFERENCE_UNVERIFIED"
    if ref_candidate == "T3":
        reg_status = "ABSTAIN_NO_TRANSFER_EVIDENCE"
    elif ref_candidate == "T2":
        reg_status = "ABSTAIN_CLASS_ONLY"
    detection_status = "REVIEW_REQUIRED_NO_DETECTOR_CONSENSUS"
    if owl_box and dino_box and consensus >= 0.20:
        detection_status = "DRAFT_CONSENSUS_BBOX"
    elif owl_box or dino_box:
        detection_status = "DRAFT_SINGLE_DETECTOR_BBOX"
    mask_status = "REVIEW_REQUIRED_CENTER_PROMPT"
    if mask_area_fraction is not None and 0.01 <= mask_area_fraction <= 0.60:
        mask_status = "DRAFT_MASK_PLAUSIBLE_AREA_ONLY"
    return {
        "image_id": image_id(path),
        "category": category(path),
        "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "methods": {
            "registration_only": {
                "lineage": ref_candidate,
                "status": reg_status,
                "inliers": match.get("match", {}).get("inliers") if match else None,
                "reprojection_px": match.get("match", {}).get("reprojection_px") if match else None,
            },
            "detection_only": {
                "owlv2_score": owl.get("score") if owl else None,
                "grounding_dino_score": dino.get("score") if dino else None,
                "owlv2_box": owl_box,
                "grounding_dino_box": dino_box,
                "bbox_iou_between_detectors": round(consensus, 6),
                "status": detection_status,
            },
            "detection_mask_draft": {
                "center_prompt_mask_area_fraction": mask_area_fraction,
                "status": mask_status,
            },
        },
        "ground_truth": "UNKNOWN_GT",
        "production_decision": "REVIEW_REQUIRED",
    }


def choose_representatives(rows, count=3):
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["category"]].append(row)
    selected = []
    for name, items in sorted(grouped.items()):
        ranked = sorted(
            items,
            key=lambda row: (
                row["methods"]["detection_only"]["bbox_iou_between_detectors"],
                -(row["methods"]["registration_only"]["inliers"] or 0),
            ),
        )
        indexes = sorted({0, len(ranked) // 2, len(ranked) - 1})
        selected.extend(ranked[index] for index in indexes[:count])
    return selected


def choose_review_sets(rows):
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["category"]].append(row)
    glass = {
        "02_Cam_Tablo_Dikey",
        "02_Cam_Tablo_Yatay",
        "04_Cam_Dograma",
        "05_Ocak_Arkasi",
    }
    glass_rows = []
    all_rows = []
    for name, items in sorted(grouped.items()):
        ranked = sorted(
            items,
            key=lambda row: (
                row["methods"]["detection_only"]["bbox_iou_between_detectors"],
                -(row["methods"]["registration_only"]["inliers"] or 0),
            ),
        )
        indexes = np.linspace(0, len(ranked) - 1, 4, dtype=int).tolist()
        chosen = [ranked[index] for index in indexes]
        all_rows.extend(chosen)
        if name in glass:
            glass_indexes = np.linspace(0, len(ranked) - 1, 5, dtype=int).tolist()
            glass_rows.extend(ranked[index] for index in glass_indexes)
    return glass_rows, all_rows


def main():
    detections = load_rows("PHASE2_DETECTION_RESULTS.json")
    matches = load_rows("MATCH_RESULTS.json")
    masks = load_rows("PHASE3_SAM2_RESULTS.json")
    rows = []
    for path in source_files():
        key = image_id(path)
        rows.append(evaluate(path, detections.get(key, {}), matches.get(key, {}), masks.get(key)))
    representatives = choose_representatives(rows)
    glass_review, category_review = choose_review_sets(rows)
    summary = {
        "tested_images": len(rows),
        "category_counts": dict(sorted(Counter(row["category"] for row in rows).items())),
        "representative_count": len(representatives),
        "glass_review_count": len(glass_review),
        "category_review_count": len(category_review),
        "ground_truth": "UNKNOWN_GT",
        "accuracy_claim": None,
        "method_status": {
            "registration_only": "candidate_evidence_only",
            "detection_only": "candidate_bbox_evidence_only",
            "detection_mask_draft": "center_prompt_mask_not_product_segmentation",
        },
        "decision": "NO_GO_REVIEW_REQUIRED",
    }
    OUT.write_text(
        json.dumps(
            {
                "summary": summary,
                "rows": rows,
                "representatives": representatives,
                "glass_review": glass_review,
                "category_review": category_review,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
