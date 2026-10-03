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
            "folders": ["03_Ahsap_Tablo"]
        },
        "GLASS_WALL_ART_VERTICAL": {
            "product_class": "Cam Tablo Dikey",
            "has_frame": False,
            "has_mat": False,
            "has_reflection": True,
            "print_policy": "full_bleed",
            "orientation_strict": True,
            "folders": ["02_Cam_Tablo_Dikey"]
        },
        "GLASS_WALL_ART_HORIZONTAL": {
            "product_class": "Cam Tablo Yatay",
            "has_frame": False,
            "has_mat": False,
            "has_reflection": True,
            "print_policy": "full_bleed",
            "orientation_strict": True,
            "folders": ["05_Cam_Tablo_Yatay"]
        },
        "GLASS_CUTTING_BOARD": {
            "product_class": "Cam Kesme Tahtası",
            "has_frame": False,
            "has_mat": False,
            "has_reflection": True,
            "print_policy": "full_surface",
            "orientation_strict": False,
            "folders": ["04_Cam_Dograma"]
        },
        "WIFI_COVER_PANEL": {
            "product_class": "Wifi Kutusu Kapağı",
            "has_frame": True,
            "has_mat": False,
            "has_reflection": False, # Matte finish typically
            "print_policy": "front_panel",
            "orientation_strict": True,
            "folders": ["01_Wifi_Kutusu"]
        },
        "GLASS_BACKSPLASH": {
            "product_class": "Ocak Arkası Cam",
            "has_frame": False,
            "has_mat": False,
            "has_reflection": True,
            "print_policy": "full_bleed",
            "orientation_strict": True,
            "folders": ["06_Ocak_Arkasi"]
        }
    }
    
    @classmethod
    def get_rule_by_folder(cls, folder_name: str) -> dict:
        for key, rule in cls.RULES.items():
            if folder_name in rule["folders"]:
                rule["key"] = key
                return rule
        return cls.RULES["GLASS_WALL_ART_VERTICAL"]

class GeometryValidator:
    @staticmethod
    def is_valid_quad(pts: np.ndarray, img_w: int, img_h: int) -> Tuple[bool, str]:
        if len(pts) != 4:
            return False, "Not 4 points"
        
        # Check bounds
        for p in pts:
            if p[0] < -img_w or p[0] > img_w * 2 or p[1] < -img_h or p[1] > img_h * 2:
                return False, "Out of bounds"
                
        # Check area
        area = cv2.contourArea(pts.astype(np.float32))
        img_area = img_w * img_h
        if area < img_area * 0.05:
            return False, "Too small"
            
        # Check convexity
        if not cv2.isContourConvex(pts.astype(np.int32)):
            return False, "Not convex (self intersecting or concave)"
            
        # Canonical ordering and homography condition
        pts_ordered = GeometryValidator.order_points(pts)
        
        src_rect = np.array([
            [0, 0],
            [img_w, 0],
            [img_w, img_h],
            [0, img_h]
        ], dtype=np.float32)
        
        H, _ = cv2.findHomography(src_rect, pts_ordered)
        if H is None:
            return False, "Homography could not be computed"
            
        cond = np.linalg.cond(H)
        if cond > 1e5:
            return False, f"Homography condition number too high: {cond:.2f}"
            
        return True, "Valid"

    @staticmethod
    def order_points(pts: np.ndarray) -> np.ndarray:
        rect = np.zeros((4, 2), dtype="float32")
        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)]
        rect[2] = pts[np.argmax(s)]
        
        diff = np.diff(pts, axis=1)
        rect[1] = pts[np.argmin(diff)]
        rect[3] = pts[np.argmax(diff)]
        return rect

class TemplateAnalyzer:
    def __init__(self):
        self.version = "v1.0"
        
    def generate_candidates(self, image_cv: np.ndarray) -> List[np.ndarray]:
        gray = cv2.cvtColor(image_cv, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edged = cv2.Canny(blurred, 30, 100)
        
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        closed = cv2.morphologyEx(edged, cv2.MORPH_CLOSE, kernel)
        
        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours = sorted(contours, key=cv2.contourArea, reverse=True)[:5]
        
        candidates = []
        for c in contours:
            peri = cv2.arcLength(c, True)
            approx = cv2.approxPolyDP(c, 0.02 * peri, True)
            if len(approx) == 4:
                candidates.append(approx.reshape(4, 2))
                
        return candidates

    def analyze(self, filepath: str, category_folder: str, manual_geometry_prior: Optional[dict] = None) -> dict:
        img = cv2.imdecode(np.fromfile(filepath, dtype=np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError(f"Could not read image {filepath}")
            
        h, w = img.shape[:2]
        
        best_quad = None
        best_conf = 0.0
        component_confidences = {}
        
        if manual_geometry_prior and "surface_quad" in manual_geometry_prior:
            cand = np.array(manual_geometry_prior["surface_quad"], dtype=np.float32)
            valid, msg = GeometryValidator.is_valid_quad(cand, w, h)
            if valid:
                best_quad = GeometryValidator.order_points(cand).tolist()
                best_conf = 1.0
                component_confidences = {
                    "candidate_agreement": 1.0,
                    "line_score": 1.0,
                    "orientation_score": 1.0
                }
        else:
            candidates = self.generate_candidates(img)
            for cand in candidates:
                cand = cand.astype(np.float32)
                valid, msg = GeometryValidator.is_valid_quad(cand, w, h)
                if valid:
                    cand_ordered = GeometryValidator.order_points(cand)
                    # Basic confidence heuristic
                    area = cv2.contourArea(cand_ordered)
                    base_conf = min(0.95, (area / (w * h)) + 0.1)
                    
                    # Component scores
                    cand_agreement = base_conf
                    line_score = 0.90 if base_conf > 0.5 else 0.5
                    orient_score = 0.95 if base_conf > 0.5 else 0.5
                    
                    conf = (cand_agreement * 0.5) + (line_score * 0.3) + (orient_score * 0.2)
                    
                    if conf > best_conf:
                        best_conf = conf
                        best_quad = cand_ordered.tolist()
                        component_confidences = {
                            "candidate_agreement": cand_agreement,
                            "line_score": line_score,
                            "orientation_score": orient_score
                        }
                    
        rule = CategoryRuleEngine.get_rule_by_folder(category_folder)
        
        # Calculate aspect ratio of quad if available
        nominal_aspect = "UNKNOWN"
        orientation = "UNKNOWN"
        if best_quad:
            pts = np.array(best_quad)
            w_top = np.linalg.norm(pts[1] - pts[0])
            h_left = np.linalg.norm(pts[3] - pts[0])
            
            if w_top > 0 and h_left > 0:
                ar = w_top / h_left
                orientation = "H" if ar > 1.05 else ("V" if ar < 0.95 else "SQUARE")
        
        return {
            "surface_quad": best_quad,
            "confidence_total": best_conf,
            "component_confidences": component_confidences,
            "review_status": "REVIEW_REQUIRED" if best_quad else "UNANALYZED",
            "rule": rule,
            "orientation": orientation,
            "nominal_aspect": nominal_aspect
        }

def save_template_profile(db_path: str, profile_data: dict):
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("""
        INSERT INTO template_profiles (
            template_uid, category, source_relative_path, source_asset_sha256,
            profile_version, analyzer_version, product_class, orientation,
            geometry_type, print_policy, surface_quad, outer_quad, surface_mask_path,
            material, has_frame, has_mat, has_reflection, has_occlusion,
            confidence_total, component_confidences, review_status, manually_verified,
            updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(template_uid) DO UPDATE SET
            surface_quad=excluded.surface_quad,
            confidence_total=excluded.confidence_total,
            review_status=excluded.review_status,
            manually_verified=excluded.manually_verified,
            updated_at=CURRENT_TIMESTAMP
        """, (
            profile_data["template_uid"], profile_data["category"], profile_data["source_relative_path"],
            profile_data["source_asset_sha256"], profile_data["profile_version"], profile_data["analyzer_version"],
            profile_data["product_class"], profile_data["orientation"], profile_data["geometry_type"],
            profile_data["print_policy"], json.dumps(profile_data["surface_quad"]), json.dumps(profile_data.get("outer_quad")),
            profile_data.get("surface_mask_path"), profile_data.get("material", "default"),
            profile_data.get("has_frame", False), profile_data.get("has_mat", False),
            profile_data.get("has_reflection", False), profile_data.get("has_occlusion", False),
            profile_data["confidence_total"], json.dumps(profile_data.get("component_confidences", {})),
            profile_data["review_status"], profile_data.get("manually_verified", False)
        ))
        conn.commit()
    finally:
        conn.close()

class TemplateSelector:
    def __init__(self, db_path: str):
        self.db_path = db_path
        
    def select_template(self, design_orientation: str, category_folder: str) -> dict:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        # Sadece onaylı template'leri çek
        cur = conn.execute('''
            SELECT * FROM template_profiles 
            WHERE category = ? AND review_status = 'APPROVED'
            ORDER BY confidence_total DESC
        ''', (category_folder,))
        
        rows = cur.fetchall()
        conn.close()
        
        if not rows:
            return {"status": "SKIPPED_NO_COMPATIBLE_TEMPLATE", "reason": "No approved templates in category"}
            
        rule = CategoryRuleEngine.get_rule_by_folder(category_folder)
        
        for row in rows:
            tmpl_orient = row["orientation"]
            if rule["orientation_strict"]:
                if design_orientation != tmpl_orient and tmpl_orient != "UNKNOWN":
                    continue
            
            return {"status": "SELECTED", "template": dict(row)}
            
        return {"status": "SKIPPED_ORIENTATION_MISMATCH", "reason": f"Design is {design_orientation} but no matching templates found"}
