"""Accessible dark ttk/Tk palette for all windows in the single Windows center."""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk

from pathlib import Path
import json

# Shared purple design tokens. Localized and read-only; missing/corrupt JSON
# safely falls back to the same built-in palette without affecting production.
_FALLBACK = {
    'background':'#0B101B','sidebar':'#0F1622','panel':'#131C2B',
    'raised':'#182238','border':'#22304A','accent':'#17D3A3',
    'accent_hover':'#0FAC80','text':'#E9EFF9','muted':'#93A6C4'
}
try:
    _raw = json.loads(Path(__file__).with_name('ui_mor_tokens_vnext.json').read_text(encoding='utf-8'))
    UI_MOR_THEME = {key: _raw[key] if isinstance(_raw.get(key),str) and len(_raw[key])==7
                    and _raw[key].startswith('#') and all(c in '0123456789abcdefABCDEF' for c in _raw[key][1:])
                    else value for key,value in _FALLBACK.items()}
except (OSError, ValueError, TypeError, KeyError):
    UI_MOR_THEME = dict(_FALLBACK)

BG = UI_MOR_THEME['background']
PANEL = UI_MOR_THEME['panel']
ENTRY = UI_MOR_THEME['raised']
FG = UI_MOR_THEME['text']
MUTED = UI_MOR_THEME['muted']
ACCENT = UI_MOR_THEME['accent']
HOVER = UI_MOR_THEME['accent_hover']


def apply_dark_theme(root: tk.Misc):
    """Install named ttk styles once per Tk interpreter; no persistent settings."""
    st = ttk.Style(root)
    st.theme_use('clam')
    st.configure('.', background=BG, foreground=FG, font=('Segoe UI', 11))
    for kind in ('TFrame', 'TLabelframe', 'TLabel', 'TCheckbutton', 'TRadiobutton'):
        st.configure(kind, background=BG, foreground=FG)
    st.map('TCheckbutton', foreground=[('disabled','#93A6C4'),('active','#93A6C4'),('pressed','#ffffff')],
           background=[('disabled',BG),('active',BG),('pressed',BG)],
           indicatorbackground=[('disabled',ENTRY),('active',ENTRY)])
    st.map('TRadiobutton', foreground=[('disabled','#93A6C4'),('active','#93A6C4')],
           background=[('disabled',BG),('active',BG)])
    st.configure('TLabelframe.Label', background=BG, foreground=FG)
    st.configure('TButton', background=ENTRY, foreground=FG, borderwidth=1, padding=(12, 9), relief='flat')
    st.map('TButton', background=[('disabled', PANEL), ('pressed', ACCENT), ('active', HOVER)], foreground=[('disabled', MUTED), ('active', '#04140E')])
    st.configure('TEntry', fieldbackground=ENTRY, foreground=FG, insertcolor=FG, bordercolor=ENTRY, padding=8)
    st.map('TEntry', fieldbackground=[('readonly', PANEL), ('disabled', PANEL)], foreground=[('readonly', FG)])
    st.configure('TCombobox', fieldbackground=ENTRY, background=ENTRY, foreground=FG, arrowcolor=FG, padding=8)
    st.map('TCombobox', fieldbackground=[('readonly', ENTRY)], selectbackground=[('readonly', ENTRY)], selectforeground=[('readonly', FG)])
    st.configure('Vertical.TScrollbar', background=ENTRY, troughcolor=BG, arrowcolor=FG)
    st.configure('Horizontal.TScrollbar', background=ENTRY, troughcolor=BG, arrowcolor=FG)
    st.configure('TSeparator', background=ENTRY)
    # ttk.Treeview (figure: lists + log panes in the new screens)
    st.configure('Treeview', background=PANEL, fieldbackground=PANEL, foreground=FG,
                 rowheight=26, borderwidth=0)
    st.configure('Treeview.Heading', background=ENTRY, foreground=FG, relief='flat', padding=(6, 4))
    st.map('Treeview', background=[('selected', ACCENT)], foreground=[('selected', '#04140E')])
    st.configure('TNotebook', background=BG, borderwidth=0)
    st.configure('TNotebook.Tab', background=ENTRY, foreground=FG, padding=(12, 7))
    st.map('TNotebook.Tab', background=[('selected', ACCENT)], foreground=[('selected', '#04140E')])
    st.configure('Premium.TLabelframe', background=PANEL, foreground=FG, bordercolor='#22304A')
    st.configure('Premium.TLabelframe.Label', background=PANEL, foreground='#E9EFF9', font=('Segoe UI', 12, 'bold'))
    st.configure('Premium.Primary.TButton', background=ACCENT, foreground='#04140E',
                 font=('Segoe UI', 11, 'bold'), padding=(18, 11), borderwidth=0,
                 relief='flat', anchor='center')
    # Explicit disabled colors prevent ttk from leaking the platform's
    # default green/active map into the primary action while a batch runs.
    st.map('Premium.Primary.TButton',
           background=[('disabled', PANEL), ('pressed', '#17D3A3'), ('active', '#0FAC80')],
           foreground=[('disabled', MUTED), ('active', '#04140E')])
    st.configure('Premium.Secondary.TButton', background=ENTRY, foreground=FG, padding=(12, 10))
    st.map('Premium.Secondary.TButton', background=[('active', '#1F2C44')])
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
