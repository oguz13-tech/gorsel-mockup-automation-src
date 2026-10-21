"""Create a separate, explicitly reviewed PETEK plan; never edit source/approval DB."""
import json
from pathlib import Path
import sys
import uuid
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE/'GUNLUK'),str(HERE/'PETEK')]
from checks import no_redirect
import petek_dolabi_app as engine


def save_plan(template,designs,quad,top,bottom,plans,expected_sha,reviewed=False):
    if reviewed is not True:raise ValueError('Yüzeyi inceleyip onay kutusunu işaretle.')
    template,designs,plans=map(lambda p:Path(p).absolute(),(template,designs,plans))
    for p in (template,designs,plans):no_redirect(p)
    if not designs.is_dir():raise ValueError('Tasarım klasörü bulunamadı.')
    if engine.file_sha256(template)!=expected_sha:raise ValueError('Şablon açıldıktan sonra değişti; yeniden seç.')
    output=plans.parent/'PETEK_TICARI_LOCAL'
    for p in (template,designs):
        a,b=p.resolve(),output.resolve()
        if a==b or a in b.parents or b in a.parents:raise ValueError('Tasarım/şablon sonuç klasöründe olamaz.')
    shape=engine.read_image(template).shape
    geometry=engine.PanelGeometry('06_Petek_Dolabi',tuple(tuple(p) for p in quad),True,tuple(top) if top else None,tuple(bottom) if bottom else None,expected_sha)
    engine.GeometryGuard().validate(geometry,shape,expected_sha)
    plans.mkdir(parents=True,exist_ok=True);directory=plans/uuid.uuid4().hex;directory.mkdir()
    geo={'category':geometry.category,'quad':quad,'reviewed':True,'template_sha256':expected_sha}
    if top is not None:geo.update(top_mid=top,bottom_mid=bottom)
    with (directory/'geometri.json').open('x',encoding='utf-8') as f:json.dump(geo,f,ensure_ascii=False,indent=2)
    # Full source hash is an internal identity. No source file is renamed.
    plan={'category':'06_Petek_Dolabi','designs':str(designs),'state_dir':str(output),'store_group':'LOCAL','seller_prefix':'PDK','upload_enabled':False,
          'templates':[{'uid':'06_Petek_Dolabi_PetekDolabi_SHA_'+expected_sha,'image':str(template),'geometry':str(directory/'geometri.json')}]}
    target=directory/'PETEK_PLANI.json'
    with target.open('x',encoding='utf-8') as f:json.dump(plan,f,ensure_ascii=False,indent=2)
    return target


def open_editor(parent,designs,on_saved):
    import tkinter as tk
    from tkinter import ttk,filedialog,messagebox
    from PIL import Image,ImageTk
    import cv2
    source=filedialog.askopenfilename(parent=parent,title='Gerçek PETEK mockup şablonunu seç',filetypes=[('Görsel','*.png *.jpg *.jpeg *.webp')])
    if not source:return
    try:
        no_redirect(Path(source));sha=engine.file_sha256(Path(source));rgb=cv2.cvtColor(engine.read_image(Path(source)),cv2.COLOR_BGR2RGB)
    except Exception as exc:messagebox.showerror('Şablon açılamadı',str(exc),parent=parent);return
    if not designs or not Path(designs).is_dir():
        designs=filedialog.askdirectory(parent=parent,title='PETEK tasarımları klasörünü seç')
        if not designs:return
    window=tk.Toplevel(parent);window.title('PETEK baskı yüzeyini incele');window.transient(parent);window.grab_set()
    scale=min(1,900/rgb.shape[1],max(250,parent.winfo_screenheight()-300)/rgb.shape[0]);size=(round(rgb.shape[1]*scale),round(rgb.shape[0]*scale))
    photo=ImageTk.PhotoImage(Image.fromarray(rgb).resize(size),master=window)
    mode=tk.StringVar(value='flat');reviewed=tk.BooleanVar(value=False);points=[]
    ttk.Label(window,text='Baskı yapılacak ön yüzeyi işaretle. Canlı köşe kayıtları değiştirilmez.',wraplength=850).pack(padx=12,pady=7)
    row=ttk.Frame(window);row.pack();status=tk.StringVar()
    canvas=tk.Canvas(window,width=size[0],height=size[1],highlightthickness=0);canvas.pack(padx=12,pady=8);canvas.create_image(0,0,anchor='nw',image=photo);canvas.image=photo
    labels=['Sol üst','Sağ üst','Sağ alt','Sol alt','Üst kenarın ortası','Alt kenarın ortası']
    def update():
        count=6 if mode.get()=='curve' else 4
        status.set('Sıradaki nokta: '+labels[len(points)] if len(points)<count else 'İşaretleri kontrol et ve aşağıdaki onay kutusunu işaretle.')
    def reset():
        points.clear();reviewed.set(False);canvas.delete('mark');update()
    ttk.Radiobutton(row,text='Düz ön yüz',value='flat',variable=mode,command=reset).pack(side='left')
    ttk.Radiobutton(row,text='Kavisli ön yüz — üst/alt kenar orta noktaları da gerekli',value='curve',variable=mode,command=reset).pack(side='left')
    ttk.Label(window,textvariable=status).pack()
    def click(event):
        count=6 if mode.get()=='curve' else 4
        if len(points)>=count or not(0<=event.x<size[0] and 0<=event.y<size[1]):return
        points.append([event.x/scale,event.y/scale]);reviewed.set(False)
        canvas.create_oval(event.x-5,event.y-5,event.x+5,event.y+5,fill='#ee3333',outline='white',tags='mark')
        canvas.create_text(event.x+10,event.y+12,text=str(len(points)),fill='#ee3333',tags='mark');update()
    canvas.bind('<Button-1>',click)
    ttk.Checkbutton(window,text='Bu şablondaki baskı yüzeyini ve düz/kavisli seçimini gözle kontrol ettim, onaylıyorum.',variable=reviewed).pack(padx=12,pady=8)
    buttons=ttk.Frame(window);buttons.pack(pady=10)
    ttk.Button(buttons,text='İşaretleri sıfırla',command=reset).pack(side='left',padx=6)
    def save():
        try:
            if len(points)!=(6 if mode.get()=='curve' else 4):raise ValueError('Gerekli tüm noktaları işaretle.')
            path=save_plan(source,designs,points[:4],points[4] if len(points)==6 else None,points[5] if len(points)==6 else None,
                           Path('C:/AI_LOCAL_OUTPUTS/GorselMockup/PETEK_PLANLARI'),sha,reviewed.get())
            on_saved(str(path),designs);window.destroy()
        except Exception as exc:messagebox.showerror('Kaydedilemedi',str(exc),parent=window)
    ttk.Button(buttons,text='Ayrı PETEK planı olarak kaydet',command=save).pack(side='left',padx=6);update()
