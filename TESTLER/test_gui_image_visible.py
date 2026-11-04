"""Regression: source image must be VISUALLY mapped, not merely decoded.

GUI test requires an interactive display (Windows desktop or Xvfb on Linux).
It uses only synthetic pixels and a temporary local PETEK registry.
"""
from __future__ import annotations
import os
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

SRC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SRC / "MERKEZ"))
from PETEK_V3.registry import Registry


def test_photo_canvas_visible_and_inside_screen(tmp_path):
    """Photo must be visible in right pane at laptop resolution."""
    if sys.platform != "win32" and not os.environ.get("DISPLAY"):
        pytest.skip("GUI display unavailable; run with xvfb-run")
    import tkinter as tk
    from PETEK_V3.gui import MaskEditor

    h, w = 720, 540
    photo = np.zeros((h, w, 3), dtype=np.uint8)
    photo[:] = (170, 180, 190)
    cv2.rectangle(photo, (45, 85), (495, 680), (245, 240, 235), -1)
    for x in range(75, 480, 27):
        cv2.rectangle(photo, (x, 185), (x + 7, 515), (35, 38, 40), -1)
    image_file = tmp_path / 'PetekOrnek.png'
    success, buffer = cv2.imencode('.png', photo)
    assert success
    image_file.write_bytes(buffer.tobytes())

    main = tk.Tk()
    main.geometry('400x260')
    try:
        editor = MaskEditor(main, registry=Registry(tmp_path / 'petek_state'))
        editor.load(image_file)
        main.update_idletasks()
        main.update()
        view = editor.canvas
        assert editor.scene is not None
        assert editor.photo is not None
        assert view.winfo_viewable(), 'Canvas is not mapped to visible UI'
        assert view.master is not editor.window, (
            'Canvas must be an actual child of layout frame, never obscured behind sibling')
        assert view.find_withtag('all'), 'No source pixels drawn to canvas'
        assert editor.draw_dims[0] <= view.winfo_width()
        assert editor.draw_dims[1] <= view.winfo_height()
        assert view.winfo_rootx() + editor.draw_dims[0] <= main.winfo_screenwidth()
        assert view.winfo_rooty() + editor.draw_dims[1] <= main.winfo_screenheight()
        assert editor.tools_scroll.winfo_viewable()
    finally:
        main.destroy()
