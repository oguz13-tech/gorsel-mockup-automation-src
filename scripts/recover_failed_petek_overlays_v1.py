"""Create-only recovery for failed PETEK overlay measurements."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from datetime import datetime

from PETEK_V3 import engine as petek_engine
from URETIM_V4.petek_overlay_variations_v1 import preflight, process_source


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", required=True, type=Path)
    ap.add_argument("--overlay-root", required=True, type=Path)
    ap.add_argument("--report-root", required=True, type=Path)
    args = ap.parse_args()

    report = json.loads(args.report.read_text(encoding="utf-8"))
    validation = preflight(args.overlay_root)
    if not validation.get("ready_for_four"):
        raise RuntimeError("Overlay klasörü recovery için hazır değil: " + "; ".join(validation.get("errors", [])[:8]))

    unique: dict[str, dict] = {}
    for item in report.get("errors", []):
        source = str(item.get("source") or "")
        if source:
            unique.setdefault(source, item)

    results = []
    counts = {"sources": len(unique), "planned": len(unique) * 4,
              "successful": 0, "failed": 0, "reused": 0}
    for source_text, item in sorted(unique.items()):
        source = Path(source_text)
        row = {
            "output": str(source),
            "output_sha": str(item.get("source_sha") or ""),
            "art_name": source.name,
        }
        try:
            result = process_source(
                row, validation, source.parent,
                source_sha=row["output_sha"] or None,
            )
            successful = sum(1 for entry in result.get("results", [])
                            if entry.get("manifest", {}).get("qa_status") != "REUSED")
            reused = sum(1 for entry in result.get("results", [])
                         if entry.get("manifest", {}).get("qa_status") == "REUSED")
            counts["successful"] += successful
            counts["reused"] += reused
            results.append({"source": str(source), "status": "PASS",
                            "outputs": [{"cm": entry["cm"], "output": entry["output"],
                                         "output_sha": entry["output_sha"]}
                                        for entry in result.get("results", [])]})
        except Exception as exc:
            counts["failed"] += 4
            results.append({"source": str(source), "status": "FAILED",
                            "error": type(exc).__name__ + ": " + str(exc)[:500]})

    counts["completed"] = counts["successful"] + counts["reused"] + counts["failed"]
    payload = {
        "schema": 1,
        "status": "PASS" if counts["failed"] == 0 else "PARTIAL",
        "source_report": str(args.report),
        "overlay_root": str(args.overlay_root),
        "counts": counts,
        "results": results,
        "created_at": datetime.now().astimezone().isoformat(),
    }
    args.report_root.mkdir(parents=True, exist_ok=True)
    out = args.report_root / ("PETEK_OVERLAY_RECOVERY_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".json")
    petek_engine.atomic_new_file(out, json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"))
    print(json.dumps({"report": str(out), "counts": counts}, ensure_ascii=False))
    return 0 if counts["failed"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
