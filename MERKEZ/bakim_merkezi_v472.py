"""Separate guarded Windows recovery center; never runs cleanup automatically."""
from __future__ import annotations
import json
from pathlib import Path
import os
import queue
import threading
import tkinter as tk
from tkinter import ttk,filedialog,messagebox,simpledialog
from legacy_manager import preferred_runtime
from magenta_reconcile_v472 import (LAB,CONFIRM as MAGENTA_CONFIRM,analyze,
                                    write_report,html_comparison,apply)
from external_inventory_v472 import (CONFIRM as INVENTORY_CONFIRM,
                                      build,save,stage)
from runtime_relocate_v473 import (CONFIRM as RUNTIME_CONFIRM,
                                   stage as stage_runtime,activate as activate_runtime)
ROOT=Path(__file__).resolve().parent.parent

class Maintenance:
    def __init__(self):
        self.window=tk.Tk()
        self.window.title('V4.7.2 — Magenta ve Eski Sürüm Dosya Güvenliği')
        self.window.geometry('920x740')
        self.window.minsize(710,580)
        self.events=queue.Queue()
        self.working=False
        frame=ttk.Frame(self.window,padding=16);frame.pack(fill='both',expand=True)
        ttk.Label(frame,text='GÜVENLİ DOSYA BİRLEŞTİRME / ÖN İNCELEME',
                  font=('Segoe UI',15,'bold')).pack(anchor='w')
        ttk.Label(frame,text='Varsayılan işlemler SALT OKUNUR. Test klasörlerini otomatik silmez, '
                            'eski programın üzerine kod yazmaz. Magenta değişimleri yalnız ayrıca açık onayla yapılır.',
                  wraplength=850).pack(anchor='w',pady=7)
        self.workspace=tk.StringVar(value=str(preferred_runtime()))
        self.lab=tk.StringVar(value=str(LAB))
        self.roots=tk.StringVar(value='C:\\AI_WORK;'+str(Path.home()/'Downloads'))
        self.code=tk.StringVar(value=str(ROOT))
        for title,variable in [('ANA ÇALIŞMA KLASÖRÜ',self.workspace),
                                ('MAGENTA KAYNAĞI',self.lab),
                                ('AKTİF TEST EDİLMİŞ KOD KLASÖRÜ',self.code),
                                ('TARANACAK TEST / SÜRÜM KÖKLERİ (noktalı virgülle)',self.roots)]:
            ttk.Label(frame,text=title).pack(anchor='w',pady=(9,1))
            ttk.Entry(frame,textvariable=variable,width=115).pack(fill='x')
        ttk.Separator(frame).pack(fill='x',pady=12)
        ttk.Label(frame,text='AŞAMA 1 — MAGENTA GÖRSELLER (görsel bazlı, klasör bazlı değil)',
                  font=('Segoe UI',11,'bold')).pack(anchor='w')
        row=ttk.Frame(frame);row.pack(fill='x',pady=6)
        self.buttons=[]
        self.btn(row,'1. Magenta ↔ Ana Önizleme / Rapor',self.magenta_report)
        self.btn(row,'2. İncelediğim Planı Uygula (açık onay)',self.magenta_apply)
        self.allow_review=tk.BooleanVar(value=False)
        ttk.Checkbutton(frame,variable=self.allow_review,
                        text='LAB insan onayı bulunmayan eşleşen görseller değişsin, '
                             'ancak dört köşe yeniden onaya düşsün (normalde kapalı)').pack(anchor='w')
        ttk.Separator(frame).pack(fill='x',pady=12)
        ttk.Label(frame,text='AŞAMA 2 — DIŞ KLASÖRLERDE KALAN DOSYALAR',
                  font=('Segoe UI',11,'bold')).pack(anchor='w')
        row=ttk.Frame(frame);row.pack(fill='x',pady=6)
        self.btn(row,'3. Eski Klasörleri Salt-Okunur Tara',self.external_report)
        self.btn(row,'4. Eksik/Farklı Kodları Kurtarma Alanına Kopyala',self.external_stage)
        ttk.Label(frame,text='4. düğme dosyaları CANLI sisteme entegre etmez; '
                            'yalnız SHA kanıtlı ayrı kurtarma alanına kopyalar. '
                            'Farklı kodları körlemesine etkinleştirmek tehlikelidir.',
                  wraplength=850).pack(anchor='w',pady=4)
        ttk.Separator(frame).pack(fill='x',pady=9)
        ttk.Label(frame,text='AŞAMA 3 — ONEDRIVE / SQLite Güvenli Çalışma Alanı',
                  font=('Segoe UI',11,'bold')).pack(anchor='w')
        rw=ttk.Frame(frame);rw.pack(fill='x',pady=6)
        self.btn(rw,'5. OneDrive Dışı Yedek Kopyayı Hazırla',self.stage_runtime)
        self.btn(rw,'6. Doğrulanan Kopyayı Etkinleştir (AÇIK ONAY)',self.activate_runtime)
        self.status=tk.StringVar(value='Hazır. Önce 1 ve 3 numaralı raporları oluşturun.')
        ttk.Label(frame,textvariable=self.status,wraplength=850).pack(anchor='w',pady=5)
        self.output=tk.Text(frame,height=11,wrap='word')
        self.output.pack(fill='both',expand=True)
        self.window.after(150,self.poll)
    def btn(self,parent,title,fn):
        b=ttk.Button(parent,text=title,command=fn)
        b.pack(side='left',padx=(0,8),fill='x',expand=True)
        self.buttons.append(b)
    def enqueue(self,fn,on_success=None):
        if self.working:
            messagebox.showwarning('İşlem devam ediyor','Önce devam eden raporun bitmesini bekleyin.')
            return
        self.working=True
        self.status.set('İşlem yapılıyor, mevcut veriler korunuyor...')
        for b in self.buttons:b.configure(state='disabled')
        def thread():
            try:self.events.put(('done',fn(),on_success))
            except Exception as e:self.events.put(('error',str(e),None))
        threading.Thread(target=thread,daemon=True).start()
    def poll(self):
        try:
            while True:
                kind,result,on_success=self.events.get_nowait()
                self.working=False
                for b in self.buttons:b.configure(state='normal')
                if kind=='error':
                    self.status.set('İŞLEM DURDU: '+str(result))
                    messagebox.showerror('Güvenli engel',str(result))
                else:
                    self.status.set('İşlem tamamlandı. Sonuç raporunu inceleyin.')
                    self.output.insert('end',str(result)+'\n\n')
                    self.output.see('end')
                    if on_success:on_success(result)
        except queue.Empty:pass
        self.window.after(150,self.poll)
    def magenta_report(self):
        def work():
            plan=analyze(Path(self.workspace.get()),Path(self.lab.get()))
            path=write_report(plan);comparison=html_comparison(path)
            from collections import Counter
            return {'report':str(path),'html':str(comparison),
                    'statuses':dict(Counter(j['status'] for j in plan['jobs']))}
        def open_result(r):
            messagebox.showinfo('Magenta Raporu','İki görselin karşılaştırması açılacak. '
                                'Kopyalama henüz yapılmadı.')
            os.startfile(r['html']) if os.name=='nt' else None
        self.enqueue(work,open_result)
    def magenta_apply(self):
        plan=filedialog.askopenfilename(
            parent=self.window,title='1. adımda oluşan MAGENTA_PLAN_...json dosyasını seç',
            filetypes=[('Magenta planı','MAGENTA_PLAN_*.json'),('JSON','*.json')])
        if not plan:return
        if not messagebox.askyesno('GÖRSEL DEĞİŞİKLİĞİ',
            'Flask ve 7 Kategori üretim uygulamalarını kapattın mı?\n'
            'Yalnız aynı kimlikli fotoğraf değişecek. Eski çalışma görüntüsü ve '
            'ana SQLite önce SHA ile yedeklenecek. Orijinal arşiv korunacak. Devam?'):
            return
        prompt=simpledialog.askstring('AÇIK ONAY','Devam etmek için şu metni eksiksiz yaz:\n\n'+MAGENTA_CONFIRM,
                                     parent=self.window)
        if prompt!=MAGENTA_CONFIRM:
            messagebox.showwarning('İptal','Onay metni eşleşmedi. Hiçbir şey değiştirilmedi.')
            return
        self.enqueue(lambda:apply(Path(plan),prompt,allow_review=self.allow_review.get()),
                     lambda r:messagebox.showinfo('Magenta aktarım sonucu',
                         'Değiştirilen: '+str(r.get('count',0))+'\n'+str(r.get('backup',''))))
    def external_report(self):
        def work():
            plan=build(Path(self.code.get()),Path(self.workspace.get()),
                       [x.strip() for x in self.roots.get().split(';') if x.strip()])
            path=save(plan)
            return {'report':str(path),
                    'candidate_code_roots':len(plan['candidate_code_roots']),
                    'different_code_files':len(plan['different_code_files']),
                    'external_state_files':len(plan['external_state_files']),
                    'warning':'Eski klasörler hâlâ otomatik silinmeye uygun değildir.'}
        self.enqueue(work,lambda r:messagebox.showinfo('Klasör taraması',
                 'Rapor: '+r['report']+'\nEski klasörleri henüz silmeyin.'))
    def external_stage(self):
        plan=filedialog.askopenfilename(parent=self.window,
            title='EXTERNAL_SCAN_...json envanter raporunu seç',
            filetypes=[('Envanter raporu','EXTERNAL_SCAN_*.json'),('JSON','*.json')])
        if not plan:return
        if not messagebox.askyesno('YALNIZ KURTARMA KOPYASI',
          'Farklı/eksik kodlar ana çalışma alanında KURTARMA_ON_INCELEME klasörüne '
          'salt kurtarma kopyası olarak alınacak. Aktif kod üstüne yazılmayacak. Devam?'):
            return
        phrase=simpledialog.askstring('AÇIK ONAY','Şu onayı yaz:\n'+INVENTORY_CONFIRM,parent=self.window)
        if phrase!=INVENTORY_CONFIRM:return
        self.enqueue(lambda:str(stage(plan,phrase)))
    def stage_runtime(self):
        target=simpledialog.askstring(
            'Yeni ana çalışma kopyası',
            'Orijinal OneDrive dosyaları taşınmaz veya silinmez. '
            'Yeni ve daha önce var olmayan, OneDrive DIŞINDA bir hedef gir:',
            initialvalue=r'C:\GorselMockup_Runtime_V473',parent=self.window)
        if not target:return
        if not messagebox.askyesno(
            'Yalnız doğrulanmış kopya oluştur',
            'Program ve 4 köşe sunucusu kapalı olmalı. Bütün çalışma alanının '
            'SHA denetimli kopyası oluşturulacak. Ana çalışma klasörü '
            'HENÜZ DEĞİŞMEYECEK. Devam?',parent=self.window):return
        self.enqueue(lambda:stage_runtime(self.workspace.get(),target))

    def activate_runtime(self):
        target=filedialog.askdirectory(parent=self.window,title='5. adımda hazırlanmış doğrulanmış çalışma kopyası')
        if not target:return
        phrase=simpledialog.askstring(
            'AYRI AKTİVASYON ONAYI',RUNTIME_CONFIRM,parent=self.window)
        if phrase!=RUNTIME_CONFIRM:
            messagebox.showwarning('İptal','Açık onay yok; çalışma alanı değişmedi.',parent=self.window)
            return
        self.enqueue(lambda:activate_runtime(target,phrase),
                     lambda record:messagebox.showinfo(
                         'Yeni ana çalışma alanı',str(record.get('active_workspace'))+
                         '\nEski dosyalar silinmedi. Yeni programı yeniden açın.',parent=self.window))

    def run(self):self.window.mainloop()
if __name__=='__main__':Maintenance().run()
