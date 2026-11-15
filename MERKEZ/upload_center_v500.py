"""Graphite V5.0 Görsel Yükleme Merkezi (Tk workspace panel)."""
from __future__ import annotations

import queue
import threading
import time
import json
import shutil
from datetime import datetime
import os
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from central_upload_v500 import (
    CentralUploader, MOCKUP_CATEGORIES, MOCKUP_LABELS, ORIENTATIONS,
)

try:
    from URETIM_V4 import ui_table_v1 as _table_tools
except Exception:
    _table_tools = None

try:
    from graphite_ui_components import module_header
except Exception:
    module_header = None

PANEL = '#131C2B'
PANEL_RAISED = '#182238'
SURFACE = '#0B101B'
BORDER = '#22304A'
FG = '#E9EFF9'
MUTED = '#66789B'
ACCENT = '#17D3A3'
BLUE = '#5AA9FF'
GREEN = '#3FD98A'
RED = '#EF6A73'
YELLOW = '#F0B84C'


def _label(parent, text='', size=9, color=FG, bold=False, **kwargs):
    return tk.Label(parent, text=text, bg=kwargs.pop('bg', parent.cget('bg')), fg=color,
                    font=('Segoe UI', size, 'bold' if bold else 'normal'),
                    anchor=kwargs.pop('anchor', 'w'), **kwargs)


def _button(parent, text, command, color=PANEL_RAISED, fg=FG, **kwargs):
    return tk.Button(parent, text=text, command=command, bg=color, fg=fg,
                     activebackground='#0B7A5F', activeforeground='#ffffff',
                     font=('Segoe UI', kwargs.pop('size', 9), 'bold'), relief='flat',
                     bd=0, highlightthickness=0, padx=10, pady=7,
                     cursor='hand2', **kwargs)


class UploadCenter:
    def __init__(self, app, host):
        self.app = app
        self.host = host
        self.uploader: CentralUploader | None = None
        self.mode = tk.StringVar(value='mockup')
        self.category = tk.StringVar(value=MOCKUP_CATEGORIES[0])
        self.orientation = tk.StringVar(value='Yatay')
        self.prefix = tk.StringVar(value='')
        self.files: list[Path] = []
        self.source_root: Path | None = None
        self.queue: queue.Queue = queue.Queue()
        self.running = False
        self._upload_started_at = None
        self._upload_total = 0
        self._upload_success = 0
        self._upload_failed = 0
        self._upload_skipped = 0
        self._preflight_invalid = 0
        self._last_result = None
        self._last_report_context = {}
        self._preflight_groups = None
        self._preflight_scope = ''
        self._preflight_token = 0
        self._preflight_after = None
        self._summary_base = ''
        self._thumb_refs = []
        self._build()
        self._refresh()

    def _build(self):
        style = ttk.Style(self.host)
        try:
            style.theme_use('clam')
        except tk.TclError:
            pass
        style.configure('Upload.Horizontal.TProgressbar', troughcolor='#080C14',
                        background=ACCENT, lightcolor=ACCENT, darkcolor='#0FAC80',
                        bordercolor='#22304A', thickness=14)
        root = tk.Frame(self.host, bg=SURFACE)
        root.pack(fill='both', expand=True)
        root.grid_columnconfigure(0, weight=1)
        root.grid_columnconfigure(1, weight=1)
        root.grid_rowconfigure(3, weight=1)
        self.root = root

        header = (module_header(root, 'Görsel Yükleme Merkezi',
                                'Yeni mockup ve ham baskı tasarımlarını güvenli, çakışmasız ve tek akışta ekleyin.')
                  if module_header else tk.Frame(root, bg=SURFACE))
        header.grid(row=0, column=0, columnspan=2, sticky='ew', padx=22, pady=(24, 8))

        cards = tk.Frame(root, bg=SURFACE)
        cards.grid(row=1, column=0, columnspan=2, sticky='ew', padx=22, pady=(8, 12))
        cards.grid_columnconfigure(0, weight=1); cards.grid_columnconfigure(1, weight=1)
        self.mockup_card = _button(cards, 'A  ·  Mockup Görseli Yükle', lambda: self._set_mode('mockup'), color='#10332B', size=11)
        self.mockup_card.grid(row=0, column=0, sticky='ew', padx=(0, 6))
        self.design_card = _button(cards, 'B  ·  Tasarım Görseli Yükle', lambda: self._set_mode('design'), color=PANEL_RAISED, size=11)
        self.design_card.grid(row=0, column=1, sticky='ew', padx=(6, 0))

        controls = tk.Frame(root, bg=PANEL)
        controls.grid(row=2, column=0, columnspan=2, sticky='ew', padx=22, pady=(0, 10))
        controls.grid_columnconfigure(1, weight=1); controls.grid_columnconfigure(3, weight=1)
        self.category_label = _label(controls, 'Kategori', 9, MUTED, True, bg=PANEL)
        self.category_label.grid(row=0, column=0, sticky='w', padx=(14, 8), pady=(12, 4))
        self.category_box = ttk.Combobox(controls, textvariable=self.category,
                                         values=list(MOCKUP_CATEGORIES), state='readonly', width=28)
        self.category_box.grid(row=0, column=1, sticky='ew', padx=8, pady=(12, 4))
        self.category_box.bind('<<ComboboxSelected>>', lambda _e: self._refresh())
        self.orientation_label = _label(controls, 'Yön', 9, MUTED, True, bg=PANEL)
        self.orientation_label.grid(row=0, column=2, sticky='w', padx=(14, 8), pady=(12, 4))
        self.orientation_box = ttk.Combobox(controls, textvariable=self.orientation,
                                            values=list(ORIENTATIONS), state='readonly', width=15)
        self.orientation_box.grid(row=0, column=3, sticky='ew', padx=8, pady=(12, 4))
        self.orientation_box.bind('<<ComboboxSelected>>', lambda _e: self._refresh())
        self.prefix_label = _label(controls, 'İsteğe bağlı ön ek', 9, MUTED, True, bg=PANEL)
        self.prefix_label.grid(row=1, column=0, sticky='w', padx=(14, 8), pady=(4, 12))
        self.prefix_entry = tk.Entry(controls, textvariable=self.prefix, bg='#0F1622', fg=FG,
                                     insertbackground=FG, relief='flat', font=('Segoe UI', 9))
        self.prefix_entry.grid(row=1, column=1, sticky='ew', padx=8, pady=(4, 12))
        self.prefix.trace_add('write', lambda *_: self._refresh())
        self.target_label = _label(controls, '', 8, MUTED, False, bg=PANEL)
        self.target_label.grid(row=1, column=2, columnspan=2, sticky='w', padx=(14, 8), pady=(4, 12))

        root.paned = tk.PanedWindow(root, orient='horizontal', bg=SURFACE, bd=0,
                                    sashwidth=7, sashrelief='raised',
                                    sashcursor='sb_h_double_arrow')
        root.paned.grid(row=3, column=0, columnspan=2, sticky='nsew', padx=(0, 0), pady=(0, 12))
        root.grid_columnconfigure(0, weight=1)
        left = tk.Frame(root.paned, bg=PANEL)
        root.paned.add(left, minsize=340, sticky='nsew')
        left.grid_rowconfigure(2, weight=1); left.grid_columnconfigure(0, weight=1)
        _label(left, 'Kaynak görseller', 10, FG, True, bg=PANEL).grid(row=0, column=0, sticky='w', padx=14, pady=(12, 7))
        actions = tk.Frame(left, bg=PANEL)
        actions.grid(row=1, column=0, sticky='ew', padx=10, pady=(0, 8))
        _button(actions, '＋ Görselleri Seç', self.select_files, color=ACCENT, fg='#04140E', size=9).pack(side='left', padx=3)
        self.folder_button = _button(actions, '▣ Klasör İçe Aktar', self.select_folder, color=PANEL_RAISED, size=9)
        self.folder_button.pack(side='left', padx=3)
        _button(actions, 'Temizle', self.clear_files, color='#2E161A', size=9).pack(side='right', padx=3)
        self.file_list = tk.Listbox(left, bg='#0F1622', fg=FG, selectbackground='#0B7A5F',
                                    relief='flat', borderwidth=0, highlightthickness=0,
                                    font=('Segoe UI', 8), activestyle='none')
        self.file_list.grid(row=2, column=0, sticky='nsew', padx=10, pady=(0, 10))
        self.file_list.bind('<<ListboxSelect>>', lambda _e: self._refresh_thumbs())
        if _table_tools is not None:
            _table_tools.attach_listbox_tooltip(self.file_list)
            left.grid_rowconfigure(3, weight=0)
            _table_tools.add_listbox_xscroll(self.file_list, row=3, column=0,
                                             parent=left)

        right = tk.Frame(root.paned, bg=PANEL)
        root.paned.add(right, minsize=380, sticky='nsew')
        right.grid_columnconfigure(0, weight=1); right.grid_rowconfigure(4, weight=1)
        _label(right, 'Yükleme öncesi kontrol', 10, FG, True, bg=PANEL).grid(row=0, column=0, sticky='w', padx=14, pady=(12, 7))
        self.summary = _label(right, '', 9, MUTED, False, bg=PANEL, justify='left')
        self.summary.grid(row=1, column=0, sticky='ew', padx=14, pady=(0, 5))
        self.preview_names = tk.Listbox(right, height=4, bg='#0F1622', fg='#8FC2FF', relief='flat',
                                        borderwidth=0, highlightthickness=0, font=('Consolas', 8))
        self.preview_names.grid(row=2, column=0, sticky='ew', padx=14, pady=(0, 6))
        if _table_tools is not None:
            _table_tools.attach_listbox_tooltip(self.preview_names)
        self.thumbs = tk.Canvas(right, height=78, bg='#0F1622', highlightthickness=0)
        self.thumbs.grid(row=3, column=0, sticky='ew', padx=14, pady=(0, 7))
        self.progress = ttk.Progressbar(right, mode='determinate', maximum=1,
                                        style='Upload.Horizontal.TProgressbar')
        self.progress.grid(row=4, column=0, sticky='ew', padx=14, pady=(7, 6))
        self.progress_text = _label(right, 'Hazır', 8, MUTED, False, bg=PANEL)
        self.progress_text.grid(row=5, column=0, sticky='w', padx=14)
        self.live_stats = _label(right, 'Başlayan: 0  ·  Başarılı: 0  ·  Hatalı: 0  ·  Atlanan: 0\nTahmini tamamlanma: —',
                                 8, MUTED, False, bg=PANEL, justify='left')
        self.live_stats.grid(row=6, column=0, sticky='ew', padx=14, pady=(2, 0))
        bottom = tk.Frame(right, bg=PANEL)
        bottom.grid(row=7, column=0, sticky='ew', padx=10, pady=(6, 10))
        self.upload_button = _button(bottom, 'Yüklemeyi Başlat', self.start_upload, color=ACCENT, fg='#04140E', size=10)
        self.upload_button.pack(side='left', padx=3)
        _button(bottom, 'Hedef Klasörü Aç', self.open_target, color=PANEL_RAISED, size=9).pack(side='left', padx=3)
        self.report_button = _button(bottom, 'Raporu Kaydet', self.save_report, color=PANEL_RAISED, size=9)
        self.report_button.pack(side='left', padx=3)
        self.report_button.configure(state='disabled')
        self.counts = _label(bottom, 'Başarılı: 0  ·  Hatalı: 0  ·  Atlanan: 0', 8, MUTED, False, bg=PANEL)
        self.counts.pack(side='right', padx=3)
        self.root.after(150, self._poll)

    def _set_mode(self, mode):
        self.mode.set(mode)
        self._last_result = None
        self._preflight_groups = None
        self.report_button.configure(state='disabled')
        self.mockup_card.configure(bg='#10332B' if mode == 'mockup' else PANEL_RAISED)
        self.design_card.configure(bg='#10332B' if mode == 'design' else PANEL_RAISED)
        self.category_label.grid() if mode == 'mockup' else self.category_label.grid_remove()
        self.category_box.grid() if mode == 'mockup' else self.category_box.grid_remove()
        self.orientation_label.grid() if mode == 'design' else self.orientation_label.grid_remove()
        self.orientation_box.grid() if mode == 'design' else self.orientation_box.grid_remove()
        self.prefix_label.grid() if mode == 'design' else self.prefix_label.grid_remove()
        self.prefix_entry.grid() if mode == 'design' else self.prefix_entry.grid_remove()
        self.folder_button.configure(text='▣ Klasör İçe Aktar' if mode == 'design' else '▣ Dosya Grubu Seç')
        self._refresh()

    def _get_uploader(self):
        if self.uploader is None or self.uploader.runtime != Path(self.app.runtime).resolve():
            self.uploader = CentralUploader(Path(self.app.runtime))
        return self.uploader

    def select_files(self):
        chosen = filedialog.askopenfilenames(parent=self.root, title='Görselleri Seç',
                                             filetypes=[('Desteklenen görseller', '*.jpg *.jpeg *.png *.webp')])
        if chosen:
            self._last_result = None
            self.report_button.configure(state='disabled')
            self.files = [Path(p) for p in chosen]
            self.source_root = None
            self._refresh()

    def select_folder(self):
        chosen = filedialog.askdirectory(parent=self.root, title='Görsel klasörünü seç')
        if chosen:
            self._last_result = None
            self.report_button.configure(state='disabled')
            self.source_root = Path(chosen)
            self.files = CentralUploader.collect_files([self.source_root], recursive=True)
            self._refresh()

    def clear_files(self):
        self._last_result = None
        self.report_button.configure(state='disabled')
        self.files = []; self.source_root = None; self._refresh()

    def _refresh_thumbs(self):
        self.thumbs.delete('all'); self._thumb_refs.clear()
        for idx, path in enumerate(self.files[:8]):
            try:
                from PIL import Image, ImageTk
                image = Image.open(path); image.thumbnail((68, 58))
                photo = ImageTk.PhotoImage(image.copy()); self._thumb_refs.append(photo)
                self.thumbs.create_image(8 + idx * 82, 6, image=photo, anchor='nw')
                self.thumbs.create_text(8 + idx * 82, 68, text=path.stem[:10], fill=MUTED, anchor='nw', font=('Segoe UI', 7))
            except Exception:
                pass

    def _refresh(self):
        try: uploader = self._get_uploader()
        except Exception as exc:
            self.summary.configure(text='Merkezi kayıt hazır değil: ' + str(exc), fg=RED)
            return
        kind = self.mode.get(); scope = self.category.get() if kind == 'mockup' else self.orientation.get()
        count = len(self.files)
        valid_count = 0
        for path in self.files:
            try:
                from central_upload_v500 import _verify_image
                _verify_image(path)
                valid_count += 1
            except Exception:
                pass
        invalid_count = max(0, count - valid_count)
        self._preflight_invalid = invalid_count
        high = uploader.registry.high(scope)
        target = (uploader._mockup_directory(scope, '2_SABLON_HAVUZU') if kind == 'mockup'
                  else uploader.runtime / 'HAM BASKI TASARIMLARI' / (scope + 'lar'))
        self.target_label.configure(text='Hedef: ' + str(target))
        self._summary_base = (f'Toplam: {count}  ·  Uygun: {valid_count}  ·  Hatalı/atlanacak: {invalid_count}\n'
                              f'Son kullanılan: {high:03d}  ·  Sonraki güvenli numara: {high + 1:03d}')
        self.summary.configure(text=self._summary_base, fg=MUTED)
        self.preview_names.delete(0, 'end')
        extensions = [path.suffix.lower() for path in self.files]
        for name in uploader.preview(kind, scope, count or 1, self.prefix.get(), extensions): self.preview_names.insert('end', '  ' + name)
        self.file_list.delete(0, 'end')
        for path in self.files: self.file_list.insert('end', '  ' + str(path))
        self._refresh_thumbs()
        if not self.running and self._last_result is None:
            self._upload_total = valid_count
            self._upload_success = self._upload_failed = self._upload_skipped = 0
            self.counts.configure(text='Başarılı: 0  ·  Hatalı: 0  ·  Atlanan: 0')
            self.live_stats.configure(text=f'Başlayan: 0/{valid_count}  ·  Başarılı: 0  ·  Hatalı: {invalid_count}  ·  Atlanan: 0\n'
                                             'Tahmini tamamlanma: —')
        self._schedule_preflight()

    def _schedule_preflight(self):
        if self._preflight_after is not None:
            try: self.root.after_cancel(self._preflight_after)
            except Exception: pass
        self._preflight_token += 1
        token = self._preflight_token
        self._preflight_groups = None
        if not self.files or self.running:
            return
        self.summary.configure(text=self._summary_base + '\nÖn kontrol: hazırlanıyor…')
        self.progress.configure(mode='indeterminate')
        self.progress.start(12)
        self._preflight_after = self.root.after(80, lambda: self._start_preflight_worker(token))

    def _start_preflight_worker(self, token):
        mode, files = self.mode.get(), list(self.files)
        category, orientation = self.category.get(), self.orientation.get()
        def work():
            try:
                groups, scope = self._preflight_upload(mode, files, category, orientation)
                self.queue.put(('preflight', token, groups, scope))
            except Exception as exc:
                self.queue.put(('preflight_error', token, str(exc)))
        threading.Thread(target=work, daemon=True, name='central-upload-preflight').start()

    @staticmethod
    def _format_duration(seconds):
        if seconds is None or seconds < 0 or seconds != seconds:
            return '—'
        seconds = int(round(seconds))
        minutes, remainder = divmod(seconds, 60)
        if minutes:
            return f'{minutes} dk {remainder:02d} sn'
        return f'{remainder} sn'

    def _update_live_stats(self, current, total, item=None):
        status = str((item or {}).get('status', '')).upper()
        if status.startswith('ERROR'):
            self._upload_failed += 1
        elif status.startswith('SKIPPED'):
            self._upload_skipped += 1
        elif status and status not in {'STARTED'}:
            self._upload_success += 1
        # The worker reports the actual operation total after its duplicate/
        # image validation pass; use that for the determinate bar and ETA.
        if total:
            self._upload_total = int(total)
        elapsed = (time.monotonic() - self._upload_started_at) if self._upload_started_at else 0
        remaining = None
        if current and elapsed > 0 and total and current < total:
            remaining = elapsed / current * (total - current)
        eta = self._format_duration(remaining) if remaining is not None else ('tamamlandı' if total and current >= total else 'hesaplanıyor…')
        percent = int(round((current / total) * 100)) if total else 0
        self.live_stats.configure(text=f'İlerleme: {current}/{total or 0} (%{percent})  ·  Başarılı: {self._upload_success}  ·  '
                                         f'Hatalı: {self._upload_failed}  ·  Atlanan: {self._upload_skipped}\n'
                                         f'Tahmini tamamlanma: {eta}')

    def open_target(self):
        try:
            uploader = self._get_uploader(); scope = self.category.get() if self.mode.get() == 'mockup' else self.orientation.get()
            target = uploader._mockup_directory(scope, '2_SABLON_HAVUZU') if self.mode.get() == 'mockup' else uploader.runtime / 'HAM BASKI TASARIMLARI' / (scope + 'lar')
            target.mkdir(parents=True, exist_ok=True)
            if hasattr(__import__('os'), 'startfile'): __import__('os').startfile(str(target))
        except Exception as exc: messagebox.showerror('Hedef klasör', str(exc), parent=self.root)

    def _preflight_upload(self, mode, files, category, orientation):
        """Read-only duplicate/validity scan performed immediately before upload."""
        uploader = self._get_uploader()
        candidates = uploader.collect_files(files, recursive=(mode == 'design'))
        seen = set()
        groups = {'new': [], 'duplicate': [], 'batch_duplicate': [], 'invalid': []}
        scope = category if mode == 'mockup' else orientation
        kind = 'mockup' if mode == 'mockup' else 'design'
        for source in candidates:
            try:
                digest = uploader.fingerprint(source)
                if digest in seen:
                    groups['batch_duplicate'].append((source, 'Aynı seçim içinde tekrar'))
                elif ((uploader.registry.duplicate_sha_anywhere(kind, digest) if kind == 'mockup'
                       else uploader.registry.duplicate_sha(kind, digest))):
                    groups['duplicate'].append((source, 'Daha önce başarıyla içeri alınmış'))
                else:
                    groups['new'].append((source, 'Yeni dosya'))
                seen.add(digest)
            except Exception as exc:
                groups['invalid'].append((source, str(exc)))
        return groups, scope

    def _confirm_preflight(self, groups, scope):
        duplicate = len(groups['duplicate'])
        batch_duplicate = len(groups['batch_duplicate'])
        skipped = duplicate + batch_duplicate
        new = len(groups['new'])
        invalid = len(groups['invalid'])
        total = new + skipped + invalid
        examples = []
        for key, label in (('duplicate', 'Daha önce alınan'), ('batch_duplicate', 'Paket içi tekrar'),
                           ('invalid', 'Hatalı')):
            for path, reason in groups[key][:3]:
                examples.append(f'• {label}: {path.name} — {reason}')
        detail = '\n'.join(examples)
        message = (f'Yükleme öncesi kontrol tamamlandı.\n\n'
                   f'Kategori/Yön: {scope}\nToplam: {total}\n'
                   f'Yeni ve içeri alınacak: {new}\n'
                   f'Daha önce alınmış, atlanacak: {duplicate}\n'
                   f'Aynı seçim içinde tekrar, atlanacak: {batch_duplicate}\n'
                   f'Hatalı/uygunsuz: {invalid}\n\n')
        if detail:
            message += 'Örnekler:\n' + detail + '\n\n'
        message += ('Yalnızca yeni ve uygun dosyalar içeri alınacak. İşlemi başlatmak istiyor musunuz?')
        return messagebox.askyesno('Yükleme öncesi ayrıntılı kontrol', message, parent=self.root)

    @staticmethod
    def _move_uploaded_sources(result, source_root):
        """Archive successes and quarantine exact duplicate source files.

        Duplicate files are moved to a recoverable ``kontrol et sil`` folder
        instead of being silently left mixed with the source set.  The folder
        is intentionally outside ``Yüklenenler`` and is ignored by the next
        recursive import.
        """
        moved = 0
        move_errors = []
        quarantined = 0
        quarantine_errors = []
        quarantine_name = 'kontrol et sil'
        if source_root:
            # Create the archive folder even when this batch has zero new
            # files, so the source-folder state is explicit after every run.
            Path(source_root).joinpath('Yüklenenler').mkdir(parents=True, exist_ok=True)
            Path(source_root).joinpath(quarantine_name).mkdir(parents=True, exist_ok=True)
        else:
            # File-by-file selection can span multiple arbitrary folders;
            # create one archive folder beside each selected source folder.
            for item in result.get('items', []):
                source = Path(str(item.get('source', '')))
                if source.parent:
                    source.parent.joinpath('Yüklenenler').mkdir(parents=True, exist_ok=True)
                    source.parent.joinpath(quarantine_name).mkdir(parents=True, exist_ok=True)
        for item in result.get('items', []):
            status = str(item.get('status', '')).upper()
            source = Path(str(item.get('source', '')))
            if not source.is_file() or status.startswith('ERROR'):
                continue
            base = Path(source_root) if source_root else source.parent
            try:
                relative = source.resolve().relative_to(base.resolve()) if source_root else Path(source.name)
            except ValueError:
                relative = Path(source.name)
            if status.startswith('SKIPPED'):
                destination = base / quarantine_name / relative
                if destination.resolve() == source.resolve():
                    continue
                destination.parent.mkdir(parents=True, exist_ok=True)
                if destination.exists():
                    stem, suffix = destination.stem, destination.suffix
                    index = 2
                    while destination.exists():
                        destination = destination.with_name(f'{stem} ({index}){suffix}')
                        index += 1
                try:
                    shutil.move(str(source), str(destination))
                    item['quarantined_to'] = str(destination)
                    quarantined += 1
                except OSError as exc:
                    item['quarantine_error'] = str(exc)
                    quarantine_errors.append({'source': str(source), 'error': str(exc)})
                continue
            destination = base / 'Yüklenenler' / relative
            if destination.resolve() == source.resolve():
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                stem, suffix = destination.stem, destination.suffix
                index = 2
                while destination.exists():
                    destination = destination.with_name(f'{stem} ({index}){suffix}')
                    index += 1
            try:
                shutil.move(str(source), str(destination))
                item['moved_to'] = str(destination)
                moved += 1
            except OSError as exc:
                item['move_error'] = str(exc)
                move_errors.append({'source': str(source), 'error': str(exc)})
        result['move_errors'] = move_errors
        result['quarantined'] = quarantined
        result['quarantine_errors'] = quarantine_errors
        return moved

    def save_report(self):
        """Save a human-readable JSON report for the latest upload attempt."""
        result = self._last_result
        if not result:
            messagebox.showinfo('Rapor', 'Önce bir yükleme işlemi başlatın; sonuç raporu burada görünecek.', parent=self.root)
            return
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        default_name = f'gorsel_yukleme_raporu_{stamp}.json'
        target = filedialog.asksaveasfilename(
            parent=self.root, title='Yükleme raporunu kaydet', initialfile=default_name,
            defaultextension='.json', filetypes=[('JSON raporu', '*.json'), ('Metin dosyası', '*.txt')])
        if not target:
            return
        payload = {
            'rapor_tarihi': datetime.now().isoformat(timespec='seconds'),
            'mod': self._last_report_context.get('mode'),
            'kategori_veya_yon': self._last_report_context.get('scope'),
            'kaynak_sayisi': self._last_report_context.get('source_count', len(result.get('items', []))),
            'ozet': {key: result.get(key, 0) for key in ('success', 'failed', 'skipped')},
            'Yüklenenler_klasorune_tasinan': result.get('moved', 0),
            'kontrol_et_sil_klasorune_tasinan': result.get('quarantined', 0),
            'aciklama': {
                'success': 'Başarıyla içeri alındı.',
                'failed': 'İçeri alınamadı; hata alanını kontrol edin.',
                'skipped': 'Aynı byte içeriğine sahip görsel daha önce alındı veya aynı işlem içinde tekrarlandı; kaynak kopya kontrol et sil klasörüne taşındı.'
            },
            'dosyalar': result.get('items', []),
        }
        temporary = target + '.tmp'
        try:
            with open(temporary, 'w', encoding='utf-8') as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.flush(); os.fsync(handle.fileno())
            os.replace(temporary, target)
            messagebox.showinfo('Rapor kaydedildi', f'{len(payload["dosyalar"])} dosyanın sonucu kaydedildi:\n{target}', parent=self.root)
        except Exception as exc:
            try: os.unlink(temporary)
            except OSError: pass
            messagebox.showerror('Rapor', f'Rapor kaydedilemedi: {exc}', parent=self.root)

    def start_upload(self):
        if self.running or not self.files:
            if not self.files: messagebox.showinfo('Görsel seçin', 'Önce en az bir görsel seçin.', parent=self.root)
            return
        mode, files, category, orientation, prefix, root = self.mode.get(), list(self.files), self.category.get(), self.orientation.get(), self.prefix.get(), self.source_root
        if self._preflight_groups is None:
            self.progress_text.configure(text='Ön kontrol henüz tamamlanmadı.')
            messagebox.showinfo('Ön kontrol sürüyor', 'Dosyaların daha önce yüklenip yüklenmediği hâlâ kontrol ediliyor. Birkaç saniye sonra tekrar deneyin.', parent=self.root)
            return
        if not self._confirm_preflight(self._preflight_groups, self._preflight_scope):
            self.progress_text.configure(text='Başlatılmadı · kullanıcı onayı bekleniyor.')
            return
        self.running = True; self._last_result = None; self._upload_started_at = time.monotonic()
        self._upload_success = self._upload_skipped = 0
        self._upload_failed = self._preflight_invalid
        self._upload_total = max(0, len(self.files))
        self.upload_button.configure(state='disabled')
        self.progress.stop(); self.progress.configure(mode='determinate', maximum=max(1, self._upload_total), value=0)
        self.live_stats.configure(text=f'Başlayan: 0/{self._upload_total}  ·  Başarılı: 0  ·  Hatalı: {self._upload_failed}  ·  Atlanan: 0\nTahmini tamamlanma: hesaplanıyor…')
        def work():
            try:
                uploader = self._get_uploader()
                callback = lambda current, total, item: self.queue.put(('progress', current, total, item))
                result = uploader.upload_mockups(category, files, callback) if mode == 'mockup' else uploader.upload_designs(orientation, files, prefix, root, callback)
                self.queue.put(('moving', 'Başarılılar Yüklenenler’e, birebir kopyalar kontrol et sil klasörüne taşınıyor…'))
                result['moved'] = self._move_uploaded_sources(result, root)
                self.queue.put(('done', result))
            except Exception as exc: self.queue.put(('error', str(exc)))
        threading.Thread(target=work, daemon=True, name='central-upload').start()

    def _poll(self):
        try:
            while True:
                message = self.queue.get_nowait()
                if message[0] == 'preflight':
                    _, token, groups, scope = message
                    if token != self._preflight_token: continue
                    self._preflight_groups, self._preflight_scope = groups, scope
                    self.progress.stop()
                    self.progress.configure(mode='determinate', maximum=max(1, len(groups['new'])), value=0)
                    duplicate = len(groups['duplicate']) + len(groups['batch_duplicate'])
                    new, invalid = len(groups['new']), len(groups['invalid'])
                    self.summary.configure(text=self._summary_base + f'\nÖn kontrol hazır: {new} yeni · {duplicate} daha önce alınmış/tekrar · {invalid} hatalı')
                    self.progress_text.configure(text='Ön kontrol hazır · başlatmak için düğmeye basın.')
                elif message[0] == 'moving':
                    self.progress_text.configure(text=message[1])
                elif message[0] == 'preflight_error':
                    _, token, error = message
                    if token == self._preflight_token:
                        self.progress.stop()
                        self.progress.configure(mode='determinate', maximum=1, value=0)
                        self.summary.configure(text=self._summary_base + '\nÖn kontrol başarısız: ' + error, fg=RED)
                        self.progress_text.configure(text='Ön kontrol başarısız.')
                elif message[0] == 'progress':
                    _, current, total, item = message; self.progress['maximum'] = max(total, 1); self.progress['value'] = current
                    percent = int(round((current / total) * 100)) if total else 0
                    self.progress_text.configure(text=f'İlerleme: {current}/{total} (%{percent}) · {item.get("status", "")}'[:120])
                    self._update_live_stats(current, total, item)
                elif message[0] == 'done':
                    result = message[1]; self.running = False; self.upload_button.configure(state='normal')
                    self._last_result = result
                    self.progress.stop()
                    self.progress.configure(mode='determinate', maximum=max(1, self.progress['maximum']), value=self.progress['maximum'])
                    self.report_button.configure(state='normal')
                    self._last_report_context = {
                        'mode': 'mockup' if self.mode.get() == 'mockup' else 'design',
                        'scope': self.category.get() if self.mode.get() == 'mockup' else self.orientation.get(),
                        'source_count': len(self.files),
                        'source_root': str(self.source_root) if self.source_root else '',
                    }
                    self.counts.configure(text=f'Başarılı: {result["success"]}  ·  Hatalı: {result["failed"]}  ·  Atlanan: {result["skipped"]}')
                    self._refresh()
                    self.progress_text.configure(text='İşlem tamamlandı · yeni dosyalar inceleme/onay akışına hazır.')
                    self.live_stats.configure(text=f'İlerleme: {self._upload_total}/{self._upload_total} (%100)  ·  '
                                                     f'Başarılı: {result["success"]}  ·  Hatalı: {result["failed"]}  ·  Atlanan: {result["skipped"]}\n'
                                                     'Tahmini tamamlanma: tamamlandı')
                    refresh = getattr(self.app, 'refresh_workbench_templates', None)
                    if callable(refresh):
                        refresh()
                    self.app.status.set('Merkezi yükleme tamamlandı: ' + str(result['success']) + ' başarılı.')
                    source_text = str(self._last_report_context.get('source_root') or 'Seçili dosyaların bulunduğu klasörler')
                    moved = int(result.get('moved', 0) or 0)
                    remaining = int(result.get('failed', 0) or 0) + int(result.get('skipped', 0) or 0)
                    move_error_count = len(result.get('move_errors', []))
                    messagebox.showinfo(
                        'Yükleme tamamlandı',
                        'İşlem özeti\n\n'
                        f'Başarılı olarak içeri alınan: {result["success"]}\n'
                        f'Atlanan (daha önce alınmış/tekrar): {result["skipped"]}\n'
                        f'Hatalı veya alınamayan: {result["failed"]}\n'
                        f'Yüklenenler klasörüne taşınan: {moved}\n\n'
                        f'Taşıma hatası: {move_error_count}\n\n'
                        f'Kaynak: {source_text}\n'
                        f'Kaynakta kalan kontrol edilecek dosya: yaklaşık {remaining}\n\n'
                        'Ayrıntılı dosya listesini görmek için “Raporu Kaydet” düğmesini kullanabilirsiniz.',
                        parent=self.root,
                    )
                elif message[0] == 'error':
                    self.running = False; self._last_result = None; self.upload_button.configure(state='normal'); self.progress.stop(); self.progress.configure(mode='determinate'); self.progress_text.configure(text='İşlem durdu: ' + message[1]); self.live_stats.configure(text=f'Başlayan: 0/{self._upload_total}  ·  Başarılı: 0  ·  Hatalı: {self._preflight_invalid + 1}  ·  Atlanan: 0\nTahmini tamamlanma: durdu'); messagebox.showerror('Merkezi yükleme', message[1], parent=self.root)
        except queue.Empty: pass
        self.root.after(150, self._poll)


def build_upload_center(app, host):
    return UploadCenter(app, host)

