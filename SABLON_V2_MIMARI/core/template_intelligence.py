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
            "folders": ["02_Cam_Tablo_Yatay"]
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
            "has_reflection": False,
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
    def is_valid_quad(pts: np.ndarray, img_w: int, img_h: int) -> Tuple[bool, str]:
        if len(pts) != 4:
            return False, "Not 4 points"
            
        for p in pts:
            if p[0] < -img_w*0.5 or p[0] > img_w * 1.5 or p[1] < -img_h*0.5 or p[1] > img_h * 1.5:
                return False, "Out of bounds"
                
        area = cv2.contourArea(pts.astype(np.float32))
        img_area = img_w * img_h
        if area < img_area * 0.05:
            return False, "Too small"
            
        if not cv2.isContourConvex(pts.astype(np.int32)):
            return False, "Not convex (self intersecting or concave)"
            
        # Homography degeneracy check using cross product and angle checks
        # True canonical sorting: verify if points are ordered clockwise/counterclockwise without self-intersection
        edges = [pts[(i+1)%4] - pts[i] for i in range(4)]
        cross_prods = [np.cross(edges[i], edges[(i+1)%4]) for i in range(4)]
        
        # All must have same sign
        if not (all(cp > 0 for cp in cross_prods) or all(cp < 0 for cp in cross_prods)):
             return False, "Self-intersecting segment or invalid ordering (cross product sign flip)"
             
        # Aspect degeneracy check (max 10:1 ratio)
        w_top = np.linalg.norm(edges[0])
        h_left = np.linalg.norm(edges[3])
        if w_top < 10 or h_left < 10 or w_top/h_left > 10.0 or h_left/w_top > 10.0:
            return False, "Degenerate aspect ratio"
            
        return True, "Valid"

class CandidateGenerators:
    @staticmethod
    def generate_canny_contours(image_cv: np.ndarray) -> List[np.ndarray]:
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

    @staticmethod
    def generate_hough_lines_quad(image_cv: np.ndarray) -> List[np.ndarray]:
        gray = cv2.cvtColor(image_cv, cv2.COLOR_BGR2GRAY)
        edged = cv2.Canny(gray, 50, 150, apertureSize=3)
        lines = cv2.HoughLinesP(edged, 1, np.pi/180, threshold=100, minLineLength=100, maxLineGap=10)
        candidates = []
        if lines is not None and len(lines) > 4:
            # Basic fallback heuristic to return the bounding box of all lines
            pts = []
            for line in lines:
                x1, y1, x2, y2 = line[0]
                pts.extend([[x1,y1], [x2,y2]])
            pts = np.array(pts)
            x,y,w,h = cv2.boundingRect(pts)
            quad = np.array([[x,y], [x+w,y], [x+w,y+h], [x,y+h]], dtype=np.int32)
            candidates.append(quad)
        return candidates



class TemplateAnalyzer:
    def __init__(self):
        self.version = "v1.2"
        self.auto_approval_enabled = False
        
    def measure_edge_contrast(self, image_cv: np.ndarray, quad: np.ndarray) -> float:
        # Actually measure edge score along the quad segments in the image!
        gray = cv2.cvtColor(image_cv, cv2.COLOR_BGR2GRAY)
        mask = np.zeros_like(gray)
        cv2.drawContours(mask, [quad.astype(np.int32)], 0, 255, 3)
        mean_val = cv2.mean(gray, mask=mask)[0]
        # Basic heuristic: if the edge is sharp, mean val on the edge in a gradient image is high
        grad = cv2.morphologyEx(gray, cv2.MORPH_GRADIENT, np.ones((3,3),np.uint8))
        edge_strength = cv2.mean(grad, mask=mask)[0]
        return min(1.0, edge_strength / 128.0)
        
    def analyze(self, filepath: str, category_folder: str) -> dict:
        img = cv2.imdecode(np.fromfile(filepath, dtype=np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError(f"Could not read image {filepath}")
            
        h, w = img.shape[:2]
        try:
            rule = CategoryRuleEngine.get_rule_by_folder(category_folder)
        except ValueError:
            rule = {"key": "UNKNOWN"}
            
        # Pipeline: Generators -> Validator -> Scorer
        candidates = []
        candidates.extend(CandidateGenerators.generate_canny_contours(img))
        candidates.extend(CandidateGenerators.generate_hough_lines_quad(img))
        candidates.extend(CandidateGenerators.generate_color_region_quad(img))
        
        best_quad = None
        best_conf = 0.0
        best_components = {}
        
        for cand in candidates:
            valid, msg = GeometryValidator.is_valid_quad(cand, w, h)
            if valid:
                area = cv2.contourArea(cand.astype(np.float32))
                area_ratio = min(1.0, area / (w * h))
                
                edge_score = self.measure_edge_contrast(img, cand)
                geometry_score = 1.0 # Validated
                
                comp_conf = {
                    "area_ratio": float(area_ratio),
                    "edge_alignment": float(edge_score),
                    "geometry_validity": float(geometry_score)
                }
                
                conf = (area_ratio * 0.4) + (edge_score * 0.5) + (geometry_score * 0.1)
                
                if conf > best_conf:
                    best_conf = conf
                    best_quad = cand.tolist()
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
            if self.auto_approval_enabled and best_conf > 0.85:
                status = "AUTO_PROPOSED" 
            else:
                status = "REVIEW_REQUIRED"
        else:
            status = "UNANALYZED"
            
        with open(filepath, "rb") as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()
            
        return {
            "source_asset_sha256": file_hash,
            "surface_quad": best_quad,
            "confidence_total": best_conf,
            "component_confidences": best_components,
            "review_status": status,
            "rule": rule,
            "orientation": orientation,
            "nominal_aspect": nominal_aspect,
            "analyzer_version": self.version
        }

def save_template_profile(db_path: str, profile_data: dict):
    conn = sqlite3.connect(db_path)
    try:
        # Check if old active profile exists
        cur = conn.execute("SELECT id, source_asset_sha256, review_status FROM template_profiles WHERE template_uid = ? AND is_active = 1", (profile_data["template_uid"],))
        row = cur.fetchone()
        
        if row:
            old_id = row[0]
            old_hash = row[1]
            new_hash = profile_data.get("source_asset_sha256")
            
            # If hash changed, mark old as inactive/stale and insert new
            if old_hash and new_hash and old_hash != new_hash:
                conn.execute("UPDATE template_profiles SET is_active = 0, review_status = 'STALE_SOURCE_CHANGED' WHERE id = ?", (old_id,))
                # Fallthrough to insert new proposal below
            else:
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
        
        for row in rows:
            tmpl_orient = row["orientation"]
            if rule["orientation_strict"]:
                if design_orientation != tmpl_orient and tmpl_orient != "UNKNOWN":
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
            
        return {"status": "SKIPPED_ASPECT_MISMATCH", "reason": "Templates skipped due to aspect or orientation mismatch"}
