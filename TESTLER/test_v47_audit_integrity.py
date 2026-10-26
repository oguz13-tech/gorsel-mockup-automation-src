"""Focused audit regressions for historical deletion and STOP/RESUME integrity.

Only synthetic local temporary state. Never reads/writes user OneDrive paths.
"""
from pathlib import Path
import sys

import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'MERKEZ'))
sys.path.insert(0,str(ROOT/'TESTLER'))

from URETIM_V4.resume_checkpoint_v47 import snapshot_inputs
from URETIM_V4.unified_batch import UnifiedV4Batch, UnifiedV4Ledger
from PETEK_V3 import engine as petek_engine
from PETEK_V3.registry import Registry
from test_v47_pause_stop_resume import fixture_batch


def test_checkpoint_catches_quad_mask_orientation_and_occlusion_changes(tmp_path):
    image=tmp_path/'design.png'
    image.write_bytes(b'unchanged-test-binary')
    base=dict(category='03_Ahsap_Tablo',uid='original',
              source_sha='c'*64, engine_type='LEGACY_6_COVER',
              quad=[[1,1],[200,2],[201,300],[2,299]],
              physical_aspect=0.75,orientation='V',
              legacy_data={'noktalar': [[1,1],[200,2],[201,300],[2,299]],'has_occlusion':False})
    first=snapshot_inputs([image],[('LOCAL',[base])])
    assert 'approved_geometry_sha256' in first
    import copy
    for mutate in (
        lambda o: o['quad'][0].__setitem__(0,3),
        lambda o: o.__setitem__('physical_aspect',.77),
        lambda o: o.__setitem__('orientation','H'),
        lambda o: o['legacy_data'].__setitem__('has_occlusion',True),
        lambda o: o.__setitem__('mask_sha','d'*64),
    ):
        altered=copy.deepcopy(base)
        mutate(altered)
        current=snapshot_inputs([image],[('LOCAL',[altered])])
        assert current['designs']==first['designs']
        assert current['groups']==first['groups']
        assert current['approved_geometry_sha256']!=first['approved_geometry_sha256']


def test_deliberately_deleted_receipt_audit_not_missing(tmp_path):
    from URETIM_V4.unified_batch import UnifiedV4Batch
    state=tmp_path/'state'
    batch=UnifiedV4Batch(state,petek_registry=Registry(tmp_path/'petek'))
    path=batch.output/'LOCAL'/'03_Ahsap_Tablo'/'deleted.png'
    with batch.ledger.connect() as con:
        con.execute("""INSERT INTO artifact
        (key,sku,category,art_sha,template_sha,mask_sha,art_name,uid,output,output_sha,status)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        ('deleted','SKU','03_Ahsap_Tablo','a'*64,'b'*64,'c'*64,
         'x.png','wood',str(path),'d'*64,'USER_REMOVED'))
    report=batch.audit()
    entry=next(e for e in report['entries'] if e['key']=='deleted')
    assert entry['audit']=='USER_REMOVED'
    assert entry['detail']=='INTENTIONALLY_DELETED_BY_OPERATOR'


def test_resume_with_same_source_but_altered_approved_geometry_blocks(tmp_path,monkeypatch):
    batch,registry,wood,designs=fixture_batch(tmp_path,art_count=3)
    def notify(msg):
        if 'ÜRETİLDİ 1:' in msg:
            batch.request_stop()
    first=batch.run(designs,selected_uids=[wood['uid']],random_seed=713,notify=notify)
    assert first['status']=='STOPPED'
    original=batch.ledger.successful()[0]
    sha=petek_engine.digest(Path(original['output']))
    old_discover=batch.discover_templates
    def changed_approval(*args,**kwargs):
        templates,audit=old_discover(*args,**kwargs)
        for item in templates:
            if item['uid']==wood['uid']:
                item['quad'][0][0]+=2.0
        return templates,audit
    monkeypatch.setattr(batch,'discover_templates',changed_approval)
    with pytest.raises(petek_engine.MaskError,match='onaylı|mağaza'):
        batch.resume_last_stopped()
    assert petek_engine.digest(Path(original['output']))==sha
    assert len(batch.ledger.successful())==1
