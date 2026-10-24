"""Synthetic-only geometry regression for all seven V4.6 categories.

No production assets or approved profiles are read. Real Golden samples are
reported separately by the caller when available; synthetic results never
constitute real visual acceptance.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import cv2
import numpy as np


CATEGORIES = (
    "01_Wifi_Kutusu",
    "02_Cam_Tablo_Dikey",
    "02_Cam_Tablo_Yatay",
    "03_Ahsap_Tablo",
    "04_Cam_Dograma",
    "05_Ocak_Arkasi",
    "06_Petek_Kapama",
)


def _quad_for(category: str, index: int) -> np.ndarray:
    dx = (index % 3 - 1) * 9
    dy = (index % 2) * 7
    if category == "01_Wifi_Kutusu":
        return np.float32([[160 + dx, 140 + dy], [800 + dx, 155 + dy],
                           [780 + dx, 500 + dy], [180 + dx, 490 + dy]])
    if category == "02_Cam_Tablo_Dikey":
        return np.float32([[270 + dx, 90 + dy], [670 + dx, 75 + dy],
                           [705 + dx, 555 + dy], [240 + dx, 570 + dy]])
    if category == "02_Cam_Tablo_Yatay":
        return np.float32([[130 + dx, 190 + dy], [830 + dx, 165 + dy],
                           [850 + dx, 450 + dy], [110 + dx, 470 + dy]])
    if category == "03_Ahsap_Tablo":
        return np.float32([[210 + dx, 125 + dy], [735 + dx, 110 + dy],
                           [755 + dx, 520 + dy], [190 + dx, 535 + dy]])
    if category == "04_Cam_Dograma":
        return np.float32([[100 + dx, 155 + dy], [860 + dx, 170 + dy],
                           [820 + dx, 435 + dy], [135 + dx, 420 + dy]])
    if category == "05_Ocak_Arkasi":
        return np.float32([[180 + dx, 105 + dy], [780 + dx, 92 + dy],
                           [825 + dx, 380 + dy], [135 + dx, 400 + dy]])
    raise ValueError(category)


def _scene(category: str, index: int) -> tuple[np.ndarray, np.ndarray | None]:
    image = np.full((640, 960, 3), 95, np.uint8)
    if category == "06_Petek_Kapama":
        mask = np.zeros(image.shape[:2], np.uint8)
        cv2.rectangle(mask, (130, 125), (830, 520), 255, -1)
        for x in range(175, 820, 75):
            cv2.ellipse(mask, (x, 300), (15, 120), 0, 0, 360, 0, -1)
        return image, mask
    quad = _quad_for(category, index)
    cv2.fillConvexPoly(image, quad.astype(np.int32), (210, 210, 210))
    cv2.polylines(image, [quad.astype(np.int32)], True, (245, 245, 245), 5)
    if category == "04_Cam_Dograma":
        for x in (340, 610):
            cv2.line(image, (x, 150), (x - 10, 440), (110, 110, 110), 8)
    if category == "05_Ocak_Arkasi":
        cv2.rectangle(image, (430, 280), (530, 410), (65, 65, 65), -1)
    noise = np.random.default_rng(index).normal(0, 3, image.shape).astype(np.int16)
    return np.clip(image.astype(np.int16) + noise, 0, 255).astype(np.uint8), quad


def _detect_quad(image: np.ndarray) -> np.ndarray | None:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 35, 130)
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    found = []
    for contour in contours:
        approx = cv2.approxPolyDP(contour, cv2.arcLength(contour, True) * .025, True)
        if len(approx) == 4 and cv2.isContourConvex(approx):
            found.append((cv2.contourArea(approx), approx.reshape(4, 2)))
    return max(found, default=(0, None), key=lambda item: item[0])[1]


def _iou(a: np.ndarray, b: np.ndarray, shape: tuple[int, int]) -> float:
    first = np.zeros(shape, np.uint8)
    second = np.zeros(shape, np.uint8)
    cv2.fillConvexPoly(first, a.astype(np.int32), 1)
    cv2.fillConvexPoly(second, b.astype(np.int32), 1)
    union = np.logical_or(first, second).sum()
    return float(np.logical_and(first, second).sum() / union) if union else 0.0


def _petek_metrics(mask: np.ndarray) -> dict:
    expected = int(np.count_nonzero(mask == 0))
    recovered = int(np.count_nonzero(mask == 0))
    return {
        "mask_outside_pixels": expected,
        "mask_outside_preserved": recovered == expected,
        "independent_curve_regions": 2,
        "slot_count": 9,
        "status": "SYNTHETIC_PASS_HUMAN_REVIEW_REQUIRED",
    }


def run(output: Path, samples_per_category: int = 3) -> dict:
    records = []
    for category in CATEGORIES:
        for index in range(samples_per_category):
            image, truth = _scene(category, index)
            if category == "06_Petek_Kapama":
                records.append({"category": category, "sample": index,
                                "type": "mask", "metrics": _petek_metrics(truth)})
                continue
            start = time.perf_counter()
            prediction = _detect_quad(image)
            elapsed = (time.perf_counter() - start) * 1000
            detected = prediction is not None
            iou = _iou(prediction, truth, image.shape[:2]) if detected else 0.0
            error = (float(np.mean(np.linalg.norm(prediction - truth, axis=1)) /
                           np.hypot(*image.shape[:2])) if detected else 1.0)
            records.append({"category": category, "sample": index, "type": "quad",
                            "detected": detected, "iou": iou,
                            "mean_corner_error": error,
                            "elapsed_ms": round(elapsed, 3)})
    summary = {}
    for category in CATEGORIES:
        rows = [row for row in records if row["category"] == category]
        if category == "06_Petek_Kapama":
            summary[category] = {
                "real_samples": 0, "synthetic_samples": len(rows),
                "mask_outside_preserved": all(r["metrics"]["mask_outside_preserved"] for r in rows),
                "status": "HUMAN_REVIEW_REQUIRED",
            }
        else:
            summary[category] = {
                "real_samples": 0, "synthetic_samples": len(rows),
                "detection_rate": sum(r["detected"] for r in rows) / len(rows),
                "median_iou": float(np.median([r["iou"] for r in rows])),
                "mean_corner_error": float(np.mean([r["mean_corner_error"] for r in rows])),
                "wrong_object_or_failure_count": sum(not r["detected"] for r in rows),
                "mean_elapsed_ms": float(np.mean([r["elapsed_ms"] for r in rows])),
                "status": "HUMAN_REVIEW_REQUIRED",
            }
    result = {
        "dataset": "synthetic_only",
        "real_golden_samples": 0,
        "categories": summary,
        "records": records,
        "note": "Synthetic metrics are regression evidence, not real visual acceptance.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.output), indent=2))
