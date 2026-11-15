"""Mağaza Profilleri — kayıtlı ayarları yükle, havuzu koru, eşleşmeyi doğrula.

Güvenlik sözleşmesi:
- ``store_profiles_v47.json`` her işlemde diskten **taze** okunur; hiçbir
  işlem mağaza şablon havuzunu sıfırlamaz veya yeniden üretmez.
- Kısa kod kaydı ve yeni mağaza oluşturma mevcut ``StoreProfiles``
  yolundan geçer (atomik yazma + ``.backup_*`` kopyası).
- Atama ekleme/çıkarma bu ekranın işi değildir; o işlem yalnızca
  "Mağaza–Mockup Eşleştirme Merkezi"nden yapılır. Bu ekran havuzu yalnız
  gösterir ve doğrular.
- Onaylı şablon listesine erişim yoksa "ONAY/SHA DEĞİŞMİŞ" işaretlemesi
  yapılamaz; bu durum açıkça raporlanır (sessiz geçilmez).
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

try:
    from graphite_ui_components import module_header
except Exception:
    module_header = None

STORE_ID = re.compile(r'^[A-Za-z0-9_][A-Za-z0-9_-]{1,35}$')
SHA64 = re.compile(r'^[0-9a-fA-F]{64}$')

# Graphite paleti (graphite_workbench_v500 ile birebir).
SIDE = '#0F1622'
PANEL = '#131C2B'
PANEL_RAISED = '#182238'
BORDER = '#22304A'
ACCENT = '#17D3A3'
ACCENT_DARK = '#0B7A5F'
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


def category_labels() -> dict[str, str]:
    try:
        from URETIM_V4.unlimited_selection import CATEGORY_LABELS_TR  # type: ignore
        return dict(CATEGORY_LABELS_TR)
    except Exception:
        return {
            '01_Wifi_Kutusu': 'Dekoratif Ahşap Wi-Fi Kutusu',
            '02_Cam_Tablo_Dikey': 'Temperli Cam Tablo Dikey',
            '02_Cam_Tablo_Yatay': 'Temperli Cam Tablo Yatay',
            '03_Ahsap_Tablo': 'Dekoratif Ahşap Tablo',
            '04_Cam_Dograma': 'Cam Doğrama Görsel Kaplama',
            '05_Ocak_Arkasi': 'Temperli Cam Ocak Arkası Koruyucu',
            '06_Petek_Kapama': 'Dekoratif Ahşap Petek Dolabı',
        }


def parse_template_key(key: str) -> dict[str, str]:
    """``category:uid@sha256`` anahtarını parçalar; bozuksa ValueError."""
    text = str(key or '').strip()
    left, at, sha = text.rpartition('@')
    if not at or not SHA64.fullmatch(sha or ''):
        raise ValueError('SHA256 eksik/bozuk: ' + text[:80])
    category, sep, uid = left.partition(':')
    if not sep or not category or not uid.strip():
        raise ValueError('category:uid biçimi bozuk: ' + text[:80])
    if any(ord(ch) < 32 for ch in uid):
        raise ValueError('uid kontrol karakteri içeriyor')
    return {'category': category, 'uid': uid, 'sha': sha.lower()}


def short_code_status(store: str, row: dict[str, Any]) -> dict[str, Any]:
    """Mağazanın kayıtlı/etkin kısa kodunu çözer; tuzakları açıklar."""
    from URETIM_V4.store_identity_v485 import (
        default_store_short_code, normalize_short_code)
    configured_raw = row.get('short_code')
    default_code = default_store_short_code(store)
    configured = None
    error = None
    if configured_raw:
        try:
            configured = normalize_short_code(configured_raw)
        except ValueError as exc:
            error = str(exc)
    effective = configured or default_code
    return {'configured': configured, 'default': default_code,
            'effective': effective, 'defined': effective is not None, 'error': error}


def validate_store_profiles(config: dict[str, Any],
                            approved_keys: set[str] | None = None) -> dict[str, Any]:
    """Mağaza-kategori-şablon eşleşmelerini denetler; hiçbir şeyi değiştirmez."""
    problems: list[dict[str, str]] = []
    labels = category_labels()
    stores = config.get('stores', {}) if isinstance(config, dict) else {}
    owner_of_key: dict[str, str] = {}
    owner_of_sha: dict[str, str] = {}
    short_owners: dict[str, str] = {}
    per_store: dict[str, dict[str, Any]] = {}
    for store, row in stores.items():
        info: dict[str, Any] = {'templates': 0, 'categories': {}, 'stale': 0, 'malformed': 0}
        per_store[store] = info
        if not STORE_ID.fullmatch(str(store)):
            problems.append({'store': str(store), 'kind': 'STORE_ID_INVALID',
                             'detail': 'Mağaza kimliği 2-36 harf/rakam/_/- olmalı.'})
        if not isinstance(row, dict) or not isinstance(row.get('templates'), list):
            problems.append({'store': str(store), 'kind': 'STORE_TEMPLATES_INVALID',
                             'detail': 'templates listesi okunamadı.'})
            continue
        # Kısa kod çakışması (kayıtlı değer ya da bilinen varsayılan üzerinden)
        status = short_code_status(store, row)
        if status['error']:
            problems.append({'store': store, 'kind': 'SHORT_CODE_INVALID', 'detail': status['error']})
        code = (status['effective'] or '').upper()
        if code:
            other = short_owners.get(code)
            if other and other != store:
                problems.append({'store': store, 'kind': 'MAGAZA_KISA_KODU_CAKISMASI',
                                 'detail': f'{code} hem {other} hem {store} için etkin.'})
            short_owners[code] = store
        seen_keys: set[str] = set()
        for key in row['templates']:
            info['templates'] += 1
            try:
                parsed = parse_template_key(key)
            except ValueError as exc:
                info['malformed'] += 1
                problems.append({'store': store, 'kind': 'KEY_INVALID', 'detail': str(exc)})
                continue
            cat = parsed['category']
            info['categories'][cat] = info['categories'].get(cat, 0) + 1
            if cat not in labels:
                problems.append({'store': store, 'kind': 'BILINMEYEN_KATEGORI',
                                 'detail': f'{cat} · {parsed["uid"]}'})
            if key in seen_keys:
                problems.append({'store': store, 'kind': 'DUPLICATE_KEY_IN_STORE',
                                 'detail': str(key)[:120]})
            seen_keys.add(key)
            other = owner_of_key.get(key)
            if other and other != store:
                problems.append({'store': store, 'kind': 'STORE_TEMPLATE_ASSIGNED_TO_MULTIPLE_STORES',
                                 'detail': f'{key[:120]} · önce: {other}'})
            owner_of_key.setdefault(key, store)
            sha_owner = owner_of_sha.get(parsed['sha'])
            if sha_owner and sha_owner != store:
                problems.append({'store': store, 'kind': 'STORE_SOURCE_IMAGE_REUSED_ACROSS_STORES',
                                 'detail': f"{parsed['category']}:{parsed['uid']} · önce: {sha_owner}"})
            owner_of_sha.setdefault(parsed['sha'], store)
            if approved_keys is not None and key not in approved_keys:
                info['stale'] += 1
    return {'ok': not problems, 'problems': problems, 'stores': per_store,
            'approved_checked': approved_keys is not None}


def approved_from_app(app: Any) -> list[dict[str, Any]] | None:
    """Gömülü üretim penceresinde zaten bulunan onaylı listeyi (varsa) oku."""
    for window in getattr(app, 'batch_windows', ()) or ():
        items = getattr(window, 'all_templates', None)
        if items:
            return list(items)
    items = getattr(app, 'all_templates', None)
    return list(items) if items else None


def approved_keys_from(approved: list[dict[str, Any]] | None) -> set[str] | None:
    if approved is None:
        return None
    from URETIM_V4.store_profiles_v47 import key_for
    keys = set()
    for item in approved:
        try:
            keys.add(key_for(item))
        except (KeyError, TypeError):
            continue
    return keys


def _call(app: Any, name: str) -> None:
    fn = getattr(app, name, None)
    if callable(fn):
        try:
            fn()
        except Exception:
            pass


def build_stores_workspace(app: Any, parent: Any, *, state_root: Path | str | None = None):
    """Mağaza Profilleri sekmesinin içeriğini üretir."""
    import tkinter as tk
    from tkinter import ttk, messagebox, scrolledtext

    try:
        from URETIM_V4.store_profiles_v47 import StoreProfiles, key_for
    except Exception as exc:  # paket importu bozuksa panel yine açılır, yazar bilgi verir
        StoreProfiles = None  # type: ignore
        key_for = None  # type: ignore
        import_error = str(exc)
    else:
        import_error = None

    root = Path(state_root) if state_root else default_state_root()

    try:
        from URETIM_V4 import ui_table_v1 as _table_tools
    except Exception:
        _table_tools = None

    shell = tk.Frame(parent, bg=SIDE, bd=0, highlightthickness=0)
    shell.grid_columnconfigure(0, weight=1)
    shell.grid_columnconfigure(1, weight=1)
    shell.grid_rowconfigure(2, weight=1)

    top = (module_header(shell, '▧  Mağaza Profilleri',
                         'Kayıtlı ayarlar ve şablon havuzu · veri güvenliği korunur')
           if module_header else tk.Frame(shell, bg=PANEL, bd=0, highlightthickness=0))
    top.grid(row=0, column=0, columnspan=2, sticky='ew', padx=6, pady=(6, 4))
    chips: dict[str, tk.Label] = {}

    def _chip(key, text, color):
        lbl = tk.Label(top, text=text, bg=color, fg='#0F1622',
                       font=('Segoe UI', 8, 'bold'), padx=8, pady=3)
        lbl.pack(side='left', padx=4)
        chips[key] = lbl

    _chip('stores', 'Mağaza: –', BLUE)
    _chip('assignments', 'Atama: –', GREEN)
    _chip('health', 'Doğrulama: –', YELLOW)

    refresh_btn = tk.Button(top, text='⟳ Yenile', bg=PANEL_RAISED, fg=FG, relief='flat',
                            font=('Segoe UI', 9, 'bold'), padx=12, pady=4, cursor='hand2')
    refresh_btn.pack(side='right', padx=8, pady=6)
    validate_btn = tk.Button(top, text='Doğrula', bg=PANEL_RAISED, fg=FG, relief='flat',
                             font=('Segoe UI', 9, 'bold'), padx=12, pady=4, cursor='hand2',
                             command=lambda: _validate())
    validate_btn.pack(side='right', padx=2, pady=6)

    paned = tk.PanedWindow(shell, orient='horizontal', bg=SIDE, bd=0,
                           sashwidth=8, sashrelief='raised', sashcursor='sb_h_double_arrow')
    paned.grid(row=2, column=0, columnspan=2, sticky='nsew', padx=0, pady=(0, 6))

    store_frame = tk.Frame(paned, bg=PANEL, bd=0, highlightthickness=0)
    paned.add(store_frame, minsize=260, sticky='nsew')
    store_frame.grid_columnconfigure(0, weight=1)
    store_frame.grid_rowconfigure(1, weight=1)
    tk.Label(store_frame, text='MAĞAZALAR', bg=PANEL_RAISED, fg=FG,
             font=('Segoe UI', 9, 'bold'), anchor='w', padx=10, pady=6).grid(row=0, column=0, sticky='ew')
    store_cols = ('Mağaza', 'Kısa Kod', 'Şablon')
    store_tree = ttk.Treeview(store_frame, columns=store_cols, show='headings',
                              selectmode='browse', height=16)
    for name, width in zip(store_cols, (120, 80, 60)):
        store_tree.heading(name, text=name)
        store_tree.column(name, width=width, anchor='w', stretch=(name == 'Mağaza'))
    if _table_tools is not None:
        _table_tools.enhance_tree(store_tree, store_cols)
    store_scroll = ttk.Scrollbar(store_frame, orient='vertical', command=store_tree.yview)
    store_tree.configure(yscrollcommand=store_scroll.set)
    store_tree.grid(row=1, column=0, sticky='nsew')
    store_scroll.grid(row=1, column=1, sticky='ns')
    if _table_tools is not None:
        _table_tools.add_horizontal_scrollbar(store_tree, row=2, column=0,
                                              columnspan=2, sticky='ew')
    add_btn = tk.Button(store_frame, text='＋ Mağaza Ekle', bg=PANEL_RAISED, fg=FG, relief='flat',
                        font=('Segoe UI', 9, 'bold'), padx=10, pady=6, cursor='hand2')
    add_btn.grid(row=4, column=0, columnspan=2, sticky='ew', padx=6, pady=6)

    detail = tk.Frame(paned, bg=PANEL, bd=0, highlightthickness=0)
    paned.add(detail, minsize=400, sticky='nsew')
    detail.grid_columnconfigure(0, weight=1)
    detail.grid_rowconfigure(3, weight=1)

    settings = tk.LabelFrame(detail, text='Kayıtlı Ayarlar', bg=PANEL, fg=BLUE,
                             font=('Segoe UI', 9, 'bold'), bd=1, relief='groove', padx=8, pady=6)
    settings.grid(row=0, column=0, sticky='ew', padx=6, pady=(6, 4))
    settings.grid_columnconfigure(1, weight=1)
    tk.Label(settings, text='Mağaza kimliği:', bg=PANEL, fg=MUTED, font=('Segoe UI', 8)).grid(
        row=0, column=0, sticky='w', padx=(2, 8))
    store_id_var = tk.StringVar(value='—')
    tk.Label(settings, textvariable=store_id_var, bg=PANEL, fg=FG,
             font=('Segoe UI', 9, 'bold')).grid(row=0, column=1, sticky='w')
    tk.Label(settings, text='Kısa kod:', bg=PANEL, fg=MUTED, font=('Segoe UI', 8)).grid(
        row=1, column=0, sticky='w', padx=(2, 8), pady=(6, 0))
    short_var = tk.StringVar(value='')
    short_entry = tk.Entry(settings, textvariable=short_var, width=14, bg=PANEL_RAISED, fg=FG,
                           insertbackground=FG, relief='flat', bd=0, highlightthickness=1,
                           highlightbackground=BORDER, highlightcolor=ACCENT, font=('Segoe UI', 9))
    short_entry.grid(row=1, column=1, sticky='w', pady=(6, 0), ipady=3)
    save_btn = tk.Button(settings, text='Kaydet', bg=ACCENT_DARK, fg='#FFFFFF', relief='flat',
                         font=('Segoe UI', 8, 'bold'), padx=14, pady=3, cursor='hand2')
    save_btn.grid(row=1, column=2, sticky='w', padx=6, pady=(6, 0))
    effective_var = tk.StringVar(value='')
    tk.Label(settings, textvariable=effective_var, bg=PANEL, fg=MUTED,
             font=('Segoe UI', 8), justify='left').grid(row=2, column=0, columnspan=3,
                                                        sticky='w', padx=2, pady=(6, 0))

    pool_frame = tk.LabelFrame(detail, text='Atanmış Şablon Havuzu (salt okunur)', bg=PANEL,
                               fg=GREEN, font=('Segoe UI', 9, 'bold'), bd=1, relief='groove',
                               padx=8, pady=6)
    pool_frame.grid(row=3, column=0, sticky='nsew', padx=6, pady=4)
    pool_frame.grid_columnconfigure(0, weight=1)
    pool_frame.grid_rowconfigure(0, weight=1)
    pool_cols = ('Kategori', 'UID', 'SHA', 'Durum')
    pool = ttk.Treeview(pool_frame, columns=pool_cols, show='headings',
                        selectmode='browse', height=12)
    for name, width in zip(pool_cols, (170, 190, 70, 150)):
        pool.heading(name, text=name)
        pool.column(name, width=width, anchor='w', stretch=(name in ('Kategori', 'UID')))
    if _table_tools is not None:
        _table_tools.enhance_tree(pool, pool_cols)
    pool_scroll = ttk.Scrollbar(pool_frame, orient='vertical', command=pool.yview)
    pool.configure(yscrollcommand=pool_scroll.set)
    pool.grid(row=0, column=0, sticky='nsew')
    pool_scroll.grid(row=0, column=1, sticky='ns')
    if _table_tools is not None:
        pool_frame.grid_rowconfigure(1, weight=0)
        _table_tools.add_horizontal_scrollbar(pool, row=1, column=0,
                                              columnspan=2, sticky='ew')
    pool.tag_configure('ok', foreground='#3FD98A')
    pool.tag_configure('stale', foreground='#F0B84C')
    pool.tag_configure('bad', foreground='#FF9AA0')

    pool_summary = tk.StringVar(value='Mağaza seçin.')
    tk.Label(detail, textvariable=pool_summary, bg=PANEL, fg='#93A6C4',
             font=('Segoe UI', 8), anchor='w', justify='left', wraplength=520).grid(
        row=4, column=0, sticky='ew', padx=8, pady=(0, 2))
    tk.Label(detail, text='Havuz yalnız "Mağaza–Mockup Eşleştirme Merkezi" ile değişir; bu ekran atama eklemez/kaldırmaz.',
             bg=PANEL, fg=MUTED, font=('Segoe UI', 8), anchor='w').grid(
        row=5, column=0, sticky='ew', padx=8, pady=(0, 4))
    center_btn = tk.Button(detail, text='Mağaza–Mockup Eşleştirme Merkezi’ni Aç',
                           bg=PANEL_RAISED, fg=FG, relief='flat', font=('Segoe UI', 9, 'bold'),
                           padx=12, pady=6, cursor='hand2',
                           command=lambda: _call(app, 'open_unified_v4'))
    center_btn.grid(row=6, column=0, sticky='ew', padx=6, pady=(0, 6))

    report = scrolledtext.ScrolledText(shell, wrap='word', height=6, bg='#080C14', fg='#93A6C4',
                                       insertbackground=FG, relief='flat', bd=0,
                                       font=('Consolas', 8))
    report.grid(row=3, column=0, columnspan=2, sticky='ew', padx=6, pady=(0, 6))
    report.insert('1.0', 'Doğrulama raporu burada görünür. "Doğrula" düğmesi hiçbir veriyi değiştirmez.\n')
    report.configure(state='disabled')

    state: dict[str, Any] = {'config': None, 'error': import_error, 'selected': None}

    def _write_report(text: str):
        report.configure(state='normal')
        report.delete('1.0', 'end')
        report.insert('1.0', text)
        report.configure(state='disabled')

    def _mgr():
        if StoreProfiles is None:
            raise RuntimeError('store_profiles modülü yüklenemedi: ' + str(state['error']))
        return StoreProfiles(root)

    def _approved():
        items = approved_from_app(app)
        return approved_keys_from(items) if items else None

    def refresh(selected: str | None = None):
        try:
            config = _mgr().load()
            state['config'] = config
            state['error'] = None
        except Exception as exc:
            state['config'] = None
            state['error'] = str(exc)
            store_tree.delete(*store_tree.get_children())
            pool.delete(*pool.get_children())
            store_id_var.set('—')
            short_var.set('')
            effective_var.set('store_profiles_v47.json okunamadı: ' + str(exc))
            chips['stores'].configure(text='Mağaza: !')
            chips['assignments'].configure(text='Atama: !')
            chips['health'].configure(text='Doğrulama: HATA')
            _write_report('store_profiles_v47.json okunamadı:\n' + str(exc)
                          + '\n\nHiçbir kayıt değiştirilmedi. Dosyayı geri yüklemek için yedekleri kullanın.')
            return
        sel = store_tree.selection()
        keep = selected or state.get('selected') or (sel[0] if sel else None)
        store_tree.delete(*store_tree.get_children())
        total = 0
        for name in sorted(config['stores']):
            row = config['stores'][name]
            total += len(row.get('templates', ()))
            status = short_code_status(name, row)
            code = status['effective'] or ('✗ TANIMSIZ' if not status['defined'] else '—')
            store_tree.insert('', 'end', iid=name,
                              values=(name, code, len(row.get('templates', ()))))
        store_names = sorted(config['stores'])
        if store_names:
            target = keep if keep in config['stores'] else store_names[0]
            state['internal_select'] = True
            try:
                store_tree.selection_set(target)
                store_tree.see(target)
            finally:
                state['internal_select'] = False
            state['selected'] = target
            _show_store(target)
        else:
            store_id_var.set('—')
            short_var.set('')
            effective_var.set('Kayıtlı mağaza yok.')
            pool.delete(*pool.get_children())
            pool_summary.set('Kayıtlı mağaza yok.')
        chips['stores'].configure(text=f'Mağaza: {len(store_names)}')
        chips['assignments'].configure(text=f'Atama: {total}')
        if hasattr(app, 'status'):
            try:
                app.status.set(f'Mağaza Profilleri: {len(store_names)} mağaza · {total} atama yüklendi.')
            except Exception:
                pass

    def _show_store(name: str):
        config = state.get('config') or {'stores': {}}
        row = config.get('stores', {}).get(name)
        state['selected'] = name
        if row is None:
            return
        store_id_var.set(name)
        short_var.set(str(row.get('short_code') or ''))
        status = short_code_status(name, row)
        if status['effective']:
            source = 'kayıtlı' if status['configured'] else 'varsayılan'
            effective_var.set(f'Etkin kısa kod: {status["effective"]} ({source}). '
                              'Kayıt Excel satır kimliğini değiştirir; üretimden önce kontrol edin.')
        else:
            effective_var.set('KISA KOD TANIMSIZ — bu mağaza için Excel/ürün kimliği üretilemez. '
                              'Bir kısa kod girip Kaydet’e basın.')
        approved_keys = _approved()
        pool.delete(*pool.get_children())
        labels = category_labels()
        stale = 0
        for index, key in enumerate(row.get('templates', ())):
            try:
                parsed = parse_template_key(key)
            except ValueError as exc:
                pool.insert('', 'end', iid=str(index),
                            values=('?', str(key)[:40], '—', 'BOZUK ANAHTAR'), tags=('bad',))
                continue
            if approved_keys is None:
                durum = 'Havuzda'
            elif key in approved_keys:
                durum = 'Bu mağazada'
            else:
                durum = 'ONAY/SHA DEĞİŞMİŞ'
                stale += 1
            tag = 'ok' if durum in ('Havuzda', 'Bu mağazada') else 'stale'
            pool.insert('', 'end', iid=str(index),
                        values=(labels.get(parsed['category'], parsed['category']),
                                parsed['uid'], parsed['sha'][:8], durum), tags=(tag,))
        if approved_keys is None:
            stale_note = 'onaylı liste yok (üretim penceresi kapalı) — yalnız biçim doğrulaması yapıldı'
        else:
            stale_note = f'{stale} onay/SHA değişmiş'
        counts: dict[str, int] = {}
        for key in row.get('templates', ()):
            try:
                cat = parse_template_key(key)['category']
            except ValueError:
                continue
            counts[cat] = counts.get(cat, 0) + 1
        breakdown = ', '.join(f'{cat}: {n}' for cat, n in sorted(counts.items())) or '—'
        pool_summary.set(f'{name}: {len(row.get("templates", ()))} atama · {breakdown}\n{stale_note}')

    def _on_store_selected(_event=None):
        if state.get('internal_select'):
            return  # programatik seçim; refresh zaten _show_store çağırır
        selection = store_tree.selection()
        if selection:
            _show_store(selection[0])

    def _save_short_code():
        name = state.get('selected')
        if not name:
            messagebox.showwarning('Mağaza seçilmedi', 'Önce listeden bir mağaza seçin.', parent=shell)
            return
        code = short_var.get().strip()
        if not code:
            messagebox.showwarning('Kısa kod boş', 'Boş bırakılan kısa kod kaydedilemez.', parent=shell)
            return
        try:
            _mgr().set_short_code(name, code)
        except Exception as exc:
            messagebox.showerror('Kısa kod kaydedilemedi', str(exc), parent=shell)
            return
        refresh(selected=name)
        if hasattr(app, 'status'):
            try:
                app.status.set(f'{name} kısa kodu kaydedildi (yedek .backup_* oluşturuldu).')
            except Exception:
                pass

    def _add_store_dialog():
        dialog = tk.Toplevel(shell)
        dialog.title('Yeni Mağaza')
        dialog.geometry('420x210')
        dialog.minsize(380, 190)
        dialog.configure(bg=PANEL)
        dialog.transient(shell.winfo_toplevel())
        tk.Label(dialog, text='Yeni mağaza kimliği (2-36 harf/rakam/_/-):',
                 bg=PANEL, fg=FG, font=('Segoe UI', 9, 'bold')).pack(anchor='w', padx=14, pady=(14, 2))
        name_var = tk.StringVar()
        name_entry = tk.Entry(dialog, textvariable=name_var, bg=PANEL_RAISED, fg=FG,
                              insertbackground=FG, relief='flat',
                              highlightthickness=1, highlightbackground=BORDER,
                              font=('Segoe UI', 10))
        name_entry.pack(fill='x', padx=14, ipady=4)
        tk.Label(dialog, text='Kısa kod (opsiyonel, 2-12; boş bırakılırsa bilinen varsayılan):',
                 bg=PANEL, fg=MUTED, font=('Segoe UI', 8)).pack(anchor='w', padx=14, pady=(10, 2))
        code_var = tk.StringVar()
        code_entry = tk.Entry(dialog, textvariable=code_var, width=16, bg=PANEL_RAISED, fg=FG,
                              insertbackground=FG, relief='flat',
                              highlightthickness=1, highlightbackground=BORDER,
                              font=('Segoe UI', 10))
        code_entry.pack(anchor='w', padx=14, ipady=4)
        buttons = tk.Frame(dialog, bg=PANEL)
        buttons.pack(fill='x', padx=14, pady=12)

        def _create():
            try:
                name = name_var.get().strip()
                _mgr().add_store(name)
                code = code_var.get().strip()
                if code:
                    _mgr().set_short_code(name, code)
            except Exception as exc:
                messagebox.showerror('Mağaza eklenemedi', str(exc), parent=dialog)
                return
            dialog.destroy()
            refresh(selected=name_var.get().strip())

        tk.Button(buttons, text='Vazgeç', bg=PANEL_RAISED, fg=FG, relief='flat',
                  padx=14, pady=5, command=dialog.destroy).pack(side='right')
        tk.Button(buttons, text='Oluştur', bg=ACCENT_DARK, fg='#FFFFFF', relief='flat',
                  font=('Segoe UI', 9, 'bold'), padx=16, pady=5, command=_create).pack(side='right', padx=(0, 8))
        name_entry.focus_set()
        dialog.grab_set()

    def _validate():
        try:
            config = _mgr().load()
        except Exception as exc:
            _write_report('store_profiles_v47.json okunamadı:\n' + str(exc))
            chips['health'].configure(text='Doğrulama: HATA')
            return
        approved_keys = _approved()
        result = validate_store_profiles(config, approved_keys)
        lines = []
        lines.append('Mağaza–Kategori–Şablon doğrulama raporu')
        lines.append('=' * 46)
        if result['approved_checked']:
            lines.append(f"Onaylı liste karşısında SHA/anahtar denetimi yapıldı "
                         f"({len(approved_keys or set())} anahtar).")
        else:
            lines.append('Onaylı liste yok (üretim penceresi kapalı): yalnız biçim ve '
                         'çapraz-mağaza denetimi yapıldı.')
        lines.append('')
        for store, info in sorted(result['stores'].items()):
            breakdown = ', '.join(f'{cat}: {n}' for cat, n in sorted(info['categories'].items())) or '—'
            lines.append(f"{store}: {info['templates']} atama · {breakdown}"
                         + (f" · onay/SHA değişmiş: {info['stale']}" if result['approved_checked'] else ''))
        lines.append('')
        if result['ok']:
            lines.append('SONUÇ: SORUN YOK — mağaza havuzları ayrık, kısa kodlar çakışmıyor, '
                         'anahtarlar biçim açısından geçerli.')
            chips['health'].configure(text='Doğrulama: TEMİZ')
        else:
            lines.append(f"SONUÇ: {len(result['problems'])} sorun bulundu:")
            for problem in result['problems']:
                lines.append(f"  [{problem['kind']}] {problem['store']} · {problem['detail']}")
            lines.append('')
            lines.append('Hiçbir kayıt otomatik değiştirilmedi. Çözüm için Eşleştirme Merkezi '
                         'veya kısa kod düzenleme kullanın.')
            chips['health'].configure(text=f"Doğrulama: {len(result['problems'])} sorun")
        _write_report('\n'.join(lines))
        if hasattr(app, 'status'):
            try:
                app.status.set('Mağaza doğrulaması tamamlandı: '
                               + ('temiz.' if result['ok'] else f"{len(result['problems'])} sorun (rapor açık)."))
            except Exception:
                pass

    store_tree.bind('<<TreeviewSelect>>', _on_store_selected)
    save_btn.configure(command=_save_short_code)
    add_btn.configure(command=_add_store_dialog)
    refresh_btn.configure(command=lambda: refresh())

    refresh()
    shell.refresh_stores = lambda: refresh()  # kabuk yenileme düğmesi için
    shell.pack(fill='both', expand=True)
    return shell
