"""Pure planning and machine-scoped performance evidence; no live DB writes."""
from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import sys
from pathlib import Path
from statistics import median

import cv2
import numpy as np


def machine_identity() -> dict:
    return {"machine": platform.node(), "cpu": platform.processor(),
            "logical_cpus": os.cpu_count(), "python": sys.version.split()[0],
            "opencv": cv2.__version__, "numpy": np.__version__,
            "implementation": "V501_RENDER_PROFILE_1"}


def machine_key() -> str:
    return hashlib.sha256(json.dumps(machine_identity(), sort_keys=True).encode()).hexdigest()


def summarize_reports(report_dir: Path) -> list[dict]:
    """Wall time, not summed concurrent task durations, defines throughput."""
    rows = []
    for path in sorted(Path(report_dir).glob("ISLEM_RAPORU_*.json")):
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
            perf = obj["performance"]
            counts = obj["counts"]
            timings = perf["stage_timings"]
            wall = float(timings["total_wall_seconds"])
            successful = int(counts["successful"])
            if wall <= 0 or successful <= 0:
                continue
            rows.append({"operation_id": obj["operation_id"],
                         "workers": perf.get("render_workers"), "wall_seconds": wall,
                         "successful": successful, "failed": int(counts.get("failed", 0)),
                         "seconds_per_output": wall / successful,
                         "outputs_per_minute": 60 * successful / wall,
                         "timings": timings, "source_report": str(path)})
        except (OSError, ValueError, TypeError, KeyError):
            continue
    return rows


def planning_summary(*, output_root: Path, jobs: int, templates: int, designs: int,
                     workers: int, report_dir: Path, upscale: bool = False,
                     render_mode: str = "all_templates_per_design") -> dict:
    base = Path(output_root)
    while not base.exists() and base != base.parent:
        base = base.parent
    free = shutil.disk_usage(base).free
    # Budget is explicitly conservative, not a promise about compressed size.
    estimated_bytes = jobs * (32_000_000 if upscale else 8_000_000)
    evidence = [r for r in summarize_reports(report_dir)
                if r["workers"] == workers and r["failed"] == 0][-5:]
    seconds = median(r["seconds_per_output"] for r in evidence) * jobs if evidence else None
    return {"jobs": jobs, "templates": templates, "designs": designs,
            "render_workers": workers, "free_disk_bytes": free,
            "estimated_disk_bytes": estimated_bytes,
            "disk_budget_ok": estimated_bytes <= free * .8,
            "estimated_seconds": seconds, "estimate_samples": len(evidence),
            "estimate_scope": "RECENT_HISTORY_NOT_CATEGORY_GUARANTEE",
            "upscale_4k": upscale, "render_mode": render_mode}


def summary_text(summary: dict) -> str:
    eta = summary["estimated_seconds"]
    mode = summary.get("render_mode", "all_templates_per_design")
    mode_text = ("Her tasarıma 1 çıktı · şablonlar dengeli tekrar kullanılır"
                 if mode == "balanced_one_per_design"
                 else "Her tasarım × her atanmış şablon")
    return (f"Üretim modeli: {mode_text}\n"
            f"{summary['templates']} şablon · {summary['designs']} tasarım: {summary['jobs']} iş\n"
            f"Worker: {summary['render_workers']} · 4K: {'Açık' if summary['upscale_4k'] else 'Kapalı'}\n"
            f"Boş disk: {summary['free_disk_bytes']/1e9:.1f} GB · ayrılan tahmini bütçe: "
            f"{summary['estimated_disk_bytes']/1e9:.1f} GB\n"
            + (f"Yaklaşık süre: {eta/60:.1f} dk (son {summary['estimate_samples']} kayıt; kategoriye göre değişir)"
               if eta is not None else "Süre tahmini için henüz eşleşen ölçüm yok."))
