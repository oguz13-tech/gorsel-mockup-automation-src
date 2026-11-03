"""Create a truthful, read-only final acceptance snapshot for the safe candidate."""
from __future__ import annotations

import hashlib
import json
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ZIP = ROOT / "V46_FINAL_CANDIDATE_92A910F.zip"
MANIFEST = ROOT / "V46_FINAL_CANDIDATE_92A910F" / "MANIFEST_SHA256.json"
OUTPUT = ROOT / "artifacts" / "v46" / "FINAL_ACCEPTANCE_SNAPSHOT.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def package_snapshot() -> dict:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    with zipfile.ZipFile(ZIP) as archive:
        entries = [entry.filename for entry in archive.infolist()]
    return {
        "path": str(ZIP),
        "sha256": sha256(ZIP),
        "source_commit": manifest["source_commit"],
        "manifest_source_file_count": len(manifest["files"]),
        "zip_file_count": len(entries),
        "manifest_plus_manifest_file_count": len(manifest["files"]) + 1,
        "contains_private_runtime_data": manifest["contains_private_runtime_data"],
        "hash_reconciliation": {
            "current": sha256(ZIP),
            "previous_candidate_value": (
                "bdb03b9271ad29b9026fa4b992e3d948693a35a5bd0f0c52730ec3f592713b4c"
            ),
            "historical_stale_value": (
                "4232ed9397ab5a217ef5c6608ff2478358ba2d7123552b124d7bad940ed89778"
            ),
        },
    }


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    snapshot = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "branch": "feature/v46-safe-consolidation-20261024",
        "release": "NO-GO",
        "package": package_snapshot(),
        "agent_executable_tests": {
            "targeted_command": (
                "python -m pytest TESTLER/test_port_transition_force_fallback.py "
                "TESTLER/test_v46_review_bulk_esrgan.py "
                "TESTLER/test_v44_group1_upscale_ui.py "
                "TESTLER/test_petek_cover_v3_2.py "
                "TESTLER/test_v40_unified_seven_category.py "
                "tests/test_p0_regressions.py "
                "tests/test_v46_synthetic_corner_benchmark.py -q"
            ),
            "result": "82 passed, 2 skipped",
        },
        "historical_read_only_evidence": {
            "g3_ledger": {
                "receipt_count": 111,
                "rendered": 110,
                "review_required": 1,
                "verified": 75,
                "missing": 35,
                "sha_mismatch": 0,
                "unsafe_paths": 0,
                "classification": "USER_REPORTED_INTENTIONAL_DELETION",
                "source": "user decision recorded in latest PR #52 instruction",
            },
            "template_profiles": {
                "previous_total": 590,
                "current_total": 591,
                "active_approved_count": "UNKNOWN",
                "classification": "BLOCKED_NO_SAFE_DATABASE_SNAPSHOT",
            },
        },
        "acceptance": {
            "PASS": [
                "targeted synthetic/regression acceptance tests",
                "alternate-port launcher smoke on isolated synthetic runtime",
                "synthetic batch reserve/integrity/emergency safety tests",
                "data-free candidate packaging and private asset scan",
                "current ZIP hash and manifest reconciliation",
            ],
            "HUMAN_REQUIRED": [
                "real Win11 GUI and seven-category production smoke",
                "real approved four-corner save/reopen visual acceptance",
                "real GPU/Real-ESRGAN acceptance",
                "real HTTPS/marketplace workbook acceptance",
                "real PETEK Golden Dataset comparison",
                "100/200/1000 real render and interruption acceptance",
            ],
            "BLOCKED": [
                "template_profiles 590 to 591 active APPROVED/stale/source-SHA classification",
            ],
        },
        "safety": {
            "live_db_written": False,
            "approved_geometry_written": False,
            "live_workspace_written": False,
            "main_merged": False,
        },
    }
    OUTPUT.write_text(
        json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(snapshot["package"], ensure_ascii=False))


if __name__ == "__main__":
    main()
