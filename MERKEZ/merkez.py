"""Seven-category single entry point: legacy six review/tools/daily + PETEK.

The legacy corner editor uses an authenticated available localhost port, started with the
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
from version_v46 import TITLE as VERSION

class Center:
    def __init__(self):
        self.root=tk.Tk()
        from dark_theme_v42 import apply_dark_theme
        apply_dark_theme(self.root)
        self.root.title('Görsel Üretim Merkezi '+VERSION+' — 7 Kategori / Tüm Araçlar')
        self.root.geometry('1020x760');self.root.minsize(800,570)
        self.running=False;self.messages=queue.Queue();self.proc=None
        self.batch_windows=[];self.editor_proc=None;self.editor_log=None;self.editor_port=8080
        from legacy_manager import preferred_runtime
        self.runtime=preferred_runtime()
        self.inbox_watcher=None
        self.ham_design_watcher=None
        self.build()
        from help_v42 import bind_help
        bind_help(self.root)
        # PETEK is a first-class physical category in the selected runtime.
        # Create-only bootstrap precedes the auto-inbox watcher; no images,
        # masks, approvals or SQLite records are migrated by this step.
        self.root.after(0,self.ensure_petek_workspace)
        self.root.after(150,self.start_auto_ham_designs)
        self.root.after(400,self.start_auto_inbox)
        self.root.protocol('WM_DELETE_WINDOW',self.close)
        self.root.after(180,self.poll)

    def build(self):
        """Single-purpose home: two everyday actions, the rest under Advanced."""
        from dark_theme_v42 import BG, PANEL, FG, MUTED
        style=ttk.Style(self.root)
        for name,background,font,size in (
            ('Center.Primary.TButton','#0e7490',('Segoe UI',12,'bold'),(16,15)),
            ('Center.Secondary.TButton','#334155',('Segoe UI',11,'bold'),(12,11)),
            ('Center.Small.TButton','#344256',('Segoe UI',10), (10,8))):
            style.configure(name,background=background,foreground='#f8fafc',
                            padding=size,borderwidth=0,font=font)
            style.map(name,background=[('active','#0f94b6'),('disabled','#364253')])
        style.configure('Center.Card.TFrame',background='#232d3b')
        style.configure('Center.Header.TFrame',background='#172b3c')
        style.configure('Center.Title.TLabel',background='#172b3c',foreground='#f8fafc',
                        font=('Segoe UI',19,'bold'))
        style.configure('Center.Subtitle.TLabel',background='#172b3c',foreground='#cbd5e1',
                        font=('Segoe UI',11))
        style.configure('Center.Heading.TLabel',background='#232d3b',foreground='#f1f5f9',
                        font=('Segoe UI',13,'bold'))
        style.configure('Center.Info.TLabel',background='#232d3b',foreground='#cbd5e1',
                        font=('Segoe UI',11))
        style.configure('Center.Status.TLabel',background='#172d31',foreground='#b8f7e0',
                        font=('Segoe UI',11),padding=(12,10))
        style.configure('Center.Path.TEntry',fieldbackground='#111d2b',foreground='#f8fafc',
                        padding=9,font=('Segoe UI',11))
        self.root.geometry('1080x800')
        self.root.minsize(870,600)
        frame=ttk.Frame(self.root);frame.pack(fill='both',expand=True)
        canvas=tk.Canvas(frame,highlightthickness=0,background=BG)
        scrollbar=ttk.Scrollbar(frame,orient='vertical',command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right',fill='y');canvas.pack(side='left',fill='both',expand=True)
        p=ttk.Frame(canvas,padding=18)
        handle=canvas.create_window((0,0),window=p,anchor='nw')
        p.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>',lambda e:canvas.itemconfigure(handle,width=e.width))
        self._wheel_canvas=canvas
        def wheel(e):
            if getattr(e,'delta',0) and canvas.winfo_ismapped():
                canvas.yview_scroll(int(-e.delta/120),'units')
        canvas.bind('<MouseWheel>',wheel)
        def card():
            x=ttk.Frame(p,style='Center.Card.TFrame',padding=17)
            x.pack(fill='x',pady=(0,13))
            return x
        def label(parent,header,desc):
            ttk.Label(parent,text=header,style='Center.Heading.TLabel').pack(anchor='w')
            ttk.Label(parent,text=desc,style='Center.Info.TLabel',
                      wraplength=910,justify='left').pack(anchor='w',pady=(5,12))
        def actions(parent,items):
            rail=ttk.Frame(parent,style='Center.Card.TFrame');rail.pack(fill='x')
            buttons=[]
            for title,callback,primary in items:
                btn=ttk.Button(rail,text=title,command=callback,
                     style='Center.Primary.TButton' if primary else 'Center.Secondary.TButton')
                btn.pack(side='left',fill='x',expand=True,padx=(0,9))
                buttons.append(btn)
            return buttons

        banner=ttk.Frame(p,style='Center.Header.TFrame',padding=20)
        banner.pack(fill='x',pady=(0,13))
        ttk.Label(banner,text='Görsel Üretim Merkezi',style='Center.Title.TLabel').pack(anchor='w')
        ttk.Label(banner,text=VERSION+'   ·   7 kategori   ·   Tek çalışma alanı',
                  style='Center.Subtitle.TLabel').pack(anchor='w',pady=(6,3))
        ttk.Label(banner,text='Şablonları onayla, ham baskı tasarımlarını yönet, mağazalara mockup üret.',
                  style='Center.Subtitle.TLabel').pack(anchor='w')

        location=card()
        label(location,'01  Ana Çalışma Alanı',
              'Seçili klasörde şablonlar, kaynaklar ve onaylar korunur. Yeni kod paketleri bu verilerin üzerine açılmaz.')
        location_bar=ttk.Frame(location,style='Center.Card.TFrame');location_bar.pack(fill='x')
        self.runtime_text=tk.StringVar(value=str(self.runtime))
        ttk.Entry(location_bar,textvariable=self.runtime_text,state='readonly',
                  style='Center.Path.TEntry').pack(side='left',fill='x',expand=True,padx=(0,8))
        ttk.Button(location_bar,text='Değiştir',command=self.select_runtime,
                   style='Center.Small.TButton').pack(side='left',padx=3)
        ttk.Button(location_bar,text='Klasörü Aç',command=self.open_runtime,
                   style='Center.Small.TButton').pack(side='left',padx=3)

        daily=card()
        label(daily,'02  Günlük İşlemler',
              'PETEK dahil yedi kategori için tek şablon inceleme merkezi ve tek seri üretim merkezi.')
        self.review_button,production_button=actions(daily,[
          ('Şablonları İncele ve Onayla',self.open_legacy_review,True),
          ('Seri Mockup Üretimi',self.open_unified_v4,True)])
        ttk.Label(daily,text='Dört köşe, PETEK maskesi ve toplu köşe tespiti ilk ekranda; '
                  'mağazalar, 4K ve Excel bağlantıları üretim ekranında.',
                  style='Center.Info.TLabel',wraplength=900).pack(anchor='w',pady=(11,0))

        designs=card()
        label(designs,'03  Ham Baskı Tasarımları',
              'Yeni dosyaları veya alt klasörleri buraya ekle. Sistem Ham1, Ham2… diye otomatik numaralandırır.')
        actions(designs,[
          ('HAM Tasarım Klasörünü Aç',self.open_ham_design_folder,False),
          ('Numara ve Dosya Sorunlarını Kontrol Et',self.show_ham_design_audit,False)])
        self.ham_home_status=tk.StringVar(value='Otomatik izleme: açılışta devreye girer.')
        ttk.Label(designs,textvariable=self.ham_home_status,style='Center.Info.TLabel',
                  wraplength=900).pack(anchor='w',pady=(10,0))

        self.status=tk.StringVar(value='Hazır. Mevcut şablonlar ve onaylı maskeler korunur.')
        ttk.Label(p,textvariable=self.status,style='Center.Status.TLabel',
                  wraplength=950).pack(fill='x',pady=(0,12))

        self.advanced_toggle=ttk.Button(p,text='▶ Diğer Araçlar ve Kurtarma',
            style='Center.Secondary.TButton',command=self.toggle_advanced)
        self.advanced_toggle.pack(fill='x',pady=(0,7))
        self.advanced_panel=ttk.Frame(p,style='Center.Card.TFrame',padding=14)
        label(self.advanced_panel,'İleri Araçlar',
              'Eski özel ekranlar burada saklanır. Aynı işi yapan düğmeler ana menüyü kalabalıklaştırmaz.')
        self.tools_button,check_button=actions(self.advanced_panel,[
          ('Profesyonel Araçlar / İsimlendirici',self.open_legacy_tools,False),
          ('PETEK Klasörlerini Denetle',self.prepare_petek_folders,False)])
        advanced=[
          (('PETEK — Eski Ayrı Maske Editörü',self.open_review),
           ('PETEK — Eski Ayrı Üretim',self.open_petek)),
          (('7 Kategori SHA Denetimi',self.open_unified_audit),
           ('PETEK Geçmiş Çıktı Denetimi',self.audit_petek)),
          (('Kurulum / SQLite Durumu',self.show_health),
           ('Kesinti ve Kilit Kurtarma',self.open_crash_recovery)),
          (('PETEK Çıktı Klasörü',self.open_petek_results),
           ('İnceleme Servisini Durdur',self.stop_legacy_editor)),
          (('Silinen Çıktı Kayıtlarını Koruma',self.archive_user_deleted_outputs),
           ('G3 Salt Okunur Bütünlük Kontrolü',self.g3_audit)),
          (('Magenta Dosya Denetimi',self.open_consolidation),
           ('Magenta LAB Güvenli Değiştir / Yeniden Onay',self.open_magenta_replace_v486)),
          (('SQLite Güvenli Yedek ve Geri Yükleme Provası',self.g3_backup),)
        ]
        for line in advanced:
            actions(self.advanced_panel,[(title,fn,False) for title,fn in line])
            ttk.Frame(self.advanced_panel,style='Center.Card.TFrame',height=6).pack(fill='x')
        ttk.Label(self.advanced_panel,text='Eski PETEK bağımsız editörü uyumluluk içindir; '
                  'günlük işlemlerde üstteki birleşik şablon inceleme düğmesini kullan.',
                  style='Center.Info.TLabel',wraplength=900).pack(anchor='w',pady=6)

        history=card()
        label(history,'04  İşlem Günlüğü',
              'Şablon, HAM numarası, dosya çakışması ve servis durumları.')
        self.log=scrolledtext.ScrolledText(history,height=7,state='disabled',
                 font=('Consolas',10),bg='#111f2d',fg=FG,insertbackground=FG,
                 padx=10,pady=8,relief='flat',borderwidth=0,wrap='word')
        self.log.pack(fill='both',expand=True)
        ttk.Label(p,text='Veri koruma: onaylı şablon ve maskeler kendiliğinden değiştirilmez. '
                  'Program sürümü ayrı, ana çalışma klasörün ayrıdır.',
                  foreground=MUTED,wraplength=960).pack(anchor='w',pady=(4,10))

    def open_magenta_replace_v486(self):
        """Separate preview-first tool; NEVER apply photos without typed consent."""
        try:
            tool=ROOT/'MAGENTA_TOPLU_GUVENLI_DEGISTIR_WINDOWS.bat'
            if os.name!='nt' or not tool.is_file():
                raise RuntimeError('MAGENTA_WINDOWS_TOOL_NOT_FOUND')
            os.startfile(str(tool))
            self._log('Magenta LAB ayrı güvenli aktarım aracı başlatıldı. '+
                      'Rapor ve yan yana önizlemeyi görmeden dosyalar değişmez.')
        except (OSError,RuntimeError) as exc:
            messagebox.showerror('Magenta aracı açılamadı',str(exc),parent=self.root)

    def open_consolidation(self):
        """Independent utility; editor or batch must be stopped before APPLY."""
        try:
            executable=ROOT/'BAKIM_V472_MAGENTA_KLASOR_DENETIM_WINDOWS.bat'
            if os.name=='nt' and executable.is_file():
                os.startfile(str(executable))
            else:
                from bakim_merkezi_v472 import Maintenance
                Maintenance().run()
            self._log('Magenta ve eski sürüm dosya denetimi ayrı pencerede açıldı.')
        except Exception as exc:
            messagebox.showerror('Bakım merkezi açılamadı',str(exc),parent=self.root)

    def g3_audit(self):
        """Only reads live databases, original folders and local output receipts."""
        try:
            import json
            from URETIM_V4.final_guard_v44 import inspect_workspaces
            summary = inspect_workspaces(self.runtime)
            pretty = json.dumps(summary, ensure_ascii=False, indent=2)
            self._log('G3 salt-okunur denetim:\n' + pretty)
            messagebox.showinfo('G3 Veri / SHA denetimi', pretty[:3500], parent=self.root)
        except Exception as exc:
            messagebox.showerror('G3 salt-okunur denetim başarısız', str(exc), parent=self.root)

    def g3_backup(self):
        """Operator-approved online backups; no live DB migration or restore."""
        if not messagebox.askyesno('G3 - açık onay gerekli',
                'Mevcut onaylı şablon veritabanı ve üretim kayıt veritabanının '
                'yerel, senkronize olmayan klasöre ayrı SQLite yedekleri alınacak. '
                'Yedeklerin KOPYASI ile geri yükleme provası yapılacak. '
                'Canlı dosyalar değiştirilmeyecek. Devam edilsin mi?',parent=self.root):
            return
        try:
            from URETIM_V4.final_guard_v44 import backup_and_restore_trial, BACKUP_CONFIRM
            info = backup_and_restore_trial(self.runtime, confirm=BACKUP_CONFIRM)
            report = info['report_path']
            self._log('G3 iki DB güvenli yedek + prova PASS: ' + report)
            messagebox.showinfo('G3 yedek doğrulandı',
                'Her iki SQLite dosyası tutarlı yedeklendi ve izole geri yükleme provasını geçti.\n'
                'Kanıt raporu: ' + report, parent=self.root)
        except Exception as exc:
            messagebox.showerror('G3 güvenli yedek başarısız', str(exc), parent=self.root)

    def toggle_advanced(self):
        """Keep rarely used maintenance actions available without crowding the UI."""
        if self.advanced_panel.winfo_manager():
            self.advanced_panel.pack_forget()
            self.advanced_toggle.configure(text='▶ Diğer Araçlar ve Kurtarma')
        else:
            self.advanced_panel.pack(fill='x',pady=(2,8),after=self.advanced_toggle)
            self.advanced_toggle.configure(text='▼ Diğer Araçlar ve Kurtarma')

    def show_ham_design_audit(self):
        try:
            from ham_designs_v487 import HamDesignVault
            v=self.ham_design_watcher.vault if self.ham_design_watcher else HamDesignVault(self.runtime)
            report=v.audit()
            self.ham_home_status.set('Son HAM numarası: '+str(report['high'])+
                '   ·   Kayıtlı: '+str(report['registered'])+
                '   ·   Kontrol: '+str(len(report['issues'])+len(report['unregistered'])))
            if report['issues'] or report['unregistered']:
                detail=str(report['issues'][:8]+
                           [{'type':'KAYITSIZ','file':name} for name in report['unregistered'][:5]])
                messagebox.showwarning('HAM tasarım kontrolü',detail,parent=self.root)
                self._log('HAM BASKI DENETIM: '+detail)
            else:
                messagebox.showinfo('HAM tasarım kontrolü',
                    'Kayıtlı numaralar tutarlı. Son numara: '+str(report['high']),
                    parent=self.root)
        except (OSError,ValueError,RuntimeError) as exc:
            messagebox.showerror('HAM tasarım denetimi',str(exc),parent=self.root)

    def start_auto_ham_designs(self):
        """Separate automatic HAM design watcher, never an old template watcher.

        The numbered design pool starts as soon as the main center opens and
        remains usable even when the classic six-category intake is declined.
        """
        try:
            if self.ham_design_watcher is not None:
                self.ham_design_watcher.stop()
                self.ham_design_watcher=None
            from ham_designs_v487 import HamDesignWatcher
            self.ham_design_watcher=HamDesignWatcher(
                self.runtime,notify=lambda message:self.messages.put(('log',message)),interval=3.0)
            self.ham_design_watcher.start()
            report=self.ham_design_watcher.vault.audit()
            if hasattr(self,'ham_home_status'):
                self.ham_home_status.set('Otomatik izleme aktif · Son numara: '+str(report['high'])+
                    ' · Kontrol: '+str(len(report['issues'])+len(report['unregistered'])))
            self._log('HAM BASKI TASARIMLARI otomatik takip aktif. Son numara: '+
                      str(report['high'])+'; klasör: '+report['path'])
            for issue in report['issues'][:6]:
                self._log('HAM TASARIM KONTROL: '+str(issue))
        except (OSError,ValueError,RuntimeError) as exc:
            self.messages.put(('log','⚠️ HAM TASARIM IZLEME AÇILAMADI: '+str(exc)))

    def open_ham_design_folder(self):
        try:
            from ham_designs_v487 import HamDesignVault
            vault=(self.ham_design_watcher.vault if self.ham_design_watcher is not None
                   else HamDesignVault(self.runtime))
            info=vault.audit()
            self._log('HAM NUMARA DURUMU: '+str(info))
            if info['issues']:
                messagebox.showwarning('HAM TASARIM UYARISI',
                    str(info['issues'][:5])+'\\nMevcut dosyalara otomatik müdahale edilmedi.',
                    parent=self.root)
            if os.name=='nt':os.startfile(str(vault.folder))
            else:self._log('HAM KLASÖRÜ: '+str(vault.folder))
        except (OSError,ValueError,RuntimeError) as exc:
            messagebox.showerror('HAM TASARIM KLASÖRÜ',str(exc),parent=self.root)

    def start_auto_inbox(self):
        """New-image intake runs automatically while the unified center is open."""
        try:
            from legacy_manager import inspect,backup_database
            state=inspect(self.runtime)
            if not state['ready']:
                self._log('Yeni görsel izleme kapalı: '+ '; '.join(state['problems']))
                return
            if not messagebox.askyesno('Yeni görsel alımını etkinleştir',
                    'Seçili çalışma klasörünün SQLite yedeği alınacak ve ayrı kopyada geri yükleme provası yapılacak. Ardından yalnız yeni görseller güvenli alıma açılacak. Mevcut onaylar değiştirilmez. Devam?',parent=self.root):
                return
            backup_database(self.runtime)
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
        if self.editor_proc is not None and self.editor_proc.poll() is None:
            messagebox.showwarning('Önce incelemeyi kapatın', 'Çalışma klasörünü değiştirmeden önce bu merkezden inceleme sunucusunu durdurun.', parent=self.root)
            return
        chosen=filedialog.askdirectory(parent=self.root,title='Orijinal GörselÜretme-ve-Mockup Otomasyonu klasörünü seç',initialdir=str(self.runtime.parent))
        if not chosen:return
        try:
            self.runtime=store_runtime_choice(Path(chosen))
            self.start_auto_ham_designs()
            self.runtime_text.set(str(self.runtime))
            petek_ready = self.ensure_petek_workspace()
            self.start_auto_inbox()
            self.status.set('Ana çalışma klasörü seçildi; PETEK klasörleri '+
                            ('doğrulandı.' if petek_ready else 'engeli için işlem günlüğünü kontrol edin.'))
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
        lines=['7 KATEGORİ — 4 KÖŞE + PETEK MASKE EDİTÖRÜ:',
               'Ana klasör: '+legacy['runtime'],'Kaynak kod: '+legacy['code'],
               'Kaynak: '+legacy['source'],'DB kayıtları: '+str(legacy['counts']),
               'Hazır: '+('EVET' if legacy['ready'] else 'HAYIR'),
               *legacy['problems'],*legacy['warnings'],'',
               'PETEK:', 'Hazır: '+('EVET' if other['petek_ready'] else 'HAYIR')]
        text='\n'.join(lines)
        self._log('\n'+text)
        messagebox.showinfo('7 kategori çalışma hazırlığı',text,parent=self.root)

    def _open_legacy(self,route):
        from legacy_manager import inspect,backup_database,launch_spec,local_state_dir,port_occupied
        from review_port_owner_v478 import ensure_canonical_8080,PortOwnerError
        if self.editor_proc is not None and self.editor_proc.poll() is None:
            from legacy_manager import server_identity_diagnostic
            runtime,code,token=self.editor_identity
            identity = server_identity_diagnostic(runtime, code, self.editor_proc.pid, token,
                                                  port=self.editor_port)
            if not identity['ready']:
                detail = self._safe_identity_error(identity)
                self._log('İnceleme servisi kimlik kontrolü: '+detail)
                messagebox.showerror('Sunucu doğrulanamadı',
                    detail+'\n\nBu merkezin başlattığı servisi Gelişmiş Araçlar > 4 Köşe Servisini Durdur ile durdurup tekrar açın. Bilinmeyen süreci kapatmayın.',
                    parent=self.root)
                return
            webbrowser.open(f'http://127.0.0.1:{self.editor_port}'+route)
            self.status.set('Dört köşe inceleme merkezi açık.')
            return
        # One canonical URL: never run a second 8081-8090 editor in parallel.
        editor_port=8080
        s=inspect(self.runtime)
        if not s['ready']:
            messagebox.showerror('7 kategori inceleme başlatılamadı',
                '\n'.join(s['problems'])+'\n\nAna çalışma klasörünü kontrol edin.',parent=self.root)
            return
        if s['warnings']:
            result=messagebox.askokcancel('Eski veritabanı uyarısı',
                '\n'.join(s['warnings'])+'\n\nBaşlatmadan önce bir yedek oluşturulacak. '
                'Eksik şema varsa bazı işlemler açılamayabilir; otomatik migration yapılmaz. Devam?',parent=self.root)
            if not result:return
        if not messagebox.askyesno('İncelemeyi aç', 'Seçili veritabanının yedeği ve izole geri yükleme provası tamamlandıktan sonra editör açılacak. Kaydetme yalnız sizin işlemlerinizle yapılır. Devam?',parent=self.root):
            return
        try:
            backup=backup_database(self.runtime)
            try:
                reclaimed=ensure_canonical_8080(occupied=lambda:port_occupied(port=8080))
            except PortOwnerError as exc:
                self._log('8080 KORUMA: '+str(exc))
                messagebox.showerror('8080 kullanımda — güvenli devir engeli',
                    '8080 kullanan süreç bize ait güvenli eski inceleme sunucusu olarak doğrulanamadı '
                    'veya üzerinde aktif bir analiz var. Hiçbir program kapatılmadı.\\n\\n'
                    +str(exc)+'\\n\\nEski şablon inceleme penceresini güvenli durdurup tekrar deneyin.',
                    parent=self.root)
                return
            if reclaimed['reclaimed']:
                self._log('8080 onaylı eski inceleme sunucusundan devralındı; eski PID: '+
                          str(reclaimed['pid']))
            command,env,cwd=launch_spec(self.runtime)
            env['MOCKUP_CENTER_TOKEN']=os.urandom(32).hex()
            env['MOCKUP_PORT']=str(editor_port)
            self.editor_identity=(self.runtime,cwd,env['MOCKUP_CENTER_TOKEN'])
            logs=local_state_dir()/'LOG';logs.mkdir(parents=True,exist_ok=True)
            output=logs/('inceleme_'+str(int(time.time()))+'_'+os.urandom(3).hex()+'.log')
            log=output.open('x',encoding='utf-8')
            try:
                options={'cwd':cwd,'env':env,'stdout':log,'stderr':subprocess.STDOUT}
                if os.name=='nt':options['creationflags']=getattr(subprocess,'CREATE_NO_WINDOW',0)
                child=subprocess.Popen(command,**options)
            finally:log.close()
            self.editor_proc=child;self.editor_log=output;self.editor_port=editor_port
            self.review_button.configure(state='disabled');self.tools_button.configure(state='disabled')
            self.status.set(f'7 kategori şablon/maske incelemesi açılıyor: 127.0.0.1:{editor_port}')
            self._log('SQLite güvenlik yedeği: '+str(backup))
            self._log('Altı kategori kodu: '+str(cwd))
            self._log('Sunucu logu: '+str(output))
            def wait_server():
                from legacy_manager import server_identity_diagnostic
                last={'ready':False,'reason':'NOT_CHECKED'}
                # A slow Windows/OneDrive machine can need extra startup time.
                # A 200 response alone is NOT proof this process belongs to us.
                for _ in range(50):
                    if child.poll() is not None:
                        last={'ready':False,'reason':'EDITOR_PROCESS_EXITED',
                              'exit_code':child.returncode}
                        break
                    last=server_identity_diagnostic(
                        self.runtime,cwd,child.pid,env['MOCKUP_CENTER_TOKEN'],
                        port=editor_port)
                    if last['ready']:
                        self.messages.put(('legacy_started',route));return
                    time.sleep(.25)
                self.messages.put(('legacy_error',(str(output),last)))
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
            from legacy_manager import server_identity_diagnostic
            runtime,code,token=self.editor_identity
            check=server_identity_diagnostic(runtime,code,self.editor_proc.pid,token,
                                             port=self.editor_port,include_pid=True)
            if not check['ready']:
                raise RuntimeError('İnceleme kimliği doğrulanamadı; süreç kapatılmadı: '+
                                   str(check.get('reason')))
            actual_pid=check['actual_pid']
            if os.name=='nt' and actual_pid!=self.editor_proc.pid:
                # A Windows venv launcher is a redirector; terminating it alone
                # leaves Flask listening on 8080. Stop only the authenticated
                # child PID with the matching secret and both directory roots.
                finished=subprocess.run(['taskkill.exe','/PID',str(actual_pid),'/F'],
                    capture_output=True,text=True,timeout=6,
                    creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                if finished.returncode:
                    raise RuntimeError('Doğrulanan Flask çocuk süreci kapatılamadı.')
                self.editor_proc.wait(timeout=6)
            else:
                self.editor_proc.terminate();self.editor_proc.wait(timeout=5)
            self._log('Doğrulanan inceleme sunucusu kullanıcı isteğiyle tamamen kapatıldı.')
            self.status.set('8080 inceleme servisi kapatıldı. Onaylı veriler korunuyor.')
        except Exception as exc:self._log('İnceleme kapatma uyarısı: '+str(exc))
        finally:self.review_button.configure(state='normal');self.tools_button.configure(state='normal')

    def open_daily(self):
        from merkez_saglik import report
        state=report()
        if not state['legacy_ready']:
            messagebox.showwarning('Günlük V2 — referanslar eksik',
                 'Günlük V2 yalnızca sabit kod/yedek SHA eşleşmesiyle çalışır.\n\n'
                 +'\n'.join(state['legacy_missing'])+'\n\n'
                 '7 kategori şablon/maske inceleme arayüzü yukarıdan ayrıca açılabilir.',parent=self.root)
            return
        self.start([sys.executable,'-B',str(HERE/'GUNLUK'/'run.py')],'Altı kategori günlük V2')

    def ensure_petek_workspace(self):
        """Safe, idempotent PETEK folder bootstrap in the selected data root.

        Creates only missing directories in the three existing work sections.
        Old approved photos, DB, masks and registry stay untouched. A populated
        legacy alias is reported, never silently renamed, merged or deleted.
        """
        try:
            from petek_folders_v46 import prepare_petek_folders
            prepared = prepare_petek_folders(self.runtime)
            if prepared['created']:
                self._log('PETEK kategori klasörleri güvenle oluşturuldu (yalnız boş klasör):\\n'+
                          '\\n'.join(prepared['created']))
            aliases = [p for p in prepared['paths'].values()
                       if Path(p).name != 'Petek_Dolabi']
            if aliases:
                self._log('PETEK ESKİ KLASÖR ADI KULLANIMDA; dosya taşınmadı: '+
                          '; '.join(aliases))
            return prepared
        except (OSError, ValueError) as exc:
            self._log('PETEK KLASÖRÜ OTOMATİK HAZIRLANAMADI (eski veriler korunuyor): '+str(exc))
            return None

    def prepare_petek_folders(self):
        try:
            from petek_folders_v46 import prepare_petek_folders
            from tkinter import messagebox
            if not messagebox.askyesno('PETEK klasörleri',
                    'Yeni Boş, çalışma ve orijinal yedekte mevcut PETEK klasörleri taranacak. '
                    'Eksik olanlar oluşturulacak. Hiçbir görsel taşınmayacak veya silinmeyecek. Devam?',
                    parent=self.root):
                return
            result=prepare_petek_folders(self.runtime)
            details='\\n'.join(f'{section}: {path}' for section,path in result['paths'].items())
            self._log('PETEK KLASÖR HARİTASI\\n'+details)
            messagebox.showinfo('PETEK klasör entegrasyonu',
                f'Oluşturulan yeni klasör: {len(result["created"])}\\n\\n'+details+
                '\\n\\nMaske ve onaylar yerel AppData/PetekV3 içinde korunuyor.',parent=self.root)
        except Exception as exc:
            messagebox.showerror('PETEK klasör engeli',str(exc),parent=self.root)

    def archive_user_deleted_outputs(self):
        try:
            from URETIM_V4.user_removed_v46 import (
                missing_user_candidates, acknowledge_user_deleted)
            from URETIM_V4.final_guard_v44 import store_v4_root
            prod=store_v4_root()
            missing=missing_user_candidates(prod)
            if not missing:
                messagebox.showinfo('Silinen çıktılar','Kayıtlı fakat eksik çıktı bulunmadı.',parent=self.root)
                return
            if not messagebox.askyesno('BİLEREK SİLİNDİ — AÇIK ONAY',
                    f'{len(missing)} üretim kaydının çıktı dosyası eksik.\\n\\n'
                    'Bu dosyaların tamamını KENDİNİZİN BİLEREK SİLDİĞİNİ ONAYLIYOR MUSUNUZ?\\n\\n'
                    'Önce her iki SQLite yedeklenip geri yükleme provası yapılacak. '
                    'Kayıtlar silinmeyecek; USER_REMOVED olarak tarihçede saklanacak. '
                    'Bu işlem hiçbir görseli silmez, yeniden üretmez.',parent=self.root):
                return
            result=acknowledge_user_deleted(prod,self.runtime,
                expected_keys=[row['key'] for row in missing],
                confirm='I_CONFIRM_THESE_FILES_WERE_DELETED_BY_ME')
            self._log('BİLEREK SİLİNEN ÇIKTI KAYITLARI: '+str(result))
            messagebox.showinfo('Üretim geçmişi korundu',
                f'{result["count"]} kayıt USER_REMOVED durumuna alındı.\\n'
                'Dosyalar ve diğer üretimler değiştirilmedi.\\n'
                'Rapor: '+result['report_path'],parent=self.root)
        except Exception as exc:
            messagebox.showerror('Silinen çıktı kayıtları işlenemedi',str(exc),parent=self.root)

    def open_review(self):
        try:
            from PETEK_V3.gui import open_mask_editor
            open_mask_editor(self.root, runtime_root=self.runtime)
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

    def open_unified_audit(self):
        """Perform a read-only SHA receipt scan from the advanced menu."""
        try:
            from URETIM_V4.read_only_audit_v44 import inspect
            summary = inspect()
            text = (f"SHA denetimi: {summary['verified']}/{summary['total']} doğrulandı; "
                    f"{summary['review_required']} inceleme bekliyor.")
            self.status.set(text)
            self._log(text)
            messagebox.showinfo('7 Kategori SHA Kayıt Denetimi',
                                text + '\nBu denetim hiçbir dosyayı değiştirmez.', parent=self.root)
        except Exception as exc:
            messagebox.showerror('SHA denetimi hatası', str(exc), parent=self.root)

    def open_crash_recovery(self):
        try:
            from URETIM_V4.gui_v4 import open_unified_v4_window
            win = open_unified_v4_window(self.root, runtime_root=self.runtime)
            self.batch_windows.append(win)
            win.open_recovery()
        except Exception as exc:messagebox.showerror('Kesinti kurtarma açılmadı',str(exc),parent=self.root)

    def start(self,command,route):
        if self.running:return
        self.running=True
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

    @staticmethod
    def _safe_identity_error(diagnostic):
        """No center token or environment secrets may enter an error dialog."""
        fields=['reason','expected_pid','actual_pid','expected_path',
                'actual_path','exit_code','error_type']
        return '\n'.join(f'{key}: {diagnostic[key]}' for key in fields
                         if key in diagnostic) or 'Kimlik yanıtı alınamadı.'

    def poll(self):
        try:
            while True:
                kind,value=self.messages.get_nowait()
                if kind=='log':self._log(value)
                elif kind=='done':
                    route,code=value;self.running=False;self.proc=None
                    self.status.set(route+' işlemi sonlandı: '+str(code))
                elif kind=='legacy_started':
                    self.review_button.configure(state='normal');self.tools_button.configure(state='normal')
                    self.status.set(
                        f'7 kategori şablon/maske incelemesi hazır: '
                        f'127.0.0.1:{self.editor_port}')
                    webbrowser.open(f'http://127.0.0.1:{self.editor_port}'+value)
                elif kind=='legacy_error':
                    self.review_button.configure(state='normal');self.tools_button.configure(state='normal')
                    filename,diagnostic=value
                    try:excerpt=Path(filename).read_text(encoding='utf-8',errors='replace')[-1600:]
                    except OSError:excerpt='Sunucu günlük dosyası okunamadı.'
                    detail=self._safe_identity_error(diagnostic)
                    self._log('İNCELEME BAŞLATMA HATASI / KİMLİK KONTROLÜ\n'+detail+'\n'+excerpt)
                    self.status.set('İnceleme açılmadı: '+str(diagnostic.get('reason','UNKNOWN')))
                    messagebox.showerror('İnceleme açılmadı',
                        'Kimlik doğrulaması: '+detail+'\n\nSunucu günlüğü:\n'+excerpt,
                        parent=self.root)
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
        if self.ham_design_watcher is not None:self.ham_design_watcher.stop()
        self.root.destroy()

if __name__=='__main__':Center().root.mainloop()
