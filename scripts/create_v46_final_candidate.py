"""Create one local, data-free V4.6 candidate folder and ZIP."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import zipfile
from pathlib import Path


EXCLUDED_PARTS = {
    ".git", "__pycache__", "V46_FINAL_CANDIDATE",
    "2_SABLON_HAVUZU", "2_SABLON_HAVUZU_ORIJINAL_YEDEK",
    "3_URETILEN_MOCKUPLAR",
}
EXCLUDED_NAMES = {
    "ayarlar.json", "ayarlar.db", "v4_ortak_uretim.sqlite3",
    "cloud_urls_v43.sqlite3",
}


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def create(root: Path, commit: str) -> tuple[Path, Path]:
    candidate = root / "V46_FINAL_CANDIDATE"
    archive = root / "V46_FINAL_CANDIDATE.zip"
    if candidate.exists():
        raise FileExistsError(f"Refusing to overwrite candidate: {candidate}")
    if archive.exists():
        raise FileExistsError(f"Refusing to overwrite archive: {archive}")
    candidate.mkdir()
    tracked = subprocess.check_output(
        ["git", "ls-files", "-z"], cwd=root, text=False
    ).split(b"\0")
    copied = []
    for raw in tracked:
        if not raw:
            continue
        relative = Path(raw.decode("utf-8"))
        if any(part in EXCLUDED_PARTS for part in relative.parts):
            continue
        if relative.name in EXCLUDED_NAMES:
            continue
        source = root / relative
        if not source.is_file():
            continue
        target = candidate / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied.append(relative.as_posix())
    manifest = {
        "candidate": "V46_FINAL_CANDIDATE",
        "source_branch": "feature/v46-safe-consolidation-20261024",
        "source_commit": commit,
        "contains_private_runtime_data": False,
        "files": {name: digest(candidate / name) for name in copied},
    }
    (candidate / "MANIFEST_SHA256.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as output:
        for path in sorted(candidate.rglob("*")):
            if path.is_file():
                output.write(path, Path(candidate.name) / path.relative_to(candidate))
    return candidate, archive


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    commit = subprocess.check_output(
        ["git", "rev-parse", "--short", "HEAD"], cwd=root, text=True
    ).strip()
    candidate, archive = create(root, commit)
    print(json.dumps({"candidate": str(candidate), "archive": str(archive)}))
