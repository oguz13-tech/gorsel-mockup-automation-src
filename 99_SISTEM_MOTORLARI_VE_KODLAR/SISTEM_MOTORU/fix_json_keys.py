# P0 SAFETY GATE: historical script retained but can never mutate live data.
# See scripts/legacy_recovery_preview.py for the safe, read-only preview.
import sys as _p0_sys
from pathlib import Path as _p0_Path
_p0_sys.path.insert(0, str(_p0_Path(__file__).resolve().parents[2]))
from scripts.legacy_recovery_preview import main as _p0_legacy_preview
raise SystemExit(_p0_legacy_preview("fix_json_keys", _p0_sys.argv[1:]))

# HISTORICAL / UNREACHABLE: dangerous legacy implementation retained below.
import json
from pathlib import Path

BASE_DIR = Path(r"C:\Users\oguzc\OneDrive\Masaüstü\GörselÜretme-ve-Mockup Otomasyonu")
AYARLAR = BASE_DIR / "99_SISTEM_MOTORLARI_VE_KODLAR" / "SISTEM_MOTORU" / "ayarlar.json"

with open(AYARLAR, "r", encoding="utf-8") as f:
    data = json.load(f)

for cat_name, cat_data in data.get("kategoriler", {}).items():
    old_sablonlar = cat_data.get("sablonlar", {})
    new_sablonlar = {}
    
    for old_name, conf in old_sablonlar.items():
        base_name = Path(old_name).stem
        new_name = f"{base_name}.png"
        
        # If there's a collision (e.g. both .webp and .jpeg existed with same base), we just keep one or rename
        if new_name in new_sablonlar:
            new_name = f"{base_name}_duplicate.png"
            
        new_sablonlar[new_name] = conf
        
    cat_data["sablonlar"] = new_sablonlar

with open(AYARLAR, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print("Veritabanı anahtarları zorla PNG olarak güncellendi.")
