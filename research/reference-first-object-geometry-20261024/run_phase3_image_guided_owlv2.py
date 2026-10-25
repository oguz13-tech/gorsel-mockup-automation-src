from __future__ import annotations

import hashlib
import json
import os
import time
from collections import defaultdict
from pathlib import Path

import torch
from PIL import Image
from transformers import Owlv2ForObjectDetection, Owlv2Processor
from transformers.models.owlv2.modeling_owlv2 import Owlv2ImageGuidedObjectDetectionOutput


LAB = Path(__file__).resolve().parent
GEOMETRY = Path(os.environ.get("PHASE3_GEOMETRY_ROOT", LAB.parent / "GORSEL_GEOMETRY_LAB_20261024"))
REPORTS = LAB / "reports"
OUT = REPORTS / "PHASE3_IMAGE_GUIDED_OWLV2.json"
CROPS = LAB / "phase3" / "reference_crops"
MODEL_ID = "google/owlv2-base-patch16-ensemble"
CONFIGS = (1, 3, 5, 10)


def category(path: Path) -> str:
    if path.is_relative_to(GEOMETRY / "source" / "PETEK"):
        return "06_PETEK"
    return path.relative_to(GEOMETRY / "source" / "TEST SABLONLARI").parts[0]


def files():
    roots = [GEOMETRY / "source" / "TEST SABLONLARI", GEOMETRY / "source" / "PETEK"]
    return sorted(
        p for root in roots for p in root.rglob("*")
        if p.suffix.lower() in {".png", ".jpg", ".jpeg"}
    )


def image_id(path):
    return f"{category(path)}/{path.name}"


def load_matches():
    return {
        row["image_id"]: row
        for row in json.loads((REPORTS / "MATCH_RESULTS.json").read_text(encoding="utf-8"))["rows"]
    }


def crop_from_legacy(path, row):
    image = Image.open(path).convert("RGB")
    row = row or {}
    legacy = row.get("legacy_geometry") or {}
    corners = legacy.get("corners", [])
    if len(corners) != 4:
        return None
    xs = [int(point[0]) for point in corners]
    ys = [int(point[1]) for point in corners]
    left, right = max(0, min(xs)), min(image.width, max(xs))
    top, bottom = max(0, min(ys)), min(image.height, max(ys))
    if right - left < 16 or bottom - top < 16:
        return None
    pad_x = max(4, int((right - left) * 0.04))
    pad_y = max(4, int((bottom - top) * 0.04))
    return image.crop(
        (max(0, left - pad_x), max(0, top - pad_y),
         min(image.width, right + pad_x), min(image.height, bottom + pad_y))
    )


def prepare_references(paths, matches):
    CROPS.mkdir(parents=True, exist_ok=True)
    by_category = defaultdict(list)
    for path in paths:
        key = image_id(path)
        crop = crop_from_legacy(path, matches.get(key, {}))
        if crop is None:
            continue
        crop_id = hashlib.sha256(path.read_bytes()).hexdigest()
        crop_path = CROPS / f"{crop_id[:16]}.jpg"
        if not crop_path.exists():
            crop.save(crop_path, quality=88)
        by_category[category(path)].append({
            "image_id": key,
            "source_sha256": crop_id,
            "crop_path": str(crop_path),
        })
    return by_category


def load_checkpoint():
    if not OUT.exists():
        return []
    return json.loads(OUT.read_text(encoding="utf-8")).get("rows", [])


def save(rows, reference_library):
    OUT.write_text(json.dumps({
        "model_id": MODEL_ID,
        "model_api": "Owlv2ForObjectDetection.image_guided_detection",
        "query_input": "reference_product_crop",
        "reference_crop_source": "legacy geometry crop, unverified and review-only",
        "configs": list(CONFIGS),
        "reference_library": reference_library,
        "rows": rows,
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def cached_image_guided(model, target_map, query_map):
    batch_size, height, width, hidden = target_map.shape
    image_feats = target_map.reshape(batch_size, height * width, hidden)
    target_boxes = model.box_predictor(image_feats, target_map)
    query_batch, query_height, query_width, query_hidden = query_map.shape
    query_feats = query_map.reshape(
        query_batch, query_height * query_width, query_hidden
    )
    query_embeds, _, query_boxes = model.embed_image_query(query_feats, query_map)
    logits, class_embeds = model.class_predictor(
        image_feats=image_feats, query_embeds=query_embeds
    )
    return Owlv2ImageGuidedObjectDetectionOutput(
        image_embeds=target_map,
        query_image_embeds=query_map,
        target_pred_boxes=target_boxes,
        query_pred_boxes=query_boxes,
        logits=logits,
        class_embeds=class_embeds,
        text_model_output=None,
        vision_model_output=None,
    )


def main():
    paths = files()
    matches = load_matches()
    by_category = prepare_references(paths, matches)
    library = {
        name: [
            {"image_id": item["image_id"], "source_sha256": item["source_sha256"]}
            for item in items
        ]
        for name, items in sorted(by_category.items())
    }
    rows = load_checkpoint()
    done = {
        (row["category"], row["target_image_id"], row["reference_count"])
        for row in rows
    }
    processor = Owlv2Processor.from_pretrained(MODEL_ID)
    model = Owlv2ForObjectDetection.from_pretrained(MODEL_ID).eval()
    query_cache = {}
    with torch.inference_mode():
        for category_name, items in sorted(by_category.items()):
            targets = [
                path for path in paths
                if category(path) == category_name and len(items) >= 1
            ]
            for target in targets:
                target_id = image_id(target)
                references = [item for item in items if item["image_id"] != target_id]
                if not references:
                    continue
                for reference_count in CONFIGS:
                    if len(references) < reference_count:
                        continue
                    key = (category_name, target_id, reference_count)
                    if key in done:
                        continue
                    selected = references[:reference_count]
                    target_image = Image.open(target).convert("RGB")
                    started = time.perf_counter()
                    target_inputs = processor(images=target_image, return_tensors="pt")
                    target_map, _ = model.image_embedder(
                        pixel_values=target_inputs["pixel_values"]
                    )
                    per_reference = []
                    for ref in selected:
                        query_map = query_cache.get(ref["crop_path"])
                        if query_map is None:
                            ref_image = Image.open(ref["crop_path"]).convert("RGB")
                            query_inputs = processor(images=ref_image, return_tensors="pt")
                            query_map, _ = model.image_embedder(
                                pixel_values=query_inputs["pixel_values"]
                            )
                            query_cache[ref["crop_path"]] = query_map
                        outputs = cached_image_guided(model, target_map, query_map)
                        result = processor.post_process_image_guided_detection(
                        outputs,
                        threshold=0.05,
                        nms_threshold=0.3,
                        target_sizes=torch.tensor([target_image.size[::-1]]),
                        )[0]
                        detections = [
                            {
                                "score": round(float(score), 6),
                                "box": [round(float(value), 1) for value in box],
                            }
                            for score, box in zip(result["scores"], result["boxes"])
                        ][:10]
                        per_reference.append({
                            "reference_image_id": ref["image_id"],
                            "reference_sha256": ref["source_sha256"],
                            "detections": detections,
                        })
                    rows.append({
                        "category": category_name,
                        "target_image_id": target_id,
                        "target_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                        "reference_count": reference_count,
                        "reference_image_ids": [ref["image_id"] for ref in selected],
                        "inference_api": "image_guided_detection",
                        "elapsed_seconds": round(time.perf_counter() - started, 3),
                        "per_reference": per_reference,
                        "ground_truth": "UNKNOWN_GT",
                        "geometry_approval": "NOT_ALLOWED",
                        "decision": "REVIEW_REQUIRED",
                    })
                    save(rows, library)
                    print(json.dumps({
                        "category": category_name,
                        "target": target_id,
                        "references": reference_count,
                        "rows": len(rows),
                    }, ensure_ascii=False))
    save(rows, library)
    print(json.dumps({"rows": len(rows), "categories": len(by_category)}))


if __name__ == "__main__":
    main()
