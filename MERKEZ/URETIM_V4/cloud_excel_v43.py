"""Explicit opt-in cloud URLs for existing, SHA-verified V4 mockups.

Legacy business contract: successful ImageKit/ImgBB/FreeImage HTTPS image URL
(verified against the original bytes) -> SKU-matched Excel 'Resim Linki' column.
No marketplace publishing. No renderer invocation.
When an operator supplies the blank Trendyol template, the same explicit action
also creates one store workbook per store; no generic duplicate workbook is made.
"""
from __future__ import annotations
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
from io import StringIO
import tempfile
from datetime import datetime
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable
from urllib.parse import urlparse

import requests
try:
    from PIL import Image
except ImportError:  # pragma: no cover - runtime dependency is optional for legacy ImgBB
    Image = None
from openpyxl import Workbook, load_workbook
from PETEK_V3 import engine as petek_engine
from .store_identity_v485 import (store_codes, trendyol_codes, design_number,
                                   petek_measurement_codes, excel_row_sort_key)

REMOTE_HEADERS = [
    "Stok Kodu", "Barkod", "Model Kodu", "Kategori", "Ham Baskı Dosyası",
    "Mağaza Grubu", "Ürün Adı", "Açıklama", "Mockup Dosya Adı",
    "Resim Linki", "Eklenme Zamanı", "Yerel Dosya", "Görsel SHA256", "Bulut Durumu",
]


def _store_id_from_output(output: Path, output_root: Path) -> str:
    """Resolve store id without mistaking the external namespace for a store."""
    parts = Path(output).resolve().relative_to(Path(output_root).resolve()).parts
    if parts and parts[0] == 'HARICI':
        if len(parts) < 3:
            raise ValueError('HARICI çıktı yolu mağaza segmenti içermiyor')
        return parts[2]
    if not parts:
        raise ValueError('Çıktı yolu mağaza segmenti içermiyor')
    return parts[0]


IMAGEKIT_ENDPOINT = "https://ik.imagekit.io/gorseluretimerkezi/"
IMAGEKIT_UPLOAD_ENDPOINT = "https://upload.imagekit.io/api/v1/files/upload"


def _load_cloud_config(runtime_root: Path | None) -> dict:
    cfg = {}
    # Legacy source of truth: <runtime>/ayarlar.json contains bulut_ayarlari.
    if runtime_root:
        config = Path(runtime_root) / "ayarlar.json"
        if config.is_file() and not config.is_symlink():
            try:
                cfg = json.loads(config.read_text(encoding="utf-8")).get("bulut_ayarlari", {})
            except (OSError, ValueError, AttributeError):
                cfg = {}
    # Secrets may come from the ignored local settings file or environment;
    # never put the ImageKit private key in source-controlled config.
    local = (Path(runtime_root) / "ayarlar.local.json") if runtime_root else None
    if local and local.is_file() and not local.is_symlink():
        try:
            local_cfg = json.loads(local.read_text(encoding="utf-8")).get("bulut_ayarlari", {})
            cfg = {**cfg, **local_cfg}
        except (OSError, ValueError, AttributeError):
            pass
    return cfg


def _as_key_list(value) -> list[str]:
    if isinstance(value, str):
        values = value.split(',')
    elif isinstance(value, (list, tuple)):
        values = list(value)
    else:
        values = []
    return [str(item).strip() for item in values if str(item).strip()]


def _keys(runtime_root: Path | None):
    cfg = _load_cloud_config(runtime_root)
    ikeys = _as_key_list(cfg.get("imgbb_keys")) or _as_key_list(os.getenv("IMGBB_KEYS", ""))
    imagekit_keys = _as_key_list(cfg.get("imagekit_private_keys"))
    if not imagekit_keys:
        imagekit_keys = _as_key_list(cfg.get("imagekit_private_key")) or _as_key_list(os.getenv("IMAGEKIT_PRIVATE_KEY", ""))
    freeimage_keys = _as_key_list(cfg.get("freeimage_keys"))
    if not freeimage_keys:
        freeimage_keys = _as_key_list(cfg.get("freeimage_key")) or _as_key_list(os.getenv("FREEIMAGE_KEY", ""))
    provider = str(cfg.get("provider") or os.getenv("IMAGE_UPLOAD_PROVIDER", "imgbb")).strip().lower()
    return ([str(k).strip() for k in ikeys if str(k).strip()],
            freeimage_keys, imagekit_keys, provider)


def _valid_https_image_url(url: str) -> bool:
    if not isinstance(url, str) or len(url) > 2048:
        return False
    u = urlparse(url)
    if (u.scheme != "https" or not u.hostname or u.username is not None
            or u.password is not None or u.fragment or any(ord(c)<32 for c in url)):
        return False
    import ipaddress
    try:
        addr=ipaddress.ip_address(u.hostname)
    except ValueError:
        if u.hostname.lower() in ('localhost',) or u.hostname.lower().endswith(('.localhost','.local')):
            return False
    else:
        if not addr.is_global:
            return False
    return True


def upload_https(path: Path, imgbb_keys: list[str], freeimage_key: str):
    """Legacy official endpoints, with failover; no keys, response bodies or tokens logged.

    Every candidate URL must serve the exact original bytes (and dimensions/
    format when Pillow is available) before it can reach the ledger or Excel —
    the same standard as the ImageKit path.  A receipt is returned as
    ``(url, meta)``; callers must also accept a bare string from legacy mocks.
    On any failure the next key/provider is tried automatically.
    """
    for key in imgbb_keys:
        try:
            with path.open("rb") as f:
                response = requests.post("https://api.imgbb.com/1/upload",
                                         data={"key": key}, files={"image": f}, timeout=30)
            if response.status_code == 200:
                url = str((response.json().get("data") or {}).get("url") or "")
                if _valid_https_image_url(url):
                    try:
                        return _verify_remote_original(path, url, 'IMGBB')
                    except Exception:
                        # Remote bytes/format mismatch or unreadable CDN: treat
                        # as a failed route, never write a bad link.
                        continue
        except (requests.RequestException, OSError, ValueError, AttributeError):
            continue
    if freeimage_key:
        try:
            with path.open("rb") as f:
                response = requests.post("https://freeimage.host/api/1/upload",
                    data={"key": freeimage_key, "action": "upload", "format": "json"},
                    files={"source": f}, timeout=30)
            if response.status_code == 200:
                url = str((response.json().get("image") or {}).get("url") or "")
                if _valid_https_image_url(url):
                    try:
                        return _verify_remote_original(path, url, 'FREEIMAGE')
                    except Exception:
                        return None
        except (requests.RequestException, OSError, ValueError, AttributeError):
            pass
    return None


def _imagekit_original_url(url: str) -> str:
    """Request ImageKit's untouched source object, retaining the original URL."""
    joiner = '&' if '?' in url else '?'
    return url + joiner + 'tr=orig-true'


def _verify_remote_original(path: Path, url: str, label: str = 'REMOTE',
                             retries: int = 3, base_delay: float = 1.0) -> tuple[str, dict]:
    """Verify remote bytes and dimensions before a link can enter the ledger.

    ``label`` only namespaces the error codes so provider failures stay
    readable in reports; the verification itself is provider-agnostic.
    The GET is retried a few times because freshly uploaded CDN objects may
    not be readable at every edge node immediately.
    """
    last_exc = None
    for attempt in range(1, max(1, retries) + 1):
        try:
            response = requests.get(url, timeout=45, allow_redirects=True)
            response.raise_for_status()
            data = response.content
            digest = hashlib.sha256(data).hexdigest()
            expected = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest != expected:
                raise RuntimeError(f'{label}_REMOTE_SHA256_MISMATCH')
            meta = {'sha256': digest, 'bytes': len(data)}
            if Image is not None:
                from io import BytesIO
                with Image.open(BytesIO(data)) as remote, Image.open(path) as source:
                    if remote.size != source.size:
                        raise RuntimeError(f'{label}_REMOTE_DIMENSIONS_MISMATCH')
                    if (remote.format or '').upper() != (source.format or '').upper():
                        raise RuntimeError(f'{label}_REMOTE_FORMAT_MISMATCH')
                    meta.update({'width': remote.width, 'height': remote.height, 'format': remote.format})
            return url, meta
        except Exception as exc:
            last_exc = exc
            if attempt < max(1, retries):
                time.sleep(base_delay * (2 ** (attempt - 1)))
    raise last_exc


def upload_to_imagekit(path: Path, private_key: str) -> tuple[str, dict]:
    if not private_key:
        raise RuntimeError('IMAGEKIT_PRIVATE_KEY_MISSING')
    # A basename is deliberately used: ImageKit receives the original bytes;
    # the local SKU/path remains the authoritative identity in the ledger.
    with path.open('rb') as handle:
        response = requests.post(
            IMAGEKIT_UPLOAD_ENDPOINT,
            auth=(private_key, ''),
            data={'fileName': path.name, 'useUniqueFileName': 'false', 'tags': 'gorsel-uretim-merkezi'},
            files={'file': (path.name, handle, 'application/octet-stream')}, timeout=60)
    response.raise_for_status()
    remote = str((response.json() or {}).get('url') or '')
    if not _valid_https_image_url(remote):
        raise RuntimeError('IMAGEKIT_INVALID_RESPONSE_URL')
    return _verify_remote_original(path, _imagekit_original_url(remote), 'IMAGEKIT')


def _provider_config(runtime_root: Path | None):
    keys, freeimage_keys, imagekit_keys, provider = _keys(runtime_root)
    if provider not in {'imgbb', 'imagekit', 'freeimage'}:
        raise RuntimeError('IMAGE_UPLOAD_PROVIDER_INVALID')
    return provider, keys, freeimage_keys, imagekit_keys


def _provider_routes(runtime_root: Path | None) -> list[dict]:
    """Return ordered provider/key routes for per-file failover.

    The local ignored settings file may define ``provider_order`` plus
    ``imagekit_private_keys``, ``imgbb_keys`` and ``freeimage_keys``.  Legacy
    singular fields remain supported.  A route is considered available only
    when it has at least one key, so a missing provider never blocks the next.
    """
    cfg = _load_cloud_config(runtime_root)
    imgbb, freeimage, imagekit, primary = _keys(runtime_root)
    configured = _as_key_list(cfg.get('provider_order'))
    # The failover contract is intentionally canonical.  A local setting may
    # limit the enabled providers, but it may not silently move ImgBB ahead of
    # ImageKit (or FreeImage ahead of ImgBB).
    requested = set(configured) if configured else {'imagekit', 'imgbb', 'freeimage'}
    if not configured and primary in {'imagekit', 'imgbb', 'freeimage'}:
        requested.add(primary)
    order = [provider for provider in ('imagekit', 'imgbb', 'freeimage')
             if provider in requested]
    routes = []
    seen = set()
    for provider in order:
        provider = str(provider).strip().lower()
        if provider in seen:
            continue
        seen.add(provider)
        if provider == 'imagekit' and imagekit:
            routes.append({'provider': provider, 'keys': imagekit})
        elif provider == 'imgbb' and imgbb:
            routes.append({'provider': provider, 'keys': imgbb})
        elif provider == 'freeimage' and freeimage:
            routes.append({'provider': provider, 'keys': freeimage})
    if not routes:
        raise RuntimeError('IMAGE_UPLOAD_NO_USABLE_ROUTE')
    return routes


def _upload_with_failover(path: Path, routes: list[dict], upload_fn=None):
    """Try every configured key/provider in order; return URL + receipt metadata."""
    if upload_fn is None:
        upload_fn = upload_https
    attempts = []
    for route in routes:
        provider = route['provider']
        for index, key in enumerate(route['keys'], 1):
            try:
                if provider == 'imagekit':
                    url, meta = upload_to_imagekit(path, key)
                elif provider == 'imgbb':
                    raw = upload_fn(path, [key], '')
                    if isinstance(raw, tuple):
                        url, meta = raw
                    else:
                        url, meta = raw, {}
                else:
                    raw = upload_fn(path, [], key)
                    if isinstance(raw, tuple):
                        url, meta = raw
                    else:
                        url, meta = raw, {}
                if url and _valid_https_image_url(url):
                    return provider, url, meta, attempts
                raise RuntimeError('INVALID_HTTPS_URL')
            except Exception as exc:
                # Never include key material or provider response bodies.
                attempts.append({'provider': provider, 'key_index': index,
                                 'error': type(exc).__name__ + ': ' + str(exc)[:180]})
    error = RuntimeError('ALL_UPLOAD_ROUTES_FAILED')
    error.attempts = attempts
    raise error


def _head_check(url: str, timeout: float = 8.0) -> tuple[bool, str]:
    """Cheap liveness check for a cloud link without downloading the image.

    Tries a HEAD request first; falls back to a 1-byte ``Range`` GET for CDNs
    that refuse or mis-answer HEAD.  Returns ``(ok, reason)``.  Any non-image
    Content-Type HTML/text response is treated as dead, because a marketplace
    thumbnail page in place of a product image breaks the store listing.
    """
    try:
        response = requests.head(url, timeout=timeout, allow_redirects=True)
        if response.status_code >= 400 or response.status_code in (0, 405, 501):
            get = requests.get(url, headers={'Range': 'bytes=0-0'}, timeout=timeout,
                               stream=True, allow_redirects=True)
            try:
                code = get.status_code
                ctype = (get.headers.get('Content-Type') or '').lower()
            finally:
                get.close()
            if code not in (200, 206):
                return False, f'dead_{code}'
            if 'text/html' in ctype or 'text/plain' in ctype:
                return False, 'not_image'
            return True, 'range_ok'
        ctype = (response.headers.get('Content-Type') or '').lower()
        if 'text/html' in ctype or 'text/plain' in ctype:
            return False, 'not_image'
        if response.status_code in (200, 201, 202, 203, 206, 304):
            return True, 'head_ok'
        if response.status_code in (301, 302):
            # Redirect followed already; if we are here the URL is bad.
            return False, f'dead_{response.status_code}'
        return False, f'dead_{response.status_code}'
    except Exception as exc:
        # Treat anything unreachable/misbehaving as unusable so the caller can
        # re-link the exact file instead of publishing a broken image.
        return False, f'unreachable_{type(exc).__name__}'


def _provider_url_matches(provider: str, url: str) -> bool:
    """Reject a receipt whose URL belongs to a different provider/variant."""
    host = (urlparse(str(url)).hostname or '').lower()
    if provider == 'imagekit':
        return host.endswith('imagekit.io') and 'tr=orig-true' in str(url)
    # ImgBB/FreeImage have historically returned several valid CDN domains;
    # their HTTPS URL plus the recorded remote SHA is the stable contract.
    if provider in {'imgbb', 'freeimage'}:
        return bool(host)
    return False


def _retry_upload(fn, attempts: int = 3):
    """Bounded exponential retry for transient provider/network failures."""
    last = None
    for attempt in range(attempts):
        try:
            return fn()
        except Exception as exc:  # provider-specific exceptions are normalized by caller
            last = exc
            if attempt + 1 < attempts:
                time.sleep(0.5 * (2 ** attempt))
    raise last


def _escape(value):
    v = str(value or "")
    return "'" + v if v.lstrip().startswith(("=", "+", "-", "@")) else v


class CloudExcel:
    def __init__(self, root: Path, reports: Path, runtime_root: Path | None = None):
        self.root = Path(root)
        self.reports = Path(reports)
        self.runtime_root = runtime_root
        self.state = self.root / "cloud_urls_v43.sqlite3"
        self.root.mkdir(parents=True, exist_ok=True)
        self.reports.mkdir(parents=True, exist_ok=True)
        if self.state.is_symlink():
            raise ValueError("Bulut link DB symlink olamaz")
        with self.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS cloud_link (
                artifact_key TEXT PRIMARY KEY,
                output_sha TEXT NOT NULL,
                url TEXT NOT NULL,
                recorded_at TEXT DEFAULT CURRENT_TIMESTAMP,
                provider TEXT DEFAULT 'imgbb',
                remote_sha TEXT,
                remote_width INTEGER,
                remote_height INTEGER,
                remote_format TEXT
            )""")
            cols = {r[1] for r in db.execute('PRAGMA table_info(cloud_link)')}
            for name, definition in (('provider', "TEXT DEFAULT 'imgbb'"), ('remote_sha', 'TEXT'),
                                     ('remote_width', 'INTEGER'), ('remote_height', 'INTEGER'), ('remote_format', 'TEXT')):
                if name not in cols:
                    db.execute(f'ALTER TABLE cloud_link ADD COLUMN {name} {definition}')

    def connect(self):
        c = sqlite3.connect(self.state, timeout=30)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA busy_timeout=30000")
        return c

    def available(self):
        try:
            _provider_routes(self.runtime_root)
            return True
        except RuntimeError:
            return False

    def upload_one(self, row: dict, *, notify: Callable = lambda _x: None) -> str:
        """Upload one already verified output for streaming production.

        This deliberately does not write Excel; the finalizer writes one
        complete workbook after production drains the queue.
        """
        routes = _provider_routes(self.runtime_root)
        path = Path(row['output'])
        safe_root = (self.root / 'uretilen_gorseller').resolve()
        if (path.is_symlink() or safe_root not in path.resolve(strict=False).parents
                or not path.is_file() or petek_engine.digest(path) != row['output_sha']):
            raise RuntimeError(f"SHA/çıktı uyuşmazlığı: {row.get('sku', row.get('key', '—'))}")
        live_url, live_reason = self._live_url_for(row)
        if live_url:
            return 'reused'
        if live_reason != 'missing':
            notify(f"Kayıtlı link ölü/geçersiz ({live_reason}), yeniden yükleniyor: {row.get('sku', row.get('key', '—'))}")
        borrowed = self._verified_receipt_for_sha(row['output_sha'])
        if borrowed is not None:
            # Identical bytes already verified in the cloud: reuse that receipt
            # instead of uploading the same image again.
            self._store_receipt(row['key'], row['output_sha'], borrowed['url'],
                                borrowed['provider'], borrowed['meta'])
            notify(f"Aynı görselin doğrulanmış linki yeniden kullanıldı: {row.get('sku', row.get('key', '—'))}")
            return 'reused'
        provider, url, meta, _attempts = _upload_with_failover(path, routes)
        self._store_receipt(row['key'], row['output_sha'], url, provider, meta)
        notify(f"HTTPS link oluşturuldu: {row.get('sku', row.get('key', '—'))}")
        return 'uploaded'

    def _store_receipt(self, key, output_sha, url, provider, meta):
        """Write one verified receipt row; used by every reuse/upload path."""
        with self.connect() as c:
            c.execute("""INSERT OR REPLACE INTO cloud_link
                       (artifact_key, output_sha, url, provider, remote_sha, remote_width, remote_height, remote_format)
                       VALUES(?,?,?,?,?,?,?,?)""",
                      (key, output_sha, url, provider, (meta or {}).get('sha256'), (meta or {}).get('width'),
                       (meta or {}).get('height'), (meta or {}).get('format')))

    def _verified_receipt_for_sha(self, output_sha):
        """Return the earliest fully verified receipt for these exact bytes.

        A receipt is only borrowed when the provider provably served the same
        bytes (``remote_sha == output_sha``) and the URL is still well formed,
        so the same image is never uploaded twice under a different key.
        """
        with self.connect() as c:
            r = c.execute("""SELECT artifact_key, output_sha, url, provider, remote_sha,
                                     remote_width, remote_height, remote_format
                              FROM cloud_link
                              WHERE output_sha = ? AND remote_sha IS NOT NULL AND remote_sha = output_sha
                              ORDER BY recorded_at ASC LIMIT 1""", (output_sha,)).fetchone()
        if not r:
            return None
        provider = str(r['provider'] or '').split(':', 1)[0].strip().lower()
        if not _valid_https_image_url(r['url']):
            return None
        if provider in {'imagekit', 'imgbb', 'freeimage'} and not _provider_url_matches(provider, r['url']):
            return None
        if not _head_check(r['url'])[0]:
            # A verified receipt for identical bytes is worthless if the CDN
            # object is gone today.
            return None
        return {'url': r['url'], 'provider': provider,
                'meta': {'sha256': r['remote_sha'], 'width': r['remote_width'],
                         'height': r['remote_height'], 'format': r['remote_format']}}

    def _url_for(self, row):
        with self.connect() as c:
            r = c.execute("SELECT output_sha, url, provider, remote_sha FROM cloud_link WHERE artifact_key=?", (row["key"],)).fetchone()
        if not r or r["output_sha"] != row["output_sha"] or not _valid_https_image_url(r["url"]):
            return None
        if r["remote_sha"] and r["remote_sha"] != row["output_sha"]:
            return None
        provider = str(r["provider"] or '').split(':', 1)[0].strip().lower()
        if provider in {'imagekit', 'imgbb', 'freeimage'} and not _provider_url_matches(provider, r["url"]):
            return None
        if provider == 'imagekit' and 'tr=orig-true' not in str(r["url"]):
            return None
        if r:
            return r["url"]
        return None

    def _live_url_for(self, row):
        """Reuse rule for an existing receipt: shape check + live HEAD check.

        Returns ``(url_or_none, reason)``.  A dead link must never be written
        to Excel as-is; the caller falls back to a real re-upload.
        """
        url = self._url_for(row)
        if not url:
            return None, 'missing'
        ok, reason = _head_check(url)
        if not ok:
            return None, reason
        return url, 'ok'

    def publish_existing(self, successful_rows: list[dict], *, notify: Callable = lambda _x: None,
                         stop: threading.Event | None = None, upload_fn=upload_https,
                         progress: Callable = lambda _x: None,
                         trend_template: Path | None = None,
                         exclude_clean_petek: bool = False):
        """Only explicit user action; read existing rendered artifacts; no marketplace API."""
        routes = _provider_routes(self.runtime_root)
        configured_provider = routes[0]['provider']
        provider = configured_provider if len(routes) == 1 else 'failover:' + ','.join(r['provider'] for r in routes)
        lock = self.root / "V43_BULUT_LINKLEME.lock"
        try:
            fd = os.open(str(lock), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError as ex:
            raise RuntimeError("Bulut Excel linkleme zaten çalışıyor; mevcut işlem durmadan ikinci yükleme başlatılmaz.") from ex
        # ``failed`` is reserved for a provider/network failure.  A rendered
        # receipt whose local PNG disappeared is a different, local integrity
        # condition and must not be reported as an ImageKit upload failure.
        counters = {"uploaded": 0, "reused": 0, "failed": 0, "missing": 0, "skipped": 0}
        errors = []
        original_count=len(successful_rows)
        if exclude_clean_petek:
            # In overlay mode the clean PETEK image is an immutable source,
            # never a cloud/Excel product.  Overlay rows are explicitly marked
            # ``artifact_kind=overlay`` by the batch ledger.
            successful_rows = [row for row in successful_rows if not (
                row.get('category') == '06_Petek_Kapama' and
                str(row.get('artifact_kind') or 'clean') == 'clean'
            )]
        distinct={}
        for item in successful_rows:
            k=str(item['key'])
            if k in distinct and distinct[k].get('output_sha')!=item.get('output_sha'):
                raise ValueError('BULUT_DUPLICATE_KEY_SHA_CONFLICT')
            distinct[k]=item
        # Deterministic queue and export order.  Each value remains a complete
        # ledger record, so its URL/SHA/path/code fields cannot be mismatched.
        successful_rows=sorted(distinct.values(), key=excel_row_sort_key)
        counters['skipped'] = original_count - len(successful_rows)
        # Wall-clock time can jump when Windows synchronizes its clock.  A
        # monotonic clock keeps the live elapsed/ETA values stable while the
        # network workers are running.
        progress_started = time.monotonic()
        excel_clock: dict[str, float | None] = {"started": None}
        total = len(successful_rows)

        def emit(operation='', *, completed=0, outcome='running', force=False,
                 phase='upload', excel_index=None, excel_total=None,
                 excel_item=None, excel_item_total=None):
            elapsed = max(0.0, time.monotonic() - progress_started)
            eta = None
            if completed and completed < total and elapsed > 0:
                eta = elapsed * (total - completed) / completed
            payload = {'completed': completed, 'total': total, 'elapsed_seconds': elapsed,
                       'eta_seconds': eta, 'operation': operation, 'outcome': outcome,
                       'index': int(completed),
                       'uploaded': counters['uploaded'], 'reused': counters['reused'],
                       'failed': counters['failed'], 'missing': counters['missing'],
                       'skipped': counters['skipped'],
                       'stage': 'excel' if phase == 'excel' else 'linkleme',
                       'phase': phase, 'force': force}
            if excel_total is not None:
                # Excel aşaması kendi alt-ilerlemesini (mağaza/adım ve kayıt
                # sayacı) her zaman dolu taşır; GUI çubuğu bu gerçek
                # sinyalle hareket eder, tahminle değil.
                x_index = max(0, int(excel_index or 0))
                x_total = max(1, int(excel_total))
                x_item = max(0, int(excel_item or 0))
                x_item_total = max(0, int(excel_item_total or 0))
                started = excel_clock['started']
                if started is not None:
                    x_elapsed = max(0.0, time.monotonic() - started)
                    item_frac = (x_item / x_item_total) if x_item_total else 0.0
                    done_units = min(float(x_total), x_index + item_frac)
                    remaining = x_total - done_units
                    if done_units > 0:
                        payload['eta_seconds'] = round(x_elapsed * remaining / done_units, 1)
                    else:
                        payload['eta_seconds'] = None
                payload['excel_index'] = x_index
                payload['excel_total'] = x_total
                payload['excel_item'] = x_item
                payload['excel_item_total'] = x_item_total
            progress(payload)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(str(os.getpid()))
            emit('Bulut linkleme kuyruğu hazırlanıyor', force=True)
            completed = 0
            # In-flight registry: identical bytes (same output_sha) are uploaded
            # exactly once per run.  The first worker becomes the leader; the
            # rest wait for it and copy its verified receipt, so a duplicate
            # image never consumes a second upload slot.
            sha_inflight: dict[str, dict] = {}
            sha_lock = threading.Lock()

            def do_upload(row):
                path = Path(row['output'])
                safe = (self.root / 'uretilen_gorseller').resolve()
                if path.is_symlink() or safe not in path.resolve(strict=False).parents:
                    return row, None, {}, 'güvensiz_çıktı_yolu', provider, []
                if not path.exists() or not path.is_file():
                    return row, None, {}, 'eksik_yerel_çıktı', provider, []
                if petek_engine.digest(path) != row['output_sha']:
                    return row, None, {}, 'yerel_sha_uyuşmazlığı', provider, []
                live_url, live_reason = self._live_url_for(row)
                if live_url:
                    return row, live_url, {}, 'reused', provider, []
                if live_reason != 'missing':
                    # The saved link is dead/forbidden/unreachable: remember it,
                    # then fall through to re-upload the very same file.
                    stale_url = self._url_for(row)
                    errors.append({"sku": row.get("sku", ""), "key": row.get("key", ""),
                                   "provider": provider, "kind": "STALE_LINK_REUPLOADING",
                                   "reason": f"Kayıtlı link cansız/geçersiz: {live_reason}",
                                   "action": "Aynı görsel yeniden yükleniyor; yeni link kaydedilip Excel bu satıra yazılacak."})
                    notify(f"Ölü link tespit edildi, yeniden yükleniyor: {row.get('sku', row.get('key', '—'))}")
                borrowed = self._verified_receipt_for_sha(row['output_sha'])
                if borrowed is not None:
                    try:
                        self._store_receipt(row['key'], row['output_sha'], borrowed['url'],
                                            borrowed['provider'], borrowed['meta'])
                    except Exception as exc:
                        return row, None, {}, f'{type(exc).__name__}: {exc}', provider, []
                    return row, borrowed['url'], borrowed['meta'], 'reused', borrowed['provider'], []
                sha = row['output_sha']
                with sha_lock:
                    entry = sha_inflight.get(sha)
                    if entry is None:
                        entry = {'event': threading.Event(), 'result': None}
                        sha_inflight[sha] = entry
                        leader = True
                    else:
                        leader = False
                if not leader:
                    got = entry['event'].wait(timeout=600)
                    res = (entry.get('result') or {}) if got else {}
                    url = res.get('url')
                    if url and _valid_https_image_url(url):
                        meta = res.get('meta') or {'sha256': sha}
                        borrowed = {'sha256': meta.get('sha256') or sha, 'width': meta.get('width'),
                                    'height': meta.get('height'), 'format': meta.get('format')}
                        try:
                            self._store_receipt(row['key'], sha, url, res.get('provider') or provider, borrowed)
                        except Exception as exc:
                            return row, None, {}, f'{type(exc).__name__}: {exc}', provider, []
                        return row, url, borrowed, 'reused', res.get('provider') or provider, []
                    attempts = res.get('attempts', [])
                    reason = res.get('error') or ('SAME_SHA_LEADER_TIMEOUT' if not got else 'ALL_UPLOAD_ROUTES_FAILED')
                    return row, None, {}, reason, provider, attempts
                try:
                    used_provider, url, meta, attempts = _upload_with_failover(path, routes, upload_fn=upload_fn)
                    result = {'url': url, 'meta': meta, 'provider': used_provider,
                              'attempts': attempts, 'error': None}
                    done = (row, url, meta, 'uploaded', used_provider, attempts)
                except Exception as exc:
                    attempts = getattr(exc, 'attempts', [])
                    result = {'url': None, 'meta': {}, 'provider': None,
                              'attempts': attempts, 'error': str(exc)}
                    done = (row, None, {}, str(exc), provider, attempts)
                finally:
                    # The finished entry stays in the registry so a worker that
                    # reaches the check after the upload completed still reuses
                    # the verified receipt instead of uploading the same bytes.
                    with sha_lock:
                        entry['result'] = result
                    entry['event'].set()
                return done

            # Uploads are network-bound; bounded workers keep the UI responsive
            # while preserving a single writer for the local link ledger.  The
            # results are consumed as each worker finishes so the GUI receives
            # real progress instead of one burst after every upload completes.
            with ThreadPoolExecutor(max_workers=min(8, max(1, len(successful_rows)))) as pool:
                futures = [pool.submit(do_upload, row) for row in successful_rows]
                for future in as_completed(futures):
                    if stop and stop.is_set():
                        break
                    row, url, meta, outcome, used_provider, attempts = future.result()
                    if outcome in {'eksik_yerel_çıktı', 'yerel_sha_uyuşmazlığı', 'güvensiz_çıktı_yolu'}:
                        counters["missing"] += 1
                        reason_map = {
                            'eksik_yerel_çıktı': 'Yerel çıktı dosyası bulunamadı',
                            'yerel_sha_uyuşmazlığı': 'Yerel çıktı SHA256 kaydıyla eşleşmiyor',
                            'güvensiz_çıktı_yolu': 'Çıktı yolu güvenlik sınırları dışında veya symlink',
                        }
                        reason = reason_map[outcome]
                        errors.append({"sku": row.get("sku", ""), "key": row.get("key", ""),
                                       "reason": reason, "kind": "LOCAL_OUTPUT_INVALID",
                                       "action": "Üretim/çıktı klasörünü ve kayıtlı SHA256 değerini inceleyin; otomatik yeniden üretim yapılmadı."})
                        notify(f"Yerel çıktı kontrolü başarısız: {row['sku']}; buluta gönderilmedi.")
                        completed += 1; emit(f"SHA doğrulama hatası · {row['sku']}", completed=completed, outcome='failed')
                        continue
                    if outcome == 'reused':
                        counters["reused"] += 1
                        completed += 1; emit(f"Mevcut link kullanıldı · {row['sku']}", completed=completed, outcome='success')
                        continue
                    if outcome != 'uploaded' or not url or not _valid_https_image_url(url):
                        counters["failed"] += 1
                        errors.append({"sku": row.get("sku", ""), "key": row.get("key", ""), "provider": provider,
                                       "attempts": attempts,
                                       "reason": f"{provider} yüklemesi başarısız veya geçersiz HTTPS URL",
                                       "action": "Sağlayıcı anahtarını, bağlantıyı ve hata raporundaki nedeni kontrol edip yeniden deneyin."})
                        notify(f"Yükleme başarısız: {row['sku']}; Excel'e geçersiz URL yazılmayacak.")
                        completed += 1; emit(f"Yükleme başarısız · {row['sku']}", completed=completed, outcome='failed')
                        continue
                    # Preserve successful result before Excel export; interrupted
                    # Excel phase can be resumed without another image upload.
                    self._store_receipt(row["key"], row["output_sha"], url, used_provider, meta)
                    counters["uploaded"] += 1
                    notify(f"HTTPS link oluşturuldu: {row['sku']}")
                    completed += 1; emit(f"HTTPS link oluşturuldu · {row['sku']}", completed=completed, outcome='success')
            # Excel aşaması canlı ilerleme: ana (yerel) Excel bir birim, her
            # mağaza Excel'i bir birim. Mağaza listesi önceden hesaplanır ki
            # çubuk/ETA gerçek birim sayısına göre çalışsın.
            safe_root = (self.root / 'uretilen_gorseller').resolve()
            stores = set()
            for row in successful_rows:
                try:
                    parts = Path(row['output']).resolve().relative_to(safe_root).parts
                    if len(parts) >= 3:
                        store_id = _store_id_from_output(row['output'], safe_root)
                        if store_id != 'LOCAL':
                            stores.add(store_id)
                except (ValueError, OSError):
                    continue
            stores = sorted(stores)
            excel_total = len(stores) + 1
            excel_done = 0
            excel_clock['started'] = time.monotonic()
            emit('Excel dosyası yazılıyor', completed=completed, force=True,
                 phase='excel', excel_index=excel_done, excel_total=excel_total)
            try:
                csv_out, xlsx_out, count = self.export(successful_rows)
            finally:
                excel_done += 1
                emit('Ana Excel yazıldı', completed=completed, force=True,
                     phase='excel', excel_index=excel_done, excel_total=excel_total)
            store_xlsx = {}
            from .store_excel_v485 import export_store_upload
            # A user-supplied template is still accepted by the lower-level
            # API, but the normal GUI path passes None and gets a fresh,
            # minimal internal template automatically.
            if stores:
                for store in stores:
                    emit(f'Trendyol Excel yazılıyor · {store}', completed=completed, force=True,
                         phase='excel', excel_index=excel_done, excel_total=excel_total)
                    try:
                        result = export_store_upload(
                            Path(trend_template) if trend_template else None,
                            self.root, store_id=store, report_root=self.reports,
                            records=successful_rows,
                            progress=lambda done, total_recs, _store_id, _done=excel_done, _store=store: emit(
                                f'Trendyol Excel · {_store} · kayıt {done}/{total_recs}',
                                completed=completed, phase='excel',
                                excel_index=_done, excel_total=excel_total,
                                excel_item=done, excel_item_total=total_recs))
                        store_xlsx[store] = result
                    except (ValueError, OSError, RuntimeError) as exc:
                        errors.append({"store": store, "kind": "STORE_EXCEL_EXPORT_FAILED",
                                       "reason": str(exc),
                                       "action": "Mağaza Excel şablonunu, doğrulanmış linkleri ve mağaza raporunu inceleyin."})
                        notify(f'TRENDYOL EXCEL HATASI [{store}]: {exc}')
                    finally:
                        excel_done += 1
                        emit(f'Trendyol Excel adımı bitti · {store}', completed=completed, force=True,
                             phase='excel', excel_index=excel_done, excel_total=excel_total)
            emit('Excel aşaması tamamlandı', completed=completed, force=True,
                 phase='excel', excel_index=excel_total, excel_total=excel_total)
            store_row_count = sum(int(result.get('rows', 0)) for result in store_xlsx.values())
            store_image_count = sum(int(result.get('images', 0)) for result in store_xlsx.values())
            expected_count = len(successful_rows)
            linked_count = int(count)
            missing_count = max(0, expected_count - linked_count)
            error_report = ""
            if errors:
                error_report = self.reports / f"BULUT_LINKLEME_HATALARI_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                petek_engine.atomic_new_file(error_report, json.dumps({"provider": provider, "expected": expected_count, "linked": linked_count,
                    "failed": counters.get("failed", 0), "missing": missing_count,
                    "local_output_invalid": counters.get("missing", 0), "errors": errors}, ensure_ascii=False, indent=2).encode("utf-8"))
            return {**counters, "provider": provider,
                    "success_rate": (linked_count / expected_count) if expected_count else 1.0,
                    "elapsed_seconds": max(0.0, time.monotonic() - progress_started),
                    "linked": linked_count, "expected": expected_count, "missing": missing_count,
                    "store_row_count": store_row_count, "store_image_count": store_image_count,
                    "store_files": list(store_xlsx.values()),
                    "errors": errors, "error_report": str(error_report) if error_report else "",
                    "xlsx": str(xlsx_out) if xlsx_out else "",
                    "csv": str(csv_out) if csv_out else "",
                    "store_xlsx": store_xlsx,
                    "status": "PARTIAL" if (counters["failed"] or counters["missing"]) else ("STOPPED" if stop and stop.is_set() else "LINKS_READY")}
        finally:
            lock.unlink(missing_ok=True)

    def export(self, rows):
        # Store-coded pictures are destined for each store's real marketplace
        # product-upload template, not an EXTRA generic CSV/XLSX report.
        # Keep legacy LOCAL export behavior unchanged for historical users.
        rows = sorted(rows, key=excel_row_sort_key)
        legacy=[];store_linked=0
        for row in rows:
            try:
                parts=Path(row['output']).resolve().relative_to((self.root/'uretilen_gorseller').resolve()).parts
                store=_store_id_from_output(row['output'], self.root/'uretilen_gorseller') if len(parts)>=3 else 'LOCAL'
                expected = None
                if store != 'LOCAL':
                    # New Trendyol identity is the authoritative export code;
                    # accept the legacy ledger SKU as well so old receipts do
                    # not suddenly become a second generic workbook.
                    try:
                        expected_codes = trendyol_codes(design_number(row['art_name']), store, row['category'])
                        if (row.get('artifact_kind') or 'clean') == 'overlay' and row.get('overlay_cm'):
                            expected_codes = petek_measurement_codes(expected_codes, row['overlay_cm'])
                        expected = expected_codes['sku']
                    except (ValueError, KeyError):
                        try:
                            expected_codes = store_codes(design_number(row['art_name']), store, row['category'])
                            if (row.get('artifact_kind') or 'clean') == 'overlay' and row.get('overlay_cm'):
                                expected_codes = petek_measurement_codes(expected_codes, row['overlay_cm'])
                            expected = expected_codes['sku']
                        except (ValueError, KeyError):
                            expected = None
                    if expected != row.get('sku'):
                        try:
                            expected = store_codes(design_number(row['art_name']), store, row['category'])['sku']
                        except (ValueError, KeyError):
                            expected = None
            except (ValueError,KeyError,IndexError,TypeError):expected=None
            if expected and expected==row.get('sku'):
                if self._url_for(row):store_linked+=1
            else:legacy.append(row)
        if not legacy:
            return None,None,store_linked
        rows=legacy
        selected = []
        for row in rows:
            url = self._url_for(row)
            if not url:
                continue
            path = Path(row["output"])
            safe_root=(self.root / 'uretilen_gorseller').resolve()
            resolved=path.resolve(strict=False)
            if (path.is_symlink() or safe_root not in resolved.parents
                    or not path.is_file() or petek_engine.digest(path) != row["output_sha"]):
                continue
            cat = row["category"]
            sku = row["sku"]
            group_name = sku.split("-", 1)[1].rsplit("-", 1)[0] if "-" in sku else "LOCAL"
            selected.append([
                _escape(v) for v in (
                    sku, "DAHILI-" + sku, "M-" + sku, cat, row['art_name'],
                    group_name, f"{cat} - {Path(row['art_name']).stem}",
                    "",  # SEO açıklaması üretilmediyse ASLA uydurma
                    path.name, url, datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
                    str(path), row['output_sha'], "BULUT_LINK_HAZIR")
            ])
        fingerprint = hashlib.sha256("|".join(x[0] + x[9] for x in selected).encode()).hexdigest()[:18]
        csv_out = self.reports / f"ORTAK_7_KATEGORI_{fingerprint}_BULUT_LINKLI.csv"
        xlsx_out = self.reports / f"ORTAK_7_KATEGORI_{fingerprint}_BULUT_LINKLI.xlsx"
        if not csv_out.exists():
            buffer = StringIO(newline="")
            w = csv.writer(buffer); w.writerow(REMOTE_HEADERS); w.writerows(selected)
            petek_engine.atomic_new_file(csv_out, ("\ufeff" + buffer.getvalue()).encode("utf-8"))
        if not xlsx_out.exists():
            wb = Workbook(); ws = wb.active; ws.title = "BULUT_LINKLI_7_KATEGORI"
            ws.freeze_panes = "A2"; ws.append(REMOTE_HEADERS)
            for line in selected:
                ws.append(line)
                cell = ws.cell(ws.max_row, 10)
                cell.hyperlink = line[9]; cell.style = "Hyperlink"
                ws.cell(ws.max_row, 12).hyperlink = Path(line[11]).resolve().as_uri()
                ws.cell(ws.max_row, 12).style = "Hyperlink"
            ws.auto_filter.ref = ws.dimensions
            ws.column_dimensions["J"].width = 68
            ws.column_dimensions["L"].width = 64
            fd, tmp = tempfile.mkstemp(prefix="v43excel-", suffix=".xlsx", dir=str(self.reports))
            os.close(fd)
            try:
                wb.save(tmp)
                petek_engine.atomic_new_file(xlsx_out, Path(tmp).read_bytes())
            finally:
                Path(tmp).unlink(missing_ok=True)
        # Read back and confirm every reported SKU has its exact HTTPS URL.
        wb = load_workbook(xlsx_out)
        try:
            ws = wb.active
            assert ws.max_row == len(selected) + 1
            for n, row in enumerate(selected, 2):
                c = ws.cell(n, 10)
                if c.value != row[9] or c.hyperlink is None or c.hyperlink.target != row[9]:
                    raise RuntimeError("Excel URL/SKU doğrulama hatası: " + row[0])
        finally:
            wb.close()
        return csv_out, xlsx_out, len(selected)
