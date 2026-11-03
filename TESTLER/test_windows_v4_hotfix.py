"""Isolated regressions for the reported November 2 production failures."""
import json
import os
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'MERKEZ'))
sys.path.insert(0, str(ROOT/'TESTLER'))
from URETIM_V4.unified_batch import UnifiedV4Batch, UnifiedV4Ledger
from URETIM_V4.crash_recovery import _is_pid_alive
from PETEK_V3 import engine
from test_v40_unified_seven_category import _build_seven_category_workspace, _write_png


def reserve(ledger, output, key='test'):
    fields = dict(key=key, sku=key, category='06_Petek_Kapama', art_sha='a'*64,
                  template_sha='b'*64, mask_sha='c'*64, art_name='art.png',
                  uid='template', output=str(output))
    ledger.reserve(fields)
    return fields


def test_retry_unwritten_retains_original_reason(tmp_path):
    ledger=UnifiedV4Ledger(tmp_path/'state')
    output=tmp_path/'state'/'outputs'/'new.png'
    reserve(ledger,output)
    ledger.quarantine('test','original render failure')
    row=ledger.retry_unwritten('test',output.parent)
    assert row['status']=='PENDING'
    with ledger.connect() as con:
        assert con.execute('SELECT previous_message FROM retry_history').fetchone()[0]=='original render failure'
    assert not output.exists()


@pytest.mark.parametrize('status,sha,exists',[
    ('REVIEW_REQUIRED','',True), ('REVIEW_REQUIRED','d'*64,False),
    ('RENDERED','d'*64,False), ('USER_REMOVED','',False)])
def test_retry_does_not_reset_existing_or_receipted_work(tmp_path,status,sha,exists):
    ledger=UnifiedV4Ledger(tmp_path/'state')
    output=tmp_path/'state'/'outputs'/'keep.png'
    reserve(ledger,output)
    if exists:
        output.parent.mkdir();output.write_bytes(b'keep partial file')
    with ledger.connect() as con:
        con.execute('UPDATE artifact SET status=?,output_sha=?',(status,sha))
    assert ledger.retry_unwritten('test',output.parent)['status']==status
    if exists:assert output.read_bytes()==b'keep partial file'


def test_retry_rejects_outside_output_root(tmp_path):
    ledger=UnifiedV4Ledger(tmp_path/'state')
    reserve(ledger,tmp_path/'outside.png')
    ledger.quarantine('test','keep')
    assert ledger.retry_unwritten('test',tmp_path/'outputs')['status']=='REVIEW_REQUIRED'


def test_repeated_missing_output_export_preserves_reports(tmp_path):
    batch=UnifiedV4Batch(tmp_path/'state')
    output=batch.output/'missing.png'
    reserve(batch.ledger,output)
    with batch.ledger.connect() as con:
        con.execute("UPDATE artifact SET status='RENDERED',output_sha=?",('d'*64,))
    legacy=batch.reports/'ORTAK_7_KATEGORI_SHA_INCELEME.json'
    legacy.write_bytes(b'previous immutable report')
    first=batch.export()
    second=batch.export()
    assert first==second and first[2]==0
    reports=list(batch.reports.glob('ORTAK_7_KATEGORI_SHA_INCELEME_*.json'))
    assert len(reports)==2
    assert legacy.read_bytes()==b'previous immutable report'
    assert all(json.loads(p.read_text(encoding='utf-8'))['status']=='REVIEW_REQUIRED' for p in reports)


def test_geometry_failure_does_not_poison_ledger_or_stop_other_templates(tmp_path,monkeypatch):
    runtime,registry=_build_seven_category_workspace(tmp_path,per_cat_count=1)
    designs=tmp_path/'designs'
    _write_png(designs/'art.png',np.full((200,300,3),(40,90,180),np.uint8))
    import PETEK_V3.petek_slot_geometry_vnext as geometry
    def ambiguous(*args,**kwargs):
        raise engine.MaskError('PETEK_IZGARA_KONUMU_BELIRSIZ: source=10 mask=1')
    monkeypatch.setattr(geometry,'measure_real_vents',ambiguous)
    batch=UnifiedV4Batch(tmp_path/'state',runtime_root=runtime,petek_registry=registry)
    result=batch.run(designs,group='TEST',petek_slot_mode='orta',lighting='off')
    assert result['rendered']==6 and result['rejected']==1
    assert result['status']=='PARTIAL'
    assert Path(result['error_report']).is_file()
    with batch.ledger.connect() as con:
        assert con.execute("SELECT count(*) FROM artifact WHERE category='06_Petek_Kapama'").fetchone()[0]==0
    again=batch.run(designs,group='TEST',petek_slot_mode='orta',lighting='off')
    assert again['reused']==6 and again['rejected']==1


@pytest.mark.skipif(os.name!='nt',reason='Windows process API regression')
def test_windows_pid_check_never_terminates_running_process():
    child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'],
                           creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        assert _is_pid_alive(child.pid)
        assert _is_pid_alive(child.pid)
        assert child.poll() is None
    finally:
        child.terminate();child.wait(timeout=10)
    assert not _is_pid_alive(child.pid)
