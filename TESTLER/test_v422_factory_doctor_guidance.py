"""V4.2.2 read-only diagnosis regressions; never accesses user data."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "SABLON_V2_MIMARI"))
from core.doctor_guidance import doctor_guidance


def demo_report(tmp_path):
    return {
        "ready": True,
        "warnings": [
            {"code": "RUNTIME_VERSION_DRIFT", "component": "python", "message": "python 3.14"},
            {"code": "RUNTIME_VERSION_DRIFT", "component": "numpy", "message": "numpy 2.5.4"},
            {"code": "GPU_RUNTIME_DRIFT", "component": "torch", "message": "torch missing"},
            {"code": "GPU_RUNTIME_DRIFT", "component": "torch_cuda", "message": "cuda missing"},
            {"code": "SYNCED_RUNTIME_DB_RISK", "message": "synced"},
            {"code": "MASTER_ASPECT_BLEED_ADAPTATION", "message": "bleed", "examples": [
                {"master_id": "M000023", "category": "05_Ocak_Arkasi", "source_orientation": "H", "relative_error": .13},
            ]},
        ],
        "checks": {
            "runtime_root": str(tmp_path / "OneDrive" / "workspace"),
            "runtime_versions": {
                "lock_path": str(tmp_path / "source" / "runtime_lock.json"),
                "mismatches": [
                    {"component": "python", "expected": "3.11", "actual": "3.14"},
                    {"component": "numpy", "expected": "2.4.6", "actual": "2.5.4"},
                ],
                "gpu_changes": [
                    {"component": "torch", "baseline": "2.5.1+cu121", "actual": None},
                    {"component": "transformers", "baseline": "5.17.0", "actual": None},
                    {"component": "torch_cuda", "baseline": "12.1", "actual": None},
                ],
            },
        },
    }


def test_all_user_warnings_explained_without_suppression(tmp_path):
    report = demo_report(tmp_path)
    before = repr(report)
    result = doctor_guidance(report, executable=r"C:\Program Files\Python314\python.exe")
    assert result["ready"] and result["read_only"]
    assert repr(report) == before
    by_code = {item["code"]: item for item in result["recommendations"]}
    assert {"RUNTIME_VERSION_DRIFT", "GPU_RUNTIME_DRIFT", "SYNCED_RUNTIME_DB_RISK", "MASTER_ASPECT_BLEED_ADAPTATION"} <= by_code.keys()
    assert "2.5.4" not in by_code["RUNTIME_VERSION_DRIFT"]["action"]
    assert "sıfırlamayın" in by_code["GPU_RUNTIME_DRIFT"]["action"]
    assert "M000023" in by_code["MASTER_ASPECT_BLEED_ADAPTATION"]["evidence"]
    assert "taşımayın" in by_code["SYNCED_RUNTIME_DB_RISK"]["action"]
    assert result["interpreter"].endswith("python.exe")
    assert list(tmp_path.iterdir()) == []


def test_gpu_present_but_version_changed_is_distinguished(tmp_path):
    report = demo_report(tmp_path)
    report["checks"]["runtime_versions"]["gpu_changes"] = [
        {"component": "torch", "baseline": "2.5.1+cu121", "actual": "2.8.0"}
    ]
    rec = doctor_guidance(report)["recommendations"]
    codes = {item["code"] for item in rec}
    assert "GPU_RUNTIME_DRIFT_CHANGED" in codes
    assert not any(item["title"].startswith("GPU/AI bileşenleri bu Python ortamında") for item in rec)


def test_empty_report_gives_no_false_success_claim():
    result = doctor_guidance({"ready": False})
    assert not result["ready"]
    assert result["recommendations"] == []


def test_launcher_prefers_python311_without_touching_existing_venv():
    source = (ROOT / "WINDOWS_HIZLI_BASLAT.bat").read_text(encoding="utf-8")
    assert 'if not exist "%PYEXE%" (' in source
    assert 'py -3.11 -m venv' in source
    assert 'py -3 -m venv' in source
    assert 'if errorlevel 1 goto failed' in source
    assert '-m pip install --disable-pip-version-check' in source
    assert "rmdir" not in source.lower()


def test_editor_preserves_original_doctor_codes():
    app = (ROOT / "SABLON_V2_MIMARI/app.py").read_text(encoding="utf-8")
    frontend = (ROOT / "SABLON_V2_MIMARI/static/js/main.js").read_text(encoding="utf-8")
    assert '"doctor": report,' in app
    assert '"doctor_guidance": doctor_guidance(report),' in app
    assert "data.uyarilar || []" in frontend
    assert 'const guidance = data.doctor_guidance || {}' in frontend
    assert 'OTOMATİK ONARIM YAPILMAZ' in frontend
