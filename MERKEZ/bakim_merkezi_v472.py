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
from external_inventory_v472 import (CONFIRM as INVENTORY_CONFIRM,
                                      build,save,stage)
from runtime_relocate_v473 import (CONFIRM as RUNTIME_CONFIRM,
                                   stage as stage_runtime,activate as activate_runtime)
from system_integrity_v475 import examine as audit_everything,write_report as audit_save
from PETEK_V3.registry import store_root as petek_store_root
from URETIM_V4.final_guard_v44 import store_v4_root
ROOT=Path(__file__).resolve().parent.parent
# Keep high-impact writes inaccessible in the operator UI until real Windows
# backup/restore acceptance, even if isolated CI regression tests pass.
P0_USER_WRITE_LOCKED=True
P0_LOCKED_TITLES=('4.','6.')

from URETIM_V4.deleted_receipts_v474 import (candidate_rows as deleted_candidates,
                                          save_plan as save_deleted_plan,
                                          mark_selected as confirm_deleted,
                                          CONFIRM as REMOVED_CONFIRM)

class Maintenance:
    def __init__(self):
        self.window=tk.Tk()
        try:
            from dark_theme_v42 import apply_dark_theme, BG
            apply_dark_theme(self.window)
        except Exception:
            BG = None
        self.window.title('V4.7.5 — Eski Sürüm Dosya Güvenliği')
        self.window.geometry('980x820')
        self.window.minsize(730,620)
        self.events=queue.Queue()
        self.working=False
        outer=ttk.Frame(self.window);outer.pack(fill='both',expand=True)
        canvas=tk.Canvas(outer,highlightthickness=0,bg=BG if BG else '#0B101B')
        vertical=ttk.Scrollbar(outer,orient='vertical',command=canvas.yview)
        canvas.configure(yscrollcommand=vertical.set)
        vertical.pack(side='right',fill='y')
        canvas.pack(side='left',fill='both',expand=True)
        frame=ttk.Frame(canvas,padding=16)
        window_id=canvas.create_window((0,0),window=frame,anchor='nw')
        frame.bind('<Configure>',lambda event:canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>',lambda event:canvas.itemconfigure(window_id,width=event.width))
        canvas.bind_all('<MouseWheel>',lambda event:canvas.yview_scroll(
            int(-event.delta/120) if event.delta else 0,'units'))
        ttk.Label(frame,text='GÜVENLİ DOSYA BİRLEŞTİRME / ÖN İNCELEME',
                  font=('Segoe UI',15,'bold')).pack(anchor='w')
        ttk.Label(frame,text='Varsayılan işlemler SALT OKUNUR. Test klasörlerini otomatik silmez, '
                            'eski programın üzerine kod yazmaz.',
                  wraplength=850).pack(anchor='w',pady=7)
        self.workspace=tk.StringVar(value=str(preferred_runtime()))
        self.roots=tk.StringVar(value='C:\\AI_WORK;'+str(Path.home()/'Downloads'))
        self.code=tk.StringVar(value=str(ROOT))
        for title,variable in [('ANA ÇALIŞMA KLASÖRÜ',self.workspace),
                                ('AKTİF TEST EDİLMİŞ KOD KLASÖRÜ',self.code),
                                ('TARANACAK TEST / SÜRÜM KÖKLERİ (noktalı virgülle)',self.roots)]:
            ttk.Label(frame,text=title).pack(anchor='w',pady=(9,1))
            ttk.Entry(frame,textvariable=variable,width=115).pack(fill='x')
        self.buttons=[]
        self.locked_buttons=[]
        ttk.Label(frame,text='AŞAMA 1 — DIŞ KLASÖRLERDE KALAN DOSYALAR',
                  font=('Segoe UI',11,'bold')).pack(anchor='w')
        row=ttk.Frame(frame);row.pack(fill='x',pady=6)
        self.btn(row,'1. Eski Klasörleri Salt-Okunur Tara',self.external_report)
        self.btn(row,'2. Eksik/Farklı Kodları Kurtarma Alanına Kopyala',self.external_stage)
        ttk.Label(frame,text='4. düğme dosyaları CANLI sisteme entegre etmez; '
                            'yalnız SHA kanıtlı ayrı kurtarma alanına kopyalar. '
                            'Farklı kodları körlemesine etkinleştirmek tehlikelidir.',
                  wraplength=850).pack(anchor='w',pady=4)
        ttk.Separator(frame).pack(fill='x',pady=9)
        ttk.Label(frame,text='AŞAMA 2 — ONEDRIVE / SQLite Güvenli Çalışma Alanı',
                  font=('Segoe UI',11,'bold')).pack(anchor='w')
        rw=ttk.Frame(frame);rw.pack(fill='x',pady=6)
        self.btn(rw,'3. OneDrive Dışı Yedek Kopyayı Hazırla',self.stage_runtime)
        self.btn(rw,'4. Doğrulanan Kopyayı Etkinleştir (AÇIK ONAY)',self.activate_runtime)
        ttk.Separator(frame).pack(fill='x',pady=9)
        ttk.Label(frame,text='AŞAMA 3 — GEÇMİŞTE BİLEREK SİLİNEN 35 ÇIKTI',
                  font=('Segoe UI',11,'bold')).pack(anchor='w')
        hist=ttk.Frame(frame);hist.pack(fill='x',pady=6)
        self.btn(hist,'5. Kayıp Çıktıları Salt-Okunur Listele',self.plan_user_removed)
        self.btn(hist,'6. Tam 35 Kaydı USER_REMOVED Olarak İşaretle (ONAY)',self.mark_user_removed)
        ttk.Separator(frame).pack(fill='x',pady=9)
        ttk.Label(frame,text='AŞAMA 4 — 7 KATEGORİ / TÜM SİSTEM BÜTÜNLÜK DENETİMİ',
                  font=('Segoe UI',11,'bold')).pack(anchor='w')
        health=ttk.Frame(frame);health.pack(fill='x',pady=6)
        self.btn(health,'7. SQLite / Şablon / Mağaza / PETEK / Kod / Çıktı SHA Raporu',
                 self.full_integrity_report)
        ttk.Label(frame,text='9 numaralı işlem yalnız okur; bütün bileşenlerin durumunu '
                            'tek JSON raporunda gösterir. Eski klasör raporu olmadan '
                            'final silme izni vermez.',wraplength=875).pack(anchor='w')
        ttk.Label(frame,text='GÜVENLİK KİLİDİ: 4 / 6 işlemleri gerçek Windows veri yedeği ve geri dönüş testi kabul edilene kadar kapalıdır.',
                  wraplength=870,foreground='#8A4A14').pack(anchor='w',pady=5)
        self.status=tk.StringVar(value='Hazır. Önce 1 ve 7 numaralı salt-okunur raporları oluşturun.')
        ttk.Label(frame,textvariable=self.status,wraplength=850).pack(anchor='w',pady=5)
        self.output=tk.Text(frame,height=11,wrap='word')
        self.output.pack(fill='both',expand=True)
        self.window.after(150,self.poll)
    def btn(self,parent,title,fn):
        b=ttk.Button(parent,text=title,command=fn)
        b.pack(side='left',padx=(0,8),fill='x',expand=True)
        self.buttons.append(b)
        if P0_USER_WRITE_LOCKED and title.startswith(P0_LOCKED_TITLES):
            b.configure(state='disabled')
            self.locked_buttons.append(b)
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
                for b in self.buttons:
                    b.configure(state='disabled' if b in self.locked_buttons else 'normal')
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
        if P0_USER_WRITE_LOCKED:
            messagebox.showwarning('Veri güvenliği kilidi',
                'Bu işlem gerçek Windows yedekleme / geri alma kabulü bitene kadar kapalı.',parent=self.window)
            return
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
        if P0_USER_WRITE_LOCKED:
            messagebox.showwarning('Veri güvenliği kilidi',
                'Bu işlem gerçek Windows yedekleme / geri alma kabulü bitene kadar kapalı.',parent=self.window)
            return
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

    def plan_user_removed(self):
        def work():
            plan=deleted_candidates()
            report=save_deleted_plan(plan)
            return {'plan':str(report),'count':plan['count'],
                    'status_counts':plan['status_counts'],
                    'note':'Hiçbir çıktı, SQLite satırı veya statü değiştirilmedi.'}
        self.enqueue(work,lambda record:messagebox.showinfo(
            'Silinen çıktı kayıtları',f"Bulunan: {record['count']}\\n{record['plan']}\\n"
            'Sadece senin sildiğini onayladığın eksik kayıtları işaretle.',
            parent=self.window))

    def mark_user_removed(self):
        plan=filedialog.askopenfilename(
            parent=self.window,title='7. adımdaki USER_REMOVED_PLAN_...json',
            filetypes=[('Çıktı planı','USER_REMOVED_PLAN_*.json'),('JSON','*.json')])
        if not plan:return
        record=json.loads(Path(plan).read_text('utf-8'))
        items=record.get('rendered_missing_candidates') or []
        if len(items)!=35:
            messagebox.showwarning('Kayıt sayısı uyuşmuyor',
                f'{len(items)} eksik kayıt bulundu. Tam 35 olduğuna dair kanıt yok. '
                'Yanlış silinme/senkronizasyon hatasını sessizce işaretlemeyeceğim.',
                parent=self.window)
            return
        if not messagebox.askyesno(
            '35 GEÇMİŞ ÇIKTI KAYDI',
            'Aşağıdaki 35 eksik dosyanın tamamını gerçekten SEN mi sildin?\\n'
            'Sadece ledger durumu USER_REMOVED olacak. Eski satır, SHA ve yol kalacak. '
            'Yeni silme veya yeniden üretim yok. Önce SQLite yedeği alınır.',
            parent=self.window):
            return
        phrase=simpledialog.askstring('AÇIK ONAY',REMOVED_CONFIRM,parent=self.window)
        if phrase!=REMOVED_CONFIRM:return
        keys=[item['key'] for item in items]
        self.enqueue(lambda:confirm_deleted(plan,keys,phrase,expected_count=35),
                     lambda result:messagebox.showinfo(
                         '35 kayıt sınıflandırıldı',
                         f"Kayıt: {result['marked']}\\nLedger yedeği: {result['backup']}\\n"
                         'Ürün görsellerine dokunulmadı.',parent=self.window))

    def full_integrity_report(self):
        def work():
            from datetime import datetime
            runtime=Path(self.workspace.get())
            code=Path(self.code.get())
            report_dir=(Path(os.environ.get('LOCALAPPDATA') or Path.home())/
                        'GorselMockup'/'UnifiedCenter'/'FULL_INTEGRITY')
            report_dir.mkdir(parents=True,exist_ok=True)
            audit=audit_everything(runtime,code,production_root=store_v4_root(),
                                   petek_root=petek_store_root())
            result=report_dir/('SISTEM_BUTUNLUK_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'.json')
            audit_save(audit,result)
            return {'report':str(result),'status':audit['status'],
                    'legacy':audit['legacy_templates'],'petek':audit['petek'],
                    'store':audit['stores'],
                    'blocking_findings':len(audit['blockers']),
                    'warnings':len(audit['warnings']),
                    'read_only':True}
        self.enqueue(work,lambda record:messagebox.showinfo(
            'Tam sistem SHA denetimi',
            'Durum: '+record['status']+'\\n'+record['report']+
            '\\nEski klasör silme izni verilmedi.',parent=self.window))

    def run(self):self.window.mainloop()
if __name__=='__main__':Maintenance().run()
