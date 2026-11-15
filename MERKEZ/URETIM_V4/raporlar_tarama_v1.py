"""Raporlar & Tarama — kanıt, denetim ve kurtarma merkezi (salt okunur).

Bu sekme hiçbir kaydı değiştirmez, hiçbir dosyayı silmez/taşımaz/yeniden
üretmez. Yalnızca denetim, tarama ve kurtarma eylemleri için kısayol
sağlar ve son oturumda geçen işlem günlüğünü gösterir.

Butonlarda kullandığı eylemler merkezdeki mevcut Center callback'lerinden
(öncü merkez fonksiyonları ile) çağrılır; hiçbir mantık bu ekranda
yeniden uygulanmaz.
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

try:
    from graphite_ui_components import module_header
except Exception:
    module_header = None

try:
    from URETIM_V4 import ui_table_v1 as _table_tools
except Exception:
    _table_tools = None

# Graphite paletiyle aynı (uretim_kayitlari_v1 / graphite_workbench_v500 ile birebir).
SIDE = '#0F1622'
PANEL = '#131C2B'
PANEL_RAISED = '#182238'
BORDER = '#22304A'
ACCENT = '#17D3A3'
BLUE = '#5AA9FF'
YELLOW = '#F0B84C'
RED = '#EF6A73'
GREEN = '#3FD98A'
FG = '#E9EFF9'
MUTED = '#66789B'


def default_state_root() -> Path:
    try:
        from URETIM_V4.unified_batch import store_v4_root  # type: ignore
        return store_v4_root()
    except Exception:
        base = os.getenv('LOCALAPPDATA')
        return (Path(base) if base else Path.home() / '.gorsel_mockup') / 'GorselMockup' / 'UnifiedV4'


def latest_error_reports(root: Path, limit: int = 6) -> list[Path]:
    reports = Path(root) / 'raporlar'
    try:
        if not reports.is_dir():
            return []
        # URETIM_INCELEME_*.json '*.json' ile de eşleşir; çift iid
        # ttk.Treeview'da "Item already exists" hatası verip paneli kırar.
        candidates = list(dict.fromkeys(
            list(reports.glob('URETIM_INCELEME_*.json')) + list(reports.glob('*.json'))))
        candidates.sort(key=lambda p: p.stat().st_mtime_ns, reverse=True)
        return candidates[: int(limit)]
    except OSError:
        return []
def build_reports_workspace(app, parent, *, state_root: Path | None = None):
    """'⚠ Raporlar & Tarama' sekmesinin içeriğini üretir."""
    import tkinter as tk
    from tkinter import ttk

    root = Path(state_root) if state_root else default_state_root()

    shell = tk.Frame(parent, bg=SIDE, bd=0, highlightthickness=0)
    shell.grid_columnconfigure(0, weight=1)
    shell.grid_columnconfigure(1, weight=1)
    shell.grid_rowconfigure(2, weight=1)

    # ---- üst bar
    top = (module_header(shell, '⚠  Raporlar & Tarama',
                         'Kanıt, denetim ve kurtarma merkezi · salt okunur')
           if module_header else tk.Frame(shell, bg=PANEL, bd=0, highlightthickness=0))
    top.grid(row=0, column=0, columnspan=2, sticky='ew', padx=6, pady=(6, 4))
    refresh_btn = tk.Button(top, text='⟳ Yenile', bg=PANEL_RAISED, fg=FG, relief='flat',
                            font=('Segoe UI', 9, 'bold'), padx=12, pady=4, cursor='hand2')
    refresh_btn.pack(side='right', padx=8, pady=6)

    # ---- tanıtım şeridi
    intro = tk.Label(shell, text='Bu sekme; sistem, klasör ve üretim sonuçlarını yalnızca okur. '
                     'Çok önemli işlemler (yedek al, kurtar) açık onay ister.',
                     bg=SIDE, fg=MUTED, font=('Segoe UI', 8), anchor='w',
                     wraplength=980, justify='left', padx=10)
    intro.grid(row=1, column=0, columnspan=2, sticky='ew', padx=6, pady=(0, 4))

    def _button(parent, label, command, *, color=PANEL_RAISED, fg=FG, row=0, column=0, span=1):
        b = tk.Button(parent, text=label, command=command, bg=color, fg=fg,
                      relief='flat', anchor='w', justify='left', cursor='hand2',
                      font=('Segoe UI', 9, 'bold'), padx=12, pady=9)
        b.grid(row=row, column=column, columnspan=span, sticky='ew', padx=5, pady=5)
        return b

    def _section_box(title, color, column, row):
        box = tk.LabelFrame(shell, text=title, bg=PANEL, fg=color,
                            font=('Segoe UI', 9, 'bold'), bd=1, relief='groove',
                            padx=8, pady=8)
        box.grid(row=row, column=column, sticky='nsew', padx=6, pady=(0, 6))
        box.grid_columnconfigure(0, weight=1)
        return box

    # ---- sol: denetimler
    left = _section_box('🔍  Denetim ve Tarama', BLUE, 0, 2)
    _call = _make_call(app)
    _button(left, '①  G3 Bütünlük Denetimi  (salt okunur)', lambda: _call('g3_audit'), row=0, column=0)
    _button(left, '②  7 Kategori SHA Kayıt Denetimi  (salt okunur)',
            lambda: _call('open_unified_audit'), row=1, column=0)
    _button(left, '③  HAM Tasarım Numara Denetimi', lambda: _call('show_ham_design_audit'),
            row=2, column=0)
    _button(left, '④  PETEK Üretim Denetimi  (salt okunur)', lambda: _call('audit_petek'),
            row=3, column=0)
    _button(left, '⑤  000 Sistem Durumu / Sağlık Raporu', lambda: _call('show_health'),
            row=4, column=0)
    _button(left, '⑥  PETEK Klasör Denetimi', lambda: _call('prepare_petek_folders'),
            row=5, column=0)

    # ---- orta/sağ: yedek & hata radarı
    mid = _section_box('💾  Yedek ve Kurtarma', GREEN, 1, 2)
    _button(mid, '⑦  SQLite Güvenli Yedek + Geri Yükleme Provası',
            lambda: _call('g3_backup'), color='#0B7A5F', fg='#FFFFFF',
            row=0, column=0)
    _button(mid, '⑧  Kesinti Kurtarma Denetimi', lambda: _call('open_crash_recovery'),
            row=1, column=0)
    _button(mid, '⑨  Silinen Çıktı Kayıtlarını Koruma', lambda: _call('archive_user_deleted_outputs'),
            row=2, column=0)
    _button(mid, '⑩  Hata Raporunu Aç', lambda: _show_error_report(), row=3, column=0)
    _button(mid, '⑪  Hata Raporunu Kopyala', lambda: _copy_error_report(), row=4, column=0)
    _button(mid, '⑫  Codex Paketi Hazırla', lambda: _prepare_codex_bundle(), row=5, column=0)

    # ---- alt: son rapor dosyaları + oturum günlüğü
    bottom = tk.Frame(shell, bg=SIDE, bd=0, highlightthickness=0)
    bottom.grid(row=3, column=0, columnspan=2, sticky='ew', padx=6, pady=(0, 6))
    bottom.grid_columnconfigure(0, weight=1)

    reports_lbl = tk.Label(bottom, text='Son rapor dosyaları (yerel raporlar/ klasörü):',
                           bg=SIDE, fg=FG, font=('Segoe UI', 9, 'bold'), anchor='w')
    reports_lbl.grid(row=0, column=0, sticky='ew', pady=(0, 3))
    reports_list = ttk.Treeview(bottom, columns=('Dosya', 'Tarih'), show='headings',
                                height=5, selectmode='browse')
    reports_list.heading('Dosya', text='Dosya')
    reports_list.heading('Tarih', text='Tarih')
    reports_list.column('Dosya', width=720, anchor='w', stretch=True)
    reports_list.column('Tarih', width=170, anchor='center')
    if _table_tools is not None:
        _table_tools.enhance_tree(reports_list, ('Dosya', 'Tarih'))
    reports_list.grid(row=1, column=0, sticky='ew')
    if _table_tools is not None:
        bottom.grid_rowconfigure(1, weight=0)
        _table_tools.add_horizontal_scrollbar(reports_list, row=2, column=0, sticky='ew')
    reports_list.bind('<Double-1>', lambda _e: _open_selected_report(reports_list, root))

    foot = tk.Label(bottom, text='Çift tık ile rapor dosyasını açabilirsiniz. '
                    'Bu panel hiçbir üretim/şablon kaydını değiştirmez.',
                    bg=SIDE, fg=MUTED, font=('Segoe UI', 7), anchor='w')
    foot.grid(row=3, column=0, sticky='ew', pady=(3, 0))

    log_lbl = tk.Label(shell, text='Bu oturumun işlem günlüğü (uygulama kapatıldığında sıfırlanır):',
                       bg=SIDE, fg=FG, font=('Segoe UI', 9, 'bold'), anchor='w')
    log_lbl.grid(row=4, column=0, columnspan=2, sticky='ew', padx=10, pady=(0, 2))
    log_box = tk.Text(shell, height=7, bg='#080C14', fg=FG, wrap='word',
                      font=('Consolas', 8), relief='flat', padx=8, pady=6)
    log_box.grid(row=5, column=0, columnspan=2, sticky='ew', padx=6, pady=(0, 6))
    log_box.configure(state='disabled')

    state = {'reports': []}

    def refresh():
        # son rapor dosyaları
        state['reports'] = latest_error_reports(root)
        reports_list.delete(*reports_list.get_children())
        for path in state['reports']:
            try:
                mtime = time.strftime('%d.%m %H:%M', time.localtime(path.stat().st_mtime))
            except OSError:
                mtime = '—'
            reports_list.insert('', 'end', iid=str(path), values=(path.name, mtime))
        # oturum günlüğü
        try:
            lines = list(getattr(app, '_recent_logs', []) or [])[-40:]
        except Exception:
            lines = []
        log_box.configure(state='normal')
        log_box.delete('1.0', 'end')
        log_box.insert('1.0', '\n'.join(lines) if lines else '(bu oturumda henüz işlem geçmedi)')
        log_box.configure(state='disabled')
        if hasattr(app, 'status'):
            try:
                app.status.set(f'Raporlar & Tarama · {len(state["reports"])} rapor dosyası bulundu')
            except Exception:
                pass

    def _show_error_report():
        try:
            from error_advisor_v498 import open_report
            open_report()
        except Exception as exc:
            if hasattr(app, 'status'):
                app.status.set('Hata raporu açılamadı: ' + str(exc))

    def _copy_error_report():
        try:
            from error_advisor_v498 import copy_report_text
            copy_report_text()
        except Exception as exc:
            if hasattr(app, 'status'):
                app.status.set('Hata raporu kopyalanamadı: ' + str(exc))

    def _prepare_codex_bundle():
        try:
            from error_advisor_v498 import prepare_codex_bundle
            prepare_codex_bundle()
        except Exception as exc:
            if hasattr(app, 'status'):
                app.status.set('Codex paketi hazırlanamadı: ' + str(exc))

    def _open_selected_report(tree, base):
        sel = tree.selection()
        if not sel:
            return
        path = Path(sel[0])
        try:
            if path.is_file() and not path.is_symlink():
                os.startfile(str(path)) if os.name == 'nt' else None
        except OSError:
            pass

    refresh_btn.configure(command=refresh)
    refresh()
    shell.refresh_reports = refresh
    shell.pack(fill='both', expand=True)
    return shell


def _make_call(app):
    def _set_status(text):
        try:
            if hasattr(app, 'status'):
                app.status.set(text)
        except Exception:
            pass

    def _call(name):
        fn = getattr(app, name, None)
        if not callable(fn):
            _set_status('Raporlar & Tarama · bu merkezde işlem tanımlı değil: ' + str(name))
            return
        try:
            fn()
        except Exception as exc:
            _set_status(f'Raporlar & Tarama · {name} başarısız: {exc}')
    return _call
