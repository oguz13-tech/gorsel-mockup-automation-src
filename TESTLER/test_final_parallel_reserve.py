"""Concurrent SQLite reserve is single-record and fail-closed on identity conflict."""
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'MERKEZ'))
from PETEK_V3.batch import Ledger
from PETEK_V3 import engine


def sample(root):
    return dict(key='item-1',sku='PDK-LOCAL-ABCD',art_sha='art1',
                template_sha='source1',mask_sha='mask1',
                art_name='example.png',uid='SomePetek',
                output=str(root/'item.png'))


def test_parallel_32_reservations_only_one_persistent_row(tmp_path):
    ledger=Ledger(tmp_path)
    fields=sample(tmp_path)
    def work(_):
        return ledger.reserve(fields)['status']
    with ThreadPoolExecutor(max_workers=12) as pool:
        statuses=list(pool.map(work,range(32)))
    assert statuses==['PENDING']*32
    with ledger.connect() as con:
        assert con.execute('SELECT COUNT(*) FROM artifact').fetchone()[0]==1
    assert ledger.file.exists()


def test_duplicate_identifier_with_different_source_never_adopted(tmp_path):
    ledger=Ledger(tmp_path);fields=sample(tmp_path)
    ledger.reserve(fields)
    fake=dict(fields,template_sha='source2')
    with pytest.raises(engine.MaskError,match='cakisiyor'):
        ledger.reserve(fake)
    with ledger.connect() as con:
        row=con.execute('SELECT template_sha FROM artifact').fetchone()
    assert row[0]=='source1'
