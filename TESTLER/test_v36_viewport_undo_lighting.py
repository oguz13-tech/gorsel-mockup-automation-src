import os,sys
from pathlib import Path
from types import SimpleNamespace
import cv2
import numpy as np
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'MERKEZ'))
from PETEK_V3.viewport import Viewport
from PETEK_V3 import engine


def test_zoom_at_pointer_keeps_source_anchor():
    v=Viewport(1200,1600,725,695)
    anchor=(210,280); before=v.source(*anchor)
    v.zoom_at(3.,*anchor)
    assert np.allclose(before,v.source(*anchor),atol=1e-5)
    assert v.scale>v.fit_scale


def test_pan_move_100pct_and_fit_no_source_edits():
    v=Viewport(1200,1600,725,695)
    fit=v.fit_scale
    v.zoom_at(4,350,340)
    b=v.source(325,320)
    v.pan(15,-20)
    assert np.allclose(v.source(340,300),b,atol=1e-5)
    v.fit()
    assert v.scale==fit


def test_resize_keeps_visual_center_and_zoom_magnitude():
    v=Viewport(1200,1600,700,680)
    v.zoom_at(1.5,350,340)
    a=v.source(350,340)
    v.resize(760,740)
    assert np.linalg.norm(np.asarray(v.source(380,370))-a)<1.0


def test_original_protected_pixels_identical_all_lighting():
    h,w=400,520
    scene=np.full((h,w,3),(170,209,252),np.uint8)
    scene[:,w//2:]+=np.uint8([5,0,0]);scene[:,:w//4]-=np.uint8([20,15,10])
    q=np.float32([[40,40],[480,40],[480,355],[40,355]])
    mask=engine.polygon_mask(scene.shape,q)
    mask[120:315,90:100]=0
    art=np.full_like(scene,(45,92,152))
    for mode in ('natural','strong','off'):
        output,qa=engine.composite(scene,art,mask,q,lighting=mode)
        assert np.array_equal(output[mask==0],scene[mask==0])
        assert qa['source_pixels_unchanged']


def test_sunlight_transfer_has_geometric_direction():
    scene=np.full((250,400,3),170,np.uint8)
    scene[:,:200]=[170,210,249]
    q=np.float32([[20,20],[380,20],[380,225],[20,225]])
    mask=engine.polygon_mask(scene.shape,q)
    art=np.full_like(scene,(50,80,140))
    from PETEK_V3.realism import apply
    dst=apply(scene,art,mask,mode='natural')
    assert dst[120,90,2]>dst[120,315,2]+5
    assert not np.array_equal(dst,art)

@pytest.mark.skipif(sys.platform!='win32' and not os.environ.get('DISPLAY'),reason='display required')
def test_curve_point_control_z_and_zoom_click(tmp_path):
    import tkinter as tk
    from PETEK_V3.gui import MaskEditor
    from PETEK_V3.registry import Registry
    root=tk.Tk();root.geometry('840x640')
    try:
        e=MaskEditor(root,registry=Registry(tmp_path/'private'))
        e.scene=np.full((400,500,3),230,np.uint8)
        e.mask=np.full((400,500),255,np.uint8)
        e.quad=[[20,20],[480,20],[480,370],[20,370]]
        e.mode.set('top');e.refresh()
        e._button_zoom(2.5)
        pt=(190,50)
        px,py=e.view.screen(*pt)
        e.click(SimpleNamespace(x=px,y=py))
        assert e.curve==[[190,50]]
        e._keyboard_undo(SimpleNamespace(widget=e.canvas))
        assert e.curve==[]
        assert e.view.scale>e.view.fit_scale
    finally:
        root.destroy()
