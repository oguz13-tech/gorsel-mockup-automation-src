# -*- coding: utf-8 -*-
"""G2 private, read-only quality evidence and review-folder inspection.

Never changes the review workspace, template DB, images, or approved masks.
Reports are facts/candidates, NOT automatic quality approvals.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Mapping

from PIL import Image, ImageChops, ImageStat

IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".webp", ".bmp", ".avif"})
GLASS = frozenset({"02_Cam_Tablo_Dikey", "02_Cam_Tablo_Yatay", "04_Cam_Dograma", "05_Ocak_Arkasi"})
CATEGORIES = frozenset({"01_Wifi_Kutusu", *GLASS, "03_Ahsap_Tablo", "06_Petek_Kapama"})


def _hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1048576), b""):
            h.update(block)
    return h.hexdigest()


def _safe_image(path: Path) -> Path:
    path = Path(path).absolute()
    for p in (path, *path.parents):
        if p.is_symlink():
            raise ValueError("SYMLINK_OR_REDIRECT_NOT_ALLOWED: " + str(p))
        if p.exists() and getattr(p.lstat(), "st_reparse_tag", 0) in (0xA0000003, 0xA000000C):
            raise ValueError("WINDOWS_JUNCTION_NOT_ALLOWED: " + str(p))
    if not path.is_file() or path.suffix.lower() not in IMAGE_EXTENSIONS:
        raise ValueError("NOT_A_SUPPORTED_IMAGE: " + str(path))
    return path


def inventory_review_folder(runtime_root: Path, selected_folder: Path, category: str) -> dict:
    """Inspect an explicitly selected review folder; never import or approve it.

    The folder must be the private runtime's KONTROL_GEREKENLER subtree,
    so accidentally selecting a user's unrelated folder cannot expose names
    to reports in the runtime workspace.
    """
    root = Path(runtime_root).resolve()
    folder = Path(selected_folder).absolute()
    for p in (folder, *folder.parents):
        if p.is_symlink():
            raise ValueError("SYMLINK_NOT_ALLOWED")
    folder = folder.resolve(strict=True)
    if category not in CATEGORIES:
        raise ValueError("UNKNOWN_CATEGORY")
    if not folder.is_dir():
        raise ValueError("REVIEW_FOLDER_NOT_FOUND")
    if not any(p.name.upper() == "KONTROL_GEREKENLER" for p in (folder, *folder.parents)):
        raise ValueError("ONLY_REVIEW_FOLDERS_CAN_BE_SELECTED")
    if not folder.is_relative_to(root):
        raise ValueError("REVIEW_FOLDER_OUTSIDE_RUNTIME")

    working = root / "2_SABLON_HAVUZU" / category
    backup = root / "2_SABLON_HAVUZU_ORIJINAL_YEDEK" / category
    files = []
    for p in sorted(folder.iterdir(), key=lambda x: x.name.casefold()):
        if p.is_symlink() or not p.is_file() or p.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        # Work with only this selected folder. Child folders are not scanned
        # recursively, because users must explicitly choose the next folder.
        matches = []
        for pool_name, pool in (("WORKING", working), ("ORIGINAL", backup)):
            if not pool.is_dir():
                continue
            for match in pool.iterdir():
                if match.is_file() and not match.is_symlink() and match.stem.casefold() == p.stem.casefold() and match.suffix.lower() in IMAGE_EXTENSIONS:
                    matches.append({"pool": pool_name, "name": match.name, "sha256": _hash(match), "identical_content": _hash(match) == _hash(p)})
        # No automatic source equality: the file could be different bytes.
        files.append({"filename": p.name, "bytes": p.stat().st_size, "sha256": _hash(p), "matches_by_name_only": matches, "review_required": True})
    return {"category": category, "folder": str(folder), "read_only": True, "auto_approved": 0, "auto_moved": 0, "count": len(files), "files": files,
            "next_action": "Dört köşe inceleme ekranında kaynağı ve SHA değerini doğrulayın. Dosyalar otomatik aktarılmadı."}


def evaluate_golden_case(case: Mapping, private_root: Path) -> dict:
    """Make objective observations only. Never call a case APPROVED.

    Same-sized source/render with an exact provided 8-bit grayscale mask can
    be checked for changes outside printed regions. In production, a rendered
    3:4 photo might have been rescaled; do not claim pixel equality then.
    """
    root = Path(private_root).resolve()
    cat = str(case.get("category", ""))
    if cat not in CATEGORIES:
        raise ValueError("UNKNOWN_CATEGORY")
    paths = {}
    for kind in ("source", "render", "mask"):
        if not case.get(kind):
            if kind != "mask":
                raise ValueError("MISSING_" + kind.upper())
            continue
        p = _safe_image(root / str(case[kind]))
        if not p.resolve().is_relative_to(root):
            raise ValueError("OUTSIDE_PRIVATE_GOLDEN_ROOT")
        paths[kind] = p
    result = {"category": cat, "case_id": str(case.get("id") or paths["render"].stem),
              "human_acceptance": "PENDING", "automatic_approval": False,
              "sha256": {k: _hash(p) for k, p in paths.items()}}
    with Image.open(paths["source"]) as original, Image.open(paths["render"]) as output:
        sw, sh = original.size; ow, oh = output.size
        if max(sw * sh, ow * oh) > 100_000_000:
            raise ValueError("GOLDEN_IMAGE_TOO_LARGE_USE_BOUNDED_PREVIEW")
        result["source_size"] = [sw, sh]
        result["output_size"] = [ow, oh]
        result["output_is_3x4"] = abs(ow * 4 - oh * 3) <= max(ow, oh) * .002
        result["zero_byte"] = not (paths["source"].stat().st_size and paths["render"].stat().st_size)
        if "mask" not in paths:
            result["mask_outside_pixel_check"] = "NOT_COMPARABLE_NO_MASK"
        elif original.size != output.size:
            result["mask_outside_pixel_check"] = "NOT_COMPARABLE_DIFFERENT_IMAGE_SIZE"
        else:
            with Image.open(paths["mask"]) as mask_image:
                if mask_image.size != original.size:
                    result["mask_outside_pixel_check"] = "NOT_COMPARABLE_MASK_SIZE"
                else:
                    # Mask>0 = printed region. If source/render differ even
                    # outside by one channel, prevent a false "all safe" pass.
                    m = mask_image.convert("L").point(lambda v: 255 if v > 0 else 0)
                    outside = m.point(lambda v: 0 if v > 0 else 255)
                    delta = ImageChops.difference(original.convert("RGB"), output.convert("RGB"))
                    changed = any(ImageChops.multiply(channel, outside).getbbox() is not None for channel in delta.split())
                    result["mask_outside_pixel_check"] = "FAIL" if changed else "PASS"
        # White/black nearly-flat is a review hint, NOT proof of corruption.
        gray = output.convert("L")
        result["output_grayscale_stddev"] = round(ImageStat.Stat(gray).stddev[0], 3)
        result["flat_image_review_hint"] = result["output_grayscale_stddev"] < 3.0
    return result


def evaluate_private_golden_manifest(manifest: Path, private_root: Path) -> dict:
    root = Path(private_root).resolve()
    supplied_manifest = Path(manifest).absolute()
    if any(p.is_symlink() for p in (supplied_manifest, *supplied_manifest.parents)):
        raise ValueError("SYMLINK_MANIFEST_FORBIDDEN")
    manifest = supplied_manifest.resolve(strict=True)
    if not manifest.is_relative_to(root):
        raise ValueError("MANIFEST_NOT_IN_PRIVATE_ROOT")
    with manifest.open("r", encoding="utf-8") as f:
        data = json.load(f)
    cases = data.get("cases")
    if not isinstance(cases, list) or len(cases) > 1000:
        raise ValueError("INVALID_CASES")
    results = []
    for case in cases:
        try:
            results.append(evaluate_golden_case(case, root))
        except (ValueError, OSError, TypeError) as exc:
            results.append({"case_id": str(case.get("id", "")) if isinstance(case, dict) else "unknown",
                            "error": str(exc), "human_acceptance": "PENDING", "automatic_approval": False})
    return {"count": len(results), "fail_count": sum(bool(r.get("error")) or r.get("mask_outside_pixel_check") == "FAIL" for r in results),
            "auto_approved": 0, "human_acceptance": "PENDING", "read_only": True, "results": results}
