"""Accessible dark ttk/Tk palette for all windows in the single Windows center."""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk

BG = '#181c24'
PANEL = '#242a35'
ENTRY = '#30394a'
FG = '#edf2f9'
MUTED = '#b8c4d4'
ACCENT = '#3b82f6'
HOVER = '#2563eb'


def apply_dark_theme(root: tk.Misc):
    """Install named ttk styles once per Tk interpreter; no persistent settings."""
    st = ttk.Style(root)
    st.theme_use('clam')
    st.configure('.', background=BG, foreground=FG, font=('Segoe UI', 10))
    for kind in ('TFrame', 'TLabelframe', 'TLabel', 'TCheckbutton', 'TRadiobutton'):
        st.configure(kind, background=BG, foreground=FG)
    st.configure('TLabelframe.Label', background=BG, foreground=FG)
    st.configure('TButton', background=ENTRY, foreground=FG, borderwidth=1, padding=(9, 7), relief='flat')
    st.map('TButton', background=[('disabled', PANEL), ('pressed', ACCENT), ('active', HOVER)], foreground=[('disabled', MUTED), ('active', '#ffffff')])
    st.configure('TEntry', fieldbackground=ENTRY, foreground=FG, insertcolor=FG, bordercolor=ENTRY, padding=5)
    st.map('TEntry', fieldbackground=[('readonly', PANEL), ('disabled', PANEL)], foreground=[('readonly', FG)])
    st.configure('TCombobox', fieldbackground=ENTRY, background=ENTRY, foreground=FG, arrowcolor=FG, padding=5)
    st.map('TCombobox', fieldbackground=[('readonly', ENTRY)], selectbackground=[('readonly', ENTRY)], selectforeground=[('readonly', FG)])
    st.configure('Vertical.TScrollbar', background=ENTRY, troughcolor=BG, arrowcolor=FG)
    st.configure('Horizontal.TScrollbar', background=ENTRY, troughcolor=BG, arrowcolor=FG)
    st.configure('TSeparator', background=ENTRY)
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
