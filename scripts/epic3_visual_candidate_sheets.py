#!/usr/bin/env python3
"""Read-only EPIC-3 visual candidate audit, preserving each template's aspect.

Read-only inputs: runtime SQLite (URI mode=ro) and existing source image files.
Writes only a newly created OS TEMP directory containing labeled contact sheets
and a manifest. Does not approve, edit, move, delete, hash, or process templates.

Usage:
    python scripts/epic3_visual_candidate_sheets.py --runtime-root "C:\path" --execute

Omit --execute for no-I/O plan. No factory imports or runtime mutations.
"""
from __future__ import annotations

import argparse
import json
from math import ceil
import os
from pathlib import Path
import sqlite3
import tempfile
from typing import Any

CATEGORIES = ("01_Wifi_Kutusu", "04_Cam_Dograma")
IMAGE_SUFFIXES = frozenset({
    ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff",
})
PAGE_SIZE, COLS = 15, 3
CELL_W, CELL_H, LABEL_H = 320, 360, 65


class AuditBlocked(RuntimeError):
    pass


def _within(parent: Path, child: Path) -> Path:
    """Resolve a child only when physically beneath the trusted pool.

    Windows can return different aliases (RUNNER~1 vs runneradmin) from
    Path.resolve() for the same NTFS directory. Compare actual ancestor file
    identities, never mere path string prefixes, to avoid both false BLOCKED
    and symlink/prefix escape bypasses.
    """
    base = Path(parent).resolve()
    candidate = Path(child).resolve()
    if candidate.is_relative_to(base):
        return candidate
    # Exact samefile comparison works across Windows 8.3 alias paths.
    for ancestor in (candidate, *candidate.parents):
        try:
            if ancestor.exists() and os.path.samefile(ancestor, base):
                suffix = candidate.relative_to(ancestor)
                normalized = base / suffix
                if normalized.resolve().exists() and os.path.samefile(normalized, candidate):
                    return normalized
        except (OSError, ValueError):
            continue
    raise AuditBlocked(f"UNSAFE_SOURCE_PATH:{child.name}")


def _load_approved(db_path: Path, pool: Path) -> dict[str, list[dict[str, Any]]]:
    if not db_path.is_file():
        raise AuditBlocked("RUNTIME_DB_NOT_FOUND")
    conn = sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True, timeout=5)
    try:
        conn.execute("PRAGMA query_only=ON")
        names = {row[1] for row in conn.execute("PRAGMA table_info(template_profiles)")}
        required = {
            "template_uid", "category", "source_relative_path",
            "review_status", "is_active", "manually_verified",
        }
        if not required.issubset(names):
            raise AuditBlocked("PROFILE_SCHEMA_MISSING")
        result: dict[str, list[dict[str, Any]]] = {}
        for cat in CATEGORIES:
            rows = conn.execute(
                """SELECT template_uid,source_relative_path,review_status,
                          is_active,manually_verified
                   FROM template_profiles
                   WHERE category=? AND review_status='APPROVED'
                         AND is_active=1 AND manually_verified=1
                   ORDER BY source_relative_path""",
                (cat,),
            ).fetchall()
            records = []
            for uid, relative, status, active, manual in rows:
                if not relative:
                    raise AuditBlocked(f"APPROVED_PATH_MISSING:{uid}")
                source = _within(pool, pool / str(relative))
                if source.parent.name != cat:
                    raise AuditBlocked(f"APPROVED_CATEGORY_PATH_INVALID:{uid}")
                records.append({
                    "uid": str(uid), "relative": str(relative),
                    "source": source, "status": str(status),
                    "manual": bool(manual),
                })
            result[cat] = records
        return result
    finally:
        conn.close()


def _physical_files(pool: Path, cat: str) -> list[Path]:
    folder = _within(pool, pool / cat)
    if not folder.is_dir():
        raise AuditBlocked(f"CATEGORY_FOLDER_MISSING:{cat}")
    images = []
    for path in folder.rglob("*"):
        if not path.is_file() or path.suffix.casefold() not in IMAGE_SUFFIXES:
            continue
        images.append(_within(pool, path))
    return sorted(images, key=lambda p: str(p.relative_to(pool)).casefold())


def _render_sheet(PIL_Image, PIL_Draw, PIL_Font, group: str,
                  records: list[dict[str, Any]], dest: Path) -> tuple[list[str], list[dict]]:
    # RGB neutral background, never square-stretch source images.
    rows = ceil(PAGE_SIZE / COLS)
    pages, manifest_items = [], []
    font = PIL_Font.load_default()
    for start in range(0, len(records), PAGE_SIZE):
        page_no = (start // PAGE_SIZE) + 1
        subset = records[start:start+PAGE_SIZE]
        canvas = PIL_Image.new(
            "RGB", (COLS*CELL_W, 62+rows*CELL_H), "#f4f4f4",
        )
        draw = PIL_Draw.Draw(canvas)
        draw.text(
            (16, 18), f"EPIC-3 {group} | page {page_no} | {len(records)} images",
            fill="#222222", font=font,
        )
        for k, rec in enumerate(subset):
            x = (k % COLS)*CELL_W
            y = 62 + (k // COLS)*CELL_H
            draw.rectangle(
                (x+6,y+6,x+CELL_W-7,y+CELL_H-7),
                outline="#b6b6b6", width=1,
            )
            source = rec["source"]
            status = rec.get("status", "UNAPPROVED")
            try:
                with PIL_Image.open(source) as raw:
                    original_size = list(raw.size)
                    img = raw.convert("RGB")
                    img.thumbnail(
                        (CELL_W-28, CELL_H-LABEL_H-28),
                        resample=PIL_Image.Resampling.LANCZOS,
                    )
                    px = x+(CELL_W-img.width)//2
                    py = y+LABEL_H+(CELL_H-LABEL_H-img.height)//2
                    canvas.paste(img, (px, py))
                error = None
            except (OSError, ValueError, PIL_Image.DecompressionBombError) as exc:
                error = f"{type(exc).__name__}: {str(exc)[:100]}"
                original_size = None
            name = source.name
            draw.text((x+13,y+16), name[:44], fill="#222222", font=font)
            draw.text((x+13,y+34), status[:35], fill="#16743c" if status=="APPROVED" else "#994433", font=font)
            if error:
                draw.text((x+13,y+90), "UNREADABLE", fill="#cc0000", font=font)
            manifest_items.append({
                "relative": rec["relative"],
                "uid": rec.get("uid"),
                "status": status,
                "size": original_size,
                "error": error,
            })
        sheet = dest / f"{group}_PAGE_{page_no:02d}.jpg"
        canvas.save(sheet, format="JPEG", quality=93, subsampling=0)
        pages.append(str(sheet))
    return pages, manifest_items


def run(runtime: Path, dest: Path) -> dict:
    from PIL import Image, ImageDraw, ImageFont

    pool = runtime / "2_SABLON_HAVUZU"
    if not pool.is_dir():
        raise AuditBlocked("WORKING_POOL_NOT_FOUND")
    approved = _load_approved(runtime / "SABLON_V2_MIMARI" / "ayarlar.db", pool)
    result = {
        "live_runtime_read_only": True,
        "output_root": str(dest),
        "categories": {},
    }
    for category in CATEGORIES:
        physical = _physical_files(pool, category)
        approved_for_cat = approved[category]
        approved_map = {r["source"]: r for r in approved_for_cat}
        records = []
        for source in physical:
            review = approved_map.get(source)
            records.append({
                "relative": str(source.relative_to(pool)),
                "source": source,
                "uid": review["uid"] if review else None,
                "status": "APPROVED" if review else "NOT_APPROVED_OR_NO_ACTIVE_PROFILE",
            })
        if category == "01_Wifi_Kutusu":
            # Keep contact sheets targeted: the user's 31 approved candidates.
            records = [r for r in records if r["status"]=="APPROVED"]
        missing_approved = [
            r["relative"] for r in approved_for_cat
            if r["source"] not in physical
        ]
        safe_name = "WIFI_APPROVED" if category=="01_Wifi_Kutusu" else "CAM_DOGRAMA_ALL"
        pages, items = _render_sheet(
            Image, ImageDraw, ImageFont, safe_name, records, dest,
        )
        result["categories"][category] = {
            "approved_profile_rows": len(approved_for_cat),
            "physical_image_count": len(physical),
            "sheet_count": len(pages),
            "sheet_paths": pages,
            "approved_sources_missing": missing_approved,
            "items": items,
        }
        print(
            "CATEGORY_RESULT", category,
            "APPROVED_ROWS", len(approved_for_cat),
            "PHYSICAL_FILES", len(physical),
            "SHEET_ITEMS", len(items),
            "PAGES", len(pages),
            "MISSING_APPROVED", len(missing_approved),
            flush=True,
        )
        for sheet in pages:
            print("CONTACT_SHEET", sheet, flush=True)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", required=True, type=Path)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    if not args.execute:
        print("PLAN_ONLY: read live pool + approved SQLite in ro mode;"
              " write proportional JPG contact sheets to new TEMP only")
        return 0
    output = Path(tempfile.mkdtemp(prefix="epic3-visual-candidates-"))
    print("ISOLATED_OUTPUT_ROOT", str(output), flush=True)
    try:
        results = run(args.runtime_root.expanduser().resolve(), output)
        (output/"candidate_manifest.json").write_text(
            json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8",
        )
        print("RESULT_MANIFEST", output/"candidate_manifest.json")
        return 0 if all(
            not group["approved_sources_missing"]
            and not any(item["error"] for item in group["items"])
            for group in results["categories"].values()
        ) else 2
    except Exception as exc:
        print("BLOCKED", type(exc).__name__, str(exc), flush=True)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
