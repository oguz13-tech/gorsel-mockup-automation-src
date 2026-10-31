"""V4.10.1 source-level regression for live-bug fixes and preserved user data."""
from pathlib import Path
import hashlib
import importlib.util

ROOT=Path(__file__).resolve().parents[1]
WEB=ROOT/'SABLON_V2_MIMARI'
BASE=Path('/mnt/data/V4100_WORK/GORSEL_V4100_WINDOWS/GORSEL_V46_CANDIDATE')


def test_no_obsolete_eight_step_human_review():
    js=(WEB/'static/js/petek_editor_v477.js').read_text('utf8')
    html=(WEB/'templates/index.html').read_text('utf8')
    assert 'petekV498ReviewDialog' not in html
    assert 'reviewLoaded' not in js and 'showNextReviewPage' not in js
    assert 'petekV498BulkApprove' in html
    fn=js.split('async function beginBulkPetekApproval(){')[1].split('function petekState(')[0]
    assert fn.count('if(!confirm(')==1
    assert 'bulk-approve-confirmed' in fn
    assert 'I_APPROVE_ALL_VALID_PETEK_DRAFTS_IN_THIS_SELECTION' in fn
    assert 'x.checked' not in fn


def test_seven_category_shared_status_filter_and_no_deleted_list():
    js=(WEB/'static/js/main.js').read_text('utf8')
    petek=(WEB/'static/js/petek_editor_v477.js').read_text('utf8')
    css=(WEB/'static/css/v4101_unified.css').read_text('utf8')
    html=(WEB/'templates/index.html').read_text('utf8')
    for state in ('NEW','APPROVED','DRAFT','ERROR'):
        assert f'data-v499-state="{state}"' in html
        assert f'v499-status-{state.lower()}' in css
    assert 'V499StatusFilters.allowed(petekState(x))' in petek
    assert 'V499StatusFilters.applyRow(item)' in js
    assert 'grid-template-columns:20px minmax(0,1fr)' in css
    assert 'input[type=checkbox].petek-v484-check' in css
    assert 'petek-v484-name' in css
    assert 'petek-v484-thumb' in css


def test_single_category_keyboard_and_revisions_kept():
    main=(WEB/'static/js/main.js').read_text('utf8')
    petek=(WEB/'static/js/petek_editor_v477.js').read_text('utf8')
    assert 'PetekV477.isActive()' in main
    assert 'stopImmediatePropagation()' in petek
    assert 'erasewood' in petek
    assert 'async function activateApprovedRevision()' in petek
    assert 'restore-approved-revision' in petek


def test_dashboard_drag_safely_only_updates_visual_json():
    src=(ROOT/'MERKEZ/premium_dashboard_v489.py').read_text('utf8')
    pref=(ROOT/'MERKEZ/ui_layout_v498.py').read_text('utf8')
    assert "drag_mode=tk.BooleanVar" in src
    assert 'winfo_containing' in src
    assert 'save_visual_layout(data)' in src
    assert 'callback()' in src and 'if drag_mode is not None and drag_mode.get():return' in src
    assert 'contrast_ratio' in pref
    assert "'panel','button','title','border'" in pref
    assert 'dest.is_symlink()' in pref
    assert 'os.replace(tmp,dest)' in pref


def test_error_popup_has_action_and_critical_batch_has_no_modal_storm():
    js=(WEB/'static/js/petek_editor_v477.js').read_text('utf8')
    html=(WEB/'templates/index.html').read_text('utf8')
    tk=(ROOT/'MERKEZ/error_advisor_v498.py').read_text('utf8')
    assert 'petekV4101ErrorDialog' in html
    assert 'Ne yapmalıyım?' in html
    assert 'if(!bad||s.bulkActive||!recommendation)return' in js
    assert 'install_global_error_advisor()' in (ROOT/'MERKEZ/merkez.py').read_text('utf8')
    assert 'messagebox.showerror=showerror' in tk


def test_protected_visual_renderers_not_modified_since_v4100():
    if not BASE.exists():
        import pytest
        pytest.skip('Reference archive not in this checkout')
    for path in ('MERKEZ/PETEK_V3/final_cleanup_v495.py',
                 'MERKEZ/PETEK_V3/petek_finish_v492.py',
                 'MERKEZ/PETEK_V3/render.py'):
        a=ROOT/path;b=BASE/path
        if b.exists():
            assert hashlib.sha256(a.read_bytes()).digest()==hashlib.sha256(b.read_bytes()).digest(),path


def test_contrast_rejects_illegible_user_palette():
    import sys
    sys.path.insert(0,str(ROOT/'MERKEZ'))
    from ui_layout_v498 import normalize
    raw={'schema':1,'dashboard':{'colors':{'panel':'#fefefe','button':'#ffffff','title':'#ffffff','background':'#fffefe','border':'#778899'}}}
    fixed=normalize(raw)['dashboard']['colors']
    assert 'panel' not in fixed and 'button' not in fixed and 'background' not in fixed
    assert fixed['title']=='#ffffff' and fixed['border']=='#778899'
