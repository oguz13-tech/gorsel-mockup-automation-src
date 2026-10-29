"""V4.0 Unlimited Human-Approved Template Discovery Across All 7 Categories.

Removes the old 10-template (2-per-category) restriction from Daily V2 while
keeping MERKEZ/GUNLUK/* byte-identical. Discovers ALL human-approved,
geometry-validated, SHA-verified templates across:
  1. 01_Wifi_Kutusu
  2. 02_Cam_Tablo_Dikey
  3. 02_Cam_Tablo_Yatay
  4. 03_Ahsap_Tablo
  5. 04_Cam_Dograma
  6. 05_Ocak_Arkasi
  7. 06_Petek_Kapama (via PETEK_V3 Registry + optional SQLite profiles)

Never mutates the live SQLite database or source template pools.
"""
from __future__ import annotations

import contextlib
import json
import math
import sqlite3
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any

from PETEK_V3 import engine as petek_engine
from PETEK_V3.registry import Registry as PetekRegistry
from petek_folders_v46 import petek_directory
from .manual_geometry import validated_legacy_manual_quad

LEGACY_SIX_CATEGORIES = (
    "01_Wifi_Kutusu",
    "02_Cam_Tablo_Dikey",
    "02_Cam_Tablo_Yatay",
    "03_Ahsap_Tablo",
    "04_Cam_Dograma",
    "05_Ocak_Arkasi",
)

ALL_SEVEN_CATEGORIES = LEGACY_SIX_CATEGORIES + ("06_Petek_Kapama",)

ORIENTATION_RULES = {
    "01_Wifi_Kutusu": "H",
    "02_Cam_Tablo_Dikey": "V",
    "02_Cam_Tablo_Yatay": "H",
    "03_Ahsap_Tablo": "V",
    "04_Cam_Dograma": None,
    "05_Ocak_Arkasi": "H",
    "06_Petek_Kapama": "H",
}

CATEGORY_SKU_PREFIXES = {
    "01_Wifi_Kutusu": "WFI",
    "02_Cam_Tablo_Dikey": "CTD",
    "02_Cam_Tablo_Yatay": "CTY",
    "03_Ahsap_Tablo": "AHT",
    "04_Cam_Dograma": "CMD",
    "05_Ocak_Arkasi": "OCA",
    "06_Petek_Kapama": "PDK",
}

CATEGORY_LABELS_TR = {
    "01_Wifi_Kutusu": "Dekoratif Ahşap Wi-Fi Kutusu",
    "02_Cam_Tablo_Dikey": "Temperli Cam Tablo Dikey",
    "02_Cam_Tablo_Yatay": "Temperli Cam Tablo Yatay",
    "03_Ahsap_Tablo": "Dekoratif Ahşap Tablo",
    "04_Cam_Dograma": "Cam Doğrama Görsel Kaplama",
    "05_Ocak_Arkasi": "Temperli Cam Ocak Arkası Koruyucu",
    "06_Petek_Kapama": "Dekoratif Ahşap Petek Dolabı",
}


def _resolve_template_source(runtime_root: Path, relative_path: str, expected_sha: str | None) -> Path:
    """Resolve the verified non-symlink source image from original backup or working pool."""
    parts = PurePosixPath(relative_path).parts
    if (
        len(parts) != 2
        or ".." in parts
        or "\\" in relative_path
        or ":" in relative_path
        or PurePosixPath(relative_path).is_absolute()
    ):
        raise ValueError("Güvensiz kaynak yolu: " + str(relative_path))

    candidates = [
        runtime_root / "2_SABLON_HAVUZU" / relative_path,
        runtime_root / "2_SABLON_HAVUZU_ORIJINAL_YEDEK" / relative_path,
    ]
    existing = []
    for candidate in candidates:
        if candidate.is_symlink():
            raise ValueError("Sembolik bağlantı şablon dosyası reddedildi: " + str(candidate))
        if candidate.is_file():
            existing.append(candidate)

    if not existing:
        raise ValueError("Şablon kaynak dosyası diskte bulunamadı: " + str(relative_path))

    if expected_sha:
        expected_lower = str(expected_sha).strip().lower()
        for candidate in existing:
            if petek_engine.digest(candidate).lower() == expected_lower:
                return candidate.resolve(strict=True)
        raise ValueError("Onaylı kaynak SHA256 diskteki şablonla eşleşmiyor.")

    return existing[0].resolve(strict=True)


def discover_all_approved_seven_categories(
    runtime_root: Path | None = None,
    *,
    petek_registry: PetekRegistry | None = None,
    categories: tuple[str, ...] | list[str] | None = None,
    per_category_limit: int | None = None,
    require_backup_copy: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Discover ALL human-approved eligible templates across all 7 categories.

    By default, `per_category_limit=None` removes the old 10-template limit so
    all human-approved templates across all 7 categories can enter batch production.
    """
    active_categories = tuple(categories or ALL_SEVEN_CATEGORIES)
    selected: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    counts: Counter = Counter()

    # 1. Discover approved templates from the 6 legacy SQLite categories (plus any SQLite 06_Petek_Kapama rows)
    if runtime_root is not None:
        runtime_root = Path(runtime_root).resolve()
        db_path = runtime_root / "SABLON_V2_MIMARI" / "ayarlar.db"
        if db_path.is_file() and not db_path.is_symlink():
            with contextlib.closing(
                sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True, timeout=10)
            ) as conn:
                conn.row_factory = sqlite3.Row
                check = conn.execute("PRAGMA quick_check(1)").fetchone()
                if not check or check[0] != "ok":
                    raise RuntimeError("SQLite veritabanı bütünlük kontrolünü geçemedi.")
                tables = {
                    r[0]
                    for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
                }
                if "template_profiles" in tables:
                    rows = [
                        dict(r)
                        for r in conn.execute(
                            "SELECT * FROM template_profiles WHERE is_active=1 ORDER BY category, template_uid"
                        )
                    ]
                    multiplicity = Counter(r["template_uid"] for r in rows)
                    for row in rows:
                        cat = str(row.get("category") or "")
                        uid = str(row.get("template_uid") or "")
                        if cat not in active_categories or cat not in ORIENTATION_RULES:
                            continue
                        try:
                            if multiplicity[uid] != 1:
                                raise ValueError("Aynı şablon için birden fazla aktif profil var")
                            if row.get("review_status") != "APPROVED" or int(row.get("manually_verified") or 0) != 1:
                                raise ValueError("İnsan onayı eksik (APPROVED & manually_verified=1 gerekli)")
                            if int(row.get("has_occlusion") or 0) != 0:
                                raise ValueError("Ön plan engeli işaretli")
                            orient = str(row.get("orientation") or "")
                            nominal = float(row.get("nominal_aspect") or 0.0)
                            if not math.isfinite(nominal) or not (0.12 <= nominal <= 12.0):
                                raise ValueError("Fiziksel en/boy oranı geçersiz")
                            if orient not in ("H", "V") or (orient == "H") != (nominal >= 1.0):
                                raise ValueError("Yön ile fiziksel oran tutarsız")
                            expected_orient = ORIENTATION_RULES.get(cat)
                            if expected_orient and orient != expected_orient:
                                raise ValueError(f"Kategori yönü uyumsuz ({orient} != {expected_orient})")
                            if cat == "04_Cam_Dograma":
                                raw_conf = row.get("component_confidences")
                                evidence = (
                                    json.loads(raw_conf)
                                    if isinstance(raw_conf, str) and raw_conf.strip()
                                    else (raw_conf or {})
                                )
                                marker = (evidence or {}).get("physical_orientation_verified")
                                verified = (
                                    marker.strip().lower() in ("1", "true", "yes")
                                    if isinstance(marker, str)
                                    else bool(marker)
                                )
                                if not verified:
                                    raise ValueError("04_Cam_Dograma fiziksel yön onayı eksik")
                            rel = str(row.get("source_relative_path") or "")
                            parts = PurePosixPath(rel).parts
                            if len(parts) != 2 or parts[0] != cat:
                                raise ValueError("Kaynak yolu kategori ile eşleşmiyor")
                            legacy_data = {}
                            if "templates" in tables:
                                legacy_rows = conn.execute(
                                    "SELECT data FROM templates WHERE category_id=? AND filename=?",
                                    (cat, parts[1]),
                                ).fetchall()
                                if len(legacy_rows) != 1:
                                    raise ValueError("templates tablosunda tekil kayıt bulunamadı")
                                legacy_data = json.loads(legacy_rows[0][0] or "{}")
                                if not isinstance(legacy_data, dict) or legacy_data.get("on_plan"):
                                    raise ValueError("Ön plan maskesi ayrıca inceleme gerektiriyor")
                            quad_raw = row.get("surface_quad")
                            quad = json.loads(quad_raw) if isinstance(quad_raw, str) else quad_raw
                            if (
                                not isinstance(quad, list)
                                or len(quad) != 4
                                or any(
                                    not isinstance(p, (list, tuple))
                                    or len(p) != 2
                                    or any(not math.isfinite(float(v)) for v in p)
                                    for p in quad
                                )
                            ):
                                raise ValueError("Geçersiz dört köşe koordinatı")
                            source_sha = str(row.get("source_asset_sha256") or "").strip()
                            if not source_sha:
                                raise ValueError("Kaynak SHA256 kaydı eksik")
                            source_file = _resolve_template_source(runtime_root, rel, source_sha)
                            if require_backup_copy:
                                backup_file = runtime_root / "2_SABLON_HAVUZU_ORIJINAL_YEDEK" / rel
                                if not backup_file.is_file() or backup_file.is_symlink():
                                    raise ValueError("Orijinal yedek kopyası eksik")
                            scene = petek_engine.read_bgr(source_file)
                            valid_quad = validated_legacy_manual_quad(quad, scene.shape)
                            if per_category_limit is not None and counts[cat] >= int(per_category_limit):
                                skipped.append(
                                    {
                                        "template_uid": uid,
                                        "category": cat,
                                        "reason": f"Kategori sınırı ({per_category_limit}) doldu",
                                    }
                                )
                                continue
                            counts[cat] += 1
                            selected.append(
                                {
                                    "uid": uid,
                                    "category": cat,
                                    "engine_type": "LEGACY_6_COVER",
                                    "source": str(source_file),
                                    "source_sha": petek_engine.digest(source_file),
                                    "relative": rel,
                                    "quad": valid_quad.astype(float).tolist(),
                                    "physical_aspect": float(nominal),
                                    "orientation": orient,
                                    "legacy_data": legacy_data,
                                }
                            )
                        except (ValueError, TypeError, KeyError, OSError, petek_engine.MaskError) as exc:
                            skipped.append({"template_uid": uid, "category": cat, "reason": str(exc)})

    # 2. Discover approved PETEK templates from PETEK_V3 Registry
    if "06_Petek_Kapama" in active_categories and petek_registry is not None:
        seen_uids = {item["uid"] for item in selected}
        for entry in petek_registry.list():
            uid = str(entry.get("uid") or "")
            if not uid or uid in seen_uids:
                continue
            if entry.get("status") != "APPROVED":
                skipped.append(
                    {
                        "template_uid": uid,
                        "category": "06_Petek_Kapama",
                        "reason": "PETEK şablonu henüz APPROVED değil (" + str(entry.get("status")) + ")",
                    }
                )
                continue
            try:
                source_file=None
                try:
                    profile, mask = petek_registry.get(uid, require_approved=True)
                    source_file = Path(profile["source"]).resolve(strict=True)
                except (petek_engine.MaskError,OSError) as exc:
                    stored=Path(str(entry.get("source") or ""))
                    if stored.exists() or stored.is_symlink() or runtime_root is None:
                        raise
                    # An old LAB path went missing. The approved record stays
                    # immutable; use an unambiguous working-pool photo ONLY
                    # if SHA and geometry match. No silent path migrations.
                    working=petek_directory(runtime_root,'2_SABLON_HAVUZU')
                    if not working.is_dir() or working.is_symlink():
                        raise petek_engine.MaskError('PETEK_CALISMA_KLASORU_YOK') from exc
                    matches=[]
                    for candidate in working.iterdir():
                        if (candidate.is_file() and not candidate.is_symlink() and
                                candidate.suffix.lower() in ('.png','.jpg','.jpeg','.webp') and
                                petek_engine.digest(candidate)==entry['source_sha']):
                            matches.append(candidate)
                    if len(matches)!=1:
                        raise petek_engine.MaskError(
                            'PETEK_ESKI_KAYNAK_ESLESMESI_GUVENSIZ: '+str(len(matches))+' eslesme') from exc
                    source_file=matches[0].resolve(strict=True)
                    profile, mask = petek_registry.get(
                        uid,require_approved=True,source_override=source_file)
                if per_category_limit is not None and counts["06_Petek_Kapama"] >= int(per_category_limit):
                    skipped.append(
                        {
                            "template_uid": uid,
                            "category": "06_Petek_Kapama",
                            "reason": f"Kategori sınırı ({per_category_limit}) doldu",
                        }
                    )
                    continue
                counts["06_Petek_Kapama"] += 1
                selected.append(
                    {
                        "uid": uid,
                        "category": "06_Petek_Kapama",
                        "engine_type": "PETEK_V3_CUTOUT",
                        "source": str(source_file),
                        "source_sha": str(profile["source_sha"]),
                        "mask_sha": str(profile["mask_sha"]),
                        "quad": profile["quad"],
                        "physical_aspect": float(profile["physical_aspect"]),
                        "orientation": "H" if float(profile["physical_aspect"]) >= 1.0 else "V",
                        "profile": profile,
                    }
                )
            except (petek_engine.MaskError, OSError, ValueError, KeyError) as exc:
                skipped.append(
                    {"template_uid": uid, "category": "06_Petek_Kapama", "reason": str(exc)}
                )

    audit = {
        "unlimited_mode": per_category_limit is None,
        "per_category_limit": per_category_limit,
        "selected_count": len(selected),
        "per_category_counts": dict(counts),
        "eligible_uids": [item["uid"] for item in selected],
        "skipped": skipped,
    }
    return selected, audit
