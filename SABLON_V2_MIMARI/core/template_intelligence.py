import os
import cv2
import json
import uuid
import hashlib
import numpy as np
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Optional, Tuple, Dict
import sqlite3

class CategoryRuleEngine:
    RULES = {
        "WOOD_FRAMED_ART": {
            "product_class": "Ahşap Tablo",
            "has_frame": True,
            "has_mat": False,
            "has_reflection": False,
            "print_policy": "inner_frame",
            "orientation_strict": True,
            "expected_orientation": "ANY",
            "folders": ["03_Ahsap_Tablo"]
        },
        "GLASS_WALL_ART_VERTICAL": {
            "product_class": "Cam Tablo Dikey",
            "has_frame": False,
            "has_mat": False,
            "has_reflection": True,
            "print_policy": "full_bleed",
            "orientation_strict": True,
            "expected_orientation": "V",
            "folders": ["02_Cam_Tablo_Dikey"]
        },
        "GLASS_WALL_ART_HORIZONTAL": {
            "product_class": "Cam Tablo Yatay",
            "has_frame": False,
            "has_mat": False,
            "has_reflection": True,
            "print_policy": "full_bleed",
            "orientation_strict": True,
            "expected_orientation": "H",
            "folders": ["02_Cam_Tablo_Yatay"]
        },
        "GLASS_CUTTING_BOARD": {
            "product_class": "Cam Kesme Tahtası",
            "has_frame": False,
            "has_mat": False,
            "has_reflection": True,
            "print_policy": "full_surface",
            "orientation_strict": False,
            "expected_orientation": "ANY",
            "folders": ["04_Cam_Dograma"]
        },
        "WIFI_COVER_PANEL": {
            "product_class": "Wifi Kutusu Kapağı",
            "has_frame": True,
            "has_mat": False,
            "has_reflection": False,
            "print_policy": "front_panel",
            "orientation_strict": True,
            "expected_orientation": "ANY",
            "folders": ["01_Wifi_Kutusu"]
        },
        "GLASS_BACKSPLASH": {
            "product_class": "Ocak Arkası Cam",
            "has_frame": False,
            "has_mat": False,
            "has_reflection": True,
            "print_policy": "full_bleed",
            "orientation_strict": True,
            "expected_orientation": "H",
            "folders": ["05_Ocak_Arkasi"]
        }
    }
    
    @classmethod
    def get_rule_by_folder(cls, folder_name: str) -> dict:
        for key, rule in cls.RULES.items():
            if folder_name in rule["folders"]:
                rule["key"] = key
                return rule
        raise ValueError(f"UNKNOWN_CATEGORY: {folder_name}")

class GeometryValidator:
    @staticmethod
    def canonical_sort(pts: np.ndarray) -> np.ndarray:
        """Sort 4 points to TL, TR, BR, BL"""
        pts_f = pts.astype(np.float32)
        s = pts_f.sum(axis=1)
        diff = np.diff(pts_f, axis=1)
        tl = pts[np.argmin(s)]
        br = pts[np.argmax(s)]
        tr = pts[np.argmin(diff)]
        bl = pts[np.argmax(diff)]
        return np.array([tl, tr, br, bl], dtype=pts.dtype)

    @staticmethod
    def is_valid_quad(pts: np.ndarray, img_w: int, img_h: int) -> Tuple[bool, str]:
        if len(pts) != 4:
            return False, "Not 4 points"
            
        for p in pts:
            if p[0] < -img_w*0.5 or p[0] > img_w * 1.5 or p[1] < -img_h*0.5 or p[1] > img_h * 1.5:
                return False, "Out of bounds"
                
        # Canonical sort for consistent edges FIRST
        sorted_pts = GeometryValidator.canonical_sort(pts)
        
        area = cv2.contourArea(sorted_pts.astype(np.float32))
        img_area = img_w * img_h
        if area < img_area * 0.05:
            return False, "Too small"
            
        if not cv2.isContourConvex(sorted_pts.astype(np.int32)):
            return False, "Not convex (self intersecting or concave)"
            
        edges = [sorted_pts[(i+1)%4] - sorted_pts[i] for i in range(4)]
        cross_prods = [np.cross(edges[i], edges[(i+1)%4]) for i in range(4)]
        
        # All must have same sign
        if not (all(cp > 0 for cp in cross_prods) or all(cp < 0 for cp in cross_prods)):
             return False, "Self-intersecting segment or invalid ordering (cross product sign flip)"
             
        # Aspect degeneracy check (max 10:1 ratio)
        w_top = np.linalg.norm(edges[0])
        h_left = np.linalg.norm(edges[3])
        if w_top < 10 or h_left < 10 or w_top/h_left > 10.0 or h_left/w_top > 10.0:
            return False, "Degenerate aspect ratio"
            
        # Homography condition number check (nondegeneracy)
        target_pts = np.array([[0,0], [100,0], [100,100], [0,100]], dtype=np.float32)
        H, _ = cv2.findHomography(sorted_pts.astype(np.float32), target_pts)
        if H is None or np.linalg.cond(H) > 1e6:
            return False, "Homography degenerate (condition number too large)"
            
        return True, "Valid"

class CandidateGenerators:
    @staticmethod
    def generate_canny_contours(image_cv: np.ndarray) -> List[np.ndarray]:
        """Generate quadrilateral candidates across several edge scales.

        EPIC-3 showed that a single Canny threshold plus RETR_EXTERNAL misses
        useful nested product surfaces. Multi-threshold extraction keeps the
        method deterministic while improving recall for low-contrast and
        nested panels. Final validation/scoring remains the responsibility of
        TemplateAnalyzer.
        """
        gray = cv2.cvtColor(image_cv, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        img_area = float(image_cv.shape[0] * image_cv.shape[1])
        candidates = []

        for low, high in ((25, 80), (40, 120), (60, 180)):
            edged = cv2.Canny(blurred, low, high)
            for kernel_size in (3, 5):
                kernel = cv2.getStructuringElement(
                    cv2.MORPH_RECT, (kernel_size, kernel_size)
                )
                closed = cv2.morphologyEx(edged, cv2.MORPH_CLOSE, kernel)
                contours, _ = cv2.findContours(
                    closed, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE
                )
                contours = sorted(contours, key=cv2.contourArea, reverse=True)[:30]

                for contour in contours:
                    area = float(abs(cv2.contourArea(contour)))
                    if area < img_area * 0.025 or area > img_area * 0.985:
                        continue

                    hull = cv2.convexHull(contour)
                    peri = cv2.arcLength(hull, True)
                    if peri <= 0:
                        continue

                    for epsilon_ratio in (0.012, 0.02, 0.03, 0.045):
                        approx = cv2.approxPolyDP(
                            hull, epsilon_ratio * peri, True
                        )
                        if len(approx) == 4 and cv2.isContourConvex(approx):
                            candidates.append(approx.reshape(4, 2))

                    # A rotated minimum-area rectangle is useful when an
                    # occluder fragments one side of an otherwise rectangular
                    # surface. It is only a proposal; scorer/validator can
                    # reject it.
                    rect = cv2.minAreaRect(hull)
                    box = cv2.boxPoints(rect)
                    if abs(cv2.contourArea(box.astype(np.float32))) >= img_area * 0.05:
                        candidates.append(np.round(box).astype(np.int32))

        return candidates

    @staticmethod
    def generate_hough_lines_quad(image_cv: np.ndarray) -> List[np.ndarray]:
        """Generate perspective quads from compatible Hough line pairs.

        The legacy implementation collapsed every detected segment into one
        global bounding rectangle. On cluttered images that frequently became
        a near-full-frame false positive. We retain that rectangle only as a
        fallback and additionally form quads from top/bottom and left/right
        line-pair intersections.
        """
        gray = cv2.cvtColor(image_cv, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edged = cv2.Canny(blurred, 40, 140, apertureSize=3)
        h_img, w_img = image_cv.shape[:2]
        min_len = max(40, int(min(w_img, h_img) * 0.12))
        lines = cv2.HoughLinesP(
            edged,
            1,
            np.pi / 180,
            threshold=max(40, int(min(w_img, h_img) * 0.08)),
            minLineLength=min_len,
            maxLineGap=max(8, int(min(w_img, h_img) * 0.02)),
        )

        candidates = []
        if lines is None or len(lines) < 4:
            return candidates

        segments = []
        for line in lines:
            coords = line.flatten()
            if len(coords) < 4:
                continue
            x1, y1, x2, y2 = map(float, coords[:4])
            dx, dy = x2 - x1, y2 - y1
            length = float(np.hypot(dx, dy))
            if length < min_len:
                continue
            segments.append(
                {
                    "pts": (x1, y1, x2, y2),
                    "length": length,
                    "mid_x": (x1 + x2) * 0.5,
                    "mid_y": (y1 + y2) * 0.5,
                    "horizontal": abs(dx) >= abs(dy),
                }
            )

        if len(segments) < 4:
            return candidates

        horizontal = sorted(
            (s for s in segments if s["horizontal"]),
            key=lambda item: item["length"],
            reverse=True,
        )[:6]
        vertical = sorted(
            (s for s in segments if not s["horizontal"]),
            key=lambda item: item["length"],
            reverse=True,
        )[:6]

        def _det(a, b):
            return (a[0] * b[1]) - (a[1] * b[0])

        def _intersection(seg_a, seg_b):
            x1, y1, x2, y2 = seg_a["pts"]
            x3, y3, x4, y4 = seg_b["pts"]
            xdiff = (x1 - x2, x3 - x4)
            ydiff = (y1 - y2, y3 - y4)
            div = _det(xdiff, ydiff)
            if abs(div) < 1e-6:
                return None
            d = (_det((x1, y1), (x2, y2)), _det((x3, y3), (x4, y4)))
            x = _det(d, xdiff) / div
            y = _det(d, ydiff) / div
            if not np.isfinite(x) or not np.isfinite(y):
                return None
            return np.array([x, y], dtype=np.float32)

        # Build perspective candidates. Pair separation avoids using duplicate
        # lines from the same physical edge.
        for hi in range(len(horizontal)):
            for hj in range(hi + 1, len(horizontal)):
                h1, h2 = horizontal[hi], horizontal[hj]
                if abs(h1["mid_y"] - h2["mid_y"]) < h_img * 0.05:
                    continue
                top, bottom = sorted((h1, h2), key=lambda item: item["mid_y"])

                for vi in range(len(vertical)):
                    for vj in range(vi + 1, len(vertical)):
                        v1, v2 = vertical[vi], vertical[vj]
                        if abs(v1["mid_x"] - v2["mid_x"]) < w_img * 0.05:
                            continue
                        left, right = sorted((v1, v2), key=lambda item: item["mid_x"])

                        tl = _intersection(top, left)
                        tr = _intersection(top, right)
                        br = _intersection(bottom, right)
                        bl = _intersection(bottom, left)
                        if any(p is None for p in (tl, tr, br, bl)):
                            continue

                        quad = np.array([tl, tr, br, bl], dtype=np.float32)
                        # Reject wildly extrapolated intersections early. The
                        # canonical validator performs the final geometry gate.
                        if (
                            np.any(quad[:, 0] < -w_img * 0.20)
                            or np.any(quad[:, 0] > w_img * 1.20)
                            or np.any(quad[:, 1] < -h_img * 0.20)
                            or np.any(quad[:, 1] > h_img * 1.20)
                        ):
                            continue

                        area_ratio = abs(cv2.contourArea(quad)) / float(w_img * h_img)
                        if 0.04 <= area_ratio <= 0.98:
                            candidates.append(np.round(quad).astype(np.int32))

        # Preserve a legacy-style fallback, but the new scorer no longer
        # rewards it merely for filling the image.
        pts = []
        for segment in segments:
            x1, y1, x2, y2 = segment["pts"]
            pts.extend([[int(x1), int(y1)], [int(x2), int(y2)]])
        if pts:
            pts_arr = np.asarray(pts, dtype=np.int32)
            x, y, bw, bh = cv2.boundingRect(pts_arr)
            quad = np.array(
                [[x, y], [x + bw, y], [x + bw, y + bh], [x, y + bh]],
                dtype=np.int32,
            )
            candidates.append(quad)

            rect = cv2.minAreaRect(pts_arr.astype(np.float32))
            box = cv2.boxPoints(rect)
            candidates.append(np.round(box).astype(np.int32))

        return candidates

    @staticmethod
    def generate_color_region_quad(image_cv: np.ndarray) -> List[np.ndarray]:
        """Generate region quads from luminance and chroma segmentation.

        Grayscale-only thresholding misses surfaces separated mainly by color
        rather than brightness. Otsu masks over HSV saturation and LAB chroma
        channels add those cases without introducing model dependencies.
        """
        gray = cv2.cvtColor(image_cv, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(image_cv, cv2.COLOR_BGR2HSV)
        lab = cv2.cvtColor(image_cv, cv2.COLOR_BGR2LAB)
        img_area = float(image_cv.shape[0] * image_cv.shape[1])

        masks = []
        gray_blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        adaptive = cv2.adaptiveThreshold(
            gray_blurred,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            51,
            5,
        )
        masks.extend((adaptive, cv2.bitwise_not(adaptive)))

        channels = (
            gray_blurred,
            cv2.GaussianBlur(hsv[:, :, 1], (5, 5), 0),
            cv2.GaussianBlur(lab[:, :, 1], (5, 5), 0),
            cv2.GaussianBlur(lab[:, :, 2], (5, 5), 0),
        )
        for channel in channels:
            _, otsu = cv2.threshold(
                channel, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
            )
            masks.extend((otsu, cv2.bitwise_not(otsu)))

        candidates = []
        for mask in masks:
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            cleaned = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
            contours, _ = cv2.findContours(
                cleaned, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE
            )
            contours = sorted(contours, key=cv2.contourArea, reverse=True)[:40]

            for contour in contours:
                area = float(abs(cv2.contourArea(contour)))
                if area < img_area * 0.025 or area > img_area * 0.985:
                    continue

                hull = cv2.convexHull(contour)
                peri = cv2.arcLength(hull, True)
                if peri <= 0:
                    continue

                for epsilon_ratio in (0.015, 0.025, 0.04, 0.06):
                    approx = cv2.approxPolyDP(
                        hull, epsilon_ratio * peri, True
                    )
                    if len(approx) == 4 and cv2.isContourConvex(approx):
                        candidates.append(approx.reshape(4, 2))

        return candidates

    # Removed heuristic generate_manual_prior_quad

class TemplateAnalyzer:
    def __init__(self):
        self.version = "v1.7"
        self.auto_approval_enabled = False
        
    def measure_edge_contrast(self, image_cv: np.ndarray, quad: np.ndarray) -> float:
        gray = cv2.cvtColor(image_cv, cv2.COLOR_BGR2GRAY)
        mask = np.zeros_like(gray)
        cv2.drawContours(mask, [quad.astype(np.int32)], 0, 255, 3)
        grad = cv2.morphologyEx(gray, cv2.MORPH_GRADIENT, np.ones((3,3),np.uint8))
        edge_strength = cv2.mean(grad, mask=mask)[0]
        return min(1.0, edge_strength / 128.0)

    @staticmethod
    def score_area_plausibility(area_ratio: float) -> float:
        """Score geometric coverage without rewarding near-full-frame quads.

        The previous scorer used raw area_ratio directly, so a bounding box
        covering almost the entire image received the strongest possible area
        contribution. Real EPIC-3 telemetry showed this systematically beating
        tighter, high-edge-contrast candidates. This transform is deliberately
        category-agnostic: it rewards a broad useful coverage band and only
        penalizes extreme tiny/full-frame geometry.
        """
        ar = float(np.clip(area_ratio, 0.0, 1.0))

        if ar <= 0.05:
            return 0.0
        if ar < 0.15:
            return (ar - 0.05) / 0.10
        if ar <= 0.60:
            return 1.0
        if ar <= 0.80:
            return 1.0 - (0.50 * ((ar - 0.60) / 0.20))
        if ar < 0.95:
            return 0.50 * (1.0 - ((ar - 0.80) / 0.15))
        return 0.0

    @classmethod
    def score_candidate(
        cls,
        area_ratio: float,
        line_score: float,
        candidate_agreement: float,
        orientation_score: float,
    ) -> Tuple[float, Dict[str, float]]:
        """Return bounded confidence and transparent component values.

        Edge evidence is the strongest runtime signal. Area is now a
        plausibility prior rather than a monotonic reward for larger boxes.
        No ground-truth information is used here.
        """
        area_score = cls.score_area_plausibility(area_ratio)
        line = float(np.clip(line_score, 0.0, 1.0))
        agreement = float(np.clip(candidate_agreement, 0.0, 1.0))
        orientation = float(np.clip(orientation_score, 0.0, 1.0))

        confidence = (
            (area_score * 0.20)
            + (line * 0.50)
            + (agreement * 0.20)
            + (orientation * 0.10)
        )
        components = {
            "area_ratio": float(np.clip(area_ratio, 0.0, 1.0)),
            "area_score": float(area_score),
            "line_score": line,
            "candidate_agreement": agreement,
            "orientation_score": orientation,
        }
        return float(np.clip(confidence, 0.0, 1.0)), components
        
    def analyze(self, filepath: str, category_folder: str, manual_geometry_prior: dict = None) -> dict:
        img = cv2.imdecode(np.fromfile(filepath, dtype=np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError(f"Could not read image {filepath}")
            
        h, w = img.shape[:2]
        try:
            rule = CategoryRuleEngine.get_rule_by_folder(category_folder)
        except ValueError:
            rule = {"key": "UNKNOWN"}
            
        best_quad = None
        best_conf = 0.0
        best_components = {}
        
        provenance = "AUTO"
        if manual_geometry_prior and "surface_quad" in manual_geometry_prior:
            cand = np.array(manual_geometry_prior["surface_quad"], dtype=np.float32)
            valid, msg = GeometryValidator.is_valid_quad(cand, w, h)
            if valid:
                best_quad = GeometryValidator.canonical_sort(cand).tolist()
                best_conf = 1.0
                best_components = {
                    "candidate_agreement": 1.0,
                    "line_score": 1.0,
                    "orientation_score": 1.0,
                    "manual_prior": 1.0
                }
                provenance = "MANUAL_PRIOR"
        else:
            # Pipeline: Generators -> Validator -> Scorer
            candidates = []
            candidates.extend(CandidateGenerators.generate_canny_contours(img))
            candidates.extend(CandidateGenerators.generate_hough_lines_quad(img))
            candidates.extend(CandidateGenerators.generate_color_region_quad(img))
            
            # Deduplicate and validate candidates. Multi-scale generators can
            # rediscover the same quad; duplicates must not artificially boost
            # candidate-agreement or distort the denominator.
            valid_cands = []
            seen_candidates = set()
            for cand in candidates:
                valid, msg = GeometryValidator.is_valid_quad(cand, w, h)
                if not valid:
                    continue

                canonical = GeometryValidator.canonical_sort(cand).astype(np.float32)
                key = tuple(
                    int(round(float(value)))
                    for point in canonical
                    for value in point
                )
                if key in seen_candidates:
                    continue
                seen_candidates.add(key)
                valid_cands.append(canonical)

            # Multi-scale generators intentionally trade precision for recall.
            # Keep runtime bounded by retaining a generous set of candidates
            # ranked only with runtime-visible evidence (never GT).
            max_candidates = 180
            if len(valid_cands) > max_candidates:
                pre_ranked = []
                for cand in valid_cands:
                    cand_area = abs(cv2.contourArea(cand.astype(np.float32)))
                    cand_area_ratio = min(1.0, cand_area / float(w * h))
                    cand_line = self.measure_edge_contrast(img, cand)
                    pre_score = (
                        self.score_area_plausibility(cand_area_ratio) * 0.35
                        + cand_line * 0.65
                    )
                    pre_ranked.append((pre_score, cand))
                pre_ranked.sort(key=lambda item: item[0], reverse=True)
                valid_cands = [item[1] for item in pre_ranked[:max_candidates]]

            candidate_stack = (
                np.stack(valid_cands).astype(np.float32)
                if valid_cands
                else np.empty((0, 4, 2), dtype=np.float32)
            )
            
            # Calculate agreement (how many candidates are similar to each
            # candidate). This preserves the previous distance definition but
            # performs the pairwise work in NumPy instead of a Python O(N^2)
            # inner loop.
            for i, cand1 in enumerate(valid_cands):
                diffs = candidate_stack - cand1
                distances = np.sqrt(np.sum(diffs * diffs, axis=(1, 2))) / max(float(w), 1.0)
                agreement_count = int(np.count_nonzero(distances < 0.05))
                
                area = cv2.contourArea(cand1.astype(np.float32))
                area_ratio = min(1.0, area / (w * h))
                
                line_score = self.measure_edge_contrast(img, cand1)
                
                # Real candidate agreement
                candidate_agreement = min(1.0, agreement_count / max(1, len(valid_cands)))
                
                # Real orientation score (does it match category expected orientation roughly?)
                # We calculate aspect ratio of cand1
                w_top = np.linalg.norm(cand1[1] - cand1[0])
                h_left = np.linalg.norm(cand1[3] - cand1[0])
                orient_score = 0.5
                if w_top > 0 and h_left > 0:
                    ar = w_top / h_left
                    cand_orient = "H" if ar > 1.05 else ("V" if ar < 0.95 else "SQUARE")
                    expected = rule.get("expected_orientation", "ANY")
                    if expected == "ANY":
                        orient_score = 1.0
                    elif expected == cand_orient:
                        orient_score = 1.0
                    else:
                        orient_score = 0.0
                        
                conf, comp_conf = self.score_candidate(
                    area_ratio=area_ratio,
                    line_score=line_score,
                    candidate_agreement=candidate_agreement,
                    orientation_score=orient_score,
                )
                
                if conf > best_conf:
                    best_conf = conf
                    best_quad = cand1.tolist()
                    best_components = comp_conf
                
        # Nominal aspect must NOT be calculated from quad. 
        # If no metadata, it is UNKNOWN.
        nominal_aspect = "UNKNOWN"
        orientation = "UNKNOWN"
        
        if best_quad:
            pts = np.array(best_quad)
            w_top = np.linalg.norm(pts[1] - pts[0])
            h_left = np.linalg.norm(pts[3] - pts[0])
            if w_top > 0 and h_left > 0:
                ar = w_top / h_left
                # Only guess orientation, do NOT trust aspect ratio for nominal print ratio
                orientation = "H" if ar > 1.05 else ("V" if ar < 0.95 else "SQUARE")
                
        if best_quad:
            if provenance == "MANUAL_PRIOR":
                status = "REVIEW_REQUIRED"
            elif self.auto_approval_enabled and best_conf > 0.85:
                status = "AUTO_PROPOSED" 
            else:
                status = "REVIEW_REQUIRED"
        else:
            status = "UNANALYZED"
            
        with open(filepath, "rb") as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()
            
        res = {
            "source_asset_sha256": file_hash,
            "provenance": provenance,
            "surface_quad": best_quad,
            "confidence_total": best_conf,
            "component_confidences": best_components,
            "review_status": status,
            "rule": rule,
            "orientation": orientation,
            "nominal_aspect": nominal_aspect,
            "analyzer_version": self.version
        }
        
        # Never fabricate frame geometry. Preserve an outer quad only when it comes
        # from trusted/manual geometry supplied to the analyzer.
        if isinstance(manual_geometry_prior, dict) and manual_geometry_prior.get("outer_quad") is not None:
            res["outer_quad"] = manual_geometry_prior["outer_quad"]
            
        return res

def save_template_profile(db_path: str, profile_data: dict):
    conn = sqlite3.connect(db_path)
    try:
        # Check if old active profile exists
        cur = conn.execute("SELECT id, source_asset_sha256, review_status, manually_verified FROM template_profiles WHERE template_uid = ? AND is_active = 1", (profile_data["template_uid"],))
        row = cur.fetchone()
        
        if row:
            old_id = row[0]
            old_hash = row[1]
            old_status = row[2]
            old_manual = row[3]
            new_hash = profile_data.get("source_asset_sha256")
            
            # If hash changed, mark old as inactive/stale and insert new
            if old_hash and new_hash and old_hash != new_hash:
                conn.execute("UPDATE template_profiles SET is_active = 0, review_status = 'STALE_SOURCE_CHANGED' WHERE id = ?", (old_id,))
                # Fallthrough to insert new proposal below
            else:
                if old_status == "APPROVED" and old_manual:
                    # Unchanged manually-approved profile must preserve approved geometry/data
                    return

                # Update in place if hash is same
                conn.execute("""
                UPDATE template_profiles SET
                    analyzer_version=?, surface_quad=?, outer_quad=?, orientation=?,
                    confidence_total=?, component_confidences=?, review_status=?, manually_verified=?,
                    updated_at=CURRENT_TIMESTAMP
                WHERE id=?
                """, (
                    profile_data["analyzer_version"], json.dumps(profile_data.get("surface_quad")),
                    json.dumps(profile_data.get("outer_quad")), profile_data["orientation"],
                    profile_data.get("confidence_total", 0.0), json.dumps(profile_data.get("component_confidences", {})),
                    profile_data["review_status"], profile_data.get("manually_verified", False), old_id
                ))
                conn.commit()
                return

        # Insert new active proposal
        conn.execute("""
        INSERT INTO template_profiles (
            template_uid, category, source_relative_path, source_asset_sha256,
            profile_version, analyzer_version, product_class, orientation,
            geometry_type, print_policy, surface_quad, outer_quad, surface_mask_path,
            material, has_frame, has_mat, has_reflection, has_occlusion,
            confidence_total, component_confidences, review_status, manually_verified, is_active
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        """, (
            profile_data["template_uid"], profile_data["category"], profile_data["source_relative_path"],
            profile_data.get("source_asset_sha256"), profile_data.get("profile_version","v2"), profile_data["analyzer_version"],
            profile_data.get("product_class","Unknown"), profile_data["orientation"], profile_data.get("geometry_type", "quad"),
            profile_data.get("print_policy","full_bleed"), json.dumps(profile_data.get("surface_quad")), json.dumps(profile_data.get("outer_quad")),
            profile_data.get("surface_mask_path"), profile_data.get("material", "default"),
            profile_data.get("has_frame", False), profile_data.get("has_mat", False),
            profile_data.get("has_reflection", False), profile_data.get("has_occlusion", False),
            profile_data.get("confidence_total", 0.0), json.dumps(profile_data.get("component_confidences", {})),
            profile_data["review_status"], profile_data.get("manually_verified", False)
        ))
        conn.commit()
    finally:
        conn.close()

class TemplateSelector:
    def __init__(self, db_path: str):
        self.db_path = db_path
        
    def select_template(self, design_orientation: str, category_folder: str, design_aspect: float = None) -> dict:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        # ONLY select APPROVED profiles
        cur = conn.execute('''
            SELECT * FROM template_profiles 
            WHERE category = ? AND review_status = 'APPROVED' AND is_active = 1
            ORDER BY confidence_total DESC
        ''', (category_folder,))
        
        rows = cur.fetchall()
        conn.close()
        
        if not rows:
            return {"status": "SKIPPED_NO_COMPATIBLE_TEMPLATE", "reason": "No approved templates in category"}
            
        try:
            rule = CategoryRuleEngine.get_rule_by_folder(category_folder)
        except ValueError:
             return {"status": "SKIPPED_UNKNOWN_CATEGORY", "reason": f"Unknown category: {category_folder}"}
        
        best_candidate = None
        best_score = -1.0
        orientation_mismatches = 0
        
        for row in rows:
            tmpl_orient = row["orientation"]
            if rule["orientation_strict"]:
                if design_orientation != tmpl_orient and tmpl_orient != "UNKNOWN":
                    orientation_mismatches += 1
                    continue
                    
            score = row["confidence_total"]
            
            # Reasoned aspect compatibility scoring (penalize if nominal aspect exists and mismatch is large)
            if design_aspect is not None and row["nominal_aspect"] and row["nominal_aspect"] != "UNKNOWN":
                try:
                    nom = float(row["nominal_aspect"])
                    diff = abs(nom - design_aspect)
                    if diff > 0.5:
                        continue # Skip entirely if hugely mismatched
                    score -= (diff * 0.5) # Penalize score
                except ValueError:
                    pass
            
            if score > best_score:
                best_score = score
                best_candidate = dict(row)
            
        if best_candidate:
            return {"status": "SELECTED", "template": best_candidate}
            
        if orientation_mismatches == len(rows):
            return {"status": "SKIPPED_ORIENTATION_MISMATCH", "reason": "All templates skipped due to orientation mismatch"}
            
        return {"status": "SKIPPED_NO_COMPATIBLE_TEMPLATE", "reason": "No compatible templates found due to aspect or other mismatch"}
