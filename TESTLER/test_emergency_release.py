"""P0 regression tests for release safety: no false success, malformed identity,
no accidental activation of legacy six categories without their live assets."""
from pathlib import Path
import sys
import cv2
import numpy as np
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'MERKEZ'))
from PETEK_V3 import engine
from PETEK_V3.batch import Ledger
from PETEK_V3.safety_audit import receipt_identity
import merkez_saglik


def test_cannot_complete_without_real_output_file(tmp_path):
    (tmp_path/'DB').mkdir()
    ledger=Ledger(tmp_path/'DB');fake=tmp_path/'missing.png'
    entry=dict(key='safetysample',sku='SKU',art_sha='a',template_sha='s',mask_sha='m',
               art_name='art.png',uid='PetekMask',output=str(fake))
    ledger.reserve(entry)
    with pytest.raises(engine.MaskError,match='URETIM_CIKTISI_YOK'):
        ledger.complete('safetysample','1'*64)
    with ledger.connect() as db:
        assert db.execute('SELECT status FROM artifact WHERE key=?',('safetysample',)).fetchone()[0]=='PENDING'
    cv2.imwrite(str(fake),np.full((160,160,3),128,np.uint8))
    with pytest.raises(engine.MaskError,match='SHA_DOGRULANAMADI'):
        ledger.complete('safetysample','0'*64)
    assert ledger.connect().execute('SELECT status FROM artifact WHERE key=?',('safetysample',)).fetchone()[0]=='PENDING'
    ledger.complete('safetysample',engine.digest(fake))
    assert ledger.connect().execute('SELECT status FROM artifact WHERE key=?',('safetysample',)).fetchone()[0]=='RENDERED'


def test_invalid_geometry_fails_closed():
    p={'uid':'test','source_sha':'source','mask_sha':'mask','physical_aspect':1.11,
       'quad':[[0,0],[10,0],[10,10],[0,10]]}
    base=dict(group='LOCAL',placement='cover',lighting='natural',recipe=engine.RECIPE)
    reference,_=receipt_identity(p,'art',**base)
    assert receipt_identity(p,'art',**base)[0]==reference
    with pytest.raises(engine.MaskError):
        receipt_identity(dict(p,physical_aspect=float('nan')),'art',**base)
    for changed in [dict(p,quad=[[0,0],[10,float('inf')],[10,10],[0,10]]),
                    dict(p,quad=[[0,0],[10,0],[10,10],[0,float('nan')]])]:
        with pytest.raises(engine.MaskError):receipt_identity(changed,'art',**base)


def test_health_does_not_claim_legacy_ready_without_assets(tmp_path):
    status=merkez_saglik.report(platform='nt',userprofile=str(tmp_path/'fictional'))
    assert not status['legacy_ready']
    assert status['legacy_missing']
    assert status['legacy_assets_are_external']


def test_distribution_contains_all_launchers():
    for path in ('WINDOWS_HIZLI_BASLAT.bat','BASLAT_WINDOWS.bat','KURULUM_WINDOWS.bat',
                 'MERKEZ/merkez.py','MERKEZ/GUNLUK/run.py','MERKEZ/PETEK_V3/gui.py',
                 'MERKEZ/PETEK_V3/batch.py','MERKEZ/merkez_saglik.py'):
        assert (ROOT/path).is_file(),path
