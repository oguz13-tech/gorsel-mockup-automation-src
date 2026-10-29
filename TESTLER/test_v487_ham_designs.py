"""V4.8.7 HAM BASKI TASARIMLARI: recursive auto naming and never-reuse IDs.

Only synthetic tmp_path photos; NO operator images/DBs are opened.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import sys
import pytest
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'MERKEZ'))
from ham_designs_v487 import HamDesignVault,FOLDER,RECEIPT
from URETIM_V4.unified_batch import iter_designs
from URETIM_V4.store_identity_v485 import store_codes,design_number,filename


def pic(path:Path,color='red'):
    path.parent.mkdir(parents=True,exist_ok=True)
    Image.new('RGB',(41,29),color).save(path)


def vault(tmp_path):
    root=tmp_path/'Ana'
    root.mkdir()
    return root,HamDesignVault(root,local_state=tmp_path/'LOCAL')


def stable(v):
    v.sweep(stable_seconds=0)
    return v.sweep(stable_seconds=0)


def test_recursive_import_after_existing_ham300_with_native_jpeg_png_webp(tmp_path):
    root=tmp_path/'Ana';root.mkdir()
    ham=root/FOLDER
    pic(ham/'Eskiler'/'Ham300.jpg',color='green')
    pic(ham/'new_offer.png',color='blue')
    pic(ham/'Koleksiyon_A'/'kedi.webp',color='yellow')
    pic(ham/'Koleksiyon_B'/'cam.jpeg',color='purple')
    before={p:p.read_bytes() for p in ham.rglob('*') if p.is_file()}
    v=HamDesignVault(root,local_state=tmp_path/'LOCAL')
    first=v.audit()
    assert first['high']==300
    outcome=stable(v)
    assert [x['number'] for x in outcome['renamed']]==[301,302,303]
    for x in outcome['renamed']:
        original=ham/x['old']
        new=ham/x['new']
        assert not original.exists() and new.read_bytes()==before[original]
        assert new.suffix.lower()==original.suffix.lower()
    assert (ham/'Eskiler'/'Ham300.jpg').read_bytes()==before[ham/'Eskiler'/'Ham300.jpg']
    assert v.audit()['high']==303
    assert v.validate_for_production()['unregistered']==[]
    assert len(list(iter_designs(ham)))==4


def test_never_recycle_deleted_used_number_after_restart(tmp_path):
    root,v=vault(tmp_path)
    ham=root/FOLDER
    pic(ham/'fresh.jpg')
    assert stable(v)['high']==1
    (ham/'Ham1.jpg').unlink()
    pic(ham/'new.png','green')
    again=HamDesignVault(root,local_state=tmp_path/'LOCAL')
    result=stable(again)
    assert result['high']==2
    assert (ham/'Ham2.png').exists() and not (ham/'Ham1.png').exists()
    assert json.loads((ham/RECEIPT).read_text('utf-8'))['never_reuse_up_to']==2
    assert any(x['type']=='HAM_REGISTERED_FILE_MISSING' for x in result['warnings'])


def test_same_ham_number_multiple_extensions_and_nested_detected(tmp_path):
    root=tmp_path/'Ana';root.mkdir()
    ham=root/FOLDER
    pic(ham/'A'/'Ham23.png','red')
    pic(ham/'B'/'Ham23.jpg','green')
    with pytest.raises(ValueError,match='HAM_AYNI_NUMARA_FARKLI_DOSYA'):
        HamDesignVault(root,local_state=tmp_path/'LOCAL')
    assert (ham/'A'/'Ham23.png').exists() and (ham/'B'/'Ham23.jpg').exists()


def test_new_files_same_stem_different_extensions_are_warned_and_not_renamed(tmp_path):
    root,v=vault(tmp_path);ham=root/FOLDER
    pic(ham/'outer.png','red');pic(ham/'Alt Klasor'/'outer.jpg','blue')
    result=stable(v)
    assert result['renamed']==[]
    assert sum(x['type']=='HAM_SAME_NAME_DIFFERENT_EXTENSION'
               for x in result['warnings'])==2
    assert (ham/'outer.png').exists()
    assert (ham/'Alt Klasor'/'outer.jpg').exists()
    pic(ham/'different.webp','green')
    result=stable(v)
    assert [x['number'] for x in result['renamed']]==[1]
    assert (ham/'Ham1.webp').exists()


def test_copied_identical_bytes_are_not_assigned_a_second_number(tmp_path):
    root,v=vault(tmp_path);ham=root/FOLDER
    pic(ham/'blue.jpg','blue')
    stable(v)
    (ham/'same_pic.jpg').write_bytes((ham/'Ham1.jpg').read_bytes())
    result=stable(v)
    assert not result['renamed']
    assert any(x['type']=='HAM_EXACT_DUPLICATE_BYTES' for x in result['warnings'])
    assert v.audit()['high']==1
    assert (ham/'same_pic.jpg').is_file()


def test_import_does_not_reencode_and_supports_store_product_codes(tmp_path):
    root,v=vault(tmp_path);ham=root/FOLDER
    pic(ham/'Arsiv'/'design.png','red')
    stable(v)
    image=next(ham.rglob('Ham1.png'))
    assert design_number(image)=='Ham1'
    codes=store_codes('Ham1','M5','01_Wifi_Kutusu')
    assert codes['sku']=='Ham1-WifiKutusu-M5'
    assert codes['model']=='Ham1-M5-WifiKutusu'
    assert filename('Ham1','M5','01_Wifi_Kutusu','Wifi_035')==(
           'Ham1__M5__WifiKutusu__TPL035__V01.png')


def test_partial_file_is_not_renamed_until_complete_and_stable(tmp_path):
    root,v=vault(tmp_path);ham=root/FOLDER
    path=ham/'incoming.png'
    path.write_bytes(b'fake partial PNG')
    assert v.sweep(stable_seconds=999999)['pending']==1
    assert not (ham/'Ham1.png').exists()
    pic(path,'green')
    assert v.sweep(stable_seconds=0)['pending']==1
    assert stable(v)['high']==1
    assert (ham/'Ham1.png').exists()


def test_active_image_byte_change_blocks_production_not_silently_reapproved(tmp_path):
    root,v=vault(tmp_path);ham=root/FOLDER
    pic(ham/'a.png','red');stable(v)
    pic(ham/'Ham1.png','blue')
    alerts=stable(v)['warnings']
    assert any(x['type']=='HAM_REGISTERED_BYTES_CHANGED' for x in alerts)
    with pytest.raises(ValueError,match='HAM_BASKI_TASARIMLARI_ONCE_KONTROL'):
        v.validate_for_production()
    assert v.audit()['high']==1


def test_bad_image_is_left_alone_and_later_valid_image_can_run(tmp_path):
    root,v=vault(tmp_path);ham=root/FOLDER
    (ham/'fake.jpg').write_bytes(b'not real JPEG')
    info=stable(v)
    assert info['renamed']==[]
    assert any(x['type']=='HAM_INPUT_REVIEW' for x in info['warnings'])
    assert (ham/'fake.jpg').exists()
    pic(ham/'valid.webp','green')
    result=stable(v)
    assert (ham/'Ham1.webp').exists()
    assert (ham/'fake.jpg').exists()


def test_cross_workspace_state_isolated_with_portable_highwater(tmp_path):
    local=tmp_path/'local'
    a=tmp_path/'A';b=tmp_path/'B'
    a.mkdir();b.mkdir()
    av=HamDesignVault(a,local_state=local)
    bv=HamDesignVault(b,local_state=local)
    pic(av.folder/'a.png')
    pic(bv.folder/'b.png','green')
    stable(av);stable(bv)
    assert (av.folder/'Ham1.png').exists() and (bv.folder/'Ham1.png').exists()
    assert av.db!=bv.db
    assert av.audit()['high']==1 and bv.audit()['high']==1
    # Even when local registry vanishes, portable high-water never decreases.
    av.db.unlink()
    (av.folder/'Ham1.png').unlink()
    revived=HamDesignVault(a,local_state=local)
    pic(revived.folder/'again.jpg','purple')
    stable(revived)
    assert (revived.folder/'Ham2.jpg').exists()


def test_audit_warns_unregistered_ham_design_and_does_not_hide_it(tmp_path):
    root,v=vault(tmp_path)
    pic(v.folder/'new.jpg','red')
    report=v.audit()
    assert report['unregistered']==['new.jpg']
    with pytest.raises(ValueError,match='HAM_BASKI_TASARIMLARI_ONCE_KONTROL'):
        v.validate_for_production()


def test_gui_and_watcher_wired_to_one_working_root():
    center=(ROOT/'MERKEZ/merkez.py').read_text('utf-8')
    gui=(ROOT/'MERKEZ/URETIM_V4/gui_v4.py').read_text('utf-8')
    assert 'self.root.after(150,self.start_auto_ham_designs)' in center
    assert 'HamDesignWatcher' in center
    assert 'self.ham_design_watcher.stop()' in center
    assert "self.runtime_root/'HAM BASKI TASARIMLARI'" in gui
    assert 'validate_for_production()' in gui
