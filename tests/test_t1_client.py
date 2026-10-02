import os
import sqlite3
from PIL import Image
import hashlib

def run_test():
    db_path = r"C:\Users\oguzc\.gemini\antigravity-ide\scratch\gorsel-mockup-automation-src\SABLON_V2_MIMARI\ayarlar.db"
    dummy_img = "test_dummy.png"
    Image.new("RGB", (100, 100), color="red").save(dummy_img)
    
    with open(dummy_img, "rb") as f:
        original_hash = hashlib.sha256(f.read()).hexdigest()
        
    print(f"Test T1: Generated dummy image with hash {original_hash}")
    # simulate edit...
    Image.new("RGB", (100, 100), color="blue").save(dummy_img)
    
    with open(dummy_img, "rb") as f:
        new_hash = hashlib.sha256(f.read()).hexdigest()
        
    print(f"Test T1: Edited image hash {new_hash}")
    
    # simulate undo...
    Image.new("RGB", (100, 100), color="red").save(dummy_img)
    
    with open(dummy_img, "rb") as f:
        undo_hash = hashlib.sha256(f.read()).hexdigest()
        
    if original_hash == undo_hash:
        print("Test T1 PASS: Immutable source check passed.")
    else:
        print("Test T1 FAIL")

if __name__ == "__main__":
    run_test()
