import os
import sys
import json
import base64
import requests
import pandas as pd
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

def load_imgbb_keys(json_path):
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get("bulut_ayarlari", {}).get("imgbb_keys", [])
    except Exception as e:
        print(f"Hata: ayarlar.json okunamadı. ({e})")
        return []

def upload_to_imgbb(image_path, api_keys):
    with open(image_path, "rb") as file:
        image_base64 = base64.b64encode(file.read()).decode('utf-8')
    
    for key in api_keys:
        url = "https://api.imgbb.com/1/upload"
        payload = {
            "key": key,
            "image": image_base64
        }
        try:
            response = requests.post(url, data=payload, timeout=30)
            if response.status_code == 200:
                result = response.json()
                return result["data"]["url"]
            else:
                print(f"Key hatası (Key: {key[:5]}...): {response.text}")
        except Exception as e:
            print(f"Bağlantı hatası: {e}")
            
    return None

def main():
    # Hide main tkinter window
    root = tk.Tk()
    root.withdraw()
    
    # Load API keys
    ayarlar_path = Path(r"C:\Users\oguzc\OneDrive\Masaüstü\GörselÜretme-ve-Mockup Otomasyonu\ayarlar.json")
    imgbb_keys = load_imgbb_keys(ayarlar_path)
    
    if not imgbb_keys:
        messagebox.showerror("Hata", "ayarlar.json içinde imgbb_keys bulunamadı!")
        return

    # Select folder
    messagebox.showinfo("Bilgi", "Lütfen linklenecek görsellerin bulunduğu klasörü seçin.")
    folder_path = filedialog.askdirectory(title="Görsel Klasörünü Seçin")
    
    if not folder_path:
        print("İşlem iptal edildi.")
        return
        
    folder_path = Path(folder_path)
    
    # Get image files
    image_extensions = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
    image_files = [f for f in folder_path.iterdir() if f.is_file() and f.suffix.lower() in image_extensions]
    
    if not image_files:
        messagebox.showwarning("Uyarı", "Seçilen klasörde görsel dosyası bulunamadı!")
        return
        
    print(f"Toplam {len(image_files)} görsel bulundu. Yükleme başlıyor...")
    
    results = []
    
    for idx, img_file in enumerate(image_files, 1):
        print(f"[{idx}/{len(image_files)}] Yükleniyor: {img_file.name}")
        url = upload_to_imgbb(img_file, imgbb_keys)
        
        if url:
            print(f"  --> Başarılı: {url}")
            results.append({
                "Dosya Adı": img_file.name,
                "Resim Linki": url
            })
        else:
            print("  --> HATA: Yükleme başarısız oldu!")
            results.append({
                "Dosya Adı": img_file.name,
                "Resim Linki": "YÜKLEME_HATASI"
            })
            
    # Save to Excel
    if results:
        df = pd.DataFrame(results)
        excel_path = folder_path / "Gorsel_Linkleri.xlsx"
        df.to_excel(excel_path, index=False)
        print(f"\nİşlem Tamamlandı! Excel dosyası kaydedildi:\n{excel_path}")
        messagebox.showinfo("Başarılı", f"{len(results)} görsel işlendi.\nExcel kaydedildi:\n{excel_path}")
        
        # Open folder
        os.startfile(folder_path)

if __name__ == "__main__":
    main()
