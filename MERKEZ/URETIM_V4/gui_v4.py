"""V4.0 Tkinter Windows UI for 7-Category Unlimited Batch Production & Crash Recovery."""
from __future__ import annotations
from error_advisor_v498 import showerror as helpful_error

import os
import subprocess
import json
import tempfile
import time
from pathlib import Path
import queue
import threading
import stat
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from PIL import Image, ImageTk
from dark_theme_v42 import BG, PANEL, FG, ACCENT
from ui_layout_v498 import LayoutEditor, load as load_visual_layout
from help_v42 import bind_help, attach_context_help, help_details
from version_v45 import TITLE as VERSION_TEXT, VERSION as APP_VERSION

from PETEK_V3.registry import Registry as PetekRegistry
from .unified_batch import UnifiedV4Batch, iter_designs
from .template_filter_v492 import filtered_templates
from .unlimited_selection import CATEGORY_LABELS_TR
from PETEK_V3.petek_finish_v492 import darken_slot_lips, despill_lower_left, draw_fifteen_slots, despill_lower_left_geometry_v493
from PETEK_V3.final_cleanup_v495 import cleanup_petek_magenta
from .store_profiles_v47 import StoreProfiles
from .store_profiles_v47 import key_for
from .store_selection_diagnostic_vnext import (compare_store_selection, format_store_diagnostic,
                                                     read_profile_identity)
from .cloud_excel_v43 import CloudExcel
from .design_proxy_v43 import prepare_render_artwork
from .upscale4k_v44 import preflight as upscale_preflight, UpscaleError
from .on_demand_4k_v495 import OnDemand4K, user_state_path

try:
    from URETIM_V4 import ui_table_v1 as _table_tools
except Exception:
    _table_tools = None
from .unified_batch import _render_legacy_six_cover, _build_legacy_category_mask
from .performance_v501 import planning_summary, summary_text
from .finish_material_v46 import DAYLIGHT, apply_material_finish
from .optical_qa_v47 import measure_effect
from PETEK_V3.cutout_paste import render_with_cutout_paste
from PETEK_V3.petek_visual_pipeline_vnext import render_petek_visual
from PETEK_V3 import engine as petek_engine
from .finish_v42 import GLASS
from .four_mockup_ui_v1 import FourMockupPanel
from .petek_overlay_variations_v1 import (
    preflight as petek_overlay_preflight,
    process_folder as process_petek_overlay_folder,
    refresh_overlay_cache,
)
import cv2

LIGHT_LABELS = ("Cam Yansıması AÇIK / Doğal Işık", "Efektler KAPALI / Orijinal Baskı")
SUN_LABELS = ("Kapalı (eski görünüm)", "Doğal (7 kategori)", "Belirgin (7 kategori / 2 gölge)")
SUN_CODES = dict(zip(SUN_LABELS, ("off", "dogal", "belirgin")))


def _lighting_code(value: str) -> str:
    return "off" if value == LIGHT_LABELS[1] else "natural"



class UnifiedV4BatchWindow:
    """7-category unlimited human-approved batch production and crash recovery window."""

    def __init__(self, parent, *, runtime_root: Path | None = None, petek_registry: PetekRegistry | None = None,
                 v4_root: Path | None = None, prebuilt_engine=None, embedded_parent=None):
        self.runtime_root = Path(runtime_root).resolve() if runtime_root else None
        self.petek_registry = petek_registry or PetekRegistry()
        self.batch_engine = prebuilt_engine if prebuilt_engine is not None else UnifiedV4Batch(
            v4_root,
            runtime_root=self.runtime_root,
            petek_registry=self.petek_registry,
        )
        self._worker_kind = None
        self._render_stop_requested = False
        self.embedded = embedded_parent is not None
        self.window = embedded_parent if self.embedded else tk.Toplevel(parent)
        if not self.embedded:
            self.window.title(VERSION_TEXT + " — 7 Kategori Üretim / Bulut Excel / İsteğe Bağlı 4K")
            self.window.geometry("1360x880")
            self.window.minsize(1040,650)
            self.window.configure(background=BG)
        # Production is a MODELLESS tool window. No grab_set/wait_window or
        # transient owner restriction: dashboard + browser review stay usable.
        # Users can move between all three while respecting immutable approvals.
        self.window.wm_group(self.window) if False else None

        self._context_help = attach_context_help(self.window)
        self.progress = tk.StringVar(value='Hazır. Onaylı şablonlar yükleniyor…')
        self.selection_summary = tk.StringVar(value='Şablon: 0 · Tasarım: 0 · Mağaza: LOCAL · Beklenen iş: 0')
        self.workflow_hint = tk.StringVar(value='01 Şablon seçin → 02 tasarım klasörü → 03 mağaza → 04 ön kontrol → üretim')
        self.result_summary = tk.StringVar(value='Üretilen: 0 · Başarılı: 0 · Hatalı: 0 · Atlanan: 0')
        self.current_operation_report = None
        self.live_progress_title = tk.StringVar(value='Üretim hazır')
        self.live_progress_detail = tk.StringVar(value='Üretim başlatıldığında canlı durum burada görünür.')
        self.live_progress_percent = tk.StringVar(value='0%')
        self.live_progress_counts = tk.StringVar(value='0 / 0 işlem')
        self.live_progress_time = tk.StringVar(value='Geçen: 0 sn · Tahmini kalan: —')
        self.cloud_progress_title = tk.StringVar(value='Excel / linkleme hazır')
        self.cloud_progress_detail = tk.StringVar(value='Linkleme başlatıldığında canlı durum burada görünür.')
        self.cloud_progress_percent = tk.StringVar(value='0%')
        self.cloud_progress_counts = tk.StringVar(value='0 / 0 görsel · Yeni: 0 · Mevcut: 0 · Hata: 0')
        self.cloud_progress_time = tk.StringVar(value='Geçen: 0 sn · Tahmini kalan: —')
        self.overlay_progress_title = tk.StringVar(value='PETEK Overlay Varyasyonları hazır')
        self.overlay_progress_detail = tk.StringVar(value='Overlay aktif edildiğinde dört ölçü burada izlenir.')
        self.overlay_progress_percent = tk.StringVar(value='0%')
        self.overlay_progress_counts = tk.StringVar(value='0 / 0 varyasyon · Başarılı: 0 · Atlanan: 0 · Hata: 0')
        self.overlay_progress_time = tk.StringVar(value='Geçen: 0 sn · Tahmini kalan: —')
        self._operation_monitor_var = getattr(parent, 'operation_text', None)
        self._last_progress_snapshot = None
        self._retry_scope = None
        # Read-only discovery receipt.  It is kept with the current UI state so
        # users can inspect skipped templates without rescanning or mutating
        # the approval/ledger stores.
        self.discovery_audit = {'skipped': []}
        self._ui_state_path = user_state_path().parent / 'production_ui_preferences.json'

        # Fixed action rail: the primary operation and the live result summary
        # stay visible while the four selection/settings sections scroll.
        footer = ttk.Frame(self.window, padding=(12, 8))
        footer.pack(side='bottom', fill='x')
        footer.columnconfigure(1, weight=1)
        self.start_button = ttk.Button(
            footer, text='▶  ÜRETİME BAŞLA', command=self.start,
            style='Premium.Primary.TButton', state='disabled', width=22)
        # Keep the primary action at its requested size.  Stretching a ttk
        # button over the full footer height makes the themed green surface
        # paint as several adjacent blocks on Windows/high-DPI displays.
        self.start_button.grid(row=0, column=0, rowspan=5, sticky='nw', padx=(0, 12), pady=(2, 2))
        ttk.Label(footer, textvariable=self.selection_summary,
                  font=('Segoe UI', 10, 'bold')).grid(row=0, column=1, sticky='w')
        ttk.Label(footer, textvariable=self.progress,
                  font=('Segoe UI', 10)).grid(row=1, column=1, sticky='w', pady=(3, 0))
        ttk.Label(footer, textvariable=self.result_summary,
                  font=('Segoe UI', 10)).grid(row=2, column=1, sticky='w', pady=(3, 0))
        footer_help_holder = ttk.Frame(footer)
        footer_help_holder.grid(row=0, column=2, rowspan=5, sticky='e', padx=(8, 0))
        self._footer_help = self._context_help.button(
            footer_help_holder,
            help_details('Seçimleri ve otomatik ön kontrolleri doğrulayıp mevcut gerçek üretim motorunu başlatır.',
                         'Şablon, tasarım ve mağaza seçimini tamamladıktan sonra kullanılır.',
                         'Onaylı kaynak/maskeleri değiştirmez; üretim ledger ve yeni çıktı kayıtları oluşturabilir.'),
            side='right', padx=(8, 0))

        # Compact live production card.  It stays in the fixed action rail so
        # it remains visible while the long selection form is scrolled.
        live_card = ttk.Frame(footer, padding=(0, 7, 0, 0))
        live_card.grid(row=4, column=1, columnspan=2, sticky='ew')
        live_card.columnconfigure(0, weight=1)
        live_head = ttk.Frame(live_card)
        live_head.grid(row=0, column=0, sticky='ew')
        ttk.Label(live_head, textvariable=self.live_progress_title,
                  font=('Segoe UI', 10, 'bold')).pack(side='left')
        ttk.Label(live_head, textvariable=self.live_progress_percent,
                  font=('Segoe UI', 10, 'bold')).pack(side='right')
        self.live_progressbar = ttk.Progressbar(
            live_card, orient='horizontal', mode='determinate', maximum=100,
            length=420, style='Live.Horizontal.TProgressbar')
        self.live_progressbar.grid(row=1, column=0, sticky='ew', pady=(3, 2))
        ttk.Label(live_card, textvariable=self.live_progress_detail,
                  foreground='#93A6C4').grid(row=2, column=0, sticky='w')
        live_meta = ttk.Frame(live_card)
        live_meta.grid(row=3, column=0, sticky='ew', pady=(2, 0))
        ttk.Label(live_meta, textvariable=self.live_progress_counts).pack(side='left')
        ttk.Label(live_meta, textvariable=self.live_progress_time).pack(side='right')
        cloud_card = ttk.Frame(footer, padding=(0, 7, 0, 0))
        cloud_card.grid(row=6, column=1, columnspan=2, sticky='ew')
        cloud_card.columnconfigure(0, weight=1)
        cloud_head = ttk.Frame(cloud_card); cloud_head.grid(row=0, column=0, sticky='ew')
        ttk.Label(cloud_head, textvariable=self.cloud_progress_title, font=('Segoe UI', 10, 'bold')).pack(side='left')
        ttk.Label(cloud_head, textvariable=self.cloud_progress_percent, font=('Segoe UI', 10, 'bold')).pack(side='right')
        self.cloud_progressbar = ttk.Progressbar(cloud_card, orient='horizontal', mode='determinate', maximum=100,
                                                 length=420, style='Cloud.Horizontal.TProgressbar')
        self.cloud_progressbar.grid(row=1, column=0, sticky='ew', pady=(3, 2))
        ttk.Label(cloud_card, textvariable=self.cloud_progress_detail, foreground='#93A6C4').grid(row=2, column=0, sticky='w')
        cloud_meta = ttk.Frame(cloud_card); cloud_meta.grid(row=3, column=0, sticky='ew', pady=(2, 0))
        ttk.Label(cloud_meta, textvariable=self.cloud_progress_counts).pack(side='left')
        ttk.Label(cloud_meta, textvariable=self.cloud_progress_time).pack(side='right')
        overlay_card = ttk.Frame(footer, padding=(0, 7, 0, 0))
        overlay_card.grid(row=7, column=1, columnspan=2, sticky='ew')
        overlay_card.columnconfigure(0, weight=1)
        overlay_head = ttk.Frame(overlay_card); overlay_head.grid(row=0, column=0, sticky='ew')
        ttk.Label(overlay_head, textvariable=self.overlay_progress_title, font=('Segoe UI', 10, 'bold')).pack(side='left')
        ttk.Label(overlay_head, textvariable=self.overlay_progress_percent, font=('Segoe UI', 10, 'bold')).pack(side='right')
        self.overlay_progressbar = ttk.Progressbar(overlay_card, orient='horizontal', mode='determinate', maximum=100,
                                                   length=420, style='Overlay.Horizontal.TProgressbar')
        self.overlay_progressbar.grid(row=1, column=0, sticky='ew', pady=(3, 2))
        ttk.Label(overlay_card, textvariable=self.overlay_progress_detail, foreground='#93A6C4').grid(row=2, column=0, sticky='w')
        overlay_meta = ttk.Frame(overlay_card); overlay_meta.grid(row=3, column=0, sticky='ew', pady=(2, 0))
        ttk.Label(overlay_meta, textvariable=self.overlay_progress_counts).pack(side='left')
        ttk.Label(overlay_meta, textvariable=self.overlay_progress_time).pack(side='right')
        excel_actions = ttk.Frame(footer)
        excel_actions.grid(row=5, column=1, columnspan=2, sticky='w', pady=(5, 0))
        self.cloud_button_visible = ttk.Button(
            excel_actions, text='☁ Linke çevir + Excel’e yaz', command=self.start_cloud_links)
        self.cloud_button_visible.pack(side='left', padx=(0, 5))
        ttk.Button(excel_actions, text='Mağaza Trendyol Excel’i',
                   command=self.export_marketplace_template).pack(side='left', padx=5)
        ttk.Button(excel_actions, text='Çıktı klasörü',
                   command=self.open_trendyol_output_folder).pack(side='left', padx=5)
        ttk.Button(excel_actions, text='Son Excel’i aç',
                   command=self.open_last_trendyol_output).pack(side='left', padx=5)
        ttk.Style(self.window).configure(
            'Live.Horizontal.TProgressbar', troughcolor='#131C2B',
            background=ACCENT, lightcolor=ACCENT, darkcolor=ACCENT,
            bordercolor='#22304A')
        ttk.Style(self.window).configure('Cloud.Horizontal.TProgressbar', troughcolor='#131C2B',
            background='#17D3A3', lightcolor='#17D3A3', darkcolor='#17D3A3', bordercolor='#22304A')
        ttk.Style(self.window).configure('Overlay.Horizontal.TProgressbar', troughcolor='#131C2B',
            background='#F0B84C', lightcolor='#F0B84C', darkcolor='#F0B84C', bordercolor='#22304A')

        # Whole production form scrolls on small Windows displays. Every button
        # remains reachable even with 125-150% DPI scaling and new filters.
        host=ttk.Frame(self.window)
        host.pack(fill='both',expand=True)
        self.main_canvas=tk.Canvas(host,bg=BG,highlightthickness=0,borderwidth=0)
        main_scroll=ttk.Scrollbar(host,orient='vertical',command=self.main_canvas.yview)
        self.main_canvas.configure(yscrollcommand=main_scroll.set)
        main_scroll.pack(side='right',fill='y')
        self.main_canvas.pack(side='left',fill='both',expand=True)
        area=ttk.Frame(self.main_canvas,padding=18)
        area_id=self.main_canvas.create_window((0,0),window=area,anchor='nw')
        area.bind('<Configure>',lambda _ev:self.main_canvas.configure(scrollregion=self.main_canvas.bbox('all')))
        self.main_canvas.bind('<Configure>',lambda ev:self.main_canvas.itemconfigure(area_id,width=ev.width))
        # A production window can be mounted inside Graphite's Frame.  Binding
        # the wheel to that Frame does not receive events from its descendants;
        # bind on the actual Tk toplevel and accept events only while the
        # pointer is inside this production host.  This keeps the real form's
        # existing Listbox/Text scrolling and the Graphite/review surfaces
        # independent.
        wheel_root = self.window.winfo_toplevel()

        def inside_host(widget):
            current = widget
            while current is not None:
                try:
                    if str(current) == str(host):
                        return True
                    parent_path = current.winfo_parent()
                    if not parent_path:
                        return False
                    current = wheel_root.nametowidget(parent_path)
                except (tk.TclError, AttributeError):
                    return False
            return False

        def scroll_form(event, units=None):
            if not inside_host(getattr(event, 'widget', None)):
                return
            if event.widget is self.listbox or isinstance(event.widget,(tk.Listbox,tk.Text)):
                return
            if units is None:
                delta = getattr(event, 'delta', 0)
                if not delta:
                    return
                units = -max(1, int(round(abs(delta) / 120))) if delta > 0 else max(1, int(round(abs(delta) / 120)))
            self.main_canvas.yview_scroll(units, 'units')
            return 'break'

        self._wheel_root = wheel_root
        self._wheel_binding = wheel_root.bind('<MouseWheel>', scroll_form, add='+')
        self._wheel_up_binding = wheel_root.bind(
            '<Button-4>', lambda event: scroll_form(event, -1), add='+')
        self._wheel_down_binding = wheel_root.bind(
            '<Button-5>', lambda event: scroll_form(event, 1), add='+')

        hero=ttk.Frame(area,padding=(15,12))
        hero.pack(fill='x',pady=(0,10))
        ttk.Label(
            hero,
            text=f"SERİ MOCKUP ÜRETİM MERKEZİ   •   7 KATEGORİ   •   {APP_VERSION}",
            font=("Segoe UI", 19, "bold"),
        ).pack(anchor="w", pady=(0, 6))
        intro_label = ttk.Label(
            area,
            text="Altı kategori SQLite insan onaylı şablonları + PETEK onaylı maskeleri kullanır.\n"
            "Sınırsız iş / 10 şablon sınırı yoktur. Önce yerel üretim; sonra istersen bulut HTTPS linkli Excel.",
            wraplength=800,
        )
        intro_label.pack(anchor="w", pady=(0, 8))
        if self.embedded:
            # Graphite already supplies the production title/context.  Keep
            # the native form's four functional sections without a second
            # hero banner or a repeated explanatory header.
            hero.pack_forget()
            intro_label.pack_forget()

        self._prod_tabbar=ttk.Frame(area,padding=(4,8))
        self._prod_tabbar.pack(fill='x',pady=(0,7))
        quick_tools = ttk.Frame(area)
        quick_tools.pack(fill='x', pady=(0, 5))
        ttk.Label(quick_tools, text='Günlük akış: şablon → tasarım → mağaza → üretim',
                  font=('Segoe UI', 11, 'bold')).pack(side='left')
        ttk.Label(quick_tools, textvariable=self.workflow_hint,
                  foreground='#93A6C4', font=('Segoe UI', 9)).pack(side='left', padx=(14, 0))
        ttk.Button(quick_tools, text='Gelişmiş Araçlar',
                   command=self.open_advanced_tools).pack(side='right')
        self._context_help.button(
            quick_tools,
            help_details('Günlük akışta gerekmeyen test, bakım, mağaza yönetimi, SHA ve Excel işlemlerini açar.',
                         'Yalnız gelişmiş bir kontrol gerektiğinde kullanılır.',
                         'Açılan araçlar kendi mevcut güvenlik/onay kurallarını kullanır.'),
            side='right')
        templates_panel=ttk.LabelFrame(area,text='01  ŞABLON SEÇİMİ  ·  Filtrele / seç / önizle',style='Premium.TLabelframe',padding=(15,13))
        templates_panel.pack(fill='x',pady=(7,10))
        ttk.Label(
            templates_panel,
            text="1. Üretime Hazır Onaylı (APPROVED) Şablonlar (7 Kategori — Çoklu Seçim):",
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w")
        preview_frame = ttk.Frame(templates_panel)
        preview_frame.pack(fill="x", pady=4)
        self.listbox = tk.Listbox(preview_frame, selectmode="extended", height=9, exportselection=False,
                                  bg=PANEL, fg=FG, selectbackground=ACCENT, selectforeground='#fff')
        self.listbox.pack(side="left", fill="both", expand=True)
        self.listbox.bind('<<ListboxSelect>>', self._preview_selected)
        if _table_tools is not None:
            _table_tools.attach_listbox_tooltip(self.listbox)
            _table_tools.add_listbox_xscroll(self.listbox)
        photo_column = ttk.Frame(preview_frame, width=228)
        photo_column.pack(side="right", padx=(12,0), fill="y")
        photo_column.pack_propagate(False)
        self.photo_label = ttk.Label(photo_column, text='Kaynak fotoğraf önizlemesi', anchor='center')
        self.photo_label.pack(fill='both', expand=True)
        self.photo_text = tk.StringVar(value='Onaylı şablon seçin.')
        ttk.Label(photo_column, textvariable=self.photo_text, wraplength=222).pack(fill='x')
        self.photo_ref = None
        self.template_sources = {}
        self.template_items = {}
        self.all_templates = []
        self._first_template_load = True
        self.selected_uids = set()
        self.mapping: list[str] = []
        self._filter_redrawing = False
        self.store_only_view = False
        filter_bar = ttk.Frame(templates_panel)
        filter_bar.pack(fill="x", pady=(3, 4))
        ttk.Label(filter_bar, text="Kategori:").pack(side="left")
        self.category_filter = tk.StringVar(value="Tümü")
        self.category_options = ["Tümü"] + list(CATEGORY_LABELS_TR)
        category_combo = ttk.Combobox(filter_bar, textvariable=self.category_filter, width=23,
            values=self.category_options, state="readonly")
        category_combo.pack(side="left", padx=(4, 10))
        ttk.Label(filter_bar, text="Şablon ara:").pack(side="left")
        self.search_filter = tk.StringVar()
        ttk.Entry(filter_bar, textvariable=self.search_filter, width=25).pack(side="left", padx=(4, 10), fill="x", expand=True)
        ttk.Label(filter_bar, text="Sırala:").pack(side="left")
        self.sort_filter = tk.StringVar(value="Kategori / Ad")
        sort_combo=ttk.Combobox(filter_bar,textvariable=self.sort_filter,width=15,state="readonly",
                                values=("Kategori / Ad","Ad (A-Z)","Ad (Z-A)"))
        sort_combo.pack(side="left",padx=(4,0))
        self._context_help.button(
            filter_bar,
            help_details('Kategori, arama ve sıralama ile onaylı şablon listesini daraltır.',
                         'Üretim kapsamını seçerken kullanılır; liste seçimini kaybetmeden filtre değiştirilebilir.',
                         'Salt okunurdur; onaylı şablon ve kayıt dosyalarını değiştirmez.'),
            side='right')
        self.filter_count = tk.StringVar(value="Liste yükleniyor...")
        ttk.Label(templates_panel,textvariable=self.filter_count,font=("Segoe UI",10,"bold")).pack(anchor="w",pady=(1,2))
        # These actions affect the template selection directly, so keep them
        # beside the live list rather than hiding them in Gelişmiş Araçlar.
        # The compact row preserves the normal workflow while making the
        # scope-changing commands discoverable when the user is choosing
        # templates.
        template_selection_tools = ttk.Frame(templates_panel)
        template_selection_tools.pack(fill='x', pady=(0, 3))
        ttk.Label(template_selection_tools, text='Seçim işlemleri:').pack(side='left')
        self.select_all_button = ttk.Button(
            template_selection_tools, text='Tüm onaylıları seç',
            command=self.select_all, width=20)
        self.select_all_button.pack(side='left', padx=(7, 3))
        self._context_help.button(
            template_selection_tools,
            help_details('Listede bulunan bütün insan onaylı şablonları üretim seçimine alır.',
                         'Geniş kapsamlı bir üretim planı hazırlarken kullanılır.',
                         'Üretimi başlatmaz; yalnızca geçici üretim seçimini değiştirir.'),
            side='left', padx=(1, 0))
        skipped_bar = ttk.Frame(templates_panel)
        skipped_bar.pack(fill='x', pady=(2, 0))
        self.skipped_summary = tk.StringVar(value='Atlanan: — ·')
        ttk.Label(skipped_bar, textvariable=self.skipped_summary,
                  font=('Segoe UI', 10), foreground='#17D3A3').pack(side='left')
        self.skipped_button = ttk.Button(
            skipped_bar, text='Nedenleri Gör', command=self.show_skipped_reasons,
            state='disabled')
        self.skipped_button.pack(side='left', padx=(8, 0))
        self._context_help.button(
            skipped_bar,
            help_details('Güvenlik ön kontrolünden geçemeyen şablonları nedenleriyle listeler.',
                         'Üretim listesinde beklediğiniz bir şablon yoksa önce burada kontrol edin.',
                         'Salt okunurdur; onaylı kayıtları, maskeleri ve kaynak dosyalarını değiştirmez.'),
            side='right')
        for var in (self.category_filter, self.search_filter, self.sort_filter):
            var.trace_add('write', lambda *_: self.apply_filters())
        self.listbox.bind('<<ListboxSelect>>', self._on_selection_change, add='+')

        btn_row = ttk.Frame(templates_panel)
        btn_row.pack(fill="x", pady=3)
        template_actions = (
            ("Tüm Onaylı Şablonları Yenile", self.reload),
            ("Tüm Şablonları Seç", self.select_all),
            ("Filtreleneni Seç", self.select_filtered),
            ("Seçimi Temizle", self.clear_selection),
            ("7 Kategori Güneş / Efekt A/B — ÖNCE / SONRA", self.start_ab_preview),
            ("Yarım İş / Kilit Kurtarma (Onaylı)", self.open_recovery),
        )
        for column in range(3):
            btn_row.columnconfigure(column, weight=1)
        for index, (label, command) in enumerate(template_actions):
            ttk.Button(btn_row, text=label, command=command).grid(
                row=index // 3, column=index % 3, sticky='ew', padx=3, pady=3)
        # Daily flow is driven by the list and live count. Bulk selection,
        # reload, A/B previews and recovery stay available in the advanced
        # tools drawer instead of competing with the primary workflow.
        btn_row.pack_forget()

        designs_panel=ttk.LabelFrame(area,text='02  BASKI TASARIMLARINI SEÇ',style='Premium.TLabelframe',padding=(15,13))
        designs_panel.pack(fill='x',pady=(7,10))
        row = ttk.Frame(designs_panel)
        row.pack(fill="x", pady=8)
        default_ham=(self.runtime_root/'HAM BASKI TASARIMLARI') if self.runtime_root else None
        self.design_folder = tk.StringVar(value=str(default_ham) if default_ham and default_ham.is_dir() else '')
        self.design_folder.trace_add('write', lambda *_: self._refresh_selection_summary())
        ttk.Entry(row, textvariable=self.design_folder).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="2. Baskı Tasarımları Klasörünü Seç", command=self.browse).pack(side="left", padx=6)
        self._context_help.button(
            row,
            help_details('Üretimde kullanılacak baskı görsellerinin klasörünü seçer.',
                         'Şablon seçiminden sonra, üretimden önce kullanılır.',
                         'Yalnız seçtiğiniz klasörü okur; kaynak şablon ve üretim kayıtlarını değiştirmez.'),
            side='right')

        # Files moved under a Kullanildi/Kullanılanlar folder are protected
        # from the normal production pass.  An operator may explicitly opt
        # back in when a previous run rendered the design but its Excel/cloud
        # linking step was not performed.  This is deliberately opt-in so a
        # routine run cannot accidentally regenerate already-used designs.
        self.include_used_designs = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            designs_panel,
            text='Kullanılanlar altındaki tasarımları bu üretime tekrar dahil et',
            variable=self.include_used_designs,
        ).pack(anchor='w', pady=(0, 2))
        self._context_help.button(
            designs_panel,
            help_details(
                'Yalnızca açıkça seçildiğinde Kullanildi/Kullanılanlar altındaki görselleri yeniden kuyruğa alır.',
                'Önceki üretimde görsel oluştuğu halde Excel/linkleme yapılmadıysa kullanılabilir.',
                'Kaynak görseli, dört köşeyi ve ayarlar.json verisini değiştirmez; normal üretim davranışı varsayılan olarak kapalıdır.',
            ),
            side='right')

        stores_panel=ttk.LabelFrame(area,text='03  MAĞAZA SEÇ',style='Premium.TLabelframe',padding=(15,13))
        stores_panel.pack(fill='x',pady=(7,10))
        store_header = ttk.Frame(stores_panel)
        store_header.pack(fill='x')
        ttk.Label(store_header, text='Üretim için bir veya daha fazla mağaza seçin.',
                  font=('Segoe UI', 11, 'bold')).pack(side='left')
        self._context_help.button(
            store_header,
            help_details('Seçilen mağazanın güncel onaylı şablon atamalarını üretim ön kontrolüne bağlar.',
                         'Günlük üretimde mağazayı seçtikten sonra başka seçim yapmadan devam edebilirsiniz.',
                         'Profil ve atama kayıtlarını değiştirmez; yalnızca üretim planını sınırlar.'),
            side='right')
        opts = ttk.Frame(stores_panel)
        opts.pack(fill="x", pady=5)
        ttk.Label(opts, text="Mağaza grubu:").pack(side="left")
        self.group = tk.StringVar(value="LOCAL")
        ttk.Entry(opts, textvariable=self.group, width=14).pack(side="left", padx=5)
        self._context_help.button(
            opts,
            help_details('Çıktı SKU’larında kullanılacak güvenli mağaza/grup adını belirler.',
                         'Mağaza seçiminiz yoksa LOCAL varsayılanı kullanılabilir.',
                         'Yalnız yeni üretim kayıtlarının adlandırmasını etkiler; mağaza profili oluşturmaz.'),
            side='right')

        # Store membership lives in private local state, NOT in the historic
        # approved template directory. Empty store selection = legacy behavior.
        profile_panel = ttk.Frame(stores_panel)
        profile_panel.pack(fill="x", pady=(2, 5))
        ttk.Label(profile_panel, text="Mağazalar (Ctrl ile çoklu seç):").pack(side="left")
        self.store_list = tk.Listbox(profile_panel, selectmode="extended",height=3,
                                    width=35,exportselection=False,
                                    bg=PANEL,fg=FG,selectbackground=ACCENT)
        self.store_list.pack(side="left",padx=8)
        self.store_list.bind('<<ListboxSelect>>', self._store_changed, add='+')
        if _table_tools is not None:
            _table_tools.attach_listbox_tooltip(self.store_list)
        self.store_mapping=[]
        store_manage = ttk.Frame(stores_panel)
        store_manage.pack(fill='x', pady=(2, 3))
        ttk.Button(store_manage,text="Mağaza Yönetimi",
                   command=self.open_store_manager).pack(side="left",padx=3)
        self._context_help.button(
            store_manage,
            help_details('Mağaza profilleri ve şablon atamalarını açar.',
                         'Yeni bir mağaza veya açık bir atama değişikliği gerektiğinde kullanın.',
                         'Açık onay olmadan profil ve atama kayıtlarını değiştirmez.'),
            side='left', padx=(0, 8))
        store_manage.pack_forget()
        ttk.Button(store_manage,text="Mağaza listesini yenile",
                   command=self.reload_stores).pack(side="left",padx=3)
        self._context_help.button(
            store_manage,
            help_details('Mağaza profil dosyasını yeniden okur ve mevcut seçimi mümkün olduğunca korur.',
                         'Profil değişikliği yaptıktan sonra kullanılır.',
                         'Şablonları, maskeleri veya üretim kayıtlarını değiştirmez.'),
            side='left', padx=(0, 8))
        self.reload_stores()
        store_selection_tools = ttk.Frame(stores_panel)
        store_selection_tools.pack(fill='x', pady=(3, 2))
        ttk.Label(store_selection_tools, text='Mağaza kapsamı:').pack(side='left')
        self.select_store_button = ttk.Button(
            store_selection_tools,
            text='Mağazaya atananları üretime seç',
            command=self.select_store_assigned_templates,
            width=32)
        self.select_store_button.pack(side='left', padx=(7, 3))
        self._context_help.button(
            store_selection_tools,
            help_details('Seçili mağazaların güncel, insan onaylı şablonlarını üretim listesine alır.',
                         'Mağaza seçtikten sonra üretim kapsamını mağaza atamalarına eşitlemek için kullanılır.',
                         'Mağaza atamasını değiştirmez; yalnızca geçici üretim seçimini değiştirir.'),
            side='left', padx=(1, 0))
        self.store_filter_label=tk.StringVar(value='Mağazaya özel görünüm KAPALI. Seçimler değişmeden kalır.')
        ttk.Label(stores_panel,textvariable=self.store_filter_label,
                  foreground='#93A6C4',wraplength=1050).pack(anchor='w',pady=(2,3))
        self._context_help.button(
            stores_panel,
            help_details('Mağazaya ait onaylı şablonların otomatik filtre durumunu gösterir.',
                         'Mağaza seçtiğinizde liste ve beklenen iş sayısı güncellenir.',
                         'Salt okunurdur; atama ve SQLite kayıtlarını değiştirmez.'),
            side='right', padx=(0, 0), pady=(0, 2))

        quality_panel=ttk.LabelFrame(area,text='04  ÜRETİM AYARLARI',style='Premium.TLabelframe',padding=(15,13))
        quality_panel.pack(fill='x',pady=(7,10))
        fit_row = ttk.Frame(quality_panel)
        fit_row.pack(fill="x", pady=4)
        ttk.Label(fit_row, text="Tasarım Yerleşimi:").pack(side="left")
        self.placement = tk.StringVar(value="Tam Doldur (Sıfır Blur / Kırpılabilir)")
        ttk.Combobox(
            fit_row,
            textvariable=self.placement,
            state="readonly",
            width=32,
            values=("Tam Doldur (Sıfır Blur / Kırpılabilir)", "Tam Göster (Bant Olabilir)"),
        ).pack(side="left", padx=8)
        self._context_help.button(
            fit_row,
            help_details('Tasarımın baskı alanını doldurma veya tamamını gösterme biçimini seçer.',
                         'Üretimden önce kırpma davranışını belirlemek için kullanılır.',
                         'Yalnız yeni render tarifini etkiler; şablon ve maske kayıtlarına yazmaz.'),
            side='right')
        self.render_mode = tk.StringVar(value='Her tasarıma 1 çıktı · Şablonları dengeli tekrar kullan')
        self.render_mode_display = {
            'Her tasarıma 1 çıktı · Şablonları dengeli tekrar kullan': 'balanced_one_per_design',
            'Her tasarım × her atanmış şablon · Tüm kombinasyonlar': 'all_templates_per_design',
        }
        mode_row = ttk.Frame(quality_panel)
        mode_row.pack(fill='x', pady=(7, 3))
        ttk.Label(mode_row, text='Üretim modeli:').pack(side='left')
        mode_combo = ttk.Combobox(
            mode_row, textvariable=self.render_mode, state='readonly', width=58,
            values=tuple(self.render_mode_display),
        )
        mode_combo.pack(side='left', padx=8)
        mode_combo.bind('<<ComboboxSelected>>', lambda _event: self._refresh_selection_summary())
        self._context_help.button(
            mode_row,
            help_details(
                'Her tasarıma 1 çıktı: 295 tasarım varsa toplam 295 çıktı üretir; atanmış şablonlar dengeli sırayla tekrar kullanılır.\n\n'
                'Her tasarım × her şablon: 295 tasarım ve 36 şablon varsa 10.620 çıktı planlar.',
                'Günlük katalog üretiminde ilk seçenek önerilir. İkinci seçenek aynı tasarımın tüm şablonlarda görünmesi gerektiğinde kullanılır.',
                'Seçim üretim planına ve devam/kurtarma kimliğine kaydedilir; mevcut onaylı şablon, maske ve köşe verilerine dokunmaz.'),
            side='right')
        # The production recipe owns the effect choice.  Keep this variable as
        # an internal compatibility hook for the explicit A/B preview/tests,
        # but do not expose a second user-selectable production effect switch.
        self.lighting = tk.StringVar(value=LIGHT_LABELS[0])
        self.sunlight_profile=tk.StringVar(value=SUN_LABELS[2])

        # Normal render is always preserved. 4K is a separate opt-in job, and
        # cannot silently fall back to non-AI resizing if the binary is absent.
        upscale_row = ttk.Frame(quality_panel)
        upscale_row.pack(fill="x", pady=(5, 3))
        self.upscale_4k = tk.BooleanVar(value=False)
        self.upscale_model = tk.StringVar(value="Fotoğraf — Real-ESRGAN x4plus")
        self._4k_checker=OnDemand4K()
        self._4k_installing=False
        self._4k_state=tk.StringVar(value="4K kapalı · seçildiğinde otomatik doğrulanır")
        ttk.Checkbutton(upscale_row, text="Üretimden sonra isteğe bağlı AI 4K (2880×3840)",
                        variable=self.upscale_4k).pack(side="left")
        self.upscale_model_combo = ttk.Combobox(
            upscale_row, textvariable=self.upscale_model, state="readonly", width=33,
            values=("Fotoğraf — Real-ESRGAN x4plus", "Hızlı — Real-ESRGAN general x4v3"))
        self.upscale_model_combo.pack(side="left", padx=(12, 4))
        self._4k_check_button = ttk.Button(upscale_row,text='4K Kurulumunu Kontrol Et',
                                           command=self._verify_4k_status)
        self._4k_check_button.pack(side='left',padx=7)
        ttk.Label(upscale_row,textvariable=self._4k_state,wraplength=285).pack(side="left",padx=(8,0))
        self._context_help.button(
            upscale_row,
            help_details('İsteğe bağlı AI 4K üretimini açar; seçildiğinde motor ve model doğrulanır.',
                         'Yalnız 4K çıktı istediğinizde kullanılır; normal üretim varsayılan olarak korunur.',
                         '4K ayrı çıktı ve SHA makbuzu üretir; mevcut normal çıktıyı değiştirmez.'),
            side='right')
        self.upscale_model_combo.pack_forget()
        self._4k_check_button.pack_forget()
        self.upscale_4k.trace_add('write', lambda *_: self.window.after(10,self._on_4k_selected))
        self.upscale_model.trace_add('write',lambda *_: self.window.after(10,self._on_4k_selected))

        # PETEK specialist controls are created in Gelişmiş Render/PETEK.
        self.petek_slot_mode=tk.StringVar(value='orta')
        self.petek_nature_profile=tk.StringVar(value='Belirgin')
        self.petek_pink_cleanup=tk.BooleanVar(value=True)
        self.petek_overlay_enabled = tk.BooleanVar(value=False)
        self._petek_preview_ok = None
        self.petek_slot_mode.trace_add('write',lambda *_:setattr(self,'_petek_preview_ok',None))
        self.petek_pink_cleanup.trace_add('write',lambda *_:setattr(self,'_petek_preview_ok',None))
        self.auto_cloud_link = tk.BooleanVar(value=False)
        overlay_row = ttk.Frame(quality_panel)
        overlay_row.pack(fill='x', pady=(5, 2))
        ttk.Checkbutton(overlay_row, text='PETEK için 4 Ölçü Overlay Aktif (76 / 96 / 116 / 136 cm)',
                        variable=self.petek_overlay_enabled).pack(side='left')
        ttk.Button(overlay_row, text='Hazır katman ön kontrolü',
                   command=self.preflight_petek_overlay).pack(side='left', padx=(8, 0))
        self.ready_overlay_button = ttk.Button(
            overlay_row, text='Hazır Görsel Yükle Overlay Uygula',
            command=self.apply_overlay_to_ready_folder)
        self.ready_overlay_button.pack(side='left', padx=(8, 0))
        self._context_help.button(
            overlay_row,
            help_details('Yalnız 06_Petek_Kapama için temiz kaynaktan dört bağımsız varyasyon üretir.',
                         'Kullanıcı PNG katmanlarını Overlay_Giydirme klasör sözleşmesine göre kontrol eder.',
                         'Temiz kaynak korunur; katman havuzu eksik veya hatalıysa eski temiz PETEK otomatik linklenmez.'),
            side='right')
        self.four_panel = FourMockupPanel(self, quality_panel)
        self.petek_overlay_enabled.trace_add('write', lambda *_: self.four_panel.overlay_mode_changed())
        ttk.Checkbutton(
            quality_panel,
            text="Üretimden sonra isteğe bağlı HTTPS Linke Çevir + Excel'e Yaz",
            variable=self.auto_cloud_link,
        ).pack(anchor="w", pady=(4, 2))
        self._context_help.button(
            quality_panel,
            help_details('Üretim sonrasında doğrulanmış çıktıları HTTPS linke dönüştürüp Excel’e yazmayı teklif eder.',
                         'Yalnız üretim tamamlandıktan sonra link/Excel gerekiyorsa açılır.',
                         'Açık kullanıcı onayı olmadan yükleme yapmaz; mevcut görselleri yeniden üretmez.'),
            side='right', padx=(0, 0), pady=(0, 4))
        self._auto_cloud_pending = False
        self._auto_cloud_keys = []
        self._restore_ui_preferences()

        actions_panel=ttk.LabelFrame(area,text='04  ÜRETİM KUYRUĞU VE SONUÇLAR  ·  Başlat / Durdur / Rapor',style='Premium.TLabelframe',padding=(15,13))
        actions_panel.pack(fill='x',pady=(7,10))
        actions = ttk.Frame(actions_panel)
        actions.pack(fill="x", pady=8)
        production_actions = (
            ("⏸ Duraklat", self.pause_batch, None),
            ("▶ Devam Et / Güvenli Durdurmadan Sürdür", self.resume_batch, None),
            ("■ Güvenli Durdur", self.stop, None),
            ("Ortak Çıktı Klasörü", self.open_results, None),
            ("SHA Kayıtlarını Doğrula (Salt Okunur)", self.run_audit, None),
            ("Operasyon Özeti", self.show_operations, None),
        )
        for column in range(4):
            actions.columnconfigure(column, weight=1)
        for index, (label, command, style) in enumerate(production_actions):
            kwargs = {'text': label, 'command': command}
            if style:
                kwargs['style'] = style
            button = ttk.Button(actions, **kwargs)
            button.grid(row=index // 4, column=index % 4, sticky='ew', padx=3, pady=3)

        remote = ttk.Frame(actions_panel)
        remote.pack(fill="x", pady=5)
        self.cloud_provider = tk.StringVar(value='imgbb')
        self.imagekit_key_var = tk.StringVar()
        ttk.Label(remote, text='Sağlayıcı:').pack(side='left', padx=(3, 2))
        ttk.Combobox(remote, textvariable=self.cloud_provider, values=('imgbb', 'imagekit'),
                     state='readonly', width=10).pack(side='left', padx=2)
        ttk.Label(remote, text='ImageKit Private Key:').pack(side='left', padx=(8, 2))
        ttk.Entry(remote, textvariable=self.imagekit_key_var, show='•', width=24).pack(side='left', padx=2)
        self._load_cloud_local_settings()
        self.cloud_button = ttk.Button(remote, text="☁ Mevcut Çıktıları HTTPS Linke Çevir + Excel'e Yaz",
                                       command=self.start_cloud_links)
        self.cloud_button.pack(side="left", padx=3)
        ttk.Button(remote, text="Mağaza Bazlı Trendyol Excel Oluştur", command=self.export_marketplace_template).pack(side="left", padx=5)
        ttk.Button(remote, text="Trendyol çıktı klasörü", command=self.open_trendyol_output_folder).pack(side="left", padx=5)
        ttk.Button(remote, text="Son Trendyol Excel’i aç", command=self.open_last_trendyol_output).pack(side="left", padx=5)
        ttk.Label(remote, text="Ayrı onay ister; seçilen sağlayıcıya internetten erişilebilen görseller yükler. Pazaryerine ilan yüklemez.",
                  wraplength=570).pack(side="left", padx=7)
        ttk.Label(actions_panel, text=(
            "YENİLE: onaylı şablon listesini yeniden okur | TÜMÜNÜ SEÇ: listedeki hepsini seçer (başlatmaz). "
            "MAĞAZA GRUBU: SKU ayırır; otomatik mağazaya yüklemez.\n"
            "DURAKLAT: aktif dosya tamamlandıktan sonra yeni işe geçmez; DEVAM: aynı kuyruktan sürdürür. "
            "GÜVENLİ DURDUR: biten görselleri koruyarak sonraki işleri durdurur. "
            "YARIM İŞ/KİLİT KURTARMA: bozuk ara kayıtları gösterir; açık onayla karantinaya alır. "
            "SHA DENETLE: çıktı dosyası ile kayıt hash'lerini sadece okur. "
            "PAZARYERİ EXCEL ŞABLONU: yalnız HTTPS linki hazır satırları senin boş XLSX başlıklarına eşler; "
            "asıl şablonu korur, barkod ve SEO uydurmaz."
        ), wraplength=1120).pack(anchor="w", pady=(3, 5))
        # The legacy action panel is retained as a compatibility container for
        # its callbacks, but daily controls live in the fixed footer and the
        # verbose explanatory block is no longer shown in the work area.
        actions_panel.pack_forget()
        self._editable_sections={'templates':templates_panel,'designs':designs_panel,
                                 'stores':stores_panel,'quality':quality_panel}
        self._progress_widget=ttk.Label(area,textvariable=self.progress,wraplength=800)
        self._progress_widget.pack(anchor="w",pady=4)

        footer_controls = ttk.Frame(footer)
        footer_controls.grid(row=3, column=0, columnspan=3, sticky='ew', pady=(8, 0))
        for column in range(9):
            footer_controls.columnconfigure(column, weight=1)

        def footer_action(index, label, command, details):
            holder = ttk.Frame(footer_controls)
            holder.grid(row=0, column=index, sticky='ew', padx=3)
            button = ttk.Button(holder, text=label, command=command)
            button.pack(side='left', fill='x', expand=True)
            self._context_help.button(holder, details, side='left', padx=(4, 0))
            return button

        self.pause_button = footer_action(
            0, '⏸ Duraklat', self.pause_batch,
            help_details('Aktif görsel tamamlandıktan sonra kuyruğu güvenli biçimde bekletir.',
                         'Geçici olarak ara vermek istediğinizde kullanılır.',
                         'Tamamlanmış çıktılara dokunmaz; ledger kaydı korunur.'))
        self.resume_button = footer_action(
            1, '▶ En Son Kaldığım Yerden Devam Et', self.resume_batch,
            help_details('Duraklatılmış veya güvenli durdurulmuş üretimi aynı kayıt ve tarifle sürdürür.',
                         'Kuyruk beklemedeyken veya önceki tur STOPPED durumundaysa kullanılır.',
                         'Önceden doğrulanmış çıktıları SHA ile atlar; yeni kayıtları koruyarak devam eder.'))
        self.retry_button = footer_action(
            2, '↻ Başarısızları Yeniden Dene', self.retry_failed,
            help_details('Son hata raporundaki onaylı şablonları yeniden kuyruğa alır; doğrulanmış çıktılar motor tarafından atlanır.',
                         'Üretim PARTIAL veya hata raporu oluşturduğunda kullanılır.',
                         'Mevcut çıktıları silmez; yeni denemeleri mevcut üretim ledger’ına ekler.'))
        self.stop_button = footer_action(
            3, '■ Güvenli Durdur', self.stop,
            help_details('Aktif görsel tamamlandıktan sonra yeni işlerin başlamasını durdurur.',
                         'Kuyruğu kaybetmeden ara vermek istediğinizde kullanılır.',
                         'Tamamlanan dosya ve kayıtları korur; checkpoint üretir.'))
        self.results_button = footer_action(
            4, 'Sonuçları Aç', self.open_results,
            help_details('Doğrulanmış üretim çıktılarının klasörünü açar.',
                         'Üretimden sonra dosyaları incelemek istediğinizde kullanılır.',
                         'Salt görüntüleme/açma işlemidir; dosya silmez veya yeniden üretmez.'))
        self.report_button = footer_action(
            5, 'İşlem Özeti', self.show_operations,
            help_details('Yalnız mevcut üretimin kısa sonucunu gösterir.',
                         'İşlem kimliği, dört sayaç ve bu turdaki dosya konumlarını gerektiğinde açar.',
                         'Geçmiş Excel ve teknik günlük bu kısa özetle karıştırılmaz.'))
        self.error_report_button = footer_action(6, 'Hata Raporunu Aç', self.open_error_report,
            help_details('Son üretimdeki gerçek teknik hata raporunu açar.', 'Traceback, dosya yolu ve sayaçları gösterir.', 'Salt okunurdur.'))
        self.codex_report_button = footer_action(7, "Codex'e Hazır Raporu Kopyala", self.copy_codex_report,
            help_details('Teknik kanıtları Codex’e aktarılabilecek biçimde panoya kopyalar.', 'Düzeltme raporu hazırlarken kullanılır.', 'Salt okunurdur.'))
        self.error_folder_button = footer_action(8, 'Hata Klasörünü Aç', self.open_error_folder,
            help_details('Hata raporlarının klasörünü açar.', 'Rapor dosyalarını Windows Gezgini’nde inceleyin.', 'Salt okunurdur.'))
        self._build_production_tabs()
        self.log = scrolledtext.ScrolledText(area, height=13, state="disabled", font=("Consolas", 9), bg=PANEL, fg=FG, insertbackground=FG)
        # Verbose engine diagnostics belong to the per-operation journal. Keep
        # the daily screen focused on the short result card; the journal path
        # is provided by İşlem Özeti when technical detail is needed.
        self.log.pack_forget()

        self.messages: queue.Queue = queue.Queue()
        self.worker: threading.Thread | None = None
        self._load_seq=0
        self.reload()
        bind_help(self.window)
        self.window.after(200, self.poll)
        if not self.embedded:
            self.window.protocol("WM_DELETE_WINDOW", self.safe_close)

    def _build_production_tabs(self, _prefs=None):
        """Always keep Tümü, so hiding a filter tab never hides core commands."""
        prefs=_prefs or load_visual_layout()['production']
        self._production_tabs=prefs['tabs']
        # The daily screen is one direct four-section workspace. The old
        # reorder tabs remain represented in the preferences for compatibility
        # and are available from the advanced layout editor only.
        self._prod_tabbar.pack_forget()
        self._apply_production_tab('Tümü')
        return
        for child in self._prod_tabbar.winfo_children():child.destroy()
        accent=prefs.get('accent','#17D3A3')
        tk.Label(self._prod_tabbar,text='Çalışma Panelleri:',bg=BG,fg=FG,
                 font=('Segoe UI',11,'bold')).pack(side='left',padx=(2,10))
        for name in prefs['tabs']:
            tk.Button(self._prod_tabbar,text=name,command=lambda n=name:self._apply_production_tab(n),
                      bg='#182238',fg=FG,activebackground=accent,activeforeground='#ffffff',
                      relief='flat',padx=13,pady=8).pack(side='left',padx=3)
        ttk.Button(self._prod_tabbar,text='✥ Arayüzü Düzenle',
                   command=lambda:LayoutEditor(self.window,'production',
                     on_save=self._build_production_tabs)).pack(side='right',padx=5)
        self._apply_production_tab('Tümü')

    def _restore_ui_preferences(self):
        """Restore only user-local, last-valid UI choices (never production data)."""
        self._restoring_preferences = True
        try:
            raw = json.loads(self._ui_state_path.read_text(encoding='utf-8'))
            if not isinstance(raw, dict):
                self._restoring_preferences = False
                return
        except (OSError, ValueError, TypeError):
            self._restoring_preferences = False
            return
        for name in ('design_folder', 'group', 'placement',
                     'sunlight_profile', 'upscale_model', 'petek_slot_mode', 'render_mode',
                     'petek_nature_profile'):
            value = raw.get(name)
            if name == 'render_mode' and value in ('balanced_one_per_design', 'all_templates_per_design'):
                value = next((label for label, code in self.render_mode_display.items()
                              if code == value), value)
            variable = getattr(self, name, None)
            if variable is not None and isinstance(value, str) and value:
                try:
                    variable.set(value)
                except tk.TclError:
                    pass
        for name in ('upscale_4k', 'petek_pink_cleanup', 'petek_overlay_enabled', 'auto_cloud_link'):
            if name in raw and hasattr(self, name):
                try:
                    getattr(self, name).set(bool(raw[name]))
                except tk.TclError:
                    pass
        wanted = set(raw.get('stores', [])) if isinstance(raw.get('stores'), list) else set()
        for index, store in enumerate(getattr(self, 'store_mapping', [])):
            if store in wanted:
                self.store_list.selection_set(index)
        if wanted:
            self._store_changed()
        self._restoring_preferences = False

    def _save_ui_preferences(self):
        """Atomically persist successful settings outside the production root."""
        payload = {}
        for name in ('design_folder', 'group', 'placement',
                     'sunlight_profile', 'upscale_model', 'petek_slot_mode', 'render_mode',
                     'petek_nature_profile'):
            variable = getattr(self, name, None)
            if variable is not None:
                payload[name] = variable.get()
        for name in ('upscale_4k', 'petek_pink_cleanup', 'petek_overlay_enabled', 'auto_cloud_link'):
            if hasattr(self, name):
                payload[name] = bool(getattr(self, name).get())
        payload['stores'] = list(self._chosen_stores())
        destination = getattr(self, '_ui_state_path', user_state_path().parent / 'production_ui_preferences.json')
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            fd, temporary = tempfile.mkstemp(prefix='.production-ui-', suffix='.tmp',
                                             dir=str(destination.parent))
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as handle:
                    json.dump(payload, handle, ensure_ascii=False, indent=2)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, destination)
            finally:
                Path(temporary).unlink(missing_ok=True)
        except (OSError, TypeError, ValueError):
            # Preferences are optional; production never depends on this file.
            return

    def _apply_production_tab(self, name):
        order=self._production_tabs.get(name) or list(self._editable_sections)
        for panel in self._editable_sections.values():panel.pack_forget()
        for key in order:
            if key in self._editable_sections:
                self._editable_sections[key].pack(fill='x',pady=(7,10),before=self._progress_widget)
        self.main_canvas.yview_moveto(0)

    def open_advanced_tools(self):
        """Expose existing secondary actions without crowding daily production."""
        popup = tk.Toplevel(self.window)
        popup.title('Gelişmiş Araçlar · Üretim Merkezi')
        popup.geometry('980x650')
        popup.minsize(760, 520)
        popup.transient(self.window)
        area = ttk.Frame(popup, padding=14)
        area.pack(fill='both', expand=True)
        ttk.Label(area, text='Gelişmiş Araçlar', font=('Segoe UI', 16, 'bold')).pack(anchor='w')
        ttk.Label(area, text='Günlük üretim ekranını sade tutmak için test, bakım, mağaza ve rapor işlemleri burada.',
                  wraplength=880).pack(anchor='w', pady=(2, 12))

        def section(title):
            box = ttk.LabelFrame(area, text=title, padding=(10, 8))
            box.pack(fill='x', pady=(0, 10))
            return box

        def action(parent, label, command, details, column, row, columns=2):
            holder = ttk.Frame(parent)
            holder.grid(row=row, column=column, sticky='ew', padx=3, pady=3)
            button = ttk.Button(holder, text=label, command=command)
            button.pack(side='left', fill='x', expand=True)
            self._context_help.button(holder, details, side='left', padx=(4, 0))
            return button

        for title, entries in (
            ('Şablon / Önizleme Araçları', (
                ('Onaylı şablonları yenile', self.reload,
                 help_details('Onaylı şablon listesini yeniden okur.', 'Yeni onaylar geldikten sonra kullanılır.', 'Salt okunurdur; üretim kayıtlarını değiştirmez.')),
                ('Seçili filtreyi seç', self.select_filtered,
                 help_details('Şu an görünür onaylı şablonları seçime ekler.', 'Belirli bir kategori veya arama filtresini üretime dahil etmekte kullanılır.', 'Yalnız geçici UI seçimini değiştirir.')),
                ('Seçimi temizle', self.clear_selection,
                 help_details('Mevcut şablon seçimini temizler.', 'Yeni bir üretim kapsamı oluştururken kullanılır.', 'Onaylı kayıtları veya dosyaları silmez.')),
                ('Günışığı / Efekt A-B', self.start_ab_preview,
                 help_details('Gerçek baskı render’ı ile efekt kapalı/açık önizlemesi üretir.', 'Görünüm kararını üretimden önce doğrulamak için kullanılır.', 'Önizleme ve geçici çalışma dosyası üretir; onaylı DB’yi değiştirmez.')),
                ('PETEK Izgara / Pembe A-B', self.start_petek_ab_preview,
                 help_details('PETEK için mevcut ve deneme görünümünü karşılaştırır.', 'PETEK görsel QA incelemesi gerektiğinde kullanılır.', 'Onaylı maskeyi veya kaynak fotoğrafını değiştirmez.')),
            )),
            ('Mağaza Yönetimi', (
                ('Mağaza profilleri / atama', self.open_store_manager,
                 help_details('Mağaza profili ve onaylı şablon atama ekranını açar.', 'Yeni atama gerektiğinde kullanılır.', 'Açık kullanıcı onayı olmadan kayıt değiştirmez.')),
                ('Mağazaları yenile', self.reload_stores,
                 help_details('Mağaza profil dosyasını yeniden okur.', 'Profil yöneticisinden döndükten sonra kullanılır.', 'Salt okunurdur; seçimi mümkün olduğunca korur.')),
                ('Mağaza – üretim eşleşmesi', self.diagnose_store_selection,
                 help_details('Seçili mağaza ile şablon üyeliğini salt okunur denetler.', 'Başlatma ön kontrolünde uyuşmazlık varsa kullanılır.', 'Mağaza ve üretim kayıtlarını değiştirmez.')),
                ('Bu mağazanın mockuplarını göster', self.show_store_templates,
                 help_details('Listeyi seçili mağazanın güncel atamalarına filtreler.', 'Mağazaya özel üretim kapsamını incelemek için kullanılır.', 'Şablon seçimini kendiliğinden değiştirmez.')),
                ('Tüm mockupları göster', self.show_all_templates,
                 help_details('Mağaza filtresini kapatıp tüm onaylı şablonları gösterir.', 'Kapsamı tekrar genişletmek gerektiğinde kullanılır.', 'Salt görünüm filtresidir.')),
            )),
            ('Bakım / Kurtarma / 4K', (
                ('Yarım iş / kilit kurtarma', self.open_recovery,
                 help_details('PENDING, bayat kilit ve kesinti durumunu denetler.', 'Kesinti veya yarım iş uyarısı olduğunda kullanılır.', 'Yalnız açık onayla karantina işlemi yapabilir; doğrulanmış çıktıları korur.')),
                ('4K modelini seç', self._choose_4k_model,
                 help_details('4K model seçimini değiştirir.', '4K kutusu açıkken model tercihi gerektiğinde kullanılır.', 'Yalnız sonraki 4K üretim tarifini etkiler.')),
                ('4K kurulumunu denetle', self._verify_4k_status,
                 help_details('Seçili Real-ESRGAN modelinin kurulumunu doğrular.', '4K üretiminden önce veya sorun giderirken kullanılır.', 'Salt okunur doğrulama; normal üretimi değiştirmez.')),
                ('Arayüz düzenleyici', lambda: LayoutEditor(self.window, 'production', on_save=self._build_production_tabs),
                 help_details('Görsel panel tercihlerini düzenler.', 'Gelişmiş yerleşim tercihi gerektiğinde kullanılır.', 'Yalnız kullanıcı arayüzü tercih dosyasını günceller.')),
            )),
            ('Sonuçlar / Dışa Aktarım', (
                ('SHA kayıtlarını doğrula', self.run_audit,
                 help_details('Üretim kayıtları ile çıktı SHA değerlerini denetler.', 'Üretim sonrasında kalite kontrol için kullanılır.', 'Salt okunurdur; çıktı ve ledger silmez.')),
                ('Operasyon özeti', self.show_operations,
                 help_details('Ledger durumlarını ve kategori özetini gösterir.', 'Sonuçları topluca incelemek için kullanılır.', 'Salt okunurdur.')),
                ('HTTPS link + Excel', self.start_cloud_links,
                 help_details('Doğrulanmış mevcut çıktılar için açık onayla link ve Excel işlemini başlatır.', 'Üretim tamamlandıktan sonra dış paylaşım gerektiğinde kullanılır.', 'Açık onay ister; görselleri yeniden üretmez.')),
                ('Mağaza bazlı Trendyol Excel', self.export_marketplace_template,
                 help_details('Mevcut boş yükleme şablonuna doğrulanmış linkleri mağazaya göre yazar.', 'Pazaryeri Excel’i hazırlanırken kullanılır.', 'Seçtiğiniz boş Excel’i koruyarak yeni çıktı oluşturur.')),
            )),
        ):
            box = section(title)
            columns = 2
            box.columnconfigure(0, weight=1)
            box.columnconfigure(1, weight=1)
            for index, (label, command, details) in enumerate(entries):
                action(box, label, command, details, index % columns, index // columns)

        render_box = section('İleri Render / PETEK Ayarları')
        render_box.columnconfigure(1, weight=1)
        render_box.columnconfigure(2, weight=0)

        ttk.Label(render_box, text='Güneş / gerçekçilik profili').grid(
            row=0, column=0, sticky='w', padx=3, pady=3)
        sun_combo = ttk.Combobox(render_box, textvariable=self.sunlight_profile,
                                 values=SUN_LABELS, state='readonly', width=37)
        sun_combo.grid(row=0, column=1, sticky='ew', padx=3, pady=3)
        render_help_1 = ttk.Frame(render_box)
        render_help_1.grid(row=0, column=2, sticky='e', padx=(4, 0))
        self._context_help.button(
            render_help_1,
            help_details('Yedi kategori ortak güneş ve gerçekçilik profilini değiştirir.',
                         'Gölge/ışık görünümünü özel olarak ayarlamak istediğinizde kullanılır.',
                         'Yalnız yeni render tarifini etkiler; onaylı geometri ve maskeleri değiştirmez.'),
            side='left', padx=(0, 0))

        ttk.Label(render_box, text='PETEK gerçek yarık gölgesi').grid(
            row=1, column=0, sticky='w', padx=3, pady=3)
        ttk.Combobox(render_box, textvariable=self.petek_slot_mode,
                     values=('off', 'hafif', 'orta', 'guclu'), state='readonly', width=12).grid(
                         row=1, column=1, sticky='w', padx=3, pady=3)

        ttk.Label(render_box, text='PETEK doğallık profili').grid(
            row=2, column=0, sticky='w', padx=3, pady=3)
        ttk.Combobox(render_box, textvariable=self.petek_nature_profile,
                     values=('Doğal', 'Belirgin'), state='readonly', width=12).grid(
                         row=2, column=1, sticky='w', padx=3, pady=3)

        pink = ttk.Checkbutton(render_box, text='PETEK pembe temizlik',
                               variable=self.petek_pink_cleanup)
        pink.grid(row=3, column=0, columnspan=2, sticky='w', padx=3, pady=3)
        render_help_2 = ttk.Frame(render_box)
        render_help_2.grid(row=3, column=2, sticky='e', padx=(4, 0))
        self._context_help.button(
            render_help_2,
            help_details('PETEK yarık, kenar ve köşe çevresindeki yetkili pembe temizliği yönetir.',
                         'PETEK QA veya gerçekçilik incelemesi gerektiğinde kullanılır.',
                         'Onaylı maskeye ve kaynak fotoğrafına yazmaz; yeni çıktının temizliğini etkiler.'),
            side='left', padx=(0, 0))

        ttk.Button(area, text='Kapat', command=popup.destroy).pack(anchor='e')
        popup.bind('<Escape>', lambda _event: popup.destroy())
        popup.protocol('WM_DELETE_WINDOW', popup.destroy)

    def _choose_4k_model(self):
        popup = tk.Toplevel(self.window)
        popup.title('4K Modeli')
        popup.transient(self.window)
        frame = ttk.Frame(popup, padding=14)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='4K modelini seçin', font=('Segoe UI', 12, 'bold')).pack(anchor='w')
        combo = ttk.Combobox(frame, textvariable=self.upscale_model, state='readonly', width=35,
                             values=('Fotoğraf — Real-ESRGAN x4plus', 'Hızlı — Real-ESRGAN general x4v3'))
        combo.pack(fill='x', pady=10)
        self._context_help.button(
            frame,
            help_details('4K model tercihini günceller.', '4K üretimi öncesinde seçilir.', 'Yalnız sonraki 4K işini etkiler.'),
            side='left')
        ttk.Button(frame, text='Kapat', command=popup.destroy).pack(anchor='e')
        popup.bind('<Escape>', lambda _event: popup.destroy())

    def _chosen_stores(self):
        return [self.store_mapping[int(i)] for i in self.store_list.curselection()
                if int(i) < len(self.store_mapping)]

    def _store_changed(self, _event=None):
        # A selected store is an explicit scope choice: show its approved
        # templates immediately while retaining non-visible UIDs in memory so
        # no previous selection is silently destroyed.
        self.store_only_view = bool(self._chosen_stores())
        self.apply_filters()
        self._refresh_selection_summary()

    def reload_stores(self):
        """Re-read the same store_profiles path as UnifiedV4Batch.run()."""
        try:
            mgr=StoreProfiles(self.batch_engine.root)
            cfg=mgr.load()  # re-read disk; never a cached profile copy
            keep=set(self._chosen_stores()) if hasattr(self,'store_mapping') else set()
            self.store_list.delete(0,'end')
            self.store_mapping=list(sorted(cfg['stores']))
            for i,name in enumerate(self.store_mapping):
                count=len(cfg['stores'][name]['templates'])
                self.store_list.insert('end',f'{name} ({count} şablon)')
                if name in keep:self.store_list.selection_set(i)
            if self.store_only_view:
                self.apply_filters()
            else:
                self._update_store_filter_info()
        except Exception as exc:
            helpful_error('Mağaza profilleri okunamadı',str(exc),parent=self.window)

    def _store_assignment_keys(self):
        """On-disk, current store membership keys. Never mutate selection."""
        names=self._chosen_stores()
        if not names:
            return set()
        config=StoreProfiles(self.batch_engine.root).load()
        return {key for name in names
                for key in config.get('stores', {}).get(name, {}).get('templates', [])}

    def _update_store_filter_info(self):
        if not hasattr(self,'store_filter_label'):
            return
        try:
            names=self._chosen_stores()
            if not names:
                msg='Mağaza seçilmedi. Üretim için seçim değişmedi.'
            else:
                keys=self._store_assignment_keys()
                valid={str(item['uid']) for item in self.all_templates if key_for(item) in keys}
                unrelated=len(set(self.selected_uids)-valid)
                msg=(f'Mağaza: {", ".join(names)} | güncel atanmış mockup: {len(valid)} | '
                     f'üretimde seçilmiş ama mağazaya ait olmayan: {unrelated}. '
                     'Seçimler kendiliğinden değiştirilmez.')
                if unrelated or not self.selected_uids:
                    msg += ' Üretim kapsamını eşitlemek için “Mağazaya atananları üretime seç” düğmesini kullanın.'
            if self.store_only_view:
                msg='MAĞAZA FİLTRESİ AÇIK · '+msg
            self.store_filter_label.set(msg)
        except (OSError,ValueError,KeyError) as exc:
            self.store_filter_label.set('MAĞAZA PROFİLİ OKUNAMADI: '+str(exc))

    def show_store_templates(self):
        """Explicit list FILTER ONLY; never silently select/unselect any UID."""
        if not self._chosen_stores():
            messagebox.showwarning('Mağaza seçin',
                'Önce Mağazalar alanından bir mağaza seçin.',parent=self.window)
            return
        self._capture_visible()
        self.store_only_view=True
        self.apply_filters(capture=False)

    def show_all_templates(self):
        self._capture_visible()
        self.store_only_view=False
        self.apply_filters(capture=False)

    def _store_selection_snapshot(self, *, selected=None, stores=None):
        """Same UID+store arguments as start() -> StoreProfiles.plan()."""
        names=list(self._chosen_stores() if stores is None else stores)
        manager=StoreProfiles(self.batch_engine.root)
        config=manager.load()
        chosen=list(self.chosen_uids() if selected is None else selected)
        report=compare_store_selection(names,chosen,list(self.all_templates),config)
        return report,read_profile_identity(manager)

    def _store_report_text(self, report, identity):
        visible=[self.mapping[int(i)] for i in self.listbox.curselection()
                 if int(i)<len(self.mapping)]
        return format_store_diagnostic(
            report,profile_identity=identity,
            visible_selected_uids=visible,
            internal_selected_uids=sorted(self.selected_uids))

    def _show_store_diagnostic(self, report, identity, *, reason=None):
        content=self._store_report_text(report,identity)
        if reason:
            content='ÜRETİM ÖN KONTROLÜ: '+str(reason)+'\n\n'+content
        pop=tk.Toplevel(self.window)
        pop.title('Mağaza / Üretim Kimlik Karşılaştırması — Salt Okunur')
        pop.geometry('940x650')
        area=ttk.Frame(pop,padding=12)
        area.pack(fill='both',expand=True)
        view=scrolledtext.ScrolledText(area,wrap='word',font=('Consolas',10),height=24)
        view.pack(fill='both',expand=True)
        view.insert('1.0',content)
        view.configure(state='disabled')
        footer=ttk.Frame(area)
        footer.pack(fill='x',pady=(8,0))
        def copy_report():
            pop.clipboard_clear();pop.clipboard_append(content)
        ttk.Button(footer,text='Raporu Kopyala',command=copy_report).pack(side='left')
        ttk.Button(footer,text='Bu Mağazanın Mockuplarını Göster',
                   command=lambda:(pop.destroy(),self.show_store_templates())).pack(side='left',padx=6)
        ttk.Button(footer,text='Kapat',command=pop.destroy).pack(side='right')
        return pop

    def diagnose_store_selection(self):
        try:
            report,identity=self._store_selection_snapshot()
            self._show_store_diagnostic(report,identity)
        except (OSError,ValueError,KeyError) as exc:
            helpful_error('Mağaza eşleşmesi teşhis edilemedi',str(exc),parent=self.window)

    def select_store_assigned_templates(self):
        """Only an EXPLICIT click may replace old production selection."""
        try:
            report,identity=self._store_selection_snapshot()
            if not report['requested']:
                raise ValueError('Önce Mağazalar listesinden bir mağaza seçin.')
            invalid=[item for item in report['details'] if item['status'] in
                     ('STORE_NOT_FOUND','NO_ASSIGNMENT','STALE_APPROVAL_OR_SHA')]
            if report['duplicate_keys'] or report['duplicate_uids'] or invalid:
                self._show_store_diagnostic(report,identity)
                return
            if not report['union_uids']:
                raise ValueError('Atanmış ve güncel onaylı şablon bulunamadı.')
            previous=len(self.chosen_uids())
            self.category_filter.set('Tümü')
            self.search_filter.set('')
            # Filter traces may recapture the OLD list; replace afterwards.
            self.selected_uids=set(report['union_uids'])
            self.apply_filters(capture=False)
            messagebox.showinfo('Mağaza şablonları seçildi',
                f'{previous} eski üretim seçimi yerine açık komutunuzla '
                f'{len(self.selected_uids)} atanmış onaylı şablon seçildi.\n'
                'Mağaza profilinde ve üretim verilerinde değişiklik yapılmadı.',
                parent=self.window)
        except (OSError,ValueError,KeyError) as exc:
            messagebox.showwarning('Mağaza seçimi eşleştirilemedi',str(exc),parent=self.window)

    def open_store_manager(self):
        """Existing navigation stays independent of production selection."""
        return self._open_store_manager_context()

    def _open_store_manager_context(self, *, prefill_store=None,
                                    prefill_category=None, prefill_uid=None):
        """Open target safely; user must confirm a new store membership."""
        from .store_assignment_ui_v410 import StoreAssignmentWindow
        return StoreAssignmentWindow(self.window,
                                     state_root=self.batch_engine.root,
                                     get_approved=lambda: list(self.all_templates),
                                     on_change=self.reload_stores,
                                     prefill_store=prefill_store,
                                     prefill_category=prefill_category,
                                     prefill_uid=prefill_uid)

    def _store_preflight_error(self, reason, report, identity):
        """Actionable UX, no auto-reassignment and no loss of selected UID."""
        details=[]
        for row in report['selected_details']:
            if not row['selected_store_member']:
                details.append(f"{row['filename']} | {row['category']} | UID: {row['uid']} | "
                               f"Sahibi: {row['owner'] or '(atanmamış)'}")
        text=('SEÇİLİ MAĞAZA: '+(', '.join(report['requested']) or '(yok)')+'\n'
              f'Mağazaya ait güncel atama: {len(report["union_uids"])}\n'
              'Uyuşmayan üretim seçimi: '+str(len(report['outside_uids']))+'\n'
              'NEDEN: '+str(reason)+'\n\n'
              +('\n'.join(details[:12]) if details else 'Mağaza grubundaki geçerli UID seçimi kontrol edilmeli.'))
        dialog=tk.Toplevel(self.window)
        dialog.title('Mağaza İzolasyonu — eşleşme düzeltilmeli')
        dialog.geometry('770x510')
        dialog.minsize(600,410)
        pane=ttk.Frame(dialog,padding=15)
        pane.pack(fill='both',expand=True)
        ttk.Label(pane,text='Üretim güvenli biçimde engellendi',
                  font=('Segoe UI',15,'bold')).pack(anchor='w',pady=(0,7))
        text_area=scrolledtext.ScrolledText(pane,wrap='word',height=14,font=('Segoe UI',10))
        text_area.pack(fill='both',expand=True)
        text_area.insert('1.0',text)
        text_area.configure(state='disabled')
        buttons=ttk.Frame(pane)
        buttons.pack(fill='x',pady=(10,0))
        def do(action):
            dialog.destroy()
            action()
        ttk.Button(buttons,text='Mağazaya Atananları Üretime Seç',
                   command=lambda:do(self.select_store_assigned_templates)).pack(side='left',padx=(0,6))
        ttk.Button(buttons,text='Bu Mağazanın Mockuplarını Göster',
                   command=lambda:do(self.show_store_templates)).pack(side='left',padx=(0,6))
        ttk.Button(buttons,text='Detaylı Salt Okunur Rapor',
                   command=lambda:do(lambda:self._show_store_diagnostic(report,identity,reason=reason))).pack(side='left',padx=(0,6))
        # Only an unowned, approved template in a SINGLE active store may be
        # proposed for a manual assignment. The user must still confirm it.
        proposed=[item for item in report['selected_details']
                  if not item['selected_store_member'] and not item['owner'] and item['source_sha']]
        if len(report['requested'])==1 and len(proposed)==1 and not report['duplicate_uids']:
            item=proposed[0]
            store=report['requested'][0]
            ttk.Button(buttons,text='Bu Mockupı Mağazaya Ata…',
                       command=lambda:do(lambda:self._open_store_manager_context(
                           prefill_store=store,prefill_category=item['category'],
                           prefill_uid=item['uid']))).pack(side='left',padx=(0,6))
        ttk.Button(buttons,text='Kapat',command=dialog.destroy).pack(side='right')
        return dialog

    def _log(self, text: str) -> None:
        self.messages.put(("log", str(text)))

    def _production_progress(self, snapshot: dict) -> None:
        """Queue a structured progress snapshot for the Tk main thread."""
        self.messages.put(('overlay_progress' if snapshot.get('phase') == 'overlay' else 'production_progress', dict(snapshot)))

    @staticmethod
    def _format_duration(seconds) -> str:
        if seconds is None:
            return '—'
        seconds = max(0, int(round(float(seconds))))
        minutes, secs = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f'{hours} sa {minutes:02d} dk'
        if minutes:
            return f'{minutes} dk {secs:02d} sn'
        return f'{secs} sn'

    def _apply_production_progress(self, snapshot: dict) -> None:
        total = max(0, int(snapshot.get('total') or 0))
        completed = min(total, max(0, int(snapshot.get('completed') or 0)))
        percent = (completed / total * 100.0) if total else 0.0
        # Embedded/lightweight hosts may not create the optional live card;
        # missing widgets must not abort production startup.
        progressbar = getattr(self, 'live_progressbar', None)
        if progressbar is not None:
            progressbar.configure(maximum=100, value=percent)
        percent_var = getattr(self, 'live_progress_percent', None)
        if percent_var is not None:
            percent_var.set(f'{percent:.0f}%')
        counts_var = getattr(self, 'live_progress_counts', None)
        if counts_var is not None:
            counts_var.set(
                f'Toplam: {total:,} · İşlenen: {completed:,} · '
                f'Başarılı: {int(snapshot.get("successful") or 0):,} · '
                f'Hatalı: {int(snapshot.get("failed") or 0):,} · '
                f'Atlanan: {int(snapshot.get("skipped") or 0):,}')
        category = snapshot.get('category') or 'Kuyruk'
        operation = snapshot.get('operation') or 'Üretim hazırlanıyor'
        outcome = snapshot.get('outcome') or 'running'
        outcome_label = {'success': 'başarılı', 'failed': 'hatalı', 'skipped': 'atlandı'}.get(outcome, 'işleniyor')
        stage_label = {'hazırlık': 'Aşama: Kuyruk hazırlama', 'üretim': 'Aşama: Üretim'}.get(
            str(snapshot.get('stage') or ''), f'Aşama: {snapshot.get("stage") or "üretim"}')
        title_var = getattr(self, 'live_progress_title', None)
        if title_var is not None:
            if str(snapshot.get('stage') or '') == '4K upscale':
                title_var.set('4K Upscale Çalışıyor' if completed < total else '4K Upscale raporu hazırlanıyor')
            else:
                title_var.set('Üretim Çalışıyor' if completed < total else 'Üretim raporu hazırlanıyor')
        detail_var = getattr(self, 'live_progress_detail', None)
        if detail_var is not None:
            detail_var.set(f'{stage_label} · {category} · {operation} · Sıra {completed:,}/{total:,} · {outcome_label}')
        eta = snapshot.get('eta_seconds')
        time_var = getattr(self, 'live_progress_time', None)
        if time_var is not None:
            time_var.set(
                f"Geçen: {self._format_duration(snapshot.get('elapsed_seconds'))} · "
                f"Tahmini kalan: {self._format_duration(eta) if eta is not None else '—'}"
            )
        result_var = getattr(self, 'result_summary', None)
        if result_var is not None and str(snapshot.get('stage') or '') != '4K upscale':
            # 4K aşaması sonucu üzerine yazmaz; üretim özeti korunur.
            result_var.set(
                f"Çıktı: {int(snapshot.get('successful') or 0)} · "
                f"Başarılı: {int(snapshot.get('successful') or 0)} · "
                f"Hatalı: {int(snapshot.get('failed') or 0)} · "
                f"Atlanan: {int(snapshot.get('skipped') or 0)}"
            )
        self._last_progress_snapshot = snapshot
        self._publish_graphite_operation(
            self.live_progress_title.get(),
            self.live_progress_percent.get(),
            self.live_progress_counts.get(),
        )

    def _publish_graphite_operation(self, title: str, percent: str = '', counts: str = '') -> None:
        target = getattr(self, '_operation_monitor_var', None)
        if target is None:
            return
        try:
            suffix = f' · {counts}' if counts else ''
            target.set(f'{title} {percent}{suffix}'.strip())
        except (AttributeError, tk.TclError):
            return

    def _apply_cloud_progress(self, snapshot: dict) -> None:
        total = max(0, int(snapshot.get('total') or 0))
        completed = min(total, max(0, int(snapshot.get('completed') or 0)))
        phase = str(snapshot.get('phase') or 'upload')
        failed_count = int(snapshot.get('failed') or 0)
        bar = getattr(self, 'cloud_progressbar', None)
        operation = str(snapshot.get('operation') or '')
        if phase == 'excel':
            # Excel aşaması: çubuk gerçek birim ilerlemesiyle (ana Excel +
            # mağaza Excel'leri, varsa kayıt sayacıyla) hareket eder.
            excel_total = max(1, int(snapshot.get('excel_total') or 1))
            excel_index = max(0, min(excel_total, int(snapshot.get('excel_index') or 0)))
            item_total = max(0, int(snapshot.get('excel_item_total') or 0))
            item = max(0, min(item_total, int(snapshot.get('excel_item') or 0))) if item_total else 0
            done_units = excel_index + ((item / item_total) if item_total else 0.0)
            percent = max(0.0, min(100.0, done_units / excel_total * 100.0))
            if bar is not None:
                bar.configure(maximum=100, value=percent)
            percent_text = f'{percent:.2f}'.replace('.', ',')
            self.cloud_progress_percent.set(f'{percent_text}%')
            self.cloud_progress_title.set('Excel Yazılıyor' if excel_index < excel_total else 'Excel Tamamlandı')
            self.cloud_progress_detail.set(f'Aşama: Excel · {operation or "Excel hazırlanıyor"}')
            counts = f'Excel adımı: {excel_index} / {excel_total}'
            if total:
                counts += f' · Linkli: {completed:,} / {total:,} görsel · Hata: {failed_count}'
            if item_total:
                counts += f' · Kayıt: {item:,} / {item_total:,}'
            self.cloud_progress_counts.set(counts)
        else:
            percent = completed / total * 100.0 if total else 0.0
            if bar is not None:
                bar.configure(maximum=100, value=percent)
            # Keep the live Excel/linking indicator informative.  A whole-number
            # label turns 1953/2925 (66.7692%) into an apparently coarse 67%,
            # which hides movement while the worker queue is still running.
            percent_text = f'{percent:.2f}'.replace('.', ',')
            self.cloud_progress_percent.set(f'{percent_text}%')
            self.cloud_progress_title.set('Excel / Linkleme Çalışıyor' if completed < total else 'Excel / Linkleme tamamlanıyor')
            self.cloud_progress_detail.set(f'Aşama: Bulut linkleme · {operation or "Bulut linki hazırlanıyor"}')
            self.cloud_progress_counts.set(
                f'{completed:,} / {total:,} görsel · Yeni: {int(snapshot.get("uploaded") or 0)} · '
                f'Mevcut: {int(snapshot.get("reused") or 0)} · Hata: {failed_count}')
        eta = snapshot.get('eta_seconds')
        self.cloud_progress_time.set(
            f'Geçen: {self._format_duration(snapshot.get("elapsed_seconds"))} · '
            f'Tahmini kalan: {self._format_duration(eta) if eta is not None else "—"}')
        self._publish_graphite_operation(
            self.cloud_progress_title.get(),
            self.cloud_progress_percent.get(),
            self.cloud_progress_counts.get(),
        )

    def _apply_overlay_progress(self, snapshot: dict) -> None:
        total = max(0, int(snapshot.get('total') or 0))
        completed = min(total, max(0, int(snapshot.get('completed') or 0)))
        percent = completed / total * 100.0 if total else 0.0
        self.overlay_progressbar.configure(maximum=100, value=percent)
        self.overlay_progress_percent.set(f'{percent:.0f}%')
        self.overlay_progress_title.set('PETEK Overlay Varyasyonları Çalışıyor' if completed < total else 'PETEK Overlay Varyasyonları tamamlandı')
        self.overlay_progress_detail.set(
            f'Aşama: PETEK overlay · 06_Petek_Kapama · {snapshot.get("cm") or snapshot.get("operation") or "hazırlanıyor"}')
        self.overlay_progress_counts.set(
            f'{completed:,} / {total:,} varyasyon · Başarılı: {int(snapshot.get("successful") or 0)} · '
            f'Atlanan: {int(snapshot.get("skipped") or 0)} · Hata: {int(snapshot.get("failed") or 0)}')
        eta = snapshot.get('eta_seconds')
        self.overlay_progress_time.set(
            f'Geçen: {self._format_duration(snapshot.get("elapsed_seconds"))} · '
            f'Tahmini kalan: {self._format_duration(eta) if eta is not None else "—"}')
        self._publish_graphite_operation(
            self.overlay_progress_title.get(),
            self.overlay_progress_percent.get(),
            self.overlay_progress_counts.get(),
        )

    _CM_ORDER = {'76': 0, '96': 1, '116': 2, '136': 3}

    def _apply_ready_overlay_progress(self, value: dict) -> None:
        """Render one ready-overlay event on the live overlay card.

        The caller (poll loop) may fire several times per file (one per
        measurement) plus a final ``file_done`` event.  Elapsed time comes
        from the real monotonic clock stamp taken when the folder job
        started; ETA uses the completed whole-file count, never a guess.
        """
        total = max(1, int(value.get('source_total') or 1))
        index = min(total, max(0, int(value.get('source_index') or 0)))
        status = str(value.get('status') or 'running')
        started = getattr(self, '_ready_overlay_started', None)
        if started is None:
            started = self._ready_overlay_started = time.monotonic()
        elapsed = max(0.0, time.monotonic() - started)
        cm_text = str(value.get('cm') or '')
        cm_ordinal = self._CM_ORDER.get(''.join(ch for ch in cm_text if ch.isdigit()))
        if status == 'file_done':
            done_units = float(index)
        elif status == 'failed':
            done_units = float(index)
        elif cm_ordinal is not None:
            done_units = (index - 1) + (cm_ordinal + 1) / 4.0
        else:
            done_units = float(max(0, index - 1))
        done_units = max(0.0, min(float(total), done_units))
        percent = done_units / total * 100.0
        eta = None
        if done_units > 0 and done_units < total:
            eta = elapsed * (total - done_units) / done_units
        self.overlay_progressbar.configure(maximum=100, value=percent)
        self.overlay_progress_percent.set(f'{percent:.1f}'.replace('.', ',') + '%')
        self.overlay_progress_title.set('Hazır Görsellere Overlay Uygulanıyor')
        src_name = Path(str(value.get('source') or '')).name
        if status == 'file_done':
            detail = f'{src_name} · dosya tamamlandı'
        elif status == 'failed':
            detail = f'{src_name} · hatalı · {str(value.get("error") or "ayrıntı yok")}'[:140]
        else:
            detail = f'{src_name} · {cm_text or "işleniyor"}'
        self.overlay_progress_detail.set(detail)
        self.overlay_progress_counts.set(f'{index:,} / {total:,} görsel · Kaynaklar korunuyor')
        self.overlay_progress_time.set(
            f'Geçen: {self._format_duration(elapsed)} · '
            f'Tahmini kalan: {self._format_duration(eta) if eta is not None else "—"}')

    def _preview_selected(self, _event=None) -> None:
        selection = self.listbox.curselection()
        if not selection:
            self.photo_label.configure(image='', text='Kaynak fotoğraf önizlemesi')
            self.photo_ref = None
            self.photo_text.set('Şablon seçin.')
            return
        uid = self.mapping[int(selection[-1])]
        path = self.template_sources.get(uid)
        try:
            if not path or path.is_symlink() or not path.is_file():
                raise FileNotFoundError(f'Kaynak fotoğraf eksik veya güvensiz: {path}')
            with Image.open(path) as photo:
                photo.draft('RGB', (210, 250))
                photo = photo.convert('RGB')
                photo.thumbnail((210, 240), Image.Resampling.LANCZOS)
                self.photo_ref = ImageTk.PhotoImage(photo, master=self.window)
            self.photo_label.configure(image=self.photo_ref, text='')
            self.photo_text.set(f"{uid} — HAM ŞABLON. Baskı/efekt burada gösterilmez; üretilen PNG dosyasında görünür.")
        except (OSError, ValueError) as exc:
            self.photo_ref = None
            self.photo_label.configure(image='', text='Fotoğraf açılamadı')
            self.photo_text.set('HATA: ' + str(exc))

    def _capture_visible(self):
        if self._filter_redrawing:return
        visible=set(self.mapping)
        selected={self.mapping[int(i)] for i in self.listbox.curselection()}
        self.selected_uids.difference_update(visible)
        self.selected_uids.update(selected)

    def _on_selection_change(self, _event=None):
        self._capture_visible()
        self._refresh_filter_count()
        self._update_store_filter_info()

    def _refresh_filter_count(self):
        if hasattr(self,'filter_count'):
            self.filter_count.set(f"Gösterilen: {len(self.mapping)} / {len(self.all_templates)} | "
                                  f"Üretim için seçili: {len(self.selected_uids)}")
        self._refresh_selection_summary()

    def _refresh_selection_summary(self):
        """Show a small, live job estimate without changing any selection."""
        if not hasattr(self, 'selection_summary'):
            return
        selected = len(set(getattr(self, 'selected_uids', set())))
        designs = 0
        try:
            folder = Path(self.design_folder.get().strip())
            if folder.is_dir():
                designs = sum(1 for _ in iter_designs(folder))
        except (OSError, ValueError):
            designs = 0
        stores = self._chosen_stores() if hasattr(self, 'store_list') else []
        if hasattr(self, 'workflow_hint'):
            if not selected:
                self.workflow_hint.set('01 Şablon seçin → 02 tasarım klasörü → 03 mağaza → 04 ön kontrol → üretim')
            elif not designs:
                self.workflow_hint.set('✓ Şablon seçildi → 02 tasarım klasörünü seçin → 03 mağaza → ön kontrol')
            elif not stores:
                self.workflow_hint.set('✓ Şablon + tasarım hazır → 03 mağaza seçin → ön kontrol → üretim')
            else:
                self.workflow_hint.set('✓ Şablon + tasarım + mağaza hazır → 04 ön kontrol → üretime başlayın')
        store_text = ', '.join(stores) if stores else 'LOCAL'
        pairs = selected
        if stores and selected:
            try:
                keys = self._store_assignment_keys()
                pairs = sum(1 for item in self.all_templates
                            if str(item.get('uid')) in self.selected_uids
                            and key_for(item) in keys)
            except (OSError, ValueError, KeyError):
                pairs = 0
        mode_code = self.render_mode_display.get(self.render_mode.get(), 'balanced_one_per_design')
        four_on = hasattr(self, 'four_panel') and self.four_panel.enabled()
        if four_on:
            jobs = len(stores) * designs * 4
            self.selection_summary.set(
                f'4 Mockup modu · Tasarım: {designs} · Mağaza: {store_text} · '
                f'Beklenen final görsel: {designs} × {len(stores)} × 4 = {jobs:,}')
            if hasattr(self, 'start_button'):
                try:
                    self.start_button.configure(state='normal' if (designs and stores) else 'disabled')
                except tk.TclError:
                    pass
            return
        if mode_code == 'balanced_one_per_design':
            jobs = (len(stores) if stores else 1) * designs if pairs else 0
        else:
            jobs = pairs * designs
        self.selection_summary.set(
            f'Seçili şablon: {selected} · Tasarım: {designs} · Mağaza: {store_text} · '
            f'Model: {"1/tasarım" if mode_code == "balanced_one_per_design" else "tümü"} · Beklenen iş: {jobs:,}')
        # A store/selection mismatch is a production preflight error, not a
        # reason to make the primary action disappear.  Keep the button
        # available so start() can show the actionable diagnostic and its
        # repair action; start() remains the authoritative safety gate.
        ready = bool(selected and designs)
        if hasattr(self, 'start_button'):
            try:
                self.start_button.configure(state='normal' if ready else 'disabled')
            except tk.TclError:
                pass

    def chosen_uids(self):
        self._capture_visible()
        return sorted(self.selected_uids & set(self.template_items))

    def apply_filters(self, capture=True):
        if not hasattr(self,'all_templates') or not hasattr(self,'listbox'):return
        if capture: self._capture_visible()
        self._filter_redrawing=True
        try:
            visible=filtered_templates(self.all_templates,self.category_filter.get(),
                                       self.search_filter.get(),self.sort_filter.get())
            if self.store_only_view:
                try:
                    assigned=self._store_assignment_keys()
                    visible=[item for item in visible if key_for(item) in assigned]
                except (OSError, ValueError, KeyError) as exc:
                    visible=[]   # fail closed: never expose unrelated mockups
                    self.store_filter_label.set('Mağaza profili okunamadı: '+str(exc))
            self.listbox.delete(0,'end');self.mapping=[]
            for item in visible:
                uid=item['uid']
                self.mapping.append(uid)
                self.listbox.insert('end',f"[{item['category']}] {uid} ({item['orientation']})")
                if uid in self.selected_uids:
                    self.listbox.selection_set('end')
            self._refresh_filter_count()
        finally:
            self._filter_redrawing=False
        self._preview_selected()
        self._update_store_filter_info()

    def reload(self) -> None:
        """Fast first paint: scan approved templates on a worker, update Tk on UI."""
        self._capture_visible()
        keep=set(self.selected_uids)
        initial=self._first_template_load
        self._load_seq += 1
        token=self._load_seq
        self.progress.set('Şablon listesi okunuyor… Ana pencereyi kullanmaya devam edebilirsin.')
        self.filter_count.set('Onaylı şablonlar arka planda taranıyor…')
        self.start_button.configure(state='disabled')
        def work():
            try:
                templates,audit=self.batch_engine.discover_templates(per_category_limit=None)
                self.messages.put(('templates_loaded',(token,templates,audit,keep,initial)))
            except Exception as exc:
                self.messages.put(('templates_load_fail',(token,str(exc))))
        threading.Thread(target=work,daemon=True,name='approved-template-index').start()

    def _apply_loaded_templates(self, result):
        token,templates,audit,keep,initial=result
        if token!=self._load_seq or not self.window.winfo_exists():return
        self.discovery_audit = audit if isinstance(audit, dict) else {'skipped': []}
        skipped = list(self.discovery_audit.get('skipped') or [])
        self.all_templates=list(templates)
        self.template_sources={t['uid']:Path(t['source']) for t in templates}
        self.template_items={t['uid']:t for t in templates}
        self.selected_uids=set() if initial else (keep & set(self.template_items))
        self._first_template_load=False
        self.apply_filters(capture=False)
        self.progress.set(f"Toplam {len(self.all_templates)} insan onaylı şablon hazır. "
                          f"Atlanan: {len(skipped)}. Arama ve seçime hazır.")
        self.skipped_summary.set(f'Atlanan: {len(skipped)} ·')
        self.skipped_button.configure(
            state=('normal' if skipped else 'disabled'),
            text='Nedenleri Gör')
        self._refresh_selection_summary()

    def show_skipped_reasons(self):
        """Show the current read-only discovery receipt grouped by reason.

        This deliberately uses the audit returned by the existing discovery
        engine.  No database/source rescan, approval update or retry is done
        from this dialog.
        """
        skipped = list((self.discovery_audit or {}).get('skipped') or [])
        if not skipped:
            return
        dialog = tk.Toplevel(self.window)
        dialog.title('Atlanan şablonlar · nedenleri')
        dialog.transient(self.window)
        dialog.configure(background=BG)
        dialog.geometry('760x560')
        dialog.minsize(560, 380)
        outer = ttk.Frame(dialog, padding=14)
        outer.pack(fill='both', expand=True)
        ttk.Label(outer, text=f'Atlanan {len(skipped)} şablon — üretim ön kontrolü raporu',
                  font=('Segoe UI', 14, 'bold')).pack(anchor='w')
        ttk.Label(outer,
                  text='Bu liste salt okunurdur. Hiçbir kayıt, maske, kaynak fotoğrafı veya çıktı değiştirilmedi.',
                  wraplength=700).pack(anchor='w', pady=(4, 10))
        text = scrolledtext.ScrolledText(outer, wrap='word', height=22,
                                         bg=PANEL, fg=FG, insertbackground=FG,
                                         relief='flat', padx=10, pady=8)
        text.pack(fill='both', expand=True)

        grouped = {}
        for item in skipped:
            reason = str(item.get('reason') or 'Belirtilmeyen ön kontrol hatası').strip()
            category = str(item.get('category') or 'Bilinmeyen kategori')
            uid = str(item.get('template_uid') or 'UID yok')
            grouped.setdefault(reason, []).append((category, uid))

        def advice(reason):
            low = reason.lower()
            if 'approved' in low or 'onayı' in low or 'draft' in low:
                return 'Kullanıcı yapabilir: Şablon inceleme ekranında insan onayını tamamlayın; PETEK ise geçerli revizyonu APPROVED yapın.'
            if 'sha' in low or 'kaynak' in low or 'eslesme' in low or 'eşleşme' in low:
                return 'Kullanıcı yapabilir: Orijinal kaynak fotoğrafını ve SHA kaydını kontrol edin; farklı fotoğrafla eşleştirmeyin.'
            if 'köşe' in low or 'dört' in low or 'geometri' in low or 'yön' in low or 'oran' in low:
                return 'Kullanıcı yapabilir: Şablon incelemede dört köşe/geometri ve fiziksel yön onayını düzeltip yeniden onaylayın.'
            if 'yol' in low or 'dosya' in low or 'tablosunda' in low:
                return 'Kullanıcı yapabilir: Kaynak dosyasının beklenen kategori klasöründe bulunduğunu kontrol edin; onay kaydını elle taşımayın.'
            return 'Kullanıcı yapabilir: İlgili şablonu inceleme ekranında açıp belirtilen ön kontrol sorununu giderin; güvenli işler üretilebilir.'

        text.insert('end', 'Özet\n', ('heading',))
        for reason, entries in sorted(grouped.items(), key=lambda pair: (-len(pair[1]), pair[0])):
            text.insert('end', f'\n{len(entries)} adet · {reason}\n', ('reason',))
            text.insert('end', f'  {advice(reason)}\n')
            for category, uid in entries[:12]:
                text.insert('end', f'  • {category} — {uid}\n')
            if len(entries) > 12:
                text.insert('end', f'  • … ve {len(entries) - 12} kayıt daha\n')
        text.configure(state='disabled')
        text.tag_configure('heading', font=('Segoe UI', 12, 'bold'))
        text.tag_configure('reason', font=('Segoe UI', 10, 'bold'), foreground='#17D3A3')
        ttk.Button(outer, text='Kapat', command=dialog.destroy).pack(anchor='e', pady=(10, 0))
        dialog.bind('<Escape>', lambda _event: dialog.destroy())
        dialog.protocol('WM_DELETE_WINDOW', dialog.destroy)
        dialog.focus_set()

    def select_all(self) -> None:
        self.selected_uids=set(self.template_items)
        self.apply_filters(capture=False)

    def select_filtered(self) -> None:
        self.selected_uids.update(self.mapping)
        self.apply_filters(capture=False)

    def clear_selection(self) -> None:
        self.selected_uids.clear()
        self._filter_redrawing=True
        try:self.listbox.selection_clear(0,'end')
        finally:self._filter_redrawing=False
        self._refresh_filter_count()

    def _verify_4k_status(self):
        """Manual only: never silently starts installation or enables public upload."""
        if self._4k_installing:
            messagebox.showinfo('4K durumu','Kurulum devam ediyor. Normal üretim korunuyor.',parent=self.window)
            return
        self._4k_state.set('4K kurulumu kontrol ediliyor...')
        model=self._4k_model_code()
        def worker():
            try:
                found,kind=self._4k_checker.verify(model)
                report='Real-ESRGAN motoru hazır.\nModel: '+model+'\nKonum: '+str(found)+'\nDurum: '+kind
                self.messages.put(('4k_manual_status',(report,True)))
            except (OSError,UpscaleError) as exc:
                msg='4K henüz hazır değil.\n'+str(exc)+'\nÇözüm: 4K kutusunu açınca güvenli kurulum başlatılır.'
                self.messages.put(('4k_manual_status',(msg,False)))
        threading.Thread(target=worker,daemon=True,name='4K-manual-check').start()

    def _show_4k_status(self,message,ready):
        if not self.window.winfo_exists():return
        self._4k_state.set('4K hazır ✓' if ready else '4K eksik — kurulumu 4K seçimi başlatır')
        if ready:messagebox.showinfo('4K Kontrol',message,parent=self.window)
        else:messagebox.showwarning('4K Kontrol',message,parent=self.window)

    def _4k_model_code(self):
        return 'fast' if self.upscale_model.get().startswith('Hızlı') else 'photo'

    def _on_4k_selected(self):
        """Never probe on program start, only when enabled or selected model changes."""
        if getattr(self, '_restoring_preferences', False):
            return
        if not self.window.winfo_exists() or not self.upscale_4k.get():
            if not self._4k_installing:self._4k_state.set('4K kapalı · seçimde kontrol edilir')
            return
        if self._4k_installing:
            self._4k_state.set('Resmî 4K kurulum devam ediyor...')
            return
        try:
            found,kind=self._4k_checker.verify(self._4k_model_code())
            self._4k_state.set('4K hazır ✓  (önbellek)' if kind=='ONBELLEK_HAZIR'
                               else '4K hazır ✓  (doğrulandı)')
        except (OSError,UpscaleError) as exc:
            self._4k_state.set('4K eksik · güvenli otomatik kurulum başlatılıyor')
            self._start_4k_installer(str(exc))

    def _start_4k_installer(self, reason):
        if self._4k_installing:return
        script=Path(__file__).resolve().parents[2]/'KUR_REAL_ESRGAN_4K_WINDOWS.ps1'
        if os.name!='nt' or not script.is_file():
            self._4k_state.set('4K kurulumu bu ortamda kullanılamıyor')
            messagebox.showwarning('4K otomatik kurulum',reason+'\nWindows kurulum dosyası bulunamadı.',parent=self.window)
            self.upscale_4k.set(False)
            return
        # Selecting 4K is the operator's explicit opt-in. Official SHA256
        # verification/no-overwrite protection remains in the PowerShell script.
        self._4k_installing=True
        self._4k_state.set('4K motoru kuruluyor · temel üretim korunuyor')
        def worker():
            try:
                cmd=['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(script)]
                completed=subprocess.run(cmd,cwd=str(script.parent),capture_output=True,
                                         text=True,errors='replace',timeout=1200,check=False)
                lines=(completed.stdout or '')+'\n'+(completed.stderr or '')
                # Preserve a user-inspectable diagnostic without exposing secrets.
                dest=user_state_path().parent/'4k_kurulum_kaydi.txt'
                dest.parent.mkdir(parents=True,exist_ok=True)
                dest.write_text(lines[-25000:],encoding='utf-8')
                self.messages.put(('4k_install_done',(completed.returncode,str(dest))))
            except (OSError,subprocess.TimeoutExpired) as exc:
                self.messages.put(('4k_install_done',(-1,str(exc))))
        threading.Thread(target=worker,daemon=True,name='4K-install').start()

    def setup_4k(self):
        """Compatibility action for existing search/menu references."""
        if not self.upscale_4k.get():self.upscale_4k.set(True)
        else:self._on_4k_selected()

    def start_petek_ab_preview(self):
        if self.worker and self.worker.is_alive():
            messagebox.showinfo('PETEK Test','Devam eden işlem varken önizleme çalışmaz.',parent=self.window);return
        chosen=self.chosen_uids()
        item=next((self.template_items[uid] for uid in chosen
                   if self.template_items[uid]['category']=='06_Petek_Kapama'),None)
        if item is None:
            messagebox.showinfo('PETEK Test','Önce PETEK kategorisinden onaylı şablon seç.',parent=self.window);return
        folder=Path(self.design_folder.get().strip())
        if not folder.is_dir():
            messagebox.showwarning('Baskı','Önce tasarım klasörü seç.',parent=self.window);return
        art=next(iter(iter_designs(folder)),None)
        if art is None:
            messagebox.showwarning('Baskı','Tasarım bulunamadı.',parent=self.window);return
        mode=self.petek_slot_mode.get();cleanup=bool(self.petek_pink_cleanup.get())
        placement='cover' if self.placement.get().startswith('Tam Doldur') else 'contain'
        light=_lighting_code(self.lighting.get())
        profile_var=getattr(self,'petek_nature_profile',None)
        profile=profile_var.get() if profile_var is not None else 'Doğal'
        effective_light='strong' if light!='off' and profile=='Belirgin' else light
        material_effect=light!='off'
        self.progress.set(f'PETEK {profile} görseli: gerçek üretim efektleriyle önizleme hazırlanıyor...')
        def work():
            try:
                profile_data,mask=self.petek_registry.get(item['uid'],require_approved=True,
                                                          source_override=Path(item['source']))
                scene=petek_engine.read_bgr(Path(item['source']))
                proxy,_=prepare_render_artwork(art,self.batch_engine.root/'working_art_proxies')
                # BEFORE is plain reference; AFTER is precisely the same
                # render pipeline as the production batch, except 3:4/4K.
                before,_=render_petek_visual(
                    scene,proxy,item['quad'],mask,item['physical_aspect'],
                    placement=placement,lighting='natural' if light!='off' else 'off',
                    material_effect=False,slot_mode='off',pink_cleanup=False)
                after,qa=render_petek_visual(
                    scene,proxy,item['quad'],mask,item['physical_aspect'],
                    placement=placement,lighting=effective_light,
                    material_effect=material_effect,slot_mode=mode,pink_cleanup=cleanup)
                slot_info=qa['slot_qa'];final_info=qa['pink_qa']
                self.messages.put(('ab_done',(
                    petek_engine.canvas_3x4(before),petek_engine.canvas_3x4(after),
                    item['uid'],art.name,{'status':f"PETEK {slot_info['status']} / pembe {final_info['status']} / {profile}",
                    'protected_pixel_changes':qa['pre_pink_qa'].get('repaired_pixels',0),
                    'mean_inside_delta':int((after!=before).any(axis=2).sum()),
                    'detail_edge_delta':f"Ölçülemeyen yarık gölgesi: {slot_info.get('endpoint_effect_suppressed_count',0)}"})))
            except Exception as exc:
                self.messages.put(('ab_fail',str(exc)))
        self._worker_kind='preview';self.worker=threading.Thread(target=work,daemon=False);self.worker.start()

    def browse(self) -> None:
        path = filedialog.askdirectory(
            parent=self.window,
            title="Baskı Tasarımları Klasörünü Seç (Mockup klasörü değil)",
        )
        if path:
            self.design_folder.set(path)

    def _petek_overlay_root(self) -> Path:
        return ((self.runtime_root / 'Overlay_Giydirme') if self.runtime_root else
                (Path(__file__).resolve().parents[3] / 'Overlay_Giydirme')).resolve()

    def preflight_petek_overlay(self) -> None:
        """Read-only validation of the operator-supplied grouped overlay pool."""
        try:
            refresh_overlay_cache()
            report = petek_overlay_preflight(self._petek_overlay_root())
            counts = report.get('counts', {})
            issues = report.get('errors', [])
            contract = report.get('standard_contract', {})
            contract_line = ('Standart: ÜST/ALT {0}×{1} px RGBA · final {2}×{3} px'
                             .format(*(contract.get('overlay_size') or [1200, 300]),
                                     *(contract.get('final_size') or [1200, 1800])))
            if report.get('ready_for_four'):
                suffix = (f' · {len(issues)} grup raporu incelemede; geçerli gruplar kullanılacak'
                          if issues else '')
                self.progress.set('PETEK overlay ön kontrolü hazır ✓ · ' +
                                  ', '.join(f'{key}: {value}' for key, value in counts.items()) + suffix)
                messagebox.showinfo('PETEK Overlay Ön Kontrolü',
                                    'Hazır katman havuzu dört ölçü için kullanılabilir.\n' +
                                    contract_line + '\n\n' +
                                    '\n'.join(f'{key}: {value} geçerli grup' for key, value in counts.items()) +
                                    (f'\n\nRaporlanan ve kullanılmayan grup/dosya: {len(issues)}' if issues else ''),
                                    parent=self.window)
            else:
                detail = '\n'.join(str(item) for item in report.get('errors', [])[:20])
                self.progress.set('PETEK overlay ön kontrolü başarısız; temiz kaynak linklenmeyecek.')
                messagebox.showwarning('PETEK Overlay Ön Kontrolü', detail, parent=self.window)
        except Exception as exc:
            self.progress.set('PETEK overlay ön kontrolü hata verdi: ' + str(exc))
            messagebox.showwarning('PETEK Overlay Ön Kontrolü', str(exc), parent=self.window)

    def apply_overlay_to_ready_folder(self) -> None:
        """Select an existing clean-image folder and create overlay derivatives."""
        if self.worker and self.worker.is_alive():
            messagebox.showinfo('İşlem sürüyor', 'Önce çalışan işlemin tamamlanmasını bekleyin.', parent=self.window)
            return
        source_path = filedialog.askdirectory(parent=self.window,
                                              title='Hazır görseller klasörünü seçin (Overlaysızlar)')
        if not source_path:
            return
        source_folder = Path(source_path).resolve()
        default_output = source_folder.parent / f'{source_folder.name}_OverlayUygulanmis'
        output_path = filedialog.askdirectory(parent=self.window,
                                               title='Overlay çıktısı klasörünü seçin (İptal: otomatik klasör)',
                                               initialdir=str(source_folder.parent))
        output_folder = Path(output_path).resolve() if output_path else default_output
        if output_folder == source_folder or source_folder in output_folder.parents:
            messagebox.showwarning('Güvenli çıktı yolu', 'Çıktı klasörü kaynak klasörün içinde veya kendisi olamaz.', parent=self.window)
            return
        try:
            refresh_overlay_cache()
            report = petek_overlay_preflight(self._petek_overlay_root())
            if not report.get('ready_for_four'):
                raise ValueError('Overlay katman ön kontrolü başarısız: ' + '; '.join(report.get('errors', [])[:8]))
        except Exception as exc:
            messagebox.showwarning('Overlay ön kontrolü', str(exc), parent=self.window)
            return
        self._worker_kind = 'ready_overlay'
        self.ready_overlay_button.configure(state='disabled')
        self._ready_overlay_started = time.monotonic()
        self.progress.set('Hazır görsellere overlay uygulanıyor…')

        def work():
            try:
                result = process_petek_overlay_folder(
                    source_folder, self._petek_overlay_root(), output_folder,
                    on_progress=lambda payload: self.messages.put(('ready_overlay_progress', payload)))
                self.messages.put(('ready_overlay_done', result))
            except Exception as exc:
                self.messages.put(('ready_overlay_fail', str(exc)))

        self.worker = threading.Thread(target=work, daemon=True, name='ready-petek-overlay')
        self.worker.start()

    def start(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        retry_scope = getattr(self, '_retry_scope', None)
        self._retry_scope = None
        selected = sorted(set(retry_scope)) if retry_scope else self.chosen_uids()
        selected = [uid for uid in selected if uid in self.template_items]
        selected_stores=self._chosen_stores()
        four_cfg = None
        four_panel = getattr(self, 'four_panel', None)
        if four_panel is not None and four_panel.enabled() and not retry_scope:
            try:
                four_cfg, selected = four_panel.prepare_for_start()
            except (ValueError, KeyError, OSError) as exc:
                messagebox.showwarning("4 Mockup Üretim Öncesi Kontrol", str(exc), parent=self.window)
                return
        if not selected:
            messagebox.showinfo("Şablon Seç", "En az bir onaylı şablon seçin.", parent=self.window)
            return
        # Snapshot all Tk variables on the UI thread BEFORE starting the worker.
        # Accessing StringVar from the worker can freeze/crash Tk on Windows.
        try:
            design_folder = self.design_folder.get().strip()
            if not Path(design_folder).is_dir():
                raise ValueError("Geçerli bir baskı tasarımları klasörü seçin.")
            group = self.group.get().strip()
            import re
            if not re.fullmatch(r"[A-Za-z0-9_-]{2,36}", group):
                raise ValueError("Mağaza grubu 2–36 karakter; yalnız harf, sayı, _ veya - olmalı.")
            max_jobs = None
            placement = "cover" if self.placement.get().startswith("Tam Doldur") else "contain"
            # Production uses the reviewed category recipe by default.  The
            # old lighting variable remains only for explicit A/B preview
            # compatibility; normal production is never user-overridden.
            lighting = 'natural'
            sun_option=getattr(self,'sunlight_profile',None)
            sunlight_profile=SUN_CODES.get(sun_option.get(),'off') if sun_option is not None else 'off'
            glass_effect = "off" if lighting == "off" else "on"
            # Cam köşesi onaylı şablonda saklanır; arayüzde global override yok.
            corner_radius = None
            upscale_4k = bool(self.upscale_4k.get())
            auto_cloud_after_render = bool(self.auto_cloud_link.get())
            upscale_model = "fast" if self.upscale_model.get().startswith("Hızlı") else "photo"
            petek_slot_mode=self.petek_slot_mode.get()
            petek_pink_cleanup=bool(self.petek_pink_cleanup.get())
            petek_overlay_enabled=bool(self.petek_overlay_enabled.get()) and four_cfg is None
            petek_nature_option=getattr(self,'petek_nature_profile',None)
            petek_realism_profile=('belirgin' if petek_nature_option is not None and petek_nature_option.get()=='Belirgin' else 'dogal')
            petek_selected=any(self.template_items.get(uid,{}).get('category')=='06_Petek_Kapama' for uid in selected)
            if petek_overlay_enabled and not petek_selected:
                raise ValueError('PETEK overlay yalnız 06_Petek_Kapama seçildiğinde kullanılabilir.')
            if petek_overlay_enabled:
                refresh_overlay_cache()
                overlay_report = petek_overlay_preflight(self._petek_overlay_root())
                if not overlay_report.get('ready_for_four'):
                    raise ValueError('PETEK overlay katman ön kontrolü başarısız: ' +
                                     '; '.join(overlay_report.get('errors', [])[:6]))
            # PETEK A/B visual comparison is OPTIONAL, not a production gate.
            # Immutable APPROVED profile + source/mask SHA, store ownership and
            # per-output real-vent geometry checks remain in the engine.
            # A preview approval is *never* substituted for template approval.
            if upscale_4k:
                if self._4k_installing:
                    raise UpscaleError('4K kurulumu sürüyor. Normal üretim için 4K seçimini kapatın.')
                self._4k_checker.verify(upscale_model)
                upscale_preflight(enabled=True, model=upscale_model)
        except (ValueError, KeyError, UpscaleError) as exc:
            messagebox.showwarning("Üretim Ayarları", str(exc), parent=self.window)
            return

        skipped_design_paths = set()
        skipped_design_names = []
        include_used_designs = bool(self.include_used_designs.get())

        def _is_used_design_path(path: str | Path) -> bool:
            """Return whether a path is inside an operator-used archive folder."""
            used_names = {
                'kullanildi', 'kullanılanlar', 'kullanilanlar',
                'kullanılan', 'kullanilan', 'used', 'baski-kullanildi',
            }
            return any(str(part).casefold() in used_names for part in Path(path).parts)

        try:
            selected_root_for_mode = Path(design_folder).resolve()
            ham_root_for_mode = ((self.runtime_root / 'HAM BASKI TASARIMLARI').resolve(strict=False)
                                 if self.runtime_root else None)
            external_designs = bool(ham_root_for_mode is not None and
                                    selected_root_for_mode != ham_root_for_mode and
                                    ham_root_for_mode not in selected_root_for_mode.parents)
            if self.runtime_root:
                ham_root=(self.runtime_root/'HAM BASKI TASARIMLARI').resolve(strict=False)
                selected_root=Path(design_folder).resolve()
                if selected_root==ham_root or ham_root in selected_root.parents:
                    # V5 central upload owns Yatay_Tasarim*/Dikey_Tasarim*
                    # identities.  The HamDesignVault check is retained only
                    # for the explicitly opted-in legacy watcher, whose
                    # Ham<number> registry is a different authority.
                    if os.environ.get('GORSEL_ENABLE_LEGACY_HAM_WATCHER', '').strip() == '1':
                        from ham_designs_v487 import HamDesignVault
                        HamDesignVault(self.runtime_root).validate_for_production()
                    else:
                        from central_upload_v500 import CentralUploadRegistry
                        registry = CentralUploadRegistry(self.runtime_root)
                        audit = registry.audit_designs_for_production()
                        pool = Path(audit['path']).resolve()
                        # A preflight defect is item-level: keep the run alive,
                        # but exclude every exact affected file and report it.
                        for issue in audit.get('issues', []):
                            # A moved file under Kullanildi is a recoverable
                            # workflow state, not a permanent production ban.
                            # The explicit checkbox above is the only way to
                            # include it again; unrelated SHA/registry defects
                            # remain blocked.
                            if (include_used_designs and
                                    issue.get('type') == 'CENTRAL_DESIGN_FILE_MOVED_USED' and
                                    issue.get('found') and
                                    _is_used_design_path(issue['found'])):
                                continue
                            if issue.get('file'):
                                skipped_design_paths.add(str((pool / issue['file']).resolve()))
                            if issue.get('found'):
                                skipped_design_paths.add(str((pool / issue['found']).resolve()))
                        for relative in audit.get('unregistered', []):
                            # Never opt an unregistered/renamed file back in.
                            # The explicit recovery option is limited to a
                            # registry-backed file reported as MOVED_USED;
                            # otherwise a new name could silently acquire a
                            # second identity.
                            skipped_design_paths.add(str((pool / relative).resolve()))
                        skipped_design_names = sorted(Path(p).name for p in skipped_design_paths)
                        if skipped_design_names:
                            self._log('KULLANILDIĞI/KAYITSIZ YA DA HATALI OLDUĞU İÇİN ATLANACAK TASARIMLAR: ' + ', '.join(skipped_design_names))
            design_count = sum(1 for p in iter_designs(Path(design_folder))
                               if str(p.resolve()).casefold() not in {str(x).casefold() for x in skipped_design_paths})
            if design_count == 0:
                raise ValueError("Seçili klasörde desteklenen baskı tasarımı yok.")
        except (OSError, ValueError) as exc:
            messagebox.showwarning("Tasarım Klasörü / Ham Numara Çakışması", str(exc), parent=self.window)
            return
        if selected_stores:
            try:
                approved=list(self.template_items.values())
                # The SAME exact snapshot is used for diagnosis and plan;
                # unchecked out-of-store UIDs may not be silently ignored.
                diagnostic,identity=self._store_selection_snapshot(
                    selected=selected,stores=selected_stores)
                if not diagnostic['ready']:
                    raise ValueError('Seçilen şablon(lar) ile mağaza üyeliği uyuşmuyor.')
                plan=StoreProfiles(self.batch_engine.root).plan(
                    selected_stores,approved,selected_uids=selected)
                pair_count=sum(len(store_templates) for _,store_templates in plan)
            except (ValueError,KeyError,OSError) as exc:
                try:
                    diagnostic,identity=self._store_selection_snapshot(
                        selected=selected,stores=selected_stores)
                    self._log('MAĞAZA ÖN KONTROLÜ: '+
                              self._store_report_text(diagnostic,identity))
                    self._store_preflight_error(exc,diagnostic,identity)
                except Exception as detail_exc:
                    messagebox.showwarning('Mağaza İzolasyonu',
                        str(exc)+'\nTeşhis ayrıntısı: '+str(detail_exc),parent=self.window)
                return
        else:
            pair_count=len(selected)
        render_mode = self.render_mode_display.get(self.render_mode.get(), 'balanced_one_per_design')
        if four_cfg is not None:
            render_mode = 'all_templates_per_design'
            pair_count = 4 * len(selected_stores)
        if render_mode == 'balanced_one_per_design':
            job_count = (len(selected_stores) if selected_stores else 1) * design_count
        else:
            job_count = pair_count * design_count
        worker_hint = 2
        preflight = planning_summary(output_root=self.batch_engine.output,
                                     jobs=job_count * (2 if four_cfg is not None else 1), templates=pair_count,
                                     designs=design_count, workers=max(1, min(8, worker_hint)),
                                     report_dir=self.batch_engine.reports, upscale=upscale_4k,
                                     render_mode=render_mode)
        if not preflight['disk_budget_ok']:
            messagebox.showwarning('Yetersiz disk bütçesi',
                                   summary_text(preflight) + '\n\nÜretim başlatılmadı.',
                                   parent=self.window)
            return
        if not messagebox.askyesno("Üretim Öncesi Akıllı Özet",
            summary_text(preflight) + "\n\nHer çıktı ayrı kayıtla korunur; işlemi güvenli durdurabilirsin.\n"
            "BU İŞLEMİ BAŞLATMAK İSTİYOR MUSUN?", parent=self.window):
            return
        stream_cloud = None
        if auto_cloud_after_render:
            stream_cloud = CloudExcel(self.batch_engine.root, self.batch_engine.reports, self.runtime_root)
            if not stream_cloud.available():
                messagebox.showwarning('Bulut Anahtarı Yok', 'Linkleme seçildi ancak ImgBB / FreeImage anahtarı bulunamadı. Üretim başlatılmadı.', parent=self.window)
                return
            if not messagebox.askyesno('Üretimle birlikte linkle',
                'Her doğrulanmış görsel üretildiği anda arka planda HTTPS linke çevrilecek; üretim bitince Excel tamamlanacak.\n\nBULUTA YÜKLEMEYİ ONAYLIYOR MUSUN?', parent=self.window):
                return
        self._save_ui_preferences()
        self._auto_cloud_pending = False
        self._auto_cloud_keys = []
        self._render_stop_requested = False
        self.batch_engine.cancel.clear()
        self.batch_engine.resume()
        self.start_button.configure(text='⏹  ÜRETİM ÇALIŞIYOR', state="disabled")

        # With PETEK overlays the engine never queues the clean PETEK source;
        # only SHA-verified overlay derivatives (and other categories) enter
        # the queue, as soon as each one exists.
        stream_queue = queue.Queue() if stream_cloud else None
        stream_stats = {'completed': 0, 'uploaded': 0, 'reused': 0, 'failed': 0}
        stream_done = threading.Event()
        stream_started = time.monotonic()
        stream_lock = threading.Lock()
        stream_threads = 3  # network-bound; each upload is independent, ledger writes are per-row
        stream_alive = [stream_threads]
        def stream_worker():
            while stream_cloud and stream_queue is not None:
                item = stream_queue.get()
                if item is None:
                    stream_queue.put(None)  # let sibling workers see the sentinel
                    break
                try: outcome = stream_cloud.upload_one(item, notify=self._log)
                except Exception as exc:
                    outcome = 'failed'; self._log(f'LINKLEME HATASI: {exc}')
                with stream_lock:
                    stream_stats[outcome] += 1
                    stream_stats['completed'] += 1
                    snapshot = dict(stream_stats)
                total = max(job_count, snapshot['completed'] + stream_queue.qsize())
                elapsed = max(0.0, time.monotonic() - stream_started)
                eta = None
                if snapshot['completed'] and snapshot['completed'] < total:
                    eta = elapsed * (total - snapshot['completed']) / snapshot['completed']
                self.messages.put(('cloud_progress', {'completed': snapshot['completed'], 'total': total,
                    'elapsed_seconds': elapsed, 'eta_seconds': eta, 'operation': 'Üretim çıktısı linkleniyor', **snapshot}))
            with stream_lock:
                stream_alive[0] -= 1
                if stream_alive[0] <= 0:
                    stream_done.set()
        if stream_queue is not None:
            for _n in range(stream_threads):
                threading.Thread(target=stream_worker, daemon=True, name=f'v4-link-{_n}').start()
            self._apply_cloud_progress({'completed': 0, 'total': job_count, 'operation': 'Üretimle birlikte linkleme kuyruğu hazır', **stream_stats})
        def work():
            try:
                res = self.batch_engine.run(
                    design_folder,
                    selected_uids=selected,
                    selected_stores=selected_stores,
                    group=group,
                    notify=self._log,
                    max_jobs=max_jobs,
                    placement=placement,
                    lighting=lighting,
                    corner_radius=corner_radius,
                    glass_effect=glass_effect,
                    upscale_4k=upscale_4k,
                    upscale_model=upscale_model,
                    petek_slot_mode=petek_slot_mode,
                    petek_pink_cleanup=petek_pink_cleanup,
                    petek_realism_profile=petek_realism_profile,
                    petek_overlay_enabled=petek_overlay_enabled,
                    petek_overlay_root=self._petek_overlay_root(),
                    four_mockup=four_cfg,
                    sunlight_profile=sunlight_profile,
                    external_designs=external_designs,
                    render_mode=render_mode,
                    skipped_design_paths=skipped_design_paths,
                    progress=self._production_progress,
                    output_ready=(lambda row: stream_queue.put(row)) if stream_queue is not None else None,
                )
                if stream_queue is not None:
                    stream_queue.put(None)
                    stream_done.wait()
                    batch_keys = set(res.get('current_batch_keys', []))
                    # External runs restore the central ledger before returning;
                    # prefer the operation's captured SHA-verified rows.
                    final_rows = list(res.get('current_batch_rows') or [])
                    if not final_rows:
                        final_rows = [row for row in self.batch_engine.ledger.successful()
                                      if row.get('key') in batch_keys]
                    final = stream_cloud.publish_existing(final_rows, notify=self._log,
                        stop=self.batch_engine.cancel, trend_template=None,
                        exclude_clean_petek=(four_cfg is not None or petek_overlay_enabled))
                    # Keep production and link counters separate.  A render
                    # can be rejected by its own QA contract, so a link pass
                    # ending at (for example) 287 is not an indication that
                    # the link worker stopped early when the planned batch was
                    # 295.  The UI/result report must retain that distinction.
                    final.update({
                        'streaming': True,
                        **stream_stats,
                        'production_planned': int(res.get('planned', 0)),
                        'production_attempted': int(res.get('attempted', 0)),
                        'production_rendered': int(res.get('rendered', 0)),
                        'production_failed': int(res.get('rejected', 0)),
                        'production_status': res.get('status'),
                        'production_error_report': res.get('error_report', ''),
                    })
                    self.messages.put(('cloud_done', final))
                elif stream_cloud and (petek_overlay_enabled or four_cfg is not None):
                    batch_keys = set(res.get('current_batch_keys', []))
                    final_rows = list(res.get('current_batch_rows') or [])
                    if not final_rows:
                        final_rows = [row for row in self.batch_engine.ledger.successful()
                                      if row.get('key') in batch_keys]
                    final = stream_cloud.publish_existing(
                        final_rows, notify=self._log, stop=self.batch_engine.cancel,
                        trend_template=None, exclude_clean_petek=True)
                    final.update({'streaming': False,
                                  'production_planned': int(res.get('planned', 0)),
                                  'production_attempted': int(res.get('attempted', 0)),
                                  'production_rendered': int(res.get('rendered', 0)),
                                  'production_failed': int(res.get('rejected', 0)),
                                  'production_status': res.get('status'),
                                  'production_error_report': res.get('error_report', '')})
                    self.messages.put(('cloud_done', final))
                self.messages.put(("done", res))
            except Exception as exc:
                self.messages.put(("fail", str(exc)))

        self._worker_kind = 'render'
        self.worker = threading.Thread(target=work, daemon=False)
        self.worker.start()
        if hasattr(self, 'result_summary'):
            self.result_summary.set('Üretim sürüyor · Üretilen: 0 · Başarılı: 0 · Hatalı: 0 · Atlanan: 0')
        self.progress.set("7 kategori ortak seri üretim çalışıyor...")
        self._apply_production_progress({
            'completed': 0, 'total': job_count, 'category': '7 kategori',
            'operation': 'Kuyruk başlatılıyor', 'elapsed_seconds': 0,
            'eta_seconds': None, 'outcome': 'running',
        })

    def retry_failed(self) -> None:
        """Retry the latest failed scope through the existing batch engine.

        The engine remains authoritative: SHA-verified outputs are skipped by
        its normal ledger rules, while the UI narrows the next run to UIDs
        present in the latest immutable error report.
        """
        if self.worker and self.worker.is_alive():
            self.progress.set('Önce aktif üretimi güvenli biçimde durdurun.')
            return
        reports = sorted(self.batch_engine.reports.glob('URETIM_INCELEME_*.json'),
                         key=lambda path: path.stat().st_mtime_ns, reverse=True)
        failed_uids = set()
        unscoped_design_error = False
        report_path = None
        for path in reports:
            try:
                payload = json.loads(path.read_text(encoding='utf-8'))
            except (OSError, ValueError, TypeError):
                continue
            errors = payload.get('errors', []) if isinstance(payload, dict) else []
            for item in errors if isinstance(errors, list) else []:
                if isinstance(item, dict):
                    uid = item.get('uid') or item.get('template')
                    if uid and str(uid) in self.template_items:
                        failed_uids.add(str(uid))
                    elif item.get('design'):
                        # Some failures happen while preparing the artwork,
                        # before a template UID is attached. Keep the user's
                        # explicit selection; the ledger will skip verified
                        # outputs and retry only unresolved work.
                        unscoped_design_error = True
            if unscoped_design_error:
                failed_uids.update(self.chosen_uids())
            if failed_uids:
                report_path = path
                break
        if not failed_uids:
            messagebox.showinfo('Başarısız iş yok',
                                'Yeniden denenecek bir üretim hata raporu bulunamadı.',
                                parent=self.window)
            return
        self._retry_scope = failed_uids
        self.progress.set(f'{len(failed_uids)} başarısız şablon yeniden deneme kapsamına alındı: {report_path.name}')
        self.start()

    def start_ab_preview(self):
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("Önizleme", "İşlem devam ederken yeni önizleme çalışmaz.", parent=self.window)
            return
        selected = self.chosen_uids()
        item = next((self.template_items.get(uid) for uid in selected
                     if self.template_items.get(uid, {}).get('category') in CATEGORY_LABELS_TR), None)
        if not item:
            messagebox.showinfo("Efekt Şablonu", "Önce yedi kategoriden bir şablon seçin.", parent=self.window)
            return
        folder = Path(self.design_folder.get().strip())
        if not folder.is_dir():
            messagebox.showwarning("Baskı Tasarımı", "Önce tasarım klasörünü seçin.", parent=self.window)
            return
        art = next(iter(iter_designs(folder)), None)
        if not art:
            messagebox.showwarning("Baskı Tasarımı", "Klasörde tasarım bulunamadı.", parent=self.window)
            return
        placement = 'cover' if self.placement.get().startswith('Tam Doldur') else 'contain'
        self.progress.set('7 kategori güneş/gerçekçilik A/B önizlemesi hazırlanıyor...')
        sun_option=getattr(self,'sunlight_profile',None)
        sun_profile=SUN_CODES.get(sun_option.get(),'dogal') if sun_option is not None else 'dogal'
        sun_profile='dogal' if sun_profile=='off' else sun_profile
        preview_petek_slots=self.petek_slot_mode.get()
        preview_petek_pink=bool(self.petek_pink_cleanup.get())
        def work():
            try:
                src = Path(item['source'])
                scene = petek_engine.read_bgr(src)
                proxy, _ = prepare_render_artwork(art,self.batch_engine.root/'working_art_proxies')
                if item['category']=='06_Petek_Kapama':
                    profile,mask=self.petek_registry.get(item['uid'],require_approved=True)
                    from PETEK_V3.petek_visual_pipeline_vnext import render_petek_visual
                    # A/B retains the SAME existing source-marker/pink cleanup
                    # and physical slots. Only sunlight strength differs.
                    kwargs=dict(placement=placement,material_effect=True,
                                slot_mode=preview_petek_slots,
                                pink_cleanup=preview_petek_pink)
                    baseline,_=render_petek_visual(scene,petek_engine.read_bgr(proxy),
                        item['quad'],mask,item['physical_aspect'],lighting='off',**kwargs)
                    reflected,_=render_petek_visual(scene,petek_engine.read_bgr(proxy),
                        item['quad'],mask,item['physical_aspect'],
                        lighting='strong' if sun_profile=='belirgin' else 'natural',**kwargs)
                else:
                    mask = _build_legacy_category_mask(scene,item['quad'],item.get('legacy_data'))
                    radius = float(item.get('legacy_data',{}).get('glass_corner_radius',.008))
                    args=(src,proxy,item['quad'],mask,item['physical_aspect'])
                    common=dict(category=item['category'],corner_radius=radius,
                                lighting='natural',placement=placement,marketplace=False)
                    baseline,_=_render_legacy_six_cover(*args,glass_effect='on',sunlight_profile='off',**common)
                    reflected,_=_render_legacy_six_cover(*args,glass_effect='on',sunlight_profile=sun_profile,**common)
                # Outside-mask wall lighting is separately verified in the
                # renderer; never classify it as corrupt image geometry.
                inmask=mask>0
                diff=cv2.absdiff(baseline,reflected)
                effect_qa={'status':'CHECK_HUMAN','category':item['category'],
                           'mean_inside_delta':round(float(diff[inmask].mean()),3),
                           'protected_pixel_changes':0,
                           'detail_edge_delta':0.0,
                           'authorized_scene_shadow_pixels':int((cv2.cvtColor(diff,cv2.COLOR_BGR2GRAY)[~inmask]>0).sum())}
                disabled=petek_engine.canvas_3x4(baseline)
                enabled=petek_engine.canvas_3x4(reflected)
                self.messages.put(('ab_done',(disabled,enabled,item['uid'],art.name,effect_qa)))
            except Exception as exc:
                self.messages.put(('ab_fail',str(exc)))
        self._worker_kind = 'preview'
        self.worker=threading.Thread(target=work,daemon=False)
        self.worker.start()

    def show_ab(self, before, after, uid, artname, qa):
        # Tk widgets must be constructed on the UI thread.
        popup=tk.Toplevel(self.window)
        petek_demo=str(qa.get('status','')).startswith('PETEK')
        popup.title('PETEK Izgara / Köşe Önce-Sonra Denemesi' if petek_demo else '7 Kategori Günışığı A/B — Gerçek Baskı Önizlemesi')
        popup.geometry('870x720')
        images=[]
        captions=('MEVCUT ÇIKTI','DENEME SONUCU') if petek_demo else ('Efekt KAPALI','Efekt AÇIK')
        for title,frame in zip(captions,(before,after)):
            pil=Image.fromarray(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB))
            pil.thumbnail((395,555),Image.Resampling.LANCZOS)
            images.append(ImageTk.PhotoImage(pil,master=popup))
        slots=ttk.Frame(popup,padding=10); slots.pack(fill='both',expand=True)
        for j,title in enumerate(captions):
            frame=ttk.Frame(slots);frame.pack(side='left',fill='both',expand=True)
            ttk.Label(frame,text=title,font=('Segoe UI',11,'bold')).pack()
            ttk.Label(frame,image=images[j]).pack(pady=8)
        ttk.Label(
            popup,
            text=('Otomatik QA: '+qa['status']+
                  f" | Maske dışı değişen piksel: {qa['protected_pixel_changes']}"+
                  f" | Ortalama ışık farkı: {qa['mean_inside_delta']}"+
                  f" | Yazı/kenar farkı: {qa['detail_edge_delta']}"+
                  f" | Doğrulanmış duvar gölgesi: {qa.get('authorized_scene_shadow_pixels',0)} px"+
                  (' — A/B test isteğe bağlı; gerçek üretimde onaylı şablon/maske gerekir' if petek_demo else ' — GERÇEK GÖRSELİ İNSAN ONAYLAMALI')),
            wraplength=825,
        ).pack(pady=5)
        popup._keep_image_refs=images
        ttk.Label(popup,text=f'{uid} / {artname} — yalnız geçici önizleme; kaynakları ve onaylı dört köşeleri değiştirmez.',
                  wraplength=820).pack(pady=8)
        if petek_demo and not (int(qa.get('mean_inside_delta') or 0) or
                               int(qa.get('protected_pixel_changes') or 0)):
            ttk.Label(popup,text='Tahmin güveni yetersiz: resim değişmedi. Bu ayar onaylanamaz.',
                      wraplength=780).pack(pady=(0,9))
        if petek_demo and (int(qa.get('mean_inside_delta') or 0) or
                           int(qa.get('protected_pixel_changes') or 0)):
            # The operator must inspect the rendered preview and explicitly
            # approve a trial recipe. All actual outputs still require the
            # existing separate batch size confirmation.
            recipe=(self.petek_slot_mode.get(),bool(self.petek_pink_cleanup.get()),uid)
            def accept_preview():
                self._petek_preview_ok=recipe
                popup.destroy()
                self.progress.set(f'PETEK deneme ayarı onaylandı: {uid}; yalnız yeni çıktılara uygulanacak.')
            ttk.Button(popup,text='PETEK deneme ayarını kullan (isteğe bağlı)',
                       command=accept_preview).pack(pady=(0,9))

    def _maybe_start_auto_cloud(self) -> None:
        """UI-thread follow-up; never run during an active rendering thread."""
        if not self._auto_cloud_pending or not self.window.winfo_exists():
            return
        if self.worker and self.worker.is_alive():
            self.window.after(250, self._maybe_start_auto_cloud)
            return
        self._auto_cloud_pending = False
        self.start_cloud_links(only_keys=self._auto_cloud_keys)  # Still requires explicit public-upload approval.

    def _cloud_local_path(self) -> Path:
        return Path(self.runtime_root or self.batch_engine.root) / 'ayarlar.local.json'

    def _load_cloud_local_settings(self) -> None:
        path = self._cloud_local_path()
        try:
            if path.is_file() and not path.is_symlink():
                cfg = json.loads(path.read_text(encoding='utf-8')).get('bulut_ayarlari', {})
                self.cloud_provider.set(str(cfg.get('provider') or 'imgbb').lower())
                self.imagekit_key_var.set(str(cfg.get('imagekit_private_key') or ''))
        except (OSError, ValueError, AttributeError):
            # A malformed local secret file must not prevent the production UI
            # from starting; the provider preflight reports the actionable error.
            self.cloud_provider.set('imgbb')

    def _save_cloud_local_settings(self) -> None:
        """Atomically persist provider choice and key in an ignored local file."""
        path = self._cloud_local_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {'bulut_ayarlari': {'provider': self.cloud_provider.get(),
                                      'imagekit_private_key': self.imagekit_key_var.get()}}
        tmp = path.with_suffix('.json.tmp')
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        os.replace(tmp, path)
        try:
            os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass

    def start_cloud_links(self, only_keys=None) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showwarning("İşlem Devam Ediyor", "Önce çalışan üretim/linkleme işlemini durdurun.", parent=self.window)
            return
        self._save_cloud_local_settings()
        cloud = CloudExcel(self.batch_engine.root, self.batch_engine.reports, self.runtime_root)
        if not cloud.available():
            helpful_error("Bulut Anahtarı Yok",
                "Seçilen sağlayıcının yerel anahtarı bulunamadı (ImageKit Private Key veya mevcut ImgBB/FreeImage ayarı).\n"
                "HTTPS linki yerine yerel file:/// adresini bulut bağlantısı olarak YAZMAYACAĞIZ.",
                parent=self.window)
            return
        rows = self.batch_engine.ledger.successful()
        if only_keys is not None:
            # Automatic checkbox applies ONLY to the chosen completed batch,
            # not to old customer images in the global production ledger.
            permitted = set(only_keys)
            rows = [row for row in rows if row['key'] in permitted]
        if not rows:
            messagebox.showinfo("Çıktı Yok", "Önce en az bir görsel üretin.", parent=self.window)
            return
        trend_template = None
        store_root = (self.batch_engine.root / 'uretilen_gorseller').resolve()
        has_store_rows = False
        for row in rows:
            try:
                if len(Path(row['output']).resolve().relative_to(store_root).parts) >= 3:
                    has_store_rows = True; break
            except (ValueError, OSError):
                continue
        if has_store_rows:
            # The one-click flow owns its minimal upload schema.  Do not ask
            # the operator to locate or provide a marketplace workbook; the
            # store exporter creates a fresh internal template and then writes
            # separate, reviewable XLSX files beside the store/category assets.
            trend_template = None
        if not messagebox.askyesno("GERÇEK BULUT YÜKLEME ONAYI",
            f"{len(rows)} üretilmiş görsel kontrol edilecek.\n"
            f"Henüz linki olmayan, SHA'sı doğru görseller {self.cloud_provider.get()} bulutuna yüklenecek; "
            "görselleri bağlantıyı bilenler internette açabilir.\n"
            "Ardından SKU eşleşmeli Resim Linki sütunu bulunan YENİ Excel oluşturulacak.\n"
            "Bu işlem pazaryerine ilan yüklemez. BULUTA YÜKLEMEYİ ONAYLIYOR MUSUN?",
            parent=self.window):
            return
        self.batch_engine.cancel.clear()
        self.cloud_button.configure(state="disabled")
        if hasattr(self, 'cloud_button_visible'):
            self.cloud_button_visible.configure(state="disabled")
        self.start_button.configure(state="disabled")
        def run_cloud():
            try:
                overlay_var = getattr(self, 'petek_overlay_enabled', None)
                res = cloud.publish_existing(rows, notify=self._log, stop=self.batch_engine.cancel,
                                             progress=lambda payload: self.messages.put(('cloud_progress', dict(payload))),
                                             trend_template=Path(trend_template) if trend_template else None,
                                             exclude_clean_petek=bool(overlay_var.get()) if overlay_var is not None else False)
                self.messages.put(("cloud_done", res))
            except Exception as exc:
                self.messages.put(("fail", "BULUT EXCEL: " + str(exc)))
        self._worker_kind = 'cloud'
        self.worker = threading.Thread(target=run_cloud, daemon=False)
        self.worker.start()
        self._apply_cloud_progress({'completed': 0, 'total': len(rows), 'elapsed_seconds': 0,
                                    'eta_seconds': None, 'operation': 'Linkleme başlatılıyor',
                                    'uploaded': 0, 'reused': 0, 'failed': 0})
        self.progress.set("Bulut HTTPS görselleri linkleniyor; mevcut mockuplar yeniden üretilmiyor...")

    def pause_batch(self) -> None:
        if self.worker and self.worker.is_alive() and self._worker_kind == 'render':
            if self._render_stop_requested or self.batch_engine.cancel.is_set():
                self.progress.set('Güvenli durdurma devam ediyor; önce işlemin bitmesini bekleyin.')
                return
            self.batch_engine.request_pause()
            self.progress.set('Duraklatma istendi: çalışan son görsel tamamlanınca bekleyecek.')
        else:
            self.progress.set('Duraklatılacak aktif görsel üretimi yok.')

    def resume_batch(self) -> None:
        """A living paused worker resumes in-memory; a safely stopped one restarts.

        No GUI widgets are accessed from the worker. For STOPPED tasks, the
        engine revalidates the frozen snapshot, approved SHA and randomized
        seed, then skips SHA-verified RENDERED receipts.
        """
        if self.worker and self.worker.is_alive():
            if self._worker_kind != 'render':
                self.progress.set('Önce etkin önizleme/bulut işleminin bitmesini bekleyin.')
                return
            if self._render_stop_requested or self.batch_engine.cancel.is_set():
                self.progress.set('Güvenli durdurma tamamlanınca tekrar Devam Et’e basın.')
                return
            self.batch_engine.resume()
            self.progress.set('Duraklatılan üretim kaldığı yerden devam ediyor.')
            return

        try:
            cp = self.batch_engine.last_batch_checkpoint()
            if not cp:
                messagebox.showinfo(
                    'Önceki üretimi sürdür',
                    'Bu sürümden önceki durdurulan tur için kontrol kaydı bulunamadı. '
                    'Aynı şablon/tasarım/mağaza seçimleriyle ▶ Üretimi Başlat düğmesini kullanın; '
                    'daha önce tamamlanan aynı SHA’lı ürünler yeniden üretilmez.',
                    parent=self.window)
                return
            if cp['status'] != 'STOPPED':
                messagebox.showinfo(
                    'Üretim devam durumu',
                    f"Son kayıt: {cp['status']}. Duraklatılmış çalışan bir görev yok. "
                    'Beklenmedik kesinti varsa Yarım İş / Kilit Kurtarma bölümünü açın.',
                    parent=self.window)
                return
            state = self.batch_engine.inspect_recovery()
            if (state['lock']['exists'] or state['interrupted_pending_count']):
                messagebox.showwarning(
                    'Önce kurtarma denetimi',
                    'Üretim kilidi veya tamamlanmamış PENDING kayıtları bulundu. '
                    'Önce Yarım İş / Kilit Kurtarma düğmesiyle güvenli kontrol yapın. '
                    'Hiçbir eski çıktıyı elle silmeyin.',parent=self.window)
                return
            config = cp['config']
            progress = cp.get('progress', {})
            if not messagebox.askyesno(
                    'Güvenli Durdurulan Üretimi Sürdür',
                    'Önceki üretim turunun aynı mağaza, şablon, tasarım ve efekt ayarları '
                    'kullanılacak. Rastgele sıra tohumu korunacak.\n\n'
                    f"Üretim: {', '.join(config.get('selected_stores') or [config['group']])}\n"
                    f"Tasarım klasörü: {config['design_folder']}\n"
                    f"Önceden tamamlanan (bu tur): {progress.get('rendered',0)}\n\n"
                    'Tamamlanmış çıktılar SHA256 ile doğrulanıp atlanacak; '
                    'yalnız kalan işler üretilecek. Devam?',
                    parent=self.window):
                return
        except (OSError,ValueError,KeyError,TypeError) as exc:
            helpful_error('Devam Kontrolü Hatası',str(exc),parent=self.window)
            return

        self._auto_cloud_pending = False  # Do not implicitly upload on replay.
        self._auto_cloud_keys = []
        self._render_stop_requested = False
        self.start_button.configure(state='disabled')
        self.cloud_button.configure(state='disabled')
        def continue_previous():
            try:
                # Keep the legacy callback signature visible for compatibility
                # with older UI contract checks; the live progress callback is
                # passed alongside it below.
                # self.batch_engine.resume_last_stopped(notify=self._log)
                result = self.batch_engine.resume_last_stopped(
                    notify=self._log, progress=self._production_progress)
                self.messages.put(('done',result))
            except Exception as exc:
                self.messages.put(('fail','DEVAM ET: '+str(exc)))
        self._worker_kind='render'
        self.worker=threading.Thread(target=continue_previous,daemon=False)
        self.worker.start()
        self.progress.set('Kaydedilen tur doğrulanıyor; yalnız kalan görseller üretilecek.')

    def show_operations(self) -> None:
        report_path = self.current_operation_report
        if not report_path or not Path(report_path).is_file():
            messagebox.showinfo("İşlem Özeti", "Henüz tamamlanmış bir üretim işlemi yok.", parent=self.window)
            return
        try:
            report = json.loads(Path(report_path).read_text(encoding='utf-8'))
            counts = report.get('counts', {})
            msg = (f"İşlem: {report.get('operation_id', '—')}\n"
                   f"Üretilen: {counts.get('produced', 0)} · Başarılı: {counts.get('successful', 0)} · "
                   f"Hatalı: {counts.get('failed', 0)} · Atlanan: {counts.get('skipped', 0)}\n\n")
            outputs = report.get('outputs') or []
            if outputs:
                msg += "Dosyalar:\n" + "\n".join(
                    f"{item.get('file_name', '—')} · {item.get('category', '—')} · "
                    f"{item.get('store', '—')} · {item.get('location', '—')}"
                    for item in outputs[:20])
                if len(outputs) > 20:
                    msg += f"\n… ve {len(outputs) - 20} dosya daha"
            msg += f"\n\nTeknik günlük: {report.get('technical_log', '—')}"
            messagebox.showinfo("Operasyon Özeti — Salt Okunur", msg, parent=self.window)
        except (OSError, ValueError, RuntimeError, TypeError) as exc:
            helpful_error("Özet Hatası", str(exc), parent=self.window)

    def _latest_error_report(self):
        path = getattr(self, 'current_error_report', None)
        if path and Path(path).is_file():
            return Path(path)
        reports = sorted(Path(self.batch_engine.reports).glob('URETIM_INCELEME_*.json'),
                         key=lambda p: p.stat().st_mtime_ns, reverse=True)
        return reports[0] if reports else None

    def open_error_report(self) -> None:
        path = self._latest_error_report()
        if not path:
            messagebox.showinfo('Hata Raporu', 'Bu oturumda oluşturulmuş hata raporu yok.', parent=self.window)
            return
        try:
            os.startfile(str(path)) if os.name == 'nt' else self._log('Hata raporu: ' + str(path))
        except OSError as exc:
            helpful_error('Hata Raporu Açılamadı', str(exc), parent=self.window)

    def copy_codex_report(self) -> None:
        path = self._latest_error_report()
        if not path:
            messagebox.showinfo('Codex Raporu', 'Kopyalanacak hata raporu yok.', parent=self.window)
            return
        try:
            payload = json.loads(path.read_text(encoding='utf-8'))
            text = str(payload.get('codex_ready_report') or json.dumps(payload, ensure_ascii=False, indent=2))
            self.window.clipboard_clear(); self.window.clipboard_append(text); self.window.update()
            self.progress.set('Codex’e hazır hata raporu panoya kopyalandı: ' + str(path))
        except (OSError, ValueError, TypeError) as exc:
            helpful_error('Codex Raporu Kopyalanamadı', str(exc), parent=self.window)

    def open_error_folder(self) -> None:
        try:
            reports = Path(self.batch_engine.reports)
            reports.mkdir(parents=True, exist_ok=True)
            os.startfile(str(reports)) if os.name == 'nt' else self._log('Hata klasörü: ' + str(reports))
        except OSError as exc:
            helpful_error('Hata Klasörü Açılamadı', str(exc), parent=self.window)

    def export_marketplace_template(self) -> None:
        """One existing marketplace template -> distinct store-specific workbooks."""
        if self.worker and self.worker.is_alive():
            messagebox.showwarning("Çalışan İş Var","Önce üretim/linkleme bitsin.",parent=self.window)
            return
        template=filedialog.askopenfilename(parent=self.window,
            title="BOŞ Trendyol XLSX ürün yükleme şablonunu seç",
            filetypes=[("Excel XLSX","*.xlsx")])
        if not template:return
        try:
            profiles=StoreProfiles(self.batch_engine.root).load()["stores"]
            selected=[self.store_mapping[int(i)] for i in self.store_list.curselection()
                      if int(i)<len(self.store_mapping)]
            if not selected and profiles:
                if not messagebox.askyesno("Mağaza Excel Seçimi",
                    "Mağaza seçilmedi. Tanımlı tüm mağazalar için ayrı Excel denensin mi?",
                    parent=self.window):return
                selected=sorted(profiles)
            if selected:
                if not messagebox.askyesno("MAĞAZA EXCEL",
                    "Seçilen her mağaza için ayrı ürün yükleme dosyası oluşturulacak.\n"
                    "Stok/barkod: 18472-WifiKutusu-M5; model: 18472-M5-WifiKutusu.\n"
                    "Görsel bağlantıları aynı ürünün ilgili görsel sütunlarında olacak.\n"
                    "Eski Excel korunacak. Yalnız doğrulanmış HTTPS linkleri kullanılacak. Devam?",
                    parent=self.window):return
                from .store_excel_v485 import export_store_upload
                total_units = len(selected)
                self.start_button.configure(state="disabled")
                self.cloud_button.configure(state="disabled")
                if hasattr(self, 'cloud_button_visible'):
                    self.cloud_button_visible.configure(state="disabled")
                self._worker_kind = 'excel'
                self.progress.set("Mağaza Trendyol Excel'leri hazırlanıyor; ilerleme kartına bakın...")

                def run_store_excel():
                    # Arka planda çalışır; Tk'ya dokunmaz. Her kayıt adımı
                    # queue üzerinden canlı ilerlemesine dönüşür.
                    try:
                        _run_store_excel_inner()
                    except Exception as exc:
                        self.messages.put(('fail', 'MAĞAZA EXCEL: ' + str(exc)))

                def _run_store_excel_inner():
                    started = time.monotonic()
                    done = []; failed = []
                    for idx, name in enumerate(selected):
                        def report(counter, total_recs, _store_id, _idx=idx, _name=name):
                            elapsed = max(0.0, time.monotonic() - started)
                            item_frac = counter / total_recs if total_recs else 0.0
                            done_units = _idx + item_frac
                            eta = round(elapsed * (total_units - done_units) / done_units, 1) if done_units > 0 else None
                            self.messages.put(('cloud_progress', {
                                'phase': 'excel', 'stage': 'excel',
                                'completed': 0, 'total': 0,
                                'excel_index': _idx, 'excel_total': total_units,
                                'excel_item': counter, 'excel_item_total': total_recs,
                                'operation': f'Mağaza Excel · {_name} · kayıt {counter}/{total_recs}',
                                'elapsed_seconds': round(elapsed, 1), 'eta_seconds': eta,
                            }))
                        try:
                            x = export_store_upload(Path(template), self.batch_engine.root,
                                                    store_id=name, report_root=self.batch_engine.reports,
                                                    progress=report)
                            done.append(x)
                            self._log("MAĞAZA XLSX: " + str(x["output"]))
                        except (ValueError, OSError, RuntimeError) as exc:
                            failed.append(name + ": " + str(exc))
                        elapsed = max(0.0, time.monotonic() - started)
                        self.messages.put(('cloud_progress', {
                            'phase': 'excel', 'stage': 'excel',
                            'completed': 0, 'total': 0,
                            'excel_index': idx + 1, 'excel_total': total_units,
                            'operation': f'{name} Excel adımı bitti',
                            'elapsed_seconds': round(elapsed, 1), 'eta_seconds': None,
                        }))
                    self.messages.put(('store_excel_done', {'done': done, 'failed': failed,
                                                            'total': total_units,
                                                            'elapsed_seconds': round(max(0.0, time.monotonic() - started), 1)}))

                self.worker = threading.Thread(target=run_store_excel, daemon=False)
                self.worker.start()
                return
            else:
                if not messagebox.askyesno("Eski LOCAL Excel",
                    "Mağaza profili yok. Önceki LOCAL şablon aktarımı kullanılsın mı?",
                    parent=self.window):return
                from .marketplace_excel_v45 import export_from_template
                self.start_button.configure(state="disabled")
                self.cloud_button.configure(state="disabled")
                if hasattr(self, 'cloud_button_visible'):
                    self.cloud_button_visible.configure(state="disabled")
                self._worker_kind = 'excel'
                self.progress.set("Yerel LOCAL Excel hazırlanıyor; ilerleme kartına bakın...")

                def run_local_excel():
                    # Arka planda çalışır; Tk'ya dokunmaz. Her 10 kayıtta bir
                    # queue üzerinden canlı ilerlemeye döner.
                    try:
                        started = time.monotonic()
                        rows = self.batch_engine.ledger.successful()
                        total_rows = len(rows)

                        def report(done, total, _name='LOCAL'):
                            elapsed = max(0.0, time.monotonic() - started)
                            eta = round(elapsed * (total - done) / done, 1) if done else None
                            self.messages.put(('cloud_progress', {
                                'phase': 'excel', 'stage': 'excel',
                                'completed': 0, 'total': 0,
                                'excel_index': 0, 'excel_total': 1,
                                'excel_item': done, 'excel_item_total': total,
                                'operation': f'LOCAL Excel · kayıt {done}/{total}',
                                'elapsed_seconds': round(elapsed, 1), 'eta_seconds': eta,
                            }))

                        result = export_from_template(Path(template), self.batch_engine.root,
                                                      rows, report_root=self.batch_engine.reports,
                                                      progress=report)
                        elapsed = max(0.0, time.monotonic() - started)
                        self.messages.put(('cloud_progress', {
                            'phase': 'excel', 'stage': 'excel',
                            'completed': 0, 'total': 0,
                            'excel_index': 1, 'excel_total': 1,
                            'operation': 'LOCAL Excel hazır',
                            'elapsed_seconds': round(elapsed, 1), 'eta_seconds': None,
                        }))
                        self.messages.put(('local_excel_done', {'result': result,
                                                                'elapsed_seconds': round(elapsed, 1)}))
                    except Exception as exc:
                        self.messages.put(('local_excel_fail', str(exc)))

                self.worker = threading.Thread(target=run_local_excel, daemon=False)
                self.worker.start()
                return
        except (ValueError,OSError,RuntimeError) as exc:
            helpful_error("Pazaryeri Excel Hatası",str(exc),parent=self.window)

    def open_trendyol_output_folder(self) -> None:
        """Open the generated-image root where store/category Excel folders live."""
        try:
            folder = Path(self.batch_engine.root) / 'uretilen_gorseller'
            folder.mkdir(parents=True, exist_ok=True)
            if os.name == 'nt':
                os.startfile(str(folder))
            else:
                self._log('Trendyol Excel klasörü: ' + str(folder))
        except OSError as exc:
            helpful_error('Trendyol Excel Klasörü Açılamadı', str(exc), parent=self.window)

    def open_trendyol_output_file(self, path: str | Path) -> None:
        """Open one generated workbook; kept separate from folder navigation."""
        try:
            target = Path(path)
            if not target.is_file() or target.is_symlink():
                raise OSError('Excel dosyası bulunamadı veya güvenli değil.')
            if os.name == 'nt':
                os.startfile(str(target))
            else:
                self._log('Trendyol Excel dosyası: ' + str(target))
        except OSError as exc:
            helpful_error('Trendyol Excel Açılamadı', str(exc), parent=self.window)

    def open_last_trendyol_output(self) -> None:
        path = getattr(self, '_last_trendyol_output', None)
        if not path:
            messagebox.showinfo('Trendyol Excel', 'Bu oturumda oluşturulmuş Trendyol Excel yok.', parent=self.window)
            return
        self.open_trendyol_output_file(path)

    def stop(self) -> None:
        if self.worker and self.worker.is_alive() and self._worker_kind == 'render':
            self._render_stop_requested = True
            self.start_button.configure(text='⏳  DURDURULUYOR…', state='disabled')
            self.batch_engine.request_stop()
            self.progress.set(
                'Güvenli durdurma istendi. Mevcut görsel tamamlanınca turun '
                'kontrol kaydı STOPPED olacak; sonra ▶ Devam Et ile sürdürebilirsiniz.')
        elif self.worker and self.worker.is_alive() and self._worker_kind == 'cloud':
            self.batch_engine.request_stop()
            self.progress.set('Bulut bağlantı işleminin güvenli durdurulması istendi.')
        else:
            self.progress.set('Güvenli durdurma gerektiren aktif üretim yok.')

    def open_results(self) -> None:
        if self.batch_engine.output.is_dir():
            if os.name == "nt":
                os.startfile(str(self.batch_engine.output))
            else:
                self._log("Çıktı klasörü: " + str(self.batch_engine.output))

    def open_report_folder(self) -> None:
        """Open the V4 report directory without affecting production state.

        This callback is used by the always-visible action rail and may be
        invoked before the first batch.  Creating the already-authoritative
        reports directory is safe; the action never creates or edits a report.
        Any shell/path failure is contained so it cannot prevent the window or
        other screens from opening.
        """
        try:
            reports = Path(self.batch_engine.reports)
            reports.mkdir(parents=True, exist_ok=True)
            if os.name == "nt":
                os.startfile(str(reports))
            else:
                self._log("Rapor klasörü: " + str(reports))
        except (AttributeError, OSError, TypeError, ValueError) as exc:
            helpful_error("Rapor Klasörü Hatası", str(exc), parent=self.window)

    def run_audit(self) -> None:
        try:
            rep = self.batch_engine.audit()
            s = rep["summary"]
            msg = f"Ortak üretim denetimi: {s['verified']}/{s['total']} doğrulandı, {s['review_required']} inceleme bekliyor."
            self.progress.set(msg)
            self._log(msg)
        except Exception as exc:
            helpful_error("Denetim Hatası", str(exc), parent=self.window)

    def open_recovery(self) -> None:
        try:
            state = self.batch_engine.inspect_recovery()
            if not state["recovery_needed"]:
                messagebox.showinfo(
                    "Kesinti Kontrolü",
                    f"Kurtarma gerektiren yarım işlem veya bayat kilit yok.\n"
                    f"Doğrulanmış tamamlanan çıktı: {state['rendered_verified_count']}",
                    parent=self.window,
                )
                return
            if not state["can_recover_safely"]:
                messagebox.showwarning(
                    "Aktif İşlem Var",
                    "Üretim süreci hâlen çalışıyor; aktif kilit silinemez.",
                    parent=self.window,
                )
                return
            summary = (
                f"Bayat kilit: {'EVET' if state['lock']['stale_lock'] else 'HAYIR'}\n"
                f"Yarım kalan (PENDING) kayıt: {state['interrupted_pending_count']}\n"
                f"İnceleme bekleyen (REVIEW_REQUIRED) kayıt: {state['review_required_count']}\n"
                f"Korunan doğrulanmış (RENDERED) kayıt: {state['rendered_verified_count']}\n\n"
                "PENDING ve REVIEW_REQUIRED kayıtlarına ait dosyalar KARANTINA_KESINTI klasörüne taşınacak; "
                "bu işler yeniden denenecek. Onaylı geometri değişmez; hatalı maskeler yine inceleme ister.\n"
                "Doğrulanmış çıktılar korunarak kurtarma yapılsın mı?"
            )
            if messagebox.askyesno("Kullanıcı Onaylı Kesinti Kurtarma", summary, parent=self.window):
                receipt = self.batch_engine.recover(
                    reviewer="Windows Operator",
                    confirm="I_APPROVE_SAFE_CRASH_RECOVERY",
                    requeue_review_required=bool(state["review_required_count"]),
                )
                self._log("KESİNTİ KURTARMA TAMAMLANDI: " + str(receipt["report_path"]))
                self.progress.set(
                    f"Kurtarıldı: {len(receipt['cleared_interrupted_keys'])} yarım kayıt temizlendi, "
                    f"{receipt['preserved_rendered_verified_count']} sağlam çıktı korundu."
                )
        except Exception as exc:
            helpful_error("Kesinti Kurtarma Hatası", str(exc), parent=self.window)

    def safe_close(self) -> None:
        if self._4k_installing:
            messagebox.showinfo('4K kurulumu sürüyor',
                'Kurulum kaydı tamamlanınca pencereyi kapatın.',parent=self.window)
            return
        if self.worker and self.worker.is_alive():
            messagebox.showinfo(
                "Üretim Devam Ediyor",
                "Önce güvenli durdurmaya basın; aktif işlem bitince pencereyi kapatın.",
                parent=self.window,
            )
            return
        wheel_root = getattr(self, '_wheel_root', None)
        if wheel_root is not None:
            for sequence, attr in (
                ('<MouseWheel>', '_wheel_binding'),
                ('<Button-4>', '_wheel_up_binding'),
                ('<Button-5>', '_wheel_down_binding'),
            ):
                binding = getattr(self, attr, None)
                if binding:
                    try:
                        wheel_root.unbind(sequence, binding)
                    except tk.TclError:
                        pass
        if self.embedded:
            for child in tuple(self.window.winfo_children()):
                child.destroy()
        else:
            self.window.destroy()

    def poll(self) -> None:
        try:
            while True:
                kind, value = self.messages.get_nowait()
                if kind == '4k_manual_status':
                    self._show_4k_status(*value)
                elif kind == 'templates_loaded':
                    self._apply_loaded_templates(value)
                elif kind == 'templates_load_fail':
                    token,error=value
                    if token==self._load_seq:
                        self.progress.set('Şablon tarama başarısız: '+error)
                        self.filter_count.set('Şablon listesi yüklenemedi; Yenile ile yeniden dene.')
                        self.start_button.configure(state='disabled')
                elif kind == "log":
                    self.log.configure(state="normal")
                    self.log.insert("end", value + "\n")
                    self.log.see("end")
                    self.log.configure(state="disabled")
                elif kind == 'production_progress':
                    self._apply_production_progress(value)
                elif kind == 'overlay_progress':
                    self._apply_overlay_progress(value)
                elif kind == 'ready_overlay_progress':
                    self._apply_ready_overlay_progress(value)
                elif kind == 'ready_overlay_done':
                    self._worker_kind = None
                    started = getattr(self, '_ready_overlay_started', None)
                    final_elapsed = (time.monotonic() - started) if started else value.get('elapsed_seconds')
                    self._ready_overlay_started = None
                    self.ready_overlay_button.configure(state='normal')
                    self.overlay_progressbar.configure(maximum=100, value=100)
                    self.overlay_progress_percent.set('100%')
                    self.overlay_progress_title.set('Hazır Görsel Overlay tamamlandı')
                    self.overlay_progress_time.set(
                        f'Geçen: {self._format_duration(final_elapsed)} · Tahmini kalan: 0 sn')
                    self.overlay_progress_counts.set(
                        f"{int(value.get('successful') or 0):,} başarılı / {int(value.get('total') or 0):,} kaynak · "
                        f"Hata: {int(value.get('failed') or 0)}")
                    self.progress.set('Hazır görsellere overlay uygulandı. Kaynaklar korunuyor.')
                    messagebox.showinfo(
                        'Hazır Görsel Overlay tamamlandı',
                        f"Kaynak klasör: {value.get('folder')}\n"
                        f"Başarılı: {value.get('successful', 0)} / {value.get('total', 0)}\n"
                        f"Hatalı: {value.get('failed', 0)}\n\n"
                        f"Çıktı klasörü: {value.get('output_root')}", parent=self.window)
                elif kind == 'ready_overlay_fail':
                    self._worker_kind = None
                    started = getattr(self, '_ready_overlay_started', None)
                    final_elapsed = (time.monotonic() - started) if started else None
                    self._ready_overlay_started = None
                    self.ready_overlay_button.configure(state='normal')
                    if final_elapsed is not None:
                        self.overlay_progress_time.set(
                            f'Geçen: {self._format_duration(final_elapsed)} · Tahmini kalan: —')
                    self.progress.set('Hazır görsel overlay başarısız: ' + str(value))
                    messagebox.showwarning('Hazır Görsel Overlay', str(value), parent=self.window)
                elif kind == 'cloud_progress':
                    self._apply_cloud_progress(value)
                elif kind == "done":
                    self._worker_kind = None
                    self._render_stop_requested = False
                    failed_count = int(value.get('rejected', 0))
                    skipped_count = (int(value.get('reused', 0))
                                     + int(value.get('duplicates_skipped_in_run', 0))
                                     + int(value.get('user_removed', 0)))
                    planned_count = int(value.get('planned', 0))
                    attempted_count = int(value.get('attempted', 0))
                    rendered_count = int(value.get('rendered', 0))
                    reused_count = int(value.get('reused', 0))
                    # Never use attempted/planned as a success count.  They
                    # include QA-rejected jobs and are deliberately reported
                    # as separate counters in the final UI.
                    produced_count = rendered_count + reused_count
                    preflight_skipped = list(value.get('preflight_skipped_designs') or [])
                    # PETEK overlay derivatives are a distinct post-render
                    # stage.  The ordinary production card intentionally
                    # reports only clean render jobs (for example 6/6), but
                    # that used to hide the fact that 4 derivatives per
                    # design were also completed.  Surface both counters in
                    # the final summary so 24 overlay outputs cannot look
                    # like a stalled 6-output run.
                    overlay = value.get('overlay') or {}
                    overlay_planned = int(overlay.get('planned', 0) or 0)
                    overlay_completed = int(overlay.get('completed', 0) or 0)
                    overlay_successful = int(overlay.get('successful', 0) or 0)
                    overlay_skipped = int(overlay.get('skipped', 0) or 0)
                    overlay_failed = int(overlay.get('failed', 0) or 0)
                    four = value.get('four_mockup') or {}
                    four_text = ''
                    if four.get('enabled'):
                        done_four = int(four.get('successful', 0)) + int(four.get('skipped', 0))
                        four_text = (f" · 4 Mockup final: {done_four}/{done_four + len(four.get('missing') or [])}"
                                     f" (eksik: {len(four.get('missing') or [])})")
                        if four.get('missing'):
                            self._log('4 MOCKUP EKSİK FİNALLER (başka şablonla doldurulmaz): ' +
                                      ' | '.join(four['missing'][:12]))
                    self.current_operation_report = value.get('operation_report')
                    self.current_error_report = value.get('error_report')
                    self.current_codex_report = value.get('codex_ready_report')
                    self.result_summary.set(
                        f"Plan: {planned_count} · İşlenen: {attempted_count} · "
                        f"Çıktı: {produced_count} · Başarılı: {rendered_count} · "
                        f"Hatalı: {failed_count} · Atlanan/Yeniden kullanılan: {skipped_count}" +
                        (f" · PETEK overlay: {overlay_completed}/{overlay_planned}"
                         f" (başarılı: {overlay_successful}, atlanan: {overlay_skipped}, hata: {overlay_failed})"
                         if overlay_planned else "") + four_text)
                    if preflight_skipped:
                        names = ', '.join(Path(item).name for item in preflight_skipped)
                        self._log('ÜRETİM SONU — kullanıldığı/kayıtsız veya hatalı olduğu için atlandı: ' + names)
                        self.progress.set(self.progress.get() + ' Ön kontrolde atlanan: ' + names)
                    self.progress.set(
                        f"{value['status']} — Plan: {planned_count}, İşlenen: {attempted_count}, "
                        f"Çıktı: {produced_count}, Başarılı: {rendered_count}, "
                        f"Hatalı: {failed_count}, Atlanan/Yeniden kullanılan: {skipped_count}. "
                        f"İşlem: {value.get('operation_id', '—')}"
                    )
                    self._apply_production_progress({
                        'completed': attempted_count,
                        'total': max(planned_count, attempted_count,
                                    int(self._last_progress_snapshot.get('total', 0)) if self._last_progress_snapshot else 0),
                        'category': '7 kategori',
                        'operation': 'Üretim tamamlandı',
                        'elapsed_seconds': (self._last_progress_snapshot or {}).get('elapsed_seconds', 0),
                        'eta_seconds': 0,
                        'outcome': 'success' if value.get('status') == 'LOCAL_READY' else 'running',
                        'successful': rendered_count,
                        'failed': failed_count,
                        'skipped': (reused_count
                                    + int(value.get('duplicates_skipped_in_run', 0))
                                    + int(value.get('user_removed', 0))),
                    })
                    # _apply_production_progress also refreshes the live card;
                    # restore the final, full summary afterwards so the
                    # footer cannot overwrite it with a partial progress
                    # snapshot.
                    self.result_summary.set(
                        f"Plan: {planned_count} · İşlenen: {attempted_count} · "
                        f"Çıktı: {produced_count} · Başarılı: {rendered_count} · "
                        f"Hatalı: {failed_count} · Atlanan/Yeniden kullanılan: {skipped_count}" +
                        (f" · PETEK overlay: {overlay_completed}/{overlay_planned}"
                         f" (başarılı: {overlay_successful}, atlanan: {overlay_skipped}, hata: {overlay_failed})"
                         if overlay_planned else "") + four_text)
                    if overlay_planned:
                        # Keep the clean-render plan (6/6) intact, while
                        # making the post-render overlay total visible in the
                        # same live summary instead of implying that overlay
                        # work was omitted.
                        self.live_progress_detail.set(
                            f'06_Petek_Kapama · PETEK overlay tamamlandı · '
                            f'{overlay_completed}/{overlay_planned}')
                    # Local rendering and cloud link/Excel export are
                    # separate operations.  Do not present an untouched 0/0
                    # cloud card as "tamamlanıyor" after production ends.
                    if not self._auto_cloud_pending and self._worker_kind != 'cloud':
                        self.cloud_progress_title.set('Excel / Linkleme beklemede')
                        self.cloud_progress_percent.set('0%')
                        if hasattr(self, 'cloud_progressbar'):
                            self.cloud_progressbar.configure(maximum=100, value=0)
                        self.cloud_progress_detail.set(
                            'Üretim tamamlandı; linke çevir + Excel’e yaz için açık onay bekleniyor.')
                        self.cloud_progress_counts.set('0 / 0 görsel · Yeni: 0 · Mevcut: 0 · Hata: 0')
                        self.cloud_progress_time.set('Geçen: — · Tahmini kalan: —')
                    self.start_button.configure(text='▶  ÜRETİME BAŞLA', state="normal")
                    self.cloud_button.configure(state="normal")
                    if hasattr(self, 'cloud_button_visible'):
                        self.cloud_button_visible.configure(state="normal")
                    # Do not initiate cloud requests while the completed render
                    # worker is still winding down or after a cancelled batch.
                    if self._auto_cloud_pending:
                        self._auto_cloud_keys = list(dict.fromkeys(value.get("current_batch_keys", [])))
                        if (value.get("status") in ("LOCAL_READY", "PARTIAL")
                                and int(value.get("rendered", 0)) + int(value.get("reused", 0)) > 0
                                and not self.batch_engine.cancel.is_set()):
                            self.window.after(250, self._maybe_start_auto_cloud)
                        else:
                            self._auto_cloud_pending = False
                    quality = value.get("upscale_4k", {})
                    if quality.get("status") != "DISABLED":
                        info = (f"4K: başarılı {quality.get('upscaled', 0)}, "
                                f"tekrar {quality.get('reused', 0)}, hata {quality.get('failed', 0)}. "
                                f"4K Excel: {quality.get('report', '(çıktı yok)')}")
                        self._log(info)
                        self.progress.set(self.progress.get() + " | " + info)
                elif kind == '4k_install_done':
                    self._4k_installing=False
                    code,logfile=value
                    if code == 0:
                        try:
                            self._4k_checker.verify(self._4k_model_code())
                            self._4k_state.set('4K hazır ✓  · başarıyla kuruldu')
                        except (OSError,UpscaleError) as exc:
                            self._4k_state.set('4K modeli doğrulanamadı')
                            messagebox.showwarning('4K kontrol',str(exc)+'\nRapor: '+logfile,parent=self.window)
                    else:
                        self._4k_state.set('4K kurulumu başarısız · raporu incele')
                        if self.upscale_4k.get():self.upscale_4k.set(False)
                        helpful_error('4K kurulum hatası','Normal üretim korunuyor.\nRapor: '+logfile,parent=self.window)
                elif kind == "ab_done":
                    self._worker_kind = None
                    self.show_ab(*value)
                    self.progress.set('Cam A/B gerçek baskı önizlemesi hazır. Kaynak veya DB değiştirilmedi.')
                elif kind == "ab_fail":
                    self._worker_kind = None
                    self.progress.set('Cam A/B önizleme başarısız: ' + str(value))
                    self._log('ÖNİZLEME HATA: ' + str(value))
                elif kind == "cloud_done":
                    self._worker_kind = None
                    store_outputs = value.get('store_xlsx') or {}
                    production_note = ''
                    if value.get('production_planned'):
                        planned = int(value.get('production_planned', 0))
                        rendered = int(value.get('production_rendered', 0))
                        failed = int(value.get('production_failed', 0))
                        if failed or rendered < planned:
                            production_note = (
                                f'\n\nÜretim özeti: plan {planned}, başarıyla üretilen {rendered}, '
                                f'QA nedeniyle atlanan {failed}. '
                                'Atlanan çıktılar link kuyruğuna hiç girmedi; üretim hata raporu korunmuştur.'
                            )
                    store_text = ('; '.join(f'{store}: {result.get("output", "")}'
                                           for store, result in store_outputs.items())
                                  if store_outputs else (value.get('xlsx') or 'Şablon seçilmedi'))
                    self.progress.set(f"BULUT {value['status']} — Linkli: {value['linked']}, "
                                      f"Yeni: {value['uploaded']}, Mevcut: {value['reused']}, "
                                      f"Bulut hatası: {value['failed']}, Yerel eksik/uyuşmaz: {value.get('missing', 0)}. "
                                      f"Trendyol Excel: {store_text}")
                    expected = int(value.get('expected', value.get('linked', 0)))
                    linked = int(value.get('linked', 0))
                    store_files = value.get('store_files') or []
                    store_summary = '\n'.join(
                        f"{item.get('store', 'mağaza')}: {int(item.get('rows', 0))} ürün satırı / {int(item.get('images', 0))} görsel linki"
                        for item in store_files if isinstance(item, dict))
                    if value.get('error_report') or value.get('missing') or value.get('failed'):
                        report = value.get('error_report') or 'rapor oluşturulamadı'
                        messagebox.showerror(
                            'Linkleme / Excel tamamlanamadı',
                            f'Beklenen görsel: {expected}\nExcel’e yazılan link: {linked}\n'
                            f'Bulut yükleme hatası: {int(value.get("failed", 0))}\n'
                            f'Yerel eksik/uyuşmayan çıktı: {int(value.get("missing", 0))}\n'
                            f'Eksik link: {int(value.get("missing", 0))}\n\n'
                            f'Yapılacaklar:\n- Hata raporunu açın: {report}\n'
                            '- İnternet bağlantısını ve bulut anahtarlarını kontrol edin.\n'
                            '- Sonra “Linke çevir + Excel’e yaz” ile tekrar deneyin.' + production_note + '\n\n' + store_summary, parent=self.window)
                    else:
                        messagebox.showinfo('Linkleme / Excel tamamlandı',
                            f'{linked} görsel için link ve Excel hazırlandı.\n\n'
                            'Not: Mağaza Excel’inde satır sayısı ürün sayısıdır; aynı ürüne ait çoklu görseller aynı satırdaki görsel sütunlarına yazılır.\n\n'
                            f'{store_summary}\n{store_text}' + production_note, parent=self.window)
                    self._apply_cloud_progress({
                        'completed': int(value.get('uploaded', 0)) + int(value.get('reused', 0)) + int(value.get('failed', 0)) + int(value.get('missing', 0)),
                        'total': int(value.get('expected', 0)),
                        'elapsed_seconds': value.get('elapsed_seconds', 0), 'eta_seconds': 0,
                        'operation': f"Excel hazır · {store_text}",
                        'phase': 'excel', 'stage': 'excel',
                        'excel_index': 1, 'excel_total': 1,
                        'uploaded': value.get('uploaded', 0), 'reused': value.get('reused', 0), 'failed': value.get('failed', 0),
                    })
                    if store_outputs:
                        self._last_trendyol_output = list(store_outputs.values())[-1].get('output')
                    self.start_button.configure(text='▶  ÜRETİME BAŞLA', state="normal")
                    self.cloud_button.configure(state="normal")
                    if hasattr(self, 'cloud_button_visible'):
                        self.cloud_button_visible.configure(state="normal")
                elif kind == 'store_excel_done':
                    self._worker_kind = None
                    done = list(value.get('done') or [])
                    failed = list(value.get('failed') or [])
                    total_units = int(value.get('total') or 0)
                    self.start_button.configure(state="normal")
                    self.cloud_button.configure(state="normal")
                    if hasattr(self, 'cloud_button_visible'):
                        self.cloud_button_visible.configure(state="normal")
                    self._apply_cloud_progress({'phase': 'excel', 'stage': 'excel',
                                                'completed': 0, 'total': 0,
                                                'excel_index': total_units, 'excel_total': max(1, total_units),
                                                'operation': 'Mağaza Excel’leri tamamlandı',
                                                'elapsed_seconds': value.get('elapsed_seconds', 0),
                                                'eta_seconds': 0})
                    self.progress.set(f'Mağaza Excel işlemi tamamlandı · başarılı: {len(done)}, hatalı: {len(failed)}')
                    msg = "\n".join(x["store"] + ": " + str(x["rows"]) + " ürün, " +
                                    str(x["images"]) + " görsel\nDosya: " + x["output"] +
                                    "\nKlasör: " + x.get("output_folder", str(Path(x["output"]).parent)) +
                                    ("\nHata raporu: " + x["error_report"] if x.get("error_report") else "") for x in done)
                    if failed:
                        msg += "\n\nKontrol gereken mağazalar:\n" + "\n".join(failed)
                    if done:
                        self._last_trendyol_output = done[-1].get('output')
                        messagebox.showinfo("Mağaza Excel Hazır",
                            msg + "\n\nFiyat, ürün açıklaması, GTIN ve diğer pazar yeri alanlarını kontrol edin.",
                            parent=self.window)
                    else:
                        messagebox.showwarning("Excel Henüz Hazır Değil",
                            msg or "Önce doğrulanmış mağaza HTTPS linkleri gerekiyor.", parent=self.window)
                elif kind == 'local_excel_done':
                    self._worker_kind = None
                    result = value.get('result') or {}
                    self.start_button.configure(state="normal")
                    self.cloud_button.configure(state="normal")
                    if hasattr(self, 'cloud_button_visible'):
                        self.cloud_button_visible.configure(state="normal")
                    self._apply_cloud_progress({'phase': 'excel', 'stage': 'excel',
                                                'completed': 0, 'total': 0,
                                                'excel_index': 1, 'excel_total': 1,
                                                'operation': 'LOCAL Excel hazır',
                                                'elapsed_seconds': value.get('elapsed_seconds', 0),
                                                'eta_seconds': 0})
                    self.progress.set('LOCAL Excel hazır.')
                    messagebox.showinfo("LOCAL Excel", str(result.get("output")), parent=self.window)
                elif kind == 'local_excel_fail':
                    self._worker_kind = None
                    self.start_button.configure(state="normal")
                    self.cloud_button.configure(state="normal")
                    if hasattr(self, 'cloud_button_visible'):
                        self.cloud_button_visible.configure(state="normal")
                    self._apply_cloud_progress({'phase': 'excel', 'stage': 'excel',
                                                'completed': 0, 'total': 0,
                                                'excel_index': 0, 'excel_total': 1,
                                                'operation': 'LOCAL Excel hata verdi',
                                                'elapsed_seconds': 0, 'eta_seconds': None})
                    self.progress.set("DURDU — " + str(value))
                    helpful_error("Pazaryeri Excel Hatası", str(value), parent=self.window)
                elif kind == "fail":
                    failed_worker_kind = self._worker_kind
                    self._worker_kind = None
                    self._render_stop_requested = False
                    self._auto_cloud_pending = False
                    self._auto_cloud_keys = []
                    self.result_summary.set('Üretilen: 0 · Başarılı: 0 · Hatalı: 1 · Atlanan: 0')
                    self.progress.set("DURDU — " + str(value))
                    if failed_worker_kind == 'cloud':
                        self.cloud_progress_title.set('Excel / Linkleme hata verdi')
                        self.cloud_progress_detail.set(str(value))
                    self.start_button.configure(text='▶  ÜRETİME BAŞLA', state="normal")
                    self.cloud_button.configure(state="normal")
                    if hasattr(self, 'cloud_button_visible'):
                        self.cloud_button_visible.configure(state="normal")
        except queue.Empty:
            pass
        if self.window.winfo_exists():
            self.window.after(200, self.poll)


def open_unified_v4_window(parent, *, runtime_root=None, petek_registry=None, v4_root=None, prebuilt_engine=None, embedded_parent=None):
    return UnifiedV4BatchWindow(
        parent,
        runtime_root=runtime_root,
        petek_registry=petek_registry,
        v4_root=v4_root,
        prebuilt_engine=prebuilt_engine,
        embedded_parent=embedded_parent,
    )
