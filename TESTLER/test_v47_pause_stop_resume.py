"""V4.7 Windows batch lifetime: PAUSE/RESUME and STOP/restart with SHA proof."""
from __future__ import annotations
import hashlib
import json
import sys
import threading
import time
from pathlib import Path

import cv2
import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'MERKEZ'))
sys.path.insert(0,str(ROOT/'TESTLER'))
from PETEK_V3 import engine as petek_engine
from URETIM_V4.unified_batch import UnifiedV4Batch
from URETIM_V4.resume_checkpoint_v47 import read_checkpoint, checkpoint_path
from URETIM_V4.store_profiles_v47 import StoreProfiles
from test_v40_unified_seven_category import _build_seven_category_workspace, _write_png


def fixture_batch(tmp_path, art_count=3):
    runtime,registry=_build_seven_category_workspace(tmp_path,per_cat_count=1)
    state=tmp_path/'LocalState'
    batch=UnifiedV4Batch(state,runtime_root=runtime,petek_registry=registry)
    templates,_=batch.discover_templates(per_category_limit=None)
    wood=next(x for x in templates if x['category']=='03_Ahsap_Tablo')
    folder=tmp_path/'Designs'
    for i in range(art_count):
        img=np.full((320,320,3),(30+i*35,90+i*25,140+i*20),np.uint8)
        _write_png(folder/f'Artwork_{i:03d}.png',img)
    return batch,registry,wood,folder


def _outputs(batch):
    return list(batch.ledger.successful())


def test_safe_stop_is_durable_and_continue_finishes_only_remaining(tmp_path):
    batch,registry,wood,designs=fixture_batch(tmp_path)
    log=[]
    def notify(msg):
        log.append(msg)
        if 'ÜRETİLDİ 1:' in msg:
            batch.request_stop()
    first=batch.run(designs,selected_uids=[wood['uid']],random_seed=389,
                    glass_effect='on',notify=notify)
    assert first['status']=='STOPPED'
    assert first['rendered']==1
    assert batch.lock_path.exists() is False
    initial=_outputs(batch)
    assert len(initial)==1
    existing=Path(initial[0]['output'])
    original_sha=petek_engine.digest(existing)
    cp=read_checkpoint(batch.root)
    assert cp['status']=='STOPPED'
    assert cp['config']['random_seed']==389
    assert cp['progress']['rendered']==1
    assert cp['inventory']['designs']
    assert len(cp['inventory']['groups']['LOCAL'])==1

    fresh=UnifiedV4Batch(batch.root,runtime_root=batch.runtime_root,petek_registry=registry)
    final=fresh.resume_last_stopped()
    assert final['status']=='LOCAL_READY'
    assert final['rendered']==2
    assert final['reused']==1
    assert len(_outputs(fresh))==3
    assert petek_engine.digest(existing)==original_sha
    assert read_checkpoint(fresh.root)['status']=='COMPLETED'
    with pytest.raises(petek_engine.MaskError,match='COMPLETED'):
        fresh.resume_last_stopped()


def test_live_pause_and_resume_single_worker(tmp_path):
    batch,_,wood,designs=fixture_batch(tmp_path,art_count=3)
    paused=threading.Event()
    done=[]
    def notify(msg):
        if 'ÜRETİLDİ 1:' in msg:
            batch.request_pause()
            paused.set()
    worker=threading.Thread(
        target=lambda:done.append(batch.run(
            designs,selected_uids=[wood['uid']],random_seed=19,notify=notify)),
        daemon=False)
    worker.start()
    try:
        assert paused.wait(20)
        time.sleep(.15)
        assert worker.is_alive()
        assert len(_outputs(batch))==1
        batch.resume()
        worker.join(timeout=35)
        assert not worker.is_alive()
        assert done and done[0]['status']=='LOCAL_READY'
        assert done[0]['rendered']==3
        assert len(_outputs(batch))==3
    finally:
        batch.resume()
        batch.request_stop()
        worker.join(timeout=3)


def test_changed_design_blocks_resume_keeps_finished_output(tmp_path):
    batch,registry,wood,designs=fixture_batch(tmp_path,art_count=3)
    def notify(msg):
        if 'ÜRETİLDİ 1:' in msg:
            batch.request_stop()
    first=batch.run(designs,selected_uids=[wood['uid']],random_seed=8,notify=notify)
    assert first['status']=='STOPPED'
    original=_outputs(batch)[0]
    finished=Path(original['output'])
    digest=petek_engine.digest(finished)
    design=next(designs.glob('*.png'))
    _write_png(design,np.full((320,320,3),(10,30,80),np.uint8))
    with pytest.raises(petek_engine.MaskError,match='tasarım dosyaları|SHA'):
        batch.resume_last_stopped()
    assert petek_engine.digest(finished)==digest
    assert len(_outputs(batch))==1
    assert not batch.lock_path.exists()
    assert read_checkpoint(batch.root)['status']=='STOPPED'


def test_checkpoint_tamper_and_active_lock_fail_closed(tmp_path):
    batch,_,wood,designs=fixture_batch(tmp_path)
    def notify(msg):
        if 'ÜRETİLDİ 1:' in msg:
            batch.request_stop()
    batch.run(designs,selected_uids=[wood['uid']],random_seed=10,notify=notify)
    lock=batch.lock_path
    lock.write_text('999999999',encoding='utf-8')
    try:
        with pytest.raises(petek_engine.MaskError,match='kilidi|kilit'):
            batch.resume_last_stopped()
    finally:
        lock.unlink()
    checkpoint=checkpoint_path(batch.root)
    obj=json.loads(checkpoint.read_text(encoding='utf-8'))
    obj['payload']['config']['random_seed']=999
    checkpoint.write_text(json.dumps(obj),encoding='utf-8')
    with pytest.raises(ValueError,match='CHECKPOINT_SHA_MISMATCH'):
        batch.resume_last_stopped()
    assert len(_outputs(batch))==1


def test_store_changes_block_resume_and_keep_completed(tmp_path):
    batch,registry,wood,designs=fixture_batch(tmp_path,art_count=3)
    more=next(x for x in batch.discover_templates()[0] if x['category']=='02_Cam_Tablo_Dikey')
    store=StoreProfiles(batch.root)
    store.add_store('Magaza_01')
    store.assign('Magaza_01',[wood])
    def notify(msg):
        if 'ÜRETİLDİ 1:' in msg:
            batch.request_stop()
    result=batch.run(designs,selected_stores=['Magaza_01'],
                     selected_uids=[wood['uid']],random_seed=555,notify=notify)
    assert result['status']=='STOPPED'
    original=_outputs(batch)[0]
    sha=petek_engine.digest(Path(original['output']))
    store.assign('Magaza_01',[more])
    with pytest.raises((ValueError, petek_engine.MaskError),match='onayı/SHA|mağaza atamaları'):
        batch.resume_last_stopped()
    assert petek_engine.digest(Path(original['output']))==sha
    assert len(_outputs(batch))==1


def test_ui_has_two_distinct_resume_modes_and_no_cloud_autopublish():
    text=(ROOT/'MERKEZ'/'URETIM_V4'/'gui_v4.py').read_text(encoding='utf-8')
    assert 'self.batch_engine.resume()' in text
    assert 'self.batch_engine.resume_last_stopped(notify=self._log)' in text
    assert "self._auto_cloud_pending = False  # Do not implicitly upload on replay." in text
    assert 'self._render_stop_requested = True' in text
