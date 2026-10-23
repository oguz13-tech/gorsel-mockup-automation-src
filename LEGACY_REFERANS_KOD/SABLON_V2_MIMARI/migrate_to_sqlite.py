import json
import os
import sys

# core modülünü import edebilmek için yolu ekle
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.db import init_db, save_settings_node, save_category, save_template

def migrate():
    print("🚀 SQLite Veritabanı başlatılıyor...")
    init_db()
    
    ayarlar_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ayarlar.json")
    
    if not os.path.exists(ayarlar_path):
        print(f"HATA: {ayarlar_path} bulunamadı!")
        return

    print("📄 ayarlar.json okunuyor...")
    with open(ayarlar_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    print("⚙️ Genel Ayarlar (settings) aktarılıyor...")
    for key, value in data.items():
        if key != "kategoriler":
            save_settings_node(key, value)
            
    print("📂 Kategoriler ve Şablonlar (categories & templates) aktarılıyor...")
    kategoriler = data.get("kategoriler", {})
    
    sablon_sayisi = 0
    kategori_sayisi = 0
    
    for cat_id, cat_data in kategoriler.items():
        # Kategori etiketini kaydet
        label = cat_data.get("etiket", cat_id)
        save_category(cat_id, label)
        kategori_sayisi += 1
        
        # Şablonları kaydet
        sablonlar = cat_data.get("sablonlar", {})
        for tmpl_filename, tmpl_data in sablonlar.items():
            save_template(cat_id, tmpl_filename, tmpl_data)
            sablon_sayisi += 1
            
    print(f"✅ Göç başarıyla tamamlandı! Toplam {kategori_sayisi} kategori ve {sablon_sayisi} şablon veritabanına eklendi.")

if __name__ == "__main__":
    migrate()
