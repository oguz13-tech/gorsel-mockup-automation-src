# -*- coding: utf-8 -*-
import cv2
import json
import numpy as np
from pathlib import Path

def imread_unicode(p):
    return cv2.imdecode(np.fromfile(str(p), dtype=np.uint8), cv2.IMREAD_COLOR)

def imwrite_unicode(p, img):
    ok, buf = cv2.imencode(Path(p).suffix, img)
    if ok:
        buf.tofile(str(p))
    return ok

def create_subpixel_antialiased_mask(h_bg: int, w_bg: int, dst_pts: np.ndarray, feather_px: float = 1.8) -> np.ndarray:
    scale = 2.0
    h_lg = int(h_bg * scale)
    w_lg = int(w_bg * scale)
    pts_lg = (dst_pts * scale).astype(np.int32)
    
    mask_lg = np.zeros((h_lg, w_lg), dtype=np.float32)
    cv2.fillConvexPoly(mask_lg, pts_lg, 1.0)
    
    ksize = int(round(feather_px * scale * 2.5)) | 1
    mask_lg_blur = cv2.GaussianBlur(mask_lg, (ksize, ksize), feather_px * scale * 0.5)
    mask_aa = cv2.resize(mask_lg_blur, (w_bg, h_bg), interpolation=cv2.INTER_AREA)
    return np.clip(mask_aa, 0.0, 1.0)

def generate_peacock_style_window_reflection(gw: int, gh: int, intensity: float = 0.55) -> np.ndarray:
    y, x = np.mgrid[0:gh, 0:gw].astype(np.float32)
    
    win_cx = gw * 0.72
    win_cy = gh * 0.32
    win_w = gw * 0.75
    win_h = gh * 0.65
    
    angle_rad = np.radians(-6.0)
    cos_a, sin_a = np.cos(angle_rad), np.sin(angle_rad)
    x_rot = (x - win_cx) * cos_a - (y - win_cy) * sin_a
    y_rot = (x - win_cx) * sin_a + (y - win_cy) * cos_a
    
    u = np.abs(x_rot) / (win_w * 0.5)
    v = np.abs(y_rot) / (win_h * 0.5)
    envelope = np.clip(1.0 - u**2.5, 0.0, 1.0) * np.clip(1.0 - v**2.5, 0.0, 1.0)
    envelope = cv2.GaussianBlur(envelope, (15, 15), 0)
    
    mullion_w = max(5, int(gw * 0.022))
    
    dist_v = np.abs(x_rot)
    bar_v = np.clip((dist_v - mullion_w * 0.5) / 1.8, 0.0, 1.0)
    
    dist_h = np.abs(y_rot)
    bar_h = np.clip((dist_h - mullion_w * 0.5) / 1.8, 0.0, 1.0)
    
    dist_h2 = np.abs(y_rot - win_h * 0.38)
    bar_h2 = np.clip((dist_h2 - mullion_w * 0.5) / 1.8, 0.0, 1.0)
    
    bars = bar_v * bar_h * bar_h2
    panes = envelope * bars
    
    glow = cv2.GaussianBlur(envelope, (45, 45), 0) * 0.25
    fresnel = ((x / float(gw)) * 0.65 + (1.0 - y / float(gh)) * 0.35) * 0.15
    
    refl = (panes * 0.85 + glow + fresnel) * intensity
    refl = np.clip(refl, 0.0, 0.85)
    
    return np.stack([refl * 1.0, refl * 0.98, refl * 0.96], axis=-1)

def generate_3d_glass_beveled_edge(h_bg: int, w_bg: int, dst_pts: np.ndarray) -> np.ndarray:
    bevel = np.zeros((h_bg, w_bg, 3), dtype=np.float32)
    p0, p1, p2, p3 = dst_pts[0], dst_pts[1], dst_pts[2], dst_pts[3]
    
    cv2.line(bevel, (int(p0[0]), int(p0[1])), (int(p1[0]), int(p1[1])), (1.0, 1.0, 1.0), 2, lineType=cv2.LINE_AA)
    cv2.line(bevel, (int(p0[0]), int(p0[1])), (int(p3[0]), int(p3[1])), (0.9, 0.95, 1.0), 2, lineType=cv2.LINE_AA)
    cv2.line(bevel, (int(p1[0]), int(p1[1])), (int(p2[0]), int(p2[1])), (0.95, 0.98, 1.0), 2, lineType=cv2.LINE_AA)
    
    off_3d = np.array([3.0, 0.5], dtype=np.float32)
    p1_3d = p1 + off_3d
    p2_3d = p2 + off_3d
    cv2.line(bevel, (int(p1_3d[0]), int(p1_3d[1])), (int(p2_3d[0]), int(p2_3d[1])), (0.6, 0.7, 0.8), 1, lineType=cv2.LINE_AA)
    
    bevel = cv2.GaussianBlur(bevel, (3, 3), 0.4)
    return bevel

def main():
    BASE_DIR = Path(r"C:\Users\oguzc\OneDrive\Masaüstü\GörselÜretme-ve-Mockup Otomasyonu")
    with open(BASE_DIR / "99_SISTEM_MOTORLARI_VE_KODLAR" / "SISTEM_MOTORU" / "ayarlar.json", encoding="utf-8") as f:
        ayarlar = json.load(f)

    art_v = imread_unicode(BASE_DIR / "1_GELEN_KAGGLE_BASKILARI" / "M000001_V.png")
    bg1 = imread_unicode(BASE_DIR / "2_SABLON_HAVUZU" / "02_Cam_Tablo_Dikey" / "Gemini_Generated_Image_484mjl484mjl484m (1).jpeg")
    cfg1 = ayarlar["kategoriler"]["02_Cam_Tablo_Dikey"]["sablonlar"]["Gemini_Generated_Image_484mjl484mjl484m (1).jpeg"]

    x, y, w, h = cfg1["x"], cfg1["y"], cfg1["w"], cfg1["h"]
    dst_pts = np.float32([[x, y], [x+w, y], [x+w, y+h], [x, y+h]])
    h_bg, w_bg = bg1.shape[:2]

    h_art, w_art = art_v.shape[:2]
    target_ar = w / float(h)
    crop_h = int(round(w_art / target_ar))
    sy = (h_art - crop_h) // 2
    art_fit = art_v[sy:sy+crop_h, :]

    fh, fw = art_fit.shape[:2]
    matrix = cv2.getPerspectiveTransform(np.float32([[0,0],[fw,0],[fw,fh],[0,fh]]), dst_pts)
    warped = cv2.warpPerspective(art_fit, matrix, (w_bg, h_bg), flags=cv2.INTER_LANCZOS4)

    mask_aa = create_subpixel_antialiased_mask(h_bg, w_bg, dst_pts, feather_px=1.8)
    mask_3c = np.stack([mask_aa]*3, axis=-1)

    refl_local = generate_peacock_style_window_reflection(w, h, intensity=0.55)
    refl_warped = cv2.warpPerspective(refl_local, matrix, (w_bg, h_bg), flags=cv2.INTER_LINEAR)

    warped_norm = np.clip(warped.astype(np.float32) / 255.0, 0.0, 1.0)
    glass_art_norm = 1.0 - (1.0 - warped_norm) * (1.0 - refl_warped)

    bevel_light = generate_3d_glass_beveled_edge(h_bg, w_bg, dst_pts)
    glass_final = np.clip(glass_art_norm + bevel_light, 0.0, 1.0) * 255.0

    shadow = np.zeros((h_bg, w_bg), dtype=np.float32)
    cv2.fillConvexPoly(shadow, (dst_pts + np.array([[12, 18]]*4)).astype(np.int32), 0.35)
    shadow = cv2.GaussianBlur(shadow, (35, 35), 0)
    shadow_outside = shadow * (1.0 - mask_aa)
    bg_shadowed = bg1.astype(np.float32) * (1.0 - np.stack([shadow_outside]*3, axis=-1))

    final_mockup = bg_shadowed * (1.0 - mask_3c) + glass_final * mask_3c
    final_mockup = np.clip(final_mockup, 0, 255).astype(np.uint8)

    out_path = BASE_DIR / "99_SISTEM_MOTORLARI_VE_KODLAR" / "SISTEM_MOTORU" / "test_effects" / "test_cam_tablo_peacock_match.jpg"
    imwrite_unicode(out_path, final_mockup)
    print("SUCCESS! Saved:", out_path)

if __name__ == "__main__":
    main()
