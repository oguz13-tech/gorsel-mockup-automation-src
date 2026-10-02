import os
import json
import cv2
import numpy as np

# Şablonların bulunduğu ana dizin
# Türkçe karakter sorununu aşmak için raw string (r"") kullanıyoruz.
SABLON_HAVUZU_DIR = r"C:\Users\oguzc\OneDrive\Masaüstü\GörselÜretme-ve-Mockup Otomasyonu\2_SABLON_HAVUZU_ORIJINAL_YEDEK"
AYARLAR_PATH = "ayarlar.json"
OUTPUT_DIR = "template_audit"

def run_inspection():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    if not os.path.exists(AYARLAR_PATH):
        print(f"[HATA] {AYARLAR_PATH} bulunamadı.")
        return

    with open(AYARLAR_PATH, "r", encoding="utf-8") as f:
        ayarlar = json.load(f)
        
    kategoriler = ayarlar.get("kategoriler", {})
    
    for kat_key, kat_data in kategoriler.items():
        sablonlar = kat_data.get("sablonlar", {})
        kat_dir = os.path.join(SABLON_HAVUZU_DIR, kat_key)
        
        for sablon_adi, sablon_data in sablonlar.items():
            img_path = os.path.join(kat_dir, sablon_adi)
            
            # Numpy ile okuma (Türkçe karakter ve özel harf desteği için - İleride hata almamak için)
            if not os.path.exists(img_path):
                print(f"[UYARI] Dosya bulunamadı, atlanıyor: {img_path}")
                continue
                
            try:
                with open(img_path, "rb") as f:
                    img_array = np.frombuffer(f.read(), dtype=np.uint8)
                    img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            except Exception as e:
                print(f"[HATA] {img_path} okunamadı: {e}")
                continue
                
            if img is None:
                print(f"[HATA] Görsel formatı desteklenmiyor veya bozuk: {img_path}")
                continue
                
            tip = sablon_data.get("tip", "duz")
            overlay = img.copy()
            
            if tip == "duz":
                x = sablon_data.get("x", 0)
                y = sablon_data.get("y", 0)
                w = sablon_data.get("w", 0)
                h = sablon_data.get("h", 0)
                
                # Kırmızı dikdörtgen çiz (İçi dolu yarı saydam için)
                cv2.rectangle(overlay, (x, y), (x+w, y+h), (0, 0, 255), -1) 
                # Kalın dış çizgi
                cv2.rectangle(img, (x, y), (x+w, y+h), (0, 0, 255), 4) 
                
            elif tip == "perspektif":
                koseler = sablon_data.get("koseler", [])
                if len(koseler) == 4:
                    pts = np.array(koseler, np.int32)
                    pts = pts.reshape((-1, 1, 2))
                    # İçi dolu poligon
                    cv2.fillConvexPoly(overlay, pts, (0, 0, 255))
                    # Dış çizgi
                    cv2.polylines(img, [pts], isClosed=True, color=(0, 0, 255), thickness=4)
            
            # Yarı saydamlık efekti (alpha blending)
            alpha = 0.5
            img = cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0)
            
            # Çıktıyı kaydet
            out_name = f"{kat_key}_{sablon_adi}.jpg"
            out_path = os.path.join(OUTPUT_DIR, out_name)
            
            # Kaydederken de numpy kullanalım (Türkçe karakter yolu için)
            is_success, im_buf_arr = cv2.imencode(".jpg", img)
            if is_success:
                im_buf_arr.tofile(out_path)
                print(f"[BASARILI] Denetim görseli oluşturuldu: {out_path}")

if __name__ == "__main__":
    print("Mockup Kalite Denetimi (Visual Auditor) Başlıyor...")
    run_inspection()
    print(f"\nİşlem tamamlandı! Lütfen proje klasöründeki '{OUTPUT_DIR}' klasörünü açıp kırmızı çizgilerin taşıp taşmadığını gözle kontrol edin.")
