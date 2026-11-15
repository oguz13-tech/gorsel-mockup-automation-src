"""V5 Graphite shell contract: no silent no-op controls."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / 'MERKEZ' / 'graphite_workbench_v500.py'


def test_graphite_workbench_has_real_workflow_bridge_and_tabs():
    source = MODULE.read_text(encoding='utf-8')
    for token in (
        'app.open_current_workflow',
        'app.open_legacy_review',
        'app.open_unified_v4',
        'app.open_ham_design_folder',
        'app.show_health',
        'Gerçek İş Akışını Aç',
        'workbench_preview_mode',
        'workbench_edge_softness',
    ):
        assert token in source


def test_graphite_workbench_contains_no_silent_noop_callback():
    tree = ast.parse(MODULE.read_text(encoding='utf-8'))
    for node in ast.walk(tree):
        if isinstance(node, ast.Lambda):
            # A lambda used for a UI callback must call/set something. The one
            # harmless compatibility assignment is intentionally excluded by
            # asserting there are no `lambda: None` forms.
            assert not (len(node.body.__class__.__name__) == len('Constant') and
                        isinstance(node.body, ast.Constant) and node.body.value is None)


def test_controls_explain_safe_external_editor_boundary():
    source = MODULE.read_text(encoding='utf-8')
    assert 'gerçek motor için Gerçek İş Akışını Açın' in source


def test_graphite_controls_are_keyboard_reachable_and_explain_shell_shortcuts():
    source = MODULE.read_text(encoding='utf-8')
    assert "kwargs.setdefault('takefocus', True)" in source
    assert "root.bind_all('<KeyPress>'" in source


def test_graphite_shell_exposes_central_operation_monitor():
    source = MODULE.read_text(encoding='utf-8')
    assert 'app.operation_text' in source
    assert 'refresh_operation_monitor' in source
    assert 'live_progress_percent' in source
    assert 'cloud_progress_percent' in source


def test_graphite_home_is_an_operational_start_surface():
    source = MODULE.read_text(encoding='utf-8')
    assert 'Günlük Operasyon Merkezi' in source
    assert 'Önerilen çalışma sırası' in source
    assert '_set_home_layout' in source


def test_graphite_workbench_declares_one_shared_route_registry():
    source = MODULE.read_text(encoding='utf-8')
    assert 'WORKBENCH_TABS = (' in source
    assert 'app.workbench_routes' in source
