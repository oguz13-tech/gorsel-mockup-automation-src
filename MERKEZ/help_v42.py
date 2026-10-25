"""Short action-level Turkish guidance, displayed on hover without intercepting clicks."""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk

HELP = {
    'Klasör seç': 'Canlı çalışma kökünü seç. Şablonlar ve onaylı kayıtlar başka yere taşınmaz.',
    'Klasörü aç': 'Seçili çalışma dizinini Dosya Gezgini ile açar. Dosya değiştirmez.',
    'ŞABLON / 4 KÖŞE İNCELE': 'Kaynak fotoğraf ve köşeleri kontrol et; doğruysa kaydet ve onayla.',
    'PROFESYONEL ARAÇLAR': 'İsimlendirici ve bağımsız araçları açar. İşleme özel açıklamaları oku.',
    'GÜNLÜK SERİ ÜRETİM': 'Eski üretim aracı. Tüm onaylı şablonlar için 7 kategori seri üretimi kullan.',
    'TÜM ONAYLI ŞABLONLARLA SERİ ÜRETİM': 'Onaylı mockupları seç, desen klasörünü belirle ve tek kuyrukta üret.',
    'Kesinti / Kilit Kurtarma': 'Yarım kalan işi analiz eder. Korunan tamamlanmış çıktıları silmez.',
    'Eski inceleme sunucusunu durdur': 'Kaydedilmemiş dört köşeler varsa önce kaydet. Açık inceleme ekranını kapatır.',
    'ŞABLON / MASKE DÜZENLE': 'PETEK için gerçek delikleri ve kavisleri manuel kontrol et, maskeyi onayla.',
    'SERİ GÖRSEL ÜRET': 'Yalnız insan onaylı maskelerle desenleri toplu PETEK fotoğraflarına uygular.',
    'Kurtarma': 'Önce salt okunur kontrol; yalnız kullanıcının açık onayıyla bayat kilit ve yarım kayıtlar karantinaya alınır.',
    'Cam A/B Önizleme': 'Seçili cam şablon + ilk tasarımı gerçek baskıyla efekt açık/kapalı gösterir. Onaylı DB değişmez.',
    'HTTPS Linke Çevir': 'Ayrı açık onayla ImgBB/FreeImage bulutuna yükler. Aynı SKUya HTTPS Resim Linki Exceli üretir; pazaryerine yüklemez.',
    'SHA Kayıtlarını Doğrula': 'Kayıt ve çıktı SHA256 eşleşmesini salt okunur denetler; hiçbir görseli silmez.',
    'Denetle': 'Kayıt ve SHA doğruluğunu kontrol eder. Dosya silmez.',
    'Yenile': 'Yeni onayları tekrar yükler; seçili şablon listesini günceller.',
    'Tümünü Seç': 'Listedeki tüm onaylı şablonları seçer. Üretimi başlatmaz.',
    'Klasörünü Seç': 'Baskı desenlerini içeren klasörü seç; mockup kaynak fotoğrafları klasörü değildir.',
    'Güvenli Durdur': 'Yeni işlerin başlatılmasını durdurur; bitmiş görsellere dokunmaz.',
    'Güvenli durdur': 'Aktif işlem biter, yeni işler durur; bitmiş dosyalar korunur.',
    'Üretimi Başlat': 'İnsan onaylı şablonlarla üretimi başlatır; çıktılar create-only kaydedilir.',
    'Çıktı klasörü': 'Tamamlanmış görsellerin bulunduğu klasörü açar.',
    'Köşeleri Yeniden Seç': 'Yalnız açık şablonun köşe düzenleme modunu sıfırlar; ayrıca kaydet gerekir.',
    'TASLAK': 'Taslak işlemi üretime açmaz; insan kontrolünden sonra ayrıca onay gerekir.',
    'GERÇEK Baskı Tasarımıyla Önizle': 'Kaydetmeden önce gerçek tasarımla PETEK baskısını görüp doğrula.',
    'Mockupı Üretime Aç': 'Kontrol ettiğin maskeyi insan onaylı kayıt yapar.',
}


def hint_for(label: str):
    text = str(label).strip()
    for key, description in HELP.items():
        if key.casefold() in text.casefold():
            return description
    return f'{text}: İşlem öncesi kaydı kontrol et. Etki ve sonucu alt durum alanından izle.'


def bind_help(window):
    """Bind existing buttons, checks and combo boxes; preserve every original command."""
    bubble = {'obj': None}
    def hide(_event=None):
        if bubble['obj'] is not None:
            try: bubble['obj'].destroy()
            except tk.TclError: pass
            bubble['obj'] = None
    def show(widget, text):
        hide()
        try:
            t = tk.Toplevel(widget)
            t.wm_overrideredirect(True)
            t.attributes('-topmost', True)
            x = widget.winfo_rootx() + 10
            y = widget.winfo_rooty() + widget.winfo_height() + 5
            t.geometry(f'+{x}+{y}')
            tk.Label(t, text=text, wraplength=325, justify='left', padx=10, pady=8,
                     bg='#30394a', fg='#ffffff', font=('Segoe UI', 9)).pack()
            bubble['obj'] = t
        except tk.TclError:
            hide()
    def rec(widget):
        for w in widget.winfo_children():
            if isinstance(w, (ttk.Button, ttk.Combobox, ttk.Checkbutton)):
                try:
                    label = w.cget('text') if w.winfo_class() != 'TCombobox' else 'Seçenek seçimi'
                except tk.TclError:
                    label = 'İşlem'
                text = hint_for(label)
                w.bind('<Enter>', lambda _e, item=w, info=text: show(item, info), add='+')
                w.bind('<Leave>', hide, add='+')
                w.bind('<ButtonPress-1>', hide, add='+')
            rec(w)
    rec(window)
    window.bind('<Destroy>', hide, add='+')