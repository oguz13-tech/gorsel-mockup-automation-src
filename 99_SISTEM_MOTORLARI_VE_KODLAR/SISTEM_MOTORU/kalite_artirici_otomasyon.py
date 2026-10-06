# -*- coding: utf-8 -*-
"""Independent Real-ESRGAN power tool.

This tool is intentionally OUTSIDE the factory artifact pipeline:
- originals are never overwritten;
- directory structure is preserved;
- existing high-resolution files are copied byte-for-byte by default;
- AI results are written atomically and basic geometry/readability QA is run.

Use the integrated factory RealESRGAN path for normal production. Use this tool
for deliberate, independent enhancement jobs.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import cv2
import numpy as np


SOURCE_ROOT = Path(__file__).resolve().parent.parent.parent
_runtime_override = str(
    os.environ.get("MOCKUP_RUNTIME_WORKSPACE") or ""
).strip()
RUNTIME_ROOT = (
    Path(_runtime_override).expanduser().resolve()
    if _runtime_override
    else SOURCE_ROOT.resolve()
)

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def _find_realesrgan() -> Path | None:
    candidates = [
        RUNTIME_ROOT / "AI_Kalite_Artirici" / "realesrgan-ncnn-vulkan.exe",
        SOURCE_ROOT / "AI_Kalite_Artirici" / "realesrgan-ncnn-vulkan.exe",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def _read_image(path: Path):
    try:
        return cv2.imdecode(
            np.fromfile(str(path), dtype=np.uint8),
            cv2.IMREAD_COLOR,
        )
    except Exception:
        return None


def _basic_output_valid(source_cv, candidate_cv) -> tuple[bool, str]:
    if source_cv is None:
        return False, "kaynak okunamıyor"
    if candidate_cv is None:
        return False, "AI çıktısı okunamıyor"

    sh, sw = source_cv.shape[:2]
    ch, cw = candidate_cv.shape[:2]
    if min(cw, ch) <= 0:
        return False, "AI çıktı boyutu geçersiz"
    if cw < sw or ch < sh:
        return False, f"AI çıktı küçülmüş: {cw}x{ch} < {sw}x{sh}"

    src_aspect = sw / float(max(sh, 1))
    out_aspect = cw / float(max(ch, 1))
    aspect_error = abs(out_aspect - src_aspect) / max(src_aspect, 1e-6)
    if aspect_error > 0.01:
        return False, (
            f"en-boy oranı değişmiş: {src_aspect:.4f} -> {out_aspect:.4f}"
        )

    gray = cv2.cvtColor(candidate_cv, cv2.COLOR_BGR2GRAY)
    if float(np.std(gray)) < 3.0:
        return False, "AI çıktı neredeyse tek renk"
    return True, f"{sw}x{sh} -> {cw}x{ch}"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Bağımsız Real-ESRGAN 4K/AI kalite power tool."
    )
    parser.add_argument(
        "--input",
        default=str(RUNTIME_ROOT / "3_URETILEN_MOCKUPLAR"),
        help="Kaynak görsel veya klasör.",
    )
    parser.add_argument(
        "--output",
        default=str(RUNTIME_ROOT / "4K_POWER_TOOL_OUTPUT"),
        help="Ayrı çıktı klasörü. Orijinaller değiştirilmez.",
    )
    parser.add_argument(
        "--force-ai",
        action="store_true",
        help=(
            "Zaten yüksek çözünürlüklü dosyalara da AI x4 uygula. "
            "Çok fazla VRAM/disk kullanabilir."
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Mevcut power-tool çıktısını yeniden üret.",
    )
    parser.add_argument(
        "--highres-threshold",
        type=int,
        default=3840,
        help=(
            "Uzun kenarı bu değere ulaşan görseller normalde byte-for-byte "
            "kopyalanır. Varsayılan 3840."
        ),
    )
    parser.add_argument(
        "--tile",
        type=int,
        default=400,
        help="Real-ESRGAN tile boyutu. Varsayılan 400.",
    )
    return parser.parse_args()


def _collect_files(input_path: Path, output_root: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path] if input_path.suffix.lower() in IMAGE_EXTS else []
    if not input_path.is_dir():
        return []

    output_resolved = output_root.resolve()
    files = []
    for path in input_path.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in IMAGE_EXTS:
            continue
        try:
            resolved = path.resolve()
            if (
                resolved == output_resolved
                or output_resolved in resolved.parents
            ):
                continue
        except Exception:
            pass
        files.append(path)
    return sorted(files)


def main() -> int:
    args = parse_args()
    input_path = Path(args.input).expanduser().resolve()
    output_root = Path(args.output).expanduser().resolve()
    exe = _find_realesrgan()

    print("=" * 78)
    print(" REAL-ESRGAN 4K / AI KALITE POWER TOOL")
    print("=" * 78)
    print(f"Kaynak : {input_path}")
    print(f"Çıktı  : {output_root}")
    print("Kural  : Orijinaller ASLA değiştirilmez.")
    print("=" * 78)

    if not input_path.exists():
        print(f"HATA: Kaynak bulunamadı: {input_path}")
        return 2

    files = _collect_files(input_path, output_root)
    if not files:
        print("İşlenecek görsel bulunamadı.")
        return 0

    if exe is None and any(
        args.force_ai
        or max((_read_image(path) or np.zeros((1, 1, 3))).shape[:2])
        < args.highres_threshold
        for path in files
    ):
        print(
            "HATA: realesrgan-ncnn-vulkan.exe bulunamadı. "
            "AI_Kalite_Artirici klasörünü kontrol edin."
        )
        return 2

    output_root.mkdir(parents=True, exist_ok=True)
    success_count = 0
    skipped_count = 0
    failed_count = 0

    input_is_file = input_path.is_file()
    input_root = input_path.parent if input_is_file else input_path

    for index, source in enumerate(files, start=1):
        relative = (
            Path(source.name)
            if input_is_file
            else source.relative_to(input_root)
        )
        destination = output_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)

        if destination.exists() and not args.force:
            print(
                f"[{index}/{len(files)}] Atlandı (çıktı var): "
                f"{relative}"
            )
            skipped_count += 1
            continue

        source_cv = _read_image(source)
        if source_cv is None:
            print(
                f"[{index}/{len(files)}] HATA okunamadı: {relative}"
            )
            failed_count += 1
            continue

        h, w = source_cv.shape[:2]
        long_edge = max(w, h)

        if long_edge >= args.highres_threshold and not args.force_ai:
            tmp_copy = destination.with_name(
                destination.name + ".copying"
            )
            try:
                shutil.copy2(source, tmp_copy)
                os.replace(tmp_copy, destination)
                print(
                    f"[{index}/{len(files)}] Yüksek çözünürlük "
                    f"({w}x{h}) -> kalite kaybı olmadan kopyalandı: "
                    f"{relative}"
                )
                success_count += 1
            except Exception as exc:
                print(f"[{index}/{len(files)}] Kopyalama HATASI: {exc}")
                failed_count += 1
                try:
                    tmp_copy.unlink(missing_ok=True)
                except OSError:
                    pass
            continue

        if exe is None:
            print(
                f"[{index}/{len(files)}] HATA: Real-ESRGAN yok: "
                f"{relative}"
            )
            failed_count += 1
            continue

        models_dir = exe.parent / "models"
        tmp_output = destination.with_name(
            destination.stem + ".ai-writing" + destination.suffix
        )
        cmd = [
            str(exe),
            "-i", str(source),
            "-o", str(tmp_output),
            "-m", str(models_dir),
            "-n", "realesrgan-x4plus",
            "-s", "4",
            "-t", str(max(int(args.tile), 32)),
        ]

        print(
            f"[{index}/{len(files)}] AI x4: "
            f"{relative} ({w}x{h})"
        )
        started = time.time()
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            candidate_cv = _read_image(tmp_output)
            valid, message = _basic_output_valid(
                source_cv,
                candidate_cv,
            )
            if result.returncode != 0 or not valid:
                print(
                    f"   -> REDDEDİLDİ: {message} "
                    f"(exit={result.returncode})"
                )
                failed_count += 1
                continue

            os.replace(tmp_output, destination)
            elapsed = time.time() - started
            print(
                f"   -> Başarılı: {message} | {elapsed:.1f} sn | "
                f"{destination}"
            )
            success_count += 1
        except Exception as exc:
            print(f"   -> HATA: {exc}")
            failed_count += 1
        finally:
            try:
                tmp_output.unlink(missing_ok=True)
            except OSError:
                pass

    print("\n" + "=" * 78)
    print(
        f"BİTTİ | başarılı={success_count} | "
        f"atlandı={skipped_count} | hatalı={failed_count}"
    )
    print(f"Çıktı: {output_root}")
    print("=" * 78)
    return 0 if failed_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
