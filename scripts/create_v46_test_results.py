"""Write the reproducible test-result summary for the final candidate."""
from __future__ import annotations

import json
from pathlib import Path


def create(path: Path, commit: str) -> None:
    data = {
        "branch": "feature/v46-safe-consolidation-20261024",
        "commit": commit,
        "tests": [
            {"name": "TESTLER/test_port_transition_force_fallback.py", "result": "6 PASS"},
            {"name": "TESTLER/test_v46_review_bulk_esrgan.py", "result": "4 PASS, 2 SKIP"},
            {"name": "TESTLER/test_v44_group1_upscale_ui.py", "result": "8 PASS"},
            {"name": "TESTLER/test_petek_cover_v3_2.py + TESTLER/test_v40_unified_seven_category.py + tests/test_p0_regressions.py", "result": "63 PASS"},
            {"name": "tests/test_v46_synthetic_corner_benchmark.py", "result": "1 PASS"},
        ],
        "skips": [
            "V4.6 Flask endpoint checks: isolated production DB safety guard blocked startup.",
        ],
        "not_run_as_pass": [
            "Win11 real GUI acceptance",
            "GPU smoke / Real-ESRGAN reinstall",
            "real four-category reflection QA",
            "real HTTPS upload and marketplace workbook acceptance",
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    create(root / "artifacts" / "v46" / "TEST_RESULTS.json", "working-tree")
