"""Four-corner review with automatic mask proposal and optional correction brush."""
from pathlib import Path
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from PIL import Image,ImageTk
import cv2
import numpy as np

from . import petek_v3 as engine
from .safety import sha


class Review:
    def __init__(self,parent,profile_root,on_saved,source=None):
        source=source or filedialog.askopenfilename(parent=parent,title='Boş/orijinal PETEK şablonunu seç',filetypes=[('Görseller','*.png *.jpg *.jpeg *.webp')])
        if not source:return
        try:self.scene=engine.image(source);self.original_sha=sha(source)
        except Exception as exc:messagebox.showerror('Şablon okunamadı',str(exc),parent=parent);return
        self.source=source;self.profile_root=profile_root;self.on_saved=on_saved
        self.quad=[];self.mask=None;self.metrics={};self.history=[];self.stroke=False
        self.window=tk.Toplevel(parent);self.window.title('PETEK — dört köşe ve baskı maskesi');self.window.grab_set()
        self.window.geometry(f'1050x{min(950,parent.winfo_screenheight()-80)}')
        frame=ttk.Frame(self.window,padding=10);frame.pack(fill='both',expand=True)
        tools=ttk.Frame(frame,width=280);tools.pack(side='right',fill='y',padx=(12,0))
        ttk.Label(tools,text='Ön panelin dört köşesi',font=('Segoe UI',13,'bold')).pack(anchor='w')
        ttk.Label(tools,text='Sıra: 1 Sol üst → 2 Sağ üst\n3 Sağ alt → 4 Sol alt\n\nKavislerin orta noktalarını seçme.\nDelik ve kavis boşluklarını maske ayırır.',wraplength=260).pack(anchor='w',pady=8)
        self.status=tk.StringVar(value='1 — Sol üst köşeye tıkla.')
        ttk.Label(tools,textvariable=self.status,wraplength=260).pack(anchor='w',pady=8)
        ttk.Button(tools,text='Dört köşeyi sıfırla',command=self.reset).pack(fill='x')
        self.sensitivity=tk.DoubleVar(value=0)
        ttk.Label(tools,text='Açıklık eşiği (istisnai düzeltme)').pack(anchor='w',pady=(12,0))
        ttk.Scale(tools,from_=-35,to=45,variable=self.sensitivity).pack(fill='x')
        ttk.Button(tools,text='Baskı maskesini otomatik çıkar',command=self.analyze).pack(fill='x',pady=7)
        ttk.Label(tools,text='YEŞİL = tasarım basılacak yer.\nDelikler, kavisler, zemin yeşil olmamalı.',wraplength=260).pack(anchor='w')
        self.mode=tk.StringVar(value='protect');self.radius=tk.IntVar(value=12)
        ttk.Radiobutton(tools,text='Koruma fırçası — yeşili kaldır',variable=self.mode,value='protect').pack(anchor='w',pady=(10,0))
        ttk.Radiobutton(tools,text='Baskı fırçası — yeşil ekle',variable=self.mode,value='paint').pack(anchor='w')
        ttk.Label(tools,text='Fırça yarıçapı').pack(anchor='w')
        ttk.Spinbox(tools,from_=1,to=60,textvariable=self.radius,width=8).pack(anchor='w')
        ttk.Button(tools,text='Son fırça işlemini geri al',command=self.undo).pack(fill='x',pady=5)
        self.show=tk.BooleanVar(value=True)
        ttk.Checkbutton(tools,text='Yeşil maskeyi göster',variable=self.show,command=self.redraw).pack(anchor='w')
        ttk.Label(tools,text='Ön panel fiziksel en / boy oranı\nBiliniyorsa gir; boşsa görüntüden tahmin.',wraplength=260).pack(anchor='w',pady=(12,0))
        self.aspect=tk.StringVar();ttk.Entry(tools,textvariable=self.aspect).pack(fill='x')
        ttk.Button(tools,text='Bir tasarımla baskıyı önizle',command=self.preview).pack(fill='x',pady=8)
        self.approved=tk.BooleanVar(value=False)
        ttk.Checkbutton(tools,text='Dört köşeyi ve yeşil maskeyi\ngözümle kontrol ettim, onaylıyorum.',variable=self.approved).pack(anchor='w',pady=8)
        ttk.Button(tools,text='Onaylı şablonu kaydet',command=self.save).pack(fill='x',pady=6)
        self.scale=min(1,710/self.scene.shape[1],max(300,parent.winfo_screenheight()-150)/self.scene.shape[0])
        self.size=(round(self.scene.shape[1]*self.scale),round(self.scene.shape[0]*self.scale))
        self.canvas=tk.Canvas(frame,width=self.size[0],height=self.size[1],highlightthickness=0);self.canvas.pack(side='left',expand=True)
        self.canvas.bind('<Button-1>',self.click);self.canvas.bind('<B1-Motion>',self.drag);self.canvas.bind('<ButtonRelease-1>',lambda e:setattr(self,'stroke',False))
        self.redraw()

    def redraw(self):
        display=engine.overlay(self.scene,self.mask) if self.mask is not None and self.show.get() else self.scene
        rgb=cv2.cvtColor(display,cv2.COLOR_BGR2RGB)
        photo=ImageTk.PhotoImage(Image.fromarray(rgb).resize(self.size,Image.Resampling.LANCZOS),master=self.window)
        self.canvas.delete('all');self.canvas.create_image(0,0,anchor='nw',image=photo);self.canvas.image=photo
        for i,(x,y) in enumerate(self.quad):
            x*=self.scale;y*=self.scale;self.canvas.create_oval(x-5,y-5,x+5,y+5,fill='red',outline='white')
            self.canvas.create_text(x+12,y+12,text=str(i+1),fill='red',font=('Segoe UI',12,'bold'))

    def reset(self):
        self.quad=[];self.mask=None;self.history=[];self.approved.set(False);self.status.set('1 — Sol üst köşeye tıkla.');self.redraw()

    def click(self,event):
        if not (0<=event.x<self.size[0] and 0<=event.y<self.size[1]):return
        if len(self.quad)<4:
            self.quad.append([event.x/self.scale,event.y/self.scale]);self.approved.set(False)
            labels=['1 — Sol üst','2 — Sağ üst','3 — Sağ alt','4 — Sol alt']
            self.status.set(labels[len(self.quad)] if len(self.quad)<4 else 'Dört köşe tamam. Otomatik maske çıkar düğmesine bas.');self.redraw()
        elif self.mask is not None:
            self.history.append(self.mask.copy());self.history=self.history[-4:];self.stroke=True;self.drag(event)

    def drag(self,event):
        if not self.stroke or self.mask is None:return
        x,y=round(event.x/self.scale),round(event.y/self.scale)
        radius=max(1,min(60,self.radius.get()))
        cv2.circle(self.mask,(x,y),radius,0 if self.mode.get()=='protect' else 255,-1)
        self.mask[engine.quad_mask(self.scene.shape,self.quad)==0]=0
        self.approved.set(False);self.redraw()

    def undo(self):
        if self.history:self.mask=self.history.pop();self.approved.set(False);self.redraw()

    def analyze(self):
        try:
            proposal=engine.analyze(self.scene,self.quad,self.sensitivity.get())
            self.mask=proposal.mask;self.metrics=proposal.metrics;self.history=[];self.approved.set(False)
            self.status.set(f'Baskı alanı: %{100*self.metrics["coverage"]:.1f}. '+(' '.join(self.metrics['warnings']) or 'Delikleri ve iki kavisi kontrol et.'))
            self.redraw()
        except Exception as exc:messagebox.showerror('Maske oluşturulamadı',str(exc),parent=self.window)

    def ratio(self):
        return float(self.aspect.get().replace(',','.')) if self.aspect.get().strip() else None

    def preview(self):
        if self.mask is None:messagebox.showinfo('Önce maske','Önce otomatik maske çıkar.',parent=self.window);return
        path=filedialog.askopenfilename(parent=self.window,title='Önizleme için bir tasarım seç',filetypes=[('Görseller','*.png *.jpg *.jpeg *.webp')])
        if not path:return
        try:
            result,quality=engine.render(engine.image(path),self.scene,self.mask,self.quad,self.ratio())
            window=tk.Toplevel(self.window);window.title('Baskı önizlemesi — kaydedilmedi')
            h=min(800,self.window.winfo_screenheight()-130);w=round(h*.75)
            photo=ImageTk.PhotoImage(Image.fromarray(cv2.cvtColor(result,cv2.COLOR_BGR2RGB)).resize((w,h)),master=window)
            label=ttk.Label(window,image=photo);label.image=photo;label.pack()
            ttk.Label(window,text=f'Tasarım kırpılması: %{100*quality["crop_fraction"]:.1f} · Orijinal korunan piksellerde fark: {quality["protected_pixel_max_difference"]}').pack()
        except Exception as exc:messagebox.showerror('Önizleme hatası',str(exc),parent=self.window)

    def save(self):
        try:
            if self.mask is None:raise ValueError('Önce maskeyi oluşturup incele.')
            if sha(self.source)!=self.original_sha:raise ValueError('Şablon açıldıktan sonra değişti; yeniden aç.')
            p=engine.save_profile(self.profile_root,self.source,self.quad,self.mask,self.metrics,self.approved.get(),self.ratio())
            self.on_saved(p);self.window.destroy()
        except Exception as exc:messagebox.showerror('Kaydedilemedi',str(exc),parent=self.window)
