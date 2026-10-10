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


def canonical_identity(name: str) -> str:
    """Extension-insensitive, case-insensitive filename identity."""
    raw = str(name or "").strip()
    if raw.endswith(".processing"):
        raw = raw[: -len(".processing")]
    return Path(raw).stem.casefold()


def same_identity(name_a: str, name_b: str) -> bool:
    return bool(
        canonical_identity(name_a)
        and canonical_identity(name_a) == canonical_identity(name_b)
    )


def same_stem_files(
    directory: Path,
    name: str,
    *,
    ignore_paths: Iterable[Path] | None = None,
) -> list[Path]:
    """Return image files with the same stem regardless of extension."""
    directory = Path(directory)
    if not directory.is_dir():
        return []

    identity = canonical_identity(name)
    ignored: set[Path] = set()
    for value in ignore_paths or []:
        try:
            ignored.add(Path(value).resolve())
        except OSError:
            ignored.add(Path(value))

    matches: list[Path] = []
    for path in directory.iterdir():
        if not path.is_file():
            continue
        raw_name = path.name
        is_processing = raw_name.endswith(".processing")
        comparison_name = (
            raw_name[: -len(".processing")]
            if is_processing
            else raw_name
        )
        suffix = Path(comparison_name).suffix.casefold()
        if suffix not in IMAGE_EXTS:
            continue
        try:
            resolved = path.resolve()
        except OSError:
            resolved = path
        if resolved in ignored:
            continue
        if canonical_identity(comparison_name) == identity:
            matches.append(path)
    return sorted(matches, key=lambda item: item.name.casefold())


def _identity_file_record(
    path: Path,
    *,
    location: str,
    runtime_root: Path,
) -> dict:
    raw_name = path.name
    comparison_name = (
        raw_name[: -len(".processing")]
        if raw_name.endswith(".processing")
        else raw_name
    )
    try:
        relative = path.resolve().relative_to(runtime_root.resolve()).as_posix()
    except Exception:
        relative = str(path)
    return {
        "location": location,
        "kind": "FILE",
        "name": comparison_name,
        "extension": Path(comparison_name).suffix.casefold(),
        "path": relative,
    }


def collect_identity_conflicts(
    runtime_root: Path,
    category: str,
    incoming_name: str,
    *,
    ignore_paths: Iterable[Path] | None = None,
    include_staging: bool = True,
) -> dict:
    """Find same category+stem across active, backup, staging and history.

    Extension is deliberately not part of identity. The report still retains
    every extension so the UI/log can explain SAME NAME / DIFFERENT EXTENSION.
    """
    runtime_root = Path(runtime_root).resolve()
    category = str(category or "")
    identity = canonical_identity(incoming_name)
    incoming_ext = Path(
        str(incoming_name or "").replace(".processing", "")
    ).suffix.casefold()

    ignored: set[Path] = set()
    for value in ignore_paths or []:
        try:
            ignored.add(Path(value).resolve())
        except OSError:
            ignored.add(Path(value))

    records: list[dict] = []
    physical_roots = [
        ("WORKING", runtime_root / "2_SABLON_HAVUZU" / category),
        (
            "ORIGINAL_ARCHIVE",
            runtime_root / "2_SABLON_HAVUZU_ORIJINAL_YEDEK" / category,
        ),
    ]
    if include_staging:
        physical_roots.append(
            (
                "STAGING",
                runtime_root / "YENI-BOS MOCKUP SABLON HAVUZU" / category,
            )
        )

    for location, directory in physical_roots:
        for path in same_stem_files(
            directory,
            incoming_name,
            ignore_paths=ignored,
        ):
            records.append(
                _identity_file_record(
                    path,
                    location=location,
                    runtime_root=runtime_root,
                )
            )

    db_path = _db_path(runtime_root)
    if db_path.is_file():
        conn = _connect_read_only(db_path)
        try:
            # Active template registry.
            try:
                for (filename,) in conn.execute(
                    "SELECT filename FROM templates WHERE category_id=?",
                    (category,),
                ).fetchall():
                    if filename and canonical_identity(filename) == identity:
                        records.append({
                            "location": "DB_ACTIVE",
                            "kind": "DB",
                            "name": str(filename),
                            "extension": Path(str(filename)).suffix.casefold(),
                            "path": None,
                        })
            except sqlite3.Error:
                pass

            # Durable number/name registry.
            try:
                rows = conn.execute(
                    """SELECT canonical_name, template_number
                       FROM template_number_registry
                       WHERE category=?""",
                    (category,),
                ).fetchall()
                for canonical_name, template_number in rows:
                    if (
                        canonical_name
                        and canonical_identity(canonical_name) == identity
                    ):
                        records.append({
                            "location": "NUMBER_REGISTRY",
                            "kind": "HISTORY",
                            "name": str(canonical_name),
                            "extension": Path(
                                str(canonical_name)
                            ).suffix.casefold(),
                            "path": None,
                            "template_number": int(template_number),
                        })
            except sqlite3.Error:
                pass

            # Historical profile rows, including inactive records.
            try:
                rows = conn.execute(
                    """SELECT source_relative_path
                       FROM template_profiles
                       WHERE category=?""",
                    (category,),
                ).fetchall()
                for (relative_path,) in rows:
                    if not relative_path:
                        continue
                    name = Path(str(relative_path)).name
                    if canonical_identity(name) == identity:
                        records.append({
                            "location": "PROFILE_HISTORY",
                            "kind": "HISTORY",
                            "name": name,
                            "extension": Path(name).suffix.casefold(),
                            "path": str(relative_path),
                        })
            except sqlite3.Error:
                pass
        finally:
            conn.close()

    # Recoverable trash metadata keeps identity even after physical files move.
    trash_dir = runtime_root / "SILINEN_SABLONLAR_COP_KUTUSU"
    if trash_dir.is_dir():
        for meta in trash_dir.glob("*_meta.json"):
            try:
                data = json.loads(meta.read_text(encoding="utf-8"))
            except Exception:
                continue
            meta_category = str(
                data.get("kategori")
                or data.get("category")
                or ""
            )
            if meta_category != category:
                continue
            name = str(
                data.get("sablon")
                or data.get("template")
                or ""
            )
            if name and canonical_identity(name) == identity:
                records.append({
                    "location": "TRASH_HISTORY",
                    "kind": "HISTORY",
                    "name": name,
                    "extension": Path(name).suffix.casefold(),
                    "path": meta.name,
                })

    # Lifecycle recovery manifests may contain duplicate/orphan variants.
    lifecycle_root = (
        runtime_root
        / "SABLON_V2_MIMARI"
        / "recovery"
        / "lifecycle"
    )
    if lifecycle_root.is_dir():
        for manifest_path in lifecycle_root.glob("*/manifest.json"):
            try:
                data = json.loads(
                    manifest_path.read_text(encoding="utf-8")
                )
            except Exception:
                continue
            if str(data.get("category") or "") != category:
                continue
            candidate_names = []
            for moved in data.get("moved", []) or []:
                if moved.get("name"):
                    candidate_names.append(str(moved["name"]))
            if data.get("template"):
                candidate_names.append(str(data["template"]))
            if data.get("keep_filename"):
                candidate_names.append(str(data["keep_filename"]))
            for name in candidate_names:
                if canonical_identity(name) == identity:
                    records.append({
                        "location": "LIFECYCLE_RECOVERY",
                        "kind": "RECOVERY",
                        "name": name,
                        "extension": Path(name).suffix.casefold(),
                        "path": manifest_path.parent.name,
                    })

    # Deduplicate repeated DB/history evidence while preserving locations.
    unique: list[dict] = []
    seen = set()
    for row in records:
        key = (
            row.get("location"),
            row.get("kind"),
            row.get("name"),
            row.get("path"),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)

    existing_exts = sorted({
        str(row.get("extension") or "")
        for row in unique
        if row.get("extension")
    })
    different_extension = bool(
        incoming_ext
        and any(ext != incoming_ext for ext in existing_exts)
    )
    same_extension = bool(
        incoming_ext
        and incoming_ext in existing_exts
    )
    return {
        "category": category,
        "identity": identity,
        "incoming_name": str(incoming_name),
        "incoming_extension": incoming_ext,
        "conflict": bool(unique),
        "same_extension_present": same_extension,
        "different_extension_present": different_extension,
        "existing_extensions": existing_exts,
        "matches": unique,
    }


def format_identity_conflict(report: dict) -> str:
    if not report.get("conflict"):
        return ""
    if report.get("different_extension_present"):
        headline = "⛔ AYNI İSİM, FARKLI UZANTI"
    else:
        headline = "⛔ AYNI İSİM / AYNI UZANTI"

    lines = [
        headline,
        f"Gelen: {report.get('incoming_name')}",
        (
            "Kimlik: "
            f"{report.get('category')} / {report.get('identity')}"
        ),
        (
            "Gelen uzantı: "
            f"{report.get('incoming_extension') or 'YOK'}"
        ),
        (
            "Sistemde görülen uzantılar: "
            + (
                ", ".join(report.get("existing_extensions") or [])
                or "YOK"
            )
        ),
        "Eşleşmeler:",
    ]
    for row in report.get("matches", []) or []:
        lines.append(
            "  - "
            f"{row.get('location')}: {row.get('name')}"
            + (
                f" [{row.get('path')}]"
                if row.get("path")
                else ""
            )
        )
    lines.append(
        "Sonuç: yeni şablon oluşturulmadı; gelen dosya değiştirilmeden bırakıldı."
    )
    return "\n".join(lines)


class TemplateIdentityConflictError(ValueError):
    def __init__(self, report: dict):
        self.report = report
        super().__init__(format_identity_conflict(report))


def assert_identity_available(
    runtime_root: Path,
    category: str,
    incoming_name: str,
    *,
    ignore_paths: Iterable[Path] | None = None,
    include_staging: bool = True,
) -> dict:
    report = collect_identity_conflicts(
        runtime_root,
        category,
        incoming_name,
        ignore_paths=ignore_paths,
        include_staging=include_staging,
    )
    if report.get("conflict"):
        raise TemplateIdentityConflictError(report)
    return report


def _db_path(runtime_root: Path) -> Path:
    return runtime_root / "SABLON_V2_MIMARI" / "ayarlar.db"


def _connect_read_only(db_path: Path) -> sqlite3.Connection:
    """Open an existing SQLite DB without creating it or writing schema/data.

    Reserved-number and incoming-file checks must never run migrations.
    Creation of the number registry belongs exclusively to explicit writer
    operations such as reserve_number() and backfill_registry().
    """
    conn = sqlite3.connect(
        db_path.resolve().as_uri() + "?mode=ro",
        uri=True,
        timeout=30,
    )
    try:
        conn.execute("PRAGMA query_only = ON")
    except BaseException:
        conn.close()
        raise
    return conn


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

    numbers: set[int] = set()
    conn = _connect_read_only(db_path)
    try:
        # Legacy databases may not yet have the registry table. A lookup
        # must never create it; the explicit writer/bootstrap path does that.
        try:
            registry_rows = conn.execute(
                """SELECT template_number
                   FROM template_number_registry
                   WHERE category=?""",
                (category,),
            ).fetchall()
        except sqlite3.OperationalError as exc:
            if "no such table: template_number_registry" not in str(exc).lower():
                raise
            registry_rows = []

        for (value,) in registry_rows:
            try:
                numbers.add(int(value))
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
