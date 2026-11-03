"""Install the reviewed PETEK master revisions without replacing live originals."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
from datetime import datetime
from pathlib import Path


ROOT_UIDS = (
    "50fa3951-3ba1-4aba-bfc2-c26527cc076b",
    "79ffa43d-baba-4f8c-944a-1efa3e85a198",
    "8fa31037-654d-4d5c-bc9a-556a7b49c170",
    "Gemini_Generated_Image_65hptp65hptp65hp-devam-yeni-varyasyon",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _find_source(base_profile: dict, runtime_root: Path | None = None) -> Path:
    original = Path(base_profile["source"])
    candidates = [original]
    configured = runtime_root or os.getenv("GORSEL_RUNTIME_ROOT")
    roots = [Path(configured)] if configured else []
    candidates.extend(root / original.name for root in roots)
    for candidate in candidates:
        if candidate.is_file() and sha256(candidate) == base_profile["source_sha"]:
            return candidate
    for root in roots:
        if not root.is_dir():
            continue
        for candidate in root.rglob(original.name):
            if candidate.is_file() and sha256(candidate) == base_profile["source_sha"]:
                return candidate
    raise RuntimeError(
        f"PETEK_SOURCE_NOT_FOUND_OR_SHA_MISMATCH: {base_profile['uid']}"
    )


def _atomic_json(path: Path, data: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    os.replace(temporary, path)


def install(package_root: Path | None = None, *, approval_token: str = "") -> dict:
    if approval_token != "ONAYLIYORUM: PETEK_MASTER_REVISION_AKTIFLESTIR":
        raise RuntimeError(
            "PETEK_MASTER_ACTIVATION_REQUIRES_EXPLICIT_HUMAN_APPROVAL"
        )
    package_root = Path(package_root or Path(__file__).resolve().parents[1])
    bundle = package_root / "PETEK_MASTER_REVISIONS"
    live = Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "GorselMockup" / "PetekV3"
    profiles = live / "profiles"
    masks = live / "masks"
    profiles.mkdir(parents=True, exist_ok=True)
    masks.mkdir(parents=True, exist_ok=True)
    index = json.loads((live / "active_revisions.json").read_text(encoding="utf-8")) \
        if (live / "active_revisions.json").is_file() else {"version": 1, "entries": {}}
    expected = {
        uid: f"{uid}_r_mastergrid_20261101" for uid in ROOT_UIDS
    }
    if all(
        index.get("entries", {}).get(uid, {}).get("active_uid") == revision_uid
        and (profiles / f"{revision_uid}.json").is_file()
        and (masks / f"{json.loads((profiles / f'{revision_uid}.json').read_text(encoding='utf-8'))['mask_sha']}.png").is_file()
        for uid, revision_uid in expected.items()
    ):
        return {"status": "PETEK_MASTER_REVISIONS_ALREADY_ACTIVE", "installed": []}
    backup = live / "backups" / ("master_revision_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
    backup.mkdir(parents=True, exist_ok=False)
    installed = []
    for root_uid in ROOT_UIDS:
        base_path = profiles / f"{root_uid}.json"
        bundled_path = bundle / "profiles" / f"{root_uid}_r_mastergrid_20261101.json"
        if not base_path.is_file() or not bundled_path.is_file():
            raise RuntimeError(f"PETEK_PROFILE_MISSING: {root_uid}")
        base = json.loads(base_path.read_text(encoding="utf-8"))
        revision = json.loads(bundled_path.read_text(encoding="utf-8"))
        source = _find_source(base, os.getenv("GORSEL_RUNTIME_ROOT"))
        if source_sha := revision.get("source_sha"):
            if source_sha != base.get("source_sha"):
                raise RuntimeError(f"PETEK_SOURCE_SHA_CONFLICT: {root_uid}")
        revision["source"] = str(source)
        revision["source_sha"] = base["source_sha"]
        revision["status"] = "APPROVED"
        revision["reviewer"] = "Kullanici-gorsel-onayi-2026-11-02"
        revision_uid = revision["uid"]
        revision_mask = masks / f"{revision['mask_sha']}.png"
        bundled_mask = bundle / "masks" / revision_mask.name
        if not bundled_mask.is_file():
            raise RuntimeError(f"PETEK_MASK_BUNDLE_MISSING: {revision_uid}")
        for path in (profiles / f"{revision_uid}.json", revision_mask):
            if path.exists():
                shutil.copy2(path, backup / path.name)
        shutil.copy2(bundled_mask, revision_mask)
        profiles_tmp = profiles / f".{revision_uid}.json.tmp"
        profiles_tmp.write_text(json.dumps(revision, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(profiles_tmp, profiles / f"{revision_uid}.json")
        base_entry = index["entries"].get(root_uid, {"history": [root_uid]})
        history = list(dict.fromkeys(base_entry.get("history", []) + [root_uid]))
        index["entries"][root_uid] = {
            "active_uid": revision_uid,
            "history": history,
            "source_sha": base["source_sha"],
        }
        installed.append({"base_uid": root_uid, "active_uid": revision_uid, "source": str(source)})
    _atomic_json(live / "active_revisions.json", index)
    return {"status": "PETEK_MASTER_REVISIONS_ACTIVE", "backup": str(backup), "installed": installed}


if __name__ == "__main__":
    print(json.dumps(install(), ensure_ascii=False, indent=2))
