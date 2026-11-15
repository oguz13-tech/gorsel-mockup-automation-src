"""Raporlar & Tarama — çift glob veri yolu dedupe regresyon koruması."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'MERKEZ'))

from URETIM_V4 import raporlar_tarama_v1 as m


def test_latest_error_reports_dedupes_uretim_inceleme_json(tmp_path):
    reports = tmp_path / 'raporlar'
    reports.mkdir()
    for name in ('URETIM_INCELEME_A.json', 'URETIM_INCELEME_B.json', 'GENEL_C.json'):
        (reports / name).write_text(json.dumps({'ok': True}), encoding='utf-8')
    found = m.latest_error_reports(tmp_path, limit=10)
    assert len(found) == len({p.resolve() for p in found}) == 3


def test_latest_error_reports_missing_dir_returns_empty(tmp_path):
    assert m.latest_error_reports(tmp_path) == []


def test_latest_error_reports_unreadable_file_tolerated(tmp_path):
    reports = tmp_path / 'raporlar'
    reports.mkdir()
    target = reports / 'URETIM_INCELEME_X.json'
    target.write_text('{}', encoding='utf-8')
    target.chmod(0)
    try:
        found = m.latest_error_reports(tmp_path)
        assert any(p.name == 'URETIM_INCELEME_X.json' for p in found)
    finally:
        target.chmod(0o600)
