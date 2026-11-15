"""Shared Tk error explanation with actionable cause/remedy, no automatic data changes.

Single user-visible modal for blocking UI operations; bulk-file failures remain in log.
Never trigger repair commands without a separate, verified user action.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import tempfile
import threading
import traceback
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from tkinter import messagebox

try:
    import numpy as _np
except Exception:  # pragma: no cover - numpy is optional for the desktop shell
    _np = None

_NATIVE_SHOWERROR = messagebox.showerror
_INSTALLED = False
_LOCK = threading.RLock()
_LAST_REPORT = None
_LISTENERS = []
_CONTEXT_PROVIDER = None
_MAX_REPORTS = 50
_MAX_BYTES = 20 * 1024 * 1024
_MAX_DIAGNOSTIC_LOCATIONS = 200
_STAGE_LOCAL = threading.local()


def _report_root():
    root = Path(os.environ.get('LOCALAPPDATA') or (Path.home() / '.gorsel_mockup'))
    return root / 'GorselMockup' / 'ErrorReports'


def _sanitize(value):
    """Mask credentials and keep reports small enough to share safely."""
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            key_text = str(key)
            if re.search(r'(api[_-]?key|token|secret|password|credential|authorization)', key_text, re.I):
                result[key_text] = '[REDACTED]'
            else:
                result[key_text] = _sanitize(item)
        return result
    if isinstance(value, (list, tuple)):
        return [_sanitize(item) for item in value[:100]]
    if isinstance(value, str):
        text = value[:12000]
        text = re.sub(r'(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+', r'\1[REDACTED]', text)
        text = re.sub(r'(?i)(sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9_]{12,}|xox[baprs]-[A-Za-z0-9-]{12,})', '[REDACTED]', text)
        text = re.sub(r'(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*[^\s,;]+', r'\1=[REDACTED]', text)
        return text
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)[:12000]


def _as_array(value):
    """Return a small, read-only numpy view for diagnostic comparisons.

    Diagnostics must never mutate a render buffer.  Paths and PIL images are
    accepted as a convenience, while failures deliberately return ``None`` so
    reporting an error can never hide the original failure.
    """
    if _np is None or value is None:
        return None
    try:
        if isinstance(value, (str, os.PathLike, Path)):
            from PIL import Image
            with Image.open(value) as image:
                value = _np.asarray(image.convert('RGBA' if image.mode == 'RGBA' else 'L'))
        elif hasattr(value, 'toarray'):
            value = value.toarray()
        array = _np.asarray(value)
        if array.ndim == 0:
            return None
        return array.copy()
    except Exception:
        return None


def _pixel_difference(expected, actual, *, tolerance=0, region_mask=None,
                      max_locations=_MAX_DIAGNOSTIC_LOCATIONS):
    """Compare two masks/images and return bounded, JSON-safe pixel evidence.

    Coordinates are emitted as ``[x, y]`` pairs (the convention used by the
    editor), while the bounding box is ``[x_min, y_min, x_max, y_max]``.  A
    region mask can restrict the comparison to pixels belonging to a failed
    operation, without changing either input buffer.
    """
    left, right = _as_array(expected), _as_array(actual)
    result = {
        'status': 'NOT_MEASURED',
        'available': False,
        'expected_shape': list(left.shape) if left is not None else None,
        'actual_shape': list(right.shape) if right is not None else None,
        'total_pixels': 0,
        'matching_pixels': 0,
        'mismatched_pixels': 0,
        'mismatch_ratio': 0.0,
        'max_delta': 0.0,
        'mean_delta': 0.0,
        'tolerance': int(max(0, tolerance or 0)),
        'coordinates': [],
        'bounding_box': None,
    }
    if left is None or right is None:
        result['reason'] = 'EXPECTED_OR_ACTUAL_PIXEL_BUFFER_UNAVAILABLE'
        return result
    if left.shape != right.shape:
        result['status'] = 'SHAPE_MISMATCH'
        result['reason'] = 'EXPECTED_ACTUAL_SHAPE_MISMATCH'
        return result
    try:
        if left.ndim >= 3:
            delta = _np.max(_np.abs(left.astype(_np.float64) - right.astype(_np.float64)), axis=-1)
        else:
            delta = _np.abs(left.astype(_np.float64) - right.astype(_np.float64))
        different = delta > float(max(0, tolerance or 0))
        region = None
        if region_mask is not None:
            region = _as_array(region_mask)
            if region is None or region.shape[:2] != different.shape[:2]:
                result['status'] = 'REGION_MASK_MISMATCH'
                result['reason'] = 'REGION_MASK_SHAPE_MISMATCH'
                return result
            active_region = region[..., 0] > 0 if region.ndim >= 3 else region > 0
            different &= active_region
        total = int(different.size if region is None else _np.count_nonzero(active_region))
        measured_delta = delta if region is None else delta[active_region]
        ys, xs = _np.where(different)
        count = int(len(xs))
        result.update({
            'status': 'FAIL' if count else 'PASS',
            'available': True,
            'total_pixels': total,
            'matching_pixels': max(0, total - count),
            'mismatched_pixels': count,
            'mismatch_ratio': round(float(count / total), 8) if total else 0.0,
            'max_delta': round(float(measured_delta.max()), 4) if measured_delta.size else 0.0,
            'mean_delta': round(float(measured_delta.mean()), 4) if measured_delta.size else 0.0,
            'coordinates': [[int(x), int(y)] for x, y in zip(xs[:max_locations], ys[:max_locations])],
        })
        if count:
            result['bounding_box'] = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]
            result['locations_truncated'] = count > max_locations
        return result
    except Exception as exc:
        result['status'] = 'NOT_MEASURED'
        result['reason'] = 'PIXEL_COMPARISON_FAILED'
        result['comparison_error'] = str(exc)[:500]
        return result


def compare_masks(expected, actual, *, stage=None, region_mask=None, tolerance=0,
                  max_locations=_MAX_DIAGNOSTIC_LOCATIONS):
    """Public mask comparison used by render, preview and recovery stages."""
    result = _pixel_difference(expected, actual, tolerance=tolerance,
                               region_mask=region_mask,
                               max_locations=max_locations)
    result['stage'] = str(stage) if stage else None
    result['comparison'] = 'mask'
    return result


def pixel_diagnostics(expected=None, actual=None, *, stage=None,
                      region_mask=None, tolerance=0,
                      max_locations=_MAX_DIAGNOSTIC_LOCATIONS, **extra):
    """Create a bounded diagnostic payload for a failed image operation."""
    result = _pixel_difference(expected, actual, tolerance=tolerance,
                               region_mask=region_mask,
                               max_locations=max_locations)
    result['stage'] = str(stage) if stage else None
    result['comparison'] = 'pixels'
    if extra:
        result['details'] = _sanitize(extra)
    return result


# Short aliases make the helper discoverable to older integrations.
compare_pixel_buffers = pixel_diagnostics
build_error_diagnostics = pixel_diagnostics
_pixel_diagnostics_builder = pixel_diagnostics


def _normalise_diagnostics(diagnostics=None, *, mask_comparison=None,
                           pixel_diagnostics_value=None, stage=None):
    """Make all supported caller forms share one report contract."""
    payload = {}
    if isinstance(diagnostics, dict):
        payload.update(diagnostics)
        if 'pixel_errors' not in payload and any(
                key in payload for key in ('changed_pixels', 'remaining_pixels',
                                           'unauthorized_changed_pixels',
                                           'protected_pixel_changes')):
            qa_payload = _diagnostics_from_qa(payload, stage=stage)
            if qa_payload:
                payload.update(qa_payload)
    if isinstance(mask_comparison, dict):
        payload['mask_comparison'] = mask_comparison
    if isinstance(pixel_diagnostics_value, dict):
        payload['pixel_errors'] = pixel_diagnostics_value
    payload.setdefault('stage', stage)
    payload.setdefault('pixel_errors', {
        'status': 'NOT_MEASURED', 'available': False,
        'mismatched_pixels': 0, 'coordinates': [], 'bounding_box': None,
        'reason': 'NO_PIXEL_DIAGNOSTICS_PROVIDED',
    })
    payload.setdefault('mask_comparison', {
        'status': 'NOT_MEASURED', 'available': False,
        'mismatched_pixels': 0, 'coordinates': [], 'bounding_box': None,
        'reason': 'NO_MASK_COMPARISON_PROVIDED',
    })
    return _sanitize(payload)


def _diagnostics_from_qa(qa, *, stage=None):
    """Translate established PETEK/Unified-V4 QA dictionaries.

    The renderers intentionally use different names (``changed_pixels``,
    ``remaining_pixels``, ``unauthorized_changed_pixels``).  This adapter
    keeps those existing contracts intact while making Error Radar consistent.
    """
    if not isinstance(qa, dict):
        return None
    pixel_count = None
    for key in ('unauthorized_changed_pixels', 'changed_outside_print_mask',
                'protected_pixel_changes', 'remaining_pixels',
                'unexpected_magenta_pixels', 'changed_pixels'):
        value = qa.get(key)
        if isinstance(value, (int, float)):
            pixel_count = max(0, int(value))
            if key in ('unauthorized_changed_pixels', 'changed_outside_print_mask',
                       'protected_pixel_changes', 'unexpected_magenta_pixels'):
                break
    coordinates = qa.get('first_protected_coordinates') or qa.get('coordinates') or []
    if not isinstance(coordinates, list):
        coordinates = []
    pixel = {
        'status': 'FAIL' if pixel_count else ('PASS' if pixel_count == 0 else 'NOT_MEASURED'),
        'available': pixel_count is not None,
        'mismatched_pixels': pixel_count or 0,
        'coordinates': coordinates[:_MAX_DIAGNOSTIC_LOCATIONS],
        'bounding_box': qa.get('bounding_box'),
        'stage': stage,
        'source': 'qa',
    }
    mask_candidates = [qa.get('mask_qa'), qa.get('source_protection_qa'),
                       qa.get('pre_pink_qa'), qa.get('pink_qa')]
    mask = next((item for item in mask_candidates if isinstance(item, dict)), None)
    comparison = None
    if mask is not None:
        mask = dict(mask)
        comparison = _diagnostics_from_qa(mask, stage=stage)
        if comparison:
            comparison = comparison['pixel_errors']
            comparison['source'] = 'qa.mask'
    return {'stage': stage, 'pixel_errors': pixel,
            'mask_comparison': comparison or {
                'status': 'NOT_MEASURED', 'available': False,
                'mismatched_pixels': 0, 'coordinates': [],
                'reason': 'QA_MASK_COMPARISON_NOT_PROVIDED',
            }}


def _git_revision():
    try:
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            ['git', '-C', str(root), 'rev-parse', '--short', 'HEAD'],
            capture_output=True, text=True, timeout=2, check=True,
        )
        return result.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def _atomic_write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.report-', suffix='.tmp', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _prune_reports(root):
    reports = sorted(root.glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True)
    total = sum(p.stat().st_size for p in reports)
    for index, path in enumerate(reports):
        if index < _MAX_REPORTS and total <= _MAX_BYTES:
            continue
        try:
            total -= path.stat().st_size
            path.unlink(missing_ok=True)
            path.with_suffix('.txt').unlink(missing_ok=True)
        except OSError:
            pass


def register_listener(callback):
    """Register a UI callback; callbacks receive a sanitized report dictionary."""
    if callable(callback) and callback not in _LISTENERS:
        _LISTENERS.append(callback)


def set_context_provider(callback):
    """Attach lightweight application context without importing the UI layer."""
    global _CONTEXT_PROVIDER
    _CONTEXT_PROVIDER = callback if callable(callback) else None


def last_report():
    with _LOCK:
        return dict(_LAST_REPORT) if isinstance(_LAST_REPORT, dict) else None


def set_processing_stage(stage):
    """Set the current thread's stage for errors raised by legacy callers."""
    _STAGE_LOCAL.value = str(stage).strip() if stage else None
    return _STAGE_LOCAL.value


def current_processing_stage():
    return getattr(_STAGE_LOCAL, 'value', None)


@contextmanager
def processing_stage(stage):
    """Temporarily label all errors in a render/QA operation."""
    previous = current_processing_stage()
    set_processing_stage(stage)
    try:
        yield stage
    finally:
        set_processing_stage(previous)


def record_error(title, message, *, stage=None, context=None, exc=None,
                 diagnostics=None, mask_comparison=None,
                 pixel_diagnostics_value=None, pixel_diagnostics=None,
                 expected_mask=None,
                 actual_mask=None, expected_pixels=None, actual_pixels=None,
                 region_mask=None, tolerance=0):
    """Create a structured + human-readable diagnostic report.

    ``expected_*``/``actual_*`` are optional render buffers.  Supplying them
    here makes the same evidence available to the JSON report, the text report
    and the Codex bundle.  Existing callers that only provide title/message
    remain valid and receive an explicit ``NOT_MEASURED`` status.
    """
    global _LAST_REPORT
    now = datetime.now(timezone.utc)
    timestamp = now.isoformat()
    error_id = uuid.uuid4().hex
    seed = f'{title}|{message}|{timestamp}|{error_id}'.encode('utf-8', 'replace')
    code = 'GFX-' + hashlib.sha256(seed).hexdigest()[:10].upper()
    # Most legacy call sites invoke ``messagebox.showerror`` directly inside
    # an ``except`` block. Capture that active traceback automatically so the
    # system-wide hook does not require every caller to be rewritten.
    active_exception = exc is not None or sys.exc_info()[0] is not None
    if sys.exc_info()[0] is not None:
        trace = traceback.format_exc()
    elif exc is not None:
        trace = ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    else:
        trace = ''
    if trace.strip() == 'NoneType: None':
        trace = ''
    provided_context = {}
    if _CONTEXT_PROVIDER is not None:
        try:
            provided_context = _CONTEXT_PROVIDER() or {}
        except Exception:
            provided_context = {}
    if context:
        provided_context.update(context)
    # Compute evidence before sanitising context so numpy/PIL buffers never
    # enter a report accidentally. Explicit diagnostics win over derived data.
    safe_diagnostics = diagnostics
    if isinstance(provided_context, dict):
        if mask_comparison is None and isinstance(provided_context.get('mask_comparison'), dict):
            mask_comparison = provided_context.get('mask_comparison')
        if pixel_diagnostics is None and pixel_diagnostics_value is None and isinstance(
                provided_context.get('pixel_errors'), dict):
            pixel_diagnostics_value = provided_context.get('pixel_errors')
    if isinstance(diagnostics, dict):
        expected_mask = diagnostics.get('expected_mask', expected_mask)
        actual_mask = diagnostics.get('actual_mask', actual_mask)
        expected_pixels = diagnostics.get('expected_pixels', expected_pixels)
        actual_pixels = diagnostics.get('actual_pixels', actual_pixels)
        region_mask = diagnostics.get('region_mask', region_mask)
        tolerance = diagnostics.get('tolerance', tolerance)
        safe_diagnostics = {
            key: value for key, value in diagnostics.items()
            if key not in {'expected_mask', 'actual_mask', 'expected_pixels',
                           'actual_pixels', 'region_mask'}
        }
    if pixel_diagnostics_value is None and pixel_diagnostics is not None:
        pixel_diagnostics_value = pixel_diagnostics
    derived_stage = (stage or
                     (provided_context.get('processing_stage') if isinstance(provided_context, dict) else None) or
                     (diagnostics.get('stage') if isinstance(diagnostics, dict) else None) or
                     (mask_comparison.get('stage') if isinstance(mask_comparison, dict) else None) or
                     (pixel_diagnostics_value.get('stage') if isinstance(pixel_diagnostics_value, dict) else None) or
                     (pixel_diagnostics.get('stage') if isinstance(pixel_diagnostics, dict) else None) or
                     current_processing_stage())
    if mask_comparison is None and (expected_mask is not None or actual_mask is not None):
        mask_comparison = compare_masks(expected_mask, actual_mask, stage=derived_stage,
                                        region_mask=region_mask, tolerance=tolerance)
    if pixel_diagnostics_value is None and (expected_pixels is not None or actual_pixels is not None):
        pixel_diagnostics_value = _pixel_diagnostics_builder(expected_pixels, actual_pixels,
                                                             stage=derived_stage,
                                                             region_mask=region_mask,
                                                             tolerance=tolerance)
    qa_diagnostics = None
    if isinstance(provided_context, dict):
        for key in ('qa', 'mask_qa', 'source_protection_qa'):
            if isinstance(provided_context.get(key), dict):
                qa_diagnostics = _diagnostics_from_qa(provided_context[key], stage=derived_stage)
                break
    normalised = _normalise_diagnostics(
        safe_diagnostics, mask_comparison=mask_comparison,
        pixel_diagnostics_value=pixel_diagnostics_value, stage=derived_stage,
    )
    if qa_diagnostics:
        merged = dict(qa_diagnostics)
        merged.update(normalised)
        # Default NOT_MEASURED placeholders should not hide concrete QA data.
        if pixel_diagnostics_value is None and diagnostics is None:
            merged['pixel_errors'] = qa_diagnostics['pixel_errors']
        if mask_comparison is None and diagnostics is None:
            merged['mask_comparison'] = qa_diagnostics['mask_comparison']
        normalised = _normalise_diagnostics(merged, stage=derived_stage)
    # Permit a QA dictionary to be passed in context while keeping the public
    # report fields stable for every subsystem.
    if isinstance(provided_context, dict):
        for key in ('diagnostics', 'error_diagnostics', 'qa'):
            candidate = provided_context.get(key)
            if isinstance(candidate, dict):
                merged = dict(candidate)
                # Preserve evidence already derived from explicit buffers or
                # from a sibling QA key in the same context payload.
                merged.setdefault('pixel_errors', normalised.get('pixel_errors'))
                merged.setdefault('mask_comparison', normalised.get('mask_comparison'))
                # Explicit keyword arguments are authoritative; otherwise a
                # QA payload supplied by the rendering stage is preserved.
                if diagnostics is not None:
                    merged.update(safe_diagnostics if isinstance(safe_diagnostics, dict) else {})
                if mask_comparison is not None:
                    merged['mask_comparison'] = mask_comparison
                if pixel_diagnostics_value is not None:
                    merged['pixel_errors'] = pixel_diagnostics_value
                normalised = _normalise_diagnostics(merged, stage=derived_stage)
                break
    try:
        pixel_error_count = int((normalised.get('pixel_errors') or {}).get('mismatched_pixels') or 0)
    except (TypeError, ValueError):
        pixel_error_count = 0
    report = {
        # Keep the envelope schema stable for existing report readers; the
        # additive diagnostics contract is versioned independently.
        'schema': 1,
        'diagnostics_schema': 1,
        'error_id': error_id,
        'error_code': code,
        'timestamp_utc': timestamp,
        'title': _sanitize(title),
        'message': _sanitize(message),
        'stage': _sanitize(derived_stage or title),
        'processing_stage': _sanitize(derived_stage or title),
        'diagnostics': normalised,
        # Stable top-level aliases keep report consumers simple and make old
        # text/Codex integrations useful without knowing the nested schema.
        'pixel_errors': normalised.get('pixel_errors'),
        'mask_comparison': normalised.get('mask_comparison'),
        'pixel_error_count': pixel_error_count,
        'error_locations': (normalised.get('pixel_errors') or {}).get('coordinates') or [],
        'mask_diff': normalised.get('mask_comparison'),
        'mask_error_locations': (normalised.get('mask_comparison') or {}).get('coordinates') or [],
        'context': _sanitize(provided_context),
        'traceback': _sanitize(trace),
        'runtime': {
            'platform': platform.platform(),
            'python': platform.python_version(),
            'app_revision': _git_revision(),
        },
    }
    root = _report_root()
    json_path = root / f'{now.strftime("%Y%m%d_%H%M%S")}_{code}.json'
    text_path = json_path.with_suffix('.txt')
    human = (
        f'GÖRSEL ÜRETİM MERKEZİ HATA RAPORU\n'
        f'Hata kodu: {code}\nZaman (UTC): {timestamp}\n'
        f'Aşama: {report["stage"]}\nBaşlık: {report["title"]}\n'
        f'Mesaj: {report["message"]}\n\n'
        f'Piksel özeti:\n{json.dumps(report["pixel_errors"], ensure_ascii=False, indent=2)}\n\n'
        f'Konum örnekleri (x,y): {report["error_locations"][:20]}\n'
        f'Maske karşılaştırması:\n{json.dumps(report["mask_comparison"], ensure_ascii=False, indent=2)}\n\n'
        f'Maske farkı konumları (x,y): {report["mask_error_locations"][:20]}\n'
        f'Bağlam:\n{json.dumps(report["context"], ensure_ascii=False, indent=2)}\n\n'
        f'Teknik iz:\n{report["traceback"] or "(traceback yok)"}\n'
    )
    try:
        with _LOCK:
            _atomic_write(json_path, json.dumps(report, ensure_ascii=False, indent=2))
            _atomic_write(text_path, human)
            _prune_reports(root)
            report['json_path'] = str(json_path)
            report['text_path'] = str(text_path)
            _LAST_REPORT = dict(report)
    except OSError:
        # Error reporting must never hide the original UI error.
        report['json_path'] = None
        report['text_path'] = None
        with _LOCK:
            _LAST_REPORT = dict(report)
    for callback in tuple(_LISTENERS):
        try:
            callback(dict(report))
        except Exception:
            pass
    return report


def open_report(report=None):
    report = report or last_report()
    path = (report or {}).get('text_path') or (report or {}).get('json_path')
    if not path:
        return None
    try:
        os.startfile(path)  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        return path
    return path


def copy_report_text(report=None):
    report = report or last_report()
    path = (report or {}).get('text_path')
    if not path:
        return None
    try:
        text = Path(path).read_text(encoding='utf-8')
    except OSError:
        return None
    try:
        import tkinter as tk
        root = tk._default_root
        if root is not None:
            root.clipboard_clear(); root.clipboard_append(text); root.update()
            return text
    except Exception:
        pass
    return text


def prepare_codex_bundle(report=None):
    """Create a tiny local zip; never sends it to an external service."""
    report = report or last_report()
    if not report:
        return None
    root = _report_root()
    root.mkdir(parents=True, exist_ok=True)
    bundle = root / f'codex_diagnosis_{report["error_code"]}.zip'
    import zipfile
    with zipfile.ZipFile(bundle, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('report.json', json.dumps(_sanitize(report), ensure_ascii=False, indent=2))
        archive.writestr('diagnostics.json', json.dumps(_sanitize({
            'error_id': report.get('error_id'),
            'error_code': report.get('error_code'),
            'processing_stage': report.get('processing_stage') or report.get('stage'),
            'pixel_errors': report.get('pixel_errors'),
            'mask_comparison': report.get('mask_comparison'),
        }), ensure_ascii=False, indent=2))
        text_path = report.get('text_path')
        if text_path and Path(text_path).is_file():
            archive.write(text_path, 'report.txt')
    return str(bundle)


def explain(title, message):
    txt=str(message or '')
    lower=(str(title)+' '+txt).casefold()
    if 'sha' in lower or 'kimlik' in lower or 'kaynak değiş' in lower:
        return ('Güvenlik kontrolü: kaynak veya maske kimliği uyuşmuyor.',
                'Dosyayı yeniden yükleyin ve şablonun mevcut sürümünü inceleyin. Eski onayı zorla kullanmayın.')
    if 'maske' in lower or 'petek' in lower or 'baskı alanı' in lower:
        return ('PETEK maskesi veya baskı alanı hazır değil / doğrulanamadı.',
                'Önce 4 köşe önerisini doğrulayın, sonra “2. Otomatik Maske Taslağı”nı çalıştırıp yeşil alanı inceleyin. Onaylı maskeyi otomatik değiştirmeyin.')
    if '4k' in lower or 'esrgan' in lower or 'gpu' in lower or 'vulkan' in lower:
        return ('4K motoru, model dosyası veya GPU erişimiyle ilgili bir sorun olabilir.',
                'Seri Üretim > “4K Kurulumunu Kontrol Et” seçeneğini çalıştırın. 4K kapalı normal üretim devam edebilir.')
    if '8080' in lower or '8090' in lower or 'port' in lower:
        return ('İnceleme servisi açık veya port başka bir işlem tarafından kullanılıyor.',
                'Şablon kaydını tamamlayın; uygulamadaki güvenli servis kapatma düğmesini kullanın. Görev Yöneticisi’nden rastgele süreç kapatmayın.')
    if 'excel' in lower or 'xlsx' in lower or 'mağaza' in lower:
        return ('Excel/mağaza verisi veya dosya erişimi tamamlanamadı.',
                'XLSX dosyasının başka programda açık olmadığını ve mağaza profilinin seçildiğini doğrulayın; yeniden denemeden önce çıktıyı yedekleyin.')
    if 'internet' in lower or 'https' in lower or 'yükle' in lower or 'token' in lower:
        return ('İnternet bağlantısı veya bulut yükleme yetkisi başarısız olabilir.',
                'Bağlantı/izinleri kontrol edin; API anahtarlarını rapora eklemeyin. Normal yerel çıktı korunur.')
    if 'dosya' in lower or 'klasör' in lower or 'path' in lower or 'izin' in lower:
        return ('Gerekli dosya veya klasöre erişim başarısız.',
                'Ana çalışma klasörünü kontrol edin; açık dosyayı kapatın ve klasör iznini doğrulayın. Orijinal yedekleri taşımayın.')
    return ('İşlem beklenmedik şekilde tamamlanamadı.',
            'Tekrar denemeden önce açık kayıtlarınızı koruyun. Test Merkezi > Sorun Var bölümüne hata metnini ve ekran adını kaydedin.')


def showerror(title, message, *, stage=None, context=None, exc=None,
              diagnostics=None, mask_comparison=None,
              pixel_diagnostics_value=None, pixel_diagnostics=None,
              expected_mask=None,
              actual_mask=None, expected_pixels=None, actual_pixels=None,
              region_mask=None, tolerance=0, **kwargs):
    """Drop-in ``messagebox.showerror`` with optional render evidence.

    Diagnostic keyword arguments are intentionally consumed here rather than
    forwarded to Tk, so existing UI call sites and richer new call sites can
    use the same function safely.
    """
    report = record_error(
        title, message, stage=stage, context=context, exc=exc,
        diagnostics=diagnostics, mask_comparison=mask_comparison,
        pixel_diagnostics_value=pixel_diagnostics_value,
        pixel_diagnostics=pixel_diagnostics,
        expected_mask=expected_mask, actual_mask=actual_mask,
        expected_pixels=expected_pixels, actual_pixels=actual_pixels,
        region_mask=region_mask, tolerance=tolerance,
    )
    cause,remedy=explain(title,message)
    text=(str(message)+'\n\nNEDEN: '+cause+'\n\nNE YAPMALIYIM? '+remedy+
          '\n\nHATA KODU: '+str(report.get('error_code'))+
          '\nAŞAMA: '+str(report.get('processing_stage'))+
          '\nHATALI PİKSEL: '+str(report.get('pixel_error_count', 0))+
          '\nMASKE FARKI: '+str((report.get('mask_comparison') or {}).get('mismatched_pixels', 0))+
          '\nKONUM ÖRNEKLERİ: '+str((report.get('error_locations') or [])[:8])+
          '\nRAPOR: '+str(report.get('text_path') or 'Rapor yazılamadı')+
          '\n\nAna panelde “Raporu Aç”, “Raporu Kopyala” veya “Codex İçin Rapor Hazırla” seçeneklerini kullanabilirsiniz.')
    return _NATIVE_SHOWERROR(title,text,**kwargs)


def install_global_error_advisor():
    """Cover existing Tk modules using tkinter.messagebox without rewriting them.

    Only showerror is patched: informational dialogs and yes/no confirmations are
    deliberately unaffected. Installation is idempotent, and the native Tk call
    was captured before patching to avoid recursion.
    """
    global _INSTALLED
    if not _INSTALLED:
        messagebox.showerror=showerror
        _INSTALLED=True

