"""UI-only review workspace settings. Never import or touch any production registry.

Stored in the Windows user's LocalAppData, completely outside the mockup workspace.
The Flask app's existing loopback/Origin/CSRF before_request guards apply.
"""
from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import re
import tempfile
from flask import Blueprint, jsonify, request

review_layout_bp = Blueprint('review_layout_vnext', __name__)
SCHEMA = 1
VALID_CARDS = {
    'review': ('review-quick', 'review-alignment', 'review-corners', 'review-source', 'review-reports', 'review-approve'),
    'petek': ('petek-preview', 'petek-general', 'petek-corners', 'petek-mask', 'petek-curves', 'petek-approval'),
}
PINNED = {'review': ('review-quick', 'review-approve'), 'petek': ('petek-approval',)}
HEX = re.compile(r'^#[0-9a-fA-F]{6}$')


def _luma(color: str) -> float:
    channels = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linears = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in channels]
    return .2126 * linears[0] + .7152 * linears[1] + .0722 * linears[2]


def contrast(a: str, b: str) -> float:
    first, second = sorted((_luma(a), _luma(b)), reverse=True)
    return (first + .05) / (second + .05)


def path() -> Path:
    # No path is derived from the application workspace or request data.
    base = Path(os.environ.get('LOCALAPPDATA') or Path.home() / '.gorsel_mockup')
    return base / 'GorselMockup' / 'UI_VNEXT' / 'review_layout.json'


def default() -> dict:
    return {
        'schema': SCHEMA,
        'widths': {'left': 290, 'right': 330},
        'paneOrder': 'photo-first',
        'density': 'normal', 'effect': 'subtle',
        'colors': {
            'accent': '#7A4DFA', 'background': '#111827', 'panel': '#1D2638',
            'border': '#384466', 'text': '#F4F6FF'
        },
        'tabs': {'review': ['Tümü'], 'petek': ['Tümü']},
        'assignments': {'review': {}, 'petek': {}},
        'order': {mode: list(ids) for mode, ids in VALID_CARDS.items()},
    }


def validate(payload: object) -> dict:
    if not isinstance(payload, dict) or payload.get('schema') != SCHEMA:
        raise ValueError('UI_SCHEMA_NOT_SUPPORTED')
    out = default()
    widths = payload.get('widths', {})
    if not isinstance(widths, dict):
        raise ValueError('UI_WIDTHS_INVALID')
    for key, lower, upper in (('left', 205, 480), ('right', 245, 530)):
        v = widths.get(key, out['widths'][key])
        if isinstance(v, bool) or not isinstance(v, int) or not lower <= v <= upper:
            raise ValueError('UI_WIDTH_OUT_OF_RANGE:' + key)
        out['widths'][key] = v
    pane_order = payload.get('paneOrder', 'photo-first')
    if pane_order not in ('photo-first', 'tools-first'):
        raise ValueError('UI_PANE_ORDER_INVALID')
    out['paneOrder'] = pane_order
    for key, valid in [('density', ('compact', 'normal', 'spacious')),
                       ('effect', ('off', 'subtle', 'soft'))]:
        v = payload.get(key, out[key])
        if v not in valid:
            raise ValueError('UI_INVALID_' + key.upper())
        out[key] = v
    colors = payload.get('colors', {})
    if not isinstance(colors, dict):
        raise ValueError('UI_COLORS_INVALID')
    for key, original in out['colors'].items():
        v = colors.get(key, original)
        if not isinstance(v, str) or not HEX.fullmatch(v):
            raise ValueError('UI_BAD_COLOR:' + key)
        out['colors'][key] = v.upper()
    fg = out['colors']['text']
    if min(contrast(fg, out['colors']['background']), contrast(fg, out['colors']['panel'])) < 4.5:
        raise ValueError('UI_CONTRAST_TOO_LOW')
    if contrast('#FFFFFF', out['colors']['accent']) < 3.0:
        raise ValueError('UI_ACCENT_CONTRAST_TOO_LOW')
    if contrast(out['colors']['border'], out['colors']['panel']) < 1.3:
        raise ValueError('UI_BORDER_NOT_VISIBLE')

    tabs = payload.get('tabs', {})
    assignments = payload.get('assignments', {})
    orders = payload.get('order', {})
    if not all(isinstance(value, dict) for value in (tabs, assignments, orders)):
        raise ValueError('UI_LAYOUT_INVALID')
    for mode, ids in VALID_CARDS.items():
        source = tabs.get(mode, ['Tümü'])
        if (not isinstance(source, list) or not source or source[0] != 'Tümü' or
                len(source) > 8 or len(set(map(str, source))) != len(source) or
                any(not isinstance(t, str) or not (1 <= len(t) <= 30) or
                    t != t.strip() for t in source)):
            raise ValueError('UI_TABS_INVALID:' + mode)
        out['tabs'][mode] = source[:]
        ass = assignments.get(mode, {})
        if not isinstance(ass, dict) or not set(ass).issubset(ids):
            raise ValueError('UI_ASSIGNMENTS_INVALID:' + mode)
        for key, tab in ass.items():
            if not isinstance(tab, str) or tab not in source:
                raise ValueError('UI_TAB_UNKNOWN:' + mode)
            if key in PINNED[mode] and tab != 'Tümü':
                raise ValueError('UI_PINNED_ACTION_CANNOT_MOVE:' + key)
        out['assignments'][mode] = dict(ass)
        order = orders.get(mode, list(ids))
        if (not isinstance(order, list) or len(order) != len(ids) or
                any(not isinstance(item, str) for item in order) or set(order) != set(ids)):
            raise ValueError('UI_CARD_ORDER_INVALID:' + mode)
        out['order'][mode] = order[:]
    return out


def _read_file(p: Path):
    if p.is_symlink() or p.parent.is_symlink():
        raise OSError('UI_SYMLINK_FORBIDDEN')
    with p.open('r', encoding='utf-8') as stream:
        return validate(json.load(stream))


def load() -> dict:
    p = path()
    try:
        return _read_file(p)
    except (OSError, ValueError, TypeError, KeyError):
        try:
            return _read_file(p.with_suffix('.lastgood.json'))
        except (OSError, ValueError, TypeError, KeyError):
            return default()


def save(payload: object) -> dict:
    data = validate(payload)
    p = path()
    if p.is_symlink() or p.parent.is_symlink():
        raise OSError('UI_SYMLINK_FORBIDDEN')
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.parent.is_symlink():
        raise OSError('UI_SYMLINK_FORBIDDEN')
    previous = None
    if p.exists():
        try:
            previous = _read_file(p)
        except (OSError, ValueError, TypeError, KeyError):
            previous = None
    def atomic(dest: Path, item: dict):
        fd, name = tempfile.mkstemp(prefix='.review-ui-', suffix='.tmp', dir=p.parent)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(item, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(name, dest)
        finally:
            if os.path.exists(name):
                os.unlink(name)
    if previous is not None:
        atomic(p.with_suffix('.backup.json'), previous)
    atomic(p, data)
    atomic(p.with_suffix('.lastgood.json'), data)
    return data


@review_layout_bp.get('/api/ui-layout/review')
def read_review_layout():
    return jsonify({'success': True, 'layout': load()})


@review_layout_bp.post('/api/ui-layout/review')
def write_review_layout():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({'success': False, 'code': 'UI_JSON_REQUIRED'}), 400
    try:
        return jsonify({'success': True, 'layout': save(body)})
    except ValueError as exc:
        return jsonify({'success': False, 'code': str(exc)}), 422
    except OSError:
        return jsonify({'success': False, 'code': 'UI_SETTINGS_WRITE_FAILED'}), 500


@review_layout_bp.get('/api/ui-layout/review/previous')
def previous_review_layout():
    try:
        data = _read_file(path().with_suffix('.backup.json'))
    except (OSError, ValueError, TypeError, KeyError):
        return jsonify({'success': False, 'code': 'UI_NO_PREVIOUS_BACKUP'}), 404
    return jsonify({'success': True, 'layout': data})
