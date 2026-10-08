import os
import sys
import json
import sqlite3
import base64
import time
import shutil
import subprocess
import cv2
import numpy as np
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file
import threading
import webbrowser

# Code comes from the checked-out source tree; mutable templates/DB/assets
# may live in a separate production workspace.
SOURCE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_runtime_override = str(os.environ.get("MOCKUP_RUNTIME_WORKSPACE") or "").strip()
BASE_DIR = os.path.abspath(
    os.path.expanduser(_runtime_override)
) if _runtime_override else SOURCE_ROOT

# Propagate the resolved runtime root to imported helpers and child processes.
os.environ["MOCKUP_RUNTIME_WORKSPACE"] = BASE_DIR

if SOURCE_ROOT not in sys.path:
    sys.path.append(SOURCE_ROOT)

from core.vision import (
    YEDEK_IMG_DIR, detect_document_corners, detect_occlusion_boxes, logger
)

from core.db import init_db, get_all_ayarlar, save_settings_node, save_category, save_template, delete_template, save_templates_bulk
from core.template_intelligence import TemplateAnalyzer, save_template_profile, TemplateSelector, GeometryValidator, CategoryRuleEngine
from core.factory_doctor import run_factory_doctor
from core.template_identity import (
    backfill_registry,
    extract_number,
    reserve_number,
)
import hashlib
import uuid

app = Flask(__name__)


def occlusion_plan_has_objects(plan) -> bool:
    """Only automatically detected object boxes prove an occluder exists."""
    if not isinstance(plan, dict):
        return False
    boxes = plan.get("object_boxes")
    return bool(isinstance(boxes, list) and boxes)


def resolve_reviewed_occlusion(
    existing_has_occlusion: bool,
    plan,
    occlusion_reviewed: bool = False,
) -> bool:
    """Resolve reviewed occlusion truth from automatic object evidence."""
    has_objects = occlusion_plan_has_objects(plan)
    if occlusion_reviewed:
        return has_objects
    return bool(existing_has_occlusion or has_objects)


def annotate_review_metadata(data: dict) -> dict:
    """Decorate UI template data with the ACTIVE profile review truth.

    The sidebar must never confuse "four coordinates exist" with "human
    APPROVED". Metadata is added only to the response object; no DB row or
    legacy template JSON is modified here.
    """
    if not isinstance(data, dict):
        return data
    db_path = os.path.join(BASE_DIR, "SABLON_V2_MIMARI", "ayarlar.db")
    if not os.path.isfile(db_path):
        return data

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """SELECT template_uid, category, source_relative_path,
                      review_status, manually_verified, is_active
               FROM template_profiles
               WHERE is_active=1"""
        ).fetchall()
    except Exception:
        return data
    finally:
        conn.close()

    uid_counts = {}
    for row in rows:
        uid = str(row["template_uid"] or "")
        uid_counts[uid] = uid_counts.get(uid, 0) + 1

    categories = data.get("kategoriler", {})
    for row in rows:
        category = str(row["category"] or "")
        templates = (
            categories.get(category, {}).get("sablonlar", {})
            if isinstance(categories, dict)
            else {}
        )
        if not isinstance(templates, dict):
            continue

        relative = str(row["source_relative_path"] or "").replace("\\", "/")
        filename = relative.split("/", 1)[-1] if relative else ""
        target_name = filename if filename in templates else None
        if target_name is None and filename:
            wanted_stem = Path(filename).stem
            matches = [
                name
                for name in templates
                if Path(name).stem == wanted_stem
            ]
            if len(matches) == 1:
                target_name = matches[0]
        if target_name is None:
            continue

        uid = str(row["template_uid"] or "")
        status = str(row["review_status"] or "UNANALYZED")
        if uid_counts.get(uid, 0) > 1:
            status = "AMBIGUOUS_DUPLICATE"

        template_data = templates.get(target_name)
        if isinstance(template_data, dict):
            template_data["_review_status"] = status
            template_data["_manually_verified"] = bool(
                row["manually_verified"]
            )
    return data


# The UI and factory share the same SQLite schema. Ensure a clean checkout can
# start safely without requiring a separate migration command first.
init_db()

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/tools')
def tools_center():
    return render_template('tools.html')


_ALLOWED_USER_TOOLS = {
    "rename",
    "convert",
    "watermark",
    "4k",
    "links",
    "seo_titles",
    "seo_descriptions",
}


@app.route('/api/tools/launch/<tool_name>', methods=['POST'])
def api_launch_user_tool(tool_name):
    """Launch one independent desktop tool without coupling it to the factory."""
    tool_name = str(tool_name or "").strip()
    if tool_name not in _ALLOWED_USER_TOOLS:
        return jsonify({
            "success": False,
            "error": "Bilinmeyen araç.",
        }), 404

    runner = Path(SOURCE_ROOT) / "SABLON_V2_MIMARI" / "tools_runner.py"
    if not runner.is_file():
        return jsonify({
            "success": False,
            "error": "Araç çalıştırıcısı bulunamadı.",
        }), 500

    env = os.environ.copy()
    env["MOCKUP_RUNTIME_WORKSPACE"] = BASE_DIR
    kwargs = {
        "cwd": SOURCE_ROOT,
        "env": env,
    }
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_CONSOLE

    try:
        process = subprocess.Popen(
            [sys.executable, str(runner), tool_name],
            **kwargs,
        )
        return jsonify({
            "success": True,
            "pid": int(process.pid),
            "message": (
                "Araç ayrı pencerede açıldı. Açılan seçim penceresinden "
                "işlem yapmak istediğiniz görselleri seçin."
            ),
        })
    except Exception as exc:
        logger.exception("Bağımsız araç başlatılamadı")
        return jsonify({
            "success": False,
            "error": str(exc),
        }), 500

@app.route('/api/ayarlar', methods=['GET', 'POST'])
def api_ayarlar():
    if request.method == 'GET':
        data = annotate_review_metadata(get_all_ayarlar())
        return jsonify(data)

    elif request.method == 'POST':
        try:
            new_data = request.json
            if "kategoriler" in new_data:
                for cat_name, cat_data in new_data["kategoriler"].items():
                    if "sablonlar" in cat_data:
                        for tmpl_name, tmpl_data in cat_data["sablonlar"].items():
                            bound_data = _bind_on_plan_source_identity(
                                cat_name,
                                tmpl_name,
                                tmpl_data,
                            )
                            save_template(cat_name, tmpl_name, bound_data)

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
            
        data = _bind_on_plan_source_identity(cat, tmpl, data)
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
            
        safe_templates = []
        for item in templates_list:
            if not isinstance(item, dict):
                return jsonify({
                    "success": False,
                    "error": "Geçersiz template kaydı",
                }), 400
            category = item.get("category")
            filename = item.get("filename")
            data = item.get("data")
            if not category or not filename or not isinstance(data, dict):
                return jsonify({
                    "success": False,
                    "error": "Bulk kayıtta category/filename/data eksik",
                }), 400
            safe_templates.append({
                "category": category,
                "filename": filename,
                "data": _bind_on_plan_source_identity(
                    category,
                    filename,
                    data,
                ),
            })

        success, result = save_templates_bulk(safe_templates)
        if success:
            return jsonify({"success": True, "saved_count": result})
        else:
            return jsonify({"success": False, "error": result}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/orijinal_yukle', methods=['POST'])
def api_orijinal_yukle():
    """Restore a template working image from the immutable original backup.

    The replacement is atomic. Any APPROVED profile bound to different source
    bytes is immediately marked stale, so the UI and production gate agree.
    """
    try:
        active_cat = request.headers.get('X-Active-Category', '')
        active_tmpl = request.headers.get('X-Active-Template', '')
        if not active_cat or not active_tmpl:
            return jsonify({"success": False, "error": "Kategori/sablon eksik"}), 400

        stem = Path(active_tmpl).stem
        backup_root = os.path.abspath(YEDEK_IMG_DIR)
        src_path = None
        for ext in ('.jpg', '.jpeg', '.webp', '.png', '.avif'):
            candidate = _safe_under_root(
                backup_root,
                active_cat,
                stem + ext,
                label="orijinal yedek",
            )
            if os.path.isfile(candidate):
                src_path = candidate
                break
        if src_path is None:
            return jsonify({
                "success": False,
                "error": "Orijinal yedek bulunamadi.",
            }), 404

        # Working template pool is normalized to PNG; never overwrite another
        # template or write outside the pool.
        dest_path = _safe_template_path(active_cat, stem + ".png")
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)

        img_raw = cv2.imdecode(
            np.fromfile(src_path, dtype=np.uint8),
            cv2.IMREAD_COLOR,
        )
        if img_raw is None:
            return jsonify({
                "success": False,
                "error": "Orijinal yedek görsel okunamadı.",
            }), 422

        ok, encoded = cv2.imencode(".png", img_raw)
        if not ok:
            return jsonify({
                "success": False,
                "error": "Orijinal görsel PNG olarak kodlanamadı.",
            }), 500

        tmp_path = dest_path + f".restore_{uuid.uuid4().hex}.tmp"
        try:
            with open(tmp_path, "wb") as handle:
                handle.write(encoded.tobytes())
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_path, dest_path)
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

        current_hash = _sha256_file(dest_path)
        _invalidate_stale_profiles_for_source(
            active_cat,
            active_tmpl,
            stem + ".png",
            current_hash,
        )
        return jsonify({
            "success": True,
            "source_sha256": current_hash,
            "profiles_revalidation_required": True,
        })
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception as exc:
        logger.exception("Orijinal sablon geri yukleme hatasi")
        return jsonify({"success": False, "error": str(exc)}), 500


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

def _find_template_backup_asset(category: str, template_name: str):
    """Find the original-backup asset that corresponds to one template."""
    backup_root = os.path.abspath(
        os.path.join(BASE_DIR, "2_SABLON_HAVUZU_ORIJINAL_YEDEK")
    )
    category_dir = _safe_under_root(
        backup_root,
        category,
        label="orijinal yedek kategorisi",
    )
    stem = Path(template_name).stem
    for ext in (".png", ".jpg", ".jpeg", ".webp", ".avif"):
        candidate = _safe_under_root(
            category_dir,
            stem + ext,
            label="orijinal yedek",
        )
        if os.path.isfile(candidate):
            return candidate
    return None


def _retire_template_safely(active_cat: str, active_tmpl: str) -> dict:
    """Retire one template with reversible files + DB state."""
    active_cat = str(active_cat or "").strip()
    active_tmpl = str(active_tmpl or "").strip()
    if not active_cat or not active_tmpl:
        raise ValueError("Kategori/sablon eksik")

    meta_path = None
    moved_pairs = []
    deactivated_rowids = []

    _ayarlar = get_all_ayarlar()
    category_data = _ayarlar.get("kategoriler", {}).get(active_cat, {})
    templates = category_data.get("sablonlar", {})
    if active_tmpl not in templates:
        raise FileNotFoundError("Sablon bulunamadi")

    src_img = _safe_template_path(active_cat, active_tmpl)
    removed_conf = templates[active_tmpl]

    template_number = extract_number(active_cat, active_tmpl)
    if template_number is not None:
        reserve_number(
            Path(BASE_DIR),
            active_cat,
            template_number,
            canonical_name=active_tmpl,
            source="review_center_delete",
        )
    if not os.path.isfile(src_img):
        raise RuntimeError(
            "Şablon kaynak görseli bulunamadı; güvenli silme yapılamaz."
        )

    trash_dir = os.path.join(BASE_DIR, "SILINEN_SABLONLAR_COP_KUTUSU")
    os.makedirs(trash_dir, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    token = uuid.uuid4().hex[:8]
    safe_stem = Path(active_tmpl).stem

    trash_image_name = (
        f"{active_cat}__{safe_stem}__{stamp}_{token}"
        f"{Path(active_tmpl).suffix}"
    )
    trash_img = os.path.join(trash_dir, trash_image_name)

    backup_src = _find_template_backup_asset(active_cat, active_tmpl)
    backup_trash_name = None
    backup_trash_path = None
    if backup_src:
        backup_trash_name = (
            f"{active_cat}__{safe_stem}__ORIGINAL__{stamp}_{token}"
            f"{Path(backup_src).suffix}"
        )
        backup_trash_path = os.path.join(trash_dir, backup_trash_name)

    db_path = os.path.join(BASE_DIR, "SABLON_V2_MIMARI", "ayarlar.db")
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """SELECT rowid AS profile_rowid, source_asset_sha256
               FROM template_profiles
               WHERE category=? AND is_active=1
                 AND (
                     source_relative_path=?
                     OR template_uid=?
                 )""",
            (
                active_cat,
                f"{active_cat}/{active_tmpl}",
                f"{active_cat}_{active_tmpl}",
            ),
        ).fetchall()
        deactivated_rowids = [
            int(row["profile_rowid"])
            for row in rows
        ]

        meta_name = (
            f"{active_cat}__{safe_stem}__{stamp}_{token}_meta.json"
        )
        meta_path = os.path.join(trash_dir, meta_name)
        meta_data = {
            "kategori": active_cat,
            "sablon": active_tmpl,
            "conf": removed_conf,
            "trash_image_name": trash_image_name,
            "backup_trash_name": backup_trash_name,
            "deactivated_profile_rowids": deactivated_rowids,
            "source_sha256": _sha256_file(src_img),
            "deleted_at": stamp,
        }

        tmp_meta = meta_path + ".tmp"
        with open(tmp_meta, "w", encoding="utf-8") as handle:
            json.dump(meta_data, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_meta, meta_path)

        shutil.move(src_img, trash_img)
        moved_pairs.append((trash_img, src_img))

        if backup_src and backup_trash_path:
            shutil.move(backup_src, backup_trash_path)
            moved_pairs.append((backup_trash_path, backup_src))

        if deactivated_rowids:
            placeholders = ",".join("?" for _ in deactivated_rowids)
            conn.execute(
                f"""UPDATE template_profiles
                    SET is_active=0, updated_at=CURRENT_TIMESTAMP
                    WHERE rowid IN ({placeholders})""",
                deactivated_rowids,
            )

        conn.execute(
            "DELETE FROM templates WHERE category_id=? AND filename=?",
            (active_cat, active_tmpl),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        for moved_dst, moved_src in reversed(moved_pairs):
            if os.path.exists(moved_dst) and not os.path.exists(moved_src):
                try:
                    os.makedirs(os.path.dirname(moved_src), exist_ok=True)
                    shutil.move(moved_dst, moved_src)
                except Exception:
                    logger.exception(
                        "Sablon silme rollback dosya geri tasima basarisiz"
                    )
        if meta_path and os.path.exists(meta_path):
            try:
                os.remove(meta_path)
            except OSError:
                pass
        raise
    finally:
        conn.close()

    return {
        "category": active_cat,
        "template": active_tmpl,
        "trash_record": os.path.basename(meta_path),
        "deactivated_profiles": len(deactivated_rowids),
        "backup_archived": bool(backup_src),
    }


@app.route('/api/sablon_sil', methods=['POST'])
def api_sablon_sil():
    """Safely retire one template."""
    try:
        result = _retire_template_safely(
            request.headers.get("X-Active-Category", ""),
            request.headers.get("X-Active-Template", ""),
        )
        return jsonify({"success": True, **result})
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except FileNotFoundError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404
    except RuntimeError as exc:
        return jsonify({
            "success": False,
            "error": str(exc),
            "code": "SOURCE_IMAGE_MISSING",
        }), 409
    except Exception as exc:
        logger.exception("Sablon cop kutusuna tasinamadi")
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route('/api/sablon_sil_toplu', methods=['POST'])
def api_sablon_sil_toplu():
    """Retire many selected templates in one browser request."""
    payload = request.get_json(silent=True) or {}
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        return jsonify({
            "success": False,
            "error": "Toplu silme için en az bir şablon seçilmeli.",
        }), 400
    if len(items) > 500:
        return jsonify({
            "success": False,
            "error": "Tek işlemde en fazla 500 şablon seçilebilir.",
        }), 400

    deleted = []
    failed = []
    seen = set()

    for item in items:
        if not isinstance(item, dict):
            failed.append({
                "category": "",
                "template": "",
                "error": "Geçersiz seçim kaydı.",
            })
            continue

        category = str(item.get("category") or "").strip()
        template = str(item.get("template") or "").strip()
        key = (category, template)
        if not category or not template or key in seen:
            if key not in seen:
                failed.append({
                    "category": category,
                    "template": template,
                    "error": "Kategori veya şablon adı eksik.",
                })
            continue
        seen.add(key)

        try:
            deleted.append(
                _retire_template_safely(category, template)
            )
        except Exception as exc:
            failed.append({
                "category": category,
                "template": template,
                "error": str(exc),
            })

    return jsonify({
        "success": len(failed) == 0,
        "deleted_count": len(deleted),
        "failed_count": len(failed),
        "deleted": deleted,
        "failed": failed,
    }), (200 if not failed else 207)


@app.route('/api/sablon_sil_geri_al', methods=['POST'])
def api_sablon_sil_geri_al():
    """Undo the most recent safe template retirement."""
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
        backup_trash_name = meta.get('backup_trash_name')
        deactivated_rowids = [
            int(value)
            for value in (
                meta.get('deactivated_profile_rowids') or []
            )
        ]
        original_sha = str(meta.get("source_sha256") or "")

        if not cat or not tmpl:
            return jsonify({
                "success": False,
                "error": "Çöp meta verisi bozuk",
            }), 422

        source_in_trash = _safe_under_root(
            trash_dir,
            trash_image_name,
            label="cop kutusu",
        )
        restore_path = _safe_template_path(cat, tmpl)
        restore_dir = os.path.dirname(restore_path)
        os.makedirs(restore_dir, exist_ok=True)

        if os.path.exists(restore_path):
            return jsonify({
                "success": False,
                "error": (
                    "Aynı isimde aktif şablon zaten var; üzerine yazılmadı."
                ),
            }), 409
        if not os.path.isfile(source_in_trash):
            return jsonify({
                "success": False,
                "error": (
                    "Çöp kutusu görseli bulunamadı; DB kaydı görselsiz "
                    "geri yüklenmedi."
                ),
                "code": "TRASH_IMAGE_MISSING",
            }), 409

        restored_backup = None
        backup_source_in_trash = None
        if backup_trash_name:
            backup_source_in_trash = _safe_under_root(
                trash_dir,
                backup_trash_name,
                label="cop kutusu orijinal yedek",
            )
            backup_root = os.path.abspath(
                os.path.join(
                    BASE_DIR,
                    "2_SABLON_HAVUZU_ORIJINAL_YEDEK",
                )
            )
            backup_cat_dir = _safe_under_root(
                backup_root,
                cat,
                label="orijinal yedek kategorisi",
            )
            os.makedirs(backup_cat_dir, exist_ok=True)
            restored_backup = _safe_under_root(
                backup_cat_dir,
                Path(backup_source_in_trash).name.split(
                    "__ORIGINAL__", 1
                )[0].split("__", 1)[-1]
                + Path(backup_source_in_trash).suffix,
                label="orijinal yedek",
            )
            # Prefer the original template stem for predictable naming.
            restored_backup = os.path.join(
                backup_cat_dir,
                Path(tmpl).stem + Path(backup_source_in_trash).suffix,
            )
            if os.path.exists(restored_backup):
                return jsonify({
                    "success": False,
                    "error": (
                        "Orijinal yedek hedefinde aynı isimde dosya var; "
                        "geri alma üzerine yazma yapmadı."
                    ),
                }), 409

        moved_back = []
        db_path = os.path.join(BASE_DIR, "SABLON_V2_MIMARI", "ayarlar.db")
        conn = sqlite3.connect(db_path)
        try:
            shutil.move(source_in_trash, restore_path)
            moved_back.append((restore_path, source_in_trash))

            if (
                backup_source_in_trash
                and restored_backup
                and os.path.isfile(backup_source_in_trash)
            ):
                shutil.move(
                    backup_source_in_trash,
                    restored_backup,
                )
                moved_back.append(
                    (restored_backup, backup_source_in_trash)
                )

            restored_hash = _sha256_file(restore_path)
            conn.execute(
                """INSERT INTO templates (category_id, filename, data)
                   VALUES (?, ?, ?)
                   ON CONFLICT(category_id, filename)
                   DO UPDATE SET data=excluded.data""",
                (
                    cat,
                    tmpl,
                    json.dumps(conf, ensure_ascii=False),
                ),
            )

            # Reactivate only the exact old approval lineage when bytes still
            # match the retired source. Modified trash content must be reviewed.
            reactivated = 0
            if (
                deactivated_rowids
                and original_sha
                and restored_hash == original_sha
            ):
                placeholders = ",".join(
                    "?" for _ in deactivated_rowids
                )
                cur = conn.execute(
                    f"""UPDATE template_profiles
                        SET is_active=1, updated_at=CURRENT_TIMESTAMP
                        WHERE rowid IN ({placeholders})
                          AND source_asset_sha256=?""",
                    [*deactivated_rowids, restored_hash],
                )
                reactivated = int(cur.rowcount or 0)
            conn.commit()
        except Exception:
            conn.rollback()
            for moved_src, moved_dst in reversed(moved_back):
                if os.path.exists(moved_src) and not os.path.exists(moved_dst):
                    try:
                        shutil.move(moved_src, moved_dst)
                    except Exception:
                        logger.exception(
                            "Sablon geri alma rollback basarisiz"
                        )
            raise
        finally:
            conn.close()

        os.remove(meta_path)
        return jsonify({
            "success": True,
            "restored_tmpl": tmpl,
            "reactivated_profiles": reactivated,
            "backup_restored": bool(restored_backup),
        })
    except Exception as e:
        logger.exception("Sablon geri alma hatasi")
        return jsonify({"success": False, "error": str(e)}), 500


def _path_within_root(root: str, candidate: str) -> bool:
    """Return True only when candidate resolves inside root (prefix-safe)."""
    root_abs = os.path.abspath(str(root))
    candidate_abs = os.path.abspath(str(candidate))
    try:
        return os.path.commonpath([root_abs, candidate_abs]) == root_abs
    except ValueError:
        return False


def _find_image_asset(root: str, category: str, template_name: str):
    """Resolve one image by exact name or same stem without leaving root."""
    import urllib.parse

    category = urllib.parse.unquote(str(category or ""))
    template_name = urllib.parse.unquote(str(template_name or ""))
    safe_root = os.path.abspath(root)
    stem = Path(template_name).stem

    candidates = [template_name]
    candidates.extend(
        stem + ext
        for ext in (".png", ".jpg", ".jpeg", ".webp", ".avif")
        if stem + ext != template_name
    )
    for name in candidates:
        candidate = os.path.abspath(
            os.path.join(safe_root, category, name)
        )
        if (
            _path_within_root(safe_root, candidate)
            and os.path.isfile(candidate)
        ):
            return candidate
    return None


def _send_image_no_cache(path: str):
    import hashlib

    file_stat = os.stat(path)
    etag = hashlib.md5(
        f"{path}:{file_stat.st_mtime}:{file_stat.st_size}".encode()
    ).hexdigest()
    client_etag = request.headers.get("If-None-Match", "")
    if client_etag == f'"{etag}"':
        return "", 304

    response = send_file(path)
    response.set_etag(etag)
    response.headers["Cache-Control"] = "no-cache"
    return response


@app.route('/working-image/<cat>/<tmpl>')
def serve_working_image(cat, tmpl):
    """Serve only the active working copy; never silently substitute backup."""
    working_root = os.path.abspath(
        os.path.join(BASE_DIR, "2_SABLON_HAVUZU")
    )
    img_path = _find_image_asset(working_root, cat, tmpl)
    if img_path is None:
        return "Calisma gorseli bulunamadi", 404
    return _send_image_no_cache(img_path)


@app.route('/original-image/<cat>/<tmpl>')
def serve_original_image(cat, tmpl):
    """Serve only the immutable/raw original backup for visual inspection."""
    backup_root = os.path.abspath(YEDEK_IMG_DIR)
    img_path = _find_image_asset(backup_root, cat, tmpl)
    if img_path is None:
        return "Ham orijinal yedek bulunamadi", 404
    return _send_image_no_cache(img_path)


@app.route('/image/<cat>/<tmpl>')
def serve_image(cat, tmpl):
    import urllib.parse
    import hashlib
    
    cat = urllib.parse.unquote(cat)
    tmpl = urllib.parse.unquote(tmpl)
    
    safe_yedek_base = os.path.abspath(YEDEK_IMG_DIR)
    img_path = os.path.abspath(os.path.join(safe_yedek_base, cat, tmpl))
    
    if not _path_within_root(safe_yedek_base, img_path):
        return "Erisim engellendi", 403
        
    if not os.path.exists(img_path):
        stem = Path(tmpl).stem
        yedek_path = None
        for alt_ext in [".webp", ".jpg", ".jpeg", ".png", ".avif"]:
            cand = os.path.abspath(os.path.join(safe_yedek_base, cat, stem + alt_ext))
            if _path_within_root(safe_yedek_base, cand) and os.path.exists(cand):
                yedek_path = cand
                break
                
        if yedek_path:
            img_path = yedek_path
        else:
            safe_havuz_base = os.path.abspath(os.path.join(BASE_DIR, "2_SABLON_HAVUZU"))
            cand_png = os.path.abspath(os.path.join(safe_havuz_base, cat, stem + ".png"))
            if _path_within_root(safe_havuz_base, cand_png) and os.path.exists(cand_png):
                img_path = cand_png
            else:
                fallback_path = os.path.abspath(os.path.join(safe_havuz_base, cat, tmpl))
                if _path_within_root(safe_havuz_base, fallback_path):
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

def _safe_under_root(root: str, *parts, label: str = "dosya") -> str:
    root_abs = os.path.abspath(str(root))
    candidate = os.path.abspath(
        os.path.join(root_abs, *(str(part) for part in parts))
    )
    try:
        if os.path.commonpath([root_abs, candidate]) != root_abs:
            raise ValueError(f"Gecersiz {label} yolu")
    except ValueError as exc:
        raise ValueError(f"Gecersiz {label} yolu") from exc
    return candidate


def _safe_template_path(category: str, template_name: str) -> str:
    """Resolve a template source path without allowing traversal outside the pool."""
    pool_root = os.path.abspath(os.path.join(BASE_DIR, "2_SABLON_HAVUZU"))
    return _safe_under_root(
        pool_root,
        category,
        template_name,
        label="sablon",
    )


def _invalidate_stale_profiles_for_source(
    category: str,
    requested_template: str,
    actual_filename: str,
    current_hash: str,
) -> int:
    """Mark approvals stale immediately after source bytes are replaced."""
    db_path = os.path.join(BASE_DIR, "SABLON_V2_MIMARI", "ayarlar.db")
    uid = f"{category}_{requested_template}"
    relative_candidates = {
        f"{category}/{requested_template}".replace("\\", "/"),
        f"{category}/{actual_filename}".replace("\\", "/"),
    }
    conn = sqlite3.connect(db_path, timeout=30)
    try:
        placeholders = ",".join("?" for _ in relative_candidates)
        params = [
            uid,
            *sorted(relative_candidates),
            current_hash,
        ]
        cur = conn.execute(
            f"""UPDATE template_profiles
                SET review_status='STALE_SOURCE_CHANGED',
                    manually_verified=0,
                    updated_at=CURRENT_TIMESTAMP
                WHERE is_active=1
                  AND (template_uid=? OR source_relative_path IN ({placeholders}))
                  AND (source_asset_sha256 IS NULL OR source_asset_sha256<>?)""",
            params,
        )
        conn.commit()
        return int(cur.rowcount or 0)
    finally:
        conn.close()


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


def _bind_on_plan_source_identity(
    category: str,
    template_name: str,
    data: dict,
) -> dict:
    """Return a copy whose manual occlusion plan is bound to source bytes."""
    if not isinstance(data, dict):
        raise ValueError("Sablon verisi nesne olmali")

    result = dict(data)
    plan = result.get("on_plan")
    if not plan:
        result.pop("on_plan_source_sha256", None)
        return result

    source_path = _safe_template_path(category, template_name)
    if not os.path.isfile(source_path):
        # Never invent trust metadata if the exact source cannot be resolved.
        result.pop("on_plan_source_sha256", None)
        if isinstance(plan, dict):
            clean_plan = dict(plan)
            clean_plan.pop("source_asset_sha256", None)
            result["on_plan"] = clean_plan
        return result

    source_hash = _sha256_file(source_path)
    result["on_plan_source_sha256"] = source_hash
    if isinstance(plan, dict):
        bound_plan = dict(plan)
        bound_plan["source_asset_sha256"] = source_hash
        result["on_plan"] = bound_plan
    return result


def _load_matching_manual_prior(db_path, uid, img_path):
    """Load trusted manual geometry only when it belongs to the current source bytes."""
    current_hash = _sha256_file(img_path)

    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            """SELECT surface_quad, outer_quad, source_asset_sha256, orientation
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
        physical_orientation = str(row[3] or "").upper()
        if physical_orientation in ("H", "V"):
            prior["physical_orientation"] = physical_orientation
        return prior
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


@app.route('/api/templates/foreground_detect', methods=['POST'])
def api_templates_foreground_detect():
    """Suggest automatic foreground object boxes using Grounding-DINO + SAM.

    The endpoint is review assistance only and never auto-approves geometry.
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
            SOURCE_ROOT,
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
                """SELECT rowid AS profile_rowid, surface_quad, source_asset_sha256, source_relative_path,
                          orientation, nominal_aspect
                   FROM template_profiles
                   WHERE template_uid=? AND is_active=1""",
                (uid,),
            ).fetchone()
            if not row:
                return jsonify({"success": False, "error": "Aktif profil bulunamadi"}), 404

            (
                profile_id,
                surface_quad_json,
                source_hash,
                relative_path,
                stored_orientation,
                stored_nominal_aspect,
            ) = row
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

            category_name = str(relative_path).replace("\\", "/").split("/", 1)[0]
            rule = CategoryRuleEngine.get_rule_by_folder(category_name)
            physical_rule_orientation = str(
                rule.get("physical_orientation") or "ANY"
            ).upper()
            if physical_rule_orientation in ("H", "V"):
                physical_orientation = physical_rule_orientation
            else:
                return jsonify({
                    "success": False,
                    "error": (
                        "Bu kategori icin fiziksel H/V yonu editor uzerinden "
                        "insan tarafindan secilip koselerle birlikte onaylanmalidir."
                    ),
                    "code": "PHYSICAL_ORIENTATION_REVIEW_REQUIRED",
                }), 422

            nominal_value = CategoryRuleEngine.get_nominal_aspect(
                category_name,
                physical_orientation,
            )
            nominal_aspect = (
                f"{nominal_value:.8f}".rstrip("0").rstrip(".")
                if nominal_value is not None
                else str(stored_nominal_aspect or "UNKNOWN")
            )

            conn.execute(
                """UPDATE template_profiles
                   SET review_status='APPROVED', manually_verified=1,
                       orientation=?, nominal_aspect=?,
                       updated_at=CURRENT_TIMESTAMP
                   WHERE rowid=?""",
                (physical_orientation, nominal_aspect, profile_id),
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
        req_physical_orientation = str(
            req.get("physical_orientation") or ""
        ).strip().upper()
        req_on_plan = req.get("on_plan")
        if req_on_plan is not None and not isinstance(req_on_plan, dict):
            return jsonify({
                "success": False,
                "error": "Otomatik nesne koruma verisi nesne olmali.",
            }), 422
        if isinstance(req_on_plan, dict):
            boxes = req_on_plan.get("object_boxes")
            req_on_plan = {
                "object_boxes": (
                    [box[:4] for box in boxes if isinstance(box, list) and len(box) == 4]
                    if isinstance(boxes, list)
                    else []
                ),
                "feather": float(req_on_plan.get("feather", 1.2) or 1.2),
                "grabcut_iterations": int(
                    req_on_plan.get("grabcut_iterations", 5) or 5
                ),
            }
            if not req_on_plan["object_boxes"]:
                req_on_plan = None
        occlusion_reviewed = bool(req.get("occlusion_reviewed", False))
        if not uid or corners is None:
            return jsonify({"success": False, "error": "Eksik parametre"}), 400

        db_path = os.path.join(BASE_DIR, "SABLON_V2_MIMARI", "ayarlar.db")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                """SELECT rowid AS profile_rowid, source_asset_sha256, source_relative_path,
                          has_occlusion
                   FROM template_profiles
                   WHERE template_uid=? AND is_active=1""",
                (uid,),
            ).fetchone()

            if row:
                profile_id = int(row["profile_rowid"])
                source_hash = row["source_asset_sha256"]
                relative_path = row["source_relative_path"]
                existing_has_occlusion = bool(row["has_occlusion"])
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
                    # The user may have intentionally restored/replaced the
                    # working source from the protected original backup. If
                    # they are now manually reviewing four corners, the
                    # submitted geometry must be allowed to create a fresh
                    # source-hash-bound manual profile instead of forcing a
                    # separate analyzer click first.
                    if not req_category or not req_template:
                        return jsonify({
                            "success": False,
                            "error": (
                                "Kaynak gorsel degismis. Yeni kaynaga manuel "
                                "onay icin category/template bilgisi gerekli."
                            ),
                            "code": "STALE_SOURCE_CHANGED",
                        }), 409

                    expected_uid = f"{req_category}_{req_template}"
                    if uid != expected_uid:
                        return jsonify({
                            "success": False,
                            "error": (
                                "Template kimligi yeni kaynak kategori/dosya "
                                "bilgisi ile uyusmuyor."
                            ),
                        }), 409

                    replacement_path = _safe_template_path(
                        req_category,
                        req_template,
                    )
                    if not os.path.isfile(replacement_path):
                        return jsonify({
                            "success": False,
                            "error": "Yeni kaynak gorsel bulunamadi.",
                        }), 404

                    replacement_hash = _sha256_file(replacement_path)

                    # Retire every active profile for this UID that belongs to
                    # older bytes. Never carry stale occlusion/mask evidence
                    # into a newly restored source.
                    conn.execute(
                        """UPDATE template_profiles
                           SET is_active=0,
                               review_status='STALE_SOURCE_CHANGED',
                               manually_verified=0,
                               updated_at=CURRENT_TIMESTAMP
                           WHERE template_uid=? AND is_active=1
                             AND (
                                 source_asset_sha256 IS NULL
                                 OR source_asset_sha256<>?
                             )""",
                        (uid, replacement_hash),
                    )

                    matching_row = conn.execute(
                        """SELECT rowid AS profile_rowid, has_occlusion
                           FROM template_profiles
                           WHERE template_uid=? AND is_active=1
                             AND source_asset_sha256=?
                           ORDER BY updated_at DESC, rowid DESC
                           LIMIT 1""",
                        (uid, replacement_hash),
                    ).fetchone()

                    source_path = replacement_path
                    source_hash = replacement_hash
                    relative_path = f"{req_category}/{req_template}"
                    category_name = req_category
                    template_name = req_template
                    existing_has_occlusion = False
                    profile_id = (
                        int(matching_row["profile_rowid"])
                        if matching_row
                        else None
                    )
                    if matching_row:
                        existing_has_occlusion = bool(
                            matching_row["has_occlusion"]
                        )
                else:
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
                existing_has_occlusion = False

            effective_has_occlusion = resolve_reviewed_occlusion(
                existing_has_occlusion,
                req_on_plan,
                occlusion_reviewed=occlusion_reviewed,
            )

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
            projected_orientation = (
                "H" if aspect > 1.05
                else ("V" if aspect < 0.95 else "SQUARE")
            )

            rule = CategoryRuleEngine.get_rule_by_folder(category_name)
            physical_rule_orientation = rule.get("physical_orientation", "ANY")
            if physical_rule_orientation in ("H", "V"):
                physical_orientation = physical_rule_orientation
            else:
                if req_physical_orientation not in ("H", "V"):
                    return jsonify({
                        "success": False,
                        "error": (
                            "Bu kategori birden fazla fiziksel yon destekliyor. "
                            "Onaydan once Yatay (H) veya Dikey (V) secin."
                        ),
                        "code": "PHYSICAL_ORIENTATION_REQUIRED",
                    }), 422
                physical_orientation = req_physical_orientation

            nominal_value = CategoryRuleEngine.get_nominal_aspect(
                category_name,
                physical_orientation,
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
                "physical_orientation_verified": 1.0,
                "physical_orientation_source": (
                    "category_contract"
                    if physical_rule_orientation in ("H", "V")
                    else "human_review"
                ),
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
                           ?, NULL, NULL, 'default', ?, ?, ?, ?, 1.0, ?,
                           'APPROVED', 1, 1
                       )""",
                    (
                        uid,
                        category_name,
                        relative_path,
                        source_hash,
                        rule.get("product_class", "Bilinmeyen"),
                        physical_orientation,
                        nominal_aspect,
                        rule.get("print_policy", "full_bleed"),
                        json.dumps(canonical.tolist()),
                        int(bool(rule.get("has_frame"))),
                        int(bool(rule.get("has_mat"))),
                        int(bool(rule.get("has_reflection"))),
                        int(effective_has_occlusion),
                        json.dumps(manual_components),
                    ),
                )
                profile_id = int(cur.lastrowid)
            else:
                conn.execute(
                    """UPDATE template_profiles
                       SET surface_quad=?, orientation=?, nominal_aspect=?,
                           has_occlusion=?,
                           confidence_total=1.0, component_confidences=?,
                           review_status='APPROVED', manually_verified=1,
                           updated_at=CURRENT_TIMESTAMP
                       WHERE rowid=?""",
                    (
                        json.dumps(canonical.tolist()),
                        physical_orientation,
                        nominal_aspect,
                        int(effective_has_occlusion),
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
                legacy_data["physical_orientation"] = physical_orientation
                if isinstance(req_on_plan, dict):
                    # Bind reviewed occlusion/mask instructions to the exact
                    # template bytes they were edited against. Production can
                    # then reject stale brush/object coordinates after a source
                    # image replacement instead of silently applying them to a
                    # different image with the same filename.
                    plan_to_store = dict(req_on_plan)
                    if plan_to_store:
                        plan_to_store["source_asset_sha256"] = source_hash
                    legacy_data["on_plan"] = plan_to_store
                    legacy_data["on_plan_source_sha256"] = source_hash
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
            "orientation": physical_orientation,
            "projected_orientation": projected_orientation,
            "nominal_aspect": nominal_aspect,
        })
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        logger.exception("Manuel geometri onayi hatasi")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/saglik_durumu')
def api_saglik_durumu():
    """Return a live, read-only workspace integrity snapshot.

    The old endpoint only replayed a possibly stale JSON log. The UI now asks
    the same current runtime DB/filesystem that production will use.
    """
    try:
        report = run_factory_doctor(
            BASE_DIR,
            source_root=SOURCE_ROOT,
            deep=False,
        )
        return jsonify({
            "ready": bool(report.get("ready")),
            "sorun_sayisi": int(report.get("error_count", 0)),
            "sorunlar": [
                f"[{item.get('code')}] {item.get('message')}"
                for item in report.get("errors", [])
            ],
            "uyari_sayisi": int(report.get("warning_count", 0)),
            "uyarilar": [
                f"[{item.get('code')}] {item.get('message')}"
                for item in report.get("warnings", [])
            ],
            # Kept for backward-compatible frontend rendering.
            "cozulen_sayisi": 0,
            "cozulenler": [],
            "doctor": report,
        })
    except Exception as exc:
        logger.exception("Canli sistem saglik taramasi basarisiz")
        return jsonify({
            "ready": False,
            "sorun_sayisi": 1,
            "sorunlar": [f"[DOCTOR_FAILED] {exc}"],
            "uyari_sayisi": 0,
            "uyarilar": [],
            "cozulen_sayisi": 0,
            "cozulenler": [],
        }), 500

@app.route('/<path:filename>')
def serve_temp_files(filename):
    # Legacy compatibility route for temporary visual assets only. Never expose
    # DB/config/source files through the broad catch-all URL surface.
    allowed_exts = {".png", ".jpg", ".jpeg", ".webp", ".avif", ".gif"}
    if Path(filename).suffix.lower() not in allowed_exts:
        return "Yasak", 403

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
    try:
        identity_history = backfill_registry(Path(BASE_DIR))
        print(
            "Sablon numara gecmisi korumasi aktif: "
            + ", ".join(
                f"{category}={count}"
                for category, count in identity_history.items()
            )
        )
    except Exception as exc:
        print(f"UYARI: Sablon numara gecmisi backfill tamamlanamadi: {exc}")

    print("SABLON_V2_MIMARI (Flask MVC) Baslatiliyor... http://127.0.0.1:8080")
    auto_browser_disabled = str(
        os.environ.get("MOCKUP_NO_AUTO_BROWSER", "")
    ).strip().lower() in {"1", "true", "yes", "on"}
    if not auto_browser_disabled:
        threading.Timer(
            1.25,
            lambda: webbrowser.open("http://127.0.0.1:8080/"),
        ).start()
    debug_enabled = str(os.environ.get("MOCKUP_FLASK_DEBUG", "")).strip().lower() in {"1", "true", "yes", "on"}
    app.run(host='127.0.0.1', port=8080, debug=debug_enabled, use_reloader=False)
