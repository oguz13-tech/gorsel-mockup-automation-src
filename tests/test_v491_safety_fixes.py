"""Targeted regression for user-facing V4.9.1 fixes; synthetic tmp folders only."""
from pathlib import Path
from unittest.mock import patch
import pytest
from PIL import Image
from SABLON_V2_MIMARI.orientation_sort_v489 import sort_folder


def image(path, size=(200, 100)):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new('RGB', size, 'magenta').save(path)


def test_no_clobber_hardlink_unsupported_and_filename_collision(tmp_path):
    source, output = tmp_path/'source', tmp_path/'out'
    image(source/'a.png')
    existing = output/'YATAY'/'a.png'
    existing.parent.mkdir(parents=True)
    existing.write_bytes(b'IRREPLACEABLE ORIGINAL')
    with patch('SABLON_V2_MIMARI.orientation_sort_v489.os.link', side_effect=OSError('hardlinks not supported')):
        result = sort_folder(source, output)
    assert existing.read_bytes() == b'IRREPLACEABLE ORIGINAL'
    assert (output/'YATAY'/'a__002.png').read_bytes() == (source/'a.png').read_bytes()
    assert result.copied == 1 and not result.errors
    assert not list(output.rglob('*.part'))


def test_failed_output_creation_does_not_remove_original_file(tmp_path):
    source, output = tmp_path/'source', tmp_path/'out'
    image(source/'a.png')
    out = output/'YATAY'/'a.png'
    out.parent.mkdir(parents=True)
    out.write_bytes(b'KEEP THIS')
    # Ensure only a pre-existing file remains, including under errors.
    with patch('SABLON_V2_MIMARI.orientation_sort_v489.os.link', side_effect=OSError('not supported')):
        with patch('SABLON_V2_MIMARI.orientation_sort_v489._sha256', side_effect=OSError('disk unreadable')):
            result = sort_folder(source, output)
    assert out.read_bytes() == b'KEEP THIS'
    assert len(result.errors) == 1 and result.report_path.exists()


def test_decompression_bomb_is_isolated_csv_still_written(tmp_path, monkeypatch):
    source, output = tmp_path/'source', tmp_path/'out'
    image(source/'a_bad.png', (201, 101))
    image(source/'z_good.png', (10, 10))
    # Real Pillow error, not mocked exception from our own code.
    old = Image.MAX_IMAGE_PIXELS
    monkeypatch.setattr(Image, 'MAX_IMAGE_PIXELS', 100)
    result = sort_folder(source, output)
    assert result.source_count == 2
    assert result.copied == 1
    assert len(result.errors) == 1
    assert result.report_path.exists()
    assert (output/'KARE'/'z_good.png').exists()
    assert 'DecompressionBombError' in result.report_path.read_text('utf-8-sig')
    monkeypatch.setattr(Image, 'MAX_IMAGE_PIXELS', old)


def test_move_forbidden_in_protected_root_even_when_target_elsewhere(tmp_path):
    protected = tmp_path/'2_SABLON_HAVUZU'
    image(protected/'a.png')
    with pytest.raises(ValueError):
        sort_folder(protected, tmp_path/'dest', move=True, protected_roots=(protected,))
    assert (protected/'a.png').exists()


def test_report_unique_when_run_twice(tmp_path):
    source, output = tmp_path/'source', tmp_path/'output'
    image(source/'a.png')
    first = sort_folder(source, output)
    second = sort_folder(source, output)
    assert first.report_path != second.report_path
    assert first.report_path.is_file() and second.report_path.is_file()
    assert (output/'YATAY'/'a.png').is_file()
    assert (output/'YATAY'/'a__002.png').is_file()


def test_callback_error_only_skips_affected_file(tmp_path):
    source, output = tmp_path/'source', tmp_path/'out'
    image(source/'a.png')
    image(source/'b.png')
    def progress(i,n,name):
        if i == 1:
            raise RuntimeError('UI lost')
    result = sort_folder(source, output, progress=progress)
    assert len(result.errors) == 1
    assert result.copied == 1
    assert result.report_path.exists()
