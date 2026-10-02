# -*- coding: utf-8 -*-
import os
import random
import re
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
    
    with open(dosya_adi, "r", encoding="utf-8", errors="ignore") as f:
        for satir in f:
            satir = satir.strip()
            if not satir: continue
            # [GRUP] formatını esnek yakala
            if satir.startswith("[") and "]" in satir:
                bitis = satir.find("]")
                aktif_grup = satir[1:bitis].strip().upper()
                gruplar[aktif_grup] = []
            elif aktif_grup:
                # Saat/tarih veya alakasız kalıntıları filtrele
                if not re.match(r'^\d{1,2}:\d{2}', satir) and satir.lower() != "trendyol":
                    gruplar[aktif_grup].append(satir)
    return gruplar

# 2. AÇIKLAMA DOSYASI OKUMA VE AKILLI AYRIŞTIRMA (aciklama_keywords.txt)
def aciklama_dosyasini_oku():
    dosya_adi = os.path.join(KLASOR_YOLU, "aciklama_keywords.txt")
    cumleler = []
    kelimeler = []
    
    if not os.path.exists(dosya_adi):
        return cumleler, kelimeler
        
    with open(dosya_adi, "r", encoding="utf-8", errors="ignore") as f:
        for satir in f:
            satir = satir.strip()
            if not satir or satir.startswith("---"): 
                continue
            # 35 karakterden uzunsa Cümle, kısaysa Anahtar Kelime
            if len(satir) > 35:
                cumleler.append(satir.strip('"'))
            else:
                kelimeler.append(satir.strip('"'))
                
    return cumleler, kelimeler

def has_duplicate_stems(title):
    low = title.lower()
    stems = ["cam", "mermer", "leopar", "geyik", "çini", "desen", "motif", "tahta", "doğrama", "tezgah", "baskı", "renk", "ayak", "tasarım", "şık"]
    for s in stems:
        if low.count(s) > 1:
            return True
    return False

# ÜRÜN İSİMLERİNİ ÜRETEN FONKSİYON (90 - 99 Karakter Garantili)
def isimleri_uret(hedef_adet, gruplar):
    nitelikler = gruplar.get("NITELIK", [])
    temalar = gruplar.get("TEMA", [])
    urunler = gruplar.get("URUN", ["Cam Kesme Tahtası"])
    tamamlayicilar = gruplar.get("TAMAMLAYICI", [])
    ebatlar = gruplar.get("EBAT", ["25x35 cm"])

    benzersiz_basliklar = set()
    deneme, max_deneme = 0, max(hedef_adet * 1500, 500000)

    patterns = [
        lambda n, d, u, t, eb: f"{n} {d} {u} {t} {eb}",
        lambda n, d, u, t, eb: f"{d} {n} {u} {t} {eb}",
        lambda n, d, u, t, eb: f"{n} {u} {d} {t} {eb}",
        lambda n, d, u, t, eb: f"{d} {u} {n} {t} {eb}"
    ]

    while len(benzersiz_basliklar) < hedef_adet and deneme < max_deneme:
        deneme += 1
        
        n = random.choice(nitelikler) if nitelikler else ""
        d = random.choice(temalar) if temalar else ""
        u = random.choice(urunler) if urunler else "Cam Kesme Tahtası"
        t = random.choice(tamamlayicilar) if tamamlayicilar else ""
        eb = random.choice(ebatlar) if ebatlar else ""

        p_fn = random.choice(patterns)
        baslik = p_fn(n, d, u, t, eb)
        baslik = re.sub(r'\s+', ' ', baslik).strip()

        if 90 <= len(baslik) <= 99:
            if not has_duplicate_stems(baslik):
                benzersiz_basliklar.add(baslik)

    return sorted(list(benzersiz_basliklar), key=len, reverse=True)

# AÇIKLAMALARI ÜRETEN FONKSİYON (Akıllı Kelime Enjeksiyonu)
def aciklamalari_uret(hedef_adet, cumleler, kelimeler):
    benzersiz_aciklamalar = set()
    deneme, max_deneme = 0, max(hedef_adet * 1000, 300000)
    
    baglac_kaliplari = [
        "{} Özelliğiyle:",
        "{} Standartlarında:",
        "{} Detaylarıyla:",
        "{} Tasarımıyla:",
        "Öne Çıkan Detay - {}:",
        "{} Yapısı:"
    ]
    
    # 4 cümle Trendyol SEO ve okunabilirlik için idealdir
    satir_sayisi = min(4, len(cumleler)) if len(cumleler) >= 4 else len(cumleler)

    while len(benzersiz_aciklamalar) < hedef_adet and deneme < max_deneme:
        deneme += 1
        
        secilen_cumleler = random.sample(cumleler, satir_sayisi)
        islenmis_satirlar = []
        
        for c in secilen_cumleler:
            if kelimeler and random.random() > 0.5:
                secilen_kelime = random.choice(kelimeler)
                secilen_baglac = random.choice(baglac_kaliplari).format(secilen_kelime)
                yeni_satir = f"{secilen_baglac} {c}"
                islenmis_satirlar.append(yeni_satir)
            else:
                islenmis_satirlar.append(c)
                
        metin = "\n".join(islenmis_satirlar)
        benzersiz_aciklamalar.add(metin)

    return list(benzersiz_aciklamalar)

# ANA ÇALIŞTIRMA FONKSİYONU
def calistir(hedef_adet):
    print("\nSistem dosyalarınızı inceliyor ve akıllı SEO eşleştirmesini başlatıyor...")
    isim_gruplari = urun_isim_dosyasini_oku()
    cumleler, kelimeler = aciklama_dosyasini_oku()
    
    if not cumleler:
        print("\nHATA: 'aciklama_keywords.txt' içinde yeterli cümle bulunamadı! Dosyanın botla aynı klasörde olduğundan emin olun.")
        return
        
    print(f"Kelime grupları okundu. {hedef_adet} adet başlık ve açıklama üretiliyor...")
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
