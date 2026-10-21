from pathlib import Path
import sys
from types import SimpleNamespace
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'MERKEZ'))
from PETEK_V3.gui import MaskEditor
from PETEK_V3 import engine

class Var:
    def __init__(self,v):self.v=v
    def get(self):return self.v
    def set(self,v):self.v=v

class Canvas:
    def __init__(self):self.items=[]
    def delete(self,*a):self.items=[]
    def create_oval(self,*a,**kw):self.items.append((a,kw))
    def create_text(self,*a,**kw):self.items.append((a,kw))

def editor():
    e=MaskEditor.__new__(MaskEditor)
    e.scene=np.full((120,160,3),(70,150,230),np.uint8)
    e.mask=np.zeros((120,160),np.uint8)
    e.quad=[[10,10],[150,10],[150,110],[10,110]]
    e.brush=Var(18);e.mode=Var('wood');e.status=Var('');e.confirm=Var(False)
    e.curve_base=None;e.undo_stack=[];e.view=None;e.scale=1;e.canvas=Canvas()
    e._next_version=lambda:None;e.refresh=lambda:None
    return e

def test_fast_stroke_solid_white_and_quad_clip():
    e=editor()
    e._paint(SimpleNamespace(x=15,y=60),first=True)
    e._paint(SimpleNamespace(x=145,y=60))
    assert np.all(e.mask[60,15:146]==255)
    assert np.all(e.mask[:10]==0) and np.all(e.mask[:,:10]==0)
    white=np.full_like(e.scene,255)
    out,_=engine.composite(e.scene,white,e.mask,e.quad,preserve_shading=False,edge_feather_px=1.4)
    assert np.all(out[60,20:140]==255)
    assert np.array_equal(out[e.mask==0],e.scene[e.mask==0])

def test_brush_cursor_tracks_size_and_zoom():
    e=editor();e._brush_cursor(SimpleNamespace(x=50,y=50))
    assert e.canvas.items[0][0]==(41,41,59,59)
    e.brush.set(42);e.scale=2;e._brush_cursor()
    assert e.canvas.items[0][0]==(8,8,92,92)

def test_exit_reentry_does_not_bridge_protected_region():
    e=editor();e._paint(SimpleNamespace(x=20,y=20),first=True)
    e._paint(SimpleNamespace(x=0,y=0))
    e._paint(SimpleNamespace(x=140,y=100))
    assert e.mask[60,80]==0
