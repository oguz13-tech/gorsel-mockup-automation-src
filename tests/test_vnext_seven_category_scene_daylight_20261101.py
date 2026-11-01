"""Seven-category scene sun: isolated matrix, controls, wall and protection."""
from pathlib import Path
import hashlib
import cv2
import numpy as np
import pytest

from URETIM_V4.scene_daylight_vnext import (CATEGORIES, PROFILES, RECIPE,
    apply_scene_daylight, daylight_lighting)
from URETIM_V4.unified_batch import (_render_legacy_six_cover,
    _build_legacy_category_mask, unified_receipt_identity)


def scene_fixture():
    h,w=450,790
    scene=np.full((h,w,3),(194,204,214),np.uint8)
    yy,xx=np.mgrid[:h,:w]
    tone=(1.8*np.sin(xx/50.)+1.3*np.cos(yy/43.)).astype(np.int16)
    scene[:]=np.uint8(np.clip(scene.astype(np.int16)+tone[:,:,None],0,255))
    scene[390:]=(80,120,160)
    scene[60:390,75:138]=(216,219,225) # real painted cabinet SIDE
    scene[58:385,138:667]=(255,0,255) # original print marker
    mask=np.zeros((h,w),np.uint8); mask[58:385,138:667]=255
    scene[150:230,725:755]=(44,64,92) # furniture/decoration
    q=np.float32([[138,58],[667,58],[667,384],[138,384]])
    return scene,mask,q


@pytest.mark.parametrize('cat', sorted(CATEGORIES))
def test_all_seven_names_use_shared_scene_field_and_protect_source(cat):
    scene,mask,q=scene_fixture()
    before=scene.copy(); before_mask=mask.copy(); before_q=q.copy()
    rendered=scene.copy(); rendered[mask>0]=(232,235,238)
    original=rendered.copy()
    output, qa=apply_scene_daylight(scene,rendered,mask,q,cat,profile='belirgin')
    assert qa['profile']=='belirgin' and qa['shadow_bands']==2
    assert qa['wall_shadow_pixels']>400
    assert np.any(output[mask>0]!=original[mask>0])
    assert np.array_equal(output[390:],scene[390:]) # parquet never touched
    assert np.array_equal(output[80:360,95:125],scene[80:360,95:125]) # cabinet side
    assert np.array_equal(output[150:230,725:755],scene[150:230,725:755]) # decor
    assert np.array_equal(scene,before) and np.array_equal(mask,before_mask)
    assert np.array_equal(q,before_q) and np.array_equal(original,rendered)


def test_original_mode_byte_exact_and_natural_never_changes_background():
    scene,mask,q=scene_fixture()
    rend=scene.copy(); rend[mask>0]=(228,230,232)
    off,qa=apply_scene_daylight(scene,rend,mask,q,'01_Wifi_Kutusu',profile='off')
    assert np.array_equal(off,rend) and qa['status']=='OFF'
    natural, qa=apply_scene_daylight(scene,rend,mask,q,'01_Wifi_Kutusu',profile='dogal')
    assert np.array_equal(natural[mask==0],scene[mask==0])
    assert qa['wall_shadow_pixels']==0


def test_invalid_settings_and_protected_furniture_are_not_shadowed():
    scene,mask,q=scene_fixture()
    with pytest.raises(ValueError,match='SETTINGS_INVALID'):
        apply_scene_daylight(scene,scene,mask,q,'FAKE',profile='belirgin')
    with pytest.raises(ValueError,match='SETTINGS_INVALID'):
        apply_scene_daylight(scene,scene,mask,q,'01_Wifi_Kutusu',profile='great')
    assert daylight_lighting('off','belirgin')=='off'
    assert daylight_lighting('natural','belirgin')=='strong'
    assert daylight_lighting('natural','off')=='natural'
    scene[:,0:75]=(17,42,67);scene[:,690:]=(17,42,67)
    img=scene.copy();img[mask>0]=(230,231,232)
    output,qa=apply_scene_daylight(scene,img,mask,q,'03_Ahsap_Tablo',profile='belirgin')
    assert qa['wall_status']=='WALL_NOT_CONFIDENT'
    assert np.array_equal(output[mask==0],scene[mask==0])


@pytest.mark.parametrize('category',sorted(CATEGORIES-{'06_Petek_Kapama'}))
def test_real_legacy_six_renderer_sun_and_magenta_guards(tmp_path,category):
    scene,mask,q=scene_fixture()
    art=np.full((180,300,3),(241,241,242),np.uint8)
    cv2.rectangle(art,(88,62),(120,130),(18,16,13),-1)
    orig=scene.copy()
    sp=tmp_path/'scene.png';ap=tmp_path/'art.png'
    assert cv2.imwrite(str(sp),scene) and cv2.imwrite(str(ap),art)
    baseline, qa_off = _render_legacy_six_cover(sp,ap,q,mask,1.6,
        category=category, sunlight_profile='off',lighting='natural',marketplace=False)
    sunlight, qa = _render_legacy_six_cover(sp,ap,q,mask,1.6,
        category=category, sunlight_profile='belirgin',lighting='natural',marketplace=False)
    assert qa_off['source_pixels_unchanged']
    assert not np.array_equal(sunlight,baseline)
    assert qa['sunlight_qa']['wall_shadow_pixels']>200
    assert np.array_equal(sunlight[390:],scene[390:])
    assert np.array_equal(sunlight[80:360,95:125],scene[80:360,95:125])
    assert np.array_equal(cv2.imread(str(sp)),orig)
    # The source magenta key should never ghost into the middle of a white design.
    face=sunlight[65:378,160:650]
    neon=(face[:,:,0]>160)&(face[:,:,2]>160)&(face[:,:,1]<90)
    assert np.count_nonzero(neon)==0


def test_receipts_distinct_and_immutable_sources():
    item={'quad':[[10,10],[105,10],[105,110],[10,110]],
          'category':'01_Wifi_Kutusu','uid':'1','source_sha':'a'*64,
          'mask_sha':'b'*64,'physical_aspect':1.}
    common=dict(group='LOCAL',placement='cover',lighting='natural',glass_effect='off')
    default,old=unified_receipt_identity(item,'c'*64,**common)
    nat,natural=unified_receipt_identity(item,'c'*64,**common,sunlight_profile='dogal',recipe='v4-6-chroma-solid-20261026+'+RECIPE)
    strong,_=unified_receipt_identity(item,'c'*64,**common,sunlight_profile='belirgin',recipe='v4-6-chroma-solid-20261026+'+RECIPE)
    assert len({default,nat,strong})==3
    assert 'sunlight_profile' not in old
    assert natural['sunlight_profile']=='dogal'


def test_petek_approved_pink_geometry_stays_file_byte_identical():
    root=Path(__file__).resolve().parents[1]
    # V4.11 intentionally changes final_cleanup to detect newly introduced
    # magenta (Luna N2) without changing the actual artwork rendering math.
    # Other pinned geometry/slot/fringe files remain byte-identical.
    expected={'MERKEZ/PETEK_V3/final_cleanup_v495.py': 'bd2e6f4dd136df4cb2e35a8735cc671390dc5db52214081a407c11bef921b45c',
 'MERKEZ/PETEK_V3/petek_finish_v492.py': '21fa469bce7a761f8d0a33f4e63a15dfcd126bc52419504c1aa75d4a9413889d',
 'MERKEZ/PETEK_V3/petek_slot_geometry_vnext.py': 'fb67792f1556f1e0174b332dad077e8eef4af7adbd75c4210e54e8378fbfc965',
 'MERKEZ/PETEK_V3/petek_source_marker_fringe_vnext.py': '8f56cf07d2ff58f5e82a154cc4e05583b6dab9f942b01a5c30ded6eac31b8a19',
}
    for rel, sha in expected.items():
        assert hashlib.sha256((root/rel).read_bytes()).hexdigest()==sha,rel
