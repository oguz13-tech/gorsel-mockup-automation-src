"""One entry point; existing category rendering and reviewed PETEK stay isolated."""
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk,filedialog,messagebox,scrolledtext
HERE=Path(__file__).resolve().parent

class Center:
    def __init__(self):
        self.root=tk.Tk();self.root.title('Görsel Mockup — Üretim Merkezi V2');self.root.geometry('830x650')
        self.running=False;self.messages=queue.Queue();self.proc=None
        panel=ttk.Frame(self.root,padding=22);panel.pack(fill='both',expand=True)
        ttk.Label(panel,text='Görsel üretim merkezi',font=('Segoe UI',19,'bold')).pack(anchor='w')
        ttk.Label(panel,text='WiFi · Yatay cam · Dikey cam · Ahşap · Cam doğrama · Ocak arkası · PETEK',wraplength=760).pack(anchor='w',pady=10)
        self.daily=ttk.Button(panel,text='Günlük üretimi aç — 10 şablon / 6 kategori',command=self.open_daily)
        self.daily.pack(fill='x',pady=(0,18))
        ttk.Separator(panel).pack(fill='x')
        ttk.Label(panel,text='PETEK — 13 yarıklı, düz veya onaylı kavisli ön panel',font=('Segoe UI',12,'bold')).pack(anchor='w',pady=(15,6))
        ttk.Label(panel,text='PETEK için gerçek şablonla eşleşen, insan incelemesi yapılmış geometriyi içeren üretim planını seç. Örnek/demo planını gerçek ürün olarak kullanma.',wraplength=750).pack(anchor='w')
        self.manifest=tk.StringVar();row=ttk.Frame(panel);row.pack(fill='x',pady=8)
        ttk.Entry(row,textvariable=self.manifest).pack(side='left',fill='x',expand=True)
        ttk.Button(row,text='PETEK planı seç',command=self.choose_manifest).pack(side='left',padx=8)
        self.designs=tk.StringVar();row=ttk.Frame(panel);row.pack(fill='x')
        ttk.Entry(row,textvariable=self.designs).pack(side='left',fill='x',expand=True)
        ttk.Button(row,text='Tasarım klasörü seç',command=self.choose_designs).pack(side='left',padx=8)
        self.plan_button=ttk.Button(panel,text='İlk kullanım: PETEK şablonunun baskı yüzeyini işaretle',command=self.new_plan);self.plan_button.pack(fill='x',pady=8)
        self.petek=ttk.Button(panel,text='PETEK görsellerini ve Excel/CSV listesini üret',command=self.open_petek);self.petek.pack(fill='x',pady=10)
        ttk.Label(panel,text='Çıktılar bilgisayarına kaydedilir. PETEK görsellerini ilk üretimde gözle kontrol et.',wraplength=750).pack(anchor='w')
        self.status=tk.StringVar(value='Üretim türünü seç.');ttk.Label(panel,textvariable=self.status,wraplength=750).pack(anchor='w',pady=10)
        self.log=scrolledtext.ScrolledText(panel,height=11,state='disabled');self.log.pack(fill='both',expand=True)
        ttk.Button(panel,text='Tüm sonuç klasörünü aç',command=self.results).pack(anchor='w',pady=8)
        self.root.protocol('WM_DELETE_WINDOW',self.close);self.root.after(150,self.poll)
    def choose_manifest(self):
        p=filedialog.askopenfilename(parent=self.root,title='PETEK onaylı üretim planı',filetypes=[('JSON','*.json')])
        if p:self.manifest.set(p)
    def choose_designs(self):
        p=filedialog.askdirectory(parent=self.root,title='PETEK tasarımları')
        if p:self.designs.set(p)
    def new_plan(self):
        from petek_plan import open_editor
        def saved(plan,designs):self.manifest.set(plan);self.designs.set(designs);self.status.set('PETEK planı kaydedildi. Üretimi başlatabilirsin.')
        open_editor(self.root,self.designs.get().strip(),saved)
    def open_daily(self):self.start([sys.executable,'-B',str(HERE/'GUNLUK/run.py')],'Günlük üretim')
    def open_petek(self):
        p=self.manifest.get().strip();d=self.designs.get().strip()
        if not p or not Path(p).is_file():messagebox.showinfo('PETEK planı gerekli','Gerçek şablon ve onaylı geometriyi içeren PETEK planını seç.',parent=self.root);return
        if not d or not Path(d).is_dir():messagebox.showinfo('Tasarım klasörü gerekli','PETEK tasarımlarının klasörünü seç.',parent=self.root);return
        self.start([sys.executable,'-B',str(HERE/'petek_entry.py'),p,d],'PETEK')
    def start(self,command,route):
        if self.running:return
        self.running=True;self.plan_button.config(state='disabled');self.daily.config(state='disabled');self.petek.config(state='disabled');self.status.set(route+' açık. Sonucu bu ekranda takip edebilirsin.')
        def work():
            try:
                env=dict(os.environ,PYTHONUTF8='1',PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1')
                self.proc=subprocess.Popen(command,cwd=HERE,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace')
                for line in self.proc.stdout:self.messages.put(('log',line))
                self.messages.put(('done',(route,self.proc.wait())))
            except Exception as exc:self.messages.put(('log',str(exc)));self.messages.put(('done',(route,2)))
        threading.Thread(target=work,daemon=False).start()
    def poll(self):
        try:
            while True:
                kind,value=self.messages.get_nowait()
                if kind=='log':
                    self.log.config(state='normal');self.log.insert('end',value);self.log.see('end');self.log.config(state='disabled')
                else:
                    route,code=value;self.running=False;self.proc=None;self.plan_button.config(state='normal');self.daily.config(state='normal');self.petek.config(state='normal')
                    self.status.set(route+(' kapandı. Üretim sayısı ve durumunu kendi sonuç raporundan kontrol et.' if code==0 else ' durdu. Yukarıdaki mesajı kopyalayıp gönder.'))
        except queue.Empty:pass
        self.root.after(150,self.poll)
    def results(self):
        p=Path('C:/AI_LOCAL_OUTPUTS/GorselMockup')
        if p.is_dir():os.startfile(str(p))
        else:messagebox.showinfo('Henüz sonuç yok','İlk üretimden sonra sonuçlar burada olacak.',parent=self.root)
    def close(self):
        if self.running:messagebox.showinfo('Üretim penceresi açık','Günlük üretim penceresini kapat veya PETEK işleminin bitmesini bekle.',parent=self.root)
        else:self.root.destroy()

if __name__=='__main__':Center().root.mainloop()
