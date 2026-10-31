"""Isolated, non-executable visual-layout preferences for the Windows dashboard.

All preferences are stored outside production data, PETEK mask registry and
approved-template SQLite. Never serialize callbacks or evaluate user content.
"""
from __future__ import annotations
from copy import deepcopy
import json
import os
from pathlib import Path
import re
import tempfile
import tkinter as tk
from tkinter import ttk, colorchooser, simpledialog, messagebox

DASH_IDS = ('review','production','designs','tools','petek','stage','reports','tests','notes','search')
PROD_IDS = ('templates','designs','quality','actions')
CARD_NAMES = {
 'review':'Şablon İnceleme','production':'Seri Üretim','designs':'Ham Tasarımlar',
 'tools':'Profesyonel Araçlar','petek':'PETEK İşlemleri','stage':'Yeni Şablon Ekle',
 'reports':'Raporlar ve Kurtarma','tests':'Yapmam Gereken Testler',
 'notes':'Notlarım ve Görevlerim','search':'Özellik / Araç Ara',
 'templates':'Şablonlar ve Filtreleme','quality':'4K / PETEK / Efekt / Excel',
 'actions':'Üretimi Başlat / Duraklat / Durdur'}


def contrast_ratio(a,b):
    """WCAG luminance ratio for hex RGB; keep theme text readable."""
    def luminance(color):
        values=[int(color[i:i+2],16)/255 for i in (1,3,5)]
        linear=[(c/12.92 if c<=0.04045 else ((c+0.055)/1.055)**2.4) for c in values]
        return .2126*linear[0]+.7152*linear[1]+.0722*linear[2]
    first,second=sorted((luminance(a),luminance(b)),reverse=True)
    return (first+0.05)/(second+0.05)


def settings_path():
    folder=Path(os.environ.get('LOCALAPPDATA') or Path.home()/'.gorsel_mockup')
    return folder/'GorselMockup'/'UI_V498'/'layout.json'


def initial():
    return {'schema':1,
        'dashboard':{'tabs':{'Ana Sayfa':list(DASH_IDS)},'accent':'#7A4DFA','effect':'hafif','colors':{}},
        'production':{'tabs':{'Tümü':list(PROD_IDS)},'accent':'#7A4DFA','effect':'hafif','colors':{}}}


def normalize(raw):
    default=initial()
    if not isinstance(raw,dict) or raw.get('schema')!=1:
        return default
    for mode,ids,home in [('dashboard',DASH_IDS,'Ana Sayfa'),('production',PROD_IDS,'Tümü')]:
        src=raw.get(mode,{})
        if not isinstance(src,dict):continue
        color=src.get('accent','#7A4DFA')
        if isinstance(color,str) and re.fullmatch('#[0-9a-fA-F]{6}',color):
            default[mode]['accent']=color.lower()
        if src.get('effect') in ('kapalı','hafif','belirgin'):
            default[mode]['effect']=src['effect']
        colors=src.get('colors',{})
        if isinstance(colors,dict):
            valid={key:value.lower() for key,value in colors.items()
                if key in ('background','panel','button','title','border') and isinstance(value,str)
                and re.fullmatch('#[0-9a-fA-F]{6}',value)}
            # Reject theme edits that would hide buttons or titles on a dark UI.
            for color_key in ('background','panel','button'):
                if color_key in valid and contrast_ratio(valid[color_key],'#f1f0ff')<4.5:
                    valid.pop(color_key)
            if 'title' in valid and contrast_ratio(valid['title'],valid.get('panel','#343c46'))<4.5:
                valid.pop('title')
            default[mode]['colors']=valid
        tabs=src.get('tabs')
        if not isinstance(tabs,dict):continue
        clean={home:[]};used=set()
        # System home must always exist. Never lose a panel ID.
        for tab,items in tabs.items():
            if not isinstance(tab,str) or not 1<=len(tab)<=40 or tab.strip()!=tab:
                continue
            if tab not in clean and len(clean)>=11:continue
            if not isinstance(items,list):continue
            clean.setdefault(tab,[])
            for card in items:
                if card in ids and (mode=='production' or card not in used):
                    clean[tab].append(card);used.add(card)
        for card in ids:
            if card not in used:clean[home].append(card)
        if mode=='production':
            # Critical controls always available on Tümü (unconditional safe route)
            clean['Tümü']=list(ids)
            for tab in list(clean):
                if tab!='Tümü':clean[tab]=list(dict.fromkeys(x for x in clean[tab] if x in ids))
        default[mode]['tabs']=clean
    return default


def load():
    try:return normalize(json.loads(settings_path().read_text('utf-8')))
    except (OSError,ValueError,TypeError):return initial()


def save(payload):
    normalized=normalize(payload)
    dest=settings_path();dest.parent.mkdir(parents=True,exist_ok=True)
    if dest.is_symlink() or dest.parent.is_symlink():raise OSError('Arayüz ayarları sembolik bağlantıya yazılamaz.')
    if dest.exists():
        import shutil
        shutil.copy2(dest,dest.with_suffix('.bak'))
    fd,tmp=tempfile.mkstemp(prefix='.layout-',suffix='.tmp',dir=str(dest.parent))
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f:
            json.dump(normalized,f,indent=2,ensure_ascii=False)
            f.flush();os.fsync(f.fileno())
        os.replace(tmp,dest)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
    return normalized


class LayoutEditor:
    """Non-modal editor; list drag-sorting, named tabs, colors and effects.

    Editing is disconnected from engine callbacks; Save only changes visual UI.
    """
    def __init__(self,parent,mode='dashboard',on_save=None):
        self.parent=parent;self.mode=mode;self.home='Ana Sayfa' if mode=='dashboard' else 'Tümü'
        self.data=load();self.working=deepcopy(self.data);self.history=[]
        self.callback=on_save;self.selected_tab=self.home
        self.win=tk.Toplevel(parent);self.win.title('Arayüzü Düzenle · Güvenli Görünüm Modu')
        self.win.geometry('1100x660');self.win.minsize(930,530)
        self.win.configure(bg='#292f37')
        self.win.protocol('WM_DELETE_WINDOW',self.close)
        self._make()

    def _checkpoint(self):
        self.history.append(deepcopy(self.working))
        if len(self.history)>30:self.history.pop(0)

    def _tabs(self):return self.working[self.mode]['tabs']

    def _make(self):
        fg='#f4efff';bg='#292f37';mid='#3a4350'
        tk.Label(self.win,text='GÖRÜNÜM DÜZENLEYİCİ  •  Üretim kodlarını değiştirmez',
             bg=bg,fg=fg,font=('Segoe UI',16,'bold')).pack(fill='x',padx=17,pady=12)
        tk.Label(self.win,text='Kartları fareyle sıralayın; sekme oluşturun, başka sekmeye taşıyın. '
             'Kaydet yalnız görsel ayarlara yazar.',bg=bg,fg='#b9c4da',wraplength=790).pack(fill='x',padx=17)
        center=tk.Frame(self.win,bg=bg);center.pack(fill='both',expand=True,padx=17,pady=10)
        left=tk.Frame(center,bg=mid);left.pack(side='left',fill='both',expand=False,padx=(0,9))
        tk.Label(left,text='Sekmeler',bg=mid,fg=fg,font=('Segoe UI',12,'bold')).pack(fill='x',pady=8)
        self.tab_list=tk.Listbox(left,height=16,width=22,bg=mid,fg=fg,selectbackground='#6544a5',borderwidth=0,exportselection=False)
        self.tab_list.pack(fill='both',expand=True,padx=8)
        self.tab_list.bind('<<ListboxSelect>>',self._tab_selected)
        for title,callback in [('＋ Yeni Sekme',self.new_tab),('Sekmeyi Sil',self.delete_tab),('Yeniden Adlandır',self.rename_tab)]:
            tk.Button(left,text=title,command=callback,bg='#373050',fg=fg,relief='flat').pack(fill='x',padx=7,pady=3)
        right=tk.Frame(center,bg=mid);right.pack(side='left',fill='both',expand=True)
        tk.Label(right,text='Kartlar — sürükleyip sıralayın',bg=mid,fg=fg,font=('Segoe UI',12,'bold')).pack(fill='x',pady=8)
        self.cards=tk.Listbox(right,height=10,bg='#313b47',fg=fg,selectbackground='#6544a5',borderwidth=0,exportselection=False,font=('Segoe UI',11))
        self.cards.pack(fill='both',expand=True,padx=10)
        self.cards.bind('<ButtonPress-1>',self._drag_start)
        self.cards.bind('<B1-Motion>',self._drag_move)
        move_row=tk.Frame(right,bg=mid);move_row.pack(fill='x',padx=10,pady=9)
        tk.Label(move_row,text='Seçili kartı sekmeye taşı:',bg=mid,fg=fg).pack(side='left')
        self.target=tk.StringVar(value=self.home)
        self.target_combo=ttk.Combobox(move_row,textvariable=self.target,state='readonly',width=22)
        self.target_combo.pack(side='left',padx=6)
        tk.Button(move_row,text='Taşı',command=self.move_card,bg='#4d397f',fg=fg,relief='flat').pack(side='left',padx=4)
        theme=tk.Frame(self.win,bg=mid);theme.pack(fill='x',padx=17,pady=(0,8))
        tk.Button(theme,text='🎨 Vurgu Rengi Seç',command=self.select_color,bg='#4d397f',fg=fg).pack(side='left',padx=7,pady=7)
        self.accent=tk.StringVar(value=self.working[self.mode]['accent'])
        tk.Label(theme,textvariable=self.accent,bg=mid,fg=fg).pack(side='left')
        for key,label in [('background','Zemin'),('panel','Kart'),('button','Düğme'),('title','Başlık'),('border','Kenar')]:
            tk.Button(theme,text='🎨 '+label,command=lambda k=key:self.select_palette(k),
                      bg='#373050',fg=fg,relief='flat').pack(side='left',padx=2,pady=7)
        tk.Label(theme,text='Efekt:',bg=mid,fg=fg).pack(side='left',padx=(9,5))
        self.effect=tk.StringVar(value=self.working[self.mode]['effect'])
        combo=ttk.Combobox(theme,textvariable=self.effect,values=('kapalı','hafif','belirgin'),state='readonly',width=12)
        combo.pack(side='left')
        combo.bind('<<ComboboxSelected>>',self._effect_change)
        bottom=tk.Frame(self.win,bg=bg);bottom.pack(fill='x',padx=17,pady=(3,15))
        for label,cmd in [('↶ Geri Al',self.undo),('Varsayılana Dön',self.reset),('Vazgeç',self.close),('✓ Kaydet',self.commit)]:
            tk.Button(bottom,text=label,command=cmd,bg='#4d397f' if label.startswith('✓') else '#282e46',fg=fg,
                      relief='flat',padx=15,pady=9).pack(side='left',padx=4)
        self.refresh()

    def refresh(self):
        tabs=self._tabs();self.tab_list.delete(0,'end')
        for name in tabs:self.tab_list.insert('end',name)
        keys=list(tabs)
        if self.selected_tab not in tabs:self.selected_tab=self.home
        idx=keys.index(self.selected_tab)
        self.tab_list.selection_set(idx);self.tab_list.see(idx)
        self.cards.delete(0,'end')
        for card in tabs[self.selected_tab]:self.cards.insert('end',CARD_NAMES.get(card,card))
        self.target_combo.configure(values=list(tabs))
        if self.target.get() not in tabs:self.target.set(self.home)
        self.accent.set(self.working[self.mode]['accent'])
        self.effect.set(self.working[self.mode]['effect'])

    def _tab_selected(self,_evt):
        sel=self.tab_list.curselection()
        if sel:
            self.selected_tab=list(self._tabs())[sel[0]]
            self.cards.delete(0,'end')
            for card in self._tabs()[self.selected_tab]:self.cards.insert('end',CARD_NAMES.get(card,card))

    def _drag_start(self,event):
        self._drag_i=self.cards.nearest(event.y)
        self._drag_checkpoint=False

    def _drag_move(self,event):
        src=getattr(self,'_drag_i',None);dest=self.cards.nearest(event.y)
        items=self._tabs()[self.selected_tab]
        if src is None or src==dest or not (0<=src<len(items) and 0<=dest<len(items)):return
        if not self._drag_checkpoint:self._checkpoint();self._drag_checkpoint=True
        item=items.pop(src);items.insert(dest,item)
        self._drag_i=dest
        self.refresh();self.cards.selection_set(dest)

    def new_tab(self):
        name=simpledialog.askstring('Yeni Sekme','Yeni sekmenin adını gir:',parent=self.win)
        if name is None:return
        name=name.strip()
        if not 1<=len(name)<=40 or name in self._tabs() or len(self._tabs())>=11:
            messagebox.showwarning('Sekme adı','1–40 karakter, benzersiz ad ve en fazla 11 sekme kullan.',parent=self.win);return
        self._checkpoint();self._tabs()[name]=[];self.selected_tab=name;self.refresh()

    def delete_tab(self):
        if self.selected_tab==self.home:
            messagebox.showinfo('Sistem sekmesi','Ana sistem sekmesi silinemez.',parent=self.win);return
        if not messagebox.askyesno('Sekmeyi Sil','Sekme kaldırılsın mı? Kartlar ana sekmeye geri taşınacak.',parent=self.win):return
        self._checkpoint();items=self._tabs().pop(self.selected_tab)
        if self.mode=='dashboard':self._tabs()[self.home].extend(items)
        self.selected_tab=self.home;self.refresh()

    def rename_tab(self):
        if self.selected_tab==self.home:return
        name=simpledialog.askstring('Sekme Adı','Yeni ad:',initialvalue=self.selected_tab,parent=self.win)
        if name is None:return
        name=name.strip()
        if not 1<=len(name)<=40 or name in self._tabs():return
        self._checkpoint();tabs=self._tabs();tabs[name]=tabs.pop(self.selected_tab)
        self.selected_tab=name;self.refresh()

    def move_card(self):
        sel=self.cards.curselection();target=self.target.get()
        if not sel or target not in self._tabs():return
        if self.mode=='production' and self.selected_tab=='Tümü':
            # Production Tümü is mandatory, custom tab receives a view shortcut.
            self._checkpoint();card=self._tabs()['Tümü'][sel[0]]
            if target!='Tümü' and card not in self._tabs()[target]:self._tabs()[target].append(card)
        else:
            self._checkpoint();card=self._tabs()[self.selected_tab][sel[0]]
            if target!=self.selected_tab:
                if self.mode=='dashboard':self._tabs()[self.selected_tab].remove(card)
                if card not in self._tabs()[target]:self._tabs()[target].append(card)
        self.refresh()

    def select_color(self):
        selection=colorchooser.askcolor(color=self.accent.get(),title='Tema Vurgu Rengi',parent=self.win)
        if selection and selection[1]:
            self._checkpoint();self.working[self.mode]['accent']=selection[1];self.refresh()

    def select_palette(self,key):
        current=self.working[self.mode].get('colors',{}).get(key,self.accent.get())
        selection=colorchooser.askcolor(color=current,title='Tema · '+key,parent=self.win)
        if selection and selection[1]:
            self._checkpoint()
            self.working[self.mode].setdefault('colors',{})[key]=selection[1]
            self.refresh()

    def _effect_change(self,_event):
        self._checkpoint();self.working[self.mode]['effect']=self.effect.get()

    def reset(self):
        if not messagebox.askyesno('Varsayılana Dön','Yalnız görünüm ayarları sıfırlanacak. Devam?',parent=self.win):return
        self._checkpoint();self.working[self.mode]=initial()[self.mode];self.selected_tab=self.home;self.refresh()

    def undo(self):
        if self.history:self.working=self.history.pop();self.refresh()

    def commit(self):
        try:
            saved=save(self.working)
            if self.callback:self.callback(saved[self.mode])
            self.win.destroy()
        except OSError as exc:messagebox.showerror('Düzen kaydı başarısız',str(exc),parent=self.win)

    def close(self):self.win.destroy()
