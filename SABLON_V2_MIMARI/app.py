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

        img_cv = cv2.imdecode(
            np.fromfile(img_path, dtype=np.uint8),
            cv2.IMREAD_COLOR,
        )
        if img_cv is None:
            return jsonify({"success": False, "error": "Resim okunamadi"}), 500

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