"""V4.0 Unified 7-Category High-Volume Persistent Batch Production Engine.

Combines all human-approved templates across all 7 categories:
  - 01_Wifi_Kutusu (WFI)
  - 02_Cam_Tablo_Dikey (CTD)
  - 02_Cam_Tablo_Yatay (CTY)
  - 03_Ahsap_Tablo (AHT)
  - 04_Cam_Dograma (CMD)
  - 05_Ocak_Arkasi (OCA)
  - 06_Petek_Kapama (PDK)

Key guarantees:
1. No 10-template limit: all human-approved eligible templates can run together
   with `max_jobs` up to 100,000 in a persistent SQLite ledger.
2. Zero blur padding: default `cover` placement fills the 4-corner print surface
   sharply without synthetic blurred borders.
3. Exact pixel preservation: outside the approved mask (including Petek top/bottom
   curves, vertical slots, parquet floor, and Cam Doğrama window mullions),
   original source pixels remain 100% byte-identical (`out[mask==0] == scene[mask==0]`).
4. Fail-closed receipts & atomic create-only files: never overwrites existing
   outputs, verifies SHA-256 on disk before marking `RENDERED`, and validates
   both `.csv` and `.xlsx` exports on read-back.
"""
from __future__ import annotations

import csv
from io import StringIO
import hashlib
import json
import logging
import math
import os
from pathlib import Path
import re
import sqlite3
import tempfile
import threading
from typing import Any

import cv2
import numpy as np
from openpyxl import Workbook, load_workbook

from PETEK_V3 import engine as petek_engine
from PETEK_V3.cutout_paste import render_with_cutout_paste
from PETEK_V3.registry import Registry as PetekRegistry
from PETEK_V3.safety_audit import audit_summary

from .unlimited_selection import (
    ALL_SEVEN_CATEGORIES,
    CATEGORY_LABELS_TR,
    CATEGORY_SKU_PREFIXES,
    discover_all_approved_seven_categories,
)
from .crash_recovery import inspect_interrupted_state, recover_interrupted_state
from .manual_geometry import validated_legacy_manual_quad
from .design_proxy_v43 import prepare_render_artwork
from .upscale4k_v44 import process as upscale_new_outputs
from .finish_v42 import GLASS, projected_rounded_alpha
from .finish_material_v46 import apply_material_finish, DAYLIGHT, RECIPE as MATERIAL_RECIPE
from PETEK_V3.geometry_qa_v47 import inspect_print_safety
from .store_profiles_v47 import StoreProfiles, key_for
from .store_identity_v485 import store_codes, design_number, filename as store_filename
from .resume_checkpoint_v47 import (read_checkpoint, write_checkpoint,
                                    snapshot_inputs, same_inputs, SCHEMA as RESUME_SCHEMA)
import random
import secrets
from PETEK_V3.excel_links_v42 import xlsx_with_photo_links, verify_photo_links

EXT = {".jpg", ".jpeg", ".png", ".webp"}
V4_RECIPE = "v4-6-chroma-solid-20261026"

UNIFIED_HEADERS = [
    "Stok Kodu",
    "Dahili Barkod (GS1 Degil)",
    "Model Kodu",
    "Kategori",
    "Urun Adi",
    "Tasarim Dosyasi",
    "Sablon",
    "Mockup Dosyasi",
    "Yerel Dosya",
    "Islem Durumu",
    "Gorsel SHA256",
]


def store_v4_root() -> Path:
    override = os.getenv("V4_UNIFIED_LOCAL_STATE", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    base = os.getenv("LOCALAPPDATA")
    return (Path(base) if base else Path.home() / ".gorsel_mockup") / "GorselMockup" / "UnifiedV4"


def _escape(text: Any) -> str:
    data = str(text or "")
    return "'" + data if data.lstrip().startswith(("=", "+", "-", "@")) else data


def iter_designs(folder: Path):
    for directory, dirs, files in os.walk(folder, followlinks=False):
        dirs[:] = sorted([name for name in dirs if not (Path(directory) / name).is_symlink()])
        for name in sorted(files):
            p = Path(directory) / name
            if p.suffix.lower() in EXT and not p.is_symlink():
                yield p


def unified_receipt_identity(
    item: dict[str, Any],
    art_sha: str,
    *,
    group: str,
    placement: str,
    lighting: str,
    recipe: str = V4_RECIPE,
    corner_radius: float = .008,
    glass_effect: str = "on",
) -> tuple[str, dict[str, Any]]:
    """Deterministic versioned identity covering category, template SHA, mask SHA, quad, aspect, and art SHA."""
    quad = item.get("quad")
    if not isinstance(quad, list) or len(quad) != 4:
        raise petek_engine.MaskError("Onaylı dört köşe bilgisi eksik.")
    geom = [[round(float(p[0]), 6), round(float(p[1]), 6)] for p in quad]
    physical = round(float(item["physical_aspect"]), 8)
    if any(len(p) != 2 or not all(math.isfinite(v) for v in p) for p in geom):
        raise petek_engine.MaskError("Geometri koordinatları geçersiz.")
    if not math.isfinite(physical) or not (0.1 < physical < 12.0):
        raise petek_engine.MaskError("Fiziksel oran geçersiz.")
    payload = {
        "identity_version": 4,
        "recipe": str(recipe),
        "group": str(group),
        "category": str(item["category"]),
        "template_uid": str(item["uid"]),
        "source_sha256": str(item["source_sha"]),
        "mask_sha256": str(item.get("mask_sha") or "POLYGON_MASK_V4"),
        "art_sha256": str(art_sha),
        "front_quad": geom,
        "physical_aspect": physical,
        "placement": str(placement),
        "lighting": str(lighting),
        "corner_radius": round(float(corner_radius), 6),
        "glass_effect": str(glass_effect),
    }
    stamp = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    digest = hashlib.sha256(stamp.encode("utf-8")).hexdigest()
    return digest, payload


def _build_legacy_category_mask(scene: np.ndarray, quad, legacy_data: dict[str, Any] | None) -> np.ndarray:
    """Build printable surface mask for categories 01..05, respecting any Cam Doğrama window frame polygons."""
    q = validated_legacy_manual_quad(quad, scene.shape)
    mask = petek_engine.polygon_mask(scene.shape, q)
    if isinstance(legacy_data, dict):
        window_polys = legacy_data.get("pencere_maskesi") or []
        if isinstance(window_polys, list):
            for poly in window_polys:
                if isinstance(poly, list) and len(poly) >= 3:
                    pts = np.round(np.asarray(poly, dtype=np.float32)).astype(np.int32)
                    cv2.fillPoly(mask, [pts], 0)
    return mask


def _render_legacy_six_cover(
    source_path: Path,
    art_path: Path,
    quad,
    mask: np.ndarray,
    physical_aspect: float,
    *,
    placement: str = "cover",
    lighting: str = "natural",
    edge_feather_px: float = 1.4,
    category: str = "",
    corner_radius: float = .008,
    glass_effect: str = "on",
    marketplace: bool = True,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Render categories 01..05 with full-bleed cover projection, natural lighting, and strict background preservation."""
    from PETEK_V3 import realism
    scene = petek_engine.read_bgr(source_path)
    design = petek_engine.read_bgr(art_path)
    q = validated_legacy_manual_quad(quad, scene.shape)
    poly = petek_engine.polygon_mask(scene.shape, q)
    leak = int(np.count_nonzero((mask > 1) & (poly == 0)))
    if leak:
        raise petek_engine.MaskError(f"Maske panel dışına taşıyor: {leak} piksel.")
    fraction = float(np.count_nonzero(mask > 127) / max(1, np.count_nonzero(poly)))
    if not (0.14 <= fraction <= 1.0):
        raise petek_engine.MaskError(f"Baskı alanı oranı geçersiz ({fraction:.1%}).")
    projected = petek_engine.warp_artwork(design, q, scene.shape, physical_aspect, placement=placement)
    from .chroma_render_v46 import prepare_chroma
    neutral_scene, chroma_pixels = prepare_chroma(scene, mask)
    lit = realism.apply(neutral_scene, projected, mask, lighting)
    if category in GLASS | DAYLIGHT and glass_effect == "on" and lighting != "off":
        lit = apply_material_finish(scene, lit, mask, q, category, enabled=True)
    out = scene.copy()
    active = mask > 0
    alpha = mask.astype(np.float32) / 255.0
    if category in GLASS and corner_radius > 0:
        alpha *= projected_rounded_alpha(scene.shape, q, corner_radius)
    if edge_feather_px > 0:
        dist = cv2.distanceTransform(np.uint8(active), cv2.DIST_L2, 3)
        alpha *= np.clip(dist / float(edge_feather_px), 0.0, 1.0)
    if chroma_pixels is not None:
        # Never blend the magenta marker back into printed edge pixels.
        alpha[chroma_pixels] = 1.0
    a = alpha[active][:, None]
    out[active] = np.uint8(
        np.clip(
            lit[active].astype(np.float32) * a + scene[active].astype(np.float32) * (1.0 - a) + 0.5,
            0,
            255,
        )
    )
    if not np.array_equal(out[mask == 0], scene[mask == 0]):
        raise petek_engine.MaskError("Orijinal arka plan / çerçeve koruma ihlali.")
    qa = {
        "chroma_solid_coverage": chroma_pixels is not None,
        "printable_fraction": round(fraction, 5),
        "preserved_pixels": int(np.count_nonzero(mask == 0)),
        "source_pixels_unchanged": True,
        "zero_blur_padding": placement == "cover",
        "lighting": lighting,
        "corner_radius": corner_radius if category in GLASS else 0.0,
        "optical_finish": category in (GLASS | DAYLIGHT) and glass_effect == "on" and lighting != "off",
        "optical_recipe": MATERIAL_RECIPE if category in (GLASS | DAYLIGHT) and glass_effect == "on" and lighting != "off" else "legacy",
        "glass_effect": glass_effect if category in GLASS else "not_applicable",
    }
    return (petek_engine.canvas_3x4(out) if marketplace else out), qa


class UnifiedV4Ledger:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.file = self.root / "v4_ortak_uretim.sqlite3"
        if self.file.is_symlink():
            raise petek_engine.MaskError("Ortak üretim DB bağlantısı güvensiz (symlink).")
        with self.connect() as con:
            con.execute(
                """CREATE TABLE IF NOT EXISTS artifact (
                    key TEXT PRIMARY KEY,
                    sku TEXT NOT NULL,
                    category TEXT NOT NULL,
                    art_sha TEXT NOT NULL,
                    template_sha TEXT NOT NULL,
                    mask_sha TEXT NOT NULL,
                    art_name TEXT NOT NULL,
                    uid TEXT NOT NULL,
                    output TEXT NOT NULL,
                    output_sha TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL,
                    message TEXT NOT NULL DEFAULT '',
                    updated TEXT DEFAULT CURRENT_TIMESTAMP
                )"""
            )
            con.execute("CREATE INDEX IF NOT EXISTS artifact_status_idx ON artifact(status)")
            con.execute("CREATE INDEX IF NOT EXISTS artifact_cat_idx ON artifact(category)")

    def connect(self):
        con = sqlite3.connect(self.file, timeout=30)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA busy_timeout=30000")
        return con

    def reserve(self, fields: dict[str, Any]) -> dict[str, Any]:
        with self.connect() as con:
            con.execute(
                """INSERT OR IGNORE INTO artifact
                (key, sku, category, art_sha, template_sha, mask_sha, art_name, uid, output, status)
                VALUES (:key, :sku, :category, :art_sha, :template_sha, :mask_sha, :art_name, :uid, :output, 'PENDING')""",
                fields,
            )
            found = dict(con.execute("SELECT * FROM artifact WHERE key=?", (fields["key"],)).fetchone())
        for k in ("key", "sku", "category", "art_sha", "template_sha", "mask_sha", "uid", "output"):
            if found[k] != fields[k]:
                raise petek_engine.MaskError("Kayıt kimliği eski işlemle çakışıyor: " + k)
        return found

    def complete(self, key: str, sha: str) -> None:
        with self.connect() as con:
            record = con.execute("SELECT output, status FROM artifact WHERE key=?", (key,)).fetchone()
            if record is None or record["status"] != "PENDING":
                raise petek_engine.MaskError("URETIM_KAYDI_TUTARSIZ")
            path = Path(record["output"])
            if path.is_symlink() or not path.is_file():
                raise petek_engine.MaskError("URETIM_CIKTISI_YOK_VEYA_GUVENSIZ")
            if not isinstance(sha, str) or len(sha) != 64 or petek_engine.digest(path) != sha:
                raise petek_engine.MaskError("URETIM_CIKTISI_SHA_DOGRULANAMADI")
            cur = con.execute(
                """UPDATE artifact SET output_sha=?, status='RENDERED', updated=CURRENT_TIMESTAMP
                WHERE key=? AND status='PENDING'""",
                (sha, key),
            )
            if cur.rowcount != 1:
                raise petek_engine.MaskError("URETIM_KAYDI_TUTARSIZ")

    def quarantine(self, key: str, error: str) -> None:
        with self.connect() as con:
            con.execute(
                """UPDATE artifact SET status='REVIEW_REQUIRED', message=?, updated=CURRENT_TIMESTAMP
                WHERE key=? AND status IN ('PENDING','REVIEW_REQUIRED')""",
                (str(error)[:300], key),
            )

    def successful(self) -> list[dict[str, Any]]:
        with self.connect() as con:
            return [
                dict(row)
                for row in con.execute(
                    "SELECT * FROM artifact WHERE status='RENDERED' ORDER BY category, sku, uid"
                )
            ]


class UnifiedV4Batch:
    """High-volume 7-category batch production engine without the 10-template limit."""

    def __init__(
        self,
        root: Path | None = None,
        *,
        runtime_root: Path | None = None,
        petek_registry: PetekRegistry | None = None,
    ):
        self.root = Path(root or store_v4_root()).resolve()
        if self.root.is_symlink():
            raise petek_engine.MaskError("V4 kayıt klasörü symlink olamaz.")
        self.output = self.root / "uretilen_gorseller"
        self.reports = self.root / "raporlar"
        for p in (self.output, self.reports):
            if p.is_symlink():
                raise petek_engine.MaskError("V4 alt klasörü symlink olamaz.")
            p.mkdir(parents=True, exist_ok=True)
        self.runtime_root = Path(runtime_root).resolve() if runtime_root else None
        self.petek_registry = petek_registry or PetekRegistry()
        self.ledger = UnifiedV4Ledger(self.root)
        self.lock_path = self.root / "V4_ORTAK_FABRIKA.lock"
        self.cancel = threading.Event()
        self.pause = threading.Event()

    def request_pause(self) -> None:
        """Pause *between* jobs; never interrupt an in-progress image write."""
        self.pause.set()

    def resume(self) -> None:
        self.pause.clear()

    def request_stop(self) -> None:
        self.cancel.set()
        self.pause.clear()  # Stop must never deadlock behind pause.

    def _wait_if_paused(self, notify) -> bool:
        """Return False for cancellation; wait cooperatively without busy spin."""
        announced = False
        while self.pause.is_set() and not self.cancel.is_set():
            if not announced:
                notify("DURAKLATILDI: mevcut görsel kaydı korundu; Devam Et veya Güvenli Durdur seçin.")
                announced = True
            self.cancel.wait(0.20)
        return not self.cancel.is_set()

    def discover_templates(
        self,
        *,
        categories: tuple[str, ...] | list[str] | None = None,
        per_category_limit: int | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Discover all human-approved templates across all 7 categories (unlimited by default)."""
        return discover_all_approved_seven_categories(
            self.runtime_root,
            petek_registry=self.petek_registry,
            categories=categories,
            per_category_limit=per_category_limit,
        )

    def inspect_recovery(self) -> dict[str, Any]:
        return inspect_interrupted_state(self.ledger.file, self.lock_path, self.output)

    def last_batch_checkpoint(self) -> dict | None:
        """Read only, local APPDATA; historical images/DB are untouched."""
        return read_checkpoint(self.root)

    def resume_last_stopped(self, *, notify=None) -> dict[str, Any]:
        """Resume a deliberately stopped job using exactly its original inputs.

        Completed items are SHA-verified from the persistent ledger and skipped.
        Stale locks, tampering, modified artwork, changed approvals or profile
        assignments FAIL CLOSED instead of implicitly altering the job.
        """
        checkpoint = self.last_batch_checkpoint()
        if not checkpoint:
            raise petek_engine.MaskError(
                'Eski turda kaydedilmiş devam kontrolü bulunamadı. '
                'Önceki sürümde durdurulan tur için aynı seçimlerle yeni üretim başlatın; '
                'onaylı mevcut çıktılar SHA ile atlanır.')
        if checkpoint['status'] != 'STOPPED':
            raise petek_engine.MaskError(
                'Devam yalnız Güvenli Durdur ile sonlanan tur içindir; durum: '
                + str(checkpoint['status']) + '. Çökme varsa Kesinti Kurtarma açın.')
        if self.lock_path.exists() or self.lock_path.is_symlink():
            raise petek_engine.MaskError(
                'Üretim kilidi mevcut. Aktif veya bayat kilit otomatik kaldırılmaz; '
                'Yarım İş / Kilit Kurtarma ile inceleyin.')
        if checkpoint.get('state_root') != str(self.root):
            raise petek_engine.MaskError('Devam kontrolü farklı üretim kayıt klasörüne ait.')
        runtime = str(self.runtime_root) if self.runtime_root else None
        if checkpoint.get('runtime_root') != runtime:
            raise petek_engine.MaskError('Devam kontrolü başka çalışma klasörüne ait.')
        if checkpoint.get('render_recipe') != (V4_RECIPE, MATERIAL_RECIPE, petek_engine.RECIPE):
            # JSON arrays round-trip as lists.
            if checkpoint.get('render_recipe') != [V4_RECIPE, MATERIAL_RECIPE, petek_engine.RECIPE]:
                raise petek_engine.MaskError(
                    'Devam kontrolü başka motor sürümüne ait; otomatik yeniden üretim güvenli değil.')
        config = checkpoint['config']
        self.cancel.clear()
        self.pause.clear()
        return self.run(**config, notify=notify, _resume_expected=checkpoint)

    def recover(
        self,
        *,
        reviewer: str,
        confirm: str,
        requeue_review_required: bool = False,
    ) -> dict[str, Any]:
        return recover_interrupted_state(
            self.ledger.file,
            self.lock_path,
            self.output,
            self.reports,
            reviewer=reviewer,
            confirm=confirm,
            requeue_review_required=requeue_review_required,
        )

    def run(
        self,
        design_folder: Path | str,
        *,
        selected_uids: list[str] | None = None,
        selected_stores: list[str] | None = None,
        random_seed: int | None = None,
        categories: tuple[str, ...] | list[str] | None = None,
        per_category_limit: int | None = None,
        group: str = "LOCAL",
        notify=None,
        max_jobs: int | None = None,
        placement: str = "cover",
        lighting: str = "natural",
        corner_radius: float | None = None,
        glass_effect: str = "on",
        upscale_4k: bool = False,
        upscale_model: str = "photo",
        upscale_exe: Path | str | None = None,
        _resume_expected: dict | None = None,
    ) -> dict[str, Any]:
        notify = notify or (lambda msg: None)
        if corner_radius is not None and not 0 <= float(corner_radius) <= .04:
            raise petek_engine.MaskError("Köşe yuvarlatma %0-%4 arasında olmalı.")
        if glass_effect not in ("on", "off"):
            raise petek_engine.MaskError("Cam efekti Açık veya Kapalı olmalı.")
        if placement not in petek_engine.PLACEMENT_MODES:
            raise petek_engine.MaskError("Yerleşim modu geçersiz: cover veya contain.")
        if not re.fullmatch(r"[A-Za-z0-9_-]{2,36}", str(group)):
            raise petek_engine.MaskError("Mağaza grubu yalnızca harf, sayı, alt çizgi, tire içerebilir.")
        if max_jobs is not None and int(max_jobs) < 1:
            raise petek_engine.MaskError("İş limiti pozitif olmalı veya sınırsız bırakılmalı.")

        designs = Path(design_folder).resolve(strict=True)
        if not designs.is_dir():
            raise petek_engine.MaskError("Tasarım klasörü bulunamadı.")
        if designs == self.root or self.root in designs.parents or designs in self.root.parents:
            raise petek_engine.MaskError("Tasarım klasörü çıktı/kayıt dizini içinde olamaz.")

        templates, discovery_audit = self.discover_templates(
            categories=categories,
            per_category_limit=per_category_limit,
        )
        if selected_uids is not None:
            wanted = set(selected_uids)
            found = {t["uid"] for t in templates}
            missing = wanted - found
            if missing:
                raise petek_engine.MaskError(
                    "Seçilen şablonların bir kısmı artık onaylı/güvenli değil: "
                    + ", ".join(sorted(missing)[:10])
                )
            templates = [t for t in templates if t["uid"] in wanted]
        if len({t["uid"] for t in templates}) != len(templates):
            raise petek_engine.MaskError(
                "Şablon UID çakışması: yanlış görsele üretim yapılmaması için işlem engellendi."
            )
        if not templates:
            raise petek_engine.MaskError("Seçilen kriterlere uygun insan onaylı (APPROVED) şablon bulunamadı.")
        # Stable source/approved SHA membership stored outside the OneDrive workspace.
        # No store selected retains the existing group + entire legacy pool.
        if selected_stores:
            production_plan = StoreProfiles(self.root).plan(selected_stores, templates,
                                                              selected_uids=selected_uids)
        else:
            production_plan = [(group, templates)]
        seed = int(random_seed) if random_seed is not None else secrets.randbits(64)
        rng = random.Random(seed)
        rng.shuffle(production_plan)
        designs_in_run = list(iter_designs(designs))
        if not designs_in_run:
            raise petek_engine.MaskError("Tasarım klasöründe kullanılabilir görsel yok.")
        rng.shuffle(designs_in_run)
        for _, store_templates in production_plan:
            rng.shuffle(store_templates)

        # Immutable checkpoint identity. We reread every chosen input SHA on
        # restart; a changed design or approved source cannot enter an old run.
        inventory = snapshot_inputs(designs_in_run, production_plan)
        config = {
            'design_folder': str(designs),
            'selected_uids': sorted(t['uid'] for t in templates),
            'selected_stores': list(selected_stores or []),
            'categories': list(categories) if categories is not None else None,
            'per_category_limit': per_category_limit,
            'group': group,
            'max_jobs': max_jobs,
            'placement': placement,
            'lighting': lighting,
            'corner_radius': corner_radius,
            'glass_effect': glass_effect,
            'upscale_4k': bool(upscale_4k),
            'upscale_model': upscale_model,
            'upscale_exe': str(upscale_exe) if upscale_exe is not None else None,
            'random_seed': seed,
        }
        if _resume_expected is not None:
            if not same_inputs(_resume_expected['inventory'], inventory):
                raise petek_engine.MaskError(
                    'Kaldığı yerden devam engellendi: tasarım dosyaları, onaylı '
                    'şablon SHA değerleri veya mağaza atamaları değişmiş. '
                    'Önce kaynak/atama değişikliklerini inceleyin.')
            if _resume_expected['config'] != config:
                raise petek_engine.MaskError(
                    'Kaldığı yerden devam engellendi: eski üretim ayarları uyuşmuyor.')

        checkpoint_record = {
            'schema': RESUME_SCHEMA,
            'status': 'RUNNING',
            'state_root': str(self.root),
            'runtime_root': str(self.runtime_root) if self.runtime_root else None,
            'render_recipe': [V4_RECIPE, MATERIAL_RECIPE, petek_engine.RECIPE],
            'config': config,
            'inventory': inventory,
            'progress': {'attempted': 0, 'rendered': 0, 'reused': 0},
        }

        for t in templates:
            # A source may disappear between discovery and production. Its
            # individual attempt must be marked for review, not crash the
            # whole batch before the persistent lock is obtained.
            src = Path(t["source"]).resolve(strict=False)
            if src == designs or designs in src.parents or src in designs.parents:
                raise petek_engine.MaskError("Tasarım klasörü kaynak şablon klasörüyle aynı olamaz.")

        if self.lock_path.exists() or self.lock_path.is_symlink():
            raise petek_engine.MaskError(
                "Başka bir V4 üretim işlemi çalışıyor veya önceki kesinti kilidi kurtarma bekliyor."
            )
        try:
            fd = os.open(str(self.lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            raise petek_engine.MaskError("V4 üretim kilidi dolu.") from exc
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))

        stats: dict[str, Any] = {
            "status": "RUNNING",
            "placement": placement,
            "lighting": lighting,
            "glass_effect": glass_effect,
            "unlimited_jobs_enabled": max_jobs is None,
            "unlimited_templates_enabled": per_category_limit is None,
            "approved_template_count": len(templates),
            "store_ids": [store for store,_ in production_plan],
            "random_order_seed": seed,
            "duplicates_skipped_in_run": 0,
            "per_category_templates": discovery_audit["per_category_counts"],
            "attempted": 0,
            "rendered": 0,
            "reused": 0,
            "current_batch_keys": [],  # Only these SHA-verified products may auto-link.
            "rejected": 0,
            "errors": [],
            "local_only": True,
            "marketplace_published": False,
        }

        # Save new output list for optional post-processing; reused older outputs
        # are never silently post-processed or uploaded.
        newly_rendered: list[dict[str, str]] = []
        notify(f"MAĞAZA/SIRA PLANI: {len(production_plan)} mağaza, "
               f"{len(designs_in_run)} tasarım; rastgele tohum: {seed}. "
               "Onaylı dört köşe ve mevcut çıktılar değişmez.")
        try:
            # Save the source/selection fingerprint before rendering begins.
            # STOP only takes effect between jobs, so ledger replay is exact.
            write_checkpoint(self.root, checkpoint_record)
            processed_jobs = set()
            for group, templates in production_plan:
                for art in designs_in_run:
                    if not self._wait_if_paused(notify):
                        break
                    if self.cancel.is_set() or (max_jobs is not None and stats["attempted"] >= int(max_jobs)):
                        break
                    original_art = art
                    try:
                        render_art, art_sha = prepare_render_artwork(
                            original_art, self.root / "working_art_proxies")
                    except (petek_engine.MaskError, cv2.error, OSError, ValueError) as exc:
                        stats["rejected"] += 1
                        stats["errors"].append({"design": original_art.name,
                                                "reason": "TASARIM_BOYUTU_VE_GUVENLIK: " + str(exc)})
                        notify(f"ATLANDI TASARIM {original_art.name}: {exc}")
                        continue

                    # Draw a fresh template permutation for EVERY design,
                    # not only once for the entire store. Large batches no
                    # longer paint each design in the same template order.
                    template_order = list(templates)
                    rng.shuffle(template_order)
                    for item in template_order:
                        if not self._wait_if_paused(notify):
                            break
                        if self.cancel.is_set() or (max_jobs is not None and stats["attempted"] >= int(max_jobs)):
                            break
                        # Prevent repeat renders for identical artwork SHA and
                        # category+approved template within the same store/run.
                        unique_pair = (group, key_for(item), art_sha)
                        if unique_pair in processed_jobs:
                            stats["duplicates_skipped_in_run"] += 1
                            notify(f"AYNI TURDA TEKRAR ATLANDI: {group}/{item['uid']}/{art.name}")
                            continue
                        processed_jobs.add(unique_pair)
                        stats["attempted"] += 1
                        cat = item["category"]
                        uid = item["uid"]
                        prefix = CATEGORY_SKU_PREFIXES.get(cat, "MKP")
                        source_path = Path(item["source"])
                        source_sha = item["source_sha"]

                        # Each selected template is independently validated. An
                        # unreadable/missing mask must NOT stop all other jobs.
                        # No ledger reservation is possible until mask + identity
                        # are verified; preserve the failure in batch QA instead.
                        try:
                            if item["engine_type"] == "PETEK_V3_CUTOUT":
                                profile, mask = self.petek_registry.get(
                                    uid, require_approved=True, source_override=source_path)
                                mask_sha = profile["mask_sha"]
                            else:
                                scene_for_mask = petek_engine.read_bgr(source_path)
                                mask = _build_legacy_category_mask(scene_for_mask, item["quad"], item.get("legacy_data"))
                                mask_sha = petek_engine.mask_hash(mask)
                            item_with_mask = dict(item, mask_sha=mask_sha)
                            saved_radius = item.get("legacy_data", {}).get("glass_corner_radius", .008)
                            active_corner_radius = (float(corner_radius) if corner_radius is not None else float(saved_radius)) if cat in GLASS else 0.0
                            if not 0 <= active_corner_radius <= .04:
                                raise petek_engine.MaskError("Şablondaki cam köşesi ayarı geçersiz.")
                            full_key, _ = unified_receipt_identity(
                                item_with_mask,
                                art_sha,
                                group=group,
                                placement=placement,
                                lighting=lighting,
                                corner_radius=active_corner_radius,
                                glass_effect=glass_effect if cat in (GLASS | DAYLIGHT) else "not_applicable",
                                recipe=((V4_RECIPE + "+" + MATERIAL_RECIPE)
                                    if cat in (GLASS | DAYLIGHT) and glass_effect == "on" and lighting != "off"
                                    else V4_RECIPE) + ('+STORE_CODES_V485' if selected_stores else ''),
                            )
                        except (petek_engine.MaskError, cv2.error, OSError, ValueError, KeyError, TypeError) as exc:
                            stats["rejected"] += 1
                            stats["errors"].append(
                                {"category": cat, "template": uid, "design": art.name,
                                 "reason": "GEOMETRI_VE_MASKE_DENETIMI: " + str(exc)}
                            )
                            notify(f"İNCELEME GEREKİYOR [{cat}] {uid} / {art.name}: {exc}")
                            continue
                        key = full_key[:24]
                        if selected_stores:
                            # The filename and business identifiers are derived
                            # from the SHARED original artwork number, never from
                            # output hashes. Different stores use separately
                            # assigned approved templates and unique filenames.
                            design_id=design_number(original_art)
                            identifiers=store_codes(design_id,group,cat)
                            sku=identifiers['sku']
                            output_name=store_filename(design_id,group,cat,uid)
                        else:
                            sku=f"{prefix}-{group}-{full_key[:18].upper()}"
                            output_name=f"{sku}_{key}.png"
                        output=self.output / group / cat / output_name

                        fields = {
                            "key": key,
                            "sku": sku,
                            "category": cat,
                            "art_sha": art_sha,
                            "template_sha": source_sha,
                            "mask_sha": mask_sha,
                            "art_name": art.name,
                            "uid": uid,
                            "output": str(output),
                        }
                        try:
                            record = self.ledger.reserve(fields)
                            if record["status"] == "USER_REMOVED":
                                # User intentionally deleted this output. Preserve its
                                # SKU/receipt and NEVER silently recreate or flag it
                                # as a corrupted render on subsequent batch runs.
                                stats["user_removed"] = stats.get("user_removed", 0) + 1
                                notify(f"KULLANICI TARAFINDAN SİLİNDİ / tarihî kayıt korundu: [{cat}] {uid} / {art.name}")
                                continue
                            if record["status"] == "RENDERED":
                                if (
                                    output.is_symlink()
                                    or not output.is_file()
                                    or petek_engine.digest(output) != record["output_sha"]
                                ):
                                    raise petek_engine.MaskError(
                                        "Önceden tamamlanan çıktı bulunamadı veya değiştirilmiş."
                                    )
                                stats["reused"] += 1
                                stats["current_batch_keys"].append(key)
                                if _resume_expected is not None and upscale_4k:
                                    # STOP can occur before the deferred 4K stage.
                                    # When resuming, completed 1200x1600 prints of
                                    # the SAME frozen batch also require 4K; the
                                    # upscaler independently reuses valid 4K
                                    # receipts and refuses to overwrite them.
                                    newly_rendered.append({
                                        "key": key, "sku": sku,
                                        "output": str(output),
                                        "output_sha": record["output_sha"],
                                    })
                                notify(f"ATLANDI / mevcut kayıt: [{cat}] {uid} / {art.name}")
                                continue
                            if record["status"] != "PENDING" or output.exists():
                                raise petek_engine.MaskError(
                                    "Şüpheli eski/tamamlanmamış çıktı: kesinti kurtarma veya inceleme gerekli."
                                )
                            if petek_engine.digest(source_path) != source_sha:
                                raise petek_engine.MaskError("Orijinal şablon üretim öncesi değiştirildi.")

                            if item["engine_type"] == "PETEK_V3_CUTOUT":
                                # Match the REAL preview settings. A 1.4px
                                # inner feather blends the original MAGENTA
                                # source back into every thin vent lip and
                                # leaves pink streaks in the final artwork.
                                # Only high-confidence magenta source scenes
                                # use a hard edge. Vent/core/floor pixels
                                # remain untouched by the immutable mask.
                                from PETEK_V3.grille_guard_v482 import recommended_edge_feather
                                source_scene=petek_engine.read_bgr(source_path)
                                grille_edge_px=recommended_edge_feather(source_scene,item["quad"])
                                picture, _, _ = render_with_cutout_paste(
                                    source_scene,
                                    render_art,
                                    item["quad"],
                                    mask,
                                    item["physical_aspect"],
                                    marketplace=False,
                                    placement=placement,
                                    lighting=lighting,
                                    edge_feather_px=grille_edge_px,
                                )
                                if lighting != "off" and glass_effect == "on":
                                    raw_scene = petek_engine.read_bgr(source_path)
                                    picture = apply_material_finish(raw_scene, picture, mask,
                                        item["quad"], cat, enabled=True)
                                # Assert untouched vent/curve/floor/background pixels
                                # before portrait conversion. The operator-approved
                                # semantic mask is still the only source of truth.
                                source_scene = petek_engine.read_bgr(source_path)
                                geometry_report = inspect_print_safety(
                                    source_scene, picture, mask, item["quad"])
                                if geometry_report['status'] != 'PASS':
                                    raise petek_engine.MaskError('PETEK_PROTECTED_PIXELS_CHANGED')
                                picture = petek_engine.canvas_3x4(picture)
                            else:
                                picture, _ = _render_legacy_six_cover(
                                    source_path,
                                    render_art,
                                    item["quad"],
                                    mask,
                                    item["physical_aspect"],
                                    marketplace=True,
                                    placement=placement,
                                    lighting=lighting,
                                    category=cat,
                                    corner_radius=active_corner_radius,
                                    glass_effect=glass_effect,
                                )

                            encoded_png = petek_engine.encode_png(picture)
                            petek_engine.atomic_new_file(output, encoded_png)
                            receipt_sha = petek_engine.digest(output)
                            if (
                                petek_engine.digest(source_path) != source_sha
                                or petek_engine.digest(original_art) != art_sha
                            ):
                                raise petek_engine.MaskError(
                                    "Kaynak dosya üretim sırasında değişmiş; çıktı incelemeye alındı."
                                )
                            self.ledger.complete(key, receipt_sha)
                            newly_rendered.append({"key": key, "sku": sku, "output": str(output),
                                                   "output_sha": receipt_sha})
                            stats["rendered"] += 1
                            stats["current_batch_keys"].append(key)
                            notify(f"ÜRETİLDİ {stats['rendered']}: [{cat}] {uid} / {art.name}")
                        except (petek_engine.MaskError, cv2.error, OSError, ValueError) as exc:
                            self.ledger.quarantine(key, str(exc))
                            stats["rejected"] += 1
                            stats["errors"].append(
                                {"category": cat, "template": uid, "design": art.name, "reason": str(exc)}
                            )
                            notify(f"ATLANDI [{cat}] {uid}/{art.name} — {exc}")

            # 4K is an explicitly selected, independent post-render step.
            # Failures do not invalidate normal 1200x1600 mockups.
            if upscale_4k and not self.cancel.is_set():
                stats["upscale_4k"] = upscale_new_outputs(
                    newly_rendered, state_root=self.root, enabled=True,
                    model=upscale_model, exe=upscale_exe,
                    cancel=self.cancel, notify=notify,
                )
            else:
                stats["upscale_4k"] = {"status": "STOPPED" if self.cancel.is_set() else "DISABLED",
                                       "upscaled": 0, "failed": 0, "reused": 0}
            csv_path, xlsx_path, count = self.export()
            stats.update(
                status=(
                    "STOPPED"
                    if self.cancel.is_set()
                    else ("PARTIAL" if stats["rejected"] else "LOCAL_READY")
                ),
                csv=str(csv_path),
                xlsx=str(xlsx_path),
                total_registry_outputs=count,
            )
            checkpoint_record['status'] = (
                'STOPPED' if stats['status'] == 'STOPPED' else 'COMPLETED')
            checkpoint_record['progress'] = {
                'attempted': stats['attempted'],
                'rendered': stats['rendered'],
                'reused': stats['reused'],
                'duplicates_skipped': stats['duplicates_skipped_in_run'],
            }
            write_checkpoint(self.root, checkpoint_record)
            return stats
        except Exception:
            # Interruption/error never marks a torn job as resumable. The
            # operator must inspect pending rows and recovery first.
            checkpoint_record['status'] = 'INTERRUPTED'
            try:
                write_checkpoint(self.root, checkpoint_record)
            except (OSError, ValueError):
                logging.exception('Unable to mark interrupted checkpoint')
            raise
        finally:
            self.lock_path.unlink(missing_ok=True)

    def audit(self) -> dict[str, Any]:
        """Read-only audit of all rows in the unified 7-category ledger."""
        base = self.output.resolve()
        with self.ledger.connect() as db:
            records = [dict(r) for r in db.execute("SELECT * FROM artifact ORDER BY key")]
        entries = []
        for rec in records:
            path = Path(rec["output"])
            item = {
                "key": rec["key"],
                "sku": rec["sku"],
                "category": rec["category"],
                "status": rec["status"],
                "output": str(path),
                "receipt_sha": rec["output_sha"],
                "audit": "REVIEW_REQUIRED",
                "detail": "",
            }
            if rec["status"] == "USER_REMOVED":
                # Owner explicitly deleted this historical output. Never
                # present the absent file as corruption or a recovery task.
                item["audit"] = "USER_REMOVED"
                item["detail"] = "INTENTIONALLY_DELETED_BY_OPERATOR"
            elif path.is_symlink() or not (path.resolve() == base or base in path.resolve().parents):
                item["detail"] = "UNSAFE_OUTPUT_PATH"
            elif not path.exists():
                item["detail"] = "OUTPUT_MISSING"
            elif not path.is_file():
                item["detail"] = "OUTPUT_NOT_A_FILE"
            else:
                actual = petek_engine.digest(path)
                item["actual_sha"] = actual
                if rec["status"] == "RENDERED" and actual == rec["output_sha"]:
                    item["audit"] = "VERIFIED"
                    item["detail"] = "OK"
                elif rec["status"] == "RENDERED":
                    item["detail"] = "OUTPUT_SHA_MISMATCH"
                elif rec["status"] == "PENDING":
                    item["detail"] = "INTERRUPTED_AFTER_FILE_WRITE"
                else:
                    item["detail"] = "UNRESOLVED_ARTIFACT"
            entries.append(item)
        return {"summary": audit_summary(entries), "entries": entries}

    def export(self) -> tuple[Path, Path, int]:
        """Export SHA-verified CSV and XLSX commercial product lists across all 7 categories."""
        rows = self.ledger.successful()
        fingerprint = hashlib.sha256(
            "|".join(r["key"] + r["output_sha"] for r in rows).encode("utf-8")
        ).hexdigest()[:18]
        csv_path = self.reports / f"ORTAK_7_KATEGORI_LISTE_{fingerprint}.csv"
        xlsx_path = self.reports / f"ORTAK_7_KATEGORI_LISTE_{fingerprint}_LINKLI.xlsx"

        def entry(row: dict[str, Any]) -> list[str]:
            sku = row["sku"]
            cat = row["category"]
            label = CATEGORY_LABELS_TR.get(cat, "Dekoratif Ürün")
            return [
                _escape(x)
                for x in (
                    sku,
                    "DAHILI-" + sku,
                    "M-" + sku,
                    cat,
                    f"{label} - {Path(row['art_name']).stem}",
                    row["art_name"],
                    row["uid"],
                    Path(row["output"]).name,
                    row["output"],
                    "YEREL_HAZIR",
                    row["output_sha"],
                )
            ]

        for row in rows:
            path = Path(row["output"])
            if path.is_symlink() or not path.is_file() or petek_engine.digest(path) != row["output_sha"]:
                raise petek_engine.MaskError(
                    "Ortak ticari liste için çıktı SHA doğrulanamadı: " + row["key"]
                )

        if not csv_path.exists():
            text = StringIO(newline="")
            writer = csv.writer(text)
            writer.writerow(UNIFIED_HEADERS)
            for row in rows:
                writer.writerow(entry(row))
            petek_engine.atomic_new_file(csv_path, ("\ufeff" + text.getvalue()).encode("utf-8"))

        if not xlsx_path.exists():
            wb = xlsx_with_photo_links(UNIFIED_HEADERS, [entry(row) for row in rows],
                                       sheet_name="ORTAK_7_KATEGORI")
            fd, tmp = tempfile.mkstemp(prefix="v4-ortak-", suffix=".xlsx", dir=str(self.reports))
            os.close(fd)
            try:
                wb.save(tmp)
                petek_engine.atomic_new_file(xlsx_path, Path(tmp).read_bytes())
            finally:
                Path(tmp).unlink(missing_ok=True)

        with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.reader(f)
            if next(reader, None) != UNIFIED_HEADERS or list(reader) != [entry(r) for r in rows]:
                raise petek_engine.MaskError("Ortak CSV export beklenen içerikle uyuşmuyor.")

        wb = load_workbook(xlsx_path, read_only=False, data_only=True)
        try:
            if [list(r) for r in wb.active.iter_rows(values_only=True)] != [UNIFIED_HEADERS] + [
                entry(r) for r in rows
            ]:
                raise petek_engine.MaskError("Ortak EXCEL export beklenen içerikle uyuşmuyor.")
            verify_photo_links(wb.active, rows)
        finally:
            wb.close()

        return csv_path, xlsx_path, len(rows)
