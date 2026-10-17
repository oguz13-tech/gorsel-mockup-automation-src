"""Static non-destructive contracts for high-risk legacy entrypoints.

These checks examine source only and NEVER execute historical recovery scripts.
"""
import ast
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
ENGINE = Path("99_SISTEM_MOTORLARI_VE_KODLAR/SISTEM_MOTORU")
DANGEROUS = [
    ENGINE / "final_fix.py", ENGINE / "ultimate_rescue.py",
    ENGINE / "rescue_edits.py", ENGINE / "rescue_edits_all.py",
    ENGINE / "rollback.py", ENGINE / "fix_json_keys.py",
]


@pytest.mark.parametrize("path", DANGEROUS)
def test_legacy_recovery_has_safe_explicit_entrypoint(path):
    """Importing a rescue helper cannot overwrite any user files."""
    source = (ROOT / path).read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert any(
        isinstance(node, ast.If) and isinstance(node.test, ast.Compare)
        and isinstance(node.test.left, ast.Name) and node.test.left.id == "__name__"
        for node in tree.body
    ), f"{path} executes at import time"
    # Historical backup fixed-name manipulation must never delete originals.
    assert ".unlink(" not in source
    assert "shutil.rmtree" not in source
    assert "shutil.copy2(BACKUP_JSON, TARGET_JSON)" not in source
    assert "with open(DEST, \"w\"" not in source


def test_old_preview_batch_never_launches_cloud_without_explicit_approval():
    source = (ROOT / ENGINE / "generate_test_13er_tane.py").read_text(encoding="utf-8")
    assert "__name__" in source
    assert "--allow-cloud-upload" in source
    assert "MOCKUP_RUNTIME_WORKSPACE" in source
    assert 'Path(r"C:\\Users\\oguzc' not in source


def test_launcher_does_not_mutate_python_environment_on_start():
    source = (ROOT / "SABLON_V2_MIMARI/v2_baslat.bat").read_text(encoding="utf-8")
    assert "pip install" not in source.lower()
    assert "MOCKUP_RUNTIME_WORKSPACE" in source


def test_git_tracked_legacy_files_keep_original_basenames():
    for file in DANGEROUS:
        assert (ROOT / file).exists(), str(file)
