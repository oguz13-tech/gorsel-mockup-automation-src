"""Shared contextual help for the Tk interfaces.

The production UI uses :class:`ContextHelp` for explicit ``?`` buttons. The
legacy hover hints remain available for older screens.
"""
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


def help_details(what, when, data):
    """Return the normalized payload used by the shared help popup."""
    return {'what': str(what), 'when': str(when), 'data': str(data)}


class ContextHelp:
    """One reusable ``?`` popup manager for a Tk top-level window."""

    def __init__(self, window):
        self.window = window
        self.popup = None
        self._outside_binding = None
        self._escape_binding = None

    def button(self, parent, details, *, side='right', padx=(4, 0), pady=0):
        btn = ttk.Button(parent, text='?', width=2)
        btn.configure(command=lambda item=details: self.show(item, btn))
        btn.configure(takefocus=True)
        btn.pack(side=side, padx=padx, pady=pady)
        return btn

    def show(self, details, anchor=None):
        self.close()
        if isinstance(details, str):
            details = help_details(details, 'Gerektiğinde kullanılır.',
                                    'Üretim verilerini kendiliğinden değiştirmez.')
        try:
            popup = tk.Toplevel(self.window)
            popup.title('Yardım')
            popup.transient(self.window)
            popup.resizable(False, False)
            popup.configure(bg='#131C2B')
            frame = tk.Frame(popup, bg='#131C2B', padx=14, pady=12)
            frame.pack(fill='both', expand=True)
            for title, key, bottom in (
                ('Bu kontrol ne yapar?', 'what', 8),
                ('Ne zaman kullanılır?', 'when', 8),
                ('Dosya/kayıt etkisi', 'data', 10),
            ):
                tk.Label(frame, text=title, bg='#131C2B', fg='#8DEBD5',
                         font=('Segoe UI', 10, 'bold'), anchor='w').pack(fill='x')
                tk.Label(frame, text=details.get(key, ''), bg='#131C2B', fg='#E9EFF9',
                         font=('Segoe UI', 10), justify='left', anchor='w',
                         wraplength=340).pack(fill='x', pady=(2, bottom))
            ttk.Button(frame, text='Kapat', command=self.close).pack(anchor='e')
            popup.bind('<Escape>', lambda _event: self.close())
            popup.protocol('WM_DELETE_WINDOW', self.close)
            popup.update_idletasks()
            anchor = anchor or self.window
            x = anchor.winfo_rootx() + anchor.winfo_width() + 6
            y = anchor.winfo_rooty()
            width, height = popup.winfo_reqwidth(), popup.winfo_reqheight()
            screen_w, screen_h = popup.winfo_screenwidth(), popup.winfo_screenheight()
            if x + width > screen_w - 8:
                x = max(8, anchor.winfo_rootx() - width - 6)
            if y + height > screen_h - 8:
                y = max(8, screen_h - height - 8)
            popup.geometry(f'+{x}+{y}')
            self.popup = popup
            self._outside_binding = self.window.bind_all('<Button-1>', self._outside_click, add='+')
            self._escape_binding = self.window.bind_all('<Escape>', lambda _event: self.close(), add='+')
            popup.focus_set()
        except tk.TclError:
            self.close()

    def _outside_click(self, event):
        popup = self.popup
        if popup is None:
            return
        try:
            if event.widget is popup or str(event.widget).startswith(str(popup)):
                return
        except tk.TclError:
            pass
        self.close()

    def close(self):
        if self._outside_binding is not None:
            try:
                self.window.unbind_all('<Button-1>')
            except tk.TclError:
                pass
            self._outside_binding = None
        if self._escape_binding is not None:
            try:
                self.window.unbind_all('<Escape>')
            except tk.TclError:
                pass
            self._escape_binding = None
        if self.popup is not None:
            try:
                self.popup.destroy()
            except tk.TclError:
                pass
            self.popup = None


def attach_context_help(window):
    """Return one manager, reusing it when a screen is rebuilt."""
    manager = getattr(window, '_context_help', None)
    if manager is None:
        manager = ContextHelp(window)
        window._context_help = manager
    return manager


def hint_for(label: str):
    text = str(label).strip()
    for key, description in HELP.items():
        if key.casefold() in text.casefold():
            return description
    return f'{text}: İşlem öncesi kaydı kontrol et. Etki ve sonucu alt durum alanından izle.'


def bind_help(window):
    """Bind existing buttons, checks and combo boxes; preserve every original command."""
    attach_context_help(window)
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
                     bg='#22304A', fg='#ffffff', font=('Segoe UI', 9)).pack()
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
