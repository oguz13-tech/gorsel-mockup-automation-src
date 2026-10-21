# -*- coding: utf-8 -*-
"""Reproducible Windows source package builder for PETEK V3 factory staging.

Only explicitly allowlisted tracked CODE is packaged, never local runtime
images, SQLite, keys or private backups. This script NEVER installs to live.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODE_DIRS = frozenset({
    "SABLON_V2_MIMARI", "99_SISTEM_MOTORLARI_VE_KODLAR",
    "BAGIMSIZ_ARACLAR", "V2_KONTROL_MERKEZI",
    "AI_Kalite_Artirici", "scripts", "docs",
})
CODE_EXTS = frozenset({
    ".py", ".html", ".js", ".css", ".md", ".txt", ".bat",
    ".ps1", ".yml", ".yaml", ".toml", ".cfg", ".ini",
})
ROOT_NAMES = frozenset({
    "AGENTS.md", ".gitignore", "requirements-core.lock.txt",
    "requirements-petek-v3.txt",
})
EXCLUDED_FRAGMENTS = frozenset({
    ".env", ".venv", "__pycache__", "runtime",
    ".pytest_cache", "node_modules", "secrets", "backup",
    "cache", "masks", "private", "output", "image",
})
MAX_SOURCE_FILE_BYTES = 4 * 1024 * 1024
WINDOWS_START = r"""@echo off
setlocal
cd /d "%~dp0"
py -3 -m pip install -r requirements-core.lock.txt
if errorlevel 1 exit /b 1
py -3 scripts\petek_v3_windows_launcher.py --stage
pause
"""
WINDOWS_TEST = r"""@echo off
setlocal
cd /d "%~dp0"
py -3 -m pip install -r requirements-core.lock.txt pytest
if errorlevel 1 exit /b 1
py -3 -m pytest -q tests\test_petek_v3.py
pause
"""
README = """PETEK V3 / Gorsel Mockup Windows staging
================================================
1. EXTRACT to NEW folder (for example C:\\AI_WORK\\MockupPetekV3Candidate).
2. Run START_PETEK_V3_WINDOWS.bat and select current runtime workspace.
3. In existing center open PETEK V3, create/review/approve per-template masks.
4. Run TEST_PETEK_V3_WINDOWS.bat before considering commercial production.

DO NOT overwrite installed code, SQLite, approved corners, original archives.
Stage mode launches localhost UI without running legacy backfill/migration.
PETEK masks, jobs and exports are isolated under Windows LOCALAPPDATA.
Cloud upload and marketplace posting are not performed by PETEK local batch.
Running existing full legacy job-engine requires a separate Windows acceptance
and controlled release: not performed by this package.

This package contains source code only, not personal user data.
"""


def git_items() -> list[Path]:
    """Enumerate tracked files from current git commit without filesystem guesses."""
    raw = subprocess.check_output(["git","ls-files","-z"],cwd=ROOT)
    items=[]
    for token in raw.split(b"\0"):
        if not token:continue
        rel = Path(os.fsdecode(token))
        if rel.is_absolute() or ".." in rel.parts:
            raise ValueError("UNSAFE_GIT_TRACKED_PATH")
        parts = {part.casefold() for part in rel.parts}
        if any(x in parts for x in EXCLUDED_FRAGMENTS):
            continue
        if rel.name in ROOT_NAMES or (
            rel.parts[0] in CODE_DIRS and rel.suffix.casefold() in CODE_EXTS
        ):
            path = ROOT/rel
            if path.is_symlink():
                raise ValueError("TRACKED_SYMLINK_REFUSED:"+rel.as_posix())
            if not path.is_file() or path.stat().st_size > MAX_SOURCE_FILE_BYTES:
                raise ValueError("TRACKED_CODE_MISSING_OR_OVERSIZE:"+rel.as_posix())
            items.append(rel)
    return sorted(items,key=lambda p:p.as_posix())


def build(destination: Path) -> Path:
    """Create a commit-addressed, create-only ZIP with content digest manifest."""
    status = subprocess.check_output(["git","status","--porcelain"],cwd=ROOT).strip()
    if status:
        raise RuntimeError("DIRTY_GIT_TREE: commit all changes before packaging")
    head = subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip()
    paths = git_items()
    required = {
        "SABLON_V2_MIMARI/core/petek_surface_v3.py",
        "SABLON_V2_MIMARI/core/petek_mask_store.py",
        "SABLON_V2_MIMARI/core/petek_serial_factory.py",
        "SABLON_V2_MIMARI/core/petek_v3_routes.py",
        "SABLON_V2_MIMARI/static/js/petek_v3.js",
        "SABLON_V2_MIMARI/templates/petek_v3.html",
        "scripts/petek_v3_windows_launcher.py",
    }
    present = {p.as_posix() for p in paths}
    if not required <= present:
        raise RuntimeError("MISSING_REQUIRED_RELEASE_CODE:"+str(sorted(required-present)))
    dest = Path(destination).resolve()
    dest.mkdir(parents=True,exist_ok=True)
    target = dest / f"GORSEL_URETIM_FABRIKASI_WINDOWS_CANDIDATE_{head[:12]}.zip"
    if target.exists():
        raise FileExistsError("PACKAGE_ALREADY_EXISTS_NO_OVERWRITE:"+str(target))
    manifest = {"git_head":head,"files":{},"mode":"staging_not_live"}
    for path in paths:
        manifest["files"][path.as_posix()] = hashlib.sha256(
            (ROOT/path).read_bytes()).hexdigest()
    extras = {
        "START_PETEK_V3_WINDOWS.bat":WINDOWS_START.encode("utf-8"),
        "TEST_PETEK_V3_WINDOWS.bat":WINDOWS_TEST.encode("utf-8"),
        "WINDOWS_PETEK_README.txt":README.encode("utf-8"),
    }
    for name,data in extras.items():
        manifest["files"][name]=hashlib.sha256(data).hexdigest()
    manifest_bytes=json.dumps(manifest,indent=2,sort_keys=True).encode("utf-8")
    with target.open("xb") as stream:
        with zipfile.ZipFile(stream,"w",compression=zipfile.ZIP_DEFLATED,
                             compresslevel=6) as bundle:
            for path in paths:
                bundle.write(ROOT/path,arcname=path.as_posix())
            for name,data in extras.items():
                bundle.writestr(name,data)
            bundle.writestr("SOURCE_SNAPSHOT.json",manifest_bytes)
    return target


def inspect(package: Path) -> dict:
    """Verify archive manifest hashes without extracting or trusting paths."""
    with zipfile.ZipFile(package) as source:
        names=source.namelist()
        if len(names)!=len(set(names)):
            raise ValueError("DUPLICATE_ZIP_ENTRY")
        for name in names:
            p=Path(name)
            if p.is_absolute() or ".." in p.parts:
                raise ValueError("UNSAFE_ZIP_ENTRY:"+name)
        manifest=json.loads(source.read("SOURCE_SNAPSHOT.json"))
        if set(names)!=(set(manifest["files"])|{"SOURCE_SNAPSHOT.json"}):
            raise ValueError("ZIP_MANIFEST_FILE_LIST_MISMATCH")
        for name,sha in manifest["files"].items():
            if hashlib.sha256(source.read(name)).hexdigest()!=sha:
                raise ValueError("ZIP_CONTENT_HASH_MISMATCH:"+name)
        return {"git_head":manifest["git_head"],
                "tracked_files":len(manifest["files"]),
                "mode":manifest["mode"],"ok":True}


def main() -> int:
    """Build or inspect from a normal CLI without touching any runtime folder."""
    cli=argparse.ArgumentParser(description=__doc__)
    sub=cli.add_subparsers(dest="command",required=True)
    b=sub.add_parser("build")
    b.add_argument("--destination",type=Path,default=ROOT/"dist")
    i=sub.add_parser("inspect")
    i.add_argument("zip",type=Path)
    args=cli.parse_args()
    try:
        if args.command=="build":
            archive=build(args.destination)
            print(json.dumps({"archive":str(archive),**inspect(archive)},indent=2))
        else:
            print(json.dumps(inspect(args.zip),indent=2))
        return 0
    except (OSError,ValueError,RuntimeError,subprocess.CalledProcessError,
            zipfile.BadZipFile) as exc:
        print(f"PETEK_RELEASE_REJECTED:{type(exc).__name__}:{exc}")
        return 2


if __name__=="__main__":
    raise SystemExit(main())
