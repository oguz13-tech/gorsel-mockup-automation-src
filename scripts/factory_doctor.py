#!/usr/bin/env python3
"""CLI wrapper for the read-only mockup Factory Doctor."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parents[1]
ARCH_DIR = SOURCE_ROOT / "SABLON_V2_MIMARI"
if str(ARCH_DIR) not in sys.path:
    sys.path.insert(0, str(ARCH_DIR))

from core.factory_doctor import run_factory_doctor


def parse_args():
    parser = argparse.ArgumentParser(
        description="Mockup fabrikasını değiştirmeden bütünlük taraması yap."
    )
    parser.add_argument(
        "--runtime",
        default=str(os.environ.get("MOCKUP_RUNTIME_WORKSPACE") or "").strip(),
        help="Runtime workspace. Varsayılan: MOCKUP_RUNTIME_WORKSPACE.",
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Dosya SHA taramasını atlayarak hızlı kontrol yap.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    runtime = str(args.runtime or "").strip()
    if not runtime:
        print(
            "HATA: Runtime workspace belirtilmedi. "
            "MOCKUP_RUNTIME_WORKSPACE ayarlayın veya --runtime kullanın."
        )
        return 2

    report = run_factory_doctor(
        runtime,
        source_root=SOURCE_ROOT,
        deep=not args.fast,
    )

    print("=" * 72)
    print("JARVIS MOCKUP FACTORY DOCTOR")
    print("=" * 72)
    print(f"Runtime : {report['checks'].get('runtime_root', runtime)}")
    print(
        f"Sonuç   : {'READY' if report['ready'] else 'BLOCKED'} | "
        f"Kritik={report['error_count']} | Uyarı={report['warning_count']}"
    )

    if report["errors"]:
        print("\nKRİTİK:")
        for item in report["errors"]:
            print(f"  ❌ [{item['code']}] {item['message']}")

    if report["warnings"]:
        print("\nUYARILAR:")
        for item in report["warnings"]:
            print(f"  ⚠️ [{item['code']}] {item['message']}")

    if not report["errors"] and not report["warnings"]:
        print("\n✅ Kritik sorun veya uyarı bulunmadı.")

    print(
        "\nDOCTOR_JSON="
        + json.dumps(
            report,
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )
    return 0 if report["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
