from __future__ import annotations

import hashlib
import html
import json
import os
from pathlib import Path

import cv2
import numpy as np


LAB = Path(__file__).resolve().parent
GEOMETRY = Path(os.environ.get("PHASE3_GEOMETRY_ROOT", LAB.parent / "GORSEL_GEOMETRY_LAB_20261024"))
REPORTS = LAB / "reports"
OUT = LAB / "phase3" / "visual_review"
INDEX = OUT / "INDEX.html"


def source_files():
    roots = [
        GEOMETRY / "source" / "TEST SABLONLARI",
        GEOMETRY / "source" / "PETEK",
    ]
    return {
        f"{('06_PETEK' if root == GEOMETRY / 'source' / 'PETEK' else p.relative_to(GEOMETRY / 'source' / 'TEST SABLONLARI').parts[0])}/{p.name}": p
        for root in roots
        for p in root.rglob("*")
        if p.suffix.lower() in {".png", ".jpg", ".jpeg"}
    }


def draw_box(image, box, color, label):
    if not box:
        return
    x1, y1, x2, y2 = [int(round(value)) for value in box]
    cv2.rectangle(image, (x1, y1), (x2, y2), color, 5)
    cv2.putText(image, label, (x1, max(30, y1 - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)


def make_card(row, sources):
    path = sources[row["image_id"]]
    image = cv2.imread(str(path))
    if image is None:
        raise RuntimeError(path)
    scale = min(1.0, 1200.0 / max(image.shape[:2]))
    if scale < 1.0:
        image = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    overlay = image.copy()
    det = row["methods"]["detection_only"]
    def scaled(box):
        return [value * scale for value in box] if box else None
    draw_box(overlay, scaled(det["owlv2_box"]), (0, 165, 255), "OWL")
    draw_box(overlay, scaled(det["grounding_dino_box"]), (255, 80, 0), "DINO")
    mask = np.zeros_like(image)
    mask_path = LAB / "phase3" / "sam2" / (hashlib.sha1(row["image_id"].encode()).hexdigest()[:12] + ".png")
    if mask_path.exists():
        raw = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
        if raw is not None:
            raw = cv2.resize(raw, (image.shape[1], image.shape[0]))
            mask[raw > 0] = (0, 255, 0)
            overlay = cv2.addWeighted(overlay, 0.78, mask, 0.22, 0)
    height = max(image.shape[0], overlay.shape[0])
    width = image.shape[1] + overlay.shape[1]
    canvas = np.zeros((height, width, 3), dtype=np.uint8)
    canvas[:, : image.shape[1]] = image
    canvas[:, image.shape[1] :] = overlay
    filename = hashlib.sha1(row["image_id"].encode()).hexdigest()[:12] + ".jpg"
    cv2.imwrite(str(OUT / filename), canvas, [cv2.IMWRITE_JPEG_QUALITY, 72])
    return filename


def main():
    data = json.loads((REPORTS / "PHASE3_AB_EXPERIMENT.json").read_text(encoding="utf-8"))
    sources = source_files()
    OUT.mkdir(parents=True, exist_ok=True)
    cards = []
    selected = data["glass_review"] + data["category_review"]
    for row in selected:
        filename = make_card(row, sources)
        cards.append(
            f"<article data-category='{html.escape(row['category'])}'><h3>{html.escape(row['image_id'])}</h3>"
            f"<img src='{filename}'><p>Left: source; right: detector overlay. "
            f"OWL/DINO bbox IoU={row['methods']['detection_only']['bbox_iou_between_detectors']:.3f}; "
            f"GT=UNKNOWN_GT; decision=REVIEW_REQUIRED.</p></article>"
        )
    categories = sorted({row["category"] for row in selected})
    buttons = "<button onclick=\"filterCards('all')\">All</button>"
    buttons += "".join(
        f"<button onclick=\"filterCards('{html.escape(name)}')\">{html.escape(name)}</button>"
        for name in categories
    )
    INDEX.write_text(
        "<!doctype html><meta charset='utf-8'><title>Phase 3 visual review</title>"
        "<style>body{font:14px sans-serif;background:#eee}article{display:inline-block;vertical-align:top;"
        "width:47%;background:#fff;margin:7px;padding:8px;box-sizing:border-box}img{width:100%;"
        "max-height:560px;object-fit:contain}button{margin:4px;padding:6px}</style>"
        "<h1>Issue #55 Phase 3 — selected local review cards</h1>"
        "<p>Cards show source beside registered detector/mask draft overlays. "
        "No card is human-approved; UNKNOWN_GT is intentional.</p>"
        + buttons
        + "".join(cards)
        + "<script>function filterCards(v){document.querySelectorAll('article').forEach(a=>"
        "a.style.display=v==='all'||a.dataset.category===v?'inline-block':'none')}</script>",
        encoding="utf-8",
    )
    print(json.dumps({"cards": len(cards), "glass_cards": len(data["glass_review"]),
                      "category_cards": len(data["category_review"]), "index": str(INDEX)}))


if __name__ == "__main__":
    main()
