"""Isolated V4.6 corner-detection benchmark for synthetic oven-glass scenes.

This experiment never reads or writes production databases, templates, or
approved profiles. It compares bounded OpenCV strategies and writes only the
requested JSON report.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import cv2
import numpy as np


def _ordered(points: np.ndarray) -> np.ndarray:
    center = points.mean(axis=0)
    angles = np.arctan2(points[:, 1] - center[1], points[:, 0] - center[0])
    points = points[np.argsort(angles)]
    start = int(np.argmin(points.sum(axis=1)))
    points = np.roll(points, -start, axis=0)
    if points[1, 0] < points[-1, 0]:
        points = points[[0, 3, 2, 1]]
    return points.astype(np.float32)


def _valid_quad(points: np.ndarray | None, shape: tuple[int, int]) -> np.ndarray | None:
    if points is None:
        return None
    points = np.asarray(points, dtype=np.float32)
    if points.shape != (4, 2) or not np.isfinite(points).all():
        return None
    points = _ordered(points)
    h, w = shape
    if np.any(points < 0) or np.any(points[:, 0] >= w) or np.any(points[:, 1] >= h):
        return None
    if abs(cv2.contourArea(points)) < h * w * 0.03:
        return None
    if not cv2.isContourConvex(points.astype(np.int32)):
        return None
    return points


def _largest_contour(image: np.ndarray) -> np.ndarray | None:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 35, 130)
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates = []
    for contour in contours:
        perimeter = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, perimeter * 0.025, True)
        if len(approx) == 4 and cv2.isContourConvex(approx):
            candidates.append((cv2.contourArea(approx), approx.reshape(4, 2)))
    return max(candidates, default=(0, None), key=lambda item: item[0])[1]


def _hough_rectangle(image: np.ndarray) -> np.ndarray | None:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 30, 110)
    lines = cv2.HoughLinesP(
        edges, 1, np.pi / 180, threshold=45,
        minLineLength=min(image.shape[:2]) * 0.22, maxLineGap=24,
    )
    if lines is None:
        return None
    points = []
    for line in lines.reshape(-1, 4):
        x1, y1, x2, y2 = map(float, line)
        points.extend(((x1, y1), (x2, y2)))
    if len(points) < 4:
        return None
    hull = cv2.convexHull(np.asarray(points, dtype=np.float32))
    if len(hull) < 4:
        return None
    return cv2.approxPolyDP(hull, 0.04 * cv2.arcLength(hull, True), True).reshape(-1, 2)[:4]


def _bright_region(image: np.ndarray) -> np.ndarray | None:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    mask = cv2.inRange(gray, 175, 255)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((11, 11), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates = []
    for contour in contours:
        if cv2.contourArea(contour) < image.shape[0] * image.shape[1] * 0.04:
            continue
        approx = cv2.approxPolyDP(contour, 0.04 * cv2.arcLength(contour, True), True)
        if len(approx) == 4:
            candidates.append((cv2.contourArea(approx), approx.reshape(4, 2)))
    return max(candidates, default=(0, None), key=lambda item: item[0])[1]


ALGORITHMS = {
    "canny_contour": _largest_contour,
    "hough_hull": _hough_rectangle,
    "bright_region": _bright_region,
}


def _scene(index: int, no_panel: bool = False) -> tuple[np.ndarray, np.ndarray | None]:
    height, width = 640, 960
    image = np.full((height, width, 3), 92, np.uint8)
    cv2.rectangle(image, (50, 430), (910, 635), (56, 56, 56), -1)
    cv2.rectangle(image, (120, 100), (250, 360), (125, 125, 125), -1)
    if no_panel:
        cv2.line(image, (80, 110), (840, 150), (145, 145, 145), 4)
        return image, None
    offsets = [(0, 0), (12, -8), (-10, 12), (18, 6), (-15, -12), (5, 18)]
    dx, dy = offsets[index % len(offsets)]
    quad = np.array([
        [180 + dx, 120 + dy], [780 + dx, 105 + dy],
        [830 + dx, 375 + dy], [130 + dx, 395 + dy],
    ], np.int32)
    cv2.fillConvexPoly(image, quad, (218, 218, 218))
    cv2.polylines(image, [quad], True, (242, 242, 242), 5)
    cv2.line(image, tuple(quad[0]), tuple(quad[2]), (205, 205, 205), 2)
    if index % 2:
        cv2.rectangle(image, (430, 250), (530, 395), (72, 72, 72), -1)
    noise = np.random.default_rng(index).normal(0, 4, image.shape).astype(np.int16)
    image = np.clip(image.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    return image, quad.astype(np.float32)


def _iou(pred: np.ndarray | None, truth: np.ndarray | None, shape: tuple[int, int]) -> float:
    if pred is None or truth is None:
        return 0.0
    a = np.zeros(shape, np.uint8)
    b = np.zeros(shape, np.uint8)
    cv2.fillConvexPoly(a, pred.astype(np.int32), 1)
    cv2.fillConvexPoly(b, truth.astype(np.int32), 1)
    union = np.logical_or(a, b).sum()
    return float(np.logical_and(a, b).sum() / union) if union else 0.0


def run(output: Path, sample_count: int = 12) -> dict:
    records = []
    for index in range(sample_count):
        image, truth = _scene(index)
        for name, algorithm in ALGORITHMS.items():
            start = time.perf_counter()
            predicted = _valid_quad(algorithm(image), image.shape[:2])
            elapsed = (time.perf_counter() - start) * 1000
            diagonal = float(np.hypot(*image.shape[:2]))
            error = 1.0
            if predicted is not None:
                error = float(np.mean(np.linalg.norm(predicted - truth, axis=1)) / diagonal)
            records.append({
                "sample": index, "category": "05_Ocak_Arkasi",
                "algorithm": name, "detected": predicted is not None,
                "iou": _iou(predicted, truth, image.shape[:2]),
                "mean_corner_error": error, "elapsed_ms": round(elapsed, 3),
            })
    for index in range(3):
        image, truth = _scene(index, no_panel=True)
        for name, algorithm in ALGORITHMS.items():
            predicted = _valid_quad(algorithm(image), image.shape[:2])
            records.append({
                "sample": f"no_panel_{index}", "category": "05_Ocak_Arkasi",
                "algorithm": name, "detected": predicted is not None,
                "iou": 0.0, "mean_corner_error": 1.0, "elapsed_ms": None,
            })
    summary = {}
    for name in ALGORITHMS:
        true_rows = [r for r in records if r["algorithm"] == name and isinstance(r["sample"], int)]
        no_panel_rows = [r for r in records if r["algorithm"] == name and not isinstance(r["sample"], int)]
        ious = [r["iou"] for r in true_rows]
        errors = [r["mean_corner_error"] for r in true_rows]
        summary[name] = {
            "true_panel_count": len(true_rows),
            "median_iou": float(np.median(ious)),
            "min_iou": float(np.min(ious)),
            "mean_corner_error": float(np.mean(errors)),
            "false_positive_no_panel": sum(r["detected"] for r in no_panel_rows),
            "mean_elapsed_ms": float(np.mean([r["elapsed_ms"] for r in true_rows])),
        }
    result = {
        "dataset": "synthetic_only",
        "category": "05_Ocak_Arkasi",
        "sample_count": sample_count,
        "no_panel_count": 3,
        "recommendation_thresholds": {
            "median_iou": 0.98, "critical_iou": 0.95,
            "mean_corner_error_fraction": 0.005,
            "false_positive_no_panel": 0,
        },
        "summary": summary,
        "records": records,
        "acceptance": "INSUFFICIENT_GOLDEN_HUMAN_REVIEW_REQUIRED",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.output), indent=2))


if __name__ == "__main__":
    main()
