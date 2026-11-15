"""V4.1 private-media Git exclusions and user-facing guided steps."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def test_petek_guided_steps_keep_cutout_tool():
    src = (ROOT / "MERKEZ" / "PETEK_V3" / "gui.py").read_text(encoding="utf-8")
    for text in ["Baskısız dolabın ODA", "Ahşap Baskı Alanını TASLAK", "Üst/Alt Kavis", "DESEN / BASKI TASARIMLARI", "verify_cutout_overlay", "Adım 1:"]:
        assert text in src


def test_git_never_tracks_real_photo_samples():
    if not (ROOT / ".git").exists():
        return
    cmd = subprocess.run(["git", "ls-files", "ORNEK_PETEK_MOCKUPLARI"], cwd=ROOT, capture_output=True, text=True, check=True)
    assert not cmd.stdout.strip(), "Real user PETEK sample photographs must not be committed"


def test_safe_push_script_enforces_private_branch_and_confirmation():
    script = ROOT / "GITHUB_PUSH_VE_PR_OLUSTUR.bat"
    if not script.exists():
        # Distribution-only ZIP deliberately removes .git AND push shortcuts.
        assert not (ROOT / '.git').exists(), 'No publish script allowed in a git checkout'
        return
    src = script.read_text(encoding="utf-8")
    assert "feat/v4-1-windows-safe-guided" in src
    assert "scripts\\check_safe_git_push.py" in src
    assert 'choice /M' in src


def test_default_v4_registry_uses_original_petek_approval_store(tmp_path, monkeypatch):
    monkeypatch.setenv("PETEK_V3_LOCAL_STATE", str(tmp_path / "OLD_APPROVED_PETEK"))
    import sys
    sys.path.insert(0, str(ROOT / "MERKEZ"))
    from URETIM_V4.unified_batch import UnifiedV4Batch
    batch = UnifiedV4Batch(tmp_path / "UNIFIED_STATE")
    assert batch.petek_registry.root == (tmp_path / "OLD_APPROVED_PETEK").resolve()
    assert batch.petek_registry.root != (tmp_path / "UNIFIED_STATE" / "petek_state")


def test_git_history_push_guard_script_present():
    script = (ROOT / "scripts" / "check_safe_git_push.py").read_text("utf-8")
    assert '"rev-list", "--objects", "HEAD"' in script
    assert '".jpeg"' in script
    assert "Private user" not in script  # expected localized gate
