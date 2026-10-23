import os
import json
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [TEMİZLİK] %(message)s")
logger = logging.getLogger("TemizlikMotoru")

BASE_DIR = Path(r"C:\Users\oguzc\OneDrive\Masaüstü\GörselÜretme-ve-Mockup Otomasyonu")
SABLON_DIR = BASE_DIR / "2_SABLON_HAVUZU"
AYARLAR_PATH = BASE_DIR / "99_SISTEM_MOTORLARI_VE_KODLAR" / "SISTEM_MOTORU" / "ayarlar.json"

def clean_ayarlar():
    """Read-only diagnostic: missing cloud-backed files NEVER delete profiles.

    Intentional P0 rule: automated cleanup of ayarlar.json is permanently
    disabled. An absent OneDrive placeholder is not evidence of deletion.
    """
    if not AYARLAR_PATH.is_file():
        logger.warning("ayarlar.json bulunamadı; hiçbir dosya değiştirilmedi.")
        return {"missing": [], "status": "NO_CONFIG", "mutated": False}
    with open(AYARLAR_PATH, "r", encoding="utf-8") as handle:
        ayarlar = json.load(handle)
    missing = []
    for category, entry in ayarlar.get("kategoriler", {}).items():
        for name in entry.get("sablonlar", {}):
            source = SABLON_DIR / category / name
            if source.is_file():
                continue
            if not any((source.parent / (source.stem + ext)).is_file()
                       for ext in (".png", ".jpg", ".jpeg", ".webp", ".avif", ".bmp")):
                missing.append({"category": category, "template": name})
    logger.warning("P0 SALT-OKUNUR: %s olası eksik kayit; otomatik silme YOK.", len(missing))
    return {"missing": missing, "status": "REVIEW_REQUIRED", "mutated": False}


if __name__ == "__main__":
    clean_ayarlar()
