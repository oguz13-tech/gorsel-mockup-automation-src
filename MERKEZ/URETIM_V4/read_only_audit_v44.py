"""Strict read-only 7-category production SHA report for the Advanced menu.

Unlike constructing UnifiedV4Batch or PETEK Registry, this does not create
folders, SQLite files/tables, log handlers, or lock state.
"""
from __future__ import annotations
import hashlib
from pathlib import Path
import sqlite3

from .unified_batch import store_v4_root


def inspect(root: Path | None = None) -> dict[str, int]:
    root = Path(root or store_v4_root()).resolve()
    db = root / "v4_ortak_uretim.sqlite3"
    output_root = (root / "uretilen_gorseller").resolve()
    if db.is_symlink() or (root / "uretilen_gorseller").is_symlink():
        raise ValueError("SHA denetimi: sembolik bağlantı güvensiz.")
    if not db.is_file():
        return {"total": 0, "verified": 0, "review_required": 0}
    uri = db.resolve(strict=True).as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as con:
        con.row_factory = sqlite3.Row
        rows = [dict(v) for v in con.execute(
            "SELECT status, output, output_sha FROM artifact ORDER BY key"
        )]
    verified = 0
    for row in rows:
        p = Path(row["output"])
        if row["status"] != "RENDERED" or p.is_symlink() or not p.is_file():
            continue
        rp = p.resolve()
        if output_root not in rp.parents:
            continue
        h = hashlib.sha256()
        with rp.open("rb") as f:
            for block in iter(lambda: f.read(1024 * 1024), b""):
                h.update(block)
        if h.hexdigest() == row["output_sha"]:
            verified += 1
    return {"total": len(rows), "verified": verified, "review_required": len(rows) - verified}
