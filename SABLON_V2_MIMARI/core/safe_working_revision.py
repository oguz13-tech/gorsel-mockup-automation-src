# -*- coding: utf-8 -*-
"""P0: transactional revisions of existing WORKING PNGs, never originals.

Raw intake and original archive creation remain immutable create-only.
This module provides a *different*, human-triggered working-copy operation.
Every modification has a SHA-verified, immutable before-snapshot and a
recoverable manifest; failed operations never claim an implicit approval.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import time
import uuid
from pathlib import Path

import cv2
import numpy as np

from .template_identity import CATEGORY_PREFIXES


class WorkingRevisionBlocked(RuntimeError):
    pass


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_new(path: Path, data: bytes) -> None:
    with open(path, "xb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def _manifest(directory: Path, data: dict) -> None:
    temp = directory / ("manifest." + uuid.uuid4().hex + ".tmp")
    _write_new(temp, json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8"))
    os.replace(temp, directory / "manifest.json")


def _working_path(root: Path, category: str, template: str) -> Path:
    root = Path(root).resolve()
    if category not in CATEGORY_PREFIXES or Path(template).name != template or not template:
        raise WorkingRevisionBlocked("INVALID_WORKING_TEMPLATE")
    working_root = root / "2_SABLON_HAVUZU"
    category_dir = working_root / category
    path = category_dir / (Path(template).stem + ".png")
    # In particular, a symlink must never redirect a working update into RAW
    # archive, immutable original backups or some external user directory.
    if any(p.is_symlink() for p in (working_root, category_dir, path)):
        raise WorkingRevisionBlocked("WORKING_SYMLINK_BLOCKED")
    if not path.is_file() or path.resolve().parent != category_dir.resolve():
        raise WorkingRevisionBlocked("WORKING_PNG_NOT_FOUND_OR_UNSAFE")
    return path


@contextlib.contextmanager
def working_png_revision(runtime_root, category: str, template: str, image: np.ndarray):
    """Publish a revision while holding an exclusive lock until caller commits.

    If the caller's settings/DB operation raises, the PNG is restored from its
    SHA-verified snapshot. If an unrelated actor changes the PNG, rollback
    cannot overwrite it and RECOVERY_REQUIRED is recorded instead.
    """
    root = Path(runtime_root).resolve()
    path = _working_path(root, category, template)
    if isinstance(image, (bytes, bytearray)):
        # Exact PNG bytes preserve alpha, metadata and byte-for-byte restores.
        after = bytes(image)
        if not after.startswith(bytes.fromhex("89504e470d0a1a0a")) or cv2.imdecode(
            np.frombuffer(after, dtype=np.uint8), cv2.IMREAD_UNCHANGED
        ) is None:
            raise WorkingRevisionBlocked("INVALID_PNG_BYTES")
    else:
        if image is None or image.size == 0:
            raise WorkingRevisionBlocked("INVALID_WORKING_IMAGE")
        ok, encoded = cv2.imencode(".png", image)
        if not ok:
            raise WorkingRevisionBlocked("PNG_ENCODING_FAILED")
        after = encoded.tobytes()
    revisions = root / "_P0_WORKING_REVISIONS"
    if revisions.is_symlink():
        raise WorkingRevisionBlocked("REVISION_ARCHIVE_SYMLINK_BLOCKED")
    revisions.mkdir(parents=True, exist_ok=True)
    locks = revisions / "locks"
    locks.mkdir(parents=True, exist_ok=True)
    lock = locks / (category + "__" + path.stem + ".lock")
    fd = None
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise WorkingRevisionBlocked("WORKING_REVISION_LOCK_BUSY") from exc

    opdir = revisions / (time.strftime("%Y%m%d_%H%M%S") + "__" + uuid.uuid4().hex)
    published = False
    before = None
    entry = None
    tmp = path.with_name("." + path.name + "." + uuid.uuid4().hex + ".p0tmp")
    try:
        # A concurrent writer operating outside this lock will be detected
        # by the last pre-publication hash comparison.
        before = path.read_bytes()
        before_hash = _sha(before)
        after_hash = _sha(after)
        opdir.mkdir(mode=0o700)
        _write_new(opdir / "working_before.png", before)
        if _sha((opdir / "working_before.png").read_bytes()) != before_hash:
            raise WorkingRevisionBlocked("SNAPSHOT_HASH_MISMATCH")
        entry = dict(
            state="PREPARED", category=category, template=template,
            before_sha256=before_hash, after_sha256=after_hash,
            target=str(path), snapshot=str(opdir / "working_before.png"),
            source="human_working_revision",
        )
        _manifest(opdir, entry)
        _write_new(tmp, after)
        if _sha(path.read_bytes()) != before_hash:
            raise WorkingRevisionBlocked("WORKING_CHANGED_CONCURRENTLY")
        os.replace(tmp, path)
        published = True
        if _sha(path.read_bytes()) != after_hash:
            raise WorkingRevisionBlocked("WORKING_PUBLISH_HASH_MISMATCH")
        entry["state"] = "PUBLISHED_PENDING_CALLER"
        _manifest(opdir, entry)
        try:
            yield dict(entry, revision_id=opdir.name)
        except BaseException:
            raise
        else:
            entry["state"] = "COMMITTED"
            _manifest(opdir, entry)
    except BaseException as error:
        if published and entry is not None:
            # Never undo someone else's concurrent edits.
            if path.is_file() and _sha(path.read_bytes()) == entry["after_sha256"]:
                restore = path.with_name("." + path.name + "." + uuid.uuid4().hex + ".rollback")
                try:
                    _write_new(restore, before)
                    os.replace(restore, path)
                    state = "ROLLED_BACK" if _sha(path.read_bytes()) == entry["before_sha256"] else "RECOVERY_REQUIRED"
                except BaseException:
                    state = "RECOVERY_REQUIRED"
                finally:
                    restore.unlink(missing_ok=True)
            else:
                state = "RECOVERY_REQUIRED"
            entry["state"] = state
            entry["error"] = type(error).__name__
            _manifest(opdir, entry)
        raise
    finally:
        tmp.unlink(missing_ok=True)
        if fd is not None:
            os.close(fd)
            lock.unlink(missing_ok=True)


def save_preview_only(runtime_root, category: str, template: str, image: np.ndarray) -> Path:
    """Update only a clearly marked derived preview; NEVER a normal template."""
    root = Path(runtime_root).resolve()
    if category not in CATEGORY_PREFIXES or Path(template).name != template or not template:
        raise WorkingRevisionBlocked("INVALID_PREVIEW_TEMPLATE")
    directory = root / "YENI-BOS MOCKUP SABLON HAVUZU" / category
    if directory.is_symlink() or not directory.is_dir():
        raise WorkingRevisionBlocked("PREVIEW_DIR_NOT_FOUND_OR_UNSAFE")
    target = directory / (Path(template).stem + "-beyazlatilmis-onizleme.png")
    if target.is_symlink():
        raise WorkingRevisionBlocked("PREVIEW_SYMLINK_BLOCKED")
    ok, encoded = cv2.imencode(".png", image)
    if not ok:
        raise WorkingRevisionBlocked("PREVIEW_ENCODING_FAILED")
    tmp = directory / ("." + uuid.uuid4().hex + ".p0tmp")
    try:
        _write_new(tmp, encoded.tobytes())
        os.replace(tmp, target)
    finally:
        tmp.unlink(missing_ok=True)
    return target
