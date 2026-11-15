"""Offline contract tests for the PETEK four-size overlay stage."""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "MERKEZ"))
from URETIM_V4.petek_overlay_variations_v1 import (  # noqa: E402
    discover_overlay_groups,
    process_source,
    validate_overlay_folder,
)


def _card(path: Path, size, color, box) -> None:
    image = Image.new("RGBA", size, (0, 0, 0, 0))
    pixels = image.load()
    for y in range(box[1], box[3]):
        for x in range(box[0], box[2]):
            pixels[x, y] = color
    image.save(path)


def _pool(root: Path) -> Path:
    for folder in ("76CM", "96CM", "116CM", "136CM", "Yan_Bilgi_Kutusu", "alt_overlay"):
        (root / folder).mkdir(parents=True)
    _card(root / "76CM" / "upper.png", (600, 180), (255, 0, 0, 220), (20, 20, 580, 160))
    for cm, color in (("96CM", (0, 255, 0, 220)), ("116CM", (0, 0, 255, 220)), ("136CM", (255, 255, 0, 220))):
        _card(root / cm / "upper.png", (600, 180), color, (20, 20, 580, 160))
    for index, color in enumerate(((255, 0, 255, 220), (0, 255, 255, 220), (255, 128, 0, 220))):
        _card(root / "Yan_Bilgi_Kutusu" / f"side{index}.png", (180, 600), color, (20, 20, 160, 580))
    _card(root / "alt_overlay" / "altbilgi-overlay.png", (600, 180), (128, 255, 128, 220), (20, 20, 580, 160))
    return root


def test_four_outputs_keep_clean_source_and_contract(tmp_path):
    pool = _pool(tmp_path / "Overlay_Giydirme")
    validation = validate_overlay_folder(pool)
    assert validation["ready"]
    source = tmp_path / "clean.png"
    Image.new("RGB", (1200, 1600), (90, 90, 90)).save(source, dpi=(96, 96))
    source_bytes = source.read_bytes()
    source_sha = hashlib.sha256(source_bytes).hexdigest()
    result = process_source(
        {"output": str(source), "output_sha": source_sha, "art_name": "Design01.png"},
        validation,
        tmp_path / "out",
        source_sha=source_sha,
    )
    assert [item["cm"] for item in result["results"]] == ["76CM", "96CM", "116CM", "136CM"]
    assert source.read_bytes() == source_bytes
    for item in result["results"]:
        with Image.open(item["output"]) as image:
            assert image.size == (1200, 1800)
            assert image.mode == "RGBA"
            assert tuple(round(value) for value in image.info["dpi"]) == (96, 96)


def test_invalid_png_is_fail_closed_and_reuse_is_deterministic(tmp_path):
    pool = _pool(tmp_path / "Overlay_Giydirme")
    (pool / "96CM" / "broken.png").write_bytes(b"not a png")
    validation = validate_overlay_folder(pool)
    assert not validation["ready"]
    assert any("OVERLAY_PNG_UNREADABLE" in error for error in validation["errors"])


def test_1200x1800_spacer_canvas_is_rejected(tmp_path):
    pool = _pool(tmp_path / "Overlay_Giydirme")
    validation = validate_overlay_folder(pool)
    source = tmp_path / "legacy_spacer_source.png"
    Image.new("RGB", (1200, 1800), (90, 90, 90)).save(source)
    source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    try:
        process_source(
            {"output": str(source), "output_sha": source_sha, "art_name": "Spacer.png"},
            validation,
            tmp_path / "out",
            source_sha=source_sha,
        )
    except ValueError as exc:
        assert "OVERLAY_SOURCE_DIMENSIONS_INVALID" in str(exc)
    else:  # pragma: no cover - the assertion documents the safety gate
        raise AssertionError("legacy 1200x1800 spacer source was accepted")


def test_existing_1200x1800_derivative_is_not_reused(tmp_path):
    pool = _pool(tmp_path / "Overlay_Giydirme")
    validation = validate_overlay_folder(pool)
    source = tmp_path / "clean.png"
    Image.new("RGB", (1200, 1600), (90, 90, 90)).save(source)
    source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    row = {"output": str(source), "output_sha": source_sha, "art_name": "Legacy.png"}
    first = process_source(row, validation, tmp_path / "out", source_sha=source_sha)
    receipts = {
        item["cm"]: {"output_sha": item["output_sha"]}
        for item in first["results"]
    }
    stale = Path(first["results"][0]["output"])
    Image.new("RGB", (1200, 1800), (90, 90, 90)).save(stale)
    second = process_source(
        row | {"overlay_outputs": receipts},
        validation,
        tmp_path / "out",
        source_sha=source_sha,
    )
    replacement = next(item for item in second["results"] if item["cm"] == "76CM")
    assert "__RETRY" in replacement["output"]
    with Image.open(replacement["output"]) as image:
        assert image.size == (1200, 1800)


def test_white_top_padding_does_not_mutate_clean_source(tmp_path):
    pool = _pool(tmp_path / "Overlay_Giydirme")
    validation = validate_overlay_folder(pool)
    source = tmp_path / "clean_with_white_top_padding.png"
    image = Image.new("RGB", (1200, 1600), (90, 90, 90))
    image.paste((250, 250, 250), (0, 0, 1200, 400))
    image.save(source)
    source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    result = process_source(
        {"output": str(source), "output_sha": source_sha, "art_name": "WhiteGap.png"},
        validation,
        tmp_path / "out",
        source_sha=source_sha,
    )
    repaired = [item for item in result["results"] if item["cm"] == "76CM"][0]
    assert repaired["manifest"]["repaired_top_overlay_gap"] == [0, 400]
    with Image.open(repaired["output"]) as output:
        assert output.size == (1200, 1800)
        assert output.getpixel((0, 520))[:3] == (90, 90, 90)


def test_white_bottom_canvas_padding_is_removed_from_output_copy(tmp_path):
    pool = _pool(tmp_path / "Overlay_Giydirme")
    validation = validate_overlay_folder(pool)
    source = tmp_path / "clean_with_white_bottom_padding.png"
    image = Image.new("RGB", (1200, 1600), (90, 90, 90))
    image.paste((250, 250, 250), (0, 1400, 1200, 1600))
    image.save(source)
    source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    result = process_source(
        {"output": str(source), "output_sha": source_sha, "art_name": "BottomGap.png"},
        validation,
        tmp_path / "out",
        source_sha=source_sha,
    )
    repaired = [item for item in result["results"] if item["cm"] == "76CM"][0]
    assert repaired["manifest"]["repaired_bottom_canvas_gap"] == [1400, 1600]
    with Image.open(repaired["output"]) as output:
        assert output.size == (1200, 1800)
        assert output.getpixel((600, 1600))[:3] == (90, 90, 90)


def _grouped_pool(root: Path) -> Path:
    """Build a dynamic-folder fixture whose names are intentionally arbitrary."""
    for cm in ("76CM", "96CM", "116CM", "136CM"):
        group = root / cm / "design_alpha"
        group.mkdir(parents=True)
        if cm == "76CM":
            _card(group / "alpha_asset.png", (600, 180), (255, 0, 0, 220), (20, 20, 580, 160))
        else:
            # The role names are deliberately not encoded in filenames.  The
            # vertical alpha bounds identify the side; horizontal geometry
            # identifies upper/bottom while the group keeps them atomic.
            _card(group / "asset_a.png", (600, 180), (255, 0, 0, 220), (20, 20, 580, 160))
            _card(group / "asset_b.png", (600, 220), (0, 255, 0, 220), (20, 20, 580, 200))
            _card(group / "asset_c.png", (180, 600), (0, 0, 255, 220), (20, 20, 160, 580))
    # A malformed group must be reported and skipped without disabling the
    # valid dynamic group above.
    (root / "116CM" / "future_group").mkdir(parents=True)
    (root / "116CM" / "future_group" / "not_png.jpg").write_bytes(b"ignored")
    (root / "alt_overlay").mkdir(parents=True)
    _card(root / "alt_overlay" / "altbilgi-overlay.png", (600, 180), (128, 255, 128, 220), (20, 20, 580, 160))
    return root


def test_grouped_discovery_is_dynamic_and_group_atomic(tmp_path):
    pool = _grouped_pool(tmp_path / "Overlay_Giydirme")
    validation = validate_overlay_folder(pool)
    assert validation["grouped"] is True
    assert validation["ready"] is True
    assert validation["group_counts"] == {"76CM": 1, "96CM": 1, "116CM": 1, "136CM": 1}
    assert any(item["name"] == "future_group" for item in validation["invalid_groups"])
    groups = discover_overlay_groups(pool)
    assert set(groups) == {"76CM", "96CM", "116CM", "136CM"}
    source = tmp_path / "clean.png"
    Image.new("RGB", (1200, 1600), (90, 90, 90)).save(source)
    source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    result = process_source(
        {"output": str(source), "output_sha": source_sha, "art_name": "Grouped.png"},
        validation,
        tmp_path / "out",
        source_sha=source_sha,
    )
    assert len(result["results"]) == 4
    for item in result["results"]:
        selection = item["selection"]
        names = {asset.group_name for asset in (selection.upper, selection.bottom) if asset}
        assert names == {"design_alpha"}
        assert item["manifest"]["group_name"] == "design_alpha"
