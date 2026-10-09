import argparse
import hashlib
import importlib.metadata
import json
import os
import sys
import tempfile
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parents[1]


def _version(dist_name):
    try:
        return importlib.metadata.version(dist_name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _source_lock_hash():
    lock_path = SOURCE_ROOT / "SABLON_V2_MIMARI" / "runtime_lock.json"
    if not lock_path.is_file():
        return None
    return hashlib.sha256(lock_path.read_bytes()).hexdigest()


def collect():
    payload = {
        "schema_version": 1,
        "python": ".".join(map(str, sys.version_info[:3])),
        "numpy": _version("numpy"),
        "opencv_python": (
            _version("opencv-python")
            or _version("opencv-python-headless")
        ),
        "torch": _version("torch"),
        "transformers": _version("transformers"),
        "runtime_lock_sha256": _source_lock_hash(),
    }
    try:
        import torch
        payload["torch_cuda"] = getattr(torch.version, "cuda", None)
        payload["cuda_available"] = bool(torch.cuda.is_available())
        payload["cudnn"] = (
            int(torch.backends.cudnn.version())
            if torch.backends.cudnn.is_available()
            else None
        )
    except Exception:
        payload["torch_cuda"] = None
        payload["cuda_available"] = False
        payload["cudnn"] = None
    return payload


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ensure", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    runtime = Path(
        os.environ.get("MOCKUP_RUNTIME_WORKSPACE") or SOURCE_ROOT
    ).expanduser().resolve()
    target = runtime / "SABLON_V2_MIMARI" / "runtime_ai_baseline.json"
    target.parent.mkdir(parents=True, exist_ok=True)

    if target.exists() and args.ensure and not args.force:
        print(f"Runtime AI baseline mevcut: {target}")
        return 0

    payload = collect()
    fd, tmp_name = tempfile.mkstemp(
        prefix="runtime_ai_baseline_",
        suffix=".tmp",
        dir=str(target.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, target)
    finally:
        if os.path.exists(tmp_name):
            os.remove(tmp_name)

    print(f"Runtime AI baseline kaydedildi: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
