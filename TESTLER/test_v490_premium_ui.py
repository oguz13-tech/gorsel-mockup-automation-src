"""V4.9 presentation integration gates, isolated from user runtime."""
from pathlib import Path
import ast
R=Path(__file__).resolve().parents[1]

def test_new_premium_dashboard_with_legacy_fallback():
    src=(R/'MERKEZ/merkez.py').read_text('utf-8')
    premium=(R/'MERKEZ/premium_dashboard_v489.py').read_text('utf-8')
    assert 'GORSEL_UI_LEGACY' in src
    assert 'build_legacy' in src
    for target in ('self.review_button', 'self.tools_button','self.runtime_text',
                   'self.ham_home_status','self.status','self.log','self.advanced_toggle',
                   'self.advanced_panel'):
        assert target.replace('self.','app.') in premium
    assert 'Şablonları İncele ve Onayla' in premium
    assert 'Magenta LAB' in premium and 'open_magenta_replace_v486' in premium


def test_web_theme_and_all_original_controls_remain():
    index=(R/'SABLON_V2_MIMARI/templates/index.html').read_text('utf-8')
    tools=(R/'SABLON_V2_MIMARI/templates/tools.html').read_text('utf-8')
    css=(R/'SABLON_V2_MIMARI/static/css/premium_v489.css').read_text('utf-8')
    assert 'premium_v489.css' in index and 'premium_v489.css' in tools
    assert 'premium_petek_v489.css' in index
    assert "launchTool('orientation_sort'" in tools
    for needed in ("launchTool('rename'", "launchTool('convert'", "launchTool('4k'", "launchTool('portrait_3x4'", "launchTool('links'"):
        assert needed in tools
    assert 'canvas{position:absolute' not in css.lower()


def test_tool_handler_is_allowed_and_desktop_launcher_exists():
    app=(R/'SABLON_V2_MIMARI/app.py').read_text('utf-8')
    runner=(R/'SABLON_V2_MIMARI/tools_runner.py').read_text('utf-8')
    assert '"orientation_sort",' in app
    assert '"orientation_sort": interactive_orientation_sort' in runner
    assert (R/'BAGIMSIZ_ARACLAR/10_YATAY_DİKEY_GORSEL_SECICI.bat').is_file()
    assert (R/'ESKI_GORUNUME_DON_WINDOWS.bat').is_file()


def test_operational_modules_not_touched_by_presentation_theme():
    theme=(R/'MERKEZ/dark_theme_v42.py').read_text('utf-8')
    assert 'darken_window' in theme and 'apply_dark_theme' in theme
    assert 'Güvenli' in (R/'MERKEZ/premium_dashboard_v489.py').read_text('utf-8')
