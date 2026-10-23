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

from PETEK_V3.registry import Registry as PetekRegistry
from .unified_batch import UnifiedV4Batch

LIGHT_LABELS = ("Doğal (Önerilen)", "Belirgin Işık", "Işıksız / Tasarım Orijinal")


def _lighting_code(value: str) -> str:
    return {
        "Doğal (Önerilen)": "natural",
        "Belirgin Işık": "strong",
        "Işıksız / Tasarım Orijinal": "off",
    }.get(value, value)


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
        self.window.title("V4.2.1 — Birleşik 7 Kategori Seri Üretim")
        self.window.geometry("1060x790")
        self.window.transient(parent)

        area = ttk.Frame(self.window, padding=18)
        area.pack(fill="both", expand=True)

        ttk.Label(
            area,
            text="7 Kategori Ortak Seri Üretim Merkezi (V4.2 — Sınırsız Onaylı Şablon)",
            font=("Segoe UI", 15, "bold"),
        ).pack(anchor="w", pady=(0, 6))
        ttk.Label(
            area,
            text="Eski 6 kategori (SQLite APPROVED) + 7. kategori PETEK (APPROVED) tek kalıcı kuyrukta birleşir.\n"
            "10 şablon sınırı kaldırılmıştır. Tüm çıktılar sıfır-blur (Tam Doldur) ve SHA-256 doğrulamalıdır.",
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
        self.photo_label = ttk.Label(photo_column, text='Mockup önizlemesi', anchor='center')
        self.photo_label.pack(fill='both', expand=True)
        self.photo_text = tk.StringVar(value='Onaylı şablon seçin.')
        ttk.Label(photo_column, textvariable=self.photo_text, wraplength=222).pack(fill='x')
        self.photo_ref = None
        self.template_sources = {}
        self.mapping: list[str] = []

        btn_row = ttk.Frame(area)
        btn_row.pack(fill="x", pady=3)
        ttk.Button(btn_row, text="Tüm Onaylı Şablonları Yenile", command=self.reload).pack(side="left")
        ttk.Button(btn_row, text="Tümünü Seç (Sınırsız)", command=self.select_all).pack(side="left", padx=6)
        ttk.Button(btn_row, text="Kesinti / Kilit Kurtarma Kontrolü", command=self.open_recovery).pack(side="left", padx=6)

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
        ttk.Label(opts, text="İş Sınırı (Max 100.000):").pack(side="left", padx=(16, 4))
        self.limit = tk.StringVar(value="25000")
        ttk.Entry(opts, textvariable=self.limit, width=10).pack(side="left")

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
        ttk.Label(fit_row, text="Fotoğraf Işığı:").pack(side="left", padx=(12, 4))
        self.lighting = tk.StringVar(value=LIGHT_LABELS[0])
        ttk.Combobox(fit_row, textvariable=self.lighting, state="readonly", values=LIGHT_LABELS, width=24).pack(side="left")

        round_row = ttk.Frame(area)
        round_row.pack(fill='x', pady=4)
        ttk.Label(round_row, text='Cam baskı köşeleri (onaylı 4 nokta sabit):').pack(side='left')
        self.corner_option = tk.StringVar(value='Hafif (%0,8)')
        ttk.Combobox(round_row, textvariable=self.corner_option, state='readonly', width=22,
                     values=('Kapalı (%0)', 'Hafif (%0,8)', 'Belirgin (%1,5)')).pack(side='left', padx=8)
        ttk.Label(round_row, text='Cam kategorilerinde uygulanır; ahşap/PETEK değişmez.').pack(side='left')

        actions = ttk.Frame(area)
        actions.pack(fill="x", pady=8)
        self.start_button = ttk.Button(actions, text="▶ 7 Kategori Seri Üretimi Başlat", command=self.start)
        self.start_button.pack(side="left", padx=3)
        ttk.Button(actions, text="■ Güvenli Durdur", command=self.stop).pack(side="left", padx=3)
        ttk.Button(actions, text="Ortak Çıktı Klasörü", command=self.open_results).pack(side="left", padx=3)
        ttk.Button(actions, text="Ortak Kayıtları Denetle", command=self.run_audit).pack(side="left", padx=3)

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
            self.photo_label.configure(image='', text='Mockup önizlemesi')
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
            self.photo_text.set(f'{uid} — gerçek mockup fotoğrafı')
        except (OSError, ValueError) as exc:
            self.photo_ref = None
            self.photo_label.configure(image='', text='Fotoğraf açılamadı')
            self.photo_text.set('HATA: ' + str(exc))

    def reload(self) -> None:
        self.listbox.delete(0, "end")
        self.mapping = []
        self.template_sources = {}
        try:
            templates, audit = self.batch_engine.discover_templates(per_category_limit=None)
            for item in templates:
                label = f"[{item['category']}] {item['uid']} ({item['orientation']})"
                self.mapping.append(item["uid"])
                self.template_sources[item["uid"]] = Path(item["source"])
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
            max_jobs = int(self.limit.get())
            if not (1 <= max_jobs <= 100000):
                raise ValueError("İş sınırı 1 ile 100.000 arasında olmalı.")
            placement = "cover" if self.placement.get().startswith("Tam Doldur") else "contain"
            lighting = _lighting_code(self.lighting.get())
            corner_radius = {"Kapalı (%0)": 0.0, "Hafif (%0,8)": .008,
                             "Belirgin (%1,5)": .015}[self.corner_option.get()]
        except (ValueError, KeyError) as exc:
            messagebox.showwarning("Üretim Ayarları", str(exc), parent=self.window)
            return

        self.batch_engine.cancel.clear()
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
                )
                self.messages.put(("done", res))
            except Exception as exc:
                self.messages.put(("fail", str(exc)))

        self.worker = threading.Thread(target=work, daemon=False)
        self.worker.start()
        self.progress.set("7 kategori ortak seri üretim çalışıyor...")

    def stop(self) -> None:
        self.batch_engine.cancel.set()
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
                elif kind == "fail":
                    self.progress.set("DURDU — " + str(value))
                    self.start_button.configure(state="normal")
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
