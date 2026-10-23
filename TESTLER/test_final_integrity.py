"""Final factory regression: collision, geometry identity and read-only audit."""
import pathlib
import sys
import cv2
import numpy as np
import pytest
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'MERKEZ'))
from PETEK_V3 import engine
from PETEK_V3.batch import Batch
from PETEK_V3.registry import Registry
from PETEK_V3.safety_audit import receipt_identity


def prepared(tmp_path):
    reg=Registry(tmp_path/'private'); art_dir=tmp_path/'art';art_dir.mkdir()
    src=tmp_path/'photo.png'
    assert cv2.imwrite(str(src),np.full((400,500,3),220,np.uint8))
    assert cv2.imwrite(str(art_dir/'art.png'),np.full((400,500,3),160,np.uint8))
    quad=[[35,35],[465,35],[465,370],[35,370]]
    mask=engine.polygon_mask((400,500),np.asarray(quad,np.float32));mask[100:300,90:105]=0
    reg.save('PetekSafeTest',src,quad,mask,1.12)
    reg.approve('PetekSafeTest','Reviewer','I_VISUALLY_CHECKED_VENTS_ARCHES_FLOOR')
    return reg,art_dir


def test_geometry_aspect_and_lighting_all_change_key(tmp_path):
    reg,designs=prepared(tmp_path);p,_=reg.get('PetekSafeTest')
    art_sha=engine.digest(designs/'art.png')
    kw=dict(group='LOCAL',placement='cover',lighting='natural',recipe=engine.RECIPE)
    k1,_=receipt_identity(p,art_sha,**kw)
    k_repeat,_=receipt_identity(p,art_sha,**kw)
    assert k1==k_repeat
    altered=dict(p,quad=[list(a) for a in p['quad']]);altered['quad'][0][0]+=1
    assert receipt_identity(altered,art_sha,**kw)[0]!=k1
    altered2=dict(p,physical_aspect=p['physical_aspect']+.01)
    assert receipt_identity(altered2,art_sha,**kw)[0]!=k1
    assert receipt_identity(p,art_sha,**dict(kw,lighting='strong'))[0]!=k1
    assert receipt_identity(p,art_sha,**dict(kw,placement='contain'))[0]!=k1


def test_receipt_missing_and_corrupt_never_marked_verified(tmp_path):
    reg,designs=prepared(tmp_path)
    b=Batch(reg);result=b.run(designs,['PetekSafeTest'],max_jobs=1)
    assert result['rendered']==1
    report=b.audit();assert report['summary']['verified']==1
    with b.ledger.connect() as db:
        row=db.execute('SELECT output FROM artifact').fetchone()
        output=pathlib.Path(row['output'])
    before=output.read_bytes()
    output.write_bytes(b'corrupt')
    check=b.audit()
    assert check['summary']['verified']==0
    assert check['entries'][0]['detail']=='OUTPUT_SHA_MISMATCH'
    # Re-run MUST NOT overwrite or silently adopt corrupt existing output.
    with pytest.raises(engine.MaskError, match='cikti SHA'):
        Batch(reg).run(designs,['PetekSafeTest'],max_jobs=1)
    assert output.read_bytes()==b'corrupt'
    output.write_bytes(before)
    assert Batch(reg).audit()['summary']['verified']==1


def test_unfinished_row_and_wrong_directory_rejected(tmp_path):
    reg,designs=prepared(tmp_path)
    batch=Batch(reg);p,_=reg.get('PetekSafeTest')
    sha=engine.digest(designs/'art.png')
    key,_=receipt_identity(p,sha,group='LOCAL',placement='cover',lighting='natural',recipe=engine.RECIPE)
    fields=dict(key=key[:24],sku='PDK-LOCAL-'+key[:18].upper(),art_sha=sha,
                template_sha=p['source_sha'],mask_sha=p['mask_sha'],art_name='art.png',
                uid=p['uid'],output=str(reg.output/'LOCAL'/'pending.png'))
    batch.ledger.reserve(fields)
    report=batch.audit()
    assert report['summary']['review_required']==1
    assert report['entries'][0]['detail']=='OUTPUT_MISSING'
    # Tampered output path outside dedicated root is never accepted.
    with batch.ledger.connect() as db:
        db.execute('UPDATE artifact SET output=? WHERE key=?',(str(tmp_path/'elsewhere.png'),key[:24]))
    assert batch.audit()['entries'][0]['detail']=='UNSAFE_OUTPUT_PATH'
