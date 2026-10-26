from pathlib import Path
import sys
from contextlib import nullcontext
import cv2
import numpy as np
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'SABLON_V2_MIMARI'))

@pytest.mark.parametrize('category',['01_Wifi_Kutusu','02_Cam_Tablo_Dikey','02_Cam_Tablo_Yatay','03_Ahsap_Tablo','04_Cam_Dograma','05_Ocak_Arkasi'])
def test_batch_chroma_draft_never_uses_legacy_or_profile(tmp_path,monkeypatch,category):
    import app
    image=np.full((600,800,3),220,np.uint8);cv2.rectangle(image,(150,100),(650,500),(255,0,255),-1)
    src=tmp_path/'new.png';cv2.imwrite(str(src),image)
    monkeypatch.setattr(app,'_safe_template_path',lambda *a:str(src))
    monkeypatch.setattr(app,'template_operation_lock',lambda *a,**k:nullcontext())
    monkeypatch.setattr(app,'_analyze_auto_cached',lambda *a:pytest.fail('legacy fallback'))
    calls=[];monkeypatch.setattr(app,'_v46_store_draft',lambda *a:calls.append(a))
    result=app._analyze_template_for_batch(category,'new.png')
    assert result['draft_only'] and result['draft_saved'] and len(calls)==1
    assert calls[0][3]==app._sha256_file(src)


def test_ambiguous_petek_no_fallback(tmp_path,monkeypatch):
    import app
    image=np.full((400,500,3),(255,0,255),np.uint8);src=tmp_path/'petek.png';cv2.imwrite(str(src),image)
    monkeypatch.setattr(app,'_safe_template_path',lambda *a:str(src))
    monkeypatch.setattr(app,'template_operation_lock',lambda *a,**k:nullcontext())
    monkeypatch.setattr(app,'_analyze_auto_cached',lambda *a:pytest.fail('legacy fallback'))
    monkeypatch.setattr(app,'_v46_store_draft',lambda *a:pytest.fail('invalid draft'))
    assert app._analyze_template_for_batch('06_PETEK','petek.png')['status']=='REVIEW_REQUIRED'


def test_single_chroma_draft_persists_source_identity_without_db(tmp_path,monkeypatch):
    import app
    image=np.full((400,500,3),220,np.uint8);cv2.rectangle(image,(70,80),(430,320),(255,0,255),-1)
    src=tmp_path/'new.png';cv2.imwrite(str(src),image)
    monkeypatch.setattr(app,'_safe_template_path',lambda *a:str(src))
    monkeypatch.setenv('LOCALAPPDATA',str(tmp_path/'local'))
    monkeypatch.setattr(app,'save_template_profile',lambda *a:pytest.fail('DB mutation'))
    with app.app.test_request_context('/api/auto_detect_corners',method='POST',
          headers={'X-Active-Category':'01_Wifi_Kutusu','X-Active-Template':'new.png'},json={'save_as_draft':True}):
        response=app.api_auto_detect_corners.__wrapped__()
    assert response.json['draft_saved']
    import json
    draft=json.loads(app._v46_draft_path('01_Wifi_Kutusu','new.png').read_text())
    assert draft['source_sha256']==app._sha256_file(src)
    assert draft['corners']==response.json['corners']
