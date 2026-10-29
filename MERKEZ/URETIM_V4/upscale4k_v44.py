"""Optional, OFF-by-default, commercial mockup post-processing via Real-ESRGAN NCNN.

This module never modifies source/template art, approved geometry, the normal
render output, or its production ledger. Upscaled images have independent
create-only names and SHA receipts. A missing executable is a visible error;
we never pretend that plain resizing is AI upscaling.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
from typing import Callable

from PIL import Image

MODELS = {
    "photo": "realesrgan-x4plus",
    "fast": "realesr-general-x4v3",
}
TARGET = (2880, 3840)  # Portrait 3:4, 3840 px long edge.
RECIPE = "v44-real-esrgan-ncnn-4k-20261023"


class UpscaleError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _checked_file(p: Path, *, what: str) -> Path:
    p = Path(p)
    if p.is_symlink() or not p.is_file() or p.stat().st_size <= 0:
        raise UpscaleError(f"{what} yok ya da güvensiz: {p}")
    return p.resolve(strict=True)


def find_engine(explicit: Path | str | None = None) -> Path:
    """Only an executable supplied/installed by the operator; no download."""
    if explicit:
        return _checked_file(Path(explicit), what="Real-ESRGAN çalıştırıcısı")
    env = os.environ.get("REAL_ESRGAN_EXE", "").strip()
    if env:
        return _checked_file(Path(env), what="REAL_ESRGAN_EXE")
    repo = Path(__file__).resolve().parents[2]
    options = [
        repo / "AI_Kalite_Artirici" / "realesrgan-ncnn-vulkan.exe",
        repo / "AI_Kalite_Artirici" / "realesrgan-ncnn-vulkan",
        repo / "models" / "realesrgan-ncnn-vulkan.exe",
    ]
    from shutil import which
    system = which("realesrgan-ncnn-vulkan")
    if system:
        options.append(Path(system))
    for item in options:
        if item.is_file() and not item.is_symlink():
            return item.resolve(strict=True)
    raise UpscaleError(
        "Real-ESRGAN çalıştırıcısı bulunamadı. 4K isteğe bağlıdır; "
        "resmî realesrgan-ncnn-vulkan.exe ve models klasörünü kurun, "
        "sonra REAL_ESRGAN_EXE ortam değişkeniyle yolunu gösterin. "
        "Yalnızca normal üretime devam etmek için 4K kutusunun işaretini kaldırın."
    )


def preflight(*, enabled: bool, model: str = "photo", exe: Path | str | None = None) -> Path | None:
    if not enabled:
        return None
    if model not in MODELS:
        raise UpscaleError("Geçersiz 4K yükseltici profili.")
    found = find_engine(exe)
    directory = found.parent / "models"
    # NCNN official models are shipped next to exe in `models`.
    stem = MODELS[model]
    if any(not (directory / f"{stem}.{ext}").is_file() or (directory / f"{stem}.{ext}").is_symlink()
           or (directory / f"{stem}.{ext}").stat().st_size == 0
           for ext in ("bin", "param")):
        raise UpscaleError(f"Real-ESRGAN modeli eksik: {stem}.bin/.param; beklenen klasör: {directory}")
    return found


def process(
    records: list[dict], *, state_root: Path, enabled: bool = False,
    model: str = "photo", exe: Path | str | None = None,
    cancel: threading.Event | None = None,
    notify: Callable[[str], None] | None = None,
) -> dict:
    """Enhance only this batch's *newly rendered* SHA-verified images.

    An already-produced 4K output will be reused only when its atomic receipt
    and actual SHA match the input/model/recipe. Any problem is surfaced without
    modifying the base production ledger. No external cloud calls.
    """
    if not enabled:
        return {"status": "DISABLED", "upscaled": 0, "failed": 0, "reused": 0}
    notify = notify or (lambda _: None)
    engine = preflight(enabled=True, model=model, exe=exe)
    assert engine is not None
    state_root = Path(state_root).resolve()
    output_root = state_root / "uretilen_gorseller_4k"
    report_root = state_root / "raporlar" / "4k"
    for base in (output_root, report_root):
        if base.is_symlink():
            raise UpscaleError(f"4K klasörü sembolik bağlantı olamaz: {base}")
        base.mkdir(parents=True, exist_ok=True)
    result = {"status": "DONE", "upscaled": 0, "failed": 0, "reused": 0, "errors": [], "items": [], "report": ""}
    for row in records:
        if cancel is not None and cancel.is_set():
            result["status"] = "STOPPED"
            break
        try:
            source = _checked_file(Path(row["output"]), what="Asıl üretim görseli")
            if state_root not in source.parents:
                raise UpscaleError("4K girişi V4 çalışma alanı dışında. Reddedildi.")
            original_sha = str(row["output_sha"])
            if sha256(source) != original_sha:
                raise UpscaleError("Normal çıktı SHA-256 eşleşmiyor; 4K uygulanmadı.")
            with Image.open(source) as opened:
                if opened.size != (1200, 1600):
                    raise UpscaleError(f"4K için 3:4/1200×1600 üretim bekleniyor, mevcut: {opened.size}")
            recipe = {"source_sha256": original_sha, "source_key": str(row["key"]),
                      "sku": str(row["sku"]), "model": MODELS[model], "recipe": RECIPE,
                      "target": list(TARGET)}
            digest = hashlib.sha256(json.dumps(recipe, sort_keys=True).encode()).hexdigest()[:24]
            # SHA-based basename; no user-controlled path components.
            output = output_root / f"{digest}_4k.png"
            receipt = report_root / f"{digest}.json"
            if output.exists() or receipt.exists() or output.is_symlink() or receipt.is_symlink():
                if output.is_symlink() or receipt.is_symlink() or not output.is_file() or not receipt.is_file():
                    raise UpscaleError("Var olan 4K çıktı/makbuz güvenli değil; üzerine yazılmadı.")
                metadata = json.loads(receipt.read_text(encoding="utf-8"))
                if metadata.get("recipe") != recipe or metadata.get("output_sha256") != sha256(output):
                    raise UpscaleError("4K makbuz/SHA tutarsız; eski dosya korunuyor, inceleme gerekli.")
                result["reused"] += 1
                result["items"].append(metadata)
                continue
            with tempfile.TemporaryDirectory(prefix="upscale_", dir=output_root) as scratch:
                trial = Path(scratch) / "enhanced.png"
                cmd = [str(engine), "-i", str(source), "-o", str(trial),
                       "-n", MODELS[model], "-s", "4", "-t", "200", "-f", "png",
                       "-m", str(engine.parent / "models")]
                completed = subprocess.run(cmd, capture_output=True, text=True,
                                           errors="replace", timeout=600, check=False)
                if completed.returncode:
                    raise UpscaleError(f"Real-ESRGAN kod={completed.returncode}: {(completed.stderr or completed.stdout)[-500:]}")
                _checked_file(trial, what="Yükseltme sonucu")
                with Image.open(trial) as im:
                    im.load()
                    if im.width < TARGET[0] or im.height < TARGET[1]:
                        raise UpscaleError("AI çıktısı 4K hedef boyutundan küçük; yükseltme başarısız.")
                    rgb = im.convert("RGB")
                    scaled = rgb.resize(TARGET, Image.Resampling.LANCZOS)
                    final = Path(scratch) / "final_4k.png"
                    scaled.save(final, format="PNG")
                if sha256(source) != original_sha:
                    raise UpscaleError("Asıl çıktı işlem sırasında değişti; yükseltilen sürüm kullanılmadı.")
                final_sha = sha256(final)
                # Atomic create-only: same-volume hard-link; existing outputs are never replaced.
                try:
                    os.link(final, output)
                except FileExistsError as ex:
                    raise UpscaleError("4K çıktı yarış nedeniyle oluştu, üzerine yazılmadı.") from ex
            metadata = {"recipe": recipe, "source_output": str(source),
                        "output": str(output), "output_sha256": final_sha,
                        "status": "VERIFIED_4K"}
            raw = json.dumps(metadata, indent=2, ensure_ascii=False, sort_keys=True).encode("utf-8")
            # A process interruption between file and receipt needs explicit review, never overwrite.
            with receipt.open("xb") as f:
                f.write(raw)
                f.flush()
                os.fsync(f.fileno())
            result["items"].append(metadata)
            result["upscaled"] += 1
            notify(f"4K hazır: {row['sku']} → {output.name}")
        except (OSError, ValueError, KeyError, UpscaleError, subprocess.TimeoutExpired) as exc:
            result["failed"] += 1
            result["errors"].append({"sku": str(row.get("sku", "?")), "reason": str(exc)})
            notify(f"4K ATLANDI {row.get('sku', '?')}: {exc}")
    if result["failed"]:
        result["status"] = "PARTIAL_4K" if result["status"] != "STOPPED" else "STOPPED"
    # 4K verification remains in the per-output JSON receipts. The unified
    # marketplace workbook is the only Excel export; a duplicate 4K workbook
    # caused two competing product-link reports.
    return result
