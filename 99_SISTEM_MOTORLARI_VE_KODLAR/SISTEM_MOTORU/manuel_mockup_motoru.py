# -*- coding: utf-8 -*-
"""
================================================================================
MANUEL GÖRSEL MOCKUP MOTORU (V5 - Direct Art Processor)
================================================================================
Kullanıcının 'MOCKUP A HAZIR GÖRSELLER' klasörüne el ile kopyaladığı görselleri
alır, en/boy oranlarını analiz eder ve otomatik olarak ilgili tüm ürün
şablonlarına giydirerek '3_URETILEN_MOCKUPLAR' klasörüne kusursuz çıktılar üretir.
================================================================================
"""

import os
import sys
import time
import json
import logging
import argparse
from pathlib import Path
from PIL import Image

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Ana motor modülünü dahil et
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR / "99_SISTEM_MOTORLARI_VE_KODLAR" / "SISTEM_MOTORU"))

from pc_master_factory import (
    PRODUCT_CATALOG,
    MockupRenderer,
    AYARLAR,
    OUTPUT_DIR,
    OUTPUT_COKLU_DIR,
    EXCEL_DIR,
    FastExcelManager,
    SeoEngine,
    StateManager
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("ManuelMockup")

MANUAL_DIR = BASE_DIR / "MOCKUP A HAZIR GÖRSELLER"
SABLON_DIR = BASE_DIR / "2_SABLON_HAVUZU"

def get_manual_images() -> list[Path]:
    if not MANUAL_DIR.exists():
        MANUAL_DIR.mkdir(parents=True, exist_ok=True)
        return []
    
    valid_exts = {".jpg", ".jpeg", ".png", ".webp"}
    images = [f for f in MANUAL_DIR.iterdir() if f.is_file() and f.suffix.lower() in valid_exts]
    return sorted(images)

def get_template_pool(prod_key: str) -> list[tuple[str, Path, dict]]:
    pool = []
    prod_def = PRODUCT_CATALOG[prod_key]
    
    kat_cfg = AYARLAR.get("kategoriler", {}).get(prod_key, {})
    sablonlar_cfg = kat_cfg.get("sablonlar", {})

    target_dir = SABLON_DIR / prod_def.folder_name
    if not target_dir.exists():
        target_dir = SABLON_DIR

    for s_name, s_conf in sablonlar_cfg.items():
        s_path = target_dir / s_name
        if not s_path.exists():
            for alt_ext in [".webp", ".jpg", ".jpeg", ".png"]:
                cand = target_dir / (Path(s_name).stem + alt_ext)
                if cand.exists():
                    s_path = cand
                    break
        if s_path.exists():
            pool.append((s_name, s_path, s_conf))

    return pool

def adapt_image_for_orientation(img_path: Path, target_orientation: str) -> Path:
    """
    Eğer kullanıcı tek bir görsel attıysa ve hem yatay hem dikey ürün istiyorsa
    akıllı merkez kırpma (Smart Center-Fit Crop) uygulayarak geçici uyumlu görsel üretir.
    """
    try:
        with Image.open(img_path) as img:
            w, h = img.size
            is_horiz = w >= h
            
            if (target_orientation == "H" and is_horiz) or (target_orientation == "V" and not is_horiz):
                return img_path

            # Kırpma gerekiyor
            temp_dir = BASE_DIR / "99_SISTEM_MOTORLARI_VE_KODLAR" / "SISTEM_MOTORU" / "logs" / "temp_crops"
            temp_dir.mkdir(parents=True, exist_ok=True)
            
            if target_orientation == "H":
                # Dikey görselden Yatay (4:3 veya 16:9 merkez kırpma)
                target_h = int(w * 0.70)
                if target_h <= h:
                    top = (h - target_h) // 2
                    cropped = img.crop((0, top, w, top + target_h))
                else:
                    cropped = img
            else:
                # Yatay görselden Dikey (3:4 veya 2:3 merkez kırpma)
                target_w = int(h * 0.70)
                if target_w <= w:
                    left = (w - target_w) // 2
                    cropped = img.crop((left, 0, left + target_w, h))
                else:
                    cropped = img

            out_path = temp_dir / f"adapted_{target_orientation}_{img_path.name}"
            cropped.save(out_path, quality=95)
            return out_path
    except Exception as e:
        logger.warning(f"Adaptasyon uyarısı ({img_path.name}): {e}")
        return img_path

def process_manual_images(mode: str = "dongusel", all_products: bool = True, limit: int = None):
    images = get_manual_images()
    if limit:
        images = images[:limit]

    if not images:
        logger.warning("==================================================================")
        logger.warning("⚠️ 'MOCKUP A HAZIR GÖRSELLER' klasöründe işlenecek görsel bulunamadı!")
        logger.warning(f"📁 Lütfen görsellerinizi buraya kopyalayın:\n   {MANUAL_DIR}")
        logger.warning("==================================================================")
        return

    logger.info("==================================================================")
    logger.info(f"🚀 MANUEL MOCKUP MOTORU BAŞLATILDI | Bulunan Görsel: {len(images)} | Mod: {mode.upper()}")
    logger.info("==================================================================")

    state = StateManager()
    seo = SeoEngine()
    excel = FastExcelManager(EXCEL_DIR / "Urun_Yukleme_Listesi.xlsx")

    total_created = 0

    for idx, raw_path in enumerate(images, start=1):
        clean_name = raw_path.stem.replace("_", " ").title()
        logger.info(f"\n🎨 [{idx}/{len(images)}] İşleniyor: {raw_path.name} ('{clean_name}')")

        with Image.open(raw_path) as im:
            orig_w, orig_h = im.size
        orig_orientation = "H" if orig_w >= orig_h else "V"

        for prod_key, prod_def in PRODUCT_CATALOG.items():
            if prod_def.orientation != orig_orientation:
                continue
                
            target_art_path = raw_path
            
            seq = state.get_next_sequence(prod_def.barkod_prefix)
            barkod = f"{prod_def.barkod_prefix}{seq:05d}"
            sku = barkod
            model_kodu = f"{prod_def.model_prefix}{seq:05d}"

            pool = get_template_pool(prod_key)
            if not pool:
                continue

            if mode == "coklu":
                secilen_sablonlar = pool
            else:
                t_idx = (seq - 1) % len(pool)
                secilen_sablonlar = [pool[t_idx]]

            for sablon_name, sablon_path, sablon_conf in secilen_sablonlar:
                out_filename = f"{sku}_{sablon_path.stem}.jpg"
                if mode == "coklu":
                    out_dir = OUTPUT_COKLU_DIR / prod_key / sablon_path.stem
                else:
                    out_dir = OUTPUT_DIR / prod_key
                out_dir.mkdir(parents=True, exist_ok=True)
                out_path = out_dir / out_filename

                if out_path.exists():
                    continue

                logger.info(f"  🖌️ Render: {sku} ({prod_def.etiket}) -> {sablon_name}")

                success = MockupRenderer.process_mockup(
                    raw_path=target_art_path,
                    template_path=sablon_path,
                    config=sablon_conf,
                    is_glass=prod_def.is_glass,
                    output_path=out_path
                )

                if not success:
                    continue

                total_created += 1

                # Excel kaydı
                seo_title = seo.generate_title(prod_key, clean_name.replace("_", " ").title())
                seo_desc = seo.get_description(prod_key, clean_name.replace("_", " ").title(), "Modern")
                excel_row = {
                    "Stok Kodu": sku,
                    "Barkod": barkod,
                    "Model Kodu": model_kodu,
                    "Kategori": prod_key,
                    "Ham Baskı Dosyası": raw_path.name,
                    "Mağaza Grubu": sablon_path.stem,
                    "Ürün Adı": seo_title,
                    "Açıklama": seo_desc,
                    "Mockup Dosya Adı": out_filename,
                    "Resim Linki": "",
                    "Eklenme Zamanı": time.strftime("%d.%m.%Y %H:%M:%S")
                }
                excel.append_row(excel_row)

    logger.info("==================================================================")
    logger.info(f"🎉 İŞLEM TAMAMLANDI! Toplam Üretilen Mockup: {total_created}")
    logger.info(f"📁 Çıktılar: {OUTPUT_DIR}")
    logger.info(f"📊 Excel: {excel.file_path}")
    logger.info("==================================================================")

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--mod", choices=["dongusel", "coklu"], default="dongusel")
    p.add_argument("--limit", type=int, default=None, help="İşlenecek maksimum ham görsel sayısı")
    args = p.parse_args()

    process_manual_images(mode=args.mod, limit=args.limit)
