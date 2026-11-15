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
3. Source/approved masks are immutable. Old/off and natural render preserve all
   background pixels; opt-in Belirgin can change ONLY photo-verified, wall-connected
   regions to continue the same two sun shadows. Physical slots, curves, cabinet
   sides, room floor and Cam Doğrama frame stay untouched.
4. Fail-closed receipts & atomic create-only files: never overwrites existing
   outputs, verifies SHA-256 on disk before marking `RENDERED`, and validates
   both `.csv` and `.xlsx` exports on read-back.
"""
from __future__ import annotations

import csv
from collections import OrderedDict
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
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
import time
import traceback
import unicodedata
import uuid
from typing import Any

import cv2
import numpy as np
from openpyxl import Workbook, load_workbook
from PIL import Image as PILImage

from PETEK_V3 import engine as petek_engine
from PETEK_V3.cutout_paste import render_with_cutout_paste
from PETEK_V3.petek_finish_v492 import darken_slot_lips, despill_lower_left, draw_fifteen_slots, despill_lower_left_geometry_v493, STRENGTH, FIFTEEN_RECIPE as PETEK_FINISH_RECIPE
from PETEK_V3.final_cleanup_v495 import cleanup_petek_magenta, RECIPE as PETEK_DESPILL_RECIPE
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
from .optical_qa_v47 import reference_quality_gate
from .scene_daylight_vnext import (apply_scene_daylight, daylight_lighting, RECIPE as SCENE_DAYLIGHT_RECIPE, PROFILES as SUNLIGHT_PROFILES)
from PETEK_V3.geometry_qa_v47 import inspect_print_safety
from PETEK_V3.petek_visual_pipeline_vnext import render_petek_visual
from .store_profiles_v47 import StoreProfiles, key_for
from .store_identity_v485 import (store_codes, trendyol_codes, design_number,
                                   filename as store_filename, petek_measurement_codes,
                                   validate_trendyol_codes, excel_row_sort_key)
from .petek_overlay_variations_v1 import (
    MEASUREMENTS as PETEK_OVERLAY_MEASUREMENTS,
    OVERLAY_FREE_FOLDER as PETEK_OVERLAY_FREE_FOLDER,
    FINAL_SIZE as PETEK_OVERLAY_FINAL_SIZE,
    OverlayValidationError,
    process_source as process_petek_overlay_source,
    validate_overlay_folder,
)
from . import four_mockup_v1 as four_mockup_mod
from . import uretim_gecmisi_v1 as history_mod
from .resume_checkpoint_v47 import (read_checkpoint, write_checkpoint,
                                    snapshot_inputs, same_inputs, SCHEMA as RESUME_SCHEMA)
import random
import secrets
from PETEK_V3.excel_links_v42 import xlsx_with_photo_links, verify_photo_links
from .performance_v501 import machine_key

EXT = {".jpg", ".jpeg", ".png", ".webp"}
V4_RECIPE = "v4-6-chroma-solid-20261026"
FIXED_RENDER_WORKERS = 2


def _petek_overlay_batch_folder_name(*, started_at: float, clean_count: int,
                                     operation_id: str) -> str:
    """Return a readable, filesystem-safe folder name for one PETEK run.

    The timestamp and planned clean-output count make the operator-facing
    ``Overlaysızlar`` tree self-describing.  The short operation suffix keeps
    two runs started in the same second from sharing a folder while preserving
    the requested ``tarih-saat-adet`` shape.
    """
    stamp = time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime(started_at))
    count = max(0, int(clean_count))
    suffix = str(operation_id).rsplit("-", 1)[-1][:8] or "RUN"
    return f"{stamp}_{count}_{suffix}"


def production_render_workers() -> tuple[int, str]:
    """Authoritative production setting; diagnostics cannot override it."""
    return FIXED_RENDER_WORKERS, "FIXED_SAFE_PROFILE_2"


def _production_code_fingerprint() -> dict[str, Any]:
    """Fingerprint active render files once when an operation report is written."""
    paths = (
        Path(__file__),
        Path(__file__).with_name("finish_material_v46.py"),
        Path(__file__).parents[1] / "PETEK_V3" / "engine.py",
        Path(__file__).parents[1] / "PETEK_V3" / "petek_visual_pipeline_vnext.py",
        Path(__file__).parents[1] / "PETEK_V3" / "petek_finish_v492.py",
    )
    files: dict[str, str] = {}
    aggregate = hashlib.sha256()
    for path in paths:
        try:
            digest = hashlib.sha256()
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
            value = digest.hexdigest()
        except OSError:
            value = "UNAVAILABLE"
        files[path.name] = value
        aggregate.update(path.name.encode("utf-8"))
        aggregate.update(value.encode("ascii"))
    return {"aggregate_sha256": aggregate.hexdigest(), "files": files}


def _init_render_worker() -> None:
    """Prevent N worker × N OpenCV-native-thread oversubscription.

    Default stays the documented safe profile (1 native thread per worker).
    ``V4_CV_THREADS`` may raise the per-worker OpenCV budget for benchmarks or
    small runs; synthetic 2-worker renders measured ~14% faster at 2-4 threads
    on a 16-core machine, at the cost the original oversubscription fix warned
    about — hence opt-in, never the default.
    """
    cv2.setUseOptimized(True)
    try:
        budget = int(os.environ.get("V4_CV_THREADS", "1"))
    except (TypeError, ValueError):
        budget = 1
    cv2.setNumThreads(max(1, min(32, budget)))


def recommended_render_workers(root: Path) -> tuple[int, str]:
    """Return a conservative machine profile without touching live data.

    A prior measured profile wins.  The yedek intentionally favors stable
    throughput over saturating all logical CPUs; image stages already use
    native vectorized code and oversubscription made six workers slower.
    """
    profile = Path(root) / "render_worker_profile.json"
    try:
        payload = json.loads(profile.read_text(encoding="utf-8"))
        value = int(payload.get("recommended_workers", 0))
        if (1 <= value <= 8 and payload.get("machine_key") == machine_key()
                and payload.get("pixel_equivalence_verified") is True):
            return value, "persisted_benchmark_profile"
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        pass
    logical = os.cpu_count() or 4
    value = 2 if logical >= 8 else 1
    return value, "conservative_cpu_fallback"

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


def _store_id_from_output(output: Path, output_root: Path) -> str:
    """Return the business store segment for central and isolated outputs.

    Isolated/external runs are deliberately nested as
    ``HARICI/<operation>/<store>/<category>/...``.  ``HARICI`` is a storage
    namespace, never a marketplace store id.
    """
    parts = Path(output).resolve().relative_to(Path(output_root).resolve()).parts
    if parts and parts[0] == "HARICI":
        if len(parts) < 3:
            raise ValueError("HARICI çıktı yolu mağaza segmenti içermiyor")
        return parts[2]
    if not parts:
        raise ValueError("Çıktı yolu mağaza segmenti içermiyor")
    return parts[0]


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


def assert_unique_print_names(designs: list[Path]) -> None:
    """Collision guard on ANY design folder, regardless of file extension.

    Same photo base in nested folders is ambiguous to the print operator and
    may produce duplicate SKU/Excel identity, so refuse before any rendering.
    """
    seen={}
    for file in designs:
        name=unicodedata.normalize('NFC',Path(file).stem).casefold()
        if name in seen:
            raise ValueError('HAM_BASKI_TASARIM_NUMARASI_CAKISMASI: '+
                             str(seen[name])+' / '+str(file))
        seen[name]=file


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
    sunlight_profile: str = "off",
    petek_realism_profile: str = "dogal",
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
    # Keep the historical natural PETEK receipt identity reusable.  The
    # profile becomes part of the key only for the alternate visual recipe,
    # which prevents a Belirgin render from reusing a Dogal receipt without
    # forcing duplicate filenames for every existing natural output.
    if str(item.get("category")) == "06_Petek_Kapama" and str(petek_realism_profile) != "dogal":
        payload["petek_realism_profile"] = str(petek_realism_profile)
    if sunlight_profile not in SUNLIGHT_PROFILES:
        raise petek_engine.MaskError("Gunes profili gecersiz")
    if sunlight_profile != "off":
        payload["sunlight_profile"] = sunlight_profile
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


def _render_job_picture(
    *,
    engine_type: str,
    source_path: Path,
    render_art: Path,
    artwork_raster: np.ndarray,
    source_scene: np.ndarray,
    mask: np.ndarray,
    item: dict[str, Any],
    placement: str,
    lighting: str,
    active_corner_radius: float,
    glass_effect: str,
    sunlight_profile: str,
    petek_slot_mode: str,
    petek_pink_cleanup: bool,
    petek_realism_profile: str,
) -> tuple[np.ndarray, dict[str, Any], str]:
    """Render one immutable job payload without touching Tk/ledger state.

    This function is intentionally side-effect free apart from native image
    computation.  It is the boundary used by the optional bounded worker pool;
    output creation and receipt commits remain in the coordinator thread.
    """
    if engine_type == "PETEK_V3_CUTOUT":
        picture, qa = render_petek_visual(
            source_scene.copy(), artwork_raster, item["quad"], mask.copy(),
            item["physical_aspect"], placement=placement,
            lighting=("strong" if lighting != "off" and petek_realism_profile == "belirgin" else lighting)
                if sunlight_profile == "off" else
                ("strong" if sunlight_profile == "belirgin" and lighting != "off"
                 else "natural" if lighting != "off" else "off"),
            material_effect=(lighting != "off" and glass_effect == "on"),
            slot_mode=petek_slot_mode, pink_cleanup=petek_pink_cleanup,
            render_fn=render_with_cutout_paste,
            material_fn=apply_material_finish,
            slot_fn=draw_fifteen_slots,
            cleanup_fn=cleanup_petek_magenta,
            safety_fn=inspect_print_safety,
            despill_fn=despill_lower_left_geometry_v493,
        )
        return petek_engine.canvas_3x4(picture), qa, "petek"

    picture, qa = _render_legacy_six_cover(
        source_path,
        render_art,
        item["quad"],
        mask.copy(),
        item["physical_aspect"],
        marketplace=True,
        placement=placement,
        lighting=lighting,
        category=item["category"],
        corner_radius=active_corner_radius,
        glass_effect=glass_effect,
        sunlight_profile=sunlight_profile,
        scene_override=source_scene.copy(),
        art_override=artwork_raster,
    )
    return picture, qa, "legacy"


def _resolve_petek_production_mask(scene: np.ndarray, approved_mask: np.ndarray, quad):
    """Return the immutable approved mask or a stricter render-only copy.

    A few historical PETEK approvals predate the independent photo/vent guard:
    their saved mask is still byte-valid, but it leaves photographed grille
    slots printable.  Production must not paint those slots, and it must not
    rewrite the approved mask or its four corners.  In that specific conflict
    case the contract derives an in-memory intersection mask from the source
    photo.  The returned mask is never persisted; callers must use its SHA as
    the render receipt identity so a stricter render cannot collide with an
    older output made with the approved raster.
    """
    from PETEK_V3.petek_render_contract_v1 import (
        ensure_source_vent_mask_consensus,
        temporary_photo_protected_preview_mask,
    )

    try:
        proof = ensure_source_vent_mask_consensus(scene, approved_mask, quad)
        return approved_mask, approved_mask_sha256(approved_mask), proof
    except petek_engine.MaskError as exc:
        if not str(exc).startswith("PETEK_SOURCE_MASK_VENT_CONFLICT_REVIEW"):
            raise
        render_mask, proof = temporary_photo_protected_preview_mask(
            scene, approved_mask, quad
        )
        proof = dict(proof)
        proof.update({
            "status": "TEMPORARY_SOURCE_EVIDENCE",
            "approved_mask_sha256": approved_mask_sha256(approved_mask),
            "render_mask_sha256": approved_mask_sha256(render_mask),
            "not_saved": True,
            "not_approved": True,
        })
        return render_mask, proof["render_mask_sha256"], proof


def approved_mask_sha256(mask: np.ndarray) -> str:
    """Hash a mask without importing the PETEK registry or touching disk."""
    return petek_engine.mask_hash(mask)


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
    sunlight_profile: str = "off",
    scene_override: np.ndarray | None = None,
    art_override: np.ndarray | None = None,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Render categories 01..05 with full-bleed cover projection, natural lighting, and strict background preservation."""
    from PETEK_V3 import realism
    # Batch callers pass the immutable, SHA-validated scene prepared once per
    # approved template.  The default keeps the public helper backward
    # compatible for previews/tests.
    scene = scene_override if scene_override is not None else petek_engine.read_bgr(source_path)
    design = art_override if art_override is not None else petek_engine.read_bgr(art_path)
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
    effective_light = daylight_lighting(lighting, sunlight_profile)
    lit = realism.apply(neutral_scene, projected, mask, effective_light)
    if category in GLASS | DAYLIGHT and glass_effect == "on" and effective_light != "off":
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
    sunlight_qa = {'status': 'OFF', 'wall_shadow_pixels': 0, 'profile': sunlight_profile}
    if sunlight_profile != 'off' and lighting != 'off':
        out, sunlight_qa = apply_scene_daylight(scene, out, mask, q, category,
                                               profile=sunlight_profile)
    # Any outside-mask difference is allowed ONLY on the verified wall shadow.
    protected_changed = np.any(out != scene, axis=2) & (mask == 0)
    if np.any(protected_changed):
        from PETEK_V3.wall_window_shadows_vnext import wall_region, apply_wall_window_shadows
        wall = wall_region(scene, mask, q)
        reference, _ = apply_wall_window_shadows(scene, scene, mask, q, lighting='strong')
        if (np.any(protected_changed & ~wall) or
                not np.array_equal(out[protected_changed], reference[protected_changed])):
            raise petek_engine.MaskError("Orijinal arka plan / çerçeve koruma ihlali.")
    reference_qa = reference_quality_gate(scene, out, mask, category)
    if reference_qa["status"] == "FAIL":
        raise petek_engine.MaskError(
            "REFERANS_KALITE_MAGENTA_SIZINTISI: "
            f"{reference_qa['new_magenta_outside_pixels']} px"
        )
    qa = {
        "chroma_solid_coverage": chroma_pixels is not None,
        "printable_fraction": round(fraction, 5),
        "preserved_pixels": int(np.count_nonzero(mask == 0)),
        "source_pixels_unchanged": not bool(np.any(protected_changed)),
        "source_files_immutable": True,
        "sunlight_qa": sunlight_qa,
        "zero_blur_padding": placement == "cover",
        "lighting": effective_light,
        "corner_radius": corner_radius if category in GLASS else 0.0,
        "optical_finish": category in (GLASS | DAYLIGHT) and glass_effect == "on" and lighting != "off",
        "optical_recipe": MATERIAL_RECIPE if category in (GLASS | DAYLIGHT) and glass_effect == "on" and lighting != "off" else "legacy",
        "glass_effect": glass_effect if category in GLASS else "not_applicable",
        "reference_quality_qa": reference_qa,
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
            # Overlay derivatives are immutable children of a clean artifact.
            # Additive columns keep existing V4 receipts readable while making
            # cloud/Excel stages able to distinguish the clean source.
            cols = {row[1] for row in con.execute("PRAGMA table_info(artifact)")}
            for name, definition in (
                ("artifact_kind", "TEXT NOT NULL DEFAULT 'clean'"),
                ("source_key", "TEXT NOT NULL DEFAULT ''"),
                ("overlay_cm", "TEXT NOT NULL DEFAULT ''"),
                ("overlay_manifest", "TEXT NOT NULL DEFAULT ''"),
            ):
                if name not in cols:
                    con.execute(f"ALTER TABLE artifact ADD COLUMN {name} {definition}")
            con.execute("CREATE INDEX IF NOT EXISTS artifact_status_idx ON artifact(status)")
            con.execute("CREATE INDEX IF NOT EXISTS artifact_cat_idx ON artifact(category)")
            con.execute("CREATE INDEX IF NOT EXISTS artifact_overlay_idx ON artifact(artifact_kind, overlay_cm)")

    def connect(self):
        con = sqlite3.connect(self.file, timeout=30)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA busy_timeout=30000")
        return con

    def reserve(self, fields: dict[str, Any]) -> dict[str, Any]:
        fields = dict(fields)
        fields.setdefault("artifact_kind", "clean")
        fields.setdefault("source_key", "")
        fields.setdefault("overlay_cm", "")
        fields.setdefault("overlay_manifest", "")
        with self.connect() as con:
            con.execute(
                """INSERT OR IGNORE INTO artifact
                (key, sku, category, art_sha, template_sha, mask_sha, art_name, uid, output, status,
                 artifact_kind, source_key, overlay_cm, overlay_manifest)
                VALUES (:key, :sku, :category, :art_sha, :template_sha, :mask_sha, :art_name, :uid, :output, 'PENDING',
                        :artifact_kind, :source_key, :overlay_cm, :overlay_manifest)""",
                fields,
            )
            found = dict(con.execute("SELECT * FROM artifact WHERE key=?", (fields["key"],)).fetchone())
        for k in ("key", "sku", "category", "art_sha", "template_sha", "mask_sha", "uid", "output"):
            if found[k] != fields[k]:
                raise petek_engine.MaskError("Kayıt kimliği eski işlemle çakışıyor: " + k)
        return found

    def retry_unwritten(self, key: str, output_root: Path) -> dict[str, Any]:
        """Retry only a failed attempt with no file and no completion receipt.

        Called under the batch lock. Keep the previous error in an append-only
        audit table; never reset completed, deleted or partially written work.
        """
        with self.connect() as con:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute("SELECT * FROM artifact WHERE key=?", (key,)).fetchone()
            if row is None:
                raise petek_engine.MaskError("URETIM_KAYDI_TUTARSIZ")
            record = dict(row)
            path = Path(record['output'])
            base = Path(output_root).resolve()
            safe = (base in path.resolve().parents and
                    not any(p.is_symlink() for p in (path, *path.parents)))
            if (record['status'] == 'REVIEW_REQUIRED' and not record['output_sha']
                    and safe and not path.exists()):
                con.execute("""CREATE TABLE IF NOT EXISTS retry_history (
                    id INTEGER PRIMARY KEY, key TEXT NOT NULL,
                    previous_message TEXT NOT NULL,
                    retried_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
                con.execute("INSERT INTO retry_history(key,previous_message) VALUES (?,?)",
                            (key, record['message']))
                con.execute("""UPDATE artifact SET status='PENDING',
                    updated=CURRENT_TIMESTAMP WHERE key=? AND status='REVIEW_REQUIRED'""", (key,))
                record['status'] = 'PENDING'
            return record

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
            rows = [
                dict(row)
                for row in con.execute(
                    "SELECT * FROM artifact WHERE status='RENDERED' ORDER BY category, sku, uid"
                )
            ]
        return sorted(rows, key=excel_row_sort_key)


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
        # Derived geometry only; source photos, masks and approved corners are
        # never stored here.  The key includes their SHA values and the recipe.
        self.geometry_cache = self.root / "petek_geometry_cache"
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

    def template_health(self, item: dict[str, Any], *, petek_slot_mode: str = "off",
                        petek_pink_cleanup: bool = False) -> tuple[bool, str]:
        """Üretimden önce, tasarımdan bağımsız şablon korumalarını üretimle aynı kodla dener.

        Hiçbir koruma gevşetilmez; yalnızca hangi şablonun reddedileceği önceden bilinir.
        """
        if item.get("engine_type") != "PETEK_V3_CUTOUT":
            return True, ""
        cache = self.__dict__.setdefault("_health_cache", {})
        key = (item["uid"], item.get("source_sha"), petek_slot_mode, bool(petek_pink_cleanup))
        if key in cache:
            return cache[key]
        try:
            profile, mask = self.petek_registry.get_current(
                item["uid"], require_approved=True, source_override=Path(item["source"]))
            scene = petek_engine.read_bgr(Path(profile["source"]))
            mask, _sha, _guard = _resolve_petek_production_mask(scene, mask, item["quad"])
            if petek_pink_cleanup:
                from PETEK_V3.petek_source_marker_fringe_vnext import marker_fringe_candidates
                marker_fringe_candidates(scene, mask, item["quad"])
            if petek_slot_mode != "off":
                from PETEK_V3.petek_slot_geometry_vnext import measure_real_vents
                measure_real_vents(scene, mask, item["quad"], cache_root=self.geometry_cache)
            result = (True, "")
        except (petek_engine.MaskError, cv2.error, OSError, ValueError, KeyError, TypeError) as exc:
            result = (False, str(exc).split(":", 1)[0][:80] or type(exc).__name__)
        cache[key] = result
        return result

    def inspect_recovery(self) -> dict[str, Any]:
        return inspect_interrupted_state(self.ledger.file, self.lock_path, self.output)

    def last_batch_checkpoint(self) -> dict | None:
        """Read only, local APPDATA; historical images/DB are untouched."""
        return read_checkpoint(self.root)

    def resume_last_stopped(self, *, notify=None, progress=None) -> dict[str, Any]:
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
        # ``petek_overlay_batch_folder`` is recorded for checkpoint equality
        # only; run() derives it from the checkpoint and does not accept it.
        config = {k: v for k, v in checkpoint['config'].items()
                  if k != 'petek_overlay_batch_folder'}
        self.cancel.clear()
        self.pause.clear()
        return self.run(**config, notify=notify, progress=progress, _resume_expected=checkpoint)

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
        progress=None,
        output_ready=None,
        max_jobs: int | None = None,
        placement: str = "cover",
        lighting: str = "natural",
        corner_radius: float | None = None,
        glass_effect: str = "on",
        upscale_4k: bool = False,
        upscale_model: str = "photo",
        upscale_exe: Path | str | None = None,
        petek_slot_mode: str = "off",
        petek_pink_cleanup: bool = False,
        petek_realism_profile: str = 'dogal',
        petek_overlay_enabled: bool = False,
        petek_overlay_root: Path | str | None = None,
        overlay_enabled: bool | None = None,
        four_mockup: dict | None = None,
        sunlight_profile: str = "off",
        external_designs: bool = False,
        render_mode: str = "balanced_one_per_design",
        skipped_design_paths: set[str] | list[str] | None = None,
        _resume_expected: dict | None = None,
    ) -> dict[str, Any]:
        operation_started = time.perf_counter()
        external_notify = notify or (lambda msg: None)
        operation_id = "OP-{}-{}".format(
            time.strftime("%Y%m%d-%H%M%S"), uuid.uuid4().hex[:8].upper())
        technical_events: list[dict[str, Any]] = []

        def notify(message):
            """Keep verbose diagnostics in the operation journal, not the result card."""
            technical_events.append({
                "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "message": str(message),
            })
            external_notify(message)

        operation_log_path = self.reports / f"ISLEM_GUNLUGU_{operation_id}.json"
        operation_report_path = self.reports / f"ISLEM_RAPORU_{operation_id}.json"
        original_engine_state = None
        external_mode = False
        external_state_dir = None
        # ``progress`` is deliberately separate from the human-readable log.
        # The UI can therefore render a stable progress model without parsing
        # translated/log-detail strings.  A callback failure must never stop a
        # production run.
        progress = progress or (lambda payload: None)
        output_ready = output_ready or (lambda row: None)
        if corner_radius is not None and not 0 <= float(corner_radius) <= .04:
            raise petek_engine.MaskError("Köşe yuvarlatma %0-%4 arasında olmalı.")
        if petek_slot_mode not in STRENGTH:
            raise petek_engine.MaskError("PETEK izgara modu gecersiz.")
        if not isinstance(petek_pink_cleanup, bool):
            raise petek_engine.MaskError("PETEK kenar temizleme ayari True/False olmali.")
        if sunlight_profile not in SUNLIGHT_PROFILES:
            raise petek_engine.MaskError('7 kategori gunes profili gecersiz.')
        if petek_realism_profile not in ('dogal', 'belirgin'):
            raise petek_engine.MaskError('PETEK dogallik profili gecersiz.')
        if glass_effect not in ("on", "off"):
            raise petek_engine.MaskError("Cam efekti Açık veya Kapalı olmalı.")
        if placement not in petek_engine.PLACEMENT_MODES:
            raise petek_engine.MaskError("Yerleşim modu geçersiz: cover veya contain.")
        if not re.fullmatch(r"[A-Za-z0-9_-]{2,36}", str(group)):
            raise petek_engine.MaskError("Mağaza grubu yalnızca harf, sayı, alt çizgi, tire içerebilir.")
        if max_jobs is not None and int(max_jobs) < 1:
            raise petek_engine.MaskError("İş limiti pozitif olmalı veya sınırsız bırakılmalı.")
        if render_mode not in ("balanced_one_per_design", "all_templates_per_design"):
            raise petek_engine.MaskError("Geçersiz üretim modeli.")
        if overlay_enabled is not None:
            petek_overlay_enabled = bool(overlay_enabled)
        four_active = four_mockup is not None
        if four_active:
            if petek_overlay_enabled:
                raise petek_engine.MaskError(
                    "DORT_MOCKUP_MOD_CAKISMASI: 4 Mockup modu ile 1 Mockup 4 Overlay modu aynı anda kullanılamaz.")
            if not selected_stores:
                raise petek_engine.MaskError("DORT_MOCKUP_MAGAZA_GEREKLI: En az bir mağaza seçilmeli.")
            render_mode = "all_templates_per_design"

        designs = Path(design_folder).resolve(strict=True)
        if not designs.is_dir():
            raise petek_engine.MaskError("Tasarım klasörü bulunamadı.")
        if designs == self.root or self.root in designs.parents or designs in self.root.parents:
            raise petek_engine.MaskError("Tasarım klasörü çıktı/kayıt dizini içinde olamaz.")
        # The central HAM pool is the only place where numbered print-design
        # identity and the persistent production ledger apply. A user-picked
        # folder outside that pool is an isolated, create-only test source.
        ham_root = ((self.runtime_root / "HAM BASKI TASARIMLARI").resolve(strict=False)
                    if self.runtime_root else None)
        external_mode = bool(external_designs or
                             (ham_root is not None and ham_root.exists() and
                              designs != ham_root and ham_root not in designs.parents))
        if external_mode:
            # Keep the operator-visible reports in the normal reports folder,
            # but move ledger/output/lock state to an operation-specific area.
            # This guarantees that external tests cannot alter central design
            # receipts, counters, or resumable checkpoints.
            external_state_dir = Path(tempfile.mkdtemp(prefix=f"harici_{operation_id}_"))
            original_engine_state = (self.ledger, self.output, self.lock_path)
            self.ledger = UnifiedV4Ledger(external_state_dir)
            # The central ledger object is temporarily replaced only for the
            # isolated run; its file is not part of the central state root.
            self.output = original_engine_state[1] / "HARICI" / operation_id
            self.output.mkdir(parents=True, exist_ok=True)
            self.lock_path = external_state_dir / "HARICI_URETIM.lock"
            notify(f"HARİCİ TASARIM MODU: geçici işlem kimliği {operation_id}; merkezi kayıtlar korunuyor.")

        queue_started = time.perf_counter()
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
        stale_store_items: list[dict[str, Any]] = []
        if selected_stores:
            store_plan = StoreProfiles(self.root).plan_resilient(
                selected_stores, templates, selected_uids=selected_uids)
            production_plan = store_plan['groups']
            stale_store_items = store_plan['stale']
            if stale_store_items and _resume_expected is not None:
                # A stopped run is an immutable snapshot.  Continuing after a
                # membership drift could mix old and new store assignments;
                # require a fresh operator-reviewed run instead.
                raise petek_engine.MaskError(
                    'Kaldığı yerden devam engellendi: mağaza atamaları veya '
                    'onaylı şablon SHA değerleri değişmiş. Önce inceleyin.')
            if not production_plan:
                details = '; '.join(f"{item['store']}: {item['key']}"
                                    for item in stale_store_items[:8])
                raise petek_engine.MaskError(
                    'GÜVENLİ DURDURMA — seçili mağazalardaki tüm şablon atamaları '
                    'onay/SHA değişikliği nedeniyle inceleme bekliyor: ' + details)
        else:
            production_plan = [(group, templates)]
        four_slots: dict[str, dict[str, str]] = {}
        four_design_slots: dict[str, dict[str, dict[str, str]]] = {}
        four_overlays: dict[str, dict] = {}
        four_slot_lookup: dict[tuple[str, str, str], str] = {}
        if four_active:
            four_notes: list[str] = []
            # The complete assigned/approved PETEK pool is retained.  A
            # per-design planner below chooses four UIDs for each design;
            # filtering the store pool here would recreate the old bug.
            four_slots, four_problems = four_mockup_mod.plan_slots(
                production_plan, (four_mockup or {}).get("slots"), notes=four_notes,
                health=lambda tpl: self.template_health(
                    tpl, petek_slot_mode=petek_slot_mode, petek_pink_cleanup=petek_pink_cleanup))
            for line in four_notes:
                notify(line)
            if four_problems:
                raise petek_engine.MaskError(
                    "DORT_MOCKUP_SABLON_EKSIK: " + " | ".join(four_problems)
                    + " — şablon tekrarı veya başka mağazanın şablonu kullanılmaz.")
            four_overlays = four_mockup_mod.normalize_overlays((four_mockup or {}).get("overlays"))
        seed = int(random_seed) if random_seed is not None else secrets.randbits(64)
        rng = random.Random(seed)
        designs_in_run = list(iter_designs(designs))
        if four_active:
            design_keys = [str(Path(art).resolve()).casefold() for art in designs_in_run]
            saved_plan = (((_resume_expected or {}).get("config") or {}).get("four_mockup") or {}).get(
                "per_design_slots")
            if saved_plan:
                # A stopped run is an immutable selection snapshot.  Reuse it
                # verbatim so completed finals retain their original keys.
                four_design_slots = {
                    str(store): {str(key): {str(cm): str(uid) for cm, uid in mapping.items()}
                                 for key, mapping in by_design.items()}
                    for store, by_design in saved_plan.items()
                }
                four_problems = []
            else:
                four_design_slots, four_problems = four_mockup_mod.plan_slots_for_designs(
                    production_plan, design_keys, (four_mockup or {}).get("slots"), notes=four_notes,
                    health=lambda tpl: self.template_health(
                        tpl, petek_slot_mode=petek_slot_mode, petek_pink_cleanup=petek_pink_cleanup))
            for line in four_notes:
                notify(line)
            if four_problems:
                raise petek_engine.MaskError(
                    "DORT_MOCKUP_SABLON_EKSIK: " + " | ".join(four_problems)
                    + " — şablon tekrarı veya başka mağazanın şablonu kullanılmaz.")
            # Keep the legacy top-level slots field as the first design's
            # selection for UI/checkpoint compatibility.
            for store, by_design in four_design_slots.items():
                if by_design:
                    four_slots[store] = next(iter(by_design.values()))
                    for design_key, mapping in by_design.items():
                        for cm, uid in mapping.items():
                            four_slot_lookup[(store, uid, design_key)] = cm
        rng.shuffle(production_plan)
        # Validate print/design names before any preflight exclusion.  A file
        # in Kullanildi/Kullanılanlar is still part of the selected source
        # tree, and must participate in collision detection even when normal
        # production would skip it.  Otherwise an active file could silently
        # share a print name with an archived/used file.
        assert_unique_print_names(designs_in_run)
        # Preflight can identify already-used/unregistered or bad-SHA files.
        # Exclude exact paths for this run without mutating the source pool.
        skipped_designs = []
        if skipped_design_paths:
            blocked = {str(Path(item).resolve()).casefold() for item in skipped_design_paths}
            kept = []
            for candidate in designs_in_run:
                if str(candidate.resolve()).casefold() in blocked:
                    skipped_designs.append(str(candidate))
                else:
                    kept.append(candidate)
            designs_in_run = kept
            for item in skipped_designs:
                notify(f"ATLANDI TASARIM (ön kontrolde sorunlu/kullanılmış): {Path(item).name}")
        # Keep the post-filter assertion as a defensive invariant for callers
        # that provide an explicit skipped_design_paths set.  The authoritative
        # check above intentionally covers the complete discovered tree.
        assert_unique_print_names(designs_in_run)
        if not designs_in_run:
            raise petek_engine.MaskError("Tasarım klasöründe kullanılabilir görsel yok.")
        petek_overlay_root_path = Path(
            petek_overlay_root
            if petek_overlay_root is not None
            else ((self.runtime_root / "Overlay_Giydirme") if self.runtime_root
                  else (Path(__file__).resolve().parents[3] / "Overlay_Giydirme"))
        ).resolve()
        overlay_active = bool(petek_overlay_enabled and any(
            str(item.get("category")) == "06_Petek_Kapama" for item in templates
        ))
        overlay_validation: dict[str, Any] | None = None
        if overlay_active:
            # Preflight before the first render: a missing/invalid prepared
            # pool is a visible overlay failure, never a silent clean upload.
            try:
                overlay_validation = validate_overlay_folder(petek_overlay_root_path)
            except OverlayValidationError as exc:
                raise petek_engine.MaskError("PETEK_OVERLAY_HAZIR_DEGIL: " + str(exc)) from exc
            if not overlay_validation.get("ready"):
                raise petek_engine.MaskError(
                    "PETEK_OVERLAY_HAZIR_DEGIL: " + "; ".join(overlay_validation.get("errors", [])[:8])
                )
        rng.shuffle(designs_in_run)
        for _, store_templates in production_plan:
            rng.shuffle(store_templates)

        if four_active:
            # Four PETEK renders per store/design; the selected UIDs vary by
            # design and are recorded in ``four_design_slots``.
            planned_jobs = 4 * len(production_plan) * len(designs_in_run)
        elif render_mode == "balanced_one_per_design":
            # One output per design; approved templates are reused in a
            # deterministic round-robin so the template pool is balanced.
            planned_jobs = len(production_plan) * len(designs_in_run)
        else:
            planned_jobs = sum(len(store_templates) for _, store_templates in production_plan) * len(designs_in_run)

        # Clean PETEK renders are kept under one production-specific folder so
        # repeated runs do not create a flat, ambiguous ``Overlaysızlar``
        # directory.  A resumed run reuses the folder recorded in its
        # checkpoint; old checkpoints without this field retain their legacy
        # flat layout and remain resumable.
        petek_overlay_batch_folder: str | None = None
        if overlay_active or four_active:
            if four_active:
                petek_clean_count = 4 * len(production_plan) * len(designs_in_run)
            elif render_mode == "balanced_one_per_design":
                petek_clean_count = sum(
                    1 for _, store_templates in production_plan
                    if any(item.get("category") == "06_Petek_Kapama" for item in store_templates)
                ) * len(designs_in_run)
            else:
                petek_clean_count = sum(
                    sum(1 for item in store_templates if item.get("category") == "06_Petek_Kapama")
                    for _, store_templates in production_plan
                ) * len(designs_in_run)
            if max_jobs is not None:
                petek_clean_count = min(petek_clean_count, int(max_jobs))
            expected_folder = ((_resume_expected or {}).get("config") or {}).get(
                "petek_overlay_batch_folder"
            )
            if four_active:
                # Deterministik klasör: yeniden çalıştırma/devam aynı kayıt
                # kimliğine denk gelir; zaman damgalı klasör kayıt çakışması yaratırdı.
                petek_overlay_batch_folder = "4_Mockup"
            elif expected_folder:
                petek_overlay_batch_folder = str(expected_folder)
            elif _resume_expected is None:
                petek_overlay_batch_folder = _petek_overlay_batch_folder_name(
                    started_at=time.time(), clean_count=petek_clean_count,
                    operation_id=operation_id,
                )
        progress_total = min(planned_jobs, int(max_jobs)) if max_jobs is not None else planned_jobs
        progress_started = time.monotonic()
        progress_completed = 0
        # Per-operation timing is deliberately kept in the receipt so a real
        # 54-job run can be compared before/after an optimization.  The
        # counters are additive and never influence rendering decisions.
        stage_timings = {
            "queue_prepare_seconds": max(0.0, time.perf_counter() - queue_started),
            "snapshot_seconds": 0.0,
            "lock_seconds": 0.0,
            "first_output_latency_seconds": None,
            "source_read_seconds": 0.0,
            "image_processing_seconds": 0.0,
            "save_seconds": 0.0,
            "ledger_seconds": 0.0,
            "export_seconds": 0.0,
            "total_wall_seconds": 0.0,
        }
        stage_counts = {"source_cache_hits": 0, "template_cache_hits": 0}
        # Defined before the first callback so the closure always observes the
        # live counters (the initial snapshot is emitted before rendering).
        stats: dict[str, Any] = {}

        def emit_progress(category="", operation="", *, outcome=None, force=False):
            """Publish a live, UI-safe snapshot after each real job outcome."""
            nonlocal progress_completed
            if outcome is not None:
                progress_completed = min(progress_total, progress_completed + 1)
            elapsed = max(0.0, time.monotonic() - progress_started)
            eta = None
            if progress_completed and progress_completed < progress_total:
                eta = elapsed * (progress_total - progress_completed) / progress_completed
            payload = {
                "completed": progress_completed,
                "total": progress_total,
                "index": progress_completed,
                "stage": "hazırlık" if (outcome is None and progress_completed == 0) else "üretim",
                "category": str(category or ""),
                "operation": str(operation or ""),
                "outcome": str(outcome or "running"),
                "elapsed_seconds": round(elapsed, 1),
                "eta_seconds": round(eta, 1) if eta is not None else None,
                "successful": int(stats.get("rendered", 0)),
                "failed": int(stats.get("rejected", 0)),
                "skipped": int(stats.get("reused", 0)) + int(stats.get("duplicates_skipped_in_run", 0)) + int(stats.get("user_removed", 0)),
                "status": str(stats.get("status", "RUNNING")),
                "report_dir": str(self.reports),
            }
            try:
                progress(payload)
            except Exception:
                logging.getLogger(__name__).debug("Progress callback failed", exc_info=True)

        # A first snapshot makes the compact UI switch to the live state before
        # the first expensive image decode/render starts.
        emit_progress(operation="Kuyruk hazırlanıyor", force=True)

        # Immutable checkpoint identity. We reread every chosen input SHA on
        # restart; a changed design or approved source cannot enter an old run.
        snapshot_started = time.perf_counter()
        inventory = snapshot_inputs(designs_in_run, production_plan)
        stage_timings["snapshot_seconds"] = time.perf_counter() - snapshot_started
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
            'sunlight_profile': sunlight_profile,
            'corner_radius': corner_radius,
            'glass_effect': glass_effect,
            'upscale_4k': bool(upscale_4k),
            'upscale_model': upscale_model,
            'petek_slot_mode': petek_slot_mode,
            'petek_pink_cleanup': petek_pink_cleanup,
            'upscale_exe': str(upscale_exe) if upscale_exe is not None else None,
            'random_seed': seed,
            'external_designs': external_mode,
            'render_mode': render_mode,
            'petek_overlay_enabled': bool(overlay_active),
            'petek_overlay_root': str(petek_overlay_root_path) if overlay_active else None,
        }
        if (overlay_active or four_active) and petek_overlay_batch_folder:
            config['petek_overlay_batch_folder'] = petek_overlay_batch_folder
        if four_active:
            config['four_mockup'] = {
                'slots': four_slots,
                'per_design_slots': four_design_slots,
                'overlays': four_overlays,
            }
        if petek_realism_profile != 'dogal':
            config['petek_realism_profile'] = petek_realism_profile
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
            'operation_id': operation_id,
            'status': 'RUNNING',
            'state_root': str(self.root),
            'runtime_root': str(self.runtime_root) if self.runtime_root else None,
            'render_recipe': [V4_RECIPE, MATERIAL_RECIPE, petek_engine.RECIPE],
            'config': config,
            'inventory': inventory,
            'progress': {'attempted': 0, 'rendered': 0, 'reused': 0},
            'external_mode': external_mode,
        }

        for t in templates:
            # A source may disappear between discovery and production. Its
            # individual attempt must be marked for review, not crash the
            # whole batch before the persistent lock is obtained.
            src = Path(t["source"]).resolve(strict=False)
            if src == designs or designs in src.parents or src in designs.parents:
                raise petek_engine.MaskError("Tasarım klasörü kaynak şablon klasörüyle aynı olamaz.")

        lock_started = time.perf_counter()
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
        stage_timings["lock_seconds"] = time.perf_counter() - lock_started

        stats.update({
            "operation_id": operation_id,
            "operation_log": str(operation_log_path),
            "operation_report": str(operation_report_path),
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
            "preflight_skipped_designs": skipped_designs,
            "per_category_templates": discovery_audit["per_category_counts"],
            "attempted": 0,
            "rendered": 0,
            "reused": 0,
            "current_batch_keys": [],  # Only these SHA-verified products may auto-link.
            "current_batch_outputs": [],
            "rejected": 0,
            "errors": [],
            "local_only": True,
            "marketplace_published": False,
            "external_mode": external_mode,
            "external_output_root": str(self.output) if external_mode else None,
            "stage_timings": stage_timings,
            "stage_counts": stage_counts,
        })
        # Store membership drift is an item-level preflight failure.  Keep it
        # in the same immutable review report as render failures, but do not
        # let it abort independent approved store groups.
        if stale_store_items:
            for item in stale_store_items:
                stats["rejected"] += 1
                stats["errors"].append({
                    "category": item["key"].split(":", 1)[0],
                    "template": item["key"].split(":", 1)[1].split("@", 1)[0],
                    "store": item["store"],
                    "design": None,
                    "error_code": "STORE_TEMPLATE_APPROVAL_SHA_CHANGED",
                    "processing_stage": "STORE_PREFLIGHT",
                    "reason": item["reason"],
                    "key": item["key"],
                })
            notify(f"İNCELEMEYE AYRILDI: {len(stale_store_items)} mağaza şablonu "
                   "onay/SHA değişikliği nedeniyle üretim dışı bırakıldı; güvenli gruplar devam ediyor.")

        # Production is deliberately fixed at the measured best setting for
        # this workstation.  Benchmark/profile files remain diagnostic only;
        # no environment variable or stale profile may change live throughput.
        render_workers, worker_source = production_render_workers()
        stats["render_workers"] = render_workers
        stats["render_worker_selection"] = worker_source
        try:
            png_compression = max(0, min(9, int(os.environ.get("V4_PNG_COMPRESSION", "4"))))
        except (TypeError, ValueError):
            png_compression = 4
        stats["png_compression"] = png_compression

        # Save new output list for optional post-processing; reused older outputs
        # are never silently post-processed or uploaded.
        newly_rendered: list[dict[str, str]] = []
        render_executor = ThreadPoolExecutor(max_workers=render_workers,
                                              thread_name_prefix="v4-render",
                                              initializer=_init_render_worker) if render_workers > 1 else None
        pending_renders: list[tuple[dict[str, Any], Any]] = []

        # PETEK overlay derivatives are computed on one dedicated worker while
        # later renders continue.  Only the pure image computation runs off
        # thread; ledger writes, stats and output_ready stay on the coordinator.
        overlay_stats = {
            "enabled": bool(overlay_active), "planned": 0, "completed": 0,
            "successful": 0, "skipped": 0, "failed": 0, "errors": [],
            "outputs": [], "warning": None, "selection_retries": [],
        }
        def emit_overlay_progress(payload: dict[str, Any]) -> None:
            try:
                progress(payload)
            except Exception:
                logging.getLogger(__name__).debug("Overlay progress callback failed", exc_info=True)
        overlay_executor = (ThreadPoolExecutor(max_workers=1, thread_name_prefix="v4-overlay")
                            if overlay_active else None)
        pending_overlays: list[tuple[dict[str, Any], str, Any]] = []
        overlay_submitted: set[str] = set()
        overlay_clock: dict[str, Any] = {"started": None}

        def _overlay_clock_snapshot() -> tuple[float, float | None]:
            """Real elapsed/ETA for the overlay stage (monotonic, never fake)."""
            started = overlay_clock.get("started") or progress_started
            elapsed = max(0.0, time.monotonic() - started)
            completed = int(overlay_stats["completed"])
            planned = int(overlay_stats["planned"])
            eta = None
            if completed and completed < planned:
                eta = elapsed * (planned - completed) / completed
            return round(elapsed, 1), (round(eta, 1) if eta is not None else None)

        def _overlay_fail(source_row: dict[str, Any], source_store: str, exc: BaseException,
                          committed: int) -> None:
            # Count only the unresolved remainder so completed never exceeds planned.
            remaining = max(0, len(PETEK_OVERLAY_MEASUREMENTS) - committed)
            overlay_stats["failed"] += remaining
            overlay_stats["completed"] += remaining
            overlay_stats["errors"].append({
                "category": "06_Petek_Kapama", "store": source_store,
                "design": source_row.get("art_name"), "source": source_row.get("output"),
                "source_sha": source_row.get("output_sha"),
                "processing_stage": "PETEK_OVERLAY", "error": str(exc),
                "suggestion": "Overlay_Giydirme PNG klasörlerini ve ürün koruma yerleşimini inceleyin.",
            })
            _elapsed_ov, _eta_ov = _overlay_clock_snapshot()
            emit_overlay_progress({
                "phase": "overlay", "stage": "overlay",
                "completed": int(overlay_stats["completed"]),
                "total": int(overlay_stats["planned"]),
                "index": int(overlay_stats["completed"]),
                "category": "06_Petek_Kapama",
                "operation": "Overlay inceleme kaydı",
                "successful": int(overlay_stats["successful"]),
                "failed": int(overlay_stats["failed"]), "skipped": int(overlay_stats["skipped"]),
                "elapsed_seconds": _elapsed_ov, "eta_seconds": _eta_ov,
            })
            notify(f"PETEK OVERLAY İNCELEME GEREKİYOR: {source_row.get('art_name')} — {exc}")

        def _overlay_submit(source_key: str) -> None:
            """Queue overlay work for one SHA-verified clean PETEK source (idempotent)."""
            source_key = str(source_key)
            if overlay_executor is None or source_key in overlay_submitted or self.cancel.is_set():
                return
            overlay_submitted.add(source_key)
            source_row: dict[str, Any] = {"key": source_key}
            source_store = group
            try:
                with self.ledger.connect() as con:
                    found = con.execute("SELECT * FROM artifact WHERE key=? AND status='RENDERED'",
                                        (source_key,)).fetchone()
                    if found is None:
                        return
                    source_row = dict(found)
                    existing_rows = [dict(r) for r in con.execute(
                        """SELECT * FROM artifact WHERE status='RENDERED' AND artifact_kind='overlay'
                           AND source_key=?""", (source_key,))]
                if (source_row.get("category") != "06_Petek_Kapama"
                        or str(source_row.get("artifact_kind") or "clean") != "clean"):
                    return
                if overlay_clock["started"] is None:
                    overlay_clock["started"] = time.monotonic()
                overlay_stats["planned"] += len(PETEK_OVERLAY_MEASUREMENTS)
                try:
                    source_store = _store_id_from_output(source_row["output"], self.output)
                except (ValueError, IndexError, OSError):
                    source_store = group
                existing_for_source = {str(row.get("overlay_cm")): row for row in existing_rows}
                for old_row in existing_for_source.values():
                    old_path = Path(old_row.get("output") or "")
                    dimensions_current = False
                    if old_path.is_file() and not old_path.is_symlink():
                        try:
                            with PILImage.open(old_path) as old_image:
                                dimensions_current = old_image.size == PETEK_OVERLAY_FINAL_SIZE
                        except (OSError, ValueError):
                            dimensions_current = False
                    if (old_path.is_symlink() or not old_path.is_file() or
                            petek_engine.digest(old_path) != old_row.get("output_sha") or
                            not dimensions_current):
                        self.ledger.quarantine(
                            str(old_row["key"]),
                            "PETEK_OVERLAY_OUTPUT_SHA_OR_DIMENSIONS_MISMATCH_RETRY",
                        )
                source_input = dict(source_row, overlay_outputs={
                    cm: {"output_sha": row.get("output_sha", "")}
                    for cm, row in existing_for_source.items()
                })
                future = overlay_executor.submit(
                    process_petek_overlay_source, source_input, overlay_validation or {},
                    Path(source_row["output"]).parent, source_sha=source_row.get("output_sha"))
                pending_overlays.append((source_row, source_store, future))
            except Exception as exc:
                _overlay_fail(source_row, source_store, exc, 0)

        def _overlay_commit(entry: tuple[dict[str, Any], str, Any]) -> None:
            source_row, source_store, future = entry
            if future.cancelled():
                overlay_stats["planned"] -= len(PETEK_OVERLAY_MEASUREMENTS)
                return
            committed = 0
            try:
                result = future.result()
                if result.get("selection_warning"):
                    overlay_stats["warning"] = "LIMITED_POOL"
                for attempt_cm, attempts in (result.get("selection_attempts") or {}).items():
                    rejected = [item for item in attempts if item.get("status") == "rejected"]
                    if rejected:
                        overlay_stats["selection_retries"].append({
                            "design": source_row.get("art_name"), "cm": attempt_cm, "attempts": attempts,
                        })
                for item in result["results"]:
                    cm = str(item["cm"])
                    manifest = item["manifest"]
                    overlay_sha = str(item["output_sha"])
                    # The key includes source, measurement and the complete asset
                    # SHA manifest. Changed PNGs create a new immutable revision.
                    overlay_key = hashlib.sha256((str(source_row["key"]) + "|" + cm + "|" +
                                                  json.dumps(manifest, sort_keys=True, ensure_ascii=False)).encode("utf-8")).hexdigest()[:24]
                    if selected_stores:
                        try:
                            base_codes = trendyol_codes(source_row["art_name"], source_store, "06_Petek_Kapama")
                            codes = petek_measurement_codes(base_codes, cm)
                            overlay_sku = codes["sku"]
                            code_errors = validate_trendyol_codes(codes)
                            if code_errors:
                                raise petek_engine.MaskError("PETEK_KOD_UZUNLUK: " + "; ".join(code_errors))
                        except ValueError as exc:
                            raise petek_engine.MaskError(str(exc)) from exc
                    else:
                        overlay_sku = f"{source_row['sku']}__{cm}"
                    fields = {
                        "key": overlay_key, "sku": overlay_sku,
                        "category": "06_Petek_Kapama", "art_sha": source_row["art_sha"],
                        "template_sha": source_row["template_sha"], "mask_sha": source_row["mask_sha"],
                        "art_name": source_row["art_name"], "uid": source_row["uid"],
                        "output": item["output"], "artifact_kind": "overlay",
                        "source_key": source_row["key"], "overlay_cm": cm,
                        "overlay_manifest": json.dumps(manifest, ensure_ascii=False, sort_keys=True),
                    }
                    record = self.ledger.reserve(fields)
                    if record["status"] == "RENDERED":
                        if (not Path(record["output"]).is_file() or
                                petek_engine.digest(Path(record["output"])) != record["output_sha"]):
                            raise petek_engine.MaskError("PETEK_OVERLAY_SHA_MISMATCH")
                        overlay_stats["skipped"] += 1
                    elif record["status"] == "PENDING":
                        self.ledger.complete(overlay_key, overlay_sha)
                        overlay_stats["successful"] += 1
                    else:
                        raise petek_engine.MaskError("PETEK_OVERLAY_KAYDI_INCELEMEDE")
                    overlay_stats["completed"] += 1
                    committed += 1
                    stats["current_batch_keys"].append(overlay_key)
                    stats["current_batch_outputs"].append({
                        "file_name": Path(item["output"]).name, "category": "06_Petek_Kapama",
                        "store": source_store, "location": item["output"], "overlay_cm": cm,
                        "source_key": source_row["key"], "output_sha": overlay_sha,
                    })
                    overlay_stats["outputs"].append({
                        "file_name": Path(item["output"]).name,
                        "location": item["output"], "overlay_cm": cm,
                        "group_name": manifest.get("group_name"),
                        "output_sha": overlay_sha,
                    })
                    overlay_row = dict(fields, store=source_store,
                                       output_sha=record.get("output_sha") or overlay_sha)
                    try:
                        output_ready(overlay_row)
                    except Exception as exc:
                        notify(f"PETEK OVERLAY BULUT KUYRUĞU UYARISI: {exc}")
                    _elapsed_ov, _eta_ov = _overlay_clock_snapshot()
                    emit_overlay_progress({
                        "phase": "overlay", "stage": "overlay",
                        "completed": int(overlay_stats["completed"]),
                        "total": int(overlay_stats["planned"]),
                        "index": int(overlay_stats["completed"]),
                        "category": "06_Petek_Kapama",
                        "operation": f"{cm} overlay",
                        "successful": int(overlay_stats["successful"]),
                        "failed": int(overlay_stats["failed"]), "skipped": int(overlay_stats["skipped"]),
                        "elapsed_seconds": _elapsed_ov, "eta_seconds": _eta_ov,
                    })
            except Exception as exc:
                _overlay_fail(source_row, source_store, exc, committed)

        def _overlay_poll(block: bool = False) -> None:
            """Commit finished overlay results in submission order."""
            while pending_overlays:
                if not block and not pending_overlays[0][2].done():
                    break
                _overlay_commit(pending_overlays.pop(0))

        four_stats = {"enabled": four_active, "planned": 0, "successful": 0, "skipped": 0,
                      "failed": 0, "errors": [], "seconds": 0.0}
        four_done: set[str] = set()
        four_label_dir = (None if not four_active else
                          ((self.runtime_root / "Overlay_Giydirme" / four_mockup_mod.LABEL_FOLDER)
                           if self.runtime_root else None))

        def _make_four_final(row: dict[str, Any], clean_bytes: bytes | None = None) -> None:
            """Clean render -> slot varyasyonu final görseli (idempotent, hata izole)."""
            source_key = str(row["key"])
            if source_key in four_done:
                return
            four_done.add(source_key)
            started = time.perf_counter()
            four_stats["planned"] += 1
            store = None
            try:
                store = _store_id_from_output(row["output"], self.output)
                design_key = str(Path(row.get("design_path") or row.get("art_name") or "").resolve()).casefold()
                cm = four_slot_lookup.get((store, str(row["uid"]), design_key))
                if cm is None:
                    # Legacy checkpoints have only store/UID slots.  Preserve
                    # their completed-selection behavior on resume.
                    cm = next((candidate_cm for (candidate_store, candidate_uid, _), candidate_cm
                               in four_slot_lookup.items()
                               if candidate_store == store and candidate_uid == str(row["uid"])), None)
                if cm is None:
                    raise petek_engine.MaskError("DORT_MOCKUP_SLOT_BULUNAMADI: " + str(row["uid"]))
                # A clean source maps to exactly one final in four-mockup
                # mode.  During STOP/resume a worker may have committed that
                # final just before the checkpoint was written; preserve it
                # instead of opening a second measurement-specific receipt.
                with self.ledger.connect() as con:
                    existing_final = con.execute(
                        "SELECT key FROM artifact WHERE status='RENDERED' "
                        "AND artifact_kind='overlay' AND source_key=? LIMIT 1",
                        (source_key,),
                    ).fetchone()
                if existing_final is not None:
                    four_stats["skipped"] += 1
                    return
                clean_path = Path(row["output"])
                data, manifest = four_mockup_mod.render_final_bytes(
                    clean_bytes if clean_bytes is not None else clean_path,
                    cm, four_overlays[cm], label_dir=four_label_dir,
                    pick_key=f"{row['art_sha']}|{store}", compression=png_compression)
                manifest["source_sha"] = row["output_sha"]
                # Harici (test) tasarımlarda motor zaten EXT-<işlem> kimliği kullanır;
                # rastgele dosya adı kod uzunluk sınırını aşabilir.
                code_name = f"EXT-{operation_id[-8:]}" if external_mode else row["art_name"]
                base_codes = trendyol_codes(code_name, store, "06_Petek_Kapama")
                codes = petek_measurement_codes(base_codes, cm)
                code_errors = validate_trendyol_codes(codes)
                if code_errors:
                    raise petek_engine.MaskError("PETEK_KOD_UZUNLUK: " + "; ".join(code_errors))
                final_path = (clean_path.parent.parent.parent / clean_path.parent.name /
                              four_mockup_mod.final_name(clean_path.name, cm))
                overlay_key = four_mockup_mod.final_key(source_key, cm, manifest)
                fields = {
                    "key": overlay_key, "sku": codes["sku"], "category": "06_Petek_Kapama",
                    "art_sha": row["art_sha"], "template_sha": row["template_sha"],
                    "mask_sha": row["mask_sha"], "art_name": row["art_name"],
                    "design_path": row.get("design_path", ""), "uid": row["uid"],
                    "output": str(final_path), "artifact_kind": "overlay", "source_key": source_key,
                    "overlay_cm": cm,
                    "overlay_manifest": json.dumps(manifest, ensure_ascii=False, sort_keys=True),
                }
                record = self.ledger.reserve(fields)
                final_sha = hashlib.sha256(data).hexdigest()
                if record["status"] == "RENDERED":
                    if (final_path.is_symlink() or not final_path.is_file()
                            or petek_engine.digest(final_path) != record["output_sha"]):
                        raise petek_engine.MaskError("DORT_MOCKUP_FINAL_SHA_UYUMSUZ")
                    four_stats["skipped"] += 1
                    final_sha = record["output_sha"]
                elif record["status"] == "PENDING":
                    if final_path.exists() and petek_engine.digest(final_path) != final_sha:
                        raise petek_engine.MaskError("DORT_MOCKUP_FINAL_DOSYASI_SUPHELI")
                    if not final_path.exists():
                        petek_engine.atomic_new_file(final_path, data)
                    self.ledger.complete(overlay_key, final_sha)
                    four_stats["successful"] += 1
                else:
                    raise petek_engine.MaskError("DORT_MOCKUP_KAYDI_INCELEMEDE")
                stats["current_batch_keys"].append(overlay_key)
                stats["current_batch_outputs"].append({
                    "file_name": final_path.name, "category": "06_Petek_Kapama", "store": store,
                    "location": str(final_path), "overlay_cm": cm, "source_key": source_key,
                    "output_sha": final_sha, "design": row["art_name"]})
                try:
                    output_ready(dict(fields, store=store, output_sha=final_sha))
                except Exception as exc:
                    notify(f"BULUT KUYRUĞU UYARISI: {exc}")
                notify(f"FINAL {cm}: {final_path.name}")
            except Exception as exc:
                four_stats["failed"] += 1
                stats["rejected"] += 1
                err = {"category": "06_Petek_Kapama", "template": row.get("uid"),
                       "design": row.get("art_name"), "store": store,
                       "error_code": str(exc).split(":", 1)[0] or "DORT_MOCKUP_HATASI",
                       "processing_stage": "DORT_MOCKUP_FINAL", "reason": str(exc),
                       "traceback": traceback.format_exc()}
                four_stats["errors"].append(err)
                stats["errors"].append(err)
                notify(f"DÖRT MOCKUP FINAL ATLANDI {row.get('art_name')}/{row.get('uid')}: {exc}")
            finally:
                four_stats["seconds"] += time.perf_counter() - started

        def _render_task(context: dict[str, Any]):
            started = time.perf_counter()
            rendered = _render_job_picture(**context["render_args"])
            return (*rendered, time.perf_counter() - started)

        def _finish_render(context: dict[str, Any], result) -> None:
            """Commit one completed render on the coordinator thread."""
            cat = context["category"]
            uid = context["uid"]
            art = context["art"]
            key = context["key"]
            output = context["output"]
            source_path = context["source_path"]
            source_sha = context["source_sha"]
            original_art = context["original_art"]
            art_sha = context["art_sha"]
            try:
                if isinstance(result, BaseException):
                    raise result
                picture, render_qa, render_kind, render_seconds = result
                stage_timings["image_processing_seconds"] += render_seconds
                if render_kind == "petek":
                    petek_qa = render_qa
                    notify(f"PETEK KORUMA KONTRATI: {petek_qa['render_plan_sha256'][:12]} / "
                           f"kaynak-mask geometri: {petek_qa['vent_guard_qa']['status']} / {uid}")
                    if petek_qa['pre_pink_qa'].get('repaired_pixels', 0):
                        notify(f"PETEK yalnız çıktı alt-sol işareti temizlendi: "
                               f"{petek_qa['pre_pink_qa']['repaired_pixels']} px / {uid}")
                    if petek_slot_mode != 'off':
                        slot_qa = petek_qa['slot_qa']
                        notify(f"PETEK gerçek yarıklar: {slot_qa['status']} / "
                               f"boy kanıtı yetersiz atlanan: "
                               f"{slot_qa.get('endpoint_effect_suppressed_count', 0)} / {uid}")
                    if petek_pink_cleanup:
                        notify(f"PETEK pembe temizlik: {petek_qa['pink_qa']['status']} / {uid}")
                elif sunlight_profile != 'off' and lighting != 'off':
                    sun_qa = render_qa['sunlight_qa']
                    notify(f"7 KATEGORI GUNES [{cat}]: {sunlight_profile}; "
                           f"duvar={sun_qa.get('wall_status', 'OFF')}; "
                           f"golge={sun_qa.get('wall_shadow_pixels', 0)} px / {uid}")

                save_started = time.perf_counter()
                encoded_png = petek_engine.encode_png(picture, png_compression)
                petek_engine.atomic_new_file(output, encoded_png)
                receipt_sha = petek_engine.digest(output)
                stage_timings["save_seconds"] += time.perf_counter() - save_started
                if stage_timings["first_output_latency_seconds"] is None:
                    stage_timings["first_output_latency_seconds"] = time.perf_counter() - operation_started
                if (petek_engine.digest(source_path) != source_sha or
                        petek_engine.digest(original_art) != art_sha):
                    raise petek_engine.MaskError(
                        "Kaynak dosya üretim sırasında değişmiş; çıktı incelemeye alındı.")
                ledger_started = time.perf_counter()
                self.ledger.complete(key, receipt_sha)
                stage_timings["ledger_seconds"] += time.perf_counter() - ledger_started
                newly_rendered.append({"key": key, "sku": context["sku"],
                                       "output": str(output), "output_sha": receipt_sha})
                stats["rendered"] += 1
                stats["current_batch_keys"].append(key)
                stats["current_batch_outputs"].append({
                    "file_name": output.name, "category": cat,
                    "store": context["group"], "location": str(output)})
                stage_counts["render_worker_completed"] = stage_counts.get("render_worker_completed", 0) + 1
                notify(f"ÜRETİLDİ {stats['rendered']}: [{cat}] {uid} / {art.name}")
                # With PETEK overlays enabled the clean source is a protected
                # intermediate; only the four verified derivatives enter the
                # explicit cloud callback after the overlay stage completes.
                if not ((overlay_active or four_active) and cat == "06_Petek_Kapama"):
                    try:
                        output_ready(dict(newly_rendered[-1]))
                    except Exception as exc:
                        notify(f"BULUT KUYRUĞU UYARISI: {exc}")
                emit_progress(cat, f"{uid} / {art.name}", outcome="success")
                if four_active and cat == "06_Petek_Kapama":
                    _make_four_final({
                        "key": key, "output": str(output), "output_sha": receipt_sha, "uid": uid,
                        "art_name": art.name, "design_path": str(original_art),
                        "art_sha": art_sha, "template_sha": source_sha,
                        "mask_sha": context["mask_sha"]}, encoded_png)
                if overlay_active and cat == "06_Petek_Kapama":
                    _overlay_submit(key)
                    _overlay_poll()
            except Exception as exc:
                try:
                    self.ledger.quarantine(key, str(exc))
                except Exception:
                    logging.exception("Unable to quarantine failed render %s", key)
                stats["rejected"] += 1
                stats["errors"].append({
                    "category": cat, "template": uid, "design": art.name,
                    "store": context["group"], "design_path": str(original_art),
                    "source_path": str(source_path),
                    "error_code": str(exc).split(':', 1)[0],
                    "processing_stage": "URETIM_CIKTISI",
                    "reason": str(exc), "traceback": traceback.format_exc(),
                })
                notify(f"ATLANDI [{cat}] {uid}/{art.name} — {exc}")
                emit_progress(cat, f"{uid} / {art.name}", outcome="failed")

        def _drain_one_render() -> None:
            if len(pending_renders) > 1:
                done, _ = wait([future for _, future in pending_renders],
                               return_when=FIRST_COMPLETED)
                index = next((idx for idx, (_, future) in enumerate(pending_renders)
                              if future in done), 0)
            else:
                index = 0
            context, future = pending_renders.pop(index)
            try:
                result = future.result()
            except BaseException as exc:
                result = exc
            _finish_render(context, result)

        history_mode = "four_mockup" if four_active else ("overlay4" if overlay_active else "standard")
        history_mod.start_session(
            self.root, operation_id=operation_id, mode=history_mode, design_folder=str(designs),
            stores=[store for store, _ in production_plan], design_count=len(designs_in_run),
            planned=progress_total, external=external_mode)

        def _history_finish(status: str) -> None:
            outputs = [o for o in stats.get("current_batch_outputs", [])
                       if (not four_active) or o.get("overlay_cm")]
            per_store: dict[str, int] = {}
            for out in outputs:
                per_store[str(out.get("store"))] = per_store.get(str(out.get("store")), 0) + 1
            done = (four_stats["successful"] if four_active else int(stats.get("rendered", 0)))
            history_mod.finish_session(
                self.root, operation_id=operation_id, status=status, successful=done,
                failed=int(stats.get("rejected", 0)),
                skipped=int(stats.get("reused", 0)) + int(four_stats["skipped"]),
                elapsed_seconds=time.perf_counter() - operation_started,
                per_store={"outputs": per_store, "four_mockup_seconds": round(four_stats["seconds"], 2)},
                report_path=str(operation_report_path))

        notify(f"MAĞAZA/SIRA PLANI: {len(production_plan)} mağaza, "
               f"{len(designs_in_run)} tasarım; rastgele tohum: {seed}. "
               "Onaylı dört köşe ve mevcut çıktılar değişmez.")
        try:
            # Save the source/selection fingerprint before rendering begins.
            # STOP only takes effect between jobs, so ledger replay is exact.
            if not external_mode:
                write_checkpoint(self.root, checkpoint_record)
            processed_jobs = set()
            # Bounded, in-memory artwork cache.  The decoded raster is shared
            # by all templates in this batch; the original file SHA remains
            # the identity and is never replaced by a cache key.
            artwork_cache: OrderedDict[tuple, tuple[Path, str, np.ndarray, int]] = OrderedDict()
            artwork_cache_bytes = 0
            artwork_cache_limit = max(
                64 * 1024 * 1024,
                int(os.environ.get("V4_ARTWORK_CACHE_BYTES", str(1024 * 1024 * 1024))),
            )
            # Approved template source/mask preparation is invariant across
            # designs and stores.  Keep it in RAM for this run only; source and
            # mask SHA values are still revalidated before each output.
            template_cache: OrderedDict[tuple, tuple[np.ndarray, str, np.ndarray, Path, str, int]] = OrderedDict()
            template_cache_bytes = 0
            template_cache_limit = max(
                128 * 1024 * 1024,
                int(os.environ.get("V4_TEMPLATE_CACHE_BYTES", str(2 * 1024 * 1024 * 1024))),
            )
            for group, templates in production_plan:
                for design_index, art in enumerate(designs_in_run):
                    if not self._wait_if_paused(notify):
                        break
                    if self.cancel.is_set() or (max_jobs is not None and stats["attempted"] >= int(max_jobs)):
                        break
                    original_art = art
                    try:
                        # Reuse safe high-resolution proxies across stores;
                        # per-output original design SHA validation remains.
                        current_stat=original_art.stat()
                        signature=(current_stat.st_size,current_stat.st_mtime_ns)
                        artwork_key = (original_art, signature)
                        cached=artwork_cache.get(artwork_key)
                        if cached is not None:
                            artwork_cache.move_to_end(artwork_key)
                            render_art,art_sha,artwork_raster,_cached_bytes=cached
                            stats["artwork_cache_hits"]=stats.get("artwork_cache_hits",0)+1
                            stage_counts["source_cache_hits"] += 1
                        else:
                            render_art,art_sha=prepare_render_artwork(
                                original_art,self.root/"working_art_proxies")
                            decode_started = time.perf_counter()
                            artwork_raster = petek_engine.read_bgr(render_art)
                            stage_timings["source_read_seconds"] += time.perf_counter() - decode_started
                            if artwork_raster.ndim != 3 or artwork_raster.dtype != np.uint8:
                                raise petek_engine.MaskError("Tasarım çalışma rasteri geçersiz.")
                            artwork_raster.setflags(write=False)
                            cached_bytes = int(artwork_raster.nbytes)
                            artwork_cache[artwork_key]=(render_art,art_sha,artwork_raster,cached_bytes)
                            artwork_cache_bytes += cached_bytes
                            while artwork_cache_bytes > artwork_cache_limit and len(artwork_cache) > 1:
                                _old_key, _old_value = artwork_cache.popitem(last=False)
                                artwork_cache_bytes -= int(_old_value[3])
                                stage_counts["artwork_cache_evictions"] = stage_counts.get("artwork_cache_evictions", 0) + 1
                    except (petek_engine.MaskError, cv2.error, OSError, ValueError) as exc:
                        stats["rejected"] += 1
                        stats["errors"].append({"design": original_art.name,
                                                "design_path": str(original_art),
                                                "source_path": str(original_art),
                                                "category": None, "store": group, "template": None,
                                                "error_code": str(exc).split(':', 1)[0],
                                                "processing_stage": "TASARIM_HAZIRLAMA",
                                                "reason": "TASARIM_BOYUTU_VE_GUVENLIK: " + str(exc),
                                                "traceback": traceback.format_exc()})
                        notify(f"ATLANDI TASARIM {original_art.name}: {exc}")
                        # The design preparation failed before the inner
                        # template loop. Count every planned pair as a failed
                        # operation so the bar cannot stall below 100%.
                        failed_items = ([templates[design_index % len(templates)]]
                                        if render_mode == "balanced_one_per_design"
                                        else templates)
                        for failed_item in failed_items:
                            if progress_completed >= progress_total:
                                break
                            emit_progress(failed_item.get("category", ""),
                                          f"{failed_item.get('uid', '')} / {original_art.name}",
                                          outcome="failed")
                        continue

                    # Draw a fresh template permutation for EVERY design,
                    # not only once for the entire store. In four-mockup mode
                    # this is the exact per-design four-UID plan.
                    design_key = str(original_art.resolve()).casefold()
                    four_selected_uids = set()
                    if four_active:
                        four_selected_uids = set(
                            (four_design_slots.get(group, {}).get(design_key) or {}).values()
                        )
                        if len(four_selected_uids) != 4:
                            raise petek_engine.MaskError(
                                f"DORT_MOCKUP_SECIMI_EKSIK: {group}/{original_art.name} için 4 şablon planlanamadı"
                            )
                    if render_mode == "balanced_one_per_design":
                        template_order = [templates[design_index % len(templates)]]
                    else:
                        template_order = [item for item in templates
                                           if not four_active or str(item.get("uid")) in four_selected_uids]
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
                            emit_progress(item.get("category", ""), f"{item.get('uid', '')} / {art.name}", outcome="skipped")
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
                            template_key = (
                                item["uid"], item["source_sha"], item.get("mask_sha", ""),
                                item["engine_type"], item["category"],
                                json.dumps(item.get("quad"), sort_keys=True, separators=(",", ":")),
                                round(float(item.get("physical_aspect", 0.0)), 8),
                                placement, lighting, glass_effect, sunlight_profile,
                                petek_slot_mode, bool(petek_pink_cleanup), petek_realism_profile,
                            )
                            prepared = template_cache.get(template_key)
                            if prepared is not None:
                                stage_counts["template_cache_hits"] += 1
                                template_cache.move_to_end(template_key)
                                mask, mask_sha, source_scene, source_path, source_sha, _cached_bytes = prepared
                                item = dict(item, source=str(source_path), source_sha=source_sha,
                                            mask_sha=mask_sha)
                            else:
                                source_read_started = time.perf_counter()
                                if item["engine_type"] == "PETEK_V3_CUTOUT":
                                    profile, mask = self.petek_registry.get_current(
                                        uid, require_approved=True, source_override=source_path)
                                    uid = profile["uid"]
                                    source_path = Path(profile["source"])
                                    source_sha = profile["source_sha"]
                                    approved_mask_sha = profile["mask_sha"]
                                    source_scene = petek_engine.read_bgr(source_path)
                                    mask, mask_sha, vent_guard = _resolve_petek_production_mask(
                                        source_scene, mask, item["quad"]
                                    )
                                    if vent_guard.get("status") == "TEMPORARY_SOURCE_EVIDENCE":
                                        notify(
                                            "PETEK geçici fotoğraf kanıtı maskesi: "
                                            f"onaylı={approved_mask_sha[:12]} / üretim={mask_sha[:12]} / "
                                            "onaylı maske ve dört köşe değiştirilmedi."
                                        )
                                    if petek_slot_mode != 'off':
                                        from PETEK_V3.petek_slot_geometry_vnext import measure_real_vents
                                        measure_real_vents(source_scene, mask, item["quad"],
                                                           cache_root=self.geometry_cache)
                                else:
                                    source_scene = petek_engine.read_bgr(source_path)
                                    mask = _build_legacy_category_mask(source_scene, item["quad"], item.get("legacy_data"))
                                    mask_sha = petek_engine.mask_hash(mask)
                                stage_timings["source_read_seconds"] += time.perf_counter() - source_read_started
                                mask.setflags(write=False)
                                source_scene.setflags(write=False)
                                cached_bytes = int(mask.nbytes + source_scene.nbytes)
                                template_cache[template_key] = (
                                    mask, mask_sha, source_scene, source_path, source_sha, cached_bytes)
                                template_cache_bytes += cached_bytes
                                while template_cache_bytes > template_cache_limit and len(template_cache) > 1:
                                    _old_key, _old_value = template_cache.popitem(last=False)
                                    template_cache_bytes -= int(_old_value[5])
                                    stage_counts["template_cache_evictions"] = stage_counts.get("template_cache_evictions", 0) + 1
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
                                sunlight_profile=sunlight_profile if lighting != 'off' else 'off',
                                petek_realism_profile=petek_realism_profile,
                                recipe=((V4_RECIPE + "+" + MATERIAL_RECIPE)
                                    if cat in (GLASS | DAYLIGHT) and glass_effect == "on" and lighting != "off"
                                    else V4_RECIPE) + ('+STORE_CODES_V485' if selected_stores else '') +
                                (('+' + PETEK_FINISH_RECIPE + ':' + petek_slot_mode + ':pink=' + str(petek_pink_cleanup) + ':' + PETEK_DESPILL_RECIPE)
                                 if cat == '06_Petek_Kapama' and (petek_slot_mode != 'off' or petek_pink_cleanup) else '') +
                                ('+' + SCENE_DAYLIGHT_RECIPE + ':' + sunlight_profile
                                 if sunlight_profile != 'off' and lighting != 'off' else ''),
                            )
                        except (petek_engine.MaskError, cv2.error, OSError, ValueError, KeyError, TypeError) as exc:
                            stats["rejected"] += 1
                            stats["errors"].append(
                                {"category": cat, "template": uid, "design": art.name,
                                 "store": group,
                                 "design_path": str(art), "source_path": str(source_path),
                                 "error_code": str(exc).split(':', 1)[0],
                                 "processing_stage": "GEOMETRI_VE_MASKE_DENETIMI",
                                 "reason": "GEOMETRI_VE_MASKE_DENETIMI: " + str(exc),
                                 "traceback": traceback.format_exc()}
                            )
                            notify(f"İNCELEME GEREKİYOR [{cat}] {uid} / {art.name}: {exc}")
                            emit_progress(cat, f"{uid} / {art.name}", outcome="failed")
                            continue
                        key = full_key[:24]
                        if selected_stores:
                            # The filename and business identifiers are derived
                            # from the SHARED original artwork number, never from
                            # output hashes. Different stores use separately
                            # assigned approved templates and unique filenames.
                            if external_mode:
                                # Original source names remain untouched and
                                # are never interpreted as central numbers.
                                # The operation id is deliberately ephemeral.
                                design_id = f"EXT-{operation_id[-8:]}"
                                try:
                                    identifiers = trendyol_codes(design_id, group, cat)
                                except ValueError:
                                    # Legacy/synthetic store profiles created
                                    # before configurable short codes remain
                                    # renderable; their Excel export reports an
                                    # explicit code error if no safe mapping is
                                    # available.
                                    identifiers = store_codes(design_id, group, cat)
                                sku = identifiers['sku']
                                safe_stem = re.sub(r'[^A-Za-z0-9_-]+', '_', original_art.stem)[:80] or 'design'
                                output_name = f"{safe_stem}__{group}__{uid}__{operation_id[-8:]}.png"
                            else:
                                design_id=design_number(original_art)
                                try:
                                    identifiers=trendyol_codes(design_id,group,cat)
                                except ValueError:
                                    identifiers=store_codes(design_id,group,cat)
                                sku=identifiers['sku']
                                output_name=store_filename(design_id,group,cat,uid)
                            # Distinct immutable output for an opt-in PETEK
                            # preview recipe. Never collide with the ordinary
                            # V01.png SKU filename of an existing production.
                            if cat=='06_Petek_Kapama' and (petek_slot_mode!='off' or petek_pink_cleanup):
                                stem=Path(output_name).stem
                                output_name=(stem+'__PV492_'+petek_slot_mode+
                                             ('_P2' if petek_pink_cleanup else '_P0')+'.png')
                            if cat == '06_Petek_Kapama' and petek_realism_profile != 'dogal':
                                stem = Path(output_name).stem
                                output_name = stem + '__PETEK_' + petek_realism_profile.upper() + '.png'
                        else:
                            sku=f"{prefix}-{group}-{full_key[:18].upper()}"
                            output_name=f"{sku}_{key}.png"
                        if selected_stores and sunlight_profile != 'off' and lighting != 'off':
                            output_name=Path(output_name).stem+'__GUNES_'+sunlight_profile.upper()+'_W2.png'
                        output_root = self.output / group / cat
                        # With PETEK overlays enabled the clean render is an
                        # intermediate artifact. Keep all such files together
                        # so the category root contains only the measurement
                        # folders for overlay derivatives.
                        if (overlay_active or four_active) and cat == "06_Petek_Kapama":
                            output_root = output_root / PETEK_OVERLAY_FREE_FOLDER
                            if petek_overlay_batch_folder:
                                output_root = output_root / petek_overlay_batch_folder
                        output = output_root / output_name

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
                            ledger_started = time.perf_counter()
                            record = self.ledger.reserve(fields)
                            stage_timings["ledger_seconds"] += time.perf_counter() - ledger_started
                            if record["status"] == "USER_REMOVED":
                                # User intentionally deleted this output. Preserve its
                                # SKU/receipt and NEVER silently recreate or flag it
                                # as a corrupted render on subsequent batch runs.
                                stats["user_removed"] = stats.get("user_removed", 0) + 1
                                notify(f"KULLANICI TARAFINDAN SİLİNDİ / tarihî kayıt korundu: [{cat}] {uid} / {art.name}")
                                emit_progress(cat, f"{uid} / {art.name}", outcome="skipped")
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
                                stats["current_batch_outputs"].append({
                                    "file_name": output.name, "category": cat,
                                    "store": group, "location": str(output)})
                                if not ((overlay_active or four_active) and cat == "06_Petek_Kapama"):
                                    try:
                                        output_ready({"key": key, "sku": sku, "output": str(output),
                                                      "output_sha": record["output_sha"]})
                                    except Exception as exc:
                                        notify(f"BULUT KUYRUĞU UYARISI: {exc}")
                                if overlay_active and cat == "06_Petek_Kapama":
                                    _overlay_submit(key)
                                    _overlay_poll()
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
                                    try:
                                        output_ready(dict(newly_rendered[-1]))
                                    except Exception as exc:
                                        notify(f"BULUT KUYRUĞU UYARISI: {exc}")
                                notify(f"ATLANDI / mevcut kayıt: [{cat}] {uid} / {art.name}")
                                emit_progress(cat, f"{uid} / {art.name}", outcome="skipped")
                                continue
                            if record["status"] == "REVIEW_REQUIRED":
                                record = self.ledger.retry_unwritten(key, self.output)
                                if record["status"] == "PENDING":
                                    notify(f"YENİDEN DENENİYOR / dosya oluşmamış iş: {uid} / {art.name}")
                                else:
                                    reason = (record.get("message") or "Önceki iş inceleme bekliyor.")
                                    stats["rejected"] += 1
                                    stats["errors"].append({"category": cat, "template": uid,
                                        "design": art.name, "reason": reason, "output": str(output)})
                                    notify(f"İNCELEME BEKLİYOR [{cat}] {uid}/{art.name} — {reason} "
                                           "| Mevcut dosya korunuyor; Kesinti Kurtarma ekranında inceleyin.")
                                    emit_progress(cat, f"{uid} / {art.name}", outcome="failed")
                                    continue
                            if record["status"] != "PENDING" or output.exists() or output.is_symlink():
                                raise petek_engine.MaskError(
                                    "Şüpheli eski/tamamlanmamış çıktı: kesinti kurtarma veya inceleme gerekli."
                                )
                            if petek_engine.digest(source_path) != source_sha:
                                raise petek_engine.MaskError("Orijinal şablon üretim öncesi değiştirildi.")

                            render_context = {
                                "key": key, "output": output, "category": cat,
                                "mask_sha": mask_sha,
                                "uid": uid, "art": art, "group": group, "sku": sku,
                                "source_path": source_path, "source_sha": source_sha,
                                "original_art": original_art, "art_sha": art_sha,
                                "render_args": {
                                    "engine_type": item["engine_type"],
                                    "source_path": source_path,
                                    "render_art": render_art,
                                    "artwork_raster": artwork_raster,
                                    "source_scene": source_scene,
                                    "mask": mask,
                                    "item": item,
                                    "placement": placement,
                                    "lighting": lighting,
                                    "active_corner_radius": active_corner_radius,
                                    "glass_effect": glass_effect,
                                    "sunlight_profile": sunlight_profile,
                                    "petek_slot_mode": petek_slot_mode,
                                    "petek_pink_cleanup": petek_pink_cleanup,
                                    "petek_realism_profile": petek_realism_profile,
                                },
                            }
                            if render_executor is None:
                                _finish_render(render_context, _render_task(render_context))
                            else:
                                pending_renders.append((
                                    render_context,
                                    render_executor.submit(_render_task, render_context),
                                ))
                                if len(pending_renders) >= render_workers:
                                    _drain_one_render()
                        except (petek_engine.MaskError, cv2.error, OSError, ValueError) as exc:
                            self.ledger.quarantine(key, str(exc))
                            stats["rejected"] += 1
                            stats["errors"].append(
                                {"category": cat, "template": uid, "design": art.name,
                                 "store": group,
                                 "design_path": str(art), "source_path": str(source_path),
                                 "error_code": str(exc).split(':', 1)[0],
                                 "processing_stage": "URETIM_CIKTISI",
                                 "reason": str(exc), "traceback": traceback.format_exc()}
                            )
                            notify(f"ATLANDI [{cat}] {uid}/{art.name} — {exc}")
                            emit_progress(cat, f"{uid} / {art.name}", outcome="failed")

            # Finish all in-flight render workers before any post-processing.
            # This keeps stop/resume and the 4K hand-off deterministic while
            # allowing the expensive native render stage to overlap.
            while pending_renders:
                _drain_one_render()

            # PETEK overlay stage now runs concurrently with rendering (see _overlay_submit).
            # It still starts from the clean SHA-verified artifact only, so it cannot
            # chain 96 -> 116 -> 136 or mutate the original.
            if four_active and not self.cancel.is_set():
                clean_keys_now = set(stats.get("current_batch_keys", []))
                for row in self.ledger.successful():
                    if (row["key"] in clean_keys_now and row.get("category") == "06_Petek_Kapama"
                            and str(row.get("artifact_kind") or "clean") == "clean"):
                        _make_four_final(row)
            if four_active:
                got = {(o.get("store"), o.get("design"), o.get("overlay_cm"))
                       for o in stats["current_batch_outputs"] if o.get("overlay_cm")}
                four_stats["missing"] = [
                    f"{design.name} · {store} · {four_mockup_mod.cm_number(cm)} cm ({uid})"
                    for store, mapping in four_slots.items() for design in designs_in_run
                    for cm, uid in mapping.items() if (store, design.name, cm) not in got]
            stats["four_mockup"] = four_stats
            if overlay_active:
                # Overlay work already overlapped the render stage.  Queue any
                # clean PETEK row not seen inline (for example resumed rows),
                # then commit every remaining result.  On STOP, unstarted
                # overlay jobs are dropped while running ones are committed
                # so no written derivative is left without a ledger receipt.
                if self.cancel.is_set():
                    for _entry in pending_overlays:
                        _entry[2].cancel()
                else:
                    clean_keys = set(stats.get("current_batch_keys", []))
                    for row in self.ledger.successful():
                        if (row["key"] in clean_keys and row.get("category") == "06_Petek_Kapama"
                                and str(row.get("artifact_kind") or "clean") == "clean"):
                            _overlay_submit(row["key"])
                _overlay_poll(block=True)
            if overlay_active and not self.cancel.is_set():
                overlay_stats["validation_errors"] = list((overlay_validation or {}).get("errors", []))
                overlay_stats["validation_warnings"] = list((overlay_validation or {}).get("warnings", []))
                overlay_stats["invalid_groups"] = list((overlay_validation or {}).get("invalid_groups", []))
                overlay_stats["group_counts"] = dict((overlay_validation or {}).get("group_counts", {}))
                overlay_started = overlay_clock["started"] or time.monotonic()
                overlay_stats["elapsed_seconds"] = round(time.monotonic() - overlay_started, 3)
                stats["overlay"] = overlay_stats
                if overlay_stats["errors"]:
                    stats["errors"].extend(overlay_stats["errors"])
                    # Overlay derivatives are a separate post-render stage.
                    # Do not add their four-measurement failures to the main
                    # production-job rejection counter; doing so makes
                    # successful + failed exceed the render plan.
                overlay_report = self.reports / f"PETEK_OVERLAY_RAPORU_{operation_id}.json"
                petek_engine.atomic_new_file(overlay_report, json.dumps({
                    "schema": 1, "operation_id": operation_id,
                    "status": "PARTIAL" if (overlay_stats["errors"] or overlay_stats.get("validation_errors")) else "PASS",
                    "counts": {key: int(overlay_stats.get(key, 0)) for key in ("planned", "completed", "successful", "skipped", "failed")},
                    "root": str(petek_overlay_root_path), "warning": overlay_stats.get("warning"),
                    "validation_errors": (overlay_validation or {}).get("errors", []),
                    "validation_warnings": (overlay_validation or {}).get("warnings", []),
                    "invalid_groups": (overlay_validation or {}).get("invalid_groups", []),
                    "group_counts": (overlay_validation or {}).get("group_counts", {}),
                    "selection_retries": overlay_stats.get("selection_retries", []),
                    "elapsed_seconds": overlay_stats.get("elapsed_seconds", 0),
                    "errors": overlay_stats["errors"], "outputs": overlay_stats["outputs"],
                }, ensure_ascii=False, indent=2).encode("utf-8"))
                stats["overlay_report"] = str(overlay_report)
            elif overlay_active:
                stats["overlay"] = overlay_stats | {"status": "STOPPED"}
                if overlay_stats["errors"]:
                    stats["errors"].extend(overlay_stats["errors"])

            # 4K is an explicitly selected, independent post-render step.
            # Failures do not invalidate normal clean 1200x1600 mockups.
            if upscale_4k and not self.cancel.is_set():
                upscale_started_at = time.monotonic()

                def emit_upscale_progress(payload):
                    """Route 4K counters to the live production card unchanged."""
                    done = int(payload.get("index") or 0)
                    total_jobs = int(payload.get("total") or 0)
                    elapsed_up = max(0.0, time.monotonic() - upscale_started_at)
                    eta_up = None
                    if done and done < total_jobs:
                        eta_up = elapsed_up * (total_jobs - done) / done
                    progress({"completed": done, "total": total_jobs, "index": done,
                              "stage": "4K upscale", "category": "4K",
                              "operation": str(payload.get("operation") or ""),
                              "outcome": str(payload.get("outcome") or "running"),
                              "elapsed_seconds": round(elapsed_up, 1),
                              "eta_seconds": round(eta_up, 1) if eta_up is not None else None,
                              "successful": int(payload.get("upscaled") or 0),
                              "failed": int(payload.get("failed") or 0),
                              "skipped": int(payload.get("reused") or 0),
                              "status": "RUNNING",
                              "report_dir": str(self.reports)})

                stats["upscale_4k"] = upscale_new_outputs(
                    newly_rendered, state_root=self.root, enabled=True,
                    model=upscale_model, exe=upscale_exe,
                    cancel=self.cancel, notify=notify,
                    progress=emit_upscale_progress,
                )
            else:
                stats["upscale_4k"] = {"status": "STOPPED" if self.cancel.is_set() else "DISABLED",
                                       "upscaled": 0, "failed": 0, "reused": 0}
            if stats["errors"]:
                error_report = self.reports / f"URETIM_INCELEME_{uuid.uuid4().hex}.json"
                for error in stats["errors"]:
                    error.setdefault("operation_id", operation_id)
                    error.setdefault("processing_stage", error.get("stage", "URETIM"))
                    error.setdefault("source_path", str(designs))
                    error.setdefault("traceback", "")
                codex_ready = (
                    f"HATA KODLARI: {', '.join(sorted({str(e.get('error_code') or 'URETIM_HATASI') for e in stats['errors']}))}\n"
                    f"İŞLEM: {operation_id}\nAŞAMA: üretim / tasarım döngüsü\n"
                    f"KAYNAK: {designs}\nDETAY: teknik nedenler report.json içindeki errors alanındadır.\n"
                    f"DURUM: {'sonraki dosyaya geçildi' if stats.get('rendered', 0) or stats.get('attempted', 0) else 'güvenli durdurma'}"
                )
                petek_engine.atomic_new_file(error_report, json.dumps(
                    {"schema": 2, "operation_id": operation_id, "error_report": str(error_report),
                     "error_codes": sorted({str(e.get("error_code") or "URETIM_HATASI") for e in stats["errors"]}),
                     "stage": "URETIM", "design_folder": str(designs), "external_mode": external_mode,
                     "settings": config, "counts": {"planned": progress_total, "attempted": stats["attempted"],
                         "produced": stats["rendered"], "successful": stats["rendered"], "failed": stats["rejected"],
                         "skipped": stats.get("reused", 0) + stats.get("duplicates_skipped_in_run", 0),
                         "pending": max(0, progress_total - progress_completed)},
                     "continued_after_error": True, "errors": stats["errors"],
                     "codex_ready_report": codex_ready}, ensure_ascii=False, indent=2).encode("utf-8"))
                stats["error_report"] = str(error_report)
                stats["error_report_open"] = str(error_report)
                stats["codex_ready_report"] = codex_ready
                notify(f"İNCELEME RAPORU: {error_report}")
            export_started = time.perf_counter()
            csv_path, xlsx_path, count = self.export()
            stage_timings["export_seconds"] = time.perf_counter() - export_started
            export_audit = getattr(self, "last_export_audit", {})
            export_rejected = int(len(export_audit.get("rejected_rendered_rows", [])))
            stats["export_verified_rows"] = int(export_audit.get("verified_export_rows", count))
            stats["export_review_required"] = export_rejected
            if export_rejected:
                # This is deliberately separate from ``stats["rejected"]``:
                # those counters describe this invocation, while export also
                # validates every historical RENDERED receipt.  Never claim a
                # locally ready batch when an older output is missing or has
                # changed on disk.
                stats["export_review_report"] = next(
                    (str(p) for p in sorted(
                        self.reports.glob("ORTAK_7_KATEGORI_SHA_INCELEME_*.json"),
                        key=lambda p: p.stat().st_mtime_ns,
                        reverse=True,
                    ) if p.is_file()),
                    None,
                )
            stats.update(
                status=(
                    "STOPPED"
                    if self.cancel.is_set()
                    else ("REVIEW_REQUIRED" if export_rejected
                          else ("PARTIAL" if stats["rejected"] else "LOCAL_READY"))
                ),
                csv=str(csv_path),
                xlsx=str(xlsx_path),
                total_registry_outputs=count,
                stage_timings={k: (round(float(v), 6) if v is not None else None)
                               for k, v in stage_timings.items()},
                stage_counts=dict(stage_counts),
            )
            stats["stage_timings"]["total_wall_seconds"] = round(
                time.perf_counter() - operation_started, 6)
            # The short, current-operation receipt is deliberately separate
            # from the historical seven-category Excel export.
            short_report = {
                "operation_id": operation_id,
                "status": stats["status"],
                "counts": {
                    "planned": int(progress_total),
                    "attempted": int(stats.get("attempted", 0)),
                    "produced": int(stats.get("rendered", 0)) + int(stats.get("reused", 0)),
                    "successful": int(stats.get("rendered", 0)),
                    "failed": int(stats.get("rejected", 0)),
                    "skipped": int(stats.get("reused", 0)) + int(stats.get("duplicates_skipped_in_run", 0)) + int(stats.get("user_removed", 0)),
                    "pending": max(0, int(progress_total) - int(progress_completed)),
                },
                "performance": {
                    "render_workers": int(stats.get("render_workers", 1)),
                    "worker_selection": stats.get("render_worker_selection"),
                    "machine_key": machine_key(),
                    "png_compression": int(stats.get("png_compression", 4)),
                    "gpu": {"enabled": False, "reason": "CPU-only verified production path"},
                    "code_fingerprint": _production_code_fingerprint(),
                    "stage_timings": stats.get("stage_timings", {}),
                    "stage_counts": stats.get("stage_counts", {}),
                    "seconds_per_attempt": round(
                        float(stats["stage_timings"]["total_wall_seconds"]) /
                        max(1, int(stats.get("attempted", 0))), 6),
                },
                "outputs": stats.get("current_batch_outputs", []),
                "overlay": stats.get("overlay", {"enabled": False}),
                "overlay_report": stats.get("overlay_report"),
                "technical_log": str(operation_log_path),
                "historical_excel": str(xlsx_path),
                "external_mode": external_mode,
                "error_report": stats.get("error_report"),
                "codex_ready_report": stats.get("codex_ready_report"),
            }
            petek_engine.atomic_new_file(operation_report_path,
                json.dumps(short_report, ensure_ascii=False, indent=2).encode("utf-8"))
            stats["operation_report"] = str(operation_report_path)
            petek_engine.atomic_new_file(operation_log_path,
                json.dumps({"operation_id": operation_id, "events": technical_events},
                           ensure_ascii=False, indent=2).encode("utf-8"))
            # External runs use an isolated, temporary ledger and restore the
            # central ledger before returning.  Preserve the exact
            # SHA-verified records for this operation in the result so the
            # GUI's post-render cloud/link phase does not query the restored
            # (and therefore unrelated) central ledger and end up with 0/0.
            current_keys = set(stats.get("current_batch_keys", []))
            stats["current_batch_rows"] = [
                dict(row) for row in self.ledger.successful()
                if row.get("key") in current_keys
            ]
            # Publish the final counters after export/report generation too;
            # this is the snapshot the UI keeps when the worker closes.
            emit_progress(operation="Rapor ve Excel doğrulanıyor", force=True)
            _history_finish(str(stats["status"]))
            checkpoint_record['status'] = (
                'STOPPED' if stats['status'] == 'STOPPED' else 'COMPLETED')
            checkpoint_record['progress'] = {
                'attempted': stats['attempted'],
                'rendered': stats['rendered'],
                'reused': stats['reused'],
                'duplicates_skipped': stats['duplicates_skipped_in_run'],
            }
            if not external_mode:
                write_checkpoint(self.root, checkpoint_record)
            return stats
        except Exception:
            # Interruption/error never marks a torn job as resumable. The
            # operator must inspect pending rows and recovery first.
            checkpoint_record['status'] = 'INTERRUPTED'
            _history_finish('INTERRUPTED')
            try:
                if not stats.get('error_report'):
                    fatal_report = self.reports / f"URETIM_INCELEME_{uuid.uuid4().hex}.json"
                    fatal_error = {
                        'error_code': 'URETIM_KRITIK_HATA',
                        'message': 'Üretim kritik hata nedeniyle kesildi.',
                        'processing_stage': 'URETIM_KRITIK_HATA',
                        'operation_id': operation_id,
                        'design_folder': str(designs),
                        'design_path': str(designs),
                        'traceback': traceback.format_exc(),
                    }
                    petek_engine.atomic_new_file(fatal_report, json.dumps({
                        'schema': 2, 'operation_id': operation_id,
                        'error_codes': ['URETIM_KRITIK_HATA'],
                        'stage': 'URETIM_KRITIK_HATA', 'design_folder': str(designs),
                        'counts': {'planned': progress_total, 'attempted': stats.get('attempted', 0),
                                   'produced': stats.get('rendered', 0), 'successful': stats.get('rendered', 0),
                                   'failed': stats.get('rejected', 0), 'skipped': stats.get('reused', 0),
                                   'pending': max(0, progress_total - progress_completed)},
                        'continued_after_error': False, 'errors': [fatal_error],
                        'codex_ready_report': 'Kritik üretim hatası; traceback ve gerçek neden errors alanındadır.'
                    }, ensure_ascii=False, indent=2).encode('utf-8'))
                    stats['error_report'] = str(fatal_report)
            except Exception:
                logging.exception('Unable to write fatal production error report')
            try:
                petek_engine.atomic_new_file(
                    operation_log_path,
                    json.dumps({"operation_id": operation_id, "events": technical_events,
                                "status": "INTERRUPTED"},
                               ensure_ascii=False, indent=2).encode("utf-8"))
            except (OSError, ValueError):
                logging.exception('Unable to write operation journal')
            if not external_mode:
                try:
                    write_checkpoint(self.root, checkpoint_record)
                except (OSError, ValueError):
                    logging.exception('Unable to mark interrupted checkpoint')
            raise
        finally:
            if render_executor is not None:
                render_executor.shutdown(wait=True, cancel_futures=False)
            if overlay_executor is not None:
                overlay_executor.shutdown(wait=True, cancel_futures=True)
            self.lock_path.unlink(missing_ok=True)
            if original_engine_state is not None:
                self.ledger, self.output, self.lock_path = original_engine_state
                if external_state_dir is not None:
                    import shutil
                    shutil.rmtree(external_state_dir, ignore_errors=True)

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
        verified_rows = []
        rejected_rows = []
        for row in rows:
            path = Path(row["output"])
            if (
                path.is_symlink()
                or not path.is_file()
                or petek_engine.digest(path) != row["output_sha"]
            ):
                if path.is_symlink():
                    failure_kind = "OUTPUT_UNSAFE_SYMLINK"
                elif not path.exists():
                    failure_kind = "OUTPUT_MISSING"
                elif not path.is_file():
                    failure_kind = "OUTPUT_NOT_A_FILE"
                else:
                    failure_kind = "OUTPUT_SHA_MISMATCH"
                rejected_rows.append(
                    {
                        "key": row["key"],
                        "category": row["category"],
                        "uid": row["uid"],
                        "art_name": row["art_name"],
                        "output": row["output"],
                        "receipt_sha": row["output_sha"],
                        "reason": "OUTPUT_MISSING_OR_SHA_MISMATCH",
                        "failure_kind": failure_kind,
                    }
                )
                continue
            verified_rows.append(row)
        rows = verified_rows
        # Keep the result on the batch object so ``run`` can make its final
        # status reflect historical ledger integrity as well as only the jobs
        # attempted in this invocation.  Previously a run with zero new
        # render errors could report LOCAL_READY while export had rejected
        # old/missing files and written a REVIEW_REQUIRED report.
        self.last_export_audit = {
            "status": "REVIEW_REQUIRED" if rejected_rows else "VERIFIED",
            "verified_export_rows": len(rows),
            "rejected_rendered_rows": rejected_rows,
            "outputs_not_marked_pass": bool(rejected_rows),
        }
        if rejected_rows:
            # Every audit is immutable, including repeated runs with missing outputs.
            report = self.reports / f"ORTAK_7_KATEGORI_SHA_INCELEME_{uuid.uuid4().hex}.json"
            petek_engine.atomic_new_file(
                report,
                json.dumps(
                    self.last_export_audit,
                    ensure_ascii=False,
                    indent=2,
                ).encode("utf-8"),
            )
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
