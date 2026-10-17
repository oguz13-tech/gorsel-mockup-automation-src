# -*- coding: utf-8 -*-
"""Human-driven create-only intake; never starts the watcher or mutates originals."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import shutil
import sys
import time
import uuid
from pathlib import Path

CATEGORIES = (
    "01_Wifi_Kutusu","02_Cam_Tablo_Dikey","02_Cam_Tablo_Yatay",
    "03_Ahsap_Tablo","04_Cam_Dograma","05_Ocak_Arkasi",
)
EXTS = {".png",".jpg",".jpeg",".webp",".bmp",".avif"}


def stage(runtime_root: Path, category: str, sources: list[Path]) -> list[dict]:
    root = Path(runtime_root).resolve()
    if category not in CATEGORIES:
        raise ValueError("UNKNOWN_CATEGORY")
    if not (root / "2_SABLON_HAVUZU_ORIJINAL_YEDEK").is_dir():
        raise RuntimeError("RUNTIME_NOT_VERIFIED")
    inbox_root = root / "YENI-BOS MOCKUP SABLON HAVUZU"
    receipt_root = root / "SABLON_V2_MIMARI" / "recovery" / "intake_receipts"
    category_dir = inbox_root / category
    if any(x.is_symlink() for x in (inbox_root, category_dir, receipt_root)):
        raise RuntimeError("SYMLINK_FOLDER_BLOCKED")
    category_dir.mkdir(parents=True, exist_ok=True)
    receipt_root.mkdir(parents=True, exist_ok=True)
    result = []
    for source in sources:
        src = Path(source).resolve()
        if not src.is_file() or src.suffix.lower() not in EXTS:
            raise ValueError("INVALID_SOURCE_IMAGE:" + src.name)
        if src.is_relative_to(root):
            raise ValueError("SOURCE_MUST_BE_OUTSIDE_RUNTIME")
        receipt_id = time.strftime("%Y%m%dT%H%M%S") + "_" + uuid.uuid4().hex
        # Hidden temporary extension is not considered ingestible by watcher.
        dest = category_dir / (src.stem + "__intake_" + receipt_id + src.suffix.lower())
        tmp = category_dir / ("." + uuid.uuid4().hex + ".pending")
        sha = hashlib.sha256()
        nbytes = 0
        try:
            with src.open("rb") as reader, tmp.open("xb") as writer:
                for chunk in iter(lambda: reader.read(1024 * 1024), b""):
                    sha.update(chunk); nbytes += len(chunk); writer.write(chunk)
                writer.flush(); os.fsync(writer.fileno())
            # Hard link is create-only and cannot replace an existing filename.
            os.link(tmp, dest)
            # Receipt is mandatory for a complete intake claim.
            receipt = {"id":receipt_id,"source":str(src),"destination":str(dest),
                       "category":category,"sha256":sha.hexdigest(),"bytes":nbytes}
            receipt_path = receipt_root / (receipt_id + ".json")
            with receipt_path.open("xb") as out:
                out.write(json.dumps(receipt, ensure_ascii=False, indent=2).encode("utf-8"))
                out.flush(); os.fsync(out.fileno())
            result.append(receipt)
        except BaseException:
            # If journaling failed, do not destroy a published image:
            # retain it in inbox as a recoverable, unreceipted intake.
            raise
        finally:
            tmp.unlink(missing_ok=True)
    return result


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--runtime-root",required=True,type=Path)
    p.add_argument("--category",choices=CATEGORIES)
    p.add_argument("--file",action="append",type=Path)
    p.add_argument("--execute",action="store_true")
    args=p.parse_args(argv)
    if not args.execute:
        print("PLAN_ONLY: no templates moved or copied.")
        return 0
    category=args.category
    files=args.file
    if not files or not category:
        from tkinter import Tk, filedialog, simpledialog
        root=Tk();root.withdraw()
        if not category:
            category=simpledialog.askstring("Sablon Kategorisi","Kategori klasor kodu: "+", ".join(CATEGORIES))
        if not files:
            files=[Path(x) for x in filedialog.askopenfilenames(title="Yeni sablon dosyalarini secin")]
        root.destroy()
    if not category or not files:
        print("CANCELLED");return 2
    records=stage(args.runtime_root, category, files)
    print(json.dumps({"status":"STAGED","count":len(records),"receipts":records},ensure_ascii=False,indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
