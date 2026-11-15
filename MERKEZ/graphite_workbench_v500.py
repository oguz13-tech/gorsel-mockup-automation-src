"""Graphite Dark V5 workbench shell.

This is a presentation-only shell around the existing callbacks.  It does not
scan templates, write corners, touch PETEK masks or open SQLite on construction.
The center canvas is intentionally a neutral preview surface until the user
opens a real review/production workflow.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, scrolledtext
from pathlib import Path
from PIL import Image, ImageTk, ImageOps

try:
    from URETIM_V4 import ui_table_v1 as _table_tools
except Exception:
    _table_tools = None

from dark_theme_v42 import BG, FG, MUTED, UI_MOR_THEME
from error_advisor_v498 import register_listener, open_report, copy_report_text, prepare_codex_bundle
from ui_layout_v498 import LayoutEditor

SIDE = '#0F1622'
SURFACE = '#0B101B'
PANEL = '#131C2B'
PANEL_RAISED = '#182238'
BORDER = '#22304A'
ACCENT = '#17D3A3'
ACCENT_DARK = '#0B7A5F'
BLUE = '#5AA9FF'
YELLOW = '#F0B84C'
RED = '#EF6A73'
GREEN = '#3FD98A'
PURPLE = '#8A7CF0'

# Single source of truth for the desktop shell's first-level workspaces.  The
# callbacks are intentionally resolved by ``switch_tab`` below; keeping the
# registry declarative prevents sidebar/tab-bar drift while preserving each
# existing module's implementation and data boundary.
WORKBENCH_TABS = (
    ('home', 'Ana Panel', 'Ana Panel · günlük operasyon akışının başlangıcı'),
    ('review', 'Şablon İnceleme', 'Şablon İnceleme · 4 köşe ve insan onayı'),
    ('uploads', 'Görsel Yükleme Merkezi', 'Görsel Yükleme Merkezi · mockup ve tasarım alımı'),
    ('petek', 'PETEK Maskesi', 'PETEK Maskesi · ızgara, kavis ve kalite kontrolü'),
    ('production', 'Görsel Üretim', 'Görsel Üretim · seri mockup ve mağaza akışı'),
    ('designs', 'Tasarım Yönetimi', 'Tasarım Yönetimi · HAM tasarımlar ve numara havuzu'),
    ('stores', 'Mağaza Profilleri', 'Mağaza Profilleri · mağaza bazlı üretim seçenekleri'),
    ('reports', 'Üretim Kayıtları', 'Üretim Kayıtları · son üretimler ve kaldığı yerden devam'),
    ('reporting', 'Raporlar & Tarama', 'Raporlar & Tarama · kanıt, denetim, yedek ve kurtarma merkezi'),
    ('tools', 'Araçlar', 'Araçlar · profesyonel yardımcı araçlar'),
)


def _records_noop():
    """Üretim Kayıtları panosu yüklenemediğinde sessiz no-op yerine kalıcı işaretçi."""


def _frame(parent, bg=SURFACE, **kwargs):
    return tk.Frame(parent, bg=bg, bd=0, highlightthickness=0, **kwargs)


def _label(parent, text='', size=10, color=FG, bold=False, bg=None, **kwargs):
    return tk.Label(parent, text=text, bg=bg or parent.cget('bg'), fg=color,
                    font=('Segoe UI', size, 'bold' if bold else 'normal'),
                    anchor='w', justify='left', **kwargs)


def _button(parent, text, command=None, color=PANEL_RAISED, fg=FG, size=9, **kwargs):
    # Explicit focus participation is important for keyboard-only operation
    # and for UIA-based automation.  Tk's platform defaults vary and can make
    # otherwise visible buttons unreachable with Tab.
    kwargs.setdefault('takefocus', True)
    return tk.Button(parent, text=text, command=command, bg=color, fg=fg,
                     activebackground=ACCENT_DARK, activeforeground='#ffffff',
                     font=('Segoe UI', size, 'bold'), relief='flat', bd=0,
                     highlightthickness=1, highlightcolor=ACCENT,
                     padx=10, pady=7, cursor='hand2', **kwargs)


def _section(parent, title, color=ACCENT):
    box = _frame(parent, PANEL)
    box.pack(fill='x', padx=8, pady=(0, 8))
    head = _frame(box, PANEL_RAISED, height=31)
    head.pack(fill='x')
    _label(head, title, 10, FG, True, PANEL_RAISED).pack(side='left', padx=10, pady=7)
    _frame(head, color, width=4).pack(side='right', fill='y')
    body = _frame(box, PANEL)
    body.pack(fill='x', padx=10, pady=9)
    return body


def _status_chip(parent, text, color):
    chip = tk.Label(parent, text=text, bg=color, fg='#04140E',
                    font=('Segoe UI', 8, 'bold'), padx=7, pady=3)
    chip.pack(side='left', padx=3)
    return chip


def build_dashboard(app):
    root = app.root
    root.title('Görsel Üretim Merkezi V5.0 · Graphite Workbench')
    root.geometry('1440x900')
    root.minsize(1120, 720)
    root.configure(bg=SURFACE)

    # Keep compatibility with existing callbacks and status updates.
    app._wheel_canvas = None
    # Template review is the operator's first workspace.  Keep the shell and
    # all other workflows available, but greet the user with the real review
    # surface instead of an otherwise empty dashboard preview.
    app.workbench_tab = tk.StringVar(value='review')
    app.workbench_context = tk.StringVar(value='Şablon İnceleme · 4 köşe ve insan onayı')
    app.workbench_title = tk.StringVar(value='Şablon İnceleme / Graphite Çalışma Tezgâhı')
    app.workbench_category = tk.StringVar(value='06 · Petek Kapama')
    app.workbench_filter = tk.StringVar(value='Tümü')
    app.workbench_search = tk.StringVar(value='')
    app.workbench_preview_mode = tk.StringVar(value='final')
    app.workbench_corners = tk.BooleanVar(value=True)
    app.workbench_petek_mask = tk.BooleanVar(value=True)
    app.workbench_list_width = tk.IntVar(value=238)
    app.workbench_inspector_width = tk.IntVar(value=350)
    app.workbench_effects = {
        'design': tk.BooleanVar(value=True),
        'reflection': tk.BooleanVar(value=True),
        'shadow': tk.BooleanVar(value=True),
    }
    app.workbench_edge_softness = tk.DoubleVar(value=30.0)
    app.workbench_image_path = None
    app.workbench_photo = None
    app.workbench_preview_photo = None

    shell = _frame(root, SURFACE)
    shell.pack(fill='both', expand=True)
    shell.grid_columnconfigure(0, weight=0, minsize=205)
    shell.grid_columnconfigure(1, weight=1)
    # The native Windows title bar is the only window heading.  The former
    # in-app ``top`` row reserved 46px for a duplicate Graphite title/search
    # strip, which made both side panels stop short of the usable height.
    # Keep the shell to two real rows: the workbench body and its status bar.
    shell.grid_rowconfigure(0, weight=1)
    shell.grid_rowconfigure(1, weight=0)
    shell.grid_rowconfigure(2, weight=0, minsize=0)

    # Left navigation
    nav = _frame(shell, SIDE, width=205)
    nav.grid(row=0, column=0, rowspan=2, sticky='nsew')
    nav.grid_propagate(False)
    nav_toggle = _button(nav, '◀', color=PANEL_RAISED, size=10)
    nav_toggle.configure(width=3, padx=0, pady=5,
                        relief='flat', takefocus=True,
                        text='◀',
                        command=lambda: set_navigation_collapsed(
                            not getattr(app, 'workbench_nav_collapsed', False)))
    nav_toggle.pack(fill='x', padx=6, pady=(7, 5))
    nav_toggle.configure(text='◀', state='normal')
    nav_body = _frame(nav, SIDE)
    nav_body.pack(fill='both', expand=True)
    app.workbench_nav_collapsed = False

    def set_navigation_collapsed(collapsed):
        """Collapse only Graphite's outer navigation, preserving the editor.

        The real review page and its callbacks remain mounted in the center;
        this only changes the Tk shell column and keeps the toggle reachable.
        """
        try:
            app.workbench_nav_collapsed = bool(collapsed)
            if collapsed:
                nav_body.pack_forget()
                nav.configure(width=38)
                shell.grid_columnconfigure(0, minsize=38)
                nav_toggle.configure(text='▶', width=3)
            else:
                shell.grid_columnconfigure(0, minsize=205)
                nav.configure(width=205)
                nav_body.pack(fill='both', expand=True)
                nav_toggle.configure(text='◀', width=3)
            root.update_idletasks()
        except tk.TclError:
            pass

    app.toggle_workbench_navigation = set_navigation_collapsed

    brand = _frame(nav_body, SIDE)
    brand.pack(fill='x', padx=14, pady=(18, 12))
    _label(brand, '✦  Görsel Üretim', 15, '#D6E8FF', True, SIDE).pack(fill='x')
    _label(brand, 'MERKEZİ  ·  V5.0', 9, MUTED, False, SIDE).pack(fill='x', pady=(3, 0))
    _frame(nav_body, BORDER, height=1).pack(fill='x', padx=12, pady=(0, 12))

    tab_buttons = {}
    tab_bar_buttons = {}  # pre-declared so switch_tab's closure always sees the name
    tab_meta = {key: (title, context) for key, title, context in WORKBENCH_TABS}
    app.workbench_routes = {key: {'title': title, 'context': context}
                            for key, title, context in WORKBENCH_TABS}

    def _set_production_layout(active):
        """Give the real production workbench the complete content canvas.

        The Graphite shell owns navigation only.  When production is active,
        the editor inspector, preview rail and template-list chrome are hidden
        instead of being nested beside the real V4 production form.  The
        production widget itself remains mounted so selections and an active
        queue survive a tab switch.
        """
        try:
            if active:
                list_pane.grid_remove(); sash_left.grid_remove()
                inspector.grid_remove(); sash_right.grid_remove()
                if bottom is not None:
                    bottom.grid_remove()
                stage_wrap.grid_configure(row=0, column=0, columnspan=5,
                                          sticky='nsew', padx=0, pady=0)
                tab_bar.grid_remove()
                toolbar.grid_remove()
                canvas.grid_remove()
                # Keep the native WebView2 parent mapped while another tab is
                # active.  Unmapping this frame makes Edge/WebView2 recreate
                # its surface on the next show, which turns a tab switch into
                # a full page reload.  It stays behind the production host.
                review_host.grid(row=0, column=0, sticky='nsew')
                review_host.lower(production_host)
                preview_hint_label.place_forget()
                preview_tag_label.place_forget()
                production_host.grid(row=0, column=0, sticky='nsew')
                production_host.lift()
                body.grid_columnconfigure(0, weight=0, minsize=0)
                body.grid_columnconfigure(2, weight=1)
                body.grid_columnconfigure(4, weight=0, minsize=0)
                shell.grid_rowconfigure(2, weight=0, minsize=0)
            else:
                production_host.grid_remove()
                canvas.grid(row=0, column=0, sticky='nsew')
                preview_hint_label.place(relx=.5, rely=.06, anchor='center')
                preview_tag_label.place(relx=.5, rely=.91, anchor='center')
                list_pane.grid(); sash_left.grid()
                inspector.grid(); sash_right.grid()
                if bottom is not None:
                    bottom.grid()
                stage_wrap.grid_configure(row=0, column=2, columnspan=1,
                                          sticky='nsew', padx=5, pady=(0, 8))
                tab_bar.grid()
                toolbar.grid()
                body.grid_columnconfigure(0, weight=0, minsize=app.workbench_list_width.get())
                body.grid_columnconfigure(2, weight=1)
                body.grid_columnconfigure(4, weight=0, minsize=app.workbench_inspector_width.get())
                shell.grid_rowconfigure(2, weight=0, minsize=0)
        except (NameError, tk.TclError):
            # The callback can be reached only after the widgets are built;
            # keeping this guard makes startup/reload safe for Tk teardown.
            return

    def _set_review_layout(active):
        """Mount the real review WebView2 surface into this workbench."""
        try:
            if active:
                list_pane.grid_remove(); sash_left.grid_remove()
                inspector.grid_remove(); sash_right.grid_remove()
                stage_wrap.grid_configure(row=0, column=0, columnspan=5,
                                          sticky='nsew', padx=0, pady=0)
                tab_bar.grid_remove()
                toolbar.grid_remove()
                canvas.grid_remove()
                production_host.grid_remove()
                review_host.grid(row=0, column=0, sticky='nsew')
                review_host.lift()
                body.grid_columnconfigure(0, weight=1, minsize=0)
                body.grid_columnconfigure(1, weight=0, minsize=0)
                body.grid_columnconfigure(4, weight=0, minsize=0)
            else:
                # Do not unmap the native WebView2 host when returning to the
                # dashboard.  Keep its renderer/session warm and place the
                # ordinary preview canvas above it instead.
                review_host.grid(row=0, column=0, sticky='nsew')
                review_host.lower(canvas)
                if app.workbench_tab.get() not in ('production',):
                    canvas.grid(row=0, column=0, sticky='nsew')
                    canvas.lift()
                list_pane.grid(); sash_left.grid()
                inspector.grid(); sash_right.grid()
                stage_wrap.grid_configure(row=0, column=2, columnspan=1,
                                          sticky='nsew', padx=5, pady=(0, 8))
                tab_bar.grid()
                toolbar.grid()
                body.grid_columnconfigure(0, weight=0, minsize=app.workbench_list_width.get())
                body.grid_columnconfigure(2, weight=1)
                body.grid_columnconfigure(4, weight=0, minsize=app.workbench_inspector_width.get())
        except (NameError, tk.TclError):
            return

    def _set_records_layout(active):
        """Mount the persistent production-records workspace in the center."""
        try:
            if active:
                _ensure_records_workspace()
                list_pane.grid_remove(); sash_left.grid_remove()
                inspector.grid_remove(); sash_right.grid_remove()
                if bottom is not None:
                    bottom.grid_remove()
                stage_wrap.grid_configure(row=0, column=0, columnspan=5,
                                          sticky='nsew', padx=0, pady=0)
                tab_bar.grid_remove()
                toolbar.grid_remove()
                canvas.grid_remove()
                production_host.grid_remove()
                upload_host.grid_remove()
                review_host.grid(row=0, column=0, sticky='nsew')
                review_host.lower(records_host)
                preview_hint_label.place_forget()
                preview_tag_label.place_forget()
                records_host.grid(row=0, column=0, sticky='nsew')
                records_host.lift()
                body.grid_columnconfigure(0, weight=1, minsize=0)
                body.grid_columnconfigure(1, weight=0, minsize=0)
                body.grid_columnconfigure(4, weight=0, minsize=0)
                shell.grid_rowconfigure(2, weight=0, minsize=0)
            else:
                records_host.grid_remove()
        except (NameError, tk.TclError):
            return

    def _set_reports_layout(active):
        """Hamtanrtıma (raporlar/taramalar) merkezi için layout."""
        try:
            if active:
                _ensure_reports_workspace()
                list_pane.grid_remove(); sash_left.grid_remove()
                inspector.grid_remove(); sash_right.grid_remove()
                if bottom is not None:
                    bottom.grid_remove()
                stage_wrap.grid_configure(row=0, column=0, columnspan=5,
                                          sticky='nsew', padx=0, pady=0)
                tab_bar.grid_remove()
                toolbar.grid_remove()
                canvas.grid_remove()
                production_host.grid_remove()
                upload_host.grid_remove()
                review_host.grid(row=0, column=0, sticky='nsew')
                review_host.lower(reports_host)
                preview_hint_label.place_forget()
                preview_tag_label.place_forget()
                records_host.grid_remove()
                reports_host.grid(row=0, column=0, sticky='nsew')
                reports_host.lift()
                body.grid_columnconfigure(0, weight=1, minsize=0)
                body.grid_columnconfigure(1, weight=0, minsize=0)
                body.grid_columnconfigure(4, weight=0, minsize=0)
                shell.grid_rowconfigure(2, weight=0, minsize=0)
            else:
                reports_host.grid_remove()
        except (NameError, tk.TclError):
            return

    def _set_designs_layout(active):
        """Mount the real Tasarım Yönetimi workspace in the center."""
        try:
            if active:
                _ensure_designs_workspace()
                list_pane.grid_remove(); sash_left.grid_remove()
                inspector.grid_remove(); sash_right.grid_remove()
                if bottom is not None:
                    bottom.grid_remove()
                stage_wrap.grid_configure(row=0, column=0, columnspan=5,
                                          sticky='nsew', padx=0, pady=0)
                tab_bar.grid_remove()
                toolbar.grid_remove()
                canvas.grid_remove()
                production_host.grid_remove()
                upload_host.grid_remove()
                records_host.grid_remove()
                reports_host.grid_remove()
                review_host.grid(row=0, column=0, sticky='nsew')
                review_host.lower(designs_host)
                preview_hint_label.place_forget()
                preview_tag_label.place_forget()
                designs_host.grid(row=0, column=0, sticky='nsew')
                designs_host.lift()
                body.grid_columnconfigure(0, weight=1, minsize=0)
                body.grid_columnconfigure(1, weight=0, minsize=0)
                body.grid_columnconfigure(4, weight=0, minsize=0)
                shell.grid_rowconfigure(2, weight=0, minsize=0)
            else:
                designs_host.grid_remove()
        except (NameError, tk.TclError):
            return

    def _set_stores_layout(active):
        """Mount the real Mağaza Profilleri workspace in the center."""
        try:
            if active:
                _ensure_stores_workspace()
                list_pane.grid_remove(); sash_left.grid_remove()
                inspector.grid_remove(); sash_right.grid_remove()
                if bottom is not None:
                    bottom.grid_remove()
                stage_wrap.grid_configure(row=0, column=0, columnspan=5,
                                          sticky='nsew', padx=0, pady=0)
                tab_bar.grid_remove()
                toolbar.grid_remove()
                canvas.grid_remove()
                production_host.grid_remove()
                upload_host.grid_remove()
                records_host.grid_remove()
                reports_host.grid_remove()
                review_host.grid(row=0, column=0, sticky='nsew')
                review_host.lower(stores_host)
                preview_hint_label.place_forget()
                preview_tag_label.place_forget()
                stores_host.grid(row=0, column=0, sticky='nsew')
                stores_host.lift()
                body.grid_columnconfigure(0, weight=1, minsize=0)
                body.grid_columnconfigure(1, weight=0, minsize=0)
                body.grid_columnconfigure(4, weight=0, minsize=0)
                shell.grid_rowconfigure(2, weight=0, minsize=0)
            else:
                stores_host.grid_remove()
        except (NameError, tk.TclError):
            return

    def _set_upload_layout(active):
        """Mount the central uploader in the same main workspace surface."""
        try:
            if active:
                list_pane.grid_remove(); sash_left.grid_remove()
                inspector.grid_remove(); sash_right.grid_remove()
                if bottom is not None:
                    bottom.grid_remove()
                stage_wrap.grid_configure(row=0, column=0, columnspan=5,
                                          sticky='nsew', padx=0, pady=0)
                tab_bar.grid_remove()
                toolbar.grid_remove()
                canvas.grid_remove()
                production_host.grid_remove()
                review_host.grid(row=0, column=0, sticky='nsew')
                review_host.lower(upload_host)
                upload_host.grid(row=0, column=0, sticky='nsew')
                upload_host.lift()
                body.grid_columnconfigure(0, weight=1, minsize=0)
                body.grid_columnconfigure(1, weight=0, minsize=0)
                body.grid_columnconfigure(4, weight=0, minsize=0)
            else:
                upload_host.grid_remove()
        except (NameError, tk.TclError):
            return

    def switch_tab(mode):
        if mode not in tab_meta:
            mode = 'home'
        app.workbench_tab.set(mode)
        title, context = tab_meta[mode]
        app.workbench_context.set(context)
        app.workbench_title.set(title + ' / Graphite Çalışma Tezgâhı')
        try:
            _set_records_layout(False)
        except Exception:
            pass
        try:
            _set_reports_layout(False)
        except Exception:
            pass
        try:
            _set_designs_layout(False)
        except Exception:
            pass
        try:
            _set_stores_layout(False)
        except Exception:
            pass
        try:
            _set_home_layout(False)
        except Exception:
            pass
        if hasattr(app, 'status'):
            if mode == 'designs':
                app.status.set('Tasarım Yönetimi · mevcut HAM tasarımlar listelendi (salt okunur).')
            elif mode == 'stores':
                app.status.set('Mağaza Profilleri · kayıtlı ayarlar ve şablon havuzu yüklendi.')
            else:
                app.status.set(context + ' · mevcut motorlar korunuyor.')
        if mode == 'production':
            _set_review_layout(False)
            _set_upload_layout(False)
            _set_production_layout(True)
            # Production is embedded into the same Graphite shell.  The
            # existing V4 engine/UI remains the single source of truth.
            try:
                app.open_unified_v4()
            except Exception as exc:
                app.status.set('Üretim çalışma alanı açılamadı: ' + str(exc))
        elif mode == 'uploads':
            _set_production_layout(False)
            _set_review_layout(False)
            _set_upload_layout(True)
            try:
                if not getattr(app, '_upload_center', None):
                    from upload_center_v500 import build_upload_center
                    app._upload_center = build_upload_center(app, upload_host)
            except Exception as exc:
                app.status.set('Görsel yükleme merkezi açılamadı: ' + str(exc))
        else:
            _set_production_layout(False)
            _set_upload_layout(False)
            _set_review_layout(mode in ('review', 'petek', 'tools'))
            if mode == 'home':
                _set_home_layout(True)
            if mode == 'reports':
                _set_records_layout(True)
            if mode == 'reporting':
                _set_reports_layout(True)
            if mode == 'designs':
                _set_designs_layout(True)
            if mode == 'stores':
                _set_stores_layout(True)
            if mode in ('review', 'petek'):
                # The tab itself is the real workflow entry point.  The
                # existing confirmation/backup/identity gates remain in the
                # center callback; no second editor is created here.
                try:
                    if mode == 'petek' and callable(getattr(app, 'open_legacy_petek', None)):
                        app.open_legacy_petek()
                    else:
                        app.open_legacy_review()
                except Exception as exc:
                    app.status.set('Şablon inceleme açılamadı: ' + str(exc))
            elif mode == 'tools':
                # The Araçlar screen is a first-class Graphite tab.  It reuses
                # the authenticated /tools page of the same loopback service;
                # the Şablon İnceleme (4-köşe) page never opens for it.
                try:
                    app.open_legacy_tools()
                except Exception as exc:
                    app.status.set('Araçlar ekranı açılamadı: ' + str(exc))
        for key, button in tab_buttons.items():
            try:
                button.configure(bg='#10332B' if key == mode else SIDE)
            except tk.TclError:
                pass
        for key, button in tab_bar_buttons.items():
            try:
                button.configure(bg='#10332B' if key == mode else PANEL_RAISED)
            except tk.TclError:
                pass

    app.switch_workbench_tab = switch_tab

    def open_current_workflow():
        mode = app.workbench_tab.get()
        if mode in ('review', 'petek'):
            if mode == 'petek' and callable(getattr(app, 'open_legacy_petek', None)):
                app.open_legacy_petek()
            else:
                app.open_legacy_review()
        elif mode == 'tools':
            app.open_legacy_tools()
        elif mode in ('production', 'stores'):
            app.open_unified_v4()
        elif mode == 'uploads':
            app.status.set('Görsel Yükleme Merkezi hazır; kaynak seçimi bekleniyor.')
        elif mode == 'designs':
            app.open_ham_design_folder()
        elif mode == 'reports':
            refresh = getattr(app, 'refresh_records_workspace', None)
            if callable(refresh):
                refresh()
            else:
                app.show_health()
        elif mode == 'reporting':
            refresh = getattr(app, 'refresh_reports_workspace', None)
            if callable(refresh):
                refresh()
            else:
                app.show_health()
        else:
            app.status.set('Ana Panel hazır; bir çalışma sekmesi seçin.')

    app.open_current_workflow = open_current_workflow

    def explain_shortcut(event):
        # The review editor owns its own C/V/Enter/N/P/arrow/Space handlers.
        # The shell should explain why those keys have no effect here instead
        # of appearing to swallow them silently.
        try:
            widget_class = str(event.widget.winfo_class())
        except Exception:
            widget_class = ''
        if widget_class in {'Entry', 'TEntry', 'Text', 'TCombobox', 'Button', 'TButton'}:
            return
        if getattr(event, 'state', 0) & 0x0004:  # Ctrl/Command-style editing
            return
        key = str(getattr(event, 'keysym', '') or '').lower()
        if key in {'c', 'v', 'n', 'p', 'return', 'space', 'left', 'right'}:
            app.status.set('Bu kısayol yalnız Şablon İnceleme veya PETEK editörü aktifken çalışır.')
    root.bind_all('<KeyPress>', explain_shortcut, add='+')

    def nav_button(title, callback, active=False, color=None, mode=None):
        button = _button(nav_body, title, callback, color=color or ('#10332B' if active else SIDE),
                         size=9, anchor='w')
        button.pack(fill='x', padx=9, pady=2)
        if mode:
            tab_buttons[mode] = button
        return button

    # Expose the sidebar tab registry for diagnostics/contract tests.
    app.workbench_nav_buttons = tab_buttons

    nav_button('⌂  Ana Panel', lambda: switch_tab('home'), mode='home')
    nav_button('▣  Görsel Üretim', lambda: switch_tab('production'), mode='production')
    nav_button('⇧  Görsel Yükleme Merkezi', lambda: switch_tab('uploads'), mode='uploads')
    app.review_button = nav_button('▤  Şablon İnceleme', lambda: switch_tab('review'),
                                   True, mode='review')
    nav_button('▥  PETEK Maskesi', lambda: switch_tab('petek'), mode='petek')
    nav_button('▦  Tasarım Yönetimi', lambda: switch_tab('designs'), mode='designs')
    nav_button('▧  Mağaza Profilleri', lambda: switch_tab('stores'), mode='stores')
    nav_button('▤  Excel ve Link İşlemleri', app.open_links_v493)
    nav_button('✓  Üretim Kayıtları', lambda: switch_tab('reports'), mode='reports')
    nav_button('⚠  Raporlar & Tarama', lambda: switch_tab('reporting'), mode='reporting')
    nav_button('⚙  Ayarlar', lambda: LayoutEditor(root, 'dashboard', on_save=app._refresh_visual_cards))
    nav_button('⚒  Araçlar', lambda: switch_tab('tools'), mode='tools')
    app.v6_button = nav_button('🖥️  V6 Denetim Panosu', app.open_legacy_v6)
    # Kimliği doğrulanmış inceleme servisini (Şablon İnceleyici / 8080 Flask +
    # WebView2) tek düğmeyle güvenli durdurur; bilinmeyen süreçlere dokunmaz.
    app.review_stop_button = nav_button('⏹  Şablon İnceleyiciyi Güvenle Kapat',
                                        app.stop_legacy_editor, color='#2A2410')
    app.tools_button = nav_button('⏻  Programı Kapat', app.close, color='#2E161A')
    _label(nav_body, 'SİSTEM DURUMU', 8, MUTED, True, SIDE).pack(side='bottom', anchor='w', padx=15, pady=(0, 5))
    _status_chip(nav_body, '● Hazır', GREEN)
    _label(nav_body, 'Kaynaklar korunuyor', 8, MUTED, False, SIDE).pack(side='bottom', anchor='w', padx=15, pady=(0, 15))

    # The duplicate in-app title/search block is intentionally not created.
    # The operating-system title bar remains the only window heading; the
    # workbench body starts immediately below it.

    # Main three-pane workbench.  It is the first (and only) expandable shell
    # row, so every resize is propagated to the list, canvas, and inspector.
    def _make_sash(parent):
        s = tk.Frame(parent, bg=BORDER, width=6, cursor='sb_h_double_arrow',
                     relief='raised', bd=0, highlightthickness=0)
        return s

    body = _frame(shell, SURFACE)
    body.grid(row=0, column=1, sticky='nsew')
    body.grid_columnconfigure(0, weight=0, minsize=app.workbench_list_width.get())
    body.grid_columnconfigure(1, weight=0, minsize=6)
    body.grid_columnconfigure(2, weight=1)
    body.grid_columnconfigure(3, weight=0, minsize=6)
    body.grid_columnconfigure(4, weight=0, minsize=app.workbench_inspector_width.get())
    body.grid_rowconfigure(0, weight=1)

    list_pane = _frame(body, PANEL, width=app.workbench_list_width.get())
    list_pane.grid(row=0, column=0, sticky='nsew', padx=(6, 4), pady=0)
    list_pane.grid_propagate(False)
    list_head = _frame(list_pane, PANEL_RAISED)
    list_head.pack(fill='x')
    _label(list_head, 'Şablon Listesi', 11, FG, True, PANEL_RAISED).pack(side='left', padx=10, pady=10)
    list_count_chip = _status_chip(list_head, '–', BLUE)
    list_filters = _frame(list_pane, PANEL)
    list_filters.pack(fill='x', padx=7, pady=(5, 0))
    category = ttk.Combobox(list_filters, textvariable=app.workbench_category,
                            values=('06 · Petek Kapama', '01 · Wifi Kutusu', '02 · Cam Tablo Dikey',
                                    '02 · Cam Tablo Yatay', '03 · Ahşap Tablo', '04 · Cam Doğrama',
                                    '05 · Ocak Arkası'),
                            state='readonly', width=18)
    category.pack(fill='x', pady=(0, 4))
    state = ttk.Combobox(list_filters, textvariable=app.workbench_filter,
                         values=('Tümü', 'Onaylı', 'Taslak', 'Yeni'),
                         state='readonly', width=18)
    state.pack(fill='x')
    # Arama kutusu: workbench_search zaten refresh_template_list'e bağlıydı
    # ancak arayüzde hiç Entry yoktu; canlı filtre artık çalışır.
    search = tk.Entry(list_filters, textvariable=app.workbench_search, bg=PANEL, fg=FG,
                      insertbackground=FG, relief='flat', bd=0, highlightthickness=1,
                      highlightbackground=BORDER, highlightcolor=ACCENT, font=('Segoe UI', 9))
    search.pack(fill='x', pady=(4, 4))
    search.bind('<Escape>', lambda _event: app.workbench_search.set(''))
    listbox = tk.Listbox(list_pane, bg=PANEL, fg=FG, selectbackground=ACCENT_DARK,
                         selectforeground='#ffffff', activestyle='none', relief='flat',
                         borderwidth=0, font=('Segoe UI', 9), highlightthickness=0)
    listbox.pack(fill='both', expand=True, padx=6, pady=6)
    if _table_tools is not None:
        _table_tools.attach_listbox_tooltip(listbox)
        _table_tools.add_listbox_xscroll(listbox)
    def category_folder():
        category = app.workbench_category.get().split('·', 1)[-1].strip()
        aliases = {
            'Wifi Kutusu': '01_Wifi_Kutusu', 'Cam Tablo Dikey': '02_Cam_Tablo_Dikey',
            'Cam Tablo Yatay': '02_Cam_Tablo_Yatay', 'Ahşap Tablo': '03_Ahsap_Tablo',
            'Cam Doğrama': '04_Cam_Dograma', 'Ocak Arkası': '05_Ocak_Arkasi',
            'Petek Kapama': '06_Petek_Kapama',
        }
        return aliases.get(category, category.replace(' ', '_'))

    def _discovery_signature(category):
        """Cheap content fingerprint of the central template registry.

        The registry file (and its WAL sidecar during uncheckpointed writes)
        change on every approval, so mtime+size are enough to detect stale data
        without reopening SQLite or parsing a single JSON row.
        """
        db_path = Path(app.runtime) / 'SABLON_V2_MIMARI' / 'ayarlar.db'
        try:
            main = db_path.stat()
        except OSError:
            return (category, None, None, None, None)
        try:
            wal = Path(str(db_path) + '-wal').stat()
            wal_stat = (wal.st_mtime_ns, wal.st_size)
        except OSError:
            wal_stat = (0, 0)
        return (category, main.st_mtime_ns, main.st_size, wal_stat[0], wal_stat[1])

    _discovery_cache = {}

    def discover_templates():
        """Read canonical names/status from the central SQLite registry.

        Search/filter taps re-invoke this on every character.  The registry
        only changes through the editor, so the full scan is served from memory
        until the database file itself changes.
        """
        signature = _discovery_signature(category_folder())
        cached = _discovery_cache.get(signature[0])
        if cached and cached[0] == signature:
            return list(cached[1])
        rows = _discover_templates_impl()
        _discovery_cache[signature[0]] = (signature, list(rows))
        return rows

    def _discover_templates_impl():
        """Full registry scan (only reached when the file signature changed)."""
        import sqlite3, json
        category = category_folder()
        db_path = Path(app.runtime) / 'SABLON_V2_MIMARI' / 'ayarlar.db'
        rows = []
        try:
            # Salt okuma: plain connect() eksik dosyayı oluştururdu.
            with sqlite3.connect(db_path.resolve().as_uri() + '?mode=ro', uri=True) as db:
                db.row_factory = sqlite3.Row
                templates = db.execute('SELECT filename,data FROM templates WHERE category_id=?', (category,)).fetchall()
                # N+1 yerine 2 sorgu: tüm aktif profilleri toplu IN ile çek,
                # Python'da uid başına en yeni (rowid DESC) profili seç.
                uid_of = {row['filename']: f'{category}_{row["filename"]}' for row in templates}
                uids = list(uid_of.values())
                profile_map = {}
                for offset in range(0, len(uids), 400):
                    chunk = uids[offset:offset + 400]
                    marks = ','.join('?' * len(chunk))
                    for prof in db.execute(
                            'SELECT template_uid,review_status,surface_quad FROM template_profiles '
                            f'WHERE is_active=1 AND template_uid IN ({marks}) ORDER BY rowid DESC',
                            chunk):
                        profile_map.setdefault(prof['template_uid'], prof)
                for row in templates:
                    data = json.loads(row['data'] or '{}')
                    profile = profile_map.get(uid_of[row['filename']])
                    status = str(profile['review_status'] if profile else data.get('review_status') or 'NEW').upper()
                    quad = profile['surface_quad'] if profile else data.get('koseler')
                    has_quad = bool(quad) and (isinstance(quad, str) and quad not in ('null','[]') or isinstance(quad, list) and len(quad) == 4)
                    label = 'Onaylı' if status == 'APPROVED' else ('Taslak' if has_quad else 'Yeni')
                    path = Path(app.runtime) / '2_SABLON_HAVUZU' / category / row['filename']
                    rows.append((row['filename'], label, path))
        except Exception:
            return []
        return sorted(rows, key=lambda item: item[0].casefold())

    preview_canvas = [None]
    # Görsel önbellekleri: seçim/filtre değişimlerinde diske ve yeniden koda
    # inilmez. Taban görsel yol+mtime ile, PhotoImage (yol, mtime) ile
    # saklanır; sınırlı sayıda girdi tutulur.
    _base_cache = {}
    _photo_cache = {}
    # Filtrelenmiş/aranmış görünür listenin dosya yolları; önizleme her zaman
    # listede görünen satırla aynı yolu gösterir.
    _visible_paths = [[]]

    def load_selected_preview(path=None):
        canvas = preview_canvas[0]
        if canvas is None:
            return
        if path is None:
            paths = _visible_paths[0]
            selection = listbox.curselection()
            index = selection[0] if selection else 0
            path = paths[index] if index < len(paths) else None
        path_obj = Path(path) if path is not None else None
        if path_obj is None or not path_obj.is_file():
            app.workbench_image_path = None
            app.workbench_preview_hint.set('Gerçek şablon bulunamadı · Gerçek İş Akışını Aç ile çalışma merkezini başlatın.')
            app.workbench_preview_tag.set('ÖNİZLEME YOK')
            canvas.delete('all')
            canvas.create_text(360, 280, text='GERÇEK ŞABLON ÖNİZLEMESİ YOK', fill='#F0B84C', font=('Segoe UI', 16, 'bold'))
            return
        try:
            mtime = path_obj.stat().st_mtime_ns
            cache_key = str(path_obj)
            base = _base_cache.get(cache_key)
            if base is None or base[0] != mtime:
                image = Image.open(path_obj)
                image = ImageOps.exif_transpose(image).convert('RGB')
                image.thumbnail((760, 540), Image.Resampling.LANCZOS)
                if len(_base_cache) > 24:
                    _base_cache.clear()
                _base_cache[cache_key] = (mtime, image)
            else:
                image = base[1]
            photo_key = (cache_key, mtime)
            final = _photo_cache.get(photo_key)
            if final is None:
                final = ImageTk.PhotoImage(image)
                if len(_photo_cache) > 30:
                    _photo_cache.clear()
                _photo_cache[photo_key] = final
            app.workbench_image_path = cache_key
            app.workbench_photo = final
            canvas.delete('all')
            canvas.create_image(380, 285, image=final, anchor='center')
            canvas.create_text(12, 12, text='GERÇEK ŞABLON · ' + path_obj.name[:70], fill='#B9F3DC', anchor='nw', font=('Segoe UI', 9, 'bold'))
            app.workbench_preview_hint.set('Gerçek şablon önizlemesi · ' + path_obj.name)
            app.workbench_preview_tag.set('GERÇEK ŞABLON · ' + path_obj.name[:58])
        except Exception as exc:
            canvas.delete('all')
            canvas.create_text(360, 280, text='ŞABLON ÖNİZLEMESİ OKUNAMADI', fill='#EF6A73', font=('Segoe UI', 15, 'bold'))
            app.workbench_preview_hint.set('Önizleme hatası: ' + str(exc))
            app.workbench_preview_tag.set('ÖNİZLEME HATASI')

    def refresh_template_list(*_args):
        discovered = discover_templates()
        home_detail = getattr(app, 'home_template_detail', None)
        if home_detail is not None:
            try:
                home_detail.configure(text=f'{len(discovered)} geçerli kayıt · kategoriye göre filtrelenebilir')
            except tk.TclError:
                pass
        query = app.workbench_search.get().casefold().strip()
        selected = app.workbench_filter.get()
        # Seçili satırı silmeden ÖNCE yakala; filtre/ara/kategori değişince
        # seçimi bozmasın.
        keep_display = None
        try:
            cur = listbox.curselection()
            if cur:
                keep_display = listbox.get(cur[0])
        except tk.TclError:
            keep_display = None
        listbox.delete(0, 'end')
        rows = list(discovered)
        if not rows:
            rows = [('Bu kategoride kayıtlı şablon bulunamadı', '—', None)]
            if selected != 'Tümü':
                selected = 'Tümü'
        visible = []
        for name, status, path in rows:
            if selected != 'Tümü' and status != selected:
                continue
            if query and query not in (name + ' ' + status).casefold():
                continue
            visible.append((name, status, path))
        _visible_paths[0] = [item[2] for item in visible]
        inserted = []
        for name, status, _path in visible:
            display = '  ' + name + '   · ' + status
            listbox.insert('end', display)
            inserted.append(display)
        if listbox.size():
            if keep_display is not None and keep_display in inserted:
                listbox.selection_set(inserted.index(keep_display))
            else:
                listbox.selection_set(0)
        filtering = bool(query) or selected != 'Tümü'
        list_count_chip.configure(text=(f'{len(visible)}/{len(discovered)}' if filtering
                                        else str(len(discovered))))
        load_selected_preview(None)
    app.refresh_workbench_templates = refresh_template_list
    app._refresh_visual_cards = refresh_template_list
    app.workbench_search.trace_add('write', refresh_template_list)
    app.workbench_filter.trace_add('write', refresh_template_list)
    app.workbench_category.trace_add('write', lambda *_: (
        app.status.set('Kategori seçildi: ' + app.workbench_category.get()),
        refresh_template_list()
    ))
    refresh_template_list()
    # Liste artık yalnızca kategori/filtre/arama değiştiğinde yenilenir; her 1.5 s'de
    # agresif yenileme kaldırıldı. Seçim, liste güncellemesinde korunuyor.
    listbox.bind('<<ListboxSelect>>', lambda _event: load_selected_preview())
    def move_selection(delta):
        if not listbox.size(): return
        index = listbox.curselection()[0] if listbox.curselection() else 0
        index = max(0, min(listbox.size() - 1, index + delta))
        listbox.selection_clear(0, 'end'); listbox.selection_set(index); listbox.see(index)
        app.status.set('Şablon seçildi: ' + listbox.get(index).strip())
    _button(list_pane, '◀  Önceki', lambda: move_selection(-1), color=PANEL_RAISED, size=8).pack(side='left', padx=7, pady=7)
    _button(list_pane, 'Sonraki  ▶', lambda: move_selection(1), color=PANEL_RAISED, size=8).pack(side='right', padx=7, pady=7)

    sash_left = _make_sash(body)
    sash_left.grid(row=0, column=1, sticky='nsew')
    sash_right = _make_sash(body)
    sash_right.grid(row=0, column=3, sticky='nsew')

    def _sash_press(event):
        sash = event.widget
        sash._drag_start_x = event.x_root
        sash._drag_start_list = app.workbench_list_width.get()
        sash._drag_start_inspector = app.workbench_inspector_width.get()
        sash.grab_set()
    def _sash_drag(event):
        sash = event.widget
        dx = event.x_root - sash._drag_start_x
        if sash is sash_left:
            new_w = max(150, min(460, sash._drag_start_list + dx))
            app.workbench_list_width.set(new_w)
            list_pane.configure(width=new_w)
            body.grid_columnconfigure(0, minsize=new_w)
        else:
            new_w = max(250, min(540, sash._drag_start_inspector - dx))
            app.workbench_inspector_width.set(new_w)
            inspector.configure(width=new_w)
            body.grid_columnconfigure(4, minsize=new_w)
    def _sash_release(event):
        event.widget.grab_release()
    for _sash in (sash_left, sash_right):
        _sash.bind('<ButtonPress-1>', _sash_press)
        _sash.bind('<B1-Motion>', _sash_drag)
        _sash.bind('<ButtonRelease-1>', _sash_release)

    stage_wrap = _frame(body, SURFACE)
    stage_wrap.grid(row=0, column=2, sticky='nsew', padx=4, pady=0)
    # The production host must consume all width left by the fixed nav.  A
    # zero-weight single grid column otherwise leaves the embedded V4 form at
    # its small requested width and creates a large dead canvas beside it.
    stage_wrap.grid_columnconfigure(0, weight=1)
    stage_wrap.grid_rowconfigure(2, weight=1)
    tab_bar = _frame(stage_wrap, PANEL_RAISED)
    tab_bar.grid(row=0, column=0, sticky='ew', pady=(0, 5))
    for mode, (title, _context) in tab_meta.items():
        if mode == 'tools':
            # Sidebar owns screen switching for Araçlar; a tenth tab-bar
            # button would clip at the minimum window width.
            continue
        button = _button(tab_bar, title, lambda m=mode: switch_tab(m),
                         color='#10332B' if mode == 'review' else PANEL_RAISED, size=8)
        button.pack(side='left', padx=2, pady=3)
        tab_bar_buttons[mode] = button
    app.workbench_tab_bar_buttons = tab_bar_buttons
    toolbar = _frame(stage_wrap, PANEL)
    toolbar.grid(row=1, column=0, sticky='ew', pady=(0, 6))
    _button(toolbar, '▶ Gerçek İş Akışını Aç', app.open_current_workflow,
            color=ACCENT_DARK, size=8).pack(side='left', padx=3, pady=5)
    app.workbench_preview_hint = tk.StringVar(value='Nihai çıktı önizlemesi · gerçek dosya için Gerçek İş Akışını Aç')
    def set_preview(mode, label):
        app.workbench_preview_mode.set(mode)
        app.workbench_preview_hint.set(label)
        app.status.set(label)
        # Ham/çalışma/nihai arasında gerçek yeniden çizim; daha önce yalnız
        # etiket değişiyor, görsel güncellenmiyordu.
        load_selected_preview(None)

    def reset_preview():
        app.workbench_filter.set('Tümü')
        app.workbench_search.set('')
        app.workbench_preview_mode.set('final')
        hint = 'Nihai çıktı görünümüne dönüldü; liste ve arama sıfırlandı.'
        app.workbench_preview_hint.set(hint)
        app.status.set(hint)
        load_selected_preview(None)

    def open_editor_undo():
        app.open_legacy_review()
        app.status.set('Geri alma (Ctrl+Z) gerçek editörde çalışır; Şablon İnceleme açıldı.')

    for label, cb in (('◉ Ham Orijinali Göster', lambda: set_preview('original', 'Ham orijinal görünümü seçildi.')),
                      ('◌ Çalışma Görseline Dön', lambda: set_preview('working', 'Çalışma görseli görünümü seçildi.')),
                      ('✧ Beyazlat', app.open_consolidation), ('⟳ 4 Köşe Otomatik', app.open_legacy_review),
                      ('↶ Sıfırla', reset_preview),
                      ('↩ Geri Al (Ctrl+Z)', open_editor_undo)):
        _button(toolbar, label, cb, color=PANEL_RAISED, size=8).pack(side='left', padx=3, pady=5)
    stage = _frame(stage_wrap, '#080C14')
    stage.pack_propagate(False)
    stage.grid(row=2, column=0, sticky='nsew')
    stage.grid_rowconfigure(0, weight=1); stage.grid_columnconfigure(0, weight=1)
    canvas = tk.Canvas(stage, bg='#080C14', highlightthickness=0)
    preview_canvas[0] = canvas
    canvas.grid(row=0, column=0, sticky='nsew')
    app._wheel_canvas = canvas
    canvas.create_text(360, 280, text='GERÇEK ŞABLON YÜKLENİYOR…', fill='#93A6C4', font=('Segoe UI', 15, 'bold'))
    preview_hint_label = _label(stage, '', 9, '#93A6C4', False, '#080C14', textvariable=app.workbench_preview_hint)
    preview_hint_label.place(relx=.5, rely=.06, anchor='center')
    app.workbench_preview_tag = tk.StringVar(value='GERÇEK ŞABLON ÖNİZLEMESİ')
    preview_tag_label = _label(stage, '', 9, '#0F1622', True, '#B9F3DC',
                               textvariable=app.workbench_preview_tag)
    preview_tag_label.place(relx=.5, rely=.91, anchor='center')
    # The real V4 production window is mounted beside (not inside) the
    # preview canvas.  Keeping this host separate lets tab switches preserve
    # selected templates/designs/store and an active queue without rebuilding
    # or duplicating the production UI.
    production_host = _frame(stage, '#0B101B')
    production_host.grid_remove()
    app.workbench_production_host = production_host
    review_host = _frame(stage, '#04140E')
    review_host.grid_remove()
    app.workbench_review_host = review_host
    upload_host = _frame(stage, SURFACE)
    upload_host.grid_remove()
    app.workbench_upload_host = upload_host
    # The home surface is a real operational dashboard, not a duplicate
    # template preview.  It gives first-time operators an obvious starting
    # point and keeps the daily flow visible without touching production data.
    home_host = _frame(stage, '#080C14')
    home_host.grid_remove()
    app.workbench_home_host = home_host

    def _build_home_workspace():
        if getattr(app, '_home_workspace_ready', False):
            return
        app._home_workspace_ready = True
        header = _frame(home_host, '#0F1622')
        header.pack(fill='x', padx=18, pady=(18, 10))
        _label(header, 'Günlük Operasyon Merkezi', 18, FG, True, '#0F1622').pack(anchor='w')
        _label(header, 'Şablon → tasarım → mağaza → üretim → link / Excel', 10, MUTED, False, '#0F1622').pack(anchor='w', pady=(4, 0))

        cards = _frame(home_host, '#080C14')
        cards.pack(fill='x', padx=18, pady=(0, 10))
        for i in range(4):
            cards.grid_columnconfigure(i, weight=1, uniform='home-card')
        card_defs = (
            ('01', 'Şablon İnceleme', 'Şablon kataloğu yükleniyor…', 'review', ACCENT),
            ('02', 'Üretime Hazırla', 'Tasarım ve mağaza seçimini yap', 'production', BLUE),
            ('03', 'Yükleme Merkezi', 'Yeni mockup / tasarım alımı', 'uploads', PURPLE),
            ('04', 'Sonuç ve Rapor', 'Üretim kayıtları ve kanıtlar', 'reports', YELLOW),
        )
        for col, (num, title, detail, mode, color) in enumerate(card_defs):
            box = _frame(cards, PANEL)
            box.grid(row=0, column=col, sticky='nsew', padx=(0 if col == 0 else 5, 5 if col < 3 else 0))
            _label(box, num, 9, color, True, PANEL).pack(anchor='w', padx=12, pady=(12, 3))
            _label(box, title, 11, FG, True, PANEL).pack(anchor='w', padx=12)
            detail_label = _label(box, detail, 9, MUTED, False, PANEL, wraplength=180)
            detail_label.pack(anchor='w', padx=12, pady=(4, 10))
            if mode == 'review':
                app.home_template_detail = detail_label
            _button(box, 'Aç', lambda m=mode: switch_tab(m), color=PANEL_RAISED, size=8).pack(anchor='w', padx=12, pady=(0, 12))

        flow = _frame(home_host, PANEL)
        flow.pack(fill='both', expand=True, padx=18, pady=(0, 18))
        _label(flow, 'Önerilen çalışma sırası', 12, FG, True, PANEL).pack(anchor='w', padx=14, pady=(14, 8))
        for idx, (title, detail, mode) in enumerate((
            ('Şablonları kontrol et', 'Onaylı, taslak ve hatalı kayıtları ayır.', 'review'),
            ('Üretim planını hazırla', 'Tasarım klasörü ve mağazaları seç.', 'production'),
            ('Üretimi çalıştır', 'Gerçek ilerleme, hata ve kalan süreyi izle.', 'production'),
            ('Sonuçları dışa aktar', 'Bulut linki ve mağaza Excel dosyalarını aç.', 'reports'),
        ), 1):
            row = _frame(flow, PANEL_RAISED)
            row.pack(fill='x', padx=14, pady=3)
            _label(row, f'{idx:02d}', 10, ACCENT, True, PANEL_RAISED).pack(side='left', padx=(10, 8), pady=9)
            _label(row, title, 10, FG, True, PANEL_RAISED).pack(side='left', pady=9)
            _label(row, detail, 9, MUTED, False, PANEL_RAISED).pack(side='left', padx=14, pady=9)
            _button(row, 'Aç', lambda m=mode: switch_tab(m), color=PANEL, size=8).pack(side='right', padx=8, pady=5)

    def _set_home_layout(active):
        try:
            if active:
                _build_home_workspace()
                list_pane.grid_remove(); sash_left.grid_remove()
                inspector.grid_remove(); sash_right.grid_remove()
                stage_wrap.grid_configure(row=0, column=0, columnspan=5, sticky='nsew', padx=0, pady=0)
                tab_bar.grid_remove(); toolbar.grid_remove(); canvas.grid_remove()
                production_host.grid_remove(); upload_host.grid_remove(); review_host.grid_remove()
                records_host.grid_remove(); reports_host.grid_remove(); designs_host.grid_remove(); stores_host.grid_remove()
                home_host.grid(row=0, column=0, sticky='nsew'); home_host.lift()
                body.grid_columnconfigure(0, weight=1, minsize=0)
                body.grid_columnconfigure(1, weight=0, minsize=0)
                body.grid_columnconfigure(4, weight=0, minsize=0)
            else:
                home_host.grid_remove()
        except (NameError, tk.TclError):
            return
    # 'Üretim Kayıtları' sekmesinin kalıcı ana panosu; ilk açılışta gerçek
    # kayıt deposuna bağlanır (salt okunur), böylece yeniden başlatmada
    # üretim durumu kayıtlardan yeniden yüklenir.
    records_host = _frame(stage, '#080C14')
    records_host.grid_remove()
    app.workbench_records_host = records_host

    def _ensure_records_workspace():
        if getattr(app, '_records_workspace', None) is not None:
            return app._records_workspace
        try:
            from URETIM_V4 import uretim_kayitlari_v1 as records_ws
            workspace = records_ws.build_records_workspace(app, records_host)
            app._records_workspace = workspace
            refresh = getattr(workspace, 'refresh_records', None)
            app.refresh_records_workspace = refresh if callable(refresh) else _records_noop
        except Exception as exc:
            app._records_workspace = None
            app.refresh_records_workspace = _records_noop
            _label(records_host, 'Üretim Kayıtları ekranı yüklenemedi', 14, RED, True,
                   '#080C14').pack(anchor='w', padx=24, pady=(24, 6))
            _label(records_host, str(exc), 9, MUTED, False, '#080C14',
                   wraplength=900, justify='left').pack(anchor='w', padx=24)
            try:
                app.status.set('Üretim Kayıtları yüklenemedi: ' + str(exc))
            except Exception:
                pass
        return app._records_workspace

    # 'Raporlar & Tarama' sekmesinin kalıcı ana panosu (Kanıt ve Kurtarma
    # Merkezi); salt okunur, Üretim Kayıtları'ndan bağımsız.
    reports_host = _frame(stage, '#080C14')
    reports_host.grid_remove()
    app.workbench_reports_host = reports_host

    # 'Tasarım Yönetimi' sekmesinin kalıcı ana panosu; mevcut HAM
    # tasarımları listeler ve seçtirir (salt okunur).
    designs_host = _frame(stage, '#080C14')
    designs_host.grid_remove()
    app.workbench_designs_host = designs_host

    def _ensure_designs_workspace():
        if getattr(app, '_designs_workspace', None) is not None:
            return app._designs_workspace
        try:
            import tasarim_yonetimi_v1 as designs_ws
            workspace = designs_ws.build_designs_workspace(app, designs_host)
            app._designs_workspace = workspace
            refresh = getattr(workspace, 'refresh_designs', None)
            app.refresh_designs_workspace = refresh if callable(refresh) else _records_noop
        except Exception as exc:
            app._designs_workspace = None
            app.refresh_designs_workspace = _records_noop
            _label(designs_host, 'Tasarım Yönetimi ekranı yüklenemedi', 14, RED, True,
                   '#080C14').pack(anchor='w', padx=24, pady=(24, 6))
            _label(designs_host, str(exc), 9, MUTED, False, '#080C14',
                   wraplength=900, justify='left').pack(anchor='w', padx=24)
            try:
                app.status.set('Tasarım Yönetimi yüklenemedi: ' + str(exc))
            except Exception:
                pass
        return app._designs_workspace

    # 'Mağaza Profilleri' sekmesinin kalıcı ana panosu; kayıtlı ayarları ve
    # atanmış şablon havuzunu gösterir. Havuz yalnız burada okunur; atama
    # değişiklikleri Eşleştirme Merkezi'ne bırakılır.
    stores_host = _frame(stage, '#080C14')
    stores_host.grid_remove()
    app.workbench_stores_host = stores_host

    def _ensure_stores_workspace():
        if getattr(app, '_stores_workspace', None) is not None:
            return app._stores_workspace
        try:
            import magaza_profilleri_v1 as stores_ws
            workspace = stores_ws.build_stores_workspace(app, stores_host)
            app._stores_workspace = workspace
            refresh = getattr(workspace, 'refresh_stores', None)
            app.refresh_stores_workspace = refresh if callable(refresh) else _records_noop
        except Exception as exc:
            app._stores_workspace = None
            app.refresh_stores_workspace = _records_noop
            _label(stores_host, 'Mağaza Profilleri ekranı yüklenemedi', 14, RED, True,
                   '#080C14').pack(anchor='w', padx=24, pady=(24, 6))
            _label(stores_host, str(exc), 9, MUTED, False, '#080C14',
                   wraplength=900, justify='left').pack(anchor='w', padx=24)
            try:
                app.status.set('Mağaza Profilleri yüklenemedi: ' + str(exc))
            except Exception:
                pass
        return app._stores_workspace

    def _ensure_reports_workspace():
        if getattr(app, '_reports_workspace', None) is not None:
            return app._reports_workspace
        try:
            from URETIM_V4 import raporlar_tarama_v1 as reports_ws
            workspace = reports_ws.build_reports_workspace(app, reports_host)
            app._reports_workspace = workspace
            refresh = getattr(workspace, 'refresh_reports', None)
            app.refresh_reports_workspace = refresh if callable(refresh) else _records_noop
        except Exception as exc:
            app._reports_workspace = None
            app.refresh_reports_workspace = _records_noop
            _label(reports_host, 'Raporlar & Tarama ekranı yüklenemedi', 14, RED, True,
                   '#080C14').pack(anchor='w', padx=24, pady=(24, 6))
            _label(reports_host, str(exc), 9, MUTED, False, '#080C14',
                   wraplength=900).pack(anchor='w', padx=24)
            try:
                app.status.set('Raporlar & Tarama yüklenemedi: ' + str(exc))
            except Exception:
                pass
        return app._reports_workspace

    inspector = _frame(body, PANEL, width=app.workbench_inspector_width.get())
    inspector.grid(row=0, column=4, sticky='nsew', padx=(4, 6), pady=0)
    inspector.grid_propagate(False)
    # Keep the inspector at full height, but let its own content scroll when
    # the window is short or an optional tools section is expanded.  A plain
    # Tk Frame clips overflow; the canvas/window pair avoids nested fixed
    # heights while preserving every existing widget callback.
    inspector_canvas = tk.Canvas(inspector, bg=PANEL, highlightthickness=0,
                                 borderwidth=0)
    inspector_scroll = ttk.Scrollbar(inspector, orient='vertical',
                                     command=inspector_canvas.yview)
    inspector_canvas.configure(yscrollcommand=inspector_scroll.set)
    inspector_canvas.pack(side='left', fill='both', expand=True)
    inspector_scroll.pack(side='right', fill='y')
    inspector_content = _frame(inspector_canvas, PANEL)
    inspector_window = inspector_canvas.create_window((0, 0), window=inspector_content,
                                                       anchor='nw')

    # <Configure> fires once per resize pixel; geometry recomputation is deferred
    # to idle time and coalesced into one pass per burst (final state identical).
    _inspector_resize_pending = [False]

    def _apply_inspector_resize():
        _inspector_resize_pending[0] = False
        try:
            width = max(1, inspector_canvas.winfo_width())
            inspector_canvas.itemconfigure(inspector_window, width=width)
            inspector_canvas.configure(scrollregion=inspector_canvas.bbox('all'))
        except tk.TclError:
            pass

    def _resize_inspector_content(event=None):
        if _inspector_resize_pending[0]:
            return
        _inspector_resize_pending[0] = True
        inspector_canvas.after_idle(_apply_inspector_resize)

    inspector_content.bind('<Configure>', _resize_inspector_content)
    inspector_canvas.bind('<Configure>', _resize_inspector_content)

    def _scroll_inspector(event):
        pointer_x = root.winfo_pointerx()
        pointer_y = root.winfo_pointery()
        left = inspector.winfo_rootx()
        top = inspector.winfo_rooty()
        if not (left <= pointer_x < left + inspector.winfo_width() and
                top <= pointer_y < top + inspector.winfo_height()):
            return
        inspector_canvas.yview_scroll(-1 * int(event.delta / 120 or (-1 if event.delta < 0 else 1)), 'units')
        return 'break'

    inspector_canvas.bind_all('<MouseWheel>', _scroll_inspector, add='+')

    tabs = _frame(inspector_content, PANEL_RAISED)
    tabs.pack(fill='x')

    # gerçek motor için Gerçek İş Akışını Açın — inspector düğmeleri bu yüzeye yönlendirir
    def _open_surface(mode, message):
        """Inspector düğmelerini çalışan editöre bağla; ölü düğme bırakma."""
        try:
            switch = getattr(app, 'switch_workbench_tab', None)
            if callable(switch):
                switch(mode)
            else:
                app.open_legacy_review()
            app.status.set(message)
        except Exception as exc:
            app.status.set('Editör açılamadı: ' + str(exc))

    _button(tabs, '4 Köşe Editörü', lambda: _open_surface('review', '4 köşe inceleme ekranı açıldı.'), color=ACCENT_DARK, size=9).pack(side='left', fill='x', expand=True, padx=4, pady=5)
    _button(tabs, 'PETEK Maske', lambda: _open_surface('petek', 'PETEK maskesi editörü açıldı (gerçek motor).'),
            color=PANEL_RAISED, size=9).pack(side='left', fill='x', expand=True, padx=4, pady=5)
    corners = _section(inspector_content, '4 Köşe Düzenleme', BLUE)
    _button(corners, '◉ Köşe Algıla (Otomatik)',
            lambda: _open_surface('review', 'Otomatik 4 köşe editörde çalışır; Şablon İnceleme açıldı.'),
            color=PANEL_RAISED, size=9).pack(fill='x', pady=3)
    _button(corners, '▱ Toplu Oto 4 Köşe',
            lambda: _open_surface('review', 'Toplu oto 4 köşe editörde çalışır; Şablon İnceleme açıldı.'),
            color=PANEL_RAISED, size=9).pack(fill='x', pady=3)
    _label(corners, '● Düz çizgi algılandı: 0 sorun', 9, '#8FC2FF', False, PANEL_RAISED).pack(fill='x', pady=(7, 0))
    petek = _section(inspector_content, 'PETEK Ayarları', GREEN)
    for text in ('Delikler / Izgaralar (15)', 'İç Gölge (Derinlik)', 'Işık Geçişi (Sah Havalandırma)', 'Alt Kavis (İçbükey)'):
        row = _frame(petek, PANEL)
        row.pack(fill='x', pady=3)
        variable = app.workbench_petek_mask if text.startswith('Delikler') else tk.BooleanVar(value=True)
        tk.Checkbutton(row, text=text, variable=variable,
                       command=lambda t=text, v=variable: _open_surface(
                           'petek', f'PETEK maskesi editörü açıldı · {t} {"etkin" if v.get() else "kapalı"} (gerçek motor).'),
                       bg=PANEL, fg=FG,
                       activebackground=PANEL, activeforeground=FG, selectcolor=ACCENT_DARK,
                       font=('Segoe UI', 8)).pack(side='left')
    effects = _section(inspector_content, 'Efekt ve Görünüm', PURPLE)
    _effect_target = {'Gerçek Tasarımı Önizle': 'review', 'Işık / Yansıma Efekti': 'petek', 'Doğal Gölge': 'petek'}

    def _effect_toggled(name, key):
        dest = _effect_target[name]
        where = 'PETEK editöründe' if dest == 'petek' else 'Şablon İnceleme ekranında'
        state = 'etkin' if app.workbench_effects[key].get() else 'kapalı'
        _open_surface(dest, f'{name} {state} · gerçek efekt {where} işlenir.')

    for text in ('Gerçek Tasarımı Önizle', 'Işık / Yansıma Efekti', 'Doğal Gölge'):
        key = {'Gerçek Tasarımı Önizle':'design','Işık / Yansıma Efekti':'reflection','Doğal Gölge':'shadow'}[text]
        tk.Checkbutton(effects, text=text, variable=app.workbench_effects[key],
                       command=lambda t=text, k=key: _effect_toggled(t, k),
                       bg=PANEL, fg=FG,
                       activebackground=PANEL, activeforeground=FG, selectcolor=PURPLE,
                       font=('Segoe UI', 8)).pack(anchor='w', pady=2)
    _label(effects, 'Kenar yumuşatma', 8, MUTED, False, PANEL).pack(anchor='w', pady=(6, 0))

    def _edge_changed(value):
        # Bu kaydırıcıya bağlı istemci tarafı motor parametresi yoktur; önizleme
        # gerçek şablonu olduğu gibi gösterir, sessizce değiştirmez.
        app.status.set(f'Kenar yumuşatma: %{float(value):.0f} · önizlemeyi etkilemez; üretim motorunda kenarlık yumuşatma ayrı parametre ile uygulanır (çift tık = 30).')

    edge_scale = ttk.Scale(effects, from_=0, to=100, variable=app.workbench_edge_softness,
                           command=_edge_changed)
    edge_scale.pack(fill='x', pady=(0, 5))
    edge_scale.bind('<Double-Button-1>', lambda _event: app.workbench_edge_softness.set(30.0))

    # Compact actions are attached to the center work area. The former
    # four-card visual-flow footer consumed vertical room without adding
    # editing capability, so it is intentionally not mounted.
    # The embedded review WebView owns the action dock. Avoid mounting a
    # second Tk rail, which duplicated the same four actions below the editor.
    action_rail = None

    # Kept as a compatibility sentinel for tab-layout callbacks.
    bottom = None

    # Compatibility status fields used by existing Center methods.
    app.runtime_text = tk.StringVar(value=str(app.runtime))
    app.ham_home_status = tk.StringVar(value='HAM izleme: başlangıç kontrolü')
    app.status = tk.StringVar(value='Hazır · çalışma alanı ve onaylı veriler korunuyor.')
    status = _frame(shell, '#0B101B', height=25)
    status.grid(row=1, column=0, columnspan=2, sticky='ew')
    _label(status, '', 8, '#93A6C4', False, '#0B101B', textvariable=app.status).pack(side='left', padx=12, pady=5)
    # Central operation monitor.  The production engine still owns the real
    # progress variables; the shell mirrors them here so the operator can
    # switch to records, reports, or uploads without losing the active job's
    # phase and percentage.
    app.operation_text = tk.StringVar(value='İşlem: hazır')
    # The production window receives the Tk root as its parent; expose the
    # shared variable on that root as a narrow, non-invasive bridge.
    try:
        root.operation_text = app.operation_text
    except Exception:
        pass
    operation_chip = tk.Label(
        status, textvariable=app.operation_text, bg='#10251F', fg='#8DEBD5',
        font=('Segoe UI', 8, 'bold'), padx=8, pady=3, anchor='w')
    operation_chip.pack(side='right', padx=(6, 8), pady=2)
    _label(status, 'Çalışma klasörü: ', 8, MUTED, False, '#0B101B').pack(side='right', padx=(0, 2))
    _label(status, '', 8, '#93A6C4', False, '#0B101B', textvariable=app.runtime_text).pack(side='right', padx=(0, 12))

    def refresh_operation_monitor():
        try:
            window = getattr(app, '_production_window', None)
            if window is None:
                windows = getattr(app, 'batch_windows', ())
                window = next((item for item in reversed(tuple(windows))
                               if getattr(item, 'window', None) is not None), None)
            if window is not None and getattr(window, 'window', None) is not None:
                try:
                    if not window.window.winfo_exists():
                        window = None
                except tk.TclError:
                    window = None
            if window is None:
                uploader = getattr(app, '_upload_center', None)
                if uploader is not None and getattr(uploader, 'running', False):
                    total = int(getattr(uploader, '_upload_total', 0) or 0)
                    done = int(getattr(uploader, '_upload_success', 0) or 0) + int(getattr(uploader, '_upload_failed', 0) or 0) + int(getattr(uploader, '_upload_skipped', 0) or 0)
                    percent = (done / total * 100) if total else 0
                    app.operation_text.set(f'Yükleme {percent:.0f}% · {done}/{total}')
                else:
                    app.operation_text.set('İşlem: hazır')
            else:
                title_var = getattr(window, 'live_progress_title', None)
                percent_var = getattr(window, 'live_progress_percent', None)
                counts_var = getattr(window, 'live_progress_counts', None)
                cloud_title = getattr(window, 'cloud_progress_title', None)
                cloud_percent = getattr(window, 'cloud_progress_percent', None)
                title = title_var.get() if title_var is not None else ''
                percent = percent_var.get() if percent_var is not None else ''
                counts = counts_var.get() if counts_var is not None else ''
                cloud = cloud_title.get() if cloud_title is not None else ''
                cloud_pct = cloud_percent.get() if cloud_percent is not None else ''
                if title and title not in {'Üretim hazır', 'Hazır'}:
                    suffix = f' · {counts}' if counts else ''
                    app.operation_text.set(f'{title} {percent}{suffix}'.strip())
                elif cloud and cloud not in {'Excel / linkleme hazır', 'Hazır'}:
                    app.operation_text.set(f'{cloud} {cloud_pct}'.strip())
                else:
                    app.operation_text.set('İşlem: hazır')
        except (tk.TclError, AttributeError, RuntimeError):
            return
        try:
            root.after(500, refresh_operation_monitor)
        except tk.TclError:
            pass

    app.refresh_operation_monitor = refresh_operation_monitor
    root.after(500, refresh_operation_monitor)

    # Existing maintenance controls stay available but collapsed.
    app.advanced_toggle = ttk.Button(inspector_content, text='▶ Diğer Araçlar ve Kurtarma', command=app.toggle_advanced)
    app.advanced_toggle.pack(fill='x', padx=8, pady=(0, 5))
    app.advanced_panel = ttk.Frame(inspector_content, padding=8)
    for i, (title, handler) in enumerate((
        ('G3 Bütünlük Denetimi', app.g3_audit), ('SQLite Güvenli Yedek', app.g3_backup),
        ('PETEK Klasör Denetimi', app.prepare_petek_folders),
        ('Sistem Durumu', app.show_health), ('Kesinti Kurtarma', app.open_crash_recovery),
    )):
        ttk.Button(app.advanced_panel, text=title, command=handler).grid(row=i // 2, column=i % 2, sticky='ew', padx=3, pady=3)
    app.advanced_panel.columnconfigure(0, weight=1); app.advanced_panel.columnconfigure(1, weight=1)

    # Error Radar strip appears only after a real error.
    radar = _frame(body, '#2E161A')
    radar.grid_forget()
    app.error_radar = radar
    app.error_radar_text = tk.StringVar(value='')
    _label(radar, '', 8, '#FFD9DC', False, '#2E161A', textvariable=app.error_radar_text).pack(side='left', padx=10, pady=6)
    for title, fn in (('Raporu Aç', open_report), ('Raporu Kopyala', copy_report_text), ('Codex Paketi', prepare_codex_bundle)):
        _button(radar, title, fn, color='#2E161A', size=8).pack(side='right', padx=3, pady=3)
    def on_error(report):
        def show():
            try:
                pixels = report.get('pixel_errors') or {}
                mask = report.get('mask_comparison') or {}
                stage = report.get('processing_stage') or report.get('stage') or 'bilinmiyor'
                app.error_radar_text.set(
                    '⚠ ' + str(report.get('error_code')) + ' · ' + str(report.get('title')) +
                    ' · Aşama: ' + str(stage) +
                    ' · Hatalı piksel: ' + str(pixels.get('mismatched_pixels', 0)) +
                    ' · Maske farkı: ' + str(mask.get('mismatched_pixels', 0))
                )
                app.error_radar.grid(row=1, column=1, sticky='ew')
            except tk.TclError:
                pass
        try: root.after_idle(show)
        except tk.TclError: pass
    register_listener(on_error)

    # Lightweight operation log remains available for diagnostics.
    app.log = scrolledtext.ScrolledText(root, height=1, state='disabled', bg='#080C14', fg=FG,
                                        insertbackground=FG, relief='flat', borderwidth=0)
    app.log.place(x=-10000, y=-10000)

    # Let Tk finish mapping the shell before launching the external review
    # service.  This makes Şablon İnceleme the actual first screen while
    # retaining the existing preflight, backup and authenticated-server gates.
    # Önce seçili satırın gerçek önizlemesini çiz; placeholder'da takılı kalmasın.
    load_selected_preview(None)
    root.after_idle(lambda: switch_tab('review'))
