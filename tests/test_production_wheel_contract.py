from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "MERKEZ" / "URETIM_V4" / "gui_v4.py"


def test_embedded_production_form_routes_wheel_from_descendants_to_canvas():
    source = MODULE.read_text(encoding="utf-8")
    assert "winfo_toplevel()" in source
    assert "inside_host" in source
    assert "bind('<MouseWheel>'" in source
    assert "'<Button-4>'" in source
    assert "'<Button-5>'" in source
    assert "self.main_canvas.yview_scroll" in source
    assert "return 'break'" in source


def test_production_wheel_bindings_are_removed_on_close():
    source = MODULE.read_text(encoding="utf-8")
    assert "_wheel_binding" in source
    assert "wheel_root.unbind(sequence, binding)" in source


def test_production_effect_choice_is_recipe_default_not_user_selectable():
    source = MODULE.read_text(encoding="utf-8")
    assert 'Kategoriye Uygun Efekt:' not in source
    assert 'self.lighting = tk.StringVar(value=LIGHT_LABELS[0])' in source
    assert "lighting = 'natural'" in source
    # Old local UI preferences cannot override the reviewed production recipe.
    assert "'design_folder', 'group', 'placement', 'lighting'" not in source


def test_scope_actions_are_visible_next_to_their_affected_selection():
    source = MODULE.read_text(encoding="utf-8")
    assert "self.select_all_button" in source
    assert "text='Tüm onaylıları seç'" in source
    assert "self.select_store_button" in source
    assert "text='Mağazaya atananları üretime seç'" in source
    # These commands are no longer hidden in the advanced-tools drawer.
    advanced = source[source.index("def open_advanced_tools"):source.index("def _choose_4k_model")]
    assert "('Tüm onaylıları seç'" not in advanced
    assert "('Mağazaya atananları üretime seç'" not in advanced


def test_store_mismatch_reaches_actionable_preflight_instead_of_disabling_start():
    source = MODULE.read_text(encoding="utf-8")
    summary = source[source.index("def _refresh_selection_summary"):source.index("def chosen_uids")]
    assert "ready = bool(selected and designs)" in summary
    assert "_store_selection_snapshot" not in summary
    assert "start() remains the authoritative safety gate" in summary
