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

# ======================== LOGGING SETUP ========================
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
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
# DINAMIK YOL: Sistemin baska bilgisayarlarda/klasorlerde cokmemesi icin dinamiklestirildi
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AYARLAR_PATH = os.path.join(BASE_DIR, "99_SISTEM_MOTORLARI_VE_KODLAR", "SISTEM_MOTORU", "ayarlar.json")
YEDEK_IMG_DIR = os.path.join(BASE_DIR, "2_SABLON_HAVUZU_ORIJINAL_YEDEK")

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
                x1, y1, x2, y2 = line[0]
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

HTML_CONTENT = """<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' rx='4' fill='%23007acc'/><text x='16' y='23' text-anchor='middle' font-size='20' fill='white'>S</text></svg>">
    <title>Şablon Hizalama Ekranı (Zoom ve Pan)</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #1e1e1e; color: #fff; margin: 0; display: flex; height: 100vh; overflow: hidden; }
        #sidebar { width: 350px; flex-shrink: 0; box-sizing: border-box; background: #2d2d30; padding: 15px; overflow-y: auto; display: flex; flex-direction: column; z-index: 10; border-right: 1px solid #444; }
        .resizer { width: 5px; background: #333; cursor: col-resize; z-index: 100; transition: background 0.2s; flex-shrink: 0; border-left: 1px solid #222; border-right: 1px solid #222; }
        .resizer:hover, .resizer.active { background: #007acc; }
        #main { flex: 1; display: flex; flex-direction: column; position: relative; min-width: 300px; }
        #toolbar { min-height: 60px; height: auto; background: #3e3e42; display: flex; flex-direction: column; padding: 10px 20px; gap: 10px; z-index: 10; justify-content: center; }
        #canvas-container { flex: 1; overflow: hidden; position: relative; background: #111 url('data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAAMUlEQVQ4T2NkYGAQYcAP3uCTZhw1gGGYhAGBZIA/ENFMo/5BAv4wMBw1gGGYhAGBCgIAVqU12f71J0EAAAAASUVORK5CYII=') repeat; }
        canvas { position: absolute; top: 0; left: 0; cursor: crosshair; }        
        .category { margin-bottom: 10px; }
        .category-title { font-weight: bold; cursor: pointer; padding: 8px; background: #444; border-radius: 4px; user-select: none; }
        .category-title:hover { background: #555; }
        .template-list { margin-left: 10px; display: none; }
        .template-item { padding: 6px; cursor: pointer; font-size: 14px; border-bottom: 1px solid #333; }
        .template-item:hover { background: #007acc; }
        .template-item.active { background: #007acc; font-weight: bold; }
        
        button { background: #007acc; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; font-size: 14px; font-weight: bold; }
        button:hover { background: #005f9e; }
        button.success { background: #28a745; }
        button.success:hover { background: #218838; }
        
        #info { background: rgba(0,0,0,0.7); position: absolute; bottom: 20px; left: 20px; padding: 10px; border-radius: 4px; pointer-events: none; z-index: 10;}
        #help-sidebar { margin-top: 20px; padding-top: 15px; border-top: 1px solid #555; font-size: 13px; color: #ccc; line-height: 1.5; }
    </style>
</head>
<body>

<div id="sidebar">
    <h2 style="margin-top:0;">Şablonlar</h2>
    <div id="categories" style="flex:1; overflow-y:auto;">Yükleniyor...</div>
    <div id="help-sidebar" style="display:none; position: absolute; left: 360px; top: 60px; background: rgba(0,0,0,0.9); padding: 15px; border-radius: 8px; z-index: 9999; border: 1px solid #555; box-shadow: 0 4px 15px rgba(0,0,0,0.5);">
        <b style="color:#fff;">Kısayollar ve Kontroller:</b><br/>
        - <b>🔴 4 Köşe:</b> Baskı köşelerini fare ile sürükleyin.<br/>
        - <b>🪄 Otomatik Nesne:</b> Şablondaki taşan nesneleri otomatik bulur.<br/>
        - <b>C / V Tuşları:</b> Köşeleri kopyala ve diğer şablona yapıştır.<br/>
        - <b>Enter Tuşu:</b> O anki şablon için otomatik köşe algılamayı tetikler.<br/>
        - <b>Boşluk (Space):</b> Basılı tutarak ekranda kaydırma (Pan) yapın.<br/>
        - <b>↶ Geri Al:</b> <b>Ctrl+Z</b> (Maske hatalarını geri alır)<br/>
        - <b>Tekerlek:</b> Yakınlaş / Uzaklaş (Zoom)<br/>
        - <b>Sağ Tık Sürükle:</b> Ekranda Gezin (Pan)
    </div>
    <div style="padding-top: 10px; border-top: 1px solid #555;">
        <button onclick="const h = document.getElementById('help-sidebar'); h.style.display = h.style.display === 'none' ? 'block' : 'none';" style="width: 100%; background: #444;">❓ Kısayollar ve Yardım</button>
    </div>
</div>
<div class="resizer" id="resizer-left"></div>

<div id="main">
    <div id="toolbar" style="flex-direction: row; justify-content: space-between; align-items: center;">
        <div style="display:flex; align-items:center; gap:8px;">
            <button type="button" onclick="prevTemplate()" style="background:#444; padding:6px 14px;" title="Önceki Şablon (P / Sol Ok)">⏮ Önceki</button>
            <button type="button" onclick="nextTemplate()" style="background:#444; padding:6px 14px;" title="Sonraki Şablon (N / Sağ Ok)">Sonraki ⏭</button>
            <span id="tmpl-counter" style="font-size: 13px; font-weight:bold; color: #00e5ff; margin-left: 5px;"></span>
            <span id="current-file" style="font-size: 17px; font-weight: bold; margin-left: 10px;">Görsel Seçin</span>
            <span id="template-type" style="margin-left: 10px; color: #aaa;"></span>
        </div>
        <div style="display:flex; align-items:center; gap:6px;">
            <button onclick="toggleType()" style="background: #6f42c1;" title="Düz dikdörtgen ile Serbest Perspektif modu arasında geçiş yapar">🔄 Düz / Perspektif Modu</button>
            <button onclick="saveAll()" class="success" style="padding: 10px 30px; font-size: 16px;">TÜMÜNÜ KAYDET</button>
        </div>
    </div>
    
    <div style="flex: 1; display: flex; overflow: hidden; position: relative;">
        <!-- Canvas Area -->
        <div id="canvas-container">
            <canvas id="c"></canvas>
            <div id="info">Sürükleyip köşeleri ayarlayın.</div>
        </div>
        
        <div class="resizer" id="resizer-right"></div>
        <!-- Vertical Toolbar on the Right -->
        <div id="right-toolbar" style="width: 220px; flex-shrink: 0; box-sizing: border-box; background: #252526; display: flex; flex-direction: column; gap: 10px; padding: 15px; border-left: 1px solid #444; overflow-y: auto; z-index: 10;">
            <h3 style="margin: 0 0 5px 0; font-size: 15px; color: #fff; text-align: center; border-bottom: 1px solid #444; padding-bottom: 10px;">Photoshop Araçları</h3>
            
            <button type="button" id="btnCorner" onclick="setEditorTool('corner')" style="outline: 3px solid #00aaff; width: 100%; text-align: left; padding: 12px 10px;" aria-label="4 Kose Modu">🔴 4 Köşe</button>
            <button type="button" id="btnAutoCorner" onclick="autoDetectCorners()" style="background: linear-gradient(135deg, #00c853, #00bfa5); box-shadow: 0 2px 6px rgba(0,200,83,0.4); width: 100%; text-align: left; padding: 12px 10px; font-weight: bold;" title="Görseldeki baskı alanının 4 köşesini otomatik olarak tespit eder (SIFT/ORB + Contour). Elle ayar gerekmez!" aria-label="Otomatik Kose Algila">🟢 Otomatik Köşe Algıla</button>
            
            <div style="height: 1px; background: #444; margin: 15px 0;"></div>

            
            <h3 style="margin: 0 0 5px 0; font-size: 15px; color: #fff; text-align: center; border-bottom: 1px solid #444; padding-bottom: 10px;">Görsel İşlemleri</h3>
            <button type="button" onclick="toggleCanvasBg()" style="background: #e67e22; width: 100%; padding: 12px 10px; font-weight: bold; margin-bottom: 5px; color: white; border: none; cursor: pointer; border-radius: 4px;" title="Arka plan rengini değiştirir (Siyah/Beyaz/Yeşil)">🎨 Arka Planı Değiştir</button>
            <button type="button" onclick="instantWhiten()" style="background: #28a745; width: 100%; padding: 12px 10px; font-weight: bold;" title="Seçtiğiniz alanları anında beyazlatarak sonucu önizleyin">✨ Anında Beyazlat (Önizle)</button>
            <button type="button" id="btnToggleOriginal" onclick="toggleOriginalView()" style="background: #9c27b0; width: 100%; padding: 12px 10px; margin-top: 5px; font-weight: bold; border-radius: 4px; border: none; color: white; cursor: pointer;" title="Önizleme ile orijinal görsel arasında geçiş yapar">👁️ Orijinal / Önizleme</button>
            <button type="button" onclick="restoreOriginal()" style="background: #6c757d; width: 100%; padding: 12px 10px; margin-top: 5px;" title="Görseli orijinal ve temiz haline geri döndür">🔄 Orijinale Dön (Temizle)</button>
            
            <div style="height: 1px; background: #444; margin: 15px 0;"></div>
            <button type="button" onclick="deleteTemplate()" style="background: #dc3545; width: 100%; padding: 12px 10px; margin-top: 5px;" title="Bu şablonu çöpe at (geri alınabilir)">🗑️ Şablonu Çöpe At</button>
            <button type="button" onclick="undoDelete()" style="background: #17a2b8; width: 100%; padding: 12px 10px; margin-top: 5px;" title="Son silinen şablonu geri al">♻️ Son Silineni Geri Al</button>
        </div>
    </div>
</div>

<script>
    window.onerror = function(msg, url, line, col, error) {
        alert("JS ERROR: " + msg + "\\nLine: " + line);
        return false;
    };
    
    // SISTEM SAĞLIK KONTROLÜ
    fetch('/api/saglik_durumu')
        .then(res => res.json())
        .then(data => {
            if(data.sorun_sayisi > 0 || data.cozulen_sayisi > 0) {
                let banner = document.createElement("div");
                banner.style.padding = "10px";
                banner.style.textAlign = "center";
                banner.style.fontWeight = "bold";
                banner.style.zIndex = "10000";
                banner.style.position = "relative";
                
                if(data.sorun_sayisi > 0) {
                    banner.style.backgroundColor = "#ff4444";
                    banner.style.color = "white";
                    banner.innerHTML = "⚠️ DİKKAT: " + data.sorun_sayisi + " ADET SİSTEM SORUNU TESPİT EDİLDİ! LÜTFEN LOGLARI KONTROL EDİN.";
                } else {
                    banner.style.backgroundColor = "#44ff44";
                    banner.style.color = "black";
                    banner.innerHTML = "✅ SİSTEM " + data.cozulen_sayisi + " ADET SORUNU OTOMATİK OLARAK ÇÖZDÜ!";
                }
                
                let details = document.createElement("button");
                details.innerText = "Detaylar";
                details.style.marginLeft = "15px";
                details.onclick = () => alert("ÇÖZÜLENLER:\n" + data.cozulenler.join("\n") + "\n\nSORUNLAR:\n" + data.sorunlar.join("\n"));
                banner.appendChild(details);
                
                document.body.insertBefore(banner, document.body.firstChild);
            }
        }).catch(err => console.log("Sağlık kontrolü alınamadı", err));
</script>
<script>
    let ayarlar = null;
    let currentCat = null;
    let currentTmpl = null;
    let currentImg = null;
    
    // Zoom & Pan vars
    let baseScale = 1;
    let userZoom = 1.65; // User requested 165% zoom by default
    let offsetX = 0;
    let offsetY = 0;
    
    let pts = []; 
    let clipboardPts = null; // For copy/paste
    let draggingPoint = -1;
    let isPanning = false;
    let isSpacePressed = false;
    let panStartX = 0;
    let panStartY = 0;

    // =========================================================
    // FOREGROUND MASK EDITOR (Photoshop Object Selection & Brush)
    // =========================================================
    let editorTool = 'corner';

    let foregroundMask = {
        object_boxes: [],
        add_brush: [],
        subtract_brush: [],
        feather: 1.2,
        grabcut_iterations: 5
    };

    let maskDragStart = null;
    let maskDragCurrent = null;

    let brushRadius = 20;
    let brushDrawing = false;
    let lastBrushPoint = null;
    let hoverBrushPoint = null;

    let maskHistory = [];

    const canvas = document.getElementById('c');
    const ctx = canvas.getContext('2d');
    const cont = document.getElementById('canvas-container');
    
    let bgMode = 0; // 0: dark, 1: white, 2: green
    const bgColors = [
        "#111 url('data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAAMUlEQVQ4T2NkYGAQYcAP3uCTZhw1gGGYhAGBZIA/ENFMo/5BAv4wMBw1gGGYhAGBCgIAVqU12f71J0EAAAAASUVORK5CYII=') repeat",
        "#ffffff",
        "#39ff14"
    ];

    function toggleCanvasBg() {
        bgMode = (bgMode + 1) % bgColors.length;
        document.getElementById('canvas-container').style.background = bgColors[bgMode];
    }
    
    let originalImgObj = null; // Ham orjinal gorseli hafizada tutar
    let isShowingOriginal = false; // Kullanici butona basili tutuyor mu
    let previewModeActive = false; // Aninda beyazlatma devrede mi
    
    let allTemplates = [];

    // Load config
    fetch('/api/ayarlar')
        .then(r => {
            if (!r.ok) throw new Error('HTTP error ' + r.status);
            return r.json();
        })
        .then(data => {
            ayarlar = data;
            renderSidebar();
        })
        .catch(err => alert("FETCH ERROR: " + err.message));
    
    function renderSidebar() {
        const catDiv = document.getElementById('categories');
        catDiv.innerHTML = '';
        allTemplates = [];
        for (const cat in ayarlar.kategoriler) {
            const div = document.createElement('div');
            div.className = 'category';
            const title = document.createElement('div');
            title.className = 'category-title';
            title.textContent = cat;
            const list = document.createElement('div');
            list.className = 'template-list';
            if (cat === currentCat) {
                list.style.display = 'block';
            }
            title.onclick = () => { list.style.display = list.style.display === 'block' ? 'none' : 'block'; };
            div.appendChild(title);
            for (const tmpl in ayarlar.kategoriler[cat].sablonlar) {
                const itemData = ayarlar.kategoriler[cat].sablonlar[tmpl];
                const item = document.createElement('div');
                item.className = 'template-item';
                
                const hasCorners = itemData.koseler && itemData.koseler.length === 4;
                if (itemData.supheli) {
                    item.innerHTML = '⚠️ ' + tmpl;
                    item.style.backgroundColor = 'rgba(220, 53, 69, 0.2)';
                    item.style.color = '#ff9999';
                    item.title = "Otomatik tespit güven puanı düşük! Lütfen köşeleri kontrol edin.";
                } else {
                    item.textContent = (hasCorners ? '✅ ' : '⏳ ') + tmpl;
                }
                
                item.onclick = () => loadTemplate(cat, tmpl, item);
                list.appendChild(item);
                allTemplates.push({cat, tmpl, elem: item, list});
            }
            div.appendChild(list);
            catDiv.appendChild(div);
        }
    }

    function nextTemplate() {
        if (allTemplates.length === 0) return;
        saveAll(true); // Auto-save on navigation
        let idx = allTemplates.findIndex(t => t.cat === currentCat && t.tmpl === currentTmpl);
        if (idx === -1 || idx === allTemplates.length - 1) idx = 0;
        else idx++;
        const target = allTemplates[idx];
        if (target.list) target.list.style.display = 'block';
        loadTemplate(target.cat, target.tmpl, target.elem);
    }

    function prevTemplate() {
        if (allTemplates.length === 0) return;
        saveAll(true); // Auto-save on navigation
        let idx = allTemplates.findIndex(t => t.cat === currentCat && t.tmpl === currentTmpl);
        if (idx <= 0) idx = allTemplates.length - 1;
        else idx--;
        const target = allTemplates[idx];
        if (target.list) target.list.style.display = 'block';
        loadTemplate(target.cat, target.tmpl, target.elem);
    }

    function updateCounter() {
        let idx = allTemplates.findIndex(t => t.cat === currentCat && t.tmpl === currentTmpl);
        const el = document.getElementById('tmpl-counter');
        if (el) {
            el.textContent = idx !== -1 ? `[${idx + 1} / ${allTemplates.length}]` : '';
        }
    }
    
    function loadTemplate(cat, tmpl, elem) {
        document.querySelectorAll('.template-item').forEach(el => el.classList.remove('active'));
        if(elem) elem.classList.add('active');
        
        currentCat = cat;
        currentTmpl = tmpl;
        const data = ayarlar.kategoriler[cat].sablonlar[tmpl];
        
        // KULLANICI TALEBI: Varsayilan olarak her zaman perspektif ile acilsin
        if (data.tip !== 'perspektif') {
            data.tip = 'perspektif';
            if (!data.koseler && data.w && data.h) {
                data.koseler = [
                    [data.x, data.y],
                    [data.x + data.w, data.y],
                    [data.x + data.w, data.y + data.h],
                    [data.x, data.y + data.h]
                ];
            }
        }
        
        document.getElementById('current-file').textContent = cat + ' / ' + tmpl;
        document.getElementById('template-type').textContent = 'Tip: ' + data.tip;
        updateCounter();
        
        resetView();

        // Ön plan maske verilerini yükle (Object selection & brush formatı)
        if (data.on_plan && typeof data.on_plan === 'object' && !Array.isArray(data.on_plan)) {
            foregroundMask = JSON.parse(JSON.stringify(data.on_plan));
            if (!foregroundMask.object_boxes) foregroundMask.object_boxes = [];
            if (!foregroundMask.add_brush) foregroundMask.add_brush = [];
            if (!foregroundMask.subtract_brush) foregroundMask.subtract_brush = [];
            if (foregroundMask.feather === undefined) foregroundMask.feather = 1.2;
            if (foregroundMask.grabcut_iterations === undefined) foregroundMask.grabcut_iterations = 5;
        } else {
            foregroundMask = {
                object_boxes: [],
                add_brush: [],
                subtract_brush: [],
                feather: 1.2,
                grabcut_iterations: 5
            };
        }
        maskHistory = [];
        setEditorTool('corner');
        
        const img = new Image();
        img.onload = () => {
            currentImg = img;
            originalImgObj = img;
            previewModeActive = false;
            initPoints(data);
            draw();
        };
        img.onerror = () => {
            alert('HATA: "' + tmpl + '" görseli diskinizde (2_SABLON_HAVUZU veya YEDEK klasöründe) bulunamadı! Lütfen dosyanın klasörde gerçekten var olduğundan emin olun.');
            currentImg = null;
            draw();
        };
        img.src = '/image/' + encodeURIComponent(cat) + '/' + encodeURIComponent(tmpl);
    }
    
    function resetView() {
        userZoom = 1.65;
        offsetX = 0;
        offsetY = 0;
    }
    
    function initPoints(data) {
        pts = [];
        if (data.tip === 'perspektif' && data.koseler) {
            pts = data.koseler.map(p => ({x: p[0], y: p[1]}));
        } else {
            let x = data.x || 0;
            let y = data.y || 0;
            let w = data.w || 100;
            let h = data.h || 100;
            pts = [
                {x: x, y: y}, {x: x+w, y: y},
                {x: x+w, y: y+h}, {x: x, y: y+h}
            ];
        }
    }
    
    function toggleType() {
        if(!currentCat) return;
        const data = ayarlar.kategoriler[currentCat].sablonlar[currentTmpl];
        if(data.tip === 'perspektif') {
            data.tip = 'duz';
            let minX = Math.min(...pts.map(p=>p.x)), maxX = Math.max(...pts.map(p=>p.x));
            let minY = Math.min(...pts.map(p=>p.y)), maxY = Math.max(...pts.map(p=>p.y));
            data.x = Math.round(minX); data.y = Math.round(minY);
            data.w = Math.round(maxX - minX); data.h = Math.round(maxY - minY);
            delete data.koseler;
        } else {
            data.tip = 'perspektif';
            data.koseler = pts.map(p => [Math.round(p.x), Math.round(p.y)]);
            delete data.x; delete data.y; delete data.w; delete data.h;
        }
        document.getElementById('template-type').textContent = 'Tip: ' + data.tip;
        initPoints(data);
        draw();
    }
    
    function updateDataFromPoints() {
        if (!currentCat || !currentTmpl) return;
        const data = ayarlar.kategoriler[currentCat].sablonlar[currentTmpl];
        if (pts.length === 4) {
            data.koseler = pts.map(p => [Math.round(p.x), Math.round(p.y)]);
            
            // Update sidebar icon
            const currentItem = allTemplates.find(t => t.cat === currentCat && t.tmpl === currentTmpl);
            if (currentItem && currentItem.elem) {
                currentItem.elem.textContent = '✅ ' + currentTmpl;
            }
        }
        if (data.supheli) {
            delete data.supheli;
        }
        if (data.tip === 'perspektif') {
            data.koseler = pts.map(p => [Math.round(p.x), Math.round(p.y)]);
        } else {
            let minX = Math.min(...pts.map(p=>p.x)), maxX = Math.max(...pts.map(p=>p.x));
            let minY = Math.min(...pts.map(p=>p.y)), maxY = Math.max(...pts.map(p=>p.y));
            data.x = Math.round(minX); data.y = Math.round(minY);
            data.w = Math.round(maxX - minX); data.h = Math.round(maxY - minY);
            initPoints(data);
        }
    }

    // =========================================================
    // FOREGROUND MASK İŞLEMLERİ
    // =========================================================

    function cloneForegroundMask() {
        return JSON.parse(JSON.stringify(foregroundMask));
    }

    function pushMaskHistory() {
        maskHistory.push(cloneForegroundMask());
        if (maskHistory.length > 50) maskHistory.shift();
    }

    function undoMaskAction() {
        if (maskHistory.length === 0) return;
        foregroundMask = maskHistory.pop();
        saveCurrentTemplateData();
        draw();
    }

    function clearForegroundMask() {
        if (confirm("Bu şablon için tüm nesne seçimlerini ve fırça maskelerini temizlemek istiyor musunuz?")) {
            pushMaskHistory();
            foregroundMask = {
                object_boxes: [],
                add_brush: [],
                subtract_brush: [],
                feather: 1.2,
                grabcut_iterations: 5
            };
            saveCurrentTemplateData();
            draw();
        }
    }

    function setEditorTool(tool) {
        editorTool = tool;
        maskDragStart = null;
        maskDragCurrent = null;
        brushDrawing = false;
        draggingPoint = -1;

        const ids = {
            corner: 'btnCorner',
            object: 'btnObject',
            add: 'btnAdd',
            subtract: 'btnSubtract'
        };

        for (const key in ids) {
            const el = document.getElementById(ids[key]);
            if (!el) continue;
            if (key === tool) {
                el.style.outline = '3px solid #00aaff';
            } else {
                el.style.outline = '';
            }
        }

        updateCursor();
        draw();
    }

    function updateCursor() {
        if (!canvas) return;
        if (isPanning) {
            canvas.style.cursor = 'grabbing';
        } else if (editorTool === 'object') {
            canvas.style.cursor = 'crosshair';
        } else if (editorTool === 'add' || editorTool === 'subtract') {
            canvas.style.cursor = 'none';
        } else {
            canvas.style.cursor = 'default';
        }
    }

    function updateBrushSize(value) {
        brushRadius = parseInt(value);
        const el = document.getElementById('maskBrushValue');
        if (el) el.textContent = brushRadius;
        const slider = document.getElementById('maskBrushSize');
        if (slider) slider.value = brushRadius;
        draw();
    }

    function saveCurrentTemplateData() {
        if (currentCat && currentTmpl && ayarlar && ayarlar.kategoriler[currentCat]) {
            const tmplObj = ayarlar.kategoriler[currentCat].sablonlar[currentTmpl];
            tmplObj.on_plan = cloneForegroundMask();
        }
    }

    // Tam koordinat dönüştürme - sınır kontrolü YOK (köşe noktası dışarıda olabilir)
    function eventToRawImagePoint(e) {
        if (!currentImg) return null;
        const finalScale = baseScale * userZoom;
        const imgDrawW = currentImg.width * finalScale;
        const imgDrawH = currentImg.height * finalScale;
        const startX = (canvas.width - imgDrawW) / 2 + offsetX;
        const startY = (canvas.height - imgDrawH) / 2 + offsetY;
        const rect = canvas.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;
        return {
            x: (mouseX - startX) / finalScale,
            y: (mouseY - startY) / finalScale
        };
    }

    // Standart koordinat - sınır kontrolü VAR (nesne seçme, fırça için)
    function eventToImagePoint(e) {
        if (!currentImg) return null;
        const finalScale = baseScale * userZoom;
        const imgDrawW = currentImg.width * finalScale;
        const imgDrawH = currentImg.height * finalScale;
        const startX = (canvas.width - imgDrawW) / 2 + offsetX;
        const startY = (canvas.height - imgDrawH) / 2 + offsetY;

        const rect = canvas.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;

        const imgX = (mouseX - startX) / finalScale;
        const imgY = (mouseY - startY) / finalScale;

        if (imgX < 0 || imgY < 0 || imgX >= currentImg.width || imgY >= currentImg.height) {
            return null;
        }

        return {
            x: Math.round(imgX),
            y: Math.round(imgY)
        };
    }

    function addBrushPoint(p) {
        if (!p) return;
        if (lastBrushPoint) {
            const dx = p.x - lastBrushPoint.x;
            const dy = p.y - lastBrushPoint.y;
            const dist = Math.sqrt(dx * dx + dy * dy);
            if (dist < Math.max(2, brushRadius * 0.25)) return;
        }

        const record = [
            Math.round(p.x),
            Math.round(p.y),
            Math.round(brushRadius)
        ];

        if (editorTool === 'add') {
            foregroundMask.add_brush.push(record);
        } else if (editorTool === 'subtract') {
            foregroundMask.subtract_brush.push(record);
        }
        lastBrushPoint = p;
    }

    // =========================================================
    // ÇİZİM MOTORU (CANVAS RENDER)
    // =========================================================

    function draw() {
        if (!currentImg) return;
        
        canvas.width = cont.clientWidth;
        canvas.height = cont.clientHeight;
        
        const padding = 40;
        const scaleX = (canvas.width - padding) / currentImg.width;
        const scaleY = (canvas.height - padding) / currentImg.height;
        baseScale = Math.min(scaleX, scaleY, 1);
        
        const finalScale = baseScale * userZoom;
        const imgDrawW = currentImg.width * finalScale;
        const imgDrawH = currentImg.height * finalScale;
        
        const startX = (canvas.width - imgDrawW) / 2 + offsetX;
        const startY = (canvas.height - imgDrawH) / 2 + offsetY;
        
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.imageSmoothingEnabled = true;
        ctx.drawImage(currentImg, startX, startY, imgDrawW, imgDrawH);
        
        // 1. Baskı Yüzeyi Poligonu (Kırmızı)
        if (pts.length === 4) {
            ctx.beginPath();
            ctx.moveTo(startX + pts[0].x * finalScale, startY + pts[0].y * finalScale);
            for(let i=1; i<4; i++) ctx.lineTo(startX + pts[i].x * finalScale, startY + pts[i].y * finalScale);
            ctx.closePath();
            
            ctx.fillStyle = 'rgba(255, 0, 0, 0.0)'; // Tamamen seffaf (Gorseli engellememesi icin)
            ctx.fill();
            ctx.strokeStyle = '#ff3333';
            ctx.lineWidth = 2;
            ctx.stroke();

            // Perspektif 3x3 Kılavuz Grid Çizgileri
            const gridSteps = 3;
            ctx.setLineDash([5, 4]);
            for (let step = 1; step < gridSteps; step++) {
                const t = step / gridSteps;
                // Dikey perspektif çizgileri (üstten alta)
                const topX = pts[0].x + (pts[1].x - pts[0].x) * t;
                const topY = pts[0].y + (pts[1].y - pts[0].y) * t;
                const botX = pts[3].x + (pts[2].x - pts[3].x) * t;
                const botY = pts[3].y + (pts[2].y - pts[3].y) * t;
                
                ctx.beginPath();
                ctx.moveTo(startX + topX * finalScale, startY + topY * finalScale);
                ctx.lineTo(startX + botX * finalScale, startY + botY * finalScale);
                ctx.strokeStyle = 'rgba(255, 255, 255, 0.4)';
                ctx.lineWidth = 1;
                ctx.stroke();

                // Yatay perspektif çizgileri (soldan sağa)
                const leftX = pts[0].x + (pts[3].x - pts[0].x) * t;
                const leftY = pts[0].y + (pts[3].y - pts[0].y) * t;
                const rightX = pts[1].x + (pts[2].x - pts[1].x) * t;
                const rightY = pts[1].y + (pts[2].y - pts[1].y) * t;
                
                ctx.beginPath();
                ctx.moveTo(startX + leftX * finalScale, startY + leftY * finalScale);
                ctx.lineTo(startX + rightX * finalScale, startY + rightY * finalScale);
                ctx.strokeStyle = 'rgba(255, 255, 255, 0.4)';
                ctx.lineWidth = 1;
                ctx.stroke();
            }
            ctx.setLineDash([]);
            
            // Köşe Noktaları ve Numaralandırma (1: Sol Üst, 2: Sağ Üst, 3: Sağ Alt, 4: Sol Alt)
            const cornerColors = ['#00e5ff', '#ffeb3b', '#ff4081', '#76ff03'];
            const cornerLabels = ['1: Sol Üst', '2: Sağ Üst', '3: Sağ Alt', '4: Sol Alt'];
            for(let i=0; i<4; i++) {
                const px = startX + pts[i].x * finalScale;
                const py = startY + pts[i].y * finalScale;
                
                ctx.beginPath();
                ctx.arc(px, py, 7, 0, Math.PI*2);
                ctx.fillStyle = cornerColors[i];
                ctx.fill();
                ctx.strokeStyle = '#000';
                ctx.lineWidth = 2;
                ctx.stroke();

                // Numara Etiketi
                ctx.fillStyle = '#000';
                ctx.font = 'bold 10px sans-serif';
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillText((i + 1).toString(), px, py);

                // Köşe Adı
                ctx.fillStyle = cornerColors[i];
                ctx.font = 'bold 11px sans-serif';
                ctx.textAlign = (i === 1 || i === 2) ? 'left' : 'right';
                ctx.textBaseline = 'middle';
                const offX = (i === 1 || i === 2) ? 12 : -12;
                ctx.fillText(cornerLabels[i], px + offX, py);
            }
        }

        // 2. Foreground Editor Katmanları (Object Boxes & Brushes)
        drawForegroundEditor(startX, startY, finalScale);
        
        const objCount = foregroundMask.object_boxes.length;
        const brushCount = foregroundMask.add_brush.length + foregroundMask.subtract_brush.length;
        const toolNames = { corner: '🔴 4 KÖŞE', object: '✨ NESNE SEÇ', add: '➕ FIRÇAYLA EKLE', subtract: '➖ FIRÇAYLA ÇIKAR' };
        let infoStr = `Görsel: ${currentImg.width}x${currentImg.height} | Zoom: ${Math.round(userZoom*100)}% | Aktif Araç: <b>${toolNames[editorTool] || editorTool}</b>`;
        infoStr += ` | Nesne Kutuları: ${objCount} | Fırça Noktaları: ${brushCount}`;
        document.getElementById('info').innerHTML = infoStr;
    }

    function drawForegroundEditor(startX, startY, finalScale) {
        ctx.save();

        // 1. Kayıtlı Nesne Seçim Kutuları (GrabCut Boxes)
        for (let i = 0; i < foregroundMask.object_boxes.length; i++) {
            const box = foregroundMask.object_boxes[i];
            if (!box || box.length !== 4) continue;
            const [x1, y1, x2, y2] = box;
            const sx = startX + x1 * finalScale;
            const sy = startY + y1 * finalScale;
            const sw = (x2 - x1) * finalScale;
            const sh = (y2 - y1) * finalScale;

            ctx.fillStyle = 'rgba(0, 255, 80, 0.14)';
            ctx.fillRect(sx, sy, sw, sh);

            ctx.strokeStyle = '#00ff66';
            ctx.lineWidth = 2;
            ctx.setLineDash([6, 4]);
            ctx.strokeRect(sx, sy, sw, sh);

            // Badge
            ctx.fillStyle = '#00ff66';
            ctx.font = 'bold 12px sans-serif';
            ctx.fillText(`✨ Nesne #${i + 1}`, sx + 4, sy + 15);
        }
        ctx.setLineDash([]);

        // 2. Şu An Sürüklenen Nesne Kutusu
        if (maskDragStart && maskDragCurrent) {
            const x1 = Math.min(maskDragStart.x, maskDragCurrent.x);
            const y1 = Math.min(maskDragStart.y, maskDragCurrent.y);
            const x2 = Math.max(maskDragStart.x, maskDragCurrent.x);
            const y2 = Math.max(maskDragStart.y, maskDragCurrent.y);

            ctx.fillStyle = 'rgba(0, 255, 255, 0.18)';
            ctx.strokeStyle = '#00ffff';
            ctx.lineWidth = 2;

            const sx = startX + x1 * finalScale;
            const sy = startY + y1 * finalScale;
            const sw = (x2 - x1) * finalScale;
            const sh = (y2 - y1) * finalScale;

            ctx.fillRect(sx, sy, sw, sh);
            ctx.strokeRect(sx, sy, sw, sh);
        }

        // 3. ➕ Ekle Fırça Katmanı
        ctx.fillStyle = 'rgba(0, 255, 80, 0.32)';
        for (const stroke of foregroundMask.add_brush) {
            const [x, y, r] = stroke;
            ctx.beginPath();
            ctx.arc(startX + x * finalScale, startY + y * finalScale, r * finalScale, 0, Math.PI * 2);
            ctx.fill();
        }

        // 4. ➖ Çıkar Fırça Katmanı
        ctx.fillStyle = 'rgba(255, 40, 40, 0.32)';
        for (const stroke of foregroundMask.subtract_brush) {
            const [x, y, r] = stroke;
            ctx.beginPath();
            ctx.arc(startX + x * finalScale, startY + y * finalScale, r * finalScale, 0, Math.PI * 2);
            ctx.fill();
        }

        // 5. Fırça İmleci Önizlemesi (Brush Cursor)
        if ((editorTool === 'add' || editorTool === 'subtract') && hoverBrushPoint) {
            const hx = startX + hoverBrushPoint.x * finalScale;
            const hy = startY + hoverBrushPoint.y * finalScale;
            const hr = brushRadius * finalScale;

            ctx.beginPath();
            ctx.arc(hx, hy, hr, 0, Math.PI * 2);
            ctx.strokeStyle = (editorTool === 'add') ? '#00ff66' : '#ff3333';
            ctx.lineWidth = 1.5;
            ctx.stroke();

            // Merkez artı işareti
            ctx.beginPath();
            ctx.moveTo(hx - 4, hy); ctx.lineTo(hx + 4, hy);
            ctx.moveTo(hx, hy - 4); ctx.lineTo(hx, hy + 4);
            ctx.strokeStyle = '#fff';
            ctx.lineWidth = 1;
            ctx.stroke();
        }

        ctx.restore();
    }

    // =========================================================
    // FARE VE İŞARETÇİ ETKİLEŞİMLERİ (POINTER EVENTS)
    // =========================================================

    canvas.addEventListener('contextmenu', e => e.preventDefault());

    window.addEventListener('keydown', e => {
        if (e.code === 'Space' && !isSpacePressed) {
            isSpacePressed = true;
            updateCursor();
        }
    });
    window.addEventListener('keyup', e => {
        if (e.code === 'Space') {
            isSpacePressed = false;
            updateCursor();
        }
    });

    canvas.addEventListener('pointerdown', function(e) {
        if (!currentImg) return;

        if (e.button === 2) {
            isPanning = true;
            panStartX = e.clientX - offsetX;
            panStartY = e.clientY - offsetY;
            updateCursor();
            return;
        }

        // Sol Tık
        if (e.button === 0) {
            // 1. Köşe Sürükleme Modu
            if (editorTool === 'corner') {
                // Köşe modu: sınır dışına taşan noktalar da yakalanabilsin
                const rawPos = eventToRawImagePoint(e);
                if (!rawPos) return;
                const finalScale = baseScale * userZoom;
                // Ekran piksel cinsinden 22px hit radius (zoom bağımsız)
                let minDist = 22 / finalScale;
                draggingPoint = -1;
                for (let i = 0; i < 4; i++) {
                    const dx = pts[i].x - rawPos.x;
                    const dy = pts[i].y - rawPos.y;
                    const dist = Math.sqrt(dx * dx + dy * dy);
                    if (dist < minDist) {
                        minDist = dist;
                        draggingPoint = i;
                    }
                }
                if (draggingPoint !== -1) {
                    try { canvas.setPointerCapture(e.pointerId); } catch (_) {}
                }
                return;
            }

            // 2. Nesne Seç veya Fırça Modları
            e.preventDefault();
            e.stopImmediatePropagation();
            const p = eventToImagePoint(e);
            if (!p) return;

            try { canvas.setPointerCapture(e.pointerId); } catch (_) {}

            if (editorTool === 'object') {
                if (e.shiftKey) {
                    // Shift+Tık ile tıklanan kutuyu sil
                    for (let i = foregroundMask.object_boxes.length - 1; i >= 0; i--) {
                        const b = foregroundMask.object_boxes[i];
                        if (p.x >= b[0] && p.x <= b[2] && p.y >= b[1] && p.y <= b[3]) {
                            pushMaskHistory();
                            foregroundMask.object_boxes.splice(i, 1);
                            saveCurrentTemplateData();
                            draw();
                            return;
                        }
                    }
                }
                pushMaskHistory();
                maskDragStart = p;
                maskDragCurrent = p;
                draw();
                return;
            }

            if (editorTool === 'add' || editorTool === 'subtract') {
                pushMaskHistory();
                brushDrawing = true;
                lastBrushPoint = null;
                addBrushPoint(p);
                draw();
                return;
            }
        }
    }, true);

    canvas.addEventListener('pointermove', function(e) {
        if (!currentImg) return;

        // Pan devam ediyor mu?
        if (isPanning) {
            offsetX = e.clientX - panStartX;
            offsetY = e.clientY - panStartY;
            draw();
            return;
        }

        // Köşe sürükleniyor mu?
        if (editorTool === 'corner' && draggingPoint !== -1) {
            // Sınır kontrolsuz koordinat kullan - dışarıya taşabilsin
            const rawPos = eventToRawImagePoint(e);
            if (!rawPos) return;
            const data = ayarlar.kategoriler[currentCat].sablonlar[currentTmpl];

            if (data.tip === 'duz') {
                const cx = Math.round(Math.max(0, Math.min(rawPos.x, currentImg.width)));
                const cy = Math.round(Math.max(0, Math.min(rawPos.y, currentImg.height)));
                if (draggingPoint === 0) { pts[0].x = cx; pts[0].y = cy; pts[3].x = cx; pts[1].y = cy; }
                if (draggingPoint === 1) { pts[1].x = cx; pts[1].y = cy; pts[2].x = cx; pts[0].y = cy; }
                if (draggingPoint === 2) { pts[2].x = cx; pts[2].y = cy; pts[1].x = cx; pts[3].y = cy; }
                if (draggingPoint === 3) { pts[3].x = cx; pts[3].y = cy; pts[0].x = cx; pts[2].y = cy; }
            } else {
                // Perspektif: sınır yok, serbestce taşabilsin
                pts[draggingPoint].x = Math.round(rawPos.x);
                pts[draggingPoint].y = Math.round(rawPos.y);
            }
            updateDataFromPoints();
            draw();
            return;
        }

        const p = eventToImagePoint(e);
        hoverBrushPoint = p;

        if (editorTool === 'object' && maskDragStart) {
            e.preventDefault();
            e.stopImmediatePropagation();
            maskDragCurrent = p || maskDragCurrent;
            draw();
            return;
        }

        if ((editorTool === 'add' || editorTool === 'subtract') && brushDrawing && p) {
            e.preventDefault();
            e.stopImmediatePropagation();
            addBrushPoint(p);
            draw();
            return;
        }

        // Fırça önizleme imlecini çiz
        if (editorTool === 'add' || editorTool === 'subtract') {
            draw();
        }
    }, true);

    canvas.addEventListener('pointerup', function(e) {
        if (e.button === 2) {
            isPanning = false;
            updateCursor();
            return;
        }

        if (editorTool === 'corner') {
            draggingPoint = -1;
            return;
        }

        e.preventDefault();
        e.stopImmediatePropagation();

        if (editorTool === 'object' && maskDragStart && maskDragCurrent) {
            let x1 = Math.min(maskDragStart.x, maskDragCurrent.x);
            let y1 = Math.min(maskDragStart.y, maskDragCurrent.y);
            let x2 = Math.max(maskDragStart.x, maskDragCurrent.x);
            let y2 = Math.max(maskDragStart.y, maskDragCurrent.y);

            // Sadece tek tık yapılmışsa akıllı otomatik kutu oluştur
            if ((x2 - x1) < 8 && (y2 - y1) < 8) {
                const autoSize = Math.max(60, Math.round(Math.min(currentImg.width, currentImg.height) * 0.08));
                const cx = maskDragStart.x;
                const cy = maskDragStart.y;
                x1 = Math.max(0, cx - autoSize);
                y1 = Math.max(0, cy - autoSize);
                x2 = Math.min(currentImg.width - 1, cx + autoSize);
                y2 = Math.min(currentImg.height - 1, cy + autoSize);
            }

            foregroundMask.object_boxes.push([
                Math.round(x1),
                Math.round(y1),
                Math.round(x2),
                Math.round(y2)
            ]);

            maskDragStart = null;
            maskDragCurrent = null;
            saveCurrentTemplateData();
        }

        if (brushDrawing) {
            brushDrawing = false;
            lastBrushPoint = null;
            saveCurrentTemplateData();
        }

        try { canvas.releasePointerCapture(e.pointerId); } catch (_) {}
        draw();
    }, true);

    canvas.addEventListener('pointercancel', function(e) {
        maskDragStart = null;
        maskDragCurrent = null;
        brushDrawing = false;
        lastBrushPoint = null;
        isPanning = false;
        updateCursor();
        draw();
    }, true);

    canvas.addEventListener('pointerleave', function(e) {
        hoverBrushPoint = null;
        draw();
    });

    // Klavye Kısayolları (Ctrl+Z, C, V, Enter, Space, 1, 2, 3, 4, [, ], N, P)
    window.addEventListener('keydown', (e) => {
        if (e.target && e.target.tagName === 'INPUT') return;
        
        if (e.key === ' ' && !isSpacePressed) {
            e.preventDefault();
            isSpacePressed = true;
            if (!isPanning) {
                isPanning = true;
                panStartX = 0; // We will update this on pointermove if needed, but usually pointerdown starts it
                document.body.style.cursor = 'grab';
            }
        } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') {
            e.preventDefault();
            undoMaskAction();
        } else if (e.key.toLowerCase() === 'c' && pts.length === 4) {
            clipboardPts = JSON.parse(JSON.stringify(pts));
        } else if (e.key.toLowerCase() === 'v' && clipboardPts) {
            pts = JSON.parse(JSON.stringify(clipboardPts));
            updateDataFromPoints();
            saveAll(true); // Auto-save after paste
            draw();
        } else if (e.key === 'Enter') {
            e.preventDefault();
            autoDetectCorners();
        } else if (e.key.toLowerCase() === 'n' || e.key === 'ArrowRight') {
            e.preventDefault();
            nextTemplate();
        } else if (e.key.toLowerCase() === 'p' || e.key === 'ArrowLeft') {
            e.preventDefault();
            prevTemplate();
        }
    });

    window.addEventListener('keyup', (e) => {
        if (e.key === ' ') {
            isSpacePressed = false;
            isPanning = false;
            updateCursor();
        }
    });

    // Zooming
    canvas.onwheel = (e) => {
        if (!currentImg) return;
        e.preventDefault();
        
        const zoomIntensity = 0.1;
        const wheel = e.deltaY < 0 ? 1 : -1;
        const zoomFactor = Math.exp(wheel * zoomIntensity);
        
        const rect = canvas.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;
        
        const centerX = canvas.width / 2;
        const centerY = canvas.height / 2;
        
        const dx = mouseX - centerX;
        const dy = mouseY - centerY;
        
        const newZoom = userZoom * zoomFactor;
        
        offsetX = offsetX * zoomFactor - dx * (zoomFactor - 1);
        offsetY = offsetY * zoomFactor - dy * (zoomFactor - 1);
        
        userZoom = newZoom;
        draw();
    };
    
    // Double click to reset
    canvas.ondblclick = () => {
        resetView();
        draw();
    };
    
    window.onresize = draw;

    function autoDetectCorners() {
        if (!currentCat || !currentTmpl) {
            alert("Lutfen once listeden bir sablon secin!");
            return;
        }
        const btn = document.getElementById('btnAutoCorner');
        const origText = btn.innerHTML;
        btn.innerHTML = '⏳ Köşeler Algılanıyor...';
        btn.disabled = true;

        fetch('/api/auto_detect_corners', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                kategori: currentCat,
                sablon: currentTmpl
            })
        })
        .then(r => r.json())
        .then(res => {
            btn.innerHTML = origText;
            btn.disabled = false;
            if (res.success && res.corners && res.corners.length === 4) {
                pts = res.corners.map(p => ({x: p[0], y: p[1]}));
                updateDataFromPoints();
                draw();
                alert('4 kose otomatik olarak basariyla tespit edildi! Koseleri kontrol edin, gerekirse ince ayar yapin.');
            } else {
                alert("Otomatik kose tespiti basarisiz: " + (res.error || "4 koselik bir alan bulunamadi. Lutfen elle ayarlayin."));
            }
        })
        .catch(err => {
            btn.innerHTML = origText;
            btn.disabled = false;
            alert("Sunucu baglanti hatasi: " + err);
        });
    }

    function instantWhiten() {
        if (!currentCat || !currentTmpl) return;
        updateDataFromPoints();
        saveCurrentTemplateData();
        fetch('/api/anlik_beyazlat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Active-Category': currentCat,
                'X-Active-Template': currentTmpl
            },
            body: JSON.stringify(ayarlar)
        }).then(r => r.json()).then(res => {
            if(res.success) {
                const tempImg = new Image();
                tempImg.onload = () => {
                    currentImg = tempImg;
                    previewModeActive = true;
                    draw();
                };
                tempImg.src = '/preview/' + encodeURIComponent(currentCat) + '/' + encodeURIComponent(currentTmpl) + '?t=' + new Date().getTime();
            } else {
                alert("Beyazlatma başarısız: " + (res.error || 'Bilinmeyen hata'));
            }
        });
    }

    let tempPreviewImg = null;
    function toggleOriginalView() {
        if (!originalImgObj) return;
        
        isShowingOriginal = !isShowingOriginal;
        
        if (isShowingOriginal) {
            tempPreviewImg = currentImg; // Onizlemeyi sakla
            currentImg = originalImgObj; // Orijinale gec
            document.getElementById('btnToggleOriginal').innerHTML = "👁️ Önizlemeye Dön";
            document.getElementById('btnToggleOriginal').style.background = "#ff9800";
        } else {
            if (tempPreviewImg) {
                currentImg = tempPreviewImg; // Onizlemeye geri don
            }
            document.getElementById('btnToggleOriginal').innerHTML = "👁️ Orijinal / Önizleme";
            document.getElementById('btnToggleOriginal').style.background = "#9c27b0";
        }
        draw();
    }

    function restoreOriginal() {
        if (!currentCat || !currentTmpl) return;
        fetch('/api/orijinal_yukle', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Active-Category': currentCat,
                'X-Active-Template': currentTmpl
            }
        }).then(r => r.json()).then(res => {
            if(res.success) {
                const tempImg = new Image();
                tempImg.onload = () => {
                    currentImg = tempImg;
                    originalImgObj = tempImg;
                    previewModeActive = false;
                    draw();
                };
                tempImg.src = '/image/' + encodeURIComponent(currentCat) + '/' + encodeURIComponent(currentTmpl) + '?t=' + new Date().getTime();
            } else {
                alert("Orijinal yükleme başarısız: " + (res.error || 'Bu görselin eski bir kopyası (orijinal yedek) bulunamadı.'));
            }
        });
    }

    function tumunuBeyazlat() {
        if (!confirm(`Tüm şablonlar (veya sadece bu kategori) arka planda kalıcı olarak beyazlatılacak. Sadece koordinatları belirlenmiş olanlar işlenecektir.\n\nSadece mevcut kategoriyi beyazlatmak istiyorsanız 'Tamam' deyin.\nTüm veritabanındaki şablonları beyazlatmak istiyorsanız 'İptal' diyerek tam beyazlatmayı seçin.`)) {
            if (!confirm("TÜM KATEGORİLERDEKİ ŞABLONLARI BEYAZLATMAK ÜZERESİNİZ. Onaylıyor musunuz?")) return;
            _triggerTumunuBeyazlat(null);
        } else {
            if (!currentCat) {
                alert("Lütfen önce bir kategori seçin!");
                return;
            }
            _triggerTumunuBeyazlat(currentCat);
        }
    }

    function _triggerTumunuBeyazlat(kategori) {
        alert("Beyazlatma işlemi arka planda başlatıldı! Sunucu ekranından (siyah ekran) takip edebilirsiniz.");
        fetch('/api/tumunu_beyazlat', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ kategori: kategori })
        }).then(r => r.json()).then(res => {
            if (res.success) {
                alert("İşlem başarıyla tamamlandı! İşlenen dosya sayısı: " + res.islenen);
            } else {
                alert("Hata oluştu: " + res.error);
            }
        }).catch(err => {
            alert("Bağlantı hatası: " + err);
        });
    }

    function deleteTemplate() {
        if (!currentCat || !currentTmpl) return;
        if (!confirm('Bu şablonu çöpe atmak istediğinize emin misiniz? (Geri alabilirsiniz)')) return;
        
        fetch('/api/sablon_sil', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Active-Category': currentCat,
                'X-Active-Template': currentTmpl
            }
        }).then(r => r.json()).then(res => {
            if(res.success) {
                // Remove from ayarlar and UI
                delete ayarlar.kategoriler[currentCat].sablonlar[currentTmpl];
                renderSidebar();
                // Load next template
                const keys = Object.keys(ayarlar.kategoriler[currentCat].sablonlar);
                if (keys.length > 0) {
                    const nextTmpl = keys[0];
                    const listItems = document.querySelectorAll('.template-item');
                    let nextElem = null;
                    listItems.forEach(el => {
                        if (el.textContent === nextTmpl || el.textContent === '⚠️ ' + nextTmpl) {
                            nextElem = el;
                        }
                    });
                    loadTemplate(currentCat, nextTmpl, nextElem);
                } else {
                    currentTmpl = null;
                    currentImg = null;
                    draw();
                }
            } else {
                alert("Silme başarısız: " + (res.error || 'Bilinmeyen hata'));
            }
        });
    }

    function undoDelete() {
        fetch('/api/sablon_sil_geri_al', {
            method: 'POST'
        }).then(r => r.json()).then(res => {
            if(res.success) {
                // Reload ayarlar and UI
                fetch('/api/ayarlar')
                    .then(r => r.json())
                    .then(data => {
                        ayarlar = data;
                        renderSidebar();
                        alert("Şablon başarıyla geri getirildi: " + res.restored_tmpl);
                    });
            } else {
                alert("Geri alma başarısız: " + (res.error || 'Çöpte dosya yok.'));
            }
        });
    }

    function saveAll(silent = false) {
        if (currentCat && currentTmpl) {
            updateDataFromPoints();
            saveCurrentTemplateData();
        }
        const saveCat = currentCat;
        const saveTmpl = currentTmpl;
        if (!saveCat || !saveTmpl) return;
        
        const currentData = ayarlar.kategoriler[saveCat].sablonlar[saveTmpl];

        fetch('/api/tekil_sablon_kaydet', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                "kategori": saveCat,
                "sablon": saveTmpl,
                "data": currentData
            })
        }).then(r => r.json()).then(res => {
            if(res.success) {
                // Sadece manuel kaydetmede görseli yenile
                if (saveCat && saveTmpl && !silent) {
                    const stem = saveTmpl.replace(/\.[^.]+$/, '');
                    const tempImg = new Image();
                    tempImg.onload = () => { currentImg = tempImg; draw(); };
                    tempImg.src = '/image/' + encodeURIComponent(saveCat) + '/' + encodeURIComponent(stem + '.png') + '?t=' + Date.now();
                }
                if (!silent) {
                    alert('Tum degisiklikler ve on plan maskeleri basariyla ayarlar.json dosyasina kaydedildi!');
                }
            } else {
                if (!silent) alert('Hata olustu! Detay: ' + (res.error || 'Bilinmeyen'));
            }
        }).catch(err => {
            if (!silent) alert('Kaydetme hatasi: ' + err);
        });
    }

    async function batchAutoDetect() {
        if (!currentCat) { alert("Lütfen önce listeden bir kategori seçin!"); return; }
        const templates = allTemplates.filter(t => t.cat === currentCat);
        if (templates.length === 0) return;
        
        // Henüz işlenmemiş olanları say (hızlandırmak için sadece boş olanları da yapabiliriz ama hepsi baştan taranacak)
        if (!confirm(`Bu kategorideki ${templates.length} şablon için otomatik algılama başlatılacak.\n\nİşlem biraz sürebilir, onaylıyor musunuz?`)) return;

        let successCount = 0;
        let failCount = 0;
        
        const btn = document.getElementById('btnBatchDetect');
        const origHtml = btn.innerHTML;
        btn.disabled = true;
        btn.style.background = '#6c757d';

        for (let i = 0; i < templates.length; i++) {
            const t = templates[i];
            btn.innerHTML = `⏳ ${i+1} / ${templates.length} taranıyor...`;
            
            // Eğer zaten köşeleri varsa atla
            const tmplData = ayarlar.kategoriler[t.cat].sablonlar[t.tmpl];
            if (tmplData.koseler && tmplData.koseler.length === 4) {
                // Atla
                continue;
            }

            try {
                const res = await fetch('/api/auto_detect_corners', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ kategori: t.cat, sablon: t.tmpl })
                }).then(r => r.json());
                
                if (res.success && res.corners && res.corners.length === 4) {
                    tmplData.koseler = res.corners;
                    tmplData.tip = 'perspektif';
                    t.elem.textContent = '✅ ' + t.tmpl; // Update sidebar
                    successCount++;
                } else {
                    failCount++;
                }
            } catch(e) { failCount++; }
        }
        
        saveAll(true); // Arka planda sessizce kaydet
        btn.disabled = false;
        btn.style.background = '#e83e8c';
        btn.innerHTML = origHtml;
        alert(`Toplu tarama tamamlandı!\n\nYeni algılanan: ${successCount}\nBulunamayan: ${failCount}`);
        
        // Ekrani guncelle
        if (currentCat && currentTmpl) {
            loadTemplate(currentCat, currentTmpl, allTemplates.find(x => x.cat===currentCat && x.tmpl===currentTmpl).elem);
        }
    }

    // --- PANELLERI BOYUTLANDIRMA (RESIZER) ---
    function setupResizer(resizerId, panelId, isLeft) {
        const resizer = document.getElementById(resizerId);
        const panel = document.getElementById(panelId);
        if (!resizer || !panel) return;
        let startX, startWidth;

        resizer.addEventListener('mousedown', function(e) {
            startX = e.clientX;
            const style = window.getComputedStyle(panel);
            startWidth = parseInt(style.width, 10);
            document.documentElement.addEventListener('mousemove', doDrag, false);
            document.documentElement.addEventListener('mouseup', stopDrag, false);
            resizer.classList.add('active');
            document.body.style.cursor = 'col-resize';
            document.body.style.userSelect = 'none'; // Secimi engelle
        });

        function doDrag(e) {
            let newWidth = isLeft ? startWidth + (e.clientX - startX) : startWidth - (e.clientX - startX);
            if (newWidth > 150 && newWidth < 800) {
                panel.style.width = newWidth + 'px';
                // Surekli guncellemek yerine ufak bir cizim tetikle (kasmamasi icin)
                draw();
            }
        }

        function stopDrag() {
            document.documentElement.removeEventListener('mousemove', doDrag, false);
            document.documentElement.removeEventListener('mouseup', stopDrag, false);
            resizer.classList.remove('active');
            document.body.style.cursor = '';
            document.body.style.userSelect = '';
            // Son boyutlandirmadan sonra canvas'i tam ortaya oturt
            setTimeout(() => {
                resetView();
                draw();
            }, 50);
        }
    }
    
    // Sayfa yuklendikten kisa sure sonra aktif et
    setTimeout(() => {
        setupResizer('resizer-left', 'sidebar', true);
        setupResizer('resizer-right', 'right-toolbar', false);
    }, 500);

</script>

</body>
</html>
"""

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
                safe_onizleme_base = os.path.abspath(os.path.join(BASE_DIR, "YENI-BOS MOCKUP SABLON HAVUZU"))
                stem = Path(tmpl).stem
                img_path = os.path.abspath(os.path.join(safe_onizleme_base, cat, stem + "-beyazlatilmis-onizleme.png"))
                
                if not img_path.startswith(safe_onizleme_base):
                    self.send_error(403, "Erisim engellendi")
                    return
                    
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
                src = os.path.join(YEDEK_IMG_DIR, active_cat, active_tmpl)
                if not os.path.isfile(src):
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
            if os.path.exists(cop_png):
                shutil.move(cop_png, restore_path)
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

if __name__ == '__main__':
    logger.info("SABLON DUZELTICI (Zoom & Pan Aktif) BASLATILDI - ThreadingTCPServer")
    print("SABLON DUZELTICI (Zoom & Pan Aktif) BASLATILDI - Port:", PORT)
    
    # P0: auto-repair intentionally disabled at panel startup.

    with socketserver.ThreadingTCPServer(("127.0.0.1", PORT), MockupHandler) as httpd:
        httpd.serve_forever()
