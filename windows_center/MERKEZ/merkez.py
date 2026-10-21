"""Unified offline Windows Center V3: 6 existing + PETEK source-preserving.

Daily V2 remains byte-for-byte unchanged, executed in a child process. PETEK
V3 uses dedicated source-SHA-bound masks and never runs obsolete 13-hole code.
"""
from __future__ import annotations
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk,messagebox,scrolledtext

HERE=Path(__file__).resolve().parent


class Center:
    def __init__(self):
        self.root=tk.Tk()
        self.root.title('Görsel Mockup — Windows Üretim Merkezi V3 (7 kategori)')
        self.root.geometry('920x660')
        self.root.minsize(760,550)
        self.running=False;self.messages=queue.Queue();self.proc=None;self.batch_windows=[]
        p=ttk.Frame(self.root,padding=26);p.pack(fill='both',expand=True)
        ttk.Label(p,text='Görsel Üretim Merkezi V3',font=('Segoe UI',22,'bold')).pack(anchor='w')
        ttk.Label(p,text='Tek merkez • 7 kategori • orijinal fotoğraf koruma • güvenli yerel seri üretim',
                  font=('Segoe UI',11)).pack(anchor='w',pady=(6,12))
        ttk.Separator(p).pack(fill='x',pady=(6,13))
        ttk.Label(p,text='Günlük V2 — Önceden onaylı 6 kategori / 10 şablon',
                  font=('Segoe UI',12,'bold')).pack(anchor='w',pady=3)
        ttk.Label(p,text='WiFi Kutusu, Cam Tablo Yatay/Dikey, Ahşap Tablo, Cam Doğrama, Ocak Arkası.\nMevcut NumberGuard V2 ve FILL V1 kod kimliği kontrolü korunur.').pack(anchor='w')
        self.daily=ttk.Button(p,text='GÜNLÜK ÜRETİMİ AÇ',command=self.open_daily)
        self.daily.pack(fill='x',pady=(8,16))
        ttk.Separator(p).pack(fill='x')
        ttk.Label(p,text='PETEK DOLABI V3 — Delikler ve kavisler orijinalden korunur',
                  font=('Segoe UI',12,'bold')).pack(anchor='w',pady=(12,7))
        ttk.Label(p,text='Sabit 13 delik yok. Her şablonun ahşap baskı maskesi ayrı inceleme/onayla kilitlenir.\nOrijinal yarıklar, iç gölgeler, üst siyah kavis, alt kavis ve gerçek zemin aynen kalır.',wraplength=850).pack(anchor='w')
        row=ttk.Frame(p);row.pack(fill='x',pady=12)
        ttk.Button(row,text='1. PETEK ŞABLON / MASKE İNCELE',command=self.open_review).pack(side='left',fill='x',expand=True,padx=(0,8))
        ttk.Button(row,text='2. PETEK SERİ ÜRETİM',command=self.open_petek).pack(side='left',fill='x',expand=True)
        ttk.Label(p,text='PETEK çıktıları yereldir; bulut/yükleme kapalıdır. Gerçek tasarımlar üretilmeden önce maskeleri gözle onayla.',wraplength=850).pack(anchor='w')
        ttk.Separator(p).pack(fill='x',pady=(14,8))
        self.status=tk.StringVar(value='Hazır. İlk PETEK kullanımında maskeyi incele ve onayla.')
        ttk.Label(p,textvariable=self.status,wraplength=850).pack(anchor='w',pady=(0,8))
        self.log=scrolledtext.ScrolledText(p,height=9,state='disabled')
        self.log.pack(fill='both',expand=True)
        ttk.Button(p,text='PETEK çıktı / kayıt klasörünü aç',command=self.open_petek_results).pack(anchor='w',pady=8)
        self.root.protocol('WM_DELETE_WINDOW',self.close)
        self.root.after(170,self.poll)

    def open_daily(self):
        self.start([sys.executable,'-B',str(HERE/'GUNLUK'/'run.py')],'Günlük V2')

    def open_review(self):
        try:
            from PETEK_V3.gui import open_mask_editor
            open_mask_editor(self.root)
        except Exception as exc:
            messagebox.showerror('PETEK V3 açılmadı',str(exc),parent=self.root)

    def open_petek(self):
        try:
            from PETEK_V3.gui import open_batch_window
            win=open_batch_window(self.root)
            self.batch_windows.append(win)
        except Exception as exc:
            messagebox.showerror('PETEK V3 seri üretim açılmadı',str(exc),parent=self.root)

    def start(self,command,route):
        if self.running:return
        self.running=True;self.daily.configure(state='disabled')
        self.status.set(route+' başlatıldı. Ayrı günlük kontrol penceresi ve çıktıları takip edin.')
        def job():
            try:
                env=dict(os.environ,PYTHONUTF8='1',PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1')
                self.proc=subprocess.Popen(command,cwd=HERE,env=env,stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace')
                for line in self.proc.stdout:self.messages.put(('log',line))
                self.messages.put(('done',(route,self.proc.wait())))
            except Exception as exc:
                self.messages.put(('log',repr(exc)))
                self.messages.put(('done',(route,2)))
        threading.Thread(target=job,daemon=False).start()

    def poll(self):
        try:
            while True:
                kind,value=self.messages.get_nowait()
                if kind=='log':
                    self.log.configure(state='normal');self.log.insert('end',value)
                    self.log.see('end');self.log.configure(state='disabled')
                else:
                    route,code=value;self.running=False;self.proc=None
                    self.daily.configure(state='normal')
                    self.status.set(route+' tamamlandı. Raporu kontrol edin.' if code==0
                                    else route+' durdu. Hata ayrıntısını yukarıdan kopyalayın.')
        except queue.Empty:pass
        self.root.after(170,self.poll)

    def open_petek_results(self):
        try:
            from PETEK_V3.registry import store_root
            folder=store_root()
            if folder.is_dir():
                if os.name=='nt':os.startfile(str(folder))
                else:self.status.set(str(folder))
            else:messagebox.showinfo('İlk üretim gerekli','PETEK kayıt klasörü henüz oluşturulmadı.',parent=self.root)
        except Exception as exc:messagebox.showerror('Dosyalar açılmadı',str(exc),parent=self.root)

    def close(self):
        active=any(win.worker and win.worker.is_alive() for win in self.batch_windows)
        if active:
            messagebox.showinfo('PETEK üretim açık','Seri üretimde güvenli durdurmayı kullanın. Çalışma tamamlanmadan merkezi kapatmayın.',parent=self.root)
            return
        if self.running:
            messagebox.showinfo('Günlük üretim açık','Günlük işlem tamamlanana kadar merkezi kapatma.',parent=self.root)
        else:self.root.destroy()


if __name__=='__main__':
    Center().root.mainloop()
