"""13/14/15/16 real openings: perspective measured, never infilled to 15."""
import cv2
import numpy as np
import pytest
from MERKEZ.PETEK_V3.petek_finish_v492 import draw_fifteen_slots
from MERKEZ.PETEK_V3.petek_slot_geometry_vnext import measure_real_vents, _fit_source_vents
from MERKEZ.PETEK_V3.final_cleanup_v495 import cleanup_petek_magenta


def scene_with_count(n, extra_artwork=False, complete_mask=False):
    gw,gh=900,690
    centers=np.rint(np.linspace(83,819,n)).astype(int)
    photo=np.full((gh,gw,3),(188,201,216),np.uint8)
    mask=np.full((gh,gw),255,np.uint8)
    for i,x in enumerate(centers):
        a=110+(i%3)*4
        b=571-(i%4)*5
        width=7+i%4
        cv2.line(photo,(int(x),a),(int(x),b),(23,25,30),width,cv2.LINE_AA)
        if complete_mask or i%4!=1:cv2.line(mask,(int(x),a),(int(x),b),0,width+1,cv2.LINE_AA)
    if extra_artwork:
        cv2.line(photo,(218,170),(218,480),(35,45,58),6,cv2.LINE_AA)
    cv2.ellipse(mask,(450,-115),(480,210),0,0,180,0,-1)
    cv2.ellipse(mask,(450,760),(430,115),0,180,360,0,-1)
    height,width=540,700
    quad=np.float32([[79,63],[626,77],[596,448],[73,481]])
    H=cv2.getPerspectiveTransform(np.float32([[0,0],[gw-1,0],[gw-1,gh-1],[0,gh-1]]),quad)
    projected=cv2.warpPerspective(photo,H,(width,height))
    panel=np.zeros((height,width),np.uint8)
    cv2.fillConvexPoly(panel,quad.astype(np.int32),255)
    source=np.full((height,width,3),(238,233,229),np.uint8)
    source[panel>0]=projected[panel>0]
    projected_mask=cv2.warpPerspective(mask,H,(width,height),flags=cv2.INTER_NEAREST)
    projected_mask[panel==0]=0
    return source,projected_mask,quad,centers


@pytest.mark.parametrize('n',[5,6,7,8,9,10,11,12,13,14,15,16,17])
def test_photo_count_real_perspective_tracks_with_missing_mask_holes(n):
    source,mask,quad,centers=scene_with_count(n)
    orig=(source.copy(),mask.copy(),quad.copy())
    rendered=np.full_like(source,(170,160,220))
    result,qa=draw_fifteen_slots(source,rendered,mask,quad,mode='orta')
    assert qa['count']==n and qa['alignment']==f'SOURCE_PHOTO_{n}'
    assert len(qa['centers_rectified_900'])==n
    assert len(qa['spacings_rectified_900'])==n-1
    assert np.max(np.abs(np.array(qa['centers_rectified_900'])-centers))<5
    # Sparse layouts can have insufficient printable-mask endpoint evidence;
    # they are still measured and reported, but no unsafe slot paint is added.
    if qa['endpoint_effect_eligible_count']:
        assert qa['changed_pixels']>0
    assert np.array_equal(result[mask==0],rendered[mask==0])
    assert all(np.array_equal(a,b) for a,b in zip(orig,(source,mask,quad)))
    cleanup,report=cleanup_petek_magenta(result,mask,quad,
        slot_centers=qa['centers_rectified_900'],enabled=True)
    assert cleanup.shape==result.shape
    assert isinstance(report,dict)


def test_real_fifteen_with_one_artwork_stripe_does_not_become_sixteen():
    source,mask,quad,centers=scene_with_count(15,extra_artwork=True)
    slots,qa=measure_real_vents(source,mask,quad)
    assert len(slots)==15
    assert qa['alignment']=='SOURCE_PHOTO_15'
    assert np.max(np.abs(np.array(qa['centers_rectified_900'])-centers))<5


def test_irregular_but_physical_twelve_peak_sequence_uses_observed_centres():
    """A valid 12-vent perspective sequence need not fit one fixed lattice."""
    centers=np.array([77,153,228,302,376,446,516,580,644,707,767,823],float)
    profile=np.zeros(900,np.float32)
    for x in centers:
        profile[int(x)]=160.0
    peaks=[(int(x),160.0) for x in centers]
    fitted,_=_fit_source_vents(peaks,profile)
    assert fitted is not None
    assert len(fitted)==12
    assert np.array_equal(np.rint(fitted).astype(int),centers.astype(int))
