import os
import sys
import json
import sqlite3
import math
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
from concurrent.futures import ThreadPoolExecutor, as_completed

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

from core.db import init_db, inspect_startup_schema, get_all_ayarlar, save_settings_node, save_category, save_template, delete_template, save_templates_bulk
from core.template_intelligence import TemplateAnalyzer, save_template_profile, TemplateSelector, GeometryValidator, CategoryRuleEngine
from core.factory_doctor import run_factory_doctor
from core.doctor_guidance import doctor_guidance
from core.template_identity import (
    backfill_registry,
    canonical_identity,
    extract_number,
    reserve_number,
    same_stem_files,
)
from core.operation_lock import (
    TemplateBusyError,
    acquire_template_lock,
    release_template_lock,
    template_operation_lock,
)
from core.analysis_cache import (
    load_analysis_cache,
    save_analysis_cache,
    cache_stats,
)
from core.job_engine import (
    PersistentJobEngine,
    create_job,
    get_job,
    list_jobs,
    request_job_stop,
)
from core.workspace_consistency import (
    workspace_consistency_report,
    save_workspace_report,
    load_latest_workspace_report,
    workspace_report_history,
)
from core.lifecycle_reconciliation import (
    LifecycleSafetyError,
    lifecycle_center_report,
    archive_duplicate_variants,
    archive_working_orphan,
    replace_original_and_working,
    rollback_replace_original,
    undo_lifecycle_operation,
)
import hashlib
import uuid
from functools import wraps

app = Flask(__name__)
from core.loopback_security_v47 import check as _loopback_check, token as _csrf_token

@app.before_request
def _enforce_loopback_csrf_v47():
    reason = _loopback_check(request, testing=app.config.get('TESTING') is True)
    if reason:
        return jsonify({'success':False,'code':reason,'error':'Yerel inceleme güvenlik denetimi'}),403

@app.after_request
def _private_editor_headers(response):
    response.headers['X-Frame-Options']='DENY'
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='same-origin'
    response.headers['Cache-Control']='private, no-store'
    response.headers['Content-Security-Policy']="frame-ancestors 'none'"
    return response

@app.route('/api/session/csrf')
def csrf_session_token():
    return jsonify({'csrf':_csrf_token()})

@app.route('/api/center_identity')
def center_identity():
    import secrets
    token = os.environ.get('MOCKUP_CENTER_TOKEN', '')
    if not token or not secrets.compare_digest(request.headers.get('X-Center-Token', ''), token):
        return jsonify({'error': 'Not authorized'}), 403
    # On Windows venv python.exe is a launcher/redirector. Popen.pid can
    # identify that launcher while Flask runs in its direct Python child.
    # A launcher-to-child identity still requires the secret token + both roots.
    return jsonify({'pid': os.getpid(), 'parent_pid': os.getppid(),
                    'token': token, 'runtime_root': BASE_DIR,
                    'code_root': SOURCE_ROOT})



def _template_guard_values(source):
    if source == "headers":
        return (
            str(request.headers.get("X-Active-Category", "")).strip(),
            str(request.headers.get("X-Active-Template", "")).strip(),
        )
    payload = request.get_json(silent=True) or {}
    if source == "json_tr":
        return (
            str(payload.get("kategori") or "").strip(),
            str(payload.get("sablon") or "").strip(),
        )
    return (
        str(payload.get("category") or "").strip(),
        str(payload.get("template") or "").strip(),
    )


def template_guard(operation, *, source="headers", wait_seconds=0.15):
    """Backend lock decorator for one-template request endpoints."""
    def decorator(func):
        @wraps(func)
        def wrapped(*args, **kwargs):
            category, template = _template_guard_values(source)
            if not category or not template:
                return func(*args, **kwargs)
            try:
                with template_operation_lock(
                    category,
                    template,
                    operation,
                    wait_seconds=wait_seconds,
                ):
                    return func(*args, **kwargs)
            except TemplateBusyError as exc:
                return jsonify({
                    "success": False,
                    "error": str(exc),
                    "code": "TEMPLATE_BUSY",
                }), 409
        return wrapped
    return decorator


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


# No automatic migration or WAL alteration during module import/startup.
# Production schema migrations require a verified off-runtime SQLite backup
# and explicit human approval. A missing/legacy DB fails closed at API gate.
DB_STARTUP_AUDIT = inspect_startup_schema()


@app.before_request
def _require_migrated_database():
    # Flask's explicit TESTING mode is used by the legacy synthetic tests
    # whose SQLite connection is patched at runtime. Production never uses
    # TESTING=True; don't reinterpret synthetic paths as live migrations.
    if app.config.get("TESTING") is True:
        # Legacy unit tests patch their disposable DB_PATH after importing app.
        # Bootstrap ONLY their test DB when it is not in a OneDrive workspace.
        from core import db as _db_for_testing
        test_db = Path(_db_for_testing.DB_PATH).resolve()
        if not any("onedrive" in part.casefold() for part in test_db.parts):
            if not inspect_startup_schema(test_db)["ready"]:
                _db_for_testing.init_db()
            return None
    if request.path.startswith("/api/") and not DB_STARTUP_AUDIT["ready"]:
        return jsonify({
            "success": False, "code": "DB_STARTUP_BLOCKED",
            "error": DB_STARTUP_AUDIT["reason"],
            "migration_required": DB_STARTUP_AUDIT.get("migration_required", False),
        }), 503


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/tools')
def tools_center():
    return render_template('tools.html')


_ALLOWED_USER_TOOLS = {
    "rename",
    "stage",
    "convert",
    "png_recursive",
    "watermark",
    "4k",
    "links",
    "seo_titles",
    "seo_descriptions",
    "portrait_3x4",
    "review_folder",
    "golden_audit",
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
@template_guard('save', source='json_tr')
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

@app.route('/api/anlik_beyazlat', methods=['POST'])
@template_guard("preview-whiten", source="headers")
def api_izole_anlik_beyazlat():
    """Real 8080 preview; immutable backup is read-only and working unchanged."""
    from core.template_identity import CATEGORY_PREFIXES
    from core.safe_working_revision import save_preview_only, WorkingRevisionBlocked
    try:
        category = str(request.headers.get("X-Active-Category", "")).strip()
        template = str(request.headers.get("X-Active-Template", "")).strip()
        if category not in CATEGORY_PREFIXES or Path(template).name != template or not template:
            return jsonify({"success":False,"error":"INVALID_PREVIEW_TEMPLATE"}),400
        payload = request.get_json(silent=True) or {}
        stem = Path(template).stem
        backup_dir = Path(YEDEK_IMG_DIR) / category
        if backup_dir.is_symlink():
            return jsonify({"success":False,"error":"ORIGINAL_SYMLINK_BLOCKED"}),409
        candidates = [backup_dir / template] + [
            backup_dir / (stem + ext)
            for ext in (".png",".jpg",".jpeg",".webp",".avif")
        ]
        source = next((p for p in candidates if p.is_file() and not p.is_symlink()),None)
        if source is None:
            return jsonify({"success":False,"error":"IMMUTABLE_ORIGINAL_NOT_FOUND"}),404
        raw = cv2.imdecode(np.fromfile(str(source),dtype=np.uint8),cv2.IMREAD_UNCHANGED)
        if raw is None:
            return jsonify({"success":False,"error":"ORIGINAL_UNREADABLE"}),422
        config = payload.get("data")
        if not isinstance(config,dict):
            config=(get_all_ayarlar().get("kategoriler",{})
                    .get(category,{}).get("sablonlar",{}).get(template,{}))
        sm_dir=str(Path(SOURCE_ROOT) / "99_SISTEM_MOTORLARI_VE_KODLAR" / "SISTEM_MOTORU")
        if sm_dir not in sys.path:
            sys.path.insert(0, sm_dir)
        from sablon_beyazlatma_motoru import whiten_canvas
        whitened=whiten_canvas(
            raw,config,
            is_frameless=category in ("01_Wifi_Kutusu","04_Cam_Dograma","05_Ocak_Arkasi")
        )
        preview=save_preview_only(BASE_DIR,category,template,whitened)
        return jsonify({
            "success":True,"preview_only":True,"working_modified":False,
            "preview_url":"/preview/"+category+"/"+template,
            "preview_name":preview.name,
        })
    except (FileNotFoundError,WorkingRevisionBlocked) as error:
        return jsonify({"success":False,"error":str(error)}),409
    except Exception as error:
        logger.exception("8080 izole onizleme basarisiz")
        return jsonify({"success":False,"error":str(error)}),500


@app.route('/preview/<category>/<template>',methods=['GET'])
def api_get_izole_onizleme(category,template):
    """Serve only derived previews, never arbitrary runtime paths."""
    from core.template_identity import CATEGORY_PREFIXES
    if (category not in CATEGORY_PREFIXES or not template
            or Path(template).name != template):
        return jsonify({"success":False,"error":"INVALID_PREVIEW_PATH"}),403
    root=Path(BASE_DIR).resolve() / "_ONIZLEME_SABLONLAR"
    file=root / category / (Path(template).stem+"-beyazlatilmis-onizleme.png")
    if (root.is_symlink() or file.parent.is_symlink() or file.is_symlink()
            or not file.resolve().is_relative_to(root.resolve())):
        return jsonify({"success":False,"error":"PREVIEW_PATH_BLOCKED"}),403
    if not file.is_file():
        return jsonify({"success":False,"error":"PREVIEW_NOT_FOUND"}),404
    return send_file(str(file),mimetype="image/png")


@app.route('/api/orijinal_yukle', methods=['POST'])
@template_guard('restore-original', source='headers')
def api_orijinal_yukle():
    """Restore a template working image from the immutable original backup.

    The replacement is atomic. Any APPROVED profile bound to different source
    bytes is immediately marked stale, so the UI and production gate agree.
    """
    from SABLON_V2_MIMARI.core.safe_working_revision import (
        working_png_revision, recreate_missing_working_png, WorkingRevisionBlocked,
    )
    try:
        active_cat = request.headers.get('X-Active-Category', '')
        active_tmpl = request.headers.get('X-Active-Template', '')
        if not active_cat or not active_tmpl:
            return jsonify({"success": False, "error": "Kategori/sablon eksik"}), 400

        stem = Path(active_tmpl).stem
        backup_root = os.path.abspath(YEDEK_IMG_DIR)

        # IMPORTANT: exact filename wins. If the active template is
        # AhsapTablo_015.png and both 015.jpg + 015.png exist in the backup,
        # restoring must use the exact 015.png the user replaced.
        src_path = _find_image_asset(
            backup_root,
            active_cat,
            active_tmpl,
        )
        if src_path is None:
            return jsonify({
                "success": False,
                "error": "Orijinal yedek bulunamadi.",
            }), 404

        # Working template pool is normalized to PNG; never overwrite another
        # template or write outside the pool.
        dest_path = _safe_template_path(active_cat, stem + ".png")
        # No creation before the dedicated audited recovery transaction.
        destination_before_sha256 = (
            _sha256_file(dest_path)
            if os.path.isfile(dest_path)
            else None
        )
        backup_source_hash = _sha256_file(src_path)

        # Human-triggered operation: archive a SHA-verified working snapshot
        # and publish only the working PNG; never mutate original/raw inputs.
        from SABLON_V2_MIMARI.core.safe_working_revision import (
            working_png_revision, WorkingRevisionBlocked,
        )
        if (Path(src_path).is_symlink() or Path(src_path).parent.is_symlink()
                or Path(backup_root).is_symlink()):
            return jsonify({"success": False, "error": "ORIGINAL_SYMLINK_BLOCKED"}), 409
        # Freeze the source bytes once. A concurrent change in OneDrive/raw
        # archives between our metadata read and actual restore is forbidden.
        raw_backup_bytes = Path(src_path).read_bytes()
        if not raw_backup_bytes or hashlib.sha256(raw_backup_bytes).hexdigest() != backup_source_hash:
            return jsonify({"success": False, "error": "ORIGINAL_CHANGED_DURING_RESTORE"}), 409
        if Path(src_path).suffix.lower() == ".png":
            # Exact bytes preserve PNG metadata, transparency and origin SHA.
            source_bytes = raw_backup_bytes
        else:
            # Convert only in memory: source backup is never rewritten.
            img_raw = cv2.imdecode(
                np.frombuffer(raw_backup_bytes, dtype=np.uint8), cv2.IMREAD_UNCHANGED
            )
            if img_raw is None:
                return jsonify({"success": False, "error": "Orijinal okunamadi"}), 422
            ok, encoded = cv2.imencode(".png", img_raw)
            if not ok:
                return jsonify({"success": False, "error": "PNG_ENCODE_FAILED"}), 500
            source_bytes = encoded.tobytes()
        missing_working = not Path(dest_path).is_file()
        # The existing revision path remains unchanged for existing working
        # files; only genuinely missing files can use create-only recovery.
        operation = (
            recreate_missing_working_png if missing_working
            else working_png_revision
        )
        with operation(BASE_DIR, active_cat, active_tmpl, source_bytes):
            current_hash = _sha256_file(dest_path)
            _invalidate_stale_profiles_for_source(
                active_cat, active_tmpl, stem + ".png", current_hash
            )
        backup_relative = os.path.relpath(
            src_path,
            backup_root,
        ).replace("\\", "/")
        working_root = os.path.abspath(
            os.path.join(BASE_DIR, "2_SABLON_HAVUZU")
        )
        destination_relative = os.path.relpath(
            dest_path,
            working_root,
        ).replace("\\", "/")
        return jsonify({
            "success": True,
            "source_sha256": current_hash,
            "backup_source_sha256": backup_source_hash,
            "destination_before_sha256": destination_before_sha256,
            "destination_after_sha256": current_hash,
            "backup_source_file": backup_relative,
            "backup_source_absolute": os.path.abspath(src_path),
            "backup_source_exact_name": (
                Path(src_path).name == Path(active_tmpl).name
            ),
            "destination_file": destination_relative,
            "destination_absolute": os.path.abspath(dest_path),
            "runtime_root": os.path.abspath(BASE_DIR),
            "source_root": "2_SABLON_HAVUZU_ORIJINAL_YEDEK",
            "destination_root": "2_SABLON_HAVUZU",
            "png_byte_exact_restore": bool(
                Path(src_path).suffix.lower() == ".png"
                and backup_source_hash == current_hash
            ),
            "profiles_revalidation_required": True,
            "recreated_missing_working": missing_working,
        })
    except (WorkingRevisionBlocked, FileNotFoundError) as exc:
        return jsonify({"success": False, "error": str(exc)}), 409
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception as exc:
        logger.exception("Orijinal sablon geri yukleme hatasi")
        return jsonify({"success": False, "error": str(exc)}), 500



@app.route('/api/lifecycle/center')
def api_lifecycle_center():
    """Read-only reconciliation/trash/recovery inventory."""
    try:
        limit = int(request.args.get("limit", 50) or 50)
        report = lifecycle_center_report(
            BASE_DIR,
            get_all_ayarlar(),
            limit=max(1, min(200, limit)),
        )
        return jsonify(report)
    except Exception as exc:
        logger.exception("Lifecycle merkezi raporu hazırlanamadı")
        return jsonify({
            "success": False,
            "error": str(exc),
        }), 500


@app.route('/api/staging/latest-collision')
def api_staging_latest_collision():
    """Return the most recent persisted staging identity/number collision."""
    txn_dir = (
        Path(BASE_DIR)
        / "SABLON_V2_MIMARI"
        / "recovery"
        / "staging_transactions"
    )
    if not txn_dir.is_dir():
        return jsonify({
            "success": True,
            "collision": None,
        })

    candidates = sorted(
        txn_dir.glob("*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for txn_path in candidates[:100]:
        try:
            data = json.loads(txn_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        identity_conflict = data.get("identity_conflict")
        number_conflict = data.get("number_conflict")
        if not identity_conflict and not number_conflict:
            continue

        try:
            age_seconds = max(
                0.0,
                time.time() - float(txn_path.stat().st_mtime),
            )
        except OSError:
            age_seconds = None

        return jsonify({
            "success": True,
            "collision": {
                "transaction_id": (
                    data.get("transaction_id")
                    or txn_path.stem
                ),
                "state": data.get("state"),
                "updated_at": data.get("updated_at"),
                "age_seconds": age_seconds,
                "error": data.get("error"),
                "identity_conflict": identity_conflict,
                "number_conflict": number_conflict,
            },
        })

    return jsonify({
        "success": True,
        "collision": None,
    })


@app.route('/api/lifecycle/resolve-duplicate', methods=['POST'])
def api_lifecycle_resolve_duplicate():
    """Move non-kept duplicate variants to recoverable lifecycle storage."""
    payload = request.get_json(silent=True) or {}
    category = str(payload.get("category") or "").strip()
    identity = str(payload.get("identity") or "").strip()
    area = str(payload.get("area") or "").strip()
    keep_filename = str(payload.get("keep_filename") or "").strip()
    if not category or not identity or not area or not keep_filename:
        return jsonify({
            "success": False,
            "error": "Duplicate çözümü için alan/kategori/kimlik/korunacak dosya eksik.",
        }), 400

    lock_name = str(payload.get("template") or keep_filename or identity)
    try:
        with template_operation_lock(
            category,
            lock_name,
            "resolve-duplicate",
            wait_seconds=0.25,
        ):
            result = archive_duplicate_variants(
                BASE_DIR,
                get_all_ayarlar(),
                area=area,
                category=category,
                identity=identity,
                keep_filename=keep_filename,
            )
        return jsonify({
            "success": True,
            "operation": result,
        })
    except LifecycleSafetyError as exc:
        return jsonify({
            "success": False,
            "error": str(exc),
            "code": "LIFECYCLE_SAFETY_BLOCK",
        }), 409
    except TemplateBusyError as exc:
        return jsonify({
            "success": False,
            "error": str(exc),
            "code": "TEMPLATE_BUSY",
        }), 409
    except Exception as exc:
        logger.exception("Duplicate recovery işlemi başarısız")
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route('/api/lifecycle/archive-working-orphan', methods=['POST'])
def api_lifecycle_archive_working_orphan():
    """Archive one DB-less working identity without permanent deletion."""
    payload = request.get_json(silent=True) or {}
    category = str(payload.get("category") or "").strip()
    identity = str(payload.get("identity") or "").strip()
    if not category or not identity:
        return jsonify({
            "success": False,
            "error": "Kategori veya çalışma yetimi kimliği eksik.",
        }), 400

    try:
        with template_operation_lock(
            category,
            identity,
            "archive-working-orphan",
            wait_seconds=0.25,
        ):
            result = archive_working_orphan(
                BASE_DIR,
                get_all_ayarlar(),
                category=category,
                identity=identity,
            )
        return jsonify({
            "success": True,
            "operation": result,
        })
    except LifecycleSafetyError as exc:
        return jsonify({
            "success": False,
            "error": str(exc),
            "code": "LIFECYCLE_SAFETY_BLOCK",
        }), 409
    except TemplateBusyError as exc:
        return jsonify({
            "success": False,
            "error": str(exc),
            "code": "TEMPLATE_BUSY",
        }), 409
    except Exception as exc:
        logger.exception("Çalışma yetimi recovery işlemi başarısız")
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route('/api/lifecycle/retire-db-orphan', methods=['POST'])
def api_lifecycle_retire_db_orphan():
    """Retire an active DB record only after proving both file sources are absent."""
    payload = request.get_json(silent=True) or {}
    category = str(payload.get("category") or "").strip()
    template = str(payload.get("template") or "").strip()
    if not category or not template:
        return jsonify({
            "success": False,
            "error": "Kategori veya şablon eksik.",
        }), 400

    working_root = os.path.join(BASE_DIR, "2_SABLON_HAVUZU")
    backup_root = os.path.join(
        BASE_DIR,
        "2_SABLON_HAVUZU_ORIJINAL_YEDEK",
    )
    if (
        _find_image_asset(working_root, category, template) is not None
        or _find_image_asset(backup_root, category, template) is not None
    ):
        return jsonify({
            "success": False,
            "error": (
                "Bu kayıt gerçek DB-yetimi değil; çalışma veya ham dosyası mevcut. "
                "Otomatik retire engellendi."
            ),
            "code": "NOT_DB_ORPHAN",
        }), 409

    try:
        result = _retire_template_safely(category, template)
        return jsonify({"success": True, **result})
    except (ValueError, FileNotFoundError) as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except TemplateBusyError as exc:
        return jsonify({
            "success": False,
            "error": str(exc),
            "code": "TEMPLATE_BUSY",
        }), 409
    except Exception as exc:
        logger.exception("DB yetimi retire işlemi başarısız")
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route('/api/lifecycle/undo', methods=['POST'])
def api_lifecycle_undo():
    """Undo the latest recoverable duplicate/orphan archive operation."""
    payload = request.get_json(silent=True) or {}
    operation_id = str(payload.get("operation_id") or "").strip() or None
    try:
        result = undo_lifecycle_operation(
            BASE_DIR,
            operation_id=operation_id,
        )
        return jsonify({
            "success": True,
            "operation": result,
        })
    except LifecycleSafetyError as exc:
        return jsonify({
            "success": False,
            "error": str(exc),
            "code": "LIFECYCLE_SAFETY_BLOCK",
        }), 409
    except Exception as exc:
        logger.exception("Lifecycle geri alma başarısız")
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route('/api/templates/replace-original', methods=['POST'])
@template_guard('replace-original', source='headers', wait_seconds=0.25)
def api_replace_original():
    """Replace raw source + working copy while archiving all previous bytes."""
    active_cat = str(
        request.headers.get("X-Active-Category", "")
    ).strip()
    active_tmpl = str(
        request.headers.get("X-Active-Template", "")
    ).strip()
    if not active_cat or not active_tmpl:
        return jsonify({
            "success": False,
            "error": "Kategori veya şablon eksik.",
        }), 400

    upload = request.files.get("file")
    if upload is None or not upload.filename:
        return jsonify({
            "success": False,
            "error": "Yeni ham görsel seçilmedi.",
        }), 400

    settings = get_all_ayarlar()
    active_templates = (
        settings.get("kategoriler", {})
        .get(active_cat, {})
        .get("sablonlar", {})
    )
    if active_tmpl not in active_templates:
        return jsonify({
            "success": False,
            "error": "Aktif şablon DB kaydı bulunamadı.",
        }), 404

    try:
        payload = upload.read()
        result = replace_original_and_working(
            BASE_DIR,
            category=active_cat,
            template=active_tmpl,
            upload_filename=upload.filename,
            upload_bytes=payload,
        )

        current_hash = str(result.get("new_working_sha256") or "")
        previous_conf = dict(active_templates.get(active_tmpl) or {})
        legacy_conf = dict(previous_conf)
        legacy_conf["review_status"] = "STALE_SOURCE_CHANGED"
        legacy_conf["supheli"] = True
        legacy_conf["source_replace_operation"] = result.get("operation_id")
        legacy_conf["source_asset_sha256"] = current_hash

        try:
            save_template(active_cat, active_tmpl, legacy_conf)
            stale_count = _invalidate_stale_profiles_for_source(
                active_cat,
                active_tmpl,
                str(result.get("new_working_filename") or active_tmpl),
                current_hash,
            )
        except Exception:
            try:
                rollback_replace_original(
                    BASE_DIR,
                    str(result.get("operation_id") or ""),
                )
            finally:
                try:
                    save_template(
                        active_cat,
                        active_tmpl,
                        previous_conf,
                    )
                except Exception:
                    logger.exception(
                        "Kaynak değiştirme DB rollback config geri yüklenemedi"
                    )
            raise

        return jsonify({
            "success": True,
            "operation_id": result.get("operation_id"),
            "backup_source_absolute": result.get("new_backup_absolute"),
            "working_absolute": result.get("new_working_absolute"),
            "backup_sha256": result.get("new_backup_sha256"),
            "working_sha256": current_hash,
            "profiles_marked_stale": stale_count,
            "review_status": "STALE_SOURCE_CHANGED",
            "previous_bytes_archived": len(result.get("moved", []) or []),
            "recovery_operation": result,
        })
    except LifecycleSafetyError as exc:
        return jsonify({
            "success": False,
            "error": str(exc),
            "code": "LIFECYCLE_SAFETY_BLOCK",
        }), 409
    except Exception as exc:
        logger.exception("Ham kaynak değiştirme başarısız")
        return jsonify({"success": False, "error": str(exc)}), 500


# V4.6 proposals live OUTSIDE production DB and working/backup template pools.
# A bulk analyze request NEVER writes to template_profiles or APPROVED geometry.
def _v46_draft_folder():
    user_root = Path(os.environ.get("LOCALAPPDATA") or
                     (Path.home() / ".local" / "share"))
    folder = user_root / "GorselMockup" / "v46_review_proposals"
    if folder.exists() and folder.is_symlink():
        raise ValueError("Taslak klasörü bağlantı (symlink) olamaz")
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _v46_draft_path(category, template):
    # Collision-safe unique identity without using the filename as a path.
    key = hashlib.sha256(json.dumps([str(Path(BASE_DIR).resolve()), category, template],
                                   ensure_ascii=False).encode("utf-8")).hexdigest()
    return _v46_draft_folder() / f"{key}.json"


def _v46_store_draft(category, template, corners, source_hash, surface_mode):
    path = _v46_draft_path(category, template)
    if path.is_symlink():
        raise ValueError("Taslak dosyası symlink")
    payload = {"category": category, "template": template, "corners": corners,
               "source_sha256": source_hash, "surface_mode": surface_mode,
               "approved": False, "version": "v46-draft-1"}
    temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temp.open("x", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


@app.route('/api/v46/corner_draft', methods=['GET'])
def api_v46_corner_draft():
    category = str(request.args.get("category", ""))
    template = str(request.args.get("template", ""))
    if not category or not template:
        return jsonify({"success": False, "error": "Kategori / şablon eksik"}), 400
    try:
        img_path = _safe_template_path(category, template)
        if not os.path.isfile(img_path):
            return jsonify({"success": False, "error": "Kaynak yok"}), 404
        path = _v46_draft_path(category, template)
        if path.is_symlink():
            return jsonify({"success": False, "error": "Güvensiz taslak dosyası"}), 409
        if not path.is_file():
            return jsonify({"success": True, "available": False})
        draft = json.loads(path.read_text(encoding="utf-8"))
        if draft.get("source_sha256") != _sha256_file(img_path):
            return jsonify({"success": True, "available": False,
                            "stale": True, "reason": "Kaynak resmi değişmiş; eski öneri kullanılamaz."})
        if draft.get("category") != category or draft.get("template") != template:
            return jsonify({"success": False, "error": "Taslak kimlik uyuşmazlığı"}), 409
        corners = draft.get("corners")
        if not isinstance(corners, list) or len(corners) != 4:
            return jsonify({"success": False, "error": "Taslak geometri bozuk"}), 409
        return jsonify({"success": True, "available": True, "corners": corners,
                        "surface_mode": draft.get("surface_mode"),
                        "source_sha256": draft.get("source_sha256"),
                        "approved": False})
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        return jsonify({"success": False, "error": str(exc)}), 400


@app.route('/api/auto_detect_corners', methods=['POST'])
@template_guard('auto-detect-corners', source='headers')
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

        detected_source_hash = _sha256_file(img_path)
        img_cv = cv2.imdecode(
            np.fromfile(img_path, dtype=np.uint8),
            cv2.IMREAD_COLOR,
        )
        if img_cv is None:
            return jsonify({"success": False, "error": "Resim okunamadi"}), 500

        # BEGIN ISOLATED_MAGENTA_QUAD_V1: independent color-only review suggestion.
        from core.chroma_quad_detector import detect as _chroma_detect
        chroma_result = _chroma_detect(img_cv, active_cat)
        if chroma_result.get("chroma_present", False):
            if not chroma_result.get("quad"):
                return jsonify({
                    "success": False,
                    "error": "Magenta belirsiz: insan incelemesi gerekli",
                    "code": "CHROMA_REVIEW_REQUIRED",
                    "engine": "magenta_color_quad_v1",
                    "review_status": "REVIEW_REQUIRED",
                    "reason": chroma_result.get("reason", "CHROMA_NO_VALID_QUAD"),
                }), 422
            candidate = np.asarray(chroma_result["quad"], dtype=np.float32)
            valid, reason = GeometryValidator.is_valid_quad(
                candidate, img_cv.shape[1], img_cv.shape[0])
            if not valid:
                return jsonify({
                    "success": False,
                    "error": "Magenta geometri gecersiz: " + str(reason),
                    "engine": "magenta_color_quad_v1",
                    "review_status": "REVIEW_REQUIRED",
                }), 422
            candidate = GeometryValidator.canonical_sort(candidate).astype(float).tolist()
            if detected_source_hash != _sha256_file(img_path):
                return jsonify({"success": False, "code": "SOURCE_CHANGED", "error": "Kaynak tespit sırasında değişti."}), 409
            draft_saved = (request.get_json(silent=True) or {}).get("save_as_draft") is True
            if draft_saved:
                _v46_store_draft(active_cat, active_tmpl, candidate, detected_source_hash, "MAGENTA_MARKED_SOURCE")
            return jsonify({
                "success": True,
                "corners": candidate,
                "source_sha256": _sha256_file(img_path),
                "engine": "magenta_color_quad_v1",
                "review_status": "REVIEW_REQUIRED",
                "confidence": 0.0,
                "component_confidences": {},
                "surface_mode": "MAGENTA_MARKED_SOURCE",
                "surface_mode_confidence": 0.0,
                "nominal_aspect": "UNKNOWN",
                "occlusions": [],
                "magenta_mask_iou": chroma_result.get("magenta_mask_iou"),
                "magenta_polygon_purity": chroma_result.get("magenta_polygon_purity"),
                "chroma_detector_status": chroma_result.get("status"),
                "chroma_warning": chroma_result.get("reason"),
                "draft_saved": draft_saved,
                "warning": "Renk dedektoru sadece DRAFT oneri verir. INSAN ONAYI ZORUNLU.",
            })
        # END ISOLATED_MAGENTA_QUAD_V1

        analysis, cache_hit = _analyze_auto_cached(
            active_cat,
            img_path,
        )
        corners = analysis.get("surface_quad")
        engine = (
            "template_analyzer_cache"
            if cache_hit
            else "template_analyzer"
        )

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

        source_hash = _sha256_file(img_path)
        if (request.get_json(silent=True) or {}).get("save_as_draft") is True:
            try:
                _v46_store_draft(active_cat, active_tmpl, corners, source_hash,
                                 analysis.get("surface_mode", "UNKNOWN"))
            except (OSError, ValueError) as exc:
                return jsonify({"success": False, "error": f"Taslak kaydı başarısız: {exc}"}), 500

        return jsonify({
            "success": True,
            "corners": corners,
            "source_sha256": source_hash,
            "occlusions": occlusion_data,
            "engine": engine,
            "confidence": float(analysis.get("confidence_total", 0.0) or 0.0),
            "component_confidences": analysis.get("component_confidences", {}),
            "surface_mode": analysis.get("surface_mode", "UNKNOWN"),
            "surface_priority_hint": (
                "SEFFAF_CAM_ONCELIKLI" if analysis.get("surface_mode") == "TRANSPARENT_GLASS"
                else "BEYAZ_CAM_ADAYI_KATEGORI_TAHMINI" if analysis.get("surface_mode") == "WHITE" and (
                    "Cam" in active_cat or "Ocak_Arkasi" in active_cat)
                else "CAM_OLMAYAN_BEYAZ" if analysis.get("surface_mode") == "WHITE"
                else "CAM_OLMAYAN_SIYAH" if analysis.get("surface_mode") == "BLACK"
                else "DIGER_VEYA_KARARSIZ"
            ),
            "surface_mode_confidence": float(
                analysis.get("surface_mode_confidence", 0.0) or 0.0
            ),
            "review_status": "REVIEW_REQUIRED",
            "nominal_aspect": analysis.get("nominal_aspect", "UNKNOWN"),
        })
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        logger.exception("Otomatik kose onerisi hatasi")
        return jsonify({"success": False, "error": str(e)}), 500

def _find_template_backup_asset(category: str, template_name: str):
    """Resolve raw backup only when the extension-insensitive identity is unique.

    Destructive/restore operations must never silently pick one extension when
    two files share the same stem.
    """
    backup_root = os.path.abspath(
        os.path.join(BASE_DIR, "2_SABLON_HAVUZU_ORIJINAL_YEDEK")
    )
    category_dir = Path(
        _safe_under_root(
            backup_root,
            category,
            label="orijinal yedek kategorisi",
        )
    )
    matches = same_stem_files(category_dir, template_name)
    if not matches:
        return None
    if len(matches) > 1:
        extensions = ", ".join(
            sorted({path.suffix.casefold() for path in matches})
        )
        names = ", ".join(path.name for path in matches)
        raise ValueError(
            "⛔ AYNI İSİM, FARKLI UZANTI: kritik ham dosya işlemi "
            "otomatik seçim yapmadı. "
            f"Kimlik={category}/{canonical_identity(template_name)}; "
            f"uzantılar={extensions}; dosyalar={names}. "
            "Önce Güvenli Eşitleme Merkezi'nden duplicate kaydını çözün."
        )
    return str(matches[0])


def _retire_template_safely_unlocked(active_cat: str, active_tmpl: str) -> dict:
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
    source_was_missing = not os.path.isfile(src_img)

    trash_dir = os.path.join(BASE_DIR, "SILINEN_SABLONLAR_COP_KUTUSU")
    os.makedirs(trash_dir, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    token = uuid.uuid4().hex[:8]
    safe_stem = Path(active_tmpl).stem

    trash_image_name = None
    trash_img = None
    if not source_was_missing:
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
            "source_sha256": (
                None if source_was_missing else _sha256_file(src_img)
            ),
            "source_was_missing": bool(source_was_missing),
            "deleted_at": stamp,
        }

        tmp_meta = meta_path + ".tmp"
        with open(tmp_meta, "w", encoding="utf-8") as handle:
            json.dump(meta_data, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_meta, meta_path)

        if not source_was_missing and trash_img:
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
        "source_was_missing": bool(source_was_missing),
        "orphan_retired": bool(source_was_missing),
    }


def _retire_template_safely(active_cat: str, active_tmpl: str) -> dict:
    with template_operation_lock(
        active_cat,
        active_tmpl,
        "delete",
        wait_seconds=0.25,
    ):
        return _retire_template_safely_unlocked(
            active_cat,
            active_tmpl,
        )


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
    except TemplateBusyError as exc:
        return jsonify({
            "success": False,
            "error": str(exc),
            "code": "TEMPLATE_BUSY",
        }), 409
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
        source_was_missing = bool(meta.get("source_was_missing"))
        trash_image_name = meta.get('trash_image_name')
        if not source_was_missing and not trash_image_name:
            trash_image_name = tmpl
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

        source_in_trash = None
        if not source_was_missing:
            source_in_trash = _safe_under_root(
                trash_dir,
                trash_image_name,
                label="cop kutusu",
            )

        restore_path = _safe_template_path(cat, tmpl)
        restore_dir = os.path.dirname(restore_path)
        os.makedirs(restore_dir, exist_ok=True)

        # The identity includes ALL format variants; restore cannot silently
        # publish a .png beside an existing same-stem .jpeg or .webp.
        if os.path.exists(restore_path) or same_stem_files(Path(restore_dir), tmpl):
            return jsonify({
                "success": False,
                "error": (
                    "Aynı isimde aktif şablon zaten var; üzerine yazılmadı."
                ),
            }), 409
        if (
            not source_was_missing
            and not os.path.isfile(source_in_trash)
        ):
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
            if os.path.exists(restored_backup) or same_stem_files(Path(backup_cat_dir), Path(restored_backup).name):
                return jsonify({
                    "success": False,
                    "error": (
                        "Orijinal yedek hedefinde aynı isimde dosya var; "
                        "geri alma üzerine yazma yapmadı."
                    ),
                }), 409

        lock_token = acquire_template_lock(
            cat,
            tmpl,
            "undo-delete",
            wait_seconds=0.25,
        )
        linked_back = []
        db_path = os.path.join(BASE_DIR, "SABLON_V2_MIMARI", "ayarlar.db")
        conn = sqlite3.connect(db_path)
        try:
            if not source_was_missing and source_in_trash:
                # os.link is exclusively create-only on Windows and POSIX.
                # Trash source remains intact if a later SQLite step fails.
                os.link(source_in_trash, restore_path)
                linked_back.append((restore_path, source_in_trash))

            if (
                backup_source_in_trash
                and restored_backup
                and os.path.isfile(backup_source_in_trash)
            ):
                os.link(backup_source_in_trash, restored_backup)
                linked_back.append((restored_backup, backup_source_in_trash))

            restored_hash = (
                "" if source_was_missing else _sha256_file(restore_path)
            )
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
            for created_path, trash_source in reversed(linked_back):
                try:
                    if (
                        os.path.isfile(created_path)
                        and os.path.isfile(trash_source)
                        and os.path.samefile(created_path, trash_source)
                    ):
                        os.unlink(created_path)
                except OSError:
                    logger.exception("P0 RESTORE_RECOVERY_REQUIRED: %s", created_path)
            raise
        finally:
            conn.close()
            release_template_lock(cat, tmpl, lock_token)

        # Keep the trashed input bytes for recovery/audit. Removing only
        # the metadata makes this entry ineligible for repeated undo.
        os.remove(meta_path)
        return jsonify({
            "success": True,
            "restored_tmpl": tmpl,
            "reactivated_profiles": reactivated,
            "backup_restored": bool(restored_backup),
            "source_restored": not source_was_missing,
            "restored_as_orphan": bool(source_was_missing),
        })
    except TemplateBusyError as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "code": "TEMPLATE_BUSY",
        }), 409
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
    """Resolve preview asset with exact-name precedence, otherwise unique stem.

    Preview may show the exact DB-selected file even when legacy alternate
    extensions still exist. If the exact file is missing and several same-stem
    variants exist, guessing is forbidden.
    """
    import urllib.parse

    category = urllib.parse.unquote(str(category or ""))
    template_name = urllib.parse.unquote(str(template_name or ""))
    safe_root = os.path.abspath(root)
    category_dir = Path(
        _safe_under_root(
            safe_root,
            category,
            label="gorsel kategorisi",
        )
    )

    exact = Path(
        _safe_under_root(
            str(category_dir),
            template_name,
            label="gorsel",
        )
    )
    if exact.is_file():
        return str(exact)

    matches = same_stem_files(category_dir, template_name)
    if len(matches) == 1:
        return str(matches[0])
    if len(matches) > 1:
        extensions = ", ".join(
            sorted({path.suffix.casefold() for path in matches})
        )
        names = ", ".join(path.name for path in matches)
        raise ValueError(
            "AYNI İSİM, FARKLI UZANTI belirsizliği: "
            f"{category} / {canonical_identity(template_name)}. "
            f"Uzantılar: {extensions}. Dosyalar: {names}. "
            "Exact istenen dosya bulunmadığı için sistem seçim yapmadı."
        )
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
    try:
        img_path = _find_image_asset(working_root, cat, tmpl)
    except ValueError as exc:
        return str(exc), 409
    if img_path is None:
        return "Calisma gorseli bulunamadi", 404
    return _send_image_no_cache(img_path)


@app.route('/original-image/<cat>/<tmpl>')
def serve_original_image(cat, tmpl):
    """Serve only the immutable/raw original backup for visual inspection."""
    backup_root = os.path.abspath(YEDEK_IMG_DIR)
    try:
        img_path = _find_image_asset(backup_root, cat, tmpl)
    except ValueError as exc:
        return str(exc), 409
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


def _analyze_auto_cached(category: str, img_path: str):
    """Run the unchanged AUTO analyzer only when cache identity misses."""
    source_hash = _sha256_file(img_path)
    analyzer = TemplateAnalyzer()
    cached = load_analysis_cache(
        category,
        source_hash,
        analyzer.version,
    )
    if cached is not None:
        return cached, True

    analysis = analyzer.analyze(
        img_path,
        category,
        manual_geometry_prior=None,
    )
    save_analysis_cache(
        category,
        source_hash,
        analyzer.version,
        analysis,
    )
    analysis = dict(analysis)
    analysis["_cache_hit"] = False
    return analysis, False


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


def _is_source_matching_approved(db_path, uid, img_path):
    """Fast batch preflight for immutable human-approved geometry.

    Query first so non-approved templates do not pay a file-hash cost. Only
    source-matching, manually verified APPROVED profiles are skipped.
    """
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            """SELECT source_asset_sha256
               FROM template_profiles
               WHERE template_uid=? AND is_active=1
                 AND manually_verified=1
                 AND review_status='APPROVED'
               ORDER BY updated_at DESC, rowid DESC
               LIMIT 1""",
            (uid,),
        ).fetchone()
    finally:
        conn.close()

    if not row or not row[0] or not os.path.isfile(img_path):
        return False

    return str(row[0]) == _sha256_file(img_path)


def _profile_data_from_analysis(category, template_name, analysis):
    return {
        "template_uid": f"{category}_{template_name}",
        "category": category,
        "source_relative_path": f"{category}/{template_name}",
        "source_asset_sha256": analysis.get("source_asset_sha256"),
        "profile_version": "v2",
        "analyzer_version": analysis.get("analyzer_version"),
        "product_class": analysis.get("rule", {}).get(
            "product_class",
            "Bilinmeyen",
        ),
        "orientation": analysis.get("orientation", "UNKNOWN"),
        "nominal_aspect": analysis.get("nominal_aspect", "UNKNOWN"),
        "print_policy": analysis.get("rule", {}).get(
            "print_policy",
            "full_bleed",
        ),
        "surface_quad": analysis.get("surface_quad"),
        "outer_quad": analysis.get("outer_quad"),
        "confidence_total": analysis.get("confidence_total", 0.0),
        "component_confidences": analysis.get(
            "component_confidences",
            {},
        ),
        "review_status": analysis.get(
            "review_status",
            "UNANALYZED",
        ),
        "manually_verified": False,
    }


def _analyze_template_for_batch(category, template_name):
    """CPU-heavy stage with backend lock + source/version cache."""
    img_path = _safe_template_path(category, template_name)
    if not os.path.isfile(img_path):
        return {
            "template": template_name,
            "status": "MISSING",
            "error": "Görsel bulunamadı",
        }

    try:
        with template_operation_lock(
            category,
            template_name,
            "batch-analyze",
            wait_seconds=0.35,
        ):
            # Use the same source-specific engine as single-image review.
            from core.chroma_quad_detector import detect
            source_hash = _sha256_file(img_path)
            image = cv2.imdecode(np.fromfile(img_path, dtype=np.uint8), cv2.IMREAD_COLOR)
            if image is None:
                raise ValueError("Görsel okunamadı")
            chroma = detect(image, category)
            if chroma.get("chroma_present"):
                quad = chroma.get("quad")
                if not quad:
                    return {"template": template_name, "status": "REVIEW_REQUIRED",
                            "reason": chroma.get("reason"), "engine": "magenta_color_quad_v1"}
                valid, reason = GeometryValidator.is_valid_quad(np.asarray(quad), image.shape[1], image.shape[0])
                if not valid:
                    return {"template": template_name, "status": "REVIEW_REQUIRED", "reason": str(reason)}
                if source_hash != _sha256_file(img_path):
                    return {"template": template_name, "status": "SOURCE_CHANGED"}
                # Sidecar draft only. Never replace a profile or its approval.
                _v46_store_draft(category, template_name, quad, source_hash, "MAGENTA_MARKED_SOURCE")
                return {"template": template_name, "status": "ANALYZED",
                        "draft_only": True, "review_status": "REVIEW_REQUIRED",
                        "engine": "magenta_color_quad_v1", "reason": chroma.get("reason"),
                        "draft_saved": True}
            analysis, cache_hit = _analyze_auto_cached(category, img_path)
        return {
            "template": template_name,
            "status": "ANALYZED",
            "analysis": analysis,
            "cache_hit": bool(cache_hit),
        }
    except TemplateBusyError as exc:
        return {
            "template": template_name,
            "status": "BUSY",
            "error": str(exc),
        }
    except Exception as exc:
        return {
            "template": template_name,
            "status": "FAILED",
            "error": str(exc),
        }


@app.route('/api/templates/foreground_detect', methods=['POST'])
@template_guard('foreground-detect', source='json')
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
@template_guard('analyze', source='headers')
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
        
        profile_data = _profile_data_from_analysis(
            active_cat,
            active_tmpl,
            result,
        )
        
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
            valid, reason = GeometryValidator.is_valid_quad(quad, w, h, manual=True)
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


def _run_batch_analysis_core(
    category,
    requested_templates,
    *,
    workers=2,
):
    """Run one small analysis batch with unchanged CV quality."""
    category = str(category or "").strip()
    if not category:
        raise ValueError("Kategori eksik")

    settings = get_all_ayarlar()
    registered = (
        settings.get("kategoriler", {})
        .get(category, {})
        .get("sablonlar", {})
    )
    if not isinstance(registered, dict):
        registered = {}

    templates = []
    seen = set()
    for value in list(requested_templates or [])[:12]:
        template_name = str(value or "").strip()
        if (
            template_name
            and template_name not in seen
            and template_name in registered
        ):
            templates.append(template_name)
            seen.add(template_name)

    worker_count = max(1, min(2, int(workers or 2)))
    db_path = os.path.join(
        BASE_DIR,
        "SABLON_V2_MIMARI",
        "ayarlar.db",
    )

    results_by_name = {}
    to_analyze = []

    for template_name in templates:
        img_path = _safe_template_path(category, template_name)
        if not os.path.isfile(img_path):
            results_by_name[template_name] = {
                "template": template_name,
                "status": "MISSING",
                "error": "Görsel bulunamadı",
            }
            continue

        uid = f"{category}_{template_name}"
        if _is_source_matching_approved(
            db_path,
            uid,
            img_path,
        ):
            results_by_name[template_name] = {
                "template": template_name,
                "status": "SKIPPED_APPROVED",
                "review_status": "APPROVED",
                "preserved": True,
            }
            continue
        conn = sqlite3.connect(Path(db_path).resolve().as_uri()+"?mode=ro", uri=True)
        try:
            protected = conn.execute("SELECT 1 FROM template_profiles WHERE template_uid=? AND is_active=1 AND manually_verified=1 AND review_status='APPROVED'", (uid,)).fetchone()
        finally:
            conn.close()
        if protected:
            results_by_name[template_name] = {"template": template_name, "status": "REVIEW_REQUIRED", "reason": "APPROVED_SOURCE_SHA_MISMATCH"}
            continue
        to_analyze.append(template_name)

    analysis_results = {}
    if to_analyze:
        if worker_count == 1 or len(to_analyze) == 1:
            for template_name in to_analyze:
                analysis_results[template_name] = (
                    _analyze_template_for_batch(
                        category,
                        template_name,
                    )
                )
        else:
            with ThreadPoolExecutor(
                max_workers=worker_count,
                thread_name_prefix="quad-scan",
            ) as executor:
                future_map = {
                    executor.submit(
                        _analyze_template_for_batch,
                        category,
                        template_name,
                    ): template_name
                    for template_name in to_analyze
                }
                for future in as_completed(future_map):
                    template_name = future_map[future]
                    try:
                        analysis_results[template_name] = future.result()
                    except Exception as exc:
                        analysis_results[template_name] = {
                            "template": template_name,
                            "status": "FAILED",
                            "error": str(exc),
                        }

    # Writes remain deliberately sequential. Re-lock and re-check source bytes
    # before saving so a restore/delete/edit between analysis and save cannot
    # attach stale geometry to new bytes.
    for template_name in to_analyze:
        item = analysis_results.get(template_name) or {
            "template": template_name,
            "status": "FAILED",
            "error": "Analiz sonucu alınamadı",
        }
        if item.get("status") != "ANALYZED" or item.get("draft_only"):
            results_by_name[template_name] = item
            continue

        analysis = item.get("analysis") or {}
        try:
            with template_operation_lock(
                category,
                template_name,
                "batch-save-analysis",
                wait_seconds=0.35,
            ):
                current_path = _safe_template_path(
                    category,
                    template_name,
                )
                if not os.path.isfile(current_path):
                    results_by_name[template_name] = {
                        "template": template_name,
                        "status": "MISSING",
                        "error": "Kaynak analiz sonrası kaldırıldı.",
                    }
                    continue
                current_hash = _sha256_file(current_path)
                if current_hash != str(
                    analysis.get("source_asset_sha256") or ""
                ):
                    results_by_name[template_name] = {
                        "template": template_name,
                        "status": "SOURCE_CHANGED",
                        "error": (
                            "Kaynak analiz sırasında değişti; eski sonuç "
                            "kaydedilmedi."
                        ),
                    }
                    continue

                save_template_profile(
                    db_path,
                    _profile_data_from_analysis(
                        category,
                        template_name,
                        analysis,
                    ),
                )
            results_by_name[template_name] = {
                "template": template_name,
                "status": "ANALYZED",
                "review_status": analysis.get(
                    "review_status",
                    "UNANALYZED",
                ),
                "cache_hit": bool(item.get("cache_hit")),
            }
        except TemplateBusyError as exc:
            results_by_name[template_name] = {
                "template": template_name,
                "status": "BUSY",
                "error": str(exc),
            }
        except Exception as exc:
            results_by_name[template_name] = {
                "template": template_name,
                "status": "FAILED",
                "error": str(exc),
            }

    ordered_results = [
        results_by_name.get(
            template_name,
            {
                "template": template_name,
                "status": "FAILED",
                "error": "Sonuç bulunamadı",
            },
        )
        for template_name in templates
    ]

    return {
        "success": True,
        "results": ordered_results,
        "analyzed_count": sum(
            1 for item in ordered_results
            if item.get("status") == "ANALYZED"
        ),
        "cache_hit_count": sum(
            1 for item in ordered_results
            if item.get("status") == "ANALYZED"
            and item.get("cache_hit")
        ),
        "approved_preserved_count": sum(
            1 for item in ordered_results
            if item.get("status") == "SKIPPED_APPROVED"
        ),
        "missing_count": sum(
            1 for item in ordered_results
            if item.get("status") == "MISSING"
        ),
        "busy_count": sum(
            1 for item in ordered_results
            if item.get("status") == "BUSY"
        ),
        "source_changed_count": sum(
            1 for item in ordered_results
            if item.get("status") == "SOURCE_CHANGED"
        ),
        "failed_count": sum(
            1 for item in ordered_results
            if item.get("status") == "FAILED"
        ),
        "workers_used": worker_count,
        "quality_algorithm": "UNCHANGED",
        "db_writes": "SEQUENTIAL",
    }


@app.route('/api/templates/batch_analyze', methods=['POST'])
def api_templates_batch_analyze():
    """Compatibility endpoint; persistent UI uses the Job Engine."""
    try:
        req = request.get_json(silent=True) or {}
        category = str(req.get("category") or "").strip()
        requested_templates = req.get("templates")
        if not category:
            return jsonify({
                "success": False,
                "error": "Kategori eksik",
            }), 400

        settings = get_all_ayarlar()
        registered = (
            settings.get("kategoriler", {})
            .get(category, {})
            .get("sablonlar", {})
        )
        if not isinstance(registered, dict):
            registered = {}

        if isinstance(requested_templates, list):
            templates = requested_templates[:12]
        else:
            templates = list(registered.keys())[:12]

        return jsonify(
            _run_batch_analysis_core(
                category,
                templates,
                workers=req.get("workers", 2),
            )
        )
    except ValueError as exc:
        return jsonify({
            "success": False,
            "error": str(exc),
        }), 400
    except Exception as exc:
        logger.exception("Toplu sablon analizi hatasi")
        return jsonify({
            "success": False,
            "error": str(exc),
        }), 500


@app.route('/api/templates/update_corners', methods=['POST'])
@template_guard('approve-update-corners', source='json')
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
        bulk_approval = req.get("bulk_approval") is True
        # A bulk selection is not proof that the operator inspected each foreground.
        if bulk_approval and (occlusion_reviewed or req_on_plan is not None):
            return jsonify({"success": False,
                            "error": "Toplu onayda ön plan koruma onayı atlanamaz."}), 422
        if not uid or corners is None:
            return jsonify({"success": False, "error": "Eksik parametre"}), 400

        db_path = os.path.join(BASE_DIR, "SABLON_V2_MIMARI", "ayarlar.db")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            if bulk_approval:
                active_count = conn.execute(
                    "SELECT COUNT(*) FROM template_profiles WHERE template_uid=? AND is_active=1",
                    (uid,),
                ).fetchone()[0]
                if active_count > 1:
                    return jsonify({"success": False,
                                    "error": "Birden fazla aktif profil var. Tekil manuel inceleme gerekli."}), 409
            row = conn.execute(
                """SELECT rowid AS profile_rowid, source_asset_sha256, source_relative_path,
                          has_occlusion
                   FROM template_profiles
                   WHERE template_uid=? AND is_active=1""",
                (uid,),
            ).fetchone()
            if bulk_approval and row and bool(row["has_occlusion"]):
                return jsonify({"success": False,
                                "error": "Ön plan engeli olan şablon toplu onaylanamaz; tekil inceleyin."}), 409

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
                    if bulk_approval:
                        return jsonify({"success": False,
                                        "error": "Kaynak görsel değişmiş. Toplu onay reddedildi; dört köşeyi yeni fotoğrafta tek tek kontrol edin.",
                                        "code": "STALE_SOURCE_CHANGED"}), 409
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

            valid, reason = GeometryValidator.is_valid_quad(quad, w, h, manual=True)
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

            # Non-destructive re-approval: keep previous approved coordinates
            # in an append-only, transactional revision trail. Same profile row
            # becomes active immediately after the human clicks Approve.
            conn.execute("""CREATE TABLE IF NOT EXISTS approved_geometry_revisions (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                template_uid TEXT NOT NULL,
                profile_rowid INTEGER,
                source_sha256 TEXT NOT NULL,
                previous_quad TEXT,
                approved_quad TEXT NOT NULL,
                approved_at TEXT DEFAULT CURRENT_TIMESTAMP
            )""")
            old_quad = None
            if profile_id is not None:
                prior = conn.execute(
                    "SELECT surface_quad FROM template_profiles WHERE rowid=?", (profile_id,)
                ).fetchone()
                old_quad = prior[0] if prior else None
            conn.execute("""INSERT INTO approved_geometry_revisions
                (template_uid, profile_rowid, source_sha256, previous_quad, approved_quad)
                VALUES (?, ?, ?, ?, ?)""", (
                uid, profile_id, source_hash, old_quad,
                json.dumps(canonical.tolist()),
            ))
            # Printing-only rounded glass corners belong to the approved
            # template setting, not a global batch dropdown.
            radius_raw = req.get("glass_corner_radius", None)
            glass_radius = None
            if radius_raw is not None:
                try:
                    glass_radius = float(radius_raw)
                except (ValueError, TypeError):
                    return jsonify({"success": False, "error": "Cam köşe ayarı sayısal olmalı."}), 422
                if not math.isfinite(glass_radius) or not (0 <= glass_radius <= .04):
                    return jsonify({"success": False, "error": "Cam köşe ayarı %0–4 arasında olmalı."}), 422

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
                if glass_radius is not None:
                    legacy_data["glass_corner_radius"] = glass_radius
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


def _inspect_template_asset(path, deep=False):
    """Return read-only health facts for one image asset."""
    if not path or not os.path.isfile(path):
        return {
            "exists": False,
            "readable": False,
            "size_bytes": 0,
            "suspicious_flat": False,
        }

    try:
        size_bytes = int(os.path.getsize(path))
    except OSError:
        size_bytes = 0

    result = {
        "exists": True,
        "readable": size_bytes > 0,
        "size_bytes": size_bytes,
        "suspicious_flat": False,
    }
    if not deep or size_bytes <= 0:
        return result

    try:
        raw = np.fromfile(path, dtype=np.uint8)
        image = cv2.imdecode(raw, cv2.IMREAD_UNCHANGED)
    except Exception:
        image = None

    if image is None or image.size == 0:
        result["readable"] = False
        return result

    result["readable"] = True
    result["width"] = int(image.shape[1])
    result["height"] = int(image.shape[0])

    # Uniform black/white images can be legitimate products. Never call these
    # "broken" automatically; only flag them for human review.
    try:
        if image.ndim == 3 and image.shape[2] >= 3:
            sample = cv2.cvtColor(image[:, :, :3], cv2.COLOR_BGR2GRAY)
        elif image.ndim == 2:
            sample = image
        else:
            sample = image[..., 0]
        stddev = float(np.std(sample))
        mean_luma = float(np.mean(sample))
        result["stddev_luma"] = round(stddev, 3)
        result["mean_luma"] = round(mean_luma, 3)
        result["suspicious_flat"] = bool(stddev < 2.0)
    except Exception:
        result["suspicious_flat"] = False

    return result


def _template_asset_health_report(deep=False):
    """Inspect active DB records and template pools without mutating anything."""
    settings = get_all_ayarlar()
    categories = settings.get("kategoriler", {})
    working_root = os.path.abspath(
        os.path.join(BASE_DIR, "2_SABLON_HAVUZU")
    )
    backup_root = os.path.abspath(
        os.path.join(BASE_DIR, "2_SABLON_HAVUZU_ORIJINAL_YEDEK")
    )
    image_exts = {".png", ".jpg", ".jpeg", ".webp", ".avif"}

    templates_report = {}
    category_report = {}
    registered_stems = set()

    summary = {
        "total_records": 0,
        "ok": 0,
        "warning": 0,
        "critical": 0,
        "filesystem_only_working": 0,
        "filesystem_only_backup": 0,
    }

    for category, category_data in categories.items():
        templates = (
            category_data.get("sablonlar", {})
            if isinstance(category_data, dict)
            else {}
        )
        if not isinstance(templates, dict):
            templates = {}

        cat_items = {}
        cat_warning = 0
        cat_critical = 0

        for template_name in templates:
            summary["total_records"] += 1
            registered_stems.add((str(category), Path(template_name).stem))

            working_path = _find_image_asset(
                working_root,
                category,
                template_name,
            )
            backup_path = _find_image_asset(
                backup_root,
                category,
                template_name,
            )
            working = _inspect_template_asset(working_path, deep=deep)
            backup = _inspect_template_asset(backup_path, deep=deep)

            severity = "OK"
            code = "OK"
            label = "Dosyalar sağlam görünüyor"
            details = []

            if not working["exists"] and not backup["exists"]:
                severity = "CRITICAL"
                code = "WORKING_AND_BACKUP_MISSING"
                label = "Çalışma ve ham yedek eksik"
                details.append("Aktif çalışma görseli bulunamadı.")
                details.append("Ham/orijinal yedek de bulunamadı.")
            elif not working["exists"]:
                severity = "WARNING"
                code = "WORKING_MISSING"
                label = "Çalışma dosyası eksik"
                details.append(
                    "Aktif çalışma görseli yok; ham yedek mevcut."
                )
            elif not working["readable"]:
                severity = "CRITICAL"
                code = "WORKING_UNREADABLE"
                label = "Çalışma dosyası okunamıyor"
                details.append(
                    "Aktif çalışma dosyası var ancak görüntü olarak okunamıyor."
                )
            elif not backup["exists"]:
                severity = "WARNING"
                code = "BACKUP_MISSING"
                label = "Ham yedek eksik"
                details.append(
                    "Çalışma görseli mevcut; korunmuş ham/orijinal yedek yok."
                )
            elif not backup["readable"]:
                severity = "WARNING"
                code = "BACKUP_UNREADABLE"
                label = "Ham yedek okunamıyor"
                details.append(
                    "Ham/orijinal yedek var ancak görüntü olarak okunamıyor."
                )
            elif deep and (
                working.get("suspicious_flat")
                or backup.get("suspicious_flat")
            ):
                severity = "WARNING"
                code = "VISUAL_REVIEW_REQUIRED"
                label = "Gözle kontrol önerilir"
                details.append(
                    "Görüntü çok düşük varyasyonlu. Siyah/beyaz ürün olabilir; "
                    "otomatik bozuk sayılmadı ve hiçbir dosya silinmedi."
                )

            if severity == "CRITICAL":
                summary["critical"] += 1
                cat_critical += 1
            elif severity == "WARNING":
                summary["warning"] += 1
                cat_warning += 1
            else:
                summary["ok"] += 1

            cat_items[template_name] = {
                "severity": severity,
                "code": code,
                "label": label,
                "details": details,
                "working": working,
                "backup": backup,
                "can_restore_from_backup": bool(
                    backup["exists"] and backup["readable"]
                ),
                "orphan_record": bool(not working["exists"]),
            }

        templates_report[category] = cat_items
        category_report[category] = {
            "template_count": len(templates),
            "warning_count": cat_warning,
            "critical_count": cat_critical,
            "issue_count": cat_warning + cat_critical,
        }

    def _scan_filesystem_only(root):
        extras = []
        if not os.path.isdir(root):
            return extras
        for category_name in os.listdir(root):
            category_path = os.path.join(root, category_name)
            if not os.path.isdir(category_path):
                continue
            for filename in os.listdir(category_path):
                path = os.path.join(category_path, filename)
                if (
                    not os.path.isfile(path)
                    or Path(filename).suffix.lower() not in image_exts
                ):
                    continue
                key = (str(category_name), Path(filename).stem)
                if key not in registered_stems:
                    extras.append({
                        "category": category_name,
                        "filename": filename,
                    })
        return extras

    filesystem_only_working = _scan_filesystem_only(working_root)
    filesystem_only_backup = _scan_filesystem_only(backup_root)
    summary["filesystem_only_working"] = len(filesystem_only_working)
    summary["filesystem_only_backup"] = len(filesystem_only_backup)

    for item in filesystem_only_working:
        cat = item["category"]
        category_report.setdefault(cat, {
            "template_count": 0,
            "warning_count": 0,
            "critical_count": 0,
            "issue_count": 0,
        })
        category_report[cat]["warning_count"] += 1
        category_report[cat]["issue_count"] += 1

    for item in filesystem_only_backup:
        cat = item["category"]
        category_report.setdefault(cat, {
            "template_count": 0,
            "warning_count": 0,
            "critical_count": 0,
            "issue_count": 0,
        })
        category_report[cat]["warning_count"] += 1
        category_report[cat]["issue_count"] += 1

    return {
        "success": True,
        "deep": bool(deep),
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "summary": summary,
        "categories": category_report,
        "templates": templates_report,
        "filesystem_only_working": filesystem_only_working,
        "filesystem_only_backup": filesystem_only_backup,
        "read_only": True,
        "auto_deleted": 0,
    }


def _template_health_saved_report_path():
    report_dir = os.path.join(
        BASE_DIR,
        "SABLON_V2_MIMARI",
        "reports",
    )
    return os.path.join(
        report_dir,
        "son_ham_dosya_saglik_raporu.json",
    )


def _template_health_history_dir():
    return os.path.join(
        BASE_DIR,
        "SABLON_V2_MIMARI",
        "reports",
        "template_health_history",
    )


def _load_saved_template_health_report():
    target = _template_health_saved_report_path()
    if not os.path.isfile(target):
        return None

    with open(target, "r", encoding="utf-8") as handle:
        report = json.load(handle)

    if not isinstance(report, dict) or not report.get("success"):
        raise ValueError("Kaydedilmiş sağlık raporu bozuk veya geçersiz.")
    return report


def _template_health_issue_keys(report):
    keys = set()
    templates = (report or {}).get("templates", {})
    if not isinstance(templates, dict):
        return keys
    for category, category_items in templates.items():
        if not isinstance(category_items, dict):
            continue
        for template_name, item in category_items.items():
            if not isinstance(item, dict):
                continue
            severity = str(item.get("severity") or "OK").upper()
            if severity == "OK":
                continue
            keys.add(
                "|".join([
                    str(category).casefold(),
                    str(template_name).casefold(),
                    str(item.get("code") or severity),
                ])
            )
    return keys


def _save_template_health_report(report):
    """Persist full health report + immutable history + previous-scan diff."""
    if not isinstance(report, dict) or not report.get("success"):
        raise ValueError("Kaydedilecek sağlık raporu geçersiz.")

    previous = _load_saved_template_health_report()
    report_to_save = dict(report)
    report_to_save["saved_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    report_to_save["saved_report"] = True

    old_keys = _template_health_issue_keys(previous)
    new_keys = _template_health_issue_keys(report_to_save)
    report_to_save["diff"] = {
        "has_previous": previous is not None,
        "previous_saved_at": (
            previous.get("saved_at")
            if isinstance(previous, dict)
            else None
        ),
        "new_issue_count": len(new_keys - old_keys),
        "resolved_issue_count": len(old_keys - new_keys),
        "unchanged_issue_count": len(new_keys & old_keys),
    }

    target = _template_health_saved_report_path()
    history_dir = _template_health_history_dir()
    os.makedirs(os.path.dirname(target), exist_ok=True)
    os.makedirs(history_dir, exist_ok=True)

    stamp = time.strftime("%Y%m%d_%H%M%S")
    history_target = os.path.join(
        history_dir,
        f"{stamp}_{uuid.uuid4().hex[:8]}.json",
    )
    serialized = json.dumps(
        report_to_save,
        ensure_ascii=False,
        indent=2,
    ).encode("utf-8")

    for destination in (history_target, target):
        tmp_path = destination + "." + uuid.uuid4().hex + ".tmp"
        try:
            with open(tmp_path, "wb") as handle:
                handle.write(serialized)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_path, destination)
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    return report_to_save


def _template_health_history(limit=20):
    history_dir = _template_health_history_dir()
    if not os.path.isdir(history_dir):
        return []
    rows = []
    files = sorted(
        Path(history_dir).glob("*.json"),
        key=lambda path: path.name,
        reverse=True,
    )[:max(1, min(100, int(limit)))]
    for path in files:
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            summary = data.get("summary", {})
            rows.append({
                "file": path.name,
                "saved_at": data.get("saved_at"),
                "total_records": int(summary.get("total_records", 0)),
                "ok": int(summary.get("ok", 0)),
                "warning": int(summary.get("warning", 0)),
                "critical": int(summary.get("critical", 0)),
                "diff": data.get("diff", {}),
            })
        except (OSError, ValueError, json.JSONDecodeError):
            continue
    return rows


def _job_batch_corner_scan(
    job_id,
    payload,
    progress,
    should_stop,
):
    category = str(payload.get("category") or "").strip()
    templates = [
        str(name)
        for name in (payload.get("templates") or [])
        if str(name or "").strip()
    ]
    if not category or not templates:
        raise ValueError("Kalıcı kategori taraması için kategori/şablon listesi gerekli.")

    state = get_job(job_id) or {}
    start_index = max(
        0,
        min(
            len(templates),
            int(state.get("progress_current") or 0),
        ),
    )
    chunk_size = 4
    counts = {
        "analyzed_count": 0,
        "cache_hit_count": 0,
        "approved_preserved_count": 0,
        "missing_count": 0,
        "busy_count": 0,
        "source_changed_count": 0,
        "failed_count": 0,
    }

    index = start_index
    while index < len(templates):
        if should_stop():
            return {
                "completed": False,
                "processed": index,
                "total": len(templates),
                **counts,
            }

        chunk = templates[index:index + chunk_size]
        progress(
            index,
            len(templates),
            "Tam kalite motoru: " + ", ".join(chunk),
        )
        result = _run_batch_analysis_core(
            category,
            chunk,
            workers=2,
        )
        for key in counts:
            counts[key] += int(result.get(key, 0) or 0)

        index += len(chunk)
        progress(
            index,
            len(templates),
            (
                f"{index}/{len(templates)} tamamlandı • "
                f"cache {counts['cache_hit_count']} • "
                f"onaylı korundu {counts['approved_preserved_count']}"
            ),
        )

    return {
        "completed": True,
        "processed": len(templates),
        "total": len(templates),
        "category": category,
        "quality_algorithm": "UNCHANGED",
        "db_writes": "SEQUENTIAL",
        "cache": cache_stats(),
        **counts,
    }


def _job_raw_health_scan(
    job_id,
    payload,
    progress,
    should_stop,
):
    if should_stop():
        return {
            "completed": False,
            "processed": 0,
            "total": 1,
        }
    progress(0, 1, "Ham ve çalışma dosyaları kontrol ediliyor...")
    report = _template_asset_health_report(deep=True)
    saved = _save_template_health_report(report)
    progress(1, 1, "Sağlık taraması tamamlandı ve son rapor kaydedildi.")
    return {
        "completed": True,
        "processed": 1,
        "total": 1,
        "saved_at": saved.get("saved_at"),
        "summary": saved.get("summary", {}),
    }



def _job_workspace_consistency_scan(
    job_id,
    payload,
    progress,
    should_stop,
):
    settings = get_all_ayarlar()
    report = workspace_consistency_report(
        BASE_DIR,
        SOURCE_ROOT,
        settings,
        progress=progress,
        should_stop=should_stop,
    )
    if report.get("cancelled") or should_stop():
        return {
            "completed": False,
            "processed": 0,
            "total": 8,
            "read_only": True,
        }
    saved = save_workspace_report(BASE_DIR, report)
    progress(
        8,
        8,
        "Tutarlılık raporu kaydedildi. Hiçbir kullanıcı dosyası değiştirilmedi.",
    )
    return {
        "completed": True,
        "processed": 8,
        "total": 8,
        "read_only": True,
        "assets_mutated": False,
        "saved_at": saved.get("saved_at"),
        "summary": saved.get("summary", {}),
        "diff": saved.get("diff", {}),
    }


@app.route('/api/jobs', methods=['GET', 'POST'])
def api_jobs():
    if request.method == 'GET':
        active_only = str(
            request.args.get("active", "0")
        ).strip().lower() in {"1", "true", "yes", "on"}
        return jsonify({
            "success": True,
            "jobs": list_jobs(
                limit=request.args.get("limit", 20),
                active_only=active_only,
            ),
        })

    req = request.get_json(silent=True) or {}
    job_type = str(req.get("job_type") or "").strip().upper()
    payload = req.get("payload") or {}
    if not isinstance(payload, dict):
        return jsonify({
            "success": False,
            "error": "Job payload nesne olmalı.",
        }), 400

    if job_type == "BATCH_CORNER_SCAN":
        category = str(payload.get("category") or "").strip()
        settings = get_all_ayarlar()
        registered = (
            settings.get("kategoriler", {})
            .get(category, {})
            .get("sablonlar", {})
        )
        if not category or not isinstance(registered, dict):
            return jsonify({
                "success": False,
                "error": "Geçerli kategori bulunamadı.",
            }), 400
        requested = payload.get("templates")
        if isinstance(requested, list):
            templates = [
                str(name)
                for name in requested
                if str(name) in registered
            ]
        else:
            templates = list(registered.keys())
        if not templates:
            return jsonify({
                "success": False,
                "error": "Kategoride taranacak şablon yok.",
            }), 400
        payload = {
            "category": category,
            "templates": templates,
        }
        total = len(templates)
    elif job_type == "RAW_HEALTH_SCAN":
        payload = {"deep": True, "save": True}
        total = 1
    elif job_type == "WORKSPACE_CONSISTENCY_SCAN":
        payload = {"read_only": True}
        total = 8
    else:
        return jsonify({
            "success": False,
            "error": "Desteklenmeyen job type.",
        }), 400

    # Avoid accidental duplicate long-running jobs of the same intent.
    for active in list_jobs(limit=100, active_only=True):
        if (
            active.get("job_type") == job_type
            and active.get("payload") == payload
        ):
            return jsonify({
                "success": True,
                "job": active,
                "reused_active_job": True,
            })

    job_id = create_job(
        job_type,
        payload,
        progress_total=total,
    )
    return jsonify({
        "success": True,
        "job": get_job(job_id),
        "reused_active_job": False,
    }), 202


@app.route('/api/jobs/<job_id>')
def api_job_detail(job_id):
    job = get_job(job_id)
    if job is None:
        return jsonify({
            "success": False,
            "error": "Job bulunamadı.",
        }), 404
    return jsonify({
        "success": True,
        "job": job,
    })


@app.route('/api/jobs/<job_id>/stop', methods=['POST'])
def api_job_stop(job_id):
    if not request_job_stop(job_id):
        job = get_job(job_id)
        if job is None:
            return jsonify({
                "success": False,
                "error": "Job bulunamadı.",
            }), 404
        return jsonify({
            "success": False,
            "error": "Job zaten tamamlanmış.",
            "job": job,
        }), 409
    return jsonify({
        "success": True,
        "job": get_job(job_id),
    })


@app.route('/api/analysis-cache/stats')
def api_analysis_cache_stats():
    return jsonify({
        "success": True,
        **cache_stats(),
        "analyzer_version": TemplateAnalyzer().version,
    })


@app.route('/api/template-health')
def api_template_health():
    """Read-only template/raw asset health scan for cleanup review."""
    try:
        deep = str(request.args.get("deep", "0")).strip().lower() in {
            "1", "true", "yes", "on"
        }
        persist = str(request.args.get("save", "0")).strip().lower() in {
            "1", "true", "yes", "on"
        }

        report = _template_asset_health_report(deep=deep)
        if persist:
            if not deep:
                return jsonify({
                    "success": False,
                    "error": (
                        "Kalıcı son rapor yalnız tam (deep) sağlık "
                        "taramasından kaydedilebilir."
                    ),
                    "code": "DEEP_SCAN_REQUIRED_FOR_SAVE",
                }), 400
            report = _save_template_health_report(report)

        return jsonify(report)
    except Exception as exc:
        logger.exception("Sablon dosya saglik taramasi basarisiz")
        return jsonify({
            "success": False,
            "error": str(exc),
        }), 500


@app.route('/api/template-health/last')
def api_template_health_last():
    """Return the last explicitly saved full health report."""
    try:
        report = _load_saved_template_health_report()
        if report is None:
            return jsonify({
                "success": False,
                "error": "Henüz kaydedilmiş bir Ham Dosya Sağlık Raporu yok.",
                "code": "NO_SAVED_HEALTH_REPORT",
            }), 404
        return jsonify(report)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        logger.exception("Kaydedilmiş sağlık raporu okunamadı")
        return jsonify({
            "success": False,
            "error": str(exc),
            "code": "SAVED_HEALTH_REPORT_INVALID",
        }), 422


@app.route('/api/template-health/history')
def api_template_health_history():
    try:
        limit = int(request.args.get("limit", 20) or 20)
        return jsonify({
            "success": True,
            "history": _template_health_history(limit),
        })
    except Exception as exc:
        return jsonify({
            "success": False,
            "error": str(exc),
        }), 500


@app.route('/api/workspace-consistency/last')
def api_workspace_consistency_last():
    try:
        report = load_latest_workspace_report(BASE_DIR)
        if report is None:
            return jsonify({
                "success": False,
                "error": "Henüz kaydedilmiş Klasör Tutarlılık Raporu yok.",
                "code": "NO_SAVED_WORKSPACE_REPORT",
            }), 404
        return jsonify(report)
    except Exception as exc:
        logger.exception("Klasör tutarlılık raporu okunamadı")
        return jsonify({
            "success": False,
            "error": str(exc),
        }), 500


@app.route('/api/workspace-consistency/history')
def api_workspace_consistency_history():
    try:
        limit = int(request.args.get("limit", 20) or 20)
        return jsonify({
            "success": True,
            "history": workspace_report_history(
                BASE_DIR,
                limit=limit,
            ),
        })
    except Exception as exc:
        return jsonify({
            "success": False,
            "error": str(exc),
        }), 500


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
            "doctor_guidance": doctor_guidance(report),
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

    job_engine = PersistentJobEngine(
        {
            "BATCH_CORNER_SCAN": _job_batch_corner_scan,
            "RAW_HEALTH_SCAN": _job_raw_health_scan,
            "WORKSPACE_CONSISTENCY_SCAN": _job_workspace_consistency_scan,
        },
        max_workers=2,
    )
    job_engine.start()
    print("Kalıcı Job Engine aktif: 2 worker, restart-resume açık.")

    try:
        bind_port = int(os.environ.get("MOCKUP_PORT", "8080"))
    except ValueError:
        bind_port = 8080
    if not 1024 <= bind_port <= 65535:
        bind_port = 8080
    bind_url = f"http://127.0.0.1:{bind_port}"
    print(f"SABLON_V2_MIMARI (Flask MVC) Baslatiliyor... {bind_url}")
    auto_browser_disabled = str(
        os.environ.get("MOCKUP_NO_AUTO_BROWSER", "")
    ).strip().lower() in {"1", "true", "yes", "on"}
    if not auto_browser_disabled:
        threading.Timer(
            1.25,
            lambda: webbrowser.open(bind_url + "/"),
        ).start()
    debug_enabled = str(os.environ.get("MOCKUP_FLASK_DEBUG", "")).strip().lower() in {"1", "true", "yes", "on"}
    app.run(host='127.0.0.1', port=bind_port, debug=debug_enabled, use_reloader=False)
