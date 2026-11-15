"""Ortak tablo/liste geliştirmeleri: tutamaçla sütun boyutlandırma, yatay
kaydırma çubuğu, tam-metin araç ipucu (tooltip).

Bütün Graphite tabloları bu yardımcıyı çağırır. Modül salt-okunur
görünümlerle ilgilenir; hiçbir veriye dokunmaz.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

ACCENT = '#17D3A3'
ACCENT_DARK = '#0B7A5F'
PANEL = '#131C2B'
PANEL_RAISED = '#182238'
BORDER = '#22304A'
FG = '#E9EFF9'
MUTED = '#66789B'


# ---------------------------------------------------------------- tooltip
class DarkTip(tk.Toplevel):
    """Basit koyu renkli tooltip penceresi."""

    def __init__(self, root, text: str):
        super().__init__(root)
        self.overrideredirect(True)
        self.configure(bg=BORDER)
        self.transient(root)
        body = tk.Label(self, text=text, bg=PANEL_RAISED, fg=FG,
                        justify='left', anchor='w', wraplength=720,
                        font=('Segoe UI', 9), padx=10, pady=6)
        body.pack(fill='both', expand=True)
        px = root.winfo_pointerx() + 18
        py = root.winfo_pointery() + 18
        self.geometry(f'+{px}+{py}')


def _short(text: str, limit: int = 1400) -> str:
    text = str(text)
    if len(text) > limit:
        return text[: limit - 1] + '…'
    return text


class TreeTooltip:
    """Seçili hücrenin tam metnini hover anında gösterir."""

    def __init__(self, tree: ttk.Treeview, *, delay: int = 420):
        self.tree = tree
        self._delay = delay
        self._after = None
        self._tip = None
        tree.bind('<Motion>', self._motion, add='+')
        tree.bind('<Leave>', self.hide, add='+')
        tree.bind('<Button-1>', self.hide, add='+')

    def _motion(self, event):
        row = self.tree.identify_row(event.y)
        col = self.tree.identify_column(event.x)
        self.hide()
        if not row or not col:
            return
        value = self.tree.set(row, col)
        if not value:
            return
        delay = self._delay
        if self._after is not None:
            self.tree.after_cancel(self._after)
        self._after = self.tree.after(delay, lambda: self._show(value))

    def _show(self, text: str):
        self._tip = DarkTip(self.tree, _short(text))

    def hide(self, *_):
        if self._after is not None:
            try:
                self.tree.after_cancel(self._after)
            except Exception:
                pass
            self._after = None
        if self._tip is not None:
            try:
                self._tip.destroy()
            except Exception:
                pass
            self._tip = None


# ------------------------------------------------------- column resizing
class ColumnResizer:
    """Başlık tutamaçlarında tıklayıp sürükleme ile sütun genişliği."""

    def __init__(self, tree: ttk.Treeview, columns, *, min_width: int = 44):
        self.tree = tree
        self.columns = list(columns)
        self.min_width = min_width
        self._active = None
        self._start_x = 0
        self._start_width = 0
        tree.bind('<Motion>', self._motion, add='+')
        tree.bind('<Button-1>', self._press, add='+')
        tree.bind('<B1-Motion>', self._drag, add='+')
        tree.bind('<ButtonRelease-1>', self._release, add='+')

    def _near_boundary(self, event):
        self.tree.update_idletasks()
        try:
            xview = self.tree.xview()
        except Exception:
            xview = (0.0, 1.0)
        total = sum(self.tree.column(c, 'width') for c in self.columns) or 1
        offset = int(xview[0] * total)
        cum = 0
        bounds = []
        for c in self.columns:
            cum += self.tree.column(c, 'width')
            bounds.append(cum - offset)
        for i in range(len(self.columns) - 1):
            if abs(event.x - bounds[i]) <= 5:
                return i
        return None

    def _motion(self, event):
        if self._active is not None:
            return
        i = self._near_boundary(event)
        self.tree.configure(cursor='sb_h_double_arrow' if i is not None else '')

    def _press(self, event):
        i = self._near_boundary(event)
        if i is None:
            return None
        self._active = i
        self._start_x = event.x
        self._start_width = self.tree.column(self.columns[i], 'width')
        return 'break'

    def _drag(self, event):
        if self._active is not None:
            dx = event.x - self._start_x
            col = self.columns[self._active]
            self.tree.column(col, width=max(self.min_width, self._start_width + dx))

    def _release(self, event):
        self._active = None


# --------------------------------------------------------- style / setup
def style_tree(tree: ttk.Treeview) -> None:
    st = ttk.Style(tree)
    st.configure('Treeview', background=PANEL, fieldbackground=PANEL,
                 foreground=FG, rowheight=26, borderwidth=0)
    st.configure('Treeview.Heading', background=PANEL_RAISED, foreground=FG,
                 relief='flat', padding=(6, 5))
    st.map('Treeview',
           background=[('selected', ACCENT_DARK)],
           foreground=[('selected', '#FFFFFF')])


def enhance_tree(tree: ttk.Treeview, columns, *, min_width: int = 44,
                 heading_text: bool = True) -> ttk.Treeview:
    """Renk teması + tutamaçla resize + tam metin tooltip."""
    style_tree(tree)
    # ttk.Treeview has no takefocus() method; takefocus is a widget option.
    try:
        tree.configure(takefocus=False)
    except tk.TclError:
        pass
    for col in columns:
        try:
            tree.column(col, minwidth=min_width)
        except Exception:
            pass
    ColumnResizer(tree, columns, min_width=min_width)
    TreeTooltip(tree)
    return tree


def toggle_xscroll(sb: ttk.Scrollbar, first, last) -> None:
    first = float(first)
    last = float(last)
    sb.set(first, last)
    if first <= 0.001 and last >= 0.999:
        try:
            sb.grid_remove()
        except Exception:
            try:
                sb.pack_forget()
            except Exception:
                pass
    else:
        try:
            sb.grid()
        except Exception:
            pass


def add_horizontal_scrollbar(tree: ttk.Treeview, row: int, column: int = 0,
                             columnspan: int = 1, sticky: str = 'ew') -> ttk.Scrollbar:
    """grid düzeni kullanan tablolar için yatay kaydırma çubuğunu bağlar."""
    sb = ttk.Scrollbar(tree.master, orient='horizontal', command=tree.xview)
    tree.configure(xscrollcommand=lambda f, l: toggle_xscroll(sb, f, l))
    sb.grid(row=row, column=column, columnspan=columnspan, sticky=sticky)
    return sb


def add_packed_horizontal_scrollbar(parent, tree: ttk.Treeview) -> ttk.Scrollbar:
    """pack düzeni kullanan tablolar için yatay kaydırma çubuğunu bağlar."""
    sb = ttk.Scrollbar(parent, orient='horizontal', command=tree.xview)
    tree.configure(xscrollcommand=sb.set)
    sb.pack(side='bottom', fill='x')
    return sb


# ------------------------------------------------------------ Listbox
class ListboxTooltip:
    """Listbox satırında kesilen metnin tamamını hover'da gösterir."""

    def __init__(self, listbox: tk.Listbox, *, delay: int = 420):
        self.listbox = listbox
        self._delay = delay
        self._after = None
        self._tip = None
        listbox.bind('<Motion>', self._motion, add='+')
        listbox.bind('<Leave>', self.hide, add='+')

    def _motion(self, event):
        self.hide()
        try:
            index = self.listbox.nearest(event.y)
            bbox = self.listbox.bbox(index)
        except Exception:
            return
        if not bbox:
            return
        x, y, w, h = bbox
        if not (y <= event.y <= y + h):
            return
        try:
            text = self.listbox.get(index)
        except Exception:
            return
        if text:
            self._after = self.listbox.after(self._delay, lambda: self._show(text))

    def _show(self, text: str):
        self._tip = DarkTip(self.listbox, _short(text))

    def hide(self, *_):
        if self._after is not None:
            try:
                self.listbox.after_cancel(self._after)
            except Exception:
                pass
            self._after = None
        if self._tip is not None:
            try:
                self._tip.destroy()
            except Exception:
                pass
            self._tip = None


def attach_listbox_tooltip(listbox: tk.Listbox) -> ListboxTooltip:
    return ListboxTooltip(listbox)


def add_listbox_xscroll(listbox: tk.Listbox, row: int = None, column: int = 0,
                        columnspan: int = 1, parent=None) -> ttk.Scrollbar:
    """Listbox için yatay kaydırma çubuğu. row verilirse grid, yoksa pack."""
    host = parent or listbox.master
    sb = ttk.Scrollbar(host, orient='horizontal', command=listbox.xview)
    listbox.configure(xscrollcommand=sb.set)
    if row is None:
        sb.pack(side='bottom', fill='x')
    else:
        sb.grid(row=row, column=column, columnspan=columnspan, sticky='ew')
    return sb
