# -*- coding: utf-8 -*-
"""
================================================================================
SABLON OTO İZLEYİCİ (Auto-Template Whitener & Watcher)
================================================================================
'YENI-BOS MOCKUP SABLON HAVUZU' staging klasörünü izler.
Yeni bir şablon geldiğinde:
1. Kullanıcının tek kopyasını koruyarak işleme alır.
2. Kurtarma yedeği + çalışma kopyası oluşturur.
3. Aktif SQLite review veritabanına REVIEW_REQUIRED olarak kaydeder.
4. İnsan onayı olmadan üretime APPROVED geometri vermez.
================================================================================
"""

import os
import sys
import time
import json
import logging
import hashlib
import shutil
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

SOURCE_ROOT = Path(__file__).resolve().parent.parent.parent
_runtime_override = str(os.environ.get("MOCKUP_RUNTIME_WORKSPACE") or "").strip()
BASE_DIR = (
    Path(_runtime_override).expanduser().resolve()
    if _runtime_override
    else SOURCE_ROOT.resolve()
)
os.environ["MOCKUP_RUNTIME_WORKSPACE"] = str(BASE_DIR)

SABLON_DIR = BASE_DIR / "2_SABLON_HAVUZU"
YEDEK_DIR = BASE_DIR / "2_SABLON_HAVUZU_ORIJINAL_YEDEK"
STAGING_DIR = BASE_DIR / "YENI-BOS MOCKUP SABLON HAVUZU"
RUNTIME_ENGINE_DIR = BASE_DIR / "99_SISTEM_MOTORLARI_VE_KODLAR" / "SISTEM_MOTORU"
REGISTRY_PATH = RUNTIME_ENGINE_DIR / "logs" / "whitened_registry.json"

SOURCE_ENGINE_DIR = SOURCE_ROOT / "99_SISTEM_MOTORLARI_VE_KODLAR" / "SISTEM_MOTORU"
SOURCE_ARCH_DIR = SOURCE_ROOT / "SABLON_V2_MIMARI"
sys.path.insert(0, str(SOURCE_ENGINE_DIR))
sys.path.insert(0, str(SOURCE_ARCH_DIR))

from sablon_beyazlatma_motoru import (
    imread_unicode,
    imwrite_unicode,
    whiten_canvas,
    get_polygon_points
)
from core.db import get_all_ayarlar, save_template
# from foreground_ai import ForegroundAIEngine # Gereksiz sistem yükü oluşturduğu için devredışı bırakıldı

FRAMELESS_KEYS = ["01_Wifi_Kutusu", "04_Cam_Dograma", "05_Ocak_Arkasi"]
VALID_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".avif"}
KNOWN_CATEGORIES = {
    "01_Wifi_Kutusu",
    "02_Cam_Tablo_Dikey",
    "02_Cam_Tablo_Yatay",
    "03_Ahsap_Tablo",
    "04_Cam_Dograma",
    "05_Ocak_Arkasi",
}

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

def _write_png_atomic(dest_path: Path, img_cv: np.ndarray) -> bool:
    """Write a PNG atomically so crashes never leave a half-written template."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(".png", img_cv)
    if not ok:
        return False
    tmp_path = dest_path.with_name(dest_path.name + ".tmp")
    try:
        with open(tmp_path, "wb") as handle:
            handle.write(encoded.tobytes())
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, dest_path)
        return True
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def recover_stale_processing_files(
    stale_seconds: float = 300.0,
) -> dict:
    """Recover crash-leftover .processing files without destroying data.

    - If the original name is free, restore it in place.
    - If the original exists and bytes are identical, remove only the duplicate.
    - If the original exists but differs, move the orphan to a dedicated
      recovery area outside the watched staging tree.
    """
    result = {
        "restored": [],
        "deduplicated": [],
        "quarantined": [],
        "failed": [],
    }
    if not STAGING_DIR.exists():
        return result

    recovery_root = BASE_DIR / "_KURTARMA_PROCESSING"
    now = time.time()

    for processing_path in sorted(STAGING_DIR.rglob("*.processing")):
        try:
            age = now - processing_path.stat().st_mtime
        except OSError as exc:
            result["failed"].append(
                {"path": str(processing_path), "error": str(exc)}
            )
            continue
        if age < float(stale_seconds):
            continue

        original_name = processing_path.name[:-len(".processing")]
        if not original_name:
            continue
        original_path = processing_path.with_name(original_name)

        try:
            if not original_path.exists():
                processing_path.rename(original_path)
                result["restored"].append(str(original_path))
                logger.warning(
                    f"↩️ Eski .processing dosyası geri yüklendi: "
                    f"{original_path}"
                )
                continue

            try:
                identical = (
                    processing_path.stat().st_size
                    == original_path.stat().st_size
                    and _sha256_file(processing_path)
                    == _sha256_file(original_path)
                )
            except OSError:
                identical = False

            if identical:
                processing_path.unlink()
                result["deduplicated"].append(str(processing_path))
                logger.info(
                    f"🧹 Aynı bytes'a sahip eski .processing kopyası "
                    f"temizlendi: {processing_path}"
                )
                continue

            category = processing_path.parent.name
            quarantine_dir = recovery_root / category
            quarantine_dir.mkdir(parents=True, exist_ok=True)
            stamp = time.strftime("%Y%m%d_%H%M%S")
            base_name = f"{Path(original_name).stem}__{stamp}"
            suffix = Path(original_name).suffix
            candidate = quarantine_dir / f"{base_name}{suffix}"
            counter = 1
            while candidate.exists():
                candidate = quarantine_dir / (
                    f"{base_name}_{counter}{suffix}"
                )
                counter += 1
            shutil.move(str(processing_path), str(candidate))
            result["quarantined"].append(str(candidate))
            logger.warning(
                "⚠️ Eski .processing ile aktif dosya farklıydı; "
                f"iki kopya da korundu. Kurtarma: {candidate}"
            )
        except Exception as exc:
            result["failed"].append(
                {"path": str(processing_path), "error": str(exc)}
            )
            logger.exception(
                f".processing kurtarma hatası: {processing_path}"
            )

    return result


def _restore_processing_file(processing_path: Path, original_path: Path) -> None:
    """Best-effort rollback: never strand the only user copy as .processing."""
    if not processing_path.exists() or original_path.exists():
        return
    try:
        processing_path.rename(original_path)
        logger.warning(
            f"↩️ İşlem tamamlanamadı; staging dosyası geri yüklendi: "
            f"{original_path.name}"
        )
    except Exception as exc:
        logger.error(
            f"KRİTİK: staging dosyası geri yüklenemedi: "
            f"{processing_path} -> {original_path}: {exc}"
        )


def _existing_template_names(cat_key: str) -> set[str]:
    names = set()
    for root in (SABLON_DIR, YEDEK_DIR):
        cat_dir = root / cat_key
        if cat_dir.exists():
            for path in cat_dir.iterdir():
                if path.is_file():
                    names.add(path.name)

    try:
        ayarlar = get_all_ayarlar()
        names.update(
            ayarlar.get("kategoriler", {})
            .get(cat_key, {})
            .get("sablonlar", {})
            .keys()
        )
    except Exception as exc:
        logger.warning(f"DB şablon isimleri okunamadı: {exc}")
    return names


def process_from_staging(staging_path: Path, thread_lock=None) -> bool:
    """Safely ingest one raw template into backup + review workspace.

    Safety contract:
    - never overwrite an existing original backup silently;
    - never delete the only staging copy before durable backup + DB registration;
    - every failure attempts to restore the original staging filename;
    - new templates enter review as REVIEW_REQUIRED, never production-approved.
    """
    if (
        "-düzenleme-yapıldı" in staging_path.stem
        or "-beyazlatilmis-onizleme" in staging_path.stem
        or staging_path.suffix == ".processing"
    ):
        return False

    original_staging_path = staging_path
    processing_path = staging_path.with_suffix(
        staging_path.suffix + ".processing"
    )
    try:
        staging_path.rename(processing_path)
    except Exception:
        # Another process may already own the file.
        return False

    cat_key = processing_path.parent.name
    if cat_key not in KNOWN_CATEGORIES:
        logger.error(
            f"Bilinmeyen staging kategorisi; dosya geri bırakıldı: {cat_key}"
        )
        _restore_processing_file(processing_path, original_staging_path)
        return False

    prefixes = {
        "01_Wifi_Kutusu": "Wifi_Kutusu",
        "02_Cam_Tablo_Dikey": "CamTabloDikey",
        "02_Cam_Tablo_Yatay": "CamTabloYatay",
        "03_Ahsap_Tablo": "AhsapTablo",
        "04_Cam_Dograma": "CamDograma",
        "05_Ocak_Arkasi": "OcakArkasi",
    }
    prefix = prefixes.get(cat_key, cat_key)

    try:
        img_cv = imread_unicode(processing_path)
        if img_cv is None:
            logger.error(f"Görsel okunamadı: {processing_path}")
            _restore_processing_file(processing_path, original_staging_path)
            return False

        existing_names = _existing_template_names(cat_key)
        existing_nums = set()
        for name in existing_names:
            p = Path(name)
            if p.suffix.lower() not in VALID_EXTS:
                continue
            try:
                existing_nums.add(int(p.stem.replace(f"{prefix}_", "")))
            except (TypeError, ValueError):
                continue

        # Silent overwrite is forbidden. Preserve a requested number only when
        # it is truly unused; otherwise allocate the first free slot.
        requested_idx = None
        original_stem = original_staging_path.stem
        if original_stem.startswith(f"{prefix}_"):
            try:
                requested_idx = int(
                    original_stem.replace(f"{prefix}_", "")
                )
            except (TypeError, ValueError):
                requested_idx = None

        if requested_idx is not None and requested_idx not in existing_nums:
            new_idx = requested_idx
        else:
            new_idx = 1
            while new_idx in existing_nums:
                new_idx += 1

        new_name = f"{prefix}_{new_idx:03d}.png"
        backup_path = YEDEK_DIR / cat_key / new_name
        working_path = SABLON_DIR / cat_key / new_name

        if backup_path.exists() or working_path.exists():
            logger.error(
                f"Güvenlik nedeniyle mevcut şablon üzerine yazılmadı: {new_name}"
            )
            _restore_processing_file(processing_path, original_staging_path)
            return False

        logger.info(
            f"🔍 Yeni şablon analiz ediliyor: "
            f"{processing_path.name} -> {new_name}"
        )
        s_conf = detect_frame_auto(img_cv)
        s_conf["review_status"] = "REVIEW_REQUIRED"
        s_conf["ingest_source"] = "staging_watcher"

        # 1) Immutable recovery copy first.
        if not _write_png_atomic(backup_path, img_cv):
            logger.error(f"Orijinal yedek yazılamadı: {backup_path}")
            _restore_processing_file(processing_path, original_staging_path)
            return False

        # 2) Working copy may later be transformed, but starts byte-equivalent
        #    in pixel content to the durable original backup.
        if not _write_png_atomic(working_path, img_cv):
            logger.error(f"Çalışma şablonu yazılamadı: {working_path}")
            try:
                backup_path.unlink(missing_ok=True)
            except Exception as cleanup_exc:
                logger.warning(
                    f"Başarısız ingest yedeği temizlenemedi: {cleanup_exc}"
                )
            _restore_processing_file(processing_path, original_staging_path)
            return False

        # 3) Register in the ACTIVE SQLite review architecture. Do not mutate
        #    legacy ayarlar.json; the Flask review UI reads ayarlar.db.
        try:
            save_template(cat_key, new_name, s_conf)
        except Exception as exc:
            logger.error(f"Şablon review DB'ye kaydedilemedi: {exc}")
            for created_path in (working_path, backup_path):
                try:
                    created_path.unlink(missing_ok=True)
                except Exception as cleanup_exc:
                    logger.warning(
                        f"Başarısız ingest artığı temizlenemedi "
                        f"({created_path.name}): {cleanup_exc}"
                    )
            _restore_processing_file(processing_path, original_staging_path)
            return False

        # Only now is the staging copy redundant.
        try:
            processing_path.unlink()
        except Exception as exc:
            logger.warning(
                f"Şablon güvenle kaydedildi ancak staging kopyası silinemedi: {exc}"
            )

        logger.info(
            f"📦 Orijinal korundu: {backup_path}"
        )
        logger.info(
            f"⏳ [REVIEW_REQUIRED] {new_name} inceleme merkezine eklendi. "
            "Üretime girmesi için insan onayı gerekiyor."
        )
        return True

    except Exception as exc:
        logger.exception(f"Şablon staging işlemi başarısız: {exc}")
        _restore_processing_file(processing_path, original_staging_path)
        return False


def run_watcher():
    logger.info("==================================================================")
    logger.info("👀 ŞABLON HAVUZU HAZIRLIK (STAGING) İZLEYİCİSİ DEVREDE")
    logger.info(f"📁 İzlenen Hazırlık Klasörü: {STAGING_DIR}")
    logger.info("ℹ️ Yeni görseller güvenli yedek + çalışma kopyası olarak kaydedilir ve REVIEW_REQUIRED durumunda inceleme merkezine eklenir.")
    logger.info("==================================================================")

    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    recovery = recover_stale_processing_files()
    recovered_count = (
        len(recovery["restored"])
        + len(recovery["deduplicated"])
        + len(recovery["quarantined"])
    )
    if recovered_count:
        logger.info(
            f"🛟 Başlangıç kurtarması tamamlandı: "
            f"{recovered_count} eski .processing kaydı ele alındı."
        )
    if recovery["failed"]:
        logger.error(
            f"⚠️ {len(recovery['failed'])} .processing dosyası "
            "otomatik kurtarılamadı."
        )

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
    if "--recover-only" in sys.argv:
        STAGING_DIR.mkdir(parents=True, exist_ok=True)
        recovery = recover_stale_processing_files(stale_seconds=0)
        print(
            json.dumps(
                recovery,
                ensure_ascii=False,
                indent=2,
            )
        )
        raise SystemExit(1 if recovery["failed"] else 0)
    run_watcher()
