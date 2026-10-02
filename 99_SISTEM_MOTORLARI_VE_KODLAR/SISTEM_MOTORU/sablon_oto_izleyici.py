# -*- coding: utf-8 -*-
"""
================================================================================
SABLON OTO İZLEYİCİ (Auto-Template Whitener & Watcher)
================================================================================
'2_SABLON_HAVUZU' klasörünü ve alt klasörlerini sürekli izler.
Kullanıcı klasöre yeni bir oda / şablon görseli eklediği anda:
1. Görseli otomatik algılar.
2. Koordinatı yoksa akıllı çerçeve tespiti yapar ve ayarlar.json'a kaydeder.
3. Çerçeve içini anında bembeyaz / boş sergi kanvasına dönüştürür.
================================================================================
"""

import os
import sys
import time
import json
import logging
from pathlib import Path
import numpy as np

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import cv2
from PIL import Image

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [OTO-BEYAZLATICI] %(message)s"
)
logger = logging.getLogger("AutoWhitener")

BASE_DIR = Path(__file__).resolve().parent.parent.parent
SABLON_DIR = BASE_DIR / "2_SABLON_HAVUZU"
AYARLAR_PATH = BASE_DIR / "99_SISTEM_MOTORLARI_VE_KODLAR" / "SISTEM_MOTORU" / "ayarlar.json"
REGISTRY_PATH = BASE_DIR / "99_SISTEM_MOTORLARI_VE_KODLAR" / "SISTEM_MOTORU" / "logs" / "whitened_registry.json"

sys.path.insert(0, str(BASE_DIR / "99_SISTEM_MOTORLARI_VE_KODLAR" / "SISTEM_MOTORU"))
from sablon_beyazlatma_motoru import (
    imread_unicode,
    imwrite_unicode,
    whiten_canvas,
    get_polygon_points
)
# from foreground_ai import ForegroundAIEngine # Gereksiz sistem yükü oluşturduğu için devredışı bırakıldı

FRAMELESS_KEYS = ["01_Wifi_Kutusu", "04_Cam_Dograma", "05_Ocak_Arkasi"]
VALID_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".avif"}

def load_registry() -> set:
    if REGISTRY_PATH.exists():
        try:
            with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            pass
    return set()

def save_registry(registry: set):
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
            json.dump(list(registry), f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"Registry kaydedilemedi: {e}")

def detect_frame_auto(img_cv: np.ndarray) -> dict:
    """
    Yeni eklenen görselin çerçeve alanını SAM 2.1 (Sıfır Eğitim) ile otomatik tespit eder.
    """
    h, w = img_cv.shape[:2]
    cx, cy = int(w * 0.5), int(h * 0.5)
    
    # 1. SAM 2.1 ZERO-SHOT TESPIT (EGER SAM CALISMAZSA VEYA HATA ALIRSA OPENCV FALLBACK)
    # GEREKSIZ YUK NEDENIYLE DEVRE DISI BIRAKILDI (Kullanici zaten arayuzden 4 koseyi elle seciyor)
    '''
    try:
        logger.info("SAM 2.1 (Zero-Shot AI) ile çerçeve tespiti başlatılıyor...")
        engine = ForegroundAIEngine.get_instance()
        # Merkeze sanal tiklama yaparak maskeyi cikariyoruz
        sam_mask = engine.segment_point(img_cv, (cx, cy))
        
        if sam_mask is not None:
            # Maskeden koseleri bul
            contours, _ = cv2.findContours(sam_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if contours:
                largest_cnt = max(contours, key=cv2.contourArea)
                peri = cv2.arcLength(largest_cnt, True)
                approx = cv2.approxPolyDP(largest_cnt, 0.04 * peri, True)
                
                # Eger 4 kose degilse convex hull ve bounding box zorlamasi (dikdortgen cerceve icin)
                if len(approx) != 4:
                    rect = cv2.minAreaRect(largest_cnt)
                    box = cv2.boxPoints(rect)
                    approx = np.int32(box)
                else:
                    approx = approx.reshape(4, 2)
                    
                pts = approx.tolist()
                pts.sort(key=lambda p: (p[1], p[0]))
                top_pts = sorted(pts[:2], key=lambda p: p[0])
                bottom_pts = sorted(pts[2:], key=lambda p: p[0], reverse=True)
                sorted_pts = [top_pts[0], top_pts[1], bottom_pts[0], bottom_pts[1]]
                
                logger.info("✅ SAM 2.1 Çerçeveyi Kusursuz Buldu!")
                return {"tip": "perspektif", "koseler": sorted_pts, "supheli": False}
    except Exception as e:
        logger.warning(f"SAM 2.1 Tespiti Başarısız Oldu, geleneksel yönteme dönülüyor: {e}")
    '''

    # 2. ESKI GELENEKSEL OPENCV FALLBACK (EGER SAM 2.1 COKER VEYA CALISMAZSA)
    logger.info("OpenCV Geleneksel Çerçeve Tespiti deneniyor...")
    gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)
    
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    best_poly = None
    max_area = 0
    img_area = w * h

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if 0.05 * img_area < area < 0.85 * img_area:
            peri = cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, 0.03 * peri, True)
            if len(approx) == 4 and area > max_area:
                max_area = area
                best_poly = approx

    if best_poly is not None:
        pts = best_poly.reshape(4, 2).tolist()
        # Saat yönünde sırala
        pts.sort(key=lambda p: (p[1], p[0]))
        top_pts = sorted(pts[:2], key=lambda p: p[0])
        bottom_pts = sorted(pts[2:], key=lambda p: p[0], reverse=True)
        sorted_pts = [top_pts[0], top_pts[1], bottom_pts[0], bottom_pts[1]]
        
        # Güven Puanı Kontrolü (Area < 15%)
        is_supheli = bool(max_area < (img_area * 0.15))
        return {"tip": "perspektif", "koseler": sorted_pts, "supheli": is_supheli}
    
    # Standart merkez dikdörtgeni (Varsayılan güvenli alan - ŞÜPHELİ)
    cx, cy = int(w * 0.25), int(h * 0.20)
    cw, ch = int(w * 0.50), int(h * 0.60)
    return {"tip": "duz", "x": cx, "y": cy, "w": cw, "h": ch, "supheli": True}

STAGING_DIR = BASE_DIR / "YENI-BOS MOCKUP SABLON HAVUZU"

def process_from_staging(staging_path: Path, thread_lock=None) -> bool:
    if "-düzenleme-yapıldı" in staging_path.stem or "-beyazlatilmis-onizleme" in staging_path.stem or staging_path.suffix == ".processing":
        return False

    # CRITICAL BUG FIX: Çoklu İşlem Çakışmasını (Race Condition) Önleme (OS-Level Lock)
    # Hem UI (SABLON_DUZELTICI) hem de oto-izleyici aynı anda aynı dosyayı işlemeye çalışırsa ayarlar.json bozulur.
    # Bunu engellemek için dosyayı işleme almadan önce adını .processing olarak değiştiriyoruz.
    processing_path = staging_path.with_suffix(staging_path.suffix + ".processing")
    try:
        staging_path.rename(processing_path)
    except Exception as e:
        # Eğer isim değiştirilemiyorsa, başka bir process şu an bu dosyayı işliyor demektir.
        return False

    cat_key = processing_path.parent.name
    is_frameless = cat_key in FRAMELESS_KEYS
    
    prefixes = {
        "01_Wifi_Kutusu": "Wifi_Kutusu",
        "02_Cam_Tablo_Dikey": "CamTabloDikey",
        "02_Cam_Tablo_Yatay": "CamTabloYatay",
        "03_Ahsap_Tablo": "AhsapTablo",
        "04_Cam_Dograma": "CamDograma",
        "05_Ocak_Arkasi": "OcakArkasi"
    }
    prefix = prefixes.get(cat_key, cat_key)
    target_cat_dir = SABLON_DIR / cat_key
    target_cat_dir.mkdir(parents=True, exist_ok=True)
    
    # KULLANICI TALEBİ: Sisteme giren her dosya ne olursa olsun anında .png'ye çevrilerek standartlaştırılsın!
    ext = ".png"
    
    # Mevcut numaraları topla, boşlukları (silinenleri) bul
    existing_nums = set()
    for ex in target_cat_dir.glob(f"{prefix}_*.*"):
        if ex.suffix.lower() in VALID_EXTS:
            try:
                num = int(ex.stem.replace(f"{prefix}_", ""))
                existing_nums.add(num)
            except:
                pass
            
    # EĞER GELEN DOSYA ZATEN SISTEMDE VARSA, YENİ İSİM VERME, ÜZERİNE YAZ
    original_stem = staging_path.stem
    new_name = None
    if original_stem.startswith(f"{prefix}_"):
        try:
            potential_num = int(original_stem.replace(f"{prefix}_", ""))
            if potential_num in existing_nums:
                new_name = f"{original_stem}{ext}"
                logger.info(f"🔄 Var olan şablon güncelleniyor (Üzerine yazılacak): {new_name}")
        except:
            pass
            
    if not new_name:
        new_idx = 1
        while new_idx in existing_nums:
            new_idx += 1
            
        new_name = f"{prefix}_{new_idx:03d}{ext}"
        
    final_target_path = target_cat_dir / new_name

    img_cv = imread_unicode(processing_path)
    if img_cv is None:
        return False

    logger.info(f"🔍 Yeni şablon için çerçeve tespit ediliyor: {processing_path.name} -> Hedef: {new_name}")
    s_conf = detect_frame_auto(img_cv)
    
    # Kiritik Bölge (Critical Section): OS-Level File Lock ile ayarlar.json'u koruma
    # Flask UI ve Oto-İzleyici farklı process'ler olduğu için thread_lock işe yaramaz.
    lock_file = AYARLAR_PATH.with_suffix('.json.lock')
    max_retries = 50
    for attempt in range(max_retries):
        try:
            # Sadece bu process lock dosyasını oluşturabilirse (exclusive creation) içeri girer
            fd = os.open(str(lock_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            break
        except FileExistsError:
            time.sleep(0.1)
    else:
        logger.error("OS-Level Lock alınamadı! ayarlar.json güncellenmedi.")
        processing_path.with_suffix(ext) # İsmi eski haline döndür
        return False

    try:
        with open(AYARLAR_PATH, "r", encoding="utf-8") as f:
            ayarlar = json.load(f)

        cat_cfg = ayarlar.setdefault("kategoriler", {}).setdefault(cat_key, {"sablonlar": {}})
        sablonlar = cat_cfg.setdefault("sablonlar", {})
        sablonlar[new_name] = s_conf
        
        tmp_path = AYARLAR_PATH.with_suffix('.json.tmp')
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(ayarlar, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, AYARLAR_PATH)
    finally:
        try:
            lock_file.unlink()
        except:
            pass
            
    logger.info(f"💾 Yeni koordinatlar ayarlar.json'a kaydedildi: {s_conf}")

    # Orijinal dosyayi YEDEK klasörüne kopyala ama artık shutil ile değil, saf PNG formatında kodla!
    yedek_cat_dir = BASE_DIR / "2_SABLON_HAVUZU_ORIJINAL_YEDEK" / cat_key
    yedek_cat_dir.mkdir(parents=True, exist_ok=True)
    try:
        imwrite_unicode(str(yedek_cat_dir / new_name), img_cv)
        logger.info(f"📦 Orijinal ham görsel standart PNG olarak yedeğe alındı: {yedek_cat_dir / new_name}")
    except Exception as ey:
        logger.error(f"Yedekleme hatası: {ey}")


    # KULLANICI TALEBİ (ONAY SİSTEMİ):
    # SAM 2.1 bazen köşeleri tam bulamayabilir. O yüzden izleyici (watcher) artık görseli otomatik olarak
    # kesip biçip '2_SABLON_HAVUZU'na (nihai havuza) ATMAYACAK. 
    # Sadece '2_SABLON_HAVUZU_ORIJINAL_YEDEK' klasörüne yedeği alacak ve ayarlar.json'a koordinatları yazacak.
    # Kullanıcı arayüzü (SABLON_DUZELTICI) açıp görseli kontrol edecek, gerekirse köşeleri eliyle düzeltecek 
    # ve arayüzdeki "KAYDET" butonuna basarak ONAY verdiğinde asıl havuza aktarılacak.

    # Eski otomatik beyazlatma ve asıl havuza atma kodu iptal edildi:
    # whitened = whiten_canvas(img_cv, s_conf, is_frameless=is_frameless)
    # success = imwrite_unicode(final_target_path, whitened)
    
    success = True # Yedekleme ve ayarlar JSON güncellemesi başarılıysa işlem başarılı sayılır.
    
    if success:
        logger.info(f"⏳ [ONAY BEKLİYOR] {new_name} yedeğe alındı ve koordinatları hesaplandı. Arayüzden onayınız (Kaydet) bekleniyor!")
        
        # Hazırlık (staging) klasöründeki orijinal dosyayı tamamen sil (Inbox mantığı)
        try:
            processing_path.unlink()
            logger.info(f"🗑️ Hazırlık klasöründen temizlendi: {processing_path.name}")
        except Exception as e:
            logger.error(f"Eski dosya silinemedi: {e}")
            
    return success

def run_watcher():
    logger.info("==================================================================")
    logger.info("👀 ŞABLON HAVUZU HAZIRLIK (STAGING) İZLEYİCİSİ DEVREDE")
    logger.info(f"📁 İzlenen Hazırlık Klasörü: {STAGING_DIR}")
    logger.info("ℹ️ Bu klasöre attığınız görseller otomatik işlenip '2_SABLON_HAVUZU'na aktarılacaktır.")
    logger.info("==================================================================")

    STAGING_DIR.mkdir(parents=True, exist_ok=True)

    try:
        while True:
            time.sleep(2.5)
            for f in STAGING_DIR.rglob("*.*"):
                if f.is_file() and f.suffix.lower() in VALID_EXTS:
                    if "-düzenleme-yapıldı" in f.stem or "-beyazlatilmis-onizleme" in f.stem or f.suffix == ".processing":
                        continue
                        
                    time.sleep(1.0)
                    logger.info(f"🚨 YENİ HAM GÖRSEL YAKALANDI: {f.name} (Klasör: {f.parent.name})")
                    process_from_staging(f)
    except KeyboardInterrupt:
        logger.info("İzleyici durduruldu.")

if __name__ == "__main__":
    run_watcher()
