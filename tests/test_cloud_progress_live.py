"""Regression coverage for live cloud-link progress and ETA reporting."""

import sys
import time
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "MERKEZ"))

import URETIM_V4.cloud_excel_v43 as cloud_module
from PETEK_V3 import engine as petek_engine
from URETIM_V4.cloud_excel_v43 import CloudExcel


def test_cloud_link_progress_is_emitted_as_workers_finish(tmp_path, monkeypatch):
    state = tmp_path / "state"
    output_dir = state / "uretilen_gorseller" / "LOCAL" / "03_Ahsap_Tablo"
    output_dir.mkdir(parents=True)
    rows = []
    for index in range(4):
        output = output_dir / f"image-{index}.png"
        Image.new("RGB", (128, 128), (index * 30, 100, 180)).save(output)
        rows.append({
            "key": str(index),
            "sku": f"AHT-LOCAL-{index:03d}",
            "category": "03_Ahsap_Tablo",
            "art_name": f"art-{index}.png",
            "output": str(output),
            "output_sha": petek_engine.digest(output),
        })

    monkeypatch.setattr(
        cloud_module,
        "_provider_routes",
        lambda _runtime: [{"provider": "imgbb", "keys": ["test-only"]}],
    )

    def upload(path, _keys, _backup):
        # Deliberately stagger completions so the first callback cannot only
        # arrive after the whole worker pool has drained.
        time.sleep(0.02 * (int(Path(path).stem.rsplit("-", 1)[-1]) + 1))
        return "https://i.ibb.co/test.png"

    snapshots = []
    result = CloudExcel(state, state / "reports").publish_existing(
        rows,
        upload_fn=upload,
        progress=snapshots.append,
    )

    assert result["uploaded"] == len(rows)
    live = [item for item in snapshots if item.get("completed", 0)]
    assert [item["completed"] for item in live[:4]] == [1, 2, 3, 4]
    assert any(item["eta_seconds"] is not None for item in live[:-1])
    assert all(item["elapsed_seconds"] > 0 for item in live)
