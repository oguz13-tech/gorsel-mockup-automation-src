# -*- coding: utf-8 -*-
"""
================================================================================
E-TİCARET PC MASTER FABRİKASI (V5 ENTERPRISE - HİBRİT MERKEZ)
================================================================================
Bu script, Kaggle AI GPU matbaasından inen master görselleri ve manifest.json
dosyasını alarak yerel PC'de tüm e-ticaret süreçlerini yönetir:

MİMARİ PRENSİPLER (ChatGPT + DeepSeek + Gemini Pro + Antigravity Sentezi):
1. 1 Master -> 5 E-Ticaret Ürünü:
   - M000001_H (Yatay): 01_Wifi_Kutusu (sg-M), 04_Cam_Dograma (cdt-M), 05_Ocak_Arkasi (oact-M)
   - M000001_V (Dikey): 02_Cam_Tablo (ct-M), 03_Ahsap_Tablo (at-M)
   * YATAY-DİKEY KARIŞMASI MATEMATİKSEL OLARAK İMKANSIZDIR.
2. Hassas Geometri & Kenar Kusursuzluğu:
   - OpenCV Homografi / PIL transform + pad (0.03) kenar sızıntısı önleme.
   - Gerçekçi oda aydınlatması harmanı (Luminance Shading %85-%15).
   - Yüzey Ayrımı: Cam için parlama/glare bandı, Ahşap için %100 mat derinlik vinyeti.
3. Çift Dağıtım Modu:
   - Mod 1: Çoklu Mağaza (K1..K11 ayrı klasörler ve ayrı Excel dosyaları).
   - Mod 2: Döngüsel Dağıtım (Tek klasör, tek Excel, sıralı oda rotasyonu).
4. SQLite WAL Durum Yönetimi:
   - Elektrik veya işlem kesilirse kaldığı yerden devam eder (Idempotent).
   - Asla mükerrer ürün basmaz.
5. Asenkron Thread Bulut Yükleyici:
   - ImgBB (4 anahtar rotasyonu) + FreeImage failover.
   - Görsel çizimi yükleme hızından etkilenmez (arkaplanda paralel çalışır).
6. Hızlı Excel Exporter (openpyxl):
   - Hafızada ws.append() ile O(1) hızında Trendyol formatında listeleme.
================================================================================
"""

from __future__ import annotations
import os
import sys
import time
import json
import random
import sqlite3
import hashlib
import logging
import threading
import argparse
import importlib.util
from pathlib import Path
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Tuple, Any

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import numpy as np
import requests
from PIL import Image, ImageOps, ImageDraw, ImageFont, ImageChops, ImageFilter

# OpenCV opsiyonel yükleme koruması
try:
    import cv2
    OPENCV_MEVCUT = True
except ImportError:
    OPENCV_MEVCUT = False

import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill

# ==============================================================================
# 1. DİZİN VE YAPILANDIRMA TANIMLARI
# ==============================================================================
BASE_DIR = Path(__file__).resolve().parent
SOURCE_ROOT = Path(__file__).resolve().parent.parent.parent


def resolve_runtime_workspace(source_root: Path = SOURCE_ROOT) -> Path:
    """Resolve mutable runtime data separately from the checked-out source tree."""
    override = str(os.environ.get("MOCKUP_RUNTIME_WORKSPACE") or "").strip()
    if not override:
        return source_root.resolve()
    return Path(override).expanduser().resolve()


USER_WORKSPACE_DIR = resolve_runtime_workspace()
RUNTIME_ENGINE_DIR = (
    USER_WORKSPACE_DIR
    / "99_SISTEM_MOTORLARI_VE_KODLAR"
    / "SISTEM_MOTORU"
)
FACTORY_DIR = USER_WORKSPACE_DIR / "1_GELEN_KAGGLE_BASKILARI"
SABLON_DIR = USER_WORKSPACE_DIR / "2_SABLON_HAVUZU"
OUTPUT_DIR = USER_WORKSPACE_DIR / "3_URETILEN_MOCKUPLAR"
OUTPUT_COKLU_DIR = USER_WORKSPACE_DIR / "Mockup_Magaza_Klasorleri"
EXCEL_DIR = USER_WORKSPACE_DIR / "4_EXCEL_YUKLEME_LISTELERI"
AYARLAR_PATH = RUNTIME_ENGINE_DIR / "ayarlar.json"
LOG_DIR = RUNTIME_ENGINE_DIR / "logs"
DB_PATH = RUNTIME_ENGINE_DIR / "commerce_state.db"
SEO_DIR = RUNTIME_ENGINE_DIR / "SEO_Verileri"
MASK_CACHE_DIR = RUNTIME_ENGINE_DIR / "masks"

# Preflight is intentionally read-only. Do not create missing runtime
# directories or log files before readiness is measured; doing so would make
# preflight validate side effects it created itself.
PREFLIGHT_MODE = "--preflight" in sys.argv
if not PREFLIGHT_MODE:
    for d in [
        FACTORY_DIR,
        SABLON_DIR,
        SEO_DIR,
        OUTPUT_DIR,
        OUTPUT_COKLU_DIR,
        EXCEL_DIR,
        LOG_DIR,
        MASK_CACHE_DIR,
    ]:
        d.mkdir(parents=True, exist_ok=True)

# Logging Kurulumu. Preflight logs only to stdout to remain read-only.
_log_handlers = [logging.StreamHandler(sys.stdout)]
if not PREFLIGHT_MODE:
    _log_handlers.insert(
        0,
        logging.FileHandler(
            LOG_DIR / "pc_master_factory.log",
            encoding="utf-8",
        ),
    )
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=_log_handlers,
)
logger = logging.getLogger("Factory")

# Production must validate approved quads with the exact same contract used by
# the review/analyzer layer. Code always comes from this checked-out branch,
# while mutable DB/templates/manifest may live in a separate runtime workspace.
ARCH_DIR = SOURCE_ROOT / "SABLON_V2_MIMARI"
if str(ARCH_DIR) not in sys.path:
    sys.path.insert(0, str(ARCH_DIR))
from core.template_intelligence import GeometryValidator as ApprovedGeometryValidator

excel_lock = threading.RLock()
db_lock = threading.RLock()

# Render recipe participates in immutable artifact identity. Bump whenever
# renderer/aspect/occlusion behavior changes so old artifacts are never silently
# reused under a new visual contract.
RECIPE_VERSION = "v3_epic3_20261007_r5"

# ==============================================================================
# 2. ÜRÜN VE FORMAT SÖZLEŞMESİ (URUN_FORMAT_HARITASI)
# ==============================================================================
@dataclass(frozen=True)
class ProductDefinition:
    key: str
    etiket: str
    barkod_prefix: str
    model_prefix: str
    boyut_cm: str
    orientation: str       # 'H' (Yatay) veya 'V' (Dikey)
    is_glass: bool          # Cam materyal efekti mi ahşap mat mı?
    folder_name: str

PRODUCT_CATALOG: Dict[str, ProductDefinition] = {
    "01_Wifi_Kutusu": ProductDefinition(
        key="01_Wifi_Kutusu",
        etiket="Wifi / Modem Gizleme Kutusu Kapağı",
        barkod_prefix="sg-M",
        model_prefix="M-sg-M",
        boyut_cm="30x40 cm",
        orientation="H",
        is_glass=False,
        folder_name="01_Wifi_Kutusu"
    ),
    "02_Cam_Tablo_Dikey": ProductDefinition(
        key="02_Cam_Tablo_Dikey",
        etiket="Lüks Temperli Cam Tablo (Dikey)",
        barkod_prefix="ct-M",
        model_prefix="M-ct-M",
        boyut_cm="50x70 cm",
        orientation="V",
        is_glass=True,
        folder_name="02_Cam_Tablo_Dikey"
    ),
    "02_Cam_Tablo_Yatay": ProductDefinition(
        key="02_Cam_Tablo_Yatay",
        etiket="Lüks Temperli Cam Tablo (Yatay)",
        barkod_prefix="cty-M",
        model_prefix="M-cty-M",
        boyut_cm="70x100 cm",
        orientation="H",
        is_glass=True,
        folder_name="02_Cam_Tablo_Yatay"
    ),
    "03_Ahsap_Tablo": ProductDefinition(
        key="03_Ahsap_Tablo",
        etiket="Doğal Ahşap Çerçeveli Tablo",
        barkod_prefix="at-M",
        model_prefix="M-at-M",
        boyut_cm="40x60 cm",
        orientation="V",
        is_glass=False,
        folder_name="03_Ahsap_Tablo"
    ),
    "04_Cam_Dograma": ProductDefinition(
        key="04_Cam_Dograma",
        etiket="Cam Kesme ve Doğrama Tahtası",
        barkod_prefix="cdt-M",
        model_prefix="M-cdt-M",
        boyut_cm="30x40 cm",
        orientation="H",
        is_glass=True,
        folder_name="04_Cam_Dograma"
    ),
    "05_Ocak_Arkasi": ProductDefinition(
        key="05_Ocak_Arkasi",
        etiket="Ocak Arkası Koruyucu Cam Panel",
        barkod_prefix="oact-M",
        model_prefix="M-oact-M",
        boyut_cm="60x80 cm",
        orientation="H",
        is_glass=True,
        folder_name="05_Ocak_Arkasi"
    )
}


def physical_aspect_for_product(
    product: ProductDefinition,
    orientation: str,
) -> Optional[float]:
    """Return trusted physical width/height from product size metadata.

    boyut_cm stores the two physical side lengths. Orientation decides which
    side is width. No projected template geometry is used.
    """
    try:
        raw = str(product.boyut_cm).lower().replace("cm", "").strip()
        first, second = [float(part.strip()) for part in raw.split("x", 1)]
        short_side = min(first, second)
        long_side = max(first, second)
        if short_side <= 0:
            return None
        orient = str(orientation or "").upper()
        if orient == "H":
            return long_side / short_side
        if orient == "V":
            return short_side / long_side
    except (TypeError, ValueError):
        return None
    return None


def foreground_ai_dependency_status() -> dict:
    """Check import/API availability without loading model weights."""
    status = {
        "torch": False,
        "transformers": False,
        "transformers_required_symbols": False,
        "missing": [],
        "errors": [],
    }

    if importlib.util.find_spec("torch") is None:
        status["missing"].append("torch")
    else:
        status["torch"] = True

    if importlib.util.find_spec("transformers") is None:
        status["missing"].append("transformers")
        return status

    status["transformers"] = True
    required_symbols = (
        "AutoProcessor",
        "AutoModelForZeroShotObjectDetection",
        "Sam2Processor",
        "Sam2Model",
    )
    try:
        transformers_mod = importlib.import_module("transformers")
        missing_symbols = [
            name
            for name in required_symbols
            if not hasattr(transformers_mod, name)
        ]
        if missing_symbols:
            status["missing"].extend(
                f"transformers.{name}" for name in missing_symbols
            )
        else:
            status["transformers_required_symbols"] = True
    except Exception as exc:
        status["errors"].append(f"transformers import: {exc}")

    return status


def duplicate_profile_uids(rows) -> list[str]:
    """Return sorted non-empty template UIDs appearing more than once."""
    counts = {}
    for row in rows:
        try:
            uid = str(row["template_uid"] or "")
        except (TypeError, KeyError, IndexError):
            uid = str(getattr(row, "template_uid", "") or "")
        counts[uid] = counts.get(uid, 0) + 1
    return sorted(uid for uid, count in counts.items() if uid and count > 1)


def cached_foreground_mask_usable(mask: np.ndarray | None, foreground_required: bool) -> bool:
    """Accept empty masks only when foreground evidence is not mandatory."""
    if mask is None:
        return False
    if foreground_required:
        return bool(np.any(mask))
    return True


def foreground_plan_has_positive_selection(plan) -> bool:
    """Return True only when a manual plan proves foreground pixels exist.

    Review UI always carries an on_plan settings object (feather, GrabCut
    iterations, empty arrays). That metadata must not be mistaken for evidence
    that an occluding object actually exists.
    """
    if isinstance(plan, list):
        return len(plan) >= 3
    if not isinstance(plan, dict):
        return False
    return bool(plan.get("object_boxes") or plan.get("add_brush"))


def foreground_is_required(config: dict, on_plan) -> bool:
    """Fail closed only for source-reviewed/explicit foreground evidence."""
    return bool(
        (config or {}).get("has_occlusion")
        or foreground_plan_has_positive_selection(on_plan)
    )


def physical_orientation_verified(component_confidences) -> bool:
    """Return whether physical H/V provenance was explicitly trusted/reviewed."""
    payload = component_confidences
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except (TypeError, json.JSONDecodeError):
            return False
    if not isinstance(payload, dict):
        return False
    marker = payload.get("physical_orientation_verified")
    if isinstance(marker, str):
        return marker.strip().lower() in {"1", "true", "yes"}
    return bool(marker)


# ==============================================================================
# 3. AYARLAR.JSON YÜKLEYİCİ VE ŞABLON YÖNETİCİSİ
# ==============================================================================
import sqlite3


def open_sqlite_readonly(path: Path) -> sqlite3.Connection:
    """Open a SQLite database with an OS-enforced read-only connection."""
    uri = path.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.execute("PRAGMA query_only = ON")
    return conn


def load_ayarlar() -> dict:
    # SABLON_V2_MIMARI'daki SQLite db'sine baglanti
    db_path = USER_WORKSPACE_DIR / "SABLON_V2_MIMARI" / "ayarlar.db"
    
    # Eger db dosyasi yoksa fallback dondur
    if not db_path.exists():
        logger.warning(f"SQLite veritabanı bulunamadı: {db_path}. Fallback yükleniyor.")
        return {
            "bulut_ayarlari": {
                "imgbb_keys": [],
                "freeimage_key": os.environ.get("FREEIMAGE_KEY", "")
            },
            "kategoriler": {}
        }
        
    try:
        conn = open_sqlite_readonly(db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        result = {"kategoriler": {}}
        
        # 1. Genel Ayarlar
        c.execute("SELECT key, value FROM settings")
        for row in c.fetchall():
            try:
                result[row["key"]] = json.loads(row["value"])
            except (TypeError, json.JSONDecodeError) as exc:
                logger.warning(
                    f"Geçersiz settings JSON atlandı: {row['key']} ({exc})"
                )
            
        # 2. Kategoriler
        c.execute("SELECT id, label FROM categories")
        for row in c.fetchall():
            cat_id = row["id"]
            result["kategoriler"][cat_id] = {
                "etiket": row["label"],
                "sablonlar": {}
            }
            
        # 3. Şablonlar
        c.execute("SELECT category_id, filename, data FROM templates")
        for row in c.fetchall():
            cat_id = row["category_id"]
            tmpl = row["filename"]
            try:
                data = json.loads(row["data"])
            except (TypeError, json.JSONDecodeError) as exc:
                logger.warning(
                    f"Geçersiz şablon JSON atlandı: {cat_id}/{tmpl} ({exc})"
                )
                continue
            if not isinstance(data, dict):
                logger.warning(
                    f"Şablon verisi nesne değil, atlandı: {cat_id}/{tmpl}"
                )
                continue
            
            if cat_id not in result["kategoriler"]:
                result["kategoriler"][cat_id] = {"sablonlar": {}}
            if "sablonlar" not in result["kategoriler"][cat_id]:
                result["kategoriler"][cat_id]["sablonlar"] = {}
                
            result["kategoriler"][cat_id]["sablonlar"][tmpl] = data
            
        conn.close()
        return result
        
    except Exception as e:
        logger.error(f"SQLite (ayarlar.db) okuma hatası: {e}")
        return {"bulut_ayarlari": {}, "kategoriler": {}}

AYARLAR = load_ayarlar()

# ==============================================================================
# 4. SQLITE DURUM YÖNETİCİSİ (WAL Mode, Idempotent, Atomic Counter)
# ==============================================================================
class StateManager:
    def __init__(self, db_path: Path = None):
        self.db_path = db_path if db_path is not None else DB_PATH
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False, timeout=30)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA journal_mode = WAL")
        self._init_tables()

    def _init_tables(self):
        with db_lock, self.conn:
            self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS masters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                master_id TEXT UNIQUE NOT NULL,
                theme_id INTEGER,
                theme_title TEXT,
                style_key TEXT,
                horizontal_path TEXT,
                vertical_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sku TEXT UNIQUE NOT NULL,
                master_id TEXT NOT NULL,
                kategori_key TEXT NOT NULL,
                barkod TEXT NOT NULL,
                model_kodu TEXT NOT NULL,
                urun_adi TEXT,
                aciklama TEXT,
                ham_baski_dosyasi TEXT,
                mockup_dosyasi TEXT,
                magaza_grubu TEXT,
                resim_linki TEXT,
                status TEXT DEFAULT 'PENDING',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (master_id) REFERENCES masters(master_id)
            );

            CREATE TABLE IF NOT EXISTS system_meta (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS render_artifacts (
                artifact_key TEXT PRIMARY KEY,
                sku TEXT,
                source_identity TEXT,
                category TEXT,
                template_identity TEXT,
                local_output_path TEXT,
                upload_url TEXT,
                status TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_products_status ON products(status);
            CREATE INDEX IF NOT EXISTS idx_products_master ON products(master_id);
            """)

    def register_master(self, master_id: str, theme_id: int, theme_title: str,
                        style_key: str, h_path: str, v_path: str):
        with db_lock, self.conn:
            self.conn.execute("""
            INSERT INTO masters (master_id, theme_id, theme_title, style_key, horizontal_path, vertical_path)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(master_id) DO UPDATE SET
                theme_title=excluded.theme_title,
                horizontal_path=excluded.horizontal_path,
                vertical_path=excluded.vertical_path
            """, (master_id, theme_id, theme_title, style_key, h_path, v_path))

    def get_next_sequence(self, prefix: str) -> int:
        key = f"seq_{prefix}"
        with db_lock, self.conn:
            row = self.conn.execute("SELECT value FROM system_meta WHERE key = ?", (key,)).fetchone()
            current = int(row["value"]) if row else 0
            nxt = current + 1
            self.conn.execute("""
            INSERT INTO system_meta (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP
            """, (key, str(nxt)))
            return nxt

    def is_product_completed(self, sku: str) -> bool:
        with db_lock, self.conn:
            row = self.conn.execute("SELECT status FROM products WHERE sku = ?", (sku,)).fetchone()
            return row is not None and row["status"] == "COMPLETED"

    def get_artifact(self, artifact_key: str) -> Optional[dict]:
        with db_lock, self.conn:
            row = self.conn.execute(
                "SELECT * FROM render_artifacts WHERE artifact_key = ?",
                (artifact_key,),
            ).fetchone()
            return dict(row) if row is not None else None

    def is_artifact_completed(self, artifact_key: str) -> bool:
        row = self.get_artifact(artifact_key)
        # Legacy "UPLOADED" means cloud upload succeeded, but older code wrote
        # that state before the Excel row was durably flushed. Only COMPLETED
        # proves the full render -> upload -> Excel transaction finished.
        return row is not None and row.get("status") == "COMPLETED"

    def save_render_artifact(self, data: dict) -> bool:
        if not data:
            return False
        with db_lock, self.conn:
            try:
                self.conn.execute("""
                INSERT INTO render_artifacts (artifact_key, sku, source_identity, category, 
                                              template_identity, local_output_path, upload_url, status, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(artifact_key) DO UPDATE SET
                    sku=excluded.sku,
                    source_identity=excluded.source_identity,
                    category=excluded.category,
                    template_identity=excluded.template_identity,
                    local_output_path=excluded.local_output_path,
                    upload_url=excluded.upload_url,
                    status=excluded.status,
                    updated_at=CURRENT_TIMESTAMP
                """, (
                    data.get("artifact_key", ""), data.get("sku", ""), data.get("source_identity", ""),
                    data.get("category", ""), data.get("template_identity", ""),
                    data.get("local_output_path", ""), data.get("upload_url", ""), data.get("status", "COMPLETED")
                ))
                return True
            except Exception as exc:
                logging.getLogger("StateDB").error(
                    f"Veritabani yazim hatasi (save_render_artifact): {exc}"
                )
                return False

    def mark_artifacts_completed(
        self,
        artifact_keys: List[str],
        recipe_version: Optional[str] = None,
    ):
        keys = [str(key) for key in artifact_keys if key]
        if not keys:
            return
        with db_lock, self.conn:
            placeholders = ",".join("?" for _ in keys)
            sku_rows = self.conn.execute(
                f"""SELECT DISTINCT sku FROM render_artifacts
                    WHERE artifact_key IN ({placeholders})""",
                keys,
            ).fetchall()

            self.conn.executemany(
                """UPDATE render_artifacts
                   SET status='COMPLETED', updated_at=CURRENT_TIMESTAMP
                   WHERE artifact_key=?""",
                [(key,) for key in keys],
            )

            # The products row represents the current logical master/category
            # run. Historical recipe artifacts remain for audit/recovery but
            # must not permanently block a newer recipe from completing.
            recipe_suffix = (
                f"_{recipe_version}" if recipe_version else None
            )
            for row in sku_rows:
                sku = row["sku"]
                if recipe_suffix:
                    pending = self.conn.execute(
                        """SELECT COUNT(*) AS c
                           FROM render_artifacts
                           WHERE sku=?
                             AND status <> 'COMPLETED'
                             AND substr(artifact_key, ?) = ?""",
                        (sku, -len(recipe_suffix), recipe_suffix),
                    ).fetchone()["c"]
                else:
                    pending = self.conn.execute(
                        """SELECT COUNT(*) AS c
                           FROM render_artifacts
                           WHERE sku=?
                             AND status <> 'COMPLETED'""",
                        (sku,),
                    ).fetchone()["c"]
                if int(pending) == 0:
                    self.conn.execute(
                        """UPDATE products
                           SET status='COMPLETED',
                               updated_at=CURRENT_TIMESTAMP
                           WHERE sku=?""",
                        (sku,),
                    )

    def save_product(self, data: dict) -> bool:
        if not data:
            return False
        with db_lock, self.conn:
            try:
                self.conn.execute("""
                INSERT INTO products (sku, master_id, kategori_key, barkod, model_kodu,
                                     urun_adi, aciklama, ham_baski_dosyasi, mockup_dosyasi,
                                     magaza_grubu, resim_linki, status, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(sku) DO UPDATE SET
                    urun_adi=excluded.urun_adi,
                    aciklama=excluded.aciklama,
                    mockup_dosyasi=excluded.mockup_dosyasi,
                    resim_linki=excluded.resim_linki,
                    status=excluded.status,
                    updated_at=CURRENT_TIMESTAMP
                """, (
                    data.get("sku", ""), data.get("master_id", ""),
                    data.get("kategori_key") or data.get("category", ""),
                    data.get("barkod", ""), data.get("model_kodu", ""), data.get("urun_adi", ""),
                    data.get("aciklama", ""), data.get("ham_baski_dosyasi", ""), data.get("mockup_dosyasi", ""),
                    data.get("magaza_grubu", ""), data.get("resim_linki", ""), data.get("status", "COMPLETED")
                ))
                return True
            except Exception as exc:
                logging.getLogger("StateDB").error(
                    f"Veritabani yazim hatasi (save_product): {exc}"
                )
                return False

    def get_summary(self) -> dict:
        with db_lock, self.conn:
            cur = self.conn.execute("SELECT status, COUNT(*) as c FROM products GROUP BY status")
            return {r["status"]: r["c"] for r in cur.fetchall()}

    def get_completed_products(self) -> list:
        with db_lock, self.conn:
            cur = self.conn.execute("SELECT * FROM products WHERE status = 'COMPLETED' ORDER BY id")
            return [dict(r) for r in cur.fetchall()]

# ==============================================================================
# 5. ASENKRON ÇOK KATMANLI BULUT YÜKLEYİCİ (Thread Pool + Failover)
# ==============================================================================
class AsyncCloudUploader:
    def __init__(self):
        cloud_cfg = AYARLAR.get("bulut_ayarlari", {})
        configured_keys = cloud_cfg.get("imgbb_keys") or []
        env_keys = os.environ.get("IMGBB_KEYS", "").split(",")
        self.imgbb_keys = [
            str(key).strip()
            for key in (configured_keys or env_keys)
            if str(key).strip()
        ]
        self.freeimage_key = str(
            cloud_cfg.get("freeimage_key")
            or os.environ.get("FREEIMAGE_KEY", "")
            or ""
        ).strip()
        self.active_key_idx = 0
        self.key_lock = threading.Lock()
        self.freeimage_active = bool(self.freeimage_key)

    def has_provider(self) -> bool:
        with self.key_lock:
            has_imgbb = self.active_key_idx < len(self.imgbb_keys)
        return has_imgbb or (self.freeimage_active and bool(self.freeimage_key))

    def _get_imgbb_key(self):
        with self.key_lock:
            if self.active_key_idx >= len(self.imgbb_keys):
                return None
            return self.active_key_idx, self.imgbb_keys[self.active_key_idx]

    def _retire_imgbb_key(self, expected_idx: int, reason: str):
        with self.key_lock:
            # Another upload thread may already have advanced the pool. Never
            # advance twice for the same failed key.
            if self.active_key_idx == expected_idx:
                logger.warning(
                    f"ImgBB Key-{expected_idx + 1} devre dışı: {reason}. "
                    "Sıradaki anahtara geçiliyor..."
                )
                self.active_key_idx += 1

    def upload_sync(self, file_path: Path) -> Optional[str]:
        if not file_path.exists():
            return None

        # 1. ImgBB rotation. Credentials are never logged.
        while True:
            key_info = self._get_imgbb_key()
            if key_info is None:
                break
            key_idx, key = key_info

            try:
                with open(file_path, "rb") as handle:
                    res = requests.post(
                        "https://api.imgbb.com/1/upload",
                        data={"key": key},
                        files={"image": handle},
                        timeout=25,
                    )

                if res.status_code == 200:
                    try:
                        data = res.json()
                    except ValueError:
                        data = {}
                    url = data.get("data", {}).get("url")
                    if url:
                        return url
                    self._retire_imgbb_key(key_idx, "geçersiz başarı yanıtı")
                    continue

                body = (res.text or "").lower()
                if (
                    res.status_code in (400, 401, 403, 429)
                    or "rate limit" in body
                    or "quota" in body
                ):
                    self._retire_imgbb_key(
                        key_idx,
                        f"HTTP {res.status_code}",
                    )
                    continue

                logger.warning(
                    f"ImgBB geçici hata HTTP {res.status_code}; "
                    "aynı anahtar daha sonra tekrar denenebilir."
                )
                break
            except requests.RequestException as exc:
                logger.warning(f"ImgBB bağlantı hatası: {exc}")
                # Network failures do not prove the API key is bad; keep it.
                break
            except OSError as exc:
                logger.error(f"Yüklenecek dosya okunamadı: {exc}")
                return None

        # 2. FreeImage failover. Do not call the service with an empty key.
        if self.freeimage_active and self.freeimage_key:
            try:
                with open(file_path, "rb") as handle:
                    res = requests.post(
                        "https://freeimage.host/api/1/upload",
                        data={
                            "key": self.freeimage_key,
                            "action": "upload",
                            "format": "json",
                        },
                        files={"source": handle},
                        timeout=30,
                    )
                if res.status_code == 200:
                    try:
                        data = res.json()
                    except ValueError:
                        data = {}
                    url = data.get("image", {}).get("url")
                    if url:
                        return url

                if res.status_code in (400, 401, 403):
                    logger.warning(
                        f"FreeImage sağlayıcısı devre dışı: HTTP {res.status_code}"
                    )
                    self.freeimage_active = False
                else:
                    logger.warning(
                        f"FreeImage geçici hata: HTTP {res.status_code}"
                    )
            except requests.RequestException as exc:
                logger.warning(f"FreeImage bağlantı hatası: {exc}")
            except OSError as exc:
                logger.error(f"Yüklenecek dosya okunamadı: {exc}")
                return None

        return None

# ==============================================================================
# 6. SEO VE İÇERİK MOTORU
# ==============================================================================
class SeoEngine:
    def __init__(self):
        self.cache: Dict[str, dict] = {}
        self._init_keywords()

    def _init_keywords(self):
        for prod_key, prod_def in PRODUCT_CATALOG.items():
            folder = SEO_DIR / prod_key
            if not folder.exists():
                folder = SEO_DIR / prod_def.folder_name
            
            k_file = folder / "keywords.txt"
            a_file = folder / "aciklama_keywords.txt"

            # Sablonlar içindeki fallback kontrolü
            if not k_file.exists():
                alt_k = SABLON_DIR / prod_def.folder_name / "keywords.txt"
                if alt_k.exists():
                    k_file = alt_k
            if not a_file.exists():
                alt_a = SABLON_DIR / prod_def.folder_name / "aciklama_keywords.txt"
                if alt_a.exists():
                    a_file = alt_a

            kw_list = []
            if k_file.exists():
                with open(k_file, "r", encoding="utf-8") as f:
                    for line in f:
                        s = line.strip()
                        if s and not s.startswith("["):
                            kw_list.append(s)

            desc_text = f"Özel üretim yüksek çözünürlüklü {prod_def.etiket}."
            if a_file.exists():
                with open(a_file, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        desc_text = content

            self.cache[prod_key] = {
                "keywords": kw_list if kw_list else ["Modern", "Lüks Tasarım", "Dekoratif", "Premium"],
                "aciklama": desc_text
            }

    def generate_title(
        self,
        prod_key: str,
        theme_title: str,
        identity_seed: str = "",
    ) -> str:
        data = self.cache.get(prod_key, {"keywords": ["Dekoratif", "Modern", "Lüks"]})
        words = list(data["keywords"])
        prod_def = PRODUCT_CATALOG[prod_key]

        # Product metadata must be idempotent across upload/Excel retries.
        # Use a local deterministic RNG so the same logical product identity
        # always receives the same keyword selection without mutating global RNG.
        seed_material = f"{prod_key}|{theme_title}|{identity_seed}"
        seed_value = int(
            hashlib.sha256(seed_material.encode("utf-8")).hexdigest()[:16],
            16,
        )
        rng = random.Random(seed_value)
        sample_words = rng.sample(words, min(3, len(words)))
        clean_theme = theme_title.replace("_", " ").strip()
        
        # Trendyol için 80-100 karakter dengesi
        title = f"{clean_theme} {prod_def.etiket} {' '.join(sample_words)}"
        return title[:120]

    def get_description(self, prod_key: str, theme_title: str, style_key: str) -> str:
        data = self.cache.get(prod_key, {"aciklama": "Özel üretim dekoratif ürün."})
        base_desc = data["aciklama"]
        footer = f"\n\nTasarım Teması: {theme_title}\nSanat Stili: {style_key or 'Özel Koleksiyon'}"
        return base_desc + footer

# ==============================================================================
# 7. MOCKUP MOTORU (Anti-Border-Seam, Pad=0.03, OpenCV & PIL Homografi)
# ==============================================================================
# 7. AI KALİTE MOTORU (Real-ESRGAN Vulkan RTX)
# ==============================================================================
class RealESRGANQualityEngine:
    @staticmethod
    def get_exe_path() -> Optional[Path]:
        candidates = [
            USER_WORKSPACE_DIR
            / "AI_Kalite_Artirici"
            / "realesrgan-ncnn-vulkan.exe",
            SOURCE_ROOT
            / "AI_Kalite_Artirici"
            / "realesrgan-ncnn-vulkan.exe",
        ]
        for c in candidates:
            if c.exists():
                return c
        return None

    @classmethod
    def upscale_4k(cls, input_path: Path, output_path: Path) -> bool:
        exe = cls.get_exe_path()
        if not exe:
            return False

        models_dir = exe.parent / "models"
        cmd = [
            str(exe),
            "-i", str(input_path),
            "-o", str(output_path),
            "-m", str(models_dir),
            "-n", "realesrgan-x4plus",
            "-s", "4",
            "-t", "400"
        ]
        try:
            import subprocess
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            return output_path.exists()
        except Exception as e:
            logger.warning(f"Real-ESRGAN upscale atlandı: {e}")
            return False

# ==============================================================================
# 8. KALİTE KONTROL VE ÖNLEM MEKANİZMASI (Quality Inspector)
# ==============================================================================
class QualityInspector:
    @staticmethod
    def inspect_mockup(img_cv: np.ndarray, koseler: Optional[list] = None) -> Tuple[bool, str]:
        """
        Görselin kenar uzaması, piksellenme ve köşe taşması hatalarını denetler.
        """
        if img_cv is None or img_cv.size == 0:
            return False, "Görsel boş veya yüklenemedi"

        h, w = img_cv.shape[:2]
        if w < 500 or h < 500:
            return False, f"Çözünürlük çok düşük: {w}x{h}"

        # Kenar çizgilenme/tekrar hatası kontrolü (Edge streak test)
        if koseler and len(koseler) == 4:
            for pt in koseler:
                px, py = int(pt[0]), int(pt[1])
                if px < 0 or px >= w or py < 0 or py >= h:
                    return False, f"Köşe koordinatı görsel sınırları dışında: ({px}, {py})"

        # Gerçek Kalite Denetimi
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        if laplacian_var < 50:
            return False, f"Düşük kalite/Bulanık (Laplacian: {laplacian_var:.1f})"
        
        return True, f"Kalite Onaylandı (Keskinlik: {laplacian_var:.1f})"

# ==============================================================================
# 9. MOCKUP MOTORU (Optik Cam Parlaması, Bevel Pahı, Gün Işığı & Sıfır Kenar Hatası)
# ==============================================================================
class MockupRenderer:
    @staticmethod
    def build_foreground_mask(
        bg_cv: np.ndarray,
        on_plan: dict | list | None,
        base_mask: np.ndarray | None = None,
    ) -> np.ndarray:
        """
        Photoshop benzeri Object Selection & Brush mantığı.
        on_plan formatı:
        {
            "object_boxes": [[x1, y1, x2, y2], ...],
            "add_brush": [[x, y, radius], ...],
            "subtract_brush": [[x, y, radius], ...],
            "feather": 1.2,
            "grabcut_iterations": 5
        }
        veya geriye dönük uyumlu polygon listesi.
        """
        h, w = bg_cv.shape[:2]
        empty_mask = np.zeros((h, w), dtype=np.uint8)

        if base_mask is not None:
            base = np.asarray(base_mask)
            if base.ndim == 3:
                base = cv2.cvtColor(base.astype(np.uint8), cv2.COLOR_BGR2GRAY)
            if base.shape[:2] != (h, w):
                base = cv2.resize(base, (w, h), interpolation=cv2.INTER_NEAREST)
            working_base = np.clip(base, 0, 255).astype(np.uint8)
        else:
            working_base = empty_mask.copy()

        if not on_plan:
            return working_base

        # Eski polygon formatı geldiyse kırılmasın
        if isinstance(on_plan, list):
            if len(on_plan) >= 3:
                try:
                    pts = np.asarray(on_plan, dtype=np.int32)
                    mask = working_base.copy()
                    pts[:, 0] = np.clip(pts[:, 0], 0, w - 1)
                    pts[:, 1] = np.clip(pts[:, 1], 0, h - 1)
                    cv2.fillPoly(mask, [pts], 255)
                    mask = cv2.GaussianBlur(mask, (0, 0), 1.2)
                    return mask
                except Exception:
                    return working_base
            return working_base

        object_boxes = on_plan.get("object_boxes", [])
        add_brush = on_plan.get("add_brush", [])
        subtract_brush = on_plan.get("subtract_brush", [])
        feather = float(on_plan.get("feather", 1.2))
        iterations = int(on_plan.get("grabcut_iterations", 5))

        final_mask = working_base.copy()

        # 1. OBJECT SELECTION (Her kutu ayrı GrabCut'tan geçirilir)
        for box in object_boxes:
            if not box or len(box) != 4:
                continue
            try:
                x1, y1, x2, y2 = map(int, box)
            except Exception:
                continue

            x1, x2 = sorted((x1, x2))
            y1, y2 = sorted((y1, y2))
            x1 = int(np.clip(x1, 0, w - 1))
            x2 = int(np.clip(x2, 0, w - 1))
            y1 = int(np.clip(y1, 0, h - 1))
            y2 = int(np.clip(y2, 0, h - 1))

            rw = x2 - x1
            rh = y2 - y1
            if rw < 10 or rh < 10:
                continue

            gx = max(1, x1)
            gy = max(1, y1)
            gw = min(rw, w - gx - 1)
            gh = min(rh, h - gy - 1)
            if gw < 5 or gh < 5:
                continue

            gc_mask = np.zeros((h, w), dtype=np.uint8)
            bg_model = np.zeros((1, 65), dtype=np.float64)
            fg_model = np.zeros((1, 65), dtype=np.float64)

            try:
                cv2.grabCut(
                    bg_cv,
                    gc_mask,
                    (gx, gy, gw, gh),
                    bg_model,
                    fg_model,
                    iterations,
                    cv2.GC_INIT_WITH_RECT
                )
                object_mask = np.where(
                    (gc_mask == cv2.GC_FGD) | (gc_mask == cv2.GC_PR_FGD),
                    255,
                    0
                ).astype(np.uint8)
                final_mask = cv2.max(final_mask, object_mask)
            except cv2.error as exc:
                logger.warning(f"[MASK] GrabCut uyarisi: {exc}")
                cv2.rectangle(final_mask, (x1, y1), (x2, y2), 255, -1)

        # 2. MANUEL + FIRÇA
        for stroke in add_brush:
            if not stroke or len(stroke) < 2:
                continue
            x = int(np.clip(int(stroke[0]), 0, w - 1))
            y = int(np.clip(int(stroke[1]), 0, h - 1))
            radius = int(stroke[2] if len(stroke) >= 3 else 20)
            cv2.circle(final_mask, (x, y), max(1, radius), 255, -1, lineType=cv2.LINE_AA)

        # 3. MANUEL - FIRÇA
        for stroke in subtract_brush:
            if not stroke or len(stroke) < 2:
                continue
            x = int(np.clip(int(stroke[0]), 0, w - 1))
            y = int(np.clip(int(stroke[1]), 0, h - 1))
            radius = int(stroke[2] if len(stroke) >= 3 else 20)
            cv2.circle(final_mask, (x, y), max(1, radius), 0, -1, lineType=cv2.LINE_AA)

        if not np.any(final_mask):
            return final_mask

        # 4. MASK TEMİZLİĞİ (Morphology Close & Küçük Leke Filtresi)
        kernel_close = np.ones((3, 3), np.uint8)
        final_mask = cv2.morphologyEx(final_mask, cv2.MORPH_CLOSE, kernel_close, iterations=1)

        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(
            (final_mask > 127).astype(np.uint8),
            connectivity=8
        )
        cleaned = np.zeros_like(final_mask)
        min_component_area = max(20, int((w * h) * 0.000005))
        for i in range(1, num_labels):
            area = stats[i, cv2.CC_STAT_AREA]
            if area >= min_component_area:
                cleaned[labels == i] = 255
        final_mask = cleaned

        # 5. EDGE FEATHER (Kenar Yumuşatma)
        if feather > 0:
            final_mask = cv2.GaussianBlur(final_mask, (0, 0), feather)

        return final_mask

    @staticmethod
    def restore_foreground(
        rendered_cv: np.ndarray,
        original_bg_cv: np.ndarray,
        foreground_mask: np.ndarray
    ) -> np.ndarray:
        if foreground_mask is None or not np.any(foreground_mask):
            return rendered_cv

        alpha = foreground_mask.astype(np.float32) / 255.0
        if len(alpha.shape) == 2:
            alpha = alpha[..., None]

        rendered_f = rendered_cv.astype(np.float32)
        original_f = original_bg_cv.astype(np.float32)

        result = original_f * alpha + rendered_f * (1.0 - alpha)
        return np.clip(result, 0, 255).astype(np.uint8)

    @staticmethod
    def create_subpixel_antialiased_mask(h_bg: int, w_bg: int, dst_pts: np.ndarray, feather_px: float = 1.8) -> np.ndarray:
        """
        Sub-pixel Kenar Yumuşatma (Anti-Aliasing):
        2x Supersampling + Gaussian blur + Area downsampling.
        Merdiven (staircase) ve pikselleşme kesinlikle oluşmaz; kenar duvara pürüzsüzce kaynar.
        """
        scale = 2.0
        h_lg = int(h_bg * scale)
        w_lg = int(w_bg * scale)
        pts_lg = (dst_pts * scale).astype(np.int32)

        mask_lg = np.zeros((h_lg, w_lg), dtype=np.float32)
        cv2.fillConvexPoly(mask_lg, pts_lg, 1.0)

        ksize = int(round(feather_px * scale * 2.5)) | 1
        mask_lg_blur = cv2.GaussianBlur(mask_lg, (ksize, ksize), feather_px * scale * 0.5)
        mask_aa = cv2.resize(mask_lg_blur, (w_bg, h_bg), interpolation=cv2.INTER_AREA)
        return np.clip(mask_aa, 0.0, 1.0)

    @staticmethod
    def generate_window_reflection(gw: int, gh: int, intensity: float = 0.48) -> np.ndarray:
        """
        Referans tavuskuşu cam tablodaki mimari pencere yansıması:
        - 2x2 veya 3x2 belirgin koyu çıtalı (mullions) pencere kurgusu
        - Üst ve sağ kadrana oturan parlak günışığı cam bölmeleri
        - Cam yüzeyinde optik Fresnel derinliği
        """
        y, x = np.mgrid[0:gh, 0:gw].astype(np.float32)

        win_cx = gw * 0.72
        win_cy = gh * 0.32
        win_w = gw * 0.75
        win_h = gh * 0.65

        angle_rad = np.radians(-6.0)
        cos_a, sin_a = np.cos(angle_rad), np.sin(angle_rad)
        x_rot = (x - win_cx) * cos_a - (y - win_cy) * sin_a
        y_rot = (x - win_cx) * sin_a + (y - win_cy) * cos_a

        u = np.abs(x_rot) / (win_w * 0.5)
        v = np.abs(y_rot) / (win_h * 0.5)
        envelope = np.clip(1.0 - u**2.5, 0.0, 1.0) * np.clip(1.0 - v**2.5, 0.0, 1.0)
        envelope = cv2.GaussianBlur(envelope, (15, 15), 0)

        mullion_w = max(5, int(gw * 0.022))

        dist_v = np.abs(x_rot)
        bar_v = np.clip((dist_v - mullion_w * 0.5) / 1.8, 0.0, 1.0)

        dist_h = np.abs(y_rot)
        bar_h = np.clip((dist_h - mullion_w * 0.5) / 1.8, 0.0, 1.0)

        dist_h2 = np.abs(y_rot - win_h * 0.38)
        bar_h2 = np.clip((dist_h2 - mullion_w * 0.5) / 1.8, 0.0, 1.0)

        bars = bar_v * bar_h * bar_h2
        panes = envelope * bars

        glow = cv2.GaussianBlur(envelope, (45, 45), 0) * 0.25
        fresnel = ((x / float(gw)) * 0.65 + (1.0 - y / float(gh)) * 0.35) * 0.15

        refl = (panes * 0.85 + glow + fresnel) * intensity
        refl = np.clip(refl, 0.0, 0.85)

        return np.stack([refl * 1.0, refl * 0.98, refl * 0.96], axis=-1)

    @staticmethod
    def generate_glass_bevel(h_bg: int, w_bg: int, dst_pts: np.ndarray):
        """
        4mm Kristal Elmas Rodaj Kenar Pahı ve Cam Kalınlığı Kırılma Işıması.
        """
        bevel = np.zeros((h_bg, w_bg, 3), dtype=np.float32)
        p0, p1, p2, p3 = dst_pts[0], dst_pts[1], dst_pts[2], dst_pts[3]

        # 1. Üst kenar rodaj pırıltısı
        cv2.line(bevel, (int(p0[0]), int(p0[1])), (int(p1[0]), int(p1[1])), (1.0, 1.0, 1.0), 2, lineType=cv2.LINE_AA)
        # 2. Sol kenar rodaj pırıltısı
        cv2.line(bevel, (int(p0[0]), int(p0[1])), (int(p3[0]), int(p3[1])), (0.9, 0.95, 1.0), 2, lineType=cv2.LINE_AA)
        # 3. Sağ kenar ön yüz pırıltısı
        cv2.line(bevel, (int(p1[0]), int(p1[1])), (int(p2[0]), int(p2[1])), (0.95, 0.98, 1.0), 2, lineType=cv2.LINE_AA)

        # 4. Sağ kenar 4mm cam derinlik çizgisi (Sağa doğru 3px ofsetli)
        off_3d = np.array([3.0, 0.5], dtype=np.float32)
        p1_3d = p1 + off_3d
        p2_3d = p2 + off_3d
        cv2.line(bevel, (int(p1_3d[0]), int(p1_3d[1])), (int(p2_3d[0]), int(p2_3d[1])), (0.5, 0.6, 0.7), 1, lineType=cv2.LINE_AA)

        bevel = cv2.GaussianBlur(bevel, (3, 3), 0.4)
        return bevel

    @staticmethod
    def generate_kitchen_countertop_sheen(gw: int, gh: int, intensity: float = 0.24) -> np.ndarray:
        """
        Cam Doğrama (Kesme Tahtası) için Mutfak Tezgahı / Spot Işık Yansıması:
        - Mutfak tezgahı üstündeki dolap altı LED veya tavan spot ışığının cam kesme tahtası üzerindeki oval pırıltısı.
        """
        y, x = np.mgrid[0:gh, 0:gw].astype(np.float32)

        spot_cx = gw * 0.50
        spot_cy = gh * 0.35

        dx = (x - spot_cx) / (gw * 0.45)
        dy = (y - spot_cy) / (gh * 0.30)
        dist_sq = dx * dx + dy * dy

        spot = np.exp(-dist_sq * 1.8)
        spot_smooth = cv2.GaussianBlur(spot, (41, 41), 0)

        edge_glow = np.exp(-((y / float(gh)) - 0.05)**2 / 0.01) * 0.30
        total = np.clip((spot_smooth * 0.85 + edge_glow) * intensity, 0.0, 0.55)
        return np.stack([total * 1.0, total * 0.98, total * 0.95], axis=-1)

    @staticmethod
    def generate_sunlight_shadow_for_wood(image_cv: np.ndarray, dst_pts: np.ndarray, intensity: float = 0.15) -> np.ndarray:
        """
        Ahşap Tablolar ve Wifi Kutuları için Doğal Güneş & Pencere Gölgesi Yansıması:
        - Cam gibi ayna/parlama yapmaz.
        - Odaya vuran doğal sıcak güneş ışığı huzmeleri ve pencere kanadı gölgeleri (güneş ve gölge yansımaları).
        """
        h, w = image_cv.shape[:2]
        y, x = np.mgrid[0:h, 0:w].astype(np.float32)

        angle_rad = np.radians(35.0)
        u = (x * np.cos(angle_rad) - y * np.sin(angle_rad)) / float(max(w, h))

        freq = 2.8
        stripes = np.sin(u * np.pi * 2.0 * freq)
        stripes = np.tanh(stripes * 1.8) * 0.5 + 0.5
        stripes_smooth = cv2.GaussianBlur(stripes, (61, 61), 0)

        factor = 1.0 + (stripes_smooth - 0.5) * intensity
        sunlight_3c = np.stack([
            factor * (1.0 - (stripes_smooth - 0.5) * 0.04),
            factor * (1.0 + (stripes_smooth - 0.5) * 0.02),
            factor * (1.0 + (stripes_smooth - 0.5) * 0.06),
        ], axis=-1)

        result = np.clip(image_cv.astype(np.float32) * sunlight_3c, 0.0, 255.0)
        return result.astype(np.uint8)

    @staticmethod
    def generate_floating_shadow(h_bg: int, w_bg: int, dst_pts: np.ndarray, dx: float = 14.0, dy: float = 20.0) -> np.ndarray:
        """
        2cm Duvardan Önde Duran Gizli Asma Aparatı Derinlik Gölgesi.
        Çift katman: Yakın koyu temas gölgesi + geniş yumuşak tütsü gölgesi.
        """
        core = np.zeros((h_bg, w_bg), dtype=np.float32)
        offset_core = np.array([[dx * 0.35, dy * 0.35]] * 4, dtype=np.float32)
        cv2.fillConvexPoly(core, (dst_pts + offset_core).astype(np.int32), 0.40)
        core = cv2.GaussianBlur(core, (11, 11), 0)

        penumbra = np.zeros((h_bg, w_bg), dtype=np.float32)
        offset_pen = np.array([[dx, dy]] * 4, dtype=np.float32)
        cv2.fillConvexPoly(penumbra, (dst_pts + offset_pen).astype(np.int32), 0.28)
        penumbra = cv2.GaussianBlur(penumbra, (45, 45), 0)

        return np.clip(core + penumbra, 0.0, 0.65)

    @staticmethod
    def apply_architectural_daylight(image_cv: np.ndarray, angle: float = 32.0, intensity: float = 0.10) -> np.ndarray:
        """
        Tüm Mockuplara Doğal Günışığı & Pencere Gölgesi Efekti.
        Odaya pencereden süzülen yumuşak günışığı huzmelerini tablo ve duvara harmanlar.
        """
        h, w = image_cv.shape[:2]
        y, x = np.mgrid[0:h, 0:w].astype(np.float32)
        rad = np.radians(angle)
        u = (x * np.cos(rad) - y * np.sin(rad)) / float(max(w, h))

        freq = 3.2
        bands = np.sin(u * np.pi * 2.0 * freq)
        bands = np.tanh(bands * 1.5) * 0.5 + 0.5
        ksize = max(41, int(min(w, h) * 0.09) | 1)
        bands_diffuse = cv2.GaussianBlur(bands, (ksize, ksize), 0)

        daylight_factor = 1.0 + (bands_diffuse - 0.5) * intensity
        daylight_3c = np.stack([
            daylight_factor * (1.0 - (bands_diffuse - 0.5) * 0.02),
            daylight_factor,
            daylight_factor * (1.0 + (bands_diffuse - 0.5) * 0.03)
        ], axis=-1)

        result = np.clip(image_cv.astype(np.float32) * daylight_3c, 0.0, 255.0)
        return result.astype(np.uint8)

    @staticmethod
    def match_color_cast(art_cv: np.ndarray, bg_cv: np.ndarray, poly_mask: np.ndarray) -> np.ndarray:
        """
        Ortam Renk Isısı Harmanlama: Arka planın (odanın) ortalama renk ısısını
        (sarımsı, mavimsi vb.) analiz edip tasarıma hafif bir White Balance kayması uygular.
        """
        poly_indices = poly_mask > 0.05
        if not np.any(poly_indices):
            return art_cv

        bg_mean = np.mean(bg_cv[poly_indices], axis=0) # [B, G, R]
        bg_lum = np.mean(bg_mean)
        if bg_lum < 10.0: 
            return art_cv
        
        # Sadece renk oranını al (parlaklık Ambient Luminance'da zaten işlendi)
        color_ratios = bg_mean / bg_lum
        
        # Etkiyi %40 civarında sınırlıyoruz (sinematik blend)
        blend_factor = 0.40
        adjusted_ratios = 1.0 + (color_ratios - 1.0) * blend_factor
        
        art_float = art_cv.astype(np.float32)
        art_float[:, :, 0] *= adjusted_ratios[0]
        art_float[:, :, 1] *= adjusted_ratios[1]
        art_float[:, :, 2] *= adjusted_ratios[2]
        
        return np.clip(art_float, 0, 255).astype(np.float32)

    @staticmethod
    def apply_chromatic_aberration(image_cv: np.ndarray, intensity: int = 1) -> np.ndarray:
        """
        Lens Sapması (Chromatic Aberration): Kamera lenslerinin köşelerde yarattığı
        RGB kırılmasını taklit eder. Gerçek fotoğraf hissini artırır.
        """
        image_uint8 = np.clip(image_cv, 0, 255).astype(np.uint8)
        b, g, r = cv2.split(image_uint8)
        
        # R kanalını hafif sağ-aşağı kaydır
        M_r = np.float32([[1, 0, intensity], [0, 1, intensity]])
        r_shifted = cv2.warpAffine(r, M_r, (r.shape[1], r.shape[0]), borderMode=cv2.BORDER_REPLICATE)
        
        # B kanalını hafif sol-yukarı kaydır
        M_b = np.float32([[1, 0, -intensity], [0, 1, -intensity]])
        b_shifted = cv2.warpAffine(b, M_b, (b.shape[1], b.shape[0]), borderMode=cv2.BORDER_REPLICATE)
        
        merged = cv2.merge((b_shifted, g, r_shifted))
        return merged.astype(np.float32)

    @staticmethod
    def apply_camera_grain(image_cv: np.ndarray, intensity: float = 3.5, seed: int = None) -> np.ndarray:
        """
        Film Greni: Sensör kumlanmasını sentetik olarak üretir.
        Parlak ve karanlık alanlarda az, orta tonlarda çok kumlanma yapar.
        """
        h, w = image_cv.shape[:2]
        rng = np.random.default_rng(seed)
        noise = rng.normal(0, intensity, (h, w, 3)).astype(np.float32)
        
        lum = cv2.cvtColor(np.clip(image_cv, 0, 255).astype(np.uint8), cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
        # 4*x*(1-x) parabolü ile orta tonları (0.5) maksimize eder, 0 ve 1'i minimize eder
        noise_mask = 4.0 * lum * (1.0 - lum)
        noise_mask = np.clip(noise_mask + 0.15, 0.0, 1.0)
        noise_mask_3c = np.stack([noise_mask] * 3, axis=-1)
        
        return image_cv + (noise * noise_mask_3c)

    @staticmethod
    def resolve_print_mask(
        quad_mask_f: np.ndarray,
        alpha_mask: np.ndarray | None,
        target_width: int,
        target_height: int,
    ) -> np.ndarray:
        """Combine reviewed quad with a meaningful transparent print hole.

        Ordinary RGBA PNGs are often fully opaque. Treating their alpha channel
        as a cut-out would zero the artwork mask and produce a technically
        successful render with no visible design. Alpha restricts the reviewed
        quad only when there is meaningful transparency inside that quad.
        """
        quad_mask_f = np.clip(quad_mask_f.astype(np.float32), 0.0, 1.0)
        if alpha_mask is None:
            return quad_mask_f

        alpha = alpha_mask
        if alpha.ndim == 3:
            alpha = cv2.cvtColor(alpha, cv2.COLOR_BGR2GRAY)
        if alpha.shape[:2] != (target_height, target_width):
            alpha = cv2.resize(
                alpha,
                (target_width, target_height),
                interpolation=cv2.INTER_LINEAR,
            )
        transparent_hole = 1.0 - (alpha.astype(np.float32) / 255.0)
        inside = quad_mask_f > 0.10
        if not np.any(inside):
            raise ValueError("Approved quad produced an empty print mask")

        # Require a real transparent region inside the approved surface.
        transparent_fraction = float(
            np.mean(transparent_hole[inside] > 0.10)
        )
        if transparent_fraction < 0.02:
            return quad_mask_f

        restricted = np.clip(transparent_hole * quad_mask_f, 0.0, 1.0)
        restricted_pixels = int(np.count_nonzero(restricted > 0.05))
        quad_pixels = int(np.count_nonzero(inside))
        if restricted_pixels < max(64, int(quad_pixels * 0.02)):
            return quad_mask_f
        return restricted

    @staticmethod
    def render_cv2_optik(
        art_cv: np.ndarray,
        bg_cv: np.ndarray,
        koseler: list,
        is_glass: bool,
        on_plan=None,
        template_name: str = None,
        category_name: str = None,
        orig_bg_cv: np.ndarray = None,
        alpha_mask: np.ndarray = None,
        source_design_identity: str = None,
        template_identity: str = None,
        recipe_version: str = None,
        template_sha: str = None,
        auto_foreground: bool = False,
        foreground_required: bool = False,
        camera_artifacts: bool = False,
    ) -> np.ndarray:
        h_bg, w_bg = bg_cv.shape[:2]
        h_art, w_art = art_cv.shape[:2]
        p = np.float32(koseler)  # [TL, TR, BR, BL]

        # -------------------------------------------------------------
        # 1. CONTENT-SAFE PERSPECTIVE INPUT
        # -------------------------------------------------------------
        # The projected quad aspect is NOT the physical print aspect. Cropping
        # the artwork against that projected ratio can remove text/content and
        # was explicitly unsafe for marketplace designs. The full source
        # artwork is therefore preserved and mapped as a single physical plane.
        w_top = np.linalg.norm(p[1] - p[0])
        w_bot = np.linalg.norm(p[2] - p[3])
        h_left = np.linalg.norm(p[3] - p[0])
        h_right = np.linalg.norm(p[2] - p[1])
        target_w = max(1.0, (w_top + w_bot) / 2.0)
        target_h = max(1.0, (h_left + h_right) / 2.0)
        art_fitted = art_cv

        # -------------------------------------------------------------
        # 2. SUB-PIXEL PERSPEKTİF HOMOGRAFİ & KENAR YUMUŞATMA (ANTI-ALIASING)
        # -------------------------------------------------------------
        fh, fw = art_fitted.shape[:2]
        src_pts = np.float32([[0, 0], [fw, 0], [fw, fh], [0, fh]])
        dst_pts = np.float32(koseler)
        matrix = cv2.getPerspectiveTransform(src_pts, dst_pts)

        warped = cv2.warpPerspective(
            art_fitted, matrix, (w_bg, h_bg),
            flags=cv2.INTER_LANCZOS4,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(0, 0, 0)
        )

        # 2x supersampled approved-quad mask is always the hard spatial
        # safety boundary. A transparent passepartout may further restrict the
        # printable hole, but it can never expand artwork outside the quad.
        quad_mask_f = MockupRenderer.create_subpixel_antialiased_mask(
            h_bg,
            w_bg,
            dst_pts,
            feather_px=1.8,
        )
        mask_f = MockupRenderer.resolve_print_mask(
            quad_mask_f,
            alpha_mask,
            w_bg,
            h_bg,
        )
        mask_3c = np.stack([mask_f] * 3, axis=-1)

        # -------------------------------------------------------------
        # 3. ORTAM IŞIĞI HARMANLAMA (AMBIENT LUMINANCE MAPPING)
        # -------------------------------------------------------------
        bg_gray = cv2.cvtColor(bg_cv, cv2.COLOR_BGR2GRAY).astype(np.float32)
        poly_indices = mask_f > 0.05
        if np.any(poly_indices):
            mean_lum = float(np.mean(bg_gray[poly_indices]))
            if mean_lum > 10.0:
                bg_smooth = cv2.GaussianBlur(bg_gray, (65, 65), 0)
                ambient_ratio = np.clip(bg_smooth / mean_lum, 0.75, 1.35)
                ambient_ratio_3c = np.stack([ambient_ratio] * 3, axis=-1)
                warped_f = warped.astype(np.float32)
                warped_lit = warped_f * ((1.0 - 0.18) + 0.18 * ambient_ratio_3c)
            else:
                warped_lit = warped.astype(np.float32)
        else:
            warped_lit = warped.astype(np.float32)

        # --- İLERİ SEVİYE SİNEMATİK POST-PROCESSING (FOTOGERÇEKÇİLİK) ---
        # 1. Ortam Renk Isısı Harmanlama (White Balance Match)
        warped_lit = MockupRenderer.match_color_cast(warped_lit, bg_cv, mask_f)
        
        # 2-3. Optional camera artifacts. Marketplace product imagery
        # defaults to maximum sharpness; cinematic grain/channel shift must be
        # explicitly opted in per template.
        if camera_artifacts:
            warped_lit = MockupRenderer.apply_chromatic_aberration(
                warped_lit,
                intensity=0.55,
            )
            seed = None
            if source_design_identity and template_identity and recipe_version:
                import hashlib
                h = hashlib.sha256(
                    f"{source_design_identity}_{template_identity}_{recipe_version}".encode()
                ).hexdigest()
                seed = int(h[:8], 16)
            warped_lit = MockupRenderer.apply_camera_grain(
                warped_lit,
                intensity=1.25,
                seed=seed,
            )
        # ----------------------------------------------------------------

        # -------------------------------------------------------------
        # 4. KATEGORİYE ÖZEL YANSIMA VE GÖLGE MOTORU
        # -------------------------------------------------------------
        is_cam_dograma = (category_name == "04_Cam_Dograma")
        is_wood_or_wifi = (category_name in ["03_Ahsap_Tablo", "01_Wifi_Kutusu"])

        # Optical overlays are generated in the same source coordinate
        # system as the artwork because they use the artwork homography.
        # Generating them at projected-quad dimensions and reusing this matrix
        # would apply the wrong coordinate transform.
        effect_w, effect_h = fw, fh

        if is_cam_dograma:
            # A) CAM DOĞRAMA / KESME TAHTASI: Mutfak Tezgahı & Dolap Altı Spot Işık Yansıması + Rodaj Kenar
            spot_sheen = MockupRenderer.generate_kitchen_countertop_sheen(
                effect_w,
                effect_h,
                intensity=0.25,
            )
            spot_warped = cv2.warpPerspective(
                spot_sheen, matrix, (w_bg, h_bg),
                flags=cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=(0, 0, 0)
            )
            warped_norm = np.clip(warped_lit / 255.0, 0.0, 1.0)
            glass_art_norm = 1.0 - (1.0 - warped_norm) * (1.0 - spot_warped)

            # 4mm Elmas Rodaj Kenar ve Cam Kalınlığı Kırılması
            bevel_light = MockupRenderer.generate_glass_bevel(h_bg, w_bg, dst_pts)
            glass_surface = np.clip(glass_art_norm + bevel_light, 0.0, 1.0) * 255.0

            # Tezgah yüzeyine düşen ince temas gölgesi
            shadow_dog = np.zeros((h_bg, w_bg), dtype=np.float32)
            cv2.fillConvexPoly(shadow_dog, (dst_pts + np.array([[6, 10]] * 4)).astype(np.int32), 0.35)
            shadow_dog = cv2.GaussianBlur(shadow_dog, (21, 21), 0)
            shadow_out = shadow_dog * (1.0 - mask_f)
            bg_shadowed = bg_cv.astype(np.float32) * (1.0 - np.stack([shadow_out] * 3, axis=-1))

            final = bg_shadowed * (1.0 - mask_3c) + glass_surface * mask_3c

        elif is_glass and not is_wood_or_wifi:
            # B) CAM TABLOLAR: Tavuskuşu Referanslı Mimari Pencere Yansıması & 4mm Rodaj
            total_shadow = MockupRenderer.generate_floating_shadow(h_bg, w_bg, dst_pts)
            shadow_outside = total_shadow * (1.0 - mask_f)
            bg_shadowed = bg_cv.astype(np.float32) * (1.0 - np.stack([shadow_outside] * 3, axis=-1))

            refl_local = MockupRenderer.generate_window_reflection(
                effect_w,
                effect_h,
                intensity=0.48,
            )
            refl_warped = cv2.warpPerspective(
                refl_local, matrix, (w_bg, h_bg),
                flags=cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=(0, 0, 0)
            )

            # Screen blend: 1 - (1 - art) * (1 - refl)
            warped_norm = np.clip(warped_lit / 255.0, 0.0, 1.0)
            glass_art_norm = 1.0 - (1.0 - warped_norm) * (1.0 - refl_warped)

            # 4mm Elmas Rodaj Kenar ve Kırılma Işıması
            bevel_light = MockupRenderer.generate_glass_bevel(h_bg, w_bg, dst_pts)
            glass_surface = np.clip(glass_art_norm + bevel_light, 0.0, 1.0) * 255.0

            final = bg_shadowed * (1.0 - mask_3c) + glass_surface * mask_3c

        else:
            # C) AHŞAP TABLOLAR & WİFİ KUTULARI: Çerçeve İçi Gölge + Doğal Güneş & Gölge
            inner_shadow = np.zeros((h_bg, w_bg), dtype=np.float32)
            p0, p1, _, p3 = dst_pts[0], dst_pts[1], dst_pts[2], dst_pts[3]
            cv2.line(inner_shadow, (int(p0[0]), int(p0[1])), (int(p1[0]), int(p1[1])), 0.38, 5, lineType=cv2.LINE_AA)
            cv2.line(inner_shadow, (int(p0[0]), int(p0[1])), (int(p3[0]), int(p3[1])), 0.38, 5, lineType=cv2.LINE_AA)
            inner_shadow = cv2.GaussianBlur(inner_shadow, (9, 9), 0)
            inner_shadow_3c = np.stack([inner_shadow] * 3, axis=-1)

            wood_surface = np.clip(warped_lit * (1.0 - inner_shadow_3c), 0.0, 255.0)
            final = bg_cv.astype(np.float32) * (1.0 - mask_3c) + wood_surface * mask_3c

        # Preserve the realism stack (ambient light, glass reflection,
        # bevel, shadows, material response) while restoring bounded fine
        # artwork detail that those low-frequency effects can soften.
        detail_strength = 0.52 if is_glass else 0.42
        final = MockupRenderer.restore_artwork_microdetail(
            np.clip(final, 0, 255).astype(np.uint8),
            warped_lit,
            mask_f,
            strength=detail_strength,
        )

        # ---------------------------------------------------------
        # FOREGROUND / OCCLUSION RESTORE
        # Automatic Grounding-DINO + SAM cache, then manual refinement.
        # AI is lazy-loaded only when a template has no usable cached mask.
        # ---------------------------------------------------------
        fg_mask = None
        cache_file = None
        cache_loaded = False
        foreground_analysis_completed = not auto_foreground
        foreground_failure_reason = None
        try:
            source_for_mask = orig_bg_cv if orig_bg_cv is not None else bg_cv
            h_mask, w_mask = source_for_mask.shape[:2]

            def _normalize_mask(mask):
                if mask is None:
                    return None
                if mask.ndim == 3:
                    mask = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
                if mask.shape[:2] != (h_mask, w_mask):
                    mask = cv2.resize(mask, (w_mask, h_mask), interpolation=cv2.INTER_NEAREST)
                return np.clip(mask, 0, 255).astype(np.uint8)

            def _read_mask(mask_path: Path):
                if not mask_path or not mask_path.exists():
                    return None
                try:
                    decoded = cv2.imdecode(
                        np.fromfile(str(mask_path), dtype=np.uint8),
                        cv2.IMREAD_GRAYSCALE,
                    )
                    return _normalize_mask(decoded)
                except Exception as exc:
                    logger.warning(f"[MASK] Cache okunamadı {mask_path.name}: {exc}")
                    return None

            def _save_mask_atomic(mask_path: Path, mask):
                normalized = _normalize_mask(mask)
                if normalized is None:
                    return False
                mask_path.parent.mkdir(parents=True, exist_ok=True)
                ok, encoded = cv2.imencode(".png", normalized)
                if not ok:
                    return False
                tmp_path = mask_path.with_name(mask_path.name + ".tmp")
                encoded.tofile(str(tmp_path))
                os.replace(tmp_path, mask_path)
                return True

            if template_name:
                stem = Path(template_name).stem
                safe_cat = category_name if category_name else "default"
                mask_analyzer_version = "v3_auto_ai"
                cache_name = (
                    f"{safe_cat}_{template_sha}_{mask_analyzer_version}_mask.png"
                    if template_sha
                    else f"{safe_cat}_{stem}_{mask_analyzer_version}_mask.png"
                )
                cache_file = MASK_CACHE_DIR / cache_name

                fg_mask = _read_mask(cache_file)
                cache_loaded = cached_foreground_mask_usable(
                    fg_mask,
                    foreground_required,
                )
                if cache_loaded:
                    foreground_analysis_completed = True
                elif fg_mask is not None and foreground_required:
                    logger.warning(
                        "[MASK] Occlusion-kritik şablonda boş cache güvenilir "
                        f"sayılmadı: {cache_file.name}"
                    )
                    fg_mask = None

                # Never auto-promote filename-only legacy masks into production.
                # Those files are not bound to source bytes and can become stale
                # when a template image is replaced under the same filename.
                # Production accepts only the source-hash cache name above,
                # a current hash-bound manual plan, or a fresh AI result.

            # Fully automatic object-aware occlusion discovery. The heavy AI
            # dependencies are imported lazily so normal categories/startup do
            # not pay the model cost.
            if auto_foreground and not cache_loaded:
                try:
                    from foreground_ai import ForegroundAIEngine

                    ai_cfg = on_plan if isinstance(on_plan, dict) else {}
                    ai_result = ForegroundAIEngine.get_instance().detect_foreground(
                        source_for_mask,
                        dst_pts.astype(float).tolist(),
                        prompts=ai_cfg.get("ai_prompts"),
                        box_threshold=float(ai_cfg.get("ai_box_threshold", 0.20)),
                        text_threshold=float(ai_cfg.get("ai_text_threshold", 0.20)),
                        min_surface_overlap=float(ai_cfg.get("ai_min_surface_overlap", 0.02)),
                        feather=float(ai_cfg.get("ai_feather", 1.0)),
                    )
                    if ai_result.get("success") and ai_result.get("mask") is not None:
                        proposed_mask = _normalize_mask(ai_result["mask"])
                        detected_objects = ai_result.get("objects") or []
                        has_foreground_pixels = bool(
                            proposed_mask is not None
                            and np.any(proposed_mask)
                        )

                        # A profile explicitly marked as occluded is trusted
                        # evidence that foreground exists. If zero-shot AI says
                        # "nothing found", do not turn that false-negative into
                        # a permanent empty cache and silently paint over the
                        # known object. A reviewed manual plan can still satisfy
                        # the requirement below.
                        if (
                            foreground_required
                            and not detected_objects
                            and not has_foreground_pixels
                        ):
                            foreground_failure_reason = (
                                "known occlusion but AI detected no foreground"
                            )
                            logger.warning(
                                "[MASK_AI] Bilinen occlusion için nesne bulunamadı; "
                                "boş maske production cache'e yazılmadı."
                            )
                        else:
                            fg_mask = proposed_mask
                            cache_loaded = True
                            foreground_analysis_completed = True
                            if cache_file is not None:
                                _save_mask_atomic(cache_file, fg_mask)
                            logger.info(
                                "[MASK_AI] Otomatik ön plan analizi tamamlandı: "
                                f"{len(detected_objects)} nesne, "
                                f"confidence={ai_result.get('confidence', 0.0)}"
                            )
                    else:
                        foreground_failure_reason = str(
                            ai_result.get("reason", "unknown")
                        )
                        logger.warning(
                            "[MASK_AI] Otomatik ön plan analizi sonuç vermedi: "
                            f"{foreground_failure_reason}"
                        )
                except Exception as exc:
                    foreground_failure_reason = str(exc)
                    logger.warning(
                        f"[MASK_AI] Otomatik maskeleme kullanılamadı: {exc}"
                    )

            # Manual Object Selection / brush corrections are additive to the
            # automatic mask. Subtract brush remains handled inside on_plan.
            if on_plan:
                # Apply Object Selection + add/subtract brushes on top of the
                # AI/cache mask so the subtract brush can genuinely correct a
                # false-positive automatic region.
                fg_mask = MockupRenderer.build_foreground_mask(
                    source_for_mask,
                    on_plan,
                    base_mask=fg_mask,
                )
                fg_mask = _normalize_mask(fg_mask)

                # A reviewed positive manual selection is sufficient evidence
                # even when the optional AI path is unavailable. A subtract-
                # only plan is not sufficient without an AI/cache base mask.
                if isinstance(on_plan, list):
                    if len(on_plan) >= 3:
                        foreground_analysis_completed = True
                elif isinstance(on_plan, dict):
                    if on_plan.get("object_boxes") or on_plan.get("add_brush"):
                        foreground_analysis_completed = True

            if auto_foreground and not foreground_analysis_completed:
                raise RuntimeError(
                    "Occlusion-safe render blocked: foreground analysis "
                    "did not complete"
                    + (
                        f" ({foreground_failure_reason})"
                        if foreground_failure_reason
                        else ""
                    )
                )

            if fg_mask is not None and np.any(fg_mask):
                final = MockupRenderer.restore_foreground(
                    final,
                    source_for_mask,
                    fg_mask,
                )
        except Exception as e:
            if auto_foreground:
                # For occlusion-sensitive templates an uncertain foreground
                # result is worse than a failed render. Propagate so the factory
                # can quarantine/retry instead of silently painting over objects.
                raise
            logger.warning(f"[FOREGROUND_RESTORE] Ön plan geri yükleme hatası: {e}")

        # ---------------------------------------------------------
        # 5. GÜNEŞ & PENCERE GÖLGESİ (Ahşap & Wifi için sıcak güneş, diğerleri için genel günışığı)
        # ---------------------------------------------------------
        if is_wood_or_wifi:
            final = MockupRenderer.generate_sunlight_shadow_for_wood(final, dst_pts, intensity=0.15)
        else:
            final = MockupRenderer.apply_architectural_daylight(final, angle=32.0, intensity=0.08)

        return final

    @staticmethod
    def prepare_artwork_for_nominal_aspect(
        image_cv: np.ndarray,
        nominal_aspect,
        max_direct_fit_error: float = 0.15,
    ) -> np.ndarray:
        """Validate aspect compatibility without manufacturing edge pixels.

        Older code padded modest ratio differences with BORDER_REPLICATE. That
        copied the outermost ornament/background pixels into long horizontal or
        vertical streaks after perspective projection. For compatible master
        variants we keep every real source pixel and let the physical homography
        perform the modest aspect fit. Large mismatches are rejected instead of
        silently cropping, stretching via an intermediate resize, or inventing
        fake edge content.
        """
        if image_cv is None or image_cv.size == 0:
            raise ValueError("Artwork is empty")

        try:
            target_ratio = float(nominal_aspect)
        except (TypeError, ValueError):
            return image_cv
        if not np.isfinite(target_ratio) or target_ratio <= 0:
            return image_cv

        h, w = image_cv.shape[:2]
        if h <= 0 or w <= 0:
            raise ValueError("Artwork dimensions are invalid")

        source_ratio = w / float(h)
        relative_error = abs(source_ratio - target_ratio) / target_ratio
        if relative_error <= 0.005:
            return image_cv

        if relative_error > max_direct_fit_error:
            raise ValueError(
                f"Artwork aspect mismatch too large: {source_ratio:.4f} "
                f"vs physical {target_ratio:.4f}"
            )

        # Important: do not pad with replicated/mirrored pixels here. The
        # perspective transform below maps the complete source artwork to the
        # reviewed physical surface in one sampling operation.
        return image_cv

    @staticmethod
    def prepare_marketplace_canvas(
        image_cv: np.ndarray,
        target_width: int = 1200,
        target_height: int = 1600,
    ) -> np.ndarray:
        """Return a marketplace-ready 3:4 canvas without cropping the scene.

        The primary rendered template is always fitted with "contain" semantics:
        no content is cropped and no non-uniform stretch is applied. If the
        template aspect differs from the marketplace canvas, a heavily blurred
        cover copy is used only as background extension.
        """
        if image_cv is None or image_cv.size == 0:
            raise ValueError("Marketplace canvas received an empty image")
        if target_width <= 0 or target_height <= 0:
            raise ValueError("Marketplace output dimensions must be positive")

        src_h, src_w = image_cv.shape[:2]
        if src_w <= 0 or src_h <= 0:
            raise ValueError("Marketplace source dimensions are invalid")

        src_ratio = src_w / float(src_h)
        target_ratio = target_width / float(target_height)

        # Near-identical aspect: a uniform resize is sufficient.
        if abs(src_ratio - target_ratio) <= 0.01:
            return cv2.resize(
                image_cv,
                (target_width, target_height),
                interpolation=cv2.INTER_LANCZOS4,
            )

        # Background extension may be cropped because it is decorative only.
        cover_scale = max(
            target_width / float(src_w),
            target_height / float(src_h),
        )
        cover_w = max(target_width, int(round(src_w * cover_scale)))
        cover_h = max(target_height, int(round(src_h * cover_scale)))
        cover = cv2.resize(
            image_cv,
            (cover_w, cover_h),
            interpolation=cv2.INTER_LANCZOS4,
        )
        x0 = max(0, (cover_w - target_width) // 2)
        y0 = max(0, (cover_h - target_height) // 2)
        background = cover[
            y0:y0 + target_height,
            x0:x0 + target_width,
        ].copy()

        # Strong blur prevents the extension from looking like duplicated
        # product content while preserving the scene's overall light/color.
        sigma = max(12.0, min(target_width, target_height) * 0.025)
        background = cv2.GaussianBlur(background, (0, 0), sigmaX=sigma, sigmaY=sigma)

        contain_scale = min(
            target_width / float(src_w),
            target_height / float(src_h),
        )
        fitted_w = max(1, int(round(src_w * contain_scale)))
        fitted_h = max(1, int(round(src_h * contain_scale)))
        fitted = cv2.resize(
            image_cv,
            (fitted_w, fitted_h),
            interpolation=cv2.INTER_LANCZOS4,
        )

        x1 = (target_width - fitted_w) // 2
        y1 = (target_height - fitted_h) // 2

        # A narrow feather hides the rectangular join without materially
        # changing the actual mockup/product region.
        alpha = np.ones((fitted_h, fitted_w), dtype=np.float32)
        feather_px = max(2, int(round(min(fitted_w, fitted_h) * 0.006)))
        if feather_px > 1:
            alpha[:feather_px, :] = 0.0
            alpha[-feather_px:, :] = 0.0
            alpha[:, :feather_px] = 0.0
            alpha[:, -feather_px:] = 0.0
            alpha = cv2.GaussianBlur(
                alpha,
                (0, 0),
                sigmaX=max(1.0, feather_px * 0.45),
                sigmaY=max(1.0, feather_px * 0.45),
            )
            alpha = np.clip(alpha, 0.0, 1.0)

        roi = background[y1:y1 + fitted_h, x1:x1 + fitted_w].astype(np.float32)
        fitted_f = fitted.astype(np.float32)
        alpha_3c = alpha[..., None]
        blended = fitted_f * alpha_3c + roi * (1.0 - alpha_3c)
        background[y1:y1 + fitted_h, x1:x1 + fitted_w] = np.clip(
            blended, 0, 255
        ).astype(np.uint8)
        return background

    @staticmethod
    def compute_quality_render_scale(
        source_width: int,
        source_height: int,
        output_width: int,
        output_height: int,
        max_scale: float = 2.5,
    ) -> float:
        """Render above template-native resolution when final output needs it.

        Optical/material effects are evaluated on this larger working canvas,
        then the finished scene is reduced only once for marketplace output.
        """
        if source_width <= 0 or source_height <= 0:
            return 1.0
        requested = max(
            output_width / float(source_width),
            output_height / float(source_height),
        )
        return float(np.clip(requested, 1.0, max_scale))

    @staticmethod
    def restore_artwork_microdetail(
        final_cv: np.ndarray,
        warped_art_cv: np.ndarray,
        mask_f: np.ndarray,
        strength: float = 0.45,
    ) -> np.ndarray:
        """Restore artwork microdetail while protecting the physical perimeter.

        Only high-frequency detail is reintroduced. The mask is contracted and
        softly feathered first so sharpening never creates ringing/halos on the
        outer product boundary.
        """
        if final_cv is None or warped_art_cv is None:
            return final_cv

        base = warped_art_cv.astype(np.float32)
        low = cv2.GaussianBlur(base, (0, 0), sigmaX=0.85, sigmaY=0.85)
        detail = np.clip(base - low, -24.0, 24.0)

        mask = np.clip(mask_f.astype(np.float32), 0.0, 1.0)
        binary = (mask > 0.20).astype(np.uint8)
        if np.any(binary):
            kernel = np.ones((5, 5), np.uint8)
            safe_core = cv2.erode(binary, kernel, iterations=1).astype(np.float32)
            safe_core = cv2.GaussianBlur(
                safe_core,
                (0, 0),
                sigmaX=1.1,
                sigmaY=1.1,
            )
            mask = np.minimum(mask, np.clip(safe_core, 0.0, 1.0))

        mask_3c = mask[..., None]
        restored = (
            final_cv.astype(np.float32)
            + detail * float(strength) * mask_3c
        )
        return np.clip(restored, 0.0, 255.0).astype(np.uint8)

    @staticmethod
    def final_master_quality_pass(
        image_cv: np.ndarray,
        strength: float = 0.34,
    ) -> np.ndarray:
        """Edge-aware final quality pass for the complete marketplace image.

        The pass operates on luminance only to avoid color fringing. Moderate
        texture/detail receives controlled high-frequency recovery, while the
        strongest contrast boundaries are automatically protected from halo and
        ringing. Material reflections, shadows and color response remain intact.
        """
        if image_cv is None or image_cv.size == 0:
            return image_cv

        image_u8 = np.clip(image_cv, 0, 255).astype(np.uint8)
        lab = cv2.cvtColor(image_u8, cv2.COLOR_BGR2LAB)
        l_chan, a_chan, b_chan = cv2.split(lab)
        l_float = l_chan.astype(np.float32)

        low = cv2.GaussianBlur(
            l_float,
            (0, 0),
            sigmaX=0.90,
            sigmaY=0.90,
        )
        detail = np.clip(l_float - low, -20.0, 20.0)

        gx = cv2.Sobel(l_float, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(l_float, cv2.CV_32F, 0, 1, ksize=3)
        gradient = cv2.magnitude(gx, gy)

        positive = gradient[gradient > 0]
        if positive.size:
            reference = float(np.percentile(positive, 92.0))
        else:
            reference = 1.0
        reference = max(reference, 1.0)
        edge_strength = np.clip(gradient / reference, 0.0, 1.5)
        edge_protection = 1.0 - np.clip(
            (edge_strength - 0.55) / 0.75,
            0.0,
            1.0,
        )

        texture = np.clip(np.abs(detail) / 7.0, 0.0, 1.0)
        adaptive_weight = (
            float(strength)
            * (0.30 + 0.70 * texture)
            * edge_protection
        )

        enhanced_l = np.clip(
            l_float + detail * adaptive_weight,
            0.0,
            255.0,
        ).astype(np.uint8)

        enhanced = cv2.cvtColor(
            cv2.merge([enhanced_l, a_chan, b_chan]),
            cv2.COLOR_LAB2BGR,
        )
        return enhanced

    @classmethod
    def process_mockup(cls, raw_path: Path, template_path: Path,
                       config: dict, is_glass: bool, output_path: Path, source_design_identity: str = None, template_identity: str = None, recipe_version: str = None, template_sha: str = None) -> bool:
        try:
            # Unicode güvenli okuma (Numpy decode)
            art_cv = cv2.imdecode(np.fromfile(str(raw_path), dtype=np.uint8), cv2.IMREAD_COLOR)
            bg_cv_raw = cv2.imdecode(np.fromfile(str(template_path), dtype=np.uint8), cv2.IMREAD_UNCHANGED)

            if art_cv is None or bg_cv_raw is None:
                logger.error(f"Görseller yüklenemedi: {raw_path.name} veya {template_path.name}")
                return False

            alpha_mask = None
            if len(bg_cv_raw.shape) == 3 and bg_cv_raw.shape[2] == 4:
                alpha_mask = bg_cv_raw[:, :, 3]
                bg_cv = bg_cv_raw[:, :, :3]
            else:
                bg_cv = bg_cv_raw

            tip = config.get("tip", "duz")
            on_plan = config.get("on_plan", None)
            category_name = template_path.parent.name
            # Cutting-board templates are the highest-occlusion category
            # (food/knife/utensil objects in front of the printable glass).
            # Templates can override this explicitly with auto_foreground.
            # Auto foreground discovery may run on any template, but a
            # no-object result is fatal only when reviewed evidence says an
            # occluder truly exists. Category membership and an empty/default
            # on_plan settings object are not occlusion evidence.
            foreground_required = foreground_is_required(config, on_plan)
            auto_foreground = bool(
                config.get(
                    "auto_foreground",
                    (
                        category_name == "04_Cam_Dograma"
                        or foreground_required
                        or bool(on_plan)
                    ),
                )
            )

            # Perspektif Giydirme
            if tip == "perspektif" and "koseler" in config:
                koseler = config["koseler"]
            else:
                # Düz Şablon Giydirme
                h_bg, w_bg = bg_cv.shape[:2]
                tw = config.get("w", int(w_bg * 0.5))
                th = config.get("h", int(h_bg * 0.5))
                tx = config.get("x", int(w_bg * 0.25))
                ty = config.get("y", int(h_bg * 0.25))
                koseler = [[tx, ty], [tx + tw, ty], [tx + tw, ty + th], [tx, ty + th]]

            # Orientation is a compatibility gate, never an automatic
            # transform. IMPORTANT: physical orientation comes from the
            # source-hash-bound approved profile, NOT from the projected quad.
            # Perspective can make a physically vertical product look wider
            # than tall in image coordinates.
            profile_orientation = str(
                config.get("profile_orientation") or ""
            ).upper()
            if profile_orientation not in ("H", "V"):
                logger.warning(
                    f"⏭️ Onaylı fiziksel yön bilgisi eksik; güvenli şekilde atlandı: "
                    f"{template_path.name} ({profile_orientation or 'UNKNOWN'})"
                )
                return False

            art_h, art_w = art_cv.shape[:2]
            if art_w > art_h * 1.01:
                art_orientation = "H"
            elif art_h > art_w * 1.01:
                art_orientation = "V"
            else:
                art_orientation = "SQUARE"

            if art_orientation != profile_orientation:
                logger.warning(
                    f"⏭️ Orientation uyumsuzluğu nedeniyle şablon atlandı: "
                    f"{raw_path.name} ({art_orientation}) -> "
                    f"{template_path.name} ({profile_orientation})"
                )
                return False

            # Preserve content and physical proportions. This is deliberately
            # done after the physical-orientation gate: H/V intent is never
            # inferred from perspective geometry or changed by the renderer.
            nominal_aspect = config.get("nominal_aspect", "UNKNOWN")
            try:
                prepared_art = cls.prepare_artwork_for_nominal_aspect(
                    art_cv,
                    nominal_aspect,
                )
            except ValueError as exc:
                logger.warning(
                    f"⏭️ Fiziksel en-boy uyumsuzluğu nedeniyle render atlandı: "
                    f"{raw_path.name} -> {template_path.name}: {exc}"
                )
                return False
            if prepared_art.shape[:2] != art_cv.shape[:2]:
                logger.info(
                    f"  ↔️ Artwork fiziksel orana içerik kaybetmeden uyarlandı: "
                    f"{art_cv.shape[1]}x{art_cv.shape[0]} -> "
                    f"{prepared_art.shape[1]}x{prepared_art.shape[0]} "
                    f"(nominal={nominal_aspect})"
                )
            art_cv = prepared_art

            # Final marketplace dimensions are known before rendering so
            # the optical renderer can work at an appropriately high internal
            # resolution instead of compositing small and enlarging later.
            output_width = int(config.get("output_width", 2400) or 2400)
            output_height = int(config.get("output_height", 3200) or 3200)

            # Orijinal yedek görseli yükle (True Shadow Mapping için)
            orig_path = USER_WORKSPACE_DIR / "2_SABLON_HAVUZU_ORIJINAL_YEDEK" / template_path.parent.name / template_path.name
            orig_bg_cv = None
            if orig_path.exists():
                orig_bg_cv = cv2.imdecode(
                    np.fromfile(str(orig_path), dtype=np.uint8),
                    cv2.IMREAD_UNCHANGED,
                )
                if (
                    orig_bg_cv is not None
                    and orig_bg_cv.ndim == 3
                    and orig_bg_cv.shape[2] == 4
                ):
                    orig_bg_cv = orig_bg_cv[:, :, :3]

            # High-resolution internal render: upscale the scene/corners,
            # not the artwork separately. warpPerspective then samples the
            # original artwork directly into the larger physical surface,
            # avoiding an extra destructive resize.
            src_h, src_w = bg_cv.shape[:2]
            max_render_scale = float(config.get("max_render_scale", 2.5) or 2.5)
            render_scale = cls.compute_quality_render_scale(
                src_w,
                src_h,
                output_width,
                output_height,
                max_scale=max_render_scale,
            )
            if render_scale > 1.001:
                work_w = max(1, int(round(src_w * render_scale)))
                work_h = max(1, int(round(src_h * render_scale)))
                bg_cv = cv2.resize(
                    bg_cv,
                    (work_w, work_h),
                    interpolation=cv2.INTER_LANCZOS4,
                )
                if orig_bg_cv is not None:
                    orig_bg_cv = cv2.resize(
                        orig_bg_cv,
                        (work_w, work_h),
                        interpolation=cv2.INTER_LANCZOS4,
                    )
                if alpha_mask is not None:
                    alpha_mask = cv2.resize(
                        alpha_mask,
                        (work_w, work_h),
                        interpolation=cv2.INTER_LINEAR,
                    )
                koseler = [
                    [float(pt[0]) * render_scale, float(pt[1]) * render_scale]
                    for pt in koseler
                ]
                logger.info(
                    f"  🔬 Yüksek çözünürlük iç render: "
                    f"{src_w}x{src_h} -> {work_w}x{work_h} "
                    f"(x{render_scale:.2f})"
                )

            final_cv = cls.render_cv2_optik(
                art_cv, bg_cv, koseler, is_glass, 
                on_plan=on_plan, template_name=template_path.name, 
                category_name=category_name, orig_bg_cv=orig_bg_cv,
                alpha_mask=alpha_mask,
                source_design_identity=source_design_identity,
                template_identity=template_identity,
                recipe_version=recipe_version,
                template_sha=template_sha,
                auto_foreground=auto_foreground,
                foreground_required=foreground_required,
                camera_artifacts=bool(config.get("camera_artifacts", True)),
            )

            # Kalite Kontrol Denetimi (Quality Inspector)
            valid, msg = QualityInspector.inspect_mockup(final_cv, koseler if "koseler" in config else None)
            if not valid:
                logger.error(f"  ❌ Kalite Denetimi Başarısız ({raw_path.name}): {msg}. QUARANTINE!")
                return False

            # Marketplace-ready output. Defaults to Trendyol-friendly 3:4
            # while allowing an explicit per-template override.
            marketplace_ready = bool(config.get("marketplace_ready", True))
            if marketplace_ready:
                final_cv = cls.prepare_marketplace_canvas(
                    final_cv,
                    target_width=output_width,
                    target_height=output_height,
                )

            # Final whole-image quality stage. This is intentionally after
            # composition so every visible pixel (scene, frame, artwork,
            # material reflections and foreground) benefits from one controlled
            # edge-aware pass.
            final_cv = cls.final_master_quality_pass(
                final_cv,
                strength=float(config.get("master_quality_strength", 0.34) or 0.34),
            )

            # Kaydet (Unicode güvenli)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            success, enc_img = cv2.imencode(
                '.jpg',
                final_cv,
                [int(cv2.IMWRITE_JPEG_QUALITY), 98],
            )
            if success:
                enc_img.tofile(str(output_path))
                return True
            return False

        except Exception as e:
            logger.error(f"Mockup render hatası: {e}", exc_info=True)
            return False

# ==============================================================================
# 8. HIZLI EXCEL YÖNETİCİSİ (openpyxl Append)
# ==============================================================================
class FastExcelManager:
    HEADERS = [
        "Stok Kodu", "Barkod", "Model Kodu", "Kategori", "Ham Baskı Dosyası",
        "Mağaza Grubu", "Ürün Adı", "Açıklama", "Mockup Dosya Adı",
        "Resim Linki", "Eklenme Zamanı"
    ]

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self._buffer = []
        self._known_keys = set()
        self._init_file()
        self._load_known_keys()

    def _init_file(self):
        if not self.file_path.exists():
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Trendyol_Yukleme"
            ws.append(self.HEADERS)
            
            # Başlık stilizasyonu
            header_fill = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")
            header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
            for col_idx in range(1, len(self.HEADERS) + 1):
                cell = ws.cell(row=1, column=col_idx)
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal="center", vertical="center")

            wb.save(self.file_path)
            wb.close()

    @staticmethod
    def _row_key_from_values(stock_code, mockup_name):
        stock = str(stock_code or "").strip()
        mockup = str(mockup_name or "").strip()
        return (stock, mockup) if stock and mockup else None

    def _load_known_keys(self):
        """Index existing output rows so resume cannot duplicate Excel entries."""
        if not self.file_path.exists():
            return
        try:
            wb = openpyxl.load_workbook(
                self.file_path,
                read_only=True,
                data_only=True,
            )
            try:
                ws = wb.active
                header = {
                    str(cell.value): idx
                    for idx, cell in enumerate(ws[1], start=1)
                    if cell.value is not None
                }
                stock_col = header.get("Stok Kodu")
                mockup_col = header.get("Mockup Dosya Adı")
                if not stock_col or not mockup_col:
                    return
                for row in ws.iter_rows(min_row=2, values_only=True):
                    key = self._row_key_from_values(
                        row[stock_col - 1] if len(row) >= stock_col else None,
                        row[mockup_col - 1] if len(row) >= mockup_col else None,
                    )
                    if key:
                        self._known_keys.add(key)
            finally:
                wb.close()
        except Exception as exc:
            logger.warning(f"Excel mevcut satır indeksi okunamadı: {exc}")

    def append_row(self, row_dict: dict) -> bool:
        row_dict = row_dict or {}
        key = self._row_key_from_values(
            row_dict.get("Stok Kodu"),
            row_dict.get("Mockup Dosya Adı"),
        )
        with excel_lock:
            if key and key in self._known_keys:
                logger.info(
                    f"    ⏭️ Excel satırı zaten var: {key[0]} / {key[1]}"
                )
                return True

            row = [row_dict.get(h, "") for h in self.HEADERS]
            self._buffer.append(row)
            if key:
                self._known_keys.add(key)
            if len(self._buffer) >= 50:
                # The row is already durably represented in the in-memory
                # buffer. A threshold flush failure must not make the caller
                # forget this artifact; the final run-level flush is the
                # authoritative success gate and will retry the retained buffer.
                self.flush()
            return True

    def flush(self) -> bool:
        with excel_lock:
            if not self._buffer:
                return True
            try:
                wb = openpyxl.load_workbook(self.file_path)
                ws = wb.active
                for row in self._buffer:
                    ws.append(row)
                wb.save(self.file_path)
                wb.close()
                self._buffer.clear()
                return True
            except Exception as e:
                logger.error(f"Excel yazım hatası (flush): {e}")
                return False

# ==============================================================================
# 9. ANA PC FABRİKA ORKESTRASYON MOTORU (Master Factory)
# ==============================================================================
def build_factory_preflight() -> dict:
    """Read-only readiness report for one-button production.

    This function never renders, uploads, mutates the template DB, or consumes
    sequence numbers. It catches the common "start and fail 10 minutes later"
    conditions before the factory is launched.
    """
    report = {
        "ready": True,
        "errors": [],
        "warnings": [],
        "manifest": {},
        "templates": {},
        "optional_ai": {},
        "occlusion": {
            "ai_required_templates": [],
            "manual_or_cached_templates": [],
        },
        "outputs": {},
    }

    manifest_path = FACTORY_DIR / "manifest.json"
    items = []
    if not manifest_path.is_file():
        report["errors"].append(f"Manifest yok: {manifest_path}")
    else:
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            items = payload.get("items", []) if isinstance(payload, dict) else []
            if not isinstance(items, list) or not items:
                report["errors"].append("Manifest items listesi boş/geçersiz.")
                items = []
            report["manifest"]["item_count"] = len(items)
        except Exception as exc:
            report["errors"].append(f"Manifest okunamadı: {exc}")

    # Check artwork source availability without changing/rotating source files.
    missing_sources = []
    for idx, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            missing_sources.append(f"item#{idx}: geçersiz kayıt")
            continue
        master_id = item.get("master_id", f"item#{idx}")
        h_raw = (
            item.get("horizontal", {}).get("file", "")
            if isinstance(item.get("horizontal"), dict)
            else ""
        ) or item.get("horizontal_path", "")
        v_raw = (
            item.get("vertical", {}).get("file", "")
            if isinstance(item.get("vertical"), dict)
            else ""
        ) or item.get("vertical_path", "")

        def _resolve(raw, suffix):
            candidate = Path(raw) if raw else Path()
            if raw and not candidate.is_absolute():
                candidate = (FACTORY_DIR / candidate).resolve()
            if not raw or not candidate.exists():
                fallback = FACTORY_DIR / f"{master_id}_{suffix}.png"
                if fallback.exists():
                    return fallback
                return None
            return candidate

        h_path = _resolve(h_raw, "H")
        v_path = _resolve(v_raw, "V")
        if h_path is None:
            missing_sources.append(f"{master_id}: H master yok")
        if v_path is None:
            missing_sources.append(f"{master_id}: V master yok")

    report["manifest"]["missing_sources"] = missing_sources
    if missing_sources:
        report["errors"].append(
            f"{len(missing_sources)} zorunlu H/V master kaynağı bulunamadı. "
            "Eksik ürün üretmemek için fabrika başlatılmadı."
        )

    # Approved geometry must still match the exact source bytes.
    profile_db = USER_WORKSPACE_DIR / "SABLON_V2_MIMARI" / "ayarlar.db"
    if not profile_db.is_file():
        report["errors"].append(f"Şablon profil DB yok: {profile_db}")
    else:
        try:
            conn = open_sqlite_readonly(profile_db)
            conn.row_factory = sqlite3.Row
            try:
                for category, product in PRODUCT_CATALOG.items():
                    rows = conn.execute(
                        """SELECT template_uid, source_relative_path,
                                  source_asset_sha256, analyzer_version, orientation,
                                  nominal_aspect, surface_quad, has_occlusion,
                                  component_confidences
                           FROM template_profiles
                           WHERE category=? AND review_status='APPROVED'
                             AND is_active=1""",
                        (category,),
                    ).fetchall()

                    duplicate_approved_uids = duplicate_profile_uids(rows)

                    usable = 0
                    stale = 0
                    invalid = 0
                    orientation_mismatch = 0
                    physical_orientation_unverified = 0
                    for row in rows:
                        if str(row["template_uid"] or "") in duplicate_approved_uids:
                            invalid += 1
                            continue
                        rel = row["source_relative_path"]
                        if not rel:
                            invalid += 1
                            continue
                        path = (SABLON_DIR / rel).resolve()
                        try:
                            if SABLON_DIR.resolve() not in path.parents:
                                invalid += 1
                                continue
                        except Exception:
                            invalid += 1
                            continue
                        if not path.is_file() or not row["source_asset_sha256"]:
                            invalid += 1
                            continue

                        digest = hashlib.sha256()
                        try:
                            with path.open("rb") as handle:
                                for chunk in iter(
                                    lambda: handle.read(1024 * 1024), b""
                                ):
                                    digest.update(chunk)
                        except OSError:
                            invalid += 1
                            continue
                        current_sha = digest.hexdigest()
                        if current_sha != row["source_asset_sha256"]:
                            stale += 1
                            continue

                        try:
                            quad = np.asarray(
                                json.loads(row["surface_quad"]),
                                dtype=np.float32,
                            )
                            image = cv2.imdecode(
                                np.fromfile(str(path), dtype=np.uint8),
                                cv2.IMREAD_COLOR,
                            )
                            if image is None:
                                raise ValueError("source image unreadable")
                            h_img, w_img = image.shape[:2]
                            quad_valid, _ = ApprovedGeometryValidator.is_valid_quad(
                                quad,
                                w_img,
                                h_img,
                            )
                            if not quad_valid:
                                raise ValueError("invalid approved quad")
                        except Exception:
                            invalid += 1
                            continue

                        orientation = str(
                            row["orientation"] or "UNKNOWN"
                        ).upper()
                        if category == "04_Cam_Dograma":
                            orient_ok = orientation in ("H", "V")
                        else:
                            # Must match the same physical-orientation contract
                            # enforced by process_mockup; UNKNOWN would pass this
                            # preflight and then be rejected during rendering.
                            orient_ok = orientation == product.orientation
                        if not orient_ok:
                            orientation_mismatch += 1
                            continue

                        # Mixed-orientation templates previously could inherit
                        # H/V from projected quad geometry. Reject those legacy
                        # approvals unless physical direction has explicit
                        # category/human-review provenance.
                        if (
                            category == "04_Cam_Dograma"
                            and not physical_orientation_verified(
                                row["component_confidences"]
                            )
                        ):
                            physical_orientation_unverified += 1
                            continue

                        usable += 1

                        # Object-aware foreground restoration is quality-critical
                        # for cutting-board templates, explicit occlusion
                        # profiles, and any legacy plan. Manual plans are usable
                        # only when bound to these exact source bytes. The sole
                        # compatibility exception is legacy_manual_v1: that
                        # migration created the APPROVED profile and read the
                        # plan from the same exact legacy record/source in one
                        # source-hash-bound pass.
                        template_name = Path(rel).name
                        legacy_templates = (
                            AYARLAR.get("kategoriler", {})
                            .get(category, {})
                            .get("sablonlar", {})
                        )
                        legacy_cfg = legacy_templates.get(template_name)
                        if legacy_cfg is None:
                            for legacy_name, candidate_cfg in legacy_templates.items():
                                if Path(legacy_name).stem == Path(template_name).stem:
                                    legacy_cfg = candidate_cfg
                                    break
                        legacy_cfg = (
                            legacy_cfg if isinstance(legacy_cfg, dict) else {}
                        )
                        plan = legacy_cfg.get("on_plan")
                        plan_source_hash = str(
                            legacy_cfg.get("on_plan_source_sha256")
                            or (
                                plan.get("source_asset_sha256")
                                if isinstance(plan, dict)
                                else ""
                            )
                            or ""
                        ).strip()
                        plan_trusted = bool(
                            plan
                            and plan_source_hash
                            and plan_source_hash == current_sha
                        )

                        requires_occlusion = bool(
                            row["has_occlusion"]
                            or foreground_plan_has_positive_selection(plan)
                        )
                        # Match render-time auto_foreground defaults. The
                        # review UI currently persists a settings-only on_plan,
                        # so AI may be intentionally used as an opportunistic
                        # scan even when no occluder is known in advance.
                        auto_foreground_requested = bool(
                            category == "04_Cam_Dograma"
                            or requires_occlusion
                            or bool(plan)
                        )
                        if auto_foreground_requested:
                            has_positive_manual_plan = False
                            if plan_trusted and isinstance(plan, list):
                                has_positive_manual_plan = len(plan) >= 3
                            elif plan_trusted and isinstance(plan, dict):
                                has_positive_manual_plan = bool(
                                    plan.get("object_boxes")
                                    or plan.get("add_brush")
                                )

                            cache_file = (
                                MASK_CACHE_DIR
                                / (
                                    f"{category}_{row['source_asset_sha256']}_"
                                    "v3_auto_ai_mask.png"
                                )
                            )
                            has_cached_mask = False
                            if cache_file.is_file():
                                try:
                                    cached = cv2.imdecode(
                                        np.fromfile(str(cache_file), dtype=np.uint8),
                                        cv2.IMREAD_GRAYSCALE,
                                    )
                                    has_cached_mask = cached_foreground_mask_usable(
                                        cached,
                                        True,
                                    )
                                except Exception:
                                    has_cached_mask = False

                            item_name = f"{category}/{template_name}"
                            if has_positive_manual_plan or has_cached_mask:
                                report["occlusion"][
                                    "manual_or_cached_templates"
                                ].append(item_name)
                            else:
                                report["occlusion"][
                                    "ai_required_templates"
                                ].append(item_name)

                    report["templates"][category] = {
                        "approved": len(rows),
                        "usable": usable,
                        "stale": stale,
                        "invalid": invalid,
                        "orientation_mismatch": orientation_mismatch,
                        "physical_orientation_unverified": physical_orientation_unverified,
                        "duplicate_approved_uids": duplicate_approved_uids,
                    }
                    if duplicate_approved_uids:
                        report["errors"].append(
                            f"{category}: aynı template_uid için birden fazla "
                            "aktif APPROVED profil var: "
                            + ", ".join(duplicate_approved_uids)
                        )
                    if usable == 0:
                        report["errors"].append(
                            f"{category}: source-valid APPROVED şablon yok."
                        )
            finally:
                conn.close()
        except Exception as exc:
            report["errors"].append(f"Şablon profilleri okunamadı: {exc}")

    # Cloud upload is part of a marketplace-ready run. Fail before rendering
    # hundreds of files when no provider credential is configured.
    cloud_cfg = AYARLAR.get("bulut_ayarlari", {})
    configured_imgbb = cloud_cfg.get("imgbb_keys") or []
    if not isinstance(configured_imgbb, list):
        configured_imgbb = []
    env_imgbb = [
        key.strip()
        for key in os.environ.get("IMGBB_KEYS", "").split(",")
        if key.strip()
    ]
    freeimage_key = str(
        cloud_cfg.get("freeimage_key")
        or os.environ.get("FREEIMAGE_KEY", "")
        or ""
    ).strip()
    report["cloud"] = {
        "imgbb_key_count": len(
            [key for key in configured_imgbb if str(key).strip()]
            or env_imgbb
        ),
        "freeimage_configured": bool(freeimage_key),
    }
    if (
        report["cloud"]["imgbb_key_count"] == 0
        and not report["cloud"]["freeimage_configured"]
    ):
        report["errors"].append(
            "Bulut yükleme sağlayıcısı yapılandırılmamış "
            "(ImgBB veya FreeImage anahtarı gerekli)."
        )

    # Occlusion AI is optional only when every occlusion-sensitive
    # approved template already has a reviewed manual plan or a source-hash-
    # bound cached mask. Otherwise starting production without the models could
    # silently paint artwork over real foreground objects.
    ai_dependency = foreground_ai_dependency_status()
    report["optional_ai"].update(ai_dependency)
    missing_ai_modules = list(ai_dependency.get("missing") or [])
    missing_ai_modules.extend(ai_dependency.get("errors") or [])

    ai_required_templates = report["occlusion"]["ai_required_templates"]
    if ai_required_templates and missing_ai_modules:
        report["errors"].append(
            "Ön-plan/occlusion AI gerekli fakat bağımlılık/API eksik: "
            + ", ".join(missing_ai_modules)
        )
    elif missing_ai_modules:
        report["warnings"].append(
            "Ön-plan AI bağımlılık/API eksikleri var fakat tüm gerekli "
            "şablonlar manuel/cache maskesiyle kapsanmış: "
            + ", ".join(missing_ai_modules)
        )

    for name, directory in {
        "output": OUTPUT_DIR,
        "output_multi": OUTPUT_COKLU_DIR,
        "excel": EXCEL_DIR,
        "logs": LOG_DIR,
    }.items():
        exists = directory.exists()
        writable = exists and os.access(str(directory), os.W_OK)
        report["outputs"][name] = {
            "path": str(directory),
            "exists": exists,
            "writable": bool(writable),
        }
        if not writable:
            report["errors"].append(f"Yazılamayan çıktı klasörü: {directory}")

    report["ready"] = len(report["errors"]) == 0
    return report


class PCMasterFactory:
    def __init__(self, mode: str = "dongusel"):
        self.mode = mode   # "dongusel" veya "coklu"
        self.state = StateManager()
        self.uploader = AsyncCloudUploader()
        self.seo = SeoEngine()
        self.excel = FastExcelManager(EXCEL_DIR / "Urun_Yukleme_Listesi.xlsx")
        self.thread_pool = ThreadPoolExecutor(max_workers=3)
        self.metrics_lock = threading.Lock()
        self.upload_failures = 0
        self.persistence_failures = 0
        self.worker_failures = 0
        self.upload_futures = []
        self.pending_excel_lock = threading.Lock()
        self.pending_excel_artifacts = []

    def load_manifest(self) -> List[dict]:
        m_path = FACTORY_DIR / "manifest.json"
        if not m_path.exists():
            logger.error(f"manifest.json bulunamadı! Beklenen yer: {m_path}")
            return []

        try:
            with open(m_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("items", [])
        except Exception as e:
            logger.error(f"manifest.json bozuk veya okunamadı: {e}")
            return []

    def get_template_pool(self, prod_key: str) -> List[Tuple[str, Path, dict]]:
        """Return only source-valid, review-approved template profiles.

        Production rendering must never fall back to arbitrary folder contents
        or unreviewed legacy geometry. Legacy template JSON is used only for
        non-geometry extras (for example manual occlusion plans); approved
        profile geometry always wins.
        """
        pool: List[Tuple[str, Path, dict]] = []
        prod_def = PRODUCT_CATALOG[prod_key]
        db_path = USER_WORKSPACE_DIR / "SABLON_V2_MIMARI" / "ayarlar.db"

        if not db_path.exists():
            logger.warning(
                f"⏭️ Onaylı şablon profili kullanılamıyor; DB yok: {db_path}"
            )
            return pool

        try:
            conn = open_sqlite_readonly(db_path)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT template_uid, source_relative_path, source_asset_sha256,
                          analyzer_version, orientation, nominal_aspect,
                          surface_quad, outer_quad,
                          confidence_total, component_confidences, print_policy,
                          surface_mask_path, has_occlusion
                   FROM template_profiles
                   WHERE category=? AND review_status='APPROVED' AND is_active=1
                   ORDER BY confidence_total DESC, updated_at DESC""",
                (prod_key,),
            ).fetchall()
        except Exception as exc:
            logger.error(f"Onaylı template_profiles okunamadı ({prod_key}): {exc}")
            return pool
        finally:
            try:
                conn.close()
            except Exception:
                pass

        legacy_templates = (
            AYARLAR.get("kategoriler", {})
            .get(prod_key, {})
            .get("sablonlar", {})
        )
        pool_root = SABLON_DIR.resolve()

        duplicate_approved_uids = set(duplicate_profile_uids(rows))
        if duplicate_approved_uids:
            logger.error(
                f"⏭️ {prod_key}: duplicate active APPROVED profile UID'leri "
                "güvenlik nedeniyle render dışı bırakıldı: "
                + ", ".join(sorted(duplicate_approved_uids))
            )

        for row in rows:
            if str(row["template_uid"] or "") in duplicate_approved_uids:
                continue
            relative_path = row["source_relative_path"]
            if not relative_path or not row["surface_quad"]:
                logger.warning(f"⏭️ Eksik onaylı geometri atlandı: {row['template_uid']}")
                continue

            try:
                template_path = (SABLON_DIR / relative_path).resolve()
                if pool_root not in template_path.parents:
                    logger.warning(f"⏭️ Güvensiz şablon yolu atlandı: {relative_path}")
                    continue
            except Exception:
                continue

            if not template_path.exists():
                logger.warning(f"⏭️ Onaylı profilin kaynak dosyası yok: {template_path}")
                continue

            # Approval is bound to exact source bytes. A changed image is stale
            # even if filename/template_uid stayed the same.
            try:
                digest = hashlib.sha256()
                with open(template_path, "rb") as handle:
                    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                        digest.update(chunk)
                current_sha = digest.hexdigest()
            except Exception as exc:
                logger.warning(f"⏭️ Şablon hash okunamadı {template_path.name}: {exc}")
                continue

            if not row["source_asset_sha256"] or current_sha != row["source_asset_sha256"]:
                logger.warning(
                    f"⏭️ STALE_SOURCE_CHANGED: {row['template_uid']} yeniden analiz/onay gerekli"
                )
                continue

            try:
                surface_quad = json.loads(row["surface_quad"])
                quad_arr = np.asarray(surface_quad, dtype=np.float32)
                image = cv2.imdecode(
                    np.fromfile(str(template_path), dtype=np.uint8),
                    cv2.IMREAD_COLOR,
                )
                if image is None:
                    raise ValueError("source image unreadable")
                h_img, w_img = image.shape[:2]
                quad_valid, quad_reason = ApprovedGeometryValidator.is_valid_quad(
                    quad_arr,
                    w_img,
                    h_img,
                )
                if not quad_valid:
                    raise ValueError(quad_reason)
                surface_quad = (
                    ApprovedGeometryValidator.canonical_sort(quad_arr)
                    .astype(float)
                    .tolist()
                )
            except Exception as exc:
                logger.warning(
                    f"⏭️ Bozuk onaylı quad atlandı: {row['template_uid']} ({exc})"
                )
                continue

            profile_orientation = (row["orientation"] or "UNKNOWN").upper()
            mixed_orientation_category = (prod_key == "04_Cam_Dograma")

            if mixed_orientation_category:
                # Cutting-board templates legitimately exist in both H and V.
                # The renderer will pair each approved template with the
                # corresponding H/V master instead of rotating artwork.
                if profile_orientation not in ("H", "V"):
                    logger.info(
                        f"⏭️ Karma yön kategorisinde yönü belirsiz şablon atlandı: "
                        f"{template_path.name} ({profile_orientation})"
                    )
                    continue
                if not physical_orientation_verified(
                    row["component_confidences"]
                ):
                    logger.warning(
                        f"⏭️ Karma yön şablonunun fiziksel H/V doğrulama kanıtı yok; "
                        f"yeniden insan onayı gerekli: {template_path.name}"
                    )
                    continue
            else:
                if profile_orientation != prod_def.orientation:
                    logger.info(
                        f"⏭️ Fiziksel orientation uyumsuz/belirsiz onaylı şablon atlandı: "
                        f"{template_path.name} "
                        f"({profile_orientation}!={prod_def.orientation})"
                    )
                    continue

            # Preserve non-geometric legacy extras by exact name, then stem.
            template_name = template_path.name
            legacy_cfg = legacy_templates.get(template_name)
            if legacy_cfg is None:
                for legacy_name, candidate_cfg in legacy_templates.items():
                    if Path(legacy_name).stem == template_path.stem:
                        legacy_cfg = candidate_cfg
                        break
            config = dict(legacy_cfg or {})
            raw_on_plan = config.get("on_plan")
            legacy_requires_occlusion = foreground_plan_has_positive_selection(
                raw_on_plan
            )
            plan_source_hash = str(
                config.get("on_plan_source_sha256")
                or (
                    raw_on_plan.get("source_asset_sha256")
                    if isinstance(raw_on_plan, dict)
                    else ""
                )
                or ""
            ).strip()
            plan_trusted = bool(
                raw_on_plan
                and plan_source_hash
                and plan_source_hash == current_sha
            )
            if raw_on_plan and not plan_trusted:
                # Keep the fact that this template needs occlusion handling,
                # but never reuse stale/unbound coordinates. AI or a current
                # source-hash-bound cache must regenerate the mask.
                config.pop("on_plan", None)
                logger.warning(
                    f"⏭️ Kaynağa bağlı olmayan/stale on_plan yok sayıldı: "
                    f"{row['template_uid']}"
                )

            # Geometry-critical fields are exclusively sourced from the
            # review-approved immutable-source profile.
            config.update({
                "tip": "perspektif",
                "koseler": surface_quad,
                "profile_uid": row["template_uid"],
                "profile_orientation": profile_orientation,
                "profile_confidence": float(row["confidence_total"] or 0.0),
                "nominal_aspect": (
                    row["nominal_aspect"]
                    if row["nominal_aspect"] not in (None, "", "UNKNOWN")
                    else (
                        physical_aspect_for_product(
                            prod_def,
                            profile_orientation
                            if profile_orientation in ("H", "V")
                            else prod_def.orientation,
                        )
                        or "UNKNOWN"
                    )
                ),
                "print_policy": row["print_policy"] or "full_bleed",
                "surface_mask_path": row["surface_mask_path"],
                "has_occlusion": (
                    bool(row["has_occlusion"]) or legacy_requires_occlusion
                ),
            })

            pool.append((template_name, template_path, config))

        if not pool:
            logger.warning(
                f"⏭️ {prod_key}: render için source-valid APPROVED şablon yok. "
                "Unreviewed klasör fallback'i güvenlik nedeniyle kapalı."
            )

        return pool

    def process_all(self) -> bool:
        items = self.load_manifest()
        if not items:
            logger.error("İşlenecek manifest öğesi bulunamadı.")
            return False

        eligible_template_count = 0
        completed_artifact_count = 0
        render_attempted = 0
        render_succeeded = 0
        render_failed = 0
        upload_resumed = 0

        logger.info(f"🚀 PC MASTER FABRİKASI BAŞLATILDI | Toplam Master: {len(items)} | Mod: {self.mode.upper()}")

        for m_idx, master_data in enumerate(items, start=1):
            master_id = master_data.get("master_id", f"M{m_idx:06d}")
            theme_id = master_data.get("theme_id", 0)
            theme_title = master_data.get("theme_title", "Özel Sanat Eseri")
            style_key = master_data.get("style_key", "")

            # Ham yollar
            h_raw = master_data.get("horizontal", {}).get("file", "") or master_data.get("horizontal_path", "")
            v_raw = master_data.get("vertical", {}).get("file", "") or master_data.get("vertical_path", "")

            h_path = (FACTORY_DIR / h_raw).resolve() if not Path(h_raw).is_absolute() else Path(h_raw)
            v_path = (FACTORY_DIR / v_raw).resolve() if not Path(v_raw).is_absolute() else Path(v_raw)

            # Fallback klasör içi arama
            if not h_path.exists():
                h_alt = FACTORY_DIR / f"{master_id}_H.png"
                if h_alt.exists():
                    h_path = h_alt
            if not v_path.exists():
                v_alt = FACTORY_DIR / f"{master_id}_V.png"
                if v_alt.exists():
                    v_path = v_alt

            self.state.register_master(master_id, theme_id, theme_title, style_key, str(h_path), str(v_path))

            logger.info("\n========================================================")
            logger.info(f"🎨 MASTER [{m_idx}/{len(items)}]: {master_id} - {theme_title}")
            logger.info("========================================================")

            # 1 Master -> ürün kategorileri genişletmesi
            for prod_key, prod_def in PRODUCT_CATALOG.items():
                template_pool = self.get_template_pool(prod_key)
                if not template_pool:
                    logger.warning(f"  ⚠️ Onaylı şablon havuzu boş: {prod_key}")
                    continue
                eligible_template_count += len(template_pool)

                recipe_version = RECIPE_VERSION

                # Hash/source identity cache. Mixed-orientation categories can
                # use both master variants in the same product without rotating
                # either source artwork.
                source_cache = {}

                def _source_for_orientation(orientation: str):
                    orient = (orientation or "").upper()
                    if orient == "H":
                        path = h_path
                    elif orient == "V":
                        path = v_path
                    else:
                        return None

                    if not path.exists():
                        return None

                    cache_key = str(path.resolve())
                    if cache_key not in source_cache:
                        digest = hashlib.sha256()
                        with open(path, "rb") as handle:
                            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                                digest.update(chunk)
                        sha = digest.hexdigest()
                        source_cache[cache_key] = {
                            "path": path,
                            "sha": sha,
                            "identity": f"{path.name}_{sha}",
                        }
                    return source_cache[cache_key]

                # Resolve every approved template to its compatible source
                # orientation, then construct immutable artifact identities.
                template_records = []
                for sablon_name, sablon_path, sablon_conf in template_pool:
                    profile_orientation = (
                        str(sablon_conf.get("profile_orientation") or "").upper()
                    )
                    source_orientation = (
                        profile_orientation
                        if profile_orientation in ("H", "V")
                        else prod_def.orientation
                    )
                    source_info = _source_for_orientation(source_orientation)
                    if source_info is None:
                        logger.warning(
                            f"  ⚠️ Ham görsel bulunamadı ({source_orientation}) "
                            f"{master_id}/{prod_key}/{sablon_name}"
                        )
                        continue

                    digest = hashlib.sha256()
                    with open(sablon_path, "rb") as handle:
                        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                            digest.update(chunk)
                    template_sha = digest.hexdigest()
                    template_identity = f"{sablon_name}_{template_sha}"
                    artifact_key = (
                        f"{source_info['identity']}_{prod_key}_"
                        f"{template_identity}_{recipe_version}"
                    )

                    artifact_state = self.state.get_artifact(
                        artifact_key
                    )
                    template_records.append({
                        "name": sablon_name,
                        "path": sablon_path,
                        "config": sablon_conf,
                        "artifact_key": artifact_key,
                        "template_identity": template_identity,
                        "template_sha": template_sha,
                        "source_path": source_info["path"],
                        "source_identity": source_info["identity"],
                        "source_orientation": source_orientation,
                        "artifact_state": artifact_state,
                        "completed": (
                            artifact_state is not None
                            and artifact_state.get("status") == "COMPLETED"
                            and bool(artifact_state.get("local_output_path"))
                            and Path(
                                artifact_state.get("local_output_path")
                            ).is_file()
                        ),
                    })

                if not template_records:
                    logger.warning(
                        f"  ⚠️ Uyumlu kaynak/şablon eşleşmesi yok: {prod_key}"
                    )
                    continue

                completed_artifact_count += sum(
                    1 for record in template_records if record["completed"]
                )

                if all(record["completed"] for record in template_records):
                    for record in template_records:
                        logger.info(
                            f"  ⏭️ Atlandı (Artifact Zaten Tamam): "
                            f"{record['artifact_key']}"
                        )
                    continue

                # Product/SKU identity belongs to master+category, not to H/V
                # source files. This keeps one logical product while individual
                # image artifacts may use different orientation masters.
                sku_key = f"sku_v2_{master_id}_{prod_key}"
                with db_lock, self.state.conn:
                    row = self.state.conn.execute(
                        "SELECT value FROM system_meta WHERE key = ?",
                        (sku_key,),
                    ).fetchone()

                    if row:
                        seq = int(row["value"])
                    else:
                        # Backward-compatible adoption of the old source-bound
                        # SKU key if this master/category was already processed.
                        seq = None
                        for source_info in source_cache.values():
                            legacy_key = (
                                f"sku_{source_info['identity']}_{prod_key}"
                            )
                            legacy_row = self.state.conn.execute(
                                "SELECT value FROM system_meta WHERE key = ?",
                                (legacy_key,),
                            ).fetchone()
                            if legacy_row:
                                seq = int(legacy_row["value"])
                                break

                        if seq is None:
                            seq = self.state.get_next_sequence(
                                prod_def.barkod_prefix
                            )

                        self.state.conn.execute(
                            """INSERT INTO system_meta (key, value, updated_at)
                               VALUES (?, ?, CURRENT_TIMESTAMP)
                               ON CONFLICT(key) DO UPDATE SET
                                   value=excluded.value,
                                   updated_at=CURRENT_TIMESTAMP""",
                            (sku_key, str(seq)),
                        )

                barkod = f"{prod_def.barkod_prefix}{seq:05d}"
                sku = barkod
                model_kodu = f"{prod_def.model_prefix}{seq:05d}"

                if self.mode == "coklu":
                    selected_records = [
                        record
                        for record in template_records
                        if not record["completed"]
                    ]
                else:
                    # Stable round-robin selection operates on all compatible
                    # approved templates, independent of which source H/V each
                    # template needs.
                    target_index = (seq - 1) % len(template_records)
                    target_record = template_records[target_index]
                    selected_records = (
                        []
                        if target_record["completed"]
                        else [target_record]
                    )

                for record in selected_records:
                    sablon_name = record["name"]
                    sablon_path = record["path"]
                    sablon_conf = record["config"]
                    artifact_key = record["artifact_key"]
                    template_identity = record["template_identity"]
                    template_sha = record["template_sha"]
                    target_raw_path = record["source_path"]
                    source_design_identity = record["source_identity"]

                    magaza_grubu = sablon_path.stem
                    # Artifact identity includes the render recipe, so the
                    # physical output path must also be recipe-versioned.
                    # Otherwise a new renderer recipe could overwrite a file
                    # still referenced by an older immutable artifact record.
                    out_filename = (
                        f"{sku}_{sablon_path.stem}_{recipe_version}.jpg"
                    )

                    if self.mode == "coklu":
                        out_dir = OUTPUT_COKLU_DIR / prod_key / magaza_grubu
                    else:
                        out_dir = OUTPUT_DIR / prod_key

                    out_path = out_dir / out_filename

                    prior_artifact = record.get("artifact_state") or {}
                    prior_local = Path(
                        prior_artifact.get("local_output_path") or ""
                    )
                    prior_status = prior_artifact.get("status")
                    pending_excel_only = (
                        prior_status in ("UPLOADED_PENDING_EXCEL", "UPLOADED")
                        and prior_local.is_file()
                        and bool(prior_artifact.get("upload_url"))
                    )
                    can_resume_local = (
                        prior_status
                        in (
                            "RENDERED",
                            "UPLOAD_FAILED",
                            "UPLOADED_PENDING_EXCEL",
                            "UPLOADED",
                        )
                        and prior_local.is_file()
                    )

                    if can_resume_local:
                        out_path = prior_local
                        upload_resumed += 1
                        if pending_excel_only:
                            logger.info(
                                f"  ♻️ Render/yükleme tekrar edilmiyor; "
                                f"Excel kaydı tamamlanacak: {out_path.name}"
                            )
                        else:
                            logger.info(
                                f"  ♻️ Render tekrar edilmiyor; mevcut artifact "
                                f"buluta yeniden gönderilecek: {out_path.name}"
                            )
                    else:
                        logger.info(
                            f"  🖌️ Render ({record['source_orientation']}): "
                            f"{artifact_key} -> {sku}"
                        )
                        render_attempted += 1

                        success = MockupRenderer.process_mockup(
                            raw_path=target_raw_path,
                            template_path=sablon_path,
                            config=sablon_conf,
                            is_glass=prod_def.is_glass,
                            output_path=out_path,
                            source_design_identity=source_design_identity,
                            template_identity=template_identity,
                            recipe_version=recipe_version,
                            template_sha=template_sha
                        )

                        if not success:
                            render_failed += 1
                            continue
                        render_succeeded += 1

                        # P0 Fix: Call RealESRGAN Quality Engine
                        if (
                            AYARLAR.get("bulut_ayarlari", {}).get(
                                "use_realesrgan", False
                            )
                            and RealESRGANQualityEngine.get_exe_path()
                        ):
                            logger.info(
                                f"  🔍 Kalite Artırılıyor (4K RealESRGAN): "
                                f"{out_path.name}"
                            )
                            upscaled_path = out_path.with_name(
                                "4k_" + out_path.name
                            )
                            if RealESRGANQualityEngine.upscale_4k(
                                out_path, upscaled_path
                            ):
                                import shutil
                                shutil.move(str(upscaled_path), str(out_path))

                        # Persist the local artifact before any network work.
                        # A crash or provider outage can then resume upload
                        # without re-rendering the image.
                        saved_local_state = self.state.save_render_artifact({
                            "artifact_key": artifact_key,
                            "sku": sku,
                            "source_identity": source_design_identity,
                            "category": prod_key,
                            "template_identity": template_identity,
                            "local_output_path": str(out_path),
                            "upload_url": "",
                            "status": "RENDERED",
                        })
                        if not saved_local_state:
                            with self.metrics_lock:
                                self.persistence_failures += 1
                            render_failed += 1
                            logger.error(
                                f"  ❌ Render state DB'ye yazılamadı; upload atlandı: "
                                f"{artifact_key}"
                            )
                            continue

                    seo_title = self.seo.generate_title(
                        prod_key,
                        theme_title,
                        identity_seed=sku,
                    )
                    seo_desc = self.seo.get_description(
                        prod_key, theme_title, style_key
                    )

                    prod_record = {
                        "artifact_key": artifact_key,
                        "source_identity": source_design_identity,
                        "category": prod_key,
                        "template_identity": template_identity,
                        "local_output_path": str(out_path),
                        "sku": sku,
                        "master_id": master_id,
                        "barkod": barkod,
                        "model_kodu": model_kodu,
                        "urun_adi": seo_title,
                        "aciklama": seo_desc,
                        "ham_baski_dosyasi": target_raw_path.name,
                        "mockup_dosyasi": out_path.name,
                        "magaza_grubu": magaza_grubu,
                        "resim_linki": (
                            str(prior_artifact.get("upload_url") or "")
                            if pending_excel_only
                            else ""
                        ),
                        "status": (
                            "UPLOADED_PENDING_EXCEL"
                            if pending_excel_only
                            else "RENDERED"
                        )
                    }

                    future = self.thread_pool.submit(
                        self._async_upload_and_excel,
                        out_path,
                        prod_record,
                    )
                    self.upload_futures.append(future)

        logger.info("\n⏳ Render aşaması bitti, arkaplandaki bulut yüklemeleri tamamlanıyor...")
        self.thread_pool.shutdown(wait=True)

        # ThreadPoolExecutor does not raise worker exceptions from shutdown().
        # Resolve every future explicitly so an unexpected background exception
        # can never be mistaken for a successful production run.
        for future in self.upload_futures:
            try:
                future.result()
            except Exception as exc:
                self.worker_failures += 1
                logger.error(
                    f"❌ Arkaplan upload/Excel worker beklenmeyen hatayla durdu: {exc}",
                    exc_info=True,
                )

        excel_flush_ok = self.excel.flush()
        if excel_flush_ok:
            with self.pending_excel_lock:
                completed_keys = list(dict.fromkeys(self.pending_excel_artifacts))
            self.state.mark_artifacts_completed(
                completed_keys,
                recipe_version=RECIPE_VERSION,
            )
        else:
            logger.error(
                "❌ Excel flush başarısız; yüklenen artifact'lar COMPLETED "
                "olarak işaretlenmedi ve sonraki çalışmada Excel adımı "
                "yeniden denenecek."
            )

        logger.info(
            "📊 Çalışma özeti | "
            f"approved_templates={eligible_template_count} "
            f"already_completed={completed_artifact_count} "
            f"render_attempted={render_attempted} "
            f"render_succeeded={render_succeeded} "
            f"render_failed={render_failed} "
            f"upload_resumed={upload_resumed} "
            f"upload_failed={self.upload_failures} "
            f"persistence_failed={self.persistence_failures} "
            f"worker_failed={self.worker_failures}"
        )
        logger.info(
            "📊 Kalıcı DB geçmiş özeti (bu koşunun sonucu değildir): "
            f"{self.state.get_summary()}"
        )
        logger.info(f"📁 Çıktı Excel: {self.excel.file_path}")

        if eligible_template_count == 0:
            logger.error(
                "❌ Üretim yapılamadı: source-valid APPROVED şablon bulunamadı. "
                "Önce Şablon İnceleme Merkezi'nde geometriyi doğrulayın."
            )
            return False

        if render_attempted > 0 and render_succeeded == 0:
            logger.error("❌ Tüm render denemeleri başarısız oldu.")
            return False

        if render_failed > 0:
            logger.error(
                f"⚠️ Üretim kısmi tamamlandı: {render_succeeded} başarılı, "
                f"{render_failed} başarısız."
            )
            return False

        if self.upload_failures > 0:
            logger.error(
                f"⚠️ Render tamamlandı ancak {self.upload_failures} artifact "
                "buluta yüklenemedi. Yeniden çalıştırmada mevcut yerel "
                "artifact yeniden render edilmeden yüklenecek."
            )
            return False

        if self.persistence_failures > 0:
            logger.error(
                f"❌ {self.persistence_failures} durum kaydı DB'ye güvenli "
                "şekilde yazılamadı. Koşu tamamlanmış sayılmayacak."
            )
            return False

        if self.worker_failures > 0:
            logger.error(
                f"❌ {self.worker_failures} arkaplan worker hatası oluştu. "
                "Koşu tamamlanmış sayılmayacak."
            )
            return False

        if not excel_flush_ok:
            return False

        if (
            render_attempted == 0
            and upload_resumed == 0
            and completed_artifact_count > 0
        ):
            logger.info(
                "✅ Yeni render/yükleme gerekmiyor; uygun artifact'ların "
                "tamamı zaten mevcut."
            )
            return True

        logger.info("\n🎉 TÜM UYGUN RENDER İŞLEMLERİ BAŞARIYLA TAMAMLANDI!")
        return True

    def _async_upload_and_excel(self, mockup_path: Path, prod_record: dict):
        # If upload already succeeded in an earlier interrupted run, resume at
        # Excel only. This avoids duplicate cloud copies.
        url = str(prod_record.get("resim_linki") or "").strip() or None

        if not url:
            for attempt in range(3):
                url = self.uploader.upload_sync(mockup_path)
                if url:
                    break
                # Her deneme arasi ufak bekleme
                time.sleep(2)

        if not url:
            prod_record["resim_linki"] = ""
            prod_record["upload_url"] = ""
            prod_record["status"] = "UPLOAD_FAILED"
            with self.metrics_lock:
                self.upload_failures += 1
            logger.error(
                f"    ❌ BULUT YÜKLEME BAŞARISIZ (3 deneme): "
                f"{prod_record['sku']}"
            )
            artifact_saved = self.state.save_render_artifact(prod_record)
            product_saved = self.state.save_product(prod_record)
            if not (artifact_saved and product_saved):
                with self.metrics_lock:
                    self.persistence_failures += 1
                logger.error(
                    f"    ❌ UPLOAD_FAILED durumu DB'ye tam yazılamadı: "
                    f"{prod_record['artifact_key']}"
                )
            # Marketplace Excel must never contain a row with a missing image
            # link. The row is emitted only after upload succeeds.
            return

        prod_record["resim_linki"] = url
        prod_record["upload_url"] = url
        prod_record["status"] = "UPLOADED_PENDING_EXCEL"
        logger.info(
            f"    ☁️ Bulut hazır: {prod_record['sku']} -> {url}"
        )

        # Persist upload success before Excel. If the process stops here, the
        # next run resumes at Excel and does not upload or render again.
        artifact_saved = self.state.save_render_artifact(prod_record)
        product_saved = self.state.save_product(prod_record)
        if not (artifact_saved and product_saved):
            with self.metrics_lock:
                self.persistence_failures += 1
            logger.error(
                f"    ❌ Upload başarılı fakat DB durumu kalıcılaştırılamadı; "
                f"Excel kuyruğuna alınmadı: {prod_record['artifact_key']}"
            )
            return

        excel_row = {
            "Stok Kodu": prod_record["sku"],
            "Barkod": prod_record["barkod"],
            "Model Kodu": prod_record["model_kodu"],
            "Kategori": prod_record["category"],
            "Ham Baskı Dosyası": prod_record["ham_baski_dosyasi"],
            "Mağaza Grubu": prod_record["magaza_grubu"],
            "Ürün Adı": prod_record["urun_adi"],
            "Açıklama": prod_record["aciklama"],
            "Mockup Dosya Adı": prod_record["mockup_dosyasi"],
            "Resim Linki": prod_record["resim_linki"],
            "Eklenme Zamanı": time.strftime("%d.%m.%Y %H:%M:%S")
        }
        queued = self.excel.append_row(excel_row)
        if queued:
            with self.pending_excel_lock:
                self.pending_excel_artifacts.append(
                    prod_record["artifact_key"]
                )
        else:
            logger.error(
                f"    ❌ Excel kuyruğu yazılamadı: "
                f"{prod_record['artifact_key']}"
            )

# ==============================================================================
# 10. CLI VE İNTERAKTİF GİRİŞ NOKTASI
# ==============================================================================
def parse_args():
    p = argparse.ArgumentParser(description="PC Master Mockup & Commerce Factory V5")
    p.add_argument("--mod", choices=["dongusel", "coklu"], default="dongusel",
                   help="Dağıtım modu: 'dongusel' (tek klasör/tek excel) veya 'coklu' (K1..K11 klasörleri)")
    p.add_argument(
        "--preflight",
        action="store_true",
        help="Üretim yapmadan manifest/profil/çıktı/opsiyonel AI hazırlığını kontrol et.",
    )
    return p.parse_args()

if __name__ == "__main__":
    args = parse_args()
    if args.preflight:
        preflight = build_factory_preflight()
        print(json.dumps(preflight, ensure_ascii=False, indent=2))
        # Stable final-line protocol for the local control center.
        print(
            "PREFLIGHT_JSON="
            + json.dumps(preflight, ensure_ascii=False, separators=(",", ":"))
        )
        raise SystemExit(0 if preflight["ready"] else 2)

    # Defense in depth: production CLI execution must not depend on the caller
    # remembering to run --preflight first. The control center and launcher
    # already preflight, but direct script execution now enforces the same
    # read-only readiness gate before any production mutation can begin.
    preflight = build_factory_preflight()
    if not preflight["ready"]:
        logger.error("❌ Üretim preflight başarısız; fabrika başlatılmadı.")
        for error in preflight.get("errors", []):
            logger.error(f"  - {error}")
        raise SystemExit(2)

    bot = PCMasterFactory(mode=args.mod)
    ok = bot.process_all()
    raise SystemExit(0 if ok else 1)
