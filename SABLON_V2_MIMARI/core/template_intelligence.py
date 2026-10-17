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
    # Physical print aspect metadata (width / height). These values come from
    # product definitions, never from projected image quads.
    NOMINAL_ASPECTS = {
        "01_Wifi_Kutusu": {"H": 4.0 / 3.0, "V": 3.0 / 4.0},
        "02_Cam_Tablo_Dikey": {"V": 5.0 / 7.0},
        "02_Cam_Tablo_Yatay": {"H": 10.0 / 7.0},
        "03_Ahsap_Tablo": {"V": 2.0 / 3.0},
        "04_Cam_Dograma": {"H": 4.0 / 3.0, "V": 3.0 / 4.0},
        "05_Ocak_Arkasi": {"H": 4.0 / 3.0},
    }

    RULES = {
        "WOOD_FRAMED_ART": {
            "product_class": "Ahşap Tablo",
            "has_frame": True,
            "has_mat": False,
            "has_reflection": False,
            "print_policy": "inner_frame",
            "orientation_strict": True,
            "expected_orientation": "ANY",
            "physical_orientation": "V",
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
            "physical_orientation": "V",
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
            "physical_orientation": "H",
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
            "physical_orientation": "ANY",
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
            "physical_orientation": "H",
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
            "physical_orientation": "H",
            "folders": ["05_Ocak_Arkasi"]
        }
    }
    
    @classmethod
    def get_rule_by_folder(cls, folder_name: str) -> dict:
        for key, rule in cls.RULES.items():
            if folder_name in rule["folders"]:
                # Never mutate the class-level rule table while answering a
                # request. A copy keeps concurrent analyses deterministic.
                resolved = dict(rule)
                resolved["folders"] = list(rule.get("folders", []))
                resolved["key"] = key
                return resolved
        raise ValueError(f"UNKNOWN_CATEGORY: {folder_name}")

    @classmethod
    def get_nominal_aspect(cls, folder_name: str, orientation: str) -> Optional[float]:
        """Return trusted physical width/height metadata for a category/orientation."""
        mapping = cls.NOMINAL_ASPECTS.get(folder_name, {})
        value = mapping.get(str(orientation or "").upper())
        return float(value) if value is not None else None

class GeometryValidator:
    @staticmethod
    def canonical_sort(pts: np.ndarray) -> np.ndarray:
        """Return four vertices in a stable clockwise TL/TR/BR/BL cycle.

        The classic min(x+y)/min(y-x) shortcut can select the same vertex twice
        on diamond-like or strongly perspective quads because of ties. Sorting
        around the centroid first guarantees four unique vertices; rotating the
        cycle to the visually top-left vertex then gives deterministic ordering.
        """
        arr = np.asarray(pts)
        if arr.shape != (4, 2):
            return arr.copy()

        work = arr.astype(np.float64)
        center = np.mean(work, axis=0)
        angles = np.arctan2(work[:, 1] - center[1], work[:, 0] - center[0])
        order = np.argsort(angles)
        cycle = work[order]

        # With image coordinates (y grows downward), ascending atan2 normally
        # yields clockwise order. Enforce one winding explicitly.
        signed_twice_area = float(
            np.sum(
                cycle[:, 0] * np.roll(cycle[:, 1], -1)
                - np.roll(cycle[:, 0], -1) * cycle[:, 1]
            )
        )
        if signed_twice_area < 0:
            cycle = cycle[::-1]

        # Choose a deterministic top-left start. min(x+y) is useful when unique;
        # lexicographic y/x breaks ties without re-selecting a point.
        sums = cycle[:, 0] + cycle[:, 1]
        min_sum = float(np.min(sums))
        tied = np.flatnonzero(np.isclose(sums, min_sum, rtol=0.0, atol=1e-6))
        if len(tied) == 1:
            start = int(tied[0])
        else:
            start = min(
                (int(i) for i in tied),
                key=lambda i: (cycle[i, 1], cycle[i, 0]),
            )
        cycle = np.roll(cycle, -start, axis=0)
        return cycle.astype(arr.dtype, copy=False)

    @staticmethod
    def is_valid_quad(pts: np.ndarray, img_w: int, img_h: int) -> Tuple[bool, str]:
        if len(pts) != 4:
            return False, "Not 4 points"
            
        if img_w <= 0 or img_h <= 0:
            return False, "Invalid source image dimensions"

        # EPIC-3 invariant: geometry is evaluated only inside the real source
        # image. UI/canvas padding (often rendered as black) is not image data
        # and must never contribute to surface classification or scoring.
        max_x = float(img_w - 1)
        max_y = float(img_h - 1)
        for p in pts:
            x = float(p[0])
            y = float(p[1])
            if not np.isfinite(x) or not np.isfinite(y):
                return False, "Non-finite point"
            if x < 0.0 or x > max_x or y < 0.0 or y > max_y:
                return False, "Outside source image bounds"
                
        # Canonical sort for consistent edges FIRST
        sorted_pts = GeometryValidator.canonical_sort(pts)
        
        area = cv2.contourArea(sorted_pts.astype(np.float32))
        img_area = img_w * img_h
        if area < img_area * 0.05:
            return False, "Too small"
            
        if not cv2.isContourConvex(sorted_pts.astype(np.int32)):
            return False, "Not convex (self intersecting or concave)"
            
        edges = [sorted_pts[(i+1)%4] - sorted_pts[i] for i in range(4)]
        # NumPy 2.x deprecates np.cross(2D, 2D), generating tens of
        # thousands of warnings in geometry sweeps. The signed 2D scalar
        # determinant is identical and future-proof for 2-element vectors.
        cross_prods = [
            float(edges[i][0] * edges[(i + 1) % 4][1]
                  - edges[i][1] * edges[(i + 1) % 4][0])
            for i in range(4)
        ]
        
        # All must have same sign
        if not (all(cp > 0 for cp in cross_prods) or all(cp < 0 for cp in cross_prods)):
             return False, "Self-intersecting segment or invalid ordering (cross product sign flip)"
             
        # Aspect degeneracy check (max 10:1 ratio). Use both opposite
        # sides so perspective shortening of one edge does not misclassify an
        # otherwise valid plane.
        side_lengths = [float(np.linalg.norm(edge)) for edge in edges]
        if min(side_lengths) < 10:
            return False, "Degenerate edge length"
        avg_w = (side_lengths[0] + side_lengths[2]) * 0.5
        avg_h = (side_lengths[1] + side_lengths[3]) * 0.5
        if avg_w / avg_h > 10.0 or avg_h / avg_w > 10.0:
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

    @staticmethod
    def _quads_from_binary_mask(
        mask: np.ndarray,
        img_area: float,
        *,
        max_contours: int = 40,
    ) -> List[np.ndarray]:
        """Convert a binary surface mask into perspective quad proposals."""
        if mask is None or mask.size == 0:
            return []
        work = np.asarray(mask, dtype=np.uint8)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        work = cv2.morphologyEx(work, cv2.MORPH_CLOSE, kernel)
        work = cv2.morphologyEx(
            work,
            cv2.MORPH_OPEN,
            cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)),
        )
        contours, _ = cv2.findContours(
            work,
            cv2.RETR_LIST,
            cv2.CHAIN_APPROX_SIMPLE,
        )
        contours = sorted(
            contours,
            key=cv2.contourArea,
            reverse=True,
        )[:max_contours]

        candidates = []
        for contour in contours:
            area = float(abs(cv2.contourArea(contour)))
            if area < img_area * 0.025 or area > img_area * 0.985:
                continue
            hull = cv2.convexHull(contour)
            peri = cv2.arcLength(hull, True)
            if peri <= 0:
                continue

            for epsilon_ratio in (0.012, 0.02, 0.035, 0.055):
                approx = cv2.approxPolyDP(
                    hull,
                    epsilon_ratio * peri,
                    True,
                )
                if len(approx) == 4 and cv2.isContourConvex(approx):
                    candidates.append(approx.reshape(4, 2))

            rect = cv2.minAreaRect(hull.astype(np.float32))
            box = cv2.boxPoints(rect)
            if abs(cv2.contourArea(box.astype(np.float32))) >= img_area * 0.05:
                candidates.append(np.round(box).astype(np.int32))
        return candidates

    @staticmethod
    def generate_extreme_tone_quads(image_cv: np.ndarray) -> List[np.ndarray]:
        """Specialized proposals for very dark and very bright print surfaces.

        These masks are intentionally separate from generic Otsu segmentation.
        A black or white insert can be nearly textureless, so its outer tone
        transition is often more reliable than internal edges.
        """
        gray = cv2.cvtColor(image_cv, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(image_cv, cv2.COLOR_BGR2HSV)
        sat = hsv[:, :, 1]
        img_area = float(image_cv.shape[0] * image_cv.shape[1])

        masks = []
        for upper in (45, 70, 95):
            masks.append(
                np.where(gray <= upper, 255, 0).astype(np.uint8)
            )

        for lower, max_sat in ((175, 95), (200, 110), (225, 135)):
            masks.append(
                np.where(
                    (gray >= lower) & (sat <= max_sat),
                    255,
                    0,
                ).astype(np.uint8)
            )

        candidates = []
        for mask in masks:
            candidates.extend(
                CandidateGenerators._quads_from_binary_mask(
                    mask,
                    img_area,
                )
            )
        return candidates

    @staticmethod
    def generate_alpha_quads(alpha_channel: Optional[np.ndarray]) -> List[np.ndarray]:
        """Generate surface proposals from true PNG alpha when it exists."""
        if alpha_channel is None or alpha_channel.size == 0:
            return []
        alpha = np.asarray(alpha_channel, dtype=np.uint8)
        img_area = float(alpha.shape[0] * alpha.shape[1])
        if int(alpha.min()) == int(alpha.max()):
            return []

        masks = []
        partial = np.where(
            (alpha > 8) & (alpha < 247),
            255,
            0,
        ).astype(np.uint8)
        if np.count_nonzero(partial):
            masks.append(partial)

        for threshold in (24, 80, 144, 208):
            masks.append(
                np.where(alpha >= threshold, 255, 0).astype(np.uint8)
            )
            masks.append(
                np.where(alpha < threshold, 255, 0).astype(np.uint8)
            )

        candidates = []
        for mask in masks:
            candidates.extend(
                CandidateGenerators._quads_from_binary_mask(
                    mask,
                    img_area,
                )
            )
        return candidates

    @staticmethod
    def generate_low_contrast_glass_quads(
        image_cv: np.ndarray,
        category_folder: str = "",
    ) -> List[np.ndarray]:
        """Recover faint rectangular glass panels from weak border/reflection lines.

        Glass is often nearly the same tone as the wall behind it. Generic
        contour ranking then favors cabinets, counters, or tiles whose edges are
        much stronger. This generator enhances local contrast, keeps many long
        line segments, and forms quads from compatible horizontal/vertical line
        pairs before normal scoring/classification.
        """
        h_img, w_img = image_cv.shape[:2]
        if h_img < 40 or w_img < 40:
            return []

        # Ocak-arkasi panels physically live behind/above the cooktop. Excluding
        # the lower cabinet-heavy strip prevents strong cabinet edges from
        # dominating Hough voting while preserving normal compositions.
        roi_h = h_img
        if str(category_folder) == "05_Ocak_Arkasi":
            roi_h = max(40, int(round(h_img * 0.72)))
        roi = image_cv[:roi_h, :]

        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(
            clipLimit=4.0,
            tileGridSize=(8, 8),
        ).apply(gray)
        smooth = cv2.GaussianBlur(clahe, (1, 1), 0)

        edge_union = np.zeros_like(smooth)
        for low, high in ((8, 28), (14, 42), (24, 70)):
            edge_union = cv2.bitwise_or(
                edge_union,
                cv2.Canny(smooth, low, high),
            )

        # Additional pass for white/opaque panel borders: higher contrast,
        # no blur, lower Canny thresholds to catch subtle panel borders.
        clahe2 = cv2.createCLAHE(
            clipLimit=6.0,
            tileGridSize=(8, 8),
        ).apply(gray)
        for low, high in ((4, 16), (8, 32)):
            edge_union = cv2.bitwise_or(
                edge_union,
                cv2.Canny(clahe2, low, high),
            )

        edge_union = cv2.morphologyEx(
            edge_union,
            cv2.MORPH_CLOSE,
            cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)),
        )

        min_dim = min(w_img, roi_h)
        min_len = max(35, int(round(min_dim * 0.16)))
        lines = cv2.HoughLinesP(
            edge_union,
            1,
            np.pi / 180.0,
            threshold=max(15, int(round(min_dim * 0.045))),
            minLineLength=min_len,
            maxLineGap=max(10, int(round(min_dim * 0.04))),
        )
        if lines is None:
            return []

        horizontal = []
        vertical = []
        for line in lines:
            x1, y1, x2, y2 = map(float, line.flatten()[:4])
            dx = x2 - x1
            dy = y2 - y1
            length = float(np.hypot(dx, dy))
            if length < min_len:
                continue
            angle = abs(float(np.degrees(np.arctan2(dy, dx))))
            angle = min(angle, abs(180.0 - angle))
            item = {
                "pts": (x1, y1, x2, y2),
                "length": length,
                "mid_x": (x1 + x2) * 0.5,
                "mid_y": (y1 + y2) * 0.5,
            }
            if angle <= 18.0:
                horizontal.append(item)
            elif abs(angle - 90.0) <= 18.0:
                vertical.append(item)

        horizontal = sorted(
            horizontal,
            key=lambda item: item["length"],
            reverse=True,
        )[:24]
        vertical = sorted(
            vertical,
            key=lambda item: item["length"],
            reverse=True,
        )[:24]
        if len(horizontal) < 2 or len(vertical) < 2:
            return []

        def _line_intersection(a, b):
            x1, y1, x2, y2 = a["pts"]
            x3, y3, x4, y4 = b["pts"]
            den = ((x1 - x2) * (y3 - y4)) - (
                (y1 - y2) * (x3 - x4)
            )
            if abs(den) < 1e-6:
                return None
            det1 = (x1 * y2) - (y1 * x2)
            det2 = (x3 * y4) - (y3 * x4)
            px = (
                (det1 * (x3 - x4))
                - ((x1 - x2) * det2)
            ) / den
            py = (
                (det1 * (y3 - y4))
                - ((y1 - y2) * det2)
            ) / den
            return np.array([px, py], dtype=np.float32)

        h_pairs = []
        for i in range(len(horizontal)):
            for j in range(i + 1, len(horizontal)):
                a = horizontal[i]
                b = horizontal[j]
                sep = abs(a["mid_y"] - b["mid_y"])
                if sep < roi_h * 0.10 or sep > roi_h * 0.62:
                    continue
                top, bottom = (
                    (a, b)
                    if a["mid_y"] <= b["mid_y"]
                    else (b, a)
                )
                h_pairs.append((top, bottom))

        v_pairs = []
        for i in range(len(vertical)):
            for j in range(i + 1, len(vertical)):
                a = vertical[i]
                b = vertical[j]
                sep = abs(a["mid_x"] - b["mid_x"])
                if sep < w_img * 0.12 or sep > w_img * 0.82:
                    continue
                left, right = (
                    (a, b)
                    if a["mid_x"] <= b["mid_x"]
                    else (b, a)
                )
                v_pairs.append((left, right))

        candidates = []
        seen = set()
        for top, bottom in h_pairs:
            for left, right in v_pairs:
                tl = _line_intersection(top, left)
                tr = _line_intersection(top, right)
                br = _line_intersection(bottom, right)
                bl = _line_intersection(bottom, left)
                if any(point is None for point in (tl, tr, br, bl)):
                    continue

                quad = np.asarray([tl, tr, br, bl], dtype=np.float32)
                valid, _ = GeometryValidator.is_valid_quad(
                    quad,
                    w_img,
                    h_img,
                )
                if not valid:
                    continue

                canonical = GeometryValidator.canonical_sort(quad)
                center = np.mean(canonical, axis=0)
                cy = float(center[1]) / float(h_img)

                area_ratio = float(
                    abs(cv2.contourArea(canonical.astype(np.float32)))
                    / max(float(w_img * h_img), 1.0)
                )
                xs = canonical[:, 0]
                ys = canonical[:, 1]
                bbox_w_ratio = float(
                    (float(np.max(xs)) - float(np.min(xs)))
                    / max(float(w_img), 1.0)
                )
                bbox_h_ratio = float(
                    (float(np.max(ys)) - float(np.min(ys)))
                    / max(float(h_img), 1.0)
                )

                if str(category_folder) == "05_Ocak_Arkasi":
                    if cy > 0.67 or cy < 0.10:
                        continue
                    if area_ratio > 0.48:
                        continue
                    if bbox_w_ratio > 0.94 or bbox_h_ratio > 0.62:
                        continue

                top_w = np.linalg.norm(canonical[1] - canonical[0])
                bottom_w = np.linalg.norm(canonical[2] - canonical[3])
                left_h = np.linalg.norm(canonical[3] - canonical[0])
                right_h = np.linalg.norm(canonical[2] - canonical[1])
                avg_w = float((top_w + bottom_w) * 0.5)
                avg_h = float((left_h + right_h) * 0.5)
                if avg_h <= 1.0 or (avg_w / avg_h) < 0.85:
                    continue

                key = tuple(
                    int(round(float(value) / 3.0))
                    for point in canonical
                    for value in point
                )
                if key in seen:
                    continue
                seen.add(key)
                candidates.append(canonical.astype(np.float32))

                # Also add white panel candidates for ocak category before hitting the limit
        if str(category_folder) == "05_Ocak_Arkasi":
            white_panel_candidates = CandidateGenerators.generate_white_panel_quads(
                image_cv,
                category_folder,
            )
            for wp in white_panel_candidates:
                key = tuple(
                    int(round(float(value) / 3.0))
                    for point in wp
                    for value in point
                )
                if key not in seen:
                    seen.add(key)
                    candidates.append(wp)

        if len(candidates) >= 120:
            return candidates

        return candidates

    @staticmethod
    def generate_white_panel_quads(
        image_cv: np.ndarray,
        category_folder: str = "",
    ) -> List[np.ndarray]:
        """Detect white/opaque rectangular panels using color and contour analysis.

        This is specifically for ocak_arkasi white/opaque backsplash panels that
        may not have strong edge contrast but have distinct white interior
        and low saturation.
        """
        h_img, w_img = image_cv.shape[:2]
        if h_img < 40 or w_img < 40:
            return []

        # Only for ocak category
        if str(category_folder) != "05_Ocak_Arkasi":
            return []

        # Restrict to upper 72% where backsplash panels live
        roi_h = max(40, int(round(h_img * 0.72)))
        roi = image_cv[:roi_h, :]

        # Convert to HSV for white panel detection
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        
        # White panel: high Value (luma), low Saturation
        # Background wall: V~214, S~2.5
        # White panel: V~238, S~0
        # Use stricter V channel threshold to exclude background wall
        white_mask = cv2.inRange(
            hsv, 
            np.array([0, 0, 225], dtype=np.uint8), 
            np.array([180, 20, 255], dtype=np.uint8)
        )
        
        # Remove small noise
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        white_mask = cv2.morphologyEx(white_mask, cv2.MORPH_CLOSE, kernel)
        white_mask = cv2.morphologyEx(white_mask, cv2.MORPH_OPEN, kernel)
        
        # Find contours
        contours, _ = cv2.findContours(white_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        candidates = []
        seen = set()
        img_area = float(w_img * h_img)
        
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < img_area * 0.02:  # At least 2% of image
                continue
            if area > img_area * 0.50:  # Not full image
                continue
            
            # Approximate to polygon
            epsilon = 0.02 * cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, epsilon, True)
            
            if len(approx) == 4:
                quad = approx.reshape(4, 2).astype(np.float32)
            else:
                # Fit minimum area rectangle
                rect = cv2.minAreaRect(cnt)
                box = cv2.boxPoints(rect)
                quad = np.asarray(box, dtype=np.float32)
            
            # Validate
            valid, _ = GeometryValidator.is_valid_quad(quad, w_img, roi_h)
            if not valid:
                continue
                
            canonical = GeometryValidator.canonical_sort(quad)
            
            # Check if in backsplash zone
            center = np.mean(canonical, axis=0)
            cy = float(center[1]) / float(roi_h)
            if cy > 0.67 or cy < 0.10:
                continue
                
            area_ratio = float(abs(cv2.contourArea(canonical)) / max(float(w_img * roi_h), 1.0))
            if area_ratio > 0.48:
                continue
            
            # Check aspect ratio
            top_w = np.linalg.norm(canonical[1] - canonical[0])
            bottom_w = np.linalg.norm(canonical[2] - canonical[3])
            left_h = np.linalg.norm(canonical[3] - canonical[0])
            right_h = np.linalg.norm(canonical[2] - canonical[1])
            avg_w = (top_w + bottom_w) * 0.5
            avg_h = (left_h + right_h) * 0.5
            if avg_h <= 1.0 or (avg_w / avg_h) < 0.85:
                continue
            
            # Convert to full image coordinates
            canonical_full = canonical.copy()
            canonical_full[:, 1] = canonical_full[:, 1]  # Already in ROI coordinates
            
            key = tuple(
                int(round(float(value) / 3.0))
                for point in canonical_full
                for value in point
            )
            if key in seen:
                continue
            seen.add(key)
            candidates.append(canonical_full.astype(np.float32))
            
            if len(candidates) >= 20:
                break

        return candidates

    @staticmethod
    def generate_texture_robust_quads(image_cv: np.ndarray) -> List[np.ndarray]:
        """Suppress interior artwork/detail and recover the outer product border.

        Strong blur removes most text/design strokes before edge extraction.
        This is deliberately complementary to normal Canny/Hough generators.
        """
        gray = cv2.cvtColor(image_cv, cv2.COLOR_BGR2GRAY)
        smooth = cv2.GaussianBlur(gray, (15, 15), 0)
        img_area = float(image_cv.shape[0] * image_cv.shape[1])
        candidates = []

        masks = []
        for low, high in ((15, 55), (30, 95)):
            edge = cv2.Canny(smooth, low, high)
            edge = cv2.morphologyEx(
                edge,
                cv2.MORPH_CLOSE,
                cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7)),
            )
            masks.append(edge)

        grad = cv2.morphologyEx(
            smooth,
            cv2.MORPH_GRADIENT,
            cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7)),
        )
        _, grad_mask = cv2.threshold(
            grad,
            0,
            255,
            cv2.THRESH_BINARY + cv2.THRESH_OTSU,
        )
        masks.append(grad_mask)

        for mask in masks:
            candidates.extend(
                CandidateGenerators._quads_from_binary_mask(
                    mask,
                    img_area,
                )
            )

        # Reuse the line-pair geometry on a smoothed BGR image so high-frequency
        # artwork strokes cannot dominate Hough voting.
        smooth_bgr = cv2.cvtColor(smooth, cv2.COLOR_GRAY2BGR)
        candidates.extend(
            CandidateGenerators.generate_hough_lines_quad(smooth_bgr)
        )
        return candidates

    # Removed heuristic generate_manual_prior_quad

class TemplateAnalyzer:
    def __init__(self):
        self.version = "v2.8"
        self.auto_approval_enabled = False
        
    @staticmethod
    def classify_candidate_surface(
        image_cv: np.ndarray,
        quad: np.ndarray,
        alpha_channel: Optional[np.ndarray] = None,
        category_folder: str = "",
    ) -> Tuple[str, float, Dict[str, float]]:
        """Classify the candidate's printable interior into four surface modes.

        Modes are intentionally coarse and operational:
        BLACK, WHITE, TRANSPARENT_GLASS, DESIGNED_TEXTURED.
        """
        h, w = image_cv.shape[:2]
        canonical = GeometryValidator.canonical_sort(
            np.asarray(quad, dtype=np.float32)
        )
        mask = np.zeros((h, w), dtype=np.uint8)
        cv2.fillConvexPoly(mask, canonical.astype(np.int32), 255)

        area = int(np.count_nonzero(mask))
        if area <= 0:
            return "DESIGNED_TEXTURED", 0.0, {}

        # Ignore a thin border when measuring the interior so frame/shadow
        # pixels do not turn a white/black panel into a false textured surface.
        shrink = max(3, int(round(min(h, w) * 0.012)))
        kernel_size = (shrink * 2) + 1
        inner = cv2.erode(
            mask,
            cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE,
                (kernel_size, kernel_size),
            ),
        )
        if np.count_nonzero(inner) < max(64, area * 0.30):
            inner = mask

        gray = cv2.cvtColor(image_cv, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(image_cv, cv2.COLOR_BGR2HSV)
        pix = gray[inner > 0]
        sat_pix = hsv[:, :, 1][inner > 0]

        mean_luma = float(np.mean(pix))
        std_luma = float(np.std(pix))
        mean_sat = float(np.mean(sat_pix))

        edge_map = cv2.Canny(gray, 40, 120)
        edge_density = float(
            np.count_nonzero(edge_map[inner > 0])
            / max(1, np.count_nonzero(inner))
        )

        ring_size = max(5, int(round(min(h, w) * 0.02)))
        ring_kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE,
            ((ring_size * 2) + 1, (ring_size * 2) + 1),
        )
        outer = cv2.dilate(mask, ring_kernel)
        ring = cv2.subtract(outer, mask)
        ring_pix = gray[ring > 0]
        ring_delta = (
            abs(mean_luma - float(np.mean(ring_pix)))
            if ring_pix.size
            else 255.0
        )

        alpha_partial = 0.0
        alpha_delta = 0.0
        if (
            alpha_channel is not None
            and alpha_channel.shape[:2] == (h, w)
        ):
            alpha = np.asarray(alpha_channel, dtype=np.uint8)
            inside_alpha = alpha[inner > 0]
            if inside_alpha.size:
                alpha_partial = float(
                    np.count_nonzero(
                        (inside_alpha > 8) & (inside_alpha < 247)
                    ) / inside_alpha.size
                )
                if ring_pix.size:
                    ring_alpha = alpha[ring > 0]
                    if ring_alpha.size:
                        alpha_delta = abs(
                            float(np.mean(inside_alpha))
                            - float(np.mean(ring_alpha))
                        )

        glass_category = (
            "Cam" in str(category_folder)
            or "Ocak_Arkasi" in str(category_folder)
        )
        optical_similarity = float(
            np.clip((42.0 - ring_delta) / 42.0, 0.0, 1.0)
        )
        low_texture = float(
            np.clip((0.14 - edge_density) / 0.14, 0.0, 1.0)
        )
        transparent_optical_score = float(
            np.clip(
                (optical_similarity * 0.62)
                + (low_texture * 0.38),
                0.0,
                1.0,
            )
        )

        metrics = {
            "mean_luma": mean_luma,
            "std_luma": std_luma,
            "mean_saturation": mean_sat,
            "edge_density": edge_density,
            "ring_luma_delta": float(ring_delta),
            "alpha_partial_ratio": alpha_partial,
            "alpha_delta": float(alpha_delta),
            "transparent_optical_score": transparent_optical_score,
        }

        if alpha_partial >= 0.08:
            confidence = min(
                1.0,
                0.70 + (alpha_partial * 0.30),
            )
            return "TRANSPARENT_GLASS", confidence, metrics

        # Strong glass evidence has first priority in glass-capable categories.
        # This is intentionally checked before BLACK/WHITE so a dark or bright
        # scene seen through clear glass is not mislabeled by its background.
        # The threshold is stricter here to preserve the proven solid-black path.
        if (
            glass_category
            and ring_delta <= 24.0
            and edge_density <= 0.095
            and transparent_optical_score >= 0.72
        ):
            confidence = float(
                0.60 + (0.35 * transparent_optical_score)
            )
            return (
                "TRANSPARENT_GLASS",
                min(0.97, confidence),
                metrics,
            )

        if mean_luma <= 78.0 and std_luma <= 72.0:
            darkness = np.clip((95.0 - mean_luma) / 95.0, 0.0, 1.0)
            uniformity = np.clip((90.0 - std_luma) / 90.0, 0.0, 1.0)
            confidence = float(0.60 + 0.25 * darkness + 0.15 * uniformity)
            return "BLACK", min(1.0, confidence), metrics

        # Weaker optical glass evidence still precedes WHITE. This catches
        # clear panels on light walls without letting ambiguous dark regions
        # steal the solid-black classification.
        if (
            glass_category
            and ring_delta <= 36.0
            and edge_density <= 0.115
            and transparent_optical_score >= 0.52
        ):
            confidence = float(
                0.52 + (0.43 * transparent_optical_score)
            )
            return (
                "TRANSPARENT_GLASS",
                min(0.95, confidence),
                metrics,
            )

        if (
            mean_luma >= 182.0
            and mean_sat <= 105.0
            and std_luma <= 78.0
        ):
            brightness = np.clip((mean_luma - 165.0) / 90.0, 0.0, 1.0)
            neutrality = np.clip((125.0 - mean_sat) / 125.0, 0.0, 1.0)
            confidence = float(
                0.58 + 0.24 * brightness + 0.18 * neutrality
            )
            return "WHITE", min(1.0, confidence), metrics

        texture = np.clip(std_luma / 75.0, 0.0, 1.0)
        edges = np.clip(edge_density / 0.12, 0.0, 1.0)
        confidence = float(0.50 + 0.30 * texture + 0.20 * edges)
        return "DESIGNED_TEXTURED", min(1.0, confidence), metrics

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

    @staticmethod
    def is_category_auto_candidate_plausible(
        category_folder: str,
        quad: np.ndarray,
        img_w: int,
        img_h: int,
    ) -> Tuple[bool, str]:
        """Apply category-only guards to AUTO proposals, never manual geometry.

        Ocak Arkasi is a horizontal glass panel mounted behind/above the
        cooktop. Strong cabinet, ceiling, wall, and full-scene rectangles are
        common false positives and are not valid automatic product surfaces.
        """
        if str(category_folder) != "05_Ocak_Arkasi":
            return True, "category-unconstrained"
        if img_w <= 0 or img_h <= 0:
            return False, "invalid-image-dimensions"

        pts = GeometryValidator.canonical_sort(
            np.asarray(quad, dtype=np.float32)
        )
        area = float(abs(cv2.contourArea(pts)))
        image_area = float(img_w * img_h)
        if image_area <= 0:
            return False, "invalid-image-area"

        area_ratio = area / image_area
        center = np.mean(pts, axis=0)
        cx = float(center[0]) / float(img_w)
        cy = float(center[1]) / float(img_h)

        top_w = float(np.linalg.norm(pts[1] - pts[0]))
        bottom_w = float(np.linalg.norm(pts[2] - pts[3]))
        left_h = float(np.linalg.norm(pts[3] - pts[0]))
        right_h = float(np.linalg.norm(pts[2] - pts[1]))
        avg_w = max(1.0, (top_w + bottom_w) * 0.5)
        avg_h = max(1.0, (left_h + right_h) * 0.5)
        projected_aspect = avg_w / avg_h

        xs = pts[:, 0]
        ys = pts[:, 1]
        bbox_w_ratio = float(
            (float(np.max(xs)) - float(np.min(xs)))
            / max(float(img_w), 1.0)
        )
        bbox_h_ratio = float(
            (float(np.max(ys)) - float(np.min(ys)))
            / max(float(img_h), 1.0)
        )

        # Product-scale guard: a backsplash may be prominent, but it is not
        # the entire photographed kitchen/wall.
        if area_ratio < 0.025:
            return False, "too-small-for-ocak-arkasi"
        if area_ratio > 0.48:
            return False, "too-large-full-scene"
        if bbox_w_ratio > 0.94 or bbox_h_ratio > 0.62:
            return False, "scene-spanning-rectangle"

        # Location guard: lower cabinet fronts are not the print surface.
        if cy > 0.68:
            return False, "below-backsplash-zone"
        if cy < 0.10:
            return False, "above-backsplash-zone"
        if cx < 0.08 or cx > 0.92:
            return False, "off-center-backsplash-zone"

        # Physical product is horizontal. Perspective can compress it, so the
        # lower bound remains permissive while eliminating tall room/wall boxes.
        if projected_aspect < 0.82 or projected_aspect > 5.0:
            return False, "implausible-projected-aspect"

        return True, "plausible"

    @staticmethod
    def score_category_spatial_prior(
        category_folder: str,
        quad: np.ndarray,
        img_w: int,
        img_h: int,
    ) -> float:
        """Weak domain prior used only to break visually ambiguous ties.

        Ocak-arkasi product surfaces are physically behind/above the cooktop.
        Cabinet doors below the worktop are a common strong-edge distractor.
        The prior stays deliberately weak so geometry/visual evidence still
        dominates and unusual compositions remain reviewable.
        """
        if img_w <= 0 or img_h <= 0:
            return 0.5

        pts = GeometryValidator.canonical_sort(
            np.asarray(quad, dtype=np.float32)
        )
        center = np.mean(pts, axis=0)
        cx = float(center[0]) / float(img_w)
        cy = float(center[1]) / float(img_h)

        if str(category_folder) == "05_Ocak_Arkasi":
            x_score = float(
                np.clip(1.0 - (abs(cx - 0.5) / 0.5), 0.0, 1.0)
            )
            if cy <= 0.62:
                y_score = float(
                    np.clip(
                        1.0 - (abs(cy - 0.42) / 0.42),
                        0.0,
                        1.0,
                    )
                )
                y_score = max(0.55, y_score)
            elif cy < 0.82:
                y_score = float(
                    np.clip((0.82 - cy) / 0.20, 0.0, 1.0)
                ) * 0.55
            else:
                y_score = 0.0
            return float(
                np.clip(
                    (x_score * 0.35) + (y_score * 0.65),
                    0.0,
                    1.0,
                )
            )

        return 0.5

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
        
    def select_ocak_arkasi_special_candidate(
        self,
        image_cv: np.ndarray,
        candidates: List[np.ndarray],
        alpha_channel: Optional[np.ndarray] = None,
    ) -> Optional[dict]:
        """Pick the real backsplash panel without changing generic detectors.

        This selector is intentionally scoped to 05_Ocak_Arkasi only. It may
        accept either optically transparent glass or a white/opaque-looking
        glass panel, because real mockups can show the same physical product in
        both states. Strong cabinet/wall rectangles are penalized by product
        scale, aspect, texture and boundary evidence.
        """
        h, w = image_cv.shape[:2]
        if not candidates or h <= 0 or w <= 0:
            return None

        records = []
        seen = set()
        for candidate in candidates:
            quad = GeometryValidator.canonical_sort(
                np.asarray(candidate, dtype=np.float32)
            )
            valid, _ = GeometryValidator.is_valid_quad(quad, w, h)
            if not valid:
                continue

            plausible, _ = self.is_category_auto_candidate_plausible(
                "05_Ocak_Arkasi",
                quad,
                w,
                h,
            )
            if not plausible:
                continue

            key = tuple(
                int(round(float(value) / 3.0))
                for point in quad
                for value in point
            )
            if key in seen:
                continue
            seen.add(key)

            area = float(abs(cv2.contourArea(quad)))
            area_ratio = area / max(float(w * h), 1.0)

            top_w = float(np.linalg.norm(quad[1] - quad[0]))
            bottom_w = float(np.linalg.norm(quad[2] - quad[3]))
            left_h = float(np.linalg.norm(quad[3] - quad[0]))
            right_h = float(np.linalg.norm(quad[2] - quad[1]))
            avg_w = max(1.0, (top_w + bottom_w) * 0.5)
            avg_h = max(1.0, (left_h + right_h) * 0.5)
            aspect = avg_w / avg_h

            center = np.mean(quad, axis=0)
            cx = float(center[0]) / float(w)
            cy = float(center[1]) / float(h)

            mode, mode_conf, metrics = self.classify_candidate_surface(
                image_cv,
                quad,
                alpha_channel=alpha_channel,
                category_folder="05_Ocak_Arkasi",
            )

            mean_luma = float(metrics.get("mean_luma", 0.0))
            std_luma = float(metrics.get("std_luma", 255.0))
            mean_sat = float(metrics.get("mean_saturation", 255.0))
            optical = float(
                metrics.get("transparent_optical_score", 0.0)
            )
            edge_density = float(metrics.get("edge_density", 1.0))

            transparent_score = (
                float(mode_conf)
                if mode == "TRANSPARENT_GLASS"
                else optical * 0.90
            )
            white_glass_score = float(
                np.clip((mean_luma - 150.0) / 95.0, 0.0, 1.0)
                * np.clip((125.0 - mean_sat) / 125.0, 0.0, 1.0)
                * np.clip((85.0 - std_luma) / 85.0, 0.0, 1.0)
            )
            surface_score = max(
                transparent_score,
                white_glass_score,
            )

            # Ocak-arkasi mockups are normally a moderate horizontal panel,
            # not a full room/wall rectangle. These are soft scores so genuine
            # perspective remains possible.
            area_score = float(
                np.exp(-((area_ratio - 0.17) / 0.14) ** 2)
            )
            aspect_score = float(
                np.exp(-((aspect - 1.55) / 1.10) ** 2)
            )
            position_score = float(
                np.clip(
                    1.0
                    - (abs(cy - 0.43) / 0.36)
                    - (0.35 * abs(cx - 0.52)),
                    0.0,
                    1.0,
                )
            )
            low_texture_score = float(
                np.clip((0.13 - edge_density) / 0.13, 0.0, 1.0)
            )
            boundary_score = float(
                self.measure_edge_contrast(image_cv, quad)
            )

            xs = quad[:, 0]
            ys = quad[:, 1]
            bbox_w_ratio = float(
                (float(np.max(xs)) - float(np.min(xs)))
                / max(float(w), 1.0)
            )
            bbox_h_ratio = float(
                (float(np.max(ys)) - float(np.min(ys)))
                / max(float(h), 1.0)
            )
            scene_penalty = 0.0
            if area_ratio > 0.38:
                scene_penalty += min(0.35, (area_ratio - 0.38) * 1.7)
            if bbox_w_ratio > 0.86:
                scene_penalty += min(
                    0.25,
                    (bbox_w_ratio - 0.86) * 1.5,
                )
            if bbox_h_ratio > 0.50:
                scene_penalty += min(
                    0.25,
                    (bbox_h_ratio - 0.50) * 1.5,
                )

            score = (
                (surface_score * 0.34)
                + (area_score * 0.18)
                + (aspect_score * 0.16)
                + (position_score * 0.14)
                + (low_texture_score * 0.10)
                + (boundary_score * 0.08)
                - scene_penalty
            )
            score = float(np.clip(score, 0.0, 1.0))

            records.append({
                "quad": quad,
                "score": score,
                "mode": mode,
                "mode_confidence": float(mode_conf),
                "surface_score": float(surface_score),
                "metrics": metrics,
                "area_ratio": float(area_ratio),
                "aspect": float(aspect),
                "position_score": float(position_score),
                "boundary_score": float(boundary_score),
            })

        if not records:
            return None

        chosen = max(records, key=lambda item: item["score"])

        # Keep the special mode conservative. If the candidate is not clearly
        # panel-like, fall back to the existing generic pipeline instead of
        # forcing another wrong rectangle.
        if chosen["score"] < 0.57:
            return None
        if chosen["surface_score"] < 0.42:
            return None
        if chosen["area_ratio"] > 0.42:
            return None
        if not (0.90 <= chosen["aspect"] <= 4.25):
            return None

        return chosen

    def analyze(self, filepath: str, category_folder: str, manual_geometry_prior: dict = None) -> dict:
        raw = cv2.imdecode(
            np.fromfile(filepath, dtype=np.uint8),
            cv2.IMREAD_UNCHANGED,
        )
        if raw is None:
            raise ValueError(f"Could not read image {filepath}")

        alpha_channel = None
        if raw.ndim == 2:
            img = cv2.cvtColor(raw, cv2.COLOR_GRAY2BGR)
        elif raw.ndim == 3 and raw.shape[2] == 4:
            alpha_channel = raw[:, :, 3].copy()
            img = raw[:, :, :3].copy()
        elif raw.ndim == 3 and raw.shape[2] >= 3:
            img = raw[:, :, :3].copy()
        else:
            raise ValueError(f"Unsupported image shape {raw.shape} for {filepath}")

        h, w = img.shape[:2]
        try:
            rule = CategoryRuleEngine.get_rule_by_folder(category_folder)
        except ValueError:
            rule = {"key": "UNKNOWN"}
            
        best_quad = None
        best_conf = 0.0
        best_components = {}
        best_surface_mode = "UNKNOWN"
        best_surface_mode_confidence = 0.0
        
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
        if (
            best_quad is None
            and str(category_folder) == "05_Ocak_Arkasi"
        ):
            ocak_special_candidates = (
                CandidateGenerators.generate_low_contrast_glass_quads(
                    img,
                    category_folder,
                )
            )
            # Also try white panel detector for opaque white panels
            white_panel_candidates = (
                CandidateGenerators.generate_white_panel_quads(
                    img,
                    category_folder,
                )
            )
            if white_panel_candidates:
                ocak_special_candidates.extend(white_panel_candidates)
            ocak_special = self.select_ocak_arkasi_special_candidate(
                img,
                ocak_special_candidates,
                alpha_channel=alpha_channel,
            )
            if ocak_special is not None:
                best_quad = (
                    np.asarray(
                        ocak_special["quad"],
                        dtype=np.float32,
                    )
                    .astype(float)
                    .tolist()
                )
                best_conf = float(ocak_special["score"])
                best_surface_mode = str(ocak_special["mode"])
                best_surface_mode_confidence = float(
                    ocak_special["mode_confidence"]
                )
                best_components = {
                    "ocak_arkasi_special_mode": 1.0,
                    "surface_mode_score": float(
                        ocak_special["surface_score"]
                    ),
                    "category_spatial_prior": float(
                        ocak_special["position_score"]
                    ),
                    "line_score": float(
                        ocak_special["boundary_score"]
                    ),
                    "area_ratio": float(
                        ocak_special["area_ratio"]
                    ),
                    "special_candidate_score": float(
                        ocak_special["score"]
                    ),
                    "glass_priority_selected": 1.0,
                }
                provenance = "AUTO_OCAK_ARKASI_SPECIAL"

        if best_quad is None:
            # Pipeline: Generators -> Validator -> Scorer.
            # An invalid manual prior must never suppress automatic recovery.
            candidates = []
            candidates.extend(CandidateGenerators.generate_canny_contours(img))
            candidates.extend(CandidateGenerators.generate_hough_lines_quad(img))
            candidates.extend(CandidateGenerators.generate_color_region_quad(img))
            candidates.extend(
                CandidateGenerators.generate_extreme_tone_quads(img)
            )
            candidates.extend(
                CandidateGenerators.generate_low_contrast_glass_quads(
                    img,
                    category_folder,
                )
            )
            candidates.extend(
                CandidateGenerators.generate_texture_robust_quads(img)
            )
            candidates.extend(
                CandidateGenerators.generate_alpha_quads(alpha_channel)
            )
            
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
                category_ok, _category_reason = (
                    self.is_category_auto_candidate_plausible(
                        category_folder,
                        canonical,
                        w,
                        h,
                    )
                )
                if not category_ok:
                    continue

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
            scored_candidates = []
            for i, cand1 in enumerate(valid_cands):
                diffs = candidate_stack - cand1
                distances = np.sqrt(np.sum(diffs * diffs, axis=(1, 2))) / max(float(w), 1.0)
                agreement_count = int(np.count_nonzero(distances < 0.05))
                
                area = cv2.contourArea(cand1.astype(np.float32))
                area_ratio = min(1.0, area / (w * h))
                
                line_score = self.measure_edge_contrast(img, cand1)
                
                # Consensus is a LOCAL signal, not "fraction of every proposal".
                # Multi-scale generators can legitimately emit 100+ distinct
                # candidates; dividing by that global count would collapse even
                # a strong 3-4 candidate cluster to ~0.02 and make agreement
                # meaningless. A four-vote saturation keeps the signal stable
                # as generator recall grows: singleton=.25, pair=.50, 3=.75,
                # 4+=1.0. The candidate itself is one of those votes.
                candidate_agreement = min(1.0, agreement_count / 4.0)
                
                # Real orientation score. Opposite-edge averages are more
                # stable under perspective than using only top/left edges.
                w_top = np.linalg.norm(cand1[1] - cand1[0])
                w_bottom = np.linalg.norm(cand1[2] - cand1[3])
                h_left = np.linalg.norm(cand1[3] - cand1[0])
                h_right = np.linalg.norm(cand1[2] - cand1[1])
                avg_w = (w_top + w_bottom) * 0.5
                avg_h = (h_left + h_right) * 0.5
                orient_score = 0.5
                if avg_w > 0 and avg_h > 0:
                    ar = avg_w / avg_h
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

                surface_mode, surface_mode_conf, surface_metrics = (
                    self.classify_candidate_surface(
                        img,
                        cand1,
                        alpha_channel=alpha_channel,
                        category_folder=category_folder,
                    )
                )

                is_glass_category = (
                    "Cam" in str(category_folder)
                    or "Ocak_Arkasi" in str(category_folder)
                )
                if (
                    is_glass_category
                    and surface_mode == "TRANSPARENT_GLASS"
                ):
                    mode_weight = 0.22
                elif surface_mode in ("BLACK", "WHITE"):
                    mode_weight = 0.10
                else:
                    mode_weight = 0.04

                spatial_prior = self.score_category_spatial_prior(
                    category_folder,
                    cand1,
                    w,
                    h,
                )
                spatial_weight = (
                    0.14
                    if str(category_folder) == "05_Ocak_Arkasi"
                    else 0.0
                )

                conf = min(
                    1.0,
                    conf
                    + (mode_weight * float(surface_mode_conf))
                    + (spatial_weight * float(spatial_prior)),
                )
                comp_conf["surface_mode_score"] = float(
                    surface_mode_conf
                )
                comp_conf["category_spatial_prior"] = float(
                    spatial_prior
                )
                comp_conf["transparent_optical_score"] = float(
                    surface_metrics.get(
                        "transparent_optical_score",
                        0.0,
                    )
                )

                scored_candidates.append({
                    "quad": cand1,
                    "confidence": float(conf),
                    "components": dict(comp_conf),
                    "surface_mode": surface_mode,
                    "surface_mode_confidence": float(surface_mode_conf),
                    "surface_metrics": dict(surface_metrics),
                    "spatial_prior": float(spatial_prior),
                })

                if conf > best_conf:
                    best_conf = conf
                    best_quad = cand1.tolist()
                    best_components = comp_conf
                    best_surface_mode = surface_mode
                    best_surface_mode_confidence = float(surface_mode_conf)

            # User/domain contract: in glass-capable categories, a trustworthy
            # transparent/glass candidate wins before solid black/white/textured
            # candidates. This is a tiered selection rule, not merely a small
            # score bonus. It prevents strong cabinet/door edges from stealing
            # Ocak-Arkasi selections when a faint real glass panel exists.
            glass_capable = bool(rule.get("has_reflection")) or (
                "Cam" in str(category_folder)
                or "Ocak_Arkasi" in str(category_folder)
            )
            if glass_capable and scored_candidates:
                glass_candidates = []
                for record in scored_candidates:
                    if record["surface_mode"] != "TRANSPARENT_GLASS":
                        continue
                    metrics = record["surface_metrics"]
                    optical = float(
                        metrics.get("transparent_optical_score", 0.0)
                    )
                    alpha_ratio = float(
                        metrics.get("alpha_partial_ratio", 0.0)
                    )
                    if record["surface_mode_confidence"] < 0.62:
                        continue
                    if max(optical, alpha_ratio) < 0.50:
                        continue

                    quad_arr = np.asarray(
                        record["quad"],
                        dtype=np.float32,
                    )
                    center = np.mean(quad_arr, axis=0)
                    cy = float(center[1]) / max(float(h), 1.0)
                    area_ratio = float(
                        abs(cv2.contourArea(quad_arr))
                        / max(float(w * h), 1.0)
                    )
                    category_ok, _ = (
                        self.is_category_auto_candidate_plausible(
                            category_folder,
                            quad_arr,
                            w,
                            h,
                        )
                    )
                    if not category_ok:
                        continue
                    if (
                        str(category_folder) == "05_Ocak_Arkasi"
                        and (
                            cy > 0.67
                            or area_ratio > 0.48
                            or record["spatial_prior"] < 0.46
                        )
                    ):
                        continue
                    glass_candidates.append(record)

                if glass_candidates:
                    chosen = max(
                        glass_candidates,
                        key=lambda record: (
                            record["confidence"]
                            + (0.24 * record["spatial_prior"])
                            + (
                                0.10
                                * float(
                                    record["surface_metrics"].get(
                                        "transparent_optical_score",
                                        0.0,
                                    )
                                )
                            )
                        ),
                    )
                    best_conf = float(chosen["confidence"])
                    best_quad = chosen["quad"].tolist()
                    best_components = dict(chosen["components"])
                    best_components["glass_priority_selected"] = 1.0
                    best_surface_mode = "TRANSPARENT_GLASS"
                    best_surface_mode_confidence = float(
                        chosen["surface_mode_confidence"]
                    )
                
        if best_quad and best_surface_mode == "UNKNOWN":
            (
                best_surface_mode,
                best_surface_mode_confidence,
                _surface_metrics,
            ) = self.classify_candidate_surface(
                img,
                np.asarray(best_quad, dtype=np.float32),
                alpha_channel=alpha_channel,
                category_folder=category_folder,
            )
            best_components["surface_mode_score"] = float(
                best_surface_mode_confidence
            )

        # Physical orientation/aspect metadata must never be inferred from
        # projected image geometry. A perspective quad may look wider than tall
        # even when the real product is physically vertical.
        nominal_aspect = "UNKNOWN"
        orientation = "UNKNOWN"
        projected_orientation = "UNKNOWN"

        if best_quad:
            pts = np.asarray(best_quad, dtype=np.float32)
            w_top = np.linalg.norm(pts[1] - pts[0])
            w_bottom = np.linalg.norm(pts[2] - pts[3])
            h_left = np.linalg.norm(pts[3] - pts[0])
            h_right = np.linalg.norm(pts[2] - pts[1])
            avg_w = (w_top + w_bottom) * 0.5
            avg_h = (h_left + h_right) * 0.5
            if avg_w > 0 and avg_h > 0:
                ar = avg_w / avg_h
                projected_orientation = (
                    "H" if ar > 1.05 else ("V" if ar < 0.95 else "SQUARE")
                )

        physical_rule_orientation = rule.get("physical_orientation", "ANY")
        if physical_rule_orientation in ("H", "V"):
            orientation = physical_rule_orientation
        elif isinstance(manual_geometry_prior, dict):
            prior_orientation = str(
                manual_geometry_prior.get("physical_orientation") or ""
            ).upper()
            if prior_orientation in ("H", "V"):
                orientation = prior_orientation

        physical_aspect = CategoryRuleEngine.get_nominal_aspect(
            category_folder,
            orientation,
        )
        if physical_aspect is not None:
            nominal_aspect = f"{physical_aspect:.8f}".rstrip("0").rstrip(".")
                
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
            "surface_mode": best_surface_mode,
            "surface_mode_confidence": float(best_surface_mode_confidence),
            "review_status": status,
            "rule": rule,
            "orientation": orientation,
            "projected_orientation": projected_orientation,
            "nominal_aspect": nominal_aspect,
            "analyzer_version": self.version
        }
        
        # Never fabricate frame geometry. Preserve an outer quad only when
        # trusted/manual geometry is itself a valid quad for these exact image
        # dimensions.
        if (
            provenance == "MANUAL_PRIOR"
            and isinstance(manual_geometry_prior, dict)
            and manual_geometry_prior.get("outer_quad") is not None
        ):
            try:
                outer = np.asarray(
                    manual_geometry_prior["outer_quad"],
                    dtype=np.float32,
                )
                outer_valid, _ = GeometryValidator.is_valid_quad(outer, w, h)
                if outer_valid:
                    res["outer_quad"] = (
                        GeometryValidator.canonical_sort(outer)
                        .astype(float)
                        .tolist()
                    )
            except (TypeError, ValueError):
                pass
            
        return res

def save_template_profile(db_path: str, profile_data: dict):
    conn = sqlite3.connect(db_path, timeout=30)
    conn.execute("PRAGMA busy_timeout = 30000")
    try:
        # Serialize profile replacement so two concurrent analyze/review calls
        # cannot both observe "no active row" and insert duplicate active
        # profiles for the same template_uid.
        conn.execute("BEGIN IMMEDIATE")
        new_hash = profile_data.get("source_asset_sha256")
        active_rows = conn.execute(
            """SELECT rowid AS profile_rowid, source_asset_sha256, review_status, manually_verified
               FROM template_profiles
               WHERE template_uid=? AND is_active=1
               ORDER BY updated_at DESC, rowid DESC""",
            (profile_data["template_uid"],),
        ).fetchall()

        row = None
        if active_rows:
            # Preserve a source-matching manually-approved row first, otherwise
            # a source-matching row, otherwise the newest active row.
            row = next(
                (
                    candidate
                    for candidate in active_rows
                    if candidate[1] == new_hash
                    and candidate[2] == "APPROVED"
                    and int(candidate[3] or 0) == 1
                ),
                None,
            )
            if row is None:
                row = next(
                    (
                        candidate
                        for candidate in active_rows
                        if candidate[1] == new_hash
                    ),
                    None,
                )
            if row is None:
                row = active_rows[0]

            keeper_id = int(row[0])
            duplicate_ids = [
                int(candidate[0])
                for candidate in active_rows
                if int(candidate[0]) != keeper_id
            ]
            if duplicate_ids:
                placeholders = ",".join("?" for _ in duplicate_ids)
                conn.execute(
                    f"""UPDATE template_profiles
                        SET is_active=0,
                            review_status=CASE
                                WHEN source_asset_sha256 IS NOT ?
                                     AND source_asset_sha256<>?
                                THEN 'STALE_SOURCE_CHANGED'
                                ELSE review_status
                            END,
                            updated_at=CURRENT_TIMESTAMP
                        WHERE rowid IN ({placeholders})""",
                    (new_hash, new_hash, *duplicate_ids),
                )

        if row:
            old_id = row[0]
            old_hash = row[1]
            old_status = row[2]
            old_manual = row[3]
            
            # If hash changed, mark old as inactive/stale and insert new
            if old_hash and new_hash and old_hash != new_hash:
                conn.execute("UPDATE template_profiles SET is_active = 0, review_status = 'STALE_SOURCE_CHANGED' WHERE rowid = ?", (old_id,))
                # Fallthrough to insert new proposal below
            else:
                if old_status == "APPROVED" and old_manual:
                    # Unchanged manually-approved profile must preserve approved
                    # geometry/data. Commit any duplicate-active normalization
                    # performed above before returning.
                    conn.commit()
                    return

                # Update in place if hash is same
                conn.execute("""
                UPDATE template_profiles SET
                    analyzer_version=?, surface_quad=?, outer_quad=?, orientation=?,
                    nominal_aspect=?, print_policy=?,
                    confidence_total=?, component_confidences=?, review_status=?, manually_verified=?,
                    updated_at=CURRENT_TIMESTAMP
                WHERE rowid=?
                """, (
                    profile_data["analyzer_version"], json.dumps(profile_data.get("surface_quad")),
                    json.dumps(profile_data.get("outer_quad")), profile_data["orientation"],
                    profile_data.get("nominal_aspect", "UNKNOWN"),
                    profile_data.get("print_policy", "full_bleed"),
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
            nominal_aspect, geometry_type, print_policy, surface_quad, outer_quad, surface_mask_path,
            material, has_frame, has_mat, has_reflection, has_occlusion,
            confidence_total, component_confidences, review_status, manually_verified, is_active
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        """, (
            profile_data["template_uid"], profile_data["category"], profile_data["source_relative_path"],
            profile_data.get("source_asset_sha256"), profile_data.get("profile_version","v2"), profile_data["analyzer_version"],
            profile_data.get("product_class","Unknown"), profile_data["orientation"], profile_data.get("nominal_aspect", "UNKNOWN"),
            profile_data.get("geometry_type", "quad"), profile_data.get("print_policy","full_bleed"),
            json.dumps(profile_data.get("surface_quad")), json.dumps(profile_data.get("outer_quad")),
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
        
        requested_orientation = str(design_orientation or "").upper()
        for row in rows:
            tmpl_orient = str(row["orientation"] or "UNKNOWN").upper()
            if rule["orientation_strict"]:
                if (
                    tmpl_orient not in ("H", "V")
                    or requested_orientation not in ("H", "V")
                    or requested_orientation != tmpl_orient
                ):
                    orientation_mismatches += 1
                    continue
                    
            score = float(row["confidence_total"] or 0.0)
            
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
