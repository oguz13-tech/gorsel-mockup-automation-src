"""The application entry point and the V6 review alias share one UI surface."""

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "SABLON_V2_MIMARI"
if str(WEB) not in sys.path:
    sys.path.insert(0, str(WEB))

from app import app  # noqa: E402


def test_root_and_v6_alias_render_the_same_canonical_review_surface():
    client = app.test_client()
    root = client.get("/")
    alias = client.get("/review/v6")

    assert root.status_code == 200
    assert alias.status_code == 200
    assert root.data == alias.data
    assert b"v6_review.js" in root.data
    assert b"graphite_embed_v1.css" in root.data
    assert b"rel=\"icon\"" in root.data


def test_legacy_review_is_explicitly_reversible_but_not_the_root():
    client = app.test_client()
    legacy = client.get("/legacy-review")
    root = client.get("/")

    assert legacy.status_code == 200
    assert b"bulkApproveButton" in legacy.data
    assert b"bulkApproveButton" not in root.data


def test_graphite_embedded_surface_hides_duplicate_v6_navigation():
    css = (WEB / "static" / "css" / "graphite_embed_v1.css").read_text(encoding="utf-8")
    assert "html.graphite-embedded #topbar" in css
    assert "display: none" in css


def test_tools_surface_uses_the_same_embedded_shell_contract():
    client = app.test_client()
    response = client.get('/tools?ui=graphite')
    assert response.status_code == 200
    assert b'graphite_embed_v1.css' in response.data


def test_petek_compatibility_surface_keeps_editor_controls_but_drops_duplicate_shell():
    client = app.test_client()
    response = client.get('/legacy-review?surface=petek&ui=graphite')
    assert response.status_code == 200
    assert b'graphite-petek-compat' in response.data
    assert b'petekV477Editor' in response.data
