import sqlite3
import sys
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "MERKEZ"))

from central_upload_v500 import CentralUploadRegistry, CentralUploader, safe_prefix  # noqa: E402


def runtime(tmp_path):
    (tmp_path / "SABLON_V2_MIMARI").mkdir()
    (tmp_path / "2_SABLON_HAVUZU").mkdir()
    (tmp_path / "2_SABLON_HAVUZU_ORIJINAL_YEDEK").mkdir()
    db = sqlite3.connect(tmp_path / "SABLON_V2_MIMARI" / "ayarlar.db")
    db.execute("CREATE TABLE categories(id TEXT PRIMARY KEY, label TEXT)")
    db.execute("CREATE TABLE templates(category_id TEXT, filename TEXT, data TEXT, PRIMARY KEY(category_id,filename))")
    db.commit(); db.close()
    return tmp_path


def test_design_upload_preserves_extension_and_never_reuses_number(tmp_path):
    root = runtime(tmp_path)
    first = root / "first.png"; second = root / "second.webp"
    Image.new("RGBA", (8, 8), (1, 2, 3, 120)).save(first)
    Image.new("RGB", (8, 8), (8, 7, 6)).save(second)
    uploader = CentralUploader(root)
    one = uploader.upload_designs("Yatay", [first], prefix="Dini Motif")
    assert one["success"] == 1
    assert (root / "HAM BASKI TASARIMLARI" / "Yataylar" / "Dini_Motif_Yatay_Tasarim001.png").is_file()
    two = uploader.upload_designs("Yatay", [second])
    assert two["success"] == 1
    assert (root / "HAM BASKI TASARIMLARI" / "Yataylar" / "Yatay_Tasarim002.webp").is_file()
    assert safe_prefix("Dini / Motif") == "Dini_Motif"


def test_mockup_is_registered_for_corner_review_without_overwriting(tmp_path):
    root = runtime(tmp_path)
    source = root / "mockup.jpeg"; Image.new("RGB", (10, 10), (20, 20, 20)).save(source)
    uploader = CentralUploader(root)
    result = uploader.upload_mockups("01_Wifi_Kutusu", [source])
    assert result["success"] == 1
    name = "Wifi_Kutusu_001.jpeg"
    assert (root / "2_SABLON_HAVUZU" / "01_Wifi_Kutusu" / name).is_file()
    db = sqlite3.connect(root / "SABLON_V2_MIMARI" / "ayarlar.db")
    row = db.execute("SELECT data FROM templates WHERE category_id=? AND filename=?", ("01_Wifi_Kutusu", name)).fetchone()
    assert row is not None and "REVIEW_REQUIRED" in row[0]
    db.close()


def test_invalid_extension_is_reported_without_stopping_batch(tmp_path):
    root = runtime(tmp_path)
    good = root / "good.jpg"; bad = root / "bad.gif"
    Image.new("RGB", (4, 4), (1, 1, 1)).save(good)
    bad.write_bytes(b"not-an-image")
    result = CentralUploader(root).upload_designs("Dikey", [bad, good])
    assert result["success"] == 1 and result["failed"] == 1


def test_folder_import_retains_selected_and_nested_folders(tmp_path):
    root = runtime(tmp_path)
    source_root = tmp_path / "Dini Motifler"
    (source_root / "Alt").mkdir(parents=True)
    image = source_root / "Alt" / "motif.png"
    Image.new("RGB", (4, 4), (9, 9, 9)).save(image)
    result = CentralUploader(root).upload_designs("Yatay", [image], source_root=source_root)
    assert result["success"] == 1
    assert (root / "HAM BASKI TASARIMLARI" / "Yataylar" / "Dini Motifler" / "Alt" / "Yatay_Tasarim001.png").is_file()


def test_central_design_gate_checks_registry_bytes_and_unregistered_files(tmp_path):
    root = runtime(tmp_path)
    image = root / "source.png"
    Image.new("RGB", (4, 4), (9, 9, 9)).save(image)
    uploader = CentralUploader(root)
    assert uploader.upload_designs("Yatay", [image])["success"] == 1
    registry = CentralUploadRegistry(root)
    assert registry.validate_designs_for_production()["unregistered"] == []

    extra = root / "HAM BASKI TASARIMLARI" / "Yataylar" / "Yatay_Tasarim999.png"
    Image.new("RGB", (4, 4), (1, 2, 3)).save(extra)
    with pytest.raises(ValueError, match="CENTRAL_UPLOAD_DESIGNS_ONCE_KONTROL"):
        registry.validate_designs_for_production()

    extra.unlink()
    published = root / "HAM BASKI TASARIMLARI" / "Yataylar" / "Yatay_Tasarim001.png"
    published.write_bytes(b"changed")
    with pytest.raises(ValueError, match="CENTRAL_UPLOAD_DESIGNS_ONCE_KONTROL"):
        registry.validate_designs_for_production()

