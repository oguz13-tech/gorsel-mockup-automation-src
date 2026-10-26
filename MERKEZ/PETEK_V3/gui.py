"""Native PETEK V3 template-mask review + local serial production screens.

No browser service, no remote publishing. Thread workers report through Tk queue.
"""
from __future__ import annotations
import io
import json
import os
from pathlib import Path
import queue
import re
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

import cv2
import numpy as np
from PIL import Image, ImageTk

from . import engine, curves as curve_math
from dark_theme_v42 import BG, PANEL, FG, MUTED
from help_v42 import bind_help
from .batch import Batch
from .registry import Registry
from .viewport import Viewport
from .brush_tools import apply_stroke, brush_radius_screen

LIGHT_LABELS=('Doğal (Önerilen)','Belirgin Işık','Işıksız / Tasarım Orijinal')
def _lighting_code(value):
    return {'Doğal (Önerilen)':'natural','Belirgin Işık':'strong','Işıksız / Tasarım Orijinal':'off'}.get(value,value)
from quad_interaction import begin,target


def _display_size(shape, canvas):
    """Fit full source photo to the ACTUAL visible canvas, not the monitor.

    Previous version used screen dimensions and positioned a Canvas whose Tk
    parent was the toplevel behind an overlapping frame. The photo loaded but
    could not be seen. All coordinates remain in unmodified source pixels.
    """
    h, w = shape[:2]
    available_w = max(160, canvas.winfo_width() - 18)
    available_h = max(160, canvas.winfo_height() - 18)
    ratio = min(1., available_w / w, available_h / h)
    return (max(1, int(round(w * ratio))),
            max(1, int(round(h * ratio))), ratio)


class MaskEditor:
    """Human-reviewed editable mask; masks stay in source-pixel coordinates."""
    def __init__(self,parent, registry=None, on_saved=None, runtime_root=None):
        self.registry=registry or Registry();self.on_saved=on_saved
        self.runtime_root=Path(runtime_root).resolve() if runtime_root else None
        self.window=tk.Toplevel(parent)
        self.window.title('PETEK — Mockup Baskı Alanı Düzenleyici')
        # Match the *usable* screen, including small laptops / display scaling.
        screen_w = self.window.winfo_screenwidth()
        screen_h = self.window.winfo_screenheight()
        window_w = min(1300, max(540, screen_w - 46))
        window_h = min(970, max(440, screen_h - 86))
        self.window.geometry(f'{window_w}x{window_h}+12+12')
        self.window.minsize(min(700, window_w), min(480, window_h))
        self.window.transient(parent)
        wrapper = ttk.Frame(self.window, padding=9)
        wrapper.pack(fill='both', expand=True)

        # Scrollable tool column: all actions remain reachable on 720px screens.
        control_width = min(285, max(205, int(screen_w * .34)))
        left_host = ttk.Frame(wrapper, width=control_width)
        left_host.pack(side='left', fill='y', padx=(0, 12))
        left_host.pack_propagate(False)
        self.tools_scroll = tk.Canvas(left_host, width=control_width, bg=BG,
                                      highlightthickness=0, borderwidth=0)
        tool_scrollbar = ttk.Scrollbar(left_host, orient='vertical',
                                      command=self.tools_scroll.yview)
        self.tools_scroll.configure(yscrollcommand=tool_scrollbar.set)
        tool_scrollbar.pack(side='right', fill='y')
        self.tools_scroll.pack(side='left', fill='both', expand=True)
        left = ttk.Frame(self.tools_scroll)
        tool_window = self.tools_scroll.create_window((0, 0), window=left,
                                                      anchor='nw')
        left.bind('<Configure>', lambda event: self.tools_scroll.configure(
            scrollregion=self.tools_scroll.bbox('all')))
        self.tools_scroll.bind('<Configure>', lambda event: self.tools_scroll.itemconfigure(
            tool_window, width=event.width))

        # CRITICAL: canvas must be an ACTUAL child of wrapper, not self.window.
        # Otherwise its sibling wrapper paints over it: image loads but is blank.
        self.canvas = tk.Canvas(wrapper, bg='#202329', highlightthickness=1,
                                borderwidth=0)
        self.canvas.pack(side='right', fill='both', expand=True)
        self.canvas.bind('<Configure>', self._canvas_resized)
        def hint(parent, value):
            ttk.Label(parent, text=value, wraplength=280, foreground=MUTED,
                      font=('Segoe UI', 9)).pack(anchor='w', pady=(0, 5))
        ttk.Label(left,text='PETEK: Mockup Hazırlama',font=('Segoe UI',16,'bold')).pack(anchor='w',pady=(2,12))
        ttk.Button(left,text='1. PETEK Mockup Fotoğrafını Seç',command=self.pick).pack(fill='x',pady=3)
        hint(left, 'Baskısız dolabın ODA fotoğrafını seç. Sonraki adım: dört köşeyi belirt.')
        self.path=tk.StringVar(value='Mockup fotoğrafı seçilmedi')
        ttk.Label(left,textvariable=self.path,wraplength=278).pack(anchor='w',pady=4)
        ttk.Label(left,text='Mockup Adı / Numarası').pack(anchor='w',pady=(10,2))
        self.uid=tk.StringVar();ttk.Entry(left,textvariable=self.uid).pack(fill='x')
        hint(left, 'Aynı mockup için benzersiz ad. Onaylı eski profil yerine yeni taslak oluştur.')
        ttk.Label(left,text='PETEK Ön Yüzü En / Boy Oranı').pack(anchor='w',pady=(8,2))
        self.aspect=tk.StringVar(value='1.1163');ttk.Entry(left,textvariable=self.aspect).pack(fill='x')
        hint(left, 'Gerçek ön panel GENİŞLİK / YÜKSEKLİK oranı; otomatik tahmin değil.')
        self.mode=tk.StringVar(value='corners')
        self._qdrag=None;self._qchanged=False;self._before_drag=None
        self._loaded_approved=False;self._mask_invalid=False
        ttk.Radiobutton(left,text='Köşeleri veya dörtgeni fareyle düzelt',
                        variable=self.mode,value='adjust').pack(anchor='w',pady=3)
        ttk.Label(left,text='Kırmızı köşeyi sürükle; mavi kenar iki köşeyi; dörtgenin içi tüm alanı taşır.',wraplength=272).pack(anchor='w')

        self.expert=ttk.Frame(left);self.expert_on=False
        for value,label in [ ('corners','Dört köşe seç (TL → TR → BR → BL)'),
                            ('wood','Fırça: AHŞAP = baskı yapılsın'),
                            ('protect','Fırça: DELİK/KAVİS/ZEMİN koru'),
                            ('top','ÜST KAVİSİ MANUEL İŞARETLE (sarı noktalar)'),
                            ('bottom','ALT KAVİSİ MANUEL İŞARETLE (mavi noktalar)')]:
            ttk.Radiobutton(self.expert,text=label,variable=self.mode,value=value).pack(anchor='w',pady=3)
        ttk.Label(self.expert,text='Fırça çapı (kaynak piksel)').pack(anchor='w',pady=(8,0))
        self.brush=tk.IntVar(value=23)
        brush_row=ttk.Frame(self.expert);brush_row.pack(fill='x')
        ttk.Scale(brush_row,from_=3,to=150,variable=self.brush,orient='horizontal').pack(side='left',fill='x',expand=True)
        self.brush_readout=ttk.Label(brush_row,text='23 px',width=9);self.brush_readout.pack(side='right')
        self.brush.trace_add('write',self._brush_size_changed)
        ttk.Button(left,text='2. Ahşap Baskı Alanını TASLAK Oluştur',command=self.auto).pack(fill='x',pady=(12,3))
        hint(left, 'Turuncu = baskı alanı. Siyah yarıkları, üst-alt kavisleri ve zemini koru; ardından düzelt.')
        ttk.Label(left,text='Ortam Işığı (fotoğraftan)').pack(anchor='w')
        self.lighting=tk.StringVar(value=LIGHT_LABELS[0])
        ttk.Combobox(left,textvariable=self.lighting,state='readonly',values=LIGHT_LABELS).pack(fill='x',pady=3)
        ttk.Button(left,text='Kavis, Fırça ve Yakınlaştırma Araçlarını Aç/Kapat',command=self.toggle_expert).pack(fill='x',pady=4)
        hint(left, 'Beyaz kalan ahşabı fırçayla işaretle; yarıkları koru. Fırça dörtgen dışına çıkmaz.')
        ttk.Button(self.expert,text='Köşeleri Yeniden Seç',command=self.reset_corners).pack(fill='x',pady=3)
        ttk.Button(self.expert,text='Dörtgen Dışındaki Turuncuyu Temizle',
                   command=self.clean_outside_mask).pack(fill='x',pady=3)
        ttk.Button(self.expert,text='Ahşaptaki küçük beyaz benekleri temizle (taslak)',
                   command=self.repair_small_gaps).pack(fill='x',pady=3)
        ttk.Button(self.expert,text='? Dört köşe / kavis nasıl işaretlenir?',
                   command=self.show_marking_help).pack(fill='x',pady=3)
        ttk.Label(self.expert,text='Kavis: soldan ve sağdan en yakın kenara tıkla; '+
                  'uçlar kenara bağlanır. Nokta sürükle; Shift+tıkla sık noktayı ekle; '+
                  'Delete sil, Ctrl+Z geri al.',wraplength=275).pack(anchor='w',pady=4)
        ttk.Button(self.expert,text='Seçtiğim Üst/Alt Kavis Çizgisini Uygula',command=self.finish_curve).pack(fill='x',pady=3)
        hint(self.expert, 'Üst ve altı AYRI işaretle; nokta uçlarını kırmızı yan sınıra yaklaştır. Sonra önizle.')
        ttk.Button(self.expert,text='Geri Al (Ctrl+Z)',command=self.undo).pack(fill='x',pady=3)
        # Sentetik şeritli debug önizlemesi kullanıcıyı karıştırmasın; gelişmiş bölümdedir.
        ttk.Button(self.expert,text='Test deseniyle kontrol (tanılama)',command=self.preview_render).pack(fill='x',pady=3)
        ttk.Button(self.expert,text='4 farklı baskı kenarı karşılaştır (A/B)',
                   command=self.preview_edge_variants).pack(fill='x',pady=3)
        ttk.Button(self.expert,text='Kes-Yapıştır Delik/Kavis Katmanı Doğrula',
                   command=self.verify_cutout_overlay).pack(fill='x',pady=3)
        ttk.Button(left,text='3. GERÇEK Baskı Tasarımıyla Önizle',command=self.preview_real_design).pack(fill='x',pady=(3,3))
        hint(left, 'Mockup değil, ürünün üzerine basılacak DESEN dosyasını seç; bu adım kaydetmez.')
        ttk.Label(left,text='Görüntüyü büyüt: fare tekerleği · Kaydır: Boşluk+Sürükle',wraplength=274).pack(anchor='w')
        ttk.Button(left,text='4. Düzenlediğim Maskeyi TASLAK Kaydet',command=self.save_draft).pack(fill='x',pady=(8,3))
        hint(left, 'Köşe, kavis ve maskeyi kaydeder. Henüz seri üretime açılmaz; sonraki adım onay.')
        self.reviewer=tk.StringVar()
        ttk.Label(left,text='İnceleyen kişi').pack(anchor='w',pady=(9,1))
        ttk.Entry(left,textvariable=self.reviewer).pack(fill='x')
        self.confirm=tk.BooleanVar(value=False)
        ttk.Checkbutton(left,text='Delikleri, iç gölgeyi, üst/alt kavis ve\narkadaki zemini kontrol ettim.',variable=self.confirm).pack(anchor='w',pady=5)
        ttk.Button(left,text='5. Kontrol Ettim — Mockupı Üretime Aç',command=self.approve).pack(fill='x',pady=4)
        hint(left, 'Yalnız görsel kontrolünden sonra onayla; onaylı profil PETEK üretim listesine girer.')
        self.status=tk.StringVar(value='Dikkat: 4 köşe içinde kalan her piksel ahşap değildir.')
        ttk.Label(left,textvariable=self.status,wraplength=275,foreground='#fbbf24').pack(fill='x',pady=10)
        ttk.Label(left,text='TURUNCU: tasarımın basılacağı yüzey.\nŞEFFAF: orijinal delik/gölge/kavis/parke.\nMaske onayı kaynak SHA ile kilitlenir.',wraplength=285).pack(anchor='w')
        self.scene=None;self.source=None;self.mask=None;self.quad=[];self.photo=None
        self.mode.set('corners');self.undo_stack=[];self.curve=[]
        self.curves={'top':[],'bottom':[]}
        self.curve_base=None  # source candidate BEFORE user-defined curves
        self._curve_mode_name='corners'
        self._dragged_curve_index=None
        self._selected_curve_index=None
        self.mode.trace_add('write',self._curve_mode_changed)
        self.view=None;self._pan_anchor=None;self._space_down=False
        self._brush_last_point=None;self._cursor_xy=None
        self.canvas.bind('<Motion>',self._cursor_motion)
        self.canvas.bind('<Leave>',self._cursor_leave)
        self.canvas.bind('<Button-1>',self.click)
        self.canvas.bind('<B1-Motion>',self.drag)
        self.canvas.bind('<ButtonRelease-1>',self._end_paint)
        self.canvas.bind('<MouseWheel>',self._mouse_zoom)
        self.canvas.bind('<Button-4>',self._mouse_zoom)
        self.canvas.bind('<Button-5>',self._mouse_zoom)
        self.canvas.bind('<Double-Button-1>',self._fit_view)
        self.canvas.bind('<Button-2>',self._start_pan)
        self.canvas.bind('<B2-Motion>',self._drag_pan)
        self.canvas.bind('<Button-3>',self._start_pan)
        self.canvas.bind('<ButtonRelease-2>',lambda e:setattr(self,'_pan_anchor',None))
        self.canvas.bind('<ButtonRelease-3>',lambda e:setattr(self,'_pan_anchor',None))
        self.canvas.bind('<B3-Motion>',self._drag_pan)
        self.window.bind('<KeyPress-space>',self._space_press)
        self.window.bind('<KeyRelease-space>',self._space_release)
        self.window.bind('<Control-z>',self._keyboard_undo)
        self.window.bind('<Control-Z>',self._keyboard_undo)
        self.window.bind('<Delete>',self.delete_curve_point)
        self.window.bind('<BackSpace>',self.delete_curve_point)
        self.window.bind('<Escape>',self._cancel_geometry)
        self._paint_active=False
        self.window.protocol('WM_DELETE_WINDOW',self.window.destroy)
        self.scale=1.0;self.draw_dims=(0,0)
        zoom_row=ttk.Frame(left);zoom_row.pack(fill='x',pady=3)
        ttk.Button(zoom_row,text='Sığdır',command=self._fit_view).pack(side='left',expand=True,fill='x')
        ttk.Button(zoom_row,text='100%',command=self._actual_size).pack(side='left',expand=True,fill='x')
        ttk.Button(zoom_row,text='−',command=lambda:self._button_zoom(.75)).pack(side='left',padx=2)
        ttk.Button(zoom_row,text='+',command=lambda:self._button_zoom(1.33)).pack(side='left')
        self._resize_after=None
        self.window.update_idletasks()
        self.window.lift()
        bind_help(self.window)

    def _curve_mode_changed(self,*_):
        previous=getattr(self,'_curve_mode_name',None)
        if not hasattr(self,'curves'):return
        if previous in ('top','bottom'):
            self.curves[previous]=[list(pt) for pt in self.curve]
        current=self.mode.get()
        self._curve_mode_name=current
        self.curve=[list(pt) for pt in self.curves.get(current,[])]
        self._selected_curve_index=None
        if getattr(self,'scene',None) is not None and getattr(self,'view',None) is not None:self.refresh()

    def _curve_snapshot(self):
        return ('curve_state', self.mode.get(),
                {k:[list(pt) for pt in v] for k,v in self.curves.items()},
                self.mask.copy(),
                None if self.curve_base is None else self.curve_base.copy())

    def _remember_curve(self, *, points_only=False):
        if points_only:
            # Avoid full resolution image copies for EACH point on a long curve.
            self.undo_stack.append(('curve_points',self.mode.get(),
                {k:[list(pt) for pt in v] for k,v in self.curves.items()}))
            self.undo_stack=self.undo_stack[-64:]
        else:
            self.undo_stack.append(self._curve_snapshot())
            self.undo_stack=self.undo_stack[-16:]


    def _preview_curve_clip(self):
        # Recreate from original candidate, never cut the previously clipped mask.
        if self.curve_base is not None:
            self.mask=curve_math.apply(self.curve_base,self.quad,
                 self.curves['top'],self.curves['bottom'],require_ends=False)

    def toggle_expert(self):
        self.expert_on=not self.expert_on
        if self.expert_on:self.expert.pack(fill='x',pady=6)
        else:self.expert.pack_forget()

    def _next_version(self):
        """Never allow automatic updates to human approved registry records."""
        if not self._loaded_approved:return
        current=self.uid.get()
        for n in range(2,500):
            new=(current[:90]+f'_r{n}')[:100]
            try:self.registry.get(new)
            except engine.MaskError:
                self.uid.set(new);self._loaded_approved=False
                return
        raise engine.MaskError('Yeni profil kimliği oluşturulamadı.')

    def _release_geometry(self):
        if self._qdrag is None:return
        self._qdrag=None
        if not self._qchanged:return
        self._qchanged=False
        self._next_version()
        if self._before_drag is not None:
            self.undo_stack.append(('geometry',self._before_drag[0],self._before_drag[1]))
            self.undo_stack=self.undo_stack[-5:]
        self.curve=[];self.curves={'top':[],'bottom':[]};self.curve_base=None
        self.mask=np.zeros(self.scene.shape[:2],np.uint8)
        # An old image-space mask CANNOT follow a new panel while retaining vents.
        # Source-driven re-segmentation is mandatory, not optional.
        try:
            self.mask,report=engine.auto_mask_candidate(self.scene,self.quad)
            self.status.set('Dörtgen düzeltildi; YENİ TASLAK oluşturuldu. Delikleri/kavisleri gerçek tasarımla kontrol et.')
        except (engine.MaskError,ValueError) as exc:
            self.status.set('Yeni geometri için maske taslağı oluştur: '+str(exc)[:120])
        self.confirm.set(False)
        self.refresh()

    def _cancel_geometry(self,_event=None):
        if self._qdrag is None or self._before_drag is None:return
        self.quad,self.mask=self._before_drag
        self._qdrag=None;self._qchanged=False
        self.status.set('Dörtgen taşınması iptal edildi.')
        self.refresh()

    def pick(self):
        initial=None
        if self.runtime_root is not None:
            try:
                from petek_folders_v46 import petek_directory
                approved_work=petek_directory(self.runtime_root,'2_SABLON_HAVUZU')
                if approved_work.is_dir():initial=str(approved_work)
            except (ValueError,OSError) as exc:
                messagebox.showerror('PETEK klasör uyuşmazlığı',str(exc),parent=self.window)
                return
        options=dict(parent=self.window,
                     title='PETEK Mockup Fotoğrafı — Çalışma Havuzu / Petek_Dolabi',
                     filetypes=[('Mockup fotoğrafı','*.jpg *.jpeg *.png *.webp')])
        if initial:options['initialdir']=initial
        path=filedialog.askopenfilename(**options)
        if path:self.load(Path(path))

    def load(self,path):
        try:
            scene=engine.read_bgr(path)
            self.scene=scene;self.source=Path(path).resolve();self.mask=np.zeros(scene.shape[:2],np.uint8);self.view=None
            self.quad=[];self.undo_stack=[];self.curve=[];self.curves={'top':[],'bottom':[]};self.curve_base=None;self._loaded_approved=False;self._qdrag=None
            uid=re.sub('[^A-Za-z0-9_-]','_',self.source.stem)[:80]
            current_sha=engine.digest(self.source)
            # A reviewed mockup can have a human-chosen UID unlike filename.
            # Reopen its unique SHA-matched profile without renaming anything.
            if not (self.registry.profiles/(uid+'.json')).is_file():
                matched=[item['uid'] for item in self.registry.list()
                         if item['source_sha']==current_sha]
                if len(matched)==1:uid=matched[0]
            else:
                # CRITICAL: identical filenames from different accounts can
                # represent different photos. Never overwrite the first UID.
                saved=json.loads((self.registry.profiles/(uid+'.json')).read_text('utf-8'))
                if saved.get('source_sha')!=current_sha:
                    uid=uid[:65]+'_'+current_sha[:16]
                    if (self.registry.profiles/(uid+'.json')).exists():
                        existing=json.loads((self.registry.profiles/(uid+'.json')).read_text('utf-8'))
                        if existing.get('source_sha')!=current_sha:
                            raise engine.MaskError('Farklı görselin aynı kimliğe sahip olması engellendi.')
                    self.status.set('Aynı isimde farklı mockup tespit edildi; SHA kimliğiyle ayrı kayıt açıldı.')
            self.uid.set(uid)
            try:
                p,mask=self.registry.get(uid)
                if p['source_sha']==engine.digest(self.source):
                    self.mask=mask.copy();self.quad=p['quad'];self.aspect.set(str(p['physical_aspect']))
                    if p.get('curve_points'):
                        self.curves={k:[list(v) for v in p['curve_points'].get(k,[])] for k in ('top','bottom')}
                        if p.get('base_mask_sha'):
                            self.curve_base=engine.decode_mask(self.registry.masks/(p['base_mask_sha']+'.png'))
                            if engine.mask_hash(self.curve_base)!=p['base_mask_sha']:
                                raise engine.MaskError('Kavis temel maskesi SHA uyuşmuyor.')
                    self._loaded_approved=p['status']=='APPROVED'
                    self.status.set('Kayıtlı '+p['status']+' maske yüklendi. Gerekirse yeni taslak kaydedin.')
            except engine.MaskError:
                # SHA-verified suggestions from user's 10 private sample mockups.
                # These are NEVER approvals: visually correct every boundary.
                suggestions=Path(__file__).with_name('reference_quads.json')
                if suggestions.is_file():
                    entry=json.loads(suggestions.read_text('utf-8')).get(engine.digest(self.source))
                    if entry:
                        self.quad=entry['quad']
                        self.status.set('Örnek görsel için TAHMİNİ dört köşe yüklendi. Dört köşeyi, kavisleri GÖZLE doğrula!')
                    else:
                        self.status.set('Ön panelin 4 köşesini sırayla işaretleyin: sol üst → sağ üst → sağ alt → sol alt.')
                else:
                    self.status.set('Ön panelin 4 köşesini sırayla işaretleyin: sol üst → sağ üst → sağ alt → sol alt.')
            if len(self.quad)==4:
                self._curve_mode_name=None  # opening another photo must not reuse previous curve
                self.mode.set('adjust')
            self.path.set('Mockup fotoğrafı: '+self.source.name)
            self.confirm.set(False)
            self.window.update_idletasks()
            self.refresh()
            self.window.lift()
        except Exception as exc:messagebox.showerror('Görsel açma hatası',str(exc),parent=self.window)

    def reset_corners(self):
        self.undo_stack.append(('state', [list(p) for p in self.quad],self.mask.copy(),[list(p) for p in self.curve],self.mode.get()))
        self.mode.set('corners');self.quad=[];self.curve=[];self.curves={'top':[],'bottom':[]};self.curve_base=None;self.confirm.set(False)
        self.status.set('Yeni 4 köşe seç: sol üst → sağ üst → sağ alt → sol alt.');self.refresh()

    def show_marking_help(self):
        """Explain independent four-corner bounds versus original curved voids."""
        messagebox.showinfo(
            'PETEK maske işaretleme kılavuzu',
            '1. KIRMIZI 4 KÖŞE: Ön ahşap panelin dış dört köşesi; '
            'sıra: sol üst, sağ üst, sağ alt, sol alt. '
            'Siyah deliğin kavisine kırmızı köşe koyma.\n\n'
            '2. SARI ÜST EĞRİ: Siyah açıklığın alt sınırı. Noktaları istediğin sırayla seç; '
            'sol ve sağ uçları kırmızı yan kenara YAKIN yerleştir; son küçük boşluk '
            'kendiliğinden kenara bağlanır. Siyah açıklığın ALT sınırını takip et, '
            'üst rafın düz çizgisini değil. Shift+tıkla sık nokta ekler; '
            'Delete seçili noktayı siler. Ctrl+Z geri alır. UYGULA.\n\n'
            '3. MAVİ ALT EĞRİ: Ahşap ile alt açıklığın ayrıldığı sınır. '
            'Üst kavisten bağımsızdır. İkisini birbirine BAĞLAMA. '
            'Genellikle 3-6 iyi işaretlenmiş nokta yeterlidir.\n\n'
            '4. TURUNCU: Yalnızca gerçek baskı yapılacak ahşap. '
            'Deliklerin içi, koyu gölgeleri, üst boşluk ve parke turuncu olamaz.\n\n'
            '5. PANEL DIŞI TAŞMA: 4 köşeyi değiştirdiysen '
            '«Panel dışı maskeyi TEMİZLE» kullan; '
            'bu işlem geri alınabilir fakat eksik ahşap maskesi otomatik dolmaz.\n\n'
            '6. Önce GÖRSEL ÖNİZLEME, sonra DRAFT, en son insan ONAYI. '
            'Onaylı maske değiştirilecekse yeni UID (_r2) kullan.',
            parent=self.window,
        )

    def _clip_after_geometry_edit(self):
        """Keep draft pixels inside updated corners; allow undo of the edit.

        Newly widened quad still requires visual review and possibly another
        auto-mask pass. Existing on-disk profiles are never altered here.
        """
        if self.scene is None or self.mask is None or len(self.quad) != 4:
            return 0
        updated, removed = engine.clip_mask_to_panel(self.mask, self.scene, self.quad)
        if removed:
            self.undo_stack.append(self.mask.copy())
            self.undo_stack = self.undo_stack[-4:]
            self.mask = updated
            self.confirm.set(False)
        return removed

    def repair_small_gaps(self):
        """Opt-in repair of existing DRAFT; approved records stay unchanged."""
        try:
            if self.scene is None or self.mask is None or len(self.quad)!=4:
                raise engine.MaskError('Önce mockup fotoğrafı ve dört köşeyi seçin.')
            original=self.curve_base if self.curve_base is not None else self.mask
            repaired,stats=engine.repair_wood_pinholes(self.scene,original,self.quad)
            n=int(stats['fixed_pixels'])
            if not n:
                self.status.set('Güvenle kapatılabilecek küçük ahşap boşluğu bulunamadı. Delikler korunuyor.')
                return
            self._next_version()
            self.undo_stack.append(('brush',self.mask.copy(),
                    None if self.curve_base is None else self.curve_base.copy()))
            self.undo_stack=self.undo_stack[-16:]
            if self.curve_base is not None:
                self.curve_base=repaired
                self._preview_curve_clip()
            else:self.mask=repaired
            self.confirm.set(False)
            self.status.set(f'{stats["fixed_components"]} ahşap dokusu boşluğu, {n} kaynak piksel '
                            'taslak maskede düzeltildi. Ctrl+Z ile geri al; gerçek yarıkları kontrol et.')
            self.refresh()
        except Exception as exc:
            messagebox.showerror('Ahşap benek temizliği',str(exc),parent=self.window)

    def clean_outside_mask(self):
        """Explicit and reversible cleanup of old V3.2 masks after corner edits."""
        try:
            if self.scene is None or len(self.quad) != 4 or self.mask is None:
                raise engine.MaskError('Önce görseli aç ve dört köşeyi tamamla.')
            removed = self._clip_after_geometry_edit()
            if removed:
                self.status.set(f'{removed} taşan piksel maskeden temizlendi (GERİ AL kullanılabilir). '
                                'Köşeler ve kavisler doğru mu kontrol et; önizle, sonra taslak kaydet.')
            else:
                self.status.set('Maske dört köşe içinde; panel dışına taşan piksel yok. '
                                'Kavis/delikleri ayrıca gözle kontrol et.')
            self.refresh()
        except Exception as exc:
            messagebox.showerror('Maske düzeltme', str(exc), parent=self.window)

    def _point(self,event):
        if self.view is not None:
            sx,sy=self.view.source(event.x,event.y)
            x,y=int(round(sx)),int(round(sy))
        else:
            x=int(round(event.x/max(.01,self.scale)))
            y=int(round(event.y/max(.01,self.scale)))
        return (max(0,min(self.scene.shape[1]-1,x)),max(0,min(self.scene.shape[0]-1,y)))

    def _brush_size_changed(self,*_):
        if hasattr(self,'brush_readout'):
            self.brush_readout.configure(text=f'{int(self.brush.get())} px')
        self._draw_brush_cursor()

    def _cursor_motion(self,event):
        self._cursor_xy=(event.x,event.y)
        self._draw_brush_cursor()

    def _cursor_leave(self,_event=None):
        self._cursor_xy=None
        if hasattr(self,'canvas'):
            self.canvas.delete('brush_cursor')

    def _draw_brush_cursor(self):
        if not hasattr(self,'canvas'):
            return
        self.canvas.delete('brush_cursor')
        if self.scene is None or self._cursor_xy is None or self.mode.get() not in ('wood','protect'):
            return
        self._ensure_view()
        x,y=self._cursor_xy
        radius=brush_radius_screen(self.brush.get(),self.view.scale)
        color='#25e7fe' if self.mode.get()=='wood' else '#f83f73'
        self.canvas.create_oval(x-radius,y-radius,x+radius,y+radius,
                                outline='#111111',width=4,tags='brush_cursor')
        self.canvas.create_oval(x-radius,y-radius,x+radius,y+radius,
                                outline=color,width=2,tags='brush_cursor')
        self.canvas.create_line(x-5,y,x+5,y,fill=color,tags='brush_cursor')
        self.canvas.create_line(x,y-5,x,y+5,fill=color,tags='brush_cursor')
        self.canvas.create_text(x+radius+8,y-radius-6,anchor='sw',
                                text=f'{int(self.brush.get())} px',fill=color,
                                font=('Segoe UI',10,'bold'),tags='brush_cursor')

    def _paint(self,event,first=False):
        if self.scene is None:return
        x,y=self._point(event)
        if len(self.quad)!=4:
            raise engine.MaskError('Fırça için önce dört köşeyi tamamla.')
        bound=engine.polygon_mask(self.scene.shape[:2],engine.validated_quad(self.quad,self.scene.shape))
        if bound[y,x]==0:
            self.status.set('Fırça dörtgenin DIŞINDA: boyama yapılmadı.')
            return
        if first:
            self._next_version()
            self.undo_stack.append(('brush',self.mask.copy(),
                None if self.curve_base is None else self.curve_base.copy()))
            self.undo_stack=self.undo_stack[-16:]
        base=self.mask if self.curve_base is None else self.curve_base
        previous=None if first else self._brush_last_point
        apply_stroke(base,bound,(x,y),int(self.brush.get()),
                     255 if self.mode.get()=='wood' else 0,previous=previous)
        self._brush_last_point=(x,y)
        self._preview_curve_clip()
        self.confirm.set(False)
        self.refresh()

    def click(self,event):
        if self.scene is None:return
        self.canvas.focus_set()
        if getattr(self,'_space_down',False):self._start_pan(event);return
        if self.mode.get()=='adjust' and len(self.quad)==4:
            x,y=self._point(event)
            self._qdrag=begin(self.quad,x,y,(self.scene.shape[1],self.scene.shape[0]),self.scale)
            self._qchanged=False
            if self._qdrag:self._before_drag=([list(p) for p in self.quad],self.mask.copy())
            return
        if self.mode.get() in ('top','bottom'):
            x,y=self._point(event)
            sx,sy=(self.view.screen(x,y) if self.view is not None else (x*self.scale,y*self.scale))
            # Within 7 px: drag existing handle; SHIFT+click always adds a new
            # point, even in a narrow curve section (previous radius was 13 px).
            near=[(i,(self.view.screen(*pt) if self.view is not None else
                       (pt[0]*self.scale,pt[1]*self.scale))) for i,pt in enumerate(self.curve)]
            candidates=[(i,(px-event.x)**2+(py-event.y)**2) for i,(px,py) in near]
            close=min(candidates,key=lambda p:p[1]) if candidates else None
            self._remember_curve(points_only=True)
            force_add=bool(getattr(event,'state',0)&0x0001)
            if close is not None and close[1]<=7**2 and not force_add:
                self._dragged_curve_index=close[0]
                self._selected_curve_index=close[0]
                self.status.set('Kavis noktası seçildi; sürükleyerek düzelt, Ctrl+Z geri al.')
            else:
                same_x=next((i for i,pt in enumerate(self.curve) if int(round(pt[0]))==x),None)
                if same_x is not None:
                    # A curve y(x) can have just one Y for a given source X.
                    self.curve[same_x]=[x,y]
                    self._dragged_curve_index=same_x
                    self._selected_curve_index=same_x
                    self.status.set('Aynı X pikselindeki nokta güncellendi; Ctrl+Z geri alır.')
                else:
                    self.curve.append([x,y]);self._dragged_curve_index=len(self.curve)-1
                    self._selected_curve_index=len(self.curve)-1
                    self.status.set(('ÜST' if self.mode.get()=='top' else 'ALT')+
                        ' kavisi: '+str(len(self.curve))+' nokta. Noktaları istediğin sırayla koy ve sürükle.')
            self.curves[self.mode.get()]=[list(pt) for pt in self.curve]
            self.confirm.set(False)
            self.refresh()
        elif self.mode.get()=='corners':
            if len(self.quad)==4:self.quad=[]
            self.quad.append(list(self._point(event)))
            if len(self.quad) == 4:
                try:
                    removed = self._clip_after_geometry_edit()
                except engine.MaskError as exc:
                    self.status.set('Dört köşe kontrolü: ' + str(exc))
                    self.confirm.set(False)
                    self.refresh()
                    return
                self.mode.set('adjust')
                if removed:
                    self.status.set(f'4 köşe güncellendi; eski maskenin {removed} taşan pikseli '
                                    'silindi (geri alınabilir). Eğrileri tekrar kontrol et.')
                else:
                    self.status.set('Dört köşe tamamlandı. Maske/delik/kavisleri kontrol et.')
            else:
                self.status.set('Köşe: '+str(len(self.quad))+'/4')
            self.confirm.set(False)
            self.refresh()
        else:
            self._paint_active=True
            try:self._paint(event,True)
            except engine.MaskError as exc:self.status.set(str(exc));self._paint_active=False

    def drag(self,event):
        if self._dragged_curve_index is not None and self.mode.get() in ('top','bottom'):
            nx,ny=self._point(event)
            idx=self._dragged_curve_index
            if any(j!=idx and int(round(pt[0]))==nx for j,pt in enumerate(self.curve)):
                # A manual Y(X) curve cannot have two points at the SAME source X;
                # keep existing point, prompt to zoom and move horizontally.
                self.status.set('Bu X konumunda zaten bir kavis noktası var. Yakınlaştırıp sağa/sola kaydır.')
                return
            self.curve[idx]=[nx,ny]
            self.curves[self.mode.get()]=[list(pt) for pt in self.curve]
            self.confirm.set(False);self.refresh()
            return
        if self._qdrag is not None and self._before_drag is not None:
            x,y=self._point(event)
            candidate=self._qdrag.at(x,y)
            try:engine.validated_quad(candidate,self.scene.shape)
            except engine.MaskError:return
            if not np.allclose(candidate,self.quad):
                self.quad=candidate.tolist();self._qchanged=True;self.confirm.set(False);self.refresh()
            return
        if self._paint_active and self.mode.get() in ('wood','protect'):
            try:self._paint(event)
            except engine.MaskError:self._paint_active=False

    def _end_paint(self,_event=None):
        self._pan_anchor=None
        self._paint_active=False
        self._brush_last_point=None
        if self._dragged_curve_index is not None:
            self._dragged_curve_index=None
            if self.curve_base is not None:
                try:self._preview_curve_clip()
                except engine.MaskError:pass
            self.refresh()
        self._release_geometry()

    def finish_curve(self):
        try:
            mode=self.mode.get()
            if self.scene is None or len(self.quad)!=4 or mode not in ('top','bottom'):
                raise engine.MaskError('Önce üst veya alt kavis modunu seç ve dört köşeyi tamamla.')
            # Curves are independent, manually authored; no mirrored guesses.
            curve_math.normalized(self.curve)
            next_curves={k:[list(pt) for pt in v] for k,v in self.curves.items()}
            next_curves[mode]=[list(pt) for pt in self.curve]
            if self.curve_base is None:
                base=self.mask.copy()
            else:base=self.curve_base
            next_mask=curve_math.apply(base,self.quad,
                next_curves['top'],next_curves['bottom'],require_ends=True)
            engine.mask_check(next_mask,self.scene,self.quad)
            self._remember_curve()
            self._next_version()
            self.curve_base=base.copy()
            self.curves=next_curves
            self.mask=next_mask
            self.confirm.set(False)
            self.status.set(('Üst' if mode=='top' else 'Alt')+
               ' kavis uygulandı. Uçlar kırmızı yan kenarlara bağlandı; çizgi noktalarına tam sadık. '
               'Üst ve alt kavis bağımsızdır.')
            self.mode.set('protect')
            self.refresh()
        except Exception as exc:messagebox.showerror('Kavis uygulanamadı',str(exc),parent=self.window)

    def delete_curve_point(self, event=None):
        if event is not None and isinstance(event.widget,(tk.Entry,ttk.Entry,tk.Text,ttk.Combobox)):
            return None
        if self.mode.get() not in ('top','bottom') or self._selected_curve_index is None:
            return None
        idx=self._selected_curve_index
        if not 0<=idx<len(self.curve):return None
        self._remember_curve(points_only=True)
        del self.curve[idx]
        self.curves[self.mode.get()]=[list(pt) for pt in self.curve]
        self._selected_curve_index=None
        self._dragged_curve_index=None
        self._preview_curve_clip()
        self.confirm.set(False)
        self.status.set('Seçili kavis noktası silindi. Ctrl+Z geri alır.')
        self.refresh()
        return 'break'

    def undo(self):
        if self.undo_stack:
            saved=self.undo_stack.pop()
            if isinstance(saved,tuple):
                if saved[0]=='geometry':
                    self.quad=saved[1];self.mask=saved[2];self.curves={'top':[],'bottom':[]};self.curve_base=None;self.mode.set('adjust')
                elif saved[0]=='curve_points':
                    _,mode,points=saved
                    self.curves=points
                    self._curve_mode_name=None
                    self.mode.set(mode)
                    self.curve=[list(p) for p in self.curves.get(mode,[])]
                    self._selected_curve_index=None
                    if self.curve_base is not None:self._preview_curve_clip()
                elif saved[0]=='curve_state':
                    _,mode,copies,mask,base=saved
                    self.curves=copies;self.mask=mask;self.curve_base=base
                    self._curve_mode_name=None
                    self.mode.set(mode)
                    self.curve=[list(p) for p in self.curves.get(mode,[])]
                elif saved[0]=='brush':
                    self.mask=saved[1];self.curve_base=saved[2]
                elif saved[0]=='point':
                    self.curve=[list(p) for p in saved[1]];self.mode.set(saved[2])
                elif saved[0]=='curve':
                    self.mask=saved[1];self.curve=[list(p) for p in saved[2]];self.mode.set(saved[3])
                elif saved[0]=='state':
                    self.quad=saved[1];self.mask=saved[2];self.curve=saved[3];self.mode.set(saved[4])
            else:self.mask=saved
            self.confirm.set(False);self.refresh()

    def auto(self):
        try:
            if self.scene is None or len(self.quad)!=4:
                raise engine.MaskError('Önce panelin dört köşesini işaretleyin.')
            m,stats=engine.auto_mask_candidate(self.scene,self.quad)
            self.undo_stack.append(self.mask.copy())
            self.undo_stack=self.undo_stack[-4:]
            self._next_version()
            self.mode.set('adjust')
            self.curves={'top':[],'bottom':[]};self.curve=[];self.curve_base=None
            self.mask=m;self.confirm.set(False)
            self.status.set(f'TASLAK: ahşap kapsama %{100*stats["area_ratio"]:.1f}. '
                            f'{stats.get("repaired_wood_pinhole_pixels",0)} ahşap pikseli temizlendi. '
                            'Delik, üst-alt kavis ve kenarları insan gözüyle kontrol edin!')
            self.refresh()
        except Exception as exc:messagebox.showerror('Maske analizi',str(exc),parent=self.window)

    def _canvas_resized(self, _event):
        """Debounced redraw ensures full photo remains visible after resizing."""
        if self.scene is None:
            return
        if self._resize_after is not None:
            self.window.after_cancel(self._resize_after)
        self._resize_after = self.window.after(90, self._refresh_after_resize)

    def _refresh_after_resize(self):
        self._resize_after = None
        if self.window.winfo_exists() and self.scene is not None:
            self.refresh()

    def _canvas_dims(self):
        return max(180,self.canvas.winfo_width()),max(180,self.canvas.winfo_height())

    def _fit_view(self,_event=None):
        if self.scene is None:return 'break'
        cw,ch=self._canvas_dims()
        self.view=Viewport(self.scene.shape[1],self.scene.shape[0],cw,ch)
        self.refresh()
        return 'break'

    def _actual_size(self):
        if self.scene is None:return
        self._ensure_view()
        cx,cy=self.view.canvas_width/2,self.view.canvas_height/2
        self.view.zoom_at(1.0/max(.01,self.view.scale),cx,cy)
        self.refresh()

    def _button_zoom(self,factor):
        if self.scene is None:return
        self._ensure_view()
        self.view.zoom_at(factor,self.view.canvas_width/2,self.view.canvas_height/2)
        self.refresh()

    def _mouse_zoom(self,event):
        if self.scene is None:return 'break'
        self._ensure_view()
        sign=1 if getattr(event,'num',None)==4 else -1 if getattr(event,'num',None)==5 else (1 if getattr(event,'delta',0)>0 else -1)
        self.view.zoom_at(1.20 if sign>0 else 1/1.20,event.x,event.y)
        self.refresh()
        return 'break'

    def _space_press(self,event):
        if isinstance(event.widget,(tk.Entry,ttk.Entry,tk.Text,ttk.Combobox)):return
        self._space_down=True

    def _space_release(self,_event):self._space_down=False

    def _keyboard_undo(self,event):
        if isinstance(event.widget,(tk.Entry,ttk.Entry,tk.Text,ttk.Combobox)):
            return None  # native text entry undo semantics
        self.undo()
        return 'break'

    def _start_pan(self,event):
        self._ensure_view()
        self._pan_anchor=(event.x,event.y)

    def _drag_pan(self,event):
        if self._pan_anchor is None:return
        self._ensure_view()
        x,y=self._pan_anchor
        self.view.pan(event.x-x,event.y-y)
        self._pan_anchor=(event.x,event.y)
        self.refresh()

    def _ensure_view(self):
        if self.scene is None:return
        cw,ch=self._canvas_dims()
        if self.view is None:
            self.view=Viewport(self.scene.shape[1],self.scene.shape[0],cw,ch)
        elif self.view.canvas_width!=cw or self.view.canvas_height!=ch:
            self.view.resize(cw,ch)
        self.scale=self.view.scale

    def refresh(self):
        if self.scene is None:return
        self._ensure_view()
        v=self.view;cw,ch=v.canvas_width,v.canvas_height
        self.scale=v.scale;self.draw_dims=(cw,ch)
        # Transform the viewport only; the source scene/mask is never rescaled
        # on disk, and annotations remain in original pixel coordinates.
        mat=np.float32([[v.scale,0,v.offset_x],[0,v.scale,v.offset_y]])
        interpolation=cv2.INTER_AREA if v.scale<1 else cv2.INTER_LINEAR
        rgb=cv2.warpAffine(self.scene,mat,(cw,ch),flags=interpolation,
                           borderMode=cv2.BORDER_CONSTANT,borderValue=(32,35,40))
        mini=cv2.warpAffine(self.mask,mat,(cw,ch),flags=cv2.INTER_LINEAR,
                            borderMode=cv2.BORDER_CONSTANT,borderValue=0)
        alpha=mini.astype(np.float32)/255*.47
        base=cv2.cvtColor(rgb,cv2.COLOR_BGR2RGB).astype(np.float32)
        out=base*(1-alpha[:,:,None])+np.array([252,140,37],np.float32)*alpha[:,:,None]
        im=Image.fromarray(np.uint8(np.clip(out,0,255)))
        self.photo=ImageTk.PhotoImage(im,master=self.window)
        self.canvas.delete('all');self.canvas.create_image(0,0,anchor='nw',image=self.photo)
        for i,(x,y) in enumerate(self.quad):
            cx,cy=v.screen(x,y)
            self.canvas.create_oval(cx-5,cy-5,cx+5,cy+5,fill='#ff2244',outline='white')
            self.canvas.create_text(cx+14,cy+12,text=str(i+1),fill='#ff2244',font=('Segoe UI',11,'bold'))
        if len(self.quad)==4:
            points=[coord for p in self.quad for coord in v.screen(*p)]
            self.canvas.create_polygon(points,outline='#ff3355',fill='',width=2)
            for i,(x,y) in enumerate(self.quad):
                x,y=v.screen(x,y)
                self.canvas.create_rectangle(x-6,y-6,x+6,y+6,fill='#f25',outline='white')
                other=self.quad[(i+1)%4]
                mx,my=v.screen((self.quad[i][0]+other[0])/2,(self.quad[i][1]+other[1])/2)
                self.canvas.create_oval(mx-5,my-5,mx+5,my+5,fill='#008ddd',outline='white')
        for kind,pts in self.curves.items():
            if not pts:continue
            clr='#ffff00' if kind=='top' else '#00ffff'
            try:
                xs,ys=curve_math.interpolate(pts,self.quad if len(self.quad)==4 else None)
                if len(xs)>1:
                    coords=[z for i in range(0,len(xs),max(1,len(xs)//250))
                            for z in v.screen(float(xs[i]),float(ys[i]))]
                    self.canvas.create_line(coords,fill=clr,width=2,smooth=False)
            except engine.MaskError:pass  # 0-2 provisional user points
            for x,y in pts:
                px,py=v.screen(x,y)
                selected=(kind==self.mode.get() and self._selected_curve_index is not None
                          and pts[self._selected_curve_index]==[x,y]) if (self._selected_curve_index is not None and self._selected_curve_index<len(pts)) else False
                radius=7 if selected else 4
                self.canvas.create_oval(px-radius,py-radius,px+radius,py+radius,
                                       fill=clr,outline='black',width=2 if selected else 1)


        self._draw_brush_cursor()

    def _display_render(self, artwork):
        if self.scene is None or len(self.quad)!=4:
            raise engine.MaskError('Önce 4 köşe ve maske gerekli.')
        leak = engine.count_outside_panel(self.mask, self.scene, self.quad)
        if leak:
            raise engine.MaskError(f'Maske panel dışına taşıyor: {leak} piksel. '
                                   'Önce «Panel dışı maskeyi TEMİZLE» düğmesine bas, '
                                   'sonra kavisleri kontrol et.')
        rendered, qa = engine.render(self.scene, artwork, self.quad, self.mask,
                                      float(self.aspect.get()), marketplace=True,
                                      placement='cover',lighting=_lighting_code(self.lighting.get()))
        win = tk.Toplevel(self.window)
        win.title('PETEK — Tasarım Önizlemesi (kaydedilmedi)')
        scale = min(1, 640 / rendered.shape[0], 560 / rendered.shape[1])
        thumb = cv2.resize(rendered,
                           (max(1, int(rendered.shape[1]*scale)),
                            max(1, int(rendered.shape[0]*scale))),
                           interpolation=cv2.INTER_AREA)
        preview = ImageTk.PhotoImage(
            Image.fromarray(cv2.cvtColor(thumb, cv2.COLOR_BGR2RGB)), master=win)
        label = ttk.Label(win, image=preview)
        label.image = preview
        label.pack(padx=12, pady=12)
        ttk.Label(win, text='TAM DOLDUR: Tasarım kenarlardan kırpılabilir. '
                  'Üst/alt kavis, dikey yarıklar, gölge ve zemin orijinal kalmalı.',
                  wraplength=540).pack(padx=12, pady=8)

    def preview_edge_variants(self):
        """Local A/B: original mask is never edited, saved or approved here."""
        try:
            if self.scene is None or len(self.quad)!=4:
                raise engine.MaskError('Önce PETEK mockup fotoğrafı, dört köşe ve baskı maskesi seç.')
            path=filedialog.askopenfilename(parent=self.window,
                title='Karşılaştırma için bir BASKI TASARIMI seç (mockup değil)',
                filetypes=[('Baskı tasarımı','*.jpg *.jpeg *.png *.webp')])
            if not path:return
            art=engine.read_bgr(Path(path))
            choices=[('1 · Çerçevesiz',0,0.),
                     ('2 · Mikro taşma %1,2',0,.012),
                     ('3 · Beyaz sınır ~5 mm',5,0.),
                     ('4 · Beyaz sınır ~10 mm',10,0.)]
            panels=[]
            for label,frame,overscan in choices:
                result,_=engine.render(self.scene,art,self.quad,self.mask,float(self.aspect.get()),
                    lighting=_lighting_code(self.lighting.get()),marketplace=True,
                    frame_mm=frame,overscan=overscan)
                thumb=cv2.resize(result,(210,280),interpolation=cv2.INTER_AREA)
                panels.append((label,ImageTk.PhotoImage(
                    Image.fromarray(cv2.cvtColor(thumb,cv2.COLOR_BGR2RGB)),master=self.window)))
            popup=tk.Toplevel(self.window)
            popup.title('PETEK · 4 Kenar Seçeneği (KAYDEDİLMEZ)')
            popup.transient(self.window)
            host=ttk.Frame(popup,padding=8);host.pack()
            for i,(name,photo) in enumerate(panels):
                c=ttk.Frame(host);c.grid(row=i//2,column=i%2,padx=8,pady=5)
                ttk.Label(c,text=name).pack()
                label=ttk.Label(c,image=photo);label.image=photo;label.pack()
            ttk.Label(popup,text='ÖNİZLEME: ~mm değerleri 96 cm varsayımsal ön yüz içindir. '
                      'Yanlış maske, çerçeve/taşmayla düzelmez. Delik ve zemin korunur.',
                      wraplength=510).pack(padx=12,pady=(5,10))
            popup.photos=[photo for _,photo in panels]
            popup.lift()
        except Exception as exc:
            messagebox.showerror('Kenar karşılaştırması başarısız',str(exc),parent=self.window)

    def verify_cutout_overlay(self):
        try:
            if self.scene is None or len(self.quad)!=4 or self.mask is None:
                raise engine.MaskError('Önce PETEK fotoğrafı, dört köşe ve baskı maskesini hazırlayın.')
            from .cutout_paste import extract_cutout_overlay_rgba
            rgba, meta = extract_cutout_overlay_rgba(self.scene, self.mask, self.quad)
            self.status.set(
                f"Kes-Yapıştır doğrulandı: {meta['detected_vertical_slots']} dikey yarık, "
                f"{meta['detected_curved_openings']} kavisli açıklık, "
                f"{meta['cutout_panel_pixels']} korunan piksel."
            )
        except Exception as exc:
            messagebox.showerror('Kes-Yapıştır Doğrulama', str(exc), parent=self.window)

    def preview_render(self):
        try:
            # Artificial preview stays local, and is never a commercial asset.
            artwork = np.full((550, 700, 3), (68, 105, 192), np.uint8)
            for row in range(80, 500, 65):
                cv2.line(artwork, (25, row), (675, row), (227, 235, 245), 2, cv2.LINE_AA)
            cv2.putText(artwork, 'PETEK TEST', (48, 275),
                        cv2.FONT_HERSHEY_DUPLEX, 1.65, (245, 245, 245), 4, cv2.LINE_AA)
            self._display_render(artwork)
        except Exception as exc:
            messagebox.showerror('Önizleme üretilemedi', str(exc), parent=self.window)

    def preview_real_design(self):
        """Preview user's art, not mockup source, without writing or approving."""
        try:
            path = filedialog.askopenfilename(
                parent=self.window, title='PETEK Üzerine Basılacak Tasarımı Seç (mockup değil)',
                filetypes=[('Tasarım PNG/JPG', '*.jpg *.jpeg *.png *.webp')])
            if not path: return
            art = engine.read_bgr(Path(path))
            self._display_render(art)
        except Exception as exc:
            messagebox.showerror('Gerçek tasarım önizlemesi başarısız', str(exc),
                                 parent=self.window)

    def save_draft(self):
        try:
            if self.source is None:raise engine.MaskError('Önce şablon görseli seçin.')
            removed=engine.count_outside_panel(self.mask,self.scene,self.quad)
            if removed:
                raise engine.MaskError(f'{removed} piksel panel dışında. '
                                       'Önce «Panel dışı maskeyi TEMİZLE» seç.')
            self._next_version()
            p=self.registry.save(self.uid.get(),self.source,self.quad,self.mask,float(self.aspect.get()),
                curve_points=self.curves,base_mask=self.curve_base)
            self.status.set('DRAFT kaydedildi. Üretime açılması için insan onayı gerekiyor. '+p['mask_sha'][:12])
            self.confirm.set(False)
            if self.on_saved:self.on_saved()
        except Exception as exc:messagebox.showerror('Maske kaydedilemedi',str(exc),parent=self.window)

    def approve(self):
        try:
            if not self.confirm.get():raise engine.MaskError('Delikler, kavisler ve zemin incelendi kutusunu işaretleyin.')
            p=self.registry.get(self.uid.get())[0]
            if self.source is None or engine.digest(self.source)!=p['source_sha']:
                raise engine.MaskError('Maskenin kaynak görsel SHA değeri tutmuyor.')
            if engine.mask_hash(self.mask)!=p['mask_sha']:
                raise engine.MaskError('Son fırça değişiklikleri DRAFT olarak kaydedilmeli.')
            approved=self.registry.approve(self.uid.get(),self.reviewer.get(),
                      'I_VISUALLY_CHECKED_VENTS_ARCHES_FLOOR')
            self.status.set('ONAYLANDI — Kaynak ve maske SHA doğrulandı: '+approved['mask_sha'][:14])
            if self.on_saved:self.on_saved()
            messagebox.showinfo('PETEK onayı','Şablonun orijinal delikleri ve kavisleri korunacak şekilde onaylandı.',parent=self.window)
        except Exception as exc:messagebox.showerror('Onay başarısız',str(exc),parent=self.window)


class BatchWindow:
    def __init__(self,parent,registry=None):
        self.registry=registry or Registry()
        self.window=tk.Toplevel(parent);self.window.title('PETEK — Seri Görsel Üretimi')
        self.window.geometry('760x690');self.window.transient(parent)
        area=ttk.Frame(self.window,padding=20);area.pack(fill='both',expand=True)
        ttk.Label(area,text='PETEK — Mockuplara Toplu Tasarım Uygula',font=('Segoe UI',16,'bold')).pack(anchor='w',pady=(0,10))
        ttk.Label(area,text='Yalnızca insan onaylı maskeler. Bulut/yükleme kapalı. Kaynak dosyalar değişmez.').pack(anchor='w')
        ttk.Label(area,text='1. ÜRETİME HAZIR PETEK MOCKUP FOTOĞRAFLARI:').pack(anchor='w',pady=(13,4))
        ttk.Label(area,text='Bunlar baskısız oda/dolap fotoğraflarıdır. Desenleri bir sonraki adımda seç.',
                  foreground=MUTED,wraplength=670).pack(anchor='w')
        self.listbox=tk.Listbox(area,selectmode='extended',height=8,exportselection=False,
                                bg=PANEL,fg=FG,selectbackground='#2563eb',selectforeground='#ffffff')
        self.listbox.pack(fill='x')
        self.mapping=[];self.reload()
        ttk.Button(area,text='Yeni Onaylanan PETEK Fotoğraflarını Listele',command=self.reload).pack(anchor='w',pady=5)
        ttk.Label(area,text='İnsan onayından sonra yenile; tüm onaylılar varsayılan seçilir, istersen seçimi değiştir.',
                  foreground=MUTED,wraplength=670).pack(anchor='w')
        row=ttk.Frame(area);row.pack(fill='x',pady=8)
        self.design_folder=tk.StringVar()
        ttk.Entry(row,textvariable=self.design_folder).pack(side='left',fill='x',expand=True)
        ttk.Button(row,text='2. DESEN / BASKI TASARIMLARI KLASÖRÜ',command=self.browse).pack(side='left',padx=5)
        ttk.Label(area,text='Mockup klasörü DEĞİL; dolabın üzerine basılacak desenleri içeren klasör.',
                  foreground=MUTED,wraplength=670).pack(anchor='w')
        t=ttk.Frame(area);t.pack(fill='x',pady=6)
        ttk.Label(t,text='Mağaza grubu:').pack(side='left')
        self.group=tk.StringVar(value='LOCAL');ttk.Entry(t,textvariable=self.group,width=15).pack(side='left',padx=5)
        ttk.Label(t,text='Bu turda en fazla çıktı:').pack(side='left',padx=(20,4))
        self.limit=tk.StringVar(value='200');ttk.Entry(t,textvariable=self.limit,width=9).pack(side='left')
        fit_row=ttk.Frame(area);fit_row.pack(fill='x',pady=(2,4))
        ttk.Label(fit_row,text='Tasarım yerleşimi:').pack(side='left')
        self.placement=tk.StringVar(value='Tam Doldur (kırpılabilir)')
        ttk.Combobox(fit_row,textvariable=self.placement,state='readonly',width=25,
                     values=('Tam Doldur (kırpılabilir)','Tam Göster (bant olabilir)')).pack(side='left',padx=8)
        # Açıklama seçim menüsünde mevcut; yinelenen açıklama ekranı kalabalıklaştırmasın.
        self.lighting=tk.StringVar(value=LIGHT_LABELS[0])
        ttk.Label(area,text='Fotoğraf ışığını baskıya uydur (Doğal önerilen)').pack(anchor='w')
        ttk.Combobox(area,textvariable=self.lighting,state='readonly',values=LIGHT_LABELS,width=29).pack(anchor='w',pady=5)
        actions=ttk.Frame(area);actions.pack(fill='x',pady=10)
        self.start_button=ttk.Button(actions,text='▶ Seri Görsel Üretimini Başlat',command=self.start)
        self.start_button.pack(side='left',padx=3)
        ttk.Button(actions,text='■ Güvenli durdur',command=self.stop).pack(side='left',padx=3)
        ttk.Button(actions,text='Çıktı klasörü',command=self.open_results).pack(side='left',padx=3)
        ttk.Label(area,text='Kullanım: Onaylı fotoğraf(lar)ı seç → desen klasörünü belirle → başlat. '
                  'Güvenli durdur, tamamlanan çıktılara dokunmaz.',
                  foreground=MUTED,wraplength=670).pack(anchor='w')
        ttk.Label(area,text='3. BAŞLAT → Çıktıları kontrol et. Eksik/hatalı sonuç için logu incele.',
                  foreground=MUTED,wraplength=670).pack(anchor='w')
        self.progress=tk.StringVar(value='Adım 1: Onaylı mockuplar. Adım 2: Desen klasörü. Adım 3: Başlat.')
        ttk.Label(area,textvariable=self.progress,wraplength=650).pack(anchor='w',pady=5)
        self.log=scrolledtext.ScrolledText(area,height=16,state='disabled',bg=PANEL,fg=FG,insertbackground=FG);self.log.pack(fill='both',expand=True)
        self.messages=queue.Queue();self.worker=None;self.runner=None
        self.window.after(200,self.poll)
        bind_help(self.window)
        self.window.protocol('WM_DELETE_WINDOW',self.safe_close)

    def safe_close(self):
        if self.worker and self.worker.is_alive():
            messagebox.showinfo('Üretim devam ediyor',
                'Önce güvenli durdurmaya basın; aktif işlem bitince pencereyi kapatın.',parent=self.window)
            return
        self.window.destroy()

    def reload(self):
        self.listbox.delete(0,'end');self.mapping=[]
        for row in self.registry.list():
            if row['status']=='APPROVED':
                self.mapping.append(row['uid']);self.listbox.insert('end',row['uid'])
        if self.mapping:
            self.listbox.selection_set(0,'end');self.listbox.activate(0)

    def browse(self):
        path=filedialog.askdirectory(parent=self.window,title='Baskı Tasarımları Klasörünü Seç — Mockup klasörü değil')
        if path:self.design_folder.set(path)

    def _log(self,line):self.messages.put(('log',str(line)))
    def start(self):
        if self.worker and self.worker.is_alive():return
        selected=[self.mapping[int(i)] for i in self.listbox.curselection()]
        if not selected:
            messagebox.showinfo('Şablon seç', 'Üstteki listeden en az bir onaylı PETEK şablonuna tıkla.',parent=self.window);return
        if not Path(self.design_folder.get()).is_dir():
            messagebox.showinfo('2. Baskı Tasarımlarının Klasörünü Seç','PETEK üzerine basılacak resimlerin olduğu ayrı klasörü seç.',parent=self.window);return
        self.runner=Batch(self.registry)
        self.start_button.configure(state='disabled')
        def work():
            try:
                result=self.runner.run(self.design_folder.get(),selected,self.group.get(),self._log,
                                           int(self.limit.get()),placement=('cover' if self.placement.get().startswith('Tam Doldur') else 'contain'),lighting=_lighting_code(self.lighting.get()))
                self.messages.put(('done',result))
            except Exception as exc:self.messages.put(('fail',str(exc)))
        self.worker=threading.Thread(target=work,daemon=False);self.worker.start()
        self.progress.set('Yerel seri üretim çalışıyor...')

    def stop(self):
        if self.runner:self.runner.cancel.set();self.progress.set('Durdurma istendi...')

    def open_results(self):
        path=self.registry.output
        if path.is_dir():
            if os.name=='nt':os.startfile(str(path))
            else:self._log(str(path))

    def poll(self):
        try:
            while True:
                kind,value=self.messages.get_nowait()
                if kind=='log':
                    self.log.configure(state='normal');self.log.insert('end',value+'\n');self.log.see('end');self.log.configure(state='disabled')
                elif kind=='done':
                    self.progress.set(f'{value["status"]} — Üretilen:{value["rendered"]}, Tekrar:{value["reused"]}, Atlanan:{value["rejected"]}. Excel: {value["xlsx"]}')
                    self.start_button.configure(state='normal')
                elif kind=='fail':
                    self.progress.set('DURDU — '+value)
                    self.start_button.configure(state='normal')
        except queue.Empty:pass
        if self.window.winfo_exists():self.window.after(200,self.poll)


def open_mask_editor(parent,registry=None,after_save=None,runtime_root=None):
    return MaskEditor(parent,registry,on_saved=after_save,runtime_root=runtime_root)
def open_batch_window(parent,registry=None):return BatchWindow(parent,registry)
