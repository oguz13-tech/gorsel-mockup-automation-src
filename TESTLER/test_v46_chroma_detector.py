"""Synthetic, review-only tests for the V4.6 magenta quad detector."""
from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "SABLON_V2_MIMARI"))

from core.chroma_quad_detector import detect


def _image(points=None):
    image = np.full((600, 800, 3), 220, dtype=np.uint8)
    if points is not None:
        cv2.fillConvexPoly(image, np.asarray(points, dtype=np.int32), (255, 0, 255))
    return image


def test_detects_planar_magenta_quad_as_review_candidate():
    result = detect(_image([(220, 80), (560, 90), (550, 540), (210, 530)]), "03_Ahsap_Tablo")
    assert result["chroma_present"] is True
    assert result["status"] == "CANDIDATE"
    assert len(result["quad"]) == 4
    assert result["magenta_mask_iou"] >= 0.975


def test_absent_magenta_does_not_fallback_inside_detector():
    result = detect(_image(), "03_Ahsap_Tablo")
    assert result["chroma_present"] is False
    assert result["status"] == "REVIEW_REQUIRED"
    assert result["reason"] == "MAGENTA_ABSENT_OR_TOO_SMALL"


def test_petek_requires_front_mask():
    result = detect(_image([(120, 100), (680, 100), (680, 500), (120, 500)]), "06_PETEK")
    assert result["status"] == "BLOCKED"
    assert result["reason"] == "PETEK_FRONT_VENT_MASK_REQUIRED"
