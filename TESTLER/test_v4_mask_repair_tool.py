from pathlib import Path
import importlib.util
import sys
import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'MERKEZ'))
spec=importlib.util.spec_from_file_location('repair_tool',ROOT/'tools/repair_ten_slot_draft.py')
tool=importlib.util.module_from_spec(spec);spec.loader.exec_module(tool)


def test_preparation_only_returns_unapproved_draft(monkeypatch):
    mask=np.ones((50,50),np.uint8)*255
    repaired=mask.copy();repaired[:,20:23]=0
    profile=dict(source='source.png',source_sha=tool.EXPECTED_SOURCE,quad=[],status='APPROVED')
    class ReadOnlyRegistry:
        def get(self,uid):
            assert uid==tool.UID
            return profile,mask
    monkeypatch.setattr(tool.engine,'read_bgr',lambda p:np.zeros((50,50,3),np.uint8))
    monkeypatch.setattr(tool,'temporary_photo_protected_preview_mask',
                        lambda *a:(repaired,{'source_vent_count':10}))
    draft,output,proof=tool.prepare(ReadOnlyRegistry())
    assert draft['status']=='DRAFT' and draft['uid']!=tool.UID
    assert profile['status']=='APPROVED' and np.all(mask==255)
    assert np.array_equal(output,repaired)


def test_preparation_refuses_different_source():
    class ReadOnlyRegistry:
        def get(self,uid):return {'source_sha':'wrong'},None
    with pytest.raises(tool.engine.MaskError,match='Beklenen Gemini'):
        tool.prepare(ReadOnlyRegistry())
