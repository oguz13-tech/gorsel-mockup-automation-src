"""Üretim geçmişi: hangi mağazaya, hangi klasörden, kaç görsel, kaç saniyede.

Mevcut ``v4_ortak_uretim.sqlite3`` içine yalnızca ek bir tablo açar; mevcut
``artifact`` kayıtlarına dokunmaz. Hata üretimi asla durdurmaz.
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

TABLE = "production_session"


def _connect(root: Path) -> sqlite3.Connection:
    con = sqlite3.connect(str(Path(root) / "v4_ortak_uretim.sqlite3"), timeout=30)
    con.row_factory = sqlite3.Row
    con.execute(f"""CREATE TABLE IF NOT EXISTS {TABLE} (
        operation_id TEXT PRIMARY KEY, started_at TEXT NOT NULL, finished_at TEXT,
        mode TEXT NOT NULL, design_folder TEXT NOT NULL, stores TEXT NOT NULL,
        design_count INTEGER NOT NULL DEFAULT 0, planned INTEGER NOT NULL DEFAULT 0,
        successful INTEGER NOT NULL DEFAULT 0, failed INTEGER NOT NULL DEFAULT 0,
        skipped INTEGER NOT NULL DEFAULT 0, elapsed_seconds REAL NOT NULL DEFAULT 0,
        seconds_per_image REAL, status TEXT NOT NULL DEFAULT 'RUNNING',
        per_store TEXT NOT NULL DEFAULT '{{}}', report_path TEXT NOT NULL DEFAULT '',
        external INTEGER NOT NULL DEFAULT 0)""")
    return con


def start_session(root: Path, *, operation_id: str, mode: str, design_folder: str,
                  stores: list[str], design_count: int, planned: int, external: bool) -> None:
    try:
        with _connect(root) as con:
            con.execute(f"""INSERT OR REPLACE INTO {TABLE}
                (operation_id, started_at, mode, design_folder, stores, design_count, planned, external)
                VALUES (?,?,?,?,?,?,?,?)""",
                        (operation_id, time.strftime("%Y-%m-%d %H:%M:%S"), mode, str(design_folder),
                         json.dumps(list(stores), ensure_ascii=False), int(design_count),
                         int(planned), int(bool(external))))
    except Exception:
        pass


def finish_session(root: Path, *, operation_id: str, status: str, successful: int, failed: int,
                   skipped: int, elapsed_seconds: float, per_store: dict, report_path: str = "") -> None:
    try:
        produced = int(successful)
        spi = round(float(elapsed_seconds) / produced, 2) if produced else None
        with _connect(root) as con:
            con.execute(f"""UPDATE {TABLE} SET finished_at=?, status=?, successful=?, failed=?,
                skipped=?, elapsed_seconds=?, seconds_per_image=?, per_store=?, report_path=?
                WHERE operation_id=?""",
                        (time.strftime("%Y-%m-%d %H:%M:%S"), status, produced, int(failed), int(skipped),
                         round(float(elapsed_seconds), 2), spi,
                         json.dumps(per_store, ensure_ascii=False), str(report_path), operation_id))
    except Exception:
        pass


def list_sessions(root: Path, limit: int = 200) -> list[dict[str, Any]]:
    """Read-only; returns [] when no history table exists yet."""
    path = Path(root) / "v4_ortak_uretim.sqlite3"
    if not path.is_file():
        return []
    try:
        with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=30) as con:
            con.row_factory = sqlite3.Row
            rows = con.execute(f"SELECT * FROM {TABLE} ORDER BY started_at DESC LIMIT ?", (int(limit),)).fetchall()
    except sqlite3.Error:
        return []
    result = []
    for row in rows:
        item = dict(row)
        for key in ("stores", "per_store"):
            try:
                item[key] = json.loads(item.get(key) or "null")
            except ValueError:
                item[key] = None
        result.append(item)
    return result


def average_seconds_per_image(root: Path, mode: str | None = None) -> float | None:
    """Gerçek geçmiş ölçümlerinden tahmini süre için ortalama (yoksa None)."""
    values = [s["seconds_per_image"] for s in list_sessions(root, 50)
              if s.get("seconds_per_image") and s.get("status") in ("LOCAL_READY", "PARTIAL")
              and (mode is None or s.get("mode") == mode) and not s.get("external")]
    return round(sum(values) / len(values), 2) if values else None
