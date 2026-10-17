"""Actual release transaction contracts on synthetic fake directories ONLY."""
import hashlib
import contextlib
import json
import sqlite3
import tempfile
from pathlib import Path

import pytest
from scripts import p0_release_transaction as release


def scenario(root):
    source = root / "release_source"
    code = root / "code_clone"
    runtime = root / "runtime_FAKE"
    vault = root / "OUTSIDE_BACKUP_VAULT"
    source.mkdir(); code.mkdir(); runtime.mkdir()
    for i, rel in enumerate(release.RELEASE_FILES):
        src = source / rel
        dst = code / rel
        src.parent.mkdir(parents=True, exist_ok=True)
        dst.parent.mkdir(parents=True, exist_ok=True)
        src.write_bytes(("NEW_CODE:" + str(i)).encode("utf-8"))
        if i % 2 == 0:
            dst.write_bytes(("OLD_CODE:" + str(i)).encode("utf-8"))
    db = runtime / "SABLON_V2_MIMARI" / "ayarlar.db"
    db.parent.mkdir(parents=True)
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE evidence(name TEXT)")
    conn.execute("INSERT INTO evidence VALUES ('UNCHANGED')")
    conn.commit(); conn.close()
    js = runtime / "ayarlar.json"
    js.write_bytes(b'{"safe":"unchanged"}')
    (runtime / "2_SABLON_HAVUZU_ORIJINAL_YEDEK").mkdir()
    (runtime / "2_SABLON_HAVUZU" / "01_Wifi_Kutusu").mkdir(parents=True)
    original = runtime / "2_SABLON_HAVUZU_ORIJINAL_YEDEK" / "original.png"
    original.write_bytes(b"ORIGINAL_SNAPSHOT_CANNOT_TOUCH")
    return source, code, runtime, vault, original, js, db


def checksum(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_release_plan_backup_install_and_code_rollback_leave_runtime_untouched():
    with tempfile.TemporaryDirectory() as tmp:
        source, code, runtime, vault, original, js, db = scenario(Path(tmp))
        evidence = {str(p):checksum(p) for p in (original, js, db)}
        assert release.plan(source, code, runtime, vault)["runtime_mutation"] is False
        assert not vault.exists()
        snapshot = release.create_snapshot(source, code, runtime, vault)
        assert snapshot["status"] == "SNAPSHOT_READY"
        assert all(checksum(p)==digest for p,digest in
                   [(original, evidence[str(original)]), (js, evidence[str(js)]), (db,evidence[str(db)])])
        # backup contains SQLite independently with validated integrity
        copied_db = Path(snapshot["snapshot"]) / "runtime_snapshot" / "SABLON_V2_MIMARI" / "ayarlar.db"
        assert copied_db.is_file()
        with contextlib.closing(sqlite3.connect(copied_db)) as conn:
            assert conn.execute("SELECT name FROM evidence").fetchone() == ("UNCHANGED",)
        with pytest.raises(release.ReleaseBlocked):
            release.install(snapshot["snapshot"], approval="")
        result = release.install(snapshot["snapshot"], approval="INSTALL_CODE_ONLY")
        assert result["status"] == "INSTALLED_CODE_ONLY"
        for rel in release.RELEASE_FILES:
            assert (code / rel).read_bytes() == (source / rel).read_bytes()
        assert {str(p):checksum(p) for p in (original,js,db)} == evidence
        with pytest.raises(release.ReleaseBlocked):
            release.rollback(snapshot["snapshot"], approval="")
        undone = release.rollback(snapshot["snapshot"], approval="ROLLBACK_CODE_ONLY")
        assert undone["status"] == "ROLLED_BACK_CODE_ONLY"
        for i, rel in enumerate(release.RELEASE_FILES):
            dest = code / rel
            if i%2 == 0:
                assert dest.read_bytes() == ("OLD_CODE:"+str(i)).encode("utf-8")
            else:
                assert not dest.exists()
        assert {str(p):checksum(p) for p in (original,js,db)} == evidence


def test_release_refuses_overwritten_target_since_backup():
    with tempfile.TemporaryDirectory() as tmp:
        source, code, runtime, vault, *_ = scenario(Path(tmp))
        snapshot = release.create_snapshot(source, code, runtime, vault)
        old = code / release.RELEASE_FILES[0]
        old.write_bytes(b"OTHER_PERSON_EDIT")
        with pytest.raises(release.ReleaseBlocked, match="CODE_CHANGED_SINCE_SNAPSHOT"):
            release.install(snapshot["snapshot"], approval="INSTALL_CODE_ONLY")
        assert old.read_bytes() == b"OTHER_PERSON_EDIT"


def test_rollback_refuses_to_overwrite_post_install_user_edit():
    with tempfile.TemporaryDirectory() as tmp:
        source, code, runtime, vault, *_ = scenario(Path(tmp))
        snapshot = release.create_snapshot(source, code, runtime, vault)
        release.install(snapshot["snapshot"], approval="INSTALL_CODE_ONLY")
        edited = code / release.RELEASE_FILES[1]
        edited.write_bytes(b"SOMEONE_CHANGED_NEW_CODE")
        with pytest.raises(release.ReleaseBlocked, match="INSTALLED_CODE_CHANGED"):
            release.rollback(snapshot["snapshot"], approval="ROLLBACK_CODE_ONLY")
        assert edited.read_bytes() == b"SOMEONE_CHANGED_NEW_CODE"
