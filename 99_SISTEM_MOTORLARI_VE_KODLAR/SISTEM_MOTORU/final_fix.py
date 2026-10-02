import json
import shutil
from pathlib import Path

BASE_DIR = Path(r"C:\Users\oguzc\OneDrive\Masaüstü\GörselÜretme-ve-Mockup Otomasyonu")
MOTOR_DIR = BASE_DIR / "99_SISTEM_MOTORLARI_VE_KODLAR" / "SISTEM_MOTORU"
SABLON_DIR = BASE_DIR / "2_SABLON_HAVUZU"
YEDEK_DIR = BASE_DIR / "2_SABLON_HAVUZU_ORIJINAL_YEDEK"

FULL_BACKUP = MOTOR_DIR / "ayarlar.json.user_backup_20260920_000450"
DEST = MOTOR_DIR / "ayarlar.json"

with open(FULL_BACKUP, "r", encoding="utf-8") as f:
    full_data = json.load(f)

# Simple extension replacement, NO SHIFTING, NO MERGING
for cat_name, cat_data in full_data.get("kategoriler", {}).items():
    new_sablonlar = {}
    for old_name, conf in cat_data.get("sablonlar", {}).items():
        base_name = Path(old_name).stem
        new_name = f"{base_name}.png"
        new_sablonlar[new_name] = conf
    cat_data["sablonlar"] = new_sablonlar

with open(DEST, "w", encoding="utf-8") as f:
    json.dump(full_data, f, ensure_ascii=False, indent=2)

print("Tertemiz 000450 yedeği PNG'ye çevrilerek ayarlar.json'a yazıldı!")

# Ensure physical files are all PNG (in case rollback.py messed them up)
for cat_name, cat_data in full_data.get("kategoriler", {}).items():
    cat_dir = SABLON_DIR / cat_name
    yedek_dir = YEDEK_DIR / cat_name
    
    if cat_dir.exists():
        for f in cat_dir.iterdir():
            if f.is_file() and f.suffix.lower() in ['.jpg', '.jpeg', '.webp']:
                new_path = f.with_suffix('.png')
                if not new_path.exists():
                    f.rename(new_path)
                else:
                    f.unlink()
                    
    if yedek_dir.exists():
        for f in yedek_dir.iterdir():
            if f.is_file() and f.suffix.lower() in ['.jpg', '.jpeg', '.webp']:
                new_path = f.with_suffix('.png')
                if not new_path.exists():
                    f.rename(new_path)
                else:
                    f.unlink()

print("Klasörlerdeki uzantılar da PNG olarak sabitlendi.")
