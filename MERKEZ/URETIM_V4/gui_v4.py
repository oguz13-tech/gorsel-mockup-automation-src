"""V4.0 Tkinter Windows UI for 7-Category Unlimited Batch Production & Crash Recovery."""
from __future__ import annotations
from error_advisor_v498 import showerror as helpful_error

import os
import subprocess
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from PIL import Image, ImageTk
from dark_theme_v42 import BG, PANEL, FG, ACCENT
from ui_layout_v498 import LayoutEditor, load as load_visual_layout
from help_v42 import bind_help
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
from .unified_batch import _render_legacy_six_cover, _build_legacy_category_mask
from .finish_material_v46 import DAYLIGHT, apply_material_finish
from .optical_qa_v47 import measure_effect
from PETEK_V3.cutout_paste import render_with_cutout_paste
from PETEK_V3.petek_visual_pipeline_vnext import render_petek_visual
from PETEK_V3 import engine as petek_engine
from .finish_v42 import GLASS
import cv2

LIGHT_LABELS = ("Cam Yansıması AÇIK / Doğal Işık", "Efektler KAPALI / Orijinal Baskı")
SUN_LABELS = ("Kapalı (eski görünüm)", "Doğal (7 kategori)", "Belirgin (7 kategori / 2 gölge)")
SUN_CODES = dict(zip(SUN_LABELS, ("off", "dogal", "belirgin")))


def _lighting_code(value: str) -> str:
    return "off" if value == LIGHT_LABELS[1] else "natural"



class UnifiedV4BatchWindow:
    """7-category unlimited human-approved batch production and crash recovery window."""

    def __init__(self, parent, *, runtime_root: Path | None = None, petek_registry: PetekRegistry | None = None,
                 v4_root: Path | None = None, prebuilt_engine=None):
        self.runtime_root = Path(runtime_root).resolve() if runtime_root else None
        self.petek_registry = petek_registry or PetekRegistry()
        self.batch_engine = prebuilt_engine if prebuilt_engine is not None else UnifiedV4Batch(
            v4_root,
            runtime_root=self.runtime_root,
            petek_registry=self.petek_registry,
        )
        self._worker_kind = None
        self._render_stop_requested = False
        self.window = tk.Toplevel(parent)
        self.window.title(VERSION_TEXT + " — 7 Kategori Üretim / Bulut Excel / İsteğe Bağlı 4K")
        self.window.geometry("1360x880")
        self.window.minsize(1040,650)
        self.window.configure(background=BG)
        # Production is a MODELLESS tool window. No grab_set/wait_window or
        # transient owner restriction: dashboard + browser review stay usable.
        # Users can move between all three while respecting immutable approvals.
        self.window.wm_group(self.window) if False else None

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
        def scroll_form(event):
            if event.widget is self.listbox or isinstance(event.widget,(tk.Listbox,tk.Text)):
                return
            if event.delta:
                self.main_canvas.yview_scroll(-1 if event.delta>0 else 1,'units')
        self.window.bind('<MouseWheel>',scroll_form)

        hero=ttk.Frame(area,padding=(15,12))
        hero.pack(fill='x',pady=(0,10))
        ttk.Label(
            hero,
            text=f"SERİ MOCKUP ÜRETİM MERKEZİ   •   7 KATEGORİ   •   {APP_VERSION}",
            font=("Segoe UI", 19, "bold"),
        ).pack(anchor="w", pady=(0, 6))
        ttk.Label(
            area,
            text="Altı kategori SQLite insan onaylı şablonları + PETEK onaylı maskeleri kullanır.\n"
            "Sınırsız iş / 10 şablon sınırı yoktur. Önce yerel üretim; sonra istersen bulut HTTPS linkli Excel.",
            wraplength=800,
        ).pack(anchor="w", pady=(0, 8))

        self._prod_tabbar=ttk.Frame(area,padding=(4,8))
        self._prod_tabbar.pack(fill='x',pady=(0,7))
        templates_panel=ttk.LabelFrame(area,text='01  ŞABLONLAR  ·  Filtrele / seç / önizle',style='Premium.TLabelframe',padding=(15,13))
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
        self.filter_count = tk.StringVar(value="Liste yükleniyor...")
        ttk.Label(templates_panel,textvariable=self.filter_count,font=("Segoe UI",10,"bold")).pack(anchor="w",pady=(1,2))
        for var in (self.category_filter, self.search_filter, self.sort_filter):
            var.trace_add('write', lambda *_: self.apply_filters())
        self.listbox.bind('<<ListboxSelect>>', self._on_selection_change, add='+')

        btn_row = ttk.Frame(templates_panel)
        btn_row.pack(fill="x", pady=3)
        ttk.Button(btn_row, text="Tüm Onaylı Şablonları Yenile", command=self.reload).pack(side="left")
        ttk.Button(btn_row, text="Tüm Şablonları Seç", command=self.select_all).pack(side="left", padx=6)
        ttk.Button(btn_row, text="Filtreleneni Seç", command=self.select_filtered).pack(side="left",padx=5)
        ttk.Button(btn_row, text="Seçimi Temizle", command=self.clear_selection).pack(side="left",padx=5)
        ttk.Button(btn_row, text="7 Kategori Güneş / Efekt A/B — ÖNCE / SONRA", command=self.start_ab_preview).pack(side="left", padx=6)
        ttk.Button(btn_row, text="Yarım İş / Kilit Kurtarma (Onaylı)", command=self.open_recovery).pack(side="left", padx=6)

        designs_panel=ttk.LabelFrame(area,text='02  TASARIMLAR VE MAĞAZALAR',style='Premium.TLabelframe',padding=(15,13))
        designs_panel.pack(fill='x',pady=(7,10))
        row = ttk.Frame(designs_panel)
        row.pack(fill="x", pady=8)
        default_ham=(self.runtime_root/'HAM BASKI TASARIMLARI') if self.runtime_root else None
        self.design_folder = tk.StringVar(value=str(default_ham) if default_ham and default_ham.is_dir() else '')
        ttk.Entry(row, textvariable=self.design_folder).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="2. Baskı Tasarımları Klasörünü Seç", command=self.browse).pack(side="left", padx=6)

        opts = ttk.Frame(designs_panel)
        opts.pack(fill="x", pady=5)
        ttk.Label(opts, text="Mağaza Grubu:").pack(side="left")
        self.group = tk.StringVar(value="LOCAL")
        ttk.Entry(opts, textvariable=self.group, width=14).pack(side="left", padx=5)
        ttk.Label(opts, text="İş sınırı yok — tüm seçili şablon × tasarımlar işlenir. Başlamadan önce toplamı onaylarsın.").pack(side="left", padx=(16, 4))

        # Store membership lives in private local state, NOT in the historic
        # approved template directory. Empty store selection = legacy behavior.
        profile_panel = ttk.Frame(designs_panel)
        profile_panel.pack(fill="x", pady=(2, 5))
        ttk.Label(profile_panel, text="Mağazalar (Ctrl ile çoklu seç; boş = eski LOCAL):").pack(side="left")
        self.store_list = tk.Listbox(profile_panel, selectmode="extended",height=3,
                                    width=35,exportselection=False,
                                    bg=PANEL,fg=FG,selectbackground=ACCENT)
        self.store_list.pack(side="left",padx=8)
        self.store_list.bind('<<ListboxSelect>>', self._store_changed, add='+')
        self.store_mapping=[]
        ttk.Button(profile_panel,text="Mağaza Profilleri / Şablon Atama",
                   command=self.open_store_manager).pack(side="left",padx=3)
        ttk.Button(profile_panel,text="Mağazaları Yenile",
                   command=self.reload_stores).pack(side="left",padx=3)
        ttk.Label(profile_panel,text="Her mağaza yalnız kendisine atanmış onaylı şablonları kullanır.",
                  wraplength=315).pack(side="left",padx=8)
        ttk.Label(designs_panel,text="Sıra rastgele: tasarımlar + şablonlar + mağazalar her turda karışır. "
                       "Aynı turda aynı SHA/tasarım/şablon/mağaza ikilisi yinelenmez.",
                  wraplength=1120).pack(anchor="w",pady=2)
        self.reload_stores()
        diagnostic_row = ttk.Frame(designs_panel)
        diagnostic_row.pack(fill='x', pady=(2,5))
        ttk.Button(diagnostic_row,
                   text='Mağaza – Üretim Eşleşmesini Denetle (Salt Okunur)',
                   command=self.diagnose_store_selection).pack(side='left', padx=(0,8))
        ttk.Button(diagnostic_row, text='Bu Mağazanın Mockuplarını Göster',
                   command=self.show_store_templates).pack(side='left', padx=(0,8))
        ttk.Button(diagnostic_row, text='Bütün Mockupları Göster',
                   command=self.show_all_templates).pack(side='left', padx=(0,8))
        ttk.Button(diagnostic_row, text='Mağazaya Atananları Üretime Seç',
                   command=self.select_store_assigned_templates).pack(side='left')
        self.store_filter_label=tk.StringVar(value='Mağazaya özel görünüm KAPALI. Seçimler değişmeden kalır.')
        ttk.Label(designs_panel,textvariable=self.store_filter_label,
                  foreground='#d9c3ff',wraplength=1050).pack(anchor='w',pady=(2,3))

        quality_panel=ttk.LabelFrame(area,text='03  KALİTE  ·  4K / PETEK / Efekt / Bulut',style='Premium.TLabelframe',padding=(15,13))
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
        ttk.Label(fit_row, text="Kategoriye Uygun Efekt:").pack(side="left", padx=(12, 4))
        self.lighting = tk.StringVar(value=LIGHT_LABELS[0])
        ttk.Combobox(fit_row, textvariable=self.lighting, state="readonly", values=LIGHT_LABELS, width=36).pack(side="left")
        sun_row=ttk.Frame(quality_panel);sun_row.pack(fill="x",pady=(4,2))
        ttk.Label(sun_row,text="7 Kategori Ortak Güneş / Gerçekçilik:").pack(side="left")
        self.sunlight_profile=tk.StringVar(value=SUN_LABELS[2])
        ttk.Combobox(sun_row,textvariable=self.sunlight_profile,values=SUN_LABELS,
                     state="readonly",width=37).pack(side="left",padx=(8,10))
        ttk.Label(sun_row,text="Belirgin: iki eğimli gölge güvenilir duvara devam eder; aksi halde çevre korunur.",wraplength=690).pack(side="left")

        ttk.Label(quality_panel, text=(
            "AÇIK: Cam tablolara pencere/çıta, cam doğramaya spot, ocak arkasına ortam yansıması; "
            "Ahşap ve PETEK'e mat günışığı. Wi-Fi dahil 7 kategoride ortak güneş seçeneği bulunur. "
            "KAPALI: yeni malzeme efekti uygulanmaz.\n"
            "Köşe yuvarlatması burada değil, 4 Köşe İnceleme > Bu Şablonu Onayla bölümünde ayrı kaydedilir."
        ), wraplength=1100).pack(anchor="w", pady=(2, 6))

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
        ttk.Combobox(upscale_row, textvariable=self.upscale_model, state="readonly", width=33,
                     values=("Fotoğraf — Real-ESRGAN x4plus", "Hızlı — Real-ESRGAN general x4v3")) \
            .pack(side="left", padx=(12, 4))
        ttk.Button(upscale_row,text='4K Kurulumunu Kontrol Et',
                   command=self._verify_4k_status).pack(side='left',padx=7)
        ttk.Label(upscale_row,textvariable=self._4k_state,wraplength=285).pack(side="left",padx=(8,0))
        self.upscale_4k.trace_add('write', lambda *_: self.window.after(10,self._on_4k_selected))
        self.upscale_model.trace_add('write',lambda *_: self.window.after(10,self._on_4k_selected))
        ttk.Label(quality_panel, text=("Varsayılan KAPALI; orijinal 1200×1600 çıktı korunur. 4K ayrı klasöre + SHA makbuzuna yazılır. "
                              "4K seçildiğinde mevcut kurulum hızlı doğrulanır, eksikse güvenli kurucu otomatik başlar; açılışta tarama yapılmaz."),
                  wraplength=1120).pack(anchor="w", pady=(0, 4))

        # Link + Excel is a separate opt-in post-render task, directly below 4K.
        # Checkbox alone NEVER authorizes a public upload: the existing explicit
        # online-sharing confirmation is required after the render completes.
        petek_row=ttk.Frame(quality_panel);petek_row.pack(fill='x',pady=(5,3))
        ttk.Label(petek_row,text="PETEK gerçek yarık gölgesi (13–16):").pack(side='left')
        self.petek_slot_mode=tk.StringVar(value='orta')
        ttk.Combobox(petek_row,textvariable=self.petek_slot_mode,width=11,state='readonly',
                     values=('off','hafif','orta','guclu')).pack(side='left',padx=7)
        # PETEK-only photometric profile; other 6 categories never inherit it.
        ttk.Label(petek_row,text='PETEK Dogallik:').pack(side='left',padx=(12,3))
        self.petek_nature_profile=tk.StringVar(value='Belirgin')
        ttk.Combobox(petek_row,textvariable=self.petek_nature_profile,width=11,state='readonly',
                     values=('Doğal','Belirgin')).pack(side='left',padx=(0,7))
        self.petek_pink_cleanup=tk.BooleanVar(value=True)
        self._petek_preview_ok = None
        self.petek_slot_mode.trace_add('write',lambda *_:setattr(self,'_petek_preview_ok',None))
        self.petek_pink_cleanup.trace_add('write',lambda *_:setattr(self,'_petek_preview_ok',None))
        ttk.Checkbutton(petek_row,text="PETEK dört kenar / köşe / ızgara pembe temizlik",
                        variable=self.petek_pink_cleanup).pack(side='left',padx=6)
        ttk.Button(petek_row,text="İsteğe Bağlı: Izgara / Pembe Önce-Sonra Test",command=self.start_petek_ab_preview).pack(side='left',padx=8)
        ttk.Label(quality_panel,text="PETEK gerçek yarık gölgesi varsayılan ORTA. Önce/Sonra testi İSTEĞE BAĞLIDIR; üretim öncesi test onayı zorunlu değildir. "
                  "Şablonun insan onayı, kaynak SHA, maske ve gerçek yarık geometrisi güvenlik kontrolleri devam eder. "
                  "Izgara motoru güvenilir ölçüm yapamazsa yalnız o üretim işi hata olarak raporlanır; orijinal dosyalar ve onaylı maskeler değişmez.",wraplength=1120).pack(anchor='w',pady=(0,4))
        self.auto_cloud_link = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            quality_panel,
            text="Üretimden sonra isteğe bağlı HTTPS Linke Çevir + Excel'e Yaz",
            variable=self.auto_cloud_link,
        ).pack(anchor="w", pady=(4, 2))
        ttk.Label(
            quality_panel,
            text="Varsayılan KAPALI. İşaretlenirse üretim bitince ayrıca bulut yükleme onayı sorulur; "
                 "onay verilmezse hiçbir görsel internete gönderilmez.",
            wraplength=1100,
        ).pack(anchor="w", pady=(0, 4))
        self._auto_cloud_pending = False
        self._auto_cloud_keys = []

        actions_panel=ttk.LabelFrame(area,text='04  SERİ ÜRETİM  ·  Başlat / Durdur / Rapor',style='Premium.TLabelframe',padding=(15,13))
        actions_panel.pack(fill='x',pady=(7,10))
        actions = ttk.Frame(actions_panel)
        actions.pack(fill="x", pady=8)
        self.start_button = ttk.Button(actions, text="▶ 7 Kategori Seri Üretimi Başlat", command=self.start,
                                       style='Premium.Primary.TButton')
        self.start_button.pack(side="left", padx=3)
        ttk.Button(actions, text="⏸ Duraklat", command=self.pause_batch).pack(side="left", padx=3)
        ttk.Button(actions, text="▶ Devam Et / Güvenli Durdurmadan Sürdür",
                   command=self.resume_batch).pack(side="left", padx=3)
        ttk.Button(actions, text="■ Güvenli Durdur", command=self.stop).pack(side="left", padx=3)
        ttk.Button(actions, text="Ortak Çıktı Klasörü", command=self.open_results).pack(side="left", padx=3)
        ttk.Button(actions, text="SHA Kayıtlarını Doğrula (Salt Okunur)", command=self.run_audit).pack(side="left", padx=3)
        ttk.Button(actions, text="Operasyon Özeti", command=self.show_operations).pack(side="left", padx=3)

        remote = ttk.Frame(actions_panel)
        remote.pack(fill="x", pady=5)
        self.cloud_button = ttk.Button(remote, text="☁ Mevcut Çıktıları HTTPS Linke Çevir + Excel'e Yaz",
                                       command=self.start_cloud_links)
        self.cloud_button.pack(side="left", padx=3)
        ttk.Button(remote, text="Mağaza Bazlı Trendyol Excel Oluştur", command=self.export_marketplace_template).pack(side="left", padx=5)
        ttk.Label(remote, text="Ayrı onay ister; ImgBB/FreeImage'a internetten erişilebilen görseller yükler. Pazaryerine ilan yüklemez.",
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
        self._editable_sections={'templates':templates_panel,'designs':designs_panel,
                                 'quality':quality_panel,'actions':actions_panel}
        self.progress = tk.StringVar(value="Hazır. Onaylı şablonlar yüklendi.")
        self._progress_widget=ttk.Label(area,textvariable=self.progress,wraplength=800)
        self._progress_widget.pack(anchor="w",pady=4)
        self._build_production_tabs()
        self.log = scrolledtext.ScrolledText(area, height=13, state="disabled", font=("Consolas", 9), bg=PANEL, fg=FG, insertbackground=FG)
        self.log.pack(fill="both", expand=True)

        self.messages: queue.Queue = queue.Queue()
        self.worker: threading.Thread | None = None
        self._load_seq=0
        self.reload()
        bind_help(self.window)
        self.window.after(200, self.poll)
        self.window.protocol("WM_DELETE_WINDOW", self.safe_close)

    def _build_production_tabs(self, _prefs=None):
        """Always keep Tümü, so hiding a filter tab never hides core commands."""
        prefs=_prefs or load_visual_layout()['production']
        self._production_tabs=prefs['tabs']
        for child in self._prod_tabbar.winfo_children():child.destroy()
        accent=prefs.get('accent','#995df4')
        tk.Label(self._prod_tabbar,text='Çalışma Panelleri:',bg=BG,fg=FG,
                 font=('Segoe UI',11,'bold')).pack(side='left',padx=(2,10))
        for name in prefs['tabs']:
            tk.Button(self._prod_tabbar,text=name,command=lambda n=name:self._apply_production_tab(n),
                      bg='#332948',fg=FG,activebackground=accent,activeforeground='#ffffff',
                      relief='flat',padx=13,pady=8).pack(side='left',padx=3)
        ttk.Button(self._prod_tabbar,text='✥ Arayüzü Düzenle',
                   command=lambda:LayoutEditor(self.window,'production',
                     on_save=self._build_production_tabs)).pack(side='right',padx=5)
        self._apply_production_tab('Tümü')

    def _apply_production_tab(self, name):
        order=self._production_tabs.get(name) or list(self._editable_sections)
        for panel in self._editable_sections.values():panel.pack_forget()
        for key in order:
            if key in self._editable_sections:
                self._editable_sections[key].pack(fill='x',pady=(7,10),before=self._progress_widget)
        self.main_canvas.yview_moveto(0)

    def _chosen_stores(self):
        return [self.store_mapping[int(i)] for i in self.store_list.curselection()
                if int(i) < len(self.store_mapping)]

    def _store_changed(self, _event=None):
        if self.store_only_view:
            self.apply_filters()
        else:
            self._update_store_filter_info()

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
        self.all_templates=list(templates)
        self.template_sources={t['uid']:Path(t['source']) for t in templates}
        self.template_items={t['uid']:t for t in templates}
        self.selected_uids=set() if initial else (keep & set(self.template_items))
        self._first_template_load=False
        self.apply_filters(capture=False)
        self.progress.set(f"Toplam {len(self.all_templates)} insan onaylı şablon hazır. "
                          f"Atlanan: {len(audit['skipped'])}. Arama ve seçime hazır.")
        self.start_button.configure(state='normal')

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

    def start(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        selected = self.chosen_uids()
        selected_stores=self._chosen_stores()
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
            lighting = _lighting_code(self.lighting.get())
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
            petek_nature_option=getattr(self,'petek_nature_profile',None)
            petek_realism_profile=('belirgin' if petek_nature_option is not None and petek_nature_option.get()=='Belirgin' else 'dogal')
            petek_selected=any(self.template_items.get(uid,{}).get('category')=='06_Petek_Kapama' for uid in selected)
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

        try:
            if self.runtime_root:
                ham_root=(self.runtime_root/'HAM BASKI TASARIMLARI').resolve(strict=False)
                selected_root=Path(design_folder).resolve()
                if selected_root==ham_root or ham_root in selected_root.parents:
                    from ham_designs_v487 import HamDesignVault
                    HamDesignVault(self.runtime_root).validate_for_production()
            design_count = sum(1 for _ in iter_designs(Path(design_folder)))
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
        job_count = pair_count * design_count
        if not messagebox.askyesno("Sınırsız Seri Üretimi Onayla",
            f"{pair_count} mağazaya özel onaylı şablon × {design_count} tasarım = {job_count:,} işlem denenecek.\n"
            "Her çıktı ayrı kayıtla korunur; işlemi istediğin zaman güvenli durdurabilirsin.\n"
            "BU İŞLEMİ BAŞLATMAK İSTİYOR MUSUN?", parent=self.window):
            return
        self._auto_cloud_pending = auto_cloud_after_render
        self._auto_cloud_keys = []
        self._render_stop_requested = False
        self.batch_engine.cancel.clear()
        self.batch_engine.resume()
        self.start_button.configure(state="disabled")

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
                    sunlight_profile=sunlight_profile,
                )
                self.messages.put(("done", res))
            except Exception as exc:
                self.messages.put(("fail", str(exc)))

        self._worker_kind = 'render'
        self.worker = threading.Thread(target=work, daemon=False)
        self.worker.start()
        self.progress.set("7 kategori ortak seri üretim çalışıyor...")

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

    def start_cloud_links(self, only_keys=None) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showwarning("İşlem Devam Ediyor", "Önce çalışan üretim/linkleme işlemini durdurun.", parent=self.window)
            return
        cloud = CloudExcel(self.batch_engine.root, self.batch_engine.reports, self.runtime_root)
        if not cloud.available():
            helpful_error("Bulut Anahtarı Yok",
                "Eski ayarlar.json > bulut_ayarlari > imgbb_keys veya freeimage_key bulunamadı.\n"
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
        if not messagebox.askyesno("GERÇEK BULUT YÜKLEME ONAYI",
            f"{len(rows)} üretilmiş görsel kontrol edilecek.\n"
            "Henüz linki olmayan, SHA'sı doğru görseller ImgBB / FreeImage bulutuna yüklenecek; "
            "görselleri bağlantıyı bilenler internette açabilir.\n"
            "Ardından SKU eşleşmeli Resim Linki sütunu bulunan YENİ Excel oluşturulacak.\n"
            "Bu işlem pazaryerine ilan yüklemez. BULUTA YÜKLEMEYİ ONAYLIYOR MUSUN?",
            parent=self.window):
            return
        self.batch_engine.cancel.clear()
        self.cloud_button.configure(state="disabled")
        self.start_button.configure(state="disabled")
        def run_cloud():
            try:
                res = cloud.publish_existing(rows, notify=self._log, stop=self.batch_engine.cancel)
                self.messages.put(("cloud_done", res))
            except Exception as exc:
                self.messages.put(("fail", "BULUT EXCEL: " + str(exc)))
        self._worker_kind = 'cloud'
        self.worker = threading.Thread(target=run_cloud, daemon=False)
        self.worker.start()
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
                result = self.batch_engine.resume_last_stopped(notify=self._log)
                self.messages.put(('done',result))
            except Exception as exc:
                self.messages.put(('fail','DEVAM ET: '+str(exc)))
        self._worker_kind='render'
        self.worker=threading.Thread(target=continue_previous,daemon=False)
        self.worker.start()
        self.progress.set('Kaydedilen tur doğrulanıyor; yalnız kalan görseller üretilecek.')

    def show_operations(self) -> None:
        from .ops_dashboard_v45 import summarize
        try:
            info = summarize(self.batch_engine.root)
            rows = [f"{name}: {value}" for name, value in sorted(info['status_counts'].items())]
            cats = [f"{name}: {value}" for name, value in sorted(info['categories'].items())]
            msg = (f"Toplam kayıt: {info['total']}\n"
                   f"Doğrulanmış görsel: {info['verified']}\n"
                   f"Kaybolan: {info['missing']} | SHA uyuşmayan: {info['sha_mismatch']}\n"
                   f"Kullanılabilir disk: {info['disk_free_gb']:.1f} GB\n\n"
                   "Durumlar:\n" + "\n".join(rows) + "\n\nKategoriler:\n" + "\n".join(cats))
            messagebox.showinfo("Operasyon Özeti — Salt Okunur", msg, parent=self.window)
        except (OSError, ValueError, RuntimeError) as exc:
            helpful_error("Özet Hatası", str(exc), parent=self.window)

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
                done=[];failed=[]
                for name in selected:
                    try:
                        x=export_store_upload(Path(template),self.batch_engine.root,
                                              store_id=name,report_root=self.batch_engine.reports)
                        done.append(x)
                        self._log("MAĞAZA XLSX: "+str(x["output"]))
                    except (ValueError,OSError,RuntimeError) as exc:
                        failed.append(name+": "+str(exc))
                msg="\n".join(x["store"]+": "+str(x["rows"])+" ürün, "+
                               str(x["images"])+" görsel\n"+x["output"] for x in done)
                if failed:msg+="\n\nKontrol gereken mağazalar:\n"+"\n".join(failed)
                if done:
                    messagebox.showinfo("Mağaza Excel Hazır",
                        msg+"\n\nFiyat, ürün açıklaması, GTIN ve diğer pazar yeri alanlarını kontrol edin.",
                        parent=self.window)
                else:
                    messagebox.showwarning("Excel Henüz Hazır Değil",
                        msg or "Önce doğrulanmış mağaza HTTPS linkleri gerekiyor.",parent=self.window)
            else:
                if not messagebox.askyesno("Eski LOCAL Excel",
                    "Mağaza profili yok. Önceki LOCAL şablon aktarımı kullanılsın mı?",
                    parent=self.window):return
                from .marketplace_excel_v45 import export_from_template
                result=export_from_template(Path(template),self.batch_engine.root,
                    self.batch_engine.ledger.successful(),report_root=self.batch_engine.reports)
                messagebox.showinfo("LOCAL Excel",str(result["output"]),parent=self.window)
        except (ValueError,OSError,RuntimeError) as exc:
            helpful_error("Pazaryeri Excel Hatası",str(exc),parent=self.window)

    def stop(self) -> None:
        if self.worker and self.worker.is_alive() and self._worker_kind == 'render':
            self._render_stop_requested = True
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
                elif kind == "done":
                    self._worker_kind = None
                    self._render_stop_requested = False
                    self.progress.set(
                        f"{value['status']} — Üretilen: {value['rendered']}, "
                        f"Tekrar: {value['reused']}, Atlanan: {value['rejected']}. "
                        f"Excel: {value['xlsx']}"
                    )
                    self.start_button.configure(state="normal")
                    self.cloud_button.configure(state="normal")
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
                    self.progress.set(f"BULUT {value['status']} — Linkli: {value['linked']}, "
                                      f"Yeni: {value['uploaded']}, Mevcut: {value['reused']}, Hata: {value['failed']}. "
                                      f"HTTPS Excel: {value['xlsx']}")
                    self.start_button.configure(state="normal")
                    self.cloud_button.configure(state="normal")
                elif kind == "fail":
                    self._worker_kind = None
                    self._render_stop_requested = False
                    self._auto_cloud_pending = False
                    self._auto_cloud_keys = []
                    self.progress.set("DURDU — " + str(value))
                    self.start_button.configure(state="normal")
                    self.cloud_button.configure(state="normal")
        except queue.Empty:
            pass
        if self.window.winfo_exists():
            self.window.after(200, self.poll)


def open_unified_v4_window(parent, *, runtime_root=None, petek_registry=None, v4_root=None, prebuilt_engine=None):
    return UnifiedV4BatchWindow(
        parent,
        runtime_root=runtime_root,
        petek_registry=petek_registry,
        v4_root=v4_root,
        prebuilt_engine=prebuilt_engine,
    )
