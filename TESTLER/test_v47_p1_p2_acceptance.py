"""Offline regression: Flask localhost security, cloud, 4K, PETEK, store similarity,
120-image stress with STOP/RESUME, and visual A/B envelope. No real network."""
from pathlib import Path
import hashlib
import importlib.util
import json
import sys
import threading
import types
import numpy as np
import cv2
import pytest
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'MERKEZ'))
sys.path.insert(0,str(ROOT/'TESTLER'))
from PETEK_V3 import engine as petek_engine
from PETEK_V3.geometry_qa_v47 import inspect_print_safety
from URETIM_V4.store_profiles_v47 import StoreProfiles,perceptual_fingerprint,near_distance
from URETIM_V4.cloud_excel_v43 import CloudExcel,_valid_https_image_url
from URETIM_V4.upscale4k_v44 import process
from URETIM_V4.finish_material_v46 import GLASS,DAYLIGHT,apply_material_finish
from URETIM_V4.optical_qa_v47 import measure_effect
from URETIM_V4.unified_batch import UnifiedV4Batch
from test_v40_unified_seven_category import _build_seven_category_workspace,_write_png


def test_single_release_identity():
    import version_v45,version_v46,version_v47
    assert version_v47.VERSION=='V4.7.7'
    assert version_v45.TITLE==version_v46.TITLE==version_v47.TITLE


def test_loopback_host_origin_csrf():
    spec=importlib.util.spec_from_file_location(
        'loopback_guard',ROOT/'SABLON_V2_MIMARI'/'core'/'loopback_security_v47.py')
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    def fake(host='127.0.0.1:8080',method='POST',headers=None):
        return types.SimpleNamespace(host=host,method=method,headers=headers or {})
    assert mod.check(fake())=='CSRF_HEADER_REQUIRED'
    assert mod.check(fake(headers={'X-V47-CSRF':mod.token()})) is None
    assert mod.check(fake(host='other-domain.example',headers={'X-V47-CSRF':mod.token()}))=='LOOPBACK_HOST_FORBIDDEN'
    assert mod.check(fake(headers={'Origin':'https://evil.example',
                         'X-V47-CSRF':mod.token()}))=='CROSS_ORIGIN_FORBIDDEN'
    assert mod.check(fake(headers={'Sec-Fetch-Site':'cross-site',
                         'X-V47-CSRF':mod.token()}))=='CROSS_SITE_FORBIDDEN'
    assert mod.check(fake(method='GET')) is None
    page=(ROOT/'SABLON_V2_MIMARI'/'templates'/'index.html').read_text('utf-8')
    assert page.index('loopback_csrf_v47.js')<page.index('main.js')


def test_store_near_duplicate_png_jpeg_sha_different(tmp_path):
    sp=StoreProfiles(tmp_path/'state')
    sp.add_store('Magaza_01');sp.add_store('Magaza_02')
    y,x=np.mgrid[0:96,0:128]
    img=np.stack([np.uint8(x*2),np.uint8(y*2),np.uint8((x+y)%256)],axis=2)
    png=_write_png(tmp_path/'one.png',img)
    jpg=tmp_path/'two.jpg'
    jpg.write_bytes(cv2.imencode('.jpg',img,[cv2.IMWRITE_JPEG_QUALITY,98])[1].tobytes())
    a={'category':'03_Ahsap_Tablo','uid':'one','source_sha':petek_engine.digest(png),'source':str(png)}
    b={'category':'03_Ahsap_Tablo','uid':'two','source_sha':petek_engine.digest(jpg),'source':str(jpg)}
    assert a['source_sha']!=b['source_sha']
    assert near_distance(perceptual_fingerprint(a),perceptual_fingerprint(b))<=4
    sp.assign('Magaza_01',[a],all_approved=[a,b])
    with pytest.raises(ValueError,match='BENZER_MOCKUP'):
        sp.assign('Magaza_02',[b],all_approved=[a,b])


def test_cloud_sha_local_only_and_idempotent(tmp_path,monkeypatch):
    import URETIM_V4.cloud_excel_v43 as cloudmodule
    state=tmp_path/'state';folder=state/'uretilen_gorseller'/'LOCAL'/'03_Ahsap_Tablo'
    folder.mkdir(parents=True)
    src=folder/'img.png';src.write_bytes(b'synthetic data')
    row={'key':'1','sku':'AHT-LOCAL-001','category':'03_Ahsap_Tablo',
         'art_name':'art.png','output':str(src),'output_sha':petek_engine.digest(src)}
    cloud=CloudExcel(state,state/'raporlar')
    monkeypatch.setattr(cloudmodule,'_keys',lambda _: (['FAKE_TEST_ONLY'],''))
    uploads=[]
    def upload(path,keys,backup):
        uploads.append(str(path))
        return 'https://i.ibb.co/test.png'
    first=cloud.publish_existing([row,row],upload_fn=upload)
    assert first['uploaded']==1 and first['linked']==1 and first['skipped']==1
    second=cloud.publish_existing([row],upload_fn=upload)
    assert second['reused']==1 and len(uploads)==1
    external=tmp_path/'private.png';external.write_bytes(src.read_bytes())
    denied=cloud.publish_existing([{**row,'key':'2','output':str(external)}],upload_fn=upload)
    assert denied['failed']==1 and len(uploads)==1
    assert not _valid_https_image_url('https://127.0.0.1/a.png')
    assert Path(first['xlsx']).is_file()


def test_4k_mock_engine_create_only_sha_and_corruption(tmp_path,monkeypatch):
    import URETIM_V4.upscale4k_v44 as upscale
    state=tmp_path/'state'
    src=state/'uretilen_gorseller'/'LOCAL'/'03_Ahsap_Tablo'/'a.png'
    src.parent.mkdir(parents=True)
    Image.new('RGB',(1200,1600),'white').save(src)
    fake=tmp_path/'fake.exe';fake.write_bytes(b'test')
    monkeypatch.setattr(upscale,'preflight',lambda **kw:fake)
    monkeypatch.setattr(upscale,'TARGET',(1200,1600))
    calls=[]
    def fake_run(command,**kw):
        calls.append(command)
        Image.new('RGB',(1200,1600),'gray').save(Path(command[command.index('-o')+1]))
        return types.SimpleNamespace(returncode=0,stdout='',stderr='')
    monkeypatch.setattr(upscale.subprocess,'run',fake_run)
    records=[{'key':'k','sku':'AHT-LOCAL-01',
              'output':str(src),'output_sha':upscale.sha256(src)}]
    first=process(records,state_root=state,enabled=True)
    assert first['upscaled']==1 and first['failed']==0
    assert process(records,state_root=state,enabled=True)['reused']==1
    assert len(calls)==1
    Path(first['items'][0]['output']).write_bytes(b'corrupt')
    assert process(records,state_root=state,enabled=True)['failed']==1
    assert len(calls)==1


@pytest.mark.parametrize('cat',sorted(GLASS|DAYLIGHT))
def test_effect_mask_and_contrast_QA(cat):
    source=np.full((250,350,3),150,np.uint8)
    q=[[30,25],[320,25],[320,225],[30,225]]
    mask=np.zeros((250,350),np.uint8)
    cv2.fillConvexPoly(mask,np.asarray(q,np.int32),255)
    mask[110:180,165:182]=0
    cv2.putText(source,'DESIGN',(60,140),cv2.FONT_HERSHEY_SIMPLEX,1.3,(15,15,15),3)
    result=measure_effect(source,apply_material_finish(source,source,mask,q,cat),mask,cat)
    assert result['status']=='CHECK_HUMAN'
    assert result['protected_pixel_changes']==0
    assert result['p95_inside_delta']<75
    assert result['detail_edge_delta']<40


def test_petek_13_vents_side_top_bottom_floor_protected():
    h,w=520,480;scene=np.full((h,w,3),165,np.uint8)
    q=[[50,75],[425,75],[425,450],[50,450]]
    mask=np.zeros((h,w),np.uint8)
    cv2.fillConvexPoly(mask,np.asarray(q,np.int32),255)
    regions={'vents':[],'side_face':[[[50,80],[80,80],[80,445],[50,445]]],
             'floor':[[[52,415],[421,415],[421,468],[52,468]]],
             'top_curve':[[[70,76],[409,76],[409,85],[70,85]]]}
    for x in range(90,90+13*24,24):
        regions['vents'].append([[x,160],[x+6,160],[x+6,369],[x,369]])
    assert len(regions['vents'])==13
    for polys in regions.values():
        for poly in polys:cv2.fillPoly(mask,[np.asarray(poly,np.int32)],0)
    finished=scene.copy();finished[mask>0]=[215,225,235]
    ok=inspect_print_safety(scene,finished,mask,q,protected=regions)
    assert ok['status']=='PASS' and ok['changed_outside_print_mask']==0
    spoiled=finished.copy();spoiled[180:200,90:96]=0
    assert inspect_print_safety(scene,spoiled,mask,q,protected=regions)['status']=='FAIL'


def test_120_jobs_stop_resume_idempotent_without_duplication(tmp_path,monkeypatch):
    runtime,registry=_build_seven_category_workspace(tmp_path,per_cat_count=1)
    batch=UnifiedV4Batch(tmp_path/'state',runtime_root=runtime,petek_registry=registry)
    selected=next(t for t in batch.discover_templates()[0] if t['category']=='03_Ahsap_Tablo')
    designs=tmp_path/'designs'
    for k in range(120):
        _write_png(designs/f'{k:03d}.png',
                   np.full((120,120,3),(k,k*3%255,k*7%255),np.uint8))
    import URETIM_V4.unified_batch as engine
    monkeypatch.setattr(engine,'_render_legacy_six_cover',
                        lambda *a,**kw:(np.full((64,48,3),155,np.uint8),{}))
    def stop(message):
        if 'ÜRETİLDİ 45:' in message:batch.request_stop()
    first=batch.run(designs,selected_uids=[selected['uid']],random_seed=45,
                    glass_effect='off',notify=stop)
    assert first['status']=='STOPPED' and first['rendered']==45
    next_run=batch.resume_last_stopped()
    assert next_run['status']=='LOCAL_READY'
    assert next_run['rendered']==75 and next_run['reused']==45
    records=batch.ledger.successful()
    assert len(records)==120==len(set(r['key'] for r in records))
    assert all(Path(r['output']).is_file() and
               petek_engine.digest(Path(r['output']))==r['output_sha'] for r in records)


def test_flask_live_route_rejects_csrf_cross_origin_and_dns_rebinding(monkeypatch):
    pytest.importorskip('flask')
    sys.path.insert(0,str(ROOT/'SABLON_V2_MIMARI'))
    import app as editor
    from core.loopback_security_v47 import token
    previous_testing=editor.app.config.get('TESTING')
    old_audit=editor.DB_STARTUP_AUDIT
    try:
        editor.app.config['TESTING']=False
        editor.DB_STARTUP_AUDIT={'ready':True}
        client=editor.app.test_client()
        mutation='/api/tools/launch/unknown-tool-name-for-security-test'
        no_token=client.post(mutation)
        assert no_token.status_code==403
        assert no_token.json['code']=='CSRF_HEADER_REQUIRED'
        origin=client.post(mutation,headers={'X-V47-CSRF':token(),'Origin':'https://evil.example'})
        assert origin.status_code==403
        assert origin.json['code']=='CROSS_ORIGIN_FORBIDDEN'
        dns=client.get('/api/session/csrf',base_url='http://remote.attacker.example:8080')
        assert dns.status_code==403
        assert dns.json['code']=='LOOPBACK_HOST_FORBIDDEN'
        valid=client.get('/api/session/csrf')
        assert valid.status_code==200 and isinstance(valid.json.get('csrf'),str)
        allowed=client.post(mutation,headers={'X-V47-CSRF':valid.json['csrf']})
        assert allowed.status_code!=403
        assert valid.headers['X-Frame-Options']=='DENY'
    finally:
        editor.app.config['TESTING']=previous_testing
        editor.DB_STARTUP_AUDIT=old_audit
