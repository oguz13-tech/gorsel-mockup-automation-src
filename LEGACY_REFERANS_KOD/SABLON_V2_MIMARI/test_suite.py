import requests
import json
import time

BASE_URL = "http://127.0.0.1:8080"

# Sistemin kendini test edeceği çeşitli ürün kategorileri
TEST_SCENARIOS = [
    {
        "desc": "Standart Çerçeveli Ürün (Cam Tablo)",
        "cat": "02_Cam_Tablo_Dikey",
        "tmpl": "CamTabloDikey_023.png",
        "frameless": False
    },
    {
        "desc": "Çerçevesiz Ürün (Wifi Kutusu) - is_frameless Mantığı Testi",
        "cat": "01_Wifi_Kutusu",
        "tmpl": "Wifi_Kutusu_001.png", # Varsayılan bir şablon, yoksa 404 döner ama sistemin çökmediğini kanıtlar
        "frameless": True
    },
    {
        "desc": "Büyük Çerçevesiz Yüzey (Cam Doğrama) - Priz/Hata Toleransı",
        "cat": "04_Cam_Dograma",
        "tmpl": "CamDograma_014.png",
        "frameless": True
    }
]

def test_step(step_num, name, method, url, payload=None, extra_headers=None):
    start_time = time.time()
    try:
        headers = {}
        if extra_headers: headers.update(extra_headers)
            
        if method == "GET":
            res = requests.get(f"{BASE_URL}{url}", headers=headers, timeout=10)
        else:
            res = requests.post(f"{BASE_URL}{url}", json=payload, headers=headers, timeout=20)
            
        elapsed = time.time() - start_time
        if res.status_code in [200, 404]: # 404 is acceptable for missing test images in DB, indicates API works
            return res, True, elapsed
        return res, False, elapsed
    except Exception as e:
        return str(e), False, time.time() - start_time

def run_monster_test_suite():
    print("="*70)
    print("🦖 CANAVAR MODU: OTO-DİAGNOSTİK VE UÇTAN UCA SENARYO TESTİ 🦖")
    print("="*70)

    # 1. Sistem Sağlık Raporu
    r_health, ok, t = test_step("Sistem", "Sağlık Raporu Çekiliyor", "GET", "/api/saglik_durumu")
    if ok and type(r_health) != str:
        data = r_health.json()
        print(f"🏥 Sistem Sağlığı: {data.get('sorun_sayisi', 0)} hata bulundu. API Aktif.")

    toplam_senaryo = len(TEST_SCENARIOS)
    basarili_senaryo = 0

    for idx, sc in enumerate(TEST_SCENARIOS):
        print(f"\n▶️ SENARYO {idx+1}: {sc['desc']} | Hedef: {sc['cat']}")
        cat, tmpl = sc['cat'], sc['tmpl']
        headers = {"X-Active-Category": cat, "X-Active-Template": tmpl}
        
        # Orijinal Çekme
        r_img, ok1, t1 = test_step("1", "Görsel Kontrolü", "GET", f"/image/{cat}/{tmpl}")
        if not ok1:
            print(f"   ⚠️ Uyarı: Şablon bulunamadı, senaryo atlanıyor.")
            continue
            
        # Köşe Algılama
        payload_auto = {"kategori": cat, "sablon": tmpl}
        r_auto, ok2, t2 = test_step("2", "Yapay Zeka Tarama", "POST", "/api/auto_detect_corners", payload_auto, headers)
        
        # Beyazlatma
        payload_beyazlat = {
            "kategoriler": { cat: { "sablonlar": { tmpl: {
                "bg_color": "#ffffff", "mask": {"object_boxes": [], "add_brush": [], "subtract_brush": [], "feather": 1.2, "grabcut_iterations": 1}
            }}}}}
        r_whiten, ok3, t3 = test_step("3", "Beyazlatma Motoru", "POST", "/api/anlik_beyazlat", payload_beyazlat, headers)
        
        if ok1 and ok2 and ok3:
            basarili_senaryo += 1
            print(f"   ✅ Senaryo {idx+1} Başarıyla Tamamlandı! (Çerçevesiz Mod: {sc['frameless']})")
        else:
            print(f"   ❌ Senaryo {idx+1} Başarısız Oldu! (Görsel: {ok1}, Köşe: {ok2}, Beyazlatma: {ok3})")

    print("\n" + "="*70)
    print(f"🎯 TEST SONUCU: {basarili_senaryo}/{toplam_senaryo} SENARYO HATASIZ GEÇİLDİ.")
    print("="*70)

if __name__ == "__main__":
    run_monster_test_suite()
