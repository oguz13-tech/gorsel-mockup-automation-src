from __future__ import annotations

import os
from pathlib import Path
from typing import Dict


PATHS: Dict[str, str] = {
    "KAGGLE_APPROVAL_INBOX": "0_KAGGLE_ONAY_BEKLEYENLER",
    "MASTER_DESIGN_INPUT": "1_GELEN_KAGGLE_BASKILARI",
    "WORKING_POOL": "2_SABLON_HAVUZU",
    "ORIGINAL_ARCHIVE": "2_SABLON_HAVUZU_ORIJINAL_YEDEK",
    "PRIMARY_RENDER_OUTPUT": "3_URETILEN_MOCKUPLAR",
    "EXCEL_EXPORT_OUTPUT": "4_EXCEL_YUKLEME_LISTELERI",
    "MANUAL_RENDER_INPUT": "MOCKUP A HAZIR GÖRSELLER",
    "MULTI_STORE_OUTPUT": "Mockup_Magaza_Klasorleri",
    "STAGING_INBOX": "YENI-BOS MOCKUP SABLON HAVUZU",
    "RECOVERABLE_TRASH": "SILINEN_SABLONLAR_COP_KUTUSU",
    "PROCESSING_RECOVERY": "_KURTARMA_PROCESSING",
    "SYSTEM_INTERNAL": "99_SISTEM_MOTORLARI_VE_KODLAR",
    "REVIEW_SYSTEM": "SABLON_V2_MIMARI",
}


def runtime_pointer_path() -> Path:
    local_app_data = str(os.environ.get("LOCALAPPDATA") or "").strip()
    if local_app_data:
        base = Path(local_app_data).expanduser()
    else:
        base = Path.home() / ".jarvis_mockup"
    return (base / "JarvisMockup" / "runtime_workspace.txt").resolve()


def previous_runtime_pointer_path() -> Path:
    path = runtime_pointer_path()
    return path.with_name("runtime_workspace.previous.txt")


def read_runtime_pointer() -> Path | None:
    path = runtime_pointer_path()
    if not path.is_file():
        return None
    try:
        raw = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not raw:
        return None
    candidate = Path(raw).expanduser().resolve()
    if (
        candidate
        / PATHS["REVIEW_SYSTEM"]
        / "ayarlar.db"
    ).is_file():
        return candidate
    return None


def write_runtime_pointer(runtime_root: str | Path) -> Path:
    target = Path(runtime_root).expanduser().resolve()
    if not (
        target
        / PATHS["REVIEW_SYSTEM"]
        / "ayarlar.db"
    ).is_file():
        raise ValueError(
            "Runtime pointer hedefinde SABLON_V2_MIMARI/ayarlar.db bulunamadı."
        )

    pointer = runtime_pointer_path()
    pointer.parent.mkdir(parents=True, exist_ok=True)
    previous = previous_runtime_pointer_path()
    if pointer.is_file():
        try:
            existing = pointer.read_text(encoding="utf-8")
            previous.write_text(existing, encoding="utf-8")
        except OSError:
            pass

    temp = pointer.with_suffix(".tmp")
    temp.write_text(str(target), encoding="utf-8")
    os.replace(temp, pointer)
    return pointer


def rollback_runtime_pointer() -> Path:
    pointer = runtime_pointer_path()
    previous = previous_runtime_pointer_path()
    if not previous.is_file():
        raise FileNotFoundError("Önceki runtime pointer kaydı bulunamadı.")
    raw = previous.read_text(encoding="utf-8").strip()
    if not raw:
        raise ValueError("Önceki runtime pointer boş.")
    target = Path(raw).expanduser().resolve()
    if not (
        target
        / PATHS["REVIEW_SYSTEM"]
        / "ayarlar.db"
    ).is_file():
        raise ValueError("Önceki runtime hedefi artık geçerli değil.")
    pointer.parent.mkdir(parents=True, exist_ok=True)
    temp = pointer.with_suffix(".tmp")
    temp.write_text(str(target), encoding="utf-8")
    os.replace(temp, pointer)
    return target


def resolve_runtime_root(source_root: str | Path | None = None) -> Path:
    override = str(os.environ.get("MOCKUP_RUNTIME_WORKSPACE") or "").strip()
    if override:
        return Path(override).expanduser().resolve()

    pointer = read_runtime_pointer()
    if pointer is not None:
        return pointer

    source = (
        Path(source_root).expanduser().resolve()
        if source_root is not None
        else Path(__file__).resolve().parents[2]
    )
    home = Path.home()
    candidates = [
        home / "OneDrive" / "Masaüstü" / "GörselÜretme-ve-Mockup Otomasyonu",
        home / "Desktop" / "GörselÜretme-ve-Mockup Otomasyonu",
        source,
    ]
    for candidate in candidates:
        if (
            candidate
            / PATHS["REVIEW_SYSTEM"]
            / "ayarlar.db"
        ).is_file():
            return candidate.resolve()
    return source


def runtime_path(
    logical_name: str,
    runtime_root: str | Path | None = None,
) -> Path:
    key = str(logical_name or "").strip().upper()
    if key not in PATHS:
        raise KeyError(f"Bilinmeyen Path Registry anahtarı: {logical_name}")
    root = (
        Path(runtime_root).expanduser().resolve()
        if runtime_root is not None
        else resolve_runtime_root()
    )
    return (root / PATHS[key]).resolve()


def registry_snapshot(
    runtime_root: str | Path | None = None,
) -> Dict[str, str]:
    root = (
        Path(runtime_root).expanduser().resolve()
        if runtime_root is not None
        else resolve_runtime_root()
    )
    return {
        key: str((root / relative).resolve())
        for key, relative in PATHS.items()
    }
