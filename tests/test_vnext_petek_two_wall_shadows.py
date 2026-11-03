"""Regressions: 2 continuous diagonal window shadows from wall to front to wall.

Safety: no modification of source, mask, geometry, floor, cabinet side or
physical holes, and only source-linked magenta repair outside print.
"""
import cv2
import numpy as np
import pytest
from MERKEZ.PETEK_V3.realism import _window_shadow_field, _diffuse_window_shadows
from MERKEZ.PETEK_V3.wall_window_shadows_vnext import wall_region,apply_wall_window_shadows
from MERKEZ.PETEK_V3.petek_visual_pipeline_vnext import verify_petek_source_protection
from MERKEZ.PETEK_V3 import engine


def photo():
    h,w=450,790
    scene=np.full((h,w,3),(194,204,214),np.uint8)
    # Wall has light real photographic variation, not magenta.
    yy,xx=np.mgrid[:h,:w]
    tone=(1.8*np.sin(xx/50.) + 1.3*np.cos(yy/43.)).astype(np.int16)
    scene=np.uint8(np.clip(scene.astype(np.int16)+tone[:,:,None],0,255))
    scene[390:]=(80,120,160)  # floor
    scene[60:390,75:138]=(216,219,225)  # painted side of real cabinet
    scene[58:385,138:667]=(255,0,255)  # raw magenta print marker
    mask=np.zeros((h,w),np.uint8)
    mask[58:385,138:667]=255
    # Actual black physical vents have no printed pixels.
    for xc in range(190,650,33):
        mask[110:340,xc:xc+5]=0
        scene[110:340,xc:xc+5]=(18,18,18)
    quad=np.float32([[138,58],[667,58],[667,384],[138,384]])
    # Wall decor on right, must not be darkened.
    scene[150:230,725:755]=(44,64,92)
    # Pink fringe outside print must remain excluded from wall shading.
    scene[90:360,137]=(255,0,255)
    return scene,mask,quad


def test_two_near_horizontal_continuous_bands_exactly():
    scene,mask,q=photo()
    field=_window_shadow_field(scene.shape,mask)
    assert np.max(field)>0.80
    # Two and only two strong peaks at middle of frame.
    line=field[:,400]
    peaks=np.where((line[1:-1]>line[:-2])&(line[1:-1]>line[2:])&(line[1:-1]>.45))[0]
    assert len(peaks)==2
    # Near-horizontal tilt is intentional, not vertical bars.
    y_left=np.argmax(field[:235,100]); y_right=np.argmax(field[:235,700]);
    assert abs(int(y_left)-int(y_right)) in range(5,65)
    assert field[y_left,100]>.40 and field[y_right,700]>.40
    assert np.count_nonzero(_diffuse_window_shadows(scene.shape,mask,.33)[mask==0])==0


def test_wall_is_connected_smooth_and_does_not_touch_props_floor_side():
    scene,mask,q=photo()
    wall=wall_region(scene,mask,q)
    assert np.count_nonzero(wall[:,0:65])>600
    assert np.count_nonzero(wall[:,690:790])>600
    assert not np.any(wall[390:])
    assert not np.any(wall[65:380,80:130])
    assert not np.any(wall[150:230,725:755])
    assert not np.any(wall[90:360,137])
    assert not np.any(wall[mask>0])
    # Avoid the previous scattered unconnected magenta-like speckles.
    count,labels,stats,_=cv2.connectedComponentsWithStats(wall.astype('uint8'),8)
    assert sum(int(s[cv2.CC_STAT_AREA])>100 for s in stats[1:])<=2


def test_same_two_bands_across_wall_and_front_persist_in_final_result():
    scene,mask,q=photo()
    before=scene.copy(); original_mask=mask.copy(); original_q=q.copy()
    printed=scene.copy()
    printed[mask>0]=(224,227,230)
    panel=_diffuse_window_shadows(scene.shape,mask,.33)
    ink=printed.astype(np.float32)
    ink[mask>0]*=(1.-panel[mask>0,None]); printed[mask>0]=np.uint8(ink[mask>0]+.5)
    output,qa=apply_wall_window_shadows(scene,printed,mask,q)
    assert qa['shadow_bands']==2 and qa['wall_shadow_pixels']>800
    assert qa['status']=='APPLIED'
    assert np.any(output[145,12]!=scene[145,12])
    # The effect should exist at a consistent global Y along the two walls.
    dy=np.mean(np.abs(output.astype('int16')-scene.astype('int16')),axis=2)
    assert np.max(dy[115:195,0:60])>5
    assert np.max(dy[115:195,675:720])>5
    assert np.array_equal(output[390:],scene[390:])
    assert np.array_equal(output[150:230,725:755],scene[150:230,725:755])
    assert np.array_equal(output[60:385,83:129],scene[60:385,83:129])
    assert np.array_equal(scene,before) and np.array_equal(mask,original_mask) and np.array_equal(q,original_q)
    qa2=verify_petek_source_protection(scene,output,mask,q,pink_cleanup=False)
    assert qa2['status']=='PASS' and qa2['authorized_wall_shadow_pixels']>800
    changed=output.copy()
    changed[420,40]=0
    with pytest.raises(engine.MaskError,match='PETEK_PREVIEW_PROTECTED_PIXELS_CHANGED'):
        verify_petek_source_protection(scene,changed,mask,q,pink_cleanup=False)


def test_weak_or_missing_wall_skips_instead_of_painting_furniture():
    scene,mask,q=photo()
    scene[:,:70]=(20,50,15)
    scene[:,680:]=(45,80,10)
    scene[390:]=(80,120,160)
    scene[150:230,725:755]=(44,64,92)
    wall=wall_region(scene,mask,q)
    assert np.count_nonzero(wall)==0
    pic,qa=apply_wall_window_shadows(scene,scene,mask,q)
    assert qa['status']=='WALL_NOT_CONFIDENT'
    assert np.array_equal(pic,scene)


def test_full_petek_pipeline_shares_wall_and_print_shadow_and_leaves_source_unchanged():
    from MERKEZ.PETEK_V3.petek_visual_pipeline_vnext import render_petek_visual
    scene,mask,quad=photo()
    src=scene.copy(); original_mask=mask.copy(); original_quad=quad.copy()
    art=np.full((310,500,3),246,np.uint8)
    art[120:180,210:260]=(12,20,32)
    frame,meta=render_petek_visual(scene,art,quad,mask,1.4,slot_mode='off',
                                   pink_cleanup=False,lighting='strong',material_effect=True)
    assert meta['wall_shadow_qa']['status']=='APPLIED'
    assert meta['wall_shadow_qa']['shadow_bands']==2
    assert meta['source_protection_qa']['status']=='PASS'
    assert np.array_equal(frame[160:220,735:745],scene[160:220,735:745])
    assert np.array_equal(scene,src) and np.array_equal(mask,original_mask)
    assert np.array_equal(quad,original_quad)
    # Normal / before mode never shadows the photographed wall.
    before,before_qa=render_petek_visual(scene,art,quad,mask,1.4,slot_mode='off',
                                   pink_cleanup=False,lighting='off',material_effect=False)
    assert before_qa['wall_shadow_qa']['status']=='OFF'
    assert np.array_equal(before[mask==0],scene[mask==0])
    assert not np.array_equal(before[mask>0],frame[mask>0])


def test_http_ab_and_browser_report_actual_wall_shadow_status():
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    web=(root/'SABLON_V2_MIMARI/core/petek_web_v477.py').read_text('utf-8')
    js=(root/'SABLON_V2_MIMARI/static/js/petek_editor_v477.js').read_text('utf-8')
    assert "'wall_shadow_qa':after_qa['wall_shadow_qa']" in web
    assert "'wall_shadow_qa':qa['wall_shadow_qa']" in web
    assert 'verify_petek_source_protection(scene,after,mask,quad,pink_cleanup=cleanup,' in web
    assert 'güvenilir duvar alanı bulunamadığından' in js
    assert 'Yatay gölge: 2 bant' in js
