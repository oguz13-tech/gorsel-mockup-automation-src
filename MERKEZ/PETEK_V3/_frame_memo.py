"""Process-local, content-keyed memo for heavy *pure* scene intermediates.

Only deterministic read-only evidence is shared (HSV views, magenta evidence,
light fields, marker candidates, wall classifications).  Pixel-repair stages
that write into image buffers are never cached, so every independent safety
replay still compares full arrays produced for THIS call's inputs.  A cached
value is byte-identical to a freshly computed one because the key is a
cryptographic hash of the full input buffers; nothing about the recipe,
protection gates or output bytes changes.

Set environment variable ``V4_FRAME_MEMO=0`` to disable caching entirely
(every call recomputes, restoring the previous behaviour exactly).
The cache is bounded; entries hold full frames and stay few.
"""
from __future__ import annotations

import hashlib
import os
import threading
from collections import OrderedDict
from typing import Any, Callable

import numpy as np

_ENV = "V4_FRAME_MEMO"
_MAX_ENTRIES = 10
_lock = threading.Lock()
_cache: "OrderedDict[tuple, Any]" = OrderedDict()


def frame_key(*arrays: np.ndarray) -> str:
    """Content identity for ndarray inputs (dtype, shape, bytes)."""
    h = hashlib.blake2b(digest_size=16)
    for arr in arrays:
        a = arr if arr.flags.c_contiguous else np.ascontiguousarray(arr)
        h.update(str(a.dtype).encode())
        h.update(str(a.shape).encode())
        if a.ndim:
            h.update(memoryview(a).cast("B"))
        else:
            h.update(b"scalar")
    return h.hexdigest()


def _enabled() -> bool:
    return os.environ.get(_ENV, "1") != "0"


def _freeze(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        view = value.view()
        view.flags.writeable = False
        return view
    if isinstance(value, tuple):
        frozen = []
        for item in value:
            if isinstance(item, np.ndarray) and item.flags.writeable:
                view = item.view()
                view.flags.writeable = False
                frozen.append(view)
            else:
                frozen.append(item)
        return tuple(frozen)
    return value


def get_or_compute(tag: str, key_arrays: tuple[np.ndarray, ...],
                   builder: Callable[[], Any], *,
                   freeze: bool = True,
                   clone: bool = False) -> Any:
    """Return the cached *tag* result for the exact input content, else build it.

    ``builder`` runs outside the lock (concurrent duplicate work is harmless and
    deterministic).  Cached arrays are stored frozen; ``clone=True`` hands the
    caller a writable copy (for functions whose callers mutate the result, e.g.
    boolean mask refinement) while the cached original stays pristine.
    """
    if not _enabled():
        return builder()
    key = (tag, frame_key(*key_arrays))
    with _lock:
        hit = _cache.get(key)
        if hit is not None:
            _cache.move_to_end(key)
            return hit.copy() if clone else hit
    value = builder()
    stored = _freeze(value) if freeze else value
    with _lock:
        _cache[key] = stored
        _cache.move_to_end(key)
        while len(_cache) > _MAX_ENTRIES:
            _cache.popitem(last=False)
    return stored.copy() if clone else stored


def clear() -> None:
    with _lock:
        _cache.clear()


def stats() -> dict:
    with _lock:
        return {"entries": len(_cache), "max_entries": _MAX_ENTRIES,
                "enabled": _enabled()}
