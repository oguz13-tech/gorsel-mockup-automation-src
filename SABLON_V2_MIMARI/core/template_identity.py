# -*- coding: utf-8 -*-
"""Permanent template-number identity registry.

A template number is a durable identity, not a disposable filename. Once a
number has been used for a category it must never silently be reused, even when
the active file was later deleted or moved to trash.
"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Iterable


CATEGORY_PREFIXES = {
    "01_Wifi_Kutusu": "Wifi_Kutusu",
    "02_Cam_Tablo_Dikey": "CamTabloDikey",
    "02_Cam_Tablo_Yatay": "CamTabloYatay",
    "03_Ahsap_Tablo": "AhsapTablo",
    "04_Cam_Dograma": "CamDograma",
    "05_Ocak_Arkasi": "OcakArkasi",
}
PREFIX_TO_CATEGORY = {
    prefix.casefold(): category
    for category, prefix in CATEGORY_PREFIXES.items()
}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".avif", ".bmp"}


class TemplateNumberConflictError(ValueError):
    def __init__(
        self,
        category: str,
        conflicts: Iterable[int],
        suggested_start: int | None = None,
    ):
        self.category = category
        self.conflicts = tuple(sorted({int(v) for v in conflicts}))
        self.suggested_start = (
            int(suggested_start)
            if suggested_start is not None
            else None
        )
        conflict_text = ", ".join(str(v) for v in self.conflicts[:20])
        if len(self.conflicts) > 20:
            conflict_text += ", ..."
        message = (
            f"Bu numara(lar) daha önce kullanılmış: {conflict_text}. "
            "Eski numaralar tekrar kullanılamaz."
        )
        if self.suggested_start is not None:
            message += (
                f" Önerilen güvenli başlangıç: {self.suggested_start}."
            )
        super().__init__(message)


def normalize_prefix(prefix: str) -> str:
    return str(prefix or "").strip().rstrip("_").casefold()


def category_for_prefix(prefix: str) -> str | None:
    return PREFIX_TO_CATEGORY.get(normalize_prefix(prefix))


def prefix_for_category(category: str) -> str:
    return CATEGORY_PREFIXES.get(str(category), str(category))


def extract_number(category: str, name: str) -> int | None:
    prefix = re.escape(prefix_for_category(category))
    stem = Path(str(name)).stem
    match = re.fullmatch(
        rf"{prefix}_(\d+)",
        stem,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    try:
        return int(match.group(1))
    except (TypeError, ValueError):
        return None


def _db_path(runtime_root: Path) -> Path:
    return runtime_root / "SABLON_V2_MIMARI" / "ayarlar.db"


def ensure_registry_table(runtime_root: Path) -> None:
    db_path = _db_path(Path(runtime_root))
    if not db_path.is_file():
        return
    conn = sqlite3.connect(str(db_path), timeout=30)
    try:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS template_number_registry (
                category TEXT NOT NULL,
                template_number INTEGER NOT NULL,
                canonical_name TEXT,
                first_seen_source TEXT,
                first_seen_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (category, template_number)
            )"""
        )
        conn.commit()
    finally:
        conn.close()


def reserve_number(
    runtime_root: Path,
    category: str,
    number: int,
    *,
    canonical_name: str | None = None,
    source: str = "runtime",
) -> None:
    runtime_root = Path(runtime_root)
    ensure_registry_table(runtime_root)
    db_path = _db_path(runtime_root)
    if not db_path.is_file():
        return
    conn = sqlite3.connect(str(db_path), timeout=30)
    try:
        conn.execute(
            """INSERT OR IGNORE INTO template_number_registry
               (category, template_number, canonical_name, first_seen_source)
               VALUES (?, ?, ?, ?)""",
            (
                str(category),
                int(number),
                str(canonical_name or ""),
                str(source or "runtime"),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _numbers_from_db(runtime_root: Path, category: str) -> set[int]:
    db_path = _db_path(runtime_root)
    if not db_path.is_file():
        return set()

    ensure_registry_table(runtime_root)
    numbers: set[int] = set()
    conn = sqlite3.connect(str(db_path), timeout=30)
    try:
        for row in conn.execute(
            """SELECT template_number
               FROM template_number_registry
               WHERE category=?""",
            (category,),
        ).fetchall():
            try:
                numbers.add(int(row[0]))
            except (TypeError, ValueError):
                pass

        # Every historical profile counts, including inactive/deleted profiles.
        try:
            rows = conn.execute(
                """SELECT source_relative_path, template_uid
                   FROM template_profiles
                   WHERE category=?""",
                (category,),
            ).fetchall()
            for relative_path, template_uid in rows:
                candidates = []
                if relative_path:
                    candidates.append(Path(str(relative_path)).name)
                if template_uid:
                    uid = str(template_uid)
                    marker = f"{category}_"
                    if uid.startswith(marker):
                        candidates.append(uid[len(marker):])
                for candidate in candidates:
                    number = extract_number(category, candidate)
                    if number is not None:
                        numbers.add(number)
        except sqlite3.Error:
            pass

        try:
            rows = conn.execute(
                """SELECT filename FROM templates WHERE category_id=?""",
                (category,),
            ).fetchall()
            for (filename,) in rows:
                number = extract_number(category, filename)
                if number is not None:
                    numbers.add(number)
        except sqlite3.Error:
            pass
    finally:
        conn.close()
    return numbers


def _numbers_from_category_dir(
    directory: Path,
    category: str,
    *,
    ignore_paths: set[Path],
) -> set[int]:
    numbers: set[int] = set()
    if not directory.exists():
        return numbers
    for path in directory.iterdir():
        if not path.is_file():
            continue
        try:
            resolved = path.resolve()
        except OSError:
            resolved = path
        if resolved in ignore_paths:
            continue
        if path.suffix.lower() not in IMAGE_EXTS and not path.name.endswith(
            ".processing"
        ):
            continue
        name = path.name
        if name.endswith(".processing"):
            name = name[: -len(".processing")]
        number = extract_number(category, name)
        if number is not None:
            numbers.add(number)
    return numbers


def _numbers_from_trash(
    trash_dir: Path,
    category: str,
) -> set[int]:
    numbers: set[int] = set()
    if not trash_dir.exists():
        return numbers

    for meta in trash_dir.glob("*.json"):
        try:
            data = json.loads(meta.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        meta_category = str(
            data.get("kategori")
            or data.get("category")
            or ""
        )
        if meta_category and meta_category != category:
            continue
        name = (
            data.get("sablon")
            or data.get("template")
            or data.get("filename")
        )
        if name:
            number = extract_number(category, str(name))
            if number is not None:
                numbers.add(number)

    # Legacy trash names contain category + template name + timestamp.
    prefix = re.escape(prefix_for_category(category))
    pattern = re.compile(
        rf"(?:^|__){prefix}_(\d+)(?:__|\.|$)",
        flags=re.IGNORECASE,
    )
    for path in trash_dir.iterdir():
        match = pattern.search(path.name)
        if match:
            numbers.add(int(match.group(1)))
    return numbers


def _numbers_from_output_history(
    output_root: Path,
    category: str,
) -> set[int]:
    """Recover identities from historical generated artifact filenames."""
    numbers: set[int] = set()
    if not output_root.exists():
        return numbers
    prefix = re.escape(prefix_for_category(category))
    pattern = re.compile(
        rf"(?:^|_){prefix}_(\d+)(?:_|\.|$)",
        flags=re.IGNORECASE,
    )
    try:
        iterator = output_root.rglob("*")
        for path in iterator:
            if not path.is_file():
                continue
            match = pattern.search(path.name)
            if match:
                numbers.add(int(match.group(1)))
    except OSError:
        pass
    return numbers


def collect_reserved_numbers(
    runtime_root: Path,
    category: str,
    *,
    ignore_paths: Iterable[Path] | None = None,
    include_pending_staging: bool = True,
) -> set[int]:
    """Collect all known current + historical template numbers."""
    runtime_root = Path(runtime_root).resolve()
    ignored: set[Path] = set()
    for value in ignore_paths or []:
        try:
            ignored.add(Path(value).resolve())
        except OSError:
            ignored.add(Path(value))

    numbers = _numbers_from_db(runtime_root, category)

    for root_name in (
        "2_SABLON_HAVUZU",
        "2_SABLON_HAVUZU_ORIJINAL_YEDEK",
    ):
        numbers.update(
            _numbers_from_category_dir(
                runtime_root / root_name / category,
                category,
                ignore_paths=ignored,
            )
        )

    if include_pending_staging:
        numbers.update(
            _numbers_from_category_dir(
                runtime_root
                / "YENI-BOS MOCKUP SABLON HAVUZU"
                / category,
                category,
                ignore_paths=ignored,
            )
        )

    for trash_name in (
        "SILINEN_SABLONLAR_COP_KUTUSU",
        "_COP_KUTUSU",
        "_KURTARMA_PROCESSING",
    ):
        numbers.update(
            _numbers_from_trash(
                runtime_root / trash_name,
                category,
            )
        )

    numbers.update(
        _numbers_from_output_history(
            runtime_root / "3_URETILEN_MOCKUPLAR",
            category,
        )
    )

    # Some legacy trash lived in the source checkout instead of runtime.
    source_root = Path(__file__).resolve().parents[2]
    if source_root.resolve() != runtime_root:
        numbers.update(
            _numbers_from_trash(
                source_root / "_COP_KUTUSU",
                category,
            )
        )

    return numbers


def find_next_contiguous_free_block(
    reserved: set[int],
    start: int,
    count: int,
) -> int:
    start = max(0, int(start))
    count = max(1, int(count))
    candidate = start
    while True:
        block = range(candidate, candidate + count)
        if all(number not in reserved for number in block):
            return candidate
        candidate += 1


def validate_number_block(
    runtime_root: Path,
    category: str,
    start: int,
    count: int,
    *,
    ignore_paths: Iterable[Path] | None = None,
) -> set[int]:
    reserved = collect_reserved_numbers(
        runtime_root,
        category,
        ignore_paths=ignore_paths,
        include_pending_staging=True,
    )
    requested = set(range(int(start), int(start) + int(count)))
    conflicts = requested.intersection(reserved)
    if conflicts:
        suggested = find_next_contiguous_free_block(
            reserved,
            int(start),
            int(count),
        )
        raise TemplateNumberConflictError(
            category,
            conflicts,
            suggested_start=suggested,
        )
    return requested


def backfill_registry(runtime_root: Path) -> dict[str, int]:
    """Persist all discoverable historical numbers so future deletes stay reserved."""
    runtime_root = Path(runtime_root).resolve()
    ensure_registry_table(runtime_root)
    summary: dict[str, int] = {}
    for category in CATEGORY_PREFIXES:
        numbers = collect_reserved_numbers(
            runtime_root,
            category,
            include_pending_staging=False,
        )
        for number in numbers:
            reserve_number(
                runtime_root,
                category,
                number,
                canonical_name=(
                    f"{prefix_for_category(category)}_{number:03d}.png"
                ),
                source="history_backfill",
            )
        summary[category] = len(numbers)
    return summary
