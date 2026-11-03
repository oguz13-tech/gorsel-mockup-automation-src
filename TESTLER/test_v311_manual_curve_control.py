"""PETEK V3.11: user's edge-join / dense point control / immutable mask tests."""
from pathlib import Path
import os
import sys
from types import SimpleNamespace
import cv2
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'MERKEZ'))
from PETEK_V3 import curves, engine


def _panel():
    shape = (400, 550)
    quad = [[45, 46], [500, 50], [485, 350], [57, 340]]
    return shape,quad,engine.polygon_mask(shape,np.asarray(quad,np.float32))


def test_join_last_tight_side_gap_with_original_user_y():
    shape, quad, mask = _panel()
    # User stopped 14px short of left edge and 11px short of right edge.
    manual = [[60, 74], [145, 94], [260, 115], [365, 99], [476, 74]]
    anchored = curves.joined_endpoints(manual,quad)
    assert len(anchored)==len(manual)+2
    assert anchored[0,0]<60 and anchored[-1,0]>476
    assert anchored[0,1]==74 and anchored[-1,1]==74
    xs,ys=curves.interpolate(manual,quad)
    # User points EXACTLY preserved; unforced V3.7 smoothing could drift.
    for x,y in manual:
        assert float(ys[list(xs).index(x)]) == float(y)
    result=curves.apply(mask,quad,top=manual)
    # Old V3.7 left an uncut dark-zone strip between side and first point.
    assert result[50,50]==0
    assert result[96,245]==0
    assert result[200,245]==255
    assert np.array_equal(result[mask==0],mask[mask==0])


def test_no_auto_mirrored_bottom_or_invented_midpoints():
    shape,q,mask = _panel()
    top=[[60,78],[270,115],[476,80]]
    result=curves.apply(mask,q,top=top)
    # Bottom wood is still printable unless manually protected by bottom points.
    assert result[320,270]==255
    xs,ys=curves.interpolate(top,q)
    assert 90<float(ys[270-xs[0]])<116
    assert len(xs)>300


def test_user_can_pack_points_two_pixels_apart_without_curve_overshoot():
    pts=[[47,64],[60,65],[62,71],[65,59],[75,70],[130,104],[250,125],[470,79],[497,63]]
    x,y=curves.interpolate(pts)
    assert np.isfinite(y).all()
    # Linear shape is bounded by the two ACTUAL neighboring user points.
    for a,b in zip(curves.normalized(pts)[:-1],curves.normalized(pts)[1:]):
        local=y[(x>=a[0])&(x<=b[0])]
        assert local.min()>=min(a[1],b[1])
        assert local.max()<=max(a[1],b[1])
    assert y[list(x).index(62)]==71
    assert y[list(x).index(65)]==59


def test_incomplete_far_endpoints_not_silently_extended():
    shape,q,base=_panel()
    unfinished=[[138,100],[260,125],[350,105]]
    with pytest.raises(engine.MaskError,match='yeterince'):
        curves.apply(base,q,top=unfinished)
    _,approx=curves.interpolate(unfinished,q,require_ends=False)
    assert len(approx)>100
    # Partial in-progress mark does not change a previously editable base.
    partial=curves.apply(base,q,top=[[65,80],[260,110]],require_ends=False)
    np.testing.assert_array_equal(partial,base)


def test_two_boundaries_manual_and_quad_clip_preserves_all_external_pixels():
    shape,q,base=_panel()
    x_list=[80,135,215,310,450]
    for x in x_list:
        cv2.rectangle(base,(x,150),(x+7,295),0,-1)
    top=[[65,71],[260,114],[480,75]]
    bottom=[[75,331],[260,315],[476,332]]
    got=curves.apply(base,q,top,bottom)
    assert got[49,270]==0 and got[380,270]==0
    assert got[230,270]==255
    for x in x_list:
        assert np.all(got[170:280,x+3]==0)
    assert not np.any(got[engine.polygon_mask(shape,np.asarray(q,np.float32))==0])


@pytest.mark.skipif(os.name!='nt' and not os.environ.get('DISPLAY'), reason='Requires display')
def test_gui_shift_add_delete_undo_close_points_and_viewport(tmp_path,monkeypatch):
    import tkinter as tk
    from PETEK_V3.gui import MaskEditor, messagebox
    warnings=[]
    monkeypatch.setattr(messagebox,'showerror',lambda *args,**kw:warnings.append(args))
    root=tk.Tk();root.geometry('1150x860')
    e=None
    try:
        photo=tmp_path/'source.png'
        scene=np.full((400,550,3),235,np.uint8)
        assert cv2.imwrite(str(photo),scene)
        e=MaskEditor(root)
        e.load(photo)
        shape,q,mask=_panel()
        e.quad=q;e.mask=mask.copy();e.uid.set('PETEK311_TEST')
        e.mode.set('top')
        def put(x,y,*,shift=0):
            sx,sy=e.view.screen(x,y)
            e.click(SimpleNamespace(x=sx,y=sy,state=shift));e._end_paint()
        put(60,74);put(260,115);put(476,74)
        assert len(e.curve)==3
        # A closely placed point, <7 screen pixels, forced by SHIFT must be ADDED.
        put(263,118,shift=1)
        assert len(e.curve)==4
        # Exact same source X cannot create an invisible duplicate: replaces Y.
        put(263,121,shift=1)
        assert len(e.curve)==4
        assert any(x==263 and y==121 for x,y in e.curve)
        e.undo()
        assert any(x==263 and y==118 for x,y in e.curve)
        e.undo()
        assert len(e.curve)==3
        e.finish_curve()
        assert not warnings,warnings
        assert e.curve_base is not None
        e.mode.set('top')
        # Zoom before editing: event and actual annotations stay in source pixels.
        sx,sy=e.view.screen(260,115)
        e.view.zoom_at(2,sx,sy);e.refresh()
        px,py=e.view.screen(260,115)
        e.click(SimpleNamespace(x=px,y=py,state=0))
        px,py=e.view.screen(265,125)
        e.drag(SimpleNamespace(x=px,y=py));e._end_paint()
        assert any(abs(y-125)<1 for x,y in e.curve)
        e.undo()
        assert any(abs(y-115)<1 for x,y in e.curve)
        # Select then Delete, then Ctrl+Z returns point and identical mask.
        px,py=e.view.screen(260,115)
        e.click(SimpleNamespace(x=px,y=py,state=0));e._end_paint()
        original=e.mask.copy()
        out=e.delete_curve_point()
        assert out=='break' and len(e.curve)==2
        e.undo()
        assert len(e.curve)==3
        np.testing.assert_array_equal(e.mask,original)
        assert not warnings,warnings
    finally:
        if e is not None:e.window.destroy()
        root.destroy()
