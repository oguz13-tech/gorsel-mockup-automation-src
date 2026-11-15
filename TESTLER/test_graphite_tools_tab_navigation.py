"""V5 Graphite sekme geçişleri: Araçlar ekranı ve tüm ana ekranlar.

Gerçek servisi, WebView2'yi veya canlı veriyi başlatmaz; kabuk geçişleri
stub callback'lerle doğrulanır. Geçici ve boş runtime klasörü kullanılır.
"""
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'MERKEZ'))

import tkinter as tk  # noqa: E402

import graphite_workbench_v500  # noqa: E402


class _FakeApp:
    pass


def _stub_workspaces(monkeypatch):
    fake_upload = types.ModuleType('upload_center_v500')

    def _build_upload(app, host):
        tk.Label(host, text='UPLOAD_STUB').pack()

    fake_upload.build_upload_center = _build_upload
    monkeypatch.setitem(sys.modules, 'upload_center_v500', fake_upload)

    for mod_name, fn_name, label in (
        ('URETIM_V4.uretim_kayitlari_v1', 'build_records_workspace', 'RECORDS_STUB'),
        ('URETIM_V4.raporlar_tarama_v1', 'build_reports_workspace', 'REPORTS_STUB'),
    ):
        fake = types.ModuleType(mod_name)

        def _build(app, host, _label=label):
            tk.Label(host, text=_label).pack()

            class _Ws:
                def refresh_records(self):
                    return None

                def refresh_reports(self):
                    return None

            return _Ws()

        setattr(fake, fn_name, _build)
        monkeypatch.setitem(sys.modules, mod_name, fake)


def _make_app(root, tmp_path, counters):
    app = _FakeApp()
    app.root = root
    app.runtime = tmp_path

    def _count(name):
        def _cb(*_a, **_kw):
            counters[name] += 1

        return _cb

    for name in ('review', 'tools', 'unified', 'ham', 'health', 'consolidation',
                 'links', 'close', 'g3_audit', 'g3_backup', 'petek_folders', 'crash', 'v6', 'stop_editor'):
        setattr(app, {'review': 'open_legacy_review',
                      'tools': 'open_legacy_tools',
                      'unified': 'open_unified_v4',
                      'ham': 'open_ham_design_folder',
                      'health': 'show_health',
                      'consolidation': 'open_consolidation',
                      'links': 'open_links_v493',
                      'close': 'close',
                      'g3_audit': 'g3_audit',
                      'g3_backup': 'g3_backup',
                      'petek_folders': 'prepare_petek_folders',
                      'crash': 'open_crash_recovery',
                      'v6': 'open_legacy_v6',
                      'stop_editor': 'stop_legacy_editor'}[name], _count(name))
    app.toggle_advanced = lambda: None
    app._refresh_visual_cards = lambda *a, **kw: None
    return app


@pytest.fixture()
def workbench(monkeypatch, tmp_path):
    _stub_workspaces(monkeypatch)
    counters = {name: 0 for name in
                ('review', 'tools', 'unified', 'ham', 'health', 'consolidation',
                 'links', 'close', 'g3_audit', 'g3_backup', 'petek_folders', 'crash', 'v6', 'stop_editor')}
    root = tk.Tk()
    root.withdraw()
    app = _make_app(root, tmp_path, counters)
    try:
        graphite_workbench_v500.build_dashboard(app)
        root.update()  # after_idle -> switch_tab('review')
        yield app, counters
    finally:
        root.destroy()


ALL_MODES = ('home', 'review', 'uploads', 'petek', 'production', 'designs',
             'stores', 'reports', 'reporting', 'tools')


def test_all_screens_switch_in_both_directions(workbench):
    app, _counters = workbench
    for _round in (1, 2):
        for mode in ALL_MODES:
            app.switch_workbench_tab(mode)
            app.root.update()
            assert app.workbench_tab.get() == mode


def test_production_to_tools_single_step(workbench):
    app, counters = workbench
    app.switch_workbench_tab('production')
    app.root.update()
    assert app.workbench_production_host.winfo_manager() == 'grid'
    app.switch_workbench_tab('tools')
    app.root.update()
    assert app.workbench_tab.get() == 'tools'
    assert app.workbench_review_host.winfo_manager() == 'grid'
    assert app.workbench_production_host.winfo_manager() != 'grid'
    assert app._wheel_canvas.winfo_manager() != 'grid'
    assert counters['tools'] >= 1


def test_tools_is_not_review_page(workbench):
    app, counters = workbench
    app.switch_workbench_tab('tools')
    app.root.update()
    # Araçlar yüzeyi açılır; 4 köşe inceleme callback'i ayrıca tetiklenmez.
    assert counters['tools'] >= 1
    assert app.workbench_tab.get() == 'tools'
    assert 'Araçlar' in app.workbench_title.get()


def test_open_current_workflow_on_every_screen(workbench):
    app, _counters = workbench
    for mode in ALL_MODES:
        app.switch_workbench_tab(mode)
        app.open_current_workflow()


def test_tab_bar_and_nav_highlight_follow_mode(workbench):
    app, _counters = workbench
    app.switch_workbench_tab('tools')
    app.root.update()
    # Sidebar 'Araçlar' navigasyon düğmesi ve sekme çubuğunda 'review' aktif değil.
    assert app.workbench_tab.get() == 'tools'
    nav_active = app.workbench_nav_buttons.get('tools')
    tabbar_active = app.workbench_tab_bar_buttons.get('review')
    assert nav_active is not None
    assert tabbar_active is not None
    assert nav_active.cget('bg') == '#10332B'
    assert tabbar_active.cget('bg') != '#10332B'
