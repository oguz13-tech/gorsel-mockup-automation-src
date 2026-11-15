from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_review_surface_does_not_fall_back_to_system_browser():
    center = (ROOT / "MERKEZ" / "merkez.py").read_text(encoding="utf-8")
    host = (ROOT / "MERKEZ" / "webview_host.py").read_text(encoding="utf-8")
    requirements = (ROOT / "MERKEZ" / "requirements.txt").read_text(encoding="utf-8")
    assert "webbrowser" not in center
    assert "_open_review_surface" in center
    assert "workbench_review_host" in center
    assert "--parent-hwnd" in center
    assert "review_host" in (ROOT / "MERKEZ" / "graphite_workbench_v500.py").read_text(encoding="utf-8")
    assert 'gui="edgechromium"' in host
    assert "pywebview>=5,<6" in requirements


def test_review_surface_reopens_when_graphite_route_changes():
    center = (ROOT / "MERKEZ" / "merkez.py").read_text(encoding="utf-8")
    assert "self._webview_route" in center
    assert "if self._webview_route == route" in center
    assert "rota değişimi için yeniden açılıyor" in center

