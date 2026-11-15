"""4 Farklı Mockup / 4 Farklı Final Görsel modu (Geliştirme 13).

Değişmez kural: varyasyon kimliği (76/96/116/136) mağazanın slotundan gelir.
Overlay dosyası yalnız etiketi belirler; kapalı olsa da kimlik değişmez.
Kod/barkod/model üretimi mevcut ``petek_measurement_codes`` ile yapılır.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont

VARIATIONS = ("76CM", "96CM", "116CM", "136CM")
PETEK_CATEGORY = "06_Petek_Kapama"
LABEL_FOLDER = "olcu_etiketleri"
_CM_TOKEN = re.compile(r"(?<!\d)(76|96|116|136)(?!\d)")
_FONT_CANDIDATES = ("segoeui.ttf", "arial.ttf", "calibri.ttf", "DejaVuSans.ttf")


class FourMockupError(ValueError):
    pass


def _natural(text: str):
    return [int(p) if p.isdigit() else p.casefold() for p in re.split(r"(\d+)", str(text))]


def cm_number(cm: str) -> str:
    value = str(cm).upper()
    return value[:-2] if value.endswith("CM") else value


def normalize_overlays(overlays: dict | None) -> dict[str, dict[str, Any]]:
    """Return one explicit spec per variation: enabled/path/allow_mismatch."""
    overlays = overlays or {}
    result = {}
    for cm in VARIATIONS:
        raw = overlays.get(cm) or overlays.get(cm_number(cm)) or {}
        path = raw.get("path")
        result[cm] = {
            "enabled": bool(raw.get("enabled", True)),
            "path": str(path) if path else None,
            "allow_mismatch": bool(raw.get("allow_mismatch", False)),
        }
    return result


def plan_slots(production_plan, pinned: dict | None = None, *, health=None, notes: list | None = None):
    """Pick 4 distinct approved PETEK templates per store, slot order 76→136.

    Never repeats a template and never borrows another store's template.
    ``health(item) -> (ok, reason)`` is the same deterministic template check
    production uses; unhealthy templates are never auto-selected (``notes``
    receives the reason) and a pinned unhealthy template is a pre-render error.
    Returns ``(slots, problems)``; slots = {store: {cm: uid}}.
    """
    slots: dict[str, dict[str, str]] = {}
    problems: list[str] = []

    def verdict(item):
        return health(item) if health else (True, "")

    for store, templates in production_plan:
        petek = {}
        for item in templates:
            if item.get("category") == PETEK_CATEGORY:
                petek.setdefault(str(item["uid"]), item)
        if pinned and store in pinned:
            chosen = [str(pinned[store].get(cm) or "") for cm in VARIATIONS]
            if len(set(chosen)) != 4 or any(uid not in petek for uid in chosen):
                missing = [u for u in chosen if u not in petek]
                problems.append(f"{store}: sabitlenmiş 4 şablon geçersiz/benzersiz değil"
                                + (f" (atamada yok: {', '.join(missing)})" if missing else ""))
                continue
            bad = [(uid, verdict(petek[uid])[1]) for uid in chosen if not verdict(petek[uid])[0]]
            if bad:
                problems.append(f"{store}: sağlıksız şablon — " + "; ".join(f"{u}: {r}" for u, r in bad)
                                + " (ayarlardan başka şablon seçin)")
                continue
        else:
            distinct, seen_sha = [], set()
            for uid in sorted(petek, key=_natural):
                if len(distinct) == 4:
                    break
                sha = str(petek[uid].get("source_sha", uid))
                if sha in seen_sha:
                    continue
                ok, reason = verdict(petek[uid])
                if not ok:
                    if notes is not None:
                        notes.append(f"{store}: {uid} otomatik seçimden çıkarıldı ({reason})")
                    continue
                seen_sha.add(sha)
                distinct.append(uid)
            if len(distinct) < 4:
                problems.append(f"{store}: yalnız {len(distinct)} benzersiz ve sağlıklı PETEK şablonu bulundu, 4 gerekli")
                continue
            chosen = distinct
        slots[store] = dict(zip(VARIATIONS, chosen))
    return slots, problems


def plan_slots_for_designs(production_plan, design_keys, pinned: dict | None = None, *,
                           health=None, notes: list | None = None):
    """Plan one distinct 4-template set per design and store.

    ``plan_slots`` is intentionally kept as the legacy/single-plan API.  The
    four-mockup production path uses this function so a store's complete
    approved PETEK pool remains available and each design receives a fresh,
    deterministic combination.  The first design honours a pinned selection;
    later designs choose the least-used templates and avoid a previously used
    4-tuple whenever the pool permits it.

    Returns ``(per_design, problems)`` where ``per_design[store][design_key]``
    maps ``76CM..136CM`` to template UID.
    """
    keys = [str(key) for key in design_keys]
    planned: dict[str, dict[str, dict[str, str]]] = {}
    problems: list[str] = []

    def verdict(item):
        return health(item) if health else (True, "")

    for store, templates in production_plan:
        petek: dict[str, dict] = {}
        for item in templates:
            if item.get("category") == PETEK_CATEGORY:
                petek.setdefault(str(item["uid"]), item)
        healthy: list[str] = []
        seen_sha: set[str] = set()
        for uid in sorted(petek, key=_natural):
            item = petek[uid]
            sha = str(item.get("source_sha", uid))
            if sha in seen_sha:
                continue
            ok, reason = verdict(item)
            if not ok:
                if notes is not None:
                    notes.append(f"{store}: {uid} otomatik seçimden çıkarıldı ({reason})")
                continue
            seen_sha.add(sha)
            healthy.append(uid)
        if len(healthy) < 4:
            problems.append(f"{store}: yalnız {len(healthy)} benzersiz ve sağlıklı PETEK şablonu bulundu, 4 gerekli")
            continue

        store_plan: dict[str, dict[str, str]] = {}
        used_counts = {uid: 0 for uid in healthy}
        used_combinations: set[tuple[str, ...]] = set()
        for index, key in enumerate(keys):
            chosen: list[str] | None = None
            if index == 0 and pinned and store in pinned:
                pinned_ids = [str(pinned[store].get(cm) or "") for cm in VARIATIONS]
                if len(set(pinned_ids)) != 4 or any(uid not in petek for uid in pinned_ids):
                    missing = [uid for uid in pinned_ids if uid not in petek]
                    problems.append(f"{store}: sabitlenmiş 4 şablon geçersiz/benzersiz değil"
                                    + (f" (atamada yok: {', '.join(missing)})" if missing else ""))
                    continue
                bad = [(uid, verdict(petek[uid])[1]) for uid in pinned_ids
                       if not verdict(petek[uid])[0]]
                if bad:
                    problems.append(f"{store}: sağlıksız şablon — "
                                    + "; ".join(f"{uid}: {reason}" for uid, reason in bad)
                                    + " (ayarlardan başka şablon seçin)")
                    continue
                if len({str(petek[uid].get("source_sha", uid)) for uid in pinned_ids}) != 4:
                    problems.append(f"{store}: sabitlenmiş 4 şablon aynı kaynak görseli tekrar ediyor")
                    continue
                chosen = pinned_ids

            if chosen is None:
                # Enumerate cyclic windows.  For pools larger than four this
                # yields a new tuple before wrapping; the score then balances
                # per-template use across the remaining candidates.
                candidates: list[tuple[tuple[int, int, tuple[str, ...]], tuple[str, ...]]] = []
                n = len(healthy)
                for offset in range(n):
                    combo = tuple(healthy[(offset + j) % n] for j in range(4))
                    if len(set(combo)) != 4:
                        continue
                    if combo in used_combinations and len(used_combinations) < max(1, n):
                        continue
                    score = (sum(used_counts[uid] for uid in combo),
                             max(used_counts[uid] for uid in combo), combo)
                    candidates.append((score, combo))
                if not candidates:
                    # Exactly four approved templates necessarily repeat as a
                    # tuple; this is not a shortage and is explicitly noted.
                    combo = tuple(healthy[:4])
                else:
                    combo = min(candidates, key=lambda pair: pair[0])[1]
                chosen = list(combo)

            used_combinations.add(tuple(chosen))
            for uid in chosen:
                used_counts[uid] += 1
            store_plan[key] = dict(zip(VARIATIONS, chosen))
        if store_plan:
            planned[store] = store_plan
    return planned, problems


def preflight(production_plan, *, design_count: int, pinned: dict | None = None,
              seconds_per_image: float | None = None, health=None) -> dict[str, Any]:
    notes: list[str] = []
    slots, problems = plan_slots(production_plan, pinned, health=health, notes=notes)
    stores = len(production_plan)
    outputs = design_count * len(slots) * 4
    return {
        "ready": not problems and bool(slots), "slots": slots, "problems": problems, "notes": notes,
        "stores": stores, "designs": design_count, "outputs": outputs,
        "formula": f"{design_count} tasarım × {len(slots)} mağaza × 4 = {outputs}",
        "estimated_seconds": round(outputs * seconds_per_image, 1) if seconds_per_image else None,
    }


def _font(size: int):
    for name in _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def default_label(cm: str, image_width: int) -> Image.Image:
    """Küçük ölçü etiketi; yalnız varyasyon kimliğinden üretilir."""
    text = f"Genişlik: {cm_number(cm)} cm"
    height = max(24, round(image_width * 0.042))
    font = _font(max(12, round(height * 0.56)))
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    left, top, right, bottom = probe.textbbox((0, 0), text, font=font)
    pad = round(height * 0.38)
    width = (right - left) + 2 * pad
    label = Image.new("RGBA", (width, height), (24, 28, 36, 235))
    ImageDraw.Draw(label).text((pad - left, (height - (bottom - top)) / 2 - top), text,
                               font=font, fill=(255, 255, 255, 255))
    return label


def check_overlay_name(cm: str, path: str | Path) -> str | None:
    """Dosya adındaki ölçü slotla çelişiyorsa açıklama döndürür."""
    tokens = set(_CM_TOKEN.findall(Path(path).stem))
    if tokens and cm_number(cm) not in tokens:
        return f"{Path(path).name} dosyası {'/'.join(sorted(tokens))} cm içeriyor, slot {cm_number(cm)} cm"
    return None


def label_pool(label_dir: Path | str | None, cm: str) -> list[Path]:
    """Ölçü havuzu: ``<label_dir>/<76CM>/**/*.png`` (alt klasörler dahil) (ayrıca düz klasörde ``overlay76*.png``)."""
    if not label_dir:
        return []
    base = Path(label_dir)
    files: dict[str, Path] = {}
    folder = base / cm
    if folder.is_dir() and not folder.is_symlink():
        for dirpath, dirs, names in os.walk(folder, followlinks=False):
            dirs[:] = sorted(d for d in dirs if d.casefold() not in {"yan", "side", "yan_overlay"}
                             and not (Path(dirpath) / d).is_symlink())
            for name in names:
                item = Path(dirpath) / name
                if item.suffix.casefold() == ".png" and not item.is_symlink():
                    files[str(item.relative_to(base)).casefold()] = item
    if base.is_dir():
        for item in base.glob(f"overlay{cm_number(cm)}*"):
            if item.is_file() and not item.is_symlink() and item.suffix.casefold() == ".png":
                files.setdefault(item.name.casefold(), item)
    return [files[name] for name in sorted(files)]


def pick_from_pool(pool: list[Path], pick_key: str, cm: str) -> Path:
    """Aynı tasarım+mağaza+ölçü her zaman aynı dosyayı seçer (devam/yeniden çalıştırma güvenli)."""
    digest = hashlib.sha256(f"{pick_key}|{cm}".encode("utf-8")).digest()
    return pool[int.from_bytes(digest[:8], "big") % len(pool)]


def resolve_label(cm: str, spec: dict, image_width: int, label_dir=None, pick_key: str = ""):
    """Return (RGBA image | None, manifest). Disabled → (None, off)."""
    if not spec.get("enabled", True):
        return None, {"kind": "off"}
    path = spec.get("path")
    kind = "custom"
    if not path:
        pool = label_pool(label_dir, cm)
        found = pick_from_pool(pool, pick_key, cm) if pool else None
        if found is None:
            image = default_label(cm, image_width)
            return image, {"kind": "default_generated", "text": f"Genişlik: {cm_number(cm)} cm",
                           "sha256": hashlib.sha256(image.tobytes()).hexdigest()}
        path, kind = str(found), "default_file"
    problem = check_overlay_name(cm, path)
    if problem and not spec.get("allow_mismatch"):
        raise FourMockupError("OVERLAY_OLCU_UYUSMAZLIGI: " + problem)
    with Image.open(path) as opened:
        opened.load()
        image = opened.convert("RGBA")
    max_w, max_h = round(image_width * 0.5), round(image_width * 0.25)
    if image.width > max_w or image.height > max_h:
        ratio = min(max_w / image.width, max_h / image.height)
        image = image.resize((max(1, round(image.width * ratio)), max(1, round(image.height * ratio))),
                             Image.LANCZOS)
    digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    return image, {"kind": kind, "file": Path(path).name, "sha256": digest,
                   "mismatch_allowed": bool(problem),
                   "pool_size": len(pool) if kind == "default_file" else 0}


def render_final_bytes(clean_png: bytes | Path | str, cm: str, spec: dict, *,
                       label_dir=None, pick_key: str = "", compression: int = 4) -> tuple[bytes, dict]:
    """Clean render + sağ alt köşe, sıfır kenar boşluğu. Overlay kapalıysa piksel aynen kalır."""
    if isinstance(clean_png, (bytes, bytearray)):
        source = Image.open(io.BytesIO(bytes(clean_png)))
    else:
        source = Image.open(clean_png)
    with source:
        source.load()
        base = source.convert("RGBA")
    label, manifest = resolve_label(cm, spec, base.width, label_dir, pick_key)
    if label is not None:
        x, y = base.width - label.width, base.height - label.height
        base.alpha_composite(label, (x, y))
        manifest["position"] = [x, y]
    out = base.convert("RGB")
    buffer = io.BytesIO()
    out.save(buffer, format="PNG", compress_level=max(0, min(9, int(compression))))
    manifest.update(mode="four_mockup", cm=cm)
    return buffer.getvalue(), manifest


def final_name(clean_name: str, cm: str) -> str:
    stem = Path(clean_name).stem
    return f"{stem}__W{cm_number(cm)}.png"


def final_key(source_key: str, cm: str, manifest: dict) -> str:
    return hashlib.sha256((str(source_key) + "|" + cm + "|" +
                           json.dumps(manifest, sort_keys=True, ensure_ascii=False)).encode("utf-8")).hexdigest()[:24]


def pixels_equal_outside_label(clean: np.ndarray, final: np.ndarray, label_box: tuple[int, int]) -> bool:
    """Test yardımcısı: etiket dışındaki piksellerin korunduğunu doğrular."""
    x, y = label_box
    mask = np.ones(clean.shape[:2], bool)
    mask[y:, x:] = False
    return bool(np.array_equal(clean[mask], final[mask]))
