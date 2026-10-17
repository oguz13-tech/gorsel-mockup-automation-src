"""SQLite Backup API proof using a disposable fake runtime, never production."""
import hashlib
import sqlite3
import tempfile
from pathlib import Path
import pytest
from scripts.p0_sqlite_consistent_snapshot import snapshot


def test_sqlite_backup_captures_committed_data_and_keeps_source():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        runtime=root/"fake"
        db=runtime/"SABLON_V2_MIMARI"/"ayarlar.db"
        db.parent.mkdir(parents=True)
        live=sqlite3.connect(db)
        try:
            live.execute("CREATE TABLE templates(id TEXT PRIMARY KEY, name TEXT)")
            live.execute("INSERT INTO templates VALUES('1','ORIGINAL')")
            live.commit()
            original=hashlib.sha256(db.read_bytes()).hexdigest()
            result=snapshot(runtime,root/"offline-snapshot")
            backed=sqlite3.connect(result["database_backup"])
            try:
                assert backed.execute("SELECT name FROM templates WHERE id='1'").fetchone()[0]=="ORIGINAL"
            finally:
                backed.close()
            assert hashlib.sha256(db.read_bytes()).hexdigest()==original
            assert not result["source_modified"] and not result["installation_authorized"]
        finally:
            live.close()


def test_snapshot_blocks_destination_inside_runtime():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        db=root/"SABLON_V2_MIMARI"/"ayarlar.db"
        db.parent.mkdir();sqlite3.connect(db).close()
        with pytest.raises(RuntimeError,match="SNAPSHOT_DESTINATION_MUST_BE_SEPARATE"):
            snapshot(root,root/"_KURULUM_YEDEKLERI")
