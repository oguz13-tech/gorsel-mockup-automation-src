"""Shared durable checkpoint and actionable error helpers.

The file is deliberately independent from the template database: it stores
only job input identities, per-item outcomes and a cursor.  Writes are atomic
so an interrupted process never destroys the last usable checkpoint.
"""
from __future__ import annotations
import hashlib, json, os, tempfile, traceback
from datetime import datetime, timezone
from pathlib import Path

def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)

def _atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = dict(payload)
    body["checkpoint_sha256"] = hashlib.sha256(_json(payload).encode("utf-8")).hexdigest()
    fd, name = tempfile.mkstemp(prefix=".resume-", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(body, fh, ensure_ascii=False, indent=2)
            fh.flush(); os.fsync(fh.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)

def read(path: Path) -> dict | None:
    path = Path(path)
    if not path.is_file() or path.is_symlink(): return None
    try:
        body = json.loads(path.read_text(encoding="utf-8"))
        digest = body.pop("checkpoint_sha256", None)
        if digest != hashlib.sha256(_json(body).encode("utf-8")).hexdigest(): return None
        return body
    except (OSError, ValueError, TypeError): return None

def update(path: Path, *, job: str, items: list[dict], cursor: int, status: str,
           errors: list[dict] | None = None, meta: dict | None = None) -> None:
    _atomic(Path(path), {"schema": 1, "job": job, "updated_at": datetime.now(timezone.utc).isoformat(),
                         "items": items, "cursor": int(cursor), "status": status,
                         "errors": errors or [], "meta": meta or {}})

def error_record(*, item: str, exc: BaseException, action: str, kind: str = "ITEM_ERROR", **extra) -> dict:
    return {"item": item, "kind": kind, "error": f"{type(exc).__name__}: {exc}",
            "action": action, "traceback": traceback.format_exc(limit=8), **extra}

def advisor(kind: str, message: str) -> str:
    hints = {
        "TEMPLATE": "Şablon dosyasını açıp okunabilirliğini, uzantısını ve kayıtlı 4 köşe/maskesini kontrol edin; düzelttikten sonra Devam Et'e basın.",
        "UPLOAD": "API anahtarını, internet bağlantısını ve sağlayıcı limitini kontrol edin; yalnız hatalı satırları yeniden deneyin.",
        "OVERLAY": "İlgili PETEK ölçü katmanını (76/96/116/136) ve 1200x300 sözleşmesini kontrol edin; temiz kaynağı değiştirmeyin.",
    }
    return hints.get(kind, "Hatalı öğeyi düzeltin, hata raporundaki yolu kontrol edin ve En Son Kaldığım Yerden Devam Et düğmesine basın.") + " " + message
