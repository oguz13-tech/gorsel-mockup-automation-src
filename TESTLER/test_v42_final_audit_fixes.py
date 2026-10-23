"""Focused final-audit regressions; uses isolated temporary paths only."""
from __future__ import annotations
import hashlib
import sys
from pathlib import Path
import numpy as np
import cv2
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'MERKEZ'))
from URETIM_V4.unified_batch import UnifiedV4Batch
from PETEK_V3.engine import MaskError


def fixture_batch(tmp_path):
    scene=np.full((340,280,3),[123,140,162],np.uint8)
    art=np.full((260,200,3),[22,56,173],np.uint8)
    src=tmp_path/'scene.png'
    designed=tmp_path/'designs'; designed.mkdir()
    cv2.imwrite(str(src),scene)
    cv2.imwrite(str(designed/'art.png'),art)
    sha=hashlib.sha256(src.read_bytes()).hexdigest()
    def template(uid,source):
        return {'uid':uid, 'category':'03_Ahsap_Tablo',
            'engine_type':'LEGACY_6_COVER','source':str(source),'source_sha':sha,
            'quad':[[52,42],[234,52],[224,279],[48,280]],
            'physical_aspect':.71,'orientation':'V','legacy_data':{}}
    batch=UnifiedV4Batch(root=tmp_path/'state',petek_registry=object())
    return batch,designed,src,template


def test_missing_template_does_not_abort_remaining_approved_jobs(tmp_path):
    batch,art,src,t=fixture_batch(tmp_path)
    fake=tmp_path/'missing-source.png'
    items=[t('BAD',fake),t('GOOD',src)]
    batch.discover_templates=lambda **kwargs:(items,{'per_category_counts':{'03_Ahsap_Tablo':2},'skipped':[]})
    result=batch.run(art,group='TEST',max_jobs=2)
    assert result['status']=='PARTIAL'
    assert result['attempted']==2
    assert result['rejected']==1 and result['rendered']==1
    assert result['errors'][0]['template']=='BAD'
    assert result['total_registry_outputs']==1
    assert Path(result['xlsx']).is_file()
    assert not batch.lock_path.exists()


def test_selection_rejected_if_one_uid_no_longer_approved(tmp_path):
    batch,art,src,t=fixture_batch(tmp_path)
    batch.discover_templates=lambda **kwargs:([t('GOOD',src)],{'per_category_counts':{},'skipped':[]})
    with pytest.raises(MaskError,match='artık onaylı/güvenli değil'):
        batch.run(art,group='TEST',selected_uids=['GOOD','MISSING'])
    assert not batch.lock_path.exists()


def test_duplicate_uid_fails_closed_before_writing(tmp_path):
    batch,art,src,t=fixture_batch(tmp_path)
    batch.discover_templates=lambda **kwargs:([t('SAME',src),t('SAME',src)],{'per_category_counts':{},'skipped':[]})
    with pytest.raises(MaskError,match='UID çakışması'):
        batch.run(art,group='TEST')
    assert not batch.lock_path.exists()


def test_tk_settings_snapshot_outside_thread():
    source=(ROOT/'MERKEZ/URETIM_V4/gui_v4.py').read_text('utf-8')
    start=source.split('    def start(self) -> None:',1)[1].split('    def stop(self) -> None:',1)[0]
    callback=start.split('        def work():',1)[1]
    assert 'self.design_folder.get()' not in callback
    assert 'self.group.get()' not in callback
    assert 'self.limit.get()' not in callback
    assert 'self.corner_option.get()' not in callback
    assert 'self.placement.get()' not in callback
    assert 'self.lighting.get()' not in callback


def test_final_launcher_recovers_partial_python_environment():
    source=(ROOT/'WINDOWS_HIZLI_BASLAT.bat').read_text('utf-8')
    assert 'pip install --disable-pip-version-check' in source
    assert 'if errorlevel 1 goto failed' in source
    assert 'MERKEZ\\.venv\\Scripts\\python.exe' in source


def test_health_report_identifies_new_release_and_no_windows_claim(tmp_path):
    from merkez_saglik import report
    result=report(platform='posix',userprofile=str(tmp_path))
    assert result['version']=='4.2.2'
    assert result['v42_native_windows_verified'] is False
    assert result['v42_installed_code_ready'] is True
