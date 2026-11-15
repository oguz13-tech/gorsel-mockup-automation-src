"""Small native WebView2 host for the existing review Flask service.

The review backend remains the existing authenticated loopback Flask process;
this process only supplies its UI surface.  It never opens the system browser
and it never creates a second editor or persistence layer.
"""
from __future__ import annotations

import argparse
import ctypes
import os
import sys
import threading
import time


def _find_window_for_process(title: str) -> int | None:
    if os.name != "nt":
        return None
    user32 = ctypes.windll.user32
    found = []
    callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    @callback_type
    def callback(hwnd, _lparam):
        process_id = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
        if int(process_id.value) != os.getpid() or not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        if str(buffer.value) == title:
            found.append(int(hwnd))
            return False
        return True

    user32.EnumWindows(callback, 0)
    return found[0] if found else None


def _embed_into_tk(hwnd: int, parent_hwnd: int) -> bool:
    if os.name != "nt" or not hwnd or not parent_hwnd:
        return False
    user32 = ctypes.windll.user32
    GWL_STYLE = -16
    GWL_EXSTYLE = -20
    WS_CHILD = 0x40000000
    WS_POPUP = 0x80000000
    WS_CAPTION = 0x00C00000
    WS_THICKFRAME = 0x00040000
    WS_MINIMIZEBOX = 0x00020000
    WS_MAXIMIZEBOX = 0x00010000
    WS_SYSMENU = 0x00080000
    WS_BORDER = 0x00800000
    WS_DLGFRAME = 0x00400000
    WS_EX_APPWINDOW = 0x00040000
    WS_EX_WINDOWEDGE = 0x00000100
    WS_EX_CLIENTEDGE = 0x00000200
    SWP_NOZORDER = 0x0004
    SWP_SHOWWINDOW = 0x0040
    SWP_FRAMECHANGED = 0x0020
    style = user32.GetWindowLongW(hwnd, GWL_STYLE)
    exstyle = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    user32.SetParent(hwnd, parent_hwnd)
    # The WebView2 host is a child surface of Graphite, not a second desktop
    # window.  Strip every non-client decoration before it is shown so the
    # title bar, min/max/close buttons and resize frame cannot leak through
    # the Tk workbench.
    style = (style & ~(WS_POPUP | WS_CAPTION | WS_THICKFRAME |
                       WS_MINIMIZEBOX | WS_MAXIMIZEBOX | WS_SYSMENU |
                       WS_BORDER | WS_DLGFRAME)) | WS_CHILD
    exstyle &= ~(WS_EX_APPWINDOW | WS_EX_WINDOWEDGE | WS_EX_CLIENTEDGE)
    user32.SetWindowLongW(hwnd, GWL_STYLE, style)
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, exstyle)
    rect = _RECT()
    user32.GetClientRect(parent_hwnd, ctypes.byref(rect))
    user32.SetWindowPos(
        hwnd, 0, 0, 0,
        max(1, rect.right - rect.left), max(1, rect.bottom - rect.top),
        SWP_NOZORDER | SWP_SHOWWINDOW | SWP_FRAMECHANGED,
    )
    return True


class _RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


def _resize_embedded(hwnd: int, parent_hwnd: int, window) -> None:
    if os.name != "nt":
        return
    user32 = ctypes.windll.user32
    rect = _RECT()
    while user32.IsWindow(hwnd) and user32.IsWindow(parent_hwnd):
        user32.GetClientRect(parent_hwnd, ctypes.byref(rect))
        user32.SetWindowPos(
            hwnd, 0, 0, 0,
            max(1, rect.right - rect.left), max(1, rect.bottom - rect.top),
            0x0004 | 0x0040,
        )
        time.sleep(0.25)
    try:
        window.destroy()
    except Exception:
        pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--title", default="Şablon İnceleme · Görsel Üretim Merkezi")
    parser.add_argument("--parent-hwnd", type=int, default=0)
    args = parser.parse_args()
    try:
        import webview
    except Exception as exc:
        print(f"WEBVIEW2_PYTHON_BRIDGE_MISSING: {exc}", file=sys.stderr)
        return 2

    try:
        window = webview.create_window(
            args.title,
            args.url,
            width=1440,
            height=900,
            min_size=(1120, 720),
            # The surface is immediately re-parented into Graphite.  Do not
            # create a second decorated/top-level editor window or a close
            # confirmation belonging to that hidden host.
            frameless=True,
            confirm_close=False,
        )
        if args.parent_hwnd:
            def attach(*_args):
                for _ in range(40):
                    native = _find_window_for_process(args.title)
                    if native and _embed_into_tk(native, args.parent_hwnd):
                        threading.Thread(
                            target=_resize_embedded,
                            args=(native, args.parent_hwnd, window),
                            daemon=True,
                            name="webview2-resize",
                        ).start()
                        return
                    time.sleep(0.1)
                print("WEBVIEW2_TK_EMBED_FAILED", file=sys.stderr)
                try:
                    window.destroy()
                except Exception:
                    pass
            window.events.shown += attach
        # EdgeChromium is the WebView2 backend on Windows.  Do not fall back
        # to a system browser if WebView2 is unavailable.
        webview.start(gui="edgechromium", debug=False)
        return 0
    except Exception as exc:
        print(f"WEBVIEW2_START_FAILED: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())

