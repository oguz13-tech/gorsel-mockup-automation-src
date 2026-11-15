"""Register create-only PETEK overlay recovery outputs in the V4 ledger."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PETEK_V3 import engine as petek_engine
from URETIM_V4.unified_batch import UnifiedV4Ledger, _store_id_from_output
from URETIM_V4.store_identity_v485 import trendyol_codes, petek_measurement_codes


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--recovery-report", required=True, type=Path)
    ap.add_argument("--source-report", required=True, type=Path)
    ap.add_argument("--state-root", required=True, type=Path)
    ap.add_argument("--output-root", required=True, type=Path)
    args = ap.parse_args()

    recovery = json.loads(args.recovery_report.read_text(encoding="utf-8"))
    source_report = json.loads(args.source_report.read_text(encoding="utf-8"))
    source_sha = {str(item.get("source")): str(item.get("source_sha") or "")
                  for item in source_report.get("errors", [])}
    ledger = UnifiedV4Ledger(args.state_root)
    clean_rows = {str(Path(row.get("output", "")).resolve()): row
                  for row in ledger.successful()
                  if row.get("category") == "06_Petek_Kapama"
                  and str(row.get("artifact_kind") or "clean") == "clean"}

    registered = 0
    reused = 0
    errors = []
    for item in recovery.get("results", []):
        if item.get("status") != "PASS":
            continue
        source = Path(str(item.get("source") or "")).resolve()
        source_row = clean_rows.get(str(source))
        if source_row is None:
            errors.append({"source": str(source), "error": "CLEAN_LEDGER_ROW_NOT_FOUND"})
            continue
        try:
            store = _store_id_from_output(source_row["output"], args.output_root)
        except Exception:
            store = "LOCAL"
        for output_item in item.get("outputs", []):
            cm = str(output_item.get("cm") or "")
            output = Path(str(output_item.get("output") or ""))
            output_sha = str(output_item.get("output_sha") or "")
            if not cm or not output.is_file() or len(output_sha) != 64:
                errors.append({"source": str(source), "cm": cm, "error": "RECOVERY_OUTPUT_INVALID"})
                continue
            key = hashlib.sha256((str(source_row["key"]) + "|" + cm + "|" + output_sha).encode()).hexdigest()[:24]
            try:
                try:
                    sku = petek_measurement_codes(
                        trendyol_codes(source_row["art_name"], store, "06_Petek_Kapama"), cm
                    )["sku"]
                except Exception:
                    sku = f"{source_row['sku']}__{cm}"
                manifest = json.dumps({
                    "recovery": "PETEK_OVERLAY_RECOVERY_V1",
                    "source": str(source), "source_sha256": source_sha,
                    "output": str(output), "output_sha256": output_sha,
                    "overlay_cm": cm,
                }, ensure_ascii=False, sort_keys=True)
                fields = {
                    "key": key, "sku": sku, "category": "06_Petek_Kapama",
                    "art_sha": source_row["art_sha"], "template_sha": source_row["template_sha"],
                    "mask_sha": source_row["mask_sha"], "art_name": source_row["art_name"],
                    "uid": source_row["uid"], "output": str(output),
                    "artifact_kind": "overlay", "source_key": source_row["key"],
                    "overlay_cm": cm, "overlay_manifest": manifest,
                }
                record = ledger.reserve(fields)
                if record["status"] == "RENDERED":
                    if record.get("output_sha") == output_sha:
                        reused += 1
                    else:
                        raise RuntimeError("OVERLAY_LEDGER_KEY_SHA_CONFLICT")
                elif record["status"] == "PENDING":
                    ledger.complete(key, output_sha)
                    registered += 1
                else:
                    raise RuntimeError("OVERLAY_LEDGER_STATUS_" + str(record["status"]))
            except Exception as exc:
                errors.append({"source": str(source), "cm": cm,
                               "error": type(exc).__name__ + ": " + str(exc)[:300]})

    payload = {
        "schema": 1,
        "status": "PASS" if not errors else "PARTIAL",
        "registered": registered, "reused": reused, "errors": errors,
        "recovery_report": str(args.recovery_report),
    }
    out = args.recovery_report.with_name(args.recovery_report.stem + "_LEDGER.json")
    petek_engine.atomic_new_file(out, json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"))
    print(json.dumps({"report": str(out), "registered": registered,
                      "reused": reused, "errors": len(errors)}, ensure_ascii=False))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
