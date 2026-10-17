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
import hashlib
import sqlite3
import math
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
    USER_WORKSPACE_DIR,
    physical_orientation_verified,
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

# Code lives in SOURCE_ROOT; user assets live in the explicitly selected
# MOCKUP_RUNTIME_WORKSPACE. Never silently switch to the git checkout.
MANUAL_DIR = USER_WORKSPACE_DIR / "MOCKUP A HAZIR GÖRSELLER"
SABLON_DIR = USER_WORKSPACE_DIR / "2_SABLON_HAVUZU"

def get_manual_images() -> list[Path]:
    if not MANUAL_DIR.exists():
        MANUAL_DIR.mkdir(parents=True, exist_ok=True)
        return []
    
    valid_exts = {".jpg", ".jpeg", ".png", ".webp"}
    images = [f for f in MANUAL_DIR.iterdir() if f.is_file() and f.suffix.lower() in valid_exts]
    return sorted(images)

def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def get_template_pool(prod_key: str) -> list[tuple[str, Path, dict]]:
    """Return ONLY human-approved, source-SHA-bound valid working templates.

    Never trust existence + legacy JSON coordinates as sufficient approval.
    Importantly, an absent/legacy SQLite schema fails CLOSED and cannot
    accidentally promote an unreviewed template to marketplace production.
    """
    if prod_key not in PRODUCT_CATALOG:
        return []
    prod_def = PRODUCT_CATALOG[prod_key]
    db_path = USER_WORKSPACE_DIR / "SABLON_V2_MIMARI" / "ayarlar.db"
    if not db_path.is_file():
        logger.error("MANUAL_APPROVED_REGISTRY_MISSING: %s", db_path)
        return []
    config_templates = AYARLAR.get("kategoriler", {}).get(prod_key, {}).get("sablonlar", {})
    cat_folder = SABLON_DIR / prod_key
    if cat_folder.is_symlink() or not cat_folder.is_dir():
        return []
    pool = []
    try:
        conn = sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True, timeout=5)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA query_only=ON")
            rows = conn.execute(
                """SELECT template_uid,source_relative_path,source_asset_sha256,
                          surface_quad,orientation,nominal_aspect,review_status,
                          manually_verified,is_active,has_occlusion,
                          component_confidences
                   FROM template_profiles WHERE category=? AND is_active=1""",
                (prod_key,),
            ).fetchall()
        finally:
            conn.close()
    except (sqlite3.Error, OSError) as exc:
        logger.error("MANUAL_APPROVED_REGISTRY_UNREADABLE: %s", exc)
        return []
    allowed = {}
    ambiguous = set()
    for row in rows:
        relative = Path(str(row["source_relative_path"] or "").replace("\\\\", "/"))
        if relative.parent.name != prod_key:
            continue
        name = relative.name.casefold()
        if name in allowed:
            ambiguous.add(name)
        else:
            allowed[name] = row
    for name in ambiguous:
        allowed.pop(name, None)
    for template, legacy_conf in config_templates.items():
        profile = allowed.get(Path(template).name.casefold())
        if profile is None or str(profile["review_status"]) != "APPROVED" or int(profile["manually_verified"] or 0) != 1:
            continue
        s_path = cat_folder / Path(template).name
        if s_path.is_symlink() or not s_path.is_file() or s_path.suffix.lower() != ".png":
            continue
        if s_path.resolve().parent != cat_folder.resolve():
            continue
        if not profile["source_asset_sha256"] or _sha256_file(s_path) != str(profile["source_asset_sha256"]):
            logger.warning("MANUAL_STALE_SOURCE_BLOCKED: %s/%s", prod_key, template)
            continue
        if int(profile["has_occlusion"] or 0):
            logger.info("MANUAL_OCCLUSION_REVIEW_REQUIRED: %s", template)
            continue
        orient = str(profile["orientation"] or "").upper()
        if orient != prod_def.orientation:
            continue
        if prod_key == "04_Cam_Dograma" and not physical_orientation_verified(profile["component_confidences"]):
            continue
        try:
            quad = json.loads(profile["surface_quad"])
            if not isinstance(quad, list) or len(quad) != 4:
                continue
            with Image.open(s_path) as im:
                width, height = im.size
            if not all(isinstance(pt, (list, tuple)) and len(pt) == 2
                       and all(math.isfinite(float(v)) for v in pt)
                       and 0 <= float(pt[0]) < width and 0 <= float(pt[1]) < height
                       for pt in quad):
                continue
            nominal = float(profile["nominal_aspect"])
            if not math.isfinite(nominal) or nominal <= 0:
                continue
        except (OSError, ValueError, TypeError):
            continue
        settings = dict(legacy_conf or {})
        settings.update({
            "tip": "perspektif", "koseler": quad,
            "profile_orientation": orient, "nominal_aspect": nominal,
            "has_occlusion": False, "auto_foreground": False, "on_plan": None,
            "output_width": 1200, "output_height": 1600,
            "marketplace_ready": True,
            "source_asset_sha256": str(profile["source_asset_sha256"]),
        })
        pool.append((template, s_path, settings))
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
            temp_dir = USER_WORKSPACE_DIR / "99_SISTEM_MOTORLARI_VE_KODLAR" / "SISTEM_MOTORU" / "logs" / "temp_crops"
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
        return False

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
            
            pool = get_template_pool(prod_key)
            if not pool:
                continue
            seq = state.get_next_sequence(prod_def.barkod_prefix)
            barkod = f"{prod_def.barkod_prefix}{seq:05d}"
            sku = barkod
            model_kodu = f"{prod_def.model_prefix}{seq:05d}"

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
    return total_created > 0

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--mod", choices=["dongusel", "coklu"], default="dongusel")
    p.add_argument("--limit", type=int, default=None, help="İşlenecek maksimum ham görsel sayısı")
    args = p.parse_args()

    if not process_manual_images(mode=args.mod, limit=args.limit):
        logger.error("MANUAL_RENDER_BLOCKED_OR_NO_SUCCESSFUL_OUTPUT")
        raise SystemExit(2)
