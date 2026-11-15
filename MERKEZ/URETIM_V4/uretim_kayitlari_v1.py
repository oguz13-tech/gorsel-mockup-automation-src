"""Üretim Kayıtları — operasyon merkezi (salt okunur).

Bu modül yalnızca **okur**: ``v4_ortak_uretim.sqlite3`` (``artifact`` ve
``production_session`` tabloları), ``v47_last_batch_resume.json`` devam
kontrolü ve kilit dosyası. Hiçbir kaydı silmez, taşımaz, karantinaya
almaz veya yeniden üretmez; bulut/Excel (cloud_link) tablolarına hiç
dokunmaz.

Tamamlanan (RENDERED) görseller listelenir ve hiçbir kod yolu onları
yeniden render etmez; "Yarım Kalanı Devam Ettir" yalnızca mevcut
``resume_batch`` onay akışını tetikler. Link ve Excel sonuçları aynen
korunur. Uygulama yeniden başlatılınca durum kayıtlardan yeniden
yüklenir.
"""
from __future__ import annotations

import json
import re
import sqlite3
import os
from pathlib import Path
from typing import Any

try:
    from graphite_ui_components import module_header
except Exception:
    module_header = None

# Graphite paletiyle aynı (graphite_workbench_v500 ile birebir).
SIDE = '#0F1622'
PANEL = '#131C2B'
PANEL_RAISED = '#182238'
BORDER = '#22304A'
ACCENT = '#17D3A3'
ACCENT_DARK = '#0B7A5F'
BLUE = '#5AA9FF'
YELLOW = '#F0B84C'
RED = '#EF6A73'
GREEN = '#3FD98A'
FG = '#E9EFF9'
MUTED = '#66789B'

_DB_NAME = 'v4_ortak_uretim.sqlite3'

try:
    from URETIM_V4 import ui_table_v1 as _table_tools
except Exception:                                  # mevcut tema yoksa/minimalist yüklemede açılır
    _table_tools = None


# ---------------------------------------------------------------- kök
def default_state_root() -> Path:
    try:
        from URETIM_V4.unified_batch import store_v4_root  # type: ignore
        return store_v4_root()
    except Exception:
        base = os.getenv('LOCALAPPDATA')
        return (Path(base) if base else Path.home() / '.gorsel_mockup') / 'GorselMockup' / 'UnifiedV4'


def _ro_connect(db_path: Path) -> sqlite3.Connection | None:
    try:
        if not db_path.is_file() or db_path.is_symlink():
            return None
        con = sqlite3.connect(db_path.resolve().as_uri() + '?mode=ro', uri=True, timeout=10)
        con.row_factory = sqlite3.Row
        return con
    except sqlite3.Error:
        return None


def _tables(con: sqlite3.Connection) -> set[str]:
    try:
        return {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    except sqlite3.Error:
        return set()


# ---------------------------------------------------------------- okuma
def status_counts(root: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    con = _ro_connect(Path(root) / _DB_NAME)
    if con is None:
        return counts
    try:
        if 'artifact' in _tables(con):
            for row in con.execute('SELECT status, COUNT(*) FROM artifact GROUP BY status'):
                counts[str(row[0])] = int(row[1])
    except sqlite3.Error:
        return {}
    finally:
        con.close()
    return counts


def recent_artifacts(root: Path, status: str, limit: int = 150) -> list[dict[str, Any]]:
    con = _ro_connect(Path(root) / _DB_NAME)
    if con is None:
        return []
    try:
        if 'artifact' not in _tables(con):
            return []
        rows = con.execute(
            'SELECT sku, category, art_name, uid, output, output_sha, message, updated,'
            '       artifact_kind, overlay_cm'
            '  FROM artifact WHERE status = ? ORDER BY updated DESC, key DESC LIMIT ?',
            (str(status), int(limit)),
        ).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.Error:
        return []
    finally:
        con.close()


def recent_sessions(root: Path, limit: int = 40) -> list[dict[str, Any]]:
    con = _ro_connect(Path(root) / _DB_NAME)
    if con is None:
        return []
    try:
        if 'production_session' not in _tables(con):
            return []
        rows = con.execute(
            'SELECT operation_id, started_at, finished_at, mode, design_folder, stores,'
            '       design_count, planned, successful, failed, skipped, elapsed_seconds,'
            '       seconds_per_image, status, per_store, report_path, external'
            '  FROM production_session ORDER BY started_at DESC LIMIT ?', (int(limit),),
        ).fetchall()
    except sqlite3.Error:
        return []
    finally:
        con.close()
    sessions = []
    for row in rows:
        item = dict(row)
        for key in ('stores', 'per_store'):
            try:
                item[key] = json.loads(item.get(key) or 'null')
            except ValueError:
                item[key] = None
        sessions.append(item)
    return sessions


def _normalize_reason(message: Any) -> str:
    text = ' '.join(str(message or '').split())
    if not text:
        return 'NEDENSIZ_HATA'
    head = re.split(r'[:;,\n]', text, maxsplit=1)[0].strip()
    return (head or text)[:90]


def error_reasons(root: Path, limit_groups: int = 12, scan: int = 5000) -> list[dict[str, Any]]:
    """Başarısız kayıtları normalize edilmiş nedenlerine göre gruplar (salt okunur)."""
    con = _ro_connect(Path(root) / _DB_NAME)
    if con is None:
        return []
    try:
        if 'artifact' not in _tables(con):
            return []
        rows = [r[0] for r in con.execute(
            "SELECT message FROM artifact WHERE status='REVIEW_REQUIRED' LIMIT ?",
            (int(scan),))]
    except sqlite3.Error:
        return []
    finally:
        con.close()
    groups: dict[str, int] = {}
    for message in rows:
        reason = _normalize_reason(message)
        groups[reason] = groups.get(reason, 0) + 1
    ordered = sorted(groups.items(), key=lambda kv: (-kv[1], kv[0]))
    return [{'reason': reason, 'count': count} for reason, count in ordered[: int(limit_groups)]]


def failed_total(root: Path) -> int:
    con = _ro_connect(Path(root) / _DB_NAME)
    if con is None:
        return 0
    try:
        if 'artifact' not in _tables(con):
            return 0
        return int(con.execute(
            "SELECT COUNT(*) FROM artifact WHERE status='REVIEW_REQUIRED'").fetchone()[0])
    except sqlite3.Error:
        return 0
    finally:
        con.close()


def interrupted_pending(root: Path) -> int:
    con = _ro_connect(Path(root) / _DB_NAME)
    if con is None:
        return 0
    try:
        if 'artifact' not in _tables(con):
            return 0
        return int(con.execute(
            "SELECT COUNT(*) FROM artifact WHERE status='PENDING'").fetchone()[0])
    except sqlite3.Error:
        return 0
    finally:
        con.close()


def checkpoint_summary(root: Path) -> dict[str, Any]:
    path = Path(root) / 'v47_last_batch_resume.json'
    if not path.is_file() or path.is_symlink():
        return {'status': 'NONE'}
    try:
        from URETIM_V4.resume_checkpoint_v47 import read_checkpoint  # type: ignore
        payload = read_checkpoint(Path(root))
        if not payload:
            return {'status': 'NONE'}
        return {'status': str(payload.get('status') or 'UNKNOWN'),
                'operation_id': payload.get('operation_id') or '',
                'progress': dict(payload.get('progress') or {}),
                'external_mode': bool(payload.get('external_mode'))}
    except Exception as exc:
        return {'status': 'CHECKPOINT_INVALID', 'error': str(exc)[:200]}


def lock_state(root: Path) -> dict[str, Any]:
    path = Path(root) / 'V4_ORTAK_FABRIKA.lock'
    try:
        from URETIM_V4 import crash_recovery as _cr  # type: ignore
        return _cr._inspect_lock_file(path)
    except Exception:
        exists = path.is_file() or path.is_symlink()
        info: dict[str, Any] = {'lock_path': str(path), 'exists': exists,
                                'pid': None, 'pid_alive': None, 'stale_lock': None}
        if exists:
            try:
                raw = path.read_text(encoding='utf-8', errors='replace').strip().splitlines()
                info['pid'] = int(raw[0].strip()) if raw else None
            except (OSError, ValueError):
                info['stale_lock'] = True
        return info


def latest_error_reports(root: Path, limit: int = 6) -> list[Path]:
    reports = Path(root) / 'raporlar'
    try:
        if not reports.is_dir():
            return []
        candidates = list(reports.glob('URETIM_INCELEME_*.json'))
        candidates.sort(key=lambda p: p.stat().st_mtime_ns, reverse=True)
        return candidates[: int(limit)]
    except OSError:
        return []


_MODE_LABEL = {'standard': 'Standart', 'overlay4': '1 Mockup · 4 Overlay', 'four_mockup': '4 Mockup'}


def session_label(session: dict[str, Any]) -> dict[str, str]:
    status = str(session.get('status') or '')
    unfinished = status == 'RUNNING' and not session.get('finished_at')
    per_store = ((session.get('per_store') or {}).get('outputs') or {}) if isinstance(session.get('per_store'), dict) else {}
    if per_store:
        stores = ', '.join(f'{name}: {count}' for name, count in per_store.items())
    else:
        stores = ', '.join(str(s) for s in (session.get('stores') or []))
    return {
        'date': str(session.get('started_at') or ''),
        'mode': _MODE_LABEL.get(str(session.get('mode') or ''), str(session.get('mode') or '—'))
                + (' (harici)' if session.get('external') else ''),
        'stores': stores or '—',
        'successful': str(session.get('successful', 0)),
        'failed': str(session.get('failed', 0)),
        'skipped': str(session.get('skipped', 0)),
        'status': 'RUNNING ⚠ yarıda kalmış olabilir' if unfinished else (status or '—'),
        'unfinished': '1' if unfinished else '0',
        'report_path': str(session.get('report_path') or ''),
    }


def classify_resume(checkpoint: dict[str, Any], lock: dict[str, Any], pending: int) -> tuple[str, str]:
    """(seviye, mesaj) — seviye: ok / resume / warning / info."""
    status = str((checkpoint or {}).get('status') or 'NONE')
    lock_exists = bool((lock or {}).get('exists'))
    pid_alive = (lock or {}).get('pid_alive')
    stale = (lock or {}).get('stale_lock')
    progress = (checkpoint or {}).get('progress') or {}
    rendered = int(progress.get('rendered') or 0)
    attempted = int(progress.get('attempted') or 0)

    if status == 'STOPPED':
        return ('resume',
                f'Güvenli durdurulmuş tur bulundu ({rendered}/{attempted} görsel işlendi). '
                '"Yarım Kalanı Devam Ettir" ile kaldığı yerden sürdürebilirsiniz; '
                'tamamlanan görseller SHA-256 ile doğrulanıp atlanır.')
    if status == 'RUNNING':
        if lock_exists and pid_alive:
            return ('info', 'Üretim şu anda çalışıyor. Bitmesini bekleyin; kayıtlar bu ekranda kendini yeniler.')
        return ('warning',
                'Üretim yarım kalmış görünüyor (uygulama kapatılmış olabilir). '
                'Önce "Kesinti Kurtarma Denetimi"ni çalıştırın; eski kayıtlar onayınız olmadan değiştirilmez.')
    if status == 'INTERRUPTED':
        return ('warning',
                'Önceki tur kritik hatayla kesildi. "Kesinti Kurtarma Denetimi" ile kilit ve '
                'yarım kayıtları inceleyin; doğrulanan çıktılar korunur.')
    if status == 'CHECKPOINT_INVALID':
        return ('warning', 'Devam kontrolü okunamadı ("%s"). "Kesinti Kurtarma Denetimi"ni çalıştırın.'
                % str((checkpoint or {}).get('error') or 'bilinmeyen hata'))
    if pending > 0:
        return ('warning',
                f'{pending} tamamlanmamış (PENDING) kayıt var; tur durduysa "Kesinti Kurtarma Denetimi"ni açın.')
    if lock_exists and stale:
        return ('warning', 'Üretim kilidi bayat görünüyor. "Kesinti Kurtarma Denetimi" ile inceleyin.')
    return ('ok', 'Devam ettirilecek yarım üretim yok. Tamamlanan görseller yeniden üretilmez.')


def summarize(root: Path | None = None) -> dict[str, Any]:
    root = Path(root) if root else default_state_root()
    checkpoint = checkpoint_summary(root)
    lock = lock_state(root)
    pending = interrupted_pending(root)
    counts = status_counts(root)
    level, banner = classify_resume(checkpoint, lock, pending)
    sessions = recent_sessions(root, 40)
    return {
        'root': root,
        'counts': counts,
        'rendered': int(counts.get('RENDERED', 0)),
        'review_required': int(counts.get('REVIEW_REQUIRED', 0)),
        'pending': pending,
        'checkpoint': checkpoint,
        'lock': lock,
        'level': level,
        'banner': banner,
        'sessions': sessions,
        'unfinished_sessions': sum(1 for s in sessions if session_label(s)['unfinished'] == '1'),
    }


# ---------------------------------------------------------------- Tk paneli
def build_records_workspace(app, parent, *, state_root: Path | None = None):
    """'✓ Üretim Kayıtları' sekmesinin içeriğini üretir (salt okunur)."""
    import tkinter as tk
    from tkinter import ttk, messagebox

    root = Path(state_root) if state_root else default_state_root()

    shell = tk.Frame(parent, bg=SIDE, bd=0, highlightthickness=0)
    shell.grid_columnconfigure(0, weight=1)
    shell.grid_rowconfigure(2, weight=1)

    # ---- üst bar
    top = (module_header(shell, '✓  Üretim Kayıtları',
                         'Operasyon merkezi · geçmiş, yarım kalanlar ve kurtarma')
           if module_header else tk.Frame(shell, bg=PANEL, bd=0, highlightthickness=0))
    top.grid(row=0, column=0, sticky='ew', padx=6, pady=(6, 4))
    chips: dict[str, tk.Label] = {}

    def _chip(key, text, color):
        lbl = tk.Label(top, text=text, bg=color, fg='#0F1622',
                       font=('Segoe UI', 8, 'bold'), padx=8, pady=3)
        lbl.pack(side='left', padx=4)
        chips[key] = lbl

    _chip('ok', 'Başarılı: –', GREEN)
    _chip('fail', 'Başarısız: –', RED)
    _chip('pending', 'Yarım: –', YELLOW)

    refresh_btn = tk.Button(top, text='⟳ Yenile', bg=PANEL_RAISED, fg=FG, relief='flat',
                            font=('Segoe UI', 9, 'bold'), padx=12, pady=4, cursor='hand2')
    refresh_btn.pack(side='right', padx=8, pady=6)
    tk.Button(top, text='Sistem Sağlığı', bg=PANEL_RAISED, fg=FG, relief='flat',
              font=('Segoe UI', 8), padx=10, pady=4, cursor='hand2',
              command=lambda: _call(app, 'show_health')).pack(side='right', padx=2, pady=6)

    # ---- devam banner'ı
    banner_row = tk.Frame(shell, bg=SIDE, bd=0, highlightthickness=0)
    banner_row.grid(row=1, column=0, sticky='ew', padx=6, pady=(0, 4))
    banner_lbl = tk.Label(banner_row, text='Kayıtlar yükleniyor…', bg=PANEL_RAISED, fg=FG,
                          font=('Segoe UI', 9), anchor='w', justify='left',
                          wraplength=900, padx=10, pady=8)
    banner_lbl.pack(side='left', fill='x', expand=True)
    resume_btn = tk.Button(banner_row, text='▶  Yarım Kalanı Devam Ettir', bg=ACCENT_DARK, fg='#FFFFFF',
                           relief='flat', font=('Segoe UI', 9, 'bold'), padx=12, pady=8, cursor='hand2')
    resume_btn.pack(side='left', padx=(6, 0))
    recovery_btn = tk.Button(banner_row, text='🛠  Kesinti Kurtarma Denetimi', bg=PANEL_RAISED, fg=FG,
                             relief='flat', font=('Segoe UI', 8), padx=10, pady=8, cursor='hand2',
                             command=lambda: _call(app, 'open_crash_recovery'))
    recovery_btn.pack(side='left', padx=4)

    # ---- gövde: sol son üretimler, sağ başarılı/başarısız sekmeleri (ayırıcı: sürükle)
    body = tk.PanedWindow(shell, orient='horizontal', bg=SIDE, bd=0,
                          sashwidth=8, sashrelief='raised', sashcursor='sb_h_double_arrow')
    body.grid(row=2, column=0, sticky='nsew', padx=6, pady=(0, 4))

    sessions_frame = tk.LabelFrame(body, text='Son Üretimler', bg=PANEL, fg=BLUE,
                                   font=('Segoe UI', 9, 'bold'), bd=1, relief='groove',
                                   padx=6, pady=6)
    sessions_frame.grid_columnconfigure(0, weight=1)
    sessions_frame.grid_rowconfigure(0, weight=1)
    session_cols = ('Tarih', 'Mod', 'Mağazalar', 'Başarılı', 'Hata', 'Durum')
    sessions_tree = ttk.Treeview(sessions_frame, columns=session_cols, show='headings',
                                 selectmode='browse', height=12)
    for name, width in zip(session_cols, (135, 120, 150, 60, 50, 150)):
        sessions_tree.heading(name, text=name)
        sessions_tree.column(name, width=width, anchor='w', stretch=(name in ('Mod', 'Mağazalar', 'Durum')))
    if _table_tools is not None:
        try:
            _table_tools.enhance_tree(sessions_tree, session_cols)
        except (AttributeError, tk.TclError):
            pass
    sessions_scroll = ttk.Scrollbar(sessions_frame, orient='vertical', command=sessions_tree.yview)
    sessions_tree.configure(yscrollcommand=sessions_scroll.set)
    sessions_tree.grid(row=0, column=0, sticky='nsew')
    sessions_scroll.grid(row=0, column=1, sticky='ns')
    if _table_tools is not None:
        _table_tools.add_horizontal_scrollbar(sessions_tree, row=1, column=0, columnspan=2, sticky='ew')
    body.add(sessions_frame, minsize=340, sticky='nsew')

    notebook = ttk.Notebook(body)
    body.add(notebook, minsize=480, sticky='nsew')

    success_tab = tk.Frame(notebook, bg=PANEL)
    fail_tab = tk.Frame(notebook, bg=PANEL)
    notebook.add(success_tab, text='✓  Başarılı Görseller')
    notebook.add(fail_tab, text='⚠  Başarısız Görseller')

    def _build_artifact_tab(tab, status, with_reasons):
        row_offset = 0
        reasons_tree = None
        if with_reasons:
            reasons_box = tk.LabelFrame(tab, text='Hata Nedenleri (en sık)', bg=PANEL, fg=YELLOW,
                                        font=('Segoe UI', 8, 'bold'), bd=1, relief='groove', padx=4, pady=4)
            reasons_box.grid(row=0, column=0, columnspan=2, sticky='ew', padx=6, pady=(6, 2))
            reasons_box.grid_columnconfigure(0, weight=1)
            reasons_tree = ttk.Treeview(reasons_box, columns=('Neden', 'Adet'), show='headings',
                                        height=4, selectmode='browse')
            reasons_tree.heading('Neden', text='Neden')
            reasons_tree.heading('Adet', text='Adet')
            reasons_tree.column('Neden', width=430, anchor='w', stretch=True)
            reasons_tree.column('Adet', width=60, anchor='center')
            if _table_tools is not None:
                try:
                    _table_tools.enhance_tree(reasons_tree, ('Neden', 'Adet'))
                except (AttributeError, tk.TclError):
                    pass
            reasons_tree.grid(row=0, column=0, sticky='ew')
            if _table_tools is not None:
                _table_tools.add_horizontal_scrollbar(reasons_tree, row=1, column=0,
                                                      columnspan=2, sticky='ew')
            row_offset = 1
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_columnconfigure(1, weight=1)
        tab.grid_rowconfigure(0 if not with_reasons else 1, weight=1)
        pane = tk.PanedWindow(tab, orient='horizontal', bg=PANEL, bd=0,
                              sashwidth=8, sashrelief='raised', sashcursor='sb_h_double_arrow')
        pane.grid(row=row_offset, column=0, columnspan=2, sticky='nsew')
        list_frame = tk.Frame(pane, bg=PANEL)
        list_frame.grid_columnconfigure(0, weight=1)
        list_frame.grid_rowconfigure(0, weight=1)
        cols = ('Dosya', 'SKU', 'Tarih')
        tree = ttk.Treeview(list_frame, columns=cols, show='headings', selectmode='browse')
        for name, width in zip(cols, (170, 150, 120)):
            tree.heading(name, text=name)
            tree.column(name, width=width, anchor='w', stretch=True)
        if _table_tools is not None:
            try:
                _table_tools.enhance_tree(tree, cols)
            except (AttributeError, tk.TclError):
                pass
        scroll = ttk.Scrollbar(list_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.grid(row=0, column=0, sticky='nsew')
        scroll.grid(row=0, column=1, sticky='ns')
        if _table_tools is not None:
            _table_tools.add_horizontal_scrollbar(tree, row=1, column=0, columnspan=2, sticky='ew')
        pane.add(list_frame, minsize=260, sticky='nsew')
        side = tk.Frame(pane, bg=PANEL)
        pane.add(side, minsize=240, sticky='nsew')
        side.grid_columnconfigure(0, weight=1)
        side.grid_rowconfigure(0, weight=3, minsize=330)
        side.grid_rowconfigure(1, weight=1, minsize=130)
        side.grid_rowconfigure(2, weight=0)
        preview = tk.Label(side, text='Önizleme için bir satır seçin', bg='#080C14', fg=MUTED,
                           anchor='center')
        preview.grid(row=0, column=0, sticky='nsew')
        detail = tk.Text(side, height=5, bg=PANEL_RAISED, fg=FG, wrap='word',
                         font=('Segoe UI', 8), relief='flat', padx=6, pady=6)
        detail.grid(row=1, column=0, sticky='nsew', pady=(6, 0))
        detail.configure(state='disabled')
        open_btn = tk.Button(side, text='📂  Çıktı Klasörünü Aç' if status == 'RENDERED' else '📄  Son Hata Raporları',
                             bg=PANEL_RAISED, fg=FG, relief='flat', font=('Segoe UI', 8),
                             padx=8, pady=4, cursor='hand2')
        open_btn.grid(row=2, column=0, sticky='ew', pady=(6, 0))
        if status == 'RENDERED':
            open_btn.configure(command=lambda: _startfile(Path(root) / 'uretilen_gorseller'))
        else:
            open_btn.configure(command=lambda: _startfile(Path(root) / 'raporlar'))
        return tree, reasons_tree, preview, detail

    ok_tree, _, ok_preview, ok_detail = _build_artifact_tab(success_tab, 'RENDERED', with_reasons=False)
    bad_tree, reasons_tree, bad_preview, bad_detail = _build_artifact_tab(fail_tab, 'REVIEW_REQUIRED', with_reasons=True)

    # ---- alt bilgi barı
    bottom = tk.Frame(shell, bg=SIDE, bd=0, highlightthickness=0)
    bottom.grid(row=3, column=0, sticky='ew', padx=6, pady=(0, 6))
    source_lbl = tk.Label(bottom, text='', bg=SIDE, fg=MUTED, font=('Segoe UI', 7), anchor='w')
    source_lbl.pack(side='left', fill='x', expand=True)

    state = {'ok_rows': [], 'bad_rows': [], 'session_rows': [], 'photo': None}

    def _set_detail(widget, text):
        widget.configure(state='normal')
        widget.delete('1.0', 'end')
        widget.insert('1.0', text)
        widget.configure(state='disabled')

    def _show_thumb(preview, path_text):
        try:
            from PIL import Image, ImageTk
            p = Path(path_text)
            if not p.is_file() or p.is_symlink():
                raise FileNotFoundError('çıktı dosyası bulunamadı:\n' + str(p))
            # Görsel, kutu boyutlarına (en-boy oranını koruyarak) sığdırılır.
            preview.update_idletasks()
            box_w = max(140, preview.winfo_width() - 8)
            box_h = max(140, preview.winfo_height() - 8)
            if box_w < 150 or box_h < 150:
                box_w, box_h = 300, 380
            with Image.open(p) as img:
                img.thumbnail((box_w, box_h), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(img.convert('RGB'))
            preview.configure(image=photo, text='')
            state['photo'] = photo
        except Exception as exc:
            state['photo'] = None
            preview.configure(image='', text='⚠ Görsel önizlemesi oluşturulamadı\n' + str(exc)[:180],
                               fg=RED)

    def _on_select(tree, rows, preview, detail, ok: bool):
        sel = tree.selection()
        if not sel:
            return
        try:
            row = rows[int(sel[0])]
        except (ValueError, IndexError):
            return
        name = Path(str(row.get('output') or '')).name or '—'
        if ok:
            _set_detail(detail,
                        f"Dosya: {row.get('output')}\nSKU: {row.get('sku')}\nKategori: {row.get('category')}\n"
                        f"Tasarım: {row.get('art_name')}\nTür: {row.get('artifact_kind')}"
                        + (f" · {row.get('overlay_cm')} cm" if row.get('artifact_kind') == 'overlay' else '')
                        + f"\nSHA256: {str(row.get('output_sha') or '—')[:32]}…\nKayıt: {row.get('updated')}")
        else:
            _set_detail(detail,
                        f"Dosya: {row.get('output')}\nSKU: {row.get('sku')}\nKategori: {row.get('category')}\n"
                        f"Tasarım: {row.get('art_name')}\nKayıt: {row.get('updated')}\n\nNEDEN:\n{row.get('message') or '—'}")
        _show_thumb(preview, str(row.get('output') or ''))

    ok_tree.bind('<<TreeviewSelect>>', lambda _e: _on_select(ok_tree, state['ok_rows'], ok_preview, ok_detail, True))
    bad_tree.bind('<<TreeviewSelect>>', lambda _e: _on_select(bad_tree, state['bad_rows'], bad_preview, bad_detail, False))

    def _session_open(_event=None):
        sel = sessions_tree.selection()
        if not sel:
            return
        try:
            idx = int(sel[0])
            row = state['session_rows'][idx]
        except (ValueError, IndexError, KeyError, tk.TclError):
            return
        report_path = str(row.get('report_path') or '')
        if report_path and Path(report_path).is_file():
            _startfile(Path(report_path))
        elif hasattr(app, 'status'):
            try:
                app.status.set('Bu tur için işlem raporu bulunamadı.')
            except Exception:
                pass

    sessions_tree.bind('<Double-1>', _session_open)

    _BANNER_COLORS = {'ok': ('#122A21', GREEN), 'resume': ('#10332B', ACCENT),
                      'warning': ('#2E161A', YELLOW), 'info': ('#22304A', BLUE)}

    def refresh():
        snap = summarize(root)
        counts = snap['counts']
        chips['ok'].configure(text=f"Başarılı: {snap['rendered']}")
        chips['fail'].configure(text=f"Başarısız: {snap['review_required']}")
        chips['pending'].configure(text=f"Yarım: {snap['pending']}")
        bg, fg = _BANNER_COLORS.get(snap['level'], _BANNER_COLORS['info'])
        banner_lbl.configure(text=snap['banner'], bg=bg, fg=fg)
        # son üretimler
        sessions_tree.delete(*sessions_tree.get_children())
        state['session_rows'] = []
        for session in snap['sessions']:
            label = session_label(session)
            idx = len(state['session_rows'])
            state['session_rows'].append({'report_path': label['report_path']})
            sessions_tree.insert('', 'end', iid=str(idx), values=(
                label['date'], label['mode'], label['stores'],
                label['successful'], label['failed'], label['status']))
        # başarılı / başarısız listeleri
        ok_rows = recent_artifacts(root, 'RENDERED', 150)
        bad_rows = recent_artifacts(root, 'REVIEW_REQUIRED', 150)
        state['ok_rows'], state['bad_rows'] = ok_rows, bad_rows
        ok_tree.delete(*ok_tree.get_children())
        for i, row in enumerate(ok_rows):
            ok_tree.insert('', 'end', iid=str(i), values=(
                Path(str(row.get('output') or '')).name, row.get('sku') or '—', row.get('updated') or '—'))
        bad_tree.delete(*bad_tree.get_children())
        for i, row in enumerate(bad_rows):
            bad_tree.insert('', 'end', iid=str(i), values=(
                Path(str(row.get('output') or '')).name, row.get('sku') or '—', row.get('updated') or '—'))
        if reasons_tree is not None:
            reasons_tree.delete(*reasons_tree.get_children())
            for group in error_reasons(root):
                reasons_tree.insert('', 'end', values=(group['reason'], group['count']))
        source_lbl.configure(text=('Kaynak (salt okunur): ' + str(root / _DB_NAME) +
                                   '  ·  Tamamlanan görseller yeniden üretilmez  ·  Link ve Excel sonuçları korunur'))
        unfinished = snap['unfinished_sessions']
        if hasattr(app, 'status'):
            try:
                app.status.set(f"Üretim kayıtları: {snap['rendered']} başarılı · "
                               f"{snap['review_required']} başarısız · {snap['pending']} yarım"
                               + (f" · {unfinished} yarıda kalan tur" if unfinished else ''))
            except Exception:
                pass

    def _resume():
        outcome = resume_via_embedded_window(app)
        if outcome.startswith('error:'):
            try:
                messagebox.showerror('Devam Ettirilemedi', outcome[len('error: '):], parent=parent)
            except Exception:
                pass

    refresh_btn.configure(command=refresh)
    resume_btn.configure(command=_resume)

    refresh()
    shell.refresh_records = refresh  # kabuk yenileme düğmesi için
    shell.pack(fill='both', expand=True)
    return shell


def resume_via_embedded_window(app) -> str:
    """Embedded V4 penceresi varsa resume_batch()'i tetikler (tek devam kod yolu).

    Pencere henüz kurulmadıysa üretim sekmesine geçer ve kullanıcıyı yönlendirir;
    hiçbir üretim kendiliğinden başlamaz, resume_batch kendi onaylarını sorar.
    Dönüş: 'delegated' | 'opened_production_tab' | 'error: <mesaj>'.
    """
    host = getattr(app, 'workbench_production_host', None)
    target = None
    for window in getattr(app, 'batch_windows', ()) or ():
        try:
            if host is not None and getattr(window, 'window', None) is host:
                target = window
                break
            if window.window.winfo_exists():
                target = target or window
        except Exception:
            continue
    try:
        if hasattr(app, 'switch_workbench_tab'):
            app.switch_workbench_tab('production')
    except Exception:
        pass
    if target is None:
        if hasattr(app, 'status'):
            try:
                app.status.set('Üretim ekranı açılıyor; hazır olunca "▶ En Son Kaldığım Yerden '
                               'Devam Et" düğmesini kullanın.')
            except Exception:
                pass
        return 'opened_production_tab'
    try:
        target.resume_batch()
        return 'delegated'
    except Exception as exc:
        return 'error: ' + str(exc)


def _call(app, name):
    fn = getattr(app, name, None)
    if callable(fn):
        try:
            fn()
        except Exception:
            pass


def _startfile(path: Path) -> None:
    try:
        if path.is_dir() or path.is_file():
            os.startfile(str(path)) if os.name == 'nt' else None
    except OSError:
        pass
