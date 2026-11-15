"""Tasarım Yönetimi + Mağaza Profilleri modülleri — izole (tmp) testler.

Canlı veriye dokunulmaz: HAM klasörü, HamDesign kayıt veritabanı ve
store_profiles_v47.json yalnız geçici klasörlerde kurulur.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'MERKEZ'))

import tasarim_yonetimi_v1 as designs  # noqa: E402
import magaza_profilleri_v1 as stores  # noqa: E402
from URETIM_V4.store_profiles_v47 import StoreProfiles, key_for  # noqa: E402

SHA_A = 'a' * 64
SHA_B = 'b' * 64
SHA_C = 'c' * 64


def _png(path: Path) -> Path:
    from PIL import Image
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new('RGB', (8, 8), (120, 80, 200)).save(path)
    return path


# ------------------------------------------------------------------ tasarım

def test_ham_number_parsing():
    assert designs.ham_number('Ham12.png') == 12
    assert designs.ham_number('HAM7.JPEG') == 7
    assert designs.ham_number('Ham0.png') is None
    assert designs.ham_number('Ham1a.png') is None
    assert designs.ham_number('Yatay_Tasarim001.png') is None


def test_list_designs_order_and_filter(tmp_path):
    ham = tmp_path / designs.FOLDER
    _png(ham / 'Ham10.png')
    _png(ham / 'Ham2.png')
    _png(ham / 'Yatay_Tasarim001.png')
    (ham / 'notlar.txt').write_text('x', encoding='utf-8')
    (ham / 'bozuk.bmp').write_bytes(b'BM')
    rows = designs.list_designs(tmp_path)
    names = [r['name'] for r in rows]
    assert names == ['Ham2.png', 'Ham10.png', 'Yatay_Tasarim001.png']
    assert rows[0]['ham_number'] == 2 and rows[1]['ham_number'] == 10
    assert rows[2]['ham_number'] is None


def test_read_registry_roundtrip_and_summarize(tmp_path):
    runtime = tmp_path / 'runtime'
    ham = runtime / designs.FOLDER
    _png(ham / 'Ham1.png')
    _png(ham / 'Ham2.png')
    _png(ham / 'Ham3.png')
    assert designs.read_registry(runtime, tmp_path / 'state') is None
    db = designs.registry_path(runtime, tmp_path / 'state')
    db.parent.mkdir(parents=True)
    con = sqlite3.connect(db)
    con.executescript("""CREATE TABLE meta(id INTEGER PRIMARY KEY CHECK(id=1),
                          high INTEGER NOT NULL CHECK(high>=0), initialized INTEGER NOT NULL);
                       CREATE TABLE history(number INTEGER PRIMARY KEY, path TEXT NOT NULL,
                          source_name TEXT NOT NULL, sha TEXT NOT NULL, size INTEGER NOT NULL,
                          mtime_ns INTEGER NOT NULL, status TEXT NOT NULL,
                          created_at TEXT DEFAULT CURRENT_TIMESTAMP);""")
    con.execute("INSERT INTO meta(id, high, initialized) VALUES (1, 42, 1)")
    con.execute("INSERT INTO history VALUES (1, 'Ham1.png', 'a.png', 'x', 1, 1, 'ACTIVE', 'now')")
    con.execute("INSERT INTO history VALUES (2, 'Ham2.png', 'b.png', 'y', 1, 1, 'ACTIVE', 'now')")
    con.commit(); con.close()
    registry = designs.read_registry(runtime, tmp_path / 'state')
    assert registry['high'] == 42 and registry['active'] == 2
    rows = designs.list_designs(runtime)
    summary = designs.summarize(rows, registry, None)
    assert summary['total'] == 3 and summary['registered'] == 2
    assert summary['unregistered'] == 1 and summary['pool_high'] == 42


def test_read_registry_missing_file_returns_none(tmp_path):
    assert designs.read_registry(tmp_path / 'nope', tmp_path / 'state') is None


# ------------------------------------------------------------------ mağaza

def _approved(uid: str, sha: str, category: str = '06_Petek_Kapama') -> dict:
    return {'uid': uid, 'category': category, 'source_sha': sha, 'source': ''}


def _config_with(store_map: dict[str, list[str]]) -> dict:
    return {'schema': 1, 'stores':
            {name: {'templates': list(keys)} for name, keys in store_map.items()}}


def test_parse_template_key_valid_and_invalid():
    parsed = stores.parse_template_key('06_Petek_Kapama:Petek_Dolabi_037@' + SHA_A)
    assert parsed == {'category': '06_Petek_Kapama', 'uid': 'Petek_Dolabi_037', 'sha': SHA_A}
    for bad in ('', 'nokey', 'cat:uid@xyz', ':uid@' + SHA_A, 'cat:@' + SHA_A,
                  'cat:u\nid@' + SHA_A, '06_Petek_Kapama:uid@' + 'A' * 63):
        with pytest.raises(ValueError):
            stores.parse_template_key(bad)


def test_short_code_status_default_and_configured():
    assert stores.short_code_status('OmzHome', {'templates': []})['effective'] == 'OMZ'
    assert stores.short_code_status('adeno', {'templates': []})['effective'] == 'ADN'
    assert stores.short_code_status('wudie', {'short_code': 'wd1', 'templates': []})['effective'] == 'WD1'
    assert stores.short_code_status('BilinmeyenMagaza', {'templates': []})['defined'] is False
    assert stores.short_code_status('adeno', {'short_code': '!', 'templates': []})['error']


def test_validate_clean_config_passes():
    key = '06_Petek_Kapama:Petek_Dolabi_037@' + SHA_A
    config = _config_with({'adeno': [key], 'wudie': ['06_Petek_Kapama:Petek_Dolabi_038@' + SHA_B]})
    result = stores.validate_store_profiles(config)
    assert result['ok'], result['problems']
    assert result['stores']['adeno']['categories'] == {'06_Petek_Kapama': 1}


def test_validate_flags_cross_store_reuse_and_duplicates():
    key = '06_Petek_Kapama:Petek_Dolabi_037@' + SHA_A
    config = _config_with({'adeno': [key], 'wudie': [key]})  # aynı anahtar iki mağazada
    result = stores.validate_store_profiles(config)
    kinds = {p['kind'] for p in result['problems']}
    assert 'STORE_TEMPLATE_ASSIGNED_TO_MULTIPLE_STORES' in kinds
    assert not result['ok']
    # aynı kaynak SHA, farklı uid anahtarı iki mağazada
    config2 = _config_with({'adeno': ['06_Petek_Kapama:A@' + SHA_A],
                            'wudie': ['06_Petek_Kapama:B@' + SHA_A]})
    kinds2 = {p['kind'] for p in stores.validate_store_profiles(config2)['problems']}
    assert 'STORE_SOURCE_IMAGE_REUSED_ACROSS_STORES' in kinds2
    # aynı mağazada tekrarlı anahtar
    config3 = _config_with({'adeno': [key, key]})
    assert any(p['kind'] == 'DUPLICATE_KEY_IN_STORE'
               for p in stores.validate_store_profiles(config3)['problems'])


def test_validate_flags_unknown_category_and_malformed():
    config = _config_with({'adeno': ['09_Bilinmeyen:X@' + SHA_A, 'bozuk-anahtar']})
    kinds = {p['kind'] for p in stores.validate_store_profiles(config)['problems']}
    assert 'BILINMEYEN_KATEGORI' in kinds and 'KEY_INVALID' in kinds


def test_validate_short_code_conflict_between_stores():
    config = _config_with({'adeno': [], 'wudie': []})
    config['stores']['adeno']['short_code'] = 'ABC'
    config['stores']['wudie']['short_code'] = 'abc'
    kinds = {p['kind'] for p in stores.validate_store_profiles(config)['problems']}
    assert 'MAGAZA_KISA_KODU_CAKISMASI' in kinds


def test_validate_stale_against_approved_keys():
    key = '06_Petek_Kapama:Petek_Dolabi_037@' + SHA_A
    config = _config_with({'adeno': [key]})
    staleless = stores.validate_store_profiles(config, {'other'})
    assert staleless['stores']['adeno']['stale'] == 1
    exact = stores.validate_store_profiles(config, {key})
    assert exact['stores']['adeno']['stale'] == 0
    blind = stores.validate_store_profiles(config, None)
    assert blind['approved_checked'] is False


def test_store_profiles_save_edit_reopen_roundtrip(tmp_path):
    state = tmp_path / 'state'
    mgr = StoreProfiles(state)
    mgr.add_store('kobold')
    item = _approved('Petek_Dolabi_037', SHA_A)
    other = _approved('Petek_Dolabi_038', SHA_B)
    mgr.assign('kobold', [item, other], all_approved=[item, other])
    mgr.set_short_code('kobold', 'KBD')
    # yeniden aç: havuz ve ayar aynen korunmalı
    fresh = StoreProfiles(state)
    cfg = fresh.load()
    assert sorted(cfg['stores']['kobold']['templates']) == sorted(
        [key_for(item), key_for(other)])
    assert cfg['stores']['kobold']['short_code'] == 'KBD'
    assert fresh.short_code('kobold') == 'KBD'
    # kayıt sırasında yedek oluşur
    backups = list(state.glob('store_profiles_v47.backup_*.json'))
    assert backups, 'atomik kayıt .backup_* kopyası üretmeli'


def test_cross_store_assignment_and_short_code_isolation(tmp_path):
    state = tmp_path / 'state'
    mgr = StoreProfiles(state)
    mgr.add_store('magaza1')
    mgr.add_store('magaza2')
    item = _approved('Petek_Dolabi_037', SHA_A)
    mgr.assign('magaza1', [item], all_approved=[item])
    with pytest.raises(ValueError):
        mgr.assign('magaza2', [item], all_approved=[item])
    mgr.set_short_code('magaza1', 'AAA')
    with pytest.raises(ValueError):
        mgr.set_short_code('magaza2', 'AAA')
    # magaza2 havuzu ve ayarı magaza1'in editinden etkilenmez
    cfg = StoreProfiles(state).load()
    assert cfg['stores']['magaza2']['templates'] == []
    assert cfg['stores']['magaza1']['templates'] == [key_for(item)]


def test_live_profile_path_not_touched(monkeypatch, tmp_path):
    """Test varsayılanının canlı store_profiles_v47.json'a yazmadığını doğrula."""
    monkeypatch.setenv('V4_UNIFIED_LOCAL_STATE', str(tmp_path / 'isolated'))
    assert str(stores.default_state_root()).startswith(str(tmp_path))
