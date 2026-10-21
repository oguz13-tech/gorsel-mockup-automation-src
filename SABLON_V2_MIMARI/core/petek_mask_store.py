# -*- coding: utf-8 -*-
"""PETEK V3 approved mask registry isolated from legacy template SQLite.

All mask data resides in a separate PETEK_V3_PRIVATE directory; the legacy
ayarlar.db, ayarlar.json, approved corners and original archives are never
modified. Drafts cannot render. Approval is explicitly human-triggered.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
import tempfile
from pathlib import Path

import cv2
import numpy as np

from .petek_surface_v3 import (
    CATEGORY, RECIPE, PetekSafetyError, candidate_print_mask,
    quad_mask, read_image, require_safe_file, sha256_file,
    validate_print_mask, validate_quad, render_approved,
)

LOG = logging.getLogger("petek.registry")


def private_root(runtime_root: Path) -> Path:
    """Keep PETEK writes in a dedicated directory, outside protected assets."""
    root = Path(runtime_root).resolve()
    return root / "PETEK_V3_PRIVATE"


def safe_uid(raw: str) -> str:
    """Allow stable template identity without any path traversal."""
    name = str(raw or "").strip()
    if not (1 <= len(name) <= 100) or not all(
        ch.isascii() and (ch.isalnum() or ch in "-_") for ch in name
    ):
        raise PetekSafetyError("INVALID_TEMPLATE_UID")
    return name


def encode_mask(mask: np.ndarray) -> bytes:
    """Encode an immutable full-scene grayscale mask with PNG losslessness."""
    if mask.ndim != 2 or mask.dtype != np.uint8:
        raise PetekSafetyError("INVALID_PRINT_MASK")
    ok, encoded = cv2.imencode(".png", mask, [cv2.IMWRITE_PNG_COMPRESSION, 3])
    if not ok:
        raise PetekSafetyError("MASK_ENCODE_FAILED")
    return encoded.tobytes()


def immutable_write(path: Path, content: bytes) -> None:
    """Create a file atomically, never replace another file or follow symlinks."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.parent.is_symlink():
        raise PetekSafetyError("UNSAFE_MASK_DIRECTORY")
    if path.is_symlink():
        raise PetekSafetyError("UNSAFE_MASK_SYMLINK")
    if path.exists():
        if path.read_bytes() != content:
            raise PetekSafetyError("IMMUTABLE_MASK_COLLISION")
        return
    fd, temporary = tempfile.mkstemp(prefix=".mask-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            if path.read_bytes() != content:
                raise PetekSafetyError("IMMUTABLE_MASK_COLLISION")
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class PetekProfileStore:
    """Durable draft/review/approved profiles independent of legacy databases."""

    def __init__(self, runtime_root: Path, template_root: Path):
        """Create only the private PETEK store; template source is read-only."""
        self.template_root = Path(template_root).resolve(strict=True)
        if not self.template_root.is_dir():
            raise PetekSafetyError("TEMPLATE_ROOT_MISSING")
        self.root = private_root(runtime_root)
        if self.root.is_symlink():
            raise PetekSafetyError("UNSAFE_PRIVATE_ROOT")
        self.root.mkdir(parents=True, exist_ok=True)
        self.mask_root = self.root / "masks"
        self.mask_root.mkdir(exist_ok=True)
        self.db_path = self.root / "petek_v3_profiles.sqlite3"
        if self.db_path.is_symlink():
            raise PetekSafetyError("UNSAFE_PROFILE_DATABASE")
        self._bootstrap()

    def _connect(self) -> sqlite3.Connection:
        """Open a transactional, bounded-time SQLite connection."""
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _bootstrap(self) -> None:
        """Create private tables with source version and audit invariants."""
        with self._connect() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS masks (
                template_uid TEXT NOT NULL,
                source_sha256 TEXT NOT NULL,
                mask_sha256 TEXT NOT NULL,
                category TEXT NOT NULL,
                profile_json TEXT NOT NULL,
                status TEXT NOT NULL,
                reviewer TEXT NOT NULL DEFAULT '',
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (template_uid, source_sha256)
            )""")
            conn.execute("""CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                template_uid TEXT NOT NULL,
                source_sha256 TEXT NOT NULL,
                event TEXT NOT NULL,
                event_sha256 TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )""")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_masks_status ON masks(status)")

    def _source(self, source: Path) -> tuple[Path, np.ndarray, str]:
        """Verify exact source file belongs to a safe runtime template folder."""
        source = require_safe_file(source, self.template_root)
        expected = self.template_root / CATEGORY
        if source.parent.resolve() != expected.resolve():
            raise PetekSafetyError("TEMPLATE_NOT_IN_PETEK_CATEGORY")
        scene = read_image(source)
        return source, scene, sha256_file(source)

    def _write_mask(self, mask: np.ndarray) -> tuple[str, str]:
        """Content-address masks for reuse without overwriting approved bytes."""
        digest = hashlib.sha256(mask.tobytes()).hexdigest()
        filename = f"{digest}.png"
        immutable_write(self.mask_root / filename, encode_mask(mask))
        return digest, filename

    def _audit(self, conn: sqlite3.Connection, uid: str,
               source_sha: str, event: str, profile: dict) -> None:
        """Append event receipt for every source-version profile transition."""
        receipt = hashlib.sha256(
            json.dumps(profile, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        conn.execute("INSERT INTO events(template_uid,source_sha256,event,event_sha256)"
                     " VALUES(?,?,?,?)", (uid, source_sha, event, receipt))

    def create_draft(self, template_uid: str, source: Path,
                     quad: object, physical_aspect: float) -> dict:
        """Analyze a new template once and store candidate WITHOUT approving it."""
        uid = safe_uid(template_uid)
        source, scene, source_sha = self._source(source)
        h, w = scene.shape[:2]
        points = validate_quad(quad, w, h)
        if not np.isfinite(physical_aspect) or not 0.1 < physical_aspect < 12:
            raise PetekSafetyError("INVALID_PHYSICAL_ASPECT")
        mask, analysis = candidate_print_mask(scene, points)
        mask_sha, mask_name = self._write_mask(mask)
        profile = {
            "category": CATEGORY, "recipe": RECIPE, "template_uid": uid,
            "source_sha256": source_sha,
            "source_dimensions": [w, h],
            "front_quad": points.astype(float).tolist(),
            "physical_aspect": float(physical_aspect),
            "mask_sha256": mask_sha,
            "mask_filename": mask_name,
            "review_status": "DRAFT",
            "analysis": analysis,
        }
        payload = json.dumps(profile, sort_keys=True, ensure_ascii=False)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT status FROM masks WHERE template_uid=? AND source_sha256=?",
                (uid, source_sha)).fetchone()
            if row and row["status"] == "APPROVED":
                raise PetekSafetyError("ALREADY_APPROVED_IMMUTABLE")
            conn.execute("""INSERT INTO masks (
                  template_uid,source_sha256,mask_sha256,category,profile_json,status
                ) VALUES(?,?,?,?,?,'DRAFT')
                ON CONFLICT(template_uid,source_sha256)
                DO UPDATE SET mask_sha256=excluded.mask_sha256,
                  profile_json=excluded.profile_json,status='DRAFT',
                  reviewer='',updated_at=CURRENT_TIMESTAMP""",
                  (uid, source_sha, mask_sha, CATEGORY, payload))
            self._audit(conn, uid, source_sha, "DRAFT", profile)
        return profile

    def replace_draft_mask(self, template_uid: str, source: Path,
                           reviewed_mask: np.ndarray) -> dict:
        """Accept explicitly edited mask; review status remains DRAFT."""
        uid = safe_uid(template_uid)
        _, scene, source_sha = self._source(source)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM masks WHERE template_uid=? AND source_sha256=?",
                (uid,source_sha)).fetchone()
            if row is None or row["status"] != "DRAFT":
                raise PetekSafetyError("DRAFT_REQUIRED_FOR_MASK_EDITS")
            profile = json.loads(row["profile_json"])
            quad = validate_quad(profile["front_quad"], scene.shape[1], scene.shape[0])
            details = validate_print_mask(reviewed_mask, scene.shape[:2], quad)
            mask_sha, mask_name = self._write_mask(reviewed_mask)
            profile.update({"mask_sha256":mask_sha,"mask_filename":mask_name,
                            "analysis":{"review_status":"DRAFT","validation":details}})
            conn.execute("""UPDATE masks SET profile_json=?,mask_sha256=?,
              updated_at=CURRENT_TIMESTAMP WHERE template_uid=? AND source_sha256=?""",
              (json.dumps(profile,sort_keys=True,ensure_ascii=False),
               mask_sha,uid,source_sha))
            self._audit(conn,uid,source_sha,"MASK_EDIT",profile)
            return profile

    def approve(self, template_uid: str, source: Path, reviewer: str,
                confirmation: str) -> dict:
        """Human-only explicit approval after exact-source mask inspection."""
        if confirmation != "I_REVIEWED_PETEK_MASK":
            raise PetekSafetyError("HUMAN_REVIEW_CONFIRMATION_REQUIRED")
        reviewer = str(reviewer or "").strip()
        if not 2 <= len(reviewer) <= 80:
            raise PetekSafetyError("REVIEWER_NAME_REQUIRED")
        uid = safe_uid(template_uid)
        _, scene, source_sha = self._source(source)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM masks WHERE template_uid=? AND source_sha256=?",
                (uid,source_sha)).fetchone()
            if row is None or row["status"] != "DRAFT":
                raise PetekSafetyError("DRAFT_REVIEW_REQUIRED")
            profile = json.loads(row["profile_json"])
            mask = self._read_mask(profile, scene.shape[:2])
            quad = validate_quad(profile["front_quad"], scene.shape[1], scene.shape[0])
            profile["analysis"]["validation"] = validate_print_mask(mask, scene.shape[:2], quad)
            profile["review_status"] = "APPROVED"
            profile["reviewer"] = reviewer
            conn.execute("""UPDATE masks SET profile_json=?, status='APPROVED',
                reviewer=?, updated_at=CURRENT_TIMESTAMP
                WHERE template_uid=? AND source_sha256=?""",
                (json.dumps(profile,sort_keys=True,ensure_ascii=False),reviewer,uid,source_sha))
            self._audit(conn,uid,source_sha,"APPROVED",profile)
        LOG.info("Human reviewed PETEK mask %s @ %s", uid, source_sha)
        return profile

    def _read_mask(self, profile: dict, expected: tuple[int,int]) -> np.ndarray:
        """Load mask from digest path; reject modified or redirected files."""
        name = str(profile.get("mask_filename",""))
        expected_name = str(profile.get("mask_sha256","")) + ".png"
        if name != expected_name or len(name) != 68:
            raise PetekSafetyError("MASK_FILENAME_TAMPERED")
        mask_path = require_safe_file(self.mask_root / name, self.mask_root)
        mask = read_image(mask_path, cv2.IMREAD_GRAYSCALE)
        if mask.shape != expected:
            raise PetekSafetyError("MASK_DIMENSIONS_CHANGED")
        if hashlib.sha256(mask.tobytes()).hexdigest() != profile["mask_sha256"]:
            raise PetekSafetyError("MASK_CONTENT_CHANGED")
        return mask

    def find(self, template_uid: str, source: Path,
             approved_only: bool = True) -> tuple[dict, np.ndarray]:
        """Return source-hash-bound approval and exact immutable mask bytes."""
        uid = safe_uid(template_uid)
        _, scene, source_sha = self._source(source)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM masks WHERE template_uid=? AND source_sha256=?",
                (uid,source_sha)).fetchone()
        if row is None:
            raise PetekSafetyError("TEMPLATE_PROFILE_NOT_FOUND")
        if approved_only and row["status"] != "APPROVED":
            raise PetekSafetyError("MASK_NOT_REVIEWED")
        profile = json.loads(row["profile_json"])
        if profile.get("source_sha256") != source_sha or profile.get("category") != CATEGORY:
            raise PetekSafetyError("PROFILE_SOURCE_IDENTITY_MISMATCH")
        if profile.get("review_status") != row["status"]:
            raise PetekSafetyError("PROFILE_DB_STATUS_MISMATCH")
        mask = self._read_mask(profile, scene.shape[:2])
        return profile, mask

    def render(self, template_uid: str, source: Path,
               artwork: Path, destination: Path, marketplace: bool = True) -> dict:
        """Render only approved masks; no remote upload, legacy DB writes or merge."""
        profile, mask = self.find(template_uid, source, approved_only=True)
        return render_approved(artwork, source, profile, mask, destination, marketplace)

    def status(self) -> list[dict]:
        """List currently recorded source-version profiles without image assets."""
        with self._connect() as conn:
            rows = conn.execute("""SELECT template_uid,source_sha256,status,
              reviewer,updated_at FROM masks ORDER BY updated_at DESC""").fetchall()
        return [dict(row) for row in rows]
