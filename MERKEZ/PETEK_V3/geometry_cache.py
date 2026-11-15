"""Bounded, immutable PETEK geometry cache.

The cache stores only derived geometry (never source pixels, masks, or four
corners).  Entries are keyed by the source/mask SHA and quad, and are written
atomically.  A bad or stale entry is ignored and recomputed; cache failures
must never change production semantics.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
import copy
from pathlib import Path
from typing import Any

import numpy as np

_LOCK = threading.RLock()
_MEMORY: dict[str, tuple[list[dict[str, Any]], dict[str, Any]]] = {}
_MAX_MEMORY = 64


def cache_key(source_sha: str, mask_sha: str, quad, recipe: str) -> str:
    payload = {
        "source_sha": str(source_sha),
        "mask_sha": str(mask_sha),
        "quad": [[round(float(p[0]), 6), round(float(p[1]), 6)] for p in quad],
        "recipe": str(recipe),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _path(root: Path, key: str) -> Path:
    return Path(root).resolve() / f"{key}.json"


def load(root: Path | None, key: str):
    with _LOCK:
        hit = _MEMORY.get(key)
        if hit is not None:
            return copy.deepcopy(hit)
    if root is None:
        return None
    path = _path(root, key)
    try:
        if path.is_symlink() or path.stat().st_size > 2_000_000:
            return None
        obj = json.loads(path.read_text(encoding="utf-8"))
        body = json.dumps(obj["data"], sort_keys=True, separators=(",", ":"), allow_nan=False)
        if obj.get("schema") != 1 or obj.get("key") != key or hashlib.sha256(body.encode()).hexdigest() != obj.get("sha256"):
            return None
        obj = obj["data"]
        slots = obj["slots"]
        measured = obj["measured"]
        homography = np.asarray(measured["homography"], dtype=np.float64)
        if homography.shape != (3, 3) or not np.isfinite(homography).all():
            return None
        measured = dict(measured, homography=homography)
        if not isinstance(slots, list) or not isinstance(measured.get("count"), int):
            return None
        value = (slots, measured)
        with _LOCK:
            _MEMORY[key] = value
            while len(_MEMORY) > _MAX_MEMORY:
                _MEMORY.pop(next(iter(_MEMORY)))
        return copy.deepcopy(value)
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        return None


def store(root: Path | None, key: str, slots, measured) -> None:
    value = copy.deepcopy((slots, measured))
    with _LOCK:
        _MEMORY[key] = value
        while len(_MEMORY) > _MAX_MEMORY:
            _MEMORY.pop(next(iter(_MEMORY)))
    if root is None:
        return
    directory = Path(root).resolve()
    if directory.is_symlink():
        return
    directory.mkdir(parents=True, exist_ok=True)
    path = _path(directory, key)
    if path.is_symlink():
        return
    serial = dict(measured)
    homography = serial.get("homography")
    serial["homography"] = np.asarray(homography, dtype=float).tolist() if homography is not None else None
    data = {"slots": slots, "measured": serial}
    body = json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False)
    payload = json.dumps({"schema": 1, "key": key, "data": data,
                          "sha256": hashlib.sha256(body.encode()).hexdigest()},
                         ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    fd, temp = tempfile.mkstemp(prefix=".petek-geometry-", suffix=".tmp", dir=str(directory))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
