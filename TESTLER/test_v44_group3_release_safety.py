"""Group 3: source-safe SQLite online snapshots, read-only audit and 1000-item ledger simulation."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "MERKEZ"))
from URETIM_V4.final_guard_v44 import (
    BACKUP_CONFIRM, inspect_workspaces, backup_and_restore_trial,
    backup_manifest_verify,
)
from URETIM_V4.unified_batch import UnifiedV4Ledger
from URETIM_V4.crash_recovery import inspect_interrupted_state, recover_interrupted_state


def _make_pair(base: Path):
    runtime = base / "OneDrive" / "Runtime"
    state = base / "LOCALAPPDATA" / "GorselMockup" / "UnifiedV4"
    legacy = runtime / "SABLON_V2_MIMARI"
    legacy.mkdir(parents=True)
    state.mkdir(parents=True)
    old = legacy / "ayarlar.db"
    con = sqlite3.connect(old)
    con.execute("CREATE TABLE categories(id INTEGER PRIMARY KEY, name TEXT)")
    con.execute("CREATE TABLE templates(id INTEGER PRIMARY KEY, name TEXT)")
    con.execute("CREATE TABLE template_profiles(id INTEGER PRIMARY KEY, surface_quad TEXT)")
    con.execute("INSERT INTO template_profiles(surface_quad) VALUES ('[[1,2],[3,4],[5,6],[7,8]]')")
    con.commit(); con.close()
    ledger = UnifiedV4Ledger(state)
    return runtime, state, old, ledger


def _fields(state: Path, n: int):
    k = f"synthetic-{n:07d}"
    dest = state / "uretilen_gorseller" / "LOCAL" / "03_Ahsap_Tablo" / (k + ".png")
    return {"key": k, "sku": "AHT-TEST-" + str(n), "category": "03_Ahsap_Tablo",
            "art_sha": "art-sha", "template_sha": "template-sha", "mask_sha": "mask-sha",
            "art_name": "test.png", "uid": "SYN-" + str(n), "output": str(dest)}


def test_audit_makes_no_folder_when_neither_workspace_exists(tmp_path):
    live = tmp_path / "missing"
    state = tmp_path / "not-created"
    res = inspect_workspaces(live, state)
    assert res["mode"] == "READ_ONLY"
    assert res["alerts"] and not state.exists() and not live.exists()


def test_read_only_audit_sha_and_status(tmp_path):
    runtime, state, old, ledger = _make_pair(tmp_path)
    fields = _fields(state, 1)
    rec = ledger.reserve(fields)
    p = Path(fields["output"]); p.parent.mkdir(parents=True)
    p.write_bytes(b"known immutable synthetic image payload")
    sha = hashlib.sha256(p.read_bytes()).hexdigest()
    ledger.complete(fields["key"], sha)
    before_db = old.read_bytes(); before_out = p.read_bytes()
    report = inspect_workspaces(runtime, state)
    assert report["db"]["approved_geometry"]["counts"]["template_profiles"] == 1
    assert report["production"]["verified"] == 1
    assert report["production"]["unfinished"] == 0
    assert old.read_bytes() == before_db and p.read_bytes() == before_out
    p.write_bytes(b"tampered")
    report = inspect_workspaces(runtime, state)
    assert report["production"]["sha_mismatch"] == 1
    assert not report["safe_to_claim_final"]


def test_backup_requires_explicit_approval(tmp_path):
    runtime, state, _, ledger = _make_pair(tmp_path)
    root = tmp_path / "safe-backups"
    with pytest.raises(PermissionError):
        backup_and_restore_trial(runtime, state, destination_root=root)
    assert not root.exists()


def test_both_dbs_backup_and_restore_trial_without_live_write(tmp_path):
    runtime, state, legacy_db, ledger = _make_pair(tmp_path)
    old_content = legacy_db.read_bytes()
    new_content = ledger.file.read_bytes()
    result = backup_and_restore_trial(runtime, state, destination_root=tmp_path / "local-safe",
                                      confirm=BACKUP_CONFIRM)
    assert result["restore_trial"] == "PASS"
    receipt = Path(result["report_path"])
    assert receipt.is_file()
    assert backup_manifest_verify(receipt) == {
        "approved_geometry": "SHA_AND_SQLITE_VERIFIED", "production_ledger": "SHA_AND_SQLITE_VERIFIED"
    }
    assert result["snapshots"]["approved_geometry"]["restored_counts"]["template_profiles"] == 1
    assert legacy_db.read_bytes() == old_content and ledger.file.read_bytes() == new_content
    path = receipt.parent / "approved_geometry.sqlite3"
    path.write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="SHA"):
        backup_manifest_verify(receipt)


def test_backup_works_with_live_uncheckpointed_wal(tmp_path):
    runtime, state, legacy_db, ledger = _make_pair(tmp_path)
    anchor = sqlite3.connect(legacy_db)
    try:
        anchor.execute("PRAGMA journal_mode=WAL")
        anchor.execute("INSERT INTO template_profiles(surface_quad) VALUES ('WAL_CHANGE')")
        anchor.commit()  # in WAL; database main file might not contain this committed row yet
        result = backup_and_restore_trial(runtime, state, destination_root=tmp_path / "safe-local",
                                          confirm=BACKUP_CONFIRM)
        assert result["snapshots"]["approved_geometry"]["restored_counts"]["template_profiles"] == 2
        assert backup_manifest_verify(Path(result["report_path"]))["approved_geometry"] == "SHA_AND_SQLITE_VERIFIED"
    finally:
        anchor.close()


def test_backup_does_not_write_into_cloud(tmp_path):
    runtime, state, *_ = _make_pair(tmp_path)
    path = tmp_path / "OneDrive" / "Backups"
    with pytest.raises(ValueError, match="bulut"):
        backup_and_restore_trial(runtime, state, destination_root=path, confirm=BACKUP_CONFIRM)
    assert not path.exists()


def test_one_thousand_synthetic_ledger_reservations_and_reuses(tmp_path):
    state = tmp_path / "app-state"
    ledger = UnifiedV4Ledger(state)
    for n in range(1000):
        fields = _fields(state, n)
        record = ledger.reserve(fields)
        assert record["status"] == "PENDING"
        output = Path(fields["output"])
        output.parent.mkdir(parents=True, exist_ok=True)
        payload = ("synthetic-image-" + str(n)).encode("ascii")
        output.write_bytes(payload)
        ledger.complete(fields["key"], hashlib.sha256(payload).hexdigest())
        assert ledger.reserve(fields)["status"] == "RENDERED"
    assert len(ledger.successful()) == 1000
    report = inspect_workspaces(tmp_path / "missing", state)
    assert report["production"]["verified"] == 1000
    assert report["production"]["sha_mismatch"] == 0
    assert report["production"]["missing"] == 0


def test_two_independent_processes_cannot_take_same_os_lock(tmp_path):
    lock = tmp_path / "job.lock"
    script = "import os,sys; fd=os.open(sys.argv[1],os.O_CREAT|os.O_EXCL|os.O_WRONLY); os.write(fd,b'123'); os.close(fd)"
    cmd = [sys.executable, "-c", script, str(lock)]
    first = subprocess.run(cmd, capture_output=True, text=True)
    second = subprocess.run(cmd, capture_output=True, text=True)
    assert first.returncode == 0
    assert second.returncode != 0
    assert lock.read_bytes() == b"123"


@pytest.mark.parametrize("round_no", [1, 2])
def test_two_independent_crash_recovery_trials(tmp_path, round_no):
    runtime, state, old, ledger = _make_pair(tmp_path)
    info = _fields(state, round_no)
    ledger.reserve(info)
    output = Path(info["output"])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(b"INCOMPLETE_IMG")
    lock = state / "V4_ORTAK_FABRIKA.lock"
    lock.write_text("999999991", encoding="ascii")
    check = inspect_interrupted_state(ledger.file, lock, state / "uretilen_gorseller")
    assert check["interrupted_pending_count"] == 1
    assert check["can_recover_safely"]
    with pytest.raises(Exception, match="açık kullanıcı onayı"):
        recover_interrupted_state(ledger.file, lock, state / "uretilen_gorseller",
                                  state / "raporlar", reviewer="TEST", confirm="NO")
    assert output.exists()
    result = recover_interrupted_state(ledger.file, lock, state / "uretilen_gorseller",
                                     state / "raporlar", reviewer="TEST", confirm="I_APPROVE_SAFE_CRASH_RECOVERY")
    assert not output.exists() and not lock.exists()
    assert result["quarantined_partial_files"]
    dest = Path(result["quarantined_partial_files"][0]["quarantined_to"])
    assert dest.read_bytes() == b"INCOMPLETE_IMG"
    assert ledger.reserve(info)["status"] == "PENDING"


def test_audit_does_not_trust_output_path_outside_managed_root(tmp_path):
    runtime, state, old, ledger = _make_pair(tmp_path)
    info = _fields(state, 9)
    outside = tmp_path / "personally_owned_original.png"
    outside.write_bytes(b"personally_owned_original")
    info["output"] = str(outside)
    ledger.reserve(info)
    result = inspect_workspaces(runtime, state)
    assert result["production"]["unfinished"] == 1
    assert outside.read_bytes() == b"personally_owned_original"
