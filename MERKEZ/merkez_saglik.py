"""Read-only Windows delivery readiness check; never touches live assets."""
from __future__ import annotations
import os
import sys
from pathlib import Path
import importlib.util
import json


def report(*, platform=None, userprofile=None):
    platform = platform if platform is not None else os.name
    if userprofile is None:
        userprofile=os.environ.get('USERPROFILE', '')
    user=Path(userprofile) if userprofile else Path.home()
    # Resolve the same portable runtime as the launchers and every production
    # module.  In particular, do not recreate the historical OneDrive path
    # here: a health check must inspect the selected data root, not report a
    # different dataset as the active installation.
    from legacy_manager import preferred_runtime, preferred_code
    runtime=preferred_runtime(userprofile=str(user))
    code=preferred_code()
    required={
      # Legacy Daily V2 imports these files before its GUI opens. Its user
      # selection was never part of the code-only ZIP and must not be invented.
      'Günlük V2 sabit seçim dosyası (haricî)':Path(__file__).resolve().parent/'GUNLUK'/'BATCH_SELECTION.json',
      'Günlük V2 sayı güvenliği dosyası':Path(__file__).resolve().parent/'GUNLUK'/'INSTALLED_NUMBER_SPEC.json',
      'Kurulu 6 kategori motoru':code/'99_SISTEM_MOTORLARI_VE_KODLAR'/'SISTEM_MOTORU'/'pc_master_factory.py',
      'Çalışma veritabanı':runtime/'SABLON_V2_MIMARI'/'ayarlar.db',
      'Çalışma şablon havuzu':runtime/'2_SABLON_HAVUZU',
      'Orijinal şablon yedeği':runtime/'2_SABLON_HAVUZU_ORIJINAL_YEDEK',
    }
    missing=[name for name,path in required.items()
             if not path.exists() or path.is_symlink()]
    deps={name:importlib.util.find_spec(name) is not None for name in ('tkinter','cv2','numpy','PIL','openpyxl')}
    petek_ready=all(deps.values())
    from legacy_manager import inspect
    editor=inspect(runtime,code)
    return dict(version='4.2.2',os=platform,python=sys.version.split()[0],
        v42_installed_code_ready=(Path(__file__).resolve().parent/'URETIM_V4'/'unified_batch.py').is_file(),
        v42_legacy_editor_ready=editor['ready'],
        v42_native_windows_verified=False,
        legacy_editor_ready=editor['ready'],legacy_editor_source=editor['code'],
        legacy_editor_problems=editor['problems'],
        legacy_ready=platform=='nt' and not missing, legacy_missing=missing,
        petek_ready=petek_ready,dependencies=deps,
        legacy_assets_are_external=True,source_paths_mutated=False)


if __name__ == '__main__':
    print(json.dumps(report(),ensure_ascii=False,indent=2))
