"""Regression: operator A/B comparison is optional; approved mask/geometry gates remain.

Never touches the user's production workspace or changes an approved mask.
"""
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'MERKEZ'))


class Var:
    def __init__(self, value): self.value=value
    def get(self): return self.value
    def set(self, value): self.value=value


def test_can_start_petek_with_medium_slot_finish_without_optional_preview(tmp_path,monkeypatch):
    from URETIM_V4 import gui_v4
    messages=[];running=[];alerts=[]
    monkeypatch.setattr(gui_v4, 'iter_designs', lambda _p: iter([tmp_path/'Ham1.jpg']))
    monkeypatch.setattr(gui_v4.messagebox,'askyesno',lambda *a,**kw: True)
    monkeypatch.setattr(gui_v4.messagebox,'showwarning',lambda *a,**kw: alerts.append((a,kw)))
    monkeypatch.setattr(gui_v4.messagebox,'showinfo',lambda *a,**kw: alerts.append((a,kw)))
    class DirectThread:
        def __init__(self, *,target,daemon):self.target=target
        def start(self):self.target()
        def is_alive(self):return False
    monkeypatch.setattr(gui_v4.threading,'Thread',DirectThread)
    view=gui_v4.UnifiedV4BatchWindow.__new__(gui_v4.UnifiedV4BatchWindow)
    view.worker=None
    view.chosen_uids=lambda:['approved-petek']
    view._chosen_stores=lambda:[]
    view.template_items={'approved-petek':{'uid':'approved-petek','category':'06_Petek_Kapama'}}
    view.window=SimpleNamespace()
    view.runtime_root=None
    view.design_folder=Var(str(tmp_path))
    view.group=Var('LOCAL')
    view.placement=Var('Tam Göster')
    view.lighting=Var(gui_v4.LIGHT_LABELS[1])
    view.upscale_4k=Var(False)
    view.auto_cloud_link=Var(False)
    view.upscale_model=Var('Hızlı')
    view.petek_slot_mode=Var('orta')
    view.petek_pink_cleanup=Var(True)
    view._petek_preview_ok=None  # Unset: user did not click the A/B test.
    view._log=lambda *_: None
    view.progress=Var('')
    view.messages=SimpleNamespace(put=messages.append)
    view.start_button=SimpleNamespace(configure=lambda **kw: None)
    def run(folder,**options):
        running.append(options)
        return {'ok':True}
    view.batch_engine=SimpleNamespace(root=tmp_path,
        cancel=SimpleNamespace(clear=lambda:None),resume=lambda:None,run=run)
    view.start()
    assert not alerts
    assert len(running)==1
    assert running[0]['selected_uids']==['approved-petek']
    assert running[0]['petek_slot_mode']=='orta'
    assert running[0]['petek_pink_cleanup'] is True
    assert ('done',{'ok':True}) in messages


@pytest.mark.parametrize('count',[13,14,15,16])
def test_real_vent_axes_straight_and_painted_pixels_do_not_overrun_measured_caps(count):
    import cv2
    from MERKEZ.PETEK_V3.petek_slot_geometry_vnext import measure_real_vents,RECT_W,RECT_H
    from MERKEZ.PETEK_V3.petek_finish_v492 import draw_fifteen_slots
    # Render synthetic real 13..16 physical openings; source and mask do not change.
    height,width=540,700
    xs=np.linspace(85,820,count)
    rect=np.full((RECT_H,RECT_W,3),200,np.uint8)
    rectmask=np.full((RECT_H,RECT_W),255,np.uint8)
    for i,x in enumerate(xs):
        x=int(round(x))
        y0=110+i%3*3; y1=555-i%4*4
        cv2.line(rect,(x,y0),(x,y1),(20,24,25),8,cv2.LINE_AA)
        cv2.line(rectmask,(x,y0),(x,y1),0,9,cv2.LINE_AA)
    quad=np.float32([[55,60],[640,63],[628,468],[63,470]])
    dst=np.float32([[0,0],[RECT_W-1,0],[RECT_W-1,RECT_H-1],[0,RECT_H-1]])
    H=cv2.getPerspectiveTransform(dst,quad)
    source=cv2.warpPerspective(rect,H,(width,height),borderValue=(240,240,240))
    mask=cv2.warpPerspective(rectmask,H,(width,height),flags=cv2.INTER_NEAREST,borderValue=0)
    source_orig=source.copy(); mask_orig=mask.copy()
    slots,report=measure_real_vents(source,mask,quad)
    assert len(slots)==count
    for slot in slots:
        assert len(slot['path'])==2
        assert np.isclose(slot['path'][0][0],slot['path'][1][0])
        assert slot['path'][0][1]==slot['y0']
        assert slot['path'][1][1]==slot['y1']
        assert 200<slot['y1']-slot['y0']<520
    rendered=np.full_like(source,(170,180,200))
    output,qa=draw_fifteen_slots(source,rendered,mask,quad,mode='orta')
    assert qa['count']==count and qa['changed_pixels']>0
    assert np.array_equal(output[mask==0],rendered[mask==0])
    assert np.array_equal(source_orig,source) and np.array_equal(mask_orig,mask)
