import os
import sys
import json
import sqlite3
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

from core.db import get_all_ayarlar, save_settings_node, save_category, save_template, delete_template, save_templates_bulk
from core.template_intelligence import TemplateAnalyzer, save_template_profile, TemplateSelector
import hashlib
import uuid

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

@app.route('/api/templates/bulk-save-geometry', methods=['POST'])
def api_bulk_save_geometry():
    try:
        req = request.json
        templates_list = req.get("templates", [])
        if not templates_list:
            return jsonify({"success": False, "error": "Boş liste gönderildi"}), 400
            
        success, result = save_templates_bulk(templates_list)
        if success:
            return jsonify({"success": True, "saved_count": result})
        else:
            return jsonify({"success": False, "error": result}), 500
    except Exception as e:
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
                            dest_dir = os.path.join(BASE_DIR, "YENI-BOS MOCKUP SABLON HAVUZU", cat)
                            os.makedirs(dest_dir, exist_ok=True)
                            dest_path = os.path.join(dest_dir, stem + "-beyazlatilmis-batch.png")
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
            trash_json = os.path.join(trash_dir, f"{stem}_meta.json")
            meta_data = {
                "kategori": active_cat,
                "sablon": active_tmpl,
                "stem": stem,
                "conf": removed_conf
            }
            with open(trash_json, "w", encoding="utf-8") as _tf:
                json.dump(meta_data, _tf, indent=2)
            
            src_img = os.path.join(BASE_DIR, "2_SABLON_HAVUZU", active_cat, active_tmpl)
            if os.path.exists(src_img):
                shutil.move(src_img, os.path.join(trash_dir, active_tmpl))
            
            return jsonify({"success": True})
        return jsonify({"success": False, "error": "Sablon bulunamadi"}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/sablon_sil_geri_al', methods=['POST'])
def api_sablon_sil_geri_al():
    try:
        import glob
        trash_dir = os.path.join(BASE_DIR, "SILINEN_SABLONLAR_COP_KUTUSU")
        metas = sorted(glob.glob(os.path.join(trash_dir, "*_meta.json")), key=os.path.getmtime, reverse=True)
        if not metas:
            return jsonify({"success": False, "error": "Çöp kutusunda geri alınacak şablon yok"}), 404
            
        meta_path = metas[0]
        with open(meta_path, 'r', encoding='utf-8') as _f:
            meta = json.load(_f)
            
        cat = meta.get('kategori')
        tmpl = meta.get('sablon')
        conf = meta.get('conf', {})
        
        # Resmi geri tasi
        cop_png = os.path.join(trash_dir, tmpl)
        restore_dir = os.path.join(BASE_DIR, "2_SABLON_HAVUZU", cat)
        os.makedirs(restore_dir, exist_ok=True)
        restore_path = os.path.join(restore_dir, tmpl)
        if os.path.exists(cop_png):
            shutil.move(cop_png, restore_path)
            
        # DB'ye geri yaz
        save_template(cat, tmpl, conf)
        
        # Metayi sil
        os.remove(meta_path)
        
        return jsonify({"success": True, "restored_tmpl": tmpl})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

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

@app.route('/api/templates/analyze', methods=['POST'])
def api_templates_analyze():
    try:
        active_cat = request.headers.get('X-Active-Category', '')
        active_tmpl = request.headers.get('X-Active-Template', '')
        if not active_cat or not active_tmpl:
            return jsonify({"success": False, "error": "Kategori/Sablon eksik"}), 400
            
        img_path = os.path.join(BASE_DIR, "2_SABLON_HAVUZU", active_cat, active_tmpl)
        if not os.path.exists(img_path):
            return jsonify({"success": False, "error": "Görsel bulunamadı"}), 404
            
        analyzer = TemplateAnalyzer()
        result = analyzer.analyze(img_path, active_cat)
        
        # Save to DB as proposed/unanalyzed/review_required
        db_path = os.path.join(BASE_DIR, "SABLON_V2_MIMARI", "ayarlar.db")
        uid = f"{active_cat}_{active_tmpl}"
        
        profile_data = {
            "template_uid": uid,
            "category": active_cat,
            "source_relative_path": f"{active_cat}/{active_tmpl}",
            "source_asset_sha256": result.get("source_asset_sha256"),
            "profile_version": "v2",
            "analyzer_version": result.get("analyzer_version"),
            "product_class": result.get("rule", {}).get("product_class", "Bilinmeyen"),
            "orientation": result.get("orientation", "UNKNOWN"),
            "print_policy": result.get("rule", {}).get("print_policy", "full_bleed"),
            "surface_quad": result.get("surface_quad"),
            "confidence_total": result.get("confidence_total", 0.0),
            "component_confidences": result.get("component_confidences", {}),
            "review_status": result.get("review_status", "UNANALYZED"),
            "manually_verified": True if result.get("provenance") == "MANUAL_PRIOR" else False
        }
        
        save_template_profile(db_path, profile_data)
        
        return jsonify({"success": True, "analysis": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/templates/approve', methods=['POST'])
def api_templates_approve():
    try:
        req = request.json
        uid = req.get("template_uid")
        if not uid:
            return jsonify({"success": False, "error": "Eksik parametre"}), 400
            
        db_path = os.path.join(BASE_DIR, "SABLON_V2_MIMARI", "ayarlar.db")
        conn = sqlite3.connect(db_path)
        conn.execute("UPDATE template_profiles SET review_status='APPROVED', manually_verified=1 WHERE template_uid=? AND is_active=1", (uid,))
        conn.commit()
        conn.close()
        
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/templates/batch_analyze', methods=['POST'])
def api_templates_batch_analyze():
    try:
        req = request.json
        category = req.get("category")
        if not category:
            return jsonify({"success": False, "error": "Kategori eksik"}), 400
            
        ayarlar = get_all_ayarlar()
        sablonlar = ayarlar.get("kategoriler", {}).get(category, {}).get("sablonlar", {})
        
        analyzer = TemplateAnalyzer()
        db_path = os.path.join(BASE_DIR, "SABLON_V2_MIMARI", "ayarlar.db")
        
        results = []
        for tmpl in sablonlar.keys():
            img_path = os.path.join(BASE_DIR, "2_SABLON_HAVUZU", category, tmpl)
            if os.path.exists(img_path):
                res = analyzer.analyze(img_path, category)
                uid = f"{category}_{tmpl}"
                profile_data = {
                    "template_uid": uid,
                    "category": category,
                    "source_relative_path": f"{category}/{tmpl}",
                    "source_asset_sha256": res.get("source_asset_sha256"),
                    "analyzer_version": res.get("analyzer_version"),
                    "orientation": res.get("orientation", "UNKNOWN"),
                    "surface_quad": res.get("surface_quad"),
                    "confidence_total": res.get("confidence_total", 0.0),
                    "component_confidences": res.get("component_confidences", {}),
                    "review_status": res.get("review_status", "UNANALYZED"),
                    "manually_verified": True if res.get("provenance") == "MANUAL_PRIOR" else False
                }
                save_template_profile(db_path, profile_data)
                results.append({"template": tmpl, "status": res.get("review_status")})
                
        return jsonify({"success": True, "results": results})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/templates/reject', methods=['POST'])
def api_templates_reject():
    try:
        req = request.json
        uid = req.get("template_uid")
        if not uid:
            return jsonify({"success": False, "error": "Eksik parametre"}), 400
            
        db_path = os.path.join(BASE_DIR, "SABLON_V2_MIMARI", "ayarlar.db")
        conn = sqlite3.connect(db_path)
        conn.execute("UPDATE template_profiles SET review_status='REJECTED', manually_verified=1 WHERE template_uid=? AND is_active=1", (uid,))
        conn.commit()
        conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/templates/update_corners', methods=['POST'])
def api_templates_update_corners():
    try:
        req = request.json
        uid = req.get("template_uid")
        corners = req.get("corners")
        if not uid or not corners:
            return jsonify({"success": False, "error": "Eksik parametre"}), 400
            
        db_path = os.path.join(BASE_DIR, "SABLON_V2_MIMARI", "ayarlar.db")
        conn = sqlite3.connect(db_path)
        conn.execute("UPDATE template_profiles SET surface_quad=?, review_status='APPROVED', manually_verified=1 WHERE template_uid=? AND is_active=1", (json.dumps(corners), uid))
        conn.commit()
        conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

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
