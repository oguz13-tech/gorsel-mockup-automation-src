"""V5.0 centralized, create-only image intake.

The old runtime had two independent rename paths: a HAM watcher and a mockup
staging watcher.  This module is the single explicit writer used by the
Graphite upload center.  It deliberately does not alter an existing file or
template record.  Every number is reserved in a small SQLite journal before a
copy is published, so a crash burns the number instead of making it available
for reuse.

The module is intentionally independent from the renderer and the four-corner
editor.  A new mockup is copied to the working/original pools and registered as
``REVIEW_REQUIRED``; the operator still approves geometry in the existing
review surface.  Design files are copied byte-for-byte to HAM BASKI
TASARIMLARI and retain their original extension and pixels.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import os
from pathlib import Path
import re
import shutil
import sqlite3
import tempfile
import threading
import unicodedata
import json
from typing import Iterable, Callable

from PIL import Image, UnidentifiedImageError

SUPPORTED_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp"})
MAX_FILE_BYTES = 250_000_000

MOCKUP_CATEGORIES = (
    "01_Wifi_Kutusu",
    "02_Cam_Tablo_Dikey",
    "02_Cam_Tablo_Yatay",
    "03_Ahsap_Tablo",
    "04_Cam_Dograma",
    "05_Ocak_Arkasi",
    "06_Petek_Kapama",
)
MOCKUP_LABELS = {
    "01_Wifi_Kutusu": "01 · Wifi Kutusu",
    "02_Cam_Tablo_Dikey": "02 · Cam Tablo Dikey",
    "02_Cam_Tablo_Yatay": "02 · Cam Tablo Yatay",
    "03_Ahsap_Tablo": "03 · Ahşap Tablo",
    "04_Cam_Dograma": "04 · Cam Doğrama",
    "05_Ocak_Arkasi": "05 · Ocak Arkası",
    "06_Petek_Kapama": "06 · Petek Kapama",
}
MOCKUP_PREFIXES = {
    "01_Wifi_Kutusu": "Wifi_Kutusu",
    "02_Cam_Tablo_Dikey": "CamTabloDikey",
    "02_Cam_Tablo_Yatay": "CamTabloYatay",
    "03_Ahsap_Tablo": "AhsapTablo",
    "04_Cam_Dograma": "CamDograma",
    "05_Ocak_Arkasi": "OcakArkasi",
    "06_Petek_Kapama": "Petek_Dolabi",
}
ORIENTATIONS = ("Yatay", "Dikey")
ORIENTATION_PREFIXES = {"Yatay": "Yatay_Tasarim", "Dikey": "Dikey_Tasarim"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_prefix(value: str) -> str:
    """Make a readable Windows filename prefix without path separators."""
    value = unicodedata.normalize("NFC", str(value or "")).strip()
    value = re.sub(r"[\s-]+", "_", value)
    value = re.sub(r"[<>:\"/\\|?*\x00-\x1f]", "", value)
    value = re.sub(r"_+", "_", value).strip("._")
    return value


def _atomic_json_backup(path: Path) -> Path:
    """Create a unique SQLite backup next to the user's local app state."""
    local = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / ".gorsel_mockup"))
    target_dir = local / "GorselMockup" / "CentralUploadBackups"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / ("before_upload_" + hashlib.sha256(
        (str(path) + str(os.stat(path).st_mtime_ns)).encode("utf-8")
    ).hexdigest()[:20] + ".sqlite3")
    if target.exists():
        return target
    with sqlite3.connect(str(path)) as src, sqlite3.connect(str(target)) as dst:
        src.backup(dst)
    if target.stat().st_size <= 0:
        target.unlink(missing_ok=True)
        raise RuntimeError("CENTRAL_UPLOAD_EMPTY_DB_BACKUP")
    return target


class CentralUploadError(RuntimeError):
    pass


class CentralUploadRegistry:
    """Durable numbering and upload records for both image families."""

    def __init__(self, runtime: Path):
        self.runtime = Path(runtime).resolve(strict=True)
        if self.runtime.is_symlink() or not self.runtime.is_dir():
            raise ValueError("CENTRAL_UPLOAD_RUNTIME_INVALID")
        # Keep the central journal in the existing live SQLite database so
        # template/design history is backed up and moved together with the
        # application's established persistence boundary.
        self.db_path = self.runtime / "SABLON_V2_MIMARI" / "ayarlar.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self._historical_digest_cache: dict[str, set[str]] = {}
        self._recorded_digest_cache: dict[str, set[str]] = {}
        self._init_db()

    @contextmanager
    def connection(self):
        conn = sqlite3.connect(str(self.db_path), timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("PRAGMA synchronous=FULL")
        try:
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self):
        if self.db_path.is_file():
            _atomic_json_backup(self.db_path)
        with self.connection() as db:
            db.executescript("""
              CREATE TABLE IF NOT EXISTS upload_meta(
                scope TEXT PRIMARY KEY, high INTEGER NOT NULL CHECK(high >= 0));
              CREATE TABLE IF NOT EXISTS upload_numbers(
                scope TEXT NOT NULL, number INTEGER NOT NULL,
                canonical_name TEXT NOT NULL, status TEXT NOT NULL,
                sha256 TEXT, source_name TEXT, destination TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(scope, number));
              CREATE TABLE IF NOT EXISTS upload_records(
                id TEXT PRIMARY KEY, kind TEXT NOT NULL, scope TEXT NOT NULL,
                number INTEGER NOT NULL, source_name TEXT NOT NULL,
                destination TEXT NOT NULL, extension TEXT NOT NULL,
                sha256 TEXT NOT NULL, status TEXT NOT NULL,
                error_text TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
              CREATE INDEX IF NOT EXISTS upload_sha_idx
                ON upload_records(kind, sha256);
            """)
            for scope in ("Yatay", "Dikey", *MOCKUP_CATEGORIES):
                db.execute("INSERT OR IGNORE INTO upload_meta(scope,high) VALUES(?,0)", (scope,))
        self._adopt_existing_numbers()

    def _adopt_existing_numbers(self):
        """Adopt visible historical names once without renaming or rewriting them."""
        with self.lock, self.connection() as db:
            for scope, directory, prefix in self._historical_sources():
                if not directory.is_dir():
                    continue
                if directory.is_symlink():
                    continue
                found = []
                for path in directory.rglob("*"):
                    if not path.is_file() or path.is_symlink() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                        continue
                    separator = r"_?" if scope in ORIENTATIONS else r"_"
                    match = re.fullmatch(re.escape(prefix) + separator + r"(\d+)", path.stem, re.IGNORECASE)
                    if not match:
                        continue
                    number = int(match.group(1))
                    found.append((number, path))
                for number, path in found:
                    db.execute("""INSERT OR IGNORE INTO upload_numbers
                        (scope,number,canonical_name,status,source_name,destination)
                        VALUES(?,?,?,'ADOPTED',?,?)""",
                        (scope, number, path.name, str(path), str(path)))
                if found:
                    high = max(number for number, _ in found)
                    db.execute("UPDATE upload_meta SET high=MAX(high,?) WHERE scope=?", (high, scope))
            # The live template registry contains tombstones for deleted or
            # cloud-only templates.  Import its high-water marks read-only so
            # the central uploader can never resurrect one of those identities.
            try:
                for category in MOCKUP_CATEGORIES:
                    if category == "06_Petek_Kapama":
                        continue  # PETEK owns a separate immutable registry.
                    rows = db.execute(
                        "SELECT template_number, canonical_name FROM template_number_registry WHERE category=?",
                        (category,),
                    ).fetchall()
                    prefix = MOCKUP_PREFIXES[category]
                    for row in rows:
                        number = int(row[0])
                        name = str(row[1] or f"{prefix}_{number:03d}.png")
                        db.execute("""INSERT OR IGNORE INTO upload_numbers
                          (scope,number,canonical_name,status,source_name)
                          VALUES(?,?,?,'HISTORICAL','template_number_registry')""",
                                   (category, number, name))
                    if rows:
                        db.execute("UPDATE upload_meta SET high=MAX(high,?) WHERE scope=?",
                                   (max(int(row[0]) for row in rows), category))
            except sqlite3.OperationalError:
                # Legacy databases without the registry are still protected by
                # visible files and the new durable upload table.
                pass

    def _historical_sources(self):
        for category, prefix in MOCKUP_PREFIXES.items():
            if category == "06_Petek_Kapama":
                try:
                    from petek_folders_v46 import petek_directory
                    yield category, petek_directory(self.runtime, "2_SABLON_HAVUZU"), prefix
                    yield category, petek_directory(self.runtime, "2_SABLON_HAVUZU_ORIJINAL_YEDEK"), prefix
                except Exception:
                    continue
            else:
                yield category, self.runtime / "2_SABLON_HAVUZU" / category, prefix
                yield category, self.runtime / "2_SABLON_HAVUZU_ORIJINAL_YEDEK" / category, prefix
        for orientation, prefix in ORIENTATION_PREFIXES.items():
            yield orientation, self.runtime / "HAM BASKI TASARIMLARI" / (orientation + "lar"), prefix

    def high(self, scope: str) -> int:
        with self.connection() as db:
            return int(db.execute("SELECT high FROM upload_meta WHERE scope=?", (scope,)).fetchone()[0])

    def preview_numbers(self, scope: str, count: int = 1) -> list[int]:
        with self.connection() as db:
            high = int(db.execute("SELECT high FROM upload_meta WHERE scope=?", (scope,)).fetchone()[0])
            return list(range(high + 1, high + count + 1))

    def reserve(self, scope: str, names: list[str], kind: str, sources: list[Path], extensions: list[str]) -> list[int]:
        with self.lock, self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            high = int(db.execute("SELECT high FROM upload_meta WHERE scope=?", (scope,)).fetchone()[0])
            numbers = list(range(high + 1, high + len(names) + 1))
            db.execute("UPDATE upload_meta SET high=? WHERE scope=?", (numbers[-1], scope))
            for number, name, source, ext in zip(numbers, names, sources, extensions):
                db.execute("""INSERT INTO upload_numbers
                    (scope,number,canonical_name,status,source_name)
                    VALUES(?,?,?,'RESERVED',?)""", (scope, number, name, str(source)))
            return numbers

    def record(self, *, kind: str, scope: str, number: int, source: Path,
               destination: Path, extension: str, digest: str, status: str,
               error: str = ""):
        with self.connection() as db:
            db.execute("""UPDATE upload_numbers SET status=?,sha256=?,destination=?
                          WHERE scope=? AND number=?""",
                       (status, digest, str(destination), scope, number))
            db.execute("""INSERT INTO upload_records
              (id,kind,scope,number,source_name,destination,extension,sha256,status,error_text)
              VALUES(lower(hex(randomblob(16))),?,?,?,?,?,?,?,?,?)""",
                       (kind, scope, number, str(source), str(destination), extension, digest, status, error))
        if status != 'ERROR':
            self._recorded_digest_cache.setdefault(kind, set()).add(digest)

    def set_reserved_names(self, scope: str, numbers: list[int], names: list[str]):
        with self.connection() as db:
            for number, name in zip(numbers, names):
                db.execute("UPDATE upload_numbers SET canonical_name=? WHERE scope=? AND number=?",
                           (name, scope, int(number)))

    def duplicate_sha(self, kind: str, digest: str) -> bool:
        cached = self._recorded_digest_cache.get(kind)
        if cached is None:
            with self.connection() as db:
                cached = {str(row[0]) for row in db.execute(
                    "SELECT sha256 FROM upload_records WHERE kind=? AND status <> 'ERROR' AND sha256 IS NOT NULL",
                    (kind,)).fetchall()}
            self._recorded_digest_cache[kind] = cached
        return digest in cached

    def duplicate_sha_anywhere(self, kind: str, digest: str) -> bool:
        """Detect an already-published byte identity even when legacy code
        failed to write an upload_records row.  This is deliberately
        read-only; the caller keeps the existing canonical file and number.
        """
        if self.duplicate_sha(kind, digest):
            return True
        if kind != "mockup":
            return False
        # Historical folders used to be rescanned for every candidate.  A
        # large folder import therefore became O(files * historical files).
        # Build the immutable-on-this-run digest set once; newly uploaded
        # records are still caught by the DB query above.
        cached = self._historical_digest_cache.get(kind)
        if cached is None:
            cached = set()
            for category, folder, _prefix in self._historical_sources():
                if category not in MOCKUP_CATEGORIES or not folder.is_dir() or folder.is_symlink():
                    continue
                for candidate in folder.iterdir():
                    if candidate.is_file() and not candidate.is_symlink():
                        try:
                            cached.add(sha256_file(candidate))
                        except OSError:
                            continue
            self._historical_digest_cache[kind] = cached
        return digest in cached

    def audit_designs_for_production(self) -> dict:
        """Validate the V5 central design pool without renaming any file.

        ``HamDesignVault`` is the legacy ``Ham<number>`` intake authority and
        is intentionally not used by the V5 central uploader.  V5 design
        identities live in ``upload_records``/``upload_numbers`` instead and
        use names such as ``Yatay_Tasarim001.png``.  The production gate must
        therefore validate that registry, its byte identities, and the visible
        pool agree.  Any drift remains a visible, reviewable block; this
        method never repairs, adopts, or rewrites files.
        """
        pool_candidate = self.runtime / "HAM BASKI TASARIMLARI"
        if pool_candidate.is_symlink() or not pool_candidate.is_dir():
            raise ValueError("CENTRAL_UPLOAD_DESIGN_POOL_INVALID: " + str(pool_candidate))
        pool = pool_candidate.resolve(strict=True)

        issues: list[dict] = []
        expected: dict[str, str] = {}
        with self.connection() as db:
            rows = db.execute(
                """SELECT scope, number, destination, extension, sha256
                   FROM upload_records
                   WHERE kind='design' AND status='ACTIVE'
                   ORDER BY scope, number"""
            ).fetchall()
            active_numbers = {
                (str(row[0]), int(row[1])): str(row[2])
                for row in db.execute(
                    """SELECT scope, number, status
                       FROM upload_numbers
                       WHERE scope IN ('Yatay','Dikey') AND status='ACTIVE'"""
                ).fetchall()
            }

        for row in rows:
            scope, number = str(row[0]), int(row[1])
            digest = str(row[4] or "")
            destination = Path(str(row[2])).resolve(strict=False)
            try:
                relative = destination.relative_to(pool)
            except ValueError:
                issues.append({"type": "CENTRAL_DESIGN_OUTSIDE_POOL",
                               "scope": scope, "number": number,
                               "file": str(destination)})
                continue
            key = str(relative).casefold()
            if key in expected:
                issues.append({"type": "CENTRAL_DESIGN_DUPLICATE_DESTINATION",
                               "file": str(relative), "other": expected[key]})
            expected[key] = str(relative)
            if (scope, number) not in active_numbers:
                issues.append({"type": "CENTRAL_DESIGN_NUMBER_NOT_ACTIVE",
                               "scope": scope, "number": number})
            if destination.is_symlink() or not destination.is_file():
                issues.append({"type": "CENTRAL_DESIGN_FILE_MISSING",
                               "file": str(relative), "scope": scope,
                               "number": number,
                               # Keep the registry identity available when a
                               # file was moved into Kullanildi.  A matching
                               # filename alone is not enough: the bytes must
                               # still be the originally named design.
                               "expected_sha256": digest})
                continue
            if destination.suffix.lower() not in SUPPORTED_EXTENSIONS:
                issues.append({"type": "CENTRAL_DESIGN_UNSUPPORTED_EXTENSION",
                               "file": str(relative)})
                continue
            if not digest or sha256_file(destination) != digest:
                issues.append({"type": "CENTRAL_DESIGN_SHA_MISMATCH",
                               "file": str(relative), "scope": scope,
                               "number": number})

        actual: dict[str, str] = {}
        for directory, dirs, files in os.walk(pool, followlinks=False):
            here = Path(directory)
            safe_dirs = []
            for name in sorted(dirs):
                candidate = here / name
                if candidate.is_symlink():
                    issues.append({"type": "CENTRAL_DESIGN_SYMLINK",
                                   "file": str(candidate.relative_to(pool))})
                else:
                    safe_dirs.append(name)
            dirs[:] = safe_dirs
            for name in sorted(files):
                candidate = here / name
                if candidate.is_symlink():
                    issues.append({"type": "CENTRAL_DESIGN_SYMLINK",
                                   "file": str(candidate.relative_to(pool))})
                    continue
                if candidate.suffix.lower() not in SUPPORTED_EXTENSIONS:
                    continue
                relative = candidate.relative_to(pool)
                actual[str(relative).casefold()] = str(relative)
        unregistered = [actual[key] for key in sorted(set(actual) - set(expected))]
        # A used design may have been moved into a ``baski-kullanildi``
        # subfolder.  It is physically present, but no longer at the
        # registry's active destination; report that fact instead of calling
        # it missing.  The discovered path is still visible to the caller so
        # production can skip it without moving or deleting anything.
        by_name: dict[str, list[str]] = {}
        for relative in actual.values():
            by_name.setdefault(Path(relative).name.casefold(), []).append(relative)
        for issue in issues:
            if issue.get("type") != "CENTRAL_DESIGN_FILE_MISSING":
                continue
            matches = by_name.get(Path(str(issue.get("file", ""))).name.casefold(), [])
            expected_sha = str(issue.get("expected_sha256") or "")
            matching = []
            for candidate in sorted(matches):
                try:
                    if expected_sha and sha256_file(pool / candidate) == expected_sha:
                        matching.append(candidate)
                except OSError:
                    continue
            if matching:
                issue["type"] = "CENTRAL_DESIGN_FILE_MOVED_USED"
                issue["found"] = matching[0]
            else:
                # Same-name but different-byte files are not recoverable
                # moved designs.  Keep them as a missing/identity defect so
                # the opt-in Kullanildi path can never mint a new identity.
                issue.pop("expected_sha256", None)
        return {"path": str(pool), "registered": len(rows),
                "issues": issues, "unregistered": unregistered}

    def validate_designs_for_production(self) -> dict:
        """Fail-closed compatibility wrapper for callers that require a gate."""
        report = self.audit_designs_for_production()
        if report["issues"] or report["unregistered"]:
            raise ValueError(
                "CENTRAL_UPLOAD_DESIGNS_ONCE_KONTROL: " + json.dumps(
                    {"issues": report["issues"][:4], "unregistered": report["unregistered"][:4]},
                    ensure_ascii=False))
        return report


def _create_copy(source: Path, destination: Path, digest: str):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_symlink():
        raise FileExistsError("CENTRAL_UPLOAD_TARGET_SYMLINK: " + str(destination))
    if destination.exists():
        if destination.is_file() and sha256_file(destination) == digest:
            return
        raise FileExistsError("CENTRAL_UPLOAD_TARGET_EXISTS: " + str(destination))
    temp = destination.parent / ("." + destination.name + ".pending")
    try:
        with source.open("rb") as src, temp.open("xb") as dst:
            for block in iter(lambda: src.read(1024 * 1024), b""):
                dst.write(block)
            dst.flush(); os.fsync(dst.fileno())
        if sha256_file(temp) != digest:
            raise CentralUploadError("CENTRAL_UPLOAD_SOURCE_CHANGED")
        os.link(temp, destination)
        # destination is a hardlink to the already SHA-verified temp inode;
        # hashing the same bytes a second time only doubled I/O for every file.
    finally:
        temp.unlink(missing_ok=True)


def _verify_image(path: Path):
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise CentralUploadError("DESTEKLENMEYEN_UZANTI")
    if path.is_symlink() or not path.is_file():
        raise CentralUploadError("GUVENSIZ_KAYNAK")
    if path.stat().st_size <= 0 or path.stat().st_size > MAX_FILE_BYTES:
        raise CentralUploadError("BOYUT_LIMITI")
    try:
        with Image.open(path) as image:
            image.verify()
    except (OSError, ValueError, SyntaxError, UnidentifiedImageError) as exc:
        raise CentralUploadError("BOZUK_GORSEL") from exc


class CentralUploader:
    def __init__(self, runtime: Path):
        self.runtime = Path(runtime)
        self.registry = CentralUploadRegistry(self.runtime)
        self._db_lock = threading.RLock()
        self._template_profile_ready: bool | None = None
        self._template_analyzer_cls = None
        self._template_analyzer = None
        self._save_template_profile = None
        self._fingerprint_cache: dict[tuple[str, int, int], str] = {}

    def fingerprint(self, source: Path) -> str:
        """Validate and hash a source once per unchanged filesystem identity."""
        source = Path(source).resolve()
        stat = source.stat()
        key = (str(source), int(stat.st_mtime_ns), int(stat.st_size))
        cached = self._fingerprint_cache.get(key)
        if cached is not None:
            return cached
        _verify_image(source)
        digest = sha256_file(source)
        self._fingerprint_cache[key] = digest
        return digest

    @staticmethod
    def collect_files(paths: Iterable[Path], *, recursive: bool = True) -> list[Path]:
        result: list[Path] = []
        for raw in paths:
            path = Path(raw)
            if path.is_file():
                result.append(path)
            elif path.is_dir():
                iterator = path.rglob("*") if recursive else path.iterdir()
                def include(candidate):
                    if not candidate.is_file():
                        return False
                    if not recursive:
                        return True
                    try:
                        relative = candidate.relative_to(path)
                    except ValueError:
                        return True
                    # Ignore archive/quarantine subfolders created by this workflow,
                    # but allow a user to legitimately choose a source folder
                    # whose own name happens to be "Yüklenenler".
                    return not (relative.parts and relative.parts[0] in {"Yüklenenler", "kontrol et sil"})
                result.extend(p for p in iterator if include(p))
        return sorted({p.resolve() for p in result}, key=lambda p: str(p).casefold())

    def _mockup_directory(self, category: str, section: str) -> Path:
        if category == "06_Petek_Kapama":
            from petek_folders_v46 import petek_directory
            return petek_directory(self.runtime, section)
        return self.runtime / section / category

    def _mockup_db_registration(self, category: str, filename: str):
        if category == "06_Petek_Kapama":
            # PETEK masks have their own registry and must never be fabricated
            # as a legacy six-category geometry row.
            return "PETEK_REVIEW_REQUIRED"
        db_path = self.runtime / "SABLON_V2_MIMARI" / "ayarlar.db"
        if not db_path.is_file() or db_path.is_symlink():
            raise CentralUploadError("LIVE_DB_MISSING")
        _atomic_json_backup(db_path)
        data = {"tip": "perspektif", "koseler": [], "review_status": "REVIEW_REQUIRED",
                "manually_verified": False,
                "kaynak": "V5 Merkezi Görsel Yükleme Merkezi; dört köşe onayı bekliyor"}
        with sqlite3.connect(str(db_path), timeout=30) as db:
            db.execute("PRAGMA busy_timeout=30000")
            db.execute("BEGIN IMMEDIATE")
            db.execute("""INSERT OR IGNORE INTO categories(id,label) VALUES(?,?)""",
                       (category, MOCKUP_LABELS.get(category, category)))
            db.execute("""INSERT OR IGNORE INTO templates(category_id,filename,data)
                       VALUES(?,?,?)""", (category, filename, json.dumps(data, ensure_ascii=False)))
            db.commit()
        return "REVIEW_REQUIRED"

    def _auto_propose_corners(self, category: str, filename: str, image_path: Path) -> bool:
        """Persist an analyzer proposal as review-only draft metadata."""
        # PETEK uses its own immutable geometry/mask registry.  Running the
        # generic TemplateAnalyzer here duplicated roughly 2–3 seconds of
        # CPU work per image without affecting the PETEK review flow.
        if category == "06_Petek_Kapama":
            return False
        db_path = self.runtime / "SABLON_V2_MIMARI" / "ayarlar.db"
        try:
            if self._template_profile_ready is None:
                with sqlite3.connect(str(db_path), timeout=30) as db:
                    tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                self._template_profile_ready = "template_profiles" in tables
            if not self._template_profile_ready:
                return False
            import sys
            core_root = self.runtime / "SABLON_V2_MIMARI"
            if str(core_root) not in sys.path:
                sys.path.insert(0, str(core_root))
            if self._template_analyzer_cls is None:
                from core.template_intelligence import TemplateAnalyzer, save_template_profile
                self._template_analyzer_cls = TemplateAnalyzer
                self._template_analyzer = TemplateAnalyzer()
                self._save_template_profile = save_template_profile
            analysis = self._template_analyzer.analyze(str(image_path), category)
            quad = analysis.get("surface_quad")
            if not isinstance(quad, list) or len(quad) != 4:
                return False
            profile = {
                "template_uid": f"{category}_{filename}", "category": category,
                "source_relative_path": f"{category}/{filename}",
                "source_asset_sha256": analysis.get("source_asset_sha256"),
                "profile_version": "v2",
                "analyzer_version": analysis.get("analyzer_version", "central_upload_v500"),
                "product_class": analysis.get("rule", {}).get("product_class", "Bilinmeyen"),
                "orientation": analysis.get("orientation", "UNKNOWN"),
                "nominal_aspect": analysis.get("nominal_aspect", "UNKNOWN"),
                "surface_quad": quad, "outer_quad": analysis.get("outer_quad"),
                "print_policy": analysis.get("rule", {}).get("print_policy", "full_bleed"),
                "confidence_total": analysis.get("confidence_total", 0.0),
                "component_confidences": analysis.get("component_confidences", {}),
                "review_status": "REVIEW_REQUIRED", "manually_verified": False,
            }
            self._save_template_profile(str(db_path), profile)
            with sqlite3.connect(str(db_path), timeout=30) as db:
                row = db.execute("SELECT data FROM templates WHERE category_id=? AND filename=?", (category, filename)).fetchone()
                data = json.loads(row[0]) if row else {}
                data.update({"koseler": quad, "review_status": "REVIEW_REQUIRED",
                             "manually_verified": False, "auto_corner_once": True,
                             "auto_corner_engine": "template_analyzer"})
                db.execute("UPDATE templates SET data=? WHERE category_id=? AND filename=?",
                           (json.dumps(data, ensure_ascii=False), category, filename))
                db.commit()
            return True
        except Exception:
            return False

    def upload_mockups(self, category: str, files: Iterable[Path], progress: Callable | None = None) -> dict:
        if category not in MOCKUP_CATEGORIES:
            raise ValueError("INVALID_MOCKUP_CATEGORY")
        candidates = self.collect_files(files, recursive=False)
        prefix = MOCKUP_PREFIXES[category]
        results = {"success": 0, "failed": 0, "skipped": 0, "items": [], "high": self.registry.high(category)}
        valid: list[tuple[Path, str, str]] = []
        valid_digests: set[str] = set()
        for source in candidates:
            try:
                digest = self.fingerprint(source)
                if self.registry.duplicate_sha_anywhere("mockup", digest):
                    results["skipped"] += 1
                    results["items"].append({"source": str(source), "status": "SKIPPED_DUPLICATE"})
                    continue
                # Two identical files in one multi-select must reserve one
                # number only; upload_records is written after the copy.
                if digest in valid_digests:
                    results["skipped"] += 1
                    results["items"].append({"source": str(source), "status": "SKIPPED_DUPLICATE_BATCH"})
                    continue
                valid.append((source, digest, source.suffix.lower()))
                valid_digests.add(digest)
            except Exception as exc:
                results["failed"] += 1
                results["items"].append({"source": str(source), "status": "ERROR", "error": str(exc)})
        numbers = self.registry.preview_numbers(category, len(valid)) if valid else []
        names = [f"{prefix}_{number:03d}{ext}" for number, (_, _, ext) in zip(numbers, valid)]
        if valid:
            numbers = self.registry.reserve(category, names, "mockup", [x[0] for x in valid], [x[2] for x in valid])
            names = [f"{prefix}_{number:03d}{ext}" for number, (_, _, ext) in zip(numbers, valid)]
            self.registry.set_reserved_names(category, numbers, names)
        for idx, (source, digest, ext) in enumerate(valid):
            number, name = numbers[idx], names[idx]
            work = self._mockup_directory(category, "2_SABLON_HAVUZU") / name
            backup = self._mockup_directory(category, "2_SABLON_HAVUZU_ORIJINAL_YEDEK") / name
            try:
                if not backup.exists(): _create_copy(source, backup, digest)
                if not work.exists(): _create_copy(source, work, digest)
                state = self._mockup_db_registration(category, name)
                draft_proposed = self._auto_propose_corners(category, name, work)
                self.registry.record(kind="mockup", scope=category, number=number, source=source,
                                     destination=work, extension=ext, digest=digest, status=state)
                results["success"] += 1
                results["items"].append({"source": str(source), "status": state, "name": name,
                                          "draft": bool(draft_proposed)})
            except Exception as exc:
                results["failed"] += 1
                self.registry.record(kind="mockup", scope=category, number=number, source=source,
                                     destination=work, extension=ext, digest=digest, status="ERROR", error=str(exc))
                results["items"].append({"source": str(source), "status": "ERROR", "name": name, "error": str(exc)})
            if progress: progress(idx + 1, len(valid), results["items"][-1])
        results["high"] = self.registry.high(category)
        return results

    def upload_designs(self, orientation: str, files: Iterable[Path], prefix: str = "",
                       source_root: Path | None = None, progress: Callable | None = None) -> dict:
        if orientation not in ORIENTATIONS:
            raise ValueError("INVALID_ORIENTATION")
        candidates = self.collect_files(files, recursive=True)
        clean_prefix = safe_prefix(prefix)
        stem_prefix = (clean_prefix + "_") if clean_prefix else ""
        target_root = self.runtime / "HAM BASKI TASARIMLARI" / (orientation + "lar")
        valid: list[tuple[Path, str, str, Path]] = []
        valid_digests: set[str] = set()
        results = {"success": 0, "failed": 0, "skipped": 0, "items": [], "high": self.registry.high(orientation)}
        for source in candidates:
            try:
                digest = self.fingerprint(source)
                if self.registry.duplicate_sha("design", digest):
                    results["skipped"] += 1
                    results["items"].append({"source": str(source), "status": "SKIPPED_DUPLICATE"})
                    continue
                if digest in valid_digests:
                    results["skipped"] += 1
                    results["items"].append({"source": str(source), "status": "SKIPPED_DUPLICATE_BATCH"})
                    continue
                relative_parent = Path()
                if source_root is not None:
                    try:
                        # Folder import retains the selected folder as the
                        # first child (Dini Motifler -> Yataylar/Dini Motifler)
                        # and then preserves every nested subfolder below it.
                        relative_parent = Path(source_root.name) / source.parent.resolve().relative_to(Path(source_root).resolve())
                    except ValueError:
                        relative_parent = Path()
                valid.append((source, digest, source.suffix.lower(), relative_parent))
                valid_digests.add(digest)
            except Exception as exc:
                results["failed"] += 1
                results["items"].append({"source": str(source), "status": "ERROR", "error": str(exc)})
        numbers = self.registry.preview_numbers(orientation, len(valid)) if valid else []
        names = [f"{stem_prefix}{ORIENTATION_PREFIXES[orientation]}{number:03d}{ext}"
                 for number, (_, _, ext, _) in zip(numbers, valid)]
        if valid:
            numbers = self.registry.reserve(orientation, names, "design", [x[0] for x in valid], [x[2] for x in valid])
            names = [f"{stem_prefix}{ORIENTATION_PREFIXES[orientation]}{number:03d}{ext}"
                     for number, (_, _, ext, _) in zip(numbers, valid)]
            self.registry.set_reserved_names(orientation, numbers, names)
        for idx, (source, digest, ext, relative_parent) in enumerate(valid):
            number, name = numbers[idx], names[idx]
            destination = target_root / relative_parent / name
            try:
                _create_copy(source, destination, digest)
                self.registry.record(kind="design", scope=orientation, number=number, source=source,
                                     destination=destination, extension=ext, digest=digest, status="ACTIVE")
                results["success"] += 1
                results["items"].append({"source": str(source), "status": "ACTIVE", "name": str(destination.relative_to(target_root))})
            except Exception as exc:
                results["failed"] += 1
                self.registry.record(kind="design", scope=orientation, number=number, source=source,
                                     destination=destination, extension=ext, digest=digest, status="ERROR", error=str(exc))
                results["items"].append({"source": str(source), "status": "ERROR", "name": name, "error": str(exc)})
            if progress: progress(idx + 1, len(valid), results["items"][-1])
        results["high"] = self.registry.high(orientation)
        return results

    def preview(self, kind: str, scope: str, count: int, prefix: str = "",
                extensions: Iterable[str] | None = None) -> list[str]:
        numbers = self.registry.preview_numbers(scope, max(0, int(count)))
        exts = list(extensions or [])
        if not exts:
            exts = [".png"] * len(numbers)
        elif len(exts) < len(numbers):
            exts.extend([exts[-1] if exts else ".png"] * (len(numbers) - len(exts)))
        if kind == "mockup":
            return [f"{MOCKUP_PREFIXES[scope]}_{n:03d}{exts[i]}" for i, n in enumerate(numbers)]
        safe = safe_prefix(prefix)
        lead = (safe + "_") if safe else ""
        return [f"{lead}{ORIENTATION_PREFIXES[scope]}{n:03d}{exts[i]}" for i, n in enumerate(numbers)]

