"""Tasarım Yönetimi — mevcut HAM tasarımları listele ve seç (salt okunur).

Bu modül hiçbir dosyayı silmez, taşımaz, yeniden adlandırmaz veya kopyalamaz;
HAM numara kayıt veritabanına da **yalnızca okuma** (``mode=ro``) bağlantısı
açar. Kayıtlı bir tasarımın listelenmesi ya da önizlenmesi, dosyanın diskteki
durumunu değiştirmez. Seçim yalnızca bellektedir.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
from pathlib import Path
from typing import Any

try:
    from graphite_ui_components import module_header, action_button
except Exception:  # standalone import yedek
    module_header = None
    action_button = None

FOLDER = 'HAM BASKI TASARIMLARI'
RECEIPT = '_HAM_NUMARA_GECMISI.json'
EXTENSIONS = frozenset({'.png', '.jpg', '.jpeg', '.webp'})
_NUMBER = re.compile(r'^ham([1-9][0-9]*)$', re.IGNORECASE)

try:
    from URETIM_V4 import ui_table_v1 as _table_tools
except Exception:
    _table_tools = None

# Graphite paleti (graphite_workbench_v500 ile birebir).
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


def design_folder(runtime: Path | str) -> Path:
    return Path(runtime) / FOLDER


def ham_number(name: str) -> int | None:
    match = _NUMBER.fullmatch(Path(name).stem)
    return int(match.group(1)) if match else None


def _workspace_key(runtime: Path) -> str:
    import hashlib
    return hashlib.sha256(os.path.normcase(str(Path(runtime).resolve())).encode('utf-8')).hexdigest()[:24]


def registry_path(runtime: Path | str, local_state: Path | str | None = None) -> Path:
    base = Path(local_state) if local_state else (
        Path(os.environ.get('LOCALAPPDATA') or (Path.home() / '.local/share')) / 'GorselMockup' / 'HamBaski')
    return base / ('ham_registry_' + _workspace_key(Path(runtime)) + '.sqlite3')


def list_designs(runtime: Path | str) -> list[dict[str, Any]]:
    """HAM klasöründeki geçerli görselleri döner; hata dosyaları listeyi bozmaz."""
    root = design_folder(runtime)
    rows: list[dict[str, Any]] = []
    if not root.is_dir() or root.is_symlink():
        return rows
    for directory, dirs, files in os.walk(root, followlinks=False):
        here = Path(directory)
        dirs[:] = sorted(d for d in dirs if not (here / d).is_symlink())
        for name in files:
            path = here / name
            try:
                if path.is_symlink() or not path.is_file():
                    continue
                if path.suffix.lower() not in EXTENSIONS:
                    continue
                stat = path.stat()
            except OSError:
                continue
            number = ham_number(name)
            rows.append({
                'name': path.name,
                'rel': str(path.relative_to(root)),
                'path': str(path),
                'size': int(stat.st_size),
                'mtime_ns': int(stat.st_mtime_ns),
                'ham_number': number,
            })
    rows.sort(key=lambda r: (r['ham_number'] is None, r['ham_number'] or 0, r['name'].casefold()))
    return rows


def read_registry(runtime: Path | str, local_state: Path | str | None = None) -> dict[str, Any] | None:
    """HamDesign numara kaydını **yalnız okuma** ile açar; dosya yoksa None."""
    db_path = registry_path(runtime, local_state)
    if not db_path.is_file() or db_path.is_symlink():
        return None
    try:
        con = sqlite3.connect(db_path.resolve().as_uri() + '?mode=ro', uri=True, timeout=5)
        try:
            con.row_factory = sqlite3.Row
            meta = con.execute('SELECT high FROM meta WHERE id=1').fetchone()
            active = con.execute("SELECT COUNT(*) FROM history WHERE status='ACTIVE'").fetchone()[0]
            registered = con.execute('SELECT COUNT(*) FROM history').fetchone()[0]
            active_paths = {str(r[0]) for r in con.execute("SELECT path FROM history WHERE status='ACTIVE'")}
        finally:
            con.close()
    except sqlite3.Error:
        return None
    return {'high': int(meta['high']) if meta else 0,
            'active': int(active),
            'registered': int(registered),
            'active_paths': active_paths}


def read_receipt_high(runtime: Path | str) -> int | None:
    try:
        receipt = design_folder(runtime) / RECEIPT
        if receipt.is_symlink() or not receipt.is_file():
            return None
        obj = json.loads(receipt.read_text('utf-8'))
        value = obj.get('never_reuse_up_to')
        return int(value) if isinstance(value, int) and 0 <= value <= 999_999_999 else None
    except (OSError, ValueError, TypeError):
        return None


def summarize(designs: list[dict[str, Any]], registry: dict[str, Any] | None,
              receipt_high: int | None) -> dict[str, Any]:
    numbered = [d['ham_number'] for d in designs if d['ham_number'] is not None]
    folder_high = max(numbered, default=0)
    if registry is None:
        registered = None  # kayıt dosyası yok / okunamadı
    else:
        # Boş (0 ACTIVE) kayıt veritabanı okunabilen bir kayıttır; "okunamadı"
        # değil, gerçekte sıfır kayıtlı demektir.
        active_paths = registry.get('active_paths') or set()
        registered = sum(1 for d in designs if d['rel'] in active_paths)
    high = max([folder_high, receipt_high or 0, (registry or {}).get('high', 0)])
    return {'total': len(designs), 'numbered': len(numbered), 'folder_high': folder_high,
            'pool_high': high, 'registered': registered,
            'unregistered': (len(designs) - registered) if registered is not None else None}


def format_size(size: int) -> str:
    value = float(max(0, int(size)))
    for unit in ('B', 'KB', 'MB', 'GB'):
        if value < 1024.0 or unit == 'GB':
            return (f'{value:.0f} {unit}' if unit == 'B' else f'{value:.1f} {unit}')
        value /= 1024.0
    return f'{value:.1f} GB'


def _call(app: Any, name: str) -> None:
    fn = getattr(app, name, None)
    if callable(fn):
        try:
            fn()
        except Exception:
            pass


def build_designs_workspace(app: Any, parent: Any, *, runtime: Path | str | None = None,
                            local_state: Path | str | None = None):
    """Tasarım Yönetimi sekmesinin içeriğini üretir (salt okunur)."""
    import tkinter as tk
    from tkinter import ttk

    root = Path(runtime) if runtime else Path(getattr(app, 'runtime', '.'))

    shell = tk.Frame(parent, bg=SIDE, bd=0, highlightthickness=0)
    shell.grid_columnconfigure(0, weight=1)
    shell.grid_columnconfigure(1, weight=1)
    shell.grid_rowconfigure(2, weight=1)

    top = (module_header(shell, '▦  Tasarım Yönetimi',
                         'HAM tasarımlar ve numara havuzu · salt okunur')
           if module_header else tk.Frame(shell, bg=PANEL, bd=0, highlightthickness=0))
    top.grid(row=0, column=0, columnspan=2, sticky='ew', padx=6, pady=(6, 4))
    chips: dict[str, tk.Label] = {}

    def _chip(key, text, color):
        lbl = tk.Label(top, text=text, bg=color, fg='#0F1622',
                       font=('Segoe UI', 8, 'bold'), padx=8, pady=3)
        lbl.pack(side='left', padx=4)
        chips[key] = lbl

    _chip('total', 'Toplam: –', BLUE)
    _chip('registered', 'Kayıtlı: –', GREEN)
    _chip('pool', 'Numara havuzu: –', YELLOW)

    refresh_btn = tk.Button(top, text='⟳ Yenile', bg=PANEL_RAISED, fg=FG, relief='flat',
                            font=('Segoe UI', 9, 'bold'), padx=12, pady=4, cursor='hand2')
    refresh_btn.pack(side='right', padx=8, pady=6)
    tk.Button(top, text='Klasörü Aç', bg=PANEL_RAISED, fg=FG, relief='flat',
              font=('Segoe UI', 9), padx=12, pady=4, cursor='hand2',
              command=lambda: _call(app, 'open_ham_design_folder')).pack(side='right', padx=2, pady=6)
    tk.Button(top, text='Numara Denetimi', bg=PANEL_RAISED, fg=FG, relief='flat',
              font=('Segoe UI', 8), padx=10, pady=4, cursor='hand2',
              command=lambda: _call(app, 'show_ham_design_audit')).pack(side='right', padx=2, pady=6)

    bar = tk.Frame(shell, bg=SIDE, bd=0, highlightthickness=0)
    bar.grid(row=1, column=0, columnspan=2, sticky='ew', padx=6, pady=(0, 4))
    tk.Label(bar, text='Ara:', bg=SIDE, fg=MUTED, font=('Segoe UI', 9)).pack(side='left')
    query = tk.StringVar(value='')
    search = tk.Entry(bar, textvariable=query, bg=PANEL, fg=FG, insertbackground=FG,
                      relief='flat', bd=0, highlightthickness=1, highlightbackground=BORDER,
                      highlightcolor=ACCENT, font=('Segoe UI', 9), width=34)
    search.pack(side='left', padx=(6, 10), ipady=3)
    search.bind('<Escape>', lambda _event: query.set(''))
    note = tk.Label(bar, text='Listeleme salt okunurdur; tasarım dosyalarına ve numaralara dokunulmaz.',
                    bg=SIDE, fg=MUTED, font=('Segoe UI', 8))
    note.pack(side='left', padx=6)

    columns = ('Dosya', 'Numara', 'Boyut', 'Değiştirme')
    paned = tk.PanedWindow(shell, orient='horizontal', bg=SIDE, bd=0,
                           sashwidth=8, sashrelief='raised', sashcursor='sb_h_double_arrow')
    paned.grid(row=2, column=0, columnspan=2, sticky='nsew')

    tree_frame = tk.Frame(paned, bg=PANEL, bd=0, highlightthickness=0)
    tree_frame.grid_columnconfigure(0, weight=1)
    tree_frame.grid_rowconfigure(0, weight=1)
    paned.add(tree_frame, minsize=360, sticky='nsew')

    tree = ttk.Treeview(tree_frame, columns=columns, show='headings',
                        selectmode='browse', height=18)
    widths = {'Dosya': 250, 'Numara': 70, 'Boyut': 80, 'Değiştirme': 130}
    for name in columns:
        tree.heading(name, text=name)
        tree.column(name, width=widths[name], anchor='w', stretch=(name == 'Dosya'))
    if _table_tools is not None:
        _table_tools.enhance_tree(tree, columns)
    tree_scroll = ttk.Scrollbar(tree_frame, orient='vertical', command=tree.yview)
    tree.configure(yscrollcommand=tree_scroll.set)
    tree.grid(row=0, column=0, sticky='nsew')
    tree_scroll.grid(row=0, column=1, sticky='ns')
    if _table_tools is not None:
        _table_tools.add_horizontal_scrollbar(tree, row=1, column=0,
                                              columnspan=2, sticky='ew')
    tree.tag_configure('registered', foreground='#8DEBD5')
    tree.tag_configure('loose', foreground='#F0B84C')

    side_panel = tk.Frame(paned, bg=PANEL, bd=0, highlightthickness=0)
    paned.add(side_panel, minsize=250, sticky='nsew')
    tk.Label(side_panel, text='ÖNİZLEME', bg=PANEL_RAISED, fg=FG,
             font=('Segoe UI', 9, 'bold'), anchor='w', padx=10, pady=6).pack(fill='x')
    preview = tk.Label(side_panel, text='Bir tasarım seçin.', bg=PANEL, fg=MUTED,
                       font=('Segoe UI', 10), anchor='center')
    preview.pack(fill='both', expand=True, padx=10, pady=10)
    detail = tk.Label(side_panel, text='', bg=PANEL, fg='#93A6C4', justify='left',
                      wraplength=310, anchor='nw', font=('Segoe UI', 8))
    detail.pack(fill='x', padx=10, pady=(0, 10))

    state: dict[str, Any] = {'rows': [], 'photo': None, 'query': ''}

    def _selection_path() -> Path | None:
        selection = tree.selection()
        if not selection:
            return None
        try:
            index = int(selection[0])
        except ValueError:
            return None
        rows = state['rows']
        if 0 <= index < len(rows):
            return Path(rows[index]['path'])
        return None

    def _show_preview(*_args):
        path = _selection_path()
        if path is None:
            preview.configure(image='', text='Bir tasarım seçin.')
            detail.configure(text='')
            return
        row = next((r for r in state['rows'] if r['path'] == str(path)), None)
        try:
            from PIL import Image, ImageTk, ImageOps
            with Image.open(path) as src:
                thumb = ImageOps.exif_transpose(src).convert('RGB')
                thumb.thumbnail((300, 300), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(thumb, master=shell)
            state['photo'] = photo  # referansı tut
            preview.configure(image=photo, text='')
        except Exception as exc:  # bozuk dosyada panel kilitlenmez
            state['photo'] = None
            preview.configure(image='', text='Önizleme açılamadı\n' + str(exc)[:120])
        if row:
            import datetime
            try:
                mtime = datetime.datetime.fromtimestamp(row['mtime_ns'] / 1e9).strftime('%Y-%m-%d %H:%M')
            except (OSError, OverflowError, ValueError):
                mtime = '—'
            number = row['ham_number']
            detail.configure(text=(
                f"Dosya: {row['name']}\n"
                f"Yol: {row['rel']}\n"
                f"HAM numarası: {number if number is not None else '— (numarasız)'}\n"
                f"Boyut: {format_size(row['size'])}\n"
                f"Değiştirme: {mtime}"))

    def _matches(row: dict[str, Any]) -> bool:
        needle = state['query']
        if not needle:
            return True
        haystack = f"{row['name']} {row['rel']} {row['ham_number'] or ''}".casefold()
        return needle in haystack

    def refresh(*_args):
        previous_path = _selection_path()
        state['query'] = query.get().casefold().strip()
        designs = list_designs(root)
        registry = read_registry(root, local_state)
        summary = summarize(designs, registry, read_receipt_high(root))
        visible = [row for row in designs if _matches(row)]
        state['rows'] = visible
        tree.delete(*tree.get_children())
        import datetime
        for index, row in enumerate(visible):
            try:
                mtime = datetime.datetime.fromtimestamp(row['mtime_ns'] / 1e9).strftime('%Y-%m-%d %H:%M')
            except (OSError, OverflowError, ValueError):
                mtime = '—'
            number = row['ham_number']
            registered = None
            if registry is not None:
                registered = row['rel'] in registry.get('active_paths', set())
            tag = 'registered' if registered else ('loose' if registered is False else 'registered')
            tree.insert('', 'end', iid=str(index),
                        values=(row['name'], str(number) if number is not None else '—',
                                format_size(row['size']), mtime),
                        tags=(tag,))
        chips['total'].configure(text=f"Toplam: {summary['total']}")
        registered = summary['registered']
        chips['registered'].configure(
            text=(f"Kayıtlı: {registered}" if registered is not None else 'Kayıtlı: —'))
        chips['pool'].configure(text=f"Numara havuzu: {summary['pool_high']}")
        if not Path(root).is_dir():
            if hasattr(app, 'status'):
                try:
                    app.status.set(f'Tasarım Yönetimi: HAM klasörü bulunamadı: {root}')
                except Exception:
                    pass
            _show_preview()
            return
        # Seçili tasarımı liste yenilenince de koru (yol üzerinden).
        if previous_path is not None:
            for index, row in enumerate(visible):
                if row['path'] == str(previous_path):
                    tree.selection_set(str(index))
                    tree.see(str(index))
                    break
        if hasattr(app, 'status'):
            try:
                app.status.set(
                    f"Tasarım Yönetimi: {summary['total']} tasarım · "
                    f"numara havuzu {summary['pool_high']} · "
                    + (f"{registered} kayıtlı" if registered is not None else 'kayıt durumu okunamadı'))
            except Exception:
                pass
        _show_preview()

    # Arama yazarken her tuşta 3315 dosyayı yeniden taramamak için kısa bir
    # bekleme (debounce). Yenile düğmesi ve ilk yükleme anında çalışır.
    _debounce: dict[str, Any] = {'id': None}

    def _on_query_write(*_args):
        if _debounce['id'] is not None:
            try:
                shell.after_cancel(_debounce['id'])
            except Exception:
                pass
        _debounce['id'] = shell.after(220, lambda: refresh())

    query.trace_add('write', _on_query_write)
    tree.bind('<<TreeviewSelect>>', _show_preview)
    tree.bind('<Double-1>', lambda _event: _call(app, 'open_ham_design_folder'))
    refresh_btn.configure(command=refresh)

    refresh()
    shell.refresh_designs = refresh  # kabuk yenileme düğmesi için
    shell.designs_tree = tree  # seçim/yenileme testi için (salt görüntüleme)
    shell.pack(fill='both', expand=True)
    return shell
