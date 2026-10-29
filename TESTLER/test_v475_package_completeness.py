"""Code-only Windows package guard, both checkout and extracted distribution."""
from pathlib import Path
import hashlib
import json
import shutil
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'MERKEZ'))
from scripts.build_v46_candidate import allowed,build
from system_integrity_v475 import _package_integrity


def _distribution_root(tmp_path):
    # Actions' extracted ZIP intentionally excludes .git. Never try git
    # ls-files there: check its actual manifest and extracted bytes instead.
    if (ROOT/'SHA256_MANIFEST.json').is_file():
        return ROOT
    archive=build(tmp_path/'dist',source=ROOT)
    assert archive.is_file()
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        z.extractall(tmp_path/'unpacked')
    return tmp_path/'unpacked'/'GORSEL_V46_CANDIDATE'


def test_known_number_spec_is_pinned_but_user_private_json_never_included():
    assert allowed('MERKEZ/GUNLUK/INSTALLED_NUMBER_SPEC.json')
    assert not allowed('ayarlar.json')
    assert not allowed('99_SISTEM_MOTORLARI_VE_KODLAR/SISTEM_MOTORU/ayarlar.json')
    assert not allowed('MERKEZ/GUNLUK/BATCH_SELECTION.json')
    assert not allowed('SABLON_V2_MIMARI/runtime_lock.json')


def test_manifest_all_legacy_launchers_and_tools_inert_and_byte_exact(tmp_path):
    root=_distribution_root(tmp_path)
    manifest=json.loads((root/'SHA256_MANIFEST.json').read_text('utf-8'))
    assert manifest['release']=='V4.8.6 PETEK_BULK_MAGENTA_SAFE_REPLACEMENT'
    assert manifest['acceptance']=='WINDOWS_NOT_VERIFIED'
    assert manifest['live_user_acceptance']=='PENDING'
    paths={row['path'] for row in manifest['files']}
    assert 'MERKEZ/GUNLUK/INSTALLED_NUMBER_SPEC.json' in paths
    assert 'MERKEZ/system_integrity_v475.py' in paths
    assert 'MERKEZ/bakim_merkezi_v472.py' in paths
    assert 'MERKEZ/PETEK_V3/registry.py' in paths
    assert any(old.startswith('WINDOWS_HIZLI_BASLAT') for old
               in manifest['legacy_launchers_archived_as_text'])
    assert 'SABLON_DUZELTICI.py' in manifest['legacy_source_tools_archived_as_text']
    assert 'toplu_gorsel_linkle.py' in manifest['legacy_source_tools_archived_as_text']
    for old in manifest['legacy_launchers_archived_as_text']:
        ref='LEGACY_LAUNCHERS_REFERENCE/'+old+'.reference.txt'
        assert ref in paths and old not in paths
        if (ROOT/old).is_file():
            assert (root/ref).read_bytes()==(ROOT/old).read_bytes()
    for old in manifest['legacy_source_tools_archived_as_text']:
        ref='LEGACY_TOOLS_REFERENCE/'+old+'.reference.txt'
        assert ref in paths and old not in paths
        if (ROOT/old).is_file():
            assert (root/ref).read_bytes()==(ROOT/old).read_bytes()
    assert 'ayarlar.json' not in paths
    assert 'MERKEZ/GUNLUK/BATCH_SELECTION.json' not in paths
    assert not any(name.endswith(('.sqlite3','.db')) for name in paths)
    for item in manifest['files']:
        file=root/item['path']
        assert file.is_file()
        assert file.stat().st_size==item['bytes']
        assert hashlib.sha256(file.read_bytes()).hexdigest()==item['sha256']
    errors=[]
    integrity=_package_integrity(root,errors)
    assert not errors,errors
    assert integrity['files_checked']==len(manifest['files'])
    assert integrity['legacy_daily_v2']=='PINNED_BACKUP_AND_SELECTION_MANUAL_DEPENDENCY'


def test_real_package_integrity_detects_removed_number_spec(tmp_path):
    source=_distribution_root(tmp_path)
    tampered=tmp_path/'tampered'
    shutil.copytree(source,tampered)
    (tampered/'MERKEZ'/'GUNLUK'/'INSTALLED_NUMBER_SPEC.json').unlink()
    errors=[]
    _package_integrity(tampered,errors)
    assert 'REQUIRED_CODE_MISSING' in {x['code'] for x in errors}
    assert 'PACKAGE_FILE_MISSING' in {x['code'] for x in errors}


def test_old_pinned_daily_is_explicitly_blocked_without_missing_user_selection(tmp_path):
    import merkez_saglik
    report=merkez_saglik.report(platform='nt',userprofile=str(tmp_path))
    assert report['legacy_ready'] is False
    assert any('sabit seçim dosyası' in msg for msg in report['legacy_missing'])
    # Seven-category production is the current active engine.
    assert report['v42_installed_code_ready'] is True
