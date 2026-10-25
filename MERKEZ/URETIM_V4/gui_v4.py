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
from .cloud_excel_v43 import CloudExcel
from .design_proxy_v43 import prepare_render_artwork
from .upscale4k_v44 import preflight as upscale_preflight, UpscaleError
from .unified_batch import _render_legacy_six_cover, _build_legacy_category_mask
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
        self.window = tk.Toplevel(parent)
        self.window.title(VERSION_TEXT + " — 7 Kategori Üretim / Bulut Excel / İsteğe Bağlı 4K")
        self.window.geometry("1190x920")
        self.window.transient(parent)

        area = ttk.Frame(self.window, padding=18)
        area.pack(fill="both", expand=True)

        ttk.Label(
            area,
            text="7 Kategori Ortak Seri Üretim Merkezi (V4.5 — Duraklat/Devam, Sınırsız İş, 4K, Bulut Excel)",
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
        ttk.Button(btn_row, text="Cam A/B Önizleme (Gerçek Baskı)", command=self.start_ab_preview).pack(side="left", padx=6)
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
        ttk.Label(fit_row, text="Cam / Fotoğraf Efekti:").pack(side="left", padx=(12, 4))
        self.lighting = tk.StringVar(value=LIGHT_LABELS[0])
        ttk.Combobox(fit_row, textvariable=self.lighting, state="readonly", values=LIGHT_LABELS, width=36).pack(side="left")

        ttk.Label(area, text=(
            "Cam efektleri: Açık = yalnız cam panellere yumuşak ve görünür yansıma; "
            "Kapalı = yansıma yok. Ahşap/Wi-Fi/PETEK'te cam yansıması uygulanmaz.\n"
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

        actions = ttk.Frame(area)
        actions.pack(fill="x", pady=8)
        self.start_button = ttk.Button(actions, text="▶ 7 Kategori Seri Üretimi Başlat", command=self.start)
        self.start_button.pack(side="left", padx=3)
        ttk.Button(actions, text="⏸ Duraklat", command=self.pause_batch).pack(side="left", padx=3)
        ttk.Button(actions, text="▶ Devam Et", command=self.resume_batch).pack(side="left", padx=3)
        ttk.Button(actions, text="■ Güvenli Durdur", command=self.stop).pack(side="left", padx=3)
        ttk.Button(actions, text="Ortak Çıktı Klasörü", command=self.open_results).pack(side="left", padx=3)
        ttk.Button(actions, text="SHA Kayıtlarını Doğrula (Salt Okunur)", command=self.run_audit).pack(side="left", padx=3)
        ttk.Button(actions, text="Operasyon Özeti", command=self.show_operations).pack(side="left", padx=3)

        remote = ttk.Frame(area)
        remote.pack(fill="x", pady=5)
        self.cloud_button = ttk.Button(remote, text="☁ Mevcut Çıktıları HTTPS Linke Çevir + Excel'e Yaz",
                                       command=self.start_cloud_links)
        self.cloud_button.pack(side="left", padx=3)
        ttk.Button(remote, text="Pazaryeri Excel Şablonuna Aktar", command=self.export_marketplace_template).pack(side="left", padx=5)
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
        job_count = len(selected) * design_count
        if not messagebox.askyesno("Sınırsız Seri Üretimi Onayla",
            f"{len(selected)} onaylı şablon × {design_count} tasarım = {job_count:,} işlem denenecek.\n"
            "Her çıktı ayrı kayıtla korunur; işlemi istediğin zaman güvenli durdurabilirsin.\n"
            "BU İŞLEMİ BAŞLATMAK İSTİYOR MUSUN?", parent=self.window):
            return
        self.batch_engine.cancel.clear()
        self.batch_engine.resume()
        self.start_button.configure(state="disabled")

        def work():
            try:
                res = self.batch_engine.run(
                    design_folder,
                    selected_uids=selected,
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

        self.worker = threading.Thread(target=work, daemon=False)
        self.worker.start()
        self.progress.set("7 kategori ortak seri üretim çalışıyor...")

    def start_ab_preview(self):
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("Önizleme", "İşlem devam ederken yeni önizleme çalışmaz.", parent=self.window)
            return
        selected = [self.mapping[int(i)] for i in self.listbox.curselection()]
        item = next((self.template_items.get(uid) for uid in selected
                     if self.template_items.get(uid, {}).get('category') in GLASS), None)
        if not item:
            messagebox.showinfo("Cam Şablonu", "Önce bir Cam Tablo / Cam Doğrama / Ocak Arkası şablonu seçin.", parent=self.window)
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
        self.progress.set('Gerçek baskılı cam A/B önizlemesi hazırlanıyor...')
        def work():
            try:
                src = Path(item['source'])
                scene = petek_engine.read_bgr(src)
                mask = _build_legacy_category_mask(scene,item['quad'],item.get('legacy_data'))
                proxy, _ = prepare_render_artwork(art,self.batch_engine.root/'working_art_proxies')
                radius = float(item.get('legacy_data',{}).get('glass_corner_radius',.008))
                args=(src,proxy,item['quad'],mask,item['physical_aspect'])
                common=dict(category=item['category'],corner_radius=radius,
                            lighting='natural',placement=placement,marketplace=True)
                disabled,_=_render_legacy_six_cover(*args,glass_effect='off',**common)
                enabled,_=_render_legacy_six_cover(*args,glass_effect='on',**common)
                self.messages.put(('ab_done',(disabled,enabled,item['uid'],art.name)))
            except Exception as exc:
                self.messages.put(('ab_fail',str(exc)))
        self.worker=threading.Thread(target=work,daemon=False)
        self.worker.start()

    def show_ab(self, before, after, uid, artname):
        # Tk widgets must be constructed on the UI thread.
        popup=tk.Toplevel(self.window)
        popup.title('Cam A/B — Gerçek Baskı Önizlemesi')
        popup.geometry('870x680')
        images=[]
        for title,frame in [('Cam efekti KAPALI',before),('Cam efekti AÇIK',after)]:
            pil=Image.fromarray(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB))
            pil.thumbnail((395,555),Image.Resampling.LANCZOS)
            images.append(ImageTk.PhotoImage(pil,master=popup))
        slots=ttk.Frame(popup,padding=10); slots.pack(fill='both',expand=True)
        for j,title in enumerate(('Cam efekti KAPALI','Cam efekti AÇIK')):
            frame=ttk.Frame(slots);frame.pack(side='left',fill='both',expand=True)
            ttk.Label(frame,text=title,font=('Segoe UI',11,'bold')).pack()
            ttk.Label(frame,image=images[j]).pack(pady=8)
        popup._keep_image_refs=images
        ttk.Label(popup,text=f'{uid} / {artname} — yalnız geçici önizleme; kaynakları ve onaylı dört köşeleri değiştirmez.',
                  wraplength=820).pack(pady=8)

    def start_cloud_links(self) -> None:
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
        self.worker = threading.Thread(target=run_cloud, daemon=False)
        self.worker.start()
        self.progress.set("Bulut HTTPS görselleri linkleniyor; mevcut mockuplar yeniden üretilmiyor...")

    def pause_batch(self) -> None:
        if self.worker and self.worker.is_alive():
            self.batch_engine.request_pause()
            self.progress.set("Duraklatma istendi: devam eden iş güvenle tamamlanınca bekleyecek.")

    def resume_batch(self) -> None:
        self.batch_engine.resume()
        if self.worker and self.worker.is_alive():
            self.progress.set("Kaldığı işten devam ediliyor.")

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
        if self.worker and self.worker.is_alive():
            messagebox.showwarning("Çalışan İş Var", "Üretim/bağlantı işlemi bitmeden Excel şablonu aktarılmaz.", parent=self.window)
            return
        template = filedialog.askopenfilename(parent=self.window, title="Pazaryerinden alınmış BOŞ XLSX ürün şablonunu seçin",
                                              filetypes=[("Excel XLSX", "*.xlsx")])
        if not template:
            return
        if not messagebox.askyesno("Yeni Excel Oluştur", "Boş şablonun orijinali korunacak. Yalnız SHA doğrulanmış ve "
                                    "HTTPS bağlantısı hazır ürünlerin SKU/Görsel 1 alanları aktarılacak. "
                                    "Barkod, SEO ve pazaryeri zorunlu alanları uydurulmayacak. Devam edilsin mi?",
                                    parent=self.window):
            return
        try:
            from .marketplace_excel_v45 import export_from_template
            result = export_from_template(Path(template), self.batch_engine.root,
                                          self.batch_engine.ledger.successful(),
                                          report_root=self.batch_engine.reports)
            messagebox.showinfo("Pazaryeri Excel Hazır", f"{result['rows']} ürün: {result['output']}\n"
                               "Barkod, kategori ve diğer zorunlu alanları yüklemeden önce kontrol edin.", parent=self.window)
            self._log("Pazaryeri şablon kopyası: " + result['output'])
        except (ValueError, OSError, RuntimeError) as exc:
            messagebox.showerror("Pazaryeri Excel Aktarım Hatası", str(exc), parent=self.window)

    def stop(self) -> None:
        self.batch_engine.request_stop()
        self.progress.set("Güvenli durdurma istendi...")

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
                    self.progress.set(
                        f"{value['status']} — Üretilen: {value['rendered']}, "
                        f"Tekrar: {value['reused']}, Atlanan: {value['rejected']}. "
                        f"Excel: {value['xlsx']}"
                    )
                    self.start_button.configure(state="normal")
                    self.cloud_button.configure(state="normal")
                    quality = value.get("upscale_4k", {})
                    if quality.get("status") != "DISABLED":
                        info = (f"4K: başarılı {quality.get('upscaled', 0)}, "
                                f"tekrar {quality.get('reused', 0)}, hata {quality.get('failed', 0)}. "
                                f"4K Excel: {quality.get('report', '(çıktı yok)')}")
                        self._log(info)
                        self.progress.set(self.progress.get() + " | " + info)
                elif kind == "ab_done":
                    self.show_ab(*value)
                    self.progress.set('Cam A/B gerçek baskı önizlemesi hazır. Kaynak veya DB değiştirilmedi.')
                elif kind == "ab_fail":
                    self.progress.set('Cam A/B önizleme başarısız: ' + str(value))
                    self._log('ÖNİZLEME HATA: ' + str(value))
                elif kind == "cloud_done":
                    self.progress.set(f"BULUT {value['status']} — Linkli: {value['linked']}, "
                                      f"Yeni: {value['uploaded']}, Mevcut: {value['reused']}, Hata: {value['failed']}. "
                                      f"HTTPS Excel: {value['xlsx']}")
                    self.start_button.configure(state="normal")
                    self.cloud_button.configure(state="normal")
                elif kind == "fail":
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
