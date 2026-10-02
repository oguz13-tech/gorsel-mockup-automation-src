import os
import json
import cv2
import numpy as np
from pathlib import Path

BASE_DIR = Path(r"C:\Users\oguzc\OneDrive\Masaüstü\GörselÜretme-ve-Mockup Otomasyonu")
AYARLAR_PATH = BASE_DIR / "99_SISTEM_MOTORLARI_VE_KODLAR" / "SISTEM_MOTORU" / "ayarlar.json"
SABLON_DIR = BASE_DIR / "2_SABLON_HAVUZU"
YEDEK_DIR = BASE_DIR / "2_SABLON_HAVUZU_ORIJINAL_YEDEK"

def imread_unicode(path: Path) -> np.ndarray:
    try:
        if path.exists():
            return cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    except Exception:
        pass
    return None

def imwrite_unicode(path: Path, img: np.ndarray) -> bool:
    try:
        success, encoded = cv2.imencode('.png', img)
        if success:
            encoded.tofile(str(path))
            return True
    except Exception:
        pass
    return False

def get_next_available_name(cat_dir: Path, prefix: str) -> str:
    existing = set()
    for f in cat_dir.glob(f"{prefix}_*.png"):
        try:
            num = int(f.stem.replace(f"{prefix}_", ""))
            existing.add(num)
        except:
            pass
    idx = 1
    while idx in existing:
        idx += 1
    return f"{prefix}_{idx:03d}.png"

def convert_file(src: Path, dest: Path) -> bool:
    if not src.exists():
        return False
    img = imread_unicode(src)
    if img is not None:
        if imwrite_unicode(dest, img):
            src.unlink() # Delete old file
            return True
    return False

def migrate_to_png():
    if not AYARLAR_PATH.exists():
        print("ayarlar.json bulunamadı.")
        return

    with open(AYARLAR_PATH, "r", encoding="utf-8") as f:
        ayarlar = json.load(f)

    kategoriler = ayarlar.get("kategoriler", {})
    changes_made = False

    for cat_key, cat_data in kategoriler.items():
        sablonlar = cat_data.get("sablonlar", {})
        new_sablonlar = {}
        
        cat_dir = SABLON_DIR / cat_key
        yedek_cat_dir = YEDEK_DIR / cat_key
        
        cat_dir.mkdir(parents=True, exist_ok=True)
        yedek_cat_dir.mkdir(parents=True, exist_ok=True)
        
        # Determine prefix
        prefix = cat_key
        if cat_key == "01_Wifi_Kutusu": prefix = "Wifi_Kutusu"
        elif cat_key == "02_Cam_Tablo_Dikey": prefix = "CamTabloDikey"
        elif cat_key == "02_Cam_Tablo_Yatay": prefix = "CamTabloYatay"
        elif cat_key == "03_Ahsap_Tablo": prefix = "AhsapTablo"
        elif cat_key == "04_Cam_Dograma": prefix = "CamDograma"
        elif cat_key == "05_Ocak_Arkasi": prefix = "OcakArkasi"

        for old_name, conf in sablonlar.items():
            if old_name.lower().endswith(".png"):
                new_sablonlar[old_name] = conf
                continue
                
            print(f"Dönüştürülüyor: {old_name}")
            
            # Find a new name
            # If the base name doesn't exist as .png, use it. Otherwise find a new one.
            base_name = Path(old_name).stem
            candidate_name = f"{base_name}.png"
            
            if (cat_dir / candidate_name).exists() or (yedek_cat_dir / candidate_name).exists() or candidate_name in new_sablonlar:
                candidate_name = get_next_available_name(cat_dir, prefix)
                
            new_name = candidate_name
            
            # Convert in SABLON_HAVUZU
            old_path = cat_dir / old_name
            new_path = cat_dir / new_name
            if old_path.exists():
                convert_file(old_path, new_path)
                
            # Convert in YEDEK
            old_yedek = yedek_cat_dir / old_name
            new_yedek = yedek_cat_dir / new_name
            if old_yedek.exists():
                convert_file(old_yedek, new_yedek)
                
            new_sablonlar[new_name] = conf
            changes_made = True

        cat_data["sablonlar"] = new_sablonlar

    if changes_made:
        with open(AYARLAR_PATH, "w", encoding="utf-8") as f:
            json.dump(ayarlar, f, ensure_ascii=False, indent=2)
        print("Tüm eski uzantılar PNG formatına dönüştürüldü ve JSON güncellendi.")
    else:
        print("Dönüştürülecek eski uzantı bulunamadı.")

if __name__ == "__main__":
    migrate_to_png()
