from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "SABLON_V2_MIMARI" / "templates" / "index.html"
PANEL_JS = ROOT / "SABLON_V2_MIMARI" / "static" / "js" / "graphite_panel_toggles_v1.js"
SIDEBAR_JS = ROOT / "SABLON_V2_MIMARI" / "static" / "js" / "sidebar_toggle_v1.js"
THEME = ROOT / "SABLON_V2_MIMARI" / "static" / "css" / "mor_premium_vnext.css"
HOST = ROOT / "MERKEZ" / "webview_host.py"


def test_review_page_has_single_real_editor_and_independent_panel_controls():
    source = HTML.read_text(encoding="utf-8")
    assert source.count('id="main"') == 1
    assert source.count('id="rightPanelToggle"') == 1
    assert source.count('id="graphiteFlowPanel"') == 1
    assert 'id="sidebarToggle"' in source
    assert 'id="graphite_panel_toggles_v1.js"' not in source  # script is src, not an editor clone
    assert "/static/js/graphite_panel_toggles_v1.js" in source
    # The actual editor callbacks remain the existing functions/DOM.
    for token in ("saveAll()", "autoDetectCorners()", "approveTemplate()", "petekV477Editor"):
        assert token in source


def test_panel_state_is_independent_and_persistent():
    source = PANEL_JS.read_text(encoding="utf-8")
    assert "graphite.review.tools.collapsed" in source
    assert "graphite.review.flow.collapsed" in source
    assert "graphite-tools-collapsed" in source
    assert "graphite-flow-collapsed" in source
    assert "graphiteRefreshFlow" in source
    assert "rightPanelToggle" in source
    assert "graphiteFlowOpen" in source


def test_template_list_toggle_is_not_the_graphite_outer_navigation():
    sidebar = SIDEBAR_JS.read_text(encoding="utf-8")
    assert "graphite.template-list.collapsed" in sidebar
    assert "Şablon listesini daralt" in sidebar
    assert "graphite.sidebar.collapsed" in sidebar  # backwards-compatible read


def test_collapsed_panels_release_layout_footprint_and_keep_edge_buttons():
    css = THEME.read_text(encoding="utf-8")
    for token in (
        "body.graphite-tools-collapsed #right-toolbar",
        "body.graphite-tools-collapsed .petek-v477-tools",
        "body.graphite-flow-collapsed .graphite-flow-panel",
        "body.graphite-flow-collapsed .graphite-flow-open",
        "position:fixed; right:7px; top:76px",
    ):
        assert token in css


def test_webview_host_removes_non_client_window_decorations():
    host = HOST.read_text(encoding="utf-8")
    assert "frameless=True" in host
    assert "WS_CAPTION" in host
    assert "WS_MINIMIZEBOX" in host
    assert "WS_EX_APPWINDOW" in host
