# -*- coding: utf-8 -*-
"""P0: Read-only template-health audit. Never auto-move, copy or delete images."""
import json
import os
from pathlib import Path


def onarim_islemini_baslat(runtime_root=None):
    root = Path(runtime_root or os.environ.get("MOCKUP_RUNTIME_WORKSPACE") or Path(__file__).resolve().parents[2])
    pool = root / "2_SABLON_HAVUZU"
    archive = root / "2_SABLON_HAVUZU_ORIJINAL_YEDEK"
    config = root / "99_SISTEM_MOTORLARI_VE_KODLAR" / "SISTEM_MOTORU" / "ayarlar.json"
    missing = []
    for label, path in (("WORKING_POOL", pool), ("ORIGINAL_ARCHIVE", archive), ("LEGACY_SETTINGS", config)):
        if not path.exists():
            missing.append({"kind": label, "path": str(path)})
    # Report is returned, never saved to runtime or used to perform repairs.
    return {"status": "READ_ONLY_AUDIT", "read_only": True,
            "automatic_repairs": "DISABLED", "missing": missing}


if __name__ == "__main__":
    print(json.dumps(onarim_islemini_baslat(), ensure_ascii=False, indent=2))
