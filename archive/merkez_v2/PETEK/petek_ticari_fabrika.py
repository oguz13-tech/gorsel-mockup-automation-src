#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PETEK DOLABI factory commerce bridge; original six product paths stay unchanged.

Design: immutable source-bound geometry -> existing PETEK renderer -> hash-bound
SQLite artifact receipt -> deterministic SKU/title -> atomic XLSX export. External
ImgBB upload is an explicit opt-in, never attempted for unapproved assets.

This bridge DOES NOT modify the user's installed Daily V2, PR #9, live DB, or
original template pool. It is an isolated PETEK-only companion workflow.
"""
from __future__ import annotations

import argparse
import contextlib
import csv
from dataclasses import dataclass
import datetime as dt
import hashlib
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import re
import shutil
import sqlite3
import sys
import tempfile
import unittest
from typing import Iterator

import cv2
from openpyxl import Workbook, load_workbook

import petek_dolabi_app as petek


@dataclass(frozen=True)
class Policy:
    """Centralized limits, identifiers, output specifications, and recipes."""
    category: str = "06_Petek_Dolabi"
    bridge_recipe: str = "petek-commerce-v1-20261020"
    local_folder_name: str = "PETEK_TICARI_LOCAL"
    panel_store_name: str = "PETEK_DOLABI_LOCAL"
    db_name: str = "commerce.db"
    lock_name: str = "FACTORY.lock"
    log_name: str = "app.log"
    report_name: str = "RUN_REPORT.json"
    json_limit: int = 300_000
    max_artwork_bytes: int = 45_000_000
    max_jobs: int = 5000
    hash_chunk: int = 1_048_576
    min_free_bytes: int = 250_000_000
    sqlite_timeout: int = 15
    sku_length: int = 16
    barcode_length: int = 20
    headline_limit: int = 120
    upload_timeout: int = 35
    publish_confirmation: str = "I_APPROVE_PETEK_CLOUD_UPLOAD"
    image_width: int = 1200
    image_height: int = 1600
    image_extensions: tuple[str, ...] = (".png", ".jpg", ".jpeg", ".webp")
    export_fields: tuple[str, ...] = (
        "Stok Kodu", "Barkod", "Model Kodu", "Kategori", "Ürün Adı",
        "Açıklama", "Tasarım SHA256", "Şablon UID", "Mockup Dosyası",
        "Resim Linki", "Mağaza Grubu", "İş Durumu", "Artifact Key",
    )


CFG = Policy()


class FactoryError(RuntimeError):
    """Controlled fail-closed rejection with no source mutation."""


def sha(path: Path) -> str:
    """Stream SHA-256 in bounded memory, rejecting unexpected filesystem links."""
    if path.is_symlink() or not path.is_file():
        raise FactoryError(f"Dosya yok veya symlink: {path}")
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(CFG.hash_chunk), b""):
            h.update(chunk)
    return h.hexdigest()


def key_hash(document: dict) -> str:
    """Return deterministic SHA-256 for stable JSON identities."""
    return hashlib.sha256(json.dumps(document, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def secure_json(path: Path) -> dict:
    """Read a bounded JSON object, rejecting unsafe links or malformed content."""
    if path.is_symlink() or not path.is_file() or path.stat().st_size > CFG.json_limit:
        raise FactoryError(f"JSON geçersiz veya sınırı aşıyor: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeError, OSError, json.JSONDecodeError) as exc:
        raise FactoryError(f"JSON okunamadı: {path.name}: {exc}") from exc
    if not isinstance(value, dict):
        raise FactoryError("JSON üst düzeyinde nesne bulunmalı")
    return value


def safe_user_path(raw: str, base: Path) -> Path:
    """Resolve configured path relative to manifest directory without writes."""
    if not isinstance(raw, str) or not raw.strip() or len(raw) > 2048:
        raise FactoryError("Dosya yolu boş ya da geçersiz")
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        candidate = base / candidate
    if candidate.is_symlink():
        raise FactoryError(f"Symlink engellendi: {candidate}")
    return candidate.resolve()


def _not_nested(a: Path, b: Path) -> bool:
    """Return whether two paths are neither ancestor nor descendant."""
    return not (a == b or a in b.parents or b in a.parents)


def _log_setup(directory: Path) -> None:
    """Install console and rotating file logging in the dedicated state root."""
    logger = logging.getLogger("petek_commerce")
    logger.setLevel(logging.INFO)
    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    file_handler = RotatingFileHandler(directory / CFG.log_name, maxBytes=3_000_000,
                                       backupCount=4, encoding="utf-8")
    file_handler.setFormatter(formatter)
    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(console)


def atomic_json(path: Path, value: dict) -> None:
    """Persist JSON with fsync and atomic replacement inside isolated state."""
    if path.is_symlink():
        raise FactoryError("JSON hedefi symlink")
    fd, name = tempfile.mkstemp(prefix="._", suffix=".json", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(value, out, ensure_ascii=False, indent=2, sort_keys=True)
            out.flush()
            os.fsync(out.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def atomic_copy(src: Path, dst: Path) -> None:
    """Create an immutable hash-matched file, never replacing a prior output."""
    if dst.is_symlink():
        raise FactoryError("Çıktı symlink; işlem durdu")
    if dst.exists():
        if sha(dst) == sha(src):
            return
        raise FactoryError("Aynı isimde farklı içerik var; çıktı üzerine yazılmadı")
    dst.parent.mkdir(parents=True, exist_ok=True)
    with src.open("rb") as reader:
        with dst.open("xb") as writer:
            for chunk in iter(lambda: reader.read(CFG.hash_chunk), b""):
                writer.write(chunk)
            writer.flush()
            os.fsync(writer.fileno())
    if sha(src) != sha(dst):
        raise FactoryError("Kopya SHA doğrulaması başarısız; kaynağa dokunulmadı")


@dataclass(frozen=True)
class SourceTemplate:
    """One reviewed PETEK template, source-bound JSON, and optional live DB provenance."""
    uid: str
    image: Path
    geometry: Path
    image_sha: str
    geometry_sha: str
    approved: bool


@dataclass(frozen=True)
class Configuration:
    """Validated manifest and independent local output location."""
    designs: Path
    templates: tuple[SourceTemplate, ...]
    state: Path
    group: str
    source_approval_db: Path | None
    seller_prefix: str
    upload_enabled: bool
    upload_approved: bool


class ApprovalGate:
    """Require source-hash-bound human approval from the existing DB for cloud operations."""

    @staticmethod
    def verify(db_path: Path | None, templates: tuple[SourceTemplate, ...]) -> bool:
        """Validate template_profiles and approved quads without touching the DB."""
        if db_path is None:
            return False
        if db_path.is_symlink() or not db_path.is_file():
            raise FactoryError("Onay veritabanı yok veya symlink")
        try:
            with contextlib.closing(sqlite3.connect(db_path.as_uri() + "?mode=ro", uri=True)) as conn:
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA query_only=ON")
                for template in templates:
                    rows = conn.execute("""SELECT category, source_asset_sha256, review_status,
                        manually_verified, is_active, surface_quad, source_relative_path
                        FROM template_profiles WHERE template_uid=? AND is_active=1""",
                        (template.uid,)).fetchall()
                    if len(rows) != 1:
                        raise FactoryError(f"Tek aktif profil gerekli: {template.uid}")
                    row = rows[0]
                    geo = petek.PanelGeometry.from_file(template.geometry)
                    if (row["category"] != CFG.category or row["source_asset_sha256"] != template.image_sha
                            or row["review_status"] != "APPROVED" or row["manually_verified"] != 1
                            or row["is_active"] != 1 or not row["source_relative_path"]
                            or not str(row["source_relative_path"]).startswith(CFG.category + "/")):
                        raise FactoryError(f"İnsan onayı veya SHA uyuşmuyor: {template.uid}")
                    recorded = json.loads(row["surface_quad"])
                    if len(recorded) != 4 or any(len(v) != 2 for v in recorded):
                        raise FactoryError("DB geometrisi geçersiz")
                    if any(abs(float(a)-float(b)) > 0.75 for src, given in zip(recorded, geo.quad)
                           for a, b in zip(src, given)):
                        raise FactoryError("DB ve JSON dört köşe farklı")
            return True
        except (sqlite3.Error, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            raise FactoryError(f"DB onay kontrolü başarısız: {exc}") from exc


class ConfigurationLoader:
    """Load and validate one independent PETEK factory configuration."""

    @staticmethod
    def load(manifest: Path) -> Configuration:
        """Reject cross-category inputs, unknown settings and protected output nesting."""
        data = secure_json(manifest)
        allowed = {"category", "designs", "templates", "state_dir", "store_group", "seller_prefix",
                   "approval_db", "upload_enabled", "upload_confirmation"}
        if set(data) - allowed or data.get("category") != CFG.category:
            raise FactoryError("Yalnızca 06_Petek_Dolabi kategorisi desteklenir")
        base = manifest.parent.resolve()
        designs = safe_user_path(data.get("designs"), base)
        if not designs.is_dir() or designs.is_symlink():
            raise FactoryError("Tasarım klasörü mevcut değil")
        state = safe_user_path(data.get("state_dir"), base)
        if state.name != CFG.local_folder_name:
            raise FactoryError("Durum klasörü yalnızca PETEK_TICARI_LOCAL adıyla oluşturulabilir")
        if state.exists() and (state.is_symlink() or not state.is_dir()):
            raise FactoryError("Durum klasörü güvensiz")
        if not _not_nested(state, designs):
            raise FactoryError("Çıktı klasörü tasarımlarla iç içe olamaz")
        group = data.get("store_group")
        if not isinstance(group, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", group):
            raise FactoryError("Mağaza grubu 1–40 ASCII harf/rakam/-/_ karakter olmalı")
        prefix = data.get("seller_prefix", "PDK")
        if not isinstance(prefix, str) or not re.fullmatch(r"[A-Z0-9]{2,8}", prefix):
            raise FactoryError("Satıcı kod öneki 2–8 büyük alfanümerik olmalı")
        incoming = data.get("templates")
        if not isinstance(incoming, list) or not 1 <= len(incoming) <= 100:
            raise FactoryError("1–100 geçerli PETEK şablonu gerekli")
        templates: list[SourceTemplate] = []
        seen: set[str] = set()
        for record in incoming:
            if not isinstance(record, dict) or set(record) != {"uid", "image", "geometry"}:
                raise FactoryError("Şablon kaydı uid/image/geometry içermeli")
            uid = record["uid"]
            if not isinstance(uid, str) or not re.fullmatch(r"06_Petek_Dolabi_PetekDolabi_(?:\d{3,8}(?:\.png)?|SHA_[0-9a-f]{64})", uid):
                raise FactoryError(f"Geçersiz PETEK UID: {uid}")
            if uid in seen:
                raise FactoryError("Tekrarlanan şablon UID")
            seen.add(uid)
            image = safe_user_path(record["image"], base)
            geometry = safe_user_path(record["geometry"], base)
            for p in (image, geometry):
                if p.is_symlink() or not p.is_file() or not _not_nested(state, p):
                    raise FactoryError("Şablon, geometri veya durum dosyası güvensiz")
            digest = sha(image)
            geom = petek.PanelGeometry.from_file(geometry)
            if geom.category != CFG.category or geom.template_sha256 != digest or not geom.reviewed:
                raise FactoryError(f"SHA veya insan geometri inceleme alanı geçersiz: {uid}")
            templates.append(SourceTemplate(uid, image, geometry, digest, sha(geometry), True))
        source_db = data.get("approval_db")
        approval_db = safe_user_path(source_db, base) if source_db is not None else None
        if approval_db and not _not_nested(state, approval_db):
            raise FactoryError("Canlı DB yerel durum içinde bulunmamalı")
        upload_enabled = data.get("upload_enabled", False)
        if type(upload_enabled) is not bool:
            raise FactoryError("upload_enabled true/false olmalı")
        confirmation = data.get("upload_confirmation") == CFG.publish_confirmation
        if upload_enabled and (not confirmation or approval_db is None):
            raise FactoryError("Bulut için açık onay ve onaylı DB zorunludur")
        return Configuration(designs, tuple(templates), state, group, approval_db,
                             prefix, upload_enabled, confirmation)


class LocalLedger:
    """Private append-only SQLite receipt store for deterministic product/artifact identity."""

    def __init__(self, state: Path):
        """Create isolated SQLite schema without opening or migrating the user's live DB."""
        self.path = state / CFG.db_name
        if self.path.is_symlink():
            raise FactoryError("Yerel DB symlink")
        try:
            with self.connect() as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("""CREATE TABLE IF NOT EXISTS products(
                    product_key TEXT PRIMARY KEY, sku TEXT NOT NULL UNIQUE,
                    barcode TEXT NOT NULL UNIQUE, model TEXT NOT NULL,
                    title TEXT NOT NULL, description TEXT NOT NULL,
                    artwork_sha TEXT NOT NULL, store_group TEXT NOT NULL)""")
                conn.execute("""CREATE TABLE IF NOT EXISTS artifacts(
                    artifact_key TEXT PRIMARY KEY, product_key TEXT NOT NULL,
                    template_uid TEXT NOT NULL, template_sha TEXT NOT NULL,
                    geometry_sha TEXT NOT NULL, output_path TEXT NOT NULL,
                    output_sha TEXT NOT NULL, status TEXT NOT NULL,
                    cloud_url TEXT NOT NULL DEFAULT '', error TEXT NOT NULL DEFAULT '',
                    FOREIGN KEY(product_key) REFERENCES products(product_key))""")
        except sqlite3.Error as exc:
            raise FactoryError(f"Yerel SQLite açılamadı: {exc}") from exc

    def connect(self) -> sqlite3.Connection:
        """Open private ledger with FK enforcement and bounded busy timeout."""
        conn = sqlite3.connect(self.path, timeout=CFG.sqlite_timeout)
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def product(self, key: str, metadata: dict) -> dict:
        """Register once without mutable SKU/title reassignment on repeat runs."""
        with self.connect() as conn:
            conn.execute("""INSERT OR IGNORE INTO products(product_key,sku,barcode,model,title,
                description,artwork_sha,store_group) VALUES(?,?,?,?,?,?,?,?)""",
                (key, metadata["sku"], metadata["barcode"], metadata["model"], metadata["title"],
                 metadata["description"], metadata["artwork_sha"], metadata["store_group"]))
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM products WHERE product_key=?", (key,)).fetchone()
            if row is None or any(row[field] != metadata[field] for field in ("sku", "barcode", "model", "artwork_sha", "store_group")):
                raise FactoryError("SKU/ürün kimliği DB çakışması")
            return dict(row)

    def artifact(self, key: str) -> dict | None:
        """Read a stored artifact without changing completion status."""
        with self.connect() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM artifacts WHERE artifact_key=?", (key,)).fetchone()
            return dict(row) if row else None

    def record(self, key: str, record: dict) -> None:
        """Insert immutable render receipt, or reject inconsistent duplicate state."""
        with self.connect() as conn:
            prior = conn.execute("SELECT output_path,output_sha FROM artifacts WHERE artifact_key=?", (key,)).fetchone()
            if prior is None:
                conn.execute("""INSERT INTO artifacts(artifact_key,product_key,template_uid,
                    template_sha,geometry_sha,output_path,output_sha,status)
                    VALUES(?,?,?,?,?,?,?,?)""",
                    (key, record["product_key"], record["template_uid"], record["template_sha"],
                     record["geometry_sha"], record["output_path"], record["output_sha"], "RENDERED"))
            elif prior != (record["output_path"], record["output_sha"]):
                raise FactoryError("Önceki artifact çıktısı farklı")

    def mark(self, key: str, status: str, url: str = "", error: str = "") -> None:
        """Move one artifact through a small explicit completion state machine."""
        allowed = {"RENDERED": {"UPLOADING", "REVIEW_REQUIRED"},
                   "UPLOADING": {"UPLOADED", "UPLOAD_UNCERTAIN"},
                   "UPLOADED": {"EXPORTED"}, "EXPORTED": set(),
                   "UPLOAD_UNCERTAIN": set(), "REVIEW_REQUIRED": set()}
        with self.connect() as conn:
            row = conn.execute("SELECT status FROM artifacts WHERE artifact_key=?", (key,)).fetchone()
            if row is None or status not in allowed.get(row[0], set()):
                raise FactoryError(f"Geçersiz artifact durum geçişi: {row} -> {status}")
            conn.execute("UPDATE artifacts SET status=?,cloud_url=?,error=? WHERE artifact_key=?",
                         (status, url, error[:400], key))

    def records(self) -> Iterator[dict]:
        """Stream persisted product+artifact entries in stable order."""
        with contextlib.closing(self.connect()) as conn:
            conn.row_factory = sqlite3.Row
            for row in conn.execute("""SELECT a.*,p.sku,p.barcode,p.model,p.title,p.description,
                        p.artwork_sha,p.store_group FROM artifacts a JOIN products p
                        ON a.product_key=p.product_key ORDER BY p.sku,a.artifact_key"""):
                yield dict(row)


class SafeExporter:
    """Create versioned, immutable XLSX and CSV snapshots from the private ledger."""

    @staticmethod
    def _cell(value: object) -> str:
        """Protect spreadsheet cells against formula injection."""
        text = str(value or "")
        if text and text.lstrip().startswith(("=", "+", "-", "@")):
            return "'" + text
        return text

    @staticmethod
    def row(value: dict) -> dict:
        """Translate private artifact metadata to commercial sheet columns."""
        return {"Stok Kodu": value["sku"], "Barkod": value["barcode"],
                "Model Kodu": value["model"], "Kategori": CFG.category,
                "Ürün Adı": value["title"], "Açıklama": value["description"],
                "Tasarım SHA256": value["artwork_sha"], "Şablon UID": value["template_uid"],
                "Mockup Dosyası": value["output_path"], "Resim Linki": value["cloud_url"],
                "Mağaza Grubu": value["store_group"], "İş Durumu": value["status"],
                "Artifact Key": value["artifact_key"]}

    def export(self, ledger: LocalLedger, state: Path) -> tuple[Path, Path, str]:
        """Write immutable report snapshots and verify their content, never clobber Excel."""
        export_root = state / "EXPORTS"
        export_root.mkdir(parents=True, exist_ok=True)
        rows = [self.row(record) for record in ledger.records()]
        snapshot = key_hash({"rows": rows, "columns": CFG.export_fields, "recipe": CFG.bridge_recipe})
        csv_path = export_root / f"PETEK_URUNLER_{snapshot[:20]}.csv"
        xlsx_path = export_root / f"PETEK_URUNLER_{snapshot[:20]}.xlsx"
        created_during_this_call = not csv_path.exists() and not xlsx_path.exists()
        if not csv_path.exists() or not xlsx_path.exists():
            wb = Workbook(write_only=True)
            ws = wb.create_sheet("PETEK DOLABI")
            ws.append(list(CFG.export_fields))
            for row in rows:
                ws.append([self._cell(row[k]) for k in CFG.export_fields])
            tmp_name = None
            try:
                with tempfile.NamedTemporaryFile(prefix="export-", suffix=".xlsx", dir=export_root, delete=False) as tmp:
                    tmp_name = Path(tmp.name)
                wb.save(tmp_name)
                atomic_copy(tmp_name, xlsx_path)
            finally:
                if tmp_name and tmp_name.exists():
                    tmp_name.unlink()
            fd, name = tempfile.mkstemp(prefix="export-", suffix=".csv", dir=export_root)
            try:
                with os.fdopen(fd, "w", newline="", encoding="utf-8-sig") as f:
                    writer = csv.writer(f)
                    writer.writerow(CFG.export_fields)
                    for row in rows:
                        writer.writerow([self._cell(row[k]) for k in CFG.export_fields])
                    f.flush(); os.fsync(f.fileno())
                atomic_copy(Path(name), csv_path)
            finally:
                if os.path.exists(name):
                    os.unlink(name)
        # Protect previously exported Excel/CSV even if tampered files keep the same row count.
        receipt = export_root / f"PETEK_EXPORT_{snapshot[:20]}.json"
        digests = {"snapshot": snapshot, "xlsx_sha256": sha(xlsx_path), "csv_sha256": sha(csv_path)}
        if receipt.exists():
            if secure_json(receipt) != digests:
                raise FactoryError("Daha önce kaydedilmiş Excel/CSV değiştirildi")
        else:
            # No trusted receipt can be silently inferred from a pre-existing export pair.
            if not created_during_this_call:
                raise FactoryError("Fişsiz geçmiş Excel/CSV; manuel kurtarma gerekir")
            with receipt.open("x", encoding="utf-8") as stream:
                json.dump(digests, stream, ensure_ascii=False, sort_keys=True)
                stream.flush(); os.fsync(stream.fileno())
        # Confirm the expected number of persisted artifact rows before publishing.
        wb = load_workbook(xlsx_path, read_only=True, data_only=True)
        try:
            count = sum(1 for _ in wb.active.iter_rows(min_row=2, values_only=True))
        finally:
            wb.close()
        if count != len(rows):
            raise FactoryError("Excel satır sayısı ledger ile uyuşmuyor")
        return csv_path, xlsx_path, snapshot


class ImgBBUploader:
    """Explicit opt-in uploader; ambiguous network results never auto-retry."""

    def upload(self, image: Path) -> str:
        """POST a single unchanged PNG and validate returned HTTPS URL."""
        import requests
        token = os.environ.get("PETEK_IMGBB_KEY", "").strip()
        if not token:
            raise FactoryError("PETEK_IMGBB_KEY tanımlı değil")
        try:
            with image.open("rb") as stream:
                result = requests.post("https://api.imgbb.com/1/upload", data={"key": token},
                                       files={"image": (image.name, stream, "image/png")},
                                       timeout=CFG.upload_timeout)
            result.raise_for_status()
            body = result.json()
            url = body.get("data", {}).get("url")
            if not isinstance(url, str) or not url.startswith("https://"):
                raise FactoryError("Bulut yanıtında geçerli HTTPS görsel URL'si yok")
            return url
        except (requests.RequestException, OSError, ValueError) as exc:
            # An upload may already have succeeded on the remote end before a timeout.
            # Mark uncertain and require manual reconciliation, NOT blind retry.
            raise FactoryError(f"Yükleme sonucu belirsiz veya başarısız: {type(exc).__name__}") from exc


class SingleRunLock:
    """Single-writer lock; stale locks require an explicit human recovery action."""

    def __init__(self, directory: Path):
        """Track lock ownership for safe cleanup."""
        self.path = directory / CFG.lock_name
        self.owned = False

    def __enter__(self):
        """Create an exclusive lock without replacing existing or stale locks."""
        try:
            with self.path.open("x", encoding="utf-8") as file:
                json.dump({"pid": os.getpid(), "created": dt.datetime.now(dt.timezone.utc).isoformat()}, file)
            self.owned = True
            return self
        except FileExistsError as exc:
            raise FactoryError("Başka üretim var veya eski lock kaldı; otomatik silinmedi") from exc

    def __exit__(self, exc_type, exc, tb):
        """Release only the lock created by this process."""
        if self.owned:
            self.path.unlink(missing_ok=True)
            self.owned = False
        return False


class CommercialBridge:
    """Coordinate PETEK rendering, immutable metadata and verified exports."""

    def __init__(self, config: Configuration):
        """Initialize dedicated filesystem and the unmodified standalone renderer."""
        self.config = config
        self.state = config.state
        self.state.mkdir(parents=True, exist_ok=True)
        if self.state.is_symlink():
            raise FactoryError("Yerel çalışma klasörü symlink")
        if shutil.disk_usage(self.state).free < CFG.min_free_bytes:
            raise FactoryError("Yetersiz boş disk alanı")
        _log_setup(self.state)
        self.logger = logging.getLogger("petek_commerce")
        self.ledger = LocalLedger(self.state)
        self.store = petek.LocalStore(self.state / CFG.panel_store_name)
        self.renderer = petek.PetekService(self.store)
        self.exporter = SafeExporter()

    def _artwork_iter(self) -> Iterator[Path]:
        """Lazily enumerate source designs without following symlinks."""
        stack = [self.config.designs]
        while stack:
            folder = stack.pop()
            entries = sorted(os.scandir(folder), key=lambda ent: ent.name.casefold(), reverse=True)
            for entry in entries:
                if entry.is_symlink():
                    continue
                p = Path(entry.path)
                if entry.is_dir(follow_symlinks=False):
                    stack.append(p)
                elif entry.is_file(follow_symlinks=False) and p.suffix.lower() in CFG.image_extensions:
                    yield p

    def _product(self, artwork: Path, artwork_sha: str) -> tuple[str, dict]:
        """Derive stable per-artwork SKU/title/barcode independent of mockup number."""
        product_key = key_hash({"category": CFG.category, "store": self.config.group,
                                "art_sha": artwork_sha, "recipe": "petek-product-v1"})
        short = product_key[:CFG.sku_length].upper()
        sku = f"{self.config.seller_prefix}-{short}"
        # Internal marketplace barcode only; NOT a GS1/EAN-13 registration.
        barcode = f"{self.config.seller_prefix}{product_key[:CFG.barcode_length].upper()}"
        model = f"M-{sku}"
        title = re.sub(r"[_\-]+", " ", artwork.stem).strip()
        title = re.sub(r"\s+", " ", title)
        title = (title if title else "Özel Tasarım")[:CFG.headline_limit // 2]
        title = f"{title} Petek Dolabı Dekoratif 13 Havalandırma Yuvalı"[:CFG.headline_limit]
        description = ("Dekoratif Petek Dolabı ön panel baskısı. "
                       "Görselde 13 dikey havalandırma açıklığı illüstrasyonu bulunur. "
                       "Fiziksel referans ölçüler: 96x86x20 cm; satış ölçülerini ayrıca doğrulayın.")
        metadata = {"sku": sku, "barcode": barcode, "model": model,
                    "title": title, "description": description, "artwork_sha": artwork_sha,
                    "store_group": self.config.group}
        return product_key, metadata

    def _validate_render(self, output: Path) -> None:
        """Verify dimensions, decode and corruption before commerce registration."""
        if output.is_symlink() or not output.is_file():
            raise FactoryError("Render çıktısı bulunamadı veya symlink")
        image = petek.read_image(output)
        if image.shape[:2] != (CFG.image_height, CFG.image_width):
            raise FactoryError(f"Çıktı boyutları 1200x1600 değil: {image.shape}")

    def execute(self) -> dict:
        """Run bounded unattended LOCAL jobs; remote stages gated by approvals."""
        approved_db = ApprovalGate.verify(self.config.source_approval_db, self.config.templates)
        if self.config.upload_enabled and not approved_db:
            raise FactoryError("Bulut üretimi için APPROVED profiller doğrulanamadı")
        report = {"status": "RUNNING", "category": CFG.category,
                  "commercial_completion": False, "source_approval_db_verified": approved_db,
                  "cloud_upload_enabled": self.config.upload_enabled,
                  "rendered": 0, "reused": 0, "failed": [], "skipped": 0, "uploaded": 0,
                  "started_at": dt.datetime.now(dt.timezone.utc).isoformat()}
        with SingleRunLock(self.state):
            try:
                jobs = 0
                for artwork in self._artwork_iter():
                    if artwork.stat().st_size > CFG.max_artwork_bytes:
                        report["failed"].append({"file": artwork.name, "error": "INPUT_TOO_LARGE"})
                        continue
                    try:
                        art_sha = sha(artwork)
                        product_key, metadata = self._product(artwork, art_sha)
                        self.ledger.product(product_key, metadata)
                    except (FactoryError, sqlite3.Error, OSError) as exc:
                        report["failed"].append({"file": artwork.name, "error": str(exc)})
                        self.logger.error("INPUT_ERROR %s: %s", artwork, exc)
                        continue
                    for template in self.config.templates:
                        jobs += 1
                        if jobs > CFG.max_jobs:
                            raise FactoryError("Güvenlik iş limiti aşıldı")
                        try:
                            identity = {"product": product_key, "template_uid": template.uid,
                                        "template": template.image_sha,
                                        "geometry": template.geometry_sha, "recipe": petek.CONFIG.recipe_version}
                            artifact_key = key_hash(identity)
                            prior = self.ledger.artifact(artifact_key)
                            output, reused = self.renderer.render_file(artwork, template.image, template.geometry)
                            self._validate_render(output)
                            output_hash = sha(output)
                            if sha(artwork) != art_sha or sha(template.image) != template.image_sha or sha(template.geometry) != template.geometry_sha:
                                raise FactoryError("Girdi render sırasında değişti")
                            self.ledger.record(artifact_key, {"product_key": product_key,
                                "template_uid": template.uid, "template_sha": template.image_sha,
                                "geometry_sha": template.geometry_sha, "output_path": str(output),
                                "output_sha": output_hash})
                            if prior and (prior["output_sha"] != output_hash or prior["output_path"] != str(output)):
                                raise FactoryError("Tekrar kullanılan kayıtta SHA farkı")
                            report["reused" if reused else "rendered"] += 1
                            row = self.ledger.artifact(artifact_key)
                            if self.config.upload_enabled and row["status"] == "RENDERED":
                                self.ledger.mark(artifact_key, "UPLOADING")
                                try:
                                    url = ImgBBUploader().upload(output)
                                    self.ledger.mark(artifact_key, "UPLOADED", url=url)
                                    report["uploaded"] += 1
                                except FactoryError as exc:
                                    self.ledger.mark(artifact_key, "UPLOAD_UNCERTAIN", error=str(exc))
                                    report["failed"].append({"artifact": artifact_key, "error": "UPLOAD_UNCERTAIN"})
                            self.logger.info("LOCAL_ARTIFACT %s %s %s", template.uid, artifact_key,
                                             "REUSED" if reused else "CREATED")
                        except (petek.RenderRejected, FactoryError, sqlite3.Error, cv2.error, OSError, ValueError) as exc:
                            self.logger.exception("ARTIFACT_BLOCKED artwork=%s template=%s: %s", artwork.name, template.uid, exc)
                            report["failed"].append({"art": artwork.name, "template": template.uid,
                                                      "error": str(exc)[:400]})
                csv_file, xlsx_file, snap = self.exporter.export(self.ledger, self.state)
                report.update(csv=str(csv_file), excel=str(xlsx_file), export_sha256=snap,
                              completed_jobs=report["rendered"] + report["reused"])
                # A successful XLSX export cannot retroactively guarantee a remote result.
                # Local-only jobs remain RENDERED; uploaded jobs remain UPLOADED.
                statuses = [row["status"] for row in self.ledger.records()]
                blocked_remote = [v for v in statuses if v in ("UPLOADING", "UPLOAD_UNCERTAIN")]
                if blocked_remote:
                    report["failed"].append({"error": "REMOTE_UPLOAD_UNCERTAIN_RECONCILIATION_REQUIRED",
                                             "count": len(blocked_remote)})
                if self.config.upload_enabled and not report["failed"] and statuses and all(v == "UPLOADED" for v in statuses):
                    report["status"] = "UPLOADED_EXCEL_EXPORTED_REVIEW_REQUIRED"
                else:
                    report["status"] = "LOCAL_RENDER_AND_EXCEL_READY_REVIEW_REQUIRED" if not report["failed"] else "PARTIAL_FAILURE_REVIEW_REQUIRED"
            except Exception as exc:
                report["status"] = "BLOCKED"
                report["fatal"] = str(exc)
                self.logger.exception("RUN_BLOCKED %s", exc)
            finally:
                report["finished_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
                atomic_json(self.state / CFG.report_name, report)
        return report


def demo_config(root: Path) -> Path:
    """Generate self-contained, synthetic-only test inputs and a safe manifest."""
    root.mkdir(parents=True, exist_ok=True)
    seed_store = petek.LocalStore(root / CFG.panel_store_name)
    artwork, template, geometry = petek.create_demo_files(seed_store)
    design_dir = root / "DESIGNS"
    design_dir.mkdir(exist_ok=True)
    imported = design_dir / "demo_artwork.png"
    atomic_copy(artwork, imported)
    manifest = root / "demo_manifest.json"
    if manifest.exists():
        return manifest
    payload = {"category": CFG.category, "designs": str(design_dir),
               "state_dir": str(root / CFG.local_folder_name), "store_group": "DEMO",
               "seller_prefix": "PDK", "upload_enabled": False,
               "templates": [{"uid": "06_Petek_Dolabi_PetekDolabi_001",
                              "image": str(template), "geometry": str(geometry)}]}
    atomic_json(manifest, payload)
    return manifest


def build_parser() -> argparse.ArgumentParser:
    """Create explicit install-free CLI with test, demo, run and status commands."""
    parser = argparse.ArgumentParser(description="PETEK isolated factory commerce bridge")
    actions = parser.add_subparsers(dest="action", required=True)
    actions.add_parser("demo", help="Build synthetic PETEK sample and run isolated render/export")
    actions.add_parser("test", help="Run unit and integration tests")
    run = actions.add_parser("run", help="Execute a reviewed PETEK manifest")
    run.add_argument("--manifest", type=Path, required=True)
    status = actions.add_parser("status", help="Read isolated run summary")
    status.add_argument("--state", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Handle all CLI failures and return a predictable exit code."""
    try:
        args = build_parser().parse_args(argv)
        if args.action == "test":
            suite = unittest.TestSuite((
                unittest.defaultTestLoader.loadTestsFromTestCase(petek.PetekTests),
                unittest.defaultTestLoader.loadTestsFromTestCase(BridgeTests),
            ))
            result = unittest.TextTestRunner(verbosity=2).run(suite)
            return 0 if result.wasSuccessful() else 2
        if args.action == "status":
            print(json.dumps(secure_json(args.state / CFG.report_name), ensure_ascii=False, indent=2))
            return 0
        if args.action == "demo":
            path = demo_config(Path(__file__).resolve().parent / "PETEK_FABRIKA_DEMO")
        else:
            path = args.manifest.resolve()
        bridge = CommercialBridge(ConfigurationLoader.load(path))
        report = bridge.execute()
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["status"] in ("LOCAL_RENDER_AND_EXCEL_READY_REVIEW_REQUIRED",
                                         "UPLOADED_EXCEL_EXPORTED_REVIEW_REQUIRED") else 2
    except (FactoryError, petek.RenderRejected, ValueError, OSError, sqlite3.Error) as exc:
        logging.getLogger("petek_commerce").exception("CONTROLLED_BLOCK: %s", exc)
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        logging.getLogger("petek_commerce").exception("FATAL: %s", exc)
        print(f"CRITICAL: {exc}", file=sys.stderr)
        return 3


class BridgeTests(unittest.TestCase):
    """Safety, identity, export, approval and end-to-end commerce bridge tests."""

    def setUp(self) -> None:
        """Create disposable isolated directories for each case."""
        self.tmp = tempfile.TemporaryDirectory(prefix="petek-commerce-tests-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_stable_metadata(self) -> None:
        """Verify repeated products receive the same SKU and barcode."""
        x = Configuration(self.root, (), self.root / CFG.local_folder_name, "MAGAZA", None, "PDK", False, False)
        bridge = CommercialBridge(x)
        a = bridge._product(Path("Türkçe tema.png"), "0" * 64)
        b = bridge._product(Path("başka dosya.jpg"), "0" * 64)
        self.assertEqual(a[0], b[0]); self.assertEqual(a[1]["sku"], b[1]["sku"])

    def test_same_file_content_renamed_has_same_product(self) -> None:
        """Duplicate design bytes produce one product identity even after renaming."""
        config = Configuration(self.root, (), self.root / CFG.local_folder_name,
                               "MAGAZA", None, "PDK", False, False)
        bridge = CommercialBridge(config)
        key1, first = bridge._product(Path("A.png"), "1" * 64)
        key2, second = bridge._product(Path("B.png"), "1" * 64)
        self.assertEqual(key1, key2)
        bridge.ledger.product(key1, first)
        stored = bridge.ledger.product(key2, second)
        self.assertEqual(stored["sku"], first["sku"])
        self.assertEqual(stored["title"], first["title"])

    def test_different_content_same_filename_stays_distinct(self) -> None:
        """Prevent file-name collisions from merging different commercial SKUs."""
        config = Configuration(self.root, (), self.root / CFG.local_folder_name,
                               "MAGAZA", None, "PDK", False, False)
        bridge = CommercialBridge(config)
        k1, r1 = bridge._product(Path("A.png"), "1" * 64)
        k2, r2 = bridge._product(Path("A.png"), "2" * 64)
        self.assertNotEqual(k1, k2)
        self.assertNotEqual(r1["sku"], r2["sku"])
        bridge.ledger.product(k1, r1)
        bridge.ledger.product(k2, r2)

    def test_no_unknown_category(self) -> None:
        """Reject attempts to send an existing category through PETEK."""
        manifest = self.root / "bad.json"
        atomic_json(manifest, {"category": "01_Wifi_Kutusu"})
        with self.assertRaises(FactoryError):
            ConfigurationLoader.load(manifest)

    def test_missing_approval_blocks_cloud(self) -> None:
        """Ensure public upload cannot be enabled without an explicit approval."""
        manifest = demo_config(self.root / "inputs")
        d = secure_json(manifest); d["upload_enabled"] = True
        bad = self.root / "bad.json"; atomic_json(bad, d)
        with self.assertRaises(FactoryError):
            ConfigurationLoader.load(bad)

    def test_atomic_no_overwrite(self) -> None:
        """Retain previous bytes when destination name exists with different content."""
        a, b = self.root / "a.txt", self.root / "b.txt"
        a.write_text("ONE", encoding="utf-8")
        b.write_text("TWO", encoding="utf-8")
        with self.assertRaises(FactoryError):
            atomic_copy(a, b)
        self.assertEqual(b.read_text(encoding="utf-8"), "TWO")

    def test_formula_escape(self) -> None:
        """Confirm spreadsheet cells cannot execute user-crafted formulas."""
        self.assertEqual(SafeExporter._cell("=HYPERLINK('x')"), "'=HYPERLINK('x')")

    def test_immutable_ledger_rejects_mismatch(self) -> None:
        """Existing artifact identities cannot point to new bytes."""
        state = self.root / CFG.local_folder_name; state.mkdir()
        l = LocalLedger(state)
        k, record = "key", {"sku": "PDK-123", "barcode": "PDKABC", "model": "M-123",
                            "title": "Petek", "description": "desc", "artwork_sha": "0" * 64,
                            "store_group": "DEMO"}
        l.product(k, record)
        item = {"product_key": k, "template_uid": "x", "template_sha": "a", "geometry_sha": "b",
                "output_path": "/tmp/file.png", "output_sha": "digest-a"}
        l.record("artifact", item)
        with self.assertRaises(FactoryError):
            l.record("artifact", dict(item, output_sha="digest-b"))

    def test_state_machine_blocks_premature_completion(self) -> None:
        """Never mark local-only images as commercial completion."""
        state = self.root / CFG.local_folder_name; state.mkdir()
        l = LocalLedger(state)
        l.product("p", {"sku": "PDK-001", "barcode": "PDKX", "model": "M-001", "title": "t",
                        "description": "d", "artwork_sha": "a", "store_group": "G"})
        l.record("a", {"product_key": "p", "template_uid": "x", "template_sha": "a",
                       "geometry_sha": "b", "output_path": "/tmp/a.png", "output_sha": "sha"})
        with self.assertRaises(FactoryError):
            l.mark("a", "EXPORTED")

    def test_safe_local_demo_and_repeat(self) -> None:
        """Run actual PETEK renderer twice, preserving each output and all receipts."""
        manifest = demo_config(self.root / "demo")
        config = ConfigurationLoader.load(manifest)
        b = CommercialBridge(config)
        first = b.execute()
        self.assertEqual(first["status"], "LOCAL_RENDER_AND_EXCEL_READY_REVIEW_REQUIRED")
        self.assertEqual(first["rendered"], 1)
        row = list(b.ledger.records())[0]
        path = Path(row["output_path"])
        digest, modified = sha(path), path.stat().st_mtime_ns
        second = b.execute()
        self.assertEqual(second["reused"], 1)
        self.assertEqual((sha(path), path.stat().st_mtime_ns), (digest, modified))
        wb = load_workbook(second["excel"], read_only=True)
        try:
            self.assertEqual(sum(1 for _ in wb.active.iter_rows(values_only=True)), 2)
        finally:
            wb.close()

    def test_invalid_quad_blocks_render(self) -> None:
        """Tampered category geometry source SHA cannot pass manifest validation."""
        manifest = demo_config(self.root / "demo")
        data = secure_json(manifest)
        geometry = Path(data["templates"][0]["geometry"])
        original = geometry.read_bytes()
        try:
            content = secure_json(geometry);content["template_sha256"] = "0" * 64
            atomic_json(geometry, content)
            with self.assertRaises(FactoryError):
                ConfigurationLoader.load(manifest)
        finally:
            geometry.write_bytes(original)

    def test_export_tamper_is_blocked(self) -> None:
        """Reject edited exported CSV while its corresponding Excel receipt exists."""
        manifest = demo_config(self.root / "demo")
        bridge = CommercialBridge(ConfigurationLoader.load(manifest))
        first = bridge.execute()
        self.assertEqual(first["status"], "LOCAL_RENDER_AND_EXCEL_READY_REVIEW_REQUIRED")
        with Path(first["csv"]).open("a", encoding="utf-8") as stream:
            stream.write("\nTAMPERED\n")
        after = bridge.execute()
        self.assertEqual(after["status"], "BLOCKED")

    def test_approved_readonly_db_gate(self) -> None:
        """Accept exact manually approved source rows and reject stale source SHA."""
        manifest = demo_config(self.root / "demo")
        row = secure_json(manifest)["templates"][0]
        geometry = secure_json(Path(row["geometry"]))
        db_path = self.root / "approve.sqlite3"
        with sqlite3.connect(db_path) as conn:
            conn.execute("""CREATE TABLE template_profiles (template_uid TEXT,category TEXT,
                source_asset_sha256 TEXT,review_status TEXT,manually_verified INT,
                is_active INT,surface_quad TEXT,source_relative_path TEXT)""")
            conn.execute("INSERT INTO template_profiles VALUES(?,?,?,?,?,?,?,?)",
                (row["uid"], CFG.category, sha(Path(row["image"])), "APPROVED", 1,
                 1, json.dumps(geometry["quad"]), CFG.category + "/PetekDolabi_001.png"))
        config = ConfigurationLoader.load(manifest)
        self.assertTrue(ApprovalGate.verify(db_path, config.templates))
        with sqlite3.connect(db_path) as conn:
            conn.execute("UPDATE template_profiles SET source_asset_sha256=?", ("0" * 64,))
        with self.assertRaises(FactoryError):
            ApprovalGate.verify(db_path, config.templates)

    def test_remote_uncertain_not_marked_complete(self) -> None:
        """Blocked upload attempts must never be silently treated as completed."""
        state = self.root / CFG.local_folder_name; state.mkdir()
        ledger = LocalLedger(state)
        ledger.product("p", {"sku": "PDK-001", "barcode": "PDK-INT", "model": "M-001",
            "title": "t", "description": "d", "artwork_sha": "a", "store_group": "G"})
        ledger.record("a", {"product_key": "p", "template_uid": "t", "template_sha": "s",
            "geometry_sha": "g", "output_path": "out", "output_sha": "sha"})
        ledger.mark("a", "UPLOADING")
        with self.assertRaises(FactoryError):
            ledger.mark("a", "EXPORTED")
        ledger.mark("a", "UPLOAD_UNCERTAIN")
        with self.assertRaises(FactoryError):
            ledger.mark("a", "UPLOADED")

    def test_lock_prevents_competing_writer(self) -> None:
        """Reject duplicate or stale process locks without automatic deletion."""
        with SingleRunLock(self.root):
            with self.assertRaises(FactoryError):
                with SingleRunLock(self.root):
                    pass


if __name__ == "__main__":
    sys.exit(main())
