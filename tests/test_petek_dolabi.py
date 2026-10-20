"""Isolated PETEK generator acceptance: deterministic, 13 slots, no source mutation."""
import importlib.util
from pathlib import Path
import sys
import cv2
import numpy as np
import pytest

path=Path(__file__).resolve().parents[1]/"SABLON_V2_MIMARI/core/petek_dolabi.py"
spec=importlib.util.spec_from_file_location("petek_dolabi",path)
p=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=p
spec.loader.exec_module(p)

@pytest.fixture
def scene():
    return np.full((650,850,3),(161,174,186),dtype=np.uint8)

@pytest.fixture
def art():
    y,x=np.mgrid[0:250,0:400]
    return np.stack([x%256,y%256,(x//3+y)%256],axis=-1).astype("uint8")

@pytest.fixture
def quad():
    return [[125,120],[725,95],[740,520],[113,550]]

def test_symmetric_13():
    geometry=p.normalized_slot_geometry(p.SlotSpec())
    assert len(geometry)==13
    gaps=np.diff([x for x,_,_ in geometry])
    assert np.ptp(gaps)<1e-10
    assert abs(geometry[0][0]-(1-geometry[-1][0]))<1e-12

def test_length_variation_is_subtle():
    lengths=[b-a for _,a,b in p.normalized_slot_geometry(p.SlotSpec(length_variation=.02))]
    assert np.ptp(lengths)<.03
    assert np.allclose(lengths,lengths[::-1])

def test_outside_panel_unchanged(scene,art,quad):
    out,d=p.render_front(art,scene,quad,return_debug=True)
    assert np.array_equal(out[20,20],scene[20,20])
    assert np.array_equal(out[610,780],scene[610,780])
    assert not np.array_equal(out[300,300],scene[300,300])
    assert d["slot_count"]==13
    n,_=cv2.connectedComponents((d["flat_slot_mask"]>.5).astype("uint8"))
    assert n-1==13

def test_source_stripes_cannot_bleed(scene,art,quad):
    stripe_scene=scene.copy()
    for x in range(190,700,25):
        cv2.line(stripe_scene,(x,180),(x,450),(0,0,0),5)
    out1=p.render_front(art,scene,quad)
    out2=p.render_front(art,stripe_scene,quad)
    assert np.array_equal(out1[250:400,240:660],out2[250:400,240:660])

def test_same_input_same_output(scene,art,quad):
    assert np.array_equal(p.render_front(art,scene,quad),p.render_front(art,scene,quad))

def test_curved_projection(scene,art,quad):
    out,d=p.render_front(art,scene,quad,edge_midpoints={"top":[425,130],"bottom":[425,570]},return_debug=True)
    assert out.shape==scene.shape and d["slot_count"]==13

@pytest.mark.parametrize("bad",[
    {"side_margin":.9},{"bottom_curve":.4},{"slot_width":0.}
])
def test_invalid_spec_rejected(scene,art,quad,bad):
    with pytest.raises(p.PetekGeometryError):
        p.render_front(art,scene,quad,spec=p.SlotSpec(**bad))

def test_out_of_bounds_rejected(scene,art):
    with pytest.raises(p.PetekGeometryError):
        p.render_front(art,scene,[[1200,0],[1300,0],[1300,20],[1200,20]])

def test_unsupported_curve_rejected(scene,art,quad):
    with pytest.raises(p.PetekGeometryError):
        p.render_front(art,scene,quad,edge_midpoints={"top":[0,0],"bottom":[0,0]})
