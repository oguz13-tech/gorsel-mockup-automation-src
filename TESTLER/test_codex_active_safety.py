from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_windows_launcher_has_no_implicit_master_activation():
    source = (ROOT / "MERKEZ" / "BASLAT.bat").read_text(encoding="utf-8")
    assert "install_petek_master_revisions.py" not in source
    assert "merkez.py" in source


def test_center_startup_does_not_create_petek_folders_implicitly():
    source = (ROOT / "MERKEZ" / "merkez.py").read_text(encoding="utf-8")
    assert "self.root.after(0,self._bootstrap_petek_async)" not in source
    assert "salt-okunur" in source


def test_master_activation_requires_explicit_human_token():
    import sys

    sys.path.insert(0, str(ROOT / "tools"))
    import install_petek_master_revisions as installer

    try:
        installer.install(ROOT)
    except RuntimeError as exc:
        assert str(exc) == "PETEK_MASTER_ACTIVATION_REQUIRES_EXPLICIT_HUMAN_APPROVAL"
    else:
        raise AssertionError("master activation unexpectedly ran without approval")


def test_master_installer_does_not_embed_one_drive_path():
    source = (ROOT / "tools" / "install_petek_master_revisions.py").read_text(
        encoding="utf-8"
    )
    assert "OneDrive" not in source
    assert "GORSEL_RUNTIME_ROOT" in source


def test_moved_workspace_wins_over_historical_onedrive(monkeypatch, tmp_path):
    from pathlib import Path
    import sys

    sys.path.insert(0, str(ROOT / "MERKEZ"))
    from legacy_manager import preferred_runtime

    root = tmp_path / "GorselUretimMerkezi"
    (root / "SABLON_V2_MIMARI").mkdir(parents=True)
    (root / "2_SABLON_HAVUZU").mkdir()
    (root / "2_SABLON_HAVUZU_ORIJINAL_YEDEK").mkdir()
    (root / "SABLON_V2_MIMARI" / "ayarlar.db").write_bytes(b"existing")
    monkeypatch.setenv("GORSEL_RUNTIME_ROOT", str(root))
    monkeypatch.setenv(
        "MOCKUP_RUNTIME_WORKSPACE",
        str(Path("C:/old/OneDrive/GorselUretme-ve-Mockup Otomasyonu")),
    )
    assert preferred_runtime() == root.resolve()
