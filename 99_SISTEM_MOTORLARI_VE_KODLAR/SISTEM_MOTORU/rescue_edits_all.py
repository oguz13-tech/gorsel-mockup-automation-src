import json
import os
import glob
from pathlib import Path

BASE_DIR = Path(r"C:\Users\oguzc\OneDrive\Masaüstü\GörselÜretme-ve-Mockup Otomasyonu")
MOTOR_DIR = BASE_DIR / "99_SISTEM_MOTORLARI_VE_KODLAR" / "SISTEM_MOTORU"

FULL_BACKUP_PATH = MOTOR_DIR / "ayarlar.json.user_backup_20260920_000450"

with open(FULL_BACKUP_PATH, "r", encoding="utf-8") as f:
    full_data = json.load(f)

backups = glob.glob(str(MOTOR_DIR / "ayarlar.json.user_backup_*"))
backups.sort()

total_edits = 0

for b in backups:
    if "000450" in b: continue
    # only check backups after 000450
    if os.path.basename(b) < "ayarlar.json.user_backup_20260920_000450": continue
    
    with open(b, "r", encoding="utf-8") as f:
        try:
            edited_data = json.load(f)
        except:
            continue
            
    edits_found = 0
    for cat_name, cat_data in edited_data.get("kategoriler", {}).items():
        if cat_name not in full_data.get("kategoriler", {}):
            continue
        
        for tmpl_name, tmpl_conf in cat_data.get("sablonlar", {}).items():
            if tmpl_name in full_data["kategoriler"][cat_name]["sablonlar"]:
                orig_conf = full_data["kategoriler"][cat_name]["sablonlar"][tmpl_name]
                
                # Compare koseler
                if "koseler" in tmpl_conf and "koseler" in orig_conf:
                    if str(tmpl_conf["koseler"]) != str(orig_conf["koseler"]):
                        full_data["kategoriler"][cat_name]["sablonlar"][tmpl_name]["koseler"] = tmpl_conf["koseler"]
                        edits_found += 1
                        total_edits += 1

    if edits_found > 0:
        print(f"Found {edits_found} edits in {os.path.basename(b)}")

print(f"Total edits merged: {total_edits}")

with open(MOTOR_DIR / "ayarlar.json", "w", encoding="utf-8") as f:
    json.dump(full_data, f, ensure_ascii=False, indent=2)
