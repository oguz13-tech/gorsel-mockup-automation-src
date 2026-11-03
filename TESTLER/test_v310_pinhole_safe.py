"""PETEK wood-grain false-negative regression; approved profiles remain immutable."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'MERKEZ'))
import numpy as np
import cv2
from PETEK_V3 import engine

Q=[[20,20],[280,20],[280,200],[20,200]]

def synthetic():
    # ~white physical front, dark real slits, pale/midgray natural wood scratches.
    src=np.full((230,310,3),205,np.uint8)
    m=engine.polygon_mask(src.shape,np.asarray(Q,np.float32))
    for x in (70,125,190):
        cv2.rectangle(src,(x,47),(x+6,169),(20,20,20),-1)
        cv2.rectangle(m,(x,47),(x+6,169),0,-1)
    for x,y in [(95,80),(145,99),(225,120)]:
        cv2.rectangle(src,(x,y),(x+3,y+14),(177,177,177),-1)
        cv2.rectangle(m,(x,y),(x+3,y+14),0,-1)
    return src,m

def test_small_wood_scratches_covered_without_touching_slots():
    src,mask=synthetic();original=src.copy();saved=mask.copy()
    got,qa=engine.repair_wood_pinholes(src,mask,Q)
    assert qa['fixed_pixels']>=150,qa
    for x,y in [(95,80),(145,99),(225,120)]: assert got[y+4,x+2]==255
    for x in (70,125,190): assert np.all(got[47:170,x+3]==0)
    assert np.array_equal(src,original) and np.array_equal(mask,saved)
    assert np.array_equal(got[engine.polygon_mask(src.shape,np.asarray(Q,np.float32))==0],mask[engine.polygon_mask(src.shape,np.asarray(Q,np.float32))==0])

def test_short_actual_deep_hole_stays_protected():
    src,mask=synthetic()
    cv2.rectangle(src,(245,69),(250,89),(10,10,10),-1)
    cv2.rectangle(mask,(245,69),(250,89),0,-1)
    got,qa=engine.repair_wood_pinholes(src,mask,Q)
    assert np.all(got[69:90,245:251]==0),qa

def test_real_curved_openings_and_border_not_filled():
    src,mask=synthetic()
    # A real opening that touches the border must never be repaired.
    src[20:38,80:245]=20;mask[20:38,80:245]=0
    src[190:201,60:270]=20;mask[190:201,60:270]=0
    src[20:24,30:36]=175;mask[20:24,30:36]=0
    got,_=engine.repair_wood_pinholes(src,mask,Q)
    assert np.all(got[20:38,80:245]==0)
    assert np.all(got[190:201,60:270]==0)
    assert np.all(got[20:24,30:36]==0)

def test_declines_large_or_unconnected_unknown_areas():
    src,mask=synthetic()
    cv2.rectangle(mask,(209,77),(249,150),0,-1)
    result,_=engine.repair_wood_pinholes(src,mask,Q)
    assert np.all(result[77:151,209:250]==0)

def test_actual_photo_ventilation_remains_protected_when_repaired():
    path=Path(__file__).resolve().parents[1]/'ORNEK_PETEK_MOCKUPLARI'/'Gemini_Generated_Image_hclufkhclufkhclu.jpeg'
    if not path.exists():
        # fixtures vary across archives; bundled base photo always available
        from pytest import skip
        skip('sample optional')
    scene=engine.read_bgr(path)
    quad=[[248,712],[1319,706],[1323,1673],[240,1673]]
    original=scene.copy()
    mask,stats=engine.auto_mask_candidate(scene,quad)
    assert stats['repaired_wood_pinhole_pixels']>1000
    # Keep every true long connected opening from the older draft.
    from unittest.mock import patch
    with patch.object(engine,'repair_wood_pinholes',side_effect=lambda s,m,q:(m,{'fixed_pixels':0})):
        previous,_=engine.auto_mask_candidate(scene,quad)
    n,lab,stats_old,_=cv2.connectedComponentsWithStats((previous==0).astype(np.uint8),8)
    long_vents=np.zeros(previous.shape,bool)
    for i in range(1,n):
        x,y,w,h,area=map(int,stats_old[i])
        if 260<h<780 and w<38 and 300<x<1290 and 795<y<1000:
            long_vents|=(lab==i)
    assert np.count_nonzero(long_vents)>30000
    assert np.array_equal(mask[long_vents],previous[long_vents])
    assert np.count_nonzero(mask>previous)>1000
    assert np.array_equal(scene,original)

def test_gui_cleanup_does_not_overwrite_approved_profile(tmp_path, monkeypatch):
    import os
    import pytest
    if os.name!='nt' and not os.environ.get('DISPLAY'):
        pytest.skip('Requires real desktop or Xvfb')
    import tkinter as tk
    from PETEK_V3.registry import Registry
    from PETEK_V3.gui import MaskEditor, messagebox
    src,mask=synthetic()
    image=tmp_path/'template.png'
    assert cv2.imwrite(str(image),src)
    registry=Registry(tmp_path/'private')
    registry.save('original',image,Q,mask,1.1)
    registry.approve('original','TEST','I_VISUALLY_CHECKED_VENTS_ARCHES_FLOOR')
    original_profile, original_mask=registry.get('original')
    alerts=[]
    monkeypatch.setattr(messagebox,'showerror',lambda *a,**kw:alerts.append(a))
    root=tk.Tk();root.withdraw()
    try:
        e=MaskEditor(root,registry)
        e.scene=src.copy();e.source=image;e.quad=[list(p) for p in Q]
        e.mask=mask.copy();e.uid.set('original');e._loaded_approved=True
        e.repair_small_gaps()
        assert not alerts,alerts
        assert e.uid.get()!='original'  # Draft fork, no approved edit
        assert int(np.count_nonzero(e.mask!=mask))>0
        check_prof,check_mask=registry.get('original')
        assert check_prof['mask_sha']==original_profile['mask_sha']
        assert np.array_equal(check_mask,original_mask)
        e.undo()
        assert np.array_equal(e.mask,mask)
        assert np.array_equal(e.scene,src)
        e.window.destroy()
    finally:root.destroy()
