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
import shutil
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
    ROOT / "SABLON_V2_MIMARI" / "core" / "db.py",
    ROOT / "SABLON_V2_MIMARI" / "core" / "vision.py",
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

# Canonical EPIC-2 golden baseline. These are minimum VALID sample counts, not
# exact totals, so a future expanded dataset can still pass while a truncated or
# accidentally empty category cannot masquerade as six-category evidence.
MIN_GOLDEN_VALID_COUNTS = {
    "01_Wifi_Kutusu": 125,
    "02_Cam_Tablo_Dikey": 43,
    "02_Cam_Tablo_Yatay": 50,
    "03_Ahsap_Tablo": 36,
    "04_Cam_Dograma": 68,
    "05_Ocak_Arkasi": 14,
}

# Runtime inputs that factory preflight is allowed to READ but never mutate.
# Output, Excel and log directories are intentionally excluded because they are
# production outputs rather than immutable validation inputs.
RUNTIME_READONLY_INPUTS = (
    Path("1_GELEN_KAGGLE_BASKILARI"),
    Path("2_SABLON_HAVUZU"),
    Path("2_SABLON_HAVUZU_ORIJINAL_YEDEK"),
    Path("99_SISTEM_MOTORLARI_VE_KODLAR") / "SISTEM_MOTORU" / "ayarlar.json",
    Path("99_SISTEM_MOTORLARI_VE_KODLAR") / "SISTEM_MOTORU" / "masks",
    Path("SABLON_V2_MIMARI") / "ayarlar.db",
)

EXPECTED_BRANCH = "feature/epic-3-geometry-accuracy"


def _run(
    name: str,
    command: List[str],
    cwd: Path = ROOT,
    env: Dict[str, str] | None = None,
) -> Dict[str, Any]:
    proc = subprocess.run(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
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


def _snapshot_runtime_readonly_inputs(runtime_workspace: Path) -> Dict[str, Any]:
    """Hash production inputs that preflight may read but must never mutate.

    Each configured root records existence/type as well as per-file SHA-256 so
    creating/deleting an empty directory is detected in addition to byte edits.
    """
    result: Dict[str, Any] = {}
    for relative_root in RUNTIME_READONLY_INPUTS:
        path = runtime_workspace / relative_root
        key = relative_root.as_posix()
        entry: Dict[str, Any] = {
            "exists": path.exists(),
            "is_dir": path.is_dir(),
            "files": {},
        }
        if path.is_file():
            entry["files"]["."] = _sha256_file(path)
        elif path.is_dir():
            for child in sorted(p for p in path.rglob("*") if p.is_file()):
                entry["files"][child.relative_to(path).as_posix()] = _sha256_file(child)
        result[key] = entry
    return result


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
        attempted = int(row.get("attempted", 0) or 0)
        excluded = int(row.get("excluded", 0) or 0)
        categories[category] = {
            "attempted": attempted,
            "valid_evaluated": max(0, attempted - excluded),
            "excluded": excluded,
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


def _golden_coverage_check(benchmark: Dict[str, Any]) -> Dict[str, Any]:
    """Require at least the canonical six-category real-golden baseline."""
    categories = benchmark.get("categories") or {}
    per_category: Dict[str, Any] = {}
    for category, minimum in MIN_GOLDEN_VALID_COUNTS.items():
        summary = categories.get(category) or {}
        attempted = int(summary.get("attempted", 0) or 0)
        excluded = int(summary.get("excluded", 0) or 0)
        actual = max(0, attempted - excluded)
        per_category[category] = {
            "minimum_valid": minimum,
            "actual_valid": actual,
            "attempted": attempted,
            "meets_minimum": actual >= minimum and attempted >= actual,
        }

    required_total = sum(MIN_GOLDEN_VALID_COUNTS.values())
    reported_global_valid = int(benchmark.get("valid_evaluated", 0) or 0)
    category_valid_total = sum(
        max(
            0,
            int((categories.get(category) or {}).get("attempted", 0) or 0)
            - int((categories.get(category) or {}).get("excluded", 0) or 0),
        )
        for category in MIN_GOLDEN_VALID_COUNTS
    )
    return {
        "required_minimum_valid_total": required_total,
        "reported_global_valid": reported_global_valid,
        "category_valid_total": category_valid_total,
        "per_category": per_category,
        "all_categories_meet_minimum": all(
            item["meets_minimum"] for item in per_category.values()
        ),
        "global_matches_category_total": reported_global_valid == category_valid_total,
        "ok": (
            reported_global_valid >= required_total
            and reported_global_valid == category_valid_total
            and all(item["meets_minimum"] for item in per_category.values())
        ),
    }


def _archive_evidence_artifacts(
    paths: List[Path],
    archive_root: Path,
) -> str | None:
    """Move prior bundle-owned evidence aside so it is preserved but never reused."""
    existing = [artifact for artifact in paths if artifact.is_file()]
    if not existing:
        return None

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    archive_dir = archive_root / "previous_runs" / stamp
    archive_dir.mkdir(parents=True, exist_ok=False)

    for artifact in existing:
        shutil.move(str(artifact), str(archive_dir / artifact.name))
    return str(archive_dir)


def _command_succeeded(commands: List[Dict[str, Any]], name: str) -> bool:
    for item in commands:
        if item.get("name") == name:
            return bool(item.get("ok"))
    return False


def _cross_evidence_consistency(evidence: Dict[str, Any]) -> Dict[str, Any]:
    benchmark = evidence.get("benchmark") or {}
    diagnostics = evidence.get("diagnostic_invariants") or {}
    bench_categories = benchmark.get("categories") or {}
    diag_categories = diagnostics.get("categories") or {}

    global_benchmark_valid = int(benchmark.get("valid_evaluated", 0) or 0)
    global_diagnostic_valid = int(
        diagnostics.get("global_valid_evaluated", 0) or 0
    )
    per_category = {}
    for category in REQUIRED_CATEGORIES:
        bench_valid = int(
            (bench_categories.get(category) or {}).get(
                "valid_evaluated",
                0,
            )
            or 0
        )
        diag_valid = int(
            (diag_categories.get(category) or {}).get(
                "valid_evaluated",
                0,
            )
            or 0
        )
        per_category[category] = {
            "benchmark_valid": bench_valid,
            "diagnostic_valid": diag_valid,
            "match": (
                category in bench_categories
                and category in diag_categories
                and bench_valid == diag_valid
            ),
        }

    return {
        "global_benchmark_valid": global_benchmark_valid,
        "global_diagnostic_valid": global_diagnostic_valid,
        "global_valid_match": global_benchmark_valid == global_diagnostic_valid,
        "per_category": per_category,
        "all_required_category_valid_counts_match": all(
            item["match"] for item in per_category.values()
        ),
        "ok": bool(
            global_benchmark_valid > 0
            and global_benchmark_valid == global_diagnostic_valid
            and all(item["match"] for item in per_category.values())
        ),
    }


def _review_readiness(
    *,
    commands_ok: bool,
    unit_tests_executed: bool,
    diagnostic_ok: bool,
    benchmark_ok: bool,
    golden_coverage_ok: bool,
    telemetry_ok: bool,
    cross_evidence_ok: bool,
    integrity_ok: bool,
) -> bool:
    """Fail closed unless every release-evidence gate was actually exercised."""
    return bool(
        commands_ok
        and unit_tests_executed
        and diagnostic_ok
        and benchmark_ok
        and golden_coverage_ok
        and telemetry_ok
        and cross_evidence_ok
        and integrity_ok
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument(
        "--runtime-workspace",
        required=True,
        type=Path,
        help=(
            "Real mutable production workspace. Source code remains in this "
            "clean checkout; manifest/templates/DB/outputs are validated here."
        ),
    )
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
    runtime_workspace = args.runtime_workspace.resolve()

    if not dataset.is_dir():
        raise SystemExit(f"Dataset directory not found: {dataset}")
    if not runtime_workspace.is_dir():
        raise SystemExit(
            f"Runtime workspace directory not found: {runtime_workspace}"
        )
    for label, path in (
        ("Runtime workspace", runtime_workspace),
        ("Golden dataset", dataset),
    ):
        try:
            path.relative_to(ROOT)
        except ValueError:
            pass
        else:
            raise SystemExit(
                f"{label} must stay outside the clean source checkout: {path}"
            )

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

    # Every run owns these exact evidence filenames. Archive leftovers from an
    # interrupted/older run before collecting new evidence so file existence can
    # never be mistaken for success in the current run, while failure evidence
    # remains available for diagnosis.
    archived_previous_evidence = _archive_evidence_artifacts(
        [
            benchmark_json,
            diagnostic_json,
            telemetry_json,
            manifest_json,
        ],
        out_dir,
    )

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
    runtime_inputs_before = _snapshot_runtime_readonly_inputs(runtime_workspace)
    commands: List[Dict[str, Any]] = []

    # Never let a globally configured runtime override leak into source-only
    # validation subprocesses. Unit tests/benchmarks must exercise the checked-
    # out branch in isolation; only factory_preflight below may inspect real
    # mutable production data.
    source_env = os.environ.copy()
    source_env.pop("MOCKUP_RUNTIME_WORKSPACE", None)

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
                env=source_env,
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
                    "tests/test_epic3_validation_bundle.py",
                    "tests/test_epic3_benchmark.py",
                    "tests/test_control_center_file_ops.py",
                    "tests/test_runtime_workspace_routing.py",
                    "-v",
                ],
                env=source_env,
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
            env=source_env,
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
            env=source_env,
        )
    )

    # Telemetry consumes only a diagnostic produced successfully in THIS run.
    # A leftover file from an interrupted older run must never satisfy this gate.
    if (
        _command_succeeded(commands, "geometry_diagnostics")
        and diagnostic_json.is_file()
    ):
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
                env=source_env,
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
        preflight_env = os.environ.copy()
        preflight_env["MOCKUP_RUNTIME_WORKSPACE"] = str(runtime_workspace)
        commands.append(
            _run(
                "factory_preflight",
                [sys.executable, str(ENGINE), "--preflight"],
                env=preflight_env,
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
    runtime_inputs_after = _snapshot_runtime_readonly_inputs(runtime_workspace)
    tracked_after = _tracked_worktree_snapshot()
    head_after = _git_head()
    branch_after = _git_branch()
    dataset_unchanged = dataset_before == dataset_after
    runtime_readonly_inputs_unchanged = (
        runtime_inputs_before == runtime_inputs_after
    )
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
        "runtime_workspace": str(runtime_workspace),
        "archived_previous_evidence": archived_previous_evidence,
        "commands": commands,
        "all_commands_ok": all(bool(item.get("ok")) for item in commands),
        "integrity": {
            "dataset_file_count_before": len(dataset_before),
            "dataset_file_count_after": len(dataset_after),
            "dataset_unchanged": dataset_unchanged,
            "runtime_readonly_inputs_unchanged": runtime_readonly_inputs_unchanged,
            "runtime_readonly_inputs_before": runtime_inputs_before,
            "runtime_readonly_inputs_after": runtime_inputs_after,
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

    if _command_succeeded(commands, "epic3_benchmark") and benchmark_json.is_file():
        try:
            raw_benchmark = _load_json(benchmark_json)
            evidence["benchmark"] = _benchmark_summary(raw_benchmark)
            evidence["golden_coverage"] = _golden_coverage_check(raw_benchmark)
        except Exception as exc:
            evidence["benchmark_error"] = str(exc)

    if _command_succeeded(commands, "geometry_diagnostics") and diagnostic_json.is_file():
        try:
            evidence["diagnostic_invariants"] = _diagnostic_invariants(
                _load_json(diagnostic_json)
            )
        except Exception as exc:
            evidence["diagnostic_error"] = str(exc)

    if _command_succeeded(commands, "scorer_telemetry") and telemetry_json.is_file():
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

    diagnostic_payload = evidence.get("diagnostic_invariants") or {}
    diagnostic_categories = diagnostic_payload.get("categories") or {}
    diagnostic_ok = bool(
        diagnostic_payload.get("global_counts_match", False)
        and diagnostic_payload.get("all_category_counts_match", False)
        and all(
            category in diagnostic_categories
            for category in REQUIRED_CATEGORIES
        )
    )
    benchmark_ok = bool(
        (evidence.get("benchmark") or {}).get(
            "all_required_categories_present", False
        )
    )
    golden_coverage_ok = bool(
        (evidence.get("golden_coverage") or {}).get("ok", False)
    )
    evidence["cross_evidence_consistency"] = _cross_evidence_consistency(
        evidence
    )
    cross_evidence_ok = bool(
        evidence["cross_evidence_consistency"].get("ok", False)
    )
    telemetry_payload = evidence.get("telemetry") or {}
    telemetry_ok = bool(
        int(telemetry_payload.get("sample_count", 0) or 0) > 0
        and not telemetry_payload.get("missing_scorer_categories")
        and "telemetry_error" not in evidence
    )

    integrity_ok = bool(
        dataset_unchanged
        and runtime_readonly_inputs_unchanged
        and branch_before == EXPECTED_BRANCH
        and git_revision_unchanged
        and not tracked_before["dirty"]
        and tracked_worktree_unchanged
    )
    unit_tests_executed = not bool(args.skip_unit_tests)
    evidence["bundle_checks"] = {
        "commands_ok": evidence["all_commands_ok"],
        "unit_tests_executed": unit_tests_executed,
        "diagnostic_invariants_ok": diagnostic_ok,
        "required_benchmark_categories_ok": benchmark_ok,
        "golden_coverage_ok": golden_coverage_ok,
        "telemetry_has_samples": telemetry_ok,
        "cross_evidence_consistency_ok": cross_evidence_ok,
        "integrity_ok": integrity_ok,
        "ready_for_human_review": _review_readiness(
            commands_ok=evidence["all_commands_ok"],
            unit_tests_executed=unit_tests_executed,
            diagnostic_ok=diagnostic_ok,
            benchmark_ok=benchmark_ok,
            golden_coverage_ok=golden_coverage_ok,
            telemetry_ok=telemetry_ok,
            cross_evidence_ok=cross_evidence_ok,
            integrity_ok=integrity_ok,
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
