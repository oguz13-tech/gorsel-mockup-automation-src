"""Read-only or explicitly backed-up Windows Group 3 safety report CLI."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from legacy_manager import preferred_runtime
from URETIM_V4.final_guard_v44 import inspect_workspaces, backup_and_restore_trial, BACKUP_CONFIRM


def main():
    parser = argparse.ArgumentParser(description="Görsel Fabrikası V4.4 güvenlik kontrolü")
    parser.add_argument("--runtime", type=Path, help="Gerçek şablon ana klasörü")
    parser.add_argument("--state", type=Path, help="Üretim kayıt klasörü (varsayılan LocalAppData)")
    parser.add_argument("--backup", action="store_true", help="Açık onayla tutarlı iki DB yedeği ve test geri yükleme")
    parser.add_argument("--backup-destination", type=Path, help="Yerel yedek klasörü")
    parser.add_argument("--confirm", default="")
    args = parser.parse_args()
    runtime = args.runtime or preferred_runtime()
    if args.backup:
        if args.confirm != BACKUP_CONFIRM:
            parser.error("Yedekleme için --confirm YEDEK_AL_V44 gereklidir")
        result = backup_and_restore_trial(runtime, args.state,
                   destination_root=args.backup_destination, confirm=args.confirm)
    else:
        result = inspect_workspaces(runtime, args.state)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))

if __name__ == "__main__":
    main()
