# -*- coding: utf-8 -*-
"""Regression: standalone conversion/watermark outputs never clobber user data."""
import hashlib
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from PIL import Image

from SABLON_V2_MIMARI.tools_runner import (
    convert_images, watermark_images, convert_folder_to_png_recursive,
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_concurrent_convert_publishes_unique_outputs_and_preserves_sources():
    with tempfile.TemporaryDirectory() as td:
        src=Path(td)/"myphoto.png"
        Image.new("RGBA",(180,240),(20,190,110,155)).save(src)
        original=sha(src)
        def task(i):
            folder,files=convert_images([src],"JPG")
            assert folder.is_dir() and len(files)==1
            return files[0]
        with ThreadPoolExecutor(max_workers=6) as pool:
            outputs=list(pool.map(task,range(6)))
        assert len({p.name for p in outputs})==6
        assert all(p.is_file() for p in outputs)
        assert sha(src)==original
        before={p.name:sha(p) for p in outputs}
        again=task(6)
        assert again.name not in before
        assert {p.name:sha(p) for p in outputs}==before


def test_watermark_never_overwrites_prior_output():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        src=root/"product.png"
        logo=root/"logo.png"
        Image.new("RGBA",(180,240),(225,225,225,255)).save(src)
        Image.new("RGBA",(30,30),(255,0,0,155)).save(logo)
        input_hash=sha(src)
        out1,files1=watermark_images(logo,[src])
        previous_hash=sha(files1[0])
        out2,files2=watermark_images(logo,[src])
        assert files1[0]!=files2[0]
        assert sha(files1[0])==previous_hash
        assert sha(src)==input_hash


def test_recursive_converter_preserves_old_png_without_overwrite():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        src=root/"photos";src.mkdir()
        Image.new("RGB",(60,50),(10,20,30)).save(src/"a.jpg")
        old_src=sha(src/"a.jpg")
        first=convert_folder_to_png_recursive(src, runtime_root=root/"isolated")
        assert first["converted_count"]==1
        existing=Path(first["output_dir"])/"a.png"
        prev=sha(existing)
        second=convert_folder_to_png_recursive(src, runtime_root=root/"isolated")
        assert second["converted_count"]==0
        assert second["skipped_existing_count"]==1
        assert sha(existing)==prev and sha(src/"a.jpg")==old_src


def test_convert_disallows_template_pool_as_output_root(monkeypatch):
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        # Controlled test isolation via explicit env; no production paths.
        from SABLON_V2_MIMARI import tools_runner
        old=tools_runner.RUNTIME_ROOT
        try:
            tools_runner.RUNTIME_ROOT=root
            src=root/"2_SABLON_HAVUZU"/"01_Wifi_Kutusu"/"Wifi_Kutusu_005.png"
            src.parent.mkdir(parents=True)
            Image.new("RGB",(24,32)).save(src)
            old_bytes=sha(src)
            with pytest.raises(ValueError):
                convert_images([src],"JPG")
            assert sha(src)==old_bytes
        finally:
            tools_runner.RUNTIME_ROOT=old
