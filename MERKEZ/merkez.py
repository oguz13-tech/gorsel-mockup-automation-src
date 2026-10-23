"""Seven-category single entry point: legacy six review/tools/daily + PETEK.

The legacy corner editor is served from 127.0.0.1:8080, started with the
actual user's original runtime workspace. No data migration/approval happens
in this GUI: on explicit editor start we first create an external SQLite backup.
"""
from __future__ import annotations
import os
import queue
from pathlib import Path
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk,messagebox,scrolledtext,filedialog
import webbrowser

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
VERSION='V4.3 — Grup 1 + Grup 2 (Son Denetim)'

class Center:
    def __init__(self):
        self.root=tk.Tk()
        from dark_theme_v42 import apply_dark_theme
        apply_dark_theme(self.root)
        self.root.title('Görsel Üretim Merkezi '+VERSION+' — 7 Kategori / Tüm Araçlar')
        self.root.geometry('1020x760');self.root.minsize(800,570)
        self.running=False;self.messages=queue.Queue();self.proc=None
        self.batch_windows=[];self.editor_proc=None;self.editor_log=None
        from legacy_manager import preferred_runtime
        self.runtime=preferred_runtime()
        self.inbox_watcher=None
        self.build()
        from help_v42 import bind_help
        bind_help(self.root)
        self.start_auto_inbox()
        self.root.protocol('WM_DELETE_WINDOW',self.close)
        self.root.after(180,self.poll)

    def build(self):
        frame=ttk.Frame(self.root);frame.pack(fill='both',expand=True)
        from dark_theme_v42 import BG, PANEL, FG, MUTED
        canvas=tk.Canvas(frame,highlightthickness=0,background=BG)
        scrollbar=ttk.Scrollbar(frame,orient='vertical',command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right',fill='y');canvas.pack(side='left',fill='both',expand=True)
        p=ttk.Frame(canvas,padding=22)
        handle=canvas.create_window((0,0),window=p,anchor='nw')
        p.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>',lambda e:canvas.itemconfigure(handle,width=e.width))
        self._wheel_canvas=canvas
        def wheel(e):
            if getattr(e,'delta',0):canvas.yview_scroll(int(-e.delta/120),'units')
        canvas.bind_all('<MouseWheel>',wheel)
        ttk.Label(p,text='Görsel Üretim Merkezi '+VERSION,font=('Segoe UI',21,'bold')).pack(anchor='w')
        ttk.Label(p,text='Tek giriş noktası • Eski 6 kategori ve bütün inceleme araçları • PETEK V3 • Kaynakları koru',
                  font=('Segoe UI',10)).pack(anchor='w',pady=(4,10))
        ttk.Separator(p).pack(fill='x',pady=(4,12))
        ttk.Label(p,text='ANA ÇALIŞMA KLASÖRÜ',font=('Segoe UI',11,'bold')).pack(anchor='w')
        line=ttk.Frame(p);line.pack(fill='x',pady=(3,8))
        self.runtime_text=tk.StringVar(value=str(self.runtime))
        ttk.Entry(line,textvariable=self.runtime_text,state='readonly').pack(side='left',fill='x',expand=True)
        ttk.Button(line,text='Klasör seç',command=self.select_runtime).pack(side='left',padx=(8,0))
        ttk.Button(line,text='Klasörü aç',command=self.open_runtime).pack(side='left',padx=(6,0))
        ttk.Separator(p).pack(fill='x',pady=(6,10))
        ttk.Label(p,text='1 — ESKİ 6 KATEGORİ: ŞABLON VE 4 KÖŞE İNCELEME',
                  font=('Segoe UI',12,'bold')).pack(anchor='w',pady=(0,4))
        ttk.Label(p,text='Wi-Fi Kutusu • Cam Tablo Yatay/Dikey • Ahşap Tablo • Cam Doğrama • Ocak Arkası.\n'
                    'İnsan onayları, dört köşe, maske, kategoriler, yedekler, raporlar ve tarama işlemleri burada.',
                  wraplength=920).pack(anchor='w')
        row=ttk.Frame(p);row.pack(fill='x',pady=(9,6))
        self.review_button=ttk.Button(row,text='6 KATEGORİ — ŞABLON / 4 KÖŞE İNCELE',command=self.open_legacy_review)
        self.review_button.pack(side='left',fill='x',expand=True,padx=(0,6))
        self.tools_button=ttk.Button(row,text='6 KATEGORİ — PROFESYONEL ARAÇLAR',command=self.open_legacy_tools)
        self.tools_button.pack(side='left',fill='x',expand=True,padx=(6,0))
        row2=ttk.Frame(p);row2.pack(fill='x',pady=(2,7))
        self.daily=ttk.Button(row2,text='6 KATEGORİ — GÜNLÜK SERİ ÜRETİM (ONAYLI 10 ŞABLON)',command=self.open_daily)
        self.daily.pack(side='left',fill='x',expand=True,padx=(0,6))
        ttk.Button(row2,text='Eski inceleme sunucusunu durdur',command=self.stop_legacy_editor).pack(side='left',padx=(6,0))
        row_v4=ttk.Frame(p);row_v4.pack(fill='x',pady=(2,7))
        ttk.Button(row_v4,text='7 KATEGORİ — TÜM ONAYLI ŞABLONLARLA SERİ ÜRETİM (V4.3)',command=self.open_unified_v4).pack(side='left',fill='x',expand=True,padx=(0,6))
        ttk.Button(row_v4,text='Kesinti / Kilit Kurtarma (V4.3)',command=self.open_crash_recovery).pack(side='left',padx=(6,0))
        ttk.Separator(p).pack(fill='x',pady=(7,10))
        ttk.Label(p,text='2 — PETEK DOLABI: ŞABLON, MASKE VE SERİ ÜRETİM',
                  font=('Segoe UI',12,'bold')).pack(anchor='w',pady=(0,3))
        ttk.Label(p,text='Sabit yarık sayısı yok; her gerçek ahşap panelin kavisleri ve delikleri korunur.\n'
                    'Üst-alt kavis, görünür fırça, otomatik benek onarımı ve doğal ışık motoru dahildir.',
                  wraplength=930).pack(anchor='w')
        r3=ttk.Frame(p);r3.pack(fill='x',pady=(8,10))
        ttk.Button(r3,text='PETEK — ŞABLON / MASKE DÜZENLE',command=self.open_review).pack(side='left',fill='x',expand=True,padx=(0,6))
        ttk.Button(r3,text='PETEK — SERİ GÖRSEL ÜRET',command=self.open_petek).pack(side='left',fill='x',expand=True,padx=(6,0))
        ttk.Separator(p).pack(fill='x',pady=(7,10))
        ttk.Label(p,text='3 — KAYIT, GÜVENLİK VE KURULUM',font=('Segoe UI',12,'bold')).pack(anchor='w')
        tools=ttk.Frame(p);tools.pack(fill='x',pady=(8,9))
        ttk.Button(tools,text='Üretim kayıtlarını denetle',command=self.audit_petek).pack(side='left',fill='x',expand=True)
        ttk.Button(tools,text='PETEK çıktı klasörü',command=self.open_petek_results).pack(side='left',fill='x',expand=True,padx=6)
        ttk.Button(tools,text='7 kategori / kurulum kontrolü',command=self.show_health).pack(side='left',fill='x',expand=True)
        self.status=tk.StringVar(value='Hazır. Eski altı kategori için ŞABLON / 4 KÖŞE İNCELE düğmesini kullan.')
        ttk.Label(p,textvariable=self.status,wraplength=920).pack(anchor='w',pady=(3,5))
        self.log=scrolledtext.ScrolledText(p,height=7,state='disabled',font=('Consolas',9), bg=PANEL, fg=FG, insertbackground=FG)
        self.log.pack(fill='both',expand=True)
        ttk.Label(p,text='Otomatik yeni şablon takibi: YENI-BOS klasörlerine görsel geldiğinde isim + SHA doğrulamasıyla ayrılır.\n'
                    'Çakışmalar incelemeye, mevcut kopyalar ayrı klasöre, yeni şablonlar dört köşe onayına gider.',
                  foreground=MUTED,wraplength=920).pack(anchor='w',pady=(3,3))
        ttk.Label(p,text='Koruma: kaynak görüntüler, orijinal yedek ve onaylı profiller kendiliğinden değiştirilmez.\n'
                    'Günlük V2 hâlen 10 onaylı şablona bağlıdır; bütün şablonlar için üretim geçerlilik kontrolüne tabidir.',
                  foreground=MUTED,wraplength=920).pack(anchor='w',pady=(7,0))

    def start_auto_inbox(self):
        """New-image intake runs automatically while the unified center is open."""
        try:
            if self.inbox_watcher is not None:self.inbox_watcher.stop()
            from inbox_auto_v42 import AutoInboxWatcher
            self.inbox_watcher=AutoInboxWatcher(
                self.runtime,notify=lambda message:self.messages.put(('log',message)),interval=3.0
            )
            self.inbox_watcher.start()
        except Exception as exc:
            self.messages.put(('log','Otomatik yeni görsel izleme başlatılamadı: '+str(exc)))

    def _log(self,value):
        self.log.configure(state='normal');self.log.insert('end',value.rstrip()+'\n')
        self.log.see('end');self.log.configure(state='disabled')

    def select_runtime(self):
        from legacy_manager import store_runtime_choice
        chosen=filedialog.askdirectory(parent=self.root,title='Orijinal GörselÜretme-ve-Mockup Otomasyonu klasörünü seç',initialdir=str(self.runtime.parent))
        if not chosen:return
        try:
            self.runtime=store_runtime_choice(Path(chosen))
            self.runtime_text.set(str(self.runtime))
            self.start_auto_inbox()
            self.status.set('Ana çalışma klasörü seçildi, yeni görseller otomatik izleniyor.')
        except Exception as exc:messagebox.showerror('Klasör geçerli değil',str(exc),parent=self.root)

    def open_runtime(self):
        try:
            if not self.runtime.is_dir():raise FileNotFoundError(str(self.runtime))
            if os.name=='nt':os.startfile(str(self.runtime))
            else:self._log('Ana klasör: '+str(self.runtime))
        except Exception as exc:messagebox.showerror('Ana klasör',str(exc),parent=self.root)

    def show_health(self):
        from legacy_manager import inspect
        from merkez_saglik import report
        legacy=inspect(self.runtime);other=report()
        lines=['ESKİ 6 KATEGORİ — 4 KÖŞE EDİTÖRÜ:',
               'Ana klasör: '+legacy['runtime'],'Kaynak kod: '+legacy['code'],
               'Kaynak: '+legacy['source'],'DB kayıtları: '+str(legacy['counts']),
               'Hazır: '+('EVET' if legacy['ready'] else 'HAYIR'),
               *legacy['problems'],*legacy['warnings'],'',
               '6 KATEGORİ GÜNLÜK V2 (10 ONAYLI ŞABLON):',
               'Hazır: '+('EVET' if other['legacy_ready'] else 'HAYIR'),
               *other['legacy_missing'],'',
               'PETEK:', 'Hazır: '+('EVET' if other['petek_ready'] else 'HAYIR')]
        text='\n'.join(lines)
        self._log('\n'+text)
        messagebox.showinfo('7 kategori çalışma hazırlığı',text,parent=self.root)

    def _open_legacy(self,route):
        from legacy_manager import inspect,backup_database,launch_spec,port_occupied,local_state_dir,LegacyLaunchError
        if self.editor_proc is not None and self.editor_proc.poll() is None:
            webbrowser.open('http://127.0.0.1:8080'+route)
            self.status.set('Eski altı kategori inceleme merkezi açık.')
            return
        if port_occupied():
            messagebox.showwarning('8080 portu dolu',
                '8080 portunu başka bir program kullanıyor. Yanlış arayüze bağlanmamak için otomatik açmıyorum.\n'
                'Önce diğer inceleme uygulamasını kapatın.',parent=self.root)
            return
        s=inspect(self.runtime)
        if not s['ready']:
            messagebox.showerror('6 kategori inceleme başlatılamadı',
                '\n'.join(s['problems'])+'\n\nAna çalışma klasörünü kontrol edin.',parent=self.root)
            return
        if s['warnings']:
            result=messagebox.askokcancel('Eski veritabanı uyarısı',
                '\n'.join(s['warnings'])+'\n\nBaşlatmadan önce bir yedek oluşturulacak. '
                'Eksik şema varsa bazı işlemler açılamayabilir; otomatik migration yapılmaz. Devam?',parent=self.root)
            if not result:return
        try:
            backup=backup_database(self.runtime)
            command,env,cwd=launch_spec(self.runtime)
            logs=local_state_dir()/'LOG';logs.mkdir(parents=True,exist_ok=True)
            output=logs/('inceleme_'+str(int(time.time()))+'_'+os.urandom(3).hex()+'.log')
            log=output.open('x',encoding='utf-8')
            try:
                options={'cwd':cwd,'env':env,'stdout':log,'stderr':subprocess.STDOUT}
                if os.name=='nt':options['creationflags']=getattr(subprocess,'CREATE_NO_WINDOW',0)
                child=subprocess.Popen(command,**options)
            finally:log.close()
            self.editor_proc=child;self.editor_log=output
            self.review_button.configure(state='disabled');self.tools_button.configure(state='disabled')
            self.status.set('Eski 6 kategori inceleme merkezi açılıyor...')
            self._log('SQLite güvenlik yedeği: '+str(backup))
            self._log('Altı kategori kodu: '+str(cwd))
            self._log('Sunucu logu: '+str(output))
            def wait_server():
                from legacy_manager import port_occupied
                for _ in range(75):
                    if child.poll() is not None:break
                    if port_occupied(timeout=.1):
                        self.messages.put(('legacy_started',route));return
                    time.sleep(.16)
                self.messages.put(('legacy_error',str(output)))
            threading.Thread(target=wait_server,daemon=True).start()
        except Exception as exc:
            messagebox.showerror('İnceleme başlatılamadı',str(exc),parent=self.root)
            self._log('İNCELEME HATASI: '+repr(exc))

    def open_legacy_review(self):self._open_legacy('/')
    def open_legacy_tools(self):self._open_legacy('/tools')

    def stop_legacy_editor(self):
        if self.editor_proc is None or self.editor_proc.poll() is not None:
            messagebox.showinfo('Eski inceleme','Bu merkez tarafından başlatılmış çalışan sunucu yok.',parent=self.root);return
        if not messagebox.askyesno('İnceleme sunucusunu durdur',
                                  'Dört köşe/şablon kaydını tamamladın mı?\n'
                                  'Devam eden analiz işleriniz varsa sunucuyu durdurmayın.',parent=self.root):return
        try:
            self.editor_proc.terminate();self.editor_proc.wait(timeout=5)
            self._log('İnceleme sunucusu kullanıcı isteğiyle kapatıldı.')
            self.status.set('Eski inceleme kapatıldı. Onaylı veriler korunuyor.')
        except Exception as exc:self._log('İnceleme kapatma uyarısı: '+str(exc))
        finally:self.review_button.configure(state='normal');self.tools_button.configure(state='normal')

    def open_daily(self):
        from merkez_saglik import report
        state=report()
        if not state['legacy_ready']:
            messagebox.showwarning('Günlük V2 — referanslar eksik',
                 'Günlük V2 yalnızca sabit kod/yedek SHA eşleşmesiyle çalışır.\n\n'
                 +'\n'.join(state['legacy_missing'])+'\n\n'
                 'Ancak 6 kategorinin 4 köşe inceleme arayüzü yukarıdan ayrıca açılabilir.',parent=self.root)
            return
        self.start([sys.executable,'-B',str(HERE/'GUNLUK'/'run.py')],'Altı kategori günlük V2')

    def open_review(self):
        try:
            from PETEK_V3.gui import open_mask_editor
            open_mask_editor(self.root)
        except Exception as exc:messagebox.showerror('PETEK maske açılmadı',str(exc),parent=self.root)

    def open_petek(self):
        try:
            from PETEK_V3.gui import open_batch_window
            self.batch_windows.append(open_batch_window(self.root))
        except Exception as exc:messagebox.showerror('PETEK seri üretim açılmadı',str(exc),parent=self.root)

    def open_unified_v4(self):
        try:
            from URETIM_V4.gui_v4 import open_unified_v4_window
            self.batch_windows.append(open_unified_v4_window(self.root, runtime_root=self.runtime))
        except Exception as exc:messagebox.showerror('V4 7 Kategori seri üretim açılmadı',str(exc),parent=self.root)

    def open_crash_recovery(self):
        try:
            from URETIM_V4.gui_v4 import open_unified_v4_window
            win = open_unified_v4_window(self.root, runtime_root=self.runtime)
            self.batch_windows.append(win)
            win.open_recovery()
        except Exception as exc:messagebox.showerror('Kesinti kurtarma açılmadı',str(exc),parent=self.root)

    def start(self,command,route):
        if self.running:return
        self.running=True;self.daily.configure(state='disabled')
        self.status.set(route+' başlatıldı; ayrıca açılan pencereden üretimi izle.')
        def job():
            try:
                env=dict(os.environ,PYTHONUTF8='1',PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1')
                self.proc=subprocess.Popen(command,cwd=HERE,env=env,stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace')
                for line in self.proc.stdout:self.messages.put(('log',line))
                self.messages.put(('done',(route,self.proc.wait())))
            except Exception as exc:self.messages.put(('done',(route,str(exc))))
        threading.Thread(target=job,daemon=True).start()

    def poll(self):
        try:
            while True:
                kind,value=self.messages.get_nowait()
                if kind=='log':self._log(value)
                elif kind=='done':
                    route,code=value;self.running=False;self.proc=None
                    self.daily.configure(state='normal')
                    self.status.set(route+' işlemi sonlandı: '+str(code))
                elif kind=='legacy_started':
                    self.review_button.configure(state='normal');self.tools_button.configure(state='normal')
                    self.status.set('6 kategori inceleme + profesyonel araçlar hazır: 127.0.0.1:8080')
                    webbrowser.open('http://127.0.0.1:8080'+value)
                elif kind=='legacy_error':
                    self.review_button.configure(state='normal');self.tools_button.configure(state='normal')
                    try:excerpt=Path(value).read_text(encoding='utf-8',errors='replace')[-1900:]
                    except OSError:excerpt='Günlük dosyası okunamadı.'
                    self._log('ESKİ İNCELEME BAŞLATMA HATASI\n'+excerpt)
                    self.status.set('Eski inceleme başlatılamadı; hata logunu kontrol et.')
                    messagebox.showerror('İnceleme açılmadı',excerpt or 'Sunucu yanıt vermedi.',parent=self.root)
        except queue.Empty:pass
        self.root.after(180,self.poll)

    def audit_petek(self):
        try:
            from petek_denetle import run_audit
            report,path=run_audit();summary=report['summary']
            self.status.set('PETEK üretim denetimi: {verified}/{total} doğru; {review_required} inceleme gerekiyor.'.format(**summary))
            self._log('Güvenlik denetimi: '+str(path))
            for item in summary['issues']:self._log('KONTROL_GEREKENLER: '+str(item))
        except Exception as exc:messagebox.showerror('Üretim kayıtları denetlenemedi',str(exc),parent=self.root)

    def open_petek_results(self):
        try:
            from PETEK_V3.registry import store_root
            folder=store_root()
            if folder.is_dir():
                if os.name=='nt':os.startfile(str(folder))
                else:self._log(str(folder))
            else:messagebox.showinfo('İlk üretim gerekli','PETEK kayıt klasörü henüz yok.',parent=self.root)
        except Exception as exc:messagebox.showerror('Çıktı klasörü açılmadı',str(exc),parent=self.root)

    def close(self):
        if any(getattr(win,'worker',None) and win.worker.is_alive() for win in self.batch_windows):
            messagebox.showinfo('PETEK işi devam ediyor','Seri üretimde güvenli durdurmayı kullanın.',parent=self.root);return
        if self.running:
            messagebox.showinfo('Günlük üretim devam ediyor','Günlük işlemi güvenli olarak bitirin.',parent=self.root);return
        if self.editor_proc is not None and self.editor_proc.poll() is None:
            messagebox.showinfo('Altı kategori inceleme açık',
                'Eski inceleme merkezi çalışıyor. Önce bu penceredeki "Eski inceleme sunucusunu durdur" düğmesini kullanın.',parent=self.root)
            return
        if self.inbox_watcher is not None:self.inbox_watcher.stop()
        self.root.destroy()

if __name__=='__main__':Center().root.mainloop()