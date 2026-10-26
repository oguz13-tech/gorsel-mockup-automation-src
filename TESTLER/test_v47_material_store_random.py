"""V4.7 regression: legacy reflective glass, matte wood/PETEK and store isolation.
All fixtures are synthetic; no live Windows user workspace is accessed.
"""
import hashlib
import sys
from pathlib import Path
import cv2
import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'MERKEZ'))
sys.path.insert(0,str(ROOT/'TESTLER'))

from URETIM_V4.finish_material_v46 import apply_material_finish, GLASS, DAYLIGHT, RECIPE
from URETIM_V4.store_profiles_v47 import StoreProfiles, key_for
from URETIM_V4.unified_batch import UnifiedV4Batch
from test_v40_unified_seven_category import _build_seven_category_workspace, _write_png


@pytest.mark.parametrize('category',sorted(GLASS|DAYLIGHT))
def test_optical_material_profile_only_changes_approved_pixels(category):
    h,w=400,500
    source=np.full((h,w,3),210,np.uint8)
    printed=np.full_like(source,245)
    q=[[50,30],[450,50],[432,370],[40,350]]
    mask=np.zeros((h,w),np.uint8)
    cv2.fillConvexPoly(mask,np.array(q,np.int32),255)
    # PETEK holes and vents are excluded from print mask even if in quad.
    mask[150:310,230:250]=0
    before=printed.copy()
    out=apply_material_finish(source,printed,mask,q,category,enabled=True)
    off=apply_material_finish(source,printed,mask,q,category,enabled=False)
    assert np.array_equal(off,printed)
    assert np.array_equal(out[mask==0],printed[mask==0])
    d=np.abs(out.astype(np.int16)-printed.astype(np.int16))
    assert int(d[mask>0].max())>=3
    assert 0 < float(d[mask>0].mean()) < 32
    assert np.array_equal(printed,before)


def test_window_mullion_architecture_on_white_panel():
    h,w=400,500
    q=[[10,10],[489,10],[489,389],[10,389]]
    white=np.full((h,w,3),249,np.uint8)
    mask=np.full((h,w),255,np.uint8)
    out=apply_material_finish(white,white,mask,q,'02_Cam_Tablo_Yatay')
    # Structural contrast across projected bars, unlike the old softbox-only.
    upper=out[65:180,220:440,0].astype(np.float32)
    assert np.percentile(upper,90)-np.percentile(upper,10)>=5
    assert not np.array_equal(out,white)


def test_non_material_category_never_modified():
    x=np.full((200,200,3),125,np.uint8)
    m=np.full((200,200),255,np.uint8)
    assert np.array_equal(apply_material_finish(x,x,m,[[0,0],[199,0],[199,199],[0,199]],
                                                '01_Wifi_Kutusu'),x)


def test_store_profiles_immutable_membership_and_sha(tmp_path):
    sp=StoreProfiles(tmp_path/'state')
    a={'category':'03_Ahsap_Tablo','uid':'wood_1','source_sha':'a'*64}
    b={'category':'06_Petek_Kapama','uid':'petek_1','source_sha':'b'*64}
    sp.add_store('Magaza_01')
    sp.add_store('Magaza_03')
    sp.assign('Magaza_01',[a])
    sp.assign('Magaza_03',[b])
    with pytest.raises(ValueError,match='another|başka'):
        sp.assign('Magaza_03',[a])
    plan=sp.plan(['Magaza_01','Magaza_03'],[a,b])
    assert [s for s,_ in plan]==['Magaza_01','Magaza_03']
    assert [[x['uid'] for x in p] for _,p in plan]==[['wood_1'],['petek_1']]
    with pytest.raises(ValueError,match='onayı/SHA'):
        sp.plan(['Magaza_01'],[{**a,'source_sha':'c'*64},b])
    sp.unassign('Magaza_01',[a])
    sp.assign('Magaza_03',[a])
    assert len(sp.load()['stores']['Magaza_03']['templates'])==2
    assert any(tmp_path.joinpath('state').glob('store_profiles_v47.backup_*.json'))


def test_random_store_batch_isolated_and_no_same_sha_duplicate(tmp_path):
    runtime,petek_reg=_build_seven_category_workspace(tmp_path,per_cat_count=1)
    state=tmp_path/'private_state'
    batch=UnifiedV4Batch(state,runtime_root=runtime,petek_registry=petek_reg)
    templates,_=batch.discover_templates(per_category_limit=None)
    wood=next(x for x in templates if x['category']=='03_Ahsap_Tablo')
    glass=next(x for x in templates if x['category']=='02_Cam_Tablo_Yatay')
    profiles=StoreProfiles(state)
    profiles.add_store('Magaza_01')
    profiles.add_store('Magaza_02')
    profiles.assign('Magaza_01',[wood])
    profiles.assign('Magaza_02',[glass])
    designs=tmp_path/'artwork'
    image=np.full((350,350,3),(25,120,200),np.uint8)
    _write_png(designs/'art_A.png',image)
    _write_png(designs/'art_B.png',image)  # different name, identical SHA!
    result=batch.run(designs,selected_stores=['Magaza_01','Magaza_02'],
                     selected_uids=[wood['uid'],glass['uid']],
                     random_seed=123,lighting='natural',glass_effect='on')
    assert result['status']=='LOCAL_READY',result['errors']
    assert result['rendered']==2
    assert result['duplicates_skipped_in_run']==2
    records=batch.ledger.successful()
    assert len(records)==2
    assert {'Magaza_01','Magaza_02'}==set(result['store_ids'])
    for record in records:
        path=Path(record['output'])
        store=path.relative_to(batch.output).parts[0]
        assert store in ('Magaza_01','Magaza_02')
        assert record['uid']==({'Magaza_01':wood['uid'],'Magaza_02':glass['uid']}[store])
        assert path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest()==record['output_sha']
    assert len(result['current_batch_keys'])==2
    # Same inputs never overwrite files and never create duplicates in ledger.
    second=batch.run(designs,selected_stores=['Magaza_01','Magaza_02'],
                     selected_uids=[wood['uid'],glass['uid']],random_seed=456)
    assert second['rendered']==0
    assert second['reused']==2
    assert second['duplicates_skipped_in_run']==2


def test_gui_multi_store_and_legacy_fallback_wired():
    code=(ROOT/'MERKEZ'/'URETIM_V4'/'gui_v4.py').read_text(encoding='utf-8')
    assert 'selected_stores=selected_stores' in code
    assert 'Mağaza Profilleri / Şablon Atama' in code
    engine=(ROOT/'MERKEZ'/'URETIM_V4'/'unified_batch.py').read_text(encoding='utf-8')
    assert 'production_plan = [(group, templates)]' in engine
    assert 'rng.shuffle(designs_in_run)' in engine
    assert 'rng.shuffle(store_templates)' in engine
    assert 'MATERIAL_RECIPE' in engine
