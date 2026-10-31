"""Presentation-only V4.9 desktop dashboard.

No runtime migration, automatic approval, mask edit or production changes.
Do not read/decorate user templates during dashboard construction.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from datetime import datetime
from dark_theme_v42 import BG, FG, MUTED
from ui_layout_v498 import load as load_visual_layout, save as save_visual_layout, LayoutEditor

SIDE = '#222831'
PANEL = '#343c46'
PANEL_ALT = '#3d4652'
OUTLINE = '#58616d'
ACCENT = '#995df4'
MAGENTA = '#ec4ca0'
ORANGE = '#f8a552'
BLUE = '#4c9df9'
GREEN = '#43d1a7'


def _frame(parent, bg=BG, **kwargs):
    return tk.Frame(parent, bg=bg, highlightthickness=0, bd=0, **kwargs)


def _label(parent, text, size=11, color=FG, bold=False, bg=None, **kwargs):
    return tk.Label(parent, text=text, bg=bg or parent.cget('bg'), fg=color,
                    font=('Segoe UI', size, 'bold' if bold else 'normal'),
                    justify='left', anchor='w', **kwargs)


def _button(parent, text, command, *, fill=False, color=PANEL_ALT, fg=FG, size=11):
    b = tk.Button(parent, text=text, command=command, bg=color, fg=fg,
                  font=('Segoe UI', size, 'bold'), bd=0, relief='flat',
                  highlightthickness=0, cursor='hand2', activebackground=ACCENT,
                  activeforeground='#ffffff', padx=15, pady=11, anchor='w')
    if fill:
        b.pack(fill='x', pady=4)
    return b


def _card(parent, title, description, action, callback, color, row, column,
          *, card_key=None, drag_mode=None, on_drop=None, palette=None):
    # Card identity is UI-only; business callbacks are never re-bound to a new ID.
    palette=palette or {}
    panel=palette.get('panel',PANEL)
    outer = _frame(parent, panel)
    outer._card_uid=card_key
    outer.grid(row=row, column=column, sticky='nsew', padx=7, pady=7)
    side = _frame(outer, color, width=5)
    side.pack(side='left', fill='y')
    body = _frame(outer, panel)
    body.pack(side='left', fill='both', expand=True, padx=19, pady=16)
    if drag_mode is not None and drag_mode.get():
        handle=_label(body, '⠿  TUT VE KARTA SÜRÜKLE · '+title, 11, bold=True,
                      color='#edd7ff',bg=panel,cursor='fleur')
        handle.pack(fill='x',pady=(0,7))
        if on_drop:handle.bind('<ButtonRelease-1>',lambda e:on_drop(card_key,e))
    _label(body, title, 15, color=palette.get('title',FG), bold=True,bg=panel).pack(fill='x', pady=(0, 7))
    description_label = _label(body, description, 11, MUTED, wraplength=280,bg=panel)
    description_label.pack(fill='x', pady=(0, 13))
    body.bind('<Configure>', lambda e: description_label.configure(wraplength=max(170, e.width-20)))
    def safe_action():
        if drag_mode is not None and drag_mode.get():return
        callback()
    b = _button(body, action+'  ›',safe_action, color=palette.get('button',PANEL_ALT),size=11)
    b.pack(anchor='w')
    return b


def build_dashboard(app):
    root = app.root
    root.geometry('1260x860')
    root.minsize(920, 650)
    root.configure(bg=BG)
    drag_mode=tk.BooleanVar(master=root,value=False)
    shell = _frame(root)
    shell.pack(fill='both', expand=True)
    sidebar = _frame(shell, SIDE, width=228)
    sidebar.pack(side='left', fill='y')
    sidebar.pack_propagate(False)
    brand = _frame(sidebar, SIDE)
    brand.pack(fill='x', padx=17, pady=(25, 27))
    _label(brand, '✦ Görsel Üretim', 17, bold=True, color='#e7d6ff', bg=SIDE).pack(fill='x')
    _label(brand, 'MERKEZİ  ·  7 KATEGORİ', 10, color='#c5d0dc', bg=SIDE).pack(fill='x', pady=(2,0))

    def nav(title, callback, active=False):
        b = _button(sidebar, title, callback, color='#4b3865' if active else SIDE, size=11)
        b.pack(fill='x', padx=11, pady=3)
        return b

    # Navigation uses the existing handlers: no duplicate business logic.
    nav('⌂   Ana Sayfa', lambda: app._wheel_canvas.yview_moveto(0), True)
    nav('▣   Şablonlar', app.open_legacy_review)
    nav('▤   Seri Üretim', app.open_unified_v4)
    nav('▧   Ham Tasarımlar', app.open_ham_design_folder)
    nav('⚒   Profesyonel Araçlar', app.open_legacy_tools)
    nav('▦   PETEK İşlemleri', app.open_legacy_review)
    nav('✓   Yapmam Gereken Testler', app.open_tests_v493)
    nav('▤   Notlarım ve Görevlerim', app.open_notes_v493)
    nav('⌕   Özellik / Araç Ara', app.open_tool_search_v493)
    nav('✥   Arayüzü Düzenle', lambda: LayoutEditor(root,'dashboard',on_save=app._refresh_visual_cards))
    nav('⏻   PROGRAMI KAPAT', app.close)
    def open_reports():
        if not app.advanced_panel.winfo_manager():
            app.toggle_advanced()
        canvas.yview_moveto(1)
    nav('▤   Raporlar ve Kurtarma', open_reports)
    _label(sidebar, 'VERİ GÜVENLİĞİ', 10, color=GREEN, bold=True, bg=SIDE).pack(
        side='bottom', anchor='w', padx=20, pady=(0,22))

    workspace = _frame(shell)
    workspace.pack(side='left', fill='both', expand=True)
    topbar = _frame(workspace, '#2b323c', height=59)
    topbar.pack(fill='x')
    topbar.pack_propagate(False)
    _label(topbar, 'GÖRSEL ÜRETİM MERKEZİ', 12, bold=True, bg='#2b323c').pack(
        side='left', padx=25, pady=14)
    _button(topbar, '⏻  Programı Kapat', app.close, color='#64243d', size=11).pack(side='right', padx=(6,20), pady=8)
    _button(topbar, '✥  Arayüzü Düzenle', lambda: LayoutEditor(root,'dashboard',on_save=app._refresh_visual_cards),color='#30345a',size=10).pack(side='right',padx=3,pady=8)
    _button(topbar, '↕ Kartları Taşı', lambda:(drag_mode.set(not drag_mode.get()),app._refresh_visual_cards()),color='#303f54',size=10).pack(side='right',padx=3,pady=8)
    _label(topbar, '●  Çalışma alanı korumalı  ·  V4.10.1', 10,
           GREEN, bg='#2b323c').pack(side='right', padx=10)

    scroll_host = _frame(workspace)
    scroll_host.pack(fill='both', expand=True)
    canvas = tk.Canvas(scroll_host, bg=BG, highlightthickness=0, borderwidth=0)
    sc = ttk.Scrollbar(scroll_host, orient='vertical', command=canvas.yview)
    canvas.configure(yscrollcommand=sc.set)
    sc.pack(side='right', fill='y')
    canvas.pack(side='left', fill='both', expand=True)
    content = _frame(canvas)
    window = canvas.create_window((0,0), window=content, anchor='nw')
    content.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
    canvas.bind('<Configure>', lambda e: canvas.itemconfigure(window, width=e.width))
    def wheel(e):
        if getattr(e,'delta',0) and canvas.winfo_ismapped():
            canvas.yview_scroll(-1 if e.delta > 0 else 1,'units')
        return 'break'
    canvas.bind('<MouseWheel>', wheel)
    app._wheel_canvas = canvas

    page = _frame(content)
    page.pack(fill='both', expand=True, padx=23, pady=22)
    banner = _frame(page, '#271b46')
    banner.pack(fill='x', pady=(0, 15))
    accent = _frame(banner, ACCENT, height=5)
    accent.pack(fill='x')
    banner_inner = _frame(banner, '#271b46')
    banner_inner.pack(fill='x', padx=22, pady=23)
    _label(banner_inner, 'BUGÜN NELER ÜRETECEĞİZ?', 22, bold=True,
           bg='#271b46').pack(fill='x')
    _label(banner_inner, 'Şablonları incele, PETEK maskelerini düzenle, mağaza bazlı mockup üret.',
           12, color='#d4cbe9', bg='#271b46').pack(fill='x', pady=(7,0))

    strip = _frame(page)
    strip.pack(fill='x', pady=(0,13))
    for i,(num,label,color) in enumerate([
       ('7', 'Ürün kategorisi', ACCENT),
       ('4 köşe', 'İnsan onayı', BLUE),
       ('PETEK', 'Maske kontrolü', MAGENTA),
       ('Güvenli', 'Ayrı veri klasörü', GREEN)]):
        frame = _frame(strip, PANEL)
        frame.pack(side='left', fill='both', expand=True, padx=(0 if i==0 else 6, 0))
        _label(frame, num, 19, bold=True, color=color, bg=PANEL).pack(anchor='w', padx=14, pady=(11,0))
        _label(frame, label, 10, MUTED, bg=PANEL).pack(anchor='w', padx=14, pady=(0,13))

    _label(page, 'Üretim ve yönetim', 17, bold=True).pack(anchor='w', pady=(0,7))
    grid = _frame(page)
    grid.pack(fill='x')
    grid.grid_columnconfigure(0, weight=1, uniform='cards')
    grid.grid_columnconfigure(1, weight=1, uniform='cards')
    # V4.10.0 visual-only tabs. Each card keeps its original callback; only
    # safe user-local appearance settings decide its notebook page and order.
    card_defs={
      'review':('Şablonları İncele ve Onayla','7 kategori, dört köşe ve PETEK maske onayı.',
                'Şablon Merkezi',app.open_legacy_review,ACCENT),
      'production':('Seri Mockup Üretimi','Mağazaya özel onaylı şablon üretimi ve Excel.',
                'Üretim Merkezi',app.open_unified_v4,MAGENTA),
      'designs':('Ham Baskı Tasarımları','Ham1, Ham2... benzersiz numara havuzu.',
                'Klasörü Aç',app.open_ham_design_folder,BLUE),
      'tools':('Profesyonel Araçlar','Görsel seçici, isimlendirme, format, 4K ve SEO.',
                'Araçları Aç',app.open_legacy_tools,ORANGE),
      'petek':('PETEK İşlemleri','15 yarık, kavis ve maske onaylarını kontrol et.',
                'PETEK İnceleme',app.open_legacy_review,MAGENTA),
      'stage':('Yeni Şablon Ekle','Görselleri YENI-BOS havuzuna güvenli kopyala.',
                'Güvenle İçe Al',app.open_safe_stage_v493,GREEN),
      'reports':('Raporlar ve Kurtarma','Bütünlük, yedek, kayıtlar ve araçlar.',
                'Gelişmiş Araçları Göster',app.toggle_advanced,GREEN),
      'tests':('Yapmam Gereken Testler','Yeni güncellemelerin kalıcı kabul merkezi.',
                'Test Merkezine Git',app.open_tests_v493,ACCENT),
      'notes':('Notlarım ve Görevlerim','Notlarını ve yapılacak işlerini kaydet.',
                'Notlarımı Aç',app.open_notes_v493,BLUE),
      'search':('Özellik / Araç Ara','Bütün özellikleri adlarıyla ara.',
                'Araç Bul',app.open_tool_search_v493,ORANGE),
    }
    # The formerly unused static grid host is the one live card container.
    app._visual_grid_host=grid
    def redraw_visual_cards(prefs=None):
        prefs=prefs or load_visual_layout()['dashboard']
        for child in tuple(grid.winfo_children()):child.destroy()
        tabs=prefs['tabs'];accent=prefs.get('accent',ACCENT)
        palette=prefs.get('colors',{})
        surface=palette.get('background',BG)
        for widget in (root,content,page,grid):
            widget.configure(bg=surface)
        canvas.configure(bg=surface)
        # An intentional edit mode: release on another card to persist a move.
        # No drag starts production, changes mask data, or touches template DB.
        def on_drag(source,event,tab):
            target_widget=root.winfo_containing(event.x_root,event.y_root)
            while target_widget is not None and not hasattr(target_widget,'_card_uid'):
                target_widget=getattr(target_widget,'master',None)
            target=getattr(target_widget,'_card_uid',None)
            keys=tabs.get(tab,[])
            if not drag_mode.get() or not target or source==target or source not in keys or target not in keys:return
            data=load_visual_layout()
            order=data['dashboard']['tabs'].get(tab,[])
            if source not in order or target not in order:return
            order.remove(source);order.insert(order.index(target),source)
            try:
                save_visual_layout(data)
                redraw_visual_cards()
            except OSError as exc:
                messagebox.showerror('Düzen kaydedilemedi',str(exc),parent=root)
        notebook=ttk.Notebook(grid)
        notebook.grid(row=0,column=0,columnspan=2,sticky='nsew')
        for tab,identities in tabs.items():
            view=_frame(notebook)
            notebook.add(view,text=tab)
            view.grid_columnconfigure(0,weight=1,uniform='cards')
            view.grid_columnconfigure(1,weight=1,uniform='cards')
            for i,key in enumerate(identities):
                if key not in card_defs:continue
                title,detail,action,callback,color=card_defs[key]
                if prefs.get('effect')=='kapalı':color=ACCENT
                elif prefs.get('effect')=='belirgin':color=accent
                btn=_card(view,title,detail,action,callback,color,i//2,i%2,
                         card_key=key,drag_mode=drag_mode,palette=palette,
                         on_drop=lambda source,e,t=tab:on_drag(source,e,t))
                if key=='review':app.review_button=btn
                if key=='tools':app.tools_button=btn
    app._refresh_visual_cards=redraw_visual_cards
    redraw_visual_cards()

    workspace_panel = _frame(page, PANEL)
    workspace_panel.pack(fill='x', pady=(16, 12))
    _label(workspace_panel, 'Ana Çalışma Klasörü', 13, bold=True,
           bg=PANEL).pack(anchor='w', padx=18, pady=(15,8))
    row = _frame(workspace_panel, PANEL)
    row.pack(fill='x', padx=18)
    app.runtime_text = tk.StringVar(value=str(app.runtime))
    entry = ttk.Entry(row, textvariable=app.runtime_text, state='readonly')
    entry.pack(side='left', fill='x', expand=True, padx=(0,8))
    _button(row, 'Değiştir', app.select_runtime).pack(side='left', padx=4)
    _button(row, 'Klasörü Aç', app.open_runtime).pack(side='left', padx=4)
    app.ham_home_status = tk.StringVar(value='HAM tasarım izlemesi: başlangıç kontrolünde')
    _label(workspace_panel, '', 10, MUTED, bg=PANEL,
           textvariable=app.ham_home_status).pack(fill='x', padx=18, pady=(11,15))

    app.status = tk.StringVar(value='Hazır. Mevcut şablonlar ve maskeler otomatik değiştirilmez.')
    _label(page, '', 11, GREEN, textvariable=app.status,
           wraplength=800).pack(fill='x', pady=(5,13))
    app.advanced_toggle = ttk.Button(page, text='▶ Diğer Araçlar ve Kurtarma',
                           command=app.toggle_advanced)
    app.advanced_toggle.pack(fill='x', pady=(0,8))
    app.advanced_panel = ttk.Frame(page, padding=14)
    advanced_actions = [
      ('G3 Bütünlük Denetimi', app.g3_audit),
      ('SQLite Güvenli Yedek', app.g3_backup),
      ('PETEK Maskesi — Eski Editör', app.open_review),
      ('PETEK Klasör Denetimi', app.prepare_petek_folders),
      ('Magenta Dosya Denetimi', app.open_consolidation),
      ('İnceleme Servisini Durdur', app.stop_legacy_editor),
      ('Üretim Kayıt Denetimi', app.open_unified_audit),
      ('Kesinti ve Kilit Kurtarma', app.open_crash_recovery),
      ('Eski PETEK Üretimi', app.open_petek),
      ('PETEK Çıktıları', app.open_petek_results),
      ('Silinen Çıktı Kayıtlarını Koruma', app.archive_user_deleted_outputs),
      ('HAM Numara Kontrolü', app.show_ham_design_audit),
      ('Sistem Durumu', app.show_health),
    ]
    for i,(title,handler) in enumerate(advanced_actions):
        ttk.Button(app.advanced_panel, text=title, command=handler).grid(
            row=i//2, column=i%2, sticky='ew', padx=6,pady=5)
    app.advanced_panel.columnconfigure(0,weight=1)
    app.advanced_panel.columnconfigure(1,weight=1)

    _label(page, 'İşlem Günlüğü', 16, bold=True).pack(anchor='w',pady=(14,8))
    app.log = scrolledtext.ScrolledText(page, height=6, state='disabled',
        font=('Consolas',10), bg='#14192a', fg=FG, insertbackground=FG,
        padx=12, pady=10, relief='flat', borderwidth=0, wrap='word')
    app.log.pack(fill='both', expand=True, pady=(0,12))
    _label(page, 'Veri koruması: orijinal şablonlar, maskeler, onaylar ve SQLite kayıtları bu arayüz tarafından değiştirilmez.',
           10, MUTED, wraplength=820).pack(fill='x',pady=(0,12))
