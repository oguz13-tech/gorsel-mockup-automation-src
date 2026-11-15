"""One-click grouped operator check is read-only and does not mutate workspace."""
from __future__ import annotations
import json
from pathlib import Path
import sqlite3
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'MERKEZ'))
from uretim_toplu_kabul_v479 import run


def test_grouped_windows_report_without_data_mutation(tmp_path):
    workspace=tmp_path/'Main'
    db=workspace/'SABLON_V2_MIMARI'/'ayarlar.db'
    db.parent.mkdir(parents=True)
    with sqlite3.connect(db) as conn:conn.execute('CREATE TABLE approvals (name TEXT)')
    wifi=workspace/'2_SABLON_HAVUZU'/'01_Wifi_Kutusu'
    wifi.mkdir(parents=True)
    photo=wifi/'Wifi_Kutusu_123.png'
    photo.write_bytes(b'synthetic-no-write')
    petek=workspace/'2_SABLON_HAVUZU'/'Petek_Dolabi'
    petek.mkdir(parents=True)
    petek_photo=petek/'Magenta_456.png'
    petek_photo.write_bytes(b'synthetic-petek')
    private=tmp_path/'Local'/'GorselMockup'/'PetekV3'/'profiles'
    private.mkdir(parents=True)
    import hashlib
    sha=hashlib.sha256(petek_photo.read_bytes()).hexdigest()
    profile=private/'Mask123.json'
    profile.write_text(json.dumps({'uid':'Mask123','source_sha':sha,'status':'APPROVED'}),'utf-8')
    originals={p:p.read_bytes() for p in (db,photo,petek_photo,profile)}
    text,details=run(root=workspace,registry_root=private.parent,
                     probe=lambda:{'success':True,'items':[{}],
                                   'scanned_photos':1,'runtime_root':str(workspace)})
    assert 'PASS | SQLite quick_check' in text
    assert '1 onaylı registry profili, 1 SHA eşleşen' in text
    assert details['results']['Tek 8080 PETEK servisi']['ok'] is True
    assert all(p.read_bytes()==data for p,data in originals.items())
    assert sorted(str(p.relative_to(tmp_path)) for p in tmp_path.rglob('*') if p.is_file())==sorted(
      str(p.relative_to(tmp_path)) for p in originals)


def test_grouped_launcher_in_package_source():
    file=ROOT/'TOPLU_URETIM_KABUL_WINDOWS.bat'
    assert file.is_file()
    text=file.read_text('utf-8')
    assert 'uretim_toplu_kabul_v479.py' in text
    assert 'TOPLU_URETIM_KABUL_WINDOWS' not in text.splitlines()[0]
