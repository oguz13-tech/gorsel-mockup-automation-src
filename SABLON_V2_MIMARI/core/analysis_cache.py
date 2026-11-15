import json

from core.db import get_db_connection


def _json_default(value):
    if hasattr(value, "item"):
        return value.item()
    if hasattr(value, "tolist"):
        return value.tolist()
    raise TypeError(
        f"Analysis cache cannot serialize {type(value).__name__}"
    )


def load_analysis_cache(
    category: str,
    source_sha256: str,
    analyzer_version: str,
):
    conn = get_db_connection()
    try:
        row = conn.execute(
            """SELECT analysis_json
               FROM analysis_cache
               WHERE category=?
                 AND source_asset_sha256=?
                 AND analyzer_version=?""",
            (
                str(category),
                str(source_sha256),
                str(analyzer_version),
            ),
        ).fetchone()
        if row is None:
            return None

        conn.execute(
            """UPDATE analysis_cache
               SET hit_count=hit_count+1,
                   last_used_at=CURRENT_TIMESTAMP
               WHERE category=?
                 AND source_asset_sha256=?
                 AND analyzer_version=?""",
            (
                str(category),
                str(source_sha256),
                str(analyzer_version),
            ),
        )
        conn.commit()
        payload = json.loads(row["analysis_json"])
        if isinstance(payload, dict):
            payload["_cache_hit"] = True
            return payload
        return None
    finally:
        conn.close()


def save_analysis_cache(
    category: str,
    source_sha256: str,
    analyzer_version: str,
    analysis: dict,
):
    if not isinstance(analysis, dict):
        raise ValueError("Analysis cache payload must be a dict.")

    clean = dict(analysis)
    clean.pop("_cache_hit", None)
    serialized = json.dumps(
        clean,
        ensure_ascii=False,
        separators=(",", ":"),
        default=_json_default,
    )

    conn = get_db_connection()
    try:
        conn.execute(
            """INSERT INTO analysis_cache (
                   category, source_asset_sha256,
                   analyzer_version, analysis_json
               ) VALUES (?, ?, ?, ?)
               ON CONFLICT(
                   category, source_asset_sha256, analyzer_version
               ) DO UPDATE SET
                   analysis_json=excluded.analysis_json,
                   last_used_at=CURRENT_TIMESTAMP""",
            (
                str(category),
                str(source_sha256),
                str(analyzer_version),
                serialized,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def cache_stats() -> dict:
    conn = get_db_connection()
    try:
        row = conn.execute(
            """SELECT COUNT(*) AS entry_count,
                      COALESCE(SUM(hit_count), 0) AS hit_count
               FROM analysis_cache"""
        ).fetchone()
        return {
            "entry_count": int(row["entry_count"] or 0),
            "hit_count": int(row["hit_count"] or 0),
        }
    finally:
        conn.close()
