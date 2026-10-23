# -*- coding: utf-8 -*-
"""Legacy 13-per-category tool: preserved, opt-in, no implicit cloud uploads."""
import argparse
from pathlib import Path
import os


def run_batch(runtime_root: Path, allow_cloud_upload: bool = False):
    import os
    import sys
    import json
    import time
    import zipfile
    from pathlib import Path
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    BASE_DIR = Path(runtime_root).resolve()
    sys.path.append(str(BASE_DIR / "99_SISTEM_MOTORLARI_VE_KODLAR" / "SISTEM_MOTORU"))
    
    from pc_master_factory import MockupRenderer, AsyncCloudUploader, PRODUCT_CATALOG
    
    AYARLAR_PATH = BASE_DIR / "99_SISTEM_MOTORLARI_VE_KODLAR" / "SISTEM_MOTORU" / "ayarlar.json"
    BASKI_DIR = BASE_DIR / "1_GELEN_KAGGLE_BASKILARI"
    SABLON_DIR = BASE_DIR / "2_SABLON_HAVUZU"
    OUT_ROOT = BASE_DIR / "3_URETILEN_MOCKUPLAR" / "TEST_13ER_TANE"
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    
    with open(AYARLAR_PATH, "r", encoding="utf-8") as f:
        ayarlar = json.load(f)
    
    kategoriler_conf = ayarlar.get("kategoriler", {})
    
    raw_h = BASKI_DIR / "M000001_H.png"
    raw_v = BASKI_DIR / "M000001_V.png"
    
    results = {}
    all_mockup_paths = []
    
    print("=== 13'ER TANE MOCKUP ÜRETİMİ BAŞLIYOR ===")
    start_time = time.time()
    
    for cat_key, prod_def in PRODUCT_CATALOG.items():
        cat_conf = kategoriler_conf.get(cat_key, {})
        sablonlar_dict = cat_conf.get("sablonlar", {})
        
        target_raw = raw_h if prod_def.orientation == "H" else raw_v
        if not target_raw.exists():
            print(f"[!] Ham baskı bulunamadı: {target_raw}")
            continue
            
        cat_out_dir = OUT_ROOT / cat_key
        cat_out_dir.mkdir(parents=True, exist_ok=True)
        
        # 13 şablon seç (veya mevcut kadar)
        available_templates = list(sablonlar_dict.keys())
        target_count = min(13, len(available_templates))
        selected_templates = available_templates[:target_count]
        
        print(f"\n[{cat_key}] Hedef: {target_count} şablon işleniyor...")
        results[cat_key] = []
        
        for i, s_name in enumerate(selected_templates, 1):
            s_conf = sablonlar_dict[s_name]
            
            # Dosya yolunu bul
            s_path = SABLON_DIR / prod_def.folder_name / s_name
            if not s_path.exists():
                s_path = BASE_DIR / "2_SABLON_HAVUZU_ORIJINAL_YEDEK" / cat_key / s_name
                
            if not s_path.exists():
                print(f"  [x] Şablon dosyası bulunamadı: {s_name}")
                continue
                
            out_filename = f"TEST_{prod_def.barkod_prefix}_{i:02d}_{Path(s_name).stem}.jpg"
            out_path = cat_out_dir / out_filename
            
            success = MockupRenderer.process_mockup(
                raw_path=target_raw,
                template_path=s_path,
                config=s_conf,
                is_glass=prod_def.is_glass,
                output_path=out_path
            )
            
            if success:
                results[cat_key].append({
                    "index": i,
                    "sablon_adi": s_name,
                    "local_path": str(out_path),
                    "filename": out_filename
                })
                all_mockup_paths.append((cat_key, out_path))
                print(f"  [{i}/{target_count}] OK: {out_filename}")
            else:
                print(f"  [{i}/{target_count}] HATA: {s_name}")
    
    render_duration = time.time() - start_time
    print(f"\n=== {len(all_mockup_paths)} MOCKUP ÜRETİLDİ! (Süre: {render_duration:.2f} sn) ===")
    
    # ZIP Paketleme
    zip_path = BASE_DIR / "TEST_13ER_TANE_MOCKUPLAR.zip"
    print(f"\nZIP paketi oluşturuluyor: {zip_path.name}")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for cat_key, m_path in all_mockup_paths:
            arcname = f"{cat_key}/{m_path.name}"
            zipf.write(m_path, arcname)
    
    print(f"ZIP boyutu: {zip_path.stat().st_size / (1024*1024):.2f} MB")
    
    cloud_links = {}
    if allow_cloud_upload:
        # Bulut Yükleme (ImgBB)
        print("\n=== BULUT YÜKLEME BAŞLIYOR (ImgBB) ===")
        uploader = AsyncCloudUploader()
        cloud_links = {}
        
        def upload_item(cat_key, m_path):
            url = uploader.upload_sync(m_path)
            return cat_key, m_path.name, url
        
        uploaded_count = 0
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(upload_item, cat, p) for cat, p in all_mockup_paths]
            for fut in as_completed(futures):
                cat_key, fname, url = fut.result()
                if cat_key not in cloud_links:
                    cloud_links[cat_key] = []
                cloud_links[cat_key].append({"filename": fname, "url": url})
                uploaded_count += 1
                if url:
                    print(f"[{uploaded_count}/{len(all_mockup_paths)}] Bulut Yüklendi: {fname} -> {url}")
                else:
                    print(f"[{uploaded_count}/{len(all_mockup_paths)}] Bulut Atlandı/Başarısız: {fname}")
        
        
    out_json = BASE_DIR / "TEST_13ER_TANE_SONUCLAR.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump({
            "toplam_mockup": len(all_mockup_paths),
            "zip_dosyasi": str(zip_path),
            "kategoriler": cloud_links
        }, f, indent=2, ensure_ascii=False)
    
    print("\n=== TÜM İŞLEM TAMAMLANDI! Sonuçlar JSON'a kaydedildi. ===")
    

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", type=Path)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--allow-cloud-upload", action="store_true")
    args = parser.parse_args(argv)
    if not args.execute:
        print("PLAN_ONLY: tool preserved. No files written or uploaded.")
        return 0
    if not args.runtime_root or not (args.runtime_root / "SABLON_V2_MIMARI" / "ayarlar.db").is_file():
        print("BLOCKED: explicit validated --runtime-root required.")
        return 2
    if args.allow_cloud_upload:
        print("BLOCKED: legacy direct cloud upload disabled for release safety.")
        return 2
    os.environ["MOCKUP_RUNTIME_WORKSPACE"] = str(args.runtime_root.resolve())
    run_batch(args.runtime_root, False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
