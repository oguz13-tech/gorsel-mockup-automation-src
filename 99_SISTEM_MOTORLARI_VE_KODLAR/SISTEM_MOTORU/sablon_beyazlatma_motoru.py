# -*- coding: utf-8 -*-
"""
================================================================================
SABLON BEYAZLATMA MOTORU (Ultra-Realistic Blank Canvas Generator)
================================================================================
"""

import os
import sys
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
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("SablonBeyazlatici")

BASE_DIR = Path(__file__).resolve().parent.parent.parent
SOURCE_DIR = BASE_DIR / "2_SABLON_HAVUZU_ORIJINAL_YEDEK"
SABLON_DIR = BASE_DIR / "2_SABLON_HAVUZU"
AYARLAR_PATH = BASE_DIR / "99_SISTEM_MOTORLARI_VE_KODLAR" / "SISTEM_MOTORU" / "ayarlar.json"
if not AYARLAR_PATH.exists():
    AYARLAR_PATH = BASE_DIR / "ayarlar.json"

def imread_unicode(path: Path) -> np.ndarray:
    path = Path(path)  # string veya Path olarak gelebilir, ikisini de destekle
    try:
        data = np.fromfile(str(path), dtype=np.uint8)
        img = cv2.imdecode(data, cv2.IMREAD_UNCHANGED)
        if img is None:
            pil_img = Image.open(path).convert("RGBA")
            img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGBA2BGRA)
        return img
    except Exception as e:
        logger.error(f"Görsel okunamadı: {path.name} ({e})")
        return None

def imwrite_unicode(path, img: np.ndarray) -> bool:
    path = Path(path)  # string veya Path olarak gelebilir, ikisini de destekle
    try:
        ext = path.suffix.lower()
        original_path = path
        
        # Eğer resim BGRA ise (Şeffaflık varsa), uzantısı ne olursa olsun PNG formatında kaydetmek ZORUNDAYIZ
        if len(img.shape) == 3 and img.shape[2] == 4:
            ext = ".png"
            path = path.with_suffix('.png')
            params = [int(cv2.IMWRITE_PNG_COMPRESSION), 4]
        else:
            if ext in [".jpg", ".jpeg"]:
                params = [int(cv2.IMWRITE_JPEG_QUALITY), 96]
            elif ext == ".webp":
                params = [int(cv2.IMWRITE_WEBP_QUALITY), 96]
            elif ext == ".png":
                params = [int(cv2.IMWRITE_PNG_COMPRESSION), 4]
            else:
                params = []
                
        is_success, buf = cv2.imencode(ext, img, params)
        if is_success:
            with open(path, "wb") as f:
                f.write(buf.tobytes())
            
            # Eğer uzantı değiştiyse ve eski dosya varsa onu sil (karışıklığı önlemek için)
            if original_path != path and original_path.exists():
                try:
                    original_path.unlink()
                except Exception as e:
                    logger.error(f"Eski dosya silinemedi: {original_path.name} ({e})")
            return True
        else:
            if img.shape[2] == 4:
                rgb = cv2.cvtColor(img, cv2.COLOR_BGRA2RGBA)
            else:
                rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(rgb)
            pil_img.save(path)
            return True
    except Exception as e:
        logger.error(f"Görsel kaydedilemedi: {path.name} ({e})")
        return False

def is_already_blank(img_cv: np.ndarray, pts: np.ndarray) -> bool:
    h, w = img_cv.shape[:2]
    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.fillConvexPoly(mask, np.int32(pts), 255)
    pixels = img_cv[mask == 255]
    if len(pixels) == 0:
        return False
    mean_val = np.mean(pixels)
    std_val = np.std(pixels)
    return mean_val > 244 and std_val < 10

def snap_to_edges(img_cv: np.ndarray, pts: np.ndarray) -> np.ndarray:
    """Kaba koordinatlari (pts) merkeze dogru hafifce cekerek tasma (bleed) hatalarini onler."""
    center = np.mean(pts, axis=0)
    snapped_pts = pts + (center - pts) * 0.015  # %1.5 iceri daraltma
    return np.float32(snapped_pts)

def get_polygon_points(config: dict, w: int, h: int) -> np.ndarray:
    tip = config.get("tip", "duz")
    if tip == "perspektif":
        if "koseler" in config and len(config["koseler"]) == 4:
            return np.float32(config["koseler"])
        elif "noktalar" in config and len(config["noktalar"]) == 4:
            return np.float32(config["noktalar"])
    
    # Düz dikdörtgen
    x = int(config.get("x", 0))
    y = int(config.get("y", 0))
    bw = int(config.get("w", w - x))
    bh = int(config.get("h", h - y))
    return np.float32([[x, y], [x + bw, y], [x + bw, y + bh], [x, y + bh]])

def whiten_canvas(img_cv: np.ndarray, config: dict, is_frameless: bool = False) -> np.ndarray:
    h, w = img_cv.shape[:2]
    pts = get_polygon_points(config, w, h)
    pts = snap_to_edges(img_cv, pts)

    # 1. Antialiased Kanvas Poligon Maskesi (İçerisi 255, Dışarısı 0)
    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.fillConvexPoly(mask, np.int32(pts), 255)
    mask_f = cv2.GaussianBlur(mask, (3, 3), 0).astype(np.float32) / 255.0

    # 2. Resmi BGRA'ya (Şeffaflık kanallı) çevir
    if len(img_cv.shape) == 2:
        img_bgra = cv2.cvtColor(img_cv, cv2.COLOR_GRAY2BGRA)
    elif len(img_cv.shape) == 3 and img_cv.shape[2] == 3:
        img_bgra = cv2.cvtColor(img_cv, cv2.COLOR_BGR2BGRA)
    else:
        img_bgra = img_cv.copy()

    # 3. Çerçevenin içini ŞEFFAF (Alpha=0) yap (Tasarımı silme mantığı)
    # mask_f değeri 1.0 (tam içerisi) olan yerlerde Alpha 0 olmalı. Dışarısında Alpha 1.0 olmalı.
    current_alpha = img_bgra[:, :, 3].astype(np.float32) / 255.0
    new_alpha = current_alpha * (1.0 - mask_f)
    img_bgra[:, :, 3] = (new_alpha * 255).astype(np.uint8)

    # Blend işlemleri sırasında siyah kenar (fringe) kalmaması için saydam olan yerlerin RGB değerini de silelim
    rgb_f = img_bgra[:, :, :3].astype(np.float32)
    rgb_f = rgb_f * (1.0 - mask_f)[..., None]
    img_bgra[:, :, :3] = rgb_f.astype(np.uint8)

    return img_bgra

def process_all(force: bool = False):
    with open(AYARLAR_PATH, "r", encoding="utf-8") as f:
        ayarlar = json.load(f)

    kategoriler = ayarlar.get("kategoriler", {})
    frameless_keys = ["01_Wifi_Kutusu", "04_Cam_Dograma", "05_Ocak_Arkasi"]

    total_whitened = 0
    total_skipped = 0
    total_failed = 0

    for cat_key, cat_data in kategoriler.items():
        sablonlar = cat_data.get("sablonlar", {})
        src_cat_dir = SOURCE_DIR / cat_key
        dest_cat_dir = SABLON_DIR / cat_key
        dest_cat_dir.mkdir(parents=True, exist_ok=True)
        if not src_cat_dir.exists():
            continue

        is_frameless = cat_key in frameless_keys
        logger.info(f"\n📂 Kategori: {cat_key} ({len(sablonlar)} dosya) [Cercevesiz: {is_frameless}]")

        for s_name, s_conf in sablonlar.items():
            src_path = src_cat_dir / s_name
            dest_path = dest_cat_dir / s_name
            if not src_path.exists():
                for alt_ext in [".webp", ".jpg", ".jpeg", ".png", ".avif"]:
                    cand = src_cat_dir / (Path(s_name).stem + alt_ext)
                    if cand.exists():
                        src_path = cand
                        break

            # EĞER ORİJİNAL YEDEK KLASÖRÜNDE YOKSA, MEVCUT SİLİNMİŞ/BEYAZLATILMIŞ DOSYAYI (2_SABLON_HAVUZU) KULLAN:
            # Zaten amacımız ortasına şeffaf delik açmak olduğu için beyaz dosya da işimizi görür.
            if not src_path.exists():
                for alt_ext in [".webp", ".jpg", ".jpeg", ".png", ".avif"]:
                    cand = dest_cat_dir / (Path(s_name).stem + alt_ext)
                    if cand.exists():
                        src_path = cand
                        break

            if not src_path.exists():
                total_failed += 1
                continue

            img_cv = imread_unicode(src_path)
            if img_cv is None:
                total_failed += 1
                continue

            h, w = img_cv.shape[:2]
            pts = get_polygon_points(s_conf, w, h)

            if not force and is_already_blank(img_cv, pts):
                total_skipped += 1
                continue

            whitened = whiten_canvas(img_cv, s_conf, is_frameless=is_frameless)
            success = imwrite_unicode(dest_path, whitened)
            if success:
                total_whitened += 1
                logger.info(f"  ✨ Beyazlatıldı: {dest_path.name}")
            else:
                total_failed += 1

    logger.info(f"\nSONUC: Beyazlatılan: {total_whitened}, Zaten Boş: {total_skipped}, Hatalı: {total_failed}")

if __name__ == "__main__":
    force_mode = "--force" in sys.argv
    process_all(force=force_mode)
