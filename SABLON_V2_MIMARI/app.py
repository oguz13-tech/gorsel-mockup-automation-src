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

from core.db import init_db, get_all_ayarlar, save_settings_node, save_category, save_template, delete_template, save_templates_bulk
from core.template_intelligence import TemplateAnalyzer, save_template_profile, TemplateSelector, GeometryValidator, CategoryRuleEngine
import hashlib
import uuid

app = Flask(__name__)

# The UI and factory share the same SQLite schema. Ensure a clean checkout can
# start safely without requiring a separate migration command first.
init_db()

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
    """Return a review-only geometry proposal from the current analyzer.

    This endpoint intentionally does NOT persist or approve geometry. The UI can
    move the four proposed points and only /api/templates/update_corners can turn
    a human-confirmed quad into APPROVED geometry.
    """
    try:
        active_cat = request.headers.get('X-Active-Category', '')
        active_tmpl = request.headers.get('X-Active-Template', '')
        if not active_cat or not active_tmpl:
            return jsonify({"success": False, "error": "Parametre eksik"}), 400

        img_path = _safe_template_path(active_cat, active_tmpl)
        if not os.path.exists(img_path):
            return jsonify({"success": False, "error": "Resim dosyasi bulunamadi"}), 404

        img_cv = cv2.imdecode(
            np.fromfile(img_path, dtype=np.uint8),
            cv2.IMREAD_COLOR,
        )
        if img_cv is None:
            return jsonify({"success": False, "error": "Resim okunamadi"}), 500

        analyzer = TemplateAnalyzer()
        analysis = analyzer.analyze(
            img_path,
            active_cat,
            manual_geometry_prior=None,
        )
        corners = analysis.get("surface_quad")
        engine = "template_analyzer"

        # Conservative compatibility fallback: legacy detector may still find a
        # proposal when every EPIC-3 generator fails. It remains review-only.
        if corners is None:
            legacy = detect_document_corners(img_cv)
            if legacy is not None:
                corners = (
                    legacy.tolist()
                    if hasattr(legacy, "tolist")
                    else legacy
                )
                engine = "legacy_fallback"

        if corners is None:
            return jsonify({"success": False, "error": "Kose bulunamadi"}), 404

        try:
            arr = np.asarray(corners, dtype=np.float32)
            valid, reason = GeometryValidator.is_valid_quad(
                arr,
                img_cv.shape[1],
                img_cv.shape[0],
            )
            if not valid:
                return jsonify({
                    "success": False,
                    "error": f"Algilanan geometri gecersiz: {reason}",
                }), 422
            corners = (
                GeometryValidator.canonical_sort(arr)
                .astype(float)
                .tolist()
            )
        except Exception as exc:
            return jsonify({
                "success": False,
                "error": f"Algilanan geometri islenemedi: {exc}",
            }), 422

        # Lightweight legacy occlusion hints are UI assistance only. Production
        # object-aware restoration uses the Grounding-DINO/SAM path plus manual
        # mask corrections.
        try:
            occlusion_data = detect_occlusion_boxes(img_cv, corners)
        except Exception:
            occlusion_data = []

        return jsonify({
            "success": True,
            "corners": corners,
            "occlusions": occlusion_data,
            "engine": engine,
            "confidence": float(analysis.get("confidence_total", 0.0) or 0.0),
            "component_confidences": analysis.get("component_confidences", {}),
            "review_status": "REVIEW_REQUIRED",
            "nominal_aspect": analysis.get("nominal_aspect", "UNKNOWN"),
        })
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        logger.exception("Otomatik kose onerisi hatasi")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/sablon_sil', methods=['POST'])
def api_sablon_sil():
    """Move a template to a reversible trash record without risking geometry."""
    meta_path = None
    moved_src = None
    moved_dst = None
    try:
        active_cat = request.headers.get('X-Active-Category', '')
        active_tmpl = request.headers.get('X-Active-Template', '')
        if not active_cat or not active_tmpl:
            return jsonify({"success": False, "error": "Kategori/sablon eksik"}), 400

        _ayarlar = get_all_ayarlar()
        category_data = _ayarlar.get('kategoriler', {}).get(active_cat, {})
        templates = category_data.get('sablonlar', {})
        if active_tmpl not in templates:
            return jsonify({"success": False, "error": "Sablon bulunamadi"}), 404

        # Resolve through the same path-safety gate used by review operations.
        src_img = _safe_template_path(active_cat, active_tmpl)
        removed_conf = templates[active_tmpl]

        trash_dir = os.path.join(BASE_DIR, "SILINEN_SABLONLAR_COP_KUTUSU")
        os.makedirs(trash_dir, exist_ok=True)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        token = uuid.uuid4().hex[:8]
        safe_stem = Path(active_tmpl).stem
        trash_image_name = f"{active_cat}__{safe_stem}__{stamp}_{token}{Path(active_tmpl).suffix}"
        trash_img = os.path.join(trash_dir, trash_image_name)
        meta_name = f"{active_cat}__{safe_stem}__{stamp}_{token}_meta.json"
        meta_path = os.path.join(trash_dir, meta_name)

        # Persist recovery metadata atomically BEFORE touching source/DB.
        meta_data = {
            "kategori": active_cat,
            "sablon": active_tmpl,
            "conf": removed_conf,
            "trash_image_name": trash_image_name,
            "deleted_at": stamp,
        }
        tmp_meta = meta_path + ".tmp"
        with open(tmp_meta, "w", encoding="utf-8") as handle:
            json.dump(meta_data, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_meta, meta_path)

        if os.path.exists(src_img):
            shutil.move(src_img, trash_img)
            moved_src = src_img
            moved_dst = trash_img

        # Delete the UI row only after recovery material is durable.
        delete_template(active_cat, active_tmpl)
        return jsonify({"success": True, "trash_record": meta_name})
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        # Best-effort rollback: never knowingly leave a source moved away while
        # the DB still points to it because the delete operation failed.
        if moved_dst and moved_src and os.path.exists(moved_dst) and not os.path.exists(moved_src):
            try:
                os.makedirs(os.path.dirname(moved_src), exist_ok=True)
                shutil.move(moved_dst, moved_src)
            except Exception:
                logger.exception("Sablon silme rollback gorsel geri tasima basarisiz")
        if meta_path and os.path.exists(meta_path):
            try:
                os.remove(meta_path)
            except OSError:
                pass
        logger.exception("Sablon cop kutusuna tasinamadi")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/sablon_sil_geri_al', methods=['POST'])
def api_sablon_sil_geri_al():
    try:
        import glob
        trash_dir = os.path.join(BASE_DIR, "SILINEN_SABLONLAR_COP_KUTUSU")
        metas = sorted(
            glob.glob(os.path.join(trash_dir, "*_meta.json")),
            key=os.path.getmtime,
            reverse=True,
        )
        if not metas:
            return jsonify({
                "success": False,
                "error": "Çöp kutusunda geri alınacak şablon yok",
            }), 404

        meta_path = metas[0]
        with open(meta_path, 'r', encoding='utf-8') as handle:
            meta = json.load(handle)

        cat = meta.get('kategori')
        tmpl = meta.get('sablon')
        conf = meta.get('conf', {})
        trash_image_name = meta.get('trash_image_name') or tmpl
        if not cat or not tmpl:
            return jsonify({"success": False, "error": "Çöp meta verisi bozuk"}), 422

        source_in_trash = os.path.join(trash_dir, trash_image_name)
        restore_dir = os.path.join(BASE_DIR, "2_SABLON_HAVUZU", cat)
        os.makedirs(restore_dir, exist_ok=True)
        restore_path = os.path.join(restore_dir, tmpl)

        if os.path.exists(restore_path):
            return jsonify({
                "success": False,
                "error": "Aynı isimde aktif şablon zaten var; üzerine yazılmadı.",
            }), 409

        moved_back = False
        try:
            if os.path.exists(source_in_trash):
                shutil.move(source_in_trash, restore_path)
                moved_back = True
            save_template(cat, tmpl, conf)
        except Exception:
            if moved_back and os.path.exists(restore_path):
                try:
                    shutil.move(restore_path, source_in_trash)
                except Exception:
                    logger.exception("Sablon geri alma rollback basarisiz")
            raise

        os.remove(meta_path)
        return jsonify({"success": True, "restored_tmpl": tmpl})
    except Exception as e:
        logger.exception("Sablon geri alma hatasi")
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

def _safe_template_path(category: str, template_name: str) -> str:
    """Resolve a template source path without allowing traversal outside the pool."""
    pool_root = os.path.abspath(os.path.join(BASE_DIR, "2_SABLON_HAVUZU"))
    candidate = os.path.abspath(os.path.join(pool_root, str(category), str(template_name)))
    try:
        if os.path.commonpath([pool_root, candidate]) != pool_root:
            raise ValueError("Gecersiz sablon yolu")
    except ValueError as exc:
        raise ValueError("Gecersiz sablon yolu") from exc
    return candidate


def _safe_profile_relative_path(relative_path: str) -> str:
    pool_root = os.path.abspath(os.path.join(BASE_DIR, "2_SABLON_HAVUZU"))
    candidate = os.path.abspath(os.path.join(pool_root, str(relative_path)))
    try:
        if os.path.commonpath([pool_root, candidate]) != pool_root:
            raise ValueError("Gecersiz profil kaynak yolu")
    except ValueError as exc:
        raise ValueError("Gecersiz profil kaynak yolu") from exc
    return candidate


def _sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_matching_manual_prior(db_path, uid, img_path):
    """Load trusted manual geometry only when it belongs to the current source bytes."""
    current_hash = _sha256_file(img_path)

    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            """SELECT surface_quad, outer_quad, source_asset_sha256
               FROM template_profiles
               WHERE template_uid=? AND is_active=1
                 AND manually_verified=1 AND review_status='APPROVED'""",
            (uid,)
        ).fetchone()
    finally:
        conn.close()

    if not row or not row[0] or not row[2] or row[2] != current_hash:
        return None

    try:
        prior = {"surface_quad": json.loads(row[0])}
        if row[1]:
            prior["outer_quad"] = json.loads(row[1])
        return prior
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


@app.route('/api/templates/foreground_detect', methods=['POST'])
def api_templates_foreground_detect():
    """Suggest object-selection boxes using Grounding-DINO + SAM evidence.

    The endpoint is review assistance only: it does not alter template files,
    settings, profiles, or approval state. Returned boxes are copied into the
    browser mask editor only after the user sees the result.
    """
    try:
        req = request.get_json(silent=True) or {}
        category = str(req.get("category") or request.headers.get(
            'X-Active-Category', ''
        )).strip()
        template = str(req.get("template") or request.headers.get(
            'X-Active-Template', ''
        )).strip()
        corners = req.get("corners")

        if not category or not template or corners is None:
            return jsonify({
                "success": False,
                "error": "Kategori, sablon ve 4 kose gerekli.",
            }), 400

        img_path = _safe_template_path(category, template)
        image = cv2.imdecode(
            np.fromfile(img_path, dtype=np.uint8),
            cv2.IMREAD_COLOR,
        )
        if image is None:
            return jsonify({"success": False, "error": "Gorsel okunamadi."}), 422

        try:
            quad = np.asarray(corners, dtype=np.float32)
        except (TypeError, ValueError):
            return jsonify({"success": False, "error": "Kose verisi gecersiz."}), 422
        if quad.shape != (4, 2) or not np.isfinite(quad).all():
            return jsonify({"success": False, "error": "Tam 4 adet sayisal kose gerekli."}), 422

        h, w = image.shape[:2]
        valid, reason = GeometryValidator.is_valid_quad(quad, w, h)
        if not valid:
            return jsonify({
                "success": False,
                "error": f"Maske analizi icin geometri gecersiz: {reason}",
            }), 422
        quad = GeometryValidator.canonical_sort(quad).astype(float).tolist()

        sm_dir = os.path.join(
            BASE_DIR,
            "99_SISTEM_MOTORLARI_VE_KODLAR",
            "SISTEM_MOTORU",
        )
        if sm_dir not in sys.path:
            sys.path.append(sm_dir)

        try:
            from foreground_ai import ForegroundAIEngine
        except Exception as exc:
            return jsonify({
                "success": False,
                "error": f"On plan AI kullanilamiyor: {exc}",
                "code": "FOREGROUND_AI_UNAVAILABLE",
            }), 503

        result = ForegroundAIEngine.get_instance().detect_foreground(
            image,
            quad,
            prompts=req.get("prompts"),
            box_threshold=float(req.get("box_threshold", 0.20)),
            text_threshold=float(req.get("text_threshold", 0.20)),
            min_surface_overlap=float(req.get("min_surface_overlap", 0.02)),
            feather=float(req.get("feather", 1.0)),
        )
        if not result.get("success"):
            return jsonify({
                "success": False,
                "error": result.get("reason", "On plan analizi basarisiz."),
                "code": "FOREGROUND_AI_FAILED",
            }), 422

        objects = result.get("objects") or []
        boxes = [
            obj.get("box")
            for obj in objects
            if isinstance(obj, dict)
            and isinstance(obj.get("box"), list)
            and len(obj.get("box")) == 4
        ]

        return jsonify({
            "success": True,
            "boxes": boxes,
            "objects": objects,
            "confidence": float(result.get("confidence", 0.0) or 0.0),
            "reason": result.get("reason", "ok"),
            "review_only": True,
        })
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception as exc:
        logger.exception("On plan AI review analizi hatasi")
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route('/api/templates/analyze', methods=['POST'])
def api_templates_analyze():
    try:
        active_cat = request.headers.get('X-Active-Category', '')
        active_tmpl = request.headers.get('X-Active-Template', '')
        if not active_cat or not active_tmpl:
            return jsonify({"success": False, "error": "Kategori/Sablon eksik"}), 400
            
        img_path = _safe_template_path(active_cat, active_tmpl)
        if not os.path.exists(img_path):
            return jsonify({"success": False, "error": "Görsel bulunamadı"}), 404
            
        uid = f"{active_cat}_{active_tmpl}"
        db_path = os.path.join(BASE_DIR, "SABLON_V2_MIMARI", "ayarlar.db")
        
        # Explicit request geometry may be used for this analysis. DB geometry is trusted
        # only when it was manually verified for the exact same source bytes.
        manual_prior = None
        if request.is_json:
            requested_prior = request.json.get("manual_geometry_prior")
            if isinstance(requested_prior, dict):
                manual_prior = requested_prior

        if not manual_prior:
            manual_prior = _load_matching_manual_prior(db_path, uid, img_path)

        analyzer = TemplateAnalyzer()
        result = analyzer.analyze(img_path, active_cat, manual_geometry_prior=manual_prior)
        
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
            "nominal_aspect": result.get("nominal_aspect", "UNKNOWN"),
            "print_policy": result.get("rule", {}).get("print_policy", "full_bleed"),
            "surface_quad": result.get("surface_quad"),
            "outer_quad": result.get("outer_quad"),
            "confidence_total": result.get("confidence_total", 0.0),
            "component_confidences": result.get("component_confidences", {}),
            "review_status": result.get("review_status", "UNANALYZED"),
            "manually_verified": False
        }
        
        save_template_profile(db_path, profile_data)
        
        return jsonify({"success": True, "analysis": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/templates/approve', methods=['POST'])
def api_templates_approve():
    """Approve only geometry that still belongs to the exact current source bytes."""
    try:
        req = request.get_json(silent=True) or {}
        uid = req.get("template_uid")
        if not uid:
            return jsonify({"success": False, "error": "Eksik parametre"}), 400

        db_path = os.path.join(BASE_DIR, "SABLON_V2_MIMARI", "ayarlar.db")
        conn = sqlite3.connect(db_path)
        try:
            row = conn.execute(
                """SELECT id, surface_quad, source_asset_sha256, source_relative_path
                   FROM template_profiles
                   WHERE template_uid=? AND is_active=1""",
                (uid,),
            ).fetchone()
            if not row:
                return jsonify({"success": False, "error": "Aktif profil bulunamadi"}), 404

            profile_id, surface_quad_json, source_hash, relative_path = row
            if not surface_quad_json or not source_hash or not relative_path:
                return jsonify({"success": False, "error": "Profil geometrisi/kaynak kimligi eksik"}), 409

            source_path = _safe_profile_relative_path(relative_path)
            if not os.path.exists(source_path):
                return jsonify({"success": False, "error": "Profil kaynak gorseli bulunamadi"}), 409

            current_hash = _sha256_file(source_path)
            if current_hash != source_hash:
                return jsonify({
                    "success": False,
                    "error": "Kaynak gorsel degismis. Onaydan once yeniden analiz gerekli.",
                    "code": "STALE_SOURCE_CHANGED",
                }), 409

            image = cv2.imdecode(np.fromfile(source_path, dtype=np.uint8), cv2.IMREAD_COLOR)
            if image is None:
                return jsonify({"success": False, "error": "Kaynak gorsel okunamadi"}), 422

            try:
                quad = np.asarray(json.loads(surface_quad_json), dtype=np.float32)
            except (TypeError, ValueError, json.JSONDecodeError):
                return jsonify({"success": False, "error": "Kayitli geometri gecersiz"}), 422

            h, w = image.shape[:2]
            valid, reason = GeometryValidator.is_valid_quad(quad, w, h)
            if not valid:
                return jsonify({
                    "success": False,
                    "error": f"Geometri onaylanamaz: {reason}",
                }), 422

            conn.execute(
                """UPDATE template_profiles
                   SET review_status='APPROVED', manually_verified=1,
                       updated_at=CURRENT_TIMESTAMP
                   WHERE id=?""",
                (profile_id,),
            )
            conn.commit()
        finally:
            conn.close()

        return jsonify({"success": True})
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
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
            img_path = _safe_template_path(category, tmpl)
            if os.path.exists(img_path):
                uid = f"{category}_{tmpl}"
                manual_prior = _load_matching_manual_prior(db_path, uid, img_path)
                res = analyzer.analyze(img_path, category, manual_geometry_prior=manual_prior)
                profile_data = {
                    "template_uid": uid,
                    "category": category,
                    "source_relative_path": f"{category}/{tmpl}",
                    "source_asset_sha256": res.get("source_asset_sha256"),
                    "profile_version": "v2",
                    "analyzer_version": res.get("analyzer_version"),
                    "product_class": res.get("rule", {}).get("product_class", "Bilinmeyen"),
                    "orientation": res.get("orientation", "UNKNOWN"),
                    "nominal_aspect": res.get("nominal_aspect", "UNKNOWN"),
                    "print_policy": res.get("rule", {}).get("print_policy", "full_bleed"),
                    "surface_quad": res.get("surface_quad"),
                    "outer_quad": res.get("outer_quad"),
                    "confidence_total": res.get("confidence_total", 0.0),
                    "component_confidences": res.get("component_confidences", {}),
                    "review_status": res.get("review_status", "UNANALYZED"),
                    "manually_verified": False
                }
                save_template_profile(db_path, profile_data)
                results.append({"template": tmpl, "status": res.get("review_status")})
                
        return jsonify({"success": True, "results": results})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/templates/reject', methods=['POST'])
def api_templates_reject():
    try:
        req = request.get_json(silent=True) or {}
        uid = req.get("template_uid")
        if not uid:
            return jsonify({"success": False, "error": "Eksik parametre"}), 400

        db_path = os.path.join(BASE_DIR, "SABLON_V2_MIMARI", "ayarlar.db")
        conn = sqlite3.connect(db_path)
        try:
            row = conn.execute(
                """SELECT id, source_asset_sha256, source_relative_path
                   FROM template_profiles
                   WHERE template_uid=? AND is_active=1""",
                (uid,),
            ).fetchone()
            if not row:
                return jsonify({"success": False, "error": "Aktif profil bulunamadi"}), 404

            profile_id, source_hash, relative_path = row
            if source_hash and relative_path:
                source_path = _safe_profile_relative_path(relative_path)
                if os.path.exists(source_path):
                    current_hash = _sha256_file(source_path)
                    if current_hash != source_hash:
                        return jsonify({
                            "success": False,
                            "error": "Kaynak gorsel degismis. Eski profil reddedilmeden once yeniden analiz gerekli.",
                            "code": "STALE_SOURCE_CHANGED",
                        }), 409

            conn.execute(
                """UPDATE template_profiles
                   SET review_status='REJECTED', manually_verified=1,
                       updated_at=CURRENT_TIMESTAMP
                   WHERE id=?""",
                (profile_id,),
            )
            conn.commit()
        finally:
            conn.close()

        return jsonify({"success": True})
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/templates/update_corners', methods=['POST'])
def api_templates_update_corners():
    """Validate and atomically approve a human-corrected quad.

    A user may approve directly from the editor even when no analyzer profile
    exists yet. In that case this endpoint creates a source-hash-bound manual
    profile instead of forcing an extra "analyze" click. The legacy templates
    JSON stored in SQLite is updated in the same transaction so re-opening the
    editor shows the exact approved corners.
    """
    try:
        req = request.get_json(silent=True) or {}
        uid = str(req.get("template_uid") or "").strip()
        corners = req.get("corners")
        req_category = str(req.get("category") or "").strip()
        req_template = str(req.get("template") or "").strip()
        if not uid or corners is None:
            return jsonify({"success": False, "error": "Eksik parametre"}), 400

        db_path = os.path.join(BASE_DIR, "SABLON_V2_MIMARI", "ayarlar.db")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                """SELECT id, source_asset_sha256, source_relative_path
                   FROM template_profiles
                   WHERE template_uid=? AND is_active=1""",
                (uid,),
            ).fetchone()

            if row:
                profile_id = int(row["id"])
                source_hash = row["source_asset_sha256"]
                relative_path = row["source_relative_path"]
                if not source_hash or not relative_path:
                    return jsonify({
                        "success": False,
                        "error": "Profil kaynak kimligi eksik",
                    }), 409

                source_path = _safe_profile_relative_path(relative_path)
                if not os.path.exists(source_path):
                    return jsonify({
                        "success": False,
                        "error": "Profil kaynak gorseli bulunamadi",
                    }), 409

                current_hash = _sha256_file(source_path)
                if current_hash != source_hash:
                    return jsonify({
                        "success": False,
                        "error": (
                            "Kaynak gorsel degismis. Koseleri kaydetmeden once "
                            "yeniden analiz gerekli."
                        ),
                        "code": "STALE_SOURCE_CHANGED",
                    }), 409

                category_name, template_name = (
                    str(relative_path).replace("\\", "/").split("/", 1)
                )
            else:
                if not req_category or not req_template:
                    return jsonify({
                        "success": False,
                        "error": (
                            "Profil yok. Dogrudan onay icin category/template "
                            "bilgisi gerekli."
                        ),
                    }), 409
                expected_uid = f"{req_category}_{req_template}"
                if uid != expected_uid:
                    return jsonify({
                        "success": False,
                        "error": "Template kimligi kategori/dosya ile uyusmuyor.",
                    }), 409

                source_path = _safe_template_path(req_category, req_template)
                if not os.path.exists(source_path):
                    return jsonify({
                        "success": False,
                        "error": "Kaynak gorsel bulunamadi.",
                    }), 404
                source_hash = _sha256_file(source_path)
                relative_path = f"{req_category}/{req_template}"
                category_name = req_category
                template_name = req_template
                profile_id = None

            image = cv2.imdecode(
                np.fromfile(source_path, dtype=np.uint8),
                cv2.IMREAD_COLOR,
            )
            if image is None:
                return jsonify({
                    "success": False,
                    "error": "Kaynak gorsel okunamadi",
                }), 422
            h, w = image.shape[:2]

            try:
                quad = np.asarray(corners, dtype=np.float32)
            except (TypeError, ValueError):
                return jsonify({
                    "success": False,
                    "error": "Kose koordinatlari sayisal olmali",
                }), 422

            if quad.shape != (4, 2) or not np.isfinite(quad).all():
                return jsonify({
                    "success": False,
                    "error": "Tam olarak 4 adet gecerli 2D kose gerekli",
                }), 422

            valid, reason = GeometryValidator.is_valid_quad(quad, w, h)
            if not valid:
                return jsonify({
                    "success": False,
                    "error": f"Gecersiz geometri: {reason}",
                }), 422

            canonical = GeometryValidator.canonical_sort(quad).astype(float)
            top = np.linalg.norm(canonical[1] - canonical[0])
            bottom = np.linalg.norm(canonical[2] - canonical[3])
            left = np.linalg.norm(canonical[3] - canonical[0])
            right = np.linalg.norm(canonical[2] - canonical[1])
            avg_w = max(1e-6, float((top + bottom) * 0.5))
            avg_h = max(1e-6, float((left + right) * 0.5))
            aspect = avg_w / avg_h
            orientation = (
                "H" if aspect > 1.05
                else ("V" if aspect < 0.95 else "SQUARE")
            )

            rule = CategoryRuleEngine.get_rule_by_folder(category_name)
            metadata_orientation = rule.get("expected_orientation", "ANY")
            if metadata_orientation not in ("H", "V"):
                metadata_orientation = orientation
            nominal_value = CategoryRuleEngine.get_nominal_aspect(
                category_name,
                metadata_orientation,
            )
            nominal_aspect = (
                f"{nominal_value:.8f}".rstrip("0").rstrip(".")
                if nominal_value is not None
                else "UNKNOWN"
            )

            manual_components = {
                "manual_prior": 1.0,
                "area_ratio": float(
                    abs(cv2.contourArea(canonical.astype(np.float32)))
                    / float(w * h)
                ),
                "line_score": 1.0,
                "candidate_agreement": 1.0,
                "orientation_score": 1.0,
            }

            if profile_id is None:
                cur = conn.execute(
                    """INSERT INTO template_profiles (
                           template_uid, category, source_relative_path,
                           source_asset_sha256, profile_version,
                           analyzer_version, product_class, orientation,
                           nominal_aspect, geometry_type, print_policy,
                           surface_quad, outer_quad, surface_mask_path,
                           material, has_frame, has_mat, has_reflection,
                           has_occlusion, confidence_total,
                           component_confidences, review_status,
                           manually_verified, is_active
                       ) VALUES (
                           ?, ?, ?, ?, 'v2', 'manual-v1', ?, ?, ?, 'quad', ?,
                           ?, NULL, NULL, 'default', ?, ?, ?, 0, 1.0, ?,
                           'APPROVED', 1, 1
                       )""",
                    (
                        uid,
                        category_name,
                        relative_path,
                        source_hash,
                        rule.get("product_class", "Bilinmeyen"),
                        orientation,
                        nominal_aspect,
                        rule.get("print_policy", "full_bleed"),
                        json.dumps(canonical.tolist()),
                        int(bool(rule.get("has_frame"))),
                        int(bool(rule.get("has_mat"))),
                        int(bool(rule.get("has_reflection"))),
                        json.dumps(manual_components),
                    ),
                )
                profile_id = int(cur.lastrowid)
            else:
                conn.execute(
                    """UPDATE template_profiles
                       SET surface_quad=?, orientation=?, nominal_aspect=?,
                           confidence_total=1.0, component_confidences=?,
                           review_status='APPROVED', manually_verified=1,
                           updated_at=CURRENT_TIMESTAMP
                       WHERE id=?""",
                    (
                        json.dumps(canonical.tolist()),
                        orientation,
                        nominal_aspect,
                        json.dumps(manual_components),
                        profile_id,
                    ),
                )

            # Keep editor state in sync without replacing any on_plan/other
            # legacy fields. The trusted production geometry remains the
            # source-hash-bound template_profile above.
            legacy_row = conn.execute(
                """SELECT data FROM templates
                   WHERE category_id=? AND filename=?""",
                (category_name, template_name),
            ).fetchone()
            if legacy_row:
                try:
                    legacy_data = json.loads(legacy_row["data"])
                except (TypeError, json.JSONDecodeError):
                    legacy_data = {}
                if not isinstance(legacy_data, dict):
                    legacy_data = {}
                legacy_data["tip"] = "perspektif"
                legacy_data["koseler"] = canonical.tolist()
                conn.execute(
                    """UPDATE templates SET data=?
                       WHERE category_id=? AND filename=?""",
                    (
                        json.dumps(legacy_data, ensure_ascii=False),
                        category_name,
                        template_name,
                    ),
                )

            conn.commit()
        finally:
            conn.close()

        return jsonify({
            "success": True,
            "profile_id": profile_id,
            "corners": canonical.tolist(),
            "orientation": orientation,
            "nominal_aspect": nominal_aspect,
        })
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        logger.exception("Manuel geometri onayi hatasi")
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
    data = request.get_json(silent=True) or {}
    filename = str(data.get('filename') or '')
    if not filename or os.path.basename(filename) != filename:
        return jsonify({"success": False, "error": "Gecersiz dosya adi"}), 400

    src = os.path.join(KAGGLE_BEKLEYENLER_DIR, filename)
    dst = os.path.join(KAGGLE_GELENLER_DIR, filename)
    if os.path.exists(src):
        import shutil
        os.makedirs(KAGGLE_GELENLER_DIR, exist_ok=True)
        shutil.move(src, dst)
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Dosya bulunamadi"}), 404

@app.route('/api/kaggle/reddet', methods=['POST'])
def api_kaggle_reddet():
    data = request.get_json(silent=True) or {}
    filename = str(data.get('filename') or '')
    if not filename or os.path.basename(filename) != filename:
        return jsonify({"success": False, "error": "Gecersiz dosya adi"}), 400

    src = os.path.join(KAGGLE_BEKLEYENLER_DIR, filename)
    if os.path.exists(src):
        # Reject is reversible: move to a timestamped recycle area instead of
        # permanently deleting user-generated artwork.
        import shutil
        recycle_dir = os.path.join(BASE_DIR, "_COP_KUTUSU", "KAGGLE_REJECTED")
        os.makedirs(recycle_dir, exist_ok=True)
        stem, ext = os.path.splitext(filename)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        dst = os.path.join(recycle_dir, f"{stem}__{stamp}{ext}")
        suffix = 1
        while os.path.exists(dst):
            dst = os.path.join(recycle_dir, f"{stem}__{stamp}_{suffix}{ext}")
            suffix += 1
        shutil.move(src, dst)
        return jsonify({"success": True, "recycled_to": os.path.basename(dst)})
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
    try:
        if os.path.commonpath([safe_base, file_path]) != safe_base:
            return "Yasak", 403
    except ValueError:
        return "Yasak", 403
    if os.path.isfile(file_path):
        return send_file(file_path)
    return "Bulunamadi", 404

if __name__ == '__main__':
    print("SABLON_V2_MIMARI (Flask MVC) Baslatiliyor... http://127.0.0.1:8080")
    threading.Timer(1.25, lambda: webbrowser.open('http://127.0.0.1:8080/')).start()
    app.run(host='127.0.0.1', port=8080, debug=True, use_reloader=False)
