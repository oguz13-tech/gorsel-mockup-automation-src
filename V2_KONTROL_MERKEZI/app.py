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
