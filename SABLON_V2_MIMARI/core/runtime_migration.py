from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
import uuid
from pathlib import Path
from typing import Callable, Iterable, Optional

from .path_registry import (
    PATHS,
    resolve_runtime_root,
    rollback_runtime_pointer,
    write_runtime_pointer,
)


IGNORED_DIR_NAMES = {
    ".git",
    ".kilo",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}
IGNORED_FILE_SUFFIXES = {".pyc", ".pyo"}
MIGRATION_MANIFEST_RELATIVE = Path(
    "SABLON_V2_MIMARI"
) / "reports" / "runtime_migration_manifest.json"


class RuntimeMigrationError(RuntimeError):
    pass


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_runtime_root(root: Path) -> None:
    db = root / PATHS["REVIEW_SYSTEM"] / "ayarlar.db"
    if not db.is_file():
        raise RuntimeMigrationError(
            f"Geçerli runtime bulunamadı: {db}"
        )


def _validate_distinct_roots(source: Path, target: Path) -> None:
    source = source.resolve()
    target = target.resolve()
    if source == target:
        raise RuntimeMigrationError("Kaynak ve hedef aynı klasör olamaz.")
    try:
        target.relative_to(source)
        raise RuntimeMigrationError(
            "Hedef runtime kaynak runtime'ın içinde olamaz."
        )
    except ValueError:
        pass
    try:
        source.relative_to(target)
        raise RuntimeMigrationError(
            "Kaynak runtime hedef runtime'ın içinde olamaz."
        )
    except ValueError:
        pass


def _should_include(relative: Path) -> bool:
    if not relative.parts:
        return False
    if any(part in IGNORED_DIR_NAMES for part in relative.parts):
        return False
    if relative.suffix.casefold() in IGNORED_FILE_SUFFIXES:
        return False
    if relative == MIGRATION_MANIFEST_RELATIVE:
        return False
    return True


def iter_runtime_files(root: Path) -> Iterable[tuple[Path, Path]]:
    root = root.resolve()
    if not root.is_dir():
        return
    for path in sorted(
        (item for item in root.rglob("*") if item.is_file()),
        key=lambda item: item.as_posix().casefold(),
    ):
        relative = path.relative_to(root)
        if _should_include(relative):
            yield relative, path


def default_target_root() -> Path:
    if os.name == "nt":
        return Path(r"C:\JARVIS_RUNTIME\MockupFactory")
    return Path.home() / "JARVIS_RUNTIME" / "MockupFactory"


def build_runtime_migration_plan(
    source_root: str | Path,
    target_root: str | Path,
) -> dict:
    source = Path(source_root).expanduser().resolve()
    target = Path(target_root).expanduser().resolve()
    _validate_runtime_root(source)
    _validate_distinct_roots(source, target)

    file_count = 0
    total_bytes = 0
    top_level_counts: dict[str, int] = {}
    for relative, path in iter_runtime_files(source):
        file_count += 1
        try:
            total_bytes += int(path.stat().st_size)
        except OSError:
            pass
        top = relative.parts[0]
        top_level_counts[top] = top_level_counts.get(top, 0) + 1

    target_existing_files = 0
    if target.is_dir():
        target_existing_files = sum(
            1 for _rel, _path in iter_runtime_files(target)
        )

    canonical_presence = {
        key: (source / relative).exists()
        for key, relative in PATHS.items()
    }

    return {
        "success": True,
        "read_only": True,
        "source_root": str(source),
        "target_root": str(target),
        "file_count": file_count,
        "total_bytes": total_bytes,
        "target_exists": target.exists(),
        "target_existing_file_count": target_existing_files,
        "ignored_dir_names": sorted(IGNORED_DIR_NAMES),
        "canonical_presence": canonical_presence,
        "top_level_file_counts": dict(
            sorted(top_level_counts.items(), key=lambda item: item[0].casefold())
        ),
        "safety": {
            "source_delete_allowed": False,
            "overwrite_conflicting_target_allowed": False,
            "switch_before_verify_allowed": False,
        },
    }


def _copy_one_atomic(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = destination.with_name(
        destination.name + f".copy_{uuid.uuid4().hex}.tmp"
    )
    try:
        shutil.copy2(source, temp)
        if _sha256_file(source) != _sha256_file(temp):
            raise RuntimeMigrationError(
                f"Kopya SHA256 doğrulaması başarısız: {source}"
            )
        os.replace(temp, destination)
    finally:
        try:
            if temp.exists():
                temp.unlink()
        except OSError:
            pass


def verify_runtime_workspace(
    source_root: str | Path,
    target_root: str | Path,
    *,
    progress: Optional[Callable[[int, int, str], None]] = None,
) -> dict:
    source = Path(source_root).expanduser().resolve()
    target = Path(target_root).expanduser().resolve()
    _validate_runtime_root(source)
    _validate_distinct_roots(source, target)

    source_files = list(iter_runtime_files(source))
    total = len(source_files)
    missing = []
    mismatched = []
    verified = 0

    for index, (relative, source_path) in enumerate(
        source_files,
        start=1,
    ):
        if progress:
            progress(index - 1, total, f"Doğrulanıyor: {relative.as_posix()}")
        target_path = target / relative
        if not target_path.is_file():
            missing.append(relative.as_posix())
            continue

        try:
            source_stat = source_path.stat()
            target_stat = target_path.stat()
            same_size = int(source_stat.st_size) == int(target_stat.st_size)
            same_hash = (
                same_size
                and _sha256_file(source_path)
                == _sha256_file(target_path)
            )
        except OSError as exc:
            mismatched.append({
                "path": relative.as_posix(),
                "error": str(exc),
            })
            continue

        if not same_hash:
            mismatched.append({
                "path": relative.as_posix(),
                "source_size": int(source_stat.st_size),
                "target_size": int(target_stat.st_size),
            })
            continue
        verified += 1

    if progress:
        progress(total, total, "Runtime doğrulaması tamamlandı.")

    target_db = target / PATHS["REVIEW_SYSTEM"] / "ayarlar.db"
    ok = (
        verified == total
        and not missing
        and not mismatched
        and target_db.is_file()
    )
    return {
        "success": True,
        "verified": bool(ok),
        "source_root": str(source),
        "target_root": str(target),
        "source_file_count": total,
        "verified_file_count": verified,
        "missing_count": len(missing),
        "mismatch_count": len(mismatched),
        "missing": missing,
        "mismatched": mismatched,
        "target_db_exists": target_db.is_file(),
    }


def _write_manifest(target: Path, payload: dict) -> Path:
    path = target / MIGRATION_MANIFEST_RELATIVE
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(temp, path)
    return path


def copy_runtime_workspace(
    source_root: str | Path,
    target_root: str | Path,
    *,
    progress: Optional[Callable[[int, int, str], None]] = None,
) -> dict:
    source = Path(source_root).expanduser().resolve()
    target = Path(target_root).expanduser().resolve()
    _validate_runtime_root(source)
    _validate_distinct_roots(source, target)

    files = list(iter_runtime_files(source))
    total = len(files)
    target.mkdir(parents=True, exist_ok=True)

    copied = 0
    skipped_identical = 0
    conflicts = []

    for index, (relative, source_path) in enumerate(files, start=1):
        if progress:
            progress(index - 1, total, f"Kopyalanıyor: {relative.as_posix()}")
        destination = target / relative

        if destination.exists():
            if not destination.is_file():
                conflicts.append({
                    "path": relative.as_posix(),
                    "reason": "Hedefte dosya yerine klasör var.",
                })
                continue
            try:
                same = (
                    source_path.stat().st_size
                    == destination.stat().st_size
                    and _sha256_file(source_path)
                    == _sha256_file(destination)
                )
            except OSError:
                same = False
            if same:
                skipped_identical += 1
                continue
            conflicts.append({
                "path": relative.as_posix(),
                "reason": (
                    "Hedefte farklı içerikli dosya var; güvenlik nedeniyle "
                    "üzerine yazılmadı."
                ),
            })
            continue

        _copy_one_atomic(source_path, destination)
        copied += 1

    if conflicts:
        manifest = {
            "state": "COPY_BLOCKED_BY_CONFLICT",
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "source_root": str(source),
            "target_root": str(target),
            "copied_count": copied,
            "skipped_identical_count": skipped_identical,
            "conflict_count": len(conflicts),
            "conflicts": conflicts,
            "source_deleted": False,
            "runtime_switched": False,
        }
        _write_manifest(target, manifest)
        return {
            "success": False,
            **manifest,
        }

    verification = verify_runtime_workspace(
        source,
        target,
        progress=progress,
    )
    state = (
        "COPIED_AND_VERIFIED"
        if verification["verified"]
        else "COPY_VERIFY_FAILED"
    )
    manifest = {
        "state": state,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source_root": str(source),
        "target_root": str(target),
        "copied_count": copied,
        "skipped_identical_count": skipped_identical,
        "conflict_count": 0,
        "source_deleted": False,
        "runtime_switched": False,
        "verification": verification,
    }
    manifest_path = _write_manifest(target, manifest)
    if progress:
        progress(total, total, "Runtime kopyalama ve doğrulama tamamlandı.")
    return {
        "success": bool(verification["verified"]),
        **manifest,
        "manifest_path": str(manifest_path),
    }


def switch_runtime_after_verification(
    source_root: str | Path,
    target_root: str | Path,
) -> dict:
    source = Path(source_root).expanduser().resolve()
    target = Path(target_root).expanduser().resolve()
    verification = verify_runtime_workspace(source, target)
    if not verification["verified"]:
        raise RuntimeMigrationError(
            "Runtime pointer değiştirilmedi; hedef kopya hash doğrulamasından geçmedi."
        )

    pointer = write_runtime_pointer(target)
    manifest_path = target / MIGRATION_MANIFEST_RELATIVE
    manifest = {}
    if manifest_path.is_file():
        try:
            manifest = json.loads(
                manifest_path.read_text(encoding="utf-8")
            )
        except Exception:
            manifest = {}
    manifest.update({
        "state": "SWITCHED",
        "switched_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "runtime_switched": True,
        "source_deleted": False,
        "verification": verification,
        "pointer_path": str(pointer),
    })
    _write_manifest(target, manifest)
    return {
        "success": True,
        "source_root": str(source),
        "target_root": str(target),
        "pointer_path": str(pointer),
        "verification": verification,
        "source_deleted": False,
    }


def rollback_runtime_switch() -> dict:
    restored = rollback_runtime_pointer()
    return {
        "success": True,
        "runtime_root": str(restored),
        "source_deleted": False,
    }


def resolve_source_runtime(source_root: str | Path | None = None) -> Path:
    if source_root is not None:
        source = Path(source_root).expanduser().resolve()
        _validate_runtime_root(source)
        return source
    source = resolve_runtime_root()
    _validate_runtime_root(source)
    return source
