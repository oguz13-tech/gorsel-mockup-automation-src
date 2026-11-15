from pathlib import Path
import sys
import cv2
import numpy as np
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'MERKEZ'))
from URETIM_V4.unified_batch import _render_legacy_six_cover
from URETIM_V4.chroma_render_v46 import prepare_chroma

@pytest.mark.parametrize('category',['01_Wifi_Kutusu','02_Cam_Tablo_Dikey','02_Cam_Tablo_Yatay','03_Ahsap_Tablo','04_Cam_Dograma','05_Ocak_Arkasi'])
def test_white_print_has_no_marker_blending_and_preserves_outside(tmp_path,category):
    scene=np.full((240,320,3),180,np.uint8);mask=np.zeros((240,320),np.uint8)
    q=[[40,40],[280,40],[280,200],[40,200]]
    cv2.fillConvexPoly(mask,np.int32(q),255);scene[mask>0]=(255,0,255)
    # A protected real mounting point stays outside printable mask.
    scene[100:105,100:105]=20;mask[100:105,100:105]=0
    source=tmp_path/'source.png';art=tmp_path/'art.png'
    cv2.imwrite(str(source),scene);cv2.imwrite(str(art),np.full((160,240,3),255,np.uint8))
    out,qa=_render_legacy_six_cover(source,art,q,mask,1.5,lighting='off',glass_effect='off',category=category,marketplace=False)
    assert qa['chroma_solid_coverage']
    assert np.all(out[mask>0]==255)
    assert np.array_equal(out[mask==0],scene[mask==0])
    final,_=_render_legacy_six_cover(source,art,q,mask,1.5,lighting='off',glass_effect='off',category=category)
    assert final.shape[:2]==(1600,1200)

def test_marker_outside_approved_mask_is_review_not_silent_edit():
    scene=np.full((240,320,3),(255,0,255),np.uint8);mask=np.zeros((240,320),np.uint8);mask[20:220,20:300]=255
    with pytest.raises(ValueError,match='CHROMA_REVIEW_REQUIRED'):prepare_chroma(scene,mask)
