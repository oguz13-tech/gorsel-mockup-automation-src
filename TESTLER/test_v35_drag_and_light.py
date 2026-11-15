import os,sys
from pathlib import Path
from types import SimpleNamespace
import numpy as np,cv2,pytest
R=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(R/'MERKEZ'))
from quad_interaction import begin,target
from PETEK_V3 import engine
from PETEK_V3.realism import apply
Q=np.float32([[60,70],[420,68],[425,335],[64,341]])

def test_corners():
 for i,(x,y) in enumerate(Q):
  g=begin(Q,float(x),float(y),(500,420));assert g.handle==('corner',i)
  move=g.at(x+5,y+6)
  np.testing.assert_allclose(move[i],Q[i]+[5,6]);engine.validated_quad(move,(420,500))

def test_edges():
 x,y=(Q[0]+Q[1])/2
 g=begin(Q,float(x),float(y),(500,420));assert g.handle==('edge',0)
 a=g.at(x,y+8)
 np.testing.assert_allclose(a[:2],Q[:2]+[0,8]);np.testing.assert_allclose(a[2:],Q[2:])

def test_whole_quad_moves_and_bounds():
 g=begin(Q,200,200,(500,420));assert g.handle==('inside',-1)
 r=g.at(240,215);np.testing.assert_allclose(r-Q,np.tile([40,15],(4,1)))
 clipped=g.at(10000,10000);assert clipped[:,0].max()<=499 and clipped[:,1].max()<=419
 assert begin(Q,0,0,(500,420)) is None

def test_photo_light_and_strict_preservation():
 scene=np.full((420,500,3),235,np.uint8)
 scene[100:250,70:200]=180
 for x in range(100,390,40):cv2.rectangle(scene,(x,140),(x+7,315),(28,28,28),-1)
 mask=engine.polygon_mask(scene.shape,Q)
 for x in range(100,390,40):mask[140:316,x:x+8]=0
 art=np.full_like(scene,(45,96,160))
 off,_=engine.composite(scene,art,mask,Q,lighting='off')
 bright,_=engine.composite(scene,art,mask,Q,lighting='strong')
 assert np.array_equal(bright[mask==0],scene[mask==0])
 assert np.mean(np.abs(bright[mask>0].astype(float)-off[mask>0].astype(float)))>2

def test_mode_off_is_exact_projected_art():
 scene=np.full((300,400,3),180,np.uint8)
 art=np.full_like(scene,(33,55,99));mask=np.full((300,400),255,np.uint8)
 assert np.array_equal(apply(scene,art,mask,'off'),art)

@pytest.mark.skipif(sys.platform!='win32' and not os.environ.get('DISPLAY'),reason='GUI display unavailable')
def test_gui_drag_recomputes_draft_and_undo(tmp_path):
 import tkinter as tk
 from PETEK_V3.gui import MaskEditor
 from PETEK_V3.registry import Registry
 root=tk.Tk()
 try:
  edit=MaskEditor(root,registry=Registry(tmp_path/'local'))
  image=np.full((420,500,3),230,np.uint8)
  for x in range(100,390,40):cv2.rectangle(image,(x,145),(x+8,290),(35,35,35),-1)
  edit.scene=image;edit.quad=Q.tolist();edit.mask=engine.polygon_mask(image.shape,Q)
  edit.mode.set('adjust');edit.scale=1.
  oldquad=np.array(edit.quad).copy()
  edit.click(SimpleNamespace(x=60,y=70));edit.drag(SimpleNamespace(x=73,y=79));edit._end_paint()
  assert edit.quad[0]!=oldquad[0].tolist()
  assert not engine.count_outside_panel(edit.mask,image,edit.quad)
  edit.undo();np.testing.assert_allclose(edit.quad,oldquad)
 finally:root.destroy()
