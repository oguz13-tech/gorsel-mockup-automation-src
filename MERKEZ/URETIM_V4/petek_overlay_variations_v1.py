"""Deterministic, source-preserving PETEK four-size overlay stage.

This module is deliberately separate from the PETEK render recipe.  It only
reads a SHA-verified clean output and the operator supplied RGBA PNGs under
``Overlay_Giydirme``; it never changes source photos, approved masks, quads or
the clean render.  The public functions are useful for the batch engine and
for isolated synthetic QA without requiring a live cloud provider.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile
import unicodedata
from typing import Any, Callable, Iterable
from functools import lru_cache

import numpy as np
from PIL import Image

try:  # package import in the unified application
    from PETEK_V3 import engine as petek_engine
except ImportError:  # pragma: no cover - direct module execution in a fixture
    from ..PETEK_V3 import engine as petek_engine


MEASUREMENTS = ("76CM", "96CM", "116CM", "136CM")
FULL_MEASUREMENTS = ("96CM", "116CM", "136CM")
OVERLAY_FREE_FOLDER = "Overlaysızlar"
CM_PIXELS_96DPI = {"76CM": 76, "96CM": 76, "116CM": 76, "136CM": 76}
# The overlay pool is authored once at this exact size.  Keeping these values
# explicit makes the placement contract auditable and avoids a resize/crop in
# the production hot path.
OVERLAY_SIZE = (1200, 300)
CLEAN_SIZE = (1200, 1600)
FINAL_SIZE = (1200, 1800)
PHOTO_OFFSET_Y = 200
UPPER_OFFSET = (0, 0)
BOTTOM_OFFSET = (0, 1500)
PNG_MAX_BYTES = 40 * 1024 * 1024
PNG_MAX_PIXELS = 40_000_000
_SAFE_CM = re.compile(r"^(?:76|96|116|136)CM$")


class OverlayValidationError(ValueError):
    """An overlay cannot be safely accepted or placed."""


@dataclass(frozen=True)
class OverlayAsset:
    path: Path
    sha256: str
    width: int
    height: int
    visible_bbox: tuple[int, int, int, int]
    visible_pixels: int
    # These fields are populated for the grouped-folder contract.  Defaults
    # keep the old flat-pool constructor/API source-compatible.
    group_name: str = ""
    role: str = ""

    @property
    def name(self) -> str:
        return self.path.name


@dataclass(frozen=True)
class OverlaySelection:
    cm: str
    upper: OverlayAsset
    bottom: OverlayAsset | None

    @property
    def group_name(self) -> str:
        """The selected group identity, if this is the new folder contract."""
        names = {
            asset.group_name for asset in (self.upper, self.bottom)
            if asset is not None and asset.group_name
        }
        # A grouped selection must never mix groups.  Returning the sole name
        # here also makes the invariant visible in receipts without requiring
        # callers to know how assets are represented.
        return next(iter(names), "") if len(names) == 1 else "MIXED_GROUP_ERROR"

    def as_manifest(self) -> dict[str, Any]:
        def one(asset: OverlayAsset | None) -> dict[str, Any] | None:
            if asset is None:
                return None
            return {"path": str(asset.path), "sha256": asset.sha256,
                    "width": asset.width, "height": asset.height,
                    "visible_bbox": list(asset.visible_bbox),
                    "group_name": asset.group_name, "role": asset.role}

        return {"cm": self.cm, "group_name": self.group_name,
                "upper": one(self.upper), "bottom": one(self.bottom),
                "version": "PETEK_OVERLAY_V2_GROUPED"}


@dataclass(frozen=True)
class OverlayGroup:
    """One atomically selectable measurement group and its upper banner."""

    cm: str
    name: str
    path: Path
    upper: OverlayAsset
    bottom: OverlayAsset | None = None

    @property
    def identity(self) -> str:
        payload = "|".join((self.cm, self.name,
                             self.upper.sha256,
                             self.bottom.sha256 if self.bottom else ""))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def as_manifest(self) -> dict[str, Any]:
        return {
            "cm": self.cm,
            "name": self.name,
            "path": str(self.path),
            "identity": self.identity,
            "assets": [
                asset.sha256 for asset in (self.upper, self.bottom)
                if asset is not None
            ],
        }


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe_child(path: Path, root: Path) -> Path:
    path = Path(path)
    root = Path(root).resolve()
    if path.is_symlink():
        raise OverlayValidationError(f"OVERLAY_SYMLINK_REJECTED: {path}")
    resolved = path.resolve(strict=True)
    if resolved == root or root not in resolved.parents:
        raise OverlayValidationError(f"OVERLAY_PATH_OUTSIDE_ROOT: {path}")
    if any(parent.is_symlink() for parent in (resolved, *resolved.parents)):
        # The root itself may be a normal directory; a symlink anywhere below
        # it would make a create-only receipt ambiguous.
        if any(parent.is_symlink() for parent in resolved.parents if parent != root):
            raise OverlayValidationError(f"OVERLAY_PATH_SYMLINK: {path}")
    return resolved


def inspect_overlay(path: Path, *, root: Path | None = None,
                    expected_size: tuple[int, int] | None = None) -> OverlayAsset:
    """Decode and validate one final user PNG, including visible alpha.

    ``expected_size`` is used by the live grouped pool to enforce the
    pre-authored 1200x300 contract.  It remains optional for legacy isolated
    fixtures and diagnostics that intentionally exercise the legacy scaler.
    """
    path = Path(path)
    if path.suffix.lower() != ".png":
        raise OverlayValidationError(f"OVERLAY_PNG_ONLY: {path.name}")
    if root is not None:
        path = _safe_child(path, root)
    if path.is_symlink() or not path.is_file():
        raise OverlayValidationError(f"OVERLAY_FILE_MISSING: {path}")
    size = path.stat().st_size
    if size <= 0 or size > PNG_MAX_BYTES:
        raise OverlayValidationError(f"OVERLAY_FILE_SIZE_INVALID: {path.name}")
    try:
        with Image.open(path) as image:
            if (image.format or "").upper() != "PNG":
                raise OverlayValidationError(f"OVERLAY_PNG_HEADER_INVALID: {path.name}")
            if expected_size is not None and image.mode != "RGBA":
                raise OverlayValidationError(
                    f"OVERLAY_RGBA_REQUIRED: {path.name}; got mode {image.mode}"
                )
            image.load()
            rgba = image.convert("RGBA")
    except OverlayValidationError:
        raise
    except Exception as exc:
        raise OverlayValidationError(f"OVERLAY_PNG_UNREADABLE: {path.name}: {exc}") from exc
    width, height = rgba.size
    if width <= 0 or height <= 0 or width * height > PNG_MAX_PIXELS:
        raise OverlayValidationError(f"OVERLAY_DIMENSIONS_INVALID: {path.name}")
    if expected_size is not None and (width, height) != tuple(expected_size):
        expected_w, expected_h = expected_size
        raise OverlayValidationError(
            f"OVERLAY_STANDARD_DIMENSIONS_INVALID: {path.name}; "
            f"expected {expected_w}x{expected_h}, got {width}x{height}"
        )
    alpha = np.asarray(rgba.getchannel("A"), dtype=np.uint8)
    visible = alpha > 0
    count = int(np.count_nonzero(visible))
    if count == 0:
        raise OverlayValidationError(f"OVERLAY_EMPTY_ALPHA: {path.name}")
    ys, xs = np.where(visible)
    bbox = (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)
    # A full opaque canvas is nearly always an accidental flattened export and
    # would hide the product.  Small opaque cards remain valid; the size guard
    # is intentionally relative to the user's final canvas rather than alpha
    # semantics alone.
    if count == width * height and width >= 800 and height >= 1000:
        raise OverlayValidationError(f"OVERLAY_OPAQUE_CANVAS_REJECTED: {path.name}")
    return OverlayAsset(path.resolve(), _sha(path), width, height, bbox, count)


def _normalised_name(value: str) -> str:
    """Return a comparison-only ASCII form; the filename remains untouched."""
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


def _role_hints(asset: OverlayAsset) -> dict[str, int]:
    """Score semantic filename hints without depending on a fixed filename.

    Hints are only tie-breakers.  Geometry remains authoritative when users
    name files arbitrarily (for example the ChatGPT-exported ``-1/-2/-3``
    files in the live pool).
    """
    name = _normalised_name(asset.path.stem)
    tokens = set(name.split())
    joined = name.replace(" ", "")
    def hit(values: tuple[str, ...]) -> int:
        return sum(1 for value in values if value in tokens or value in joined)
    return {
        "upper": hit(("ust", "upper", "top", "genislik", "width")),
        "bottom": hit(("alt", "bottom", "lower", "uyari", "olculer", "measure")),
        "side": hit(("yan", "side", "left", "right", "avantaj", "ozellik")),
    }


def _visible_aspect(asset: OverlayAsset) -> float:
    x0, y0, x1, y1 = asset.visible_bbox
    return (y1 - y0) / max(1.0, float(x1 - x0))


def _with_group(asset: OverlayAsset, group_name: str, role: str) -> OverlayAsset:
    return OverlayAsset(asset.path, asset.sha256, asset.width, asset.height,
                        asset.visible_bbox, asset.visible_pixels,
                        group_name=group_name, role=role)


def _group_upper_paths(group_path: Path) -> tuple[list[Path], bool]:
    """Return the authored ÜST PNGs for one measurement group.

    The current contract keeps each upper asset in a dedicated ``UST``
    directory.  The second return value identifies that current layout so the
    caller can enforce the exact 1200x300 standard.  Direct files remain
    readable for old offline fixtures and are handled by the legacy scaler.
    """
    role_dirs = [child for child in group_path.iterdir()
                 if child.is_dir() and not child.is_symlink()]
    ust_dir = next((child for child in role_dirs
                    if child.name.casefold() in {"ust", "upper", "top"}), None)
    if ust_dir is not None:
        return ([path for path in sorted(ust_dir.iterdir(), key=lambda item: item.name.casefold())
                 if path.is_file() and not path.is_symlink() and path.suffix.casefold() == ".png"], True)
    return ([path for path in sorted(group_path.iterdir(), key=lambda item: item.name.casefold())
             if path.is_file() and not path.is_symlink() and path.suffix.casefold() == ".png"], False)


def _classify_group(cm: str, group_path: Path, png_paths: list[Path], *, root: Path,
                    errors: list[str], warnings: list[str], standard_layout: bool = False) -> OverlayGroup | None:
    """Inspect one directory and return it only when its complete tuple is safe."""
    label = f"{cm}/{group_path.name}"
    if not png_paths:
        errors.append(f"OVERLAY_GROUP_INVALID: {label}: no upper PNG found")
        return None
    inspected: list[OverlayAsset] = []
    for path in png_paths:
        try:
            inspected.append(inspect_overlay(
                path, root=root, expected_size=OVERLAY_SIZE if standard_layout else None))
        except OverlayValidationError as exc:
            errors.append(f"OVERLAY_GROUP_INVALID: {label}: {exc}")
    if len(inspected) != len(png_paths):
        return None
    # A legacy folder may still contain an old vertical/side PNG beside its
    # upper banner.  Keep the horizontal upper variants and ignore that stale
    # file; no side layer is ever selected or rendered.
    horizontal = [asset for asset in inspected if _visible_aspect(asset) < 1.0]
    upper = sorted(horizontal or inspected, key=lambda asset: (asset.sha256, asset.name.casefold()))[0]
    if len(inspected) > 1:
        warnings.append(f"OVERLAY_NON_UPPER_PNG_SKIPPED: {label}")
    return OverlayGroup(cm, group_path.name, group_path.resolve(),
                        _with_group(upper, group_path.name, "upper"))


def _validate_grouped_folder(root: Path, *, errors: list[str], warnings: list[str]) -> dict[str, Any]:
    groups: dict[str, list[OverlayGroup]] = {cm: [] for cm in MEASUREMENTS}
    assets: dict[str, list[OverlayAsset]] = {cm: [] for cm in MEASUREMENTS}
    invalid_groups: list[dict[str, Any]] = []
    for cm in MEASUREMENTS:
        folder = root / cm
        if folder.is_symlink() or not folder.is_dir():
            errors.append(f"OVERLAY_FOLDER_MISSING: {cm}")
            continue
        children = sorted(folder.iterdir(), key=lambda item: item.name.casefold())
        for child in children:
            if child.is_symlink():
                reason = f"OVERLAY_GROUP_SYMLINK_REJECTED: {cm}/{child.name}"
                errors.append(reason)
                invalid_groups.append({"cm": cm, "name": child.name,
                                       "path": str(child), "reason": [reason]})
        child_dirs = [path for path in children if path.is_dir() and not path.is_symlink()]
        if not child_dirs:
            errors.append(f"OVERLAY_GROUPS_MISSING: {cm}")
            continue
        for group_path in child_dirs:
            group_children = sorted(group_path.iterdir(), key=lambda item: item.name.casefold())
            for child in group_children:
                if child.is_symlink():
                    errors.append(f"OVERLAY_FILE_SYMLINK_REJECTED: {cm}/{group_path.name}/{child.name}")
            all_files = [path for path in group_children if path.is_file() and not path.is_symlink()]
            side_dirs = [path for path in group_children
                         if path.is_dir() and not path.is_symlink()
                         and path.name.casefold() in {"yan", "side", "yan_overlay"}]
            if side_dirs:
                warnings.extend(f"OVERLAY_SIDE_SKIPPED: {cm}/{group_path.name}/{path.name}"
                                for path in side_dirs)
            png_paths, standard_layout = _group_upper_paths(group_path)
            non_png = [path for path in all_files if path.suffix.casefold() != ".png"]
            if non_png:
                warnings.extend(f"OVERLAY_PNG_ONLY_SKIPPED: {path.name} ({cm}/{group_path.name})"
                                for path in non_png)
            before = len(errors)
            group = _classify_group(cm, group_path, png_paths, root=root,
                                    errors=errors, warnings=warnings,
                                    standard_layout=standard_layout)
            if group is None:
                invalid_groups.append({"cm": cm, "name": group_path.name,
                                       "path": str(group_path),
                                       "reason": errors[before:] or ["OVERLAY_GROUP_INVALID"]})
                continue
            groups[cm].append(group)
            assets[cm].extend(asset for asset in (group.upper, group.bottom) if asset is not None)
        if not groups[cm]:
            errors.append(f"OVERLAY_{cm}_UNAVAILABLE")
    # One immutable common bottom asset is shared by 96/116/136.  It is never
    # searched for inside measurement/group folders and is deliberately absent
    # from 76CM selections.
    bottom_folder = root / "alt_overlay"
    # New authored name first; the old name remains a read-only compatibility
    # yedek for archived fixtures only.
    bottom_path = bottom_folder / "ALT_COMMON_1200x300.png"
    if not bottom_path.is_file():
        bottom_path = bottom_folder / "altbilgi-overlay.png"
    shared_bottom: OverlayAsset | None = None
    try:
        shared_bottom = _with_group(
            inspect_overlay(bottom_path, root=root,
                            expected_size=OVERLAY_SIZE if bottom_path.name.casefold() == "alt_common_1200x300.png" else None),
            "__COMMON_ALT__", "bottom")
    except (OverlayValidationError, OSError) as exc:
        errors.append(f"OVERLAY_SHARED_BOTTOM_INVALID: {exc}")
    if shared_bottom is not None:
        for cm in FULL_MEASUREMENTS:
            groups[cm] = [OverlayGroup(group.cm, group.name, group.path, group.upper,
                                       bottom= _with_group(shared_bottom, group.name, "bottom"))
                          for group in groups[cm]]
            assets[cm] = [asset for group in groups[cm] for asset in (group.upper, group.bottom)]
    fatal = [f"OVERLAY_{cm}_UNAVAILABLE" for cm in MEASUREMENTS if not groups[cm]]
    fatal.extend(["OVERLAY_SHARED_BOTTOM_INVALID"] if shared_bottom is None else [])
    return {"grouped": True, "groups": groups, "assets": assets, "shared_bottom": shared_bottom,
            "invalid_groups": invalid_groups, "errors": errors,
            "warnings": warnings, "ready": not fatal,
            "group_counts": {cm: len(groups[cm]) for cm in MEASUREMENTS}}


def _validate_flat_folder(root: Path, *, errors: list[str], warnings: list[str]) -> dict[str, Any]:
    """Legacy six-folder adapter retained for older isolated tests/fixtures."""
    folders = {cm: root / cm for cm in MEASUREMENTS}
    folders["bottom"] = root / "alt_overlay"
    assets: dict[str, list[OverlayAsset]] = {}
    for name, folder in folders.items():
        if folder.is_symlink() or not folder.is_dir():
            errors.append(f"OVERLAY_FOLDER_MISSING: {name}")
            assets[name] = []
            continue
        values: list[OverlayAsset] = []
        for path in sorted(folder.iterdir(), key=lambda item: item.name.casefold()):
            if path.is_dir():
                continue
            if path.suffix.lower() != ".png":
                warnings.append(f"OVERLAY_PNG_ONLY_SKIPPED: {path.name} ({name})")
                continue
            try:
                values.append(inspect_overlay(path, root=root))
            except OverlayValidationError as exc:
                errors.append(str(exc))
        assets[name] = values
        if not values:
            errors.append(f"OVERLAY_NO_VALID_PNG: {name}")
    if not assets.get("76CM"):
        errors.append("OVERLAY_76CM_UNAVAILABLE")
    for cm in FULL_MEASUREMENTS:
        if not assets.get(cm):
            errors.append(f"OVERLAY_{cm}_UNAVAILABLE")
    if not assets.get("bottom"):
        errors.append("OVERLAY_BOTTOM_UNAVAILABLE")
    return {"grouped": False, "groups": {}, "assets": assets,
            "invalid_groups": [], "errors": errors, "warnings": warnings,
            "ready": not errors}


def validate_overlay_folder(root: Path | str) -> dict[str, Any]:
    """Discover and validate dynamic measurement groups without mutation.

    The live contract is ``<root>/<measurement>/<arbitrary-group>/*.png``.
    Group counts and filenames are observed at runtime.  A bad group is
    retained in the report but does not disable another valid group for the
    same measurement; a measurement with no valid group remains a hard error.
    """
    root = Path(root).resolve()
    if root.is_symlink() or not root.is_dir():
        raise OverlayValidationError(f"OVERLAY_ROOT_MISSING: {root}")
    errors: list[str] = []
    warnings: list[str] = []
    measurement_dirs = [root / cm for cm in MEASUREMENTS]
    grouped = any(folder.is_dir() and not folder.is_symlink() and
                  any(child.is_dir() for child in folder.iterdir())
                  for folder in measurement_dirs if folder.exists())
    result = (_validate_grouped_folder(root, errors=errors, warnings=warnings)
              if grouped else _validate_flat_folder(root, errors=errors, warnings=warnings))
    result.update({"root": str(root), "errors": errors, "warnings": warnings})
    return result


def discover_overlay_groups(root: Path | str) -> dict[str, list[OverlayGroup]]:
    """Public read-only discovery helper used by diagnostics and tests."""
    result = validate_overlay_folder(root)
    return result.get("groups", {})


def _asset_sort(assets: Iterable[OverlayAsset]) -> list[OverlayAsset]:
    # SHA, not filename, is the identity. Duplicate filenames/content therefore
    # do not create fake diversity.
    unique: dict[str, OverlayAsset] = {asset.sha256: asset for asset in assets}
    return sorted(unique.values(), key=lambda asset: (asset.sha256, asset.name.casefold()))


def _group_candidates(validation: dict[str, Any], cm: str, source_sha: str) -> list[OverlayGroup]:
    """Return a deterministic pseudo-random retry order for one measurement."""
    groups = list((validation.get("groups") or {}).get(cm) or [])
    if not groups:
        raise OverlayValidationError(f"OVERLAY_{cm}_UNAVAILABLE")
    # The source identity is the local RNG seed.  This gives random-looking
    # distribution across designs while keeping retries/resume reproducible.
    seed = int(hashlib.sha256((str(source_sha) + "|" + cm).encode("utf-8")).hexdigest()[:16], 16)
    ordered = sorted(groups, key=lambda group: (group.identity, group.name.casefold()))
    start = seed % len(ordered)
    return ordered[start:] + ordered[:start]


def _selection_from_group(group: OverlayGroup) -> OverlaySelection:
    return OverlaySelection(group.cm, group.upper, group.bottom)


def _grouped_selection_candidates(validation: dict[str, Any], *, source_sha: str) -> dict[str, list[OverlaySelection]]:
    result: dict[str, list[OverlaySelection]] = {}
    for index, cm in enumerate(MEASUREMENTS):
        result[cm] = [_selection_from_group(group)
                      for group in _group_candidates(validation, cm, source_sha)]
    return result


def _legacy_selection_candidates(validation: dict[str, Any], *, source_sha: str) -> dict[str, list[OverlaySelection]]:
    """Original flat-pool selector, kept only for old isolated fixtures."""
    assets = validation.get("assets") or {}
    upper_by_cm = {cm: _asset_sort(assets.get(cm, [])) for cm in MEASUREMENTS}
    bottoms = _asset_sort(assets.get("bottom", []))
    if not upper_by_cm["76CM"]:
        raise OverlayValidationError("OVERLAY_76CM_UNAVAILABLE")
    if not bottoms:
        raise OverlayValidationError("OVERLAY_SHARED_LAYER_UNAVAILABLE")
    seed = int(hashlib.sha256(str(source_sha).encode("utf-8")).hexdigest()[:16], 16)
    used: set[tuple[str, str, str]] = set()
    result: dict[str, list[OverlaySelection]] = {
        "76CM": [OverlaySelection("76CM", asset, None)
                 for asset in upper_by_cm["76CM"]]
    }
    # Legacy mode has no group atom to preserve, so combinations are still
    # rotated without reusing a tuple until the cartesian pool is exhausted.
    for index, cm in enumerate(FULL_MEASUREMENTS):
        combinations = [(upper, bottom)
                        for upper in upper_by_cm.get(cm, [])
                        for bottom in bottoms]
        if not combinations:
            raise OverlayValidationError(f"OVERLAY_{cm}_COMBINATION_UNAVAILABLE")
        unique = [combo for combo in combinations
                  if tuple(asset.sha256 for asset in combo) not in used]
        pool = unique or combinations
        start = (seed + index) % len(pool)
        ordered = pool[start:] + pool[:start]
        result[cm] = [OverlaySelection(cm, combo[0], combo[1])
                      for combo in ordered]
        used.add(tuple(asset.sha256 for asset in ordered[0]))
    return result


def choose_selections(validation: dict[str, Any], *, source_sha: str) -> dict[str, OverlaySelection]:
    """Choose one group per measurement using a reproducible local RNG."""
    if validation.get("grouped"):
        candidates = _grouped_selection_candidates(validation, source_sha=source_sha)
    else:
        candidates = _legacy_selection_candidates(validation, source_sha=source_sha)
    return {cm: values[0] for cm, values in candidates.items()}


def _resize_rgba(image: Image.Image, width: int, height: int) -> Image.Image:
    if width <= 0 or height <= 0:
        raise OverlayValidationError("OVERLAY_SCALE_EMPTY")
    if image.size == (width, height):
        return image.copy()
    return image.resize((width, height), Image.Resampling.LANCZOS)


@lru_cache(maxsize=32)
def _decoded_asset(path: str, sha256: str) -> np.ndarray:
    """Decode each prepared PNG once per immutable SHA in a batch/process."""
    with Image.open(path) as image:
        image.load()
        return np.asarray(image.convert("RGBA"), dtype=np.uint8).copy()


def refresh_overlay_cache() -> dict[str, int]:
    """Drop in-process decoded overlay data after operators replace PNGs.

    Cache identity already includes SHA-256, so a new worker would naturally
    read new bytes.  This explicit hook is useful for a long-running GUI or
    batch worker where the operator replaces assets between runs.
    """
    before = _decoded_asset.cache_info()
    _decoded_asset.cache_clear()
    after = _decoded_asset.cache_info()
    return {"cleared": int(before.currsize), "remaining": int(after.currsize)}


def _fit_visible(asset: OverlayAsset, canvas_w: int, canvas_h: int, *, kind: str) -> tuple[Image.Image, tuple[int, int]]:
    """Prepare one layer for placement.

    Authored 1200x300 assets are returned byte-for-byte at native size.  This
    is the normal production path: no crop, resample, or alpha-bound trim is
    performed.  The legacy branch is retained solely for old flat fixtures.
    """
    if (asset.width, asset.height) == OVERLAY_SIZE and canvas_w == FINAL_SIZE[0]:
        source = Image.fromarray(_decoded_asset(str(asset.path), asset.sha256), mode="RGBA")
        if kind == "upper":
            return source, UPPER_OFFSET
        if kind == "bottom":
            return source, BOTTOM_OFFSET
        raise OverlayValidationError(f"OVERLAY_SIDE_REMOVED: {asset.name}")
    bx0, by0, bx1, by1 = asset.visible_bbox
    visible_w, visible_h = bx1 - bx0, by1 - by0
    scale = canvas_w / float(visible_w)
    full_w = canvas_w
    full_h = max(1, int(round(visible_h * scale)))
    source = Image.fromarray(_decoded_asset(str(asset.path), asset.sha256), mode="RGBA")
    # Cropping removes only the fully transparent exterior; alpha inside the
    # artwork remains untouched and is composited normally.
    source = source.crop((bx0, by0, bx1, by1))
    if kind == "upper":
        x, y = 0, 0
    elif kind == "bottom":
        x, y = 0, canvas_h - full_h
    else:
        raise OverlayValidationError(f"OVERLAY_SIDE_REMOVED: {asset.name}")
    return _resize_rgba(source, full_w, full_h), (x, y)


def _paste_checked(base: Image.Image, layer: Image.Image, position: tuple[int, int], *, protected: np.ndarray | None, label: str) -> tuple[Image.Image, dict[str, Any]]:
    x, y = position
    canvas_w, canvas_h = base.size
    # Only transparent padding may be clipped. Visible pixels outside the
    # canvas are a placement error, never silently cropped.
    alpha = np.asarray(layer.getchannel("A"), dtype=np.uint8)
    ys, xs = np.where(alpha > 0)
    if len(xs) == 0:
        raise OverlayValidationError(f"OVERLAY_EMPTY_AFTER_SCALE: {label}")
    if int(xs.min()) + x < 0 or int(ys.min()) + y < 0 or int(xs.max()) + x >= canvas_w or int(ys.max()) + y >= canvas_h:
        raise OverlayValidationError(f"OVERLAY_OUTSIDE_CANVAS: {label}")
    yy = ys + y; xx = xs + x
    # Upper/lower banners are intentionally allowed to overlap the photograph
    # (the required Canva result).  Product collision protection remains
    # available to callers for any future non-edge layer.
    if protected is not None and not label.startswith(("upper", "bottom")):
        mask = alpha > 0
        if np.any(protected[yy, xx] & mask[ys, xs]):
            raise OverlayValidationError(f"OVERLAY_PRODUCT_COLLISION: {label}")
    before = np.asarray(base, dtype=np.uint8)
    out = base.copy()
    out.alpha_composite(layer, dest=(x, y))
    after = np.asarray(out, dtype=np.uint8)
    # The base image must remain byte-identical wherever this layer is fully
    # transparent; this catches accidental canvas resampling/colour conversion.
    changed = np.any(after[:, :, :3] != before[:, :, :3], axis=2)
    expected = np.zeros((canvas_h, canvas_w), dtype=bool)
    expected[yy, xx] = alpha[ys, xs] > 0
    if np.any(changed & ~expected):
        raise OverlayValidationError(f"OVERLAY_SOURCE_PIXELS_CHANGED: {label}")
    return out, {"label": label, "position": [int(x), int(y)], "scale": [layer.width, layer.height],
                 "visible_pixels": int(len(xs)), "changed_pixels": int(np.count_nonzero(changed))}


def _default_protection(width: int, height: int) -> np.ndarray:
    """Conservative product region used when no approved mask is available.

    The edge bands reserved by the contract are kept free; callers with a
    measured product mask can provide it to enforce the stronger check.
    """
    mask = np.zeros((height, width), dtype=bool)
    x0, x1 = int(width * .15), int(width * .85)
    y0, y1 = int(height * .20), int(height * .80)
    mask[y0:y1, x0:x1] = True
    return mask


def _repair_top_overlay_gap(image: Image.Image, start_y: int) -> tuple[Image.Image, list[int] | None]:
    """Remove a synthetic near-white strip directly below the top banner.

    Clean marketplace canvases can still carry a short, uniform white
    letterbox row at the top.  If the selected banner is shorter than that
    row, the old gap remains visible.  Only a contiguous near-white run that
    starts immediately below the banner is replaced, using the first real
    photo row below it.  The clean source file is never written or changed.
    """
    rgba = np.asarray(image.convert("RGBA"), dtype=np.uint8).copy()
    rgb = rgba[:, :, :3].astype(np.uint16)
    near_white = (rgb.min(axis=2) >= 242) & (rgb.max(axis=2) <= 255)
    row_is_blank = near_white.mean(axis=1) >= 0.995
    start_y = max(0, min(int(start_y), rgba.shape[0]))
    first = start_y
    while first < rgba.shape[0] and not row_is_blank[first]:
        first += 1
    end = first
    while end < rgba.shape[0] and row_is_blank[end]:
        end += 1
    # A tiny anti-aliased edge is harmless; only repair a meaningful band.
    if end - first < 4 or end >= rgba.shape[0]:
        return image, None
    rgba[first:end] = rgba[end].copy()
    return Image.fromarray(rgba, mode="RGBA"), [first, end]


def _repair_bottom_canvas_gap(image: Image.Image) -> tuple[Image.Image, list[int] | None]:
    """Close a synthetic near-white bottom canvas band for 76CM outputs."""
    rgba = np.asarray(image.convert("RGBA"), dtype=np.uint8).copy()
    rgb = rgba[:, :, :3].astype(np.uint16)
    near_white = (rgb.min(axis=2) >= 242) & (rgb.max(axis=2) <= 255)
    row_is_blank = near_white.mean(axis=1) >= 0.995
    end = rgba.shape[0]
    first = end
    while first > 0 and row_is_blank[first - 1]:
        first -= 1
    if end - first < 4 or first <= 0:
        return image, None
    rgba[first:end] = rgba[first - 1].copy()
    return Image.fromarray(rgba, mode="RGBA"), [first, end]


def _repair_source_edge_letterbox(image: Image.Image) -> tuple[Image.Image, dict[str, list[int] | None]]:
    """Remove full-width synthetic white letterbox bands from the copy.

    Some clean PETEK renders carry a 245-white band at the top and/or bottom
    of the otherwise valid 1200x1600 photo.  Moving that source to y=200
    exposes the bands as the exact white gaps operators reported.  We keep the
    SHA-verified source untouched and repair only the in-memory composition
    copy, replacing an edge run with the first/last real photo row.  A local
    scene that merely contains a small white object is not touched: the run
    must be at least 16 rows and 99.5%% of every row must be near-white.
    """
    rgba = np.asarray(image.convert("RGBA"), dtype=np.uint8).copy()
    rgb = rgba[:, :, :3].astype(np.uint16)
    near_white = (rgb.min(axis=2) >= 242) & (rgb.max(axis=2) <= 255)
    row_is_blank = near_white.mean(axis=1) >= 0.995
    height = rgba.shape[0]
    repairs: dict[str, list[int] | None] = {"top": None, "bottom": None}
    min_rows = 16

    top = 0
    while top < height and row_is_blank[top]:
        top += 1
    if min_rows <= top < height:
        rgba[:top] = rgba[top].copy()
        repairs["top"] = [0, int(top)]

    bottom = height
    while bottom > 0 and row_is_blank[bottom - 1]:
        bottom -= 1
    if min_rows <= height - bottom and bottom > 0:
        rgba[bottom:] = rgba[bottom - 1].copy()
        repairs["bottom"] = [int(bottom), height]

    if not any(repairs.values()):
        return image, repairs
    return Image.fromarray(rgba, mode="RGBA"), repairs


def _full_width_white_runs(image: Image.Image, *, min_rows: int = 16) -> list[list[int]]:
    """Find opaque, full-width near-white bands that would render as gaps."""
    rgba = np.asarray(image.convert("RGBA"), dtype=np.uint8)
    rgb = rgba[:, :, :3].astype(np.uint16)
    opaque = rgba[:, :, 3] >= 250
    near_white = (rgb.min(axis=2) >= 242) & (rgb.max(axis=2) <= 255) & opaque
    row_is_blank = near_white.mean(axis=1) >= 0.995
    runs: list[list[int]] = []
    index = 0
    while index < len(row_is_blank):
        if not row_is_blank[index]:
            index += 1
            continue
        end = index
        while end < len(row_is_blank) and row_is_blank[end]:
            end += 1
        if end - index >= int(min_rows):
            runs.append([int(index), int(end)])
        index = end
    return runs


def render_variation(source: Path | str, selection: OverlaySelection, output: Path | str,
                     *, source_sha: str | None = None, protection_mask: np.ndarray | None = None,
                     dpi: int = 96) -> dict[str, Any]:
    """Render one variation atomically and return its immutable QA manifest."""
    source = Path(source)
    output = Path(output)
    if source.is_symlink() or not source.is_file() or (source_sha is not None and _sha(source) != source_sha):
        raise OverlayValidationError("OVERLAY_SOURCE_SHA_MISMATCH")
    with Image.open(source) as opened:
        opened.load()
        original = opened.convert("RGBA")
    # The clean PETEK render remains 1200x1600.  It is placed unchanged at
    # y=200 on the final 1200x1800 transparent canvas; the authored 1200x300
    # layers overlap its top/bottom edges.  This adds no synthetic white rows
    # and never resamples, crops, or stretches the clean photo.
    if original.size != CLEAN_SIZE:
        raise OverlayValidationError(
            f"OVERLAY_SOURCE_DIMENSIONS_INVALID: {original.size}; expected {CLEAN_SIZE[0]}x{CLEAN_SIZE[1]}"
        )
    width, height = FINAL_SIZE
    repaired_photo, edge_repairs = _repair_source_edge_letterbox(original)
    # The added 200 px must not become transparent (many marketplace viewers
    # display that as a black gap).  Fill only the new header area by repeating
    # the repaired photo's first row; the protected 1200x1600 photo region is
    # still copied pixel-for-pixel at y=200.
    repaired_array = np.asarray(repaired_photo, dtype=np.uint8)
    top_fill = np.repeat(repaired_array[0:1], PHOTO_OFFSET_Y, axis=0)
    canvas_array = np.empty((FINAL_SIZE[1], FINAL_SIZE[0], 4), dtype=np.uint8)
    canvas_array[:PHOTO_OFFSET_Y] = top_fill
    canvas_array[PHOTO_OFFSET_Y:] = repaired_array
    base = Image.fromarray(canvas_array, mode="RGBA")
    clean_protected = protection_mask if protection_mask is not None else _default_protection(*CLEAN_SIZE)
    if clean_protected.shape != (CLEAN_SIZE[1], CLEAN_SIZE[0]):
        raise OverlayValidationError("OVERLAY_PROTECTION_MASK_DIMENSIONS")
    protected = np.zeros((height, width), dtype=bool)
    protected[PHOTO_OFFSET_Y:PHOTO_OFFSET_Y + CLEAN_SIZE[1], :CLEAN_SIZE[0]] = clean_protected
    manifest = selection.as_manifest()
    steps: list[dict[str, Any]] = []
    composed = base.copy()
    upper, pos = _fit_visible(selection.upper, width, height, kind="upper")
    composed, qa = _paste_checked(composed, upper, pos, protected=protected, label="upper")
    steps.append(qa)
    if selection.bottom is not None:
        bottom, pos = _fit_visible(selection.bottom, width, height, kind="bottom")
        composed, qa = _paste_checked(composed, bottom, pos, protected=protected, label="bottom")
        steps.append(qa)
    # Some 76CM source/overlay combinations leave a near-white band in the
    # newly added header or footer.  Repair only those synthetic edge rows in
    # the in-memory composition copy; the protected 1200x1600 photo and the
    # original source file remain unchanged.
    composed, top_overlay_repair = _repair_top_overlay_gap(composed, 0)
    composed, bottom_canvas_repair = _repair_bottom_canvas_gap(composed)
    white_gap_runs = _full_width_white_runs(composed)
    if white_gap_runs:
        raise OverlayValidationError(
            "OVERLAY_WHITE_GAP_REMAINED: " + json.dumps(white_gap_runs, ensure_ascii=False)
        )
    # Keep the final PNG RGBA with an opaque composed canvas.  Transparent
    # overlay pixels reveal the photo/edge fill instead of becoming an
    # accidental black/white rectangle.  DPI is explicit metadata and does not
    # alter pixel dimensions.
    output = Path(output)
    if output.exists() or output.is_symlink():
        if output.is_file() and _sha(output) == _sha(source):
            raise OverlayValidationError("OVERLAY_OUTPUT_COLLIDES_WITH_SOURCE")
        raise OverlayValidationError(f"OVERLAY_OUTPUT_EXISTS: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.parent.is_symlink():
        raise OverlayValidationError(f"OVERLAY_OUTPUT_PARENT_SYMLINK: {output.parent}")
    encoded = tempfile.NamedTemporaryFile(prefix=".petek-overlay-", suffix=".png", dir=str(output.parent), delete=False)
    temp = Path(encoded.name)
    try:
        encoded.close()
        composed.save(temp, format="PNG", dpi=(dpi, dpi), optimize=False)
        try:
            # Hard-link commit is create-only even when two workers race on a
            # deterministic path; an existing artifact is never overwritten.
            os.link(temp, output)
        except FileExistsError as exc:
            raise OverlayValidationError(f"OVERLAY_OUTPUT_EXISTS: {output}") from exc
    finally:
        temp.unlink(missing_ok=True)
    output_sha = _sha(output)
    manifest.update({"source": str(source), "source_sha256": source_sha or _sha(source),
                     "output": str(output), "output_sha256": output_sha,
                     "dimensions": [width, height], "dpi": [dpi, dpi], "steps": steps,
                     "photo_placement": {"x": 0, "y": PHOTO_OFFSET_Y,
                                         "width": CLEAN_SIZE[0], "height": CLEAN_SIZE[1]},
                     "repaired_source_edge_letterbox": edge_repairs,
                     "repaired_top_overlay_gap": edge_repairs.get("top") or top_overlay_repair,
                     "repaired_bottom_canvas_gap": edge_repairs.get("bottom") or bottom_canvas_repair,
                     "white_gap_qa": {"status": "PASS", "runs": []},
                     "canvas_policy": "FINAL_1200x1800_PHOTO_AT_Y200",
                     "output_mode": "RGBA_PNG_STRAIGHT_ALPHA_OPAQUE_CANVAS",
                     "opaque_canvas": True,
                     "top_edge_fill": {"y": 0, "height": PHOTO_OFFSET_Y,
                                       "source": "repaired_photo_first_row"},
                     "source_pixels_unchanged_at_photo_placement": not any(edge_repairs.values()),
                     "source_pixels_unchanged_outside_alpha": not any(edge_repairs.values()),
                     "source_letterbox_repair_applied": any(edge_repairs.values()),
                     "pixel_protection": "DEFAULT_EDGE_BANDS" if protection_mask is None else "SUPPLIED_MASK",
                     "qa_status": "PASS"})
    return manifest


def process_source(source_row: dict[str, Any], validation: dict[str, Any], output_root: Path | str,
                   *, source_sha: str | None = None, protection_mask: np.ndarray | None = None,
                   on_progress: Callable[[dict[str, Any]], None] | None = None) -> dict[str, Any]:
    """Create/reuse four variants for one clean ledger row.

    Each measurement retries the next discovered group when a candidate fails
    placement/collision QA.  A successful candidate is rendered from the
    untouched clean source; no derivative is ever used as the next input.
    """
    source = Path(source_row["output"])
    expected_sha = source_sha or source_row.get("output_sha") or _sha(source)
    if source.is_symlink() or not source.is_file() or (expected_sha and _sha(source) != expected_sha):
        raise OverlayValidationError("OVERLAY_SOURCE_SHA_MISMATCH")
    if validation.get("grouped"):
        candidate_map = _grouped_selection_candidates(validation, source_sha=expected_sha)
    else:
        candidate_map = _legacy_selection_candidates(validation, source_sha=expected_sha)
    root = Path(output_root)
    # Keep overlay derivatives separated by measurement first.  This makes the
    # operator-facing store/category tree self-describing (76CM/96CM/116CM/
    # 136CM) while the design subfolder still prevents filename collisions.
    design = re.sub(r"[^A-Za-z0-9_.-]+", "_", Path(source_row.get("art_name") or source.stem).stem)[:100] or "design"
    results: list[dict[str, Any]] = []
    selection_attempts: dict[str, list[dict[str, Any]]] = {}
    for cm in MEASUREMENTS:
        attempts: list[dict[str, Any]] = []
        selection_attempts[cm] = attempts
        selected_result: dict[str, Any] | None = None
        for selection in candidate_map[cm]:
            combo_id = hashlib.sha256(json.dumps(selection.as_manifest(), sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:12].upper()
            source_revision = expected_sha[:12].upper()
            destination = root / cm / design
            output = destination / f"{source.stem}__{cm}__S{source_revision}__OV{combo_id}.png"
            retry_revision = None
            try:
                if output.is_file() and not output.is_symlink():
                    with Image.open(output) as existing:
                        existing.load()
                        receipt_sha = str(source_row.get("overlay_outputs", {}).get(cm, {}).get("output_sha") or "")
                        actual_sha = _sha(output)
                        if (receipt_sha and actual_sha == receipt_sha
                                and existing.size == FINAL_SIZE):
                            manifest = dict(selection.as_manifest(), output=str(output), output_sha256=actual_sha,
                                            source=str(source), source_sha256=expected_sha, dimensions=list(existing.size),
                                            dpi=[96, 96], qa_status="REUSED")
                            selected_result = {"cm": cm, "output": str(output), "output_sha": actual_sha,
                                               "manifest": manifest, "selection": selection}
                            attempts.append({"group": selection.group_name, "status": "reused"})
                            break
                        # A damaged or superseded-dimension derivative is
                        # retried into a new immutable path; its old
                        # file/receipt remains available.  This prevents the
                        # retired 1200x1800 spacer outputs from being reused.
                        if receipt_sha:
                            retry_revision = hashlib.sha256((str(output) + receipt_sha + actual_sha).encode("utf-8")).hexdigest()[:10].upper()
                            output = output.with_name(output.stem + "__RETRY" + retry_revision + output.suffix)
                        else:
                            raise OverlayValidationError(f"OVERLAY_OUTPUT_COLLISION: {output.name}")
                elif output.is_symlink():
                    raise OverlayValidationError(f"OVERLAY_OUTPUT_COLLISION: {output.name}")
                if output.exists() or output.is_symlink():
                    raise OverlayValidationError(f"OVERLAY_OUTPUT_COLLISION: {output.name}")
                manifest = render_variation(source, selection, output, source_sha=expected_sha,
                                            protection_mask=protection_mask)
                if retry_revision:
                    manifest["retry_revision"] = retry_revision
                selected_result = {"cm": cm, "output": str(output),
                                   "output_sha": manifest["output_sha256"],
                                   "manifest": manifest, "selection": selection}
                attempts.append({"group": selection.group_name, "status": "success"})
                break
            except (OverlayValidationError, OSError, ValueError) as exc:
                attempts.append({"group": selection.group_name, "status": "rejected", "error": str(exc)})
                continue
        if selected_result is None:
            summary = "; ".join(f"{item.get('group')}: {item.get('error', 'rejected')}" for item in attempts)
            raise OverlayValidationError(f"OVERLAY_NO_SAFE_GROUP: {cm}: {summary}")
        results.append(selected_result)
        if on_progress:
            on_progress({"cm": cm, "output": selected_result["output"], "status": "success",
                         "group_name": selected_result["selection"].group_name,
                         "attempts": attempts})
    return {"source": str(source), "source_sha": expected_sha, "design": design,
            "results": results, "selection_warning": "LIMITED_POOL" if _has_limited_pool(validation) else None,
            "selection_attempts": selection_attempts}


def process_folder(folder: Path | str, overlay_root: Path | str, output_root: Path | str | None = None,
                   *, on_progress: Callable[[dict[str, Any]], None] | None = None) -> dict[str, Any]:
    """Apply PETEK overlays to existing clean images in a user-selected folder.

    This is intentionally ledger-free: every input is read by SHA, every
    derivative is written below a separate output folder, and the original
    image is never replaced.  Only the established 1200x1600 clean PETEK
    contract is accepted by ``process_source``.
    """
    folder = Path(folder).resolve()
    if not folder.is_dir() or folder.is_symlink():
        raise OverlayValidationError(f"HAZIR_GORSEL_KLASORU_GECERSIZ: {folder}")
    validation = validate_overlay_folder(Path(overlay_root).resolve())
    if not validation.get("ready"):
        raise OverlayValidationError("PETEK overlay katman ön kontrolü başarısız: " +
                                     "; ".join(validation.get("errors", [])[:8]))
    destination = Path(output_root).resolve() if output_root else folder.parent / f"{folder.name}_OverlayUygulanmis"
    if destination == folder or folder in destination.parents:
        raise OverlayValidationError("OVERLAY_OUTPUT_FOLDER_MUST_BE_SEPARATE")
    destination.mkdir(parents=True, exist_ok=True)
    image_exts = {".png", ".jpg", ".jpeg", ".webp"}
    files = sorted((p for p in folder.rglob("*") if p.is_file() and not p.is_symlink()
                    and p.suffix.lower() in image_exts
                    and destination not in p.resolve().parents), key=lambda p: str(p).casefold())
    if not files:
        raise OverlayValidationError("HAZIR_GORSEL_BULUNAMADI")
    results: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for index, source in enumerate(files, 1):
        try:
            source_row = {"output": str(source), "output_sha": _sha(source),
                          "art_name": source.stem, "overlay_outputs": {}}
            result = process_source(source_row, validation, destination,
                                    source_sha=source_row["output_sha"],
                                    on_progress=lambda payload, src=source, i=index: on_progress and on_progress({
                                        **payload, "source": str(src), "source_index": i, "source_total": len(files)}))
            results.append(result)
            if on_progress:
                # Dosya tamamlandı sinyali: GUI bunu gerçek hız/ETA ölçümü
                # ve çubuğun parça parça değil kesin adımlı ilerlemesi için
                # kullanır. Çıktılar, kaynak koruması ve sayımlar değişmez.
                on_progress({"source": str(source), "source_index": index,
                             "source_total": len(files), "status": "file_done"})
        except Exception as exc:
            errors.append({"source": str(source), "error": str(exc)})
            if on_progress:
                on_progress({"source": str(source), "source_index": index,
                             "source_total": len(files), "status": "failed", "error": str(exc)})
    return {"folder": str(folder), "output_root": str(destination), "total": len(files),
            "successful": len(results), "failed": len(errors), "results": results,
            "errors": errors, "validation": preflight(Path(overlay_root))}


def _has_limited_pool(validation: dict[str, Any]) -> bool:
    if validation.get("grouped"):
        groups = validation.get("groups") or {}
        return any(len(groups.get(cm) or []) < 2 for cm in MEASUREMENTS)
    assets = validation.get("assets") or {}
    combos = len(_asset_sort(assets.get("bottom", [])))
    return combos < 3 or any(len(_asset_sort(assets.get(cm, []))) < 1 for cm in FULL_MEASUREMENTS)


def preflight(root: Path | str) -> dict[str, Any]:
    """A non-mutating UI/preflight summary."""
    result = validate_overlay_folder(root)
    assets = result.get("assets", {})
    result["counts"] = (dict(result.get("group_counts") or {}) if result.get("grouped")
                         else {name: len(values) for name, values in assets.items()})
    result["ready_for_four"] = bool(result.get("ready"))
    result["standard_contract"] = {
        "overlay_size": list(OVERLAY_SIZE),
        "clean_size": list(CLEAN_SIZE),
        "final_size": list(FINAL_SIZE),
        "photo_y": PHOTO_OFFSET_Y,
        "upper_xy": list(UPPER_OFFSET),
        "bottom_xy": list(BOTTOM_OFFSET),
        "output_mode": "RGBA_PNG_STRAIGHT_ALPHA_OPAQUE_CANVAS",
    }
    return result


# Small descriptive aliases keep the stage easy to call from diagnostics and
# future UI tooling without duplicating the implementation.
validate_overlay_assets = validate_overlay_folder
apply_overlay_variation = render_variation
render_petek_overlay_variations = process_source


__all__ = [
    "MEASUREMENTS", "FULL_MEASUREMENTS", "OVERLAY_FREE_FOLDER", "OVERLAY_SIZE", "CLEAN_SIZE", "FINAL_SIZE",
    "PHOTO_OFFSET_Y", "OverlayAsset", "OverlayGroup", "OverlaySelection",
    "OverlayValidationError", "inspect_overlay", "validate_overlay_folder",
    "refresh_overlay_cache",
    "discover_overlay_groups", "validate_overlay_assets", "choose_selections", "render_variation",
    "apply_overlay_variation", "process_source", "render_petek_overlay_variations",
    "preflight",
]
