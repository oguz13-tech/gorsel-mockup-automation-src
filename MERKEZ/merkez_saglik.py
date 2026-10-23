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
    # Paths are intentionally inherited from pinned legacy Daily V2. Do not
    # rewrite these paths or create fake templates when the files are absent.
    code=Path('C:/AI_WORK/gorsel-mockup-automation-src')
    backup=Path('C:/AI_BACKUPS/GORSEL_MOCKUP/P0_20261019_214610_99f583e8')
    runtime=user/'OneDrive'/'Masaüstü'/'GörselÜretme-ve-Mockup Otomasyonu'
    required={
      r'Kurulu 6 kategori motoru: C:\AI_WORK\gorsel-mockup-automation-src':code/'99_SISTEM_MOTORLARI_VE_KODLAR'/'SISTEM_MOTORU'/'pc_master_factory.py',
      r'Onaylı 6 kategori yedeği: C:\AI_BACKUPS\GORSEL_MOCKUP':backup/'RUNTIME_BACKUP_SHA256.json',
      '6 kategori çalışma klasörü (OneDrive Masaüstü)':runtime/'SABLON_V2_MIMARI'/'ayarlar.db',
    }
    missing=[name for name,path in required.items() if not path.is_file()]
    deps={name:importlib.util.find_spec(name) is not None for name in ('tkinter','cv2','numpy','PIL','openpyxl')}
    petek_ready=all(deps.values())
    from legacy_manager import inspect, preferred_runtime, preferred_code
    editor=inspect(preferred_runtime(userprofile=userprofile),preferred_code())
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
