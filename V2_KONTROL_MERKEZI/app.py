import os
import sys
import subprocess
import threading
import glob
import json
import ctypes
import time
import sqlite3
from PIL import Image
from flask import Flask, render_template, request, jsonify
import tkinter as tk

# Source code and mutable production data are intentionally separable.
SOURCE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_runtime_override = str(os.environ.get("MOCKUP_RUNTIME_WORKSPACE") or "").strip()
BASE_DIR = os.path.abspath(
    os.path.expanduser(_runtime_override)
) if _runtime_override else SOURCE_ROOT

# Propagate the resolved runtime root to imported helpers and child processes.
os.environ["MOCKUP_RUNTIME_WORKSPACE"] = BASE_DIR

SYS_MOTORS_DIR = os.path.join(
    SOURCE_ROOT,
    "99_SISTEM_MOTORLARI_VE_KODLAR",
    "SISTEM_MOTORU",
)
TEMPLATE_CENTER_DIR = os.path.join(SOURCE_ROOT, "SABLON_V2_MIMARI")
RUNTIME_TEMPLATE_CENTER_DIR = os.path.join(BASE_DIR, "SABLON_V2_MIMARI")

RUNNING_PROCESSES = {}
PROCESS_LOCK = threading.RLock()


def load_cloud_settings():
    """Load cloud upload settings without hard-coding credentials.

    Primary source is the shared SABLON_V2_MIMARI SQLite settings table. Legacy
    ayarlar.json is read only as a compatibility fallback. Environment variables
    may supply a FreeImage key without persisting it to disk.
    """
    settings = {}
    db_path = os.path.join(RUNTIME_TEMPLATE_CENTER_DIR, "ayarlar.db")
    try:
        conn = sqlite3.connect(db_path)
        try:
            row = conn.execute(
                "SELECT value FROM settings WHERE key='bulut_ayarlari'"
            ).fetchone()
            if row and row[0]:
                payload = json.loads(row[0])
                if isinstance(payload, dict):
                    settings.update(payload)
        finally:
            conn.close()
    except Exception:
        pass

    if not settings:
        legacy_path = os.path.join(BASE_DIR, "ayarlar.json")
        try:
            with open(legacy_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            legacy = payload.get("bulut_ayarlari", {})
            if isinstance(legacy, dict):
                settings.update(legacy)
        except Exception:
            pass

    env_freeimage = os.environ.get("FREEIMAGE_KEY")
    if env_freeimage and not settings.get("freeimage_key"):
        settings["freeimage_key"] = env_freeimage

    keys = settings.get("imgbb_keys", [])
    if not isinstance(keys, list):
        keys = []
    settings["imgbb_keys"] = [
        str(key).strip() for key in keys if str(key).strip()
    ]
    return settings


def collision_safe_path(path):
    """Return a non-existing sibling path; never overwrite a user file."""
    candidate = os.fspath(path)
    if not os.path.exists(candidate):
        return candidate
    root, ext = os.path.splitext(candidate)
    suffix = 1
    while True:
        candidate = f"{root}__{suffix}{ext}"
        if not os.path.exists(candidate):
            return candidate
        suffix += 1


def safe_two_phase_rename(files, prefix):
    """Rename a selected set without collisions or partial name swaps."""
    if not files:
        return []

    normalized = [os.path.abspath(path) for path in files]
    folder = os.path.dirname(normalized[0])
    if any(os.path.dirname(path) != folder for path in normalized):
        raise ValueError("Toplu isimlendirme aynı klasördeki dosyalarla yapılmalı.")

    token = f".rename_tmp_{int(time.time() * 1000)}_"
    staged = []
    finalized = []
    results = []
    try:
        # Stage first so target names can overlap original selected names.
        for idx, source in enumerate(normalized, 1):
            ext = os.path.splitext(source)[1]
            temp_path = os.path.join(folder, f"{token}{idx:04d}{ext}")
            while os.path.exists(temp_path):
                temp_path += "_"
            os.rename(source, temp_path)
            staged.append((source, temp_path, ext))

        for idx, (source, temp_path, ext) in enumerate(staged, 1):
            requested = os.path.join(folder, f"{prefix}{idx:03d}{ext}")
            target = collision_safe_path(requested)
            os.rename(temp_path, target)
            finalized.append((source, temp_path, target))
            results.append(target)
        return results
    except Exception:
        # Roll completed phase-2 moves back into their unique staging names
        # first. Directly moving target -> source is unsafe when a target name
        # overlaps another selected file's original path (rename chains/swaps).
        for _, temp_path, target in reversed(finalized):
            if os.path.exists(target) and not os.path.exists(temp_path):
                try:
                    os.rename(target, temp_path)
                except OSError:
                    pass

        # Once every recoverable file is back in staging, restore originals.
        for source, temp_path, _ in reversed(staged):
            if os.path.exists(temp_path) and not os.path.exists(source):
                try:
                    os.rename(temp_path, source)
                except OSError:
                    pass
        raise

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
        tmp_path = PERFORMANCE_FILE + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, PERFORMANCE_FILE)
    except Exception:
        pass

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
    elif folder_name in ("TASARIM_YUKLE", "GELEN_MASTER"):
        # Production factory consumes approved Kaggle H/V masters from here.
        target_path = os.path.join(BASE_DIR, "1_GELEN_KAGGLE_BASKILARI")
    elif folder_name == "URETILEN_MOCKUP":
        target_path = os.path.join(BASE_DIR, "3_URETILEN_MOCKUPLAR")
        
    if os.path.exists(target_path):
        os.startfile(target_path)
        return jsonify({"status": "success", "message": "Klasör açıldı."})
    return jsonify({"status": "error", "message": "Klasör bulunamadı."}), 404

def _factory_preflight_payload():
    """Run the read-only production readiness gate.

    This helper is used both by the UI preflight endpoint and by the actual
    OTOMATIK_URETIM launch path so a direct API call cannot bypass safety.
    """
    script_path = os.path.join(SYS_MOTORS_DIR, "pc_master_factory.py")
    if not os.path.isfile(script_path):
        return {
            "status": "error",
            "ready": False,
            "errors": ["pc_master_factory.py bulunamadı."],
            "exit_code": None,
        }, 404

    try:
        completed = subprocess.run(
            [sys.executable, script_path, "--preflight"],
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=90,
        )
    except subprocess.TimeoutExpired:
        return {
            "status": "error",
            "ready": False,
            "errors": ["Preflight 90 saniyede tamamlanamadı."],
            "exit_code": None,
        }, 504
    except Exception as exc:
        return {
            "status": "error",
            "ready": False,
            "errors": [f"Preflight başlatılamadı: {exc}"],
            "exit_code": None,
        }, 500

    payload = None
    for line in reversed((completed.stdout or "").splitlines()):
        if line.startswith("PREFLIGHT_JSON="):
            try:
                payload = json.loads(line.split("=", 1)[1])
            except json.JSONDecodeError:
                payload = None
            break

    if not isinstance(payload, dict):
        return {
            "status": "error",
            "ready": False,
            "errors": ["Preflight çıktısı okunamadı."],
            "exit_code": completed.returncode,
            "stderr": (completed.stderr or "")[-4000:],
        }, 500

    payload["status"] = "success" if payload.get("ready") else "blocked"
    payload["exit_code"] = completed.returncode

    # The factory process itself returns non-zero when a hard preflight error is
    # present. Treat either signal as blocking; never launch on disagreement.
    if completed.returncode != 0 or not payload.get("ready"):
        payload["ready"] = False
        payload["status"] = "blocked"
        return payload, 409

    return payload, 200


@app.route('/api/run_script', methods=['POST'])
def run_script():
    """Start only explicitly-whitelisted local tools.

    Long-running Flask/tool processes are tracked so repeated UI clicks cannot
    accidentally launch duplicate factories or duplicate template servers.
    """
    data = request.get_json(silent=True) or {}
    script_id = str(data.get('script_id') or '').strip()
    mode = str(data.get('mode') or 'dongusel').strip().lower()
    if mode not in ('dongusel', 'coklu'):
        mode = 'dongusel'

    specs = {
        "SABLON_DUZELTICI": {
            "path": os.path.join(SOURCE_ROOT, "SABLON_DUZELTICI.py"),
            "cwd": BASE_DIR,
            "args": [],
            "display": "Şablon Motoru (Legacy)",
            "server": False,
        },
        "MANUEL_URETIM": {
            "path": os.path.join(SYS_MOTORS_DIR, "manuel_mockup_motoru.py"),
            "cwd": SYS_MOTORS_DIR,
            "args": [],
            "display": "Manuel Mockup Üretimi",
            "server": False,
        },
        "SABLON_V2": {
            "path": os.path.join(TEMPLATE_CENTER_DIR, "app.py"),
            "cwd": TEMPLATE_CENTER_DIR,
            "args": [],
            "display": "Şablon İnceleme Merkezi",
            "server": True,
            "url": "http://127.0.0.1:8080/",
        },
        "OTOMATIK_URETIM": {
            "path": os.path.join(SYS_MOTORS_DIR, "pc_master_factory.py"),
            "cwd": BASE_DIR,
            "args": ["--mod", mode],
            "display": "Otomatik Mockup Fabrikası",
            "server": False,
        },
    }

    spec = specs.get(script_id)
    if spec is None:
        return jsonify({
            "status": "error",
            "message": "Bilinmeyen veya izin verilmeyen script kimliği.",
        }), 400

    if script_id == "OTOMATIK_URETIM":
        preflight, preflight_status = _factory_preflight_payload()
        if preflight_status != 200 or not preflight.get("ready"):
            return jsonify({
                "status": "blocked",
                "message": "Otomatik üretim preflight nedeniyle başlatılmadı.",
                "preflight": preflight,
            }), preflight_status

    script_path = spec["path"]
    if not os.path.exists(script_path):
        return jsonify({
            "status": "error",
            "message": f"Script bulunamadı: {os.path.basename(script_path)}",
        }), 404

    with PROCESS_LOCK:
        existing = RUNNING_PROCESSES.get(script_id)
        if existing is not None and existing.poll() is None:
            response = {
                "status": "already_running",
                "message": f"{spec['display']} zaten çalışıyor.",
            }
            if spec.get("url"):
                response["url"] = spec["url"]
            return jsonify(response)

        command = [sys.executable, script_path] + list(spec.get("args", []))

        if spec.get("server"):
            # Keep the server process alive independently of the request.
            proc = subprocess.Popen(
                command,
                cwd=spec["cwd"],
                creationflags=(
                    subprocess.CREATE_NEW_PROCESS_GROUP
                    if os.name == "nt"
                    else 0
                ),
            )
            RUNNING_PROCESSES[script_id] = proc
            return jsonify({
                "status": "success",
                "message": f"{spec['display']} başlatıldı.",
                "url": spec.get("url"),
            })

        # One-shot jobs run in a worker thread, but duplicate starts are still
        # prevented by storing the live Popen handle immediately.
        proc = subprocess.Popen(command, cwd=spec["cwd"])
        RUNNING_PROCESSES[script_id] = proc

    def wait_for_job():
        start_time = time.time()
        return_code = proc.wait()
        with PROCESS_LOCK:
            if RUNNING_PROCESSES.get(script_id) is proc:
                RUNNING_PROCESSES.pop(script_id, None)

        if return_code == 0:
            try:
                show_colored_popup(
                    script_id,
                    spec["display"],
                    start_time,
                )
            except Exception as exc:
                print(f"Tamamlanma bildirimi açılamadı: {exc}")
        else:
            print(
                f"{spec['display']} hata koduyla sonlandı: {return_code}"
            )

    threading.Thread(target=wait_for_job, daemon=True).start()
    return jsonify({
        "status": "success",
        "message": f"{spec['display']} başlatıldı.",
    })


@app.route('/api/process_status', methods=['GET'])
def process_status():
    with PROCESS_LOCK:
        status = {
            key: bool(proc is not None and proc.poll() is None)
            for key, proc in RUNNING_PROCESSES.items()
        }
    return jsonify({"status": "success", "processes": status})


@app.route('/api/factory_preflight', methods=['GET'])
def factory_preflight():
    """Expose the same server-side readiness gate used by production launch."""
    payload, status_code = _factory_preflight_payload()
    return jsonify(payload), status_code

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
                    target = collision_safe_path(
                        os.path.splitext(file)[0] + '.jpg'
                    )
                    rgb_im.save(target, quality=95)
                elif target_format == 'PNG' and file.lower().endswith(('.jpg', '.jpeg')):
                    img = Image.open(file)
                    target = collision_safe_path(
                        os.path.splitext(file)[0] + '.png'
                    )
                    img.save(target)
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
        # Two-phase rename prevents swaps/collisions and never overwrites
        # an existing user file.
        folder_path = os.path.dirname(files[0]) if files else ""
        try:
            safe_two_phase_rename(files, prefix)
        except Exception as e:
            print(f"Toplu isimlendirme hatası: {e}")
            return
                
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
                
                out_path = collision_safe_path(
                    os.path.join(out_dir, os.path.basename(file))
                )
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
        
        # Use the same cloud settings source as the production factory.
        # Credential values are never logged or embedded in source.
        cloud_settings = load_cloud_settings()
        imgbb_keys = cloud_settings.get("imgbb_keys", [])
            
        if not imgbb_keys:
            ctypes.windll.user32.MessageBoxW(
                0,
                "Bulut ayarlarında ImgBB anahtarı bulunamadı. İşlem iptal edildi.",
                "Anahtar Eksik",
                0x10,
            )
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
    
    script_dir = os.path.join(SOURCE_ROOT, "ÜRÜN ADI YAZDIRMA BOTU")
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
        
    script_dir = os.path.join(SOURCE_ROOT, "AI_Kalite_Artirici")
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
    debug_enabled = str(os.environ.get("MOCKUP_FLASK_DEBUG", "")).strip().lower() in {"1", "true", "yes", "on"}
    app.run(host='127.0.0.1', port=5000, debug=debug_enabled, use_reloader=False)
