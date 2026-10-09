from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCH = ROOT / "SABLON_V2_MIMARI"
if str(ARCH) not in sys.path:
    sys.path.insert(0, str(ARCH))

from core.runtime_migration import (  # noqa: E402
    RuntimeMigrationError,
    build_runtime_migration_plan,
    copy_runtime_workspace,
    default_target_root,
    resolve_source_runtime,
    rollback_runtime_switch,
    switch_runtime_after_verification,
    verify_runtime_workspace,
)


def _print(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _progress(current: int, total: int, message: str) -> None:
    print(f"[{current}/{total}] {message}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Mockup runtime workspace için güvenli plan/copy/verify/"
            "switch/rollback aracı. Kaynak dosyaları silmez."
        )
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def add_source_target(p):
        p.add_argument(
            "--source",
            help="Kaynak runtime. Boşsa mevcut runtime otomatik çözülür.",
        )
        p.add_argument(
            "--target",
            default=str(default_target_root()),
            help="Hedef runtime klasörü.",
        )

    add_source_target(sub.add_parser("plan"))
    add_source_target(sub.add_parser("copy"))
    add_source_target(sub.add_parser("verify"))
    add_source_target(sub.add_parser("switch"))
    sub.add_parser("rollback")

    args = parser.parse_args()

    try:
        if args.command == "rollback":
            _print(rollback_runtime_switch())
            return 0

        source = resolve_source_runtime(args.source)
        target = Path(args.target).expanduser().resolve()

        if args.command == "plan":
            _print(build_runtime_migration_plan(source, target))
            return 0

        if args.command == "copy":
            result = copy_runtime_workspace(
                source,
                target,
                progress=_progress,
            )
            _print(result)
            return 0 if result.get("success") else 2

        if args.command == "verify":
            result = verify_runtime_workspace(
                source,
                target,
                progress=_progress,
            )
            _print(result)
            return 0 if result.get("verified") else 3

        if args.command == "switch":
            result = switch_runtime_after_verification(
                source,
                target,
            )
            _print(result)
            return 0

    except (RuntimeMigrationError, ValueError, FileNotFoundError) as exc:
        _print({
            "success": False,
            "error": str(exc),
            "source_deleted": False,
        })
        return 4

    return 5


if __name__ == "__main__":
    raise SystemExit(main())
