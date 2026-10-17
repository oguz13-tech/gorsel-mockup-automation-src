"""Schema migration rehearsal on SQLite backup, never on a live DB."""
import hashlib
import contextlib
import sqlite3
import tempfile
from pathlib import Path

from scripts.p0_db_migration_gate import simulate


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def test_legacy_sqlite_rehearsal_does_not_modify_source_database():
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="p0-migration-sim-") as tmp:
        fake = Path(tmp) / "FAKE_RUNTIME"
        backup_vault = Path(tmp) / "OFFLINE_TEST_BACKUP"
        db = fake / "SABLON_V2_MIMARI" / "ayarlar.db"
        db.parent.mkdir(parents=True)
        conn = sqlite3.connect(db)
        conn.execute("""CREATE TABLE template_profiles(
           template_uid TEXT UNIQUE,category TEXT,source_relative_path TEXT,
           review_status TEXT, manually_verified INTEGER
        )""")
        conn.execute("""INSERT INTO template_profiles
          VALUES('T-1','01_Wifi_Kutusu','01_Wifi_Kutusu/test.png','APPROVED',1)""")
        conn.commit(); conn.close()
        original_hash = sha(db)
        result = simulate(fake,backup_vault,root)
        assert result["status"] == "SIMULATED_SCHEMA_MIGRATION_PASS_NOT_LIVE_APPROVAL"
        assert result["before_counts"]["template_profiles"] == 1
        assert result["after_counts"]["template_profiles"] == 1
        assert result["production_db_modified"] is False
        assert sha(db) == original_hash
        copy = Path(result["snapshot"])
        assert copy.is_file()
        with contextlib.closing(sqlite3.connect(copy)) as conn:
            cols = {row[1] for row in conn.execute("PRAGMA table_info(template_profiles)")}
            assert {"nominal_aspect", "is_active"}.issubset(cols)
            assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
