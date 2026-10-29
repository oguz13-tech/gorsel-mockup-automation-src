"""V4.0 Tkinter Windows UI for 7-Category Unlimited Batch Production & Crash Recovery."""
from __future__ import annotations

import os
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from PIL import Image, ImageTk
from dark_theme_v42 import BG, PANEL, FG
from help_v42 import bind_help
from version_v45 import TITLE as VERSION_TEXT

from PETEK_V3.registry import Registry as PetekRegistry
from .unified_batch import UnifiedV4Batch, iter_designs
from .store_profiles_v47 import StoreProfiles
from .cloud_excel_v43 import CloudExcel
from .design_proxy_v43 import prepare_render_artwork
from .upscale4k_v44 import preflight as upscale_preflight, UpscaleError
from .unified_batch import _render_legacy_six_cover, _build_legacy_category_mask
from .finish_material_v46 import DAYLIGHT, apply_material_finish
from .optical_qa_v47 import measure_effect
from PETEK_V3.cutout_paste import render_with_cutout_paste
from PETEK_V3 import engine as petek_engine
from .finish_v42 import GLASS
import cv2

LIGHT_LABELS = ("Cam Yansıması AÇIK / Doğal Işık", "Efektler KAPALI / Orijinal Baskı")


def _lighting_code(value: str) -> str:
    return "off" if value == LIGHT_LABELS[1] else "natural"



class UnifiedV4BatchWindow:
    """7-category unlimited human-approved batch production and crash recovery window."""

    def __init__(self, parent, *, runtime_root: Path | None = None, petek_registry: PetekRegistry | None = None, v4_root: Path | None = None):
        self.runtime_root = Path(runtime_root).resolve() if runtime_root else None
        self.petek_registry = petek_registry or PetekRegistry()
        self.batch_engine = UnifiedV4Batch(
            v4_root,
            runtime_root=self.runtime_root,
            petek_registry=self.petek_registry,
        )
        self._worker_kind = None
        self._render_stop_requested = False
        self.window = tk.Toplevel(parent)
        self.window.title(VERSION_TEXT + " — 7 Kategori Üretim / Bulut Excel / İsteğe Bağlı 4K")
        self.window.geometry("1190x920")
        self.window.transient(parent)

        area = ttk.Frame(self.window, padding=18)
        area.pack(fill="both", expand=True)

        ttk.Label(
            area,
            text="7 Kategori Ortak Seri Üretim Merkezi (V4.7.7 — Güvenli Devam, Mağazalar, Efektler, 4K, Excel)",
            font=("Segoe UI", 15, "bold"),
        ).pack(anchor="w", pady=(0, 6))
        ttk.Label(
            area,
            text="Altı kategori SQLite insan onaylı şablonları + PETEK onaylı maskeleri kullanır.\n"
            "Sınırsız iş / 10 şablon sınırı yoktur. Önce yerel üretim; sonra istersen bulut HTTPS linkli Excel.",
            wraplength=800,
        ).pack(anchor="w", pady=(0, 8))

        ttk.Label(
            area,
            text="1. Üretime Hazır Onaylı (APPROVED) Şablonlar (7 Kategori — Çoklu Seçim):",
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w")
        preview_frame = ttk.Frame(area)
        preview_frame.pack(fill="x", pady=4)
        self.listbox = tk.Listbox(preview_frame, selectmode="extended", height=9, exportselection=False,
                                  bg=PANEL, fg=FG, selectbackground='#2563eb', selectforeground='#fff')
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
        self.mapping: list[str] = []

        btn_row = ttk.Frame(area)
        btn_row.pack(fill="x", pady=3)
        ttk.Button(btn_row, text="Tüm Onaylı Şablonları Yenile", command=self.reload).pack(side="left")
        ttk.Button(btn_row, text="Tüm Şablonları Seç", command=self.select_all).pack(side="left", padx=6)
        ttk.Button(btn_row, text="Kategori Efekti A/B (Cam / Ahşap / PETEK)", command=self.start_ab_preview).pack(side="left", padx=6)
        ttk.Button(btn_row, text="Yarım İş / Kilit Kurtarma (Onaylı)", command=self.open_recovery).pack(side="left", padx=6)

        row = ttk.Frame(area)
        row.pack(fill="x", pady=8)
        self.design_folder = tk.StringVar()
        ttk.Entry(row, textvariable=self.design_folder).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="2. Baskı Tasarımları Klasörünü Seç", command=self.browse).pack(side="left", padx=6)

        opts = ttk.Frame(area)
        opts.pack(fill="x", pady=5)
        ttk.Label(opts, text="Mağaza Grubu:").pack(side="left")
        self.group = tk.StringVar(value="LOCAL")
        ttk.Entry(opts, textvariable=self.group, width=14).pack(side="left", padx=5)
        ttk.Label(opts, text="İş sınırı yok — tüm seçili şablon × tasarımlar işlenir. Başlamadan önce toplamı onaylarsın.").pack(side="left", padx=(16, 4))

        # Store membership lives in private local state, NOT in the historic
        # approved template directory. Empty store selection = legacy behavior.
        profile_panel = ttk.Frame(area)
        profile_panel.pack(fill="x", pady=(2, 5))
        ttk.Label(profile_panel, text="Mağazalar (Ctrl ile çoklu seç; boş = eski LOCAL):").pack(side="left")
        self.store_list = tk.Listbox(profile_panel, selectmode="extended",height=3,
                                    width=35,exportselection=False,
                                    bg=PANEL,fg=FG,selectbackground='#2563eb')
        self.store_list.pack(side="left",padx=8)
        self.store_mapping=[]
        ttk.Button(profile_panel,text="Mağaza Profilleri / Şablon Atama",
                   command=self.open_store_manager).pack(side="left",padx=3)
        ttk.Button(profile_panel,text="Mağazaları Yenile",
                   command=self.reload_stores).pack(side="left",padx=3)
        ttk.Label(profile_panel,text="Her mağaza yalnız kendisine atanmış onaylı şablonları kullanır.",
                  wraplength=315).pack(side="left",padx=8)
        ttk.Label(area,text="Sıra rastgele: tasarımlar + şablonlar + mağazalar her turda karışır. "
                       "Aynı turda aynı SHA/tasarım/şablon/mağaza ikilisi yinelenmez.",
                  wraplength=1120).pack(anchor="w",pady=2)
        self.reload_stores()

        fit_row = ttk.Frame(area)
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

        ttk.Label(area, text=(
            "AÇIK: Cam tablolara pencere/çıta, cam doğramaya spot, ocak arkasına ortam yansıması; "
            "Ahşap ve PETEK'e mat, yumuşak diyagonal günışığı. Wi-Fi'de değişiklik yok. "
            "KAPALI: yeni malzeme efekti uygulanmaz.\n"
            "Köşe yuvarlatması burada değil, 4 Köşe İnceleme > Bu Şablonu Onayla bölümünde ayrı kaydedilir."
        ), wraplength=1100).pack(anchor="w", pady=(2, 6))

        # Normal render is always preserved. 4K is a separate opt-in job, and
        # cannot silently fall back to non-AI resizing if the binary is absent.
        upscale_row = ttk.Frame(area)
        upscale_row.pack(fill="x", pady=(5, 3))
        self.upscale_4k = tk.BooleanVar(value=False)
        self.upscale_model = tk.StringVar(value="Fotoğraf — Real-ESRGAN x4plus")
        ttk.Checkbutton(upscale_row, text="Üretimden sonra isteğe bağlı AI 4K (2880×3840)",
                        variable=self.upscale_4k).pack(side="left")
        ttk.Combobox(upscale_row, textvariable=self.upscale_model, state="readonly", width=33,
                     values=("Fotoğraf — Real-ESRGAN x4plus", "Hızlı — Real-ESRGAN general x4v3")) \
            .pack(side="left", padx=(12, 4))
        ttk.Label(area, text=("Varsayılan KAPALI; orijinal 1200×1600 çıktı korunur. 4K ayrı klasöre + SHA makbuzuna yazılır. "
                              "Bilgisayarda resmi Real-ESRGAN programı ve model dosyaları bulunmalıdır; yoksa üretimden önce uyarılır."),
                  wraplength=1120).pack(anchor="w", pady=(0, 4))

        # Link + Excel is a separate opt-in post-render task, directly below 4K.
        # Checkbox alone NEVER authorizes a public upload: the existing explicit
        # online-sharing confirmation is required after the render completes.
        self.auto_cloud_link = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            area,
            text="Üretimden sonra isteğe bağlı HTTPS Linke Çevir + Excel'e Yaz",
            variable=self.auto_cloud_link,
        ).pack(anchor="w", pady=(4, 2))
        ttk.Label(
            area,
            text="Varsayılan KAPALI. İşaretlenirse üretim bitince ayrıca bulut yükleme onayı sorulur; "
                 "onay verilmezse hiçbir görsel internete gönderilmez.",
            wraplength=1100,
        ).pack(anchor="w", pady=(0, 4))
        self._auto_cloud_pending = False
        self._auto_cloud_keys = []

        actions = ttk.Frame(area)
        actions.pack(fill="x", pady=8)
        self.start_button = ttk.Button(actions, text="▶ 7 Kategori Seri Üretimi Başlat", command=self.start)
        self.start_button.pack(side="left", padx=3)
        ttk.Button(actions, text="⏸ Duraklat", command=self.pause_batch).pack(side="left", padx=3)
        ttk.Button(actions, text="▶ Devam Et / Güvenli Durdurmadan Sürdür",
                   command=self.resume_batch).pack(side="left", padx=3)
        ttk.Button(actions, text="■ Güvenli Durdur", command=self.stop).pack(side="left", padx=3)
        ttk.Button(actions, text="Ortak Çıktı Klasörü", command=self.open_results).pack(side="left", padx=3)
        ttk.Button(actions, text="SHA Kayıtlarını Doğrula (Salt Okunur)", command=self.run_audit).pack(side="left", padx=3)
        ttk.Button(actions, text="Operasyon Özeti", command=self.show_operations).pack(side="left", padx=3)

        remote = ttk.Frame(area)
        remote.pack(fill="x", pady=5)
        self.cloud_button = ttk.Button(remote, text="☁ Mevcut Çıktıları HTTPS Linke Çevir + Excel'e Yaz",
                                       command=self.start_cloud_links)
        self.cloud_button.pack(side="left", padx=3)
        ttk.Button(remote, text="Mağaza Bazlı Trendyol Excel Oluştur", command=self.export_marketplace_template).pack(side="left", padx=5)
        ttk.Label(remote, text="Ayrı onay ister; ImgBB/FreeImage'a internetten erişilebilen görseller yükler. Pazaryerine ilan yüklemez.",
                  wraplength=570).pack(side="left", padx=7)
        ttk.Label(area, text=(
            "YENİLE: onaylı şablon listesini yeniden okur | TÜMÜNÜ SEÇ: listedeki hepsini seçer (başlatmaz). "
            "MAĞAZA GRUBU: SKU ayırır; otomatik mağazaya yüklemez.\n"
            "DURAKLAT: aktif dosya tamamlandıktan sonra yeni işe geçmez; DEVAM: aynı kuyruktan sürdürür. "
            "GÜVENLİ DURDUR: biten görselleri koruyarak sonraki işleri durdurur. "
            "YARIM İŞ/KİLİT KURTARMA: bozuk ara kayıtları gösterir; açık onayla karantinaya alır. "
            "SHA DENETLE: çıktı dosyası ile kayıt hash'lerini sadece okur. "
            "PAZARYERİ EXCEL ŞABLONU: yalnız HTTPS linki hazır satırları senin boş XLSX başlıklarına eşler; "
            "asıl şablonu korur, barkod ve SEO uydurmaz."
        ), wraplength=1120).pack(anchor="w", pady=(3, 5))
        self.progress = tk.StringVar(value="Hazır. Onaylı şablonlar yüklendi.")
        ttk.Label(area, textvariable=self.progress, wraplength=800).pack(anchor="w", pady=4)
        self.log = scrolledtext.ScrolledText(area, height=13, state="disabled", font=("Consolas", 9), bg=PANEL, fg=FG, insertbackground=FG)
        self.log.pack(fill="both", expand=True)

        self.messages: queue.Queue = queue.Queue()
        self.worker: threading.Thread | None = None
        self.reload()
        bind_help(self.window)
        self.window.after(200, self.poll)
        self.window.protocol("WM_DELETE_WINDOW", self.safe_close)

    def reload_stores(self):
        try:
            cfg=StoreProfiles(self.batch_engine.root).load()
            keep={self.store_mapping[i] for i in self.store_list.curselection()
                  if i<len(self.store_mapping)}
            self.store_list.delete(0,"end")
            self.store_mapping=list(sorted(cfg["stores"]))
            for i,name in enumerate(self.store_mapping):
                count=len(cfg["stores"][name]["templates"])
                self.store_list.insert("end",f"{name} ({count} şablon)")
                if name in keep:self.store_list.selection_set(i)
        except Exception as exc:
            messagebox.showerror("Mağaza profilleri okunamadı",str(exc),parent=self.window)

    def open_store_manager(self):
        pop=tk.Toplevel(self.window);pop.title("Mağaza Profilleri — Onaylı Şablon Atama")
        pop.geometry("660x400");pop.transient(self.window)
        root=ttk.Frame(pop,padding=16);root.pack(fill="both",expand=True)
        ttk.Label(root,text="Yeni mağaza kodu (örn: Magaza_01):").pack(anchor="w")
        name=tk.StringVar()
        ttk.Entry(root,textvariable=name,width=30).pack(anchor="w",pady=5)
        ttk.Label(root,text="Şablon atamak için ana üretim listesinden onaylı şablonları seç. "
                   "Buradan kaydedilen eşleşmeler başka mağazayla paylaşılmaz.",
                  wraplength=590).pack(anchor="w",pady=6)
        listing=tk.Listbox(root,height=10,exportselection=False,bg=PANEL,fg=FG)
        listing.pack(fill="both",expand=True,pady=5)
        names=[]
        def refresh():
            selected=names[listing.curselection()[0]] if listing.curselection() else None
            cfg=StoreProfiles(self.batch_engine.root).load()
            listing.delete(0,"end")
            names.clear();names.extend(sorted(cfg["stores"]))
            for i,k in enumerate(names):
                listing.insert("end",f"{k} — {len(cfg['stores'][k]['templates'])} onaylı şablon")
                if k==selected:listing.selection_set(i)
            self.reload_stores()
        def run(action):
            try:
                mgr=StoreProfiles(self.batch_engine.root)
                if action=="add":mgr.add_store(name.get().strip())
                else:
                    sel=listing.curselection()
                    if len(sel)!=1:raise ValueError("Önce bu pencerede tek mağaza seçin.")
                    store=names[sel[0]]
                    templates=[self.template_items[self.mapping[int(i)]]
                               for i in self.listbox.curselection()]
                    if action=="assign":mgr.assign(store,templates,all_approved=list(self.template_items.values()))
                    else:mgr.unassign(store,templates)
                refresh()
            except (ValueError,KeyError,OSError) as exc:
                messagebox.showerror("Mağaza eşleştirmesi",str(exc),parent=pop)
        bar=ttk.Frame(root);bar.pack(fill="x",pady=6)
        ttk.Button(bar,text="Mağaza Ekle",command=lambda:run("add")).pack(side="left",padx=3)
        ttk.Button(bar,text="Seçili Şablonları Ata",command=lambda:run("assign")).pack(side="left",padx=3)
        ttk.Button(bar,text="Atamayı Kaldır",command=lambda:run("unassign")).pack(side="left",padx=3)
        ttk.Button(bar,text="Kapat",command=pop.destroy).pack(side="right",padx=3)
        refresh()

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

    def reload(self) -> None:
        self.listbox.delete(0, "end")
        self.mapping = []
        self.template_sources = {}
        self.template_items = {}
        try:
            templates, audit = self.batch_engine.discover_templates(per_category_limit=None)
            for item in templates:
                label = f"[{item['category']}] {item['uid']} ({item['orientation']})"
                self.mapping.append(item["uid"])
                self.template_sources[item["uid"]] = Path(item["source"])
                self.template_items[item["uid"]] = item
                self.listbox.insert("end", label)
            if self.mapping:
                self.listbox.selection_set(0, len(self.mapping) - 1)
                self._preview_selected()
            self.progress.set(
                f"Toplam {len(self.mapping)} insan onaylı şablon hazır (10 şablon sınırı yok). "
                f"Atlanan: {len(audit['skipped'])}."
            )
        except Exception as exc:
            self.progress.set("Şablon tarama uyarısı: " + str(exc))

    def select_all(self) -> None:
        if self.mapping:
            self.listbox.selection_set(0, len(self.mapping) - 1)

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
        selected = [self.mapping[int(i)] for i in self.listbox.curselection()]
        selected_stores=[self.store_mapping[int(i)] for i in self.store_list.curselection()]
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
            glass_effect = "off" if lighting == "off" else "on"
            # Cam köşesi onaylı şablonda saklanır; arayüzde global override yok.
            corner_radius = None
            upscale_4k = bool(self.upscale_4k.get())
            auto_cloud_after_render = bool(self.auto_cloud_link.get())
            upscale_model = "fast" if self.upscale_model.get().startswith("Hızlı") else "photo"
            if upscale_4k:
                upscale_preflight(enabled=True, model=upscale_model)
        except (ValueError, KeyError, UpscaleError) as exc:
            messagebox.showwarning("Üretim Ayarları", str(exc), parent=self.window)
            return

        try:
            design_count = sum(1 for _ in iter_designs(Path(design_folder)))
            if design_count == 0:
                raise ValueError("Seçili klasörde desteklenen baskı tasarımı yok.")
        except OSError as exc:
            messagebox.showwarning("Tasarım Klasörü", str(exc), parent=self.window)
            return
        if selected_stores:
            try:
                approved=[self.template_items[uid] for uid in self.mapping]
                plan=StoreProfiles(self.batch_engine.root).plan(selected_stores,approved,selected_uids=selected)
                pair_count=sum(len(store_templates) for _,store_templates in plan)
            except (ValueError,KeyError,OSError) as exc:
                messagebox.showwarning("Mağaza İzolasyonu",str(exc),parent=self.window)
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
        selected = [self.mapping[int(i)] for i in self.listbox.curselection()]
        item = next((self.template_items.get(uid) for uid in selected
                     if self.template_items.get(uid, {}).get('category') in (GLASS | DAYLIGHT)), None)
        if not item:
            messagebox.showinfo("Efekt Şablonu", "Önce cam, ahşap tablo veya PETEK kategorisinden bir şablon seçin.", parent=self.window)
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
        self.progress.set('Kategoriye uygun malzeme efekti A/B önizlemesi hazırlanıyor...')
        def work():
            try:
                src = Path(item['source'])
                scene = petek_engine.read_bgr(src)
                proxy, _ = prepare_render_artwork(art,self.batch_engine.root/'working_art_proxies')
                if item['category']=='06_Petek_Kapama':
                    profile,mask=self.petek_registry.get(item['uid'],require_approved=True)
                    baseline,_,_=render_with_cutout_paste(
                        src,proxy,item['quad'],mask,item['physical_aspect'],
                        placement=placement,lighting='natural',marketplace=False)
                    reflected=apply_material_finish(scene,baseline,mask,
                                                     item['quad'],item['category'])
                    effect_qa=measure_effect(baseline,reflected,mask,item['category'])
                    disabled=petek_engine.canvas_3x4(baseline)
                    enabled=petek_engine.canvas_3x4(reflected)
                else:
                    mask = _build_legacy_category_mask(scene,item['quad'],item.get('legacy_data'))
                    radius = float(item.get('legacy_data',{}).get('glass_corner_radius',.008))
                    args=(src,proxy,item['quad'],mask,item['physical_aspect'])
                    common=dict(category=item['category'],corner_radius=radius,
                                lighting='natural',placement=placement,marketplace=False)
                    baseline,_=_render_legacy_six_cover(*args,glass_effect='off',**common)
                    reflected,_=_render_legacy_six_cover(*args,glass_effect='on',**common)
                    effect_qa=measure_effect(baseline,reflected,mask,item['category'])
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
        popup.title('Malzeme Efekti A/B — Gerçek Baskı Önizlemesi')
        popup.geometry('870x680')
        images=[]
        for title,frame in [('Efekt KAPALI',before),('Efekt AÇIK',after)]:
            pil=Image.fromarray(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB))
            pil.thumbnail((395,555),Image.Resampling.LANCZOS)
            images.append(ImageTk.PhotoImage(pil,master=popup))
        slots=ttk.Frame(popup,padding=10); slots.pack(fill='both',expand=True)
        for j,title in enumerate(('Efekt KAPALI','Efekt AÇIK')):
            frame=ttk.Frame(slots);frame.pack(side='left',fill='both',expand=True)
            ttk.Label(frame,text=title,font=('Segoe UI',11,'bold')).pack()
            ttk.Label(frame,image=images[j]).pack(pady=8)
        ttk.Label(
            popup,
            text=('Otomatik QA: '+qa['status']+
                  f" | Maske dışı değişen piksel: {qa['protected_pixel_changes']}"+
                  f" | Ortalama ışık farkı: {qa['mean_inside_delta']}"+
                  f" | Yazı/kenar farkı: {qa['detail_edge_delta']}"+
                  ' — GERÇEK GÖRSELİ İNSAN ONAYLAMALI'),
            wraplength=825,
        ).pack(pady=5)
        popup._keep_image_refs=images
        ttk.Label(popup,text=f'{uid} / {artname} — yalnız geçici önizleme; kaynakları ve onaylı dört köşeleri değiştirmez.',
                  wraplength=820).pack(pady=8)

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
            messagebox.showerror("Bulut Anahtarı Yok",
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
            messagebox.showerror('Devam Kontrolü Hatası',str(exc),parent=self.window)
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
            messagebox.showerror("Özet Hatası", str(exc), parent=self.window)

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
            messagebox.showerror("Pazaryeri Excel Hatası",str(exc),parent=self.window)

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
            messagebox.showerror("Denetim Hatası", str(exc), parent=self.window)

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
                "Yarım dosyaları KARANTINA_KESINTI klasörüne taşıyıp kuyruğu güvenli şekilde kurtarmak istiyor musunuz?"
            )
            if messagebox.askyesno("Kullanıcı Onaylı Kesinti Kurtarma", summary, parent=self.window):
                receipt = self.batch_engine.recover(
                    reviewer="Windows Operator",
                    confirm="I_APPROVE_SAFE_CRASH_RECOVERY",
                    requeue_review_required=False,
                )
                self._log("KESİNTİ KURTARMA TAMAMLANDI: " + str(receipt["report_path"]))
                self.progress.set(
                    f"Kurtarıldı: {len(receipt['cleared_interrupted_keys'])} yarım kayıt temizlendi, "
                    f"{receipt['preserved_rendered_verified_count']} sağlam çıktı korundu."
                )
        except Exception as exc:
            messagebox.showerror("Kesinti Kurtarma Hatası", str(exc), parent=self.window)

    def safe_close(self) -> None:
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
                if kind == "log":
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


def open_unified_v4_window(parent, *, runtime_root=None, petek_registry=None, v4_root=None):
    return UnifiedV4BatchWindow(
        parent,
        runtime_root=runtime_root,
        petek_registry=petek_registry,
        v4_root=v4_root,
    )
