"""Verified ledger tagging of historical, owner-deleted outputs. Synthetic only."""
from pathlib import Path
import json
import sqlite3
import sys
import hashlib
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'MERKEZ'))
from URETIM_V4.deleted_receipts_v474 import (candidate_rows,save_plan,
    mark_selected,CONFIRM)
from URETIM_V4.final_guard_v44 import _output_audit

def make_ledger(tmp_path, deleted=35, existing=2):
    state=tmp_path/'State'
    images=state/'uretilen_gorseller'/'LOCAL'/'03_Ahsap_Tablo'
    images.mkdir(parents=True)
    db=state/'v4_ortak_uretim.sqlite3'
    with sqlite3.connect(db) as con:
        con.execute("""CREATE TABLE artifact(key TEXT PRIMARY KEY,sku TEXT,category TEXT,
           status TEXT,output TEXT, output_sha TEXT,message TEXT DEFAULT '',
           updated TEXT DEFAULT CURRENT_TIMESTAMP)""")
        for i in range(deleted+existing):
            path=images/f'{i}.png'
            if i>=deleted:path.write_bytes(b'valid'+str(i).encode())
            con.execute("""INSERT INTO artifact
              (key,sku,category,status,output,output_sha) VALUES(?,?,?,?,?,?)""",
              (f'job_{i:03d}',f'J{i}','03_Ahsap_Tablo','RENDERED',str(path),
               hashlib.sha256((b'valid'+str(i).encode())).hexdigest()))
    return state,db


def test_readonly_plan_is_not_auto_tagged(tmp_path):
    state,db=make_ledger(tmp_path)
    before=db.read_bytes()
    plan=candidate_rows(state)
    assert plan['count']==35
    assert len(plan['rendered_missing_candidates'])==35
    assert db.read_bytes()==before
    assert plan['status_counts']=={'RENDERED':37}


def test_explicit_35_mark_and_backup_leaves_other_rendered(tmp_path,monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA',str(tmp_path/'local'))
    state,db=make_ledger(tmp_path)
    plan=save_plan(candidate_rows(state))
    keys=[x['key'] for x in json.loads(plan.read_text())['rendered_missing_candidates']]
    with pytest.raises(PermissionError):
        mark_selected(plan,keys,'WRONG')
    result=mark_selected(plan,keys,CONFIRM)
    assert result['marked']==35 and result['images_deleted']==0
    assert Path(result['backup']).is_file()
    with sqlite3.connect(db) as con:
        counts=dict(con.execute('SELECT status,COUNT(*) FROM artifact GROUP BY status').fetchall())
    assert counts=={'RENDERED':2,'USER_REMOVED':35}
    report=_output_audit(db,state/'uretilen_gorseller')
    assert report['user_removed']==35 and report['missing']==0
    assert report['verified']==2
    with pytest.raises(RuntimeError,match='CHANGED'):
        mark_selected(plan,keys,CONFIRM)


def test_absent_output_is_not_conclusive_without_exact_confirmation(tmp_path,monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA',str(tmp_path/'local'))
    state,db=make_ledger(tmp_path,deleted=34,existing=1)
    plan=save_plan(candidate_rows(state))
    keys=[r['key'] for r in json.loads(plan.read_text())['rendered_missing_candidates']]
    with pytest.raises(ValueError,match='COUNT_UNEXPECTED'):
        mark_selected(plan,keys,CONFIRM)
    with sqlite3.connect(db) as con:
        assert con.execute('SELECT COUNT(*) FROM artifact WHERE status=?',
                           ('RENDERED',)).fetchone()[0]==35


def test_nonexistent_external_output_or_sha_mismatch_not_tagged(tmp_path):
    state,db=make_ledger(tmp_path,deleted=1,existing=1)
    with sqlite3.connect(db) as con:
        con.execute("UPDATE artifact SET output=? WHERE key='job_000'",
                    (str(tmp_path/'not-an-output.png'),))
    assert candidate_rows(state)['count']==0


def test_reappeared_image_blocks_tagging(tmp_path,monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA',str(tmp_path/'local'))
    state,db=make_ledger(tmp_path,deleted=1,existing=1)
    plan=save_plan(candidate_rows(state))
    path=Path(json.loads(plan.read_text())['rendered_missing_candidates'][0]['output'])
    path.write_bytes(b'file recovered after report')
    with pytest.raises(RuntimeError,match='CHANGED'):
        mark_selected(plan,['job_000'],CONFIRM,expected_count=1)
    with sqlite3.connect(db) as con:
        assert con.execute("SELECT status FROM artifact WHERE key='job_000'").fetchone()[0]=='RENDERED'
