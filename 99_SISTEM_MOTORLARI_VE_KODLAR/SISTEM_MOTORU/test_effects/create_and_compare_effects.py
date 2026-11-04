# -*- coding: utf-8 -*-
import cv2
import json
import os
import numpy as np
from pathlib import Path

BASE_DIR = Path(os.environ.get("MOCKUP_RUNTIME_WORKSPACE") or Path(__file__).resolve().parents[3]).resolve()
OUTPUT_DIR = BASE_DIR / "SISTEM_MOTORU" / "test_effects"
 # P0: no writes on import; caller must explicitly prepare isolated output.

def create_subpixel_antialiased_mask(h_bg: int, w_bg: int, dst_pts: np.ndarray, feather_px: float = 1.8) -> np.ndarray:
    """
    Sub-pixel Kenar Yumuşatma (Anti-Aliasing):
    2x Supersampling + Gaussian blur + Area downsampling.
    Merdiven (staircase) ve pikselleşme kesinlikle oluşmaz; kenar duvara pürüzsüzce kaynar.
    """
    scale = 2.0
    h_lg = int(h_bg * scale)
    w_lg = int(w_bg * scale)
    pts_lg = (dst_pts * scale).astype(np.int32)
    
    mask_lg = np.zeros((h_lg, w_lg), dtype=np.float32)
    cv2.fillConvexPoly(mask_lg, pts_lg, 1.0)
    
    # 2x ölçekte yumuşatma
    ksize = int(round(feather_px * scale * 2.5)) | 1
    mask_lg_blur = cv2.GaussianBlur(mask_lg, (ksize, ksize), feather_px * scale * 0.5)
    
    # Area downsampling ile alt piksel yumuşatma
    mask_aa = cv2.resize(mask_lg_blur, (w_bg, h_bg), interpolation=cv2.INTER_AREA)
    return np.clip(mask_aa, 0.0, 1.0)

def generate_architectural_window_reflection(gw: int, gh: int, intensity: float = 0.35) -> np.ndarray:
    """
    Kullanıcının gönderdiği tavuskuşlu cam tablo görselindeki birebir pencere yansıması:
    - 2x2 veya 3x2 belirgin koyu çıtalı (mullions) mimari pencere kurgusu
    - Üst ve sağ kısma odaklı gerçekçi oda penceresi ışık dağılımı
    - Çıta aralarında parlak günışığı cam pencereleri
    - Cam yüzeyinde doğal Fresnel kenar ışıması
    """
    canvas = np.zeros((gh, gw), dtype=np.float32)
    
    # Pencerenin tablo üzerindeki konumu (Kullanıcı görselinde üst ve sağ ağırlıklı)
    # Merkez: x: ~0.65, y: ~0.35
    win_cx = int(gw * 0.68)
    win_cy = int(gh * 0.36)
    win_w = int(gw * 0.75)
    win_h = int(gh * 0.65)
    
    # Pencere koordinat ızgarası
    y, x = np.mgrid[0:gh, 0:gw].astype(np.float32)
    
    # Hafif oda açısı (diyagonal eğim ~ 8-12 derece)
    angle_rad = np.radians(-8.0)
    cos_a, sin_a = np.cos(angle_rad), np.sin(angle_rad)
    x_rot = (x - win_cx) * cos_a - (y - win_cy) * sin_a
    y_rot = (x - win_cx) * sin_a + (y - win_cy) * cos_a
    
    # Pencere ana ışık çerçevesi (Yumuşak sınır falloff)
    u = np.abs(x_rot) / (win_w * 0.5)
    v = np.abs(y_rot) / (win_h * 0.5)
    
    window_envelope = np.clip(1.0 - u**2.2, 0.0, 1.0) * np.clip(1.0 - v**2.2, 0.0, 1.0)
    window_envelope = cv2.GaussianBlur(window_envelope, (21, 21), 0)
    
    # Çıtalar (Mullions - Koyu pencere çıtaları)
    # 1 dikey çıta (ortada) + 1 yatay çıta (ortada) -> 2x2 pencere
    # Çıta kalınlığı ~ 1.5%
    mullion_w = max(4, int(gw * 0.016))
    mullion_mask = np.ones((gh, gw), dtype=np.float32)
    
    # Dikey çıta (x_rot = 0 civarı)
    dist_v = np.abs(x_rot)
    mullion_v = np.clip((dist_v - mullion_w * 0.5) / 2.5, 0.0, 1.0)
    
    # Yatay çıta (y_rot = 0 civarı)
    dist_h = np.abs(y_rot)
    mullion_h = np.clip((dist_h - mullion_w * 0.5) / 2.5, 0.0, 1.0)
    
    # İkincil üst yatay çıta (eğer pencere uzunsa 3x2 görünüm için)
    dist_h2 = np.abs(y_rot - win_h * 0.35)
    mullion_h2 = np.clip((dist_h2 - mullion_w * 0.5) / 2.5, 0.0, 1.0)
    
    mullions_combined = mullion_v * mullion_h * mullion_h2
    
    # Pencere camları (Panes): Işık her bölmede hafif kavisli cam bombesi gibi parlar
    panes_light = window_envelope * mullions_combined
    
    # Çıtaların hafif yumuşatılması (gerçekçi optik yansıma)
    panes_smooth = cv2.GaussianBlur(panes_light, (5, 5), 1.0)
    
    # Çift katman: Geniş yumuşak difüz ışık + belirgin pencere şekli
    diffuse_glare = cv2.GaussianBlur(window_envelope, (51, 51), 0) * 0.40
    
    # Camın genel yüzey Fresnel yansıması (Sağ üstten sol alta doğru tatlı bir gradyan)
    fresnel = ((x / float(gw)) * 0.6 + (1.0 - y / float(gh)) * 0.4) * 0.18
    
    total_reflection = (panes_smooth * 0.85 + diffuse_glare + fresnel) * intensity
    total_reflection = np.clip(total_reflection, 0.0, 0.70)
    
    # Nötr günışığı rengi (hafif mavi-beyaz)
    refl_b = total_reflection * 1.00
    refl_g = total_reflection * 0.98
    refl_r = total_reflection * 0.96
    
    return np.stack([refl_b, refl_g, refl_r], axis=-1)

def generate_glass_edge_highlight(h_bg: int, w_bg: int, dst_pts: np.ndarray) -> tuple:
    """
    Kullanıcı görselindeki 4mm Elmas Rodaj Kenar Kalınlığı:
    - Üst ve sağ kenarda net kristal rodaj pahı (1-2px parlama)
    - Camın fiziksel kalınlığını gösteren çift kırılma hattı
    """
    highlight = np.zeros((h_bg, w_bg, 3), dtype=np.float32)
    thickness_line = np.zeros((h_bg, w_bg, 3), dtype=np.float32)
    p0, p1, p2, p3 = dst_pts[0], dst_pts[1], dst_pts[2], dst_pts[3]
    
    # 1. Üst kenar rodaj ışığı
    cv2.line(highlight, (int(p0[0]), int(p0[1])), (int(p1[0]), int(p1[1])), (0.95, 0.98, 1.0), 2, lineType=cv2.LINE_AA)
    # Sol kenar
    cv2.line(highlight, (int(p0[0]), int(p0[1])), (int(p3[0]), int(p3[1])), (0.85, 0.92, 1.0), 2, lineType=cv2.LINE_AA)
    # Sağ kenar (Işığın kırıldığı kenar - cam kalınlığı)
    cv2.line(highlight, (int(p1[0]), int(p1[1])), (int(p2[0]), int(p2[1])), (0.80, 0.90, 1.0), 2, lineType=cv2.LINE_AA)
    
    # 4mm cam derinlik çizgisi (Sağa 2-3px ofsetli ince paralel çizgi)
    offset_edge = np.array([2.5, 0.5], dtype=np.float32)
    p1_off = p1 + offset_edge
    p2_off = p2 + offset_edge
    cv2.line(thickness_line, (int(p1_off[0]), int(p1_off[1])), (int(p2_off[0]), int(p2_off[1])), (0.45, 0.55, 0.65), 1, lineType=cv2.LINE_AA)
    
    highlight = cv2.GaussianBlur(highlight, (3, 3), 0.5)
    return highlight, thickness_line

def generate_sunlight_shadow_for_wood(image_cv: np.ndarray, dst_pts: np.ndarray, intensity: float = 0.18) -> np.ndarray:
    """
    Ahşap Tablolar ve Wifi Kutuları için Doğal Güneş & Pencere Gölgesi Yansıması:
    - Cam gibi ayna/parlama yapmaz.
    - Odaya vuran doğal sıcak güneş ışığı huzmeleri ve pencere kanadı gölgeleri (güneş ve gölge yansımaları)
    """
    h, w = image_cv.shape[:2]
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    
    # 35 derece açıyla vuran güneş huzmeleri
    angle_rad = np.radians(35.0)
    u = (x * np.cos(angle_rad) - y * np.sin(angle_rad)) / float(max(w, h))
    
    # Yumuşak jaluzi / pencere pervazı güneş şeritleri
    freq = 2.8
    stripes = np.sin(u * np.pi * 2.0 * freq)
    stripes = np.tanh(stripes * 1.8) * 0.5 + 0.5
    stripes_smooth = cv2.GaussianBlur(stripes, (61, 61), 0)
    
    # Sıcak altın günışığı tonu
    factor = 1.0 + (stripes_smooth - 0.5) * intensity
    sunlight_3c = np.stack([
        factor * (1.0 - (stripes_smooth - 0.5) * 0.04), # Mavi hafif düşük (sıcak ton)
        factor * (1.0 + (stripes_smooth - 0.5) * 0.02), # Yeşil hafif yüksek
        factor * (1.0 + (stripes_smooth - 0.5) * 0.06), # Kırmızı daha yüksek (altın sarısı güneş)
    ], axis=-1)
    
    result = np.clip(image_cv.astype(np.float32) * sunlight_3c, 0.0, 255.0)
    return result.astype(np.uint8)

def generate_kitchen_countertop_sheen(gw: int, gh: int, intensity: float = 0.22) -> np.ndarray:
    """
    Cam Doğrama (Kesme Tahtası) için Mutfak Tezgahı / Spot Işık Yansıması:
    - Mutfak tezgahı üstündeki dolap altı LED veya tavan spot ışığının cam kesme tahtası üzerindeki oval pırıltısı.
    """
    y, x = np.mgrid[0:gh, 0:gw].astype(np.float32)
    
    # Mutfak spotu elips şeklinde parlama
    spot_cx = gw * 0.50
    spot_cy = gh * 0.35
    
    # Geniş yatay elips (tezgah ışığı)
    dx = (x - spot_cx) / (gw * 0.45)
    dy = (y - spot_cy) / (gh * 0.30)
    dist_sq = dx * dx + dy * dy
    
    spot = np.exp(-dist_sq * 1.8)
    spot_smooth = cv2.GaussianBlur(spot, (41, 41), 0)
    
    # Camın 4 kenarında güvenlik yuvarlatılmış rodaj pırıltısı
    edge_glow = np.exp(-((y / float(gh)) - 0.05)**2 / 0.01) * 0.35
    
    total = np.clip((spot_smooth * 0.85 + edge_glow) * intensity, 0.0, 0.60)
    return np.stack([total * 1.0, total * 0.98, total * 0.95], axis=-1)

print("Shader functions defined successfully!")
