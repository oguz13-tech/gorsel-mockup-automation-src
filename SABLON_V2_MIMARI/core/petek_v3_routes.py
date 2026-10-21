# -*- coding: utf-8 -*-
"""PETEK V3 UI routes embedded in the existing Template Review Center.

Read-only legacy geometry lookup; mask drafts are stored separately. Browser
painting never mutates source, approvals or the original template database.
"""
from __future__ import annotations

import io
import json
import logging
import secrets
import sqlite3
import threading
import dataclasses
from pathlib import Path

import cv2
import numpy as np
from flask import Blueprint, jsonify, render_template, request, send_file

from .petek_mask_store import PetekProfileStore, safe_uid, private_root
from .petek_surface_v3 import (
    CATEGORY, PetekSafetyError, quad_mask, read_image, require_safe_file,
    sha256_file, validate_quad,
)

LOG = logging.getLogger("petek.routes")
MUTATION_TOKEN = secrets.token_urlsafe(32)
ALLOWED_EXTENSIONS = frozenset({".png", ".jpeg", ".jpg", ".webp", ".bmp"})
MAX_UPLOAD_BYTES = 35 * 1024 * 1024


def register_petek_v3(app, runtime_root: Path) -> None:
    """Add the dedicated PETEK tab and guarded review APIs to the existing Flask app."""
    root = Path(runtime_root).resolve()
    template_root = root / "2_SABLON_HAVUZU"
    blueprint = Blueprint("petek_v3", __name__, url_prefix="/petek-v3")

    def ensure_local():
        """Forbid mutating private profile data from remote/browser origins."""
        addr = str(request.remote_addr or "")
        if addr not in ("127.0.0.1", "::1"):
            raise PetekSafetyError("LOCALHOST_ONLY")
        host = str(request.host or "").split(":")[0].lower()
        if host not in ("127.0.0.1", "localhost", "[::1]"):
            raise PetekSafetyError("HOST_NOT_LOCAL")

    def authorize():
        """Require CSRF token in addition to localhost origin for every write."""
        ensure_local()
        if not secrets.compare_digest(
            request.headers.get("X-Petek-Token", ""), MUTATION_TOKEN
        ):
            raise PetekSafetyError("PETEK_CSRF_TOKEN_REQUIRED")

    def store():
        """Create the isolated profile DB only when PETEK feature is requested."""
        return PetekProfileStore(root, template_root)

    def source(name: str) -> Path:
        """Resolve a named file in the PETEK category without directory traversal."""
        name = str(name or "")
        if Path(name).name != name or Path(name).suffix.lower() not in ALLOWED_EXTENSIONS:
            raise PetekSafetyError("INVALID_PETEK_TEMPLATE_NAME")
        return require_safe_file(template_root / CATEGORY / name,
                                 template_root / CATEGORY)

    def parse_body():
        """Validate JSON payload size and object shape before mutation."""
        if request.content_length is not None and request.content_length > MAX_UPLOAD_BYTES:
            raise PetekSafetyError("REQUEST_TOO_LARGE")
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            raise PetekSafetyError("JSON_OBJECT_REQUIRED")
        return data

    def legacy_reviewed_quad(image_name: str):
        """Read but never edit source-version-approved legacy geometry."""
        db_path = root / "SABLON_V2_MIMARI" / "ayarlar.db"
        if not db_path.is_file() or db_path.is_symlink():
            return None
        template = source(image_name)
        digest = sha256_file(template)
        try:
            conn = sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro",
                                   uri=True, timeout=5)
            conn.row_factory = sqlite3.Row
            try:
                conn.execute("PRAGMA query_only=ON")
                records = conn.execute(
                    """SELECT source_relative_path,surface_quad
                       FROM template_profiles
                       WHERE category=? AND source_asset_sha256=?
                       AND review_status='APPROVED' AND manually_verified=1
                       AND is_active=1""", (CATEGORY, digest)).fetchall()
            finally:
                conn.close()
            matching = [
                row for row in records
                if Path(str(row["source_relative_path"]).replace("\\", "/")).name == image_name
            ]
            if len(matching) != 1:
                return None
            image = read_image(template)
            pts = validate_quad(json.loads(matching[0]["surface_quad"]),
                                image.shape[1], image.shape[0])
            return pts.astype(float).tolist()
        except (OSError, sqlite3.Error, ValueError, TypeError) as exc:
            LOG.warning("Legacy read-only quad lookup: %s", type(exc).__name__)
            return None

    @blueprint.app_errorhandler(PetekSafetyError)
    def on_rejected(exc):
        """Return structured errors without Flask 500 or private path leakage."""
        LOG.warning("PETEK rejected: %s", exc)
        return jsonify({"ok":False, "error":str(exc)}), 422

    @blueprint.app_errorhandler(Exception)
    def on_unexpected(exc):
        """Log unexpected errors, avoid reporting success on partial writes."""
        LOG.exception("PETEK unexpected error: %s", type(exc).__name__)
        return jsonify({"ok":False, "error":"PETEK_INTERNAL_ERROR"}), 500

    @blueprint.get("/")
    def home():
        """Render the PETEK review tab inside the existing main application."""
        ensure_local()
        return render_template("petek_v3.html", csrf_token=MUTATION_TOKEN)

    @blueprint.get("/api/templates")
    def templates():
        """List only PETEK source images; never return another category."""
        ensure_local()
        folder = template_root / CATEGORY
        names = sorted((p.name for p in folder.iterdir()
                        if p.is_file() and not p.is_symlink()
                        and p.suffix.lower() in ALLOWED_EXTENSIONS), key=str.lower) if folder.is_dir() else []
        return jsonify({"ok":True,"category":CATEGORY,"templates":names,
                        "profiles":store().status()})

    @blueprint.get("/api/original/<name>")
    def original(name):
        """Stream a template unchanged for human visual review."""
        ensure_local()
        path = source(name)
        return send_file(path, conditional=True)

    @blueprint.get("/api/legacy-quad/<name>")
    def legacy_quad(name):
        """Read previously reviewed corners when still bound to same source bytes."""
        ensure_local()
        return jsonify({"ok":True,"quad":legacy_reviewed_quad(name)})

    @blueprint.post("/api/draft")
    def draft():
        """Build a mask candidate only; never promote it to production."""
        authorize()
        data = parse_body()
        path = source(str(data.get("name") or ""))
        uid = safe_uid(str(data.get("uid") or path.stem))
        scene = read_image(path)
        shape = scene.shape[:2]
        quad = validate_quad(data.get("quad"), shape[1], shape[0])
        old_quad = legacy_reviewed_quad(path.name)
        if old_quad is not None and not np.allclose(
            np.asarray(old_quad), quad, atol=1.5):
            raise PetekSafetyError("QUAD_DIFFERS_FROM_EXISTING_HUMAN_APPROVAL")
        profile = store().create_draft(
            uid,path,quad,float(data.get("physical_aspect")))
        return jsonify({"ok":True,"profile":profile})

    @blueprint.get("/api/mask/<name>")
    def mask(name):
        """Stream immutable stored mask, including drafts, for browser editing."""
        ensure_local()
        src = source(name)
        uid = safe_uid(request.args.get("uid", src.stem))
        profile, pixels = store().find(uid, src, approved_only=False)
        ok, encoded = cv2.imencode(".png", pixels)
        if not ok:
            raise PetekSafetyError("MASK_PREVIEW_ENCODE_FAILED")
        response = send_file(io.BytesIO(encoded.tobytes()), mimetype="image/png",
                             download_name="printable_mask.png")
        response.headers["X-Petek-Review"] = profile["review_status"]
        response.headers["Cache-Control"] = "no-store"
        return response

    @blueprint.post("/api/mask/<name>")
    def save_mask(name):
        """Store user-painted grayscale mask as another immutable DRAFT digest."""
        authorize()
        src = source(name)
        uid = safe_uid(request.form.get("uid", src.stem))
        uploaded = request.files.get("mask")
        if uploaded is None:
            raise PetekSafetyError("MASK_UPLOAD_REQUIRED")
        binary = uploaded.read(MAX_UPLOAD_BYTES + 1)
        if len(binary) > MAX_UPLOAD_BYTES:
            raise PetekSafetyError("MASK_UPLOAD_TOO_LARGE")
        decoded = cv2.imdecode(np.frombuffer(binary,dtype=np.uint8),
                               cv2.IMREAD_GRAYSCALE)
        if decoded is None:
            raise PetekSafetyError("MASK_UPLOAD_DECODE_FAILED")
        profile = store().replace_draft_mask(uid, src, decoded)
        return jsonify({"ok":True,"profile":profile})

    @blueprint.post("/api/approve/<name>")
    def approve(name):
        """Require explicit reviewer and checkbox confirmation of mask."""
        authorize()
        body = parse_body()
        src = source(name)
        uid = safe_uid(str(body.get("uid") or src.stem))
        profile = store().approve(uid, src, str(body.get("reviewer") or ""),
                                  str(body.get("confirmation") or ""))
        return jsonify({"ok":True,"status":profile["review_status"],
                        "source_sha256":profile["source_sha256"]})


    batch_guard = threading.RLock()
    batch_context = {"worker":None,"runner":None,"result":None,"error":None}

    @blueprint.get("/api/design-folders")
    def design_folders():
        """List local incoming folders without exposing arbitrary disk browsing."""
        ensure_local()
        incoming = root / "1_GELEN_KAGGLE_BASKILARI"
        folders = ["."]
        if incoming.is_dir():
            folders.extend(sorted((f.name for f in incoming.iterdir()
                                   if f.is_dir() and not f.is_symlink()),
                                  key=str.casefold))
        return jsonify({"ok":True,"folders":folders})

    @blueprint.get("/api/batch/status")
    def batch_status():
        """Expose live in-process job counters and previous terminal result."""
        ensure_local()
        with batch_guard:
            worker = batch_context["worker"]
            runner = batch_context["runner"]
            return jsonify({"ok":True,"running":bool(worker and worker.is_alive()),
                            "progress":runner.status() if runner else {},
                            "result":batch_context["result"],
                            "error":batch_context["error"]})

    @blueprint.post("/api/batch/start")
    def batch_start():
        """Start a single approved-mask local production worker, no cloud."""
        authorize()
        payload = parse_body()
        relative = str(payload.get("folder") or ".")
        if relative not in (".","") and (
            "/" in relative or "\\" in relative or relative in (".","..")
        ):
            raise PetekSafetyError("DESIGN_FOLDER_MUST_BE_SELECTED_CHILD")
        filenames=payload.get("templates")
        if not isinstance(filenames,list) or not filenames or len(filenames)>500:
            raise PetekSafetyError("SELECT_APPROVED_TEMPLATES")
        from .petek_serial_factory import PetekBatchRunner
        with batch_guard:
            worker=batch_context["worker"]
            if worker and worker.is_alive():
                return jsonify({"ok":False,"error":"PETEK_BATCH_ALREADY_RUNNING"}),409
            runner=PetekBatchRunner(root)
            batch_context.update({"runner":runner,"error":None,"result":None})
            folder=root/"1_GELEN_KAGGLE_BASKILARI"/relative
            group=str(payload.get("store_group") or "MAIN")
            try:
                limit=int(payload.get("max_items") or 1000)
            except (ValueError,TypeError) as exc:
                raise PetekSafetyError("MAX_ITEMS_MUST_BE_INTEGER") from exc
            def task():
                """Persist state in private ledger; failures never imply success."""
                try:
                    report=runner.run(folder,filenames,store_group=group,max_items=limit)
                    with batch_guard:
                        batch_context["result"]=dataclasses.asdict(report)
                except Exception as exc:
                    LOG.exception("PETEK local batch failed")
                    with batch_guard:
                        batch_context["error"]=str(exc)
            worker=threading.Thread(target=task,name="petek-v3-local-batch",daemon=True)
            batch_context["worker"]=worker
            worker.start()
        return jsonify({"ok":True,"status":"STARTED_LOCAL_ONLY"})

    @blueprint.post("/api/batch/stop")
    def batch_stop():
        """Request safe stop after active artifact finishes publishing."""
        authorize()
        with batch_guard:
            runner=batch_context["runner"]
            if runner:
                runner.stop()
        return jsonify({"ok":True,"status":"STOP_REQUESTED"})

    @blueprint.get("/api/batch/download/<name>")
    def batch_download(name):
        """Download only generated private PETEK CSV/XLSX exports."""
        ensure_local()
        if Path(name).name!=name or Path(name).suffix.lower() not in (".csv",".xlsx"):
            raise PetekSafetyError("INVALID_EXPORT_NAME")
        from .petek_surface_v3 import require_safe_file
        location = private_root(root) / "exports"
        file = require_safe_file(location / name, location)
        return send_file(file, as_attachment=True, download_name=name)

    app.register_blueprint(blueprint)
