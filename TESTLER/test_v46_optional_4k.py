from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'MERKEZ'))
from URETIM_V4.upscale4k_v44 import preflight,UpscaleError

def test_disabled_4k_needs_no_executable(tmp_path):
    assert preflight(enabled=False,exe=tmp_path/'missing.exe') is None

def test_empty_models_never_report_ready(tmp_path):
    exe=tmp_path/'engine.exe';exe.write_bytes(b'synthetic executable')
    model=tmp_path/'models';model.mkdir()
    (model/'realesrgan-x4plus.bin').write_bytes(b'')
    (model/'realesrgan-x4plus.param').write_bytes(b'fake')
    with pytest.raises(UpscaleError):preflight(enabled=True,exe=exe)
