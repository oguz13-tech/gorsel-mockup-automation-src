"""EPIC-3 local validation evidence bundle.

This script is intentionally NOT a production auto-approval gate. It orchestrates
read-only/local validation after GitHub-native implementation work is complete and
writes evidence outside the repository when the caller supplies an external
--output-dir.

It never edits templates, ayarlar.json, template_profiles, source images or
production outputs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
ENGINE = (
    ROOT
    / "99_SISTEM_MOTORLARI_VE_KODLAR"
    / "SISTEM_MOTORU"
    / "pc_master_factory.py"
)

SYNTAX_CHECK_FILES = (
    ROOT / "SABLON_V2_MIMARI" / "core" / "template_intelligence.py",
    ROOT / "SABLON_V2_MIMARI" / "app.py",
    ROOT / "V2_KONTROL_MERKEZI" / "app.py",
    ROOT / "99_SISTEM_MOTORLARI_VE_KODLAR" / "SISTEM_MOTORU" / "foreground_ai.py",
    ENGINE,
    ROOT / "scripts" / "epic3_benchmark.py",
    ROOT / "scripts" / "geometry_diagnostics.py",
    ROOT / "scripts" / "scorer_telemetry.py",
    ROOT / "scripts" / "migrate_legacy_geometry_profiles.py",
    ROOT / "scripts" / "epic3_validation_bundle.py",
)

REQUIRED_CATEGORIES = (
    "01_Wifi_Kutusu",
    "02_Cam_Tablo_Dikey",
    "02_Cam_Tablo_Yatay",
    "03_Ahsap_Tablo",
    "04_Cam_Dograma",
    "05_Ocak_Arkasi",
)

SCORER_CATEGORIES = (
    "02_Cam_Tablo_Dikey",
    "02_Cam_Tablo_Yatay",
    "03_Ahsap_Tablo",
    "05_Ocak_Arkasi",
)

EXPECTED_BRANCH = "feature/epic-3-geometry-accuracy"


def _run(name: str, command: List[str], cwd: Path = ROOT) -> Dict[str, Any]:
    proc = subprocess.run(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return {
        "name": name,
        "command": command,
        "exit_code": int(proc.returncode),
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "ok": proc.returncode == 0,
    }


def _git_head() -> str:
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        return "UNKNOWN"
    return proc.stdout.strip()


def _git_branch() -> str:
    proc = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.stdout.strip() if proc.returncode == 0 else "UNKNOWN"


def _tracked_worktree_snapshot() -> Dict[str, Any]:
    """Snapshot staged + unstaged tracked changes, ignoring untracked evidence."""
    digest = hashlib.sha256()
    dirty = False
    for command in (
        ["git", "diff", "--binary", "--no-ext-diff"],
        ["git", "diff", "--cached", "--binary", "--no-ext-diff"],
    ):
        proc = subprocess.run(
            command,
            cwd=str(ROOT),
            capture_output=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"Unable to snapshot tracked worktree (exit={proc.returncode}): "
                + proc.stderr.decode("utf-8", errors="replace")
            )
        if proc.stdout:
            dirty = True
        digest.update(proc.stdout)
        digest.update(b"\0")
    return {"fingerprint": digest.hexdigest(), "dirty": dirty}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _snapshot_dataset(dataset: Path) -> Dict[str, str]:
    """Hash the local golden dataset so validation cannot silently mutate it."""
    snapshot: Dict[str, str] = {}
    for path in sorted(p for p in dataset.rglob("*") if p.is_file()):
        rel = path.relative_to(dataset).as_posix()
        snapshot[rel] = _sha256_file(path)
    return snapshot


def _parse_preflight(commands: List[Dict[str, Any]]) -> Dict[str, Any] | None:
    for item in commands:
        if item.get("name") != "factory_preflight":
            continue
        for line in reversed(str(item.get("stdout") or "").splitlines()):
            if line.startswith("PREFLIGHT_JSON="):
                try:
                    payload = json.loads(line.split("=", 1)[1])
                except json.JSONDecodeError:
                    return None
                return payload if isinstance(payload, dict) else None
    return None


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def _diagnostic_invariants(diag: Dict[str, Any]) -> Dict[str, Any]:
    global_summary = diag.get("global") or {}
    classes = global_summary.get("classification_counts") or {}
    valid = int(global_summary.get("valid_evaluated", 0) or 0)
    class_total = sum(int(v or 0) for v in classes.values())

    category_checks = {}
    for category, summary in (diag.get("categories") or {}).items():
        counts = (summary or {}).get("classification_counts") or {}
        cat_valid = int((summary or {}).get("valid_evaluated", 0) or 0)
        category_checks[category] = {
            "valid_evaluated": cat_valid,
            "classification_total": sum(int(v or 0) for v in counts.values()),
            "counts_match": sum(int(v or 0) for v in counts.values()) == cat_valid,
        }

    return {
        "global_valid_evaluated": valid,
        "global_classification_total": class_total,
        "global_counts_match": class_total == valid,
        "categories": category_checks,
        "all_category_counts_match": all(
            item["counts_match"] for item in category_checks.values()
        ),
    }


def _benchmark_summary(bench: Dict[str, Any]) -> Dict[str, Any]:
    global_data = bench.get("global") or {}
    epic2 = global_data.get("epic2") or {}
    epic3 = global_data.get("epic3") or {}

    epic2_iou = float(epic2.get("median_iou", 0.0) or 0.0)
    epic3_iou = float(epic3.get("median_iou", 0.0) or 0.0)

    categories = {}
    raw_categories = bench.get("categories") or {}
    for category in REQUIRED_CATEGORIES:
        row = raw_categories.get(category) or {}
        old = row.get("epic2") or {}
        new = row.get("epic3") or {}
        categories[category] = {
            "attempted": int(row.get("attempted", 0) or 0),
            "excluded": int(row.get("excluded", 0) or 0),
            "epic2_median_iou": float(old.get("median_iou", 0.0) or 0.0),
            "epic3_median_iou": float(new.get("median_iou", 0.0) or 0.0),
            "epic2_recall_at_50": float(old.get("recall_at_50", 0.0) or 0.0),
            "epic3_recall_at_50": float(new.get("recall_at_50", 0.0) or 0.0),
            "regressed_iou_count": int(row.get("regressed_iou_count", 0) or 0),
            "improved_iou_count": int(row.get("improved_iou_count", 0) or 0),
        }

    return {
        "attempted": int(bench.get("attempted", 0) or 0),
        "valid_evaluated": int(bench.get("valid_evaluated", 0) or 0),
        "excluded": int(bench.get("excluded", 0) or 0),
        "epic2_median_iou": epic2_iou,
        "epic3_median_iou": epic3_iou,
        "median_iou_delta": epic3_iou - epic2_iou,
        "epic2_recall_at_50": float(epic2.get("recall_at_50", 0.0) or 0.0),
        "epic3_recall_at_50": float(epic3.get("recall_at_50", 0.0) or 0.0),
        "epic3_not_worse_by_median_iou": epic3_iou >= epic2_iou,
        "global_regressed_iou_count": int(
            global_data.get("regressed_iou_count", 0) or 0
        ),
        "global_improved_iou_count": int(
            global_data.get("improved_iou_count", 0) or 0
        ),
        "categories": categories,
        "all_required_categories_present": all(
            category in raw_categories for category in REQUIRED_CATEGORIES
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument(
        "--skip-unit-tests",
        action="store_true",
        help="Collect benchmark/preflight evidence without running unittest.",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=40,
        help="Number of largest scorer selection-gap samples to inspect.",
    )
    args = parser.parse_args()

    dataset = args.dataset.resolve()
    out_dir = args.output_dir.resolve()

    if not dataset.is_dir():
        raise SystemExit(f"Dataset directory not found: {dataset}")

    # Keep evidence out of the source repository by default. A caller can still
    # explicitly choose another location, but we refuse accidental in-repo output.
    try:
        out_dir.relative_to(ROOT)
    except ValueError:
        pass
    else:
        raise SystemExit(
            "Refusing to write validation evidence inside the source repository. "
            "Choose an external --output-dir (for example C:\\AI_WORK\\epic3_validation)."
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    benchmark_json = out_dir / "epic3_benchmark.json"
    diagnostic_json = out_dir / "geometry_diagnostics.json"
    telemetry_json = out_dir / "scorer_telemetry.json"
    manifest_json = out_dir / "validation_manifest.json"

    head_before = _git_head()
    branch_before = _git_branch()
    if branch_before != EXPECTED_BRANCH:
        raise SystemExit(
            f"Refusing EPIC-3 validation on branch {branch_before!r}; "
            f"expected {EXPECTED_BRANCH!r}."
        )

    tracked_before = _tracked_worktree_snapshot()
    if tracked_before["dirty"]:
        raise SystemExit(
            "Refusing EPIC-3 validation with staged/unstaged tracked changes. "
            "Commit or revert tracked source changes first so evidence is bound "
            "to the reported HEAD SHA."
        )

    dataset_before = _snapshot_dataset(dataset)
    commands: List[Dict[str, Any]] = []

    missing_syntax_files = [
        str(path) for path in SYNTAX_CHECK_FILES if not path.is_file()
    ]
    if missing_syntax_files:
        commands.append({
            "name": "python_syntax_gate",
            "command": [],
            "exit_code": None,
            "stdout": "",
            "stderr": "Missing syntax-check files: " + ", ".join(missing_syntax_files),
            "ok": False,
        })
    else:
        commands.append(
            _run(
                "python_syntax_gate",
                [
                    sys.executable,
                    "-m",
                    "py_compile",
                    *[str(path) for path in SYNTAX_CHECK_FILES],
                ],
            )
        )

    if not args.skip_unit_tests:
        commands.append(
            _run(
                "full_regression_suite",
                [
                    sys.executable,
                    "-m",
                    "unittest",
                    "tests/test_p0_regressions.py",
                    "tests/test_p1_p15_suite.py",
                    "tests/test_t1_client.py",
                    "tests/test_benchmark_metrics.py",
                    "tests/test_geometry_diagnostics.py",
                    "-v",
                ],
            )
        )

    commands.append(
        _run(
            "epic3_benchmark",
            [
                sys.executable,
                "scripts/epic3_benchmark.py",
                "--dataset",
                str(dataset),
                "--output",
                str(benchmark_json),
            ],
        )
    )
    commands.append(
        _run(
            "geometry_diagnostics",
            [
                sys.executable,
                "scripts/geometry_diagnostics.py",
                "--dataset",
                str(dataset),
                "--output",
                str(diagnostic_json),
            ],
        )
    )

    # Telemetry consumes the just-produced diagnostic file. If diagnostics
    # failed, record a deterministic blocked command instead of fabricating data.
    if diagnostic_json.exists():
        commands.append(
            _run(
                "scorer_telemetry",
                [
                    sys.executable,
                    "scripts/scorer_telemetry.py",
                    "--dataset",
                    str(dataset),
                    "--diag-json",
                    str(diagnostic_json),
                    "--output",
                    str(telemetry_json),
                    "--top-n",
                    str(max(1, args.top_n)),
                ],
            )
        )
    else:
        commands.append(
            {
                "name": "scorer_telemetry",
                "command": [],
                "exit_code": None,
                "stdout": "",
                "stderr": "Blocked: geometry_diagnostics.json was not produced.",
                "ok": False,
            }
        )

    if ENGINE.exists():
        commands.append(
            _run(
                "factory_preflight",
                [sys.executable, str(ENGINE), "--preflight"],
            )
        )
    else:
        commands.append(
            {
                "name": "factory_preflight",
                "command": [sys.executable, str(ENGINE), "--preflight"],
                "exit_code": None,
                "stdout": "",
                "stderr": f"Engine not found: {ENGINE}",
                "ok": False,
            }
        )

    dataset_after = _snapshot_dataset(dataset)
    tracked_after = _tracked_worktree_snapshot()
    head_after = _git_head()
    branch_after = _git_branch()
    dataset_unchanged = dataset_before == dataset_after
    tracked_worktree_unchanged = (
        tracked_before["fingerprint"] == tracked_after["fingerprint"]
    )
    git_revision_unchanged = (
        head_before == head_after and branch_before == branch_after
    )
    preflight = _parse_preflight(commands)

    evidence: Dict[str, Any] = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "head_sha": head_before,
        "branch": branch_before,
        "dataset": str(dataset),
        "output_dir": str(out_dir),
        "commands": commands,
        "all_commands_ok": all(bool(item.get("ok")) for item in commands),
        "integrity": {
            "dataset_file_count_before": len(dataset_before),
            "dataset_file_count_after": len(dataset_after),
            "dataset_unchanged": dataset_unchanged,
            "expected_branch": EXPECTED_BRANCH,
            "branch_before": branch_before,
            "branch_after": branch_after,
            "head_sha_before": head_before,
            "head_sha_after": head_after,
            "git_revision_unchanged": git_revision_unchanged,
            "tracked_worktree_fingerprint_before": tracked_before["fingerprint"],
            "tracked_worktree_fingerprint_after": tracked_after["fingerprint"],
            "tracked_worktree_dirty_before": bool(tracked_before["dirty"]),
            "tracked_worktree_dirty_after": bool(tracked_after["dirty"]),
            "tracked_worktree_clean_before": not bool(tracked_before["dirty"]),
            "tracked_worktree_unchanged": tracked_worktree_unchanged,
            "validation_created_tracked_changes": not tracked_worktree_unchanged,
        },
        "preflight": preflight,
        "manual_evidence_still_required": [
            "representative real renders from all six categories",
            "at least one text-containing artwork",
            "H and V artwork sources",
            "mixed-orientation cutting-board templates",
            "at least one real occlusion case",
            "UI review flow and exact manual-corner persistence",
            "original production-source hash/byte immutability",
        ],
        "auto_approval_assertion": (
            "This bundle does not enable or approve autonomous geometry."
        ),
    }

    if benchmark_json.exists():
        try:
            evidence["benchmark"] = _benchmark_summary(_load_json(benchmark_json))
        except Exception as exc:
            evidence["benchmark_error"] = str(exc)

    if diagnostic_json.exists():
        try:
            evidence["diagnostic_invariants"] = _diagnostic_invariants(
                _load_json(diagnostic_json)
            )
        except Exception as exc:
            evidence["diagnostic_error"] = str(exc)

    if telemetry_json.exists():
        try:
            telemetry = _load_json(telemetry_json)
            telemetry_categories = sorted(
                (telemetry.get("categories") or {}).keys()
            )
            evidence["telemetry"] = {
                "sample_count": int(telemetry.get("sample_count", 0) or 0),
                "categories": telemetry_categories,
                "expected_scorer_categories": list(SCORER_CATEGORIES),
                "missing_scorer_categories": [
                    category
                    for category in SCORER_CATEGORIES
                    if category not in telemetry_categories
                ],
            }
        except Exception as exc:
            evidence["telemetry_error"] = str(exc)

    diagnostic_ok = bool(
        (evidence.get("diagnostic_invariants") or {}).get(
            "global_counts_match", False
        )
        and (evidence.get("diagnostic_invariants") or {}).get(
            "all_category_counts_match", False
        )
    )
    benchmark_ok = bool(
        (evidence.get("benchmark") or {}).get(
            "all_required_categories_present", False
        )
    )
    integrity_ok = bool(
        dataset_unchanged
        and branch_before == EXPECTED_BRANCH
        and git_revision_unchanged
        and not tracked_before["dirty"]
        and tracked_worktree_unchanged
    )
    evidence["bundle_checks"] = {
        "commands_ok": evidence["all_commands_ok"],
        "diagnostic_invariants_ok": diagnostic_ok,
        "required_benchmark_categories_ok": benchmark_ok,
        "integrity_ok": integrity_ok,
        "ready_for_human_review": bool(
            evidence["all_commands_ok"]
            and diagnostic_ok
            and benchmark_ok
            and integrity_ok
        ),
    }

    manifest_json.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Validation evidence manifest: {manifest_json}")
    print(f"HEAD: {evidence['head_sha']}")
    print(f"All commands OK: {evidence['all_commands_ok']}")
    if "benchmark" in evidence:
        bench = evidence["benchmark"]
        print(
            "Median IoU EPIC-2 -> EPIC-3: "
            f"{bench['epic2_median_iou']:.3f} -> "
            f"{bench['epic3_median_iou']:.3f}"
        )

    return 0 if evidence["bundle_checks"]["ready_for_human_review"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
