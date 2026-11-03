"""V3.7 user-reported X-duplicate bug and production safety regressions."""
from pathlib import Path
import os,sys
from types import SimpleNamespace
import json
import cv2
import numpy as np
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'MERKEZ'))
from PETEK_V3 import curves,engine
from PETEK_V3.registry import Registry
from PETEK_V3.batch import Batch


def test_duplicate_horizontal_coordinate_keeps_latest_explicit_point():
    p=curves.normalized([[350,80],[100,75],[250,90],[250,110],[450,77]])
    assert p.tolist()==[[100.,75.],[250.,110.],[350.,80.],[450.,77.]]
    x,y=curves.interpolate(p)
    assert x[0]==100 and x[-1]==450
    assert y[list(x).index(250)]==110
    for a,b in zip(p[:-1],p[1:]):
        local=y[(x>=a[0])&(x<=b[0])]
        assert local.min()>=min(a[1],b[1])-1e-6
        assert local.max()<=max(a[1],b[1])+1e-6


def test_manual_upper_and_lower_curves_do_not_connect_or_extrapolate():
    h,w=380,520
    quad=np.float32([[40,35],[480,35],[480,350],[40,350]])
    base=engine.polygon_mask((h,w),quad)
    top=[[40,100],[250,125],[480,100]]
    bottom=[[40,310],[250,285],[480,310]]
    output=curves.apply(base,quad,top,bottom)
    assert output[50,250]==0 and output[150,250]==255
    assert output[300,250]==0 and output[210,250]==255
    assert output[190,250]==255
    assert output[250,5]==0 and output[250,500]==0
    assert engine.count_outside_panel(output,np.zeros((h,w,3),np.uint8),quad)==0
    only_top=curves.apply(base,quad,top)
    assert only_top[300,250]==255
    with pytest.raises(engine.MaskError, match='yeterince'):
        curves.apply(base,quad,[[130,100],[250,125],[390,100]],[])


def test_manual_curve_has_no_automatic_mirrored_curve():
    q=np.float32([[10,10],[390,10],[390,380],[10,380]])
    base=engine.polygon_mask((400,400),q)
    top=[[10,40],[200,70],[390,40]]
    expected=curves.apply(base,q,top)
    assert expected[355,200]==255

@pytest.mark.skipif(sys.platform!='win32' and not os.environ.get('DISPLAY'),reason='GUI display required')
def test_manual_gui_curve_points_drag_undo_persist(tmp_path,monkeypatch):
    import tkinter as tk
    from PETEK_V3.gui import MaskEditor, messagebox
    def fail_dialog(title,msg,**kwargs):
        raise AssertionError(f'Unexpected dialog: {title}: {msg}')
    monkeypatch.setattr(messagebox,'showerror',fail_dialog)
    root=tk.Tk();root.geometry('980x780')
    try:
        reg=Registry(tmp_path/'private')
        file=tmp_path/'blank.png'
        scene=np.full((440,520,3),235,np.uint8)
        cv2.rectangle(scene,(120,160),(130,330),(35,35,35),-1)
        assert cv2.imwrite(str(file),scene)
        e=MaskEditor(root,registry=reg);e.load(file)
        q=[[40,40],[480,40],[480,390],[40,390]]
        e.quad=q;e.mask=engine.polygon_mask(scene.shape,q);e.uid.set('PETEK_Test_37')
        e.refresh();e.mode.set('top')
        for sx,sy in [(240,110),(480,85),(40,85),(240,108)]:
            px,py=e.view.screen(sx,sy)
            e.click(SimpleNamespace(x=px,y=py))
            e._end_paint()
        # A click within handle radius selects existing point instead of
        # multiplying two equal-X source pixel points.
        assert len(e.curve)==3
        e.finish_curve()
        assert e.curve_base is not None
        assert e.mode.get()=='protect'
        assert len(e.curves['top'])==3
        prior=e.mask.copy()
        e.mode.set('top')
        px,py=e.view.screen(240,110)
        e.click(SimpleNamespace(x=px,y=py))
        px2,py2=e.view.screen(240,145)
        e.drag(SimpleNamespace(x=px2,y=py2));e._end_paint()
        assert not np.array_equal(e.mask,prior)
        e.undo()
        np.testing.assert_array_equal(e.mask,prior)
        e.mode.set('top'); e.finish_curve()
        e.mode.set('bottom')
        for sx,sy in [(40,350),(240,335),(480,350)]:
            px,py=e.view.screen(sx,sy);e.click(SimpleNamespace(x=px,y=py));e._end_paint()
        e.finish_curve()
        assert len(e.curves['top'])==3 and len(e.curves['bottom'])==3
        # Attempt to paint well OUTSIDE quad must not change mask or base.
        old=e.mask.copy();before=e.curve_base.copy()
        e.mode.set('wood')
        sx,sy=e.view.screen(1,1)
        e.click(SimpleNamespace(x=sx,y=sy));e._end_paint()
        np.testing.assert_array_equal(e.mask,old)
        np.testing.assert_array_equal(e.curve_base,before)
        # Huge brush inside quad cannot paint an external pixel.
        e.brush.set(150)
        px,py=e.view.screen(42,180)
        e.click(SimpleNamespace(x=px,y=py));e._end_paint()
        assert e.mask[180,1]==0
        e.mode.set('adjust')
        e.save_draft()
        p,stored=reg.get('PETEK_Test_37')
        assert p['base_mask_sha'] and len(p['curve_points']['top'])==3
        np.testing.assert_array_equal(stored,e.mask)
        # Approve must preserve independently editable points + immutable base SHA.
        reg.approve('PETEK_Test_37','HumanReviewer','I_VISUALLY_CHECKED_VENTS_ARCHES_FLOOR')
        approved,_=reg.get('PETEK_Test_37',require_approved=True)
        assert approved['base_mask_sha']==p['base_mask_sha']
        assert approved['curve_points']==p['curve_points']
        with pytest.raises(engine.MaskError):
            reg.save('PETEK_Test_37',file,q,e.mask,1.1163)
        e.load(file)
        assert e.curves['top'] and e.curves['bottom']
        assert e.curve_base is not None
    finally:
        root.destroy()


def test_sku_unique_for_same_art_across_two_templates(tmp_path):
    # Distinct approved templates (same art) must never share sellable SKU.
    srcs=[]
    art_dir=tmp_path/'designs';art_dir.mkdir()
    art=np.full((350,480,3),160,np.uint8)
    assert cv2.imwrite(str(art_dir/'design.png'),art)
    reg=Registry(tmp_path/'private')
    quad=np.float32([[35,35],[465,35],[465,370],[35,370]])
    mask=engine.polygon_mask((400,500),quad)
    mask[100:300,115:122]=0
    for i in range(2):
        scene=np.full((400,500,3),220+i,np.uint8)
        f=tmp_path/f'source{i}.png'
        assert cv2.imwrite(str(f),scene)
        uid=f'Test_37_{i}'
        reg.save(uid,f,quad,mask,1.12)
        reg.approve(uid,'Review','I_VISUALLY_CHECKED_VENTS_ARCHES_FLOOR')
        srcs.append(uid)
    result=Batch(reg).run(art_dir,srcs,group='LOCAL',max_jobs=2)
    assert result['rendered']==2 and not result['rejected']
    with Batch(reg).ledger.connect() as con:
        rows=con.execute('SELECT sku,output FROM artifact').fetchall()
    assert len({row['sku'] for row in rows})==2
    assert all(Path(row['output']).exists() for row in rows)


def test_same_filename_from_different_folders_never_collides(tmp_path):
    designs=tmp_path/'arts'
    for i in range(2):
        folder=designs/('account'+str(i));folder.mkdir(parents=True)
        data=np.full((360,480,3),120+i*50,np.uint8)
        assert cv2.imwrite(str(folder/'image.png'),data)
    src=tmp_path/'PETEK_original.png'
    assert cv2.imwrite(str(src),np.full((400,500,3),220,np.uint8))
    q=[[35,35],[465,35],[465,370],[35,370]]
    mask=engine.polygon_mask((400,500),np.asarray(q,np.float32))
    mask[160:290,90:99]=0
    reg=Registry(tmp_path/'private')
    reg.save('PetekSample_37',src,q,mask,1.12)
    reg.approve('PetekSample_37','Reviewer','I_VISUALLY_CHECKED_VENTS_ARCHES_FLOOR')
    result=Batch(reg).run(designs,['PetekSample_37'],max_jobs=5)
    assert result['rendered']==2
    with Batch(reg).ledger.connect() as db:
        paths=[Path(x['output']) for x in db.execute('SELECT output FROM artifact')]
    assert len(set(paths))==2 and all(p.exists() for p in paths)
    hashes=[engine.digest(p) for p in paths]
    assert len(set(hashes))==2
    repeat=Batch(reg).run(designs,['PetekSample_37'],max_jobs=5)
    assert repeat['reused']==2 and repeat['rendered']==0

@pytest.mark.skipif(sys.platform!='win32' and not os.environ.get('DISPLAY'),reason='GUI display required')
def test_same_mockup_filename_different_source_image_gets_distinct_uid(tmp_path):
    import tkinter as tk
    from PETEK_V3.gui import MaskEditor
    reg=Registry(tmp_path/'private')
    srcs=[]
    for i in range(2):
        f=tmp_path/f'account_{i}'/'Gemini_Generated_Image.png'
        f.parent.mkdir()
        assert cv2.imwrite(str(f),np.full((400,500,3),210+i,np.uint8))
        srcs.append(f)
    q=[[40,40],[460,40],[460,350],[40,350]]
    mask=engine.polygon_mask((400,500),np.asarray(q,np.float32))
    mask[100:320,110:120]=0
    reg.save('Gemini_Generated_Image',srcs[0],q,mask,1.1)
    root=tk.Tk()
    try:
        editor=MaskEditor(root,registry=reg)
        editor.load(srcs[1])
        assert editor.uid.get()!='Gemini_Generated_Image'
        assert reg.get('Gemini_Generated_Image')[0]['source_sha']==engine.digest(srcs[0])
    finally:root.destroy()
