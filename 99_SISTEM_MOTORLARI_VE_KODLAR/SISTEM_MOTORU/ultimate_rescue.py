import json
import os
import shutil
from pathlib import Path

BASE_DIR = Path(r"C:\Users\oguzc\OneDrive\Masaüstü\GörselÜretme-ve-Mockup Otomasyonu")
MOTOR_DIR = BASE_DIR / "99_SISTEM_MOTORLARI_VE_KODLAR" / "SISTEM_MOTORU"
SABLON_DIR = BASE_DIR / "2_SABLON_HAVUZU"
YEDEK_DIR = BASE_DIR / "2_SABLON_HAVUZU_ORIJINAL_YEDEK"

FULL_BACKUP = MOTOR_DIR / "ayarlar.json.user_backup_20260920_000450"
USER_EDITS = MOTOR_DIR / "ayarlar.json.user_backup_20260920_001352"
DEST = MOTOR_DIR / "ayarlar.json"

with open(FULL_BACKUP, "r", encoding="utf-8") as f:
    full_data = json.load(f)
    
with open(USER_EDITS, "r", encoding="utf-8") as f:
    user_edits = json.load(f)

# Step 1: Normalize FULL_BACKUP keys to .png
for cat_name, cat_data in full_data.get("kategoriler", {}).items():
    new_sablonlar = {}
    for old_name, conf in cat_data.get("sablonlar", {}).items():
        base_name = Path(old_name).stem
        new_name = f"{base_name}.png"
        new_sablonlar[new_name] = conf
    cat_data["sablonlar"] = new_sablonlar

# Step 2: Merge User Edits from 001352 (which already has .png keys)
merged_count = 0
for cat_name, cat_data in user_edits.get("kategoriler", {}).items():
    if cat_name not in full_data.get("kategoriler", {}):
        full_data.setdefault("kategoriler", {})[cat_name] = {"sablonlar": {}}
        
    for tmpl_name, conf in cat_data.get("sablonlar", {}).items():
        # Overwrite the template in full_data with the user's latest edited template!
        full_data["kategoriler"][cat_name]["sablonlar"][tmpl_name] = conf
        merged_count += 1

with open(DEST, "w", encoding="utf-8") as f:
    json.dump(full_data, f, ensure_ascii=False, indent=2)

print(f"Başarılı! 000450 tabanlı ana veritabanı PNG'ye çevrildi. Üzerine 001352'deki {merged_count} adet kullanıcı düzenlemesi yazıldı.")

# Step 3: Ensure physical files are .png
for cat_name, cat_data in full_data.get("kategoriler", {}).items():
    cat_dir = SABLON_DIR / cat_name
    yedek_dir = YEDEK_DIR / cat_name
    
    if not cat_dir.exists(): continue
    
    for f in cat_dir.iterdir():
        if f.is_file() and f.suffix.lower() in ['.jpg', '.jpeg', '.webp']:
            new_path = f.with_suffix('.png')
            if not new_path.exists():
                f.rename(new_path)
            else:
                f.unlink() # duplicate old extension
                
    if not yedek_dir.exists(): continue
    for f in yedek_dir.iterdir():
        if f.is_file() and f.suffix.lower() in ['.jpg', '.jpeg', '.webp']:
            new_path = f.with_suffix('.png')
            if not new_path.exists():
                f.rename(new_path)
            else:
                f.unlink()
