from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path


LAB = Path(__file__).resolve().parent
REPORTS = LAB / "reports"
INPUT = REPORTS / "PHASE3_IMAGE_GUIDED_OWLV2.json"
OUTPUT = REPORTS / "REFERENCE_GUIDED_DECISION_REPORT.md"


def main():
    data = json.loads(INPUT.read_text(encoding="utf-8"))
    rows = data["rows"]
    by_category = defaultdict(list)
    for row in rows:
        by_category[row["category"]].append(row)
    lines = [
        "# Reference-guided OWLv2 decision report",
        "",
        "## Scope",
        "",
        f"- Recorded rows: **{len(rows)}** across **{len(by_category)}** categories.",
        f"- Model/API: `{data['model_id']}` / `{data['model_api']}`.",
        f"- Query input: `{data['query_input']}`.",
        "- Reference crops are derived from legacy unverified geometry and are not approved ground truth.",
        "- Every row remains `UNKNOWN_GT`, `REVIEW_REQUIRED`, and `geometry_approval=NOT_ALLOWED`.",
        "",
        "## Coverage",
        "",
        "| Category | Rows | Targets | Reference counts |",
        "|---|---:|---:|---|",
    ]
    for category, category_rows in sorted(by_category.items()):
        counts = Counter(row["reference_count"] for row in category_rows)
        targets = len({row["target_image_id"] for row in category_rows})
        lines.append(
            f"| {category} | {len(category_rows)} | {targets} | "
            + ", ".join(f"{count}={value}" for count, value in sorted(counts.items()))
            + " |"
        )
    missing_categories = sorted({
        "01_Wifi_Kutusu",
        "02_Cam_Tablo_Dikey",
        "02_Cam_Tablo_Yatay",
        "03_Ahsap_Tablo",
        "04_Cam_Dograma",
        "05_Ocak_Arkasi",
        "06_PETEK",
    } - set(by_category))
    lines.extend([
        "",
        "## Measured outputs",
        "",
        "The experiment records per-reference candidate boxes, score, elapsed time,",
        "target/reference SHA, and checkpoint progress. Candidate count is not accuracy.",
        "A reference crop can point to a wrong object or background; this is why no",
        "automatic acceptance is derived from the scores.",
        "",
        "## Independent decision",
        "",
        "**NO-GO for production geometry.** The strongest useful next path is a",
        "hybrid abstaining decision: image-guided candidates plus text baseline",
        "agreement, bbox-prompted SAM2, category-specific printable-surface rules,",
        "and human review for disagreement. PETEK must remain contour/slot based,",
        "not forced into a four-corner quad.",
        "",
        "## Limitations",
        "",
        "- No approved source-SHA ground truth was available.",
        "- Legacy geometry was used only to create candidate reference crops.",
        "- Text-guided and SIFT results remain baselines; their outputs were not relabeled as truth.",
        "- Center-prompt SAM2 masks are not substituted for bbox-prompted masks.",
        "",
        "## Coverage blockers",
        "",
        "- The completed run has 140 distinct targets: 21 Wi-Fi, 23 Cam Dikey, 23 Cam Yatay,",
        "  23 Ahşap, 23 Cam Doğrama, and 27 Ocak Arkası candidates were available through",
        "  reference crops. PETEK has no verified legacy product crop, so it was not fabricated",
        "  and remains blocked rather than being counted as a successful category.",
        "- Ocak Arkası has only five crop-backed independent references; higher reference counts",
        "  therefore have fewer eligible independent targets. This is a data-coverage limitation,",
        "  not a model success.",
        f"- Missing category in this run: {', '.join(missing_categories) or 'none'}.",
    ])
    OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"rows": len(rows), "output": str(OUTPUT)}))


if __name__ == "__main__":
    main()
