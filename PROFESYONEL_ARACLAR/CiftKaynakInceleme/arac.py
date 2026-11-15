"""Gorsel Uretim Merkezi | Cift Kaynak Inceleme - UI bridge.

Existing application UI must call baslat() from its Professional Tools button.
This module does not add buttons or modify application files by itself.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import threading
from typing import Callable

_CALISMA_KILIDI = threading.Lock()

_SCRIPT = Path(__file__).resolve().with_name("CIFT_KAYNAK_INCELEME_HAZIRLA.ps1")


def baslat(
    parent=None,
    *,
    tamamlandi: Callable[[bool, str], None] | None = None,
    durum: Callable[[str], None] | None = None,
) -> bool:
    """Start nonblocking source-code packaging; script opens ZIP folder on success.

    parent: an existing Tk/CustomTkinter widget for safe .after() callback dispatch.
    tamamlandi: optional callback(ok, explanation). On Tk main thread when parent.
    durum: optional callback for brief starting status.
    Returns False if process could not be started.
    """
    if os.name != "nt":
        raise RuntimeError("Bu araç yalnızca Windows için hazırlanmıştır.")
    if not _SCRIPT.is_file():
        raise FileNotFoundError(f"Kaynak paketleme betiği bulunamadı: {_SCRIPT}")

    if not _CALISMA_KILIDI.acquire(blocking=False):
        if durum:
            try:
                if parent is not None:
                    parent.after(0, lambda: durum("Paketleme zaten çalışıyor."))
                else:
                    durum("Paketleme zaten çalışıyor.")
            except (RuntimeError, AttributeError):
                pass
        return False

    if tamamlandi is None:
        def tamamlandi(basarili: bool, bilgi: str):
            if parent is not None:
                from tkinter import messagebox
                if basarili:
                    messagebox.showinfo("Çift Kaynak İnceleme", bilgi, parent=parent)
                else:
                    messagebox.showerror("Çift Kaynak İnceleme", bilgi, parent=parent)
            else:
                print(bilgi)

    def dispatch(callback, *args):
        if callback is None:
            return
        if parent is None:
            callback(*args)
        else:
            try:
                parent.after(0, lambda: callback(*args))
            except (RuntimeError, AttributeError):
                # Parent has been destroyed / no working UI event queue.
                pass

    dispatch(durum, "İki kaynak dosya ağacı taranıyor ve ZIP hazırlanıyor...")
    command = [
        "powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive",
        "-ExecutionPolicy", "Bypass", "-File", str(_SCRIPT),
    ]
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    def worker():
        try:
            run = subprocess.run(
                command,
                cwd=str(_SCRIPT.parent),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding="utf-8",
                errors="replace",
                creationflags=flags,
                check=False,
            )
            lines = run.stdout.splitlines()
            out_path = next((line.split("=", 1)[1].strip() for line in lines
                             if line.startswith("ZIP_OUTPUT=")), "")
            if run.returncode == 0 and out_path and Path(out_path).is_file():
                dispatch(tamamlandi, True, f"ZIP hazırlandı: {out_path}")
            else:
                detail = (run.stderr or run.stdout or "Bilinmeyen hata").strip()
                dispatch(tamamlandi, False, "Paket oluşturulamadı: " + detail[-2000:])
        except Exception as exc:
            dispatch(tamamlandi, False, "Paketleme aracı çalıştırılamadı: " + str(exc))
        finally:
            _CALISMA_KILIDI.release()

    threading.Thread(target=worker, name="cift-kaynak-inceleme", daemon=True).start()
    return True
