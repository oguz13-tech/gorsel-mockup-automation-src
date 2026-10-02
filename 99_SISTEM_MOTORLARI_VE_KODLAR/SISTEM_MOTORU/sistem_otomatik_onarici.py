import os
import json
import cv2
import shutil
import logging
from pathlib import Path

# Logger Ayarları
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [SISTEM ONARICI] %(message)s"
)
logger = logging.getLogger("AutoHeal")

BASE_DIR = Path(r"C:\Users\oguzc\OneDrive\Masaüstü\GörselÜretme-ve-Mockup Otomasyonu")
AYARLAR_PATH = BASE_DIR / "99_SISTEM_MOTORLARI_VE_KODLAR" / "SISTEM_MOTORU" / "ayarlar.json"
SABLON_DIR = BASE_DIR / "2_SABLON_HAVUZU"
YEDEK_DIR = BASE_DIR / "2_SABLON_HAVUZU_ORIJINAL_YEDEK"

def compute_image_hash(img_path):
    # Basit bir algısal (perceptual) hash benzeri yöntem: 
    # Görseli 16x16'ya küçültüp griye çeviriyoruz.
    try:
        stream = open(img_path, "rb")
        bytes_data = bytearray(stream.read())
        import numpy as np
        np_arr = np.asarray(bytes_data, dtype=np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_GRAYSCALE)
        if img is None:
            return None
        resized = cv2.resize(img, (16, 16))
        return resized
    except Exception:
        return None

def is_similar(hash1, hash2):
    if hash1 is None or hash2 is None:
        return False
    # Mean Squared Error (MSE) hesapla
    import numpy as np
    err = np.sum((hash1.astype("float") - hash2.astype("float")) ** 2)
    err /= float(hash1.shape[0] * hash1.shape[1])
    return err < 500  # Çok benzerlerse (beyaz kutu eklenmiş hali bile ana hatlarıyla benzer kalır)

def onarim_islemini_baslat():
    if not AYARLAR_PATH.exists():
        logger.error("ayarlar.json bulunamadı!")
        return

    try:
        with open(AYARLAR_PATH, "r", encoding="utf-8") as f:
            ayarlar = json.load(f)
    except Exception as e:
        logger.error(f"Ayarlar okunamadı: {e}")
        return

    kategoriler = ayarlar.get("kategoriler", {})
    sorunlar = []
    cozulenler = []

    for cat_name, cat_data in kategoriler.items():
        sablonlar = cat_data.get("sablonlar", {})
        havuz_cat_dir = SABLON_DIR / cat_name
        yedek_cat_dir = YEDEK_DIR / cat_name

        havuz_cat_dir.mkdir(parents=True, exist_ok=True)
        yedek_cat_dir.mkdir(parents=True, exist_ok=True)

        # 1. Havuzdaki dosyaları listele
        valid_exts = {".png", ".jpg", ".jpeg", ".webp"}
        havuz_files = {f.name: f for f in havuz_cat_dir.glob("*.*") if f.is_file() and f.suffix.lower() in valid_exts}
        
        # 2. Yedekteki tüm dosyaları listele ve hash'lerini çıkar (İsim eşleştirme için)
        yedek_files = list(yedek_cat_dir.glob("*.*"))
        yedek_hashes = {}
        for y_file in yedek_files:
            yedek_hashes[y_file] = compute_image_hash(y_file)

        # 3. Ayarlar.json'daki her bir şablonu kontrol et
        for tmpl_name in list(sablonlar.keys()):
            h_path = havuz_cat_dir / tmpl_name
            y_path = yedek_cat_dir / tmpl_name

            # Hata 1: ayarlar.json'da var ama havuzda fiziksel olarak yok
            if not h_path.exists():
                if y_path.exists():
                    # Kullanıcı onayını (arayüzden Kaydet'e basmayı) bekliyor olabilir!
                    sorunlar.append(f"ONAY BEKLEYEN ŞABLON: '{tmpl_name}' ayarlar.json ve yedekte var ama havuzda yok. (Henüz arayüzden onaylanmamış olabilir)")
                else:
                    cozulenler.append(f"KAYIP DOSYA SİLİNDİ: '{tmpl_name}' hiçbir yerde yok. Veritabanından temizlendi.")
                    del sablonlar[tmpl_name]
                continue

            # Hata 2: Havuzda var ama yedeği yok (veya yanlış isimde)
            if not y_path.exists():
                h_hash = compute_image_hash(h_path)
                match_found = False
                
                # Yedeklerdeki garip isimli dosyalarla görsel benzerliğine bak
                for y_file, y_hash in yedek_hashes.items():
                    if y_file.name != tmpl_name and is_similar(h_hash, y_hash):
                        # Eşleşme bulundu! Yanlış isimli yedeği doğru isme taşı/kopyala
                        try:
                            shutil.copy2(y_file, y_path)
                            cozulenler.append(f"İSİM DÜZELTİLDİ: '{y_file.name}' yedeği, asıl şablon olan '{tmpl_name}' ile eşleştirildi ve yeniden adlandırıldı.")
                            match_found = True
                            break
                        except Exception as e:
                            pass
                
                if not match_found:
                    # Eşleşme yoksa, havuzdaki dosyayı (siyahlı haliyle bile olsa) mecburen yedek klasörüne atalım ki sistem çökmesin
                    try:
                        shutil.copy2(h_path, y_path)
                        cozulenler.append(f"EKSİK YEDEK TAMAMLANDI: '{tmpl_name}' için orijinal yedek bulunamadı. Havuzdaki kopyası YEDEK klasörüne aktarıldı.")
                    except Exception as e:
                        sorunlar.append(f"YEDEKLEME HATASI: '{tmpl_name}' yedeklenemedi. {e}")

        # Hata 3: Havuzda fiziksel olarak var ama ayarlar.json'da kaydı yok (Orphan files)
        for h_name in havuz_files.keys():
            if h_name not in sablonlar:
                h_path = havuz_cat_dir / h_name
                yeni_bos_path = BASE_DIR / "YENI-BOS MOCKUP SABLON HAVUZU" / cat_name / h_name
                yeni_bos_path.parent.mkdir(parents=True, exist_ok=True)
                try:
                    shutil.move(str(h_path), str(yeni_bos_path))
                    cozulenler.append(f"KAYIT DIŞI DOSYA KURTARILDI: '{h_name}' ana havuzdan alınıp otomatik sisteme dahil olması için YENI-BOS'a taşındı.")
                except Exception as e:
                    sorunlar.append(f"KAYIT DIŞI DOSYA TAŞINAMADI: '{h_name}'. Hata: {e}")

    # Yapılan silme/düzeltme işlemlerinden sonra ayarlar.json'u kaydet
    if cozulenler:
        try:
            with open(AYARLAR_PATH, "w", encoding="utf-8") as f:
                json.dump(ayarlar, f, ensure_ascii=False, indent=2)
        except Exception as e:
            sorunlar.append(f"AYARLAR KAYDEDILEMEDI: {e}")

    # Raporlama
    print("="*60)
    print("SİSTEM SAĞLIK VE ONARIM RAPORU")
    print("="*60)
    
    if cozulenler:
        print(f"[OK] {len(cozulenler)} ADET SORUN OTOMATIK COZULDU:")
        for c in cozulenler:
            print("  ->", c)
        print("-" * 60)
        
    if sorunlar:
        print(f"[UYARI] {len(sorunlar)} ADET COZULEMEYEN VEYA DIKKAT GEREKTIREN SORUN BULUNDU:")
        for s in sorunlar:
            print("  ->", s)
    else:
        print("[OK] SISTEM KUSURSUZ CALISIYOR. BUTUN DOSYALAR VE YEDEKLER SENKRONIZE DURUMDA.")
    
    print("="*60)

    # Sağlık durumu JSON olarak da kaydedilsin ki arayüz (SABLON_DUZELTICI) okuyup kullanıcıya uyarı verebilsin
    rapor = {
        "cozulen_sayisi": len(cozulenler),
        "cozulenler": cozulenler,
        "sorun_sayisi": len(sorunlar),
        "sorunlar": sorunlar
    }
    rapor_path = BASE_DIR / "99_SISTEM_MOTORLARI_VE_KODLAR" / "SISTEM_MOTORU" / "logs" / "sistem_saglik_raporu.json"
    rapor_path.parent.mkdir(exist_ok=True, parents=True)
    with open(rapor_path, "w", encoding="utf-8") as rf:
        json.dump(rapor, rf, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    onarim_islemini_baslat()
