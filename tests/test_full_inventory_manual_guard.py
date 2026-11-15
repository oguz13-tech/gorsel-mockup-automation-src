"""Manual mockup may NEVER bypass source-bound human approval."""
import hashlib
import sqlite3
import tempfile
from pathlib import Path

from SABLON_V2_MIMARI.core.manual_production_guard import (
    SourceApprovalBlocked, verify_approved_source,
)

CAT="01_Wifi_Kutusu"
NAME="Wifi_Kutusu_001.png"


def test_manual_render_requires_source_approved_geometry():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        path=root/"2_SABLON_HAVUZU"/CAT/NAME
        path.parent.mkdir(parents=True)
        path.write_bytes(b"TEST_BACKGROUND")
        db=root/"SABLON_V2_MIMARI"/"ayarlar.db"
        db.parent.mkdir()
        conn=sqlite3.connect(db)
        conn.execute("""CREATE TABLE template_profiles (
            category TEXT, source_relative_path TEXT, source_asset_sha256 TEXT,
            review_status TEXT, manually_verified INTEGER, is_active INTEGER,
            surface_quad TEXT, orientation TEXT, nominal_aspect REAL,
            has_occlusion INTEGER)""")
        conn.execute("INSERT INTO template_profiles VALUES (?,?,?,?,?,?,?,?,?,?)",
            (CAT,f"{CAT}/{NAME}",hashlib.sha256(path.read_bytes()).hexdigest(),
             "APPROVED",1,1,"[[1,1],[7,1],[7,7],[1,7]]","H",1.333,0))
        conn.commit();conn.close()
        assert verify_approved_source(root,CAT,path)["status"]=="APPROVED"
        path.write_bytes(b"CHANGED")
        try:
            verify_approved_source(root,CAT,path)
        except SourceApprovalBlocked:
            pass
        else:
            raise AssertionError("stale template accepted")


def test_manual_render_rejects_missing_db():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        path=root/"2_SABLON_HAVUZU"/CAT/NAME
        path.parent.mkdir(parents=True)
        path.write_bytes(b"TEST")
        try:
            verify_approved_source(root,CAT,path)
        except SourceApprovalBlocked:
            pass
        else:
            raise AssertionError("missing DB allowed")


def test_manual_launcher_requires_explicit_runtime_and_no_false_success():
    repo=Path(__file__).resolve().parents[1]
    content=(repo/"MANUEL_GORSELLERDEN_MOCKUP_URET.bat").read_text("utf-8")
    assert "MOCKUP_RUNTIME_WORKSPACE" in content
    assert "if errorlevel 1" in content
