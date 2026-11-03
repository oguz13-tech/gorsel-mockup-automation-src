# -*- coding: utf-8 -*-
"""Isolated V4.6 magenta quad proposal engine. Does NOT query/save profiles.

Based on manually reviewed 346-frame magenta-only standalone test. All proposals
remain REVIEW_REQUIRED until independently approved by a human.
"""
import cv2
import numpy as np


ORIENTATIONS = {
    '01_Wifi_Kutusu': 'H',
    '02_Cam_Tablo_Dikey': 'V',
    '02_Cam_Tablo_Yatay': 'H',
    '03_Ahsap_Tablo': 'V',
    '04_Cam_Dograma': 'H',
    '05_Ocak_Arkasi': 'H',
}


def _order_clockwise_xy(q):
    q = np.asarray(q, dtype=np.float32).reshape(4, 2)
    ctr = q.mean(axis=0)
    q = q[np.argsort(np.arctan2(q[:, 1] - ctr[1], q[:, 0] - ctr[0]))]
    idx = int(np.argmin(q.sum(axis=1)))
    q = np.roll(q, -idx, axis=0)
    signed = float(sum(q[i, 0] * q[(i + 1) % 4, 1] - q[(i + 1) % 4, 0] * q[i, 1] for i in range(4)))
    if signed < 0:
        q = np.asarray([q[0], q[3], q[2], q[1]], dtype=np.float32)
    return q


def detect(bgr, category):
    """Find magenta printable surface without DB priors. Return metadata + quad or abstain.

    PETEK remains unsupported: it needs a verified front/vent/slot mask, not a quad.
    Caller may fall through to legacy ONLY if magenta is absent/too small.
    """
    h, w = bgr.shape[:2]
    if min(h, w) < 150:
        return {'status': 'REVIEW_REQUIRED', 'reason': 'IMAGE_TOO_SMALL', 'chroma_present': False, 'pixels': 0}
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    bb, gg, rr = cv2.split(bgr)
    mask = ((hsv[:, :, 0] >= 137) & (hsv[:, :, 0] <= 178) &
            (hsv[:, :, 1] >= 125) & (hsv[:, :, 2] >= 105) &
            (rr >= 120) & (bb >= 120) &
            (gg.astype(np.float32) <= .62 * np.minimum(rr, bb)) &
            (np.abs(rr.astype(np.int16) - bb.astype(np.int16)) < 108)).astype(np.uint8) * 255
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    pixels = int(cv2.countNonZero(mask))
    if pixels < max(600, round(w * h * .0015)):
        return {'status': 'REVIEW_REQUIRED', 'reason': 'MAGENTA_ABSENT_OR_TOO_SMALL',
                'pixels': pixels, 'chroma_present': False}
    if 'petek' in category.lower():
        return {'status': 'BLOCKED', 'reason': 'PETEK_FRONT_VENT_MASK_REQUIRED',
                'pixels': pixels, 'chroma_present': True}
    if category not in ORIENTATIONS:
        return {'status': 'REVIEW_REQUIRED', 'reason': 'CATEGORY_UNRECOGNIZED',
                'pixels': pixels, 'chroma_present': True}
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)
    if not contours:
        return {'status': 'REVIEW_REQUIRED', 'reason': 'NO_CONTOUR',
                'pixels': pixels, 'chroma_present': True}
    best = contours[0]
    largest_area = cv2.contourArea(best)
    if largest_area < max(500, w * h * .0015):
        return {'status': 'REVIEW_REQUIRED', 'reason': 'REGION_TOO_SMALL',
                'pixels': pixels, 'chroma_present': True}
    if len(contours) > 1 and cv2.contourArea(contours[1]) > largest_area * .08:
        return {'status': 'REVIEW_REQUIRED', 'reason': 'MULTIPLE_MAGENTA_REGIONS',
                'pixels': pixels, 'chroma_present': True}
    hull = cv2.convexHull(best)
    per = cv2.arcLength(hull, True)
    if per <= 0:
        return {'status': 'REVIEW_REQUIRED', 'reason': 'NO_PERIMETER',
                'pixels': pixels, 'chroma_present': True}
    matches = []
    for epsilon in [.002, .003, .004, .005, .006, .008, .01, .013, .016, .02, .025, .03, .04]:
        approx = cv2.approxPolyDP(hull, epsilon * per, True)
        if len(approx) != 4 or not cv2.isContourConvex(approx):
            continue
        pts = _order_clockwise_xy(approx[:, 0, :])
        poly = np.zeros((h, w), np.uint8)
        cv2.fillConvexPoly(poly, np.round(pts).astype(np.int32), 255)
        inter = cv2.countNonZero(cv2.bitwise_and(poly, mask))
        union = cv2.countNonZero(cv2.bitwise_or(poly, mask))
        iou = inter / union if union else 0.0
        area = cv2.countNonZero(poly)
        avgwidth = (float(np.linalg.norm(pts[1] - pts[0])) + float(np.linalg.norm(pts[2] - pts[3]))) / 2
        avgheight = (float(np.linalg.norm(pts[3] - pts[0])) + float(np.linalg.norm(pts[2] - pts[1]))) / 2
        ratio = avgwidth / max(1, avgheight)
        rot = 'H' if ratio >= 1.06 else 'V' if ratio <= .94 else '?'
        matches.append((iou, pts, ratio, rot, inter / max(1, area)))
    if not matches:
        return {'status': 'REVIEW_REQUIRED', 'reason': 'NO_UNAMBIGUOUS_FOUR_CORNERS',
                'pixels': pixels, 'chroma_present': True}
    iou, q, ratio, rot, purity = max(matches, key=lambda t: t[0])
    reasons = []
    if iou < .975:
        reasons.append('MAGENTA_POLYGON_IOU_LOW')
    if purity < .97:
        reasons.append('REGION_HAS_HOLES_OR_OCCLUSION')
    if rot != '?' and rot != ORIENTATIONS[category]:
        reasons.append('ORIENTATION_MISMATCH')
    if rot == '?':
        reasons.append('ORIENTATION_AMBIGUOUS')
    if any(x < 0 or x >= w or y < 0 or y >= h for x, y in q):
        reasons.append('OUT_OF_BOUNDS')
    for j in range(4):
        if np.linalg.norm(q[(j + 1) % 4] - q[j]) < min(w, h) * .045:
            reasons.append('VERY_SHORT_SIDE')
    return {
        'status': 'CANDIDATE' if not reasons else 'REVIEW_REQUIRED',
        'chroma_present': True, 'pixels': pixels,
        'reason': ';'.join(dict.fromkeys(reasons)) or 'MAGENTA_ONLY_QUAD_CANDIDATE',
        'quad': q.astype(float).tolist(),
        'magenta_mask_iou': round(float(iou), 6),
        'magenta_polygon_purity': round(float(purity), 6),
        'width_height_ratio': round(float(ratio), 4),
        'orientation': rot,
    }
