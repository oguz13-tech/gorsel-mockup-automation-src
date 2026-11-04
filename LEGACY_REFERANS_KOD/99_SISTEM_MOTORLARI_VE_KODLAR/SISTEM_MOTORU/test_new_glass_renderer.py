# -*- coding: utf-8 -*-
import os
import sys
import json
import cv2
import numpy as np
from pathlib import Path

BASE_DIR = Path(r"C:\Users\oguzc\OneDrive\Masaüstü\GörselÜretme-ve-Mockup Otomasyonu")

def render_advanced_mockup(
    art_cv: np.ndarray,
    bg_cv: np.ndarray,
    koseler: list,
    is_glass: bool,
    foreground_mask: np.ndarray = None
) -> np.ndarray:
    h_bg, w_bg = bg_cv.shape[:2]
    h_art, w_art = art_cv.shape[:2]
    p = np.float32(koseler) # [TL, TR, BR, BL]

    # -------------------------------------------------------------
    # 1. SMART-COVER: EN-BOY ORANI KORUMA (SÜNDÜRME & YAYILMA ÖNLEME)
    # -------------------------------------------------------------
    w_top = np.linalg.norm(p[1] - p[0])
    w_bot = np.linalg.norm(p[2] - p[3])
    h_left = np.linalg.norm(p[3] - p[0])
    h_right = np.linalg.norm(p[2] - p[1])
    target_w = max(1.0, (w_top + w_bot) / 2.0)
    target_h = max(1.0, (h_left + h_right) / 2.0)
    target_ar = target_w / target_h

    art_ar = w_art / float(h_art)

    if art_ar > target_ar:
        # Görsel hedeften daha geniş -> soldan ve sağdan eşit merkez kırp
        crop_w = int(round(h_art * target_ar))
        crop_h = h_art
        sx = max(0, (w_art - crop_w) // 2)
        sy = 0
        art_fitted = art_cv[:, sx:sx + crop_w]
    else:
        # Görsel hedeften daha uzun -> üstten ve alttan eşit merkez kırp
        crop_w = w_art
        crop_h = int(round(w_art / target_ar))
        sx = 0
        sy = max(0, (h_art - crop_h) // 2)
        art_fitted = art_cv[sy:sy + crop_h, :]

    # -------------------------------------------------------------
    # 2. SUB-PIXEL PERSPEKTİF HOMOGRAFİ
    # -------------------------------------------------------------
    fh, fw = art_fitted.shape[:2]
    src_pts = np.float32([[0, 0], [fw, 0], [fw, fh], [0, fh]])
    dst_pts = np.float32(koseler)
    matrix = cv2.getPerspectiveTransform(src_pts, dst_pts)

    warped = cv2.warpPerspective(
        art_fitted, matrix, (w_bg, h_bg),
        flags=cv2.INTER_LANCZOS4,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0)
    )

    # Temel Poligon Maskesi (Kenar antialiasing ile)
    mask_raw = np.zeros((h_bg, w_bg), dtype=np.uint8)
    cv2.fillConvexPoly(mask_raw, np.int32(dst_pts), 255)
    mask_f = cv2.GaussianBlur(mask_raw, (3, 3), 0.8).astype(np.float32) / 255.0
    mask_3c = np.stack([mask_f] * 3, axis=-1)

    # -------------------------------------------------------------
    # 3. ORTAM IŞIĞI HARMANLAMA (AMBIENT LUMINANCE MAPPING)
    # -------------------------------------------------------------
    bg_gray = cv2.cvtColor(bg_cv, cv2.COLOR_BGR2GRAY).astype(np.float32)
    poly_indices = mask_raw > 0
    if np.any(poly_indices):
        mean_lum = float(np.mean(bg_gray[poly_indices]))
        if mean_lum > 10.0:
            bg_smooth = cv2.GaussianBlur(bg_gray, (65, 65), 0)
            ambient_ratio = np.clip(bg_smooth / mean_lum, 0.75, 1.35)
            ambient_ratio_3c = np.stack([ambient_ratio] * 3, axis=-1)
            # Odanın doğal ışığını %18 oranında tasarıma yedir (spot ışık, pencere ışığı)
            warped_f = warped.astype(np.float32)
            warped_lit = warped_f * ((1.0 - 0.18) + 0.18 * ambient_ratio_3c)
        else:
            warped_lit = warped.astype(np.float32)
    else:
        warped_lit = warped.astype(np.float32)

    # -------------------------------------------------------------
    # 4. FİZİKSEL DUVAR / ZEMİN GÖLGESİ (3D DROP SHADOW)
    # -------------------------------------------------------------
    # Temas gölgesi (Contact shadow - keskin ve koyu)
    contact_shadow = np.zeros((h_bg, w_bg), dtype=np.float32)
    offset_c = np.array([[3, 5], [3, 5], [3, 5], [3, 5]], dtype=np.float32)
    cv2.fillConvexPoly(contact_shadow, (dst_pts + offset_c).astype(np.int32), 0.35)
    contact_shadow = cv2.GaussianBlur(contact_shadow, (9, 9), 0)

    # Ortam duvar gölgesi (Ambient shadow - geniş ve yumuşak)
    ambient_shadow = np.zeros((h_bg, w_bg), dtype=np.float32)
    offset_a = np.array([[12, 18], [12, 18], [12, 18], [12, 18]], dtype=np.float32)
    cv2.fillConvexPoly(ambient_shadow, (dst_pts + offset_a).astype(np.int32), 0.28)
    ambient_shadow = cv2.GaussianBlur(ambient_shadow, (39, 39), 0)

    total_shadow = np.clip(contact_shadow + ambient_shadow, 0.0, 0.65)
    # Yalnızca tablonun dışına düşen gölgeler
    shadow_outside = total_shadow * (1.0 - mask_f)
    shadow_outside_3c = np.stack([shadow_outside] * 3, axis=-1)

    # Arka plana gölgeyi çarp (Multiply)
    bg_shadowed = bg_cv.astype(np.float32) * (1.0 - shadow_outside_3c)

    if is_glass:
        # -------------------------------------------------------------
        # 5. ULTRA-GERÇEKÇİ KRİSTAL CAM SHADER (SPECULAR GLARE & RODAJ)
        # -------------------------------------------------------------
        # A) Kristal Derinlik & Kontrast (UV cam altı baskı derinliği)
        # S-Curve ile siyahlar tok, renkler canlı
        art_enhanced = warped_lit * 1.03 - 4.0
        art_enhanced = np.clip(art_enhanced, 0.0, 255.0)

        # B) Diyagonal Pencere / Stüdyo Işık Yansımaları (Specular Glare)
        # Kaynak alanda u, v koordinat haritası oluştur ve perspektifle bük
        gw, gh = int(target_w), int(target_h)
        yy, xx = np.mgrid[0:gh, 0:gw].astype(np.float32)
        u = (xx / float(gw) * 0.45 + (1.0 - yy / float(gh)) * 0.55)
        
        # Çift pencere ışıma bandı (Geniş ana pencere + ince ikincil yansıma)
        g1 = np.exp(-((u - 0.34) / 0.08) ** 2) * 55.0   # Ana pencere parlama çizgisi (peak ~22%)
        g2 = np.exp(-((u - 0.60) / 0.14) ** 2) * 35.0   # İkincil yumuşak ışık huzmesi
        g3 = (1.0 - (yy / float(gh))) * 18.0            # Tavandan süzülen ortam ışığı
        glare_local = np.clip(g1 + g2 + g3, 0.0, 95.0)
        glare_local_3c = np.stack([glare_local] * 3, axis=-1)

        glare_warped = cv2.warpPerspective(
            glare_local_3c, matrix, (w_bg, h_bg),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(0, 0, 0)
        )

        # C) 4mm Kristal Elmas Rodaj Kenar Pahı (Bevel Highlight & Shadow)
        bevel = np.zeros((h_bg, w_bg, 3), dtype=np.float32)
        p0, p1, p2, p3 = dst_pts[0], dst_pts[1], dst_pts[2], dst_pts[3]
        
        # Işık alan kenarlar (Üst ve Sol): Parlak beyaz rodaj çizgisi
        cv2.line(bevel, (int(p0[0]), int(p0[1])), (int(p1[0]), int(p1[1])), (255, 255, 255), 2, lineType=cv2.LINE_AA)
        cv2.line(bevel, (int(p0[0]), int(p0[1])), (int(p3[0]), int(p3[1])), (245, 245, 255), 2, lineType=cv2.LINE_AA)
        
        # Gölgede kalan kenarlar (Alt ve Sağ): Koyu derinlik kırılması
        bevel_dark = np.zeros((h_bg, w_bg, 3), dtype=np.float32)
        cv2.line(bevel_dark, (int(p3[0]), int(p3[1])), (int(p2[0]), int(p2[1])), (40, 40, 40), 2, lineType=cv2.LINE_AA)
        cv2.line(bevel_dark, (int(p1[0]), int(p1[1])), (int(p2[0]), int(p2[1])), (40, 40, 40), 2, lineType=cv2.LINE_AA)

        # Rodaj yumuşatma
        bevel = cv2.GaussianBlur(bevel, (3, 3), 0) * 0.70
        bevel_dark = cv2.GaussianBlur(bevel_dark, (3, 3), 0) * 0.40

        # D) Cam Yüzeyini Birleştir: (Baskı + Yansıma + Rodaj Işığı - Kenar Kırılması)
        glass_surface = np.clip(art_enhanced + glare_warped + bevel - bevel_dark, 0.0, 255.0)
        final = bg_shadowed * (1.0 - mask_3c) + glass_surface * mask_3c

    else:
        # -------------------------------------------------------------
        # 6. DOĞAL MAT AHŞAP & KANVAS MOTORU
        # -------------------------------------------------------------
        # Ahşap çerçeveli tablolarda çerçeve içi iç gölge (Inner frame shadow)
        inner_shadow = np.zeros((h_bg, w_bg), dtype=np.float32)
        p0, p1, p2, p3 = dst_pts[0], dst_pts[1], dst_pts[2], dst_pts[3]
        cv2.line(inner_shadow, (int(p0[0]), int(p0[1])), (int(p1[0]), int(p1[1])), 0.35, 4, lineType=cv2.LINE_AA)
        cv2.line(inner_shadow, (int(p0[0]), int(p0[1])), (int(p3[0]), int(p3[1])), 0.35, 4, lineType=cv2.LINE_AA)
        inner_shadow = cv2.GaussianBlur(inner_shadow, (7, 7), 0)
        inner_shadow_3c = np.stack([inner_shadow] * 3, axis=-1)

        wood_surface = np.clip(warped_lit * (1.0 - inner_shadow_3c), 0.0, 255.0)
        final = bg_shadowed * (1.0 - mask_3c) + wood_surface * mask_3c

    final = np.clip(final, 0, 255).astype(np.uint8)

    # -------------------------------------------------------------
    # 7. CANVA AKILLI ÖN PLAN (FOREGROUND RESTORE)
    # -------------------------------------------------------------
    if foreground_mask is not None and np.any(foreground_mask):
        alpha = (foreground_mask.astype(np.float32) / 255.0)[..., None]
        final = np.clip(bg_cv.astype(np.float32) * alpha + final.astype(np.float32) * (1.0 - alpha), 0, 255).astype(np.uint8)

    return final

if __name__ == "__main__":
    print("Test rendering with advanced glass and perspective...")
    # Test 1: Cam Tablo Dikey
    bg1 = cv2.imread(r"2_SABLON_HAVUZU/02_Cam_Tablo_Dikey/Gemini_Generated_Image_484mjl484mjl484m (1).jpeg")
    art_v = cv2.imread(r"1_GELEN_KAGGLE_BASKILARI/M000001_V.png")
    
    with open(r"SISTEM_MOTORU/ayarlar.json", "r", encoding="utf-8") as f:
        ayarlar = json.load(f)
        
    def get_koseler(s_conf):
        if "koseler" in s_conf:
            return s_conf["koseler"]
        x, y, w, h = s_conf["x"], s_conf["y"], s_conf["w"], s_conf["h"]
        return [[x, y], [x + w, y], [x + w, y + h], [x, y + h]]

    s_conf1 = ayarlar["kategoriler"]["02_Cam_Tablo_Dikey"]["sablonlar"]["Gemini_Generated_Image_484mjl484mjl484m (1).jpeg"]
    k1 = get_koseler(s_conf1)
    res1 = render_advanced_mockup(art_v, bg1, k1, is_glass=True)
    cv2.imwrite(r"SISTEM_MOTORU/test_advanced_cam_tablo_dikey.jpg", res1)
    print("Saved test_advanced_cam_tablo_dikey.jpg")

    # Test 2: Cam Tablo Yatay
    bg2 = cv2.imread(r"2_SABLON_HAVUZU/02_Cam_Tablo_Yatay/olimpos-simsegi-cam-tablo_2.webp")
    art_h = cv2.imread(r"1_GELEN_KAGGLE_BASKILARI/M000001_H.png")
    s_conf2 = ayarlar["kategoriler"]["02_Cam_Tablo_Yatay"]["sablonlar"]["olimpos-simsegi-cam-tablo_2.webp"]
    k2 = get_koseler(s_conf2)
    res2 = render_advanced_mockup(art_h, bg2, k2, is_glass=True)
    cv2.imwrite(r"SISTEM_MOTORU/test_advanced_cam_tablo_yatay.jpg", res2)
    print("Saved test_advanced_cam_tablo_yatay.jpg")

    # Test 3: Ocak Arkası (Köşe Düzeltilmiş)
    bg3 = cv2.imread(r"2_SABLON_HAVUZU/05_Ocak_Arkasi/1_org_zoom.webp")
    # Grounded on countertop at y=1075:
    k3 = [[202, 455], [994, 457], [995, 1075], [202, 1075]]
    res3 = render_advanced_mockup(art_h, bg3, k3, is_glass=True)
    cv2.imwrite(r"SISTEM_MOTORU/test_advanced_ocak_arkasi.jpg", res3)
    print("Saved test_advanced_ocak_arkasi.jpg")

    # Test 4: Wifi Kutusu (Exact White Box Corners)
    bg4 = cv2.imread(r"2_SABLON_HAVUZU/01_Wifi_Kutusu/wifiKutusuBos4.jpeg")
    k4 = [[405, 489], [743, 489], [743, 786], [405, 786]]
    res4 = render_advanced_mockup(art_h, bg4, k4, is_glass=False)
    cv2.imwrite(r"SISTEM_MOTORU/test_advanced_wifi_kutusu.jpg", res4)
    print("Saved test_advanced_wifi_kutusu.jpg")

    # Test 5: Cam Doğrama (Canva Foreground Mask ile)
    bg5 = cv2.imread(r"2_SABLON_HAVUZU/04_Cam_Dograma/cam-kesme-tahtasi-kalin-ve-kirilmaz-cam-vintage-sebzeler-21-30cm-dograma-tahtasi-mutfak-dekoru-53384.webp")
    k5 = [[143, 1040], [2254, 1052], [2254, 2523], [152, 2538]]
    mask_file = Path(r"SISTEM_MOTORU/masks/cam-kesme-tahtasi-kalin-ve-kirilmaz-cam-vintage-sebzeler-21-30cm-dograma-tahtasi-mutfak-dekoru-53384_foreground_mask.png")
    fg_m = cv2.imread(str(mask_file), cv2.IMREAD_GRAYSCALE) if mask_file.exists() else None
    res5 = render_advanced_mockup(art_h, bg5, k5, is_glass=True, foreground_mask=fg_m)
    cv2.imwrite(r"SISTEM_MOTORU/test_advanced_cam_dograma.jpg", res5)
    print("Saved test_advanced_cam_dograma.jpg")
