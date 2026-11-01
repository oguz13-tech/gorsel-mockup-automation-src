"""Bridge module exposing PETEK V4.0 Cut-and-Paste + Zero-Blur Cover engine inside SABLON_V2_MIMARI."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MERKEZ_DIR = ROOT / "MERKEZ"
if str(MERKEZ_DIR) not in sys.path:
    sys.path.insert(0, str(MERKEZ_DIR))

from PETEK_V3 import engine as petek_engine
from PETEK_V3 import curves as petek_curves
from PETEK_V3 import brush_tools as petek_brush
from PETEK_V3.cutout_paste import (
    extract_cutout_overlay_rgba,
    paste_cutout_overlay,
    render_with_cutout_paste,
    save_cutout_overlay_png,
)

__all__ = [
    "petek_engine",
    "petek_curves",
    "petek_brush",
    "extract_cutout_overlay_rgba",
    "paste_cutout_overlay",
    "render_with_cutout_paste",
    "save_cutout_overlay_png",
]
