"""Small native Windows launcher; no web service or live job engine."""
import os
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog,messagebox,ttk
from daily import Production,STORE
from session_safety import atomic_json
import json


def main():
    root=tk.Tk();root.title('Görsel Mockup — Günlük Üretim — 6 Kategori');root.geometry('840x700');root.minsize(680,540)
    style=ttk.Style(root);style.theme_use('clam');style.configure('TLabel',font=('Segoe UI',10));style.configure('TButton',font=('Segoe UI',10),padding=8)
    body=ttk.Frame(root,padding=24);body.pack(fill='both',expand=True)
    ttk.Label(body,text='Tasarım klasöründen mockup üret',font=('Segoe UI',18,'bold')).pack(anchor='w',pady=(0,12))
    ttk.Label(body,text='Çıktı: 1200 × 1600 • Görsel kalite incelemesi gerekli • Tekrar koruması etkin').pack(anchor='w')
    ttk.Label(body,text='10 seçili şablon · Her uygun tasarım–şablon eşleşmesinde üretim').pack(anchor='w',pady=(6,18))
    folder=tk.StringVar();row=ttk.Frame(body);row.pack(fill='x')
    entry=ttk.Entry(row,textvariable=folder);entry.pack(side='left',fill='x',expand=True)
    def choose():
        selected=filedialog.askdirectory(parent=root,title='Tasarım görsellerinin bulunduğu klasörü seç')
        if selected:folder.set(selected)
    browse=ttk.Button(row,text='Klasör seç',command=choose);browse.pack(side='left',padx=(8,0))
    ttk.Label(body,text='Alt klasörler de okunur. Destek: JPG, JPEG, PNG, WEBP. Tasarım dosyaları değiştirilmez.').pack(anchor='w',pady=(8,12))
    categories=[('01_Wifi_Kutusu','WiFi kutusu — 4 şablon'),('02_Cam_Tablo_Yatay','Yatay cam tablo — 1 şablon'),('02_Cam_Tablo_Dikey','Dikey cam tablo — 1 şablon'),('03_Ahsap_Tablo','Ahşap tablo — 1 dikey şablon'),('04_Cam_Dograma','Cam doğrama — 1 şablon'),('05_Ocak_Arkasi','Ocak arkası — 2 şablon')]
    variables={};boxes=[]
    for key,label in categories:
        variables[key]=tk.BooleanVar(value=True);box=ttk.Checkbutton(body,text=label,variable=variables[key]);box.pack(anchor='w',pady=3);boxes.append(box)
    status=tk.StringVar(value='Klasörü seç, kategorileri işaretle ve Üretimi başlat düğmesine bas.')
    ttk.Label(body,textvariable=status,wraplength=710).pack(anchor='w',fill='x',pady=(18,8))
    progress=ttk.Progressbar(body,mode='indeterminate');progress.pack(fill='x')
    actions=ttk.Frame(body);actions.pack(fill='x',pady=14)
    messages=queue.Queue();state={'running':False,'cancel':None,'output':None,'close':False}
    def open_results():
        path=state['output']
        if path:
            gallery=path/'SONUCLAR.html'
            os.startfile(str(gallery if gallery.exists() else path))
        elif STORE.exists():os.startfile(str(STORE))
    def report_folder():
        if state['output']:os.startfile(str(state['output']))
    def stop():
        if state['cancel']:
            state['cancel'].set();status.set('Durdurma istendi. Mevcut iş ve tekrar kontrolü bitince duracak.');stop_button.configure(state='disabled')
    def controls(running):
        for widget in [entry,browse,start_button,*boxes]:widget.configure(state='disabled' if running else 'normal')
        stop_button.configure(state='normal' if running else 'disabled')
    def work(selected,chosen,cancel):
        try:
            report,out=Production(selected,chosen,notify=lambda value:messages.put(('progress',value)),cancel=cancel).run()
            messages.put(('done',(report,out)))
        except Exception as exc:messages.put(('done',({'status':'BLOCKED','error':str(exc)},None)))
    def start():
        selected=folder.get().strip();chosen=[key for key,_ in categories if variables[key].get()]
        if not selected or not Path(selected).is_dir():messagebox.showinfo('Klasör seç','Önce tasarım klasörünü seç.',parent=root);return
        if not chosen:messagebox.showinfo('Kategori seç','En az bir kategori seç.',parent=root);return
        state.update(running=True,cancel=threading.Event(),output=None);controls(True);progress.start(15)
        threading.Thread(target=work,args=(selected,chosen,state['cancel']),daemon=False).start()
    start_button=ttk.Button(actions,text='Üretimi başlat',command=start);start_button.pack(side='left')
    stop_button=ttk.Button(actions,text='Mevcut işten sonra durdur',command=stop,state='disabled');stop_button.pack(side='left',padx=8)
    ttk.Button(actions,text='Sonuçları aç',command=open_results).pack(side='left')
    ttk.Button(actions,text='Rapor klasörü',command=report_folder).pack(side='left',padx=(8,0))
    ttk.Label(body,text='Çıktılar: C:\\AI_LOCAL_OUTPUTS\\GorselMockup\\GORSELLER\nCanlı şablonlar, köşeler, JSON ve canlı DB korunur. Bulut ve Excel bu sürümde kullanılmaz.',wraplength=710).pack(anchor='w')
    def poll():
        try:
            while True:
                kind,value=messages.get_nowait()
                if kind=='progress':
                    if not state['cancel'].is_set():status.set(value)
                else:
                    report,out=value;state.update(running=False,output=out);progress.stop();controls(False)
                    pointer=os.environ.get('MOCKUP_FINAL_PARENT_REPORT')
                    if pointer and out:
                        target=Path(pointer)
                        entries=json.loads(target.read_text(encoding='utf-8')) if target.exists() else []
                        entries.append({'status':report['status'],'completed_jobs':report.get('completed_jobs',0),'report':str(out/'GUNLUK_URETIM_SONUC.json')})
                        atomic_json(target,entries)
                    error=report.get('error') or report.get('closing_error')
                    if error:
                        status.set('Durdu: '+error);messagebox.showerror('İşlem durdu',error+('\n\nRapor klasörü:\n'+str(out) if out else ''),parent=root)
                    else:
                        status.set('Tamamlandı: '+str(report.get('completed_jobs',0))+' iş · '+str(report.get('new_renders',0))+' yeni · '+str(report.get('reused_outputs',0))+' mevcut · '+str(sum('template_uid' in x for x in report.get('skipped',[])))+' uyumsuz eşleşme · '+str(sum('template_uid' not in x for x in report.get('skipped',[])))+' atlanan dosya')
                        messagebox.showinfo('Üretim sonucu',status.get()+'\n\nSonuçları aç düğmesiyle görselleri inceleyebilirsin.\nRapor: '+str(out)+'\n\nUyumsuz yön/oran veya saydam tasarımların nedenleri raporda listelenir.',parent=root)
                    if state['close']:root.destroy();return
        except queue.Empty:pass
        root.after(150,poll)
    def close():
        if state['running']:state['close']=True;stop()
        else:root.destroy()
    root.protocol('WM_DELETE_WINDOW',close);root.after(150,poll);root.mainloop()

if __name__=='__main__':main()
