import os
import sys
import json
import hashlib

sys.path.append(r"C:\Users\oguzc\OneDrive\Masaüstü\GörselÜretme-ve-Mockup Otomasyonu\SABLON_V2_MIMARI")
from app import app
from core.db import save_template

CAT = "02_Cam_Tablo_Dikey"
TMPL = "CamTabloDikey_023.png"
IMG_PATH = rf"C:\Users\oguzc\OneDrive\Masaüstü\GörselÜretme-ve-Mockup Otomasyonu\2_SABLON_HAVUZU\{CAT}\{TMPL}"

def get_hash(path):
    if not os.path.exists(path): return None
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()

def test_t1_undo():
    print("Testing T1 Undo via Flask test client...")
    
    # 0. Ensure it's in the DB
    save_template(CAT, TMPL, {"dummy": "data"})
    
    client = app.test_client()
    
    # Check initial hash
    orig_hash = get_hash(IMG_PATH)
    if not orig_hash:
        print(f"Skipping T1 test. Image {IMG_PATH} not found.")
        return False
        
    print(f"Original Hash: {orig_hash}")
    
    # DELETE
    headers = {"X-Active-Category": CAT, "X-Active-Template": TMPL}
    r = client.post("/api/sablon_sil", headers=headers)
    print(f"Delete response: {r.status_code} {r.get_data(as_text=True)}")
    
    if r.status_code != 200 or not r.get_json().get("success"):
        print("Delete failed.")
        return False
        
    if os.path.exists(IMG_PATH):
        print("File still exists after delete!")
        return False
        
    print("File successfully deleted.")
    
    # UNDO
    r = client.post("/api/sablon_sil_geri_al", headers=headers)
    print(f"Undo response: {r.status_code} {r.get_data(as_text=True)}")
    
    if r.status_code != 200 or not r.get_json().get("success"):
        print("Undo failed.")
        return False
        
    if not os.path.exists(IMG_PATH):
        print("File not restored!")
        return False
        
    restored_hash = get_hash(IMG_PATH)
    print(f"Restored Hash: {restored_hash}")
    
    if orig_hash != restored_hash:
        print("HASH MISMATCH! Immutable source violated.")
        return False
        
    print("T1 UNDO TEST: PASS")
    return True

if __name__ == "__main__":
    trash = rf"C:\Users\oguzc\OneDrive\Masaüstü\GörselÜretme-ve-Mockup Otomasyonu\SILINEN_SABLONLAR_COP_KUTUSU\{TMPL}"
    if not os.path.exists(IMG_PATH) and os.path.exists(trash):
        import shutil
        shutil.move(trash, IMG_PATH)
    test_t1_undo()
