"""Regression coverage for the V6 review catalog normalization.

The review page reads the same protected catalog as the legacy editor.  This
test keeps the storage field (``koseler``) and the editor field (``corners``)
in sync so a valid API response cannot regress to ``undefined.map``.
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "SABLON_V2_MIMARI" / "static" / "js" / "v6_review.js"


def test_v6_catalog_normalizes_protected_corners_for_selection():
    source = SOURCE.read_text(encoding="utf-8")
    assert "const raw = Array.isArray(tmpl.koseler)" in source
    assert "(Array.isArray(tmpl.corners) ? tmpl.corners : [])" in source
    assert "corners: points" in source
    assert "const sourceCorners = Array.isArray(t.corners) ? t.corners : t.koseler;" in source


def test_v6_catalog_has_actionable_empty_and_error_states():
    source = SOURCE.read_text(encoding="utf-8")
    assert "Kullanılabilir dört köşeli şablon bulunamadı." in source
    assert "Tekrar Dene" in source


def test_v6_navigation_never_routes_review_to_unrelated_tools():
    source = SOURCE.read_text(encoding="utf-8")
    assert "if (dest === 'review')" in source
    assert "window.location.href = '/';" in source
    assert "Graphite masaüstü kabuğundan açılır." in source


def test_v6_lists_petek_category_from_its_own_registry():
    """PETEK must appear as a seventh category without fabricating catalog rows.

    The ayarlar catalog deliberately has no 06_Petek_Kapama rows; the board
    merges the read-only /api/petek/templates list instead.
    """
    source = SOURCE.read_text(encoding="utf-8")
    assert "const PETEK_CATEGORY = '06_Petek_Kapama';" in source
    assert "'06_Petek_Kapama': '06 · Dekoratif Ahşap Petek Dolabı'," in source
    assert "fetch('/api/petek/templates'" in source
    assert "function petekItems(rawItems)" in source
    assert "state.petekItems = petekItems(petekData.items);" in source
    assert "state.items.filter(t => !t.petek).concat(state.petekItems)" in source
    assert "fetch('/api/petek/detail/'" in source
    assert "'/api/petek/photo/'" in source


def test_v6_never_writes_petek_records_from_the_review_board():
    """PETEK approvals/masks stay in their own editor; V6 stays read-only."""
    source = SOURCE.read_text(encoding="utf-8")
    assert "state.current.petek) {" in source
    assert "PETEK onayı ayrı düzenleyicide yapılır" in source
    assert "'🔥 PETEK köşeleri bu panoda düzenlenmez'" in source
    assert "syncActionButtons();" in source
