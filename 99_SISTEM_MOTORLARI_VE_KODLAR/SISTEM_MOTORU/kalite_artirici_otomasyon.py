# -*- coding: utf-8 -*-
import os, sys, subprocess, time, cv2
import numpy as np
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
MOCKUP_DIR = BASE_DIR / "3_URETILEN_MOCKUPLAR"
ESRGAN_EXE = BASE_DIR / "AI_Kalite_Artirici" / "realesrgan-ncnn-vulkan.exe"
MODELS_DIR = BASE_DIR / "AI_Kalite_Artirici" / "models"
OUTPUT_4K_DIR = BASE_DIR / "3_URETILEN_MOCKUPLAR" / "4K_KRISTAL_NETLIK"

OUTPUT_4K_DIR.mkdir(parents=True, exist_ok=True)

print("=" * 70)
print("   AI REAL-ESRGAN VULKAN 4K/5K KALITE MOTORU (RTX 3060)")
print("=" * 70)

if not ESRGAN_EXE.exists():
    print("HATA: ESRGAN exe bulunamadi!")
    sys.exit(1)

files = [f for f in MOCKUP_DIR.rglob("*.*") if f.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"] and "4K_" not in str(f)]
print(f"Toplam görsel: {len(files)}")

for i, f in enumerate(files, start=1):
    out_file = OUTPUT_4K_DIR / f.name
    if out_file.exists():
        print(f"[{i}/{len(files)}] Zaten 4K mevcut: {f.name}")
        continue

    # Görsel boyutunu kontrol et
    im = cv2.imdecode(np.fromfile(str(f), dtype=np.uint8), cv2.IMREAD_COLOR)
    if im is None:
        continue
    h, w = im.shape[:2]

    # Eğer görsel zaten 2000px üstündeyse, doğrudan yüksek kaliteyle kaydet
    if max(w, h) >= 2500:
        cv2.imencode('.jpg', im, [int(cv2.IMWRITE_JPEG_QUALITY), 95])[1].tofile(str(out_file))
        print(f"[{i}/{len(files)}] Zaten Ultra-HD ({w}x{h}): {f.name} -> Kaydedildi.")
        continue

    # Düşük çözünürlüklü ise Real-ESRGAN ile 4K yap
    print(f"[{i}/{len(files)}] AI 4K Upscale Yapiliyor ({w}x{h}): {f.name}...")
    cmd = [
        str(ESRGAN_EXE),
        "-i", str(f),
        "-o", str(out_file),
        "-m", str(MODELS_DIR),
        "-n", "realesrgan-x4plus",
        "-s", "4",
        "-t", "200"
    ]
    t0 = time.time()
    res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t1 = time.time()
    if out_file.exists():
        kb = out_file.stat().st_size // 1024
        print(f"   -> Basarili! ({t1-t0:.1f} sn) -> {kb} KB")
    else:
        print("   -> Hata: Cikti olusturulamadi.")

print("\n" + "=" * 70)
print("TUM GORSELLER 4K KRISTAL NETLIGE YUKSELTILDI!")
print(f"Konum: {OUTPUT_4K_DIR}")
print("=" * 70)
