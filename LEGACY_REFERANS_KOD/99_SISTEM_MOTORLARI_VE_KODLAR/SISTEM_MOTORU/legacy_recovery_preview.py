# -*- coding: utf-8 -*-
"""Read-only historical recovery viewer (never apply/overwrite).

Historical one-shot scripts in this directory previously wrote to specific
OneDrive file names at import and could delete backups. Their original script
entrypoints are retained and now delegate to this diagnostic instead.

No restore or mutation API is offered here. A real restore must use the
separate human-approved lifecycle control plane and immutable snapshots.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

HISTORICAL = (
    "ayarlar.json.user_backup_20260920_000450",
    "ayarlar.json.user_backup_20260920_001352",
)


def inspect(kind: str, workspace: str | Path | None = None) -> dict:
    root_raw = workspace or os.getenv("MOCKUP_RUNTIME_WORKSPACE")
    if not root_raw:
        return {
            "status": "BLOCKED_NO_RUNTIME",
            "kind": kind,
            "mutated": False,
            "message": "Explicit --runtime-root required for historical recovery review.",
        }
    root = Path(root_raw).expanduser().resolve()
    motor = root / "99_SISTEM_MOTORLARI_VE_KODLAR" / "SISTEM_MOTORU"
    outputs = []
    for filename in HISTORICAL + ("ayarlar.json",):
        file = motor / filename
        if not file.is_file() or file.is_symlink():
            outputs.append({"name": filename, "exists": False})
            continue
        try:
            raw = file.read_bytes()
            data = json.loads(raw)
            by_category = {
                name: len(entry.get("sablonlar", {}))
                for name, entry in data.get("kategoriler", {}).items()
                if isinstance(entry, dict)
            }
            outputs.append({
                "name": filename, "exists": True,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "templates_per_category": by_category,
            })
        except (ValueError, OSError, TypeError) as e:
            outputs.append({
                "name": filename, "exists": True,
                "status": "UNREADABLE", "error": type(e).__name__,
            })
    return {
        "status": "READ_ONLY_REVIEW_REQUIRED",
        "kind": kind, "workspace": str(root), "mutated": False,
        "backups": outputs,
        "message": "No files were moved, renamed, deleted or restored.",
    }


def main(kind: str) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only historical template recovery inventory."
    )
    parser.add_argument("--runtime-root", type=Path)
    options = parser.parse_args()
    result = inspect(kind, options.runtime_root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 2 if result["status"].startswith("BLOCKED") else 0
