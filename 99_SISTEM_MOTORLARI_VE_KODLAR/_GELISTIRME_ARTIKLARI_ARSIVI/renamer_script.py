import os
import json
import shutil
from pathlib import Path

base_dir = Path(r'C:\Users\oguzc\OneDrive\Masaüstü\GörselÜretme-ve-Mockup Otomasyonu')
sablon_dir = base_dir / "2_SABLON_HAVUZU"
ayarlar_path = base_dir / "SISTEM_MOTORU" / "ayarlar.json"
backup_path = base_dir / "SISTEM_MOTORU" / "ayarlar_yedek_renamer.json"

# Yedek al
shutil.copy2(ayarlar_path, backup_path)

with open(ayarlar_path, "r", encoding="utf-8") as f:
    ayarlar = json.load(f)

prefixes = {
    "01_Wifi_Kutusu": "Wifi_Kutusu",
    "02_Cam_Tablo_Dikey": "CamTabloDikey",
    "02_Cam_Tablo_Yatay": "CamTabloYatay",
    "03_Ahsap_Tablo": "AhsapTablo",
    "04_Cam_Dograma": "CamDograma",
    "05_Ocak_Arkasi": "OcakArkasi"
}

kategoriler = ayarlar.get("kategoriler", {})
total_renamed = 0

for cat_folder, prefix in prefixes.items():
    cat_dir = sablon_dir / cat_folder
    if not cat_dir.exists():
        continue
        
    cat_config = kategoriler.get(cat_folder, {})
    sablon_config = cat_config.get("sablonlar", {})
    new_sablon_config = {}
    
    # Mevcut sablon_config kopyası (kaybetmemek için)
    # Fiziksel dosyalar üzerinden gidiyoruz
    files = sorted([f for f in cat_dir.iterdir() if f.suffix.lower() in {'.jpg', '.jpeg', '.png', '.webp'}])
    
    idx = 1
    # Çakışmaları önlemek için önce tüm dosyaları geçici bir isme taşı
    temp_files = []
    for f in files:
        temp_name = f"TEMP_RENAME_{f.name}"
        temp_path = f.with_name(temp_name)
        f.rename(temp_path)
        temp_files.append((temp_path, f.name, f.suffix.lower()))
        
    for temp_path, old_name, ext in temp_files:
        new_name = f"{prefix}_{idx:03d}{ext}"
        new_path = temp_path.with_name(new_name)
        
        # json güncelle
        if old_name in sablon_config:
            new_sablon_config[new_name] = sablon_config[old_name]
        else:
            # case insensitive match
            found = False
            for k, v in sablon_config.items():
                if k.lower() == old_name.lower():
                    new_sablon_config[new_name] = v
                    found = True
                    break
            if not found:
                # Koordinat ayarı yoksa bile ekle ama varsayılan değerlerle (isteğe bağlı, aslında boş kalabilir)
                pass 
                
        temp_path.rename(new_path)
        total_renamed += 1
        idx += 1

    # Fiziksel olarak bulunamayan ama JSON'da olanları silmiş olduk. Bu doğru bir temizliktir.
    if cat_folder in kategoriler:
        kategoriler[cat_folder]["sablonlar"] = new_sablon_config

ayarlar["kategoriler"] = kategoriler

with open(ayarlar_path, "w", encoding="utf-8") as f:
    json.dump(ayarlar, f, indent=4, ensure_ascii=False)

print(f"Islem tamam. {total_renamed} dosya isimlendirildi. Eski ayarlar yedeği: ayarlar_yedek_renamer.json")
