from __future__ import annotations

import json
from pathlib import Path

import pytest

from MERKEZ.workspace_contract import (
    WorkspaceContractError,
    contract_report,
    resolve_contract,
)


def _fixture(tmp_path: Path) -> tuple[Path, Path]:
    code = tmp_path / "CODEX_ACTIVE"
    (code / "MERKEZ").mkdir(parents=True)
    (code / "SABLON_V2_MIMARI" / "core").mkdir(parents=True)
    (code / "SABLON_V2_MIMARI" / "app.py").write_text("# source", encoding="utf-8")
    (code / "SABLON_V2_MIMARI" / "core" / "db.py").write_text("# source", encoding="utf-8")
    runtime = tmp_path / "runtime"
    (runtime / "SABLON_V2_MIMARI").mkdir(parents=True)
    (runtime / "2_SABLON_HAVUZU").mkdir()
    (runtime / "2_SABLON_HAVUZU_ORIJINAL_YEDEK").mkdir()
    (runtime / "ayarlar.json").write_text("{}", encoding="utf-8")
    (runtime / "SABLON_V2_MIMARI" / "ayarlar.db").write_bytes(b"synthetic")
    return code, runtime


def test_contract_distinguishes_duplicate_template_folder_names(tmp_path):
    code, runtime = _fixture(tmp_path)
    contract = resolve_contract(code_root=code, runtime_root=runtime, validate=True)
    assert contract.code_root == code
    assert contract.runtime_root == runtime
    assert contract.database == runtime / "SABLON_V2_MIMARI" / "ayarlar.db"


def test_invalid_override_fails_closed(tmp_path):
    code, runtime = _fixture(tmp_path)
    bad = tmp_path / "stale"
    with pytest.raises(WorkspaceContractError):
        resolve_contract(code_root=code, runtime_root=bad, validate=True)


def test_live_db_in_source_is_rejected(tmp_path):
    code, runtime = _fixture(tmp_path)
    source_db = code / "SABLON_V2_MIMARI" / "ayarlar.db"
    source_db.write_bytes(b"not-live-here")
    with pytest.raises(WorkspaceContractError):
        resolve_contract(code_root=code, runtime_root=runtime, validate=True)


def test_report_is_read_only_and_explicit(tmp_path):
    code, runtime = _fixture(tmp_path)
    before = (runtime / "ayarlar.json").read_bytes()
    report = contract_report(code_root=code, runtime_root=runtime)
    assert report["code_root"] == str(code)
    assert report["runtime_root"] == str(runtime)
    assert Path(report["database"]) == runtime / "SABLON_V2_MIMARI" / "ayarlar.db"
    assert (runtime / "ayarlar.json").read_bytes() == before

