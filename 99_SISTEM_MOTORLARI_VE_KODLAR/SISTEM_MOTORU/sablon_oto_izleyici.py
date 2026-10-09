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
from core.db import get_all_ayarlar, save_template, delete_template
from core.template_intelligence import TemplateAnalyzer, save_template_profile
from core.template_identity import (
    TemplateNumberConflictError,
    backfill_registry,
    collect_reserved_numbers,
    find_next_contiguous_free_block,
    reserve_number,
    validate_number_block,
)
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

def _staging_txn_dir() -> Path:
    return (
        BASE_DIR
        / "SABLON_V2_MIMARI"
        / "recovery"
        / "staging_transactions"
    )


def _write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass


def _begin_staging_txn(
    original_path: Path,
    processing_path: Path,
) -> tuple[Path, dict]:
    _staging_txn_dir().mkdir(parents=True, exist_ok=True)
    txn_id = (
        time.strftime("%Y%m%d_%H%M%S")
        + "_"
        + original_path.stem
        + "_"
        + hashlib.sha256(
            (str(original_path) + str(time.time_ns())).encode("utf-8")
        ).hexdigest()[:10]
    )
    txn_path = _staging_txn_dir() / f"{txn_id}.json"
    payload = {
        "transaction_id": txn_id,
        "state": "PROCESSING_OWNED",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "original_staging_path": str(original_path),
        "processing_path": str(processing_path),
        "category": processing_path.parent.name,
        "canonical_name": None,
        "backup_path": None,
        "working_path": None,
        "source_sha256": None,
        "error": None,
    }
    _write_json_atomic(txn_path, payload)
    return txn_path, payload


def _update_staging_txn(
    txn_path: Path | None,
    payload: dict | None,
    **changes,
) -> None:
    if txn_path is None or payload is None:
        return
    payload.update(changes)
    payload["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    _write_json_atomic(txn_path, payload)


def reconcile_staging_transaction_journals() -> dict:
    """Classify crash-leftover ingest journals without mutating user files."""
    result = {
        "committed": 0,
        "recovered": 0,
        "recovery_required": 0,
        "failed": 0,
    }
    if not _staging_txn_dir().is_dir():
        return result

    for txn_path in sorted(_staging_txn_dir().glob("*.json")):
        try:
            payload = json.loads(txn_path.read_text(encoding="utf-8"))
            state = str(payload.get("state") or "")
            if state in {"COMMITTED", "ROLLED_BACK", "RECOVERED"}:
                if state == "COMMITTED":
                    result["committed"] += 1
                elif state in {"ROLLED_BACK", "RECOVERED"}:
                    result["recovered"] += 1
                continue

            original = Path(str(payload.get("original_staging_path") or ""))
            processing = Path(str(payload.get("processing_path") or ""))
            backup = Path(str(payload.get("backup_path") or "")) if payload.get("backup_path") else None
            working = Path(str(payload.get("working_path") or "")) if payload.get("working_path") else None

            partial_exists = bool(
                (backup and backup.exists())
                or (working and working.exists())
                or processing.exists()
            )
            if original.exists() and not partial_exists:
                _update_staging_txn(
                    txn_path,
                    payload,
                    state="RECOVERED",
                    error=None,
                )
                result["recovered"] += 1
            else:
                _update_staging_txn(
                    txn_path,
                    payload,
                    state="RECOVERY_REQUIRED",
                    error=(
                        "Önceki ingest yarım kaldı; dosya durumları insan "
                        "incelemesi gerektiriyor."
                    ),
                )
                result["recovery_required"] += 1
        except Exception:
            result["failed"] += 1
            logger.exception(
                f"Staging transaction journal okunamadı: {txn_path}"
            )
    return result


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


def analyze_new_template_once(
    working_path: Path,
    category: str,
    image_cv: np.ndarray,
) -> tuple[dict, dict]:
    """Run first-pass geometry exactly once for a newly ingested template.

    The proposal is review-only. It never auto-approves a template. The same
    template can later be re-analyzed explicitly from the UI if the user wants.
    """
    source_hash = _sha256_file(working_path)
    engine = "template_analyzer"
    try:
        analyzer = TemplateAnalyzer()
        result = analyzer.analyze(
            str(working_path),
            category,
            manual_geometry_prior=None,
        )
    except Exception as exc:
        logger.warning(
            f"İlk otomatik köşe analizi başarısız; güvenli fallback "
            f"denenecek: {working_path.name} ({exc})"
        )
        result = {
            "source_asset_sha256": source_hash,
            "surface_quad": None,
            "outer_quad": None,
            "confidence_total": 0.0,
            "component_confidences": {},
            "review_status": "UNANALYZED",
            "rule": {},
            "orientation": "UNKNOWN",
            "nominal_aspect": "UNKNOWN",
            "analyzer_version": "staging-fallback-v1",
        }
        engine = "legacy_fallback"

    corners = result.get("surface_quad")
    if corners is None:
        fallback = detect_frame_auto(image_cv)
        fallback_corners = fallback.get("koseler") if isinstance(fallback, dict) else None
        if (
            isinstance(fallback_corners, list)
            and len(fallback_corners) == 4
        ):
            corners = fallback_corners
            result["surface_quad"] = corners
            result["review_status"] = "REVIEW_REQUIRED"
            result["component_confidences"] = {
                **(result.get("component_confidences") or {}),
                "legacy_fallback": 1.0,
            }
            engine = "legacy_fallback"

    confidence = float(result.get("confidence_total", 0.0) or 0.0)
    review_status = (
        "REVIEW_REQUIRED"
        if corners is not None
        else "UNANALYZED"
    )
    result["review_status"] = review_status

    legacy_conf = {
        "tip": "perspektif" if corners is not None else "duz",
        "supheli": bool(corners is None or confidence < 0.70),
        "review_status": review_status,
        "ingest_source": "staging_watcher",
        "auto_corner_once": True,
        "auto_corner_engine": engine,
        "auto_corner_confidence": confidence,
    }
    if corners is not None:
        legacy_conf["koseler"] = corners

    rule = result.get("rule") or {}
    profile_data = {
        "template_uid": f"{category}_{working_path.name}",
        "category": category,
        "source_relative_path": f"{category}/{working_path.name}",
        "source_asset_sha256": result.get("source_asset_sha256") or source_hash,
        "profile_version": "v2",
        "analyzer_version": result.get("analyzer_version") or "unknown",
        "product_class": rule.get("product_class", "Bilinmeyen"),
        "orientation": result.get("orientation", "UNKNOWN"),
        "nominal_aspect": result.get("nominal_aspect", "UNKNOWN"),
        "print_policy": rule.get("print_policy", "full_bleed"),
        "surface_quad": corners,
        "outer_quad": result.get("outer_quad"),
        "confidence_total": confidence,
        "component_confidences": {
            **(result.get("component_confidences") or {}),
            "first_pass_auto": 1.0,
        },
        "review_status": review_status,
        "manually_verified": False,
    }
    return legacy_conf, profile_data


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
    txn_path = None
    txn = None
    committed = False
    planned_backup_path = None
    planned_working_path = None

    try:
        staging_path.rename(processing_path)
    except Exception:
        # Another process may already own the file.
        return False

    try:
        txn_path, txn = _begin_staging_txn(
            original_staging_path,
            processing_path,
        )
    except Exception as exc:
        logger.warning(
            f"Staging transaction journal başlatılamadı: {exc}"
        )

    cat_key = processing_path.parent.name
    if cat_key not in KNOWN_CATEGORIES:
        logger.error(
            f"Bilinmeyen staging kategorisi; dosya geri bırakıldı: {cat_key}"
        )
        _restore_processing_file(processing_path, original_staging_path)
        _update_staging_txn(
            txn_path,
            txn,
            state="ROLLED_BACK",
            error=f"Bilinmeyen staging kategorisi: {cat_key}",
        )
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

        # A template number is a permanent identity across active files,
        # backups, DB history, trash and generated artifact history.
        reserved_nums = collect_reserved_numbers(
            BASE_DIR,
            cat_key,
            ignore_paths=[processing_path],
            include_pending_staging=True,
        )

        requested_idx = None
        original_stem = original_staging_path.stem
        if original_stem.startswith(f"{prefix}_"):
            try:
                requested_idx = int(
                    original_stem.replace(f"{prefix}_", "")
                )
            except (TypeError, ValueError):
                requested_idx = None

        if requested_idx is not None:
            try:
                validate_number_block(
                    BASE_DIR,
                    cat_key,
                    requested_idx,
                    1,
                    ignore_paths=[processing_path],
                )
            except TemplateNumberConflictError as exc:
                logger.error(
                    "⛔ İSİM ÇAKIŞMASI: %s daha önce kullanılmış. "
                    "Dosya işlenmedi ve adı değiştirilmeden geri bırakıldı. "
                    "Önerilen yeni numara: %s. Görsel İsimlendirici ile "
                    "yeni numara seçin.",
                    requested_idx,
                    exc.suggested_start,
                )
                _restore_processing_file(
                    processing_path,
                    original_staging_path,
                )
                return False
            new_idx = requested_idx
        else:
            # Generic filenames may still be accepted, but allocation uses the
            # permanent registry and never recycles an old identity.
            new_idx = find_next_contiguous_free_block(
                reserved_nums,
                1,
                1,
            )
            logger.info(
                "ℹ️ Dosyada şablon numarası yok; ilk kalıcı boş numara "
                "atanacak: %s_%03d",
                prefix,
                new_idx,
            )

        new_name = f"{prefix}_{new_idx:03d}.png"
        backup_path = YEDEK_DIR / cat_key / new_name
        working_path = SABLON_DIR / cat_key / new_name
        planned_backup_path = backup_path
        planned_working_path = working_path
        _update_staging_txn(
            txn_path,
            txn,
            state="PLANNED",
            canonical_name=new_name,
            backup_path=str(backup_path),
            working_path=str(working_path),
            source_sha256=_sha256_file(processing_path),
        )

        if backup_path.exists() or working_path.exists():
            logger.error(
                f"Güvenlik nedeniyle mevcut şablon üzerine yazılmadı: {new_name}"
            )
            _restore_processing_file(processing_path, original_staging_path)
            return False

        logger.info(
            f"🔍 Yeni şablon hazırlanıyor: "
            f"{processing_path.name} -> {new_name}"
        )

        # 1) Immutable recovery copy first.
        if not _write_png_atomic(backup_path, img_cv):
            logger.error(f"Orijinal yedek yazılamadı: {backup_path}")
            _restore_processing_file(processing_path, original_staging_path)
            return False
        _update_staging_txn(
            txn_path,
            txn,
            state="BACKUP_WRITTEN",
            backup_sha256=_sha256_file(backup_path),
        )

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
        _update_staging_txn(
            txn_path,
            txn,
            state="WORKING_WRITTEN",
            working_sha256=_sha256_file(working_path),
        )

        # 3) First-pass automatic corner proposal runs exactly once for this
        #    newly ingested template. It remains REVIEW_REQUIRED and never
        #    becomes APPROVED without a human click in the review center.
        s_conf, profile_data = analyze_new_template_once(
            working_path,
            cat_key,
            img_cv,
        )
        if profile_data.get("surface_quad") is not None:
            logger.info(
                f"🧭 İlk köşe önerisi hazır: {new_name} "
                f"(motor={s_conf.get('auto_corner_engine')}, "
                f"güven={s_conf.get('auto_corner_confidence', 0.0):.2f})"
            )
        else:
            logger.warning(
                f"⚠️ İlk köşe önerisi bulunamadı: {new_name}. "
                "İnceleme ekranından 'Köşeleri Yeniden Algıla' kullanılabilir."
            )

        # 4) Register both the UI row and source-hash-bound review profile.
        #    If either DB write fails, undo the partial registration and restore
        #    the user's staging file.
        try:
            save_template(cat_key, new_name, s_conf)
            review_db = BASE_DIR / "SABLON_V2_MIMARI" / "ayarlar.db"
            save_template_profile(str(review_db), profile_data)
            reserve_number(
                BASE_DIR,
                cat_key,
                new_idx,
                canonical_name=new_name,
                source="staging_ingest",
            )
            _update_staging_txn(
                txn_path,
                txn,
                state="DB_REGISTERED",
            )
        except Exception as exc:
            logger.error(f"Şablon review DB'ye kaydedilemedi: {exc}")
            try:
                delete_template(cat_key, new_name)
            except Exception as cleanup_exc:
                logger.warning(
                    f"Başarısız DB kaydı geri alınamadı "
                    f"({new_name}): {cleanup_exc}"
                )
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

        committed = True
        _update_staging_txn(
            txn_path,
            txn,
            state="COMMITTED",
            completed_at=time.strftime("%Y-%m-%d %H:%M:%S"),
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
        _update_staging_txn(
            txn_path,
            txn,
            error=str(exc),
        )
        return False
    finally:
        if txn_path is not None and txn is not None and not committed:
            original_restored = original_staging_path.exists()
            processing_left = processing_path.exists()
            backup_left = bool(
                planned_backup_path
                and planned_backup_path.exists()
            )
            working_left = bool(
                planned_working_path
                and planned_working_path.exists()
            )
            clean_rollback = bool(
                original_restored
                and not processing_left
                and not backup_left
                and not working_left
            )
            _update_staging_txn(
                txn_path,
                txn,
                state=(
                    "ROLLED_BACK"
                    if clean_rollback
                    else "RECOVERY_REQUIRED"
                ),
                rollback_original_restored=original_restored,
                rollback_processing_left=processing_left,
                rollback_backup_left=backup_left,
                rollback_working_left=working_left,
            )


def run_watcher():
    try:
        history = backfill_registry(BASE_DIR)
        logger.info(
            "🔒 Şablon numara geçmişi yüklendi: %s",
            ", ".join(
                f"{category}={count}"
                for category, count in history.items()
            ),
        )
    except Exception as exc:
        logger.warning(
            "Şablon numara geçmişi tam yüklenemedi; dinamik koruma devam ediyor: %s",
            exc,
        )

    logger.info("==================================================================")
    logger.info("👀 ŞABLON HAVUZU HAZIRLIK (STAGING) İZLEYİCİSİ DEVREDE")
    logger.info(f"📁 İzlenen Hazırlık Klasörü: {STAGING_DIR}")
    logger.info("ℹ️ Yeni görseller güvenli yedeklenir, köşeleri bir kez otomatik önerilir ve REVIEW_REQUIRED olarak inceleme merkezine eklenir.")
    logger.info("==================================================================")

    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    recovery = recover_stale_processing_files()
    txn_recovery = reconcile_staging_transaction_journals()
    if txn_recovery["recovery_required"]:
        logger.error(
            "⚠️ %s staging transaction kaydı insan incelemesi gerektiriyor.",
            txn_recovery["recovery_required"],
        )
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

    # FAST SAFE BATCH MODE:
    # - No parallel DB/file writes: templates are still ingested sequentially.
    # - One short settle check is shared by the whole batch instead of sleeping
    #   one second for every image.
    # - Failed/conflicting files are temporarily backed off so one bad file
    #   cannot create a hot retry loop.
    poll_seconds = float(os.environ.get("MOCKUP_WATCH_POLL_SECONDS", "0.75"))
    settle_seconds = float(os.environ.get("MOCKUP_FILE_SETTLE_SECONDS", "0.35"))
    retry_seconds = float(os.environ.get("MOCKUP_FAILED_RETRY_SECONDS", "15"))
    batch_limit = max(
        1,
        int(os.environ.get("MOCKUP_WATCH_BATCH_LIMIT", "250")),
    )
    retry_after = {}

    logger.info(
        "⚡ HIZLI TOPLU TARAMA MODU AKTİF "
        "(batch=%s, poll=%.2fs, settle=%.2fs, paralel_yazma=kapalı)",
        batch_limit,
        poll_seconds,
        settle_seconds,
    )

    try:
        while True:
            scan_now = time.time()
            candidates = []

            for candidate in sorted(STAGING_DIR.rglob("*.*")):
                if not candidate.is_file():
                    continue
                if candidate.suffix.lower() not in VALID_EXTS:
                    continue
                if (
                    "-düzenleme-yapıldı" in candidate.stem
                    or "-beyazlatilmis-onizleme" in candidate.stem
                    or candidate.suffix == ".processing"
                ):
                    continue

                try:
                    stat = candidate.stat()
                except OSError:
                    continue

                signature = (int(stat.st_size), int(stat.st_mtime_ns))
                retry_state = retry_after.get(str(candidate))
                if (
                    retry_state is not None
                    and retry_state[0] == signature
                    and scan_now < retry_state[1]
                ):
                    continue

                candidates.append((candidate, signature))
                if len(candidates) >= batch_limit:
                    break

            if not candidates:
                time.sleep(poll_seconds)
                continue

            # Files may still be copying/syncing (especially under OneDrive).
            # Check the whole batch once after a short settle window.
            time.sleep(settle_seconds)
            ready = []
            for candidate, first_signature in candidates:
                try:
                    stat = candidate.stat()
                except OSError:
                    continue
                second_signature = (
                    int(stat.st_size),
                    int(stat.st_mtime_ns),
                )
                if (
                    second_signature == first_signature
                    and second_signature[0] > 0
                ):
                    ready.append((candidate, second_signature))

            if not ready:
                time.sleep(poll_seconds)
                continue

            logger.info(
                "⚡ Toplu tarama: %s hazır görsel sırayla işlenecek.",
                len(ready),
            )

            completed = 0
            failed = 0
            for candidate, signature in ready:
                logger.info(
                    "🚨 YENİ HAM GÖRSEL YAKALANDI: %s (Klasör: %s)",
                    candidate.name,
                    candidate.parent.name,
                )
                ok = process_from_staging(candidate)
                if ok:
                    completed += 1
                    retry_after.pop(str(candidate), None)
                    continue

                failed += 1
                if candidate.exists():
                    try:
                        current = candidate.stat()
                        current_signature = (
                            int(current.st_size),
                            int(current.st_mtime_ns),
                        )
                    except OSError:
                        current_signature = signature
                    retry_after[str(candidate)] = (
                        current_signature,
                        time.time() + retry_seconds,
                    )
                else:
                    retry_after.pop(str(candidate), None)

            # Keep retry bookkeeping bounded if users frequently rename/remove
            # conflicting files while the watcher is running.
            if len(retry_after) > 1000:
                retry_after = {
                    key: value
                    for key, value in retry_after.items()
                    if Path(key).exists()
                }

            logger.info(
                "⚡ Toplu tur tamamlandı: başarılı=%s, bekleyen/hatalı=%s",
                completed,
                failed,
            )
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
