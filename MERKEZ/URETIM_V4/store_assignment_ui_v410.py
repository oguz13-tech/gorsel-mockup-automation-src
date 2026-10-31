"""Modeless, explicit store -> category -> approved mockup assignment wizard.

Does not use the production screen's selected templates. Every assignment
requires a visible manual selection and one final confirmation.
"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from PIL import Image, ImageTk, ImageOps
from dark_theme_v42 import BG, PANEL, FG, MUTED, ACCENT, apply_dark_theme
from .store_profiles_v47 import StoreProfiles, key_for
from .store_assignment_v410 import status_inventory, checked_assignment, assigned_for_store
from .unlimited_selection import CATEGORY_LABELS_TR


class StoreAssignmentWindow:
    def __init__(self, parent, *, state_root, get_approved, on_change):
        self.mgr = StoreProfiles(Path(state_root))
        self.get_approved = get_approved
        self.on_change = on_change
        self.approved = []
        self.rows = {}
        self.marked = set()
        self._visible_keys = []
        self._all_category_rows = []
        self._page = 0
        self._page_limit = 36
        self._thumb_seq = 0
        self._thumb_refs = {}
        self.pop = tk.Toplevel(parent)
        self.pop.title('Mağaza–Mockup Eşleştirme Merkezi · Güvenli Atama')
        self.pop.geometry('1290x790')
        self.pop.minsize(970, 600)
        self.pop.configure(bg=BG)
        apply_dark_theme(self.pop)
        self._image = None
        self._image_seq = 0
        styles=ttk.Style(self.pop)
        styles.configure('StoreAssign.Treeview',rowheight=43,background=PANEL,foreground=FG,fieldbackground=PANEL,font=('Segoe UI',10))
        styles.configure('StoreAssign.Treeview.Heading',font=('Segoe UI',10,'bold'))
        styles.configure('StoreAssign.Small.Treeview',rowheight=26,background=PANEL,foreground=FG,fieldbackground=PANEL,font=('Segoe UI',9))
        styles.configure('StoreAssign.Small.Treeview.Heading',font=('Segoe UI',9,'bold'))
        self._build()
        self.reload_stores()
        self.pop.protocol('WM_DELETE_WINDOW', self.pop.destroy)

    def _build(self):
        body = ttk.Frame(self.pop, padding=16)
        body.pack(fill='both', expand=True)
        ttk.Label(body, text='MAĞAZA–MOCKUP EŞLEŞTİRME MERKEZİ',
                  font=('Segoe UI', 19, 'bold')).pack(anchor='w', pady=(2, 4))
        ttk.Label(body, text='1. Mağaza seç     →     2. Kategori seç     →     3. Onaylı mockupları seç     →     4. Önizle ve Ata',
                  font=('Segoe UI', 11, 'bold')).pack(anchor='w', pady=(0, 7))
        ttk.Label(body, text='Aynı baskı tasarımı bütün mağazalarda kullanılabilir. Aynı mockup kaynak fotoğrafı başka mağazaya atanamaz.',
                  foreground='#cbd7ee', wraplength=1180).pack(anchor='w', pady=(0, 13))

        top = ttk.LabelFrame(body, text='1  MAĞAZA VE KATEGORİ', style='Premium.TLabelframe', padding=(12, 10))
        top.pack(fill='x', pady=(0, 12))
        row = ttk.Frame(top)
        row.pack(fill='x')
        ttk.Label(row, text='Mağaza:').pack(side='left', padx=(0, 6))
        self.store = tk.StringVar(value='')
        self.stores = ttk.Combobox(row, textvariable=self.store, state='readonly', width=22)
        self.stores.pack(side='left', padx=(0, 12))
        self.stores.bind('<<ComboboxSelected>>', lambda _event: self._changed_store())
        ttk.Label(row, text='Yeni mağaza kodu:').pack(side='left', padx=(5, 6))
        self.new_store = tk.StringVar()
        ttk.Entry(row, textvariable=self.new_store, width=18).pack(side='left')
        ttk.Button(row, text='Mağaza Oluştur', command=self.add_store).pack(side='left', padx=(6, 18))
        ttk.Label(row, text='Kategori:').pack(side='left', padx=(2, 5))
        self.category = tk.StringVar(value='')
        self.categories = ttk.Combobox(row, textvariable=self.category, state='disabled', width=28)
        self.categories['values'] = [f'{label}  ({key})' for key, label in CATEGORY_LABELS_TR.items()]
        self.categories.pack(side='left', padx=(0, 9))
        self.categories.bind('<<ComboboxSelected>>', lambda _event: self.refresh())
        ttk.Button(row, text='Listeyi Yenile', command=self.refresh).pack(side='left', padx=3)

        main = ttk.Frame(body)
        main.pack(fill='both', expand=True)
        left = ttk.LabelFrame(main, text='2  ONAYLI MOCKUP HAVUZU — sadece uygun olanlar seçilebilir',
                              style='Premium.TLabelframe', padding=9)
        left.pack(side='left', fill='both', expand=True, padx=(0, 7))
        filters = ttk.Frame(left)
        filters.pack(fill='x', pady=(2, 7))
        ttk.Label(filters, text='Ara:').pack(side='left')
        self.search = tk.StringVar()
        ttk.Entry(filters, textvariable=self.search, width=27).pack(side='left', padx=8, fill='x', expand=True)
        self.search.trace_add('write', lambda *_: self._search_changed())
        ttk.Button(filters, text='Sayfadaki Uygunları Seç', command=self.select_available).pack(side='left', padx=3)
        ttk.Button(filters, text='Kategorideki Tüm Uygunları Seç', command=self.select_all_available).pack(side='left', padx=3)
        ttk.Button(filters, text='Seçimi Temizle', command=self.clear_selection).pack(side='left', padx=3)
        self.status = tk.StringVar(value='Önce mağaza seçin; ardından kategoriyi belirleyin.')
        ttk.Label(left, textvariable=self.status, foreground='#cbd7ee').pack(anchor='w', pady=(0, 5))
        pager=ttk.Frame(left)
        pager.pack(fill='x',pady=(0,5))
        ttk.Button(pager,text='◀ Önceki',command=lambda:self.change_page(-1)).pack(side='left')
        self.page_text=tk.StringVar(value='Sayfa 1/1')
        ttk.Label(pager,textvariable=self.page_text).pack(side='left',padx=10)
        ttk.Button(pager,text='Sonraki ▶',command=lambda:self.change_page(1)).pack(side='left')
        self.pool = ttk.Treeview(left, columns=('mark', 'uid', 'state', 'owner'), show='tree headings',
                                 selectmode='browse', height=10,style='StoreAssign.Treeview')
        self.pool.heading('#0', text='Fotoğraf')
        self.pool.column('#0',width=90,minwidth=65,stretch=False,anchor='center')
        for key, title, width, stretch in [
            ('mark', 'Seç', 58, False), ('uid', 'Onaylı mockup görseli', 240, True),
            ('state', 'Durum', 165, False), ('owner', 'Mağaza', 140, False),
        ]:
            self.pool.heading(key, text=title)
            self.pool.column(key, width=width, minwidth=45, stretch=stretch,
                             anchor='center' if key in ('mark','state') else 'w')
        self.pool.tag_configure('available', foreground='#b9dfec')
        self.pool.tag_configure('assigned_here', foreground='#6ef5aa')
        self.pool.tag_configure('used_elsewhere', foreground='#fb9e9e')
        self.pool.tag_configure('stale', foreground='#ffbc77')
        scroll = ttk.Scrollbar(left, orient='vertical', command=self.pool.yview)
        self.pool.configure(yscrollcommand=scroll.set)
        self.pool.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')
        self.pool.bind('<ButtonRelease-1>', self._toggle_row)
        self.pool.bind('<space>', self._toggle_keyboard)
        self.pool.bind('<<TreeviewSelect>>', self._preview_selected, add='+')

        right = ttk.LabelFrame(main, text='3  SEÇİLEN MAĞAZANIN MEVCUT ATAMALARI',
                               style='Premium.TLabelframe', padding=10)
        right.pack(side='left', fill='both', expand=True, padx=(7, 0))
        self.assigned_summary = tk.StringVar(value='Henüz mağaza seçilmedi.')
        ttk.Label(right, textvariable=self.assigned_summary, wraplength=310).pack(anchor='w', pady=(0, 5))
        self.assigned = ttk.Treeview(right, columns=('template', 'condition'), show='headings',
                                     selectmode='extended', height=6, style='StoreAssign.Small.Treeview')
        for key, label, width in [('template','Kategori / Atanmış mockup',242),('condition','Durum',98)]:
            self.assigned.heading(key, text=label)
            self.assigned.column(key, width=width, minwidth=60, stretch=True)
        self.assigned.tag_configure('healthy',foreground='#6ef5aa')
        self.assigned.tag_configure('stale',foreground='#fdba74')
        self.assigned.pack(fill='x',pady=(0, 8))
        preview = ttk.Frame(right, padding=5)
        preview.pack(fill='both', expand=True)
        self.preview_image = ttk.Label(preview, text='Şablon önizlemesi\nListeden bir mockup seçin.', anchor='center')
        self.preview_image.pack(fill='both', expand=True)
        self.preview_info = tk.StringVar(value='')
        ttk.Label(preview, textvariable=self.preview_info, wraplength=340, justify='left').pack(fill='x')
        ttk.Button(right, text='Seçili Atamaları Kaldır (Onaylı)', command=self.unassign).pack(side='bottom',fill='x',before=preview,pady=(5, 0))

        bottom = ttk.Frame(body, padding=(5, 11))
        bottom.pack(side='bottom',fill='x',before=main)
        self.marked_count = tk.StringVar(value='0 mockup seçildi')
        ttk.Label(bottom, textvariable=self.marked_count, font=('Segoe UI', 12, 'bold')).pack(side='left')
        ttk.Label(bottom, text='Kırmızı: başka mağazada · Yeşil: bu mağazada · Mavi: atanabilir',
                  foreground='#cbd7ee').pack(side='left', padx=22)
        ttk.Button(bottom, text='Kapat', command=self.pop.destroy).pack(side='right')
        ttk.Button(bottom, text='✓ SEÇİLEN MOCKUPLARI MAĞAZAYA ATA',
                   style='Premium.Primary.TButton', command=self.assign).pack(side='right', padx=(0, 14))

    def _category_code(self):
        s = self.category.get()
        for cat in CATEGORY_LABELS_TR:
            if s.endswith(f'({cat})'):
                return cat
        return None

    def reload_stores(self, selected=None):
        cfg = self.mgr.load()
        names = sorted(cfg['stores'])
        self.stores['values'] = names
        keep = selected or self.store.get()
        self.store.set(keep if keep in names else '')
        self.categories.configure(state='readonly' if self.store.get() else 'disabled')
        self.refresh()

    def add_store(self):
        try:
            name = self.new_store.get().strip()
            self.mgr.add_store(name)
            self.new_store.set('')
            self.reload_stores(name)
            self.on_change()
        except (ValueError, OSError) as exc:
            messagebox.showerror('Mağaza oluşturulamadı', f'{exc}\n\nYeni ve benzersiz mağaza kodu girin.', parent=self.pop)

    def _changed_store(self):
        self.category.set('')
        self._page=0
        self.marked.clear()
        self.categories.configure(state='readonly' if self.store.get() else 'disabled')
        self.refresh()

    def refresh(self):
        self.marked.clear()
        self._page=0
        self.approved = list(self.get_approved())
        self.config = self.mgr.load()
        self.render_rows()
        self.render_assigned()

    def _search_changed(self):
        self._page=0
        self.render_rows()

    def change_page(self, delta):
        self._page=max(0,self._page+delta)
        self.render_rows()

    def render_rows(self):
        self._thumb_seq += 1
        self._thumb_refs.clear()
        self.pool.delete(*self.pool.get_children())
        self.rows.clear()
        self._visible_keys=[]
        self._all_category_rows=[]
        if not self.store.get():
            self.status.set('Önce mağaza seçin.')
            self._marked_count()
            return
        cat = self._category_code()
        if not cat:
            self.status.set('Şimdi kategori seçin. Onaylı mockup görselleri burada listelenecek.')
            self._marked_count()
            return
        available = status_inventory(self.store.get(), cat, self.approved, self.config)
        query = self.search.get().strip().casefold()
        self._all_category_rows=available
        filtered = [r for r in available if not query or query in str(r['item']['uid']).casefold()]
        total_pages=max(1,(len(filtered)+self._page_limit-1)//self._page_limit)
        self._page=min(self._page,total_pages-1)
        visible = filtered[self._page*self._page_limit:(self._page+1)*self._page_limit]
        self.page_text.set(f'Sayfa {self._page+1}/{total_pages} · {len(filtered)} kayıt')
        state_counts = {s: sum(r['state'] == s for r in filtered)
                        for s in ('available','assigned_here','used_elsewhere','stale')}
        for index, row in enumerate(visible):
            key = row['key']
            self.rows[key] = row
            name = str(row['item']['uid'])
            owner = row['owner'] or '—'
            states = {'available':'Kullanılabilir','assigned_here':'Bu mağazada',
                      'used_elsewhere':'DAHA ÖNCE KULLANILDI', 'stale':'ONAY/SHA DEĞİŞMİŞ'}
            mark = '☑' if key in self.marked else ('☐' if row['state']=='available' else '—')
            self.pool.insert('', 'end', iid=str(index), text='▣', values=(mark,name,states[row['state']],owner),
                             tags=(row['state'],))
        self._visible_keys = [r['key'] for r in visible]
        self.marked.intersection_update({r['key'] for r in available if r['state']=='available'})
        self.status.set(f"{len(filtered)} onaylı mockup | Uygun: {state_counts['available']}  "
                        f"| Bu mağazada: {state_counts['assigned_here']}  | Başka mağazada: {state_counts['used_elsewhere']}  | İnceleme: {state_counts['stale']}")
        self._marked_count()
        seq=self._thumb_seq
        if visible:
            self.pop.after(1,lambda:self._draw_row_thumbnails(seq,visible,0))

    def _draw_row_thumbnails(self, seq, visible, index):
        if seq != self._thumb_seq or not self.pop.winfo_exists() or index>=len(visible):
            return
        iid=str(index)
        try:
            item=visible[index]['item']
            path=Path(item.get('source') or '')
            if not item.get('source') or path.is_symlink() or not path.is_file():
                raise OSError('Dosya yok')
            with Image.open(path) as src:
                src.draft('RGB',(90,64))
                thumb=ImageOps.exif_transpose(src).convert('RGB')
                thumb.thumbnail((60,37),Image.Resampling.BILINEAR)
            ref=ImageTk.PhotoImage(thumb,master=self.pop)
            self._thumb_refs[iid]=ref
            if self.pool.exists(iid):
                self.pool.item(iid,image=ref,text='')
        except (OSError,ValueError,tk.TclError):
            pass
        self.pop.after(1,lambda:self._draw_row_thumbnails(seq,visible,index+1))

    def _toggle_row(self, event):
        iid = self.pool.identify_row(event.y)
        if iid:
            self._toggle_iid(iid)

    def _toggle_keyboard(self, _event):
        selection = self.pool.selection()
        if selection:
            self._toggle_iid(selection[0])
        return 'break'

    def _toggle_iid(self, iid):
        index = int(iid)
        if index >= len(self._visible_keys):
            return
        key = self._visible_keys[index]
        row = self.rows[key]
        if row['state'] != 'available':
            self.preview_info.set(f"Kullanılamaz: {row['item']['uid']}\nAit olduğu mağaza: {row['owner']}\n"
                                  'Aynı mockup başka mağazada tekrar kullanılamaz. '
                                  'Aynı baskı tasarımını farklı mockup ile kullanabilirsin.')
            return
        if key in self.marked:
            self.marked.remove(key)
        else:
            self.marked.add(key)
        self.pool.set(iid, 'mark', '☑' if key in self.marked else '☐')
        self._marked_count()

    def _marked_count(self):
        self.marked_count.set(f'{len(self.marked)} mockup seçildi — yalnız bunlar atanacak')

    def select_available(self):
        self.marked.update(key for key in self._visible_keys if self.rows[key]['state']=='available')
        self.render_rows()
        # render_rows preserves marked keys when list reloaded.

    def select_all_available(self):
        self.marked.update(row['key'] for row in self._all_category_rows if row['state']=='available')
        self.render_rows()

    def clear_selection(self):
        self.marked.clear()
        self.render_rows()

    def render_assigned(self):
        self.assigned.delete(*self.assigned.get_children())
        self.assigned_keys = []
        store = self.store.get()
        if not store:
            self.assigned_summary.set('Önce mağaza seçin.')
            return
        entries = assigned_for_store(store, self.approved, self.config)
        for n, row in enumerate(entries):
            item = row['item']
            key = row['key']
            self.assigned_keys.append(key)
            if item is None:
                self.assigned.insert('', 'end', iid=str(n), values=(key.split('@')[0], 'Onay/SHA değişmiş'),tags=('stale',))
            else:
                self.assigned.insert('', 'end', iid=str(n),
                                     values=(f"{item['category'].split('_')[0]} · {item['uid']}", 'Bu mağazada'), tags=('healthy',))
        self.assigned_summary.set(f'{store} mağazası: {len(entries)} atama. '
                                  'Sağda atanan şablonları, solda uygun ve kullanılmış şablonları görüyorsun.')

    def _preview_selected(self, _event=None):
        sel = self.pool.selection()
        if not sel or not self._visible_keys:
            return
        index = int(sel[-1])
        if index >= len(self._visible_keys):
            return
        row = self.rows.get(self._visible_keys[index])
        if not row:
            return
        item = row['item']
        self.preview_info.set(f"{item['uid']}\n{CATEGORY_LABELS_TR.get(item['category'],'')}\n"
                              f"{('Kullanılabilir' if row['state']=='available' else 'Ait olduğu mağaza: '+str(row['owner']))}")
        self._image_seq += 1
        seq = self._image_seq
        self.pop.after(65, lambda: self._draw_preview(item, seq))

    def _draw_preview(self, item, seq):
        if seq != self._image_seq or not self.pop.winfo_exists():
            return
        try:
            path = Path(item.get('source') or '')
            if not item.get('source') or path.is_symlink() or not path.is_file():
                raise OSError('Kaynak dosya bulunamadı.')
            with Image.open(path) as src:
                src.draft('RGB',(210,180))
                thumb = ImageOps.exif_transpose(src).convert('RGB')
                thumb.thumbnail((185,130),Image.Resampling.LANCZOS)
            self._image = ImageTk.PhotoImage(thumb,master=self.pop)
            self.preview_image.configure(image=self._image,text='')
        except (OSError,ValueError):
            self._image = None
            self.preview_image.configure(image='',text='Önizleme açılamadı')

    def _confirm_assignment(self, store: str, category: str, names: list[str]) -> bool:
        """Scrollable final preview of EVERY chosen mockup; exactly one explicit confirmation."""
        dialog=tk.Toplevel(self.pop)
        dialog.title('SON KONTROL — Mağaza ve Seçili Mockup Onayı')
        dialog.geometry('690x550')
        dialog.minsize(520,390)
        dialog.configure(bg=BG)
        dialog.transient(self.pop)
        body=ttk.Frame(dialog,padding=16)
        body.pack(fill='both',expand=True)
        ttk.Label(body,text=f'Mağaza: {store}',font=('Segoe UI',15,'bold')).pack(anchor='w')
        ttk.Label(body,text=f'Kategori: {CATEGORY_LABELS_TR.get(category,category)}',
                  font=('Segoe UI',12,'bold')).pack(anchor='w',pady=(4,8))
        ttk.Label(body,text=f'YALNIZCA aşağıdaki {len(names)} onaylı mockup atanacak.',
                  foreground='#6ef5aa',font=('Segoe UI',12,'bold')).pack(anchor='w',pady=(0,9))
        ttk.Label(body,text='Aynı HAM baskı tasarımını başka mağazada farklı mockup ile kullanabilirsin.',
                  wraplength=630).pack(anchor='w',pady=(0,7))
        content=ttk.Frame(body)
        content.pack(fill='both',expand=True)
        listbox=tk.Listbox(content,bg=PANEL,fg=FG,selectbackground=ACCENT,
                           font=('Segoe UI',10),height=12,exportselection=False)
        listbox.pack(side='left',fill='both',expand=True)
        sb=ttk.Scrollbar(content,orient='vertical',command=listbox.yview)
        sb.pack(side='right',fill='y')
        listbox.configure(yscrollcommand=sb.set)
        for i,name in enumerate(names,1):
            listbox.insert('end',f'{i:03d}  {name}')
        result=[False]
        def done(ok):
            result[0]=ok
            dialog.destroy()
        bar=ttk.Frame(body)
        bar.pack(fill='x',pady=(12,0))
        ttk.Button(bar,text='Vazgeç',command=lambda:done(False)).pack(side='right')
        ttk.Button(bar,text=f'✓ {len(names)} MOCKUPU ATA',style='Premium.Primary.TButton',
                   command=lambda:done(True)).pack(side='right',padx=(0,12))
        dialog.protocol('WM_DELETE_WINDOW',lambda:done(False))
        dialog.grab_set()
        dialog.wait_window()
        return result[0]

    def assign(self):
        try:
            store = self.store.get()
            cat = self._category_code()
            if not cat:
                raise ValueError('Önce mağazayı, ardından kategoriyi seçin.')
            fresh = self.mgr.load()
            items = checked_assignment(store,cat,self.marked,self.approved,fresh)
            names = [str(x['uid']) for x in items]
            sure = self._confirm_assignment(store,cat,names)
            if not sure:
                return
            # Recheck ownership and approved status at the last possible moment.
            checked_assignment(store,cat,self.marked,self.approved,self.mgr.load())
            self.mgr.assign(store,items,all_approved=self.approved)
            messagebox.showinfo('Atama tamamlandı',f'{store}: {len(items)} mockup atandı.\n'
                                'Diğer mağazalar bu mockup kaynaklarını seçemez.', parent=self.pop)
            self.refresh()
            self.on_change()
        except (OSError,ValueError,KeyError) as exc:
            messagebox.showerror('Atama yapılamadı',str(exc)+'\n\nListeyi yenileyip uygun şablon seçin.',parent=self.pop)

    def unassign(self):
        indices = self.assigned.selection()
        store = self.store.get()
        if not indices or not store:
            messagebox.showwarning('Atama seçilmedi','Sağdaki listeden kaldırmak istediğin atamaları seç.',parent=self.pop)
            return
        keys = [self.assigned_keys[int(i)] for i in indices]
        names = '\n'.join('• '+k.split('@')[0] for k in keys[:12])
        if not messagebox.askyesno('Atamayı kaldır',f'{store} mağazasından {len(keys)} atama kaldırılsın mı?\n{names}\n\n'
                                   'Kaynak şablonlar ve eski üretim çıktıları silinmez.',parent=self.pop):
            return
        try:
            cfg = self.mgr.load()
            current = cfg['stores'][store]['templates']
            if not set(keys).issubset(set(current)):
                raise ValueError('Atama listesi değişti. Yenileyip tekrar dene.')
            cfg['stores'][store]['templates'] = [k for k in current if k not in set(keys)]
            self.mgr.save(cfg)
            self.refresh()
            self.on_change()
        except (OSError,ValueError,KeyError) as exc:
            messagebox.showerror('Kaldırma hatası',str(exc),parent=self.pop)
