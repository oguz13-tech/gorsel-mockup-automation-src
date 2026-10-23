import http.server
import socketserver
import json
import os
import time
import urllib.parse
import shutil
import cv2
import numpy as np
import logging
import glob
import hashlib
import sys
import threading
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[2]
_runtime_override = str(os.environ.get("MOCKUP_RUNTIME_WORKSPACE") or "").strip()
RUNTIME_ROOT = (
    Path(_runtime_override).expanduser().resolve()
    if _runtime_override
    else SOURCE_ROOT.resolve()
)

# ======================== LOGGING SETUP ========================
LOG_DIR = os.fspath(
    RUNTIME_ROOT / "SABLON_V2_MIMARI" / "core" / "logs"
)
os.makedirs(LOG_DIR, exist_ok=True)
logger = logging.getLogger('sablon_duzeltici')
logger.setLevel(logging.DEBUG)
_fh = logging.FileHandler(os.path.join(LOG_DIR, 'sablon.log'), encoding='utf-8')
_fh.setLevel(logging.DEBUG)
_ch = logging.StreamHandler()
_ch.setLevel(logging.INFO)
_fmt = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
_fh.setFormatter(_fmt)
_ch.setFormatter(_fmt)
logger.addHandler(_fh)
logger.addHandler(_ch)

PORT = 8999
# Mutable assets come from the explicit runtime workspace when configured.
BASE_DIR = os.fspath(RUNTIME_ROOT)
AYARLAR_PATH = os.path.join(
    BASE_DIR,
    "99_SISTEM_MOTORLARI_VE_KODLAR",
    "SISTEM_MOTORU",
    "ayarlar.json",
)
YEDEK_IMG_DIR = os.path.join(
    BASE_DIR,
    "2_SABLON_HAVUZU_ORIJINAL_YEDEK",
)

AYARLAR_LOCK = threading.Lock()
import contextlib
@contextlib.contextmanager
def acquire_os_lock(path_str):
    lock_file = str(path_str).replace('.json', '.json.lock')
    fd = None
    for attempt in range(50):
        try:
            fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            time.sleep(0.1)
    else:
        logger.error(f"Kritik Hata: OS-Level Lock alınamadı! {lock_file}")
        raise RuntimeError(f"Sistem meşgul, {lock_file} kilitli. Lütfen birkaç saniye sonra tekrar deneyin.")
    
    try:
        yield
    finally:
        if fd is not None:
            os.close(fd)
            try:
                os.remove(lock_file)
            except:
                pass


# ======================== OTOMATIK KOSE ALGILAMA ========================
def detect_document_corners(img_cv, method='advanced'):
    """
    Gorsel uzerinde baskiya uygun duz yuzey/cerceve icini (en buyuk dikdortgenimsi bolgeyi)
    otomatik tespit eder. SIFT/ORB + contour + approxPolyDP kullanir.
    
    Returns: [[x1,y1],[x2,y2],[x3,y3],[x4,y4]] saat yonunde siralanmis 4 kose
             veya None (bulunamazsa)
    """
    if img_cv is None:
        return None
    
    h, w = img_cv.shape[:2]
    
    # Performans icin buyuk gorselleri kucult
    max_dim = 1200
    scale = 1.0
    if max(h, w) > max_dim:
        scale = max_dim / max(h, w)
        img_small = cv2.resize(img_cv, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    else:
        img_small = img_cv.copy()
    
    sh, sw = img_small.shape[:2]
    
    # ---- YONTEM 1: Renk/Parlaklık Farkı ile İç Alan Tespiti ----
    gray = cv2.cvtColor(img_small, cv2.COLOR_BGR2GRAY)
    
    # Adaptif Gaussian blur + threshold
    blurred = cv2.GaussianBlur(gray, (7, 7), 0)
    
    # Birden fazla threshold denemesi yap
    best_corners = None
    best_area = 0
    
    # Canny edge detection ile contour ara
    for canny_low in [30, 50, 80]:
        for canny_high in [100, 150, 200]:
            edges = cv2.Canny(blurred, canny_low, canny_high)
            
            # Morfolojik kapama - kirik kenarlari birlestir
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
            edges = cv2.dilate(edges, kernel, iterations=2)
            edges = cv2.erode(edges, kernel, iterations=1)
            
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            for cnt in contours:
                area = cv2.contourArea(cnt)
                if area < (sw * sh * 0.05):  # Cok kucuk alanları atla
                    continue
                if area > (sw * sh * 0.95):  # Tam gorseli kaplayan contour'u atla
                    continue
                
                peri = cv2.arcLength(cnt, True)
                approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
                
                if len(approx) == 4 and cv2.isContourConvex(approx):
                    if area > best_area:
                        best_area = area
                        best_corners = approx.reshape(4, 2)
    
    # ---- YONTEM 2: Hough Lines + kesisim noktaları ----
    if best_corners is None:
        edges2 = cv2.Canny(blurred, 50, 150)
        lines = cv2.HoughLinesP(edges2, 1, np.pi / 180, 80, minLineLength=sw * 0.15, maxLineGap=20)
        
        if lines is not None and len(lines) >= 4:
            # En guclu yatay ve dikey cizgileri bul
            h_lines = []
            v_lines = []
            for line in lines:
                flat_line = line.flatten()
                if len(flat_line) != 4:
                    continue
                x1, y1, x2, y2 = flat_line
                angle = abs(np.degrees(np.arctan2(y2 - y1, x2 - x1)))
                if angle < 20 or angle > 160:  # Yatay
                    h_lines.append((x1, y1, x2, y2))
                elif 70 < angle < 110:  # Dikey
                    v_lines.append((x1, y1, x2, y2))
            
            if len(h_lines) >= 2 and len(v_lines) >= 2:
                # En ust ve en alt yatay cizgi
                h_lines.sort(key=lambda l: (l[1] + l[3]) / 2)
                top_line = h_lines[0]
                bot_line = h_lines[-1]
                
                # En sol ve en sag dikey cizgi
                v_lines.sort(key=lambda l: (l[0] + l[2]) / 2)
                left_line = v_lines[0]
                right_line = v_lines[-1]
                
                # 4 kesisim noktasini hesapla
                def line_intersection(l1, l2):
                    x1, y1, x2, y2 = l1
                    x3, y3, x4, y4 = l2
                    denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
                    if abs(denom) < 1e-6:
                        return None
                    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom
                    ix = x1 + t * (x2 - x1)
                    iy = y1 + t * (y2 - y1)
                    return (ix, iy)
                
                tl = line_intersection(top_line, left_line)
                tr = line_intersection(top_line, right_line)
                br = line_intersection(bot_line, right_line)
                bl = line_intersection(bot_line, left_line)
                
                if all(p is not None for p in [tl, tr, br, bl]):
                    corners = np.array([tl, tr, br, bl], dtype=np.float32)
                    # Sinirlari kontrol et
                    if np.all(corners >= 0) and np.all(corners[:, 0] <= sw) and np.all(corners[:, 1] <= sh):
                        best_corners = corners
    
    # ---- YONTEM 3: ORB Feature Matching + Homography (en guclu) ----
    if best_corners is None:
        # Buyuk, homojen (beyaz/duz) ic alani tespit et
        # HSV uzayinda dusuk saturasyon ve yuksek parlaklik -> beyaz/acik alan
        hsv = cv2.cvtColor(img_small, cv2.COLOR_BGR2HSV)
        # Dusuk doygunluk ve yuksek parlaklık -> baskı alanı adayı
        mask_bright = cv2.inRange(hsv, (0, 0, 160), (180, 60, 255))
        # Morfolojik acma/kapama
        kernel_big = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
        mask_bright = cv2.morphologyEx(mask_bright, cv2.MORPH_CLOSE, kernel_big)
        mask_bright = cv2.morphologyEx(mask_bright, cv2.MORPH_OPEN, kernel_big)
        
        contours_b, _ = cv2.findContours(mask_bright, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in sorted(contours_b, key=cv2.contourArea, reverse=True):
            area = cv2.contourArea(cnt)
            if area < (sw * sh * 0.03):
                break
            if area > (sw * sh * 0.90):
                continue
            peri = cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, 0.03 * peri, True)
            if len(approx) == 4 and cv2.isContourConvex(approx):
                best_corners = approx.reshape(4, 2)
                best_area = area
                break
            elif len(approx) > 4:
                # MinAreaRect ile dikdortgen yakinsama
                rect = cv2.minAreaRect(cnt)
                box = cv2.boxPoints(rect)
                best_corners = box.astype(np.float32)
                best_area = area
                break
    
    if best_corners is None:
        logger.warning("Otomatik kose algılama basarisiz - hicbir yontemle 4 kose bulunamadi")
        return None
    
    # Olceklemeyi geri al
    if scale != 1.0:
        best_corners = best_corners / scale
    
    # Saat yonunde siralama (sol-ust'ten baslayarak)
    corners = best_corners.astype(np.float32)
    center = corners.mean(axis=0)
    angles = np.arctan2(corners[:, 1] - center[1], corners[:, 0] - center[0])
    sorted_idx = np.argsort(angles)
    sorted_corners = corners[sorted_idx]
    
    # Sol-ust'u bul (en kucuk x+y toplami)
    sums = sorted_corners[:, 0] + sorted_corners[:, 1]
    start_idx = np.argmin(sums)
    ordered = np.roll(sorted_corners, -start_idx, axis=0)
    
    result = [[int(round(p[0])), int(round(p[1]))] for p in ordered]
    logger.info(f"Otomatik kose algilama basarili: {result}")
    return result


def detect_occlusion_boxes(img_cv, koseler_pts):
    """
    4 köşe ile tanımlı baskı alanına dışarıdan taşan / ön planda duran nesneleri (domates, sarımsak, bıçak, yeşillik vb.)
    otomatik olarak tespit edip GrabCut nesne kutularını üretir.
    """
    if img_cv is None or not koseler_pts or len(koseler_pts) < 3:
        return []
        
    h, w = img_cv.shape[:2]
    pts = np.array(koseler_pts, dtype=np.int32)
    
    # 1. Ürün poligon maskesi
    board_mask = np.zeros((h, w), dtype=np.uint8)
    cv2.fillPoly(board_mask, [pts], 255)
    
    bx, by, bw, bh = cv2.boundingRect(pts)
    board_center = np.array([bx + bw / 2.0, by + bh / 2.0])
    
    # 2. Masanın (dış alan) medyan rengi
    table_mask = cv2.bitwise_not(board_mask)
    table_pixels = img_cv[table_mask == 255]
    if len(table_pixels) > 0:
        median_table = np.median(table_pixels, axis=0)
    else:
        median_table = np.array([200, 200, 200], dtype=np.float32)
        
    # 3. Masadaki nesneler (Masa renginden farklı kalın/hacimli nesneler)
    diff_table = np.linalg.norm(img_cv.astype(np.float32) - median_table.astype(np.float32), axis=2)
    
    # Tahta çevresindeki 250 px'lik dış banda odaklan
    band_size = max(151, int(min(bw, bh) * 0.25))
    if band_size % 2 == 0:
        band_size += 1
    outer_band = cv2.dilate(board_mask, cv2.getStructuringElement(cv2.MORPH_RECT, (band_size, band_size)))
    table_props = (diff_table > 35).astype(np.uint8) * 255
    table_props = cv2.bitwise_and(table_props, outer_band)
    table_props[board_mask == 255] = 0 # Kesinlikle tahta dışı
    
    # Elips açma ile ince gölgeleri ve cam kenar çizgilerini yok et
    k_thick = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (25, 25))
    table_props_thick = cv2.morphologyEx(table_props, cv2.MORPH_OPEN, k_thick)
    table_props_thick = cv2.morphologyEx(table_props_thick, cv2.MORPH_CLOSE, k_thick)
    
    # 4. Tahta sınırına değen/kesişen nesneleri bul
    perim = np.zeros((h, w), dtype=np.uint8)
    cv2.polylines(perim, [pts], isClosed=True, color=255, thickness=20)
    
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(table_props_thick)
    generated_boxes = []
    
    for i in range(1, num_labels):
        area = stats[i, cv2.CC_STAT_AREA]
        if area < 2500:
            continue
            
        comp_mask = (labels == i).astype(np.uint8)
        touches = np.count_nonzero(cv2.bitwise_and(comp_mask, perim))
        if touches < 10:
            continue
            
        px = stats[i, cv2.CC_STAT_LEFT]
        py = stats[i, cv2.CC_STAT_TOP]
        pw = stats[i, cv2.CC_STAT_WIDTH]
        ph = stats[i, cv2.CC_STAT_HEIGHT]
        
        touch_pts = np.argwhere(cv2.bitwise_and(comp_mask, perim) > 0)
        min_ty, min_tx = np.min(touch_pts, axis=0)
        max_ty, max_tx = np.max(touch_pts, axis=0)
        touch_center = np.array([(min_tx + max_tx) / 2.0, (min_ty + max_ty) / 2.0])
        
        direction = board_center - touch_center
        dir_norm = np.linalg.norm(direction)
        if dir_norm > 1e-3:
            dir_unit = direction / dir_norm
        else:
            dir_unit = np.array([0.0, 0.0])
            
        # Intrusion depth (içe taşma derinliği)
        prop_dim = max(pw, ph)
        intrusion_depth = int(np.clip(prop_dim * 0.75, 120, 320))
        
        box_x1 = min(px, int(touch_center[0] + dir_unit[0] * intrusion_depth)) - 25
        box_x2 = max(px + pw, int(touch_center[0] + dir_unit[0] * intrusion_depth)) + 25
        box_y1 = min(py, int(touch_center[1] + dir_unit[1] * intrusion_depth)) - 25
        box_y2 = max(py + ph, int(touch_center[1] + dir_unit[1] * intrusion_depth)) + 25
        
        box_x1 = max(0, int(box_x1))
        box_y1 = max(0, int(box_y1))
        box_x2 = min(w, int(box_x2))
        box_y2 = min(h, int(box_y2))
        
        box_w = box_x2 - box_x1
        box_h = box_y2 - box_y1
        if box_w > 50 and box_h > 50 and (box_w * box_h) < (w * h * 0.40):
            generated_boxes.append([box_x1, box_y1, box_x2, box_y2])
            
    # Kesişen kutuları birleştir
    def merge_intersecting(boxes):
        merged = []
        for b in boxes:
            matched = False
            for m in merged:
                if not (b[2] < m[0] or b[0] > m[2] or b[3] < m[1] or b[1] > m[3]):
                    m[0] = min(m[0], b[0])
                    m[1] = min(m[1], b[1])
                    m[2] = max(m[2], b[2])
                    m[3] = max(m[3], b[3])
                    matched = True
                    break
            if not matched:
                merged.append(list(b))
        return merged

    final_boxes = merge_intersecting(generated_boxes)
    return [[int(c) for c in b] for b in final_boxes]

class MockupHandler(http.server.SimpleHTTPRequestHandler):
    def address_string(self):
        # DNS cozumlemesini devre disi birakarak her istegin 2-4 saniye gecikmesini onler
        host, port = self.client_address[:2]
        return host

    def send_file_download(self, file_path, send_body=True):
        self.send_response(200)
        if file_path.endswith('.zip'):
            self.send_header('Content-type', 'application/zip')
        elif file_path.endswith('.xlsx'):
            self.send_header('Content-type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        else:
            self.send_header('Content-type', 'application/octet-stream')
        self.send_header('Content-Disposition', f'attachment; filename="{os.path.basename(file_path)}"')
        self.send_header('Content-Length', str(os.path.getsize(file_path)))
        self.end_headers()
        if send_body:
            with open(file_path, 'rb') as f:
                shutil.copyfileobj(f, self.wfile)

    def do_HEAD(self):
        if self.path.startswith('/download/'):
            filename = urllib.parse.unquote(self.path.replace('/download/', '', 1))
            
            # GUVENLIK: Path Traversal (Dizin Atlatma) Korumasi
            safe_base = os.path.abspath(BASE_DIR)
            file_path = os.path.abspath(os.path.join(safe_base, filename))
            if not file_path.startswith(safe_base):
                self.send_error(403, "Erisim engellendi")
                return
                
            if not os.path.exists(file_path):
                alt_base = os.path.join(safe_base, "3_URETILEN_MOCKUPLAR")
                alt_file_path = os.path.abspath(os.path.join(alt_base, filename))
                if alt_file_path.startswith(os.path.abspath(alt_base)):
                    file_path = alt_file_path

            if os.path.exists(file_path) and os.path.isfile(file_path):
                self.send_file_download(file_path, send_body=False)
                return
            self.send_error(404, "Dosya bulunamadi")
        elif self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(HTML_CONTENT.encode('utf-8'))))
            self.end_headers()
        else:
            self.send_response(200)
            self.end_headers()

    def do_GET(self):
        req_path = self.path.split('?')[0]
        if req_path == '/':
            encoded_html = HTML_CONTENT.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.send_header('Connection', 'close')
            self.end_headers()
            self.wfile.write(encoded_html)
        elif req_path == '/api/saglik_durumu':
            rapor_path = os.path.join(BASE_DIR, "99_SISTEM_MOTORLARI_VE_KODLAR", "SISTEM_MOTORU", "logs", "sistem_saglik_raporu.json")
            if os.path.exists(rapor_path):
                with open(rapor_path, 'r', encoding='utf-8') as rf:
                    data = rf.read()
            else:
                data = '{"sorun_sayisi": 0, "sorunlar": [], "cozulen_sayisi": 0, "cozulenler": []}'
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(data.encode('utf-8'))
        elif req_path == '/api/ayarlar':
            # P0: Reading settings must never mutate or ingest images.
            with AYARLAR_LOCK:
                with open(AYARLAR_PATH, 'r', encoding='utf-8') as f:
                    encoded_json = f.read().encode('utf-8')
            self.send_response(200)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.send_header('Connection', 'close')
            self.end_headers()
            self.wfile.write(encoded_json)
        elif req_path == '/favicon.ico':
            # Inline SVG favicon - 404 onleme
            self.send_response(204)
            self.end_headers()
        elif req_path.startswith('/preview/'):
            parts = [urllib.parse.unquote(p) for p in req_path.split('/') if p]
            if len(parts) >= 3:
                cat = parts[1]
                tmpl = parts[2]
                # P0: previews are derived images outside the watcher inbox.
                # Reject traversal, spoofed category IDs and symlink redirects.
                from SABLON_V2_MIMARI.core.template_identity import CATEGORY_PREFIXES
                if cat not in CATEGORY_PREFIXES or Path(tmpl).name != tmpl:
                    self.send_error(403, "Gecersiz onizleme konumu")
                    return
                preview_base = Path(BASE_DIR).resolve() / "_ONIZLEME_SABLONLAR"
                image = preview_base / cat / (Path(tmpl).stem + "-beyazlatilmis-onizleme.png")
                if (preview_base.is_symlink() or image.parent.is_symlink()
                        or image.is_symlink()
                        or not image.resolve().is_relative_to(preview_base.resolve())):
                    self.send_error(403, "Onizleme erisimi engellendi")
                    return
                img_path = str(image)

                if os.path.exists(img_path):
                    self.send_file_download(img_path, send_body=True)
                else:
                    self.send_error(404, "Onizleme bulunamadi")
            else:
                self.send_error(400, "Hatali istek")
        elif req_path.startswith('/image/'):
            parts = [urllib.parse.unquote(p) for p in req_path.split('/') if p]
            if len(parts) >= 3:
                cat = parts[1]
                tmpl = parts[2]
                
                # GUVENLIK: Path Traversal (Dizin Atlatma) Korumasi
                safe_yedek_base = os.path.abspath(YEDEK_IMG_DIR)
                img_path = os.path.abspath(os.path.join(safe_yedek_base, cat, tmpl))
                
                if not img_path.startswith(safe_yedek_base):
                    self.send_error(403, "Erisim engellendi")
                    return
                
                if not os.path.exists(img_path):
                    # Orijinal yedek yoksa (veya PNG ise uzantiyi kontrol et)
                    stem = Path(tmpl).stem
                    
                    # 1. Önce YEDEK klasöründen orijinal bozulmamış halini ara (Kullanıcı köşeleri rahat seçebilsin diye)
                    yedek_path = None
                    for alt_ext in [".webp", ".jpg", ".jpeg", ".png", ".avif"]:
                        cand = os.path.abspath(os.path.join(safe_yedek_base, cat, stem + alt_ext))
                        if cand.startswith(safe_yedek_base) and os.path.exists(cand):
                            yedek_path = cand
                            break
                            
                    if yedek_path:
                        img_path = yedek_path
                    else:
                        # 2. YEDEK'te yoksa, mevcut 2_SABLON_HAVUZU'ndaki PNG'yi veya diğerlerini al
                        safe_havuz_base = os.path.abspath(os.path.join(BASE_DIR, "2_SABLON_HAVUZU"))
                        cand_png = os.path.abspath(os.path.join(safe_havuz_base, cat, stem + ".png"))
                        if cand_png.startswith(safe_havuz_base) and os.path.exists(cand_png):
                            img_path = cand_png
                        else:
                            fallback_path = os.path.abspath(os.path.join(safe_havuz_base, cat, tmpl))
                            if fallback_path.startswith(safe_havuz_base):
                                img_path = fallback_path
                if os.path.exists(img_path):
                    # ETag ve Last-Modified cache kontrolu
                    file_stat = os.stat(img_path)
                    etag = hashlib.md5(f"{img_path}:{file_stat.st_mtime}:{file_stat.st_size}".encode()).hexdigest()
                    last_modified = time.strftime('%a, %d %b %Y %H:%M:%S GMT', time.gmtime(file_stat.st_mtime))
                    
                    # If-None-Match kontrolu - degismemisse 304 don
                    client_etag = self.headers.get('If-None-Match', '')
                    if client_etag == f'"{etag}"':
                        self.send_response(304)
                        self.send_header('ETag', f'"{etag}"')
                        self.send_header('Cache-Control', 'no-cache')
                        self.end_headers()
                        return
                    
                    self.send_response(200)
                    if img_path.lower().endswith('.png'):
                        self.send_header('Content-type', 'image/png')
                    elif img_path.lower().endswith('.webp'):
                        self.send_header('Content-type', 'image/webp')
                    else:
                        self.send_header('Content-type', 'image/jpeg')
                    self.send_header('ETag', f'"{etag}"')
                    self.send_header('Last-Modified', last_modified)
                    self.send_header('Cache-Control', 'no-cache')
                    self.end_headers()
                    with open(img_path, 'rb') as f:
                        self.wfile.write(f.read())
                    return
            self.send_error(404, "Resim bulunamadi")
        elif self.path.startswith('/download/'):
            filename = urllib.parse.unquote(self.path.replace('/download/', '', 1))
            
            # GUVENLIK: Path Traversal (Dizin Atlatma) Korumasi
            safe_base = os.path.abspath(BASE_DIR)
            file_path = os.path.abspath(os.path.join(safe_base, filename))
            if not file_path.startswith(safe_base):
                self.send_error(403, "Erisim engellendi")
                return
                
            if not os.path.exists(file_path):
                alt_base = os.path.join(safe_base, "3_URETILEN_MOCKUPLAR")
                alt_file_path = os.path.abspath(os.path.join(alt_base, filename))
                if alt_file_path.startswith(os.path.abspath(alt_base)):
                    file_path = alt_file_path

            if os.path.exists(file_path) and os.path.isfile(file_path):
                self.send_file_download(file_path, send_body=True)
                return
            self.send_error(404, "Dosya bulunamadi")
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        routes = {
            '/api/ayarlar': self._handle_api_ayarlar,
            '/api/tekil_sablon_kaydet': self._handle_api_tekil_sablon_kaydet,
            '/api/anlik_beyazlat': self._handle_api_anlik_beyazlat,
            '/api/orijinal_yukle': self._handle_api_orijinal_yukle,
            '/api/sablon_sil': self._handle_api_sablon_sil,
            '/api/sablon_sil_geri_al': self._handle_api_sablon_sil_geri_al,
            '/api/tumunu_beyazlat': self._handle_api_tumunu_beyazlat,
            '/api/auto_detect_corners': self._handle_api_auto_detect_corners
        }
        handler = routes.get(self.path)
        if handler:
            handler()
        else:
            self.send_error(404, "Not Found")

    def _handle_api_tekil_sablon_kaydet(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        try:
            req = json.loads(post_data.decode('utf-8'))
            cat = req.get("kategori")
            tmpl = req.get("sablon")
            data = req.get("data")
            
            if not cat or not tmpl or not data:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": "Eksik parametre"}).encode())
                return
                
            with AYARLAR_LOCK:
                with acquire_os_lock(AYARLAR_PATH):
                    if os.path.exists(AYARLAR_PATH):
                        with open(AYARLAR_PATH, 'r', encoding='utf-8') as current_f:
                            try:
                                current_data = json.load(current_f)
                            except:
                                current_data = {"kategoriler": {}}
                    else:
                        current_data = {"kategoriler": {}}
                        
                    if "kategoriler" not in current_data:
                        current_data["kategoriler"] = {}
                    if cat not in current_data["kategoriler"]:
                        current_data["kategoriler"][cat] = {"sablonlar": {}}
                        
                    # Yalnizca belirtilen sablonu guncelle, geri kalan HER SEYI (diger sekmelerdeki degisiklikleri) koru
                    current_data["kategoriler"][cat]["sablonlar"][tmpl] = data
                    
                    # ATOMIC WRITE
                    tmp_path = AYARLAR_PATH + ".tmp"
                    with open(tmp_path, 'w', encoding='utf-8') as f:
                        json.dump(current_data, f, indent=2, ensure_ascii=False)
                    os.replace(tmp_path, AYARLAR_PATH)
                    
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"success": True}).encode('utf-8'))
        except Exception as e:
            logger.error(f"Tekil kayit hatasi: {e}")
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode())

    def _handle_api_ayarlar(self):
        """Persist settings and an optional, explicitly selected working revision.

        Order matters: working PNG is snapshotted/published first and will be
        rolled back if JSON cannot be saved. No original/archive mutation.
        """
        from SABLON_V2_MIMARI.core.safe_working_revision import (
            working_png_revision, WorkingRevisionBlocked,
        )
        try:
            import contextlib
            import uuid
            content_length = int(self.headers["Content-Length"])
            new_data = json.loads(self.rfile.read(content_length).decode("utf-8"))
            active_cat = self.headers.get("X-Active-Category", "")
            active_tmpl = self.headers.get("X-Active-Template", "")
            transaction = contextlib.nullcontext()
            if bool(active_cat) != bool(active_tmpl):
                raise ValueError("ACTIVE_CATEGORY_TEMPLATE_MISMATCH")
            if active_cat:
                sm_dir = os.path.join(BASE_DIR, "99_SISTEM_MOTORLARI_VE_KODLAR", "SISTEM_MOTORU")
                if sm_dir not in sys.path:
                    sys.path.append(sm_dir)
                from sablon_beyazlatma_motoru import whiten_canvas, imread_unicode
                from SABLON_V2_MIMARI.core.template_identity import CATEGORY_PREFIXES
                if active_cat not in CATEGORY_PREFIXES or Path(active_tmpl).name != active_tmpl:
                    raise ValueError("INVALID_ACTIVE_TEMPLATE_PATH")
                backup_folder = Path(YEDEK_IMG_DIR) / active_cat
                if backup_folder.is_symlink():
                    raise WorkingRevisionBlocked("ORIGINAL_FOLDER_SYMLINK_BLOCKED")
                candidates = [backup_folder / active_tmpl] + [
                    backup_folder / (Path(active_tmpl).stem + ext)
                    for ext in (".png", ".jpg", ".jpeg", ".webp", ".avif")
                ]
                src = next((p for p in candidates if p.is_file() and not p.is_symlink()), None)
                if src is None:
                    raise FileNotFoundError("IMMUTABLE_ORIGINAL_NOT_FOUND: " + active_tmpl)
                image = imread_unicode(src)
                if image is None:
                    raise ValueError("ORIGINAL_IMAGE_UNREADABLE")
                conf = new_data["kategoriler"][active_cat]["sablonlar"][active_tmpl]
                whitened = whiten_canvas(
                    image, conf,
                    is_frameless=active_cat in ("01_Wifi_Kutusu", "04_Cam_Dograma", "05_Ocak_Arkasi"),
                )
                transaction = working_png_revision(BASE_DIR, active_cat, active_tmpl, whitened)
            with transaction:
                with AYARLAR_LOCK:
                    with acquire_os_lock(AYARLAR_PATH):
                        if os.path.isfile(AYARLAR_PATH):
                            with open(AYARLAR_PATH, "r", encoding="utf-8") as stream:
                                current = json.load(stream)  # Corrupt JSON MUST fail closed.
                        else:
                            current = {"kategoriler": {}}
                        current.setdefault("kategoriler", {})
                        for cat, obj in new_data.get("kategoriler", {}).items():
                            current["kategoriler"].setdefault(cat, {"sablonlar": {}})
                            current["kategoriler"][cat].setdefault("sablonlar", {})
                            for name, values in obj.get("sablonlar", {}).items():
                                current["kategoriler"][cat]["sablonlar"][name] = values
                        for key, value in new_data.items():
                            if key != "kategoriler":
                                current[key] = value
                        # Never rotate/delete backups just to make space.
                        if os.path.isfile(AYARLAR_PATH):
                            ts = time.strftime("%Y%m%d_%H%M%S")
                            snapshot = AYARLAR_PATH + ".user_backup_" + ts + "_" + uuid.uuid4().hex
                            with open(AYARLAR_PATH, "rb") as src, open(snapshot, "xb") as dst:
                                shutil.copyfileobj(src, dst)
                        tmp = AYARLAR_PATH + "." + uuid.uuid4().hex + ".p0tmp"
                        try:
                            with open(tmp, "x", encoding="utf-8") as stream:
                                json.dump(current, stream, indent=2, ensure_ascii=False)
                                stream.flush()
                                os.fsync(stream.fileno())
                            os.replace(tmp, AYARLAR_PATH)
                        finally:
                            if os.path.exists(tmp):
                                os.unlink(tmp)
                        # Optional compatibility copy: not a second commit gate.
                        try:
                            root_copy = os.path.join(BASE_DIR, "ayarlar.json")
                            shutil.copy2(AYARLAR_PATH, root_copy)
                        except OSError as mirror_error:
                            logger.warning("AYARLAR ROOT MIRROR UNAVAILABLE: %s", mirror_error)
            self.send_response(200)
            self.send_header("Content-type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(b'{"success": true}')
        except Exception as error:
            logger.error("P0 SETTINGS/WORKING REVISION FAILED: %s", error)
            self.send_response(409 if isinstance(error, (WorkingRevisionBlocked, FileNotFoundError)) else 500)
            self.send_header("Content-type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"success": False, "error": str(error)}).encode("utf-8"))

    def _handle_api_anlik_beyazlat(self):
        """Derived preview only: does NOT change the approved working PNG."""
        from SABLON_V2_MIMARI.core.safe_working_revision import (
            save_preview_only, WorkingRevisionBlocked,
        )
        try:
            new_data = json.loads(self.rfile.read(int(self.headers["Content-Length"])).decode("utf-8"))
            category = self.headers.get("X-Active-Category", "")
            template = self.headers.get("X-Active-Template", "")
            if not category or not template:
                raise ValueError("Kategori veya sablon eksik")
            sm_dir = os.path.join(BASE_DIR, "99_SISTEM_MOTORLARI_VE_KODLAR", "SISTEM_MOTORU")
            if sm_dir not in sys.path:
                sys.path.append(sm_dir)
            from sablon_beyazlatma_motoru import whiten_canvas, imread_unicode
            stem = Path(template).stem
            source = None
            for ext in (".png", ".jpg", ".jpeg", ".webp", ".avif"):
                candidate = Path(YEDEK_IMG_DIR) / category / (stem + ext)
                if candidate.is_file() and not candidate.is_symlink():
                    source = candidate
                    break
            if source is None:
                raise FileNotFoundError("IMMUTABLE_SOURCE_NOT_FOUND")
            image = imread_unicode(source)
            if image is None:
                raise ValueError("ORIGINAL_IMAGE_UNREADABLE")
            config = new_data["kategoriler"][category]["sablonlar"][template]
            whitened = whiten_canvas(
                image, config,
                is_frameless=category in ("01_Wifi_Kutusu", "04_Cam_Dograma", "05_Ocak_Arkasi"),
            )
            preview = save_preview_only(BASE_DIR, category, template, whitened)
            logger.info("PREVIEW_ONLY CREATED: %s", preview)
            self.send_response(200)
            self.send_header("Content-type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({
                "success": True, "preview_only": True, "source_unchanged": True,
                "preview_name": preview.name,
            }).encode("utf-8"))
        except Exception as error:
            logger.error("P0 PREVIEW FAILED: %s", error)
            self.send_response(409 if isinstance(error, (WorkingRevisionBlocked, FileNotFoundError)) else 500)
            self.send_header("Content-type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"success": False, "error": str(error)}).encode("utf-8"))

    def _handle_api_orijinal_yukle(self):
        """Explicitly restore a WORKING copy from an immutable original.

        Original/archive inputs remain unmodified, including transparent PNG.
        """
        from SABLON_V2_MIMARI.core.safe_working_revision import (
            working_png_revision, WorkingRevisionBlocked,
        )
        from SABLON_V2_MIMARI.core.template_identity import CATEGORY_PREFIXES
        try:
            category = self.headers.get("X-Active-Category", "")
            template = self.headers.get("X-Active-Template", "")
            if category not in CATEGORY_PREFIXES or not template or Path(template).name != template:
                raise ValueError("INVALID_RESTORE_IDENTITY")
            stem = Path(template).stem
            backup_folder = Path(YEDEK_IMG_DIR) / category
            if backup_folder.is_symlink():
                raise WorkingRevisionBlocked("ORIGINAL_FOLDER_SYMLINK_BLOCKED")
            src = None
            for ext in (".png", ".jpg", ".jpeg", ".webp", ".avif"):
                candidate = backup_folder / (stem + ext)
                if candidate.is_file() and not candidate.is_symlink():
                    src = candidate
                    break
            if src is None:
                raise FileNotFoundError("Orijinal yedek bulunamadi")
            image = cv2.imdecode(np.fromfile(str(src), dtype=np.uint8), cv2.IMREAD_UNCHANGED)
            if image is None:
                raise ValueError("ORIGINAL_IMAGE_UNREADABLE")
            with working_png_revision(BASE_DIR, category, template, image):
                pass
            logger.info("P0 WORKING RESTORED from immutable original: %s", template)
            self.send_response(200)
            self.send_header("Content-type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(b'{"success": true, "working_restored": true, "original_unchanged": true}')
        except Exception as error:
            logger.error("P0 ORIGINAL RESTORE BLOCKED: %s", error)
            self.send_response(409 if isinstance(error, (WorkingRevisionBlocked, FileNotFoundError, FileExistsError)) else 500)
            self.send_header("Content-type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"success": False, "error": str(error)}).encode("utf-8"))

    def _handle_api_tumunu_beyazlat(self):
        """Explicit bulk working-only revision; no overwrite or silent success."""
        from SABLON_V2_MIMARI.core.safe_working_revision import (
            working_png_revision, WorkingRevisionBlocked,
        )
        from SABLON_V2_MIMARI.core.template_identity import CATEGORY_PREFIXES
        try:
            request = json.loads(self.rfile.read(int(self.headers["Content-Length"])).decode("utf-8"))
            requested_category = request.get("kategori")
            if requested_category and requested_category not in CATEGORY_PREFIXES:
                raise ValueError("INVALID_TEMPLATE_CATEGORY")
            with open(AYARLAR_PATH, "r", encoding="utf-8") as stream:
                settings = json.load(stream)
            sm_dir = os.path.join(BASE_DIR, "99_SISTEM_MOTORLARI_VE_KODLAR", "SISTEM_MOTORU")
            if sm_dir not in sys.path:
                sys.path.append(sm_dir)
            from sablon_beyazlatma_motoru import whiten_canvas, imread_unicode
            categories = [requested_category] if requested_category else [
                c for c in settings.get("kategoriler", {}) if c in CATEGORY_PREFIXES
            ]
            processed = 0
            failed = []
            for category in categories:
                for template, conf in settings.get("kategoriler", {}).get(category, {}).get("sablonlar", {}).items():
                    try:
                        backup = Path(YEDEK_IMG_DIR) / category
                        if backup.is_symlink() or Path(template).name != template:
                            raise WorkingRevisionBlocked("INVALID_ORIGINAL_PATH")
                        source = next((
                            backup / (Path(template).stem + ext)
                            for ext in (".png", ".jpg", ".jpeg", ".webp", ".avif")
                            if (backup / (Path(template).stem + ext)).is_file()
                            and not (backup / (Path(template).stem + ext)).is_symlink()
                        ), None)
                        if source is None:
                            raise FileNotFoundError("ORIGINAL_NOT_FOUND")
                        raw = imread_unicode(source)
                        if raw is None:
                            raise ValueError("UNREADABLE_ORIGINAL")
                        whitened = whiten_canvas(
                            raw, conf,
                            is_frameless=category in ("01_Wifi_Kutusu", "04_Cam_Dograma", "05_Ocak_Arkasi"),
                        )
                        with working_png_revision(BASE_DIR, category, template, whitened):
                            pass
                        processed += 1
                    except Exception as template_error:
                        failed.append({"category": category, "template": template, "error": str(template_error)})
                        logger.error("P0 BULK WORKING REVISION FAILED %s/%s: %s", category, template, template_error)
            # Partial success is NOT reported as success. Each successful item
            # has its own immutable snapshot and can be audited individually.
            success = not failed
            self.send_response(200 if success else 409)
            self.send_header("Content-type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({
                "success": success, "islenen": processed,
                "failed_count": len(failed), "failed": failed[:100],
                "requires_review": True,
            }).encode("utf-8"))
        except Exception as error:
            logger.error("P0 BULK REVISION BLOCKED: %s", error)
            self.send_response(500)
            self.send_header("Content-type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"success": False, "error": str(error)}).encode("utf-8"))

    def _handle_api_sablon_sil(self):
        try:
            active_cat = self.headers.get('X-Active-Category', '')
            active_tmpl = self.headers.get('X-Active-Template', '')
            if not active_cat or not active_tmpl:
                raise ValueError("Kategori veya sablon eksik")
            stem = Path(active_tmpl).stem
            # ayarlar.json'dan kaldir
            with AYARLAR_LOCK:
                with acquire_os_lock(AYARLAR_PATH):
                    with open(AYARLAR_PATH, 'r', encoding='utf-8') as _f:
                        _ayarlar = json.load(_f)
                    if active_cat not in _ayarlar['kategoriler'] or active_tmpl not in _ayarlar['kategoriler'][active_cat]['sablonlar']:
                        raise ValueError("Sablon JSON'da bulunamadi")
                    removed_conf = _ayarlar['kategoriler'][active_cat]['sablonlar'].pop(active_tmpl)
                    tmp_path = AYARLAR_PATH + ".tmp"
                    with open(tmp_path, 'w', encoding='utf-8') as _f:
                        json.dump(_ayarlar, _f, indent=2, ensure_ascii=False)
                    os.replace(tmp_path, AYARLAR_PATH)
                    
                    root_copy = os.path.join(BASE_DIR, "ayarlar.json")
                    shutil.copy2(AYARLAR_PATH, root_copy)
            # Havuzdaki PNG'yi cop klasorune tas
            png_src = os.path.join(BASE_DIR, "2_SABLON_HAVUZU", active_cat, stem + ".png")
            cop_dir = os.path.join(BASE_DIR, "_COP_KUTUSU")
            os.makedirs(cop_dir, exist_ok=True)
            ts_del = time.strftime("%Y%m%d_%H%M%S")
            cop_dest = os.path.join(cop_dir, f"{active_cat}__{stem}__{ts_del}.png")
            if os.path.exists(png_src):
                shutil.move(png_src, cop_dest)
            # Geri almak icin metadata kaydet
            cop_meta = cop_dest + ".meta.json"
            with open(cop_meta, 'w', encoding='utf-8') as _f:
                json.dump({
                    "kategori": active_cat,
                    "sablon": active_tmpl,
                    "stem": stem,
                    "conf": removed_conf,
                    "cop_png": cop_dest
                }, _f, ensure_ascii=False)
            self.send_response(200)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({'success': True}).encode('utf-8'))
            logger.info(f"SABLON SILINDI: {active_cat}/{active_tmpl}")
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode('utf-8'))
            logger.error(f"SABLON SIL HATASI: {e}")

    def _handle_api_sablon_sil_geri_al(self):
        try:
            cop_dir = os.path.join(BASE_DIR, "_COP_KUTUSU")
            # En son silinen meta dosyasini bul
            metas = sorted(glob.glob(os.path.join(cop_dir, "*.meta.json")), reverse=True)
            if not metas:
                raise ValueError("Cop kutusunda geri alinacak sablon yok")
            meta_path = metas[0]
            with open(meta_path, 'r', encoding='utf-8') as _f:
                meta = json.load(_f)
            # PNG'yi geri tasi
            cop_png = meta['cop_png']
            restore_dir = os.path.join(BASE_DIR, "2_SABLON_HAVUZU", meta['kategori'])
            restore_path = os.path.join(restore_dir, meta['stem'] + ".png")
            # The trash can contain untrusted/stale metadata. Validate its
            # source and destination; NEVER replace an existing working name.
            from SABLON_V2_MIMARI.core.template_identity import CATEGORY_PREFIXES, same_stem_files
            if meta["kategori"] not in CATEGORY_PREFIXES or Path(meta["stem"]).name != meta["stem"]:
                raise ValueError("INVALID_TRASH_RESTORE_IDENTITY")
            trash_root = Path(cop_dir).resolve()
            source = Path(cop_png)
            destination = Path(restore_path)
            if source.is_symlink() or not source.is_file() or not source.resolve().is_relative_to(trash_root):
                raise FileNotFoundError("TRASH_ORIGINAL_NOT_AVAILABLE_OR_UNSAFE")
            if destination.parent.is_symlink() or destination.exists() or same_stem_files(destination.parent, destination.name):
                raise FileExistsError("RESTORE_TARGET_ALREADY_EXISTS_NO_OVERWRITE")
            # Atomic create-only; retain the trash source until settings
            # metadata is durably committed, so failure cannot lose content.
            os.link(str(source), str(destination))
            # ayarlar.json'a geri ekle
            with AYARLAR_LOCK:
                with acquire_os_lock(AYARLAR_PATH):
                    with open(AYARLAR_PATH, 'r', encoding='utf-8') as _f:
                        _ayarlar = json.load(_f)
                        
                    _cat = meta['kategori']
                    _tmpl = meta['sablon']
                    if 'kategoriler' not in _ayarlar:
                        _ayarlar['kategoriler'] = {}
                    if _cat not in _ayarlar['kategoriler']:
                        _ayarlar['kategoriler'][_cat] = {'sablonlar': {}}
                    if 'sablonlar' not in _ayarlar['kategoriler'][_cat]:
                        _ayarlar['kategoriler'][_cat]['sablonlar'] = {}
                        
                    _ayarlar['kategoriler'][_cat]['sablonlar'][_tmpl] = meta['conf']
                    
                    tmp_path = AYARLAR_PATH + ".tmp"
                    with open(tmp_path, 'w', encoding='utf-8') as _f:
                        json.dump(_ayarlar, _f, indent=2, ensure_ascii=False)
                    os.replace(tmp_path, AYARLAR_PATH)
                    
                    root_copy = os.path.join(BASE_DIR, "ayarlar.json")
                    shutil.copy2(AYARLAR_PATH, root_copy)
            # Meta dosyasini sil
            os.remove(meta_path)
            self.send_response(200)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({'success': True, 'restored_tmpl': meta['sablon']}).encode('utf-8'))
            logger.info(f"SABLON GERI ALINDI: {meta['kategori']}/{meta['sablon']}")
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode('utf-8'))
            logger.error(f"GERI AL HATASI: {e}")

    def _handle_api_auto_detect_corners(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        try:
            req = json.loads(post_data.decode('utf-8'))
            cat = req.get('kategori')
            tmpl = req.get('sablon')
            # Gorsel yolunu bul (tum uzantilar)
            img_path = None
            stem = Path(tmpl).stem
            for _ext in ['.jpg', '.jpeg', '.webp', '.png', '.avif']:
                _cand = os.path.join(YEDEK_IMG_DIR, cat, stem + _ext)
                if os.path.exists(_cand):
                    img_path = _cand
                    break
            if not img_path:
                # Havuzda ara
                for _ext in ['.png', '.jpg', '.jpeg', '.webp']:
                    _cand = os.path.join(BASE_DIR, "2_SABLON_HAVUZU", cat, stem + _ext)
                    if os.path.exists(_cand):
                        img_path = _cand
                        break
            if not img_path:
                raise FileNotFoundError(f"Gorsel bulunamadi: {cat}/{tmpl}")
            img_cv = cv2.imdecode(np.fromfile(img_path, dtype=np.uint8), cv2.IMREAD_COLOR)
            if img_cv is None:
                raise ValueError(f"Gorsel okunamadi: {img_path}")
            corners = detect_document_corners(img_cv)
            if corners is None:
                self.send_response(200)
                self.send_header('Content-type', 'application/json; charset=utf-8')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'success': False,
                    'error': '4 koselik bir baski alani bulunamadi. Lutfen elle ayarlayin.'
                }).encode('utf-8'))
                logger.warning(f"KOSE ALGILAMA BASARISIZ: {cat}/{tmpl}")
                return
            self.send_response(200)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({
                'success': True,
                'corners': corners
            }).encode('utf-8'))
            logger.info(f"KOSE ALGILAMA BASARILI: {cat}/{tmpl} -> {corners}")
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode('utf-8'))
            logger.error(f"KOSE ALGILAMA HATASI: {e}")
    def do_OPTIONS(self):
        """CORS preflight handler"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-Active-Category, X-Active-Template')
        self.end_headers()

