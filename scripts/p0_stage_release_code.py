# -*- coding: utf-8 -*-
"""Stage release code in a NEW directory; never overwrite live code or data.

This is purposely NOT a live installer. Promotion/launcher switch requires
separate human approval after offline acceptance and SQLite backup.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import subprocess
import uuid
from pathlib import Path

def git(root:Path,*args:str) -> bytes:
    result=subprocess.run(["git","-C",str(root),*args],stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE,check=False,timeout=60)
    if result.returncode:
        raise RuntimeError("GIT_SOURCE_UNAVAILABLE:"+result.stderr.decode(errors="replace")[:200])
    return result.stdout

def stage_code(source_root:Path,destination_root:Path,expected_sha:str)->dict:
    source=Path(source_root).resolve()
    dest=Path(destination_root).resolve()
    current=git(source,"rev-parse","HEAD").decode().strip()
    if current != expected_sha or len(expected_sha)!=40:
        raise RuntimeError("UNEXPECTED_RELEASE_HEAD")
    if dest==source or dest.is_relative_to(source) or source.is_relative_to(dest):
        raise RuntimeError("STAGING_INSIDE_SOURCE_BLOCKED")
    if dest.exists():
        raise FileExistsError("RELEASE_DEST_ALREADY_EXISTS_NO_OVERWRITE")
    # Never copy a modified/untracked file into a release. Git blob objects
    # are the immutable source of truth.
    manifest={"head":current,"mode":"STAGED_CODE_ONLY_NO_ACTIVATION",
              "source_modified":False,"runtime_modified":False,"files":[]}
    tracked=git(source,"ls-tree","-r","-z","--name-only",current).split(b"\0")
    dest.mkdir(parents=True)
    for raw in tracked:
        if not raw:
            continue
        relative=raw.decode("utf-8","surrogateescape")
        if relative.startswith("/") or ".." in Path(relative).parts:
            raise RuntimeError("UNSAFE_TRACKED_PATH")
        target=dest/relative
        if not target.resolve().is_relative_to(dest):
            raise RuntimeError("UNSAFE_RELEASE_PATH")
        target.parent.mkdir(parents=True,exist_ok=True)
        contents=git(source,"show",current+":"+relative)
        with target.open("xb") as fp:
            fp.write(contents)
            fp.flush();os.fsync(fp.fileno())
        manifest["files"].append({"path":relative,"sha256":hashlib.sha256(contents).hexdigest(),
                                 "size":len(contents)})
    receipt=dest/"P0_STAGED_CODE_MANIFEST.json"
    with receipt.open("x",encoding="utf-8") as fp:
        json.dump(manifest,fp,indent=2,ensure_ascii=False)
    return {"head":current,"staged_code_files":len(manifest["files"]),
            "destination":str(dest),"manifest":str(receipt),
            "live_install_performed":False,"rollback_required":False}

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-root",required=True,type=Path)
    p.add_argument("--destination-root",required=True,type=Path)
    p.add_argument("--expected-head",required=True)
    p.add_argument("--execute",action="store_true")
    a=p.parse_args(argv)
    if not a.execute:
        print("PLAN_ONLY: existing launchers/code/runtime unchanged.")
        return 0
    print(json.dumps(stage_code(a.source_root,a.destination_root,a.expected_head),
                     indent=2,ensure_ascii=False))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
