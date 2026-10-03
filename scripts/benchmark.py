import os
import sys
import json
import time
import numpy as np
from pathlib import Path
import cv2

# Add parent to path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "SABLON_V2_MIMARI"))

from core.template_intelligence import TemplateAnalyzer

def calculate_iou(quad1, quad2, w, h):
    """Calculate Intersection over Union for two quads."""
    if quad1 is None or quad2 is None:
        return 0.0
    
    # Create masks
    mask1 = np.zeros((h, w), dtype=np.uint8)
    mask2 = np.zeros((h, w), dtype=np.uint8)
    
    cv2.fillPoly(mask1, [np.array(quad1, dtype=np.int32)], 255)
    cv2.fillPoly(mask2, [np.array(quad2, dtype=np.int32)], 255)
    
    intersection = np.logical_and(mask1, mask2).sum()
    union = np.logical_or(mask1, mask2).sum()
    
    if union == 0:
        return 0.0
    return intersection / union

def calculate_corner_error(quad_pred, quad_gt, w, h):
    """Calculate normalized corner error (Euclidean distance / image diagonal)."""
    if quad_pred is None or quad_gt is None:
        return 1.0
        
    diag = np.sqrt(w**2 + h**2)
    p1 = np.array(quad_pred)
    p2 = np.array(quad_gt)
    
    errors = np.linalg.norm(p1 - p2, axis=1)
    mean_error = np.mean(errors) / diag
    return mean_error

def run_benchmark(dataset_path: str, output_json: str):
    """
    Runs benchmark on 6 categories, computing OLD vs NEW raw evidence,
    median normalized corner error, P95, median IoU, invalid/exclusions,
    and high-confidence-bad metrics.
    """
    categories = [
        "01_Wifi_Kutusu",
        "02_Cam_Tablo_Dikey",
        "02_Cam_Tablo_Yatay",
        "03_Ahsap_Tablo",
        "04_Cam_Dograma",
        "05_Ocak_Arkasi"
    ]
    
    analyzer = TemplateAnalyzer()
    
    results = {
        "timestamp": time.time(),
        "total_samples": 0,
        "categories": {},
        "global_metrics": {
            "median_iou": 0.0,
            "median_corner_error": 0.0,
            "p95_corner_error": 0.0,
            "high_confidence_bad": 0,
            "invalid_exclusions": 0
        },
        "raw_evidence": []
    }
    
    all_ious = []
    all_errors = []
    
    gt_file = os.path.join(dataset_path, "ground_truth.json")
    dataset = {}
    if os.path.exists(gt_file):
        with open(gt_file, 'r') as f:
            dataset = json.load(f)
            
    for cat in categories:
        cat_samples = [k for k,v in dataset.items() if v.get("category") == cat]
        
        if not cat_samples:
            raise ValueError(f"CRITICAL: Missing real samples for category {cat}. Benchmark blocked.")
            
        results["categories"][cat] = {
            "samples": len(cat_samples),
            "median_iou": 0.0,
            "p95_error": 0.0,
            "detection_rate": 0.0
        }
            
        cat_ious = []
        cat_errors = []
        detected_count = 0
        
        for sample in cat_samples:
            results["total_samples"] += 1
            
            gt_quad = dataset.get(sample, {}).get("quad")
            if gt_quad is None or len(gt_quad) != 4:
                results["global_metrics"]["invalid_exclusions"] += 1
                continue
            
            full_sample_path = os.path.join(dataset_path, sample)
            if not os.path.exists(full_sample_path):
                raise ValueError(f"CRITICAL: Missing sample file {full_sample_path}. Benchmark blocked.")
            
            img = cv2.imread(full_sample_path)
            if img is None:
                raise ValueError(f"CRITICAL: Unreadable image {full_sample_path}. Benchmark blocked.")
            h, w = img.shape[:2]
            
            try:
                res = analyzer.analyze(full_sample_path, cat)
                pred_quad = res.get("surface_quad")
                conf = res.get("confidence_total", 0.0)
            except Exception as e:
                results["global_metrics"]["invalid_exclusions"] += 1
                pred_quad = None
                conf = 0.0
                
            iou = calculate_iou(pred_quad, gt_quad, w, h)
            err = calculate_corner_error(pred_quad, gt_quad, w, h)
            
            # Use real OLD analyzer snapshot
            try:
                import importlib.util
                spec = importlib.util.spec_from_file_location("old_intel", "old_intelligence_utf8.py")
                old_intel = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(old_intel)
                old_analyzer = old_intel.TemplateAnalyzer()
                old_res = old_analyzer.analyze(full_sample_path, cat)
                old_pred = old_res.get("surface_quad")
            except Exception:
                # If old analyzer fails or isn't available, BLOCK the benchmark.
                raise ValueError("CRITICAL: Failed to run real OLD algorithm adapter. Benchmark blocked.")
            
            old_iou = calculate_iou(old_pred, gt_quad, w, h)
            
            if pred_quad is not None and len(pred_quad) == 4:
                detected_count += 1
                
            cat_ious.append(iou)
            cat_errors.append(err)
            
            if conf > 0.85 and iou < 0.5:
                results["global_metrics"]["high_confidence_bad"] += 1
                
            results["raw_evidence"].append({
                "sample": sample,
                "category": cat,
                "old_iou": float(old_iou), 
                "new_iou": float(iou),
                "new_conf": float(conf),
                "corner_error": float(err)
            })
            
        if cat_ious:
            results["categories"][cat]["median_iou"] = np.median(cat_ious)
            results["categories"][cat]["p95_error"] = np.percentile(cat_errors, 95)
            results["categories"][cat]["detection_rate"] = detected_count / len(cat_samples)
            all_ious.extend(cat_ious)
            all_errors.extend(cat_errors)
            
    if all_ious:
        results["global_metrics"]["median_iou"] = float(np.median(all_ious))
        results["global_metrics"]["median_corner_error"] = float(np.median(all_errors))
        results["global_metrics"]["p95_corner_error"] = float(np.percentile(all_errors, 95))
        results["global_metrics"]["detection_rate"] = sum(c["detection_rate"] * c["samples"] for c in results["categories"].values()) / results["total_samples"]
        
    for cat, data in results["categories"].items():
        data["median_iou"] = float(data["median_iou"])
        data["p95_error"] = float(data["p95_error"])
        data["detection_rate"] = float(data["detection_rate"])
        
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
        
    print(f"Benchmark finished on {results['total_samples']} samples.")
    print(f"Metrics saved to {output_json}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=str, default="benchmark_dataset")
    parser.add_argument("--output", type=str, default="benchmark_results_v4.json")
    args = parser.parse_args()
    
    run_benchmark(args.dataset, args.output)
