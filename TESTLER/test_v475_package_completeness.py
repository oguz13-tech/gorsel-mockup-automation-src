"""Code-only Windows package guard: include runtime constants and historical launchers.

Test only a temporary local ZIP created from tracked GitHub sources. No user
templates, private ayarlar.json, SQLite files or real output PNGs are packaged.
"""
from pathlib import Path
import hashlib
import json
import sys
import zipfile
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'MERKEZ'))
from scripts.build_v46_candidate import allowed,build
from system_integrity_v475 import _package_integrity


def test_known_number_spec_is_pinned_but_user_private_json_never_included():
    assert allowed('MERKEZ/GUNLUK/INSTALLED_NUMBER_SPEC.json')
    assert not allowed('ayarlar.json')
    assert not allowed('99_SISTEM_MOTORLARI_VE_KODLAR/SISTEM_MOTORU/ayarlar.json')
    assert not allowed('MERKEZ/GUNLUK/BATCH_SELECTION.json')
    assert not allowed('SABLON_V2_MIMARI/runtime_lock.json')


def test_single_package_has_exact_sha_manifest_and_all_legacy_launchers_archived(tmp_path):
    package=build(tmp_path,source=ROOT)
    assert package.is_file()
    with zipfile.ZipFile(package) as z:
        assert z.testzip() is None
        prefix='GORSEL_V46_CANDIDATE/'
        manifest=json.loads(z.read(prefix+'SHA256_MANIFEST.json'))
        assert manifest['release']=='V4.7.5 CODE_FINAL_CANDIDATE'
        assert manifest['acceptance']=='LIVE_WINDOWS_NOT_VERIFIED'
        paths={row['path'] for row in manifest['files']}
        assert 'MERKEZ/GUNLUK/INSTALLED_NUMBER_SPEC.json' in paths
        assert 'MERKEZ/system_integrity_v475.py' in paths
        assert 'MERKEZ/bakim_merkezi_v472.py' in paths
        assert 'MERKEZ/PETEK_V3/registry.py' in paths
        for old in manifest['legacy_launchers_archived_as_text']:
            archive='LEGACY_LAUNCHERS_REFERENCE/'+old+'.reference.txt'
            assert archive in paths
            assert z.read(prefix+archive)==(ROOT/old).read_bytes()
            assert old not in paths  # Never activate or ship old launcher as executable.
        assert any(old.startswith('WINDOWS_HIZLI_BASLAT') for old in
                   manifest['legacy_launchers_archived_as_text'])
        for row in manifest['files']:
            raw=z.read(prefix+row['path'])
            assert hashlib.sha256(raw).hexdigest()==row['sha256']
            assert len(raw)==row['bytes']
        assert 'ayarlar.json' not in paths
        assert 'MERKEZ/GUNLUK/BATCH_SELECTION.json' not in paths
        assert not any(item.endswith('.sqlite3') or item.endswith('.db') for item in paths)
    root=tmp_path/'unpacked'
    with zipfile.ZipFile(package) as z:
        z.extractall(root)
    errors=[]
    result=_package_integrity(root/'GORSEL_V46_CANDIDATE',errors)
    assert not errors,errors
    assert result['files_checked']==len(manifest['files'])
    assert result['legacy_daily_v2']=='PINNED_BACKUP_AND_SELECTION_MANUAL_DEPENDENCY'


def test_package_integrity_flags_missing_real_runtime_spec(tmp_path):
    package=build(tmp_path/'created',source=ROOT)
    with zipfile.ZipFile(package) as z:
        z.extractall(tmp_path/'unpacked')
    source=tmp_path/'unpacked'/'GORSEL_V46_CANDIDATE'
    (source/'MERKEZ'/'GUNLUK'/'INSTALLED_NUMBER_SPEC.json').unlink()
    errors=[]
    _package_integrity(source,errors)
    assert 'REQUIRED_CODE_MISSING' in {x['code'] for x in errors}
    assert 'PACKAGE_FILE_MISSING' in {x['code'] for x in errors}
