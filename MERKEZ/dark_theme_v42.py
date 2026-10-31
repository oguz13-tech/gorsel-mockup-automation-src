"""Accessible dark ttk/Tk palette for all windows in the single Windows center."""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk

BG = '#252a30'
PANEL = '#343c46'
ENTRY = '#3b4552'
FG = '#f1f0ff'
MUTED = '#d0d8e3'
ACCENT = '#8a5cf6'
HOVER = '#7246d5'


def apply_dark_theme(root: tk.Misc):
    """Install named ttk styles once per Tk interpreter; no persistent settings."""
    st = ttk.Style(root)
    st.theme_use('clam')
    st.configure('.', background=BG, foreground=FG, font=('Segoe UI', 11))
    for kind in ('TFrame', 'TLabelframe', 'TLabel', 'TCheckbutton', 'TRadiobutton'):
        st.configure(kind, background=BG, foreground=FG)
    st.map('TCheckbutton', foreground=[('disabled','#c4c8d8'),('active','#f1f0ff'),('pressed','#ffffff')],
           background=[('disabled',BG),('active',BG),('pressed',BG)],
           indicatorbackground=[('disabled',ENTRY),('active',ENTRY)])
    st.map('TRadiobutton', foreground=[('disabled','#c4c8d8'),('active','#f1f0ff')],
           background=[('disabled',BG),('active',BG)])
    st.configure('TLabelframe.Label', background=BG, foreground=FG)
    st.configure('TButton', background=ENTRY, foreground=FG, borderwidth=1, padding=(12, 9), relief='flat')
    st.map('TButton', background=[('disabled', PANEL), ('pressed', ACCENT), ('active', HOVER)], foreground=[('disabled', MUTED), ('active', '#ffffff')])
    st.configure('TEntry', fieldbackground=ENTRY, foreground=FG, insertcolor=FG, bordercolor=ENTRY, padding=8)
    st.map('TEntry', fieldbackground=[('readonly', PANEL), ('disabled', PANEL)], foreground=[('readonly', FG)])
    st.configure('TCombobox', fieldbackground=ENTRY, background=ENTRY, foreground=FG, arrowcolor=FG, padding=8)
    st.map('TCombobox', fieldbackground=[('readonly', ENTRY)], selectbackground=[('readonly', ENTRY)], selectforeground=[('readonly', FG)])
    st.configure('Vertical.TScrollbar', background=ENTRY, troughcolor=BG, arrowcolor=FG)
    st.configure('Horizontal.TScrollbar', background=ENTRY, troughcolor=BG, arrowcolor=FG)
    st.configure('TSeparator', background=ENTRY)
    st.configure('Premium.TLabelframe', background=PANEL, foreground=FG, bordercolor='#56606d')
    st.configure('Premium.TLabelframe.Label', background=PANEL, foreground='#e2d9ff', font=('Segoe UI', 12, 'bold'))
    st.configure('Premium.Primary.TButton', background=ACCENT, foreground='#ffffff', font=('Segoe UI', 11, 'bold'), padding=(15, 11))
    st.map('Premium.Primary.TButton', background=[('active', '#a77cff'), ('pressed', '#6c3fce')])
    st.configure('Premium.Secondary.TButton', background=ENTRY, foreground=FG, padding=(12, 10))
    st.map('Premium.Secondary.TButton', background=[('active', '#4e5664')])
    root.configure(background=BG)
    root.option_add('*TCombobox*Listbox.background', ENTRY)
    root.option_add('*TCombobox*Listbox.foreground', FG)
    root.option_add('*TCombobox*Listbox.selectBackground', ACCENT)


def darken_window(window: tk.Misc):
    """Color native Tk widgets, preserve canvases containing a source photograph."""
    for obj in [window] + list(_descendants(window)):
        try:
            if isinstance(obj, (tk.Listbox, tk.Text)):
                obj.configure(bg=PANEL, fg=FG, selectbackground=ACCENT, selectforeground='#fff',
                              insertbackground=FG, highlightbackground=ENTRY)
            elif isinstance(obj, (tk.Entry,)):
                obj.configure(bg=ENTRY, fg=FG, insertbackground=FG)
            elif isinstance(obj, (tk.Canvas,)):
                # Dedicated photograph/editor canvas backgrounds must not be replaced.
                if str(obj.cget('background')).lower() not in ('#111', '#202329', '#202020'):
                    obj.configure(bg=BG)
        except (tk.TclError, AttributeError):
            pass
    try:
        window.configure(bg=BG)
    except tk.TclError:
        pass


def _descendants(w):
    for child in w.winfo_children():
        yield child
        yield from _descendants(child)
