"""Üretim Kayıtları operasyon merkezi — izole (tmp) testler.

Canlı AppData veritabanına hiçbir yazma yapılmaz; tüm SQLite/checkpoint
işlemleri geçici klasörde kurulur.
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'MERKEZ'))

from URETIM_V4 import uretim_kayitlari_v1 as records  # noqa: E402
from URETIM_V4 import resume_checkpoint_v47 as ckpt  # noqa: E402


def _make_ledger(root: Path, rows: list[tuple]) -> Path:
    """rows: (key, sku, category, status, output, output_sha, message, updated)"""
    db = root / 'v4_ortak_uretim.sqlite3'
    with sqlite3.connect(db) as con:
        con.execute("""CREATE TABLE artifact (
            key TEXT PRIMARY KEY, sku TEXT NOT NULL, category TEXT NOT NULL,
            art_sha TEXT NOT NULL, template_sha TEXT NOT NULL, mask_sha TEXT NOT NULL,
            art_name TEXT NOT NULL, uid TEXT NOT NULL, output TEXT NOT NULL,
            output_sha TEXT NOT NULL DEFAULT '', status TEXT NOT NULL,
            message TEXT NOT NULL DEFAULT '', updated TEXT DEFAULT CURRENT_TIMESTAMP,
            artifact_kind TEXT NOT NULL DEFAULT 'clean',
            source_key TEXT NOT NULL DEFAULT '', overlay_cm TEXT NOT NULL DEFAULT '',
            overlay_manifest TEXT NOT NULL DEFAULT '')""")
        for key, sku, category, status, output, sha, message, updated in rows:
            con.execute(
                "INSERT INTO artifact(key, sku, category, art_sha, template_sha, mask_sha,"
                " art_name, uid, output, output_sha, status, message, updated)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (key, sku, category, 'a' * 64, 't' * 64, 'm' * 64,
                 'art-' + sku, 'uid-' + sku, str(output), sha or '', status, message, updated))
        con.execute("""CREATE TABLE production_session (
            operation_id TEXT PRIMARY KEY, started_at TEXT NOT NULL, finished_at TEXT,
            mode TEXT NOT NULL, design_folder TEXT NOT NULL, stores TEXT NOT NULL,
            design_count INTEGER NOT NULL DEFAULT 0, planned INTEGER NOT NULL DEFAULT 0,
            successful INTEGER NOT NULL DEFAULT 0, failed INTEGER NOT NULL DEFAULT 0,
            skipped INTEGER NOT NULL DEFAULT 0, elapsed_seconds REAL NOT NULL DEFAULT 0,
            seconds_per_image REAL, status TEXT NOT NULL DEFAULT 'RUNNING',
            per_store TEXT NOT NULL DEFAULT '{}', report_path TEXT NOT NULL DEFAULT '',
            external INTEGER NOT NULL DEFAULT 0)""")
        con.execute("""INSERT INTO production_session VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    ('OP-TEST-1', '2026-11-13 09:00:00', '2026-11-13 09:30:00', 'standard',
                     'C:/tasarimlar', json.dumps(['adeno', 'wudie']), 2, 20, 18, 2, 0,
                     1500.0, 83.3, 'LOCAL_READY',
                     json.dumps({'outputs': {'adeno': 9, 'wudie': 9}}), 'C:/rapor.json', 0))
        con.execute("""INSERT INTO production_session VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    ('OP-TEST-2', '2026-11-13 10:00:00', None, 'four_mockup',
                     'C:/tasarimlar', json.dumps(['adeno']), 1, 4, 0, 0, 0,
                     0.0, None, 'RUNNING', '{}', '', 0))
    return db


def _row(key, status, output, msg='', updated='2026-11-13 09:00:00', sku='SKU-1'):
    return (key, sku, '06_Petek_Kapama', status, output, 'f' * 64, msg, updated)


@pytest.fixture
def ledger_root():
    # DSH kum havuzu pytest'in tmp_path dizinini engelleyebildiği için
    # tempfile ile yalıtılmış geçici kök açılır (canlı veriye dokunulmaz).
    root = Path(tempfile.mkdtemp(prefix='gum_records_test_'))
    rows = [
        _row('k1', 'RENDERED', root / 'uretilen_gorseller' / 'a.png', sku='SKU-R1'),
        _row('k2', 'RENDERED', root / 'uretilen_gorseller' / 'b.png', sku='SKU-R2',
             updated='2026-11-13 09:05:00'),
        _row('k3', 'REVIEW_REQUIRED', root / 'uretilen_gorseller' / 'c.png',
             msg='PETEK_PINK_CLEANUP_INCOMPLETE_REVIEW', sku='SKU-F1'),
        _row('k4', 'REVIEW_REQUIRED', root / 'uretilen_gorseller' / 'd.png',
             msg='PETEK_PINK_CLEANUP_INCOMPLETE_REVIEW; detay: x', sku='SKU-F2',
             updated='2026-11-13 09:10:00'),
        _row('k5', 'REVIEW_REQUIRED', root / 'uretilen_gorseller' / 'e.png',
             msg='Ayni isimli dosya var: ASLA UZERINE YAZILMAZ.', sku='SKU-F3',
             updated='2026-11-13 09:15:00'),
        _row('k6', 'PENDING', root / 'uretilen_gorseller' / 'f.png', sku='SKU-P1'),
    ]
    _make_ledger(root, rows)
    yield root
    shutil.rmtree(root, ignore_errors=True)


def test_status_counts_splits_success_failure(ledger_root):
    counts = records.status_counts(ledger_root)
    assert counts == {'RENDERED': 2, 'REVIEW_REQUIRED': 3, 'PENDING': 1}
    assert records.interrupted_pending(ledger_root) == 1


def test_recent_artifacts_success_and_failure_separate(ledger_root):
    ok = records.recent_artifacts(ledger_root, 'RENDERED')
    bad = records.recent_artifacts(ledger_root, 'REVIEW_REQUIRED')
    assert {r['sku'] for r in ok} == {'SKU-R1', 'SKU-R2'}
    assert {r['sku'] for r in bad} == {'SKU-F1', 'SKU-F2', 'SKU-F3'}
    assert all('message' in r for r in bad)


def test_error_reasons_grouped_with_counts(ledger_root):
    reasons = records.error_reasons(ledger_root)
    by_reason = {g['reason']: g['count'] for g in reasons}
    assert by_reason['PETEK_PINK_CLEANUP_INCOMPLETE_REVIEW'] == 2
    assert by_reason['Ayni isimli dosya var'] == 1


def test_sessions_parse_and_unfinished_flag(ledger_root):
    sessions = records.recent_sessions(ledger_root)
    assert len(sessions) == 2
    latest = sessions[0]
    assert latest['operation_id'] == 'OP-TEST-2'
    assert latest['stores'] == ['adeno']
    finished = records.session_label(records.recent_sessions(ledger_root)[1])
    assert finished['unfinished'] == '0'
    assert finished['stores'] == 'adeno: 9, wudie: 9'
    running = records.session_label(latest)
    assert running['unfinished'] == '1'
    assert 'yarıda' in running['status']


def test_classify_resume_states():
    none_state = records.classify_resume({'status': 'NONE'}, {'exists': False}, 0)
    assert none_state[0] == 'ok'
    stopped = records.classify_resume(
        {'status': 'STOPPED', 'progress': {'attempted': 20, 'rendered': 12}},
        {'exists': False}, 0)
    assert stopped[0] == 'resume' and '12' in stopped[1] and 'SHA' in stopped[1]
    running_alive = records.classify_resume(
        {'status': 'RUNNING'}, {'exists': True, 'pid_alive': True}, 0)
    assert running_alive[0] == 'info'
    running_dead = records.classify_resume(
        {'status': 'RUNNING'}, {'exists': False, 'pid_alive': False, 'stale_lock': True}, 0)
    assert running_dead[0] == 'warning'
    interrupted = records.classify_resume({'status': 'INTERRUPTED'}, {'exists': False}, 0)
    assert interrupted[0] == 'warning'
    pending = records.classify_resume({'status': 'NONE'}, {'exists': False}, 3)
    assert pending[0] == 'warning' and '3' in pending[1]
    garbage = records.classify_resume({'status': 'CHECKPOINT_INVALID', 'error': 'x'}, {'exists': False}, 0)
    assert garbage[0] == 'warning'


def test_checkpoint_summary_roundtrip_and_tamper(ledger_root):
    payload = {'schema': 1, 'operation_id': 'OP-TEST-CKPT', 'status': 'STOPPED',
               'state_root': str(ledger_root), 'runtime_root': None,
               'render_recipe': ['a', 'b', 'c'], 'config': {'group': 'LOCAL'},
               'inventory': {'designs': {}}, 'progress': {'attempted': 10, 'rendered': 7, 'reused': 0}}
    ckpt.write_checkpoint(ledger_root, payload)
    summary = records.checkpoint_summary(ledger_root)
    assert summary['status'] == 'STOPPED'
    assert summary['progress']['rendered'] == 7
    path = ledger_root / 'v47_last_batch_resume.json'
    envelope = json.loads(path.read_text(encoding='utf-8'))
    envelope['payload']['config']['group'] = 'DEĞİŞTİRİLDİ'
    path.write_text(json.dumps(envelope), encoding='utf-8')
    tampered = records.checkpoint_summary(ledger_root)
    assert tampered['status'] == 'CHECKPOINT_INVALID'


def test_summarize_combines_everything(ledger_root):
    snap = records.summarize(ledger_root)
    assert snap['rendered'] == 2
    assert snap['review_required'] == 3
    assert snap['pending'] == 1
    assert snap['level'] == 'warning'  # pending > 0 ve RUNNING oturumu
    assert len(snap['sessions']) == 2
    assert snap['unfinished_sessions'] == 1


def test_resume_delegation_prefers_embedded_host():
    calls = []

    class FakeInner:
        def winfo_exists(self):
            return True

    class FakeWindow:
        def __init__(self, window):
            self.window = window

        def resume_batch(self):
            calls.append('resume')

    class FakeApp:
        def __init__(self):
            self.workbench_production_host = object()
            self.batch_windows = [FakeWindow(self.workbench_production_host)]
            self.switched = []
            self.status = type('S', (), {'set': lambda self, t: None})()

        def switch_workbench_tab(self, mode):
            self.switched.append(mode)

    app = FakeApp()
    outcome = records.resume_via_embedded_window(app)
    assert outcome == 'delegated'
    assert calls == ['resume']
    assert app.switched == ['production']


def test_resume_delegation_without_window_opens_production_tab():
    class FakeApp:
        def __init__(self):
            self.workbench_production_host = None
            self.batch_windows = []
            self.switched = []
            self.status_log = []

            outer = self

            class _Status:
                def set(self, text):
                    outer.status_log.append(text)

            self.status = _Status()

        def switch_workbench_tab(self, mode):
            self.switched.append(mode)

    app = FakeApp()
    outcome = records.resume_via_embedded_window(app)
    assert outcome == 'opened_production_tab'
    assert app.switched == ['production']
    assert app.status_log  # kullanıcı yönlendirildi


def test_panel_builds_and_refreshes_headless(ledger_root):
    import tkinter as tk
    try:
        root_win = tk.Tk()
        root_win.withdraw()
    except tk.TclError:
        pytest.skip('Tk ekranı bu ortamda kullanılamıyor')
    try:
        class FakeApp:
            def __init__(self):
                self.workbench_production_host = None
                self.batch_windows = []

            def switch_workbench_tab(self, mode):
                pass

            class status:  # noqa: N801 - basit stub
                @staticmethod
                def set(_text):
                    pass

        parent = tk.Frame(root_win)
        parent.pack()
        panel = records.build_records_workspace(FakeApp(), parent, state_root=ledger_root)
        panel.pack()
        panel.refresh_records()  # canlıya dokunmadan tmp kayıtlarını yeniden okur
        root_win.update_idletasks()
    finally:
        root_win.destroy()
