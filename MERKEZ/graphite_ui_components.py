"""Ortak Graphite arayüz parçaları.

Bu modül yalnızca Tk widget'larının görünümünü ve yerleşim sözleşmesini
ortaklaştırır; iş mantığına, veri kaynaklarına veya kalıcı kayıtlara dokunmaz.
Modüller aynı başlık, eylem çubuğu, durum rozeti ve boş/hata durumlarını
kullanarak tek bir uygulama deneyimi verir.
"""
from __future__ import annotations

import tkinter as tk
from typing import Callable

SIDE = '#0F1622'
PANEL = '#131C2B'
PANEL_RAISED = '#182238'
BORDER = '#22304A'
ACCENT = '#17D3A3'
BLUE = '#5AA9FF'
YELLOW = '#F0B84C'
RED = '#EF6A73'
GREEN = '#3FD98A'
FG = '#E9EFF9'
MUTED = '#8A9AB8'


def module_header(parent, title: str, subtitle: str = '', *, badge: str | None = None,
                  on_refresh: Callable[[], object] | None = None,
                  refresh_text: str = '⟳ Yenile') -> tk.Frame:
    """Create the standard two-line module header and action area."""
    frame = tk.Frame(parent, bg=PANEL, bd=0, highlightthickness=0)
    copy = tk.Frame(frame, bg=PANEL)
    copy.pack(side='left', anchor='w', padx=14, pady=(10, 8))
    title_row = tk.Frame(copy, bg=PANEL)
    title_row.pack(anchor='w')
    tk.Label(title_row, text=title, bg=PANEL, fg=FG,
             font=('Segoe UI', 12, 'bold')).pack(side='left')
    if badge:
        tk.Label(title_row, text=f'  {badge}  ', bg='#20384A', fg=ACCENT,
                 font=('Segoe UI', 8, 'bold'), padx=5, pady=2).pack(side='left', padx=(8, 0))
    if subtitle:
        tk.Label(copy, text=subtitle, bg=PANEL, fg=MUTED,
                 font=('Segoe UI', 8), anchor='w').pack(anchor='w', pady=(3, 0))
    actions = tk.Frame(frame, bg=PANEL)
    actions.pack(side='right', anchor='e', padx=8, pady=6)
    if on_refresh is not None:
        tk.Button(actions, text=refresh_text, command=on_refresh, bg=PANEL_RAISED, fg=FG,
                  relief='flat', cursor='hand2', font=('Segoe UI', 9, 'bold'),
                  padx=12, pady=5).pack(side='right')
    return frame


def action_button(parent, text: str, command: Callable[[], object], *, primary: bool = False,
                  danger: bool = False, compact: bool = False, **grid) -> tk.Button:
    """Create a consistent Graphite action button; optionally grid it."""
    color = '#8E3D49' if danger else (ACCENT if primary else PANEL_RAISED)
    fg = '#07151A' if primary else FG
    button = tk.Button(parent, text=text, command=command, bg=color, fg=fg,
                       activebackground=color, activeforeground=fg, relief='flat',
                       cursor='hand2', font=('Segoe UI', 9, 'bold'),
                       padx=10 if compact else 12, pady=5 if compact else 8)
    if grid:
        button.grid(**grid)
    return button


def status_badge(parent, text: str, *, tone: str = 'neutral') -> tk.Label:
    colors = {'ok': (GREEN, '#10291F'), 'warning': (YELLOW, '#332A12'),
              'error': (RED, '#32171D'), 'info': (BLUE, '#152A45'),
              'neutral': (MUTED, '#202B3F')}
    fg, bg = colors.get(tone, colors['neutral'])
    return tk.Label(parent, text=f' {text} ', bg=bg, fg=fg,
                    font=('Segoe UI', 8, 'bold'), padx=5, pady=2)


def empty_state(parent, title: str, detail: str = '', *, tone: str = 'neutral') -> tk.Frame:
    frame = tk.Frame(parent, bg=PANEL_RAISED, bd=0, highlightthickness=1,
                     highlightbackground=BORDER)
    status_badge(frame, 'HAZIR', tone=tone).pack(anchor='w', padx=14, pady=(14, 5))
    tk.Label(frame, text=title, bg=PANEL_RAISED, fg=FG,
             font=('Segoe UI', 10, 'bold'), anchor='w').pack(anchor='w', padx=14)
    if detail:
        tk.Label(frame, text=detail, bg=PANEL_RAISED, fg=MUTED,
                 font=('Segoe UI', 8), anchor='w', justify='left', wraplength=620).pack(
                     anchor='w', padx=14, pady=(4, 14))
    return frame
