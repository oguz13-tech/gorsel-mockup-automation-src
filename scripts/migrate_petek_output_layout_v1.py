"""Move existing PETEK outputs to the measurement/Overlaysızlar layout.

The migration is create/move-only: file bytes are never rewritten. Existing
ledger output paths are updated in one SQLite transaction after every move is
verified by SHA-256. A collision is preserved with a deterministic suffix.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import sqlite3
from pathlib import Path


MEASUREMENTS = ("76CM", "96CM", "116CM", "136CM")
OVERLAY_FREE = "Overlaysızlar"
OVERLAY_RE = re.compile(r"__(76CM|96CM|116CM|136CM)(?:__|\.)", re.IGNORECASE)
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def unique_destination(path: Path, source: Path) -> Path:
    if not path.exists():
        return path
    if path.is_file() and sha(path) == sha(source):
        return path
    for index in range(1, 10000):
        candidate = path.with_name(f"{path.stem}__MIGRATED{index}{path.suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"destination collision limit exceeded: {path}")


def move_verified(source: Path, destination: Path, mapping: dict[str, str]) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    target = unique_destination(destination, source)
    if target == destination and target.exists():
        # Identical duplicate already exists; preserve the destination and
        # remove only the redundant source after byte verification.
        if sha(source) != sha(target):
            raise RuntimeError(f"hash collision: {source} -> {target}")
        source.unlink()
        mapping[str(source)] = str(target)
        return target
    before = sha(source)
    shutil.move(str(source), str(target))
    if not target.is_file() or sha(target) != before:
        raise RuntimeError(f"move verification failed: {target}")
    mapping[str(source)] = str(target)
    return target


def migrate_category(category: Path, mapping: dict[str, str]) -> dict[str, int]:
    counts = {"clean": 0, "overlay": 0, "collision_duplicates": 0}
    free = category / OVERLAY_FREE
    free.mkdir(exist_ok=True)
    # Snapshot files before moving so newly-created destination folders are not
    # scanned again.
    root_files = list(category.iterdir())
    for entry in root_files:
        if not entry.is_file() or entry.suffix.lower() not in IMAGE_EXTS:
            continue
        destination = free / entry.name
        before = sha(entry)
        target = unique_destination(destination, entry)
        if target.exists():
            if sha(target) != before:
                target = unique_destination(destination, entry)
            else:
                entry.unlink()
                mapping[str(entry)] = str(target)
                counts["collision_duplicates"] += 1
                counts["clean"] += 1
                continue
        shutil.move(str(entry), str(target))
        if sha(target) != before:
            raise RuntimeError(f"SHA changed during move: {entry}")
        mapping[str(entry)] = str(target)
        counts["clean"] += 1

    # Existing design folders and any legacy measurement folders are flattened
    # into category/<CM>/<design>/file. Non-overlay images go to Overlaysızlar.
    for folder in list(category.iterdir()):
        if not folder.is_dir() or folder.name == OVERLAY_FREE:
            continue
        legacy_cm = folder.name.upper() if folder.name.upper() in MEASUREMENTS else None
        for entry in list(folder.rglob("*")):
            if not entry.is_file() or entry.suffix.lower() not in IMAGE_EXTS:
                continue
            match = OVERLAY_RE.search(entry.name)
            cm = match.group(1).upper() if match else legacy_cm
            before = sha(entry)
            if cm:
                # For a legacy CM folder, keep the original nested design name
                # when present; for a design folder use its immediate child.
                design = folder.name if not legacy_cm else (entry.parent.name if entry.parent != folder else "design")
                destination = category / cm / design / entry.name
                counts["overlay"] += 1
            else:
                destination = free / entry.name
                counts["clean"] += 1
            target = unique_destination(destination, entry)
            if target.exists():
                if sha(target) != before:
                    target = unique_destination(destination, entry)
                else:
                    entry.unlink()
                    mapping[str(entry)] = str(target)
                    counts["collision_duplicates"] += 1
                    continue
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(entry), str(target))
            if sha(target) != before:
                raise RuntimeError(f"SHA changed during move: {entry}")
            mapping[str(entry)] = str(target)
        # Remove empty legacy/design folders only.
        for empty in sorted((p for p in folder.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
            try:
                empty.rmdir()
            except OSError:
                pass
        try:
            folder.rmdir()
        except OSError:
            pass
    return counts


def update_ledger(db_path: Path, mapping: dict[str, str]) -> int:
    if not db_path.is_file() or not mapping:
        return 0
    with sqlite3.connect(db_path) as con:
        updated = 0
        for old, new in mapping.items():
            cur = con.execute("UPDATE artifact SET output=? WHERE output=?", (new, old))
            updated += int(cur.rowcount or 0)
        return updated


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--ledger", type=Path)
    args = parser.parse_args()
    output_root = args.output_root.resolve()
    if not output_root.is_dir():
        raise SystemExit(f"missing output root: {output_root}")
    categories = sorted(output_root.rglob("06_Petek_Kapama"))
    mapping: dict[str, str] = {}
    total = {"clean": 0, "overlay": 0, "collision_duplicates": 0, "categories": 0}
    for category in categories:
        if not category.is_dir() or category.name != "06_Petek_Kapama":
            continue
        result = migrate_category(category, mapping)
        total["categories"] += 1
        for key in ("clean", "overlay", "collision_duplicates"):
            total[key] += result[key]
    updated = update_ledger(args.ledger.resolve() if args.ledger else output_root.parent / "v4_ortak_uretim.sqlite3", mapping)
    print({**total, "moved_or_deduped": len(mapping), "ledger_rows_updated": updated})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
