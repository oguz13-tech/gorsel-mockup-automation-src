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
    if not AYARLAR_PATH.exists():
        logger.error("ayarlar.json bulunamadı!")
        return

    with open(AYARLAR_PATH, "r", encoding="utf-8") as f:
        ayarlar = json.load(f)

    kategoriler = ayarlar.get("kategoriler", {})
    silinen_toplam = 0

    for cat_key, cat_data in kategoriler.items():
        sablonlar = cat_data.get("sablonlar", {})
        cat_dir = SABLON_DIR / cat_key
        
        # Silinecek anahtarları topluyoruz
        silinecek_anahtarlar = []
        for sablon_name in sablonlar.keys():
            s_path = cat_dir / sablon_name
            
            # Ana uzantı yoksa alternatif uzantıları da kontrol et
            if not s_path.exists():
                found = False
                for alt_ext in [".webp", ".jpg", ".jpeg", ".png", ".avif", ".bmp"]:
                    cand = cat_dir / (Path(sablon_name).stem + alt_ext)
                    if cand.exists():
                        found = True
                        break
                if not found:
                    silinecek_anahtarlar.append(sablon_name)

        # Bulunamayanları JSON'dan sil
        for key in silinecek_anahtarlar:
            del sablonlar[key]
            silinen_toplam += 1
            logger.info(f"🗑️ Silindi (Klasörde Yok): [{cat_key}] -> {key}")

    if silinen_toplam > 0:
        tmp_path = AYARLAR_PATH.with_suffix('.json.tmp')
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(ayarlar, f, ensure_ascii=False, indent=4)
        os.replace(tmp_path, AYARLAR_PATH)
        logger.info(f"✅ Temizlik Tamamlandı! Toplam {silinen_toplam} adet hayalet kayıt ayarlar.json'dan silindi.")
    else:
        logger.info("✅ Her şey tertemiz! ayarlar.json içinde hayalet kayıt bulunamadı.")

if __name__ == "__main__":
    clean_ayarlar()
