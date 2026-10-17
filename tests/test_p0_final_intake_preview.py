"""Final integration: isolated receipt-intake and preview; never live OneDrive."""
import hashlib
import json
import tempfile
from pathlib import Path
import cv2
import numpy as np
import pytest
from scripts.safe_intake_manual import stage

CAT="01_Wifi_Kutusu"


def test_safe_intake_same_name_different_content_preserved():
    with tempfile.TemporaryDirectory(prefix="intake-p0-") as td:
        root=Path(td)
        runtime=root/"fake-runtime"
        (runtime/"2_SABLON_HAVUZU_ORIJINAL_YEDEK").mkdir(parents=True)
        a=root/"mail-a"/"same.png"; b=root/"mail-b"/"same.png"
        a.parent.mkdir();b.parent.mkdir()
        a.write_bytes(b"RAW-A");b.write_bytes(b"RAW-B")
        result=stage(runtime,CAT,[a,b])
        assert len(result)==2
        assert result[0]["destination"] != result[1]["destination"]
        for source,row in zip((a,b),result):
            image=Path(row["destination"])
            assert image.read_bytes()==source.read_bytes()
            assert hashlib.sha256(image.read_bytes()).hexdigest()==row["sha256"]
            receipt=runtime/"SABLON_V2_MIMARI"/"recovery"/"intake_receipts"/(row["id"]+".json")
            assert json.loads(receipt.read_text())["sha256"]==row["sha256"]
        assert a.read_bytes()==b"RAW-A" and b.read_bytes()==b"RAW-B"


def test_safe_intake_rejects_inside_runtime_and_unknown_category():
    with tempfile.TemporaryDirectory(prefix="intake-p0-") as td:
        root=Path(td)
        runtime=root/"fake-runtime"
        (runtime/"2_SABLON_HAVUZU_ORIJINAL_YEDEK").mkdir(parents=True)
        image=runtime/"inside.png";image.write_bytes(b"IMAGE")
        with pytest.raises(ValueError, match="SOURCE_MUST_BE_OUTSIDE_RUNTIME"):
            stage(runtime,CAT,[image])
        with pytest.raises(ValueError, match="UNKNOWN_CATEGORY"):
            stage(runtime,"evil",[image])


def test_preview_stays_out_of_watched_folder():
    from SABLON_V2_MIMARI.core.safe_working_revision import save_preview_only
    with tempfile.TemporaryDirectory(prefix="preview-p0-") as td:
        root=Path(td)
        rendered=np.zeros((25,30,4),dtype=np.uint8)
        preview=save_preview_only(root,CAT,"Wifi_Kutusu_001.png",rendered)
        assert preview.parent.parent.name=="_ONIZLEME_SABLONLAR"
        assert preview.is_file()
        assert not (root/"YENI-BOS MOCKUP SABLON HAVUZU").exists()
