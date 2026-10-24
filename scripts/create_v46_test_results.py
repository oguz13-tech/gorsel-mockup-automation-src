"""Write the reproducible test-result summary for the final candidate."""
from __future__ import annotations

import json
from pathlib import Path


def create(path: Path, commit: str) -> None:
    data = {
        "branch": "feature/v46-safe-consolidation-20261024",
        "commit": commit,
        "release": "NO-GO",
        "root_cause_report": "docs/V46_ROOT_CAUSE_ACCEPTANCE_20261024.md",
        "tests": [
            {"name": "TESTLER/test_port_transition_force_fallback.py", "result": "6 PASS"},
            {"name": "TESTLER/test_v46_review_bulk_esrgan.py", "result": "4 PASS, 2 SKIP"},
            {"name": "TESTLER/test_v44_group1_upscale_ui.py", "result": "8 PASS"},
            {"name": "TESTLER/test_petek_cover_v3_2.py + TESTLER/test_v40_unified_seven_category.py + tests/test_p0_regressions.py", "result": "63 PASS"},
            {"name": "tests/test_v46_synthetic_corner_benchmark.py", "result": "1 PASS"},
            {"name": "scripts/create_v46_final_candidate.py + ZIP manifest verification",
             "result": "PASS; 389 extracted files; private asset scan PASS"},
        ],
        "skips": [
            "V4.6 Flask endpoint checks: isolated production DB safety guard blocked startup.",
        ],
        "not_run_as_pass": [
            "Win11 real GUI acceptance",
            "GPU smoke / Real-ESRGAN reinstall",
            "real four-category reflection QA",
            "real HTTPS upload and marketplace workbook acceptance",
            "isolated Win11 GUI and seven-category production smoke",
            "real PETEK Golden Dataset quality comparison",
            "100/200/1000 real render and interruption acceptance",
        ],
        "candidate": {
            "path": "C:/AI_WORK/GORSEL_V46_PR52_SAFE_20261024/V46_FINAL_CANDIDATE.zip",
            "sha256": "4232ed9397ab5a217ef5c6608ff2478358ba2d7123552b124d7bad940ed89778",
            "manifest_verification": "PASS",
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    create(root / "artifacts" / "v46" / "TEST_RESULTS.json", "27449cd")
