import json
import os
import shutil
from pathlib import Path

BASE_DIR = Path(r"C:\Users\oguzc\OneDrive\Masaüstü\GörselÜretme-ve-Mockup Otomasyonu")
MOTOR_DIR = BASE_DIR / "99_SISTEM_MOTORLARI_VE_KODLAR" / "SISTEM_MOTORU"
SABLON_DIR = BASE_DIR / "2_SABLON_HAVUZU"
YEDEK_DIR = BASE_DIR / "2_SABLON_HAVUZU_ORIJINAL_YEDEK"

BACKUP_JSON = MOTOR_DIR / "ayarlar.json.user_backup_20260920_000450"
TARGET_JSON = MOTOR_DIR / "ayarlar.json"

if not BACKUP_JSON.exists():
    print("Backup not found.")
    exit(1)

with open(BACKUP_JSON, "r", encoding="utf-8") as f:
    data = json.load(f)

# Restore JSON immediately
shutil.copy2(BACKUP_JSON, TARGET_JSON)

# Rollback files
for cat_name, cat_data in data.get("kategoriler", {}).items():
    sablonlar = cat_data.get("sablonlar", {})
    
    cat_dir = SABLON_DIR / cat_name
    yedek_dir = YEDEK_DIR / cat_name
    
    for tmpl_name in sablonlar.keys():
        if tmpl_name.lower().endswith(".png"):
            continue # Was already png, no rollback needed
            
        base_name = Path(tmpl_name).stem
        png_name = f"{base_name}.png"
        
        png_path = cat_dir / png_name
        orig_path = cat_dir / tmpl_name
        
        if png_path.exists() and not orig_path.exists():
            # Rename back to original extension
            try:
                png_path.rename(orig_path)
            except Exception as e:
                print(f"Failed to rename {png_path}: {e}")
                
        # Do the same for yedek
        png_yedek = yedek_dir / png_name
        orig_yedek = yedek_dir / tmpl_name
        
        if png_yedek.exists() and not orig_yedek.exists():
            try:
                png_yedek.rename(orig_yedek)
            except Exception as e:
                print(f"Failed to rename yedek {png_yedek}: {e}")

print("Tüm görseller ve veritabanı orijinal hallerine (00:04 durumuna) tam olarak geri yüklendi.")
