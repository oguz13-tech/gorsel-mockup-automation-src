# -*- coding: utf-8 -*-
"""Historical rescue scripts: safe, read-only preview gateway.

Legacy entry points are retained for user discoverability. Their former
hard-coded OneDrive mutation logic is preserved in version control for
forensic history, but it is impossible to execute through these launchers.
The current Lifecycle Center owns approved recovery/rollback workflows.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

MODES = {"final_fix","ultimate_rescue","rollback","rescue_edits","rescue_edits_all","fix_json_keys"}

def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main(mode, argv=None):
    if mode not in MODES:
        raise ValueError("UNKNOWN_LEGACY_RECOVERY_MODE")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", type=Path, default=None)
    options = parser.parse_args(argv)
    explicit = options.runtime_root or os.environ.get("MOCKUP_RUNTIME_WORKSPACE")
    if not explicit:
        print(json.dumps({"status":"BLOCKED_NO_EXPLICIT_RUNTIME","mode":mode,
                          "mutated":False}, ensure_ascii=False))
        return 2
    root = Path(explicit).expanduser().resolve()
    motor = root / "99_SISTEM_MOTORLARI_VE_KODLAR" / "SISTEM_MOTORU"
    settings = motor / "ayarlar.json"
    backups = sorted(motor.glob("ayarlar.json.user_backup_*")) if motor.is_dir() else []
    current = {}
    if settings.is_file():
        try:
            current = json.loads(settings.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            print(json.dumps({"status":"BLOCKED_INVALID_SETTINGS","mode":mode,
                              "mutated":False}, ensure_ascii=False))
            return 2
    categories = current.get("kategoriler", {}) if isinstance(current, dict) else {}
    total = 0
    duplicate_stems = 0
    for category, entry in categories.items():
        names = list((entry or {}).get("sablonlar", {}).keys())
        total += len(names)
        stems = [Path(name).stem.casefold() for name in names]
        duplicate_stems += len(stems) - len(set(stems))
    report = {
        "status":"READ_ONLY_HISTORICAL_RECOVERY_PREVIEW",
        "mode":mode, "runtime_exists":root.is_dir(),
        "settings_exists":settings.is_file(),
        "settings_sha256":_sha(settings) if settings.is_file() else None,
        "available_backup_count":len(backups),
        "template_records":total,
        "extension_independent_collisions":duplicate_stems,
        "mutated":False,
        "restore_applied":False,
        "next_action":"Use the current Lifecycle Center and a verified separate backup, not the historical destructive script.",
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 2  # Explicitly BLOCKED: report != successful recovery.

if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[0]).stem, sys.argv[1:]))
