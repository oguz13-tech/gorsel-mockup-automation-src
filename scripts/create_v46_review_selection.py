"""Select local review cards without publishing private images."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAB_RESULTS = Path(r"C:\AI_WORK\GORSEL_REFERENCE_LAB_20261024\phase3\PHASE3_RESULTS.json")
OUT = ROOT / "artifacts" / "v46" / "REVIEW_SELECTION_LOCAL.json"

GLASS = {"02_Cam_Tablo_Dikey", "02_Cam_Tablo_Yatay", "04_Cam_Dograma", "05_Ocak_Arkasi"}


def main() -> None:
    rows = json.loads(LAB_RESULTS.read_text(encoding="utf-8"))["rows"]
    by_category = {}
    for row in rows:
        by_category.setdefault(row["category"], []).append(row)
    glass = []
    for category in sorted(GLASS):
        glass.extend(by_category[category][:5])
    selected = []
    for category in sorted(by_category):
        selected.extend(by_category[category][:4])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "publication": "LOCAL_ONLY_PRIVATE_IMAGES_NOT_UPLOADED",
        "glass_review_cards": [
            {"image_id": row["image_id"], "overlay": row["overlay"],
             "qa_status": row["qa_status"]}
            for row in glass
        ],
        "seven_category_review_cards": [
            {"image_id": row["image_id"], "overlay": row["overlay"],
             "qa_status": row["qa_status"]}
            for row in selected
        ],
        "counts": {"glass": len(glass), "seven_category": len(selected)},
        "review_labels": ["GOOD_CANDIDATE", "WRONG", "SUSPECT", "UNREVIEWED"],
        "note": "Cards are unreviewed local candidates; no visual quality claim is made.",
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"glass": len(glass), "seven_category": len(selected)}))


if __name__ == "__main__":
    main()
