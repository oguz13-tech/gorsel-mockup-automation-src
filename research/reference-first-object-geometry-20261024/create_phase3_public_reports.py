from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path


LAB = Path(__file__).resolve().parent
REPORTS = LAB / "reports"


def main():
    experiment = json.loads(
        (REPORTS / "PHASE3_AB_EXPERIMENT.json").read_text(encoding="utf-8")
    )
    rows = experiment["rows"]
    categories = Counter(row["category"] for row in rows)
    variants = defaultdict(lambda: {"tested_images": 0, "evidence": "candidate_only"})
    for row in rows:
        variants[row["category"]]["tested_images"] += 1
    (REPORTS / "REFERENCE_VARIANTS_AGGREGATE.json").write_text(
        json.dumps(
            {
                "ground_truth": "UNKNOWN_GT",
                "variant_policy": "No category was forced into ten groups.",
                "categories": dict(sorted(variants.items())),
                "decision": "Physical variant counts remain UNKNOWN_GT without approved source-SHA identity.",
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    (REPORTS / "PHASE3_MODEL_CATALOG.json").write_text(
        json.dumps(
            {
                "models": [
                    {
                        "name": "OWLv2",
                        "architecture": "open-vocabulary detector",
                        "checkpoint": "google/owlv2-base-patch16-ensemble",
                        "tested_images": 170,
                        "status": "LOCAL_INFERENCE_COMPLETED",
                        "role": "candidate_bbox_only",
                    },
                    {
                        "name": "Grounding DINO",
                        "architecture": "open-vocabulary detector",
                        "checkpoint": "IDEA-Research/grounding-dino-base",
                        "tested_images": 170,
                        "status": "LOCAL_INFERENCE_COMPLETED",
                        "role": "candidate_bbox_only",
                    },
                    {
                        "name": "SAM2.1 Hiera Small",
                        "architecture": "prompted segmentation",
                        "checkpoint": "facebook/sam2.1-hiera-small",
                        "tested_images": 170,
                        "status": "LOCAL_INFERENCE_COMPLETED",
                        "role": "center_prompt_mask_draft_only",
                    },
                    {
                        "name": "Florence-2",
                        "architecture": "vision-language grounding",
                        "checkpoint": "microsoft/Florence-2-base",
                        "tested_images": 0,
                        "status": "BLOCKED_TRANSFORMERS_COMPATIBILITY",
                        "role": "not counted as evidence",
                    },
                    {
                        "name": "ResNet18",
                        "architecture": "ImageNet embedding classifier",
                        "checkpoint": "torchvision ResNet18 weights",
                        "tested_images": 170,
                        "status": "LOCAL_INFERENCE_COMPLETED",
                        "role": "reference_similarity_only",
                    },
                ]
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    matrix = {
        "tested_images": len(rows),
        "categories": dict(sorted(categories.items())),
        "ground_truth_rows": 0,
        "metrics": {
            "precision": None,
            "recall": None,
            "mask_iou": None,
            "corner_error_px": None,
            "wrong_object_rate": None,
            "review_required_rate": 1.0,
        },
        "privacy": {
            "public_full_dataset": False,
            "public_model_cache": False,
            "public_sqlite_or_customer_data": False,
            "selected_cards_local_only_until_explicit_delivery": True,
        },
        "status": "PARTIAL_BLOCKED",
    }
    (REPORTS / "PHASE3_VALIDATION_MATRIX.json").write_text(
        json.dumps(matrix, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (REPORTS / "PHASE3_SUMMARY.md").write_text(
        "# Issue #55 Phase 3 summary\n\n"
        f"- Existing evidence evaluated: **{len(rows)}/170** images.\n"
        f"- Categories: {', '.join(f'{name}={count}' for name, count in sorted(categories.items()))}.\n"
        "- Methods compared: registration-only, detector-only, detector plus center-prompt mask draft.\n"
        "- Ground truth: `UNKNOWN_GT`; no precision, recall, IoU, corner accuracy, or wrong-object rate is claimed.\n"
        "- OWLv2, Grounding DINO, and SAM2.1 had recorded local inference for 170/170; their outputs remain draft candidates.\n"
        "- Florence-2 was not counted because the recorded Transformers compatibility error blocked inference.\n"
        "- Selected review evidence: 20 glass cards and 28 category cards in `phase3/visual_review/INDEX.html`.\n"
        "- Release decision: **NO-GO / REVIEW_REQUIRED**.\n",
        encoding="utf-8",
    )
    print(json.dumps({"reports": 4, "images": len(rows)}))


if __name__ == "__main__":
    main()
