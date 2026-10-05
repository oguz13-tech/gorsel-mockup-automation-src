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

    commands: List[Dict[str, Any]] = []

    if not args.skip_unit_tests:
        commands.append(
            _run(
                "geometry_diagnostics_unit_tests",
                [
                    sys.executable,
                    "-m",
                    "unittest",
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

    evidence: Dict[str, Any] = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "head_sha": _git_head(),
        "dataset": str(dataset),
        "output_dir": str(out_dir),
        "commands": commands,
        "all_commands_ok": all(bool(item.get("ok")) for item in commands),
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
            evidence["telemetry"] = {
                "sample_count": int(telemetry.get("sample_count", 0) or 0),
                "categories": sorted((telemetry.get("categories") or {}).keys()),
            }
        except Exception as exc:
            evidence["telemetry_error"] = str(exc)

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

    return 0 if evidence["all_commands_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
