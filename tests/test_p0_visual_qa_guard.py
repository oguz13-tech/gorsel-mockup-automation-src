"""Advisory visual QA must not alter source and must block SHA-bound defects."""
import hashlib
import numpy as np
from SABLON_V2_MIMARI.core.visual_qa_audit import (
    KNOWN_BLOCKED_TEMPLATE_SHAS,visual_qa_report
)


def test_argon_known_defective_sha_is_blocked_without_changing_image():
    arr=np.full((1600,1200,3),150,dtype=np.uint8)
    old=arr.tobytes()
    key=next(iter(KNOWN_BLOCKED_TEMPLATE_SHAS))
    record=visual_qa_report(
        "01_Wifi_Kutusu",arr,[[210,350],[810,350],[810,800],[210,800]],
        nominal_aspect=4/3,source_sha256=key,
    )
    assert record["status"] == "BLOCKED"
    assert "WATERMARK_OR_LICENSE_RISK" in record["blocking_defects"]
    assert arr.tobytes() == old


def test_unknown_valid_quad_still_needs_human_review():
    arr=np.zeros((1600,1200,3),dtype=np.uint8)
    result=visual_qa_report(
        "02_Cam_Tablo_Yatay",arr,[[200,400],[800,400],[800,850],[200,850]],
        source_sha256="f"*64,
        render_output=np.full((1600,1200,3),180,dtype=np.uint8),
    )
    assert result["status"] == "VISUAL_REVIEW_REQUIRED"
    assert result["human_approval_required"] is True
    assert not result["blocking_defects"]


def test_invalid_quad_and_wrong_marketplace_aspect_blocked():
    arr=np.full((1600,1200,3),128,dtype=np.uint8)
    result=visual_qa_report(
        "03_Ahsap_Tablo",arr,[[0,0],[10000,0],[100,100],[0,100]],
        render_output=np.zeros((1000,1000,3),dtype=np.uint8),
    )
    assert result["status"] == "BLOCKED"
    assert "GEOMETRY_MISALIGNMENT" in result["blocking_defects"]
    assert "MARKETPLACE_FRAMING_FAILURE" in result["blocking_defects"]
