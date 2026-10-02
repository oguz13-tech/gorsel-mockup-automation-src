import os
import subprocess
import time
from tkinter import Tk, filedialog

def klasor_sec():
    """Kullanıcıya görsel bir pencere açarak hedef klasörü seçtirir."""
    root = Tk()
    root.withdraw() # Ana pencereyi gizle
    klasor_yolu = filedialog.askdirectory(title="İşlenecek Görsellerin Bulunduğu Klasörü Seçin")
    return klasor_yolu

def kalite_artir(kat_sayi="4"):
    print("=" * 60)
    print("      YAPAY ZEKA (REAL-ESRGAN) 4K/5K KALİTE MOTORU")
    print("=" * 60)
    
    # Kendi dizinindeki realesrgan exe dosyasını bul
    exe_yolu = os.path.join(os.path.dirname(os.path.abspath(__file__)), "realesrgan-ncnn-vulkan.exe")
    
    if not os.path.exists(exe_yolu):
        print(f"\n[HATA] 'realesrgan-ncnn-vulkan.exe' bulunamadı!")
        print("Lütfen exe dosyasını ve model dosyalarını bu Python scripti ile aynı klasöre koyun.")
        input("Çıkmak için Enter'a basın...")
        return

    secilen_ana_klasor = klasor_sec()
    
    if not secilen_ana_klasor:
        print("\nİşlem iptal edildi (Klasör seçilmedi).")
        return

    # Çıktılar için ayrı bir klasör oluştur (Seçilen klasörün içinde "4K_Ciktilar" adında)
    cikti_klasoru = os.path.join(secilen_ana_klasor, f"{kat_sayi}X_Kalite_Ciktilari")
    os.makedirs(cikti_klasoru, exist_ok=True)

    # Desteklenen görsel formatları
    gecerli_uzantilar = ('.png', '.jpg', '.jpeg', '.webp')
    islem_gorecekler = [f for f in os.listdir(secilen_ana_klasor) if f.lower().endswith(gecerli_uzantilar)]
    
    if not islem_gorecekler:
        print(f"\n[BİLGİ] Seçilen klasörde uygun bir görsel (.jpg, .png, .webp) bulunamadı.")
        return

    print(f"\nSeçilen Klasör: {secilen_ana_klasor}")
    print(f"Çıktı Klasörü: {cikti_klasoru}")
    print(f"İşlenecek Toplam Görsel: {len(islem_gorecekler)}\n")

    baslangic_zamani = time.time()
    
    for index, dosya in enumerate(islem_gorecekler, 1):
        girdi_yolu = os.path.join(secilen_ana_klasor, dosya)
        cikti_yolu = os.path.join(cikti_klasoru, dosya)
        
        # Eğer bu görsel daha önceden işlenip yeni klasöre atıldıysa tekrar uğraşma
        if os.path.exists(cikti_yolu):
            print(f"[{index}/{len(islem_gorecekler)}] Zaten mevcut, atlandı: {dosya}")
            continue

        # Komut satırı argümanları (Bozulmaları önlemek için -t 200 yapıldı, x4plus modeli korundu)
        komut = [
            exe_yolu,
            "-i", girdi_yolu,
            "-o", cikti_yolu,
            "-n", "realesrgan-x4plus", # Standart fotoğraflar için en iyi model
            "-s", str(kat_sayi),       # Dinamik kat büyütme
            "-t", "200"                # Tile sınırı DÜŞÜRÜLDÜ (200) - Çizgilenme ve renk bozulmalarını engeller!
        ]
        
        print(f"[{index}/{len(islem_gorecekler)}] İşleniyor: {dosya}")
        
        try:
            # Subprocess ile Exe'yi çalıştır
            subprocess.run(komut, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            if os.path.exists(cikti_yolu):
                print(f"   ✨ Başarıyla 4K_Ciktilar klasörüne kaydedildi!")
            else:
                print(f"   ❌ Hata: Çıktı oluşturulamadı.")
                
        except Exception as e:
            print(f"   ❌ Kritik Hata: {e}")

    bitis_zamani = time.time()
    gecen_sure = round((bitis_zamani - baslangic_zamani) / 60, 2)
    
    print("\n" + "=" * 60)
    print(f"İŞLEM BİTTİ! ({gecen_sure} dakika sürdü)")
    print(f"Tüm yüksek kaliteli görselleriniz '{cikti_klasoru}' klasöründe sizi bekliyor.")
    print("=" * 60)
    input("\nKapatmak için Enter'a basın...")

if __name__ == "__main__":
    kalite_artir()