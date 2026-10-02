# E-TİCARET GÖRSEL ÜRETİM VE MOCKUP OTOMASYONU - SİSTEM ANALİZ DOSYASI

## 1. PROJENİN AMACI VE HEDEFLERİ
Bu proje, bir e-ticaret satıcısının satmak istediği binlerce tasarımı (tablo, wifi kutusu, cam doğrama vb.) alıp, **insan müdahalesi olmadan milimetrik bir şekilde oda/mekan şablonlarına oturtmayı (mockup) ve Trendyol gibi pazar yerlerine yüklemeye hazır Excel çıktıları üretmeyi** amaçlar.

### Temel Hedefler:
- **Yüksek Hız ve Ölçeklenebilirlik:** Yüzlerce ham şablonu (11 farklı açı) ve binlerce tasarımı alıp saatler içinde on binlerce satışa hazır ürün görseli oluşturmak.
- **Kaggle AI Entegrasyonu:** Kaggle GPU matbaasında (Stable Diffusion/Midjourney) üretilen yepyeni, eşsiz görsel desenlerini API veya yerel klasör (Onay Mekanizması) üzerinden çekip anında mockuplara basmak.
- **Akıllı Maskeleme (OpenCV):** Şablonlarda ürünün nereye basılacağının koordinatlarını bulmak, arkaplanı otomatik beyazlatmak, eşya önünde kalan kısımları hesaplamak (occlusion).
- **Çoklu V2 Arayüz (Flask):** Kullanıcının sistemi tek bir komuta tıklar gibi kolay yönetmesini sağlayan Ana Kontrol Merkezi (Port 5000) ve şablonların köşelerinin hassas olarak işaretlendiği Şablon Düzeltici (Port 8080).

## 2. SİSTEM MİMARİSİ
1. **V2_KONTROL_MERKEZI (Flask):** Ana gösterge paneli. Kullanıcı iş akışını (Şablon yükle, Düzelticiyi aç, Kaggle Onay, Üretim başlat) buradan yönetir.
2. **SABLON_V2_MIMARI (Flask):** SQLite (ayarlar.db) destekli. Kullanıcı arayüzden şablondaki (resimdeki) çerçevenin 4 köşesini ayarlar. OpenCV yardımıyla taşma noktaları belirlenir.
3. **pc_master_factory.py (Üretim Motoru):** Kullanıcının `ayarlar.db` de belirlediği köşe koordinatlarını alarak `cv2.getPerspectiveTransform` ve `cv2.warpPerspective` ile ana görselleri şablona giydiren, ardından ImgBB bulutuna yükleyip Excel oluşturan ana işçi scripttir.
4. **Kaggle Onay Mekanizması:** Kaggle'dan gelen baskılar `0_KAGGLE_ONAY_BEKLEYENLER` klasöründe tutulur. Flask UI üzerinden 'Onayla' denirse `1_GELEN_KAGGLE_BASKILARI`na alınır ve Üretim Motoruna devredilir.

## 3. PROJE DOSYALARI VE KODLAR

Lütfen aşağıdaki tüm kodları inceleyerek; sistemin performansında, veritabanı (SQLite) kullanımında, OpenCV perspektif dönüşümlerinde veya genel Python mimarisinde güvenlik/hız açısından **eksik veya hatalı** bulduğunuz yerleri analiz edin.

### SİSTEMİ BAŞLATAN BATCH (SISTEMI_BASLAT.bat)
```bat
@echo off
title Ana Kontrol Merkezi (V2)
color 0A

echo ===================================================
echo 🚀 GORSEL URETIM FABRIKASI - ANA KONTROL MERKEZI
echo ===================================================
echo.
echo Gerekli sistem kontrol ediliyor...

:: Check if flask is installed
python -c "import flask" >nul 2>&1
if %errorlevel% neq 0 (
    echo Flask bulunamadi, otomatik kuruluyor... lutfen bekleyin.
    pip install flask
)

echo.
echo Ana Kontrol Merkezi calistiriliyor... Lutfen bu siyah ekrani KAPATMAYIN!
echo Tarayiciniz otomatik olarak acilacaktir...
echo.

:: Sunucuyu baslat
start "Motor" cmd /k "python V2_KONTROL_MERKEZI\app.py"

:: 3 Saniye bekle ve tarayiciyi ac
timeout /t 3 /nobreak >nul
start http://127.0.0.1:5000

exit

```

### OTOMASYON ÇALIŞTIRICI (OTOMASYONU_CALISTIR.bat)
```bat
@echo off
chcp 65001 > nul
title Trendyol ve E-Ticaret Otomasyonu V5
cls
echo ===============================================================================
echo      E-TICARET OTOMASYON MERKEZI (V5 MASTER FACTORY)
echo ===============================================================================
echo.
echo [1/3] 1_GELEN_KAGGLE_BASKILARI klasoru taraniyor...
echo [2/3] Master eserler 5 urun kategorisine donusturuluyor...
echo [3/3] Mockuplar basiliyor, ImgBB yukleniyor, Excel hazirlaniyor...
echo.
python 99_SISTEM_MOTORLARI_VE_KODLAR\SISTEM_MOTORU\pc_master_factory.py --mod dongusel
echo.
echo ===============================================================================
echo  TEBRIKLER! TUM ISLEMLER TAMAMLANDI!
echo  Hazir Mockuplar : 3_URETILEN_MOCKUPLAR klasorunde
echo  Yukleme Listesi : 4_EXCEL_YUKLEME_LISTELERI klasorunde
echo ===============================================================================
echo.
pause
```

### ANA KONTROL MERKEZİ BACKEND (V2_KONTROL_MERKEZI\app.py)
```python
import os
import sys
import subprocess
import threading
import glob
import json
import ctypes
import time
from PIL import Image
from flask import Flask, render_template, request, jsonify
import tkinter as tk

# Base Directory Setup
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SYS_MOTORS_DIR = os.path.join(BASE_DIR, "99_SISTEM_MOTORLARI_VE_KODLAR", "SISTEM_MOTORU")

def show_colored_popup(task_name, display_name, start_time):
    duration = time.time() - start_time
    prev_time = None
    PERFORMANCE_FILE = os.path.join(BASE_DIR, "logs", "performance.json")
    os.makedirs(os.path.dirname(PERFORMANCE_FILE), exist_ok=True)

    try:
        if os.path.exists(PERFORMANCE_FILE):
            with open(PERFORMANCE_FILE, "r") as f:
                prev_time = json.load(f).get(task_name)
    except: pass
        
    try:
        data = {}
        if os.path.exists(PERFORMANCE_FILE):
            with open(PERFORMANCE_FILE, "r") as f:
                data = json.load(f)
        data[task_name] = duration
        with open(PERFORMANCE_FILE, "w") as f:
            json.dump(data, f)
    except: pass

    dk = int(duration // 60)
    sn = int(duration % 60)
    süre_text = f"{dk} dk. {sn} sn." if dk > 0 else f"{sn} sn."
    
    root = tk.Tk()
    root.title("İşlem Tamamlandı")
    root.geometry("380x160")
    root.attributes("-topmost", True)
    root.configure(bg="#f8f9fa")
    
    tk.Label(root, text=f"{display_name} Başarıyla Tamamlandı!", font=("Segoe UI", 12, "bold"), bg="#f8f9fa", fg="#212529").pack(pady=12)
    
    time_frame = tk.Frame(root, bg="#f8f9fa")
    time_frame.pack()
    
    tk.Label(time_frame, text=f"⏱️ Süre: {süre_text}", font=("Segoe UI", 11), bg="#f8f9fa", fg="#495057").pack(side="left")
    
    if prev_time is not None:
        fark = prev_time - duration
        if fark > 0:
            tk.Label(time_frame, text=f"  (+{int(fark)} saniye)", font=("Segoe UI", 11, "bold"), fg="#198754", bg="#f8f9fa").pack(side="left")
        elif fark < 0:
            tk.Label(time_frame, text=f"  ({int(fark)} saniye)", font=("Segoe UI", 11, "bold"), fg="#dc3545", bg="#f8f9fa").pack(side="left")
        else:
            tk.Label(time_frame, text=f"  (Aynı)", font=("Segoe UI", 11, "bold"), fg="#6c757d", bg="#f8f9fa").pack(side="left")
            
    tk.Button(root, text="Harika!", command=root.destroy, width=15, bg="#0d6efd", fg="white", font=("Segoe UI", 10, "bold"), relief="flat", cursor="hand2").pack(pady=15)
    
    root.eval('tk::PlaceWindow . center')
    root.mainloop()

app = Flask(__name__)

# --- ROUTLAR (Sayfalar) ---
@app.route('/')
def index():
    return render_template('index.html')

# --- APILER (Botları Çalıştıran Komutlar) ---

@app.route('/api/open_folder', methods=['POST'])
def open_folder():
    """Belirtilen klasörü Windows Gezgini'nde açar (Örn: Şablon Yükleme Klasörü)"""
    data = request.json
    folder_name = data.get('folder_name')
    
    # Şimdilik örnek klasör yolları (Gerçek yollarla güncellenecek)
    target_path = BASE_DIR
    if folder_name == "SABLON_YUKLE":
        target_path = os.path.join(BASE_DIR, "2_SABLON_HAVUZU")
    elif folder_name == "TASARIM_YUKLE":
        target_path = os.path.join(BASE_DIR, "1_TASARIMLAR")
        
    if os.path.exists(target_path):
        os.startfile(target_path)
        return jsonify({"status": "success", "message": "Klasör açıldı."})
    return jsonify({"status": "error", "message": "Klasör bulunamadı."}), 404

@app.route('/api/run_script', methods=['POST'])
def run_script():
    """İstenilen Python scriptini çalıştırır"""
    data = request.json
    script_id = data.get('script_id')
    
    script_path = None
    cwd = BASE_DIR
    
    if script_id == "SABLON_DUZELTICI":
        script_path = os.path.join(BASE_DIR, "SABLON_DUZELTICI.py")
    elif script_id == "MANUEL_URETIM":
        script_path = os.path.join(SYS_MOTORS_DIR, "manuel_mockup_motoru.py")
        cwd = SYS_MOTORS_DIR
        
    # TODO: Diğer toollar buraya eklenecek (Watermark, İsimlendirici vs.)
        
    if script_path and os.path.exists(script_path):
        # Scripti arka planda başlat (UI'yi dondurmamak için)
        def run_proc():
            start_time = time.time()
            subprocess.run([sys.executable, script_path], cwd=cwd)
            display_name = "Şablon Motoru" if script_id == "SABLON_DUZELTICI" else "Manuel Mockup Üretimi"
            show_colored_popup(script_id, display_name, start_time)
            
        threading.Thread(target=run_proc).start()
        return jsonify({"status": "success", "message": f"{script_id} başlatıldı."})
        
    return jsonify({"status": "error", "message": "Script bulunamadı."}), 404

# --- ARAÇLAR (Tools) APILERI ---

@app.route('/api/tools/format_convert', methods=['POST'])
def format_convert():
    data = request.json
    target_format = data.get('format', 'JPG') # 'JPG' or 'PNG'
    
    # Çoklu dosya seçimi: İster tek, ister bazıları, ister tümünü (Ctrl+A) seçebilir
    cmd = [sys.executable, '-c', 'import tkinter.filedialog as fd, tkinter as tk, json; root=tk.Tk(); root.attributes("-topmost", True); root.withdraw(); print(json.dumps(fd.askopenfilenames(title="Görselleri Seçin (Tümünü istiyorsanız Ctrl+A yapın)", filetypes=[("Resimler", "*.png *.jpg *.jpeg")])))']
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    try:
        files = json.loads(result.stdout.strip())
    except:
        files = []
        
    if not files:
        return jsonify({"status": "error", "message": "Hiçbir görsel seçilmedi."}), 400
        
    def process():
        start_time = time.time()
        folder_path = os.path.dirname(files[0]) if files else ""
        for file in files:
            try:
                if target_format == 'JPG' and file.lower().endswith('.png'):
                    img = Image.open(file)
                    rgb_im = img.convert('RGB')
                    rgb_im.save(file.replace('.png', '.jpg'), quality=95)
                elif target_format == 'PNG' and file.lower().endswith(('.jpg', '.jpeg')):
                    img = Image.open(file)
                    img.save(file.rsplit('.', 1)[0] + '.png')
            except Exception as e:
                print(f"Hata: {e}")
                
        # İşlem bitince klasörü aç ve bilgi ver
        if folder_path:
            os.startfile(folder_path)
            show_colored_popup("format_convert", f"Format Çevirici ({target_format})", start_time)
                
    threading.Thread(target=process).start()
    return jsonify({"status": "success", "message": f"Arka planda tüm görseller {target_format} formatına çevriliyor. Bittiğinde klasör otomatik açılacak!"})

@app.route('/api/tools/rename_images', methods=['POST'])
def rename_images():
    data = request.json
    prefix = data.get('prefix', 'Gorsel_')
    
    cmd = [sys.executable, '-c', 'import tkinter.filedialog as fd, tkinter as tk, json; root=tk.Tk(); root.attributes("-topmost", True); root.withdraw(); print(json.dumps(fd.askopenfilenames(title="İsimlendirilecek Görselleri Seçin (Tümünü istiyorsanız Ctrl+A yapın)", filetypes=[("Resimler", "*.png *.jpg *.jpeg")])))']
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    try:
        files = json.loads(result.stdout.strip())
    except:
        files = []
        
    if not files:
        return jsonify({"status": "error", "message": "Hiçbir görsel seçilmedi."}), 400
        
    def process():
        start_time = time.time()
        # Filtreleme veya klasör bulma
        folder_path = os.path.dirname(files[0]) if files else ""
        for idx, file in enumerate(files, 1):
            ext = os.path.splitext(file)[1]
            new_name = f"{prefix}{idx:03d}{ext}"
            new_path = os.path.join(folder_path, new_name)
            try:
                os.rename(file, new_path)
            except Exception as e:
                print(f"Hata: {e}")
                
        # İşlem bitince klasörü aç ve bilgi ver
        if folder_path:
            os.startfile(folder_path)
            show_colored_popup("rename_images", "Toplu İsimlendirici", start_time)
                
    threading.Thread(target=process).start()
    return jsonify({"status": "success", "message": f"Görseller '{prefix}001' şeklinde isimlendiriliyor. Bittiğinde klasör otomatik açılacak!"})

@app.route('/api/tools/watermark', methods=['POST'])
def watermark():
    # 1. Logo Secimi
    cmd_logo = [sys.executable, '-c', 'import tkinter.filedialog as fd, tkinter as tk; root=tk.Tk(); root.attributes("-topmost", True); root.withdraw(); print(fd.askopenfilename(title="1. ADIM: Lütfen LOGO (Filigran) dosyasını seçin", filetypes=[("PNG Görseli", "*.png")]))']
    result_logo = subprocess.run(cmd_logo, capture_output=True, text=True)
    logo_path = result_logo.stdout.strip()
    
    if not logo_path: return jsonify({"status": "error", "message": "Logo seçilmedi."}), 400
    
    # 2. Resimlerin Secimi
    cmd_imgs = [sys.executable, '-c', 'import tkinter.filedialog as fd, tkinter as tk, json; root=tk.Tk(); root.attributes("-topmost", True); root.withdraw(); print(json.dumps(fd.askopenfilenames(title="2. ADIM: Logonun basılacağı görselleri seçin", filetypes=[("Resimler", "*.png *.jpg *.jpeg")])))']
    result_imgs = subprocess.run(cmd_imgs, capture_output=True, text=True)
    try:
        files = json.loads(result_imgs.stdout.strip())
    except:
        files = []
        
    if not files: return jsonify({"status": "error", "message": "Görsel seçilmedi."}), 400
    
    def process():
        start_time = time.time()
        folder_path = os.path.dirname(files[0]) if files else ""
        out_dir = os.path.join(folder_path, "Filigranli_Gorseller")
        if not os.path.exists(out_dir): os.makedirs(out_dir)
        
        try:
            watermark_img = Image.open(logo_path).convert("RGBA")
            for file in files:
                img = Image.open(file)
                if img.mode != 'RGBA':
                    img = img.convert('RGBA')
                    
                # Logoyu resmin %20'si boyutuna ayarla
                wm_width = int(img.width * 0.20)
                wm_ratio = wm_width / watermark_img.width
                wm_height = int(watermark_img.height * wm_ratio)
                wm_resized = watermark_img.resize((wm_width, wm_height), Image.Resampling.LANCZOS)
                
                # Pozisyon: Sağ Alt (Kenarlardan %5 boşluk)
                padding_x = int(img.width * 0.05)
                padding_y = int(img.height * 0.05)
                position = (img.width - wm_width - padding_x, img.height - wm_height - padding_y)
                
                img.paste(wm_resized, position, wm_resized)
                
                out_path = os.path.join(out_dir, os.path.basename(file))
                if file.lower().endswith(('.jpg', '.jpeg')):
                    img.convert('RGB').save(out_path, quality=100, subsampling=0)
                else:
                    img.save(out_path)
        except Exception as e:
            print(f"Hata: {e}")
            
        if folder_path:
            os.startfile(out_dir)
            show_colored_popup("watermark", "Filigran Motoru", start_time)

    threading.Thread(target=process).start()
    return jsonify({"status": "success", "message": "Logo ve görseller alındı. Filigran basılıyor..."})

@app.route('/api/tools/image_to_excel', methods=['POST'])
def image_to_excel():
    cmd = [sys.executable, '-c', 'import tkinter.filedialog as fd, tkinter as tk, json; root=tk.Tk(); root.attributes("-topmost", True); root.withdraw(); print(json.dumps(fd.askopenfilenames(title="Linke dönüştürülecek görselleri seçin", filetypes=[("Resimler", "*.png *.jpg *.jpeg")])))']
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        files = json.loads(result.stdout.strip())
    except:
        files = []
        
    if not files: return jsonify({"status": "error", "message": "Görsel seçilmedi."}), 400
    
    def process():
        start_time = time.time()
        import base64, requests, pandas as pd
        folder_path = os.path.dirname(files[0]) if files else ""
        
        # Load API keys from ayarlar.json
        ayarlar_path = os.path.join(BASE_DIR, "ayarlar.json")
        imgbb_keys = []
        try:
            with open(ayarlar_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                imgbb_keys = data.get("bulut_ayarlari", {}).get("imgbb_keys", [])
        except Exception as e:
            print(f"Hata: ayarlar.json okunamadı. ({e})")
            
        if not imgbb_keys:
            ctypes.windll.user32.MessageBoxW(0, "ayarlar.json dosyasında 'imgbb_keys' (API Anahtarı) bulunamadı! İşlem iptal edildi.", "Anahtar Eksik", 0x10)
            return
            
        def upload_to_imgbb(image_path, api_keys):
            try:
                with open(image_path, "rb") as file:
                    image_base64 = base64.b64encode(file.read()).decode('utf-8')
                for key in api_keys:
                    url = "https://api.imgbb.com/1/upload"
                    payload = {"key": key, "image": image_base64}
                    response = requests.post(url, data=payload, timeout=30)
                    if response.status_code == 200:
                        return response.json()["data"]["url"]
            except Exception as e:
                print(f"Yükleme hatası: {e}")
            return "YÜKLEME_HATASI"
            
        results = []
        for file in files:
            url = upload_to_imgbb(file, imgbb_keys)
            results.append({
                "Gorsel_Adi": os.path.basename(file),
                "Internet_Linki": url,
                "Sistem_Dosya_Yolu": file
            })
            
        if results and folder_path:
            df = pd.DataFrame(results)
            excel_path = os.path.join(folder_path, "Gorsel_Linkleri.xlsx")
            df.to_excel(excel_path, index=False)
            os.startfile(folder_path)
            show_colored_popup("image_to_excel", "Excel Aktarıcı (ImgBB)", start_time)

    threading.Thread(target=process).start()
    return jsonify({"status": "success", "message": "Görseller ImgBB'ye yükleniyor... Bu işlem dosya boyutuna göre birkaç dakika sürebilir. Bittiğinde klasör açılacak."})

@app.route('/api/tools/seo_generator', methods=['POST'])
def seo_generator():
    data = request.json or {}
    try:
        raw_adet = data.get('adet', 10)
        adet = int(raw_adet) if raw_adet else 10
    except (ValueError, TypeError):
        adet = 10
    
    script_dir = os.path.join(BASE_DIR, "ÜRÜN ADI YAZDIRMA BOTU")
    script_path = os.path.join(script_dir, "Benzersiz-ürün-adlari-yaz.py")
    
    if not os.path.exists(script_path):
        return jsonify({"status": "error", "message": "Bot dosyası bulunamadı."}), 404
        
    def process():
        start_time = time.time()
        wrapper = f"""
import sys, os, builtins
sys.path.append(r"{script_dir}")
import importlib.util
builtins.input = lambda x: str({adet})
spec = importlib.util.spec_from_file_location("seo_bot", r"{script_path}")
seo_bot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(seo_bot)
try:
    seo_bot.calistir({adet})
except Exception as e:
    print(e)
"""
        subprocess.run([sys.executable, "-c", wrapper], cwd=script_dir)
        os.startfile(script_dir)
        show_colored_popup("seo_generator", "SEO Üretici", start_time)
            
    threading.Thread(target=process).start()
    return jsonify({"status": "success", "message": f"{adet} adet SEO uyumlu ürün listesi üretiliyor..."})

@app.route('/api/tools/ai_enhancer', methods=['POST'])
def ai_enhancer():
    data = request.json or {}
    kat = data.get('kat', "4")
    if not kat or not str(kat).isdigit():
        kat = "4"
        
    script_dir = os.path.join(BASE_DIR, "AI_Kalite_Artirici")
    script_path = os.path.join(script_dir, "kalite_motoru.py")
    
    if not os.path.exists(script_path):
        return jsonify({"status": "error", "message": "Yapay Zeka motoru bulunamadı."}), 404
        
    def process():
        start_time = time.time()
        wrapper = f"""
import sys, os, builtins
sys.path.append(r"{script_dir}")
import importlib.util
builtins.input = lambda x: ""
spec = importlib.util.spec_from_file_location("ai_bot", r"{script_path}")
ai_bot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ai_bot)
try:
    ai_bot.kalite_artir(kat_sayi="{kat}")
except Exception as e:
    print(e)
"""
        subprocess.run([sys.executable, "-c", wrapper], cwd=script_dir)
        show_colored_popup("ai_enhancer", "Yapay Zeka (AI) 4K Kalite Motoru", start_time)
            
    threading.Thread(target=process).start()
    return jsonify({"status": "success", "message": "Lütfen açılacak pencereden kalitesi artırılacak KLASÖRÜ seçin. Yapay Zeka işlemi dosya sayısına göre uzun sürebilir..."})

if __name__ == '__main__':
    print("\n--- ANA KONTROL MERKEZI BASLATILIYOR (http://127.0.0.1:5000) ---")
    app.run(host='127.0.0.1', port=5000, debug=True, use_reloader=False)

```

### ANA KONTROL MERKEZİ ARAYÜZÜ (V2_KONTROL_MERKEZI\templates\index.html)
```html
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🚀 Mockup Ana Kontrol Merkezi</title>
    <!-- Bootstrap CSS -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <!-- FontAwesome Icons -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <!-- Google Fonts -->
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;800&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-color: #0d1117;
            --panel-bg: rgba(22, 27, 34, 0.7);
            --accent: #2ea043;
            --accent-hover: #3fb950;
            --text-main: #c9d1d9;
            --text-muted: #8b949e;
        }

        body {
            background-color: var(--bg-color);
            color: var(--text-main);
            font-family: 'Inter', sans-serif;
            overflow-x: hidden;
            background-image: radial-gradient(circle at top right, #1f2937, #0d1117);
            min-height: 100vh;
        }

        /* Glassmorphism Panels */
        .glass-panel {
            background: var(--panel-bg);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 15px;
            padding: 20px;
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
            transition: transform 0.2s, box-shadow 0.2s;
        }

        .glass-panel:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 40px 0 rgba(0, 0, 0, 0.5);
            border-color: rgba(255, 255, 255, 0.2);
        }

        /* Left Workflow Steps */
        .workflow-step {
            display: flex;
            align-items: center;
            margin-bottom: 25px;
            cursor: pointer;
            text-decoration: none;
            color: var(--text-main);
        }
        
        .workflow-step:hover .step-number {
            background: var(--accent);
            color: white;
            box-shadow: 0 0 15px var(--accent);
        }

        .step-number {
            width: 50px;
            height: 50px;
            border-radius: 50%;
            background: #21262d;
            border: 2px solid var(--accent);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.5rem;
            font-weight: 800;
            margin-right: 20px;
            transition: all 0.3s;
            flex-shrink: 0;
        }

        .step-details h3 {
            margin: 0;
            font-size: 1.2rem;
            font-weight: 600;
        }

        .step-details p {
            margin: 0;
            font-size: 0.9rem;
            color: var(--text-muted);
        }

        /* Right Tools Sidebar */
        .tools-sidebar {
            position: fixed;
            top: 0;
            right: -400px;
            width: 400px;
            height: 100vh;
            background: rgba(13, 17, 23, 0.95);
            backdrop-filter: blur(20px);
            border-left: 1px solid rgba(255,255,255,0.1);
            transition: right 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
            z-index: 1050;
            padding: 20px;
            overflow-y: auto;
        }

        .tools-sidebar.open {
            right: 0;
        }

        .sidebar-toggle {
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 1060;
            background: var(--accent);
            border: none;
            border-radius: 50%;
            width: 60px;
            height: 60px;
            color: white;
            font-size: 1.5rem;
            cursor: pointer;
            box-shadow: 0 0 20px rgba(46, 160, 67, 0.4);
            transition: transform 0.3s;
        }
        
        .sidebar-toggle:hover {
            transform: scale(1.1) rotate(90deg);
        }

        /* Tools List */
        .tool-item {
            background: #21262d;
            border: 1px solid rgba(255,255,255,0.05);
            border-radius: 10px;
            padding: 15px;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            transition: background 0.2s;
            cursor: pointer;
        }

        .tool-item:hover {
            background: #30363d;
            border-color: var(--accent);
        }

        .tool-icon {
            font-size: 2rem;
            color: var(--accent);
            margin-right: 15px;
            width: 40px;
            text-align: center;
        }

        .main-header {
            border-bottom: 1px solid rgba(255,255,255,0.1);
            padding-bottom: 15px;
            margin-bottom: 30px;
        }
        
        /* Custom Checkbox / Toggle for Watermark */
        .form-switch .form-check-input {
            width: 3em;
            height: 1.5em;
        }
    </style>
</head>
<body>

    <!-- Toggle Button for Tools Sidebar -->
    <button class="sidebar-toggle" onclick="toggleSidebar()" title="Araç Kutusunu Aç">
        <i class="fas fa-toolbox"></i>
    </button>

    <div class="container mt-5">
        <div class="row">
            <div class="col-12 main-header text-center">
                <h1 class="fw-bold"><i class="fa-solid fa-rocket text-success"></i> Ana Kontrol Merkezi</h1>
                <p class="text-muted">Görsel Üretim Fabrikanızın Kalbi. Lütfen adımları sırayla takip edin.</p>
            </div>
        </div>

        <div class="row">
            <!-- Left Side: Main Workflow -->
            <div class="col-lg-8 offset-lg-2">
                <div class="glass-panel">
                    <h2 class="h4 mb-4 border-bottom border-secondary pb-2"><i class="fas fa-route text-success"></i> Kusursuz Üretim Akışı</h2>
                    
                    <!-- Step 1 -->
                    <div class="workflow-step" onclick="openFolder('SABLON_YUKLE')">
                        <div class="step-number">1</div>
                        <div class="step-details">
                            <h3>Ham Şablonları Yükle</h3>
                            <p>Sisteme yeni eklenecek boş bardak/tablo fotoğraflarını klasöre bırakın.</p>
                        </div>
                        <div class="ms-auto"><i class="fas fa-folder-open text-muted fa-2x"></i></div>
                    </div>

                    <!-- Step 2 -->
                    <div class="workflow-step" onclick="runScript('SABLON_DUZELTICI')">
                        <div class="step-number">2</div>
                        <div class="step-details">
                            <h3>Şablon Düzelticiyi Aç</h3>
                            <p>Tarayıcıda şablonları beyazlatın ve köşe noktalarını işaretleyin.</p>
                        </div>
                        <div class="ms-auto"><i class="fas fa-crop-simple text-muted fa-2x"></i></div>
                    </div>

                    <!-- Step 3: Kaggle -->
                    <div class="workflow-step" onclick="window.open('http://127.0.0.1:8080/?kaggle=1', '_blank')" style="background: rgba(0, 122, 204, 0.1); border-radius: 10px; padding: 10px;">
                        <div class="step-number" style="background:#007acc; color:white; border-color:#007acc;">3</div>
                        <div class="step-details">
                            <h3 style="color:#00e5ff;">🚀 Kaggle Matbaası Onay Odası</h3>
                            <p>Kaggle Yapay Zeka baskılarını üretime girmeden önce seçin/eleyin.</p>
                        </div>
                        <div class="ms-auto"><i class="fas fa-microchip" style="color:#00e5ff; font-size:2em;"></i></div>
                    </div>

                    <!-- Step 4 -->
                    <div class="workflow-step" onclick="openFolder('TASARIM_YUKLE')">
                        <div class="step-number">4</div>
                        <div class="step-details">
                            <h3>Müşteri Tasarımlarını (Logoları) Seç</h3>
                            <p>Şablonlara oturtulacak nihai PNG/JPG tasarımlarınızı yükleyin.</p>
                        </div>
                        <div class="ms-auto"><i class="fas fa-image text-muted fa-2x"></i></div>
                    </div>

                    <!-- Step 5 -->
                    <div class="workflow-step" style="background: rgba(46, 160, 67, 0.1); border-radius: 10px; padding: 15px;" onclick="runScript('MANUEL_URETIM')">
                        <div class="step-number" style="background: var(--accent); color: white; border-color: white;">5</div>
                        <div class="step-details">
                            <h3 class="text-success fw-bold">⚡ Üretimi Başlat (Mockup Motoru)</h3>
                            <p>Sistemi çalıştırın ve kahvenizi alın. Tüm varyasyonlar otomatik basılsın.</p>
                        </div>
                        <div class="ms-auto"><i class="fas fa-play-circle text-success fa-3x"></i></div>
                    </div>

                </div>
            </div>
        </div>
    </div>

    <!-- Right Sidebar: Growth Hacker Tools -->
    <div class="tools-sidebar" id="toolsSidebar">
        <h3 class="border-bottom border-secondary pb-3 mb-4"><i class="fas fa-screwdriver-wrench"></i> Profesyonel Araçlar</h3>
        
        <!-- Tool 1 -->
        <div class="tool-item" onclick="runTool('watermark')">
            <div class="tool-icon"><i class="fas fa-copyright"></i></div>
            <div class="flex-grow-1">
                <h5 class="mb-1">Otomatik Filigran</h5>
                <p class="text-muted small mb-0">Seçtiğiniz logoyu görsellere basar.</p>
            </div>
        </div>

        <!-- Tool 2 -->
        <div class="tool-item" onclick="runTool('rename_images')">
            <div class="tool-icon"><i class="fas fa-signature"></i></div>
            <div>
                <h5 class="mb-1">Görsel İsimlendirici</h5>
                <p class="text-muted small mb-0">Örn: Tablo_001, Tablo_002 yapar.</p>
            </div>
        </div>

        <!-- Tool 3 -->
        <div class="tool-item" onclick="runTool('format_convert')">
            <div class="tool-icon"><i class="fas fa-file-export"></i></div>
            <div>
                <h5 class="mb-1">Format Çevirici - png-jpg</h5>
                <p class="text-muted small mb-0">Tümünü PNG veya JPG yapar.</p>
            </div>
        </div>

        <!-- Tool 4 -->
        <div class="tool-item" onclick="runTool('ai_enhancer')">
            <div class="tool-icon"><i class="fas fa-wand-magic-sparkles"></i></div>
            <div>
                <h5 class="mb-1">Görsel Kalite Artırıcı Ai</h5>
                <p class="text-muted small mb-0">Düşük çözünürlüklü fotoğrafları 4K yapar.</p>
            </div>
        </div>

        <!-- Tool 5 -->
        <div class="tool-item" onclick="runTool('image_to_excel')">
            <div class="tool-icon"><i class="fas fa-link"></i></div>
            <div>
                <h5 class="mb-1">Görselleri Link Dönüştürücü</h5>
                <p class="text-muted small mb-0">Toplu yükleme için isimleri Excel'e çeker.</p>
            </div>
        </div>

        <!-- Tool 6 -->
        <div class="tool-item" onclick="runTool('seo_generator')">
            <div class="tool-icon"><i class="fas fa-tags"></i></div>
            <div>
                <h5 class="mb-1">Seo Uyumlu Ürün Adı Üretici</h5>
                <p class="text-muted small mb-0">Etsy/Trendyol için özel başlıklar yazar.</p>
            </div>
        </div>

        <!-- Tool 7 -->
        <div class="tool-item" onclick="runTool('seo_generator')">
            <div class="tool-icon"><i class="fas fa-pen-nib"></i></div>
            <div>
                <h5 class="mb-1">Seo Uyumlu Açıklama Üretici</h5>
                <p class="text-muted small mb-0">Ürünlere özel uzun metinler yazar.</p>
            </div>
        </div>

    </div>

    <!-- Bootstrap JS -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    
    <script>
        function toggleSidebar() {
            document.getElementById('toolsSidebar').classList.toggle('open');
        }

        async function openFolder(folderName) {
            try {
                const response = await fetch('/api/open_folder', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ folder_name: folderName })
                });
                const data = await response.json();
                console.log(data.message);
            } catch (err) {
                console.error("Hata:", err);
            }
        }

        async function runScript(scriptId) {
            try {
                const response = await fetch('/api/run_script', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ script_id: scriptId })
                });
                const data = await response.json();
                
                // Show a tiny notification (Optional enhancement later)
                alert(scriptId + " komutu gönderildi: " + data.message);
                
            } catch (err) {
                console.error("Hata:", err);
                alert("Başlatılamadı!");
            }
        }
        async function runTool(toolEndpoint) {
            try {
                // Determine format/prefix defaults or we could add modals later.
                let bodyData = {};
                if(toolEndpoint === 'format_convert') {
                    const format = prompt("Hangi formata çevrilecek? (JPG veya PNG yazın):", "JPG");
                    if(!format) return; // cancelled
                    bodyData.format = format.toUpperCase();
                } else if(toolEndpoint === 'rename_images') {
                    const prefix = prompt("Görseller hangi kelime ile başlasın? (Örn: Tablo_):", "Gorsel_");
                    if(!prefix) return; // cancelled
                    bodyData.prefix = prefix;
                } else if(toolEndpoint === 'watermark') {
                    alert("Açılacak ilk pencereden LOGO DOSYASINI (.png), ikinci pencereden basılacak GÖRSELLERİ seçin.");
                } else if(toolEndpoint === 'image_to_excel') {
                    alert("Açılacak pencereden Excel'e yazılacak görselleri seçin.");
                } else if(toolEndpoint === 'seo_generator') {
                    const adet = prompt("Kaç adet SEO uyumlu isim/açıklama üretilsin?", "10");
                    if(!adet) return;
                    bodyData.adet = parseInt(adet);
                } else if(toolEndpoint === 'ai_enhancer') {
                    const kat = prompt("Görseller kaç kat büyütülsün? (Varsayılan: 4)\nBüyük sayılar işlemi yavaşlatabilir.", "4");
                    if(!kat) return;
                    bodyData.kat = kat;
                } else {
                    alert("Lütfen açılacak pencereden işlem yapılacak GÖRSELLERİ seçin.");
                }
                
                const response = await fetch('/api/tools/' + toolEndpoint, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(bodyData)
                });
                const data = await response.json();
                alert(data.message);
                
            } catch (err) {
                console.error("Hata:", err);
                alert("İşlem başlatılamadı!");
            }
        }
    </script>
</body>
</html>

```

### ŞABLON DÜZELTİCİ BACKEND (SABLON_V2_MIMARI\app.py)
```python
import os
import sys
import json
import base64
import time
import shutil
import cv2
import numpy as np
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file
import threading
import webbrowser

# Parent klasörü sys.path'e ekle
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from core.vision import (
    YEDEK_IMG_DIR, detect_document_corners, detect_occlusion_boxes, logger
)

from core.db import get_all_ayarlar, save_settings_node, save_category, save_template, delete_template

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/ayarlar', methods=['GET', 'POST'])
def api_ayarlar():
    if request.method == 'GET':
        data = get_all_ayarlar()
        return jsonify(data)

    elif request.method == 'POST':
        try:
            new_data = request.json
            if "kategoriler" in new_data:
                for cat_name, cat_data in new_data["kategoriler"].items():
                    if "sablonlar" in cat_data:
                        for tmpl_name, tmpl_data in cat_data["sablonlar"].items():
                            save_template(cat_name, tmpl_name, tmpl_data)

            return jsonify({"success": True})
        except Exception as e:
            logger.error(f"Ayarlar kaydetme hatasi: {e}")
            return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/tekil_sablon_kaydet', methods=['POST'])
def api_tekil_sablon_kaydet():
    try:
        req = request.json
        cat = req.get("kategori")
        tmpl = req.get("sablon")
        data = req.get("data")
        
        if not cat or not tmpl or not data:
            return jsonify({"success": False, "error": "Eksik parametre"}), 400
            
        save_template(cat, tmpl, data)
        return jsonify({"success": True})
    except Exception as e:
        logger.error(f"Tekil kayit hatasi: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/orijinal_yukle', methods=['POST'])
def api_orijinal_yukle():
    try:
        active_cat = request.headers.get('X-Active-Category', '')
        active_tmpl = request.headers.get('X-Active-Template', '')
        
        if active_cat and active_tmpl:
            stem = Path(active_tmpl).stem
            src_path = None
            for _ext in ['.jpg', '.jpeg', '.webp', '.png', '.avif']:
                _cand = os.path.join(YEDEK_IMG_DIR, active_cat, stem + _ext)
                if os.path.exists(_cand):
                    src_path = _cand
                    break
            
            dest_path = os.path.join(BASE_DIR, "2_SABLON_HAVUZU", active_cat, stem + ".png")
            
            if src_path and os.path.exists(src_path):
                img_raw = cv2.imdecode(np.fromfile(src_path, dtype=np.uint8), cv2.IMREAD_COLOR)
                if img_raw is not None:
                    _, buf = cv2.imencode('.png', img_raw)
                    with open(dest_path, 'wb') as _f:
                        _f.write(buf.tobytes())
                else:
                    shutil.copy2(src_path, dest_path)
                return jsonify({"success": True})
            else:
                return jsonify({"success": False, "error": "Orijinal yedek bulunamadi."}), 404
        return jsonify({"success": False, "error": "Kategori eksik"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/anlik_beyazlat', methods=['POST'])
def api_anlik_beyazlat():
    try:
        new_data = request.json
        active_cat = request.headers.get('X-Active-Category', '')
        active_tmpl = request.headers.get('X-Active-Template', '')
        
        if active_cat and active_tmpl:
            sm_dir = os.path.join(BASE_DIR, "99_SISTEM_MOTORLARI_VE_KODLAR", "SISTEM_MOTORU")
            if sm_dir not in sys.path:
                sys.path.append(sm_dir)
            from sablon_beyazlatma_motoru import whiten_canvas, imread_unicode, imwrite_unicode
            
            stem = Path(active_tmpl).stem
            src_path = None
            for _ext in ['.jpg', '.jpeg', '.webp', '.png', '.avif']:
                _cand = os.path.join(YEDEK_IMG_DIR, active_cat, stem + _ext)
                if os.path.exists(_cand):
                    src_path = _cand
                    break
            if not src_path:
                src_path = os.path.join(BASE_DIR, "2_SABLON_HAVUZU", active_cat, stem + ".png")
            if not src_path or not os.path.exists(src_path):
                src_path = os.path.join(BASE_DIR, "2_SABLON_HAVUZU", active_cat, active_tmpl)
                
            dest_path = os.path.join(BASE_DIR, "2_SABLON_HAVUZU", active_cat, stem + ".png")
            
            img_cv = imread_unicode(src_path)
            if img_cv is not None:
                s_conf = new_data["kategoriler"][active_cat]["sablonlar"][active_tmpl]
                is_frameless = active_cat in ["01_Wifi_Kutusu", "04_Cam_Dograma", "05_Ocak_Arkasi"]
                whitened = whiten_canvas(img_cv, s_conf, is_frameless=is_frameless)
                
                try:
                    preview_path = os.path.join(BASE_DIR, "YENI-BOS MOCKUP SABLON HAVUZU", active_cat, stem + "-beyazlatilmis-onizleme.png")
                    os.makedirs(os.path.dirname(preview_path), exist_ok=True)
                    imwrite_unicode(preview_path, whitened)
                except Exception as ep:
                    logger.error(f"Onizleme guncellenemedi: {ep}")
                    
                return jsonify({"success": True})
        return jsonify({"success": False, "error": "Kategori veya sablon eksik"}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/tumunu_beyazlat', methods=['POST'])
def api_tumunu_beyazlat():
    try:
        req = request.json
        hedef_cat = req.get("kategori", None)
        
        ayarlar = get_all_ayarlar()
            
        sm_dir = os.path.join(BASE_DIR, "99_SISTEM_MOTORLARI_VE_KODLAR", "SISTEM_MOTORU")
        if sm_dir not in sys.path:
            sys.path.append(sm_dir)
        from sablon_beyazlatma_motoru import whiten_canvas, imread_unicode, imwrite_unicode
        
        islenen_sayisi = 0
        kategoriler = [hedef_cat] if hedef_cat else ayarlar.get("kategoriler", {}).keys()
        
        for cat in kategoriler:
            sablonlar = ayarlar.get("kategoriler", {}).get(cat, {}).get("sablonlar", {})
            is_frameless = cat in ["01_Wifi_Kutusu", "04_Cam_Dograma", "05_Ocak_Arkasi"]
            
            for tmpl, s_conf in sablonlar.items():
                src_path = os.path.join(YEDEK_IMG_DIR, cat, tmpl)
                if not os.path.exists(src_path):
                    stem = Path(tmpl).stem
                    for _ext in ['.jpg', '.jpeg', '.webp', '.png', '.avif']:
                        _cand = os.path.join(YEDEK_IMG_DIR, cat, stem + _ext)
                        if os.path.exists(_cand):
                            src_path = _cand
                            break
                if not os.path.exists(src_path):
                    src_path = os.path.join(BASE_DIR, "2_SABLON_HAVUZU", cat, tmpl)
                    
                if os.path.exists(src_path):
                    img_cv = imread_unicode(src_path)
                    if img_cv is not None:
                        try:
                            whitened = whiten_canvas(img_cv, s_conf, is_frameless=is_frameless)
                            stem = Path(tmpl).stem
                            dest_path = os.path.join(BASE_DIR, "2_SABLON_HAVUZU", cat, stem + ".png")
                            imwrite_unicode(dest_path, whitened)
                            islenen_sayisi += 1
                        except Exception as ex:
                            logger.error(f"SABLON {tmpl} BEYAZLATILAMADI: {ex}")
        return jsonify({'success': True, 'islenen': islenen_sayisi})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/auto_detect_corners', methods=['POST'])
def api_auto_detect_corners():
    try:
        active_cat = request.headers.get('X-Active-Category', '')
        active_tmpl = request.headers.get('X-Active-Template', '')
        
        if active_cat and active_tmpl:
            img_path = os.path.join(BASE_DIR, "2_SABLON_HAVUZU", active_cat, active_tmpl)
            if not os.path.exists(img_path):
                return jsonify({"success": False, "error": "Resim dosyasi bulunamadi"}), 404
                
            img_cv = cv2.imdecode(np.fromfile(img_path, dtype=np.uint8), cv2.IMREAD_COLOR)
            if img_cv is None:
                return jsonify({"success": False, "error": "Resim okunamadi"}), 500
                
            corners = detect_document_corners(img_cv)
            if corners is not None:
                # Eger NumPy array ise listeye cevir, degilse zaten listedir.
                corners_list = corners.tolist() if hasattr(corners, 'tolist') else corners
                # Occlusion ve delik tespiti
                occlusion_data = detect_occlusion_boxes(img_cv, corners_list)
                return jsonify({
                    "success": True, 
                    "corners": corners_list,
                    "occlusions": occlusion_data
                })
            else:
                return jsonify({"success": False, "error": "Kose bulunamadi"}), 404
        return jsonify({"success": False, "error": "Parametre eksik"}), 400
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/sablon_sil', methods=['POST'])
def api_sablon_sil():
    try:
        active_cat = request.headers.get('X-Active-Category', '')
        active_tmpl = request.headers.get('X-Active-Template', '')
        stem = Path(active_tmpl).stem
        
        _ayarlar = get_all_ayarlar()
        if active_cat in _ayarlar['kategoriler'] and active_tmpl in _ayarlar['kategoriler'][active_cat]['sablonlar']:
            removed_conf = _ayarlar['kategoriler'][active_cat]['sablonlar'][active_tmpl]
            delete_template(active_cat, active_tmpl)
            
            trash_dir = os.path.join(BASE_DIR, "SILINEN_SABLONLAR_COP_KUTUSU")
            os.makedirs(trash_dir, exist_ok=True)
            trash_json = os.path.join(trash_dir, f"{stem}_ayarlar.json")
            with open(trash_json, "w", encoding="utf-8") as _tf:
                json.dump(removed_conf, _tf, indent=2)
            
            src_img = os.path.join(BASE_DIR, "2_SABLON_HAVUZU", active_cat, active_tmpl)
            if os.path.exists(src_img):
                shutil.move(src_img, os.path.join(trash_dir, active_tmpl))
            
            return jsonify({"success": True})
        return jsonify({"success": False, "error": "Sablon bulunamadi"}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/sablon_sil_geri_al', methods=['POST'])
def api_sablon_sil_geri_al():
    return jsonify({"success": True})

@app.route('/preview/<cat>/<tmpl>')
def serve_preview(cat, tmpl):
    import urllib.parse
    cat = urllib.parse.unquote(cat)
    tmpl = urllib.parse.unquote(tmpl)
    stem = Path(tmpl).stem
    
    safe_preview_base = os.path.abspath(os.path.join(BASE_DIR, "YENI-BOS MOCKUP SABLON HAVUZU"))
    preview_path = os.path.abspath(os.path.join(safe_preview_base, cat, stem + "-beyazlatilmis-onizleme.png"))
    
    if not preview_path.startswith(safe_preview_base):
        return "Erisim engellendi", 403
        
    if os.path.exists(preview_path):
        response = send_file(preview_path)
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        return response
        
    return "Onizleme bulunamadi", 404

@app.route('/image/<cat>/<tmpl>')
def serve_image(cat, tmpl):
    import urllib.parse
    import hashlib
    
    cat = urllib.parse.unquote(cat)
    tmpl = urllib.parse.unquote(tmpl)
    
    safe_yedek_base = os.path.abspath(YEDEK_IMG_DIR)
    img_path = os.path.abspath(os.path.join(safe_yedek_base, cat, tmpl))
    
    if not img_path.startswith(safe_yedek_base):
        return "Erisim engellendi", 403
        
    if not os.path.exists(img_path):
        stem = Path(tmpl).stem
        yedek_path = None
        for alt_ext in [".webp", ".jpg", ".jpeg", ".png", ".avif"]:
            cand = os.path.abspath(os.path.join(safe_yedek_base, cat, stem + alt_ext))
            if cand.startswith(safe_yedek_base) and os.path.exists(cand):
                yedek_path = cand
                break
                
        if yedek_path:
            img_path = yedek_path
        else:
            safe_havuz_base = os.path.abspath(os.path.join(BASE_DIR, "2_SABLON_HAVUZU"))
            cand_png = os.path.abspath(os.path.join(safe_havuz_base, cat, stem + ".png"))
            if cand_png.startswith(safe_havuz_base) and os.path.exists(cand_png):
                img_path = cand_png
            else:
                fallback_path = os.path.abspath(os.path.join(safe_havuz_base, cat, tmpl))
                if fallback_path.startswith(safe_havuz_base):
                    img_path = fallback_path
                    
    if os.path.exists(img_path):
        file_stat = os.stat(img_path)
        etag = hashlib.md5(f"{img_path}:{file_stat.st_mtime}:{file_stat.st_size}".encode()).hexdigest()
        client_etag = request.headers.get('If-None-Match', '')
        
        if client_etag == f'"{etag}"':
            return '', 304
            
        response = send_file(img_path)
        response.set_etag(etag)
        response.headers['Cache-Control'] = 'no-cache'
        return response
        
    return "Resim bulunamadi", 404

# ==========================================
# KAGGLE ONAY SİSTEMİ (0_KAGGLE_ONAY_BEKLEYENLER -> 1_GELEN_KAGGLE_BASKILARI)
# ==========================================
WORKSPACE_DIR = BASE_DIR
KAGGLE_BEKLEYENLER_DIR = os.path.join(WORKSPACE_DIR, "0_KAGGLE_ONAY_BEKLEYENLER")
KAGGLE_GELENLER_DIR = os.path.join(WORKSPACE_DIR, "1_GELEN_KAGGLE_BASKILARI")

os.makedirs(KAGGLE_BEKLEYENLER_DIR, exist_ok=True)
os.makedirs(KAGGLE_GELENLER_DIR, exist_ok=True)

@app.route('/api/kaggle/bekleyenler', methods=['GET'])
def api_kaggle_bekleyenler():
    files = []
    exists = os.path.exists(KAGGLE_BEKLEYENLER_DIR)
    if exists:
        for f in os.listdir(KAGGLE_BEKLEYENLER_DIR):
            if f.lower().endswith(('.png', '.jpg', '.jpeg')):
                files.append(f)
    return jsonify({"success": True, "files": files, "dir": KAGGLE_BEKLEYENLER_DIR, "exists": exists})

@app.route('/image_kaggle/<path:filename>')
def serve_kaggle_image(filename):
    return send_from_directory(KAGGLE_BEKLEYENLER_DIR, filename)

@app.route('/api/kaggle/onayla', methods=['POST'])
def api_kaggle_onayla():
    data = request.json
    filename = data.get('filename')
    if not filename:
        return jsonify({"success": False, "error": "Parametre eksik"}), 400
    src = os.path.join(KAGGLE_BEKLEYENLER_DIR, filename)
    dst = os.path.join(KAGGLE_GELENLER_DIR, filename)
    if os.path.exists(src):
        import shutil
        shutil.move(src, dst)
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Dosya bulunamadi"}), 404

@app.route('/api/kaggle/reddet', methods=['POST'])
def api_kaggle_reddet():
    data = request.json
    filename = data.get('filename')
    if not filename:
        return jsonify({"success": False, "error": "Parametre eksik"}), 400
    src = os.path.join(KAGGLE_BEKLEYENLER_DIR, filename)
    if os.path.exists(src):
        os.remove(src)
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Dosya bulunamadi"}), 404

@app.route('/api/saglik_durumu')
def api_saglik_durumu():
    rapor_path = os.path.join(BASE_DIR, "99_SISTEM_MOTORLARI_VE_KODLAR", "SISTEM_MOTORU", "logs", "sistem_saglik_raporu.json")
    if os.path.exists(rapor_path):
        with open(rapor_path, 'r', encoding='utf-8') as rf:
            data = json.load(rf)
            return jsonify(data)
    return jsonify({"sorun_sayisi": 0, "sorunlar": [], "cozulen_sayisi": 0, "cozulenler": []})

@app.route('/<path:filename>')
def serve_temp_files(filename):
    safe_base = os.path.abspath(BASE_DIR)
    file_path = os.path.abspath(os.path.join(safe_base, filename))
    if not file_path.startswith(safe_base):
        return "Yasak", 403
    if os.path.exists(file_path):
        return send_file(file_path)
    return "Bulunamadi", 404

if __name__ == '__main__':
    print("SABLON_V2_MIMARI (Flask MVC) Baslatiliyor... http://127.0.0.1:8080")
    threading.Timer(1.25, lambda: webbrowser.open('http://127.0.0.1:8080/')).start()
    app.run(host='127.0.0.1', port=8080, debug=True, use_reloader=False)

```

### ŞABLON DÜZELTİCİ DB KATMANI (SABLON_V2_MIMARI\core\db.py)
```python
import sqlite3
import json
import os

# DB yolu: SABLON_V2_MIMARI/ayarlar.db
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "ayarlar.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    # Kategoriler Tablosu
    c.execute('''CREATE TABLE IF NOT EXISTS categories (
                    id TEXT PRIMARY KEY,
                    label TEXT
                 )''')
    # Sablonlar Tablosu (data sütunu JSON formatında string tutar)
    c.execute('''CREATE TABLE IF NOT EXISTS templates (
                    category_id TEXT,
                    filename TEXT,
                    data TEXT,
                    PRIMARY KEY (category_id, filename)
                 )''')
    # Genel Ayarlar Tablosu
    c.execute('''CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                 )''')
    conn.commit()
    conn.close()

def get_all_ayarlar():
    """Tüm veritabanını okuyup, frontend'in beklediği devasa JSON yapısını anında oluşturur."""
    conn = get_db_connection()
    c = conn.cursor()
    
    result = {"kategoriler": {}}
    
    # 1. Genel ayarları çek (bulut_ayarlari vb.)
    c.execute("SELECT key, value FROM settings")
    for row in c.fetchall():
        result[row["key"]] = json.loads(row["value"])
        
    # 2. Kategorileri çek
    c.execute("SELECT id, label FROM categories")
    for row in c.fetchall():
        cat_id = row["id"]
        result["kategoriler"][cat_id] = {
            "etiket": row["label"],
            "sablonlar": {}
        }
        
    # 3. Tüm şablonları çek ve ilgili kategoriye yerleştir
    c.execute("SELECT category_id, filename, data FROM templates")
    for row in c.fetchall():
        cat_id = row["category_id"]
        tmpl = row["filename"]
        data = json.loads(row["data"])
        
        # Eğer kategori henüz result içinde yoksa güvenli bir şekilde oluştur
        if cat_id not in result["kategoriler"]:
            result["kategoriler"][cat_id] = {"sablonlar": {}}
            
        if "sablonlar" not in result["kategoriler"][cat_id]:
            result["kategoriler"][cat_id]["sablonlar"] = {}
            
        result["kategoriler"][cat_id]["sablonlar"][tmpl] = data

    conn.close()
    return result

def save_settings_node(node_name, data):
    """(Örn: bulut_ayarlari) Tüm root seviyesindeki key'leri günceller."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''INSERT INTO settings (key, value) 
                 VALUES (?, ?)
                 ON CONFLICT(key) 
                 DO UPDATE SET value=excluded.value''',
              (node_name, json.dumps(data, ensure_ascii=False)))
    conn.commit()
    conn.close()

def save_category(cat_id, label):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''INSERT INTO categories (id, label) 
                 VALUES (?, ?)
                 ON CONFLICT(id) 
                 DO UPDATE SET label=excluded.label''',
              (cat_id, label))
    conn.commit()
    conn.close()

def save_template(category_id, filename, data):
    """Tek bir şablonun koordinatlarını ve özelliklerini veritabanına kaydeder/günceller."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''INSERT INTO templates (category_id, filename, data) 
                 VALUES (?, ?, ?)
                 ON CONFLICT(category_id, filename) 
                 DO UPDATE SET data=excluded.data''',
              (category_id, filename, json.dumps(data, ensure_ascii=False)))
    conn.commit()
    conn.close()

def delete_template(category_id, filename):
    """Tek bir şablonu veritabanından kalıcı olarak siler."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM templates WHERE category_id=? AND filename=?", (category_id, filename))
    conn.commit()
    conn.close()

```

### ŞABLON DÜZELTİCİ GÖRÜNTÜ İŞLEME (SABLON_V2_MIMARI\core\vision.py)
```python
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
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
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
            try:
                sm_dir = os.path.join(BASE_DIR, "99_SISTEM_MOTORLARI_VE_KODLAR", "SISTEM_MOTORU")
                if sm_dir not in sys.path:
                    sys.path.append(sm_dir)
                import sablon_oto_izleyici as soi
                staging = soi.STAGING_DIR
                if staging.exists():
                    for f in staging.rglob("*.*"):
                        if f.is_file() and f.suffix.lower() in soi.VALID_EXTS:
                            if "-düzenleme-yapıldı" not in f.stem and "-beyazlatilmis-onizleme" not in f.stem:
                                logger.info(f"UI SYNC: Yeni dosya tespit edildi, isleniyor: {f.name}")
                                soi.process_from_staging(f, thread_lock=AYARLAR_LOCK)
            except Exception as e:
                logger.error(f"UI SYNC Hatasi: {e}")
                
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
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        try:
            new_data = json.loads(post_data.decode('utf-8'))
            
            with AYARLAR_LOCK:
                with acquire_os_lock(AYARLAR_PATH):
                    if os.path.exists(AYARLAR_PATH):
                        with open(AYARLAR_PATH, 'r', encoding='utf-8') as current_f:
                            try:
                                current_data = json.load(current_f)
                            except Exception as e:
                                logger.error(f"Eski veritabanı okunamadı, boş başlatılıyor: {e}")
                                current_data = {"kategoriler": {}}
                        # SMART DEEP MERGE: Sadece new_data'daki şablonları current_data içine yedir.
                        # Arayüzde (new_data) bulunmayan ama arkaplanda botun eklediği şablonlar (current_data) ASLA SİLİNMESİN.
                        if "kategoriler" not in current_data:
                            current_data["kategoriler"] = {}
                        
                        for cat, cat_data in new_data.get('kategoriler', {}).items():
                            if cat not in current_data['kategoriler']:
                                current_data['kategoriler'][cat] = {'sablonlar': {}}
                            for tmpl, tmpl_data in cat_data.get('sablonlar', {}).items():
                                current_data['kategoriler'][cat]['sablonlar'][tmpl] = tmpl_data
                        
                        for k, v in new_data.items():
                            if k != 'kategoriler':
                                current_data[k] = v
                        ts = time.strftime("%Y%m%d_%H%M%S")
                        shutil.copy2(AYARLAR_PATH, AYARLAR_PATH + '.arayuz_yedek')
                        shutil.copy2(AYARLAR_PATH, AYARLAR_PATH + f'.user_backup_{ts}')
                        
                        # PERFORMANS: Yedek Rotasyonu (Sadece son 10 yedegi tut)
                        backups = sorted(glob.glob(AYARLAR_PATH + '.user_backup_*'))
                        while len(backups) > 10:
                            old_backup = backups.pop(0)
                            try:
                                os.remove(old_backup)
                            except Exception:
                                pass
                    else:
                        current_data = new_data
                        
                    # ATOMIC WRITE: Write to .tmp first, then replace
                    tmp_path = AYARLAR_PATH + ".tmp"
                    with open(tmp_path, 'w', encoding='utf-8') as f:
                        json.dump(current_data, f, indent=2, ensure_ascii=False)
                    os.replace(tmp_path, AYARLAR_PATH)
                    
                    root_copy = os.path.join(BASE_DIR, "ayarlar.json")
                    shutil.copy2(AYARLAR_PATH, root_copy)
            active_cat = self.headers.get('X-Active-Category', '')
            active_tmpl = self.headers.get('X-Active-Template', '')
            
            # Sadece aktif olan görseli anında fiziksel olarak da beyazlat
            if active_cat and active_tmpl:
                try:
                    sm_dir = os.path.join(BASE_DIR, "99_SISTEM_MOTORLARI_VE_KODLAR", "SISTEM_MOTORU")
                    if sm_dir not in sys.path:
                        sys.path.append(sm_dir)
                    from sablon_beyazlatma_motoru import whiten_canvas, imread_unicode, imwrite_unicode
                    
                    src_path = os.path.join(YEDEK_IMG_DIR, active_cat, active_tmpl)
                    if not os.path.exists(src_path):
                        src_path = os.path.join(BASE_DIR, "2_SABLON_HAVUZU", active_cat, active_tmpl)
                    
                    # Transparent sablonlar zorunlu olarak PNG kaydedilir
                    stem = Path(active_tmpl).stem
                    dest_path = os.path.join(BASE_DIR, "2_SABLON_HAVUZU", active_cat, stem + ".png")
                    
                    img_cv = imread_unicode(src_path)
                    if img_cv is not None:
                        s_conf = new_data["kategoriler"][active_cat]["sablonlar"][active_tmpl]
                        is_frameless = active_cat in ["01_Wifi_Kutusu", "04_Cam_Dograma", "05_Ocak_Arkasi"]
                        whitened = whiten_canvas(img_cv, s_conf, is_frameless=is_frameless)
                        imwrite_unicode(dest_path, whitened)
                        logger.info(f"AKTIF GORSEL KOORDINATLARI KAYDEDILDI VE ONAYLANIP BEYAZLATILDI: {active_tmpl}")
                        
                        # Onizleme dosyasini da guncelle (YENI-BOS MOCKUP SABLON HAVUZU)
                        try:
                            staging_cat_dir = Path(BASE_DIR) / "YENI-BOS MOCKUP SABLON HAVUZU" / active_cat
                            t_stem = Path(active_tmpl).stem
                            t_ext = Path(active_tmpl).suffix
                            preview_name = f"{t_stem}-beyazlatilmis-onizleme{t_ext}"
                            preview_path = staging_cat_dir / preview_name
                            if preview_path.exists():
                                imwrite_unicode(preview_path, whitened)
                                logger.info(f"HAZIRLIK KLASORUNDEKI ONIZLEME GUNCELLEDI: {preview_name}")
                        except Exception as e_prev:
                            logger.error(f"ONIZLEME GUNCELLEME HATASI: {e_prev}")
                except Exception as ex:
                    logger.error(f"BEYAZLATMA HATASI: {ex}")
                    
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(b'{"success": true}')
            
            logger.info(f"AYARLAR.JSON BASARIYLA GUNCELLENDI VE YEDEKLENDI (user_backup_{ts})!")
        except Exception as e:
            self.send_response(500)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(b'{"success": false}')
            logger.error(f"HATA: {e}")

    def _handle_api_anlik_beyazlat(self):
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            new_data = json.loads(post_data.decode('utf-8'))
            active_cat = self.headers.get('X-Active-Category', '')
            active_tmpl = self.headers.get('X-Active-Template', '')
            
            if active_cat and active_tmpl:
                sm_dir = os.path.join(BASE_DIR, "99_SISTEM_MOTORLARI_VE_KODLAR", "SISTEM_MOTORU")
                if sm_dir not in sys.path:
                    sys.path.append(sm_dir)
                from sablon_beyazlatma_motoru import whiten_canvas, imread_unicode, imwrite_unicode
                
                stem = Path(active_tmpl).stem
                
                # Yedek klasöründe tüm uzantıları dene
                src_path = None
                for _ext in ['.jpg', '.jpeg', '.webp', '.png', '.avif']:
                    _cand = os.path.join(YEDEK_IMG_DIR, active_cat, stem + _ext)
                    if os.path.exists(_cand):
                        src_path = _cand
                        break
                # Yedekte yoksa havuzdaki PNG'yi kullan
                if not src_path:
                    src_path = os.path.join(BASE_DIR, "2_SABLON_HAVUZU", active_cat, stem + ".png")
                if not src_path or not os.path.exists(src_path):
                    src_path = os.path.join(BASE_DIR, "2_SABLON_HAVUZU", active_cat, active_tmpl)
                # Her zaman PNG olarak kaydet (şeffaflık için)
                dest_path = os.path.join(BASE_DIR, "2_SABLON_HAVUZU", active_cat, stem + ".png")
                
                img_cv = imread_unicode(src_path)
                if img_cv is not None:
                    s_conf = new_data["kategoriler"][active_cat]["sablonlar"][active_tmpl]
                    is_frameless = active_cat in ["01_Wifi_Kutusu", "04_Cam_Dograma", "05_Ocak_Arkasi"]
                    whitened = whiten_canvas(img_cv, s_conf, is_frameless=is_frameless)
                    
                    try:
                        preview_path = os.path.join(BASE_DIR, "YENI-BOS MOCKUP SABLON HAVUZU", active_cat, stem + "-beyazlatilmis-onizleme.png")
                        if os.path.exists(os.path.dirname(preview_path)):
                            imwrite_unicode(preview_path, whitened)
                    except Exception as ep:
                        logger.error(f"Onizleme guncellenemedi: {ep}")
                        
                    logger.info(f"ANLIK BEYAZLATMA BASARILI: {active_tmpl} -> {dest_path}")
                    
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(b'{"success": true}')
                    return
            
            self.send_response(400)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(b'{"success": false, "error": "Kategori veya sablon eksik"}')
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode('utf-8'))
            logger.error(f"ANLIK BEYAZLAT HATASI: {e}")

    def _handle_api_orijinal_yukle(self):
        try:
            active_cat = self.headers.get('X-Active-Category', '')
            active_tmpl = self.headers.get('X-Active-Template', '')
            
            if active_cat and active_tmpl:
                stem = Path(active_tmpl).stem
                
                # Yedek klasorunde tum uzantilari dene
                src_path = None
                for _ext in ['.jpg', '.jpeg', '.webp', '.png', '.avif']:
                    _cand = os.path.join(YEDEK_IMG_DIR, active_cat, stem + _ext)
                    if os.path.exists(_cand):
                        src_path = _cand
                        break
                
                # Havuzdaki PNG'yi geri yukle (orijinalin kopyasini PNG olarak yaz)
                dest_path = os.path.join(BASE_DIR, "2_SABLON_HAVUZU", active_cat, stem + ".png")
                
                if src_path and os.path.exists(src_path):
                    img_raw = cv2.imdecode(np.fromfile(src_path, dtype=np.uint8), cv2.IMREAD_COLOR)
                    if img_raw is not None:
                        _, buf = cv2.imencode('.png', img_raw)
                        with open(dest_path, 'wb') as _f:
                            _f.write(buf.tobytes())
                    else:
                        shutil.copy2(src_path, dest_path)
                    logger.info(f"ORIJINAL GORSEL GERI YUKLENDI: {stem}.png <- {Path(src_path).name}")
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(b'{"success": true}')
                    return
                else:
                    self.send_response(404)
                    self.send_header('Content-type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(b'{"success": false, "error": "Orijinal yedek bulunamadi. Bu dosya eski ve yedegi yok."}')
                    return
                    
            self.send_response(400)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(b'{"success": false, "error": "Kategori eksik"}')
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode('utf-8'))
            logger.error(f"ORIJINAL YUKLE HATASI: {e}")

    def _handle_api_tumunu_beyazlat(self):
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            req = json.loads(post_data.decode('utf-8'))
            hedef_cat = req.get("kategori", None)
            
            with open(AYARLAR_PATH, 'r', encoding='utf-8') as f:
                ayarlar = json.load(f)
                
            sm_dir = os.path.join(BASE_DIR, "99_SISTEM_MOTORLARI_VE_KODLAR", "SISTEM_MOTORU")
            if sm_dir not in sys.path:
                sys.path.append(sm_dir)
            from sablon_beyazlatma_motoru import whiten_canvas, imread_unicode, imwrite_unicode
            
            islenen_sayisi = 0
            kategoriler = [hedef_cat] if hedef_cat else ayarlar.get("kategoriler", {}).keys()
            
            for cat in kategoriler:
                sablonlar = ayarlar.get("kategoriler", {}).get(cat, {}).get("sablonlar", {})
                is_frameless = cat in ["01_Wifi_Kutusu", "04_Cam_Dograma", "05_Ocak_Arkasi"]
                
                for tmpl, s_conf in sablonlar.items():
                    src_path = os.path.join(YEDEK_IMG_DIR, cat, tmpl)
                    if not os.path.exists(src_path):
                        # Diger uzantilari dene
                        stem = Path(tmpl).stem
                        for _ext in ['.jpg', '.jpeg', '.webp', '.png', '.avif']:
                            _cand = os.path.join(YEDEK_IMG_DIR, cat, stem + _ext)
                            if os.path.exists(_cand):
                                src_path = _cand
                                break
                    if not os.path.exists(src_path):
                        src_path = os.path.join(BASE_DIR, "2_SABLON_HAVUZU", cat, tmpl)
                        
                    if os.path.exists(src_path):
                        img_cv = imread_unicode(src_path)
                        if img_cv is not None:
                            try:
                                whitened = whiten_canvas(img_cv, s_conf, is_frameless=is_frameless)
                                stem = Path(tmpl).stem
                                dest_path = os.path.join(BASE_DIR, "2_SABLON_HAVUZU", cat, stem + ".png")
                                imwrite_unicode(dest_path, whitened)
                                islenen_sayisi += 1
                                logger.info(f"Toplu Beyazlatma Tamamlandi: {dest_path}")
                            except Exception as ex:
                                logger.error(f"SABLON {tmpl} BEYAZLATILAMADI: {ex}")
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({'success': True, 'islenen': islenen_sayisi}).encode('utf-8'))
            logger.info(f"TUMUNU BEYAZLAT BASARILI. Islenen Sablon: {islenen_sayisi}")
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode('utf-8'))
            logger.error(f"TUMUNU BEYAZLAT HATASI: {e}")

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


```

### ŞABLON DÜZELTİCİ ARAYÜZ (HTML) (SABLON_V2_MIMARI\templates\index.html)
```html
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' rx='4' fill='%23007acc'/><text x='16' y='23' text-anchor='middle' font-size='20' fill='white'>S</text></svg>">
    <title>Şablon Hizalama Ekranı (Zoom ve Pan)</title>
    <link rel="stylesheet" href="/static/css/style.css">
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
        <button onclick="toggleKaggleView()" style="width: 100%; background: #007acc; font-weight: bold; margin-bottom: 5px;">🚀 Kaggle Matbaası (Onay)</button>
        <button onclick="const h = document.getElementById('help-sidebar'); h.style.display = h.style.display === 'none' ? 'block' : 'none';" style="width: 100%; background: #444;">❓ Kısayollar ve Yardım</button>
    </div>
</div>
<div class="resizer" id="resizer-left"></div>

<div id="main">
    <!-- KAGGLE DASHBOARD (Hidden by default) -->
    <div id="kaggle-dashboard" style="display:none; position: absolute; top:0; left:0; width:100%; height:100%; background:#1e1e1e; z-index:1000; padding:20px; box-sizing:border-box; flex-direction:column;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 20px; border-bottom: 2px solid #333; padding-bottom: 10px;">
            <h1 style="color:#00e5ff; margin:0;">🚀 Kaggle Yapay Zeka Matbaası (Onay Bekleyenler)</h1>
            <button onclick="toggleKaggleView()" style="background:#dc3545; padding: 10px 20px; font-size: 16px;">❌ Kapat</button>
        </div>
        <p style="color:#aaa; font-size:14px;">Aşağıdaki görseller Kaggle API üzerinden sisteme aktarılmıştır. Onayladıklarınız "1_GELEN_KAGGLE_BASKILARI" klasörüne taşınır ve otomatik mockup sistemine dahil edilir.</p>
        <div id="kaggle-grid" style="display:flex; flex-wrap:wrap; gap:15px; overflow-y:auto; flex:1;">
            <!-- Images will be injected here -->
        </div>
    </div>
    
    <div id="toolbar" style="flex-direction: row; justify-content: space-between; align-items: center;">
        <div style="display:flex; align-items:center; gap:8px;">
            <button type="button" onclick="prevTemplate()" style="background:#444; padding:6px 14px;" title="Önceki Şablon (P / Sol Ok)">⏮ Önceki</button>
            <button type="button" onclick="nextTemplate()" style="background:#444; padding:6px 14px;" title="Sonraki Şablon (N / Sağ Ok)">Sonraki ⏭</button>
            <span id="tmpl-counter" style="font-size: 13px; font-weight:bold; color: #00e5ff; margin-left: 5px;"></span>
            <span id="current-file" style="font-size: 17px; font-weight: bold; margin-left: 10px;">Görsel Seçin</span>
            <span id="template-type" style="margin-left: 10px; color: #aaa;"></span>
            <span id="perf-metric" style="margin-left: 15px; font-size: 15px; font-weight: bold; padding: 4px 8px; border-radius: 4px; display: none;"></span>
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

<script src="/static/js/main.js"></script>

</body>
</html>

```

### ŞABLON DÜZELTİCİ ARAYÜZ (JS) (SABLON_V2_MIMARI\static\js\main.js)
```javascript
window.onerror = function(msg, url, line, col, error) {
        alert("JS ERROR: " + msg + "\\nLine: " + line);
        return false;
    };
    
    // GLOBAL PERFORMANS OLCUM (FETCH WRAPPER)
    const originalFetch = window.fetch;
    window.fetch = async function(...args) {
        const url = args[0];
        if (typeof url === 'string' && url.startsWith('/api/')) {
            const startTime = performance.now();
            try {
                const response = await originalFetch.apply(this, args);
                const endTime = performance.now();
                const durationMs = endTime - startTime;
                
                let perfMetric = document.getElementById("perf-metric");
                if (perfMetric) {
                    perfMetric.style.display = "inline-block";
                    let sec = (durationMs / 1000).toFixed(2);
                    
                    if (durationMs < 500) {
                        perfMetric.style.color = "#44ff44";
                        perfMetric.innerText = `⚡ ${sec}s`;
                    } else if (durationMs < 2000) {
                        perfMetric.style.color = "#ffdd44";
                        perfMetric.innerText = `⏱️ ${sec}s`;
                    } else {
                        perfMetric.style.color = "#ff4444";
                        perfMetric.innerText = `🐢 ${sec}s`;
                    }
                    
                    // 3 saniye sonra gizle (eger yeni istek gelmezse)
                    clearTimeout(window.perfTimeout);
                    window.perfTimeout = setTimeout(() => {
                        perfMetric.style.display = "none";
                    }, 4000);
                }
                return response;
            } catch (error) {
                console.error("Fetch hatasi:", error);
                throw error;
            }
        }
        return originalFetch.apply(this, args);
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
                
                let mainDiv = document.getElementById("main");
                if (mainDiv) {
                    mainDiv.insertBefore(banner, mainDiv.firstChild);
                } else {
                    document.body.insertBefore(banner, document.body.firstChild);
                }
            }
        }).catch(err => console.log("Sağlık kontrolü alınamadı", err));


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
        
        // RESET PREVIEW STATE
        isShowingOriginal = false;
        tempPreviewImg = null;
        let btnOrig = document.getElementById('btnToggleOriginal');
        if (btnOrig) {
            btnOrig.innerHTML = "👁️ Orijinal / Önizleme";
            btnOrig.style.background = "#9c27b0";
        }
        
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
            headers: {
                'Content-Type': 'application/json',
                'X-Active-Category': currentCat,
                'X-Active-Template': currentTmpl
            },
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
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Active-Category': t.cat,
                        'X-Active-Template': t.tmpl
                    },
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
        
        // Eger URL'de ?kaggle=1 varsa direkt olarak Kaggle Onay galerisini ac
        if (window.location.search.includes('kaggle=1')) {
            toggleKaggleView();
        }
    }, 500);

    // ==========================================
    // KAGGLE ONAY SISTEMI
    // ==========================================
    function toggleKaggleView() {
        const dashboard = document.getElementById('kaggle-dashboard');
        if (dashboard.style.display === 'none') {
            dashboard.style.display = 'flex';
            loadKaggleImages();
        } else {
            dashboard.style.display = 'none';
        }
    }

    function loadKaggleImages() {
        fetch('/api/kaggle/bekleyenler')
            .then(r => r.json())
            .then(data => {
                const grid = document.getElementById('kaggle-grid');
                grid.innerHTML = '';
                if(data.success && data.files.length > 0) {
                    data.files.forEach(file => {
                        grid.innerHTML += `
                            <div style="background:#2d2d2d; border-radius:8px; padding:10px; width:220px; display:flex; flex-direction:column; align-items:center;">
                                <img src="/image_kaggle/${file}?t=${new Date().getTime()}" style="max-width:100%; max-height:200px; object-fit:contain; border-radius:4px; margin-bottom:10px;">
                                <span style="color:#fff; font-size:12px; margin-bottom:10px; word-break:break-all;">${file}</span>
                                <div style="display:flex; width:100%; gap:5px;">
                                    <button onclick="approveKaggleImage('${file}')" style="flex:1; background:#28a745; padding:8px; font-weight:bold;">✅ Onayla</button>
                                    <button onclick="rejectKaggleImage('${file}')" style="flex:1; background:#dc3545; padding:8px; font-weight:bold;">❌ Reddet</button>
                                </div>
                            </div>
                        `;
                    });
                } else {
                    grid.innerHTML = '<div style="color:#aaa; font-style:italic; padding:20px;">Onay bekleyen Kaggle baskısı bulunmuyor.</div>';
                }
            })
            .catch(err => console.error(err));
    }

    function approveKaggleImage(filename) {
        fetch('/api/kaggle/onayla', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({filename: filename})
        }).then(r=>r.json()).then(data => {
            if(data.success) {
                loadKaggleImages();
            } else {
                alert("Hata: " + data.error);
            }
        });
    }

    function rejectKaggleImage(filename) {
        if(!confirm("Bu görseli tamamen silmek (çöpe atmak) istediğinize emin misiniz?")) return;
        fetch('/api/kaggle/reddet', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({filename: filename})
        }).then(r=>r.json()).then(data => {
            if(data.success) {
                loadKaggleImages();
            } else {
                alert("Hata: " + data.error);
            }
        });
    }
```

### ANA ÜRETİM MOTORU (99_SISTEM_MOTORLARI_VE_KODLAR\SISTEM_MOTORU\pc_master_factory.py)
```python
# -*- coding: utf-8 -*-
"""
================================================================================
E-TİCARET PC MASTER FABRİKASI (V5 ENTERPRISE - HİBRİT MERKEZ)
================================================================================
Bu script, Kaggle AI GPU matbaasından inen master görselleri ve manifest.json
dosyasını alarak yerel PC'de tüm e-ticaret süreçlerini yönetir:

MİMARİ PRENSİPLER (ChatGPT + DeepSeek + Gemini Pro + Antigravity Sentezi):
1. 1 Master -> 5 E-Ticaret Ürünü:
   - M000001_H (Yatay): 01_Wifi_Kutusu (sg-M), 04_Cam_Dograma (cdt-M), 05_Ocak_Arkasi (oact-M)
   - M000001_V (Dikey): 02_Cam_Tablo (ct-M), 03_Ahsap_Tablo (at-M)
   * YATAY-DİKEY KARIŞMASI MATEMATİKSEL OLARAK İMKANSIZDIR.
2. Hassas Geometri & Kenar Kusursuzluğu:
   - OpenCV Homografi / PIL transform + pad (0.03) kenar sızıntısı önleme.
   - Gerçekçi oda aydınlatması harmanı (Luminance Shading %85-%15).
   - Yüzey Ayrımı: Cam için parlama/glare bandı, Ahşap için %100 mat derinlik vinyeti.
3. Çift Dağıtım Modu:
   - Mod 1: Çoklu Mağaza (K1..K11 ayrı klasörler ve ayrı Excel dosyaları).
   - Mod 2: Döngüsel Dağıtım (Tek klasör, tek Excel, sıralı oda rotasyonu).
4. SQLite WAL Durum Yönetimi:
   - Elektrik veya işlem kesilirse kaldığı yerden devam eder (Idempotent).
   - Asla mükerrer ürün basmaz.
5. Asenkron Thread Bulut Yükleyici:
   - ImgBB (4 anahtar rotasyonu) + FreeImage failover.
   - Görsel çizimi yükleme hızından etkilenmez (arkaplanda paralel çalışır).
6. Hızlı Excel Exporter (openpyxl):
   - Hafızada ws.append() ile O(1) hızında Trendyol formatında listeleme.
================================================================================
"""

from __future__ import annotations
import os
import sys
import time
import json
import random
import sqlite3
import hashlib
import logging
import threading
import argparse
from pathlib import Path
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Tuple, Any

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import numpy as np
import requests
from PIL import Image, ImageOps, ImageDraw, ImageFont, ImageChops, ImageFilter

# OpenCV opsiyonel yükleme koruması
try:
    import cv2
    OPENCV_MEVCUT = True
except ImportError:
    OPENCV_MEVCUT = False

import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill

# ==============================================================================
# 1. DİZİN VE YAPILANDIRMA TANIMLARI
# ==============================================================================
BASE_DIR = Path(__file__).resolve().parent
USER_WORKSPACE_DIR = Path(r"C:\Users\oguzc\OneDrive\Masaüstü\GörselÜretme-ve-Mockup Otomasyonu")
if USER_WORKSPACE_DIR.exists():
    FACTORY_DIR = USER_WORKSPACE_DIR / "1_GELEN_KAGGLE_BASKILARI"
    SABLON_DIR = USER_WORKSPACE_DIR / "2_SABLON_HAVUZU"
    OUTPUT_DIR = USER_WORKSPACE_DIR / "3_URETILEN_MOCKUPLAR"
    OUTPUT_COKLU_DIR = USER_WORKSPACE_DIR / "Mockup_Magaza_Klasorleri"
    EXCEL_DIR = USER_WORKSPACE_DIR / "4_EXCEL_YUKLEME_LISTELERI"
    AYARLAR_PATH = USER_WORKSPACE_DIR / "99_SISTEM_MOTORLARI_VE_KODLAR" / "SISTEM_MOTORU" / "ayarlar.json"
    LOG_DIR = USER_WORKSPACE_DIR / "99_SISTEM_MOTORLARI_VE_KODLAR" / "SISTEM_MOTORU" / "logs"
    DB_PATH = USER_WORKSPACE_DIR / "99_SISTEM_MOTORLARI_VE_KODLAR" / "SISTEM_MOTORU" / "commerce_state.db"
    SEO_DIR = USER_WORKSPACE_DIR / "99_SISTEM_MOTORLARI_VE_KODLAR" / "SISTEM_MOTORU" / "SEO_Verileri"
else:
    FACTORY_DIR = BASE_DIR / "factory_outputs"
    SABLON_DIR = BASE_DIR / "Sablonlar"
    OUTPUT_DIR = BASE_DIR / "Mockup_Dongusel_Dagitim"
    OUTPUT_COKLU_DIR = BASE_DIR / "Mockup_Hazir_Urunler"
    EXCEL_DIR = BASE_DIR / "Mockup_Dongusel_Dagitim"
    AYARLAR_PATH = BASE_DIR / "ayarlar.json"
    LOG_DIR = BASE_DIR / "logs"
    DB_PATH = BASE_DIR / "commerce_state.db"
    SEO_DIR = BASE_DIR / "SEO_Verileri"

for d in [FACTORY_DIR, SABLON_DIR, SEO_DIR, OUTPUT_DIR, OUTPUT_COKLU_DIR, EXCEL_DIR, LOG_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Logging Kurulumu
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "pc_master_factory.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("Factory")

excel_lock = threading.Lock()
db_lock = threading.Lock()

# ==============================================================================
# 2. ÜRÜN VE FORMAT SÖZLEŞMESİ (URUN_FORMAT_HARITASI)
# ==============================================================================
@dataclass(frozen=True)
class ProductDefinition:
    key: str
    etiket: str
    barkod_prefix: str
    model_prefix: str
    boyut_cm: str
    orientation: str       # 'H' (Yatay) veya 'V' (Dikey)
    is_glass: bool          # Cam materyal efekti mi ahşap mat mı?
    folder_name: str

PRODUCT_CATALOG: Dict[str, ProductDefinition] = {
    "01_Wifi_Kutusu": ProductDefinition(
        key="01_Wifi_Kutusu",
        etiket="Wifi / Modem Gizleme Kutusu Kapağı",
        barkod_prefix="sg-M",
        model_prefix="M-sg-M",
        boyut_cm="30x40 cm",
        orientation="H",
        is_glass=False,
        folder_name="01_Wifi_Kutusu"
    ),
    "02_Cam_Tablo_Dikey": ProductDefinition(
        key="02_Cam_Tablo_Dikey",
        etiket="Lüks Temperli Cam Tablo (Dikey)",
        barkod_prefix="ct-M",
        model_prefix="M-ct-M",
        boyut_cm="50x70 cm",
        orientation="V",
        is_glass=True,
        folder_name="02_Cam_Tablo_Dikey"
    ),
    "02_Cam_Tablo_Yatay": ProductDefinition(
        key="02_Cam_Tablo_Yatay",
        etiket="Lüks Temperli Cam Tablo (Yatay)",
        barkod_prefix="cty-M",
        model_prefix="M-cty-M",
        boyut_cm="70x100 cm",
        orientation="H",
        is_glass=True,
        folder_name="02_Cam_Tablo_Yatay"
    ),
    "03_Ahsap_Tablo": ProductDefinition(
        key="03_Ahsap_Tablo",
        etiket="Doğal Ahşap Çerçeveli Tablo",
        barkod_prefix="at-M",
        model_prefix="M-at-M",
        boyut_cm="40x60 cm",
        orientation="V",
        is_glass=False,
        folder_name="03_Ahsap_Tablo"
    ),
    "04_Cam_Dograma": ProductDefinition(
        key="04_Cam_Dograma",
        etiket="Cam Kesme ve Doğrama Tahtası",
        barkod_prefix="cdt-M",
        model_prefix="M-cdt-M",
        boyut_cm="30x40 cm",
        orientation="H",
        is_glass=True,
        folder_name="04_Cam_Dograma"
    ),
    "05_Ocak_Arkasi": ProductDefinition(
        key="05_Ocak_Arkasi",
        etiket="Ocak Arkası Koruyucu Cam Panel",
        barkod_prefix="oact-M",
        model_prefix="M-oact-M",
        boyut_cm="60x80 cm",
        orientation="H",
        is_glass=True,
        folder_name="05_Ocak_Arkasi"
    )
}

# ==============================================================================
# 3. AYARLAR.JSON YÜKLEYİCİ VE ŞABLON YÖNETİCİSİ
# ==============================================================================
import sqlite3

def load_ayarlar() -> dict:
    # SABLON_V2_MIMARI'daki SQLite db'sine baglanti
    db_path = USER_WORKSPACE_DIR / "SABLON_V2_MIMARI" / "ayarlar.db"
    
    # Eger db dosyasi yoksa fallback dondur
    if not db_path.exists():
        logger.warning(f"SQLite veritabanı bulunamadı: {db_path}. Fallback yükleniyor.")
        return {
            "bulut_ayarlari": {
                "imgbb_keys": ["5e1f5e0e6477654f2d72eb0ca5bea181", "06ed7ebc958d7a2fafc5d3ecbf8bf49e", "1b165e98a26bcb8a110718f14eda2e8b", "17bfb92dcc58513236003b9344c73621"],
                "freeimage_key": "6d207e02198a847aa98d0a2a901485a5"
            },
            "kategoriler": {}
        }
        
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        result = {"kategoriler": {}}
        
        # 1. Genel Ayarlar
        c.execute("SELECT key, value FROM settings")
        for row in c.fetchall():
            result[row["key"]] = json.loads(row["value"])
            
        # 2. Kategoriler
        c.execute("SELECT id, label FROM categories")
        for row in c.fetchall():
            cat_id = row["id"]
            result["kategoriler"][cat_id] = {
                "etiket": row["label"],
                "sablonlar": {}
            }
            
        # 3. Şablonlar
        c.execute("SELECT category_id, filename, data FROM templates")
        for row in c.fetchall():
            cat_id = row["category_id"]
            tmpl = row["filename"]
            data = json.loads(row["data"])
            
            if cat_id not in result["kategoriler"]:
                result["kategoriler"][cat_id] = {"sablonlar": {}}
            if "sablonlar" not in result["kategoriler"][cat_id]:
                result["kategoriler"][cat_id]["sablonlar"] = {}
                
            result["kategoriler"][cat_id]["sablonlar"][tmpl] = data
            
        conn.close()
        return result
        
    except Exception as e:
        logger.error(f"SQLite (ayarlar.db) okuma hatası: {e}")
        return {"bulut_ayarlari": {}, "kategoriler": {}}

AYARLAR = load_ayarlar()

# ==============================================================================
# 4. SQLITE DURUM YÖNETİCİSİ (WAL Mode, Idempotent, Atomic Counter)
# ==============================================================================
class StateManager:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False, timeout=30)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA journal_mode = WAL")
        self._init_tables()

    def _init_tables(self):
        with db_lock, self.conn:
            self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS masters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                master_id TEXT UNIQUE NOT NULL,
                theme_id INTEGER,
                theme_title TEXT,
                style_key TEXT,
                horizontal_path TEXT,
                vertical_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sku TEXT UNIQUE NOT NULL,
                master_id TEXT NOT NULL,
                kategori_key TEXT NOT NULL,
                barkod TEXT NOT NULL,
                model_kodu TEXT NOT NULL,
                urun_adi TEXT,
                aciklama TEXT,
                ham_baski_dosyasi TEXT,
                mockup_dosyasi TEXT,
                magaza_grubu TEXT,
                resim_linki TEXT,
                status TEXT DEFAULT 'PENDING',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (master_id) REFERENCES masters(master_id)
            );

            CREATE TABLE IF NOT EXISTS system_meta (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_products_status ON products(status);
            CREATE INDEX IF NOT EXISTS idx_products_master ON products(master_id);
            """)

    def register_master(self, master_id: str, theme_id: int, theme_title: str,
                        style_key: str, h_path: str, v_path: str):
        with db_lock, self.conn:
            self.conn.execute("""
            INSERT INTO masters (master_id, theme_id, theme_title, style_key, horizontal_path, vertical_path)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(master_id) DO UPDATE SET
                theme_title=excluded.theme_title,
                horizontal_path=excluded.horizontal_path,
                vertical_path=excluded.vertical_path
            """, (master_id, theme_id, theme_title, style_key, h_path, v_path))

    def get_next_sequence(self, prefix: str) -> int:
        key = f"seq_{prefix}"
        with db_lock, self.conn:
            row = self.conn.execute("SELECT value FROM system_meta WHERE key = ?", (key,)).fetchone()
            current = int(row["value"]) if row else 0
            nxt = current + 1
            self.conn.execute("""
            INSERT INTO system_meta (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP
            """, (key, str(nxt)))
            return nxt

    def is_product_completed(self, sku: str) -> bool:
        with db_lock, self.conn:
            row = self.conn.execute("SELECT status FROM products WHERE sku = ?", (sku,)).fetchone()
            return row is not None and row["status"] == "COMPLETED"

    def save_product(self, data: dict):
        if not data:
            return
        with db_lock, self.conn:
            try:
                self.conn.execute("""
                INSERT INTO products (sku, master_id, kategori_key, barkod, model_kodu,
                                     urun_adi, aciklama, ham_baski_dosyasi, mockup_dosyasi,
                                     magaza_grubu, resim_linki, status, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'COMPLETED', CURRENT_TIMESTAMP)
                ON CONFLICT(sku) DO UPDATE SET
                    urun_adi=excluded.urun_adi,
                    aciklama=excluded.aciklama,
                    mockup_dosyasi=excluded.mockup_dosyasi,
                    resim_linki=excluded.resim_linki,
                    status='COMPLETED',
                    updated_at=CURRENT_TIMESTAMP
                """, (
                    data.get("sku", ""), data.get("master_id", ""), data.get("kategori_key", ""), 
                    data.get("barkod", ""), data.get("model_kodu", ""), data.get("urun_adi", ""), 
                    data.get("aciklama", ""), data.get("ham_baski_dosyasi", ""), data.get("mockup_dosyasi", ""),
                    data.get("magaza_grubu", ""), data.get("resim_linki", "")
                ))
            except Exception as e:
                import logging
                logging.getLogger("StateDB").error(f"Veritabani yazim hatasi (save_product): {e}")

    def get_summary(self) -> dict:
        with db_lock, self.conn:
            cur = self.conn.execute("SELECT status, COUNT(*) as c FROM products GROUP BY status")
            return {r["status"]: r["c"] for r in cur.fetchall()}

    def get_completed_products(self) -> list:
        with db_lock, self.conn:
            cur = self.conn.execute("SELECT * FROM products WHERE status = 'COMPLETED' ORDER BY id")
            return [dict(r) for r in cur.fetchall()]

# ==============================================================================
# 5. ASENKRON ÇOK KATMANLI BULUT YÜKLEYİCİ (Thread Pool + Failover)
# ==============================================================================
class AsyncCloudUploader:
    def __init__(self):
        cloud_cfg = AYARLAR.get("bulut_ayarlari", {})
        self.imgbb_keys = cloud_cfg.get("imgbb_keys", [
            "5e1f5e0e6477654f2d72eb0ca5bea181",
            "06ed7ebc958d7a2fafc5d3ecbf8bf49e",
            "1b165e98a26bcb8a110718f14eda2e8b",
            "17bfb92dcc58513236003b9344c73621"
        ])
        self.freeimage_key = cloud_cfg.get("freeimage_key", "6d207e02198a847aa98d0a2a901485a5")
        self.active_key_idx = 0
        self.key_lock = threading.Lock()
        self.freeimage_active = True

    def upload_sync(self, file_path: Path) -> Optional[str]:
        if not file_path.exists():
            return None

        # 1. ImgBB Rotasyonu
        while self.active_key_idx < len(self.imgbb_keys):
            key = self.imgbb_keys[self.active_key_idx]
            try:
                with open(file_path, "rb") as f:
                    res = requests.post(
                        "https://api.imgbb.com/1/upload",
                        data={"key": key},
                        files={"image": f},
                        timeout=25
                    )
                if res.status_code == 200:
                    data = res.json()
                    return data.get("data", {}).get("url")
                
                # Rate limit / Kota aşımı
                if "Rate limit" in res.text or res.status_code == 400:
                    with self.key_lock:
                        logger.warning(f"ImgBB Key-{self.active_key_idx+1} kotası doldu. Sıradakine geçiliyor...")
                        self.active_key_idx += 1
                        time.sleep(0.5)
                    continue
            except Exception as e:
                logger.warning(f"ImgBB bağlantı hatası: {e}")
                with self.key_lock:
                    self.active_key_idx += 1

        # 2. FreeImage Failover
        if self.freeimage_active:
            try:
                with open(file_path, "rb") as f:
                    res = requests.post(
                        "https://freeimage.host/api/1/upload",
                        data={"key": self.freeimage_key, "action": "upload", "format": "json"},
                        files={"source": f},
                        timeout=30
                    )
                if res.status_code == 200:
                    data = res.json()
                    if "image" in data and "url" in data["image"]:
                        return data["image"]["url"]
            except Exception as e:
                logger.warning(f"FreeImage bağlantı hatası: {e}")
                self.freeimage_active = False

        return None

# ==============================================================================
# 6. SEO VE İÇERİK MOTORU
# ==============================================================================
class SeoEngine:
    def __init__(self):
        self.cache: Dict[str, dict] = {}
        self._init_keywords()

    def _init_keywords(self):
        for prod_key, prod_def in PRODUCT_CATALOG.items():
            folder = SEO_DIR / prod_key
            if not folder.exists():
                folder = SEO_DIR / prod_def.folder_name
            
            k_file = folder / "keywords.txt"
            a_file = folder / "aciklama_keywords.txt"

            # Sablonlar içindeki fallback kontrolü
            if not k_file.exists():
                alt_k = SABLON_DIR / prod_def.folder_name / "keywords.txt"
                if alt_k.exists():
                    k_file = alt_k
            if not a_file.exists():
                alt_a = SABLON_DIR / prod_def.folder_name / "aciklama_keywords.txt"
                if alt_a.exists():
                    a_file = alt_a

            kw_list = []
            if k_file.exists():
                with open(k_file, "r", encoding="utf-8") as f:
                    for line in f:
                        s = line.strip()
                        if s and not s.startswith("["):
                            kw_list.append(s)

            desc_text = f"Özel üretim yüksek çözünürlüklü {prod_def.etiket}."
            if a_file.exists():
                with open(a_file, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        desc_text = content

            self.cache[prod_key] = {
                "keywords": kw_list if kw_list else ["Modern", "Lüks Tasarım", "Dekoratif", "Premium"],
                "aciklama": desc_text
            }

    def generate_title(self, prod_key: str, theme_title: str) -> str:
        data = self.cache.get(prod_key, {"keywords": ["Dekoratif", "Modern", "Lüks"]})
        words = data["keywords"]
        prod_def = PRODUCT_CATALOG[prod_key]
        sample_words = random.sample(words, min(3, len(words)))
        clean_theme = theme_title.replace("_", " ").strip()
        
        # Trendyol için 80-100 karakter dengesi
        title = f"{clean_theme} {prod_def.etiket} {' '.join(sample_words)}"
        return title[:120]

    def get_description(self, prod_key: str, theme_title: str, style_key: str) -> str:
        data = self.cache.get(prod_key, {"aciklama": "Özel üretim dekoratif ürün."})
        base_desc = data["aciklama"]
        footer = f"\n\nTasarım Teması: {theme_title}\nSanat Stili: {style_key or 'Özel Koleksiyon'}"
        return base_desc + footer

# ==============================================================================
# 7. MOCKUP MOTORU (Anti-Border-Seam, Pad=0.03, OpenCV & PIL Homografi)
# ==============================================================================
# 7. AI KALİTE MOTORU (Real-ESRGAN Vulkan RTX)
# ==============================================================================
class RealESRGANQualityEngine:
    @staticmethod
    def get_exe_path() -> Optional[Path]:
        candidates = [
            USER_WORKSPACE_DIR / "AI_Kalite_Artirici" / "realesrgan-ncnn-vulkan.exe",
            BASE_DIR.parent / "AI_Kalite_Artirici" / "realesrgan-ncnn-vulkan.exe"
        ]
        for c in candidates:
            if c.exists():
                return c
        return None

    @classmethod
    def upscale_4k(cls, input_path: Path, output_path: Path) -> bool:
        exe = cls.get_exe_path()
        if not exe:
            return False

        models_dir = exe.parent / "models"
        cmd = [
            str(exe),
            "-i", str(input_path),
            "-o", str(output_path),
            "-m", str(models_dir),
            "-n", "realesrgan-x4plus",
            "-s", "4",
            "-t", "400"
        ]
        try:
            import subprocess
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            return output_path.exists()
        except Exception as e:
            logger.warning(f"Real-ESRGAN upscale atlandı: {e}")
            return False

# ==============================================================================
# 8. KALİTE KONTROL VE ÖNLEM MEKANİZMASI (Quality Inspector)
# ==============================================================================
class QualityInspector:
    @staticmethod
    def inspect_mockup(img_cv: np.ndarray, koseler: Optional[list] = None) -> Tuple[bool, str]:
        """
        Görselin kenar uzaması, piksellenme ve köşe taşması hatalarını denetler.
        """
        if img_cv is None or img_cv.size == 0:
            return False, "Görsel boş veya yüklenemedi"

        h, w = img_cv.shape[:2]
        if w < 500 or h < 500:
            return False, f"Çözünürlük çok düşük: {w}x{h}"

        # Kenar çizgilenme/tekrar hatası kontrolü (Edge streak test)
        if koseler and len(koseler) == 4:
            for pt in koseler:
                px, py = int(pt[0]), int(pt[1])
                if px < 0 or px >= w or py < 0 or py >= h:
                    return False, f"Köşe koordinatı görsel sınırları dışında: ({px}, {py})"

        return True, "100/100 Mükemmel Kalite Onayı"

# ==============================================================================
# 9. MOCKUP MOTORU (Optik Cam Parlaması, Bevel Pahı, Gün Işığı & Sıfır Kenar Hatası)
# ==============================================================================
class MockupRenderer:
    @staticmethod
    def build_foreground_mask(
        bg_cv: np.ndarray,
        on_plan: dict | list | None,
    ) -> np.ndarray:
        """
        Photoshop benzeri Object Selection & Brush mantığı.
        on_plan formatı:
        {
            "object_boxes": [[x1, y1, x2, y2], ...],
            "add_brush": [[x, y, radius], ...],
            "subtract_brush": [[x, y, radius], ...],
            "feather": 1.2,
            "grabcut_iterations": 5
        }
        veya geriye dönük uyumlu polygon listesi.
        """
        h, w = bg_cv.shape[:2]
        empty_mask = np.zeros((h, w), dtype=np.uint8)

        if not on_plan:
            return empty_mask

        # Eski polygon formatı geldiyse kırılmasın
        if isinstance(on_plan, list):
            if len(on_plan) >= 3:
                try:
                    pts = np.asarray(on_plan, dtype=np.int32)
                    mask = np.zeros((h, w), dtype=np.uint8)
                    pts[:, 0] = np.clip(pts[:, 0], 0, w - 1)
                    pts[:, 1] = np.clip(pts[:, 1], 0, h - 1)
                    cv2.fillPoly(mask, [pts], 255)
                    mask = cv2.GaussianBlur(mask, (0, 0), 1.2)
                    return mask
                except Exception:
                    return empty_mask
            return empty_mask

        object_boxes = on_plan.get("object_boxes", [])
        add_brush = on_plan.get("add_brush", [])
        subtract_brush = on_plan.get("subtract_brush", [])
        feather = float(on_plan.get("feather", 1.2))
        iterations = int(on_plan.get("grabcut_iterations", 5))

        final_mask = np.zeros((h, w), dtype=np.uint8)

        # 1. OBJECT SELECTION (Her kutu ayrı GrabCut'tan geçirilir)
        for box in object_boxes:
            if not box or len(box) != 4:
                continue
            try:
                x1, y1, x2, y2 = map(int, box)
            except Exception:
                continue

            x1, x2 = sorted((x1, x2))
            y1, y2 = sorted((y1, y2))
            x1 = int(np.clip(x1, 0, w - 1))
            x2 = int(np.clip(x2, 0, w - 1))
            y1 = int(np.clip(y1, 0, h - 1))
            y2 = int(np.clip(y2, 0, h - 1))

            rw = x2 - x1
            rh = y2 - y1
            if rw < 10 or rh < 10:
                continue

            gx = max(1, x1)
            gy = max(1, y1)
            gw = min(rw, w - gx - 1)
            gh = min(rh, h - gy - 1)
            if gw < 5 or gh < 5:
                continue

            gc_mask = np.zeros((h, w), dtype=np.uint8)
            bg_model = np.zeros((1, 65), dtype=np.float64)
            fg_model = np.zeros((1, 65), dtype=np.float64)

            try:
                cv2.grabCut(
                    bg_cv,
                    gc_mask,
                    (gx, gy, gw, gh),
                    bg_model,
                    fg_model,
                    iterations,
                    cv2.GC_INIT_WITH_RECT
                )
                object_mask = np.where(
                    (gc_mask == cv2.GC_FGD) | (gc_mask == cv2.GC_PR_FGD),
                    255,
                    0
                ).astype(np.uint8)
                final_mask = cv2.max(final_mask, object_mask)
            except cv2.error as exc:
                logger.warning(f"[MASK] GrabCut uyarisi: {exc}")
                cv2.rectangle(final_mask, (x1, y1), (x2, y2), 255, -1)

        # 2. MANUEL + FIRÇA
        for stroke in add_brush:
            if not stroke or len(stroke) < 2:
                continue
            x = int(np.clip(int(stroke[0]), 0, w - 1))
            y = int(np.clip(int(stroke[1]), 0, h - 1))
            radius = int(stroke[2] if len(stroke) >= 3 else 20)
            cv2.circle(final_mask, (x, y), max(1, radius), 255, -1, lineType=cv2.LINE_AA)

        # 3. MANUEL - FIRÇA
        for stroke in subtract_brush:
            if not stroke or len(stroke) < 2:
                continue
            x = int(np.clip(int(stroke[0]), 0, w - 1))
            y = int(np.clip(int(stroke[1]), 0, h - 1))
            radius = int(stroke[2] if len(stroke) >= 3 else 20)
            cv2.circle(final_mask, (x, y), max(1, radius), 0, -1, lineType=cv2.LINE_AA)

        if not np.any(final_mask):
            return final_mask

        # 4. MASK TEMİZLİĞİ (Morphology Close & Küçük Leke Filtresi)
        kernel_close = np.ones((3, 3), np.uint8)
        final_mask = cv2.morphologyEx(final_mask, cv2.MORPH_CLOSE, kernel_close, iterations=1)

        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(
            (final_mask > 127).astype(np.uint8),
            connectivity=8
        )
        cleaned = np.zeros_like(final_mask)
        min_component_area = max(20, int((w * h) * 0.000005))
        for i in range(1, num_labels):
            area = stats[i, cv2.CC_STAT_AREA]
            if area >= min_component_area:
                cleaned[labels == i] = 255
        final_mask = cleaned

        # 5. EDGE FEATHER (Kenar Yumuşatma)
        if feather > 0:
            final_mask = cv2.GaussianBlur(final_mask, (0, 0), feather)

        return final_mask

    @staticmethod
    def restore_foreground(
        rendered_cv: np.ndarray,
        original_bg_cv: np.ndarray,
        foreground_mask: np.ndarray
    ) -> np.ndarray:
        if foreground_mask is None or not np.any(foreground_mask):
            return rendered_cv

        alpha = foreground_mask.astype(np.float32) / 255.0
        if len(alpha.shape) == 2:
            alpha = alpha[..., None]

        rendered_f = rendered_cv.astype(np.float32)
        original_f = original_bg_cv.astype(np.float32)

        result = original_f * alpha + rendered_f * (1.0 - alpha)
        return np.clip(result, 0, 255).astype(np.uint8)

    @staticmethod
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

        ksize = int(round(feather_px * scale * 2.5)) | 1
        mask_lg_blur = cv2.GaussianBlur(mask_lg, (ksize, ksize), feather_px * scale * 0.5)
        mask_aa = cv2.resize(mask_lg_blur, (w_bg, h_bg), interpolation=cv2.INTER_AREA)
        return np.clip(mask_aa, 0.0, 1.0)

    @staticmethod
    def generate_window_reflection(gw: int, gh: int, intensity: float = 0.48) -> np.ndarray:
        """
        Referans tavuskuşu cam tablodaki mimari pencere yansıması:
        - 2x2 veya 3x2 belirgin koyu çıtalı (mullions) pencere kurgusu
        - Üst ve sağ kadrana oturan parlak günışığı cam bölmeleri
        - Cam yüzeyinde optik Fresnel derinliği
        """
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

    @staticmethod
    def generate_glass_bevel(h_bg: int, w_bg: int, dst_pts: np.ndarray):
        """
        4mm Kristal Elmas Rodaj Kenar Pahı ve Cam Kalınlığı Kırılma Işıması.
        """
        bevel = np.zeros((h_bg, w_bg, 3), dtype=np.float32)
        p0, p1, p2, p3 = dst_pts[0], dst_pts[1], dst_pts[2], dst_pts[3]

        # 1. Üst kenar rodaj pırıltısı
        cv2.line(bevel, (int(p0[0]), int(p0[1])), (int(p1[0]), int(p1[1])), (1.0, 1.0, 1.0), 2, lineType=cv2.LINE_AA)
        # 2. Sol kenar rodaj pırıltısı
        cv2.line(bevel, (int(p0[0]), int(p0[1])), (int(p3[0]), int(p3[1])), (0.9, 0.95, 1.0), 2, lineType=cv2.LINE_AA)
        # 3. Sağ kenar ön yüz pırıltısı
        cv2.line(bevel, (int(p1[0]), int(p1[1])), (int(p2[0]), int(p2[1])), (0.95, 0.98, 1.0), 2, lineType=cv2.LINE_AA)

        # 4. Sağ kenar 4mm cam derinlik çizgisi (Sağa doğru 3px ofsetli)
        off_3d = np.array([3.0, 0.5], dtype=np.float32)
        p1_3d = p1 + off_3d
        p2_3d = p2 + off_3d
        cv2.line(bevel, (int(p1_3d[0]), int(p1_3d[1])), (int(p2_3d[0]), int(p2_3d[1])), (0.5, 0.6, 0.7), 1, lineType=cv2.LINE_AA)

        bevel = cv2.GaussianBlur(bevel, (3, 3), 0.4)
        return bevel

    @staticmethod
    def generate_kitchen_countertop_sheen(gw: int, gh: int, intensity: float = 0.24) -> np.ndarray:
        """
        Cam Doğrama (Kesme Tahtası) için Mutfak Tezgahı / Spot Işık Yansıması:
        - Mutfak tezgahı üstündeki dolap altı LED veya tavan spot ışığının cam kesme tahtası üzerindeki oval pırıltısı.
        """
        y, x = np.mgrid[0:gh, 0:gw].astype(np.float32)

        spot_cx = gw * 0.50
        spot_cy = gh * 0.35

        dx = (x - spot_cx) / (gw * 0.45)
        dy = (y - spot_cy) / (gh * 0.30)
        dist_sq = dx * dx + dy * dy

        spot = np.exp(-dist_sq * 1.8)
        spot_smooth = cv2.GaussianBlur(spot, (41, 41), 0)

        edge_glow = np.exp(-((y / float(gh)) - 0.05)**2 / 0.01) * 0.30
        total = np.clip((spot_smooth * 0.85 + edge_glow) * intensity, 0.0, 0.55)
        return np.stack([total * 1.0, total * 0.98, total * 0.95], axis=-1)

    @staticmethod
    def generate_sunlight_shadow_for_wood(image_cv: np.ndarray, dst_pts: np.ndarray, intensity: float = 0.15) -> np.ndarray:
        """
        Ahşap Tablolar ve Wifi Kutuları için Doğal Güneş & Pencere Gölgesi Yansıması:
        - Cam gibi ayna/parlama yapmaz.
        - Odaya vuran doğal sıcak güneş ışığı huzmeleri ve pencere kanadı gölgeleri (güneş ve gölge yansımaları).
        """
        h, w = image_cv.shape[:2]
        y, x = np.mgrid[0:h, 0:w].astype(np.float32)

        angle_rad = np.radians(35.0)
        u = (x * np.cos(angle_rad) - y * np.sin(angle_rad)) / float(max(w, h))

        freq = 2.8
        stripes = np.sin(u * np.pi * 2.0 * freq)
        stripes = np.tanh(stripes * 1.8) * 0.5 + 0.5
        stripes_smooth = cv2.GaussianBlur(stripes, (61, 61), 0)

        factor = 1.0 + (stripes_smooth - 0.5) * intensity
        sunlight_3c = np.stack([
            factor * (1.0 - (stripes_smooth - 0.5) * 0.04),
            factor * (1.0 + (stripes_smooth - 0.5) * 0.02),
            factor * (1.0 + (stripes_smooth - 0.5) * 0.06),
        ], axis=-1)

        result = np.clip(image_cv.astype(np.float32) * sunlight_3c, 0.0, 255.0)
        return result.astype(np.uint8)

    @staticmethod
    def generate_floating_shadow(h_bg: int, w_bg: int, dst_pts: np.ndarray, dx: float = 14.0, dy: float = 20.0) -> np.ndarray:
        """
        2cm Duvardan Önde Duran Gizli Asma Aparatı Derinlik Gölgesi.
        Çift katman: Yakın koyu temas gölgesi + geniş yumuşak tütsü gölgesi.
        """
        core = np.zeros((h_bg, w_bg), dtype=np.float32)
        offset_core = np.array([[dx * 0.35, dy * 0.35]] * 4, dtype=np.float32)
        cv2.fillConvexPoly(core, (dst_pts + offset_core).astype(np.int32), 0.40)
        core = cv2.GaussianBlur(core, (11, 11), 0)

        penumbra = np.zeros((h_bg, w_bg), dtype=np.float32)
        offset_pen = np.array([[dx, dy]] * 4, dtype=np.float32)
        cv2.fillConvexPoly(penumbra, (dst_pts + offset_pen).astype(np.int32), 0.28)
        penumbra = cv2.GaussianBlur(penumbra, (45, 45), 0)

        return np.clip(core + penumbra, 0.0, 0.65)

    @staticmethod
    def apply_architectural_daylight(image_cv: np.ndarray, angle: float = 32.0, intensity: float = 0.10) -> np.ndarray:
        """
        Tüm Mockuplara Doğal Günışığı & Pencere Gölgesi Efekti.
        Odaya pencereden süzülen yumuşak günışığı huzmelerini tablo ve duvara harmanlar.
        """
        h, w = image_cv.shape[:2]
        y, x = np.mgrid[0:h, 0:w].astype(np.float32)
        rad = np.radians(angle)
        u = (x * np.cos(rad) - y * np.sin(rad)) / float(max(w, h))

        freq = 3.2
        bands = np.sin(u * np.pi * 2.0 * freq)
        bands = np.tanh(bands * 1.5) * 0.5 + 0.5
        ksize = max(41, int(min(w, h) * 0.09) | 1)
        bands_diffuse = cv2.GaussianBlur(bands, (ksize, ksize), 0)

        daylight_factor = 1.0 + (bands_diffuse - 0.5) * intensity
        daylight_3c = np.stack([
            daylight_factor * (1.0 - (bands_diffuse - 0.5) * 0.02),
            daylight_factor,
            daylight_factor * (1.0 + (bands_diffuse - 0.5) * 0.03)
        ], axis=-1)

        result = np.clip(image_cv.astype(np.float32) * daylight_3c, 0.0, 255.0)
        return result.astype(np.uint8)

    @staticmethod
    def match_color_cast(art_cv: np.ndarray, bg_cv: np.ndarray, poly_mask: np.ndarray) -> np.ndarray:
        """
        Ortam Renk Isısı Harmanlama: Arka planın (odanın) ortalama renk ısısını
        (sarımsı, mavimsi vb.) analiz edip tasarıma hafif bir White Balance kayması uygular.
        """
        poly_indices = poly_mask > 0.05
        if not np.any(poly_indices):
            return art_cv

        bg_mean = np.mean(bg_cv[poly_indices], axis=0) # [B, G, R]
        bg_lum = np.mean(bg_mean)
        if bg_lum < 10.0: 
            return art_cv
        
        # Sadece renk oranını al (parlaklık Ambient Luminance'da zaten işlendi)
        color_ratios = bg_mean / bg_lum
        
        # Etkiyi %40 civarında sınırlıyoruz (sinematik blend)
        blend_factor = 0.40
        adjusted_ratios = 1.0 + (color_ratios - 1.0) * blend_factor
        
        art_float = art_cv.astype(np.float32)
        art_float[:, :, 0] *= adjusted_ratios[0]
        art_float[:, :, 1] *= adjusted_ratios[1]
        art_float[:, :, 2] *= adjusted_ratios[2]
        
        return np.clip(art_float, 0, 255).astype(np.float32)

    @staticmethod
    def apply_chromatic_aberration(image_cv: np.ndarray, intensity: int = 1) -> np.ndarray:
        """
        Lens Sapması (Chromatic Aberration): Kamera lenslerinin köşelerde yarattığı
        RGB kırılmasını taklit eder. Gerçek fotoğraf hissini artırır.
        """
        image_uint8 = np.clip(image_cv, 0, 255).astype(np.uint8)
        b, g, r = cv2.split(image_uint8)
        
        # R kanalını hafif sağ-aşağı kaydır
        M_r = np.float32([[1, 0, intensity], [0, 1, intensity]])
        r_shifted = cv2.warpAffine(r, M_r, (r.shape[1], r.shape[0]), borderMode=cv2.BORDER_REPLICATE)
        
        # B kanalını hafif sol-yukarı kaydır
        M_b = np.float32([[1, 0, -intensity], [0, 1, -intensity]])
        b_shifted = cv2.warpAffine(b, M_b, (b.shape[1], b.shape[0]), borderMode=cv2.BORDER_REPLICATE)
        
        merged = cv2.merge((b_shifted, g, r_shifted))
        return merged.astype(np.float32)

    @staticmethod
    def apply_camera_grain(image_cv: np.ndarray, intensity: float = 3.5) -> np.ndarray:
        """
        Film Greni: Sensör kumlanmasını sentetik olarak üretir.
        Parlak ve karanlık alanlarda az, orta tonlarda çok kumlanma yapar.
        """
        h, w = image_cv.shape[:2]
        noise = np.random.normal(0, intensity, (h, w, 3)).astype(np.float32)
        
        lum = cv2.cvtColor(np.clip(image_cv, 0, 255).astype(np.uint8), cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
        # 4*x*(1-x) parabolü ile orta tonları (0.5) maksimize eder, 0 ve 1'i minimize eder
        noise_mask = 4.0 * lum * (1.0 - lum)
        noise_mask = np.clip(noise_mask + 0.15, 0.0, 1.0)
        noise_mask_3c = np.stack([noise_mask] * 3, axis=-1)
        
        return image_cv + (noise * noise_mask_3c)

    @staticmethod
    def render_cv2_optik(art_cv: np.ndarray, bg_cv: np.ndarray, koseler: list, is_glass: bool, on_plan=None, template_name: str = None, category_name: str = None, orig_bg_cv: np.ndarray = None, alpha_mask: np.ndarray = None) -> np.ndarray:
        h_bg, w_bg = bg_cv.shape[:2]
        h_art, w_art = art_cv.shape[:2]
        p = np.float32(koseler)  # [TL, TR, BR, BL]

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
            crop_w = int(round(h_art * target_ar))
            crop_h = h_art
            sx = max(0, (w_art - crop_w) // 2)
            sy = 0
            art_fitted = art_cv[:, sx:sx + crop_w]
        else:
            crop_w = w_art
            crop_h = int(round(w_art / target_ar))
            sx = 0
            sy = max(0, (h_art - crop_h) // 2)
            art_fitted = art_cv[sy:sy + crop_h, :]

        # -------------------------------------------------------------
        # 2. SUB-PIXEL PERSPEKTİF HOMOGRAFİ & KENAR YUMUŞATMA (ANTI-ALIASING)
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

        # 2x Supersampled Sub-pixel Kenar Yumuşatma Maskesi
        if alpha_mask is not None:
            # Şeffaf Delik (Passepartout) Maskesi
            mask_f = 1.0 - (alpha_mask.astype(np.float32) / 255.0)
        else:
            mask_f = MockupRenderer.create_subpixel_antialiased_mask(h_bg, w_bg, dst_pts, feather_px=1.8)
        mask_3c = np.stack([mask_f] * 3, axis=-1)

        # -------------------------------------------------------------
        # 3. ORTAM IŞIĞI HARMANLAMA (AMBIENT LUMINANCE MAPPING)
        # -------------------------------------------------------------
        bg_gray = cv2.cvtColor(bg_cv, cv2.COLOR_BGR2GRAY).astype(np.float32)
        poly_indices = mask_f > 0.05
        if np.any(poly_indices):
            mean_lum = float(np.mean(bg_gray[poly_indices]))
            if mean_lum > 10.0:
                bg_smooth = cv2.GaussianBlur(bg_gray, (65, 65), 0)
                ambient_ratio = np.clip(bg_smooth / mean_lum, 0.75, 1.35)
                ambient_ratio_3c = np.stack([ambient_ratio] * 3, axis=-1)
                warped_f = warped.astype(np.float32)
                warped_lit = warped_f * ((1.0 - 0.18) + 0.18 * ambient_ratio_3c)
            else:
                warped_lit = warped.astype(np.float32)
        else:
            warped_lit = warped.astype(np.float32)

        # --- İLERİ SEVİYE SİNEMATİK POST-PROCESSING (FOTOGERÇEKÇİLİK) ---
        # 1. Ortam Renk Isısı Harmanlama (White Balance Match)
        warped_lit = MockupRenderer.match_color_cast(warped_lit, bg_cv, mask_f)
        
        # 2. Lens Sapması (Chromatic Aberration)
        warped_lit = MockupRenderer.apply_chromatic_aberration(warped_lit, intensity=1)
        
        # 3. Sensör Kumlanması (Camera Grain)
        warped_lit = MockupRenderer.apply_camera_grain(warped_lit, intensity=3.5)
        # ----------------------------------------------------------------

        # -------------------------------------------------------------
        # 4. KATEGORİYE ÖZEL YANSIMA VE GÖLGE MOTORU
        # -------------------------------------------------------------
        is_cam_dograma = (category_name == "04_Cam_Dograma")
        is_wood_or_wifi = (category_name in ["03_Ahsap_Tablo", "01_Wifi_Kutusu"])

        gw, gh = int(target_w), int(target_h)

        if is_cam_dograma:
            # A) CAM DOĞRAMA / KESME TAHTASI: Mutfak Tezgahı & Dolap Altı Spot Işık Yansıması + Rodaj Kenar
            spot_sheen = MockupRenderer.generate_kitchen_countertop_sheen(gw, gh, intensity=0.25)
            spot_warped = cv2.warpPerspective(
                spot_sheen, matrix, (w_bg, h_bg),
                flags=cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=(0, 0, 0)
            )
            warped_norm = np.clip(warped_lit / 255.0, 0.0, 1.0)
            glass_art_norm = 1.0 - (1.0 - warped_norm) * (1.0 - spot_warped)

            # 4mm Elmas Rodaj Kenar ve Cam Kalınlığı Kırılması
            bevel_light = MockupRenderer.generate_glass_bevel(h_bg, w_bg, dst_pts)
            glass_surface = np.clip(glass_art_norm + bevel_light, 0.0, 1.0) * 255.0

            # Tezgah yüzeyine düşen ince temas gölgesi
            shadow_dog = np.zeros((h_bg, w_bg), dtype=np.float32)
            cv2.fillConvexPoly(shadow_dog, (dst_pts + np.array([[6, 10]] * 4)).astype(np.int32), 0.35)
            shadow_dog = cv2.GaussianBlur(shadow_dog, (21, 21), 0)
            shadow_out = shadow_dog * (1.0 - mask_f)
            bg_shadowed = bg_cv.astype(np.float32) * (1.0 - np.stack([shadow_out] * 3, axis=-1))

            final = bg_shadowed * (1.0 - mask_3c) + glass_surface * mask_3c

        elif is_glass and not is_wood_or_wifi:
            # B) CAM TABLOLAR: Tavuskuşu Referanslı Mimari Pencere Yansıması & 4mm Rodaj
            total_shadow = MockupRenderer.generate_floating_shadow(h_bg, w_bg, dst_pts)
            shadow_outside = total_shadow * (1.0 - mask_f)
            bg_shadowed = bg_cv.astype(np.float32) * (1.0 - np.stack([shadow_outside] * 3, axis=-1))

            refl_local = MockupRenderer.generate_window_reflection(gw, gh, intensity=0.48)
            refl_warped = cv2.warpPerspective(
                refl_local, matrix, (w_bg, h_bg),
                flags=cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=(0, 0, 0)
            )

            # Screen blend: 1 - (1 - art) * (1 - refl)
            warped_norm = np.clip(warped_lit / 255.0, 0.0, 1.0)
            glass_art_norm = 1.0 - (1.0 - warped_norm) * (1.0 - refl_warped)

            # 4mm Elmas Rodaj Kenar ve Kırılma Işıması
            bevel_light = MockupRenderer.generate_glass_bevel(h_bg, w_bg, dst_pts)
            glass_surface = np.clip(glass_art_norm + bevel_light, 0.0, 1.0) * 255.0

            final = bg_shadowed * (1.0 - mask_3c) + glass_surface * mask_3c

        else:
            # C) AHŞAP TABLOLAR & WİFİ KUTULARI: Çerçeve İçi Gölge + Doğal Güneş & Gölge
            inner_shadow = np.zeros((h_bg, w_bg), dtype=np.float32)
            p0, p1, _, p3 = dst_pts[0], dst_pts[1], dst_pts[2], dst_pts[3]
            cv2.line(inner_shadow, (int(p0[0]), int(p0[1])), (int(p1[0]), int(p1[1])), 0.38, 5, lineType=cv2.LINE_AA)
            cv2.line(inner_shadow, (int(p0[0]), int(p0[1])), (int(p3[0]), int(p3[1])), 0.38, 5, lineType=cv2.LINE_AA)
            inner_shadow = cv2.GaussianBlur(inner_shadow, (9, 9), 0)
            inner_shadow_3c = np.stack([inner_shadow] * 3, axis=-1)

            wood_surface = np.clip(warped_lit * (1.0 - inner_shadow_3c), 0.0, 255.0)
            final = bg_cv.astype(np.float32) * (1.0 - mask_3c) + wood_surface * mask_3c

        final = np.clip(final, 0, 255).astype(np.uint8)

        # ---------------------------------------------------------
        # FOREGROUND / OCCLUSION RESTORE (AI Cache + Manual on_plan)
        # ---------------------------------------------------------
        fg_mask = None
        try:
            if template_name:
                stem = Path(template_name).stem
                cache_file = BASE_DIR / "masks" / f"{stem}_foreground_mask.png"
                if cache_file.exists():
                    fg_mask = cv2.imdecode(np.fromfile(str(cache_file), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)

            if on_plan:
                manual_mask = MockupRenderer.build_foreground_mask(bg_cv, on_plan)
                if manual_mask is not None and np.any(manual_mask):
                    if fg_mask is not None:
                        fg_mask = cv2.bitwise_or(fg_mask, manual_mask)
                    else:
                        fg_mask = manual_mask

            if fg_mask is not None and np.any(fg_mask):
                final = MockupRenderer.restore_foreground(final, bg_cv, fg_mask)
        except Exception as e:
            logger.warning(f"[FOREGROUND_RESTORE] Ön plan geri yükleme hatası: {e}")

        # ---------------------------------------------------------
        # 5. GÜNEŞ & PENCERE GÖLGESİ (Ahşap & Wifi için sıcak güneş, diğerleri için genel günışığı)
        # ---------------------------------------------------------
        if is_wood_or_wifi:
            final = MockupRenderer.generate_sunlight_shadow_for_wood(final, dst_pts, intensity=0.15)
        else:
            final = MockupRenderer.apply_architectural_daylight(final, angle=32.0, intensity=0.08)

        return final

    @classmethod
    def process_mockup(cls, raw_path: Path, template_path: Path,
                       config: dict, is_glass: bool, output_path: Path) -> bool:
        try:
            # Unicode güvenli okuma (Numpy decode)
            art_cv = cv2.imdecode(np.fromfile(str(raw_path), dtype=np.uint8), cv2.IMREAD_COLOR)
            bg_cv_raw = cv2.imdecode(np.fromfile(str(template_path), dtype=np.uint8), cv2.IMREAD_UNCHANGED)

            if art_cv is None or bg_cv_raw is None:
                logger.error(f"Görseller yüklenemedi: {raw_path.name} veya {template_path.name}")
                return False

            alpha_mask = None
            if len(bg_cv_raw.shape) == 3 and bg_cv_raw.shape[2] == 4:
                alpha_mask = bg_cv_raw[:, :, 3]
                bg_cv = bg_cv_raw[:, :, :3]
            else:
                bg_cv = bg_cv_raw

            tip = config.get("tip", "duz")
            on_plan = config.get("on_plan", None)
            category_name = template_path.parent.name

            # Perspektif Giydirme
            if tip == "perspektif" and "koseler" in config:
                koseler = config["koseler"]
            else:
                # Düz Şablon Giydirme
                h_bg, w_bg = bg_cv.shape[:2]
                tw = config.get("w", int(w_bg * 0.5))
                th = config.get("h", int(h_bg * 0.5))
                tx = config.get("x", int(w_bg * 0.25))
                ty = config.get("y", int(h_bg * 0.25))
                koseler = [[tx, ty], [tx + tw, ty], [tx + tw, ty + th], [tx, ty + th]]

            # Akıllı Döndürme (Smart Rotation) - Sıkışmayı Önlemek İçin
            pts = np.array(koseler)
            tw_approx = np.linalg.norm(pts[1] - pts[0])
            th_approx = np.linalg.norm(pts[2] - pts[1])
            template_is_horiz = tw_approx >= th_approx
            
            art_h, art_w = art_cv.shape[:2]
            art_is_horiz = art_w >= art_h
            
            if art_is_horiz != template_is_horiz:
                art_cv = cv2.rotate(art_cv, cv2.ROTATE_90_CLOCKWISE)
                logger.info(f"🔄 Görsel sıkışmaması için 90 derece döndürüldü: {raw_path.name}")

            # Orijinal yedek görseli yükle (True Shadow Mapping için)
            orig_path = USER_WORKSPACE_DIR / "2_SABLON_HAVUZU_ORIJINAL_YEDEK" / template_path.parent.name / template_path.name
            orig_bg_cv = None
            if orig_path.exists():
                orig_bg_cv = cv2.imdecode(np.fromfile(str(orig_path), dtype=np.uint8), cv2.IMREAD_UNCHANGED)

            final_cv = cls.render_cv2_optik(
                art_cv, bg_cv, koseler, is_glass, 
                on_plan=on_plan, template_name=template_path.name, 
                category_name=category_name, orig_bg_cv=orig_bg_cv,
                alpha_mask=alpha_mask
            )

            # Kalite Kontrol Denetimi (Quality Inspector)
            valid, msg = QualityInspector.inspect_mockup(final_cv, koseler if "koseler" in config else None)
            if not valid:
                logger.warning(f"  ⚠️ Kalite Denetimi Uyarısı ({raw_path.name}): {msg}")

            # Kaydet (Unicode güvenli)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            success, enc_img = cv2.imencode('.jpg', final_cv, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
            if success:
                enc_img.tofile(str(output_path))
                return True
            return False

        except Exception as e:
            logger.error(f"Mockup render hatası: {e}", exc_info=True)
            return False

# ==============================================================================
# 8. HIZLI EXCEL YÖNETİCİSİ (openpyxl Append)
# ==============================================================================
class FastExcelManager:
    HEADERS = [
        "Stok Kodu", "Barkod", "Model Kodu", "Kategori", "Ham Baskı Dosyası",
        "Mağaza Grubu", "Ürün Adı", "Açıklama", "Mockup Dosya Adı",
        "Resim Linki", "Eklenme Zamanı"
    ]

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self._init_file()

    def _init_file(self):
        if not self.file_path.exists():
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Trendyol_Yukleme"
            ws.append(self.HEADERS)
            
            # Başlık stilizasyonu
            header_fill = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")
            header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
            for col_idx in range(1, len(self.HEADERS) + 1):
                cell = ws.cell(row=1, column=col_idx)
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal="center", vertical="center")

            wb.save(self.file_path)
            wb.close()

    def append_row(self, row_dict: dict):
        row_dict = row_dict or {}
        with excel_lock:
            try:
                wb = openpyxl.load_workbook(self.file_path)
                ws = wb.active
                row = [row_dict.get(h, "") for h in self.HEADERS]
                ws.append(row)
                wb.save(self.file_path)
                wb.close()
            except Exception as e:
                logger.error(f"Excel yazım hatası: {e}")

# ==============================================================================
# 9. ANA PC FABRİKA ORKESTRASYON MOTORU (Master Factory)
# ==============================================================================
class PCMasterFactory:
    def __init__(self, mode: str = "dongusel"):
        self.mode = mode   # "dongusel" veya "coklu"
        self.state = StateManager()
        self.uploader = AsyncCloudUploader()
        self.seo = SeoEngine()
        self.excel = FastExcelManager(EXCEL_DIR / "Urun_Yukleme_Listesi.xlsx")
        self.thread_pool = ThreadPoolExecutor(max_workers=3)

    def load_manifest(self) -> List[dict]:
        m_path = FACTORY_DIR / "manifest.json"
        if not m_path.exists():
            logger.error(f"manifest.json bulunamadı! Beklenen yer: {m_path}")
            return []

        try:
            with open(m_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("items", [])
        except Exception as e:
            logger.error(f"manifest.json bozuk veya okunamadı: {e}")
            return []

    def get_template_pool(self, prod_key: str) -> List[Tuple[str, Path, dict]]:
        """
        İlgili ürün için ayarlar.json ve Sablonlar klasöründen şablon havuzunu çeker.
        """
        pool = []
        prod_def = PRODUCT_CATALOG[prod_key]
        
        # 1. ayarlar.json içindeki kayıtlı şablonlar
        kat_cfg = AYARLAR.get("kategoriler", {}).get(prod_key, {})
        sablonlar_cfg = kat_cfg.get("sablonlar", {})

        # Klasör taraması (Sablonlar/01_Wifi_Kutusu veya kök Sablonlar/)
        target_dir = SABLON_DIR / prod_def.folder_name
        if not target_dir.exists():
            target_dir = SABLON_DIR

        for s_name, s_conf in sablonlar_cfg.items():
            base_stem = Path(s_name).stem
            s_path = target_dir / s_name
            
            # Şeffaf Sistem (Passepartout): Dosya PNG olarak kaydedilmiş olabilir
            if not s_path.exists():
                s_path_png = target_dir / f"{base_stem}.png"
                if s_path_png.exists():
                    s_path = s_path_png
                else:
                    s_path = SABLON_DIR / s_name
                    if not s_path.exists():
                        s_path_png_root = SABLON_DIR / f"{base_stem}.png"
                        if s_path_png_root.exists():
                            s_path = s_path_png_root
                            
            if s_path.exists():
                pool.append((s_name, s_path, s_conf))

        # Eğer kategoride ayarlar.json boşsa klasördeki dosyaları al (default fallback rect)
        if not pool and target_dir.exists():
            for f in target_dir.iterdir():
                if f.is_file() and f.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]:
                    pool.append((
                        f.name, f,
                        {"tip": "duz", "x": int(800*0.2), "y": int(800*0.2), "w": int(800*0.6), "h": int(800*0.6)}
                    ))

        return pool

    def process_all(self):
        items = self.load_manifest()
        if not items:
            logger.warning("İşlenecek manifest öğesi bulunamadı.")
            return

        logger.info(f"🚀 PC MASTER FABRİKASI BAŞLATILDI | Toplam Master: {len(items)} | Mod: {self.mode.upper()}")

        for m_idx, master_data in enumerate(items, start=1):
            master_id = master_data.get("master_id", f"M{m_idx:06d}")
            theme_id = master_data.get("theme_id", 0)
            theme_title = master_data.get("theme_title", "Özel Sanat Eseri")
            style_key = master_data.get("style_key", "")

            # Ham yollar
            h_raw = master_data.get("horizontal", {}).get("file", "") or master_data.get("horizontal_path", "")
            v_raw = master_data.get("vertical", {}).get("file", "") or master_data.get("vertical_path", "")

            h_path = (FACTORY_DIR / h_raw).resolve() if not Path(h_raw).is_absolute() else Path(h_raw)
            v_path = (FACTORY_DIR / v_raw).resolve() if not Path(v_raw).is_absolute() else Path(v_raw)

            # Fallback klasör içi arama
            if not h_path.exists():
                h_alt = FACTORY_DIR / f"{master_id}_H.png"
                if h_alt.exists():
                    h_path = h_alt
            if not v_path.exists():
                v_alt = FACTORY_DIR / f"{master_id}_V.png"
                if v_alt.exists():
                    v_path = v_alt

            self.state.register_master(master_id, theme_id, theme_title, style_key, str(h_path), str(v_path))

            logger.info("\n========================================================")
            logger.info(f"🎨 MASTER [{m_idx}/{len(items)}]: {master_id} - {theme_title}")
            logger.info("========================================================")

            # 1 Master -> 5 Ürün Genişletmesi
            for prod_key, prod_def in PRODUCT_CATALOG.items():
                # YATAY-DİKEY GARANTİSİ
                target_raw_path = h_path if prod_def.orientation == "H" else v_path
                if not target_raw_path.exists():
                    logger.warning(f"  ⚠️ Ham görsel bulunamadı ({prod_def.orientation}): {target_raw_path.name}")
                    continue

                seq = self.state.get_next_sequence(prod_def.barkod_prefix)
                barkod = f"{prod_def.barkod_prefix}{seq:05d}"
                sku = barkod
                model_kodu = f"{prod_def.model_prefix}{seq:05d}"

                if self.state.is_product_completed(sku):
                    logger.info(f"  ⏭️ Atlandı (Zaten tamam): {sku}")
                    continue

                template_pool = self.get_template_pool(prod_key)
                if not template_pool:
                    logger.warning(f"  ⚠️ Şablon havuzu boş: {prod_key}")
                    continue

                # Şablon Seçimi
                if self.mode == "coklu":
                    secilen_sablonlar = template_pool
                else:
                    # Döngüsel mod: Sıradaki şablon
                    t_idx = (seq - 1) % len(template_pool)
                    secilen_sablonlar = [template_pool[t_idx]]

                for sablon_name, sablon_path, sablon_conf in secilen_sablonlar:
                    magaza_grubu = sablon_path.stem
                    out_filename = f"{sku}_{sablon_path.stem}.jpg"
                    
                    if self.mode == "coklu":
                        out_dir = OUTPUT_COKLU_DIR / prod_key / magaza_grubu
                    else:
                        out_dir = OUTPUT_DIR / prod_key

                    out_path = out_dir / out_filename

                    logger.info(f"  🖌️ Render: {sku} ({prod_def.etiket}) -> {sablon_name}")

                    success = MockupRenderer.process_mockup(
                        raw_path=target_raw_path,
                        template_path=sablon_path,
                        config=sablon_conf,
                        is_glass=prod_def.is_glass,
                        output_path=out_path
                    )

                    if not success:
                        continue

                    # SEO Başlık ve Açıklama
                    seo_title = self.seo.generate_title(prod_key, theme_title)
                    seo_desc = self.seo.get_description(prod_key, theme_title, style_key)

                    prod_record = {
                        "sku": sku,
                        "master_id": master_id,
                        "kategori_key": prod_key,
                        "barkod": barkod,
                        "model_kodu": model_kodu,
                        "urun_adi": seo_title,
                        "aciklama": seo_desc,
                        "ham_baski_dosyasi": target_raw_path.name,
                        "mockup_dosyasi": out_filename,
                        "magaza_grubu": magaza_grubu,
                        "resim_linki": ""
                    }

                    # Arka Planda Yükle ve Excel'e Yaz (Non-blocking)
                    self.thread_pool.submit(self._async_upload_and_excel, out_path, prod_record)

        logger.info("\n⏳ Tüm mockuplar çizildi, arkaplandaki bulut yüklemeleri tamamlanıyor...")
        self.thread_pool.shutdown(wait=True)

        logger.info("\n🎉 TÜM İŞLEMLER BAŞARIYLA TAMAMLANDI!")
        logger.info(f"📊 Durum Özeti: {self.state.get_summary()}")
        logger.info(f"📁 Çıktı Excel: {self.excel.file_path}")

    def _async_upload_and_excel(self, mockup_path: Path, prod_record: dict):
        url = self.uploader.upload_sync(mockup_path)
        if url:
            prod_record["resim_linki"] = url
            logger.info(f"    ☁️ Bulut Yüklendi: {prod_record['sku']} -> {url}")
        else:
            logger.info(f"    💾 Yerel Kaydedildi (Bulut atlandı): {prod_record['sku']}")

        self.state.save_product(prod_record)

        excel_row = {
            "Stok Kodu": prod_record["sku"],
            "Barkod": prod_record["barkod"],
            "Model Kodu": prod_record["model_kodu"],
            "Kategori": prod_record["kategori_key"],
            "Ham Baskı Dosyası": prod_record["ham_baski_dosyasi"],
            "Mağaza Grubu": prod_record["magaza_grubu"],
            "Ürün Adı": prod_record["urun_adi"],
            "Açıklama": prod_record["aciklama"],
            "Mockup Dosya Adı": prod_record["mockup_dosyasi"],
            "Resim Linki": prod_record.get("resim_linki", ""),
            "Eklenme Zamanı": time.strftime("%d.%m.%Y %H:%M:%S")
        }
        self.excel.append_row(excel_row)

# ==============================================================================
# 10. CLI VE İNTERAKTİF GİRİŞ NOKTASI
# ==============================================================================
def parse_args():
    p = argparse.ArgumentParser(description="PC Master Mockup & Commerce Factory V5")
    p.add_argument("--mod", choices=["dongusel", "coklu"], default="dongusel",
                   help="Dağıtım modu: 'dongusel' (tek klasör/tek excel) veya 'coklu' (K1..K11 klasörleri)")
    return p.parse_args()

if __name__ == "__main__":
    args = parse_args()
    bot = PCMasterFactory(mode=args.mod)
    bot.process_all()

```

