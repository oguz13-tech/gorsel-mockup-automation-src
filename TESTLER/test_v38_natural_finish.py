"""V3.8: photograph-derived shadows and user-preview-only edge trials."""
from pathlib import Path
import sys
import numpy as np
import cv2
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'MERKEZ'))
from PETEK_V3 import engine, realism
from PETEK_V3.finish import white_border


def make_sample():
    h,w=540,720
    src=np.full((h,w,3),(219,226,231),np.uint8)
    quad=np.float32([[100,100],[620,98],[610,440],[105,440]])
    poly=engine.polygon_mask(src.shape,quad)
    mask=poly.copy()
    for xx in range(132,610,29):
        cv2.rectangle(mask,(xx,165),(xx+8,400),0,-1)
        cv2.rectangle(src,(xx,165),(xx+8,400),(35,37,38),-1)
    # White source sunlight from top-left, gentle directional shading.
    yy,xx=np.indices((h,w))
    shade=np.clip(1-.21*(xx/float(w))+.07*(1-yy/h),.75,1.05)
    src=np.uint8(np.clip(src.astype(np.float32)*shade[:,:,None],0,255))
    art=np.zeros((240,700,3),np.uint8)
    art[:,:,0]=64
    art[:,:,1]=cv2.resize(np.linspace(50,210,700,dtype=np.uint8)[None,:],(700,240))
    art[:,:,2]=146
    return src,quad,mask,art


def test_source_protection_every_option():
    src,q,mask,art=make_sample()
    for frame in (0,5,10):
        for mode in ('natural','strong','off'):
            out,qa=engine.render(src,art,q,mask,1.1163,frame_mm=frame,
                                 lighting=mode,marketplace=False)
            assert qa['source_pixels_unchanged']
            assert np.array_equal(out[mask==0],src[mask==0])
            assert out.shape==src.shape


def test_border_is_optional_monotonic_and_mask_clipped():
    src,q,mask,art=make_sample()
    page=engine.warp_artwork(art,q,src.shape,1.1163)
    base=white_border(page,q,mask,frame_mm=0)
    assert np.array_equal(base,page)
    thin=white_border(page,q,mask,frame_mm=5)
    thick=white_border(page,q,mask,frame_mm=10)
    assert np.array_equal(thin[mask==0],page[mask==0])
    assert np.array_equal(thick[mask==0],page[mask==0])
    assert np.count_nonzero(np.any(thin!=base,axis=2))>100
    assert np.count_nonzero(np.any(thick!=base,axis=2))>np.count_nonzero(np.any(thin!=base,axis=2))


def test_nominal_mm_are_not_false_calibration():
    src,q,mask,art=make_sample()
    a,_=engine.render(src,art,q,mask,1.1163,frame_mm=5,marketplace=False)
    b,qa=engine.render(src,art,q,mask,1.1163,frame_mm=5,
                        panel_width_cm=90,marketplace=False)
    assert qa['frame_width_nominal'] is False
    assert not np.array_equal(a,b)
    with pytest.raises(ValueError):
        engine.render(src,art,q,mask,1.1163,frame_mm=7,marketplace=False)


def test_sunlight_darkens_shaded_wood_without_fake_glare():
    h,w=320,420
    scene=np.full((h,w,3),(205,210,225),np.uint8)
    scene[:,:w//2]=[235,239,242]
    art=np.full_like(scene,(90,105,125))
    mask=np.full((h,w),255,np.uint8)
    out=realism.apply(scene,art,mask,'natural')
    # Source sunlight should be measurable, but bounded; prior code allowed 47% boost.
    a=out[150,100].mean();b=out[150,350].mean()
    assert a>b
    assert abs(a-b)>3
    assert a<165
    assert out[150,100].mean()<art[150,100].mean()*1.12
    assert np.array_equal(realism.apply(scene,art,mask,'off'),art)


def test_overscan_crops_artwork_only_and_does_not_rewrite_source_mask():
    src,q,mask,art=make_sample()
    old=mask.copy();scene=src.copy()
    a,_=engine.render(src,art,q,mask,1.1163,overscan=0,marketplace=False)
    b,_=engine.render(src,art,q,mask,1.1163,overscan=.012,marketplace=False)
    assert not np.array_equal(a[mask>200],b[mask>200])
    assert np.array_equal(src,scene) and np.array_equal(mask,old)
    assert np.array_equal(b[mask==0],src[mask==0])
    with pytest.raises(engine.MaskError):
        engine.render(src,art,q,mask,1.1163,overscan=.08,marketplace=False)


def test_soft_edge_blends_inside_only():
    src,q,mask,art=make_sample()
    page=engine.warp_artwork(art,q,src.shape,1.1163)
    raw,_=engine.composite(src,page,mask,q,lighting='off',edge_feather_px=0)
    smooth,_=engine.composite(src,page,mask,q,lighting='off',edge_feather_px=2.)
    assert np.array_equal(raw[mask==0],src[mask==0])
    assert np.array_equal(smooth[mask==0],src[mask==0])
    assert np.any(raw[mask>0]!=smooth[mask>0])
    # Deep inside face must remain identical despite edge treatment.
    d=cv2.distanceTransform(np.uint8(mask>0),cv2.DIST_L2,3)
    assert np.array_equal(raw[d>5],smooth[d>5])


def test_4way_gui_ab_is_preview_only(monkeypatch,tmp_path):
    import os
    if not os.environ.get('DISPLAY'):
        pytest.skip('needs virtual display')
    import tkinter as tk
    from PETEK_V3.gui import MaskEditor
    from PETEK_V3 import gui
    from PETEK_V3.registry import Registry
    src,q,mask,art=make_sample()
    pic=tmp_path/'DESEN.png'
    assert cv2.imwrite(str(pic),art)
    monkeypatch.setattr(gui.filedialog,'askopenfilename',lambda **kwargs: str(pic))
    errors=[]
    monkeypatch.setattr(gui.messagebox,'showerror',lambda *a,**kw: errors.append(a))
    root=tk.Tk()
    root.withdraw()
    editor=MaskEditor(root,registry=Registry(root=tmp_path/'private'))
    editor.scene=src.copy();editor.mask=mask.copy();editor.quad=q.tolist()
    scene_before=editor.scene.copy();mask_before=editor.mask.copy()
    editor.preview_edge_variants()
    assert not errors,errors
    windows=[w for w in editor.window.winfo_children() if isinstance(w,tk.Toplevel)]
    assert any('4 Kenar Seçeneği' in w.title() for w in windows)
    assert np.array_equal(editor.scene,scene_before)
    assert np.array_equal(editor.mask,mask_before)
    for w in windows:
        w.destroy()
    root.destroy()
