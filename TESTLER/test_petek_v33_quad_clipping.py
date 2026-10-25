"""V3.3 regression: changing the four corners cannot leave an invalid mask.

No user files; all images and profiles live in pytest temporary folders.
"""
from pathlib import Path
import os
import sys
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'MERKEZ'))
from PETEK_V3 import engine
from PETEK_V3.registry import Registry


def sample():
    scene=np.full((480,640,3),(154,167,177),np.uint8)
    original=[[50,70],[580,67],[585,425],[53,440]]
    closer=[[80,75],[560,75],[560,400],[80,410]]
    mask=engine.polygon_mask(scene.shape,engine.validated_quad(original,scene.shape))
    for x in range(150,510,48):
        mask[180:365,x:x+7]=0  # original narrow vent recesses must remain protected
    return scene,original,closer,mask


def test_clip_reduces_leakage_without_source_mutation():
    scene,old,quad,mask=sample()
    raw=scene.copy();previous=mask.copy()
    with pytest.raises(engine.MaskError, match='panel disina tasiyor'):
        engine.mask_check(mask,scene,quad)
    clipped, removed=engine.clip_mask_to_panel(mask,scene,quad)
    assert removed>5000
    assert engine.count_outside_panel(clipped,scene,quad)==0
    assert np.array_equal(scene,raw)
    assert np.array_equal(mask,previous)
    # Clip must never invent printable pixels inside a widened quad.
    assert np.all(clipped <= previous)
    assert engine.mask_check(clipped,scene,quad)['printable_fraction']>0


def test_clip_is_idempotent_and_preserves_original_vents():
    scene,old,quad,mask=sample()
    mask[190:370,140:149]=0   # protected vent interior
    clipped,n=engine.clip_mask_to_panel(mask,scene,quad)
    again,count=engine.clip_mask_to_panel(clipped,scene,quad)
    assert n>0 and count==0
    np.testing.assert_array_equal(clipped,again)
    assert np.count_nonzero(clipped[190:370,140:149])==0


def test_mask_check_remains_strict_for_persisted_profile(tmp_path):
    scene,old,quad,mask=sample()
    image=tmp_path/'source.png'
    ok,data=cv2.imencode('.png',scene)
    assert ok
    image.write_bytes(data.tobytes())
    registry=Registry(tmp_path/'petek_private')
    with pytest.raises(engine.MaskError,match='panel disina tasiyor'):
        registry.save('Petek001',image,quad,mask,1.1)
    assert not list(registry.profiles.glob('*.json'))


def test_gui_changed_corner_auto_clips_and_can_undo(tmp_path):
    if sys.platform != 'win32' and not os.environ.get('DISPLAY'):
        pytest.skip('Tk display requires Windows or xvfb-run')
    import tkinter as tk
    from PETEK_V3.gui import MaskEditor
    scene,old,quad,mask=sample()
    root=tk.Tk();root.geometry('350x250')
    try:
        e=MaskEditor(root,registry=Registry(tmp_path/'private'))
        e.scene=scene.copy();e.mask=mask.copy();e.scale=1.0
        e.quad=[];e.mode.set('corners')
        e._ensure_view()
        for x,y in quad:
            x_screen,y_screen=e.view.screen(x,y)
            e.click(SimpleNamespace(x=x_screen,y=y_screen))
        assert engine.count_outside_panel(e.mask,scene,e.quad)==0
        assert len(e.undo_stack)==1
        assert e.confirm.get() is False
        assert 'taşan' in e.status.get()
        np.testing.assert_array_equal(e.undo_stack[-1],mask)
        e.undo()
        assert engine.count_outside_panel(e.mask,scene,quad)>0
        e.clean_outside_mask()
        assert engine.count_outside_panel(e.mask,scene,quad)==0
        assert 'temizlendi' in e.status.get()
    finally:
        root.destroy()


def test_curve_cleanup_is_safe_after_corner_update(tmp_path):
    if sys.platform != 'win32' and not os.environ.get('DISPLAY'):
        pytest.skip('Tk display requires Windows or xvfb-run')
    import tkinter as tk
    from PETEK_V3.gui import MaskEditor
    scene,old,quad,mask=sample()
    root=tk.Tk();root.geometry('350x250')
    try:
        editor=MaskEditor(root,registry=Registry(tmp_path/'private'))
        editor.scene=scene.copy();editor.mask=mask.copy()
        editor.quad=quad
        editor.mode.set('top')
        editor.curve=[[90,115],[320,135],[540,115]]
        editor.finish_curve()
        assert engine.count_outside_panel(editor.mask,scene,quad)==0
        assert editor.mode.get()=='protect'
    finally:
        root.destroy()
