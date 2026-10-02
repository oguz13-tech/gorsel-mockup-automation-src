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
USER_WORKSPACE_DIR = Path(__file__).resolve().parent.parent.parent
if USER_WORKSPACE_DIR.exists():
    FACTORY_DIR = USER_WORKSPACE_DIR / "1_GELEN_KAGGLE_BASKILARI"
    SABLON_DIR = USER_WORKSPACE_DIR / "2_SABLON_HAVUZU"
    OUTPUT_DIR = USER_WORKSPACE_DIR / "3_URETILEN_MOCKUPLAR"
    OUTPUT_COKLU_DIR = USER_WORKSPACE_DIR / "Mockup_Magaza_Klasorleri"
    EXCEL_DIR = USER_WORKSPACE_DIR / "4_EXCEL_YUKLEME_LISTELERI"
    AYARLAR_PATH = USER_WORKSPACE_DIR / "99_SISTEM_MOTORLARI_VE_KODLAR" / "SISTEM_MOTORU" / "ayarlar.json"
    LOG_DIR = USER_WORKSPACE_DIR / "99_SISTEM_MOTORLARI_VE_KODLAR" / "SISTEM_MOTORU" / "logs"
    DB_PATH = USER_WORKSPACE_DIR / "99_SISTEM_MOTORLARI_VE_KODLAR" / "SISTEM_MOTORU" / "commerce_state.db"
    SEO_DIR = USER_WORKSPACE_DIR / "99_SISTEM_MOTORLARI_VE_KODLAR" / "SISTEM_MOTORU" / "SEO_Verileri"
else:
    FACTORY_DIR = BASE_DIR / "factory_outputs"
    SABLON_DIR = BASE_DIR / "Sablonlar"
    OUTPUT_DIR = BASE_DIR / "Mockup_Dongusel_Dagitim"
    OUTPUT_COKLU_DIR = BASE_DIR / "Mockup_Hazir_Urunler"
    EXCEL_DIR = BASE_DIR / "Mockup_Dongusel_Dagitim"
    AYARLAR_PATH = BASE_DIR / "ayarlar.json"
    LOG_DIR = BASE_DIR / "logs"
    DB_PATH = BASE_DIR / "commerce_state.db"
    SEO_DIR = BASE_DIR / "SEO_Verileri"

for d in [FACTORY_DIR, SABLON_DIR, SEO_DIR, OUTPUT_DIR, OUTPUT_COKLU_DIR, EXCEL_DIR, LOG_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Logging Kurulumu
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "pc_master_factory.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("Factory")

excel_lock = threading.Lock()
db_lock = threading.Lock()

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

# ==============================================================================
# 3. AYARLAR.JSON YÜKLEYİCİ VE ŞABLON YÖNETİCİSİ
# ==============================================================================
import sqlite3

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
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        result = {"kategoriler": {}}
        
        # 1. Genel Ayarlar
        c.execute("SELECT key, value FROM settings")
        for row in c.fetchall():
            result[row["key"]] = json.loads(row["value"])
            
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
            data = json.loads(row["data"])
            
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
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False, timeout=30)
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

    def is_artifact_completed(self, artifact_key: str) -> bool:
        with db_lock, self.conn:
            row = self.conn.execute("SELECT status FROM render_artifacts WHERE artifact_key = ?", (artifact_key,)).fetchone()
            return row is not None and row["status"] in ("COMPLETED", "UPLOADED", "UPLOAD_FAILED")

    def save_render_artifact(self, data: dict):
        if not data: return
        with db_lock, self.conn:
            try:
                self.conn.execute("""
                INSERT INTO render_artifacts (artifact_key, sku, source_identity, category, 
                                              template_identity, local_output_path, upload_url, status, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(artifact_key) DO UPDATE SET
                    upload_url=excluded.upload_url,
                    status=excluded.status,
                    updated_at=CURRENT_TIMESTAMP
                """, (
                    data.get("artifact_key", ""), data.get("sku", ""), data.get("source_identity", ""),
                    data.get("category", ""), data.get("template_identity", ""), 
                    data.get("local_output_path", ""), data.get("upload_url", ""), data.get("status", "COMPLETED")
                ))
            except Exception as e:
                import logging
                logging.getLogger("StateDB").error(f"Veritabani yazim hatasi (save_render_artifact): {e}")

    def save_product(self, data: dict):
        if not data:
            return
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
                    data.get("sku", ""), data.get("master_id", ""), data.get("kategori_key", ""), 
                    data.get("barkod", ""), data.get("model_kodu", ""), data.get("urun_adi", ""), 
                    data.get("aciklama", ""), data.get("ham_baski_dosyasi", ""), data.get("mockup_dosyasi", ""),
                    data.get("magaza_grubu", ""), data.get("resim_linki", ""), data.get("status", "COMPLETED")
                ))
            except Exception as e:
                import logging
                logging.getLogger("StateDB").error(f"Veritabani yazim hatasi (save_product): {e}")

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
        self.imgbb_keys = cloud_cfg.get("imgbb_keys", os.environ.get("IMGBB_KEYS", "").split(",")))
        self.freeimage_key = cloud_cfg.get("freeimage_key", os.environ.get("FREEIMAGE_KEY", ""))
        self.active_key_idx = 0
        self.key_lock = threading.Lock()
        self.freeimage_active = True

    def upload_sync(self, file_path: Path) -> Optional[str]:
        if not file_path.exists():
            return None

        # 1. ImgBB Rotasyonu
        while self.active_key_idx < len(self.imgbb_keys):
            key = self.imgbb_keys[self.active_key_idx]
            try:
                with open(file_path, "rb") as f:
                    res = requests.post(
                        "https://api.imgbb.com/1/upload",
                        data={"key": key},
                        files={"image": f},
                        timeout=25
                    )
                if res.status_code == 200:
                    data = res.json()
                    return data.get("data", {}).get("url")
                
                # Rate limit / Kota aşımı
                if "Rate limit" in res.text or res.status_code == 400:
                    with self.key_lock:
                        logger.warning(f"ImgBB Key-{self.active_key_idx+1} kotası doldu. Sıradakine geçiliyor...")
                        self.active_key_idx += 1
                        time.sleep(0.5)
                    continue
            except Exception as e:
                logger.warning(f"ImgBB bağlantı hatası: {e}")
                with self.key_lock:
                    self.active_key_idx += 1

        # 2. FreeImage Failover
        if self.freeimage_active:
            try:
                with open(file_path, "rb") as f:
                    res = requests.post(
                        "https://freeimage.host/api/1/upload",
                        data={"key": self.freeimage_key, "action": "upload", "format": "json"},
                        files={"source": f},
                        timeout=30
                    )
                if res.status_code == 200:
                    data = res.json()
                    if "image" in data and "url" in data["image"]:
                        return data["image"]["url"]
            except Exception as e:
                logger.warning(f"FreeImage bağlantı hatası: {e}")
                self.freeimage_active = False

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

    def generate_title(self, prod_key: str, theme_title: str) -> str:
        data = self.cache.get(prod_key, {"keywords": ["Dekoratif", "Modern", "Lüks"]})
        words = data["keywords"]
        prod_def = PRODUCT_CATALOG[prod_key]
        sample_words = random.sample(words, min(3, len(words)))
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
            USER_WORKSPACE_DIR / "AI_Kalite_Artirici" / "realesrgan-ncnn-vulkan.exe",
            BASE_DIR.parent / "AI_Kalite_Artirici" / "realesrgan-ncnn-vulkan.exe"
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

        if not on_plan:
            return empty_mask

        # Eski polygon formatı geldiyse kırılmasın
        if isinstance(on_plan, list):
            if len(on_plan) >= 3:
                try:
                    pts = np.asarray(on_plan, dtype=np.int32)
                    mask = np.zeros((h, w), dtype=np.uint8)
                    pts[:, 0] = np.clip(pts[:, 0], 0, w - 1)
                    pts[:, 1] = np.clip(pts[:, 1], 0, h - 1)
                    cv2.fillPoly(mask, [pts], 255)
                    mask = cv2.GaussianBlur(mask, (0, 0), 1.2)
                    return mask
                except Exception:
                    return empty_mask
            return empty_mask

        object_boxes = on_plan.get("object_boxes", [])
        add_brush = on_plan.get("add_brush", [])
        subtract_brush = on_plan.get("subtract_brush", [])
        feather = float(on_plan.get("feather", 1.2))
        iterations = int(on_plan.get("grabcut_iterations", 5))

        final_mask = np.zeros((h, w), dtype=np.uint8)

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
        if seed is not None:
            np.random.seed(seed)
        noise = np.random.normal(0, intensity, (h, w, 3)).astype(np.float32)
        if seed is not None:
            np.random.seed(None)
        
        lum = cv2.cvtColor(np.clip(image_cv, 0, 255).astype(np.uint8), cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
        # 4*x*(1-x) parabolü ile orta tonları (0.5) maksimize eder, 0 ve 1'i minimize eder
        noise_mask = 4.0 * lum * (1.0 - lum)
        noise_mask = np.clip(noise_mask + 0.15, 0.0, 1.0)
        noise_mask_3c = np.stack([noise_mask] * 3, axis=-1)
        
        return image_cv + (noise * noise_mask_3c)

    @staticmethod
    def render_cv2_optik(art_cv: np.ndarray, bg_cv: np.ndarray, koseler: list, is_glass: bool, on_plan=None, template_name: str = None, category_name: str = None, orig_bg_cv: np.ndarray = None, alpha_mask: np.ndarray = None, source_design_identity: str = None, template_identity: str = None, recipe_version: str = None, template_sha: str = None) -> np.ndarray:
        h_bg, w_bg = bg_cv.shape[:2]
        h_art, w_art = art_cv.shape[:2]
        p = np.float32(koseler)  # [TL, TR, BR, BL]

        # -------------------------------------------------------------
        # 1. SMART-COVER: EN-BOY ORANI KORUMA (SÜNDÜRME & YAYILMA ÖNLEME)
        # -------------------------------------------------------------
        w_top = np.linalg.norm(p[1] - p[0])
        w_bot = np.linalg.norm(p[2] - p[3])
        h_left = np.linalg.norm(p[3] - p[0])
        h_right = np.linalg.norm(p[2] - p[1])
        target_w = max(1.0, (w_top + w_bot) / 2.0)
        target_h = max(1.0, (h_left + h_right) / 2.0)
        target_ar = target_w / target_h

        art_ar = w_art / float(h_art)

        if art_ar > target_ar:
            crop_w = int(round(h_art * target_ar))
            crop_h = h_art
            sx = max(0, (w_art - crop_w) // 2)
            sy = 0
            art_fitted = art_cv[:, sx:sx + crop_w]
        else:
            crop_w = w_art
            crop_h = int(round(w_art / target_ar))
            sx = 0
            sy = max(0, (h_art - crop_h) // 2)
            art_fitted = art_cv[sy:sy + crop_h, :]

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

        # 2x Supersampled Sub-pixel Kenar Yumuşatma Maskesi
        if alpha_mask is not None:
            # Şeffaf Delik (Passepartout) Maskesi
            mask_f = 1.0 - (alpha_mask.astype(np.float32) / 255.0)
        else:
            mask_f = MockupRenderer.create_subpixel_antialiased_mask(h_bg, w_bg, dst_pts, feather_px=1.8)
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
        
        # 2. Lens Sapması (Chromatic Aberration)
        warped_lit = MockupRenderer.apply_chromatic_aberration(warped_lit, intensity=1)
        
        # 3. Sensör Kumlanması (Camera Grain)
        seed = None
        if source_design_identity and template_identity and recipe_version:
            import hashlib
            h = hashlib.sha256(f"{source_design_identity}_{template_identity}_{recipe_version}".encode()).hexdigest()
            seed = int(h[:8], 16)
        warped_lit = MockupRenderer.apply_camera_grain(warped_lit, intensity=3.5, seed=seed)
        # ----------------------------------------------------------------

        # -------------------------------------------------------------
        # 4. KATEGORİYE ÖZEL YANSIMA VE GÖLGE MOTORU
        # -------------------------------------------------------------
        is_cam_dograma = (category_name == "04_Cam_Dograma")
        is_wood_or_wifi = (category_name in ["03_Ahsap_Tablo", "01_Wifi_Kutusu"])

        gw, gh = int(target_w), int(target_h)

        if is_cam_dograma:
            # A) CAM DOĞRAMA / KESME TAHTASI: Mutfak Tezgahı & Dolap Altı Spot Işık Yansıması + Rodaj Kenar
            spot_sheen = MockupRenderer.generate_kitchen_countertop_sheen(gw, gh, intensity=0.25)
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

            refl_local = MockupRenderer.generate_window_reflection(gw, gh, intensity=0.48)
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

        final = np.clip(final, 0, 255).astype(np.uint8)

        # ---------------------------------------------------------
        # FOREGROUND / OCCLUSION RESTORE (AI Cache + Manual on_plan)
        # ---------------------------------------------------------
        fg_mask = None
        try:
            if template_name:
                stem = Path(template_name).stem
                safe_cat = category_name if category_name else "default"
                mask_analyzer_version = "v1"
                cache_name = f"{safe_cat}_{template_sha}_{mask_analyzer_version}_mask.png" if template_sha else f"{safe_cat}_{stem}_foreground_mask.png"
                cache_file = BASE_DIR / "masks" / cache_name
                
                # Backward compatibility for old cache mask naming
                legacy_cache = BASE_DIR / "masks" / f"{stem}_foreground_mask.png"
                legacy_cache_cat = BASE_DIR / "masks" / f"{safe_cat}_{stem}_foreground_mask.png"
                
                if cache_file.exists():
                    fg_mask = cv2.imdecode(np.fromfile(str(cache_file), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
                elif legacy_cache_cat.exists():
                    fg_mask = cv2.imdecode(np.fromfile(str(legacy_cache_cat), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
                    cv2.imencode('.png', fg_mask)[1].tofile(str(cache_file))
                elif legacy_cache.exists():
                    fg_mask = cv2.imdecode(np.fromfile(str(legacy_cache), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
                    cv2.imencode('.png', fg_mask)[1].tofile(str(cache_file))
                    
            source_for_mask = orig_bg_cv if orig_bg_cv is not None else bg_cv
            if on_plan:
                manual_mask = MockupRenderer.build_foreground_mask(source_for_mask, on_plan)
                if manual_mask is not None and np.any(manual_mask):
                    if fg_mask is not None:
                        fg_mask = cv2.bitwise_or(fg_mask, manual_mask)
                    else:
                        fg_mask = manual_mask

            if fg_mask is not None and np.any(fg_mask):
                source_for_restore = orig_bg_cv if orig_bg_cv is not None else bg_cv
                final = MockupRenderer.restore_foreground(final, source_for_restore, fg_mask)
        except Exception as e:
            logger.warning(f"[FOREGROUND_RESTORE] Ön plan geri yükleme hatası: {e}")

        # ---------------------------------------------------------
        # 5. GÜNEŞ & PENCERE GÖLGESİ (Ahşap & Wifi için sıcak güneş, diğerleri için genel günışığı)
        # ---------------------------------------------------------
        if is_wood_or_wifi:
            final = MockupRenderer.generate_sunlight_shadow_for_wood(final, dst_pts, intensity=0.15)
        else:
            final = MockupRenderer.apply_architectural_daylight(final, angle=32.0, intensity=0.08)

        return final

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

            # Akıllı Döndürme (Smart Rotation) - Sıkışmayı Önlemek İçin
            pts = np.array(koseler)
            tw_approx = np.linalg.norm(pts[1] - pts[0])
            th_approx = np.linalg.norm(pts[2] - pts[1])
            template_is_horiz = tw_approx >= th_approx
            
            art_h, art_w = art_cv.shape[:2]
            art_is_horiz = art_w >= art_h
            
            if art_is_horiz != template_is_horiz:
                art_cv = cv2.rotate(art_cv, cv2.ROTATE_90_CLOCKWISE)
                logger.info(f"🔄 Görsel sıkışmaması için 90 derece döndürüldü: {raw_path.name}")

            # Orijinal yedek görseli yükle (True Shadow Mapping için)
            orig_path = USER_WORKSPACE_DIR / "2_SABLON_HAVUZU_ORIJINAL_YEDEK" / template_path.parent.name / template_path.name
            orig_bg_cv = None
            if orig_path.exists():
                orig_bg_cv = cv2.imdecode(np.fromfile(str(orig_path), dtype=np.uint8), cv2.IMREAD_UNCHANGED)

            final_cv = cls.render_cv2_optik(
                art_cv, bg_cv, koseler, is_glass, 
                on_plan=on_plan, template_name=template_path.name, 
                category_name=category_name, orig_bg_cv=orig_bg_cv,
                alpha_mask=alpha_mask,
                source_design_identity=source_design_identity,
                template_identity=template_identity,
                recipe_version=recipe_version,
                template_sha=template_sha
            )

            # Kalite Kontrol Denetimi (Quality Inspector)
            valid, msg = QualityInspector.inspect_mockup(final_cv, koseler if "koseler" in config else None)
            if not valid:
                logger.warning(f"  ⚠️ Kalite Denetimi Uyarısı ({raw_path.name}): {msg}")

            # Kaydet (Unicode güvenli)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            success, enc_img = cv2.imencode('.jpg', final_cv, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
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
        self._init_file()

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

    def append_row(self, row_dict: dict):
        row_dict = row_dict or {}
        with excel_lock:
            row = [row_dict.get(h, "") for h in self.HEADERS]
            self._buffer.append(row)
            if len(self._buffer) >= 50:
                self.flush()

    def flush(self):
        with excel_lock:
            if not self._buffer:
                return
            try:
                wb = openpyxl.load_workbook(self.file_path)
                ws = wb.active
                for row in self._buffer:
                    ws.append(row)
                wb.save(self.file_path)
                wb.close()
                self._buffer.clear()
            except Exception as e:
                logger.error(f"Excel yazım hatası (flush): {e}")

# ==============================================================================
# 9. ANA PC FABRİKA ORKESTRASYON MOTORU (Master Factory)
# ==============================================================================
class PCMasterFactory:
    def __init__(self, mode: str = "dongusel"):
        self.mode = mode   # "dongusel" veya "coklu"
        self.state = StateManager()
        self.uploader = AsyncCloudUploader()
        self.seo = SeoEngine()
        self.excel = FastExcelManager(EXCEL_DIR / "Urun_Yukleme_Listesi.xlsx")
        self.thread_pool = ThreadPoolExecutor(max_workers=3)

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
        """
        İlgili ürün için ayarlar.json ve Sablonlar klasöründen şablon havuzunu çeker.
        """
        pool = []
        prod_def = PRODUCT_CATALOG[prod_key]
        
        # 1. ayarlar.json içindeki kayıtlı şablonlar
        kat_cfg = AYARLAR.get("kategoriler", {}).get(prod_key, {})
        sablonlar_cfg = kat_cfg.get("sablonlar", {})

        # Klasör taraması (Sablonlar/01_Wifi_Kutusu veya kök Sablonlar/)
        target_dir = SABLON_DIR / prod_def.folder_name
        if not target_dir.exists():
            target_dir = SABLON_DIR

        for s_name, s_conf in sablonlar_cfg.items():
            base_stem = Path(s_name).stem
            s_path = target_dir / s_name
            
            # Şeffaf Sistem (Passepartout): Dosya PNG olarak kaydedilmiş olabilir
            if not s_path.exists():
                s_path_png = target_dir / f"{base_stem}.png"
                if s_path_png.exists():
                    s_path = s_path_png
                else:
                    s_path = SABLON_DIR / s_name
                    if not s_path.exists():
                        s_path_png_root = SABLON_DIR / f"{base_stem}.png"
                        if s_path_png_root.exists():
                            s_path = s_path_png_root
                            
            if s_path.exists():
                pool.append((s_name, s_path, s_conf))

        # Eğer kategoride ayarlar.json boşsa klasördeki dosyaları al (default fallback rect)
        if not pool and target_dir.exists():
            for f in target_dir.iterdir():
                if f.is_file() and f.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]:
                    pool.append((
                        f.name, f,
                        {"tip": "duz", "x": int(800*0.2), "y": int(800*0.2), "w": int(800*0.6), "h": int(800*0.6)}
                    ))

        return pool

    def process_all(self):
        items = self.load_manifest()
        if not items:
            logger.warning("İşlenecek manifest öğesi bulunamadı.")
            return

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

            # 1 Master -> 5 Ürün Genişletmesi
            for prod_key, prod_def in PRODUCT_CATALOG.items():
                # YATAY-DİKEY GARANTİSİ
                target_raw_path = h_path if prod_def.orientation == "H" else v_path
                if not target_raw_path.exists():
                    logger.warning(f"  ⚠️ Ham görsel bulunamadı ({prod_def.orientation}): {target_raw_path.name}")
                    continue

                template_pool = self.get_template_pool(prod_key)
                if not template_pool:
                    logger.warning(f"  ⚠️ Şablon havuzu boş: {prod_key}")
                    continue

                # Stable identities
                import hashlib
                recipe_version = "v1"
                with open(target_raw_path, 'rb') as f:
                    source_sha = hashlib.sha256(f.read()).hexdigest()
                source_design_identity = f"{target_raw_path.name}_{source_sha}"
                
                # Check if there are any incomplete templates to determine if we need to run
                templates_to_run = []
                for sablon_name, sablon_path, sablon_conf in template_pool:
                    with open(sablon_path, 'rb') as f:
                        template_sha = hashlib.sha256(f.read()).hexdigest()
                    template_identity = f"{sablon_name}_{template_sha}"
                    artifact_key = f"{source_design_identity}_{prod_key}_{template_identity}_{recipe_version}"
                    
                    if not self.state.is_artifact_completed(artifact_key):
                        templates_to_run.append((sablon_name, sablon_path, sablon_conf, artifact_key, template_identity, source_design_identity, recipe_version, template_sha))
                    else:
                        logger.info(f"  ⏭️ Atlandı (Artifact Zaten Tamam): {artifact_key}")
                
                if not templates_to_run:
                    continue

                # Get SKU consistently for this source_identity if needed
                sku_key = f"sku_{source_design_identity}_{prod_key}"
                with db_lock, self.state.conn:
                    row = self.state.conn.execute("SELECT value FROM system_meta WHERE key = ?", (sku_key,)).fetchone()
                    if row:
                        seq = int(row["value"])
                    else:
                        seq = self.state.get_next_sequence(prod_def.barkod_prefix)
                        self.state.conn.execute("INSERT INTO system_meta (key, value) VALUES (?, ?)", (sku_key, str(seq)))
                
                barkod = f"{prod_def.barkod_prefix}{seq:05d}"
                sku = barkod
                model_kodu = f"{prod_def.model_prefix}{seq:05d}"

                if self.mode == "coklu":
                    secilen_sablonlar = templates_to_run
                else:
                    t_idx = (seq - 1) % len(template_pool)
                    target_tmpl = template_pool[t_idx]
                    secilen_sablonlar = [t for t in templates_to_run if t[0] == target_tmpl[0]]

                for sablon_name, sablon_path, sablon_conf, artifact_key, template_identity, source_design_identity, recipe_version, template_sha in secilen_sablonlar:
                    magaza_grubu = sablon_path.stem
                    out_filename = f"{sku}_{sablon_path.stem}.jpg"
                    
                    if self.mode == "coklu":
                        out_dir = OUTPUT_COKLU_DIR / prod_key / magaza_grubu
                    else:
                        out_dir = OUTPUT_DIR / prod_key

                    out_path = out_dir / out_filename

                    logger.info(f"  🖌️ Render: {artifact_key} -> {sku}")

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
                        continue
                        
                    # P0 Fix: Call RealESRGAN Quality Engine
                    # We check if 4K engine is active/available
                    if RealESRGANQualityEngine.get_exe_path():
                        logger.info(f"  🔍 Kalite Artırılıyor (4K RealESRGAN): {out_path.name}")
                        upscaled_path = out_path.with_name("4k_" + out_path.name)
                        if RealESRGANQualityEngine.upscale_4k(out_path, upscaled_path):
                            # Replace original with upscaled
                            import shutil
                            shutil.move(str(upscaled_path), str(out_path))

                    # SEO Başlık ve Açıklama
                    seo_title = self.seo.generate_title(prod_key, theme_title)
                    seo_desc = self.seo.get_description(prod_key, theme_title, style_key)

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
                        "mockup_dosyasi": out_filename,
                        "magaza_grubu": magaza_grubu,
                        "resim_linki": "",
                        "status": "RENDERED"
                    }

                    # Arka Planda Yükle ve Excel'e Yaz (Non-blocking)
                    self.thread_pool.submit(self._async_upload_and_excel, out_path, prod_record)

        logger.info("\n⏳ Tüm mockuplar çizildi, arkaplandaki bulut yüklemeleri tamamlanıyor...")
        self.thread_pool.shutdown(wait=True)
        self.excel.flush()

        logger.info("\n🎉 TÜM İŞLEMLER BAŞARIYLA TAMAMLANDI!")
        logger.info(f"📊 Durum Özeti: {self.state.get_summary()}")
        logger.info(f"📁 Çıktı Excel: {self.excel.file_path}")

    def _async_upload_and_excel(self, mockup_path: Path, prod_record: dict):
        url = self.uploader.upload_sync(mockup_path)
        if url:
            prod_record["resim_linki"] = url
            prod_record["upload_url"] = url
            prod_record["status"] = "UPLOADED"
            logger.info(f"    ☁️ Bulut Yüklendi: {prod_record['sku']} -> {url}")
        else:
            prod_record["status"] = "UPLOAD_FAILED"
            logger.info(f"    💾 Yerel Kaydedildi (Bulut atlandı/Hata): {prod_record['sku']}")

        self.state.save_render_artifact(prod_record)
        # Sadece backward-compatibility icin products'a update
        self.state.save_product(prod_record)

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
            "Resim Linki": prod_record.get("resim_linki", ""),
            "Eklenme Zamanı": time.strftime("%d.%m.%Y %H:%M:%S")
        }
        self.excel.append_row(excel_row)

# ==============================================================================
# 10. CLI VE İNTERAKTİF GİRİŞ NOKTASI
# ==============================================================================
def parse_args():
    p = argparse.ArgumentParser(description="PC Master Mockup & Commerce Factory V5")
    p.add_argument("--mod", choices=["dongusel", "coklu"], default="dongusel",
                   help="Dağıtım modu: 'dongusel' (tek klasör/tek excel) veya 'coklu' (K1..K11 klasörleri)")
    return p.parse_args()

if __name__ == "__main__":
    args = parse_args()
    bot = PCMasterFactory(mode=args.mod)
    bot.process_all()
