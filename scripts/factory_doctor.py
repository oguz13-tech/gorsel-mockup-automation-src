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



def _safe_console_print(value: str = "") -> None:
    """Escape unsupported glyphs on Windows legacy consoles, preserving output."""
    value = str(value)
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    try:
        display = value.encode(encoding, errors="backslashreplace").decode(encoding)
    except LookupError:
        display = value.encode("ascii", errors="backslashreplace").decode("ascii")
    sys.stdout.write(display + "\n")


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
        _safe_console_print(
            "HATA: Runtime workspace belirtilmedi. "
            "MOCKUP_RUNTIME_WORKSPACE ayarlayın veya --runtime kullanın."
        )
        return 2

    report = run_factory_doctor(
        runtime,
        source_root=SOURCE_ROOT,
        deep=not args.fast,
    )

    _safe_console_print("=" * 72)
    _safe_console_print("JARVIS MOCKUP FACTORY DOCTOR")
    _safe_console_print("=" * 72)
    _safe_console_print(f"Runtime : {report['checks'].get('runtime_root', runtime)}")
    _safe_console_print(
        f"Sonuç   : {'READY' if report['ready'] else 'BLOCKED'} | "
        f"Kritik={report['error_count']} | Uyarı={report['warning_count']}"
    )

    if report["errors"]:
        _safe_console_print("\nKRİTİK:")
        for item in report["errors"]:
            _safe_console_print(f"  ❌ [{item['code']}] {item['message']}")

    if report["warnings"]:
        _safe_console_print("\nUYARILAR:")
        for item in report["warnings"]:
            _safe_console_print(f"  ⚠️ [{item['code']}] {item['message']}")

    if not report["errors"] and not report["warnings"]:
        _safe_console_print("\n✅ Kritik sorun veya uyarı bulunmadı.")

    _safe_console_print(
        "\nDOCTOR_JSON="
        + json.dumps(
            report,
            ensure_ascii=True,
            separators=(",", ":"),
        )
    )
    return 0 if report["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
