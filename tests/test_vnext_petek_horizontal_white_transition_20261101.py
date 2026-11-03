"""User acceptance: horizontal shadows + left-to-centre white recovery."""
import numpy as np
from MERKEZ.PETEK_V3.realism import _diffuse_window_shadows, apply


def test_horizontal_shadow_band_has_broad_width_not_vertical_columns():
    h,w=540,900
    mask=np.zeros((h,w),np.uint8)
    mask[35:505,65:850]=255
    shadow=_diffuse_window_shadows((h,w,3),mask,.6)
    assert np.array_equal(shadow[mask==0],np.zeros_like(shadow[mask==0]))
    y=int(35+(505-35)*.57)
    # More than two-thirds of full printable width is affected on one row.
    assert np.count_nonzero(shadow[y,85:835]>.2)>500
    # At a given x, the band changes over y: horizontal strip, not a
    # vertical full-height shadow column.
    assert shadow[y,400] > shadow[100,400]+.2
    assert shadow[y,400] > shadow[490,400]+.2


def test_left_white_near_real_cabinet_mid_reverts_bright_without_magenta():
    h,w=460,770
    scene=np.full((h,w,3),(198,207,214),np.uint8)
    mask=np.zeros((h,w),np.uint8)
    mask[50:410,115:700]=255
    scene[50:410,115:700]=(255,0,255) # original chroma marker
    art=np.full_like(scene,255)
    out=apply(scene,art,mask,'strong')
    # Use multiple rows to avoid comparing one artificially shadowed strip.
    rows=np.arange(90,400,8)
    left=np.mean(out[rows,130],axis=0)
    centre=np.mean(out[rows,440],axis=0)
    assert np.mean(centre) > np.mean(left)+10
    # Real side panel has BGR approx (198,207,214). Left starts near it.
    assert np.mean(np.abs(left-scene[70,80].astype(float)))<27
    # White recovers gradually without straight hard seam or fully blown 255.
    assert np.mean(out[rows,240]) < np.mean(out[rows,440])
    assert np.max(out[mask>0])<255
    # No magenta mixing: blue/red high relative to green would reveal marker.
    pix=out[mask>0].astype(np.int16)
    assert not np.any((pix[:,0]>pix[:,1]+25)&(pix[:,2]>pix[:,1]+25))


def test_ink_preserved_and_off_unchanged():
    h,w=460,770
    scene=np.full((h,w,3),(210,215,219),np.uint8)
    mask=np.zeros((h,w),np.uint8)
    mask[40:420,80:720]=255
    scene[40:420,80:720]=(255,0,255)
    design=np.full_like(scene,255)
    design[160:300,310:390]=(5,6,7)
    edited=apply(scene,design,mask,'strong')
    assert np.mean(edited[200,350])<25
    assert np.array_equal(apply(scene,design,mask,'off'),design)
    assert np.array_equal(scene[150,200],np.array([255,0,255],np.uint8))
