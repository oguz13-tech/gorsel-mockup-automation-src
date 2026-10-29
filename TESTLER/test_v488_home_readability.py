"""V4.8.8 modern single entry layout and readable PETEK CSS guards.

GUI layout is statically inspected on CI (headless Ubuntu cannot open Tk).
Real Windows screenshot and readability acceptance remain user-local.
"""
from pathlib import Path
import ast
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'MERKEZ'))
import merkez


def test_center_has_two_clear_primary_workflows_and_no_duplicate_petek_on_home():
    tree=ast.parse((ROOT/'MERKEZ/merkez.py').read_text('utf-8'))
    center=next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name=='Center')
    build=next(x for x in center.body if isinstance(x,ast.FunctionDef) and x.name=='build')
    source=ast.get_source_segment((ROOT/'MERKEZ/merkez.py').read_text('utf-8'),build)
    assert "Şablonları İncele ve Onayla" in source
    assert "Seri Mockup Üretimi" in source
    assert "self.open_legacy_review" in source
    assert "self.open_unified_v4" in source
    assert "self.review_button" in source and "self.tools_button" in source
    assert "advanced=[" in source
    assert "self.open_review" in source and "self.open_petek" in source
    assert "self.prepare_petek_folders" in source
    assert "self.open_unified_audit" in source
    assert "self.g3_backup" in source
    assert "HAM Tasarım Klasörünü Aç" in source
    assert "self.show_ham_design_audit" in source
    assert "'Segoe UI',19" in source
    assert "'Segoe UI',12,'bold'" in source
    assert "self._wheel_canvas" in source


def test_petek_minimum_readable_fonts_and_full_original_filename_tooltip():
    css=(ROOT/'SABLON_V2_MIMARI/static/css/petek_editor_v477.css').read_text('utf-8')
    js=(ROOT/'SABLON_V2_MIMARI/static/js/petek_editor_v477.js').read_text('utf-8')
    html=(ROOT/'SABLON_V2_MIMARI/templates/index.html').read_text('utf-8')
    assert "V4.8.8: accessible 14px minimum" in css
    for target in ('.petek-v477-tools .petek-v477-note',
                   '.petek-v484-bulk-row button',
                   '#petekV477List .petek-v477-list-item',
                   '#petekV484BulkDetect'):
        assert target in css
    assert "font-size:14px" in css
    assert "button.title=item.name+' · '+item.uid+' · '+item.status" in js
    assert "button.textContent=shortName+' — '+readableState" in js
    assert "'/api/petek/thumbnail/'" in js
    assert 'v=488-legible' in html


def test_main_working_root_never_auto_migrates_and_versions_are_in_sync():
    src=(ROOT/'MERKEZ/merkez.py').read_text('utf-8')
    version=(ROOT/'MERKEZ/version_v47.py').read_text('utf-8')
    gui=(ROOT/'MERKEZ/URETIM_V4/gui_v4.py').read_text('utf-8')
    assert 'VERSION = "V4.8.8"' in version
    assert 'V4.8.8 —' in gui
    assert "self.runtime=preferred_runtime()" in src
    assert 'store_runtime_choice(Path(chosen))' in src
    assert 'self.root.after(150,self.start_auto_ham_designs)' in src
    assert 'self.ham_design_watcher.vault.audit()' in src
    assert 'self.root.after(400,self.start_auto_inbox)' in src
    # Old/source folders must be untouched without explicit operator action.
    assert "def build(self):" in src
    assert "shutil.move(" not in src
    assert "shutil.rmtree(" not in src
