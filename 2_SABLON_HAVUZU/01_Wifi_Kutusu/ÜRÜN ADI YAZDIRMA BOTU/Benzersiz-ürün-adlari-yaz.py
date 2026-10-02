import os
import random
import pandas as pd

# DİNAMİK KLASÖR YOLU 
KLASOR_YOLU = os.path.dirname(os.path.abspath(__file__))

# 1. ÜRÜN ADI KELİME HAVUZU OKUMA (keywords.txt)
def urun_isim_dosyasini_oku():
    dosya_adi = os.path.join(KLASOR_YOLU, "keywords.txt")
    gruplar = {}
    aktif_grup = None
    if not os.path.exists(dosya_adi): 
        return gruplar
    
    with open(dosya_adi, "r", encoding="utf-8") as f:
        for satir in f:
            satir = satir.strip()
            if not satir: continue
            if satir.startswith("[") and satir.endswith("]"):
                aktif_grup = satir[1:-1]
                gruplar[aktif_grup] = []
            elif aktif_grup:
                gruplar[aktif_grup].append(satir)
    return gruplar

# 2. AÇIKLAMA DOSYASI OKUMA VE AKILLI AYRIŞTIRMA (aciklama_keywords.txt)
def aciklama_dosyasini_oku():
    dosya_adi = os.path.join(KLASOR_YOLU, "aciklama_keywords.txt")
    cumleler = []
    kelimeler = []
    
    if not os.path.exists(dosya_adi):
        return cumleler, kelimeler
        
    with open(dosya_adi, "r", encoding="utf-8") as f:
        for satir in f:
            satir = satir.strip()
            # Boş satırları veya --- ile başlayan başlıkları atla
            if not satir or satir.startswith("---"): 
                continue
                
            # 40 karakterden uzunsa "Cümle", kısaysa "SEO Kelimesi" olarak ayır
            if len(satir) > 40:
                cumleler.append(satir)
            else:
                kelimeler.append(satir)
                
    return cumleler, kelimeler

# ÜRÜN İSİMLERİNİ ÜRETEN FONKSİYON
def isimleri_uret(hedef_adet, gruplar):
    nitelikler = gruplar.get("NITELIK", [])
    malzemeler = gruplar.get("MALZEME", [])
    montajlar = gruplar.get("MONTAJ", [])
    urunler = gruplar.get("URUN", [])
    tamamlayicilar = gruplar.get("TAMAMLAYICI", [])

    benzersiz_basliklar = set()
    deneme, max_deneme = 0, hedef_adet * 500

    while len(benzersiz_basliklar) < hedef_adet and deneme < max_deneme:
        deneme += 1
        secilenler = []

        n_adet = random.choice([1, 2])
        if len(nitelikler) >= n_adet: secilenler.extend(random.sample(nitelikler, n_adet))
        if malzemeler: secilenler.append(random.choice(malzemeler))
        if montajlar: secilenler.append(random.choice(montajlar))
        if urunler: secilenler.append(random.choice(urunler))
        
        t_adet = random.choice([1, 2])
        if len(tamamlayicilar) >= t_adet: secilenler.extend(random.sample(tamamlayicilar, t_adet))

        if len(secilenler) == len(set(secilenler)):
            baslik = " ".join(secilenler)
            if 90 <= len(baslik) <= 99:
                benzersiz_basliklar.add(baslik)

    return sorted(list(benzersiz_basliklar), key=len, reverse=True)

# AÇIKLAMALARI ÜRETEN FONKSİYON (Akıllı Kelime Enjeksiyonu)
def aciklamalari_uret(hedef_adet, cumleler, kelimeler):
    benzersiz_aciklamalar = set()
    deneme, max_deneme = 0, hedef_adet * 300
    
    baglac_kaliplari = [
        "{} Özelliğiyle:",
        "{} Standartlarında:",
        "{} Detaylarıyla:",
        "{} Tasarımıyla:",
        "Öne Çıkan Detay - {}:",
        "{} Yapısı:"
    ]
    
    kullanilacak_satir = min(13, len(cumleler))

    while len(benzersiz_aciklamalar) < hedef_adet and deneme < max_deneme:
        deneme += 1
        
        secilen_cumleler = random.sample(cumleler, kullanilacak_satir)
        islenmis_satirlar = []
        
        for c in secilen_cumleler:
            if kelimeler and random.random() > 0.4:
                secilen_kelime = random.choice(kelimeler)
                secilen_baglac = random.choice(baglac_kaliplari).format(secilen_kelime)
                yeni_satir = f"{secilen_baglac} {c}"
                islenmis_satirlar.append(yeni_satir)
            else:
                islenmis_satirlar.append(c)
                
        # DÜZELTİLEN KISIM: Satırlar arasında gereksiz boşluk bırakmadan alt alta birleştirir
        metin = "\n".join(islenmis_satirlar)
        benzersiz_aciklamalar.add(metin)

    return list(benzersiz_aciklamalar)

# ANA ÇALIŞTIRMA FONKSİYONU
def calistir(hedef_adet):
    print("\nSistem dosyalarınızı inceliyor ve akıllı SEO eşleştirmesini başlatıyor...")
    isim_gruplari = urun_isim_dosyasini_oku()
    cumleler, kelimeler = aciklama_dosyasini_oku()
    
    if not cumleler:
        print("\nHATA: 'aciklama_keywords.txt' içinde uzun cümle bulunamadı! Dosyanın botla aynı klasörde olduğundan emin olun.")
        return
        
    isimler = isimleri_uret(hedef_adet, isim_gruplari)
    aciklamalar = aciklamalari_uret(hedef_adet, cumleler, kelimeler)
    
    eslesen_adet = min(len(isimler), len(aciklamalar))
    
    if eslesen_adet == 0:
        print("\nHATA: Yeterli kombinasyon üretilemedi. keywords.txt dosyanızın içinin dolu olduğundan emin olun.")
        return

    veri = []
    for i in range(eslesen_adet):
        veri.append({
            "Sıra": i + 1,
            "Ürün Adı": isimler[i],
            "Karakter Sayısı": len(isimler[i]),
            "Ürün Açıklaması": aciklamalar[i]
        })
        
    df = pd.DataFrame(veri)
    cikti_dosyasi = os.path.join(KLASOR_YOLU, "Trendyol_Toplu_Urun_Yukleme_Listesi.xlsx")
    df.to_excel(cikti_dosyasi, index=False)
    
    print(f"\nİşlem Başarılı! Toplam {eslesen_adet} adet eşsiz SEO açıklamalı ürün Excel'e yazıldı.")
    print(f"Excel Dosyasının Kaydedildiği Konum:\n{cikti_dosyasi}\n")

if __name__ == "__main__":
    print("--- Trendyol Akıllı Matris (İsim & Açıklama) Botu ---")
    try:
        adet = int(input("Kaç adet ürün yazdırmak istiyorsunuz? "))
        calistir(adet)
    except ValueError:
        print("Lütfen geçerli bir sayı girin!")
        
    input("\nİşlem tamamlandı. Çıkış yapmak için klavyeden ENTER tuşuna basabilirsiniz...")