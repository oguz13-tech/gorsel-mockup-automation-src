"""No-live-mutation release code staging acceptance."""
import hashlib
import subprocess
import tempfile
from pathlib import Path
import pytest
from scripts.p0_stage_release_code import stage_code

ROOT=Path(__file__).resolve().parents[1]


def test_stage_code_from_git_objects_in_disposable_directory():
    head=subprocess.check_output(["git","-C",str(ROOT),"rev-parse","HEAD"],text=True).strip()
    with tempfile.TemporaryDirectory(prefix="p0-stage-code-") as td:
        dest=Path(td)/"new-release"
        result=stage_code(ROOT,dest,head)
        assert not result["live_install_performed"]
        assert not result["runtime_modified"] if "runtime_modified" in result else True
        assert result["staged_code_files"]>=100
        assert (dest/"SABLON_V2_MIMARI"/"app.py").is_file()
        with pytest.raises(FileExistsError):
            stage_code(ROOT,dest,head)


def test_stage_rejects_wrong_commit():
    with tempfile.TemporaryDirectory() as td:
        with pytest.raises(RuntimeError,match="UNEXPECTED_RELEASE_HEAD"):
            stage_code(ROOT,Path(td)/"new-release","0"*40)
