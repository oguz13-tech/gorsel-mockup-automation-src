"""Create-only output and durable rename snapshots. Never overwrite user bytes."""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
from pathlib import Path
import uuid


def reject_redirect(path):
    path = Path(path).absolute()
    for item in (path, *path.parents):
        if item.is_symlink():
            raise ValueError("FILE_PATH_SYMLINK_BLOCKED:" + str(item))
        if item.exists():
            tag = getattr(item.lstat(), "st_reparse_tag", 0)
            # OneDrive cloud placeholders are allowed; junctions are not.
            if tag in (0xA0000003, 0xA000000C):
                raise ValueError("FILE_PATH_JUNCTION_BLOCKED:" + str(item))


def sha256_file(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def write_manifest(path, data):
    path = Path(path)
    temp = path.with_name("." + uuid.uuid4().hex + ".journal-tmp")
    try:
        with temp.open("xb") as stream:
            stream.write(json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def copy_exclusive(source, destination):
    """Copy to a private temporary file, then atomically create a new name."""
    source, destination = Path(source), Path(destination)
    reject_redirect(source)
    reject_redirect(destination)
    temp = destination.with_name("." + uuid.uuid4().hex + ".copy-tmp")
    try:
        with source.open("rb") as src, temp.open("xb") as dst:
            for chunk in iter(lambda: src.read(1024 * 1024), b""):
                dst.write(chunk)
            dst.flush()
            os.fsync(dst.fileno())
        os.link(temp, destination)
    finally:
        temp.unlink(missing_ok=True)


def move_create_only(source, destination):
    """Same-volume move with no replace fallback; failed unlink retains both."""
    source, destination = Path(source), Path(destination)
    reject_redirect(source)
    reject_redirect(destination)
    os.link(source, destination)
    if not os.path.samefile(source, destination):
        raise RuntimeError("MOVE_SOURCE_CHANGED_RECOVERY_REQUIRED")
    source.unlink()


def save_image_create_only(image, desired, *, format, unique=True, **kwargs):
    """No exists-then-save race; complete bytes are published with os.link."""
    desired = Path(desired)
    reject_redirect(desired)
    temp = desired.with_name("." + uuid.uuid4().hex + ".image-tmp")
    try:
        with temp.open("xb") as stream:
            image.save(stream, format=format, **kwargs)
            stream.flush()
            os.fsync(stream.fileno())
        for index in range(1, 10000 if unique else 2):
            candidate = desired if index == 1 else desired.with_name(
                desired.stem + "_" + str(index) + desired.suffix
            )
            try:
                os.link(temp, candidate)
                return candidate
            except FileExistsError:
                if not unique:
                    raise
        raise RuntimeError("OUTPUT_NAME_LIMIT_REACHED")
    finally:
        temp.unlink(missing_ok=True)


@contextlib.contextmanager
def rename_safety_transaction(selected, targets):
    """Permanent byte snapshots and journal BEFORE the first source rename.

    A crash leaves this directory's lock and a recoverable manifest. Do not
    auto-delete a stale lock or restore over a changed path.
    """
    from .template_identity import same_stem_files

    parent = selected[0].parent
    reject_redirect(parent)
    vault = parent / "_GORSEL_ISIMLENDIRME_YEDEKLERI"
    reject_redirect(vault)
    vault.mkdir(exist_ok=True)
    lock = vault / "RENAME_IN_PROGRESS.lock"
    token = uuid.uuid4().hex
    try:
        fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise RuntimeError("RENAME_BUSY_OR_RECOVERY_REQUIRED:" + str(vault)) from exc
    txn = None
    data = None
    safe_to_unlock = True
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(token.encode("ascii")); handle.flush(); os.fsync(handle.fileno())
        for target in targets:
            if same_stem_files(parent, target.name, ignore_paths=selected):
                raise FileExistsError("RENAME_IDENTITY_COLLISION:" + target.name)
        txn = vault / token
        txn.mkdir()
        raw = txn / "raw"
        raw.mkdir()
        data = {"version": "NUMBER_GUARD_V2", "state": "PREPARING", "files": []}
        journal = txn / "manifest.json"
        write_manifest(journal, data)
        for index, (source, target) in enumerate(zip(selected, targets)):
            reject_redirect(source)
            snapshot = raw / (str(index) + source.suffix.lower())
            before = sha256_file(source)
            copy_exclusive(source, snapshot)
            if sha256_file(snapshot) != before or sha256_file(source) != before:
                raise RuntimeError("SOURCE_CHANGED_DURING_RENAME_SNAPSHOT")
            data["files"].append({"source": str(source), "target": str(target),
                                   "snapshot": str(snapshot), "sha256": before})
            write_manifest(journal, data)
        data["state"] = "READY"
        write_manifest(journal, data)
        try:
            yield txn
            for item in data["files"]:
                if sha256_file(item["target"]) != item["sha256"]:
                    raise RuntimeError("RENAME_OUTPUT_SHA_MISMATCH")
            data["state"] = "COMMITTED"
            write_manifest(journal, data)
        except BaseException:
            # The renamer normally rolls back. Restore a missing original from
            # an independent byte snapshot if its temporary name was removed.
            recovered = True
            for item in data["files"]:
                original = Path(item["source"])
                try:
                    if not original.exists():
                        copy_exclusive(item["snapshot"], original)
                    if sha256_file(original) != item["sha256"]:
                        recovered = False
                except OSError:
                    recovered = False
            data["state"] = "ROLLED_BACK" if recovered else "RECOVERY_REQUIRED"
            safe_to_unlock = recovered
            write_manifest(journal, data)
            raise
    finally:
        if safe_to_unlock and lock.is_file() and lock.read_text(encoding="ascii") == token:
            lock.unlink()
