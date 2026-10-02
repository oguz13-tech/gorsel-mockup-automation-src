import json
import os
from pathlib import Path

BASE_DIR = Path(r"C:\Users\oguzc\OneDrive\Masaüstü\GörselÜretme-ve-Mockup Otomasyonu")
MOTOR_DIR = BASE_DIR / "99_SISTEM_MOTORLARI_VE_KODLAR" / "SISTEM_MOTORU"

FULL_BACKUP_PATH = MOTOR_DIR / "ayarlar.json.user_backup_20260920_000450"
TRUNCATED_EDITED_PATH = MOTOR_DIR / "ayarlar.json.user_backup_20260920_001352"
DEST_PATH = MOTOR_DIR / "ayarlar.json"

with open(FULL_BACKUP_PATH, "r", encoding="utf-8") as f:
    full_data = json.load(f)

with open(TRUNCATED_EDITED_PATH, "r", encoding="utf-8") as f:
    edited_data = json.load(f)

edits_found = 0

for cat_name, cat_data in edited_data.get("kategoriler", {}).items():
    if cat_name not in full_data.get("kategoriler", {}):
        continue
    
    for tmpl_name, tmpl_conf in cat_data.get("sablonlar", {}).items():
        if tmpl_name in full_data["kategoriler"][cat_name]["sablonlar"]:
            orig_conf = full_data["kategoriler"][cat_name]["sablonlar"][tmpl_name]
            
            # Compare koseler (perspective)
            if "koseler" in tmpl_conf and "koseler" in orig_conf:
                if str(tmpl_conf["koseler"]) != str(orig_conf["koseler"]):
                    full_data["kategoriler"][cat_name]["sablonlar"][tmpl_name]["koseler"] = tmpl_conf["koseler"]
                    edits_found += 1
            
            # Compare x,y,w,h (flat)
            if tmpl_conf.get("tip") == "duz" and orig_conf.get("tip") == "duz":
                if tmpl_conf.get("x") != orig_conf.get("x") or tmpl_conf.get("w") != orig_conf.get("w"):
                    full_data["kategoriler"][cat_name]["sablonlar"][tmpl_name]["x"] = tmpl_conf.get("x", orig_conf.get("x"))
                    full_data["kategoriler"][cat_name]["sablonlar"][tmpl_name]["y"] = tmpl_conf.get("y", orig_conf.get("y"))
                    full_data["kategoriler"][cat_name]["sablonlar"][tmpl_name]["w"] = tmpl_conf.get("w", orig_conf.get("w"))
                    full_data["kategoriler"][cat_name]["sablonlar"][tmpl_name]["h"] = tmpl_conf.get("h", orig_conf.get("h"))
                    edits_found += 1

with open(DEST_PATH, "w", encoding="utf-8") as f:
    json.dump(full_data, f, ensure_ascii=False, indent=2)

print(f"Bitti. Kullanıcının yaptığı toplam {edits_found} adet revize başarıyla orijinal veritabanına aktarıldı.")
