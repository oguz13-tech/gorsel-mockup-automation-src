"""Single Windows GUI for seven categories, template review and durable production."""
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk,filedialog,messagebox,scrolledtext
import uuid

from .production import default_config
from .queue_store import CATEGORIES
from .review import Review
from .safety import json_atomic,read_json,safe

HERE=Path(__file__).resolve().parent


class App:
    def __init__(self):
        self.root=tk.Tk();self.root.title('Görsel Üretim Fabrikası V3');self.root.geometry('1020x820');self.root.minsize(800,650)
        self.config=default_config();self.messages=queue.Queue();self.proc=None;self.running=False;self.paused=False;self.close_pending=False
        saved=Path(self.config['output'])/'SETTINGS.json'
        if saved.is_file():
            try:self.config.update(read_json(saved))
            except Exception:pass
        book=ttk.Notebook(self.root);book.pack(fill='both',expand=True,padx=12,pady=12)
        prod=ttk.Frame(book,padding=15);templates=ttk.Frame(book,padding=15);settings=ttk.Frame(book,padding=15)
        book.add(prod,text='Üretim');book.add(templates,text='Şablon inceleme');book.add(settings,text='Klasörler / geçiş')
        ttk.Label(prod,text='Yedi kategori • Tek üretim kuyruğu',font=('Segoe UI',18,'bold')).pack(anchor='w')
        self.vars={}
        self.path_row(prod,'Tasarım klasörü','designs')
        categories=ttk.Frame(prod);categories.pack(fill='x',pady=10)
        self.cat={}
        for i,(key,label) in enumerate(CATEGORIES.items()):
            self.cat[key]=tk.BooleanVar(value=key in self.config['categories'])
            ttk.Checkbutton(categories,text=label,variable=self.cat[key]).grid(row=i//3,column=i%3,sticky='w',padx=12,pady=5)
        ttk.Label(prod,text='Diğer kategoriler: mevcut onaylı şablonlar. PETEK: aşağıdaki listeden seçilen V3 maskeleri.').pack(anchor='w')
        self.all_approved=tk.BooleanVar(value=self.config.get('all_approved',False))
        ttk.Checkbutton(prod,text='Altı kategoride yedeği doğrulanabilen tüm uygun insan onaylı şablonları kullan (kapalı: test edilmiş 10 şablon)',variable=self.all_approved).pack(anchor='w',pady=6)
        self.profiles=tk.Listbox(prod,selectmode='extended',height=5,exportselection=False);self.profiles.pack(fill='x')
        row=ttk.Frame(prod);row.pack(fill='x',pady=7)
        ttk.Button(row,text='PETEK profili ekle',command=self.add_profile).pack(side='left')
        ttk.Button(row,text='Listedeki seçimi kaldır',command=self.remove_profile).pack(side='left',padx=6)
        self.profile_paths=[]
        for p in self.config.get('profiles',[]):self.append_profile(p)
        self.status=tk.StringVar(value='Tasarım klasörünü ve kategorileri seç. PETEK için önce orijinal şablonu incele.')
        ttk.Label(prod,textvariable=self.status,wraplength=930).pack(anchor='w',pady=10)
        self.progress=ttk.Progressbar(prod,mode='indeterminate');self.progress.pack(fill='x')
        row=ttk.Frame(prod);row.pack(fill='x',pady=10)
        self.start_button=ttk.Button(row,text='Üretimi başlat / yarım işleri devam ettir',command=self.start);self.start_button.pack(side='left')
        self.pause_button=ttk.Button(row,text='Duraklat',command=self.pause,state='disabled');self.pause_button.pack(side='left',padx=6)
        self.cancel_button=ttk.Button(row,text='Mevcut işten sonra durdur',command=self.cancel,state='disabled');self.cancel_button.pack(side='left')
        ttk.Button(row,text='Sonuçları aç',command=self.results).pack(side='left',padx=6)
        self.log=scrolledtext.ScrolledText(prod,height=12);self.log.pack(fill='both',expand=True)
        ttk.Label(prod,text='1200×1600 çıktı · Dahili SKU/barkod ve Excel/CSV · İlk sonuçların görsel onayı gerekli').pack(anchor='w',pady=6)
        ttk.Label(templates,text='PETEK: dört köşe → otomatik maske → gözle onay',font=('Segoe UI',15,'bold')).pack(anchor='w',pady=10)
        ttk.Label(templates,text='Boş/orijinal mockup seç. Ön panelin dört köşesini işaretle. Yeşil alan basılacak yüzeydir.\nDeliklerin sayısını girmen gerekmez. Orijinal delik ve kavisler korunur.\nBelirsiz maskeyi fırça ile düzelt; onay sonrasında aynı şablon yeniden analiz edilmez.',wraplength=900).pack(anchor='w',pady=12)
        self.review_button=ttk.Button(templates,text='Yeni PETEK şablonu incele / maskeyi düzelt',command=self.review);self.review_button.pack(anchor='w',pady=12)
        ttk.Label(templates,text='Eski PETEK planları otomatik onaylanmaz; orijinal şablonu burada bir kez incele.\nDiğer altı kategorinin mevcut İnceleme Merkezi ve onaylı köşeleri kullanılmaya devam eder.',wraplength=900).pack(anchor='w')
        for label,name in [('Kurulu kaynak kodu','code'),('Canlı çalışma klasörü','runtime'),('Doğrulanmış P0 yedek klasörü','backup'),('Mevcut günlük çıktı kökü','legacy_store'),('Yeni fabrika çıktı klasörü','output')]:self.path_row(settings,label,name)
        ttk.Label(settings,text='Yedek klasörü PR9_SOURCE, RUNTIME_BACKUP ve RUNTIME_BACKUP_SHA256.json içermeli.\nPETEK tek başına çalışırken eski kategorilerin yedeği gerekmez.\nYeni sürüm ayrı klasörden çalışır. Önceki BASLAT.bat geri dönüş yoludur.',wraplength=900).pack(anchor='w',pady=12)
        self.root.after(120,self.poll);self.root.protocol('WM_DELETE_WINDOW',self.close)

    def path_row(self,parent,label,key):
        ttk.Label(parent,text=label).pack(anchor='w',pady=(9,2))
        row=ttk.Frame(parent);row.pack(fill='x');self.vars[key]=tk.StringVar(value=self.config.get(key,''))
        ttk.Entry(row,textvariable=self.vars[key]).pack(side='left',fill='x',expand=True)
        def choose():
            if self.running:return
            path=filedialog.askdirectory(parent=self.root,title=label)
            if path:self.vars[key].set(path)
        ttk.Button(row,text='Seç',command=choose).pack(side='left',padx=7)

    def append_profile(self,p):
        p=str(p)
        if p not in self.profile_paths:
            self.profile_paths.append(p)
            try:label=Path(read_json(p)['source']).name
            except Exception:label=Path(p).name
            self.profiles.insert('end',label+' | '+p);self.profiles.selection_set('end')

    def add_profile(self):
        if self.running:return
        for p in filedialog.askopenfilenames(parent=self.root,title='V3 PROFILE.json seç',filetypes=[('Onaylı profil','*.json')]):
            try:
                from .petek_v3 import load_profile
                load_profile(p);self.append_profile(p)
            except Exception as exc:messagebox.showerror('Profil kullanılamadı',str(exc),parent=self.root)

    def remove_profile(self):
        if self.running:return
        for i in reversed(self.profiles.curselection()):self.profile_paths.pop(i);self.profiles.delete(i)

    def review(self):
        if self.running:return
        root=safe(self.vars['output'].get())/'PROFILES'
        Review(self.root,root,self.append_profile)

    def start(self):
        if self.running:return
        config=dict(self.config)
        config.update({k:v.get().strip() for k,v in self.vars.items()})
        config['categories']=[k for k,v in self.cat.items() if v.get()]
        config['profiles']=[self.profile_paths[i] for i in self.profiles.curselection()]
        config['all_approved']=self.all_approved.get()
        if not config['categories'] or not Path(config['designs']).is_dir():messagebox.showinfo('Seçim gerekli','Tasarım klasörünü ve en az bir kategoriyi seç.',parent=self.root);return
        if '06_Petek_Dolabi' in config['categories'] and not config['profiles']:messagebox.showinfo('PETEK şablonu gerekli','Şablon inceleme bölümünden bir PETEK maskesi onayla veya listede mevcut profilini seç.',parent=self.root);return
        try:
            from .safety import separate
            root=safe(config['output'])
            for p in (HERE,config['code'],config['runtime'],config['designs']):separate(root,p)
            if config.get('backup'):separate(root,config['backup'])
            root.mkdir(parents=True,exist_ok=True)
            json_atomic(root/'SETTINGS.json',config)
            token=uuid.uuid4().hex;config_path=root/('RUN_'+token+'.json');json_atomic(config_path,config)
            self.control=root/('CONTROL_'+token+'.json');json_atomic(self.control,{'command':'run'})
        except Exception as exc:messagebox.showerror('Başlatılamadı',str(exc),parent=self.root);return
        self.config=config;self.running=True;self.paused=False;self.progress.start(15)
        self.start_button.config(state='disabled');self.review_button.config(state='disabled');self.pause_button.config(state='normal');self.cancel_button.config(state='normal')
        self.status.set('Üretim başladı. Durum ve rapor yolu aşağıda gösterilir.')
        def worker():
            try:
                env=dict(os.environ,PYTHONUTF8='1',PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1')
                self.proc=subprocess.Popen([sys.executable,'-B','-m','FABRIKA.production',str(config_path),str(self.control)],cwd=HERE.parent,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace')
                for line in self.proc.stdout:self.messages.put(('log',line))
                self.messages.put(('done',self.proc.wait()))
            except Exception as exc:self.messages.put(('log',str(exc)));self.messages.put(('done',2))
        threading.Thread(target=worker,daemon=False).start()

    def pause(self):
        if not self.running:return
        self.paused=not self.paused;json_atomic(self.control,{'command':'pause' if self.paused else 'run'})
        self.pause_button.config(text='Devam et' if self.paused else 'Duraklat')
        self.status.set('Mevcut iş bitince duraklatılacak.' if self.paused else 'Üretim devam ediyor.')

    def cancel(self):
        if self.running:json_atomic(self.control,{'command':'cancel'});self.status.set('Mevcut iş tamamlanıp rapor kaydedilince duracak.')

    def results(self):
        root=Path(self.vars['output'].get());sessions=sorted((root/'OTURUMLAR').glob('*'))
        target=sessions[-1] if sessions else root
        if target.exists() and os.name=='nt':os.startfile(str(target))
        else:messagebox.showinfo('Sonuç yolu',str(target),parent=self.root)

    def poll(self):
        try:
            while True:
                kind,value=self.messages.get_nowait()
                if kind=='log':self.log.insert('end',value);self.log.see('end')
                else:
                    self.running=False;self.proc=None;self.progress.stop();self.start_button.config(state='normal');self.review_button.config(state='normal');self.pause_button.config(state='disabled',text='Duraklat');self.cancel_button.config(state='disabled')
                    self.status.set('İşlem kapandı. Sonuçları aç ile raporu ve görselleri kontrol et.' if value==0 else 'İşlem güvenli şekilde durdu. Aşağıdaki hata ve sonuç raporunu gönder.')
                    if self.close_pending:self.root.destroy();return
        except queue.Empty:pass
        self.root.after(120,self.poll)

    def close(self):
        if self.running:self.close_pending=True;self.cancel()
        else:self.root.destroy()

if __name__=='__main__':App().root.mainloop()
