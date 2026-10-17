# -*- coding: utf-8 -*-
"""Full-system audit gates: retained tools and read-only legacy recovery."""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MOTOR = ROOT / "99_SISTEM_MOTORLARI_VE_KODLAR" / "SISTEM_MOTORU"
RECOVERY = (
    "final_fix.py", "ultimate_rescue.py", "rollback.py",
    "rescue_edits.py", "rescue_edits_all.py", "fix_json_keys.py",
)
TOOLS = {
    "01_GORSEL_ISIMLENDIRICI.bat": "rename",
    "02_FORMAT_CEVIRICI_PNG_JPG.bat": "convert",
    "03_OTOMATIK_FILIGRAN.bat": "watermark",
    "04_AI_4K_KALITE_ARTIRICI.bat": "4k",
    "05_GORSEL_LINK_EXCEL.bat": "links",
    "06_SEO_URUN_ADI_URETICI.bat": "seo_titles",
    "07_SEO_ACIKLAMA_URETICI.bat": "seo_descriptions",
    "08_RECURSIVE_PNG_DONUSTURUCU.bat": "png_recursive",
}

def _hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

@pytest.mark.parametrize("name",RECOVERY)
def test_historical_rescue_entrypoints_remain_available_but_read_only(name):
    with tempfile.TemporaryDirectory(prefix="p0-legacy-recovery-") as td:
        runtime = Path(td)
        root = runtime / "99_SISTEM_MOTORLARI_VE_KODLAR" / "SISTEM_MOTORU"
        root.mkdir(parents=True)
        settings = root / "ayarlar.json"
        data = {"kategoriler": {"01_Wifi_Kutusu": {
            "sablonlar": {"Wifi_Kutusu_005.png": {"koseler": [[1,1],[2,1],[2,2],[1,2]]}}
        }}}
        settings.write_text(json.dumps(data), encoding="utf-8")
        existing = _hash(settings)
        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        p = subprocess.run(
            [sys.executable, "-B", str(MOTOR / name),
             "--runtime-root", str(runtime)],
            cwd=str(ROOT),env=env,text=True,capture_output=True,
            encoding="utf-8", errors="replace",timeout=15,
        )
        assert p.returncode == 2, (name,p.stdout,p.stderr)
        report = json.loads(p.stdout)
        assert report["mutated"] is False
        assert report["restore_applied"] is False
        assert _hash(settings) == existing

@pytest.mark.parametrize("filename,mode",TOOLS.items())
def test_all_eight_independent_professional_tools_remain_startable(filename,mode):
    path=ROOT/"BAGIMSIZ_ARACLAR"/filename
    assert path.is_file()
    script=path.read_text(encoding="utf-8-sig")
    assert "tools_runner.py" in script
    assert " "+mode in script
    assert "cd /d" in script.lower()

def test_old_control_center_cannot_rename_live_pool():
    import importlib.util
    path=ROOT/"V2_KONTROL_MERKEZI"/"app.py"
    spec=importlib.util.spec_from_file_location("old_v2_test_guard",path)
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    with tempfile.TemporaryDirectory(prefix="p0-v2-guard-") as td:
        root=Path(td)
        pool=root/"2_SABLON_HAVUZU"/"01_Wifi_Kutusu"
        pool.mkdir(parents=True)
        src=pool/"Wifi_Kutusu_005.jpg"
        src.write_bytes(b"preserve")
        mod.BASE_DIR=str(root)
        with pytest.raises((ValueError,RuntimeError)):
            mod.safe_two_phase_rename([str(src)],"Wifi_Kutusu_")
        assert src.read_bytes()==b"preserve"
