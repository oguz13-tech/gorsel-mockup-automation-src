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
OUT = LAB / "phase3" / "image_guided_review"


def source_files():
    roots = [GEOMETRY / "source" / "TEST SABLONLARI", GEOMETRY / "source" / "PETEK"]
    return {
        f"{('06_PETEK' if root == GEOMETRY / 'source' / 'PETEK' else p.relative_to(GEOMETRY / 'source' / 'TEST SABLONLARI').parts[0])}/{p.name}": p
        for root in roots
        for p in root.rglob("*")
        if p.suffix.lower() in {".png", ".jpg", ".jpeg"}
    }


def draw_boxes(image, detections, color, label):
    for detection in detections[:3]:
        box = detection.get("box")
        if not box:
            continue
        x1, y1, x2, y2 = [int(round(value)) for value in box]
        cv2.rectangle(image, (x1, y1), (x2, y2), color, 4)
        cv2.putText(
            image, f"{label} {detection.get('score', 0):.2f}",
            (x1, max(24, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2,
        )


def main():
    data = json.loads((REPORTS / "PHASE3_IMAGE_GUIDED_OWLV2.json").read_text(encoding="utf-8"))
    sources = source_files()
    grouped = {}
    for row in data["rows"]:
        grouped.setdefault(row["category"], []).append(row)
    selected = []
    for category, rows in sorted(grouped.items()):
        selected.extend(sorted(rows, key=lambda row: row["target_image_id"])[:6])
    OUT.mkdir(parents=True, exist_ok=True)
    cards = []
    for row in selected:
        source = sources.get(row["target_image_id"])
        if source is None:
            continue
        image = cv2.imread(str(source))
        if image is None:
            continue
        reference_item = row["per_reference"][0] if row["per_reference"] else {}
        reference = cv2.imread(str(LAB / "phase3" / "reference_crops" /
                                   f"{reference_item.get('reference_sha256', '')[:16]}.jpg"))
        if reference is None:
            reference = np.zeros_like(image)
        target = image.copy()
        detections = row["per_reference"][0]["detections"] if row["per_reference"] else []
        draw_boxes(target, detections, (0, 165, 255), "IMAGE_GUIDED")
        height = max(image.shape[0], reference.shape[0], target.shape[0])
        width = image.shape[1] + reference.shape[1] + target.shape[1]
        canvas = np.zeros((height, width, 3), dtype=np.uint8)
        x = 0
        for panel in (image, reference, target):
            canvas[:panel.shape[0], x:x + panel.shape[1]] = panel
            x += panel.shape[1]
        filename = hashlib.sha1(
            f"{row['category']}|{row['target_image_id']}|{row['reference_count']}".encode()
        ).hexdigest()[:12] + ".jpg"
        cv2.imwrite(str(OUT / filename), canvas, [cv2.IMWRITE_JPEG_QUALITY, 72])
        cards.append(
            f"<article data-category='{html.escape(row['category'])}'><h3>{html.escape(row['target_image_id'])}</h3>"
            f"<img src='{filename}'><p>Panels: target | reference crop | image-guided overlay. "
            f"refs={row['reference_count']}; GT=UNKNOWN_GT; REVIEW_REQUIRED.</p></article>"
        )
    categories = sorted(grouped)
    buttons = "<button onclick=\"filterCards('all')\">All</button>" + "".join(
        f"<button onclick=\"filterCards('{html.escape(category)}')\">{html.escape(category)}</button>"
        for category in categories
    )
    (OUT / "INDEX.html").write_text(
        "<!doctype html><meta charset='utf-8'><title>Image-guided review</title>"
        "<style>body{font:14px sans-serif;background:#eee}article{display:inline-block;vertical-align:top;"
        "width:47%;background:#fff;margin:7px;padding:8px;box-sizing:border-box}img{width:100%;"
        "max-height:520px;object-fit:contain}button{margin:4px;padding:6px}</style>"
        "<h1>Issue #55 — OWLv2 image-guided review</h1>"
        "<p>Target | reference crop | image-guided overlay. No approval or accuracy claim.</p>"
        + buttons + "".join(cards)
        + "<script>function filterCards(v){document.querySelectorAll('article').forEach(a=>"
        "a.style.display=v==='all'||a.dataset.category===v?'inline-block':'none')}</script>",
        encoding="utf-8",
    )
    print(json.dumps({"cards": len(cards), "categories": len(grouped)}))


if __name__ == "__main__":
    main()
