"""Tkinter yardımcıları: 4 Mockup modu paneli, ön kontrol ve üretim geçmişi penceresi."""
from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any

from PIL import Image, ImageTk

from . import four_mockup_v1 as fm
from . import uretim_gecmisi_v1 as history
from .store_profiles_v47 import StoreProfiles

try:
    from URETIM_V4 import ui_table_v1 as _table_tools
except Exception:
    _table_tools = None


def _fmt_seconds(value) -> str:
    if value is None:
        return "—"
    value = float(value)
    return f"{value:.0f} sn" if value < 120 else f"{value / 60:.1f} dk"


class FourMockupPanel:
    """Mod seçimi, slot/overlay ayarları, ön kontrol ve geçmiş düğmeleri."""

    def __init__(self, owner, parent: ttk.Frame):
        self.owner = owner
        self.enabled_var = tk.BooleanVar(value=False)
        self.pinned: dict[str, dict[str, str]] | None = None
        self.overlays = fm.normalize_overlays(None)
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=(5, 2))
        ttk.Checkbutton(
            row, text="4 Farklı Mockup · 4 Farklı Final Görsel Modu (76 / 96 / 116 / 136 cm)",
            variable=self.enabled_var, command=self._toggled).pack(side="left")
        ttk.Button(row, text="Slot ve Overlay Ayarları…", command=self.open_settings).pack(side="left", padx=(8, 0))
        ttk.Button(row, text="Üretim Öncesi Kontrol", command=self.show_preflight).pack(side="left", padx=(8, 0))
        ttk.Button(row, text="Üretim Geçmişi", command=lambda: show_history_window(owner)).pack(side="left", padx=(8, 0))

    def enabled(self) -> bool:
        return bool(self.enabled_var.get())

    def _toggled(self) -> None:
        if self.enabled():
            self.owner.petek_overlay_enabled.set(False)
            if hasattr(self.owner, "auto_cloud_link"):
                self.owner.auto_cloud_link.set(True)  # final görseller üretimle birlikte otomatik linklenir
        try:
            self.owner._refresh_selection_summary()
        except Exception:
            pass

    def overlay_mode_changed(self) -> None:
        if self.owner.petek_overlay_enabled.get() and self.enabled():
            self.enabled_var.set(False)

    # -- plan ---------------------------------------------------------------
    def _plan(self):
        stores = self.owner._chosen_stores()
        if not stores:
            raise ValueError("4 Mockup modu için en az bir mağaza seçin.")
        approved = list(self.owner.all_templates)
        result = StoreProfiles(self.owner.batch_engine.root).plan_resilient(stores, approved)
        return result["groups"]

    def _design_count(self) -> int:
        from .unified_batch import iter_designs
        folder = Path(self.owner.design_folder.get().strip())
        return sum(1 for _ in iter_designs(folder)) if folder.is_dir() else 0

    def preflight(self) -> dict[str, Any]:
        plan = self._plan()
        spi = history.average_seconds_per_image(self.owner.batch_engine.root, "four_mockup")
        engine = self.owner.batch_engine
        slot_mode = self.owner.petek_slot_mode.get() if hasattr(self.owner, "petek_slot_mode") else "off"
        pink = bool(self.owner.petek_pink_cleanup.get()) if hasattr(self.owner, "petek_pink_cleanup") else False
        report = fm.preflight(plan, design_count=self._design_count(), pinned=self.pinned,
                              seconds_per_image=spi,
                              health=lambda tpl: engine.template_health(
                                  tpl, petek_slot_mode=slot_mode, petek_pink_cleanup=pink))
        report["seconds_per_image"] = spi
        return report

    def prepare_for_start(self):
        """Return (engine config, selected uid list) or raise ValueError."""
        report = self.preflight()
        if not report["ready"]:
            raise ValueError("Eksik şablon:\n" + "\n".join(report["problems"]))
        if not report["designs"]:
            raise ValueError("Baskı tasarımı klasöründe görsel yok.")
        uids = sorted({uid for mapping in report["slots"].values() for uid in mapping.values()})
        return {"slots": report["slots"], "overlays": self.overlays}, uids

    def show_preflight(self) -> None:
        win = self.owner.window
        try:
            report = self.preflight()
        except Exception as exc:
            messagebox.showwarning("Üretim Öncesi Kontrol", str(exc), parent=win)
            return
        lines = [f"Hesap: {report['formula']}", ""]
        for store, mapping in report["slots"].items():
            lines.append(f"{store}: " + " · ".join(f"{fm.cm_number(cm)} cm = {uid}" for cm, uid in mapping.items()))
        if report.get("notes"):
            lines += ["", "Otomatik seçimden çıkarılan sağlıksız şablonlar (kalite korumaları gevşetilmedi):"] + report["notes"]
        if report["problems"]:
            lines += ["", "EKSİKLER (üretim başlatılamaz, şablon tekrarı yapılmaz):"] + report["problems"]
        if report["estimated_seconds"] is not None:
            lines += ["", f"Tahmini süre (geçmiş ölçüm {report['seconds_per_image']} sn/görsel): "
                          f"{_fmt_seconds(report['estimated_seconds'])}"]
        else:
            lines += ["", "Tahmini süre: henüz ölçülmüş 4 Mockup geçmişi yok."]
        off = [fm.cm_number(cm) for cm, spec in self.overlays.items() if not spec["enabled"]]
        if off:
            lines.append("Overlay kapalı: " + ", ".join(off) + " cm (kimlik değişmez)")
        (messagebox.showinfo if report["ready"] else messagebox.showwarning)(
            "Üretim Öncesi Kontrol", "\n".join(lines), parent=win)

    # -- ayar penceresi -------------------------------------------------------
    def open_settings(self) -> None:
        win = self.owner.window
        try:
            plan = self._plan()
        except Exception as exc:
            messagebox.showwarning("4 Mockup Ayarları", str(exc), parent=win)
            return
        auto, problems = fm.plan_slots(plan, None)
        top = tk.Toplevel(win)
        top.title("4 Mockup · Slot ve Overlay Ayarları")
        top.geometry("920x640")
        top.transient(win)
        thumbs: dict[str, ImageTk.PhotoImage] = {}
        body = ttk.Frame(top, padding=10)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="Slot = ölçü kimliği. Aynı mağazada bir şablon yalnız bir slota atanır; "
                             "seçim üretim başladığında sabitlenir.", wraplength=860).pack(anchor="w")
        notebook = ttk.Notebook(body)
        notebook.pack(fill="both", expand=True, pady=6)
        slot_vars: dict[str, dict[str, tk.StringVar]] = {}
        sources = {str(t["uid"]): t for t in self.owner.all_templates}

        def thumb(uid: str, label: ttk.Label):
            item = sources.get(uid)
            try:
                with Image.open(item["source"]) as img:
                    img.thumbnail((84, 84))
                    thumbs[uid] = ImageTk.PhotoImage(img.convert("RGB"))
                label.configure(image=thumbs[uid])
            except Exception:
                label.configure(image="", text="önizleme yok")

        for store, items in plan:
            petek = sorted({str(t["uid"]) for t in items if t.get("category") == fm.PETEK_CATEGORY}, key=fm._natural)
            frame = ttk.Frame(notebook, padding=8)
            notebook.add(frame, text=f"{store} ({len(petek)} PETEK şablonu)")
            if len(petek) < 4:
                ttk.Label(frame, foreground="#A94442",
                          text=f"Yalnız {len(petek)} PETEK şablonu atanmış; 4 gerekli. Mağaza profiline şablon ekleyin.").pack(anchor="w")
            current = (self.pinned or {}).get(store) or auto.get(store) or {}
            slot_vars[store] = {}
            for cm in fm.VARIATIONS:
                line = ttk.Frame(frame)
                line.pack(fill="x", pady=3)
                ttk.Label(line, text=f"{fm.cm_number(cm)} cm", width=8, font=("Segoe UI", 10, "bold")).pack(side="left")
                var = tk.StringVar(value=current.get(cm, ""))
                slot_vars[store][cm] = var
                preview = ttk.Label(line, width=12)
                combo = ttk.Combobox(line, textvariable=var, values=petek, state="readonly", width=36)
                combo.pack(side="left", padx=6)
                preview.pack(side="left")
                combo.bind("<<ComboboxSelected>>", lambda _e, v=var, p=preview: thumb(v.get(), p))
                if var.get():
                    thumb(var.get(), preview)
        ov = ttk.LabelFrame(body, text="Ölçü etiketi (sağ alt köşe, sıfır kenar boşluğu)", padding=8)
        ov.pack(fill="x")
        ov_vars: dict[str, dict[str, Any]] = {}
        previews: dict[str, ImageTk.PhotoImage] = {}

        def refresh_preview(cm: str, canvas: tk.Canvas):
            spec = {"enabled": ov_vars[cm]["enabled"].get(), "path": ov_vars[cm]["path"].get() or None,
                    "allow_mismatch": True}
            canvas.delete("all")
            try:
                label, _ = fm.resolve_label(cm, spec, 1200, self._label_dir(), 'onizleme')
            except Exception as exc:
                canvas.create_text(5, 20, anchor="w", text=str(exc)[:40], fill="#A94442")
                return
            base = Image.new("RGB", (240, 56), (200, 200, 200))
            if label is not None:
                small = label.resize((max(1, round(label.width / 5)), max(1, round(label.height / 5))))
                base.paste(small, (240 - small.width, 56 - small.height), small)
            previews[cm] = ImageTk.PhotoImage(base)
            canvas.create_image(0, 0, anchor="nw", image=previews[cm])

        for cm in fm.VARIATIONS:
            spec = self.overlays[cm]
            ov_vars[cm] = {"enabled": tk.BooleanVar(value=spec["enabled"]),
                           "path": tk.StringVar(value=spec["path"] or "")}
            line = ttk.Frame(ov)
            line.pack(fill="x", pady=2)
            canvas = tk.Canvas(line, width=240, height=56, highlightthickness=1)
            ttk.Checkbutton(line, text=f"{fm.cm_number(cm)} cm Overlay Uygula",
                            variable=ov_vars[cm]["enabled"],
                            command=lambda c=cm, cv=canvas: refresh_preview(c, cv)).pack(side="left")
            ttk.Label(line, textvariable=ov_vars[cm]["path"], width=34).pack(side="left", padx=6)

            def choose(c=cm, cv=canvas):
                path = filedialog.askopenfilename(parent=top, title="Özel overlay PNG", filetypes=[("PNG", "*.png")])
                if path:
                    ov_vars[c]["path"].set(path)
                    refresh_preview(c, cv)
            ttk.Button(line, text="Özel dosya…", command=choose).pack(side="left")
            ttk.Button(line, text="Varsayılan", command=lambda c=cm, cv=canvas: (
                ov_vars[c]["path"].set(""), refresh_preview(c, cv))).pack(side="left", padx=4)
            canvas.pack(side="right")
            refresh_preview(cm, canvas)

        def apply():
            pinned: dict[str, dict[str, str]] = {}
            for store, mapping in slot_vars.items():
                chosen = {cm: var.get() for cm, var in mapping.items()}
                if len(set(chosen.values())) != 4 or "" in chosen.values():
                    messagebox.showwarning("Slot", f"{store}: dört slota dört farklı şablon seçilmeli.", parent=top)
                    return
                pinned[store] = chosen
            new_overlays = {}
            for cm in fm.VARIATIONS:
                path = ov_vars[cm]["path"].get() or None
                allow = False
                if path and fm.check_overlay_name(cm, path):
                    allow = messagebox.askyesno(
                        "Ölçü uyuşmazlığı riski", fm.check_overlay_name(cm, path) +
                        "\n\nYine de bu dosya kullanılsın mı? (Excel kimliği değişmez.)", parent=top)
                    if not allow:
                        return
                new_overlays[cm] = {"enabled": ov_vars[cm]["enabled"].get(), "path": path,
                                    "allow_mismatch": allow}
            self.pinned = pinned
            self.overlays = fm.normalize_overlays(new_overlays)
            top.destroy()
        bar = ttk.Frame(body)
        bar.pack(fill="x", pady=(8, 0))
        ttk.Button(bar, text="Kaydet", command=apply).pack(side="right")
        ttk.Button(bar, text="Vazgeç", command=top.destroy).pack(side="right", padx=6)

    def _label_dir(self):
        root = getattr(self.owner, "runtime_root", None)
        return Path(root) / "Overlay_Giydirme" / fm.LABEL_FOLDER if root else None


def show_history_window(owner) -> None:
    """Salt okunur üretim geçmişi: mağaza, klasör, adet, süre."""
    top = tk.Toplevel(owner.window)
    top.title("Üretim Geçmişi")
    top.geometry("1180x520")
    top.transient(owner.window)
    columns = ("Tarih", "Mod", "Mağaza", "Klasör", "Adet", "Hata", "Süre", "sn/görsel", "Durum")
    tree = ttk.Treeview(top, columns=columns, show="headings")
    widths = (140, 90, 160, 330, 60, 50, 80, 80, 110)
    for name, width in zip(columns, widths):
        tree.heading(name, text=name)
        tree.column(name, width=width, anchor="w")
    scroll = ttk.Scrollbar(top, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scroll.set)
    if _table_tools is not None:
        _table_tools.enhance_tree(tree, columns)
    tree.pack(side="left", fill="both", expand=True)
    scroll.pack(side="right", fill="y")
    if _table_tools is not None:
        _table_tools.add_packed_horizontal_scrollbar(top, tree)
    modes = {"standard": "Standart", "overlay4": "1 Mockup 4 Overlay", "four_mockup": "4 Mockup"}

    def load() -> None:
        tree.delete(*tree.get_children())
        for s in history.list_sessions(owner.batch_engine.root):
            per_store = (s.get("per_store") or {}).get("outputs") or {}
            stores = ", ".join(f"{name}: {count}" for name, count in per_store.items()) or ", ".join(s.get("stores") or [])
            tree.insert("", "end", values=(
                s.get("started_at", ""), modes.get(s.get("mode"), s.get("mode")) + (" (harici)" if s.get("external") else ""),
                stores, s.get("design_folder", ""), s.get("successful", 0), s.get("failed", 0),
                _fmt_seconds(s.get("elapsed_seconds")), s.get("seconds_per_image") or "—", s.get("status", "")))
    load()
    ttk.Button(top, text="Yenile", command=load).place(relx=1.0, rely=1.0, x=-90, y=-8, anchor="se")
