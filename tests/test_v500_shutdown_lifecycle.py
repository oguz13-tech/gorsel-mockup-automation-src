"""Regression tests for the V5.0 center shutdown/startup lifecycle.

These tests intentionally use a small headless Center double.  They do not
open Tk windows or touch the production SQLite/template roots.
"""

from __future__ import annotations

import queue
import sys
import threading
from pathlib import Path


MERKEZ = Path(__file__).resolve().parents[1] / "MERKEZ"
if str(MERKEZ) not in sys.path:
    sys.path.insert(0, str(MERKEZ))

from merkez import Center  # noqa: E402


class _Root:
    def __init__(self):
        self.destroyed = False

    def winfo_children(self):
        return []

    def destroy(self):
        self.destroyed = True

    def after(self, *_args):
        return None


class _Value:
    def __init__(self, value=""):
        self.value = value

    def set(self, value):
        self.value = value


class _Log:
    def configure(self, **_kwargs):
        return None

    def insert(self, *_args):
        return None

    def see(self, *_args):
        return None


def _center_for_close():
    center = Center.__new__(Center)
    center.root = _Root()
    center._closing = False
    center._shutdown_requested = False
    center._startup_lock = threading.Lock()
    center._inbox_backup_in_progress = False
    center._inbox_preflight_pending = False
    center._inbox_watcher_pending = False
    center._ham_watcher_pending = True
    center.batch_windows = []
    center.running = False
    center.editor_proc = None
    center.webview_proc = None
    center.inbox_watcher = None
    center.ham_design_watcher = None
    return center


def test_slow_watcher_start_does_not_block_close(monkeypatch):
    center = _center_for_close()
    messages = []
    monkeypatch.setattr("merkez.messagebox.showinfo", lambda *args, **kwargs: messages.append(args))

    center.close()

    assert center.root.destroyed is True
    assert messages == []
    assert center._shutdown_requested is True


def test_close_warns_only_for_active_database_backup(monkeypatch):
    center = _center_for_close()
    center._inbox_backup_in_progress = True
    messages = []
    monkeypatch.setattr("merkez.messagebox.showinfo", lambda *args, **kwargs: messages.append(args))

    center.close()

    assert center.root.destroyed is False
    assert messages and messages[0][0] == "Güvenlik yedeği sürüyor"


def test_broken_watcher_keeps_window_open_and_allows_retry(monkeypatch):
    # Yeni güvenli kapatma sözleşmesi: durdurulamayan izleyici varken Tk yok
    # edilmez (yazma hâlâ sürüyordur), kullanıcıya hatası gösterilir ve
    # kapanış işaretleri geri alınır ki X düğmesi yeniden denenebilsin.
    center = _center_for_close()
    center._recent_logs = []
    center.log = _Log()
    errors = []
    monkeypatch.setattr(
        "merkez.messagebox.showerror",
        lambda *args, **kwargs: errors.append(args),
    )

    class BrokenWatcher:
        def stop(self):
            raise RuntimeError("watcher already stopped")

    center.inbox_watcher = BrokenWatcher()
    center.close()

    assert center.root.destroyed is False
    assert errors and errors[0][0] == 'Güvenli kapanış tamamlanmadı'
    assert center._closing is False
    assert center._shutdown_requested is False


def test_inbox_failure_clears_all_startup_flags():
    center = _center_for_close()
    center.messages = queue.Queue()
    center.messages.put(("inbox_failed", "watcher test failure"))
    center._recent_logs = []
    center.log = _Log()
    center.status = _Value()
    center.root.after = lambda *_args: None
    center._inbox_preflight_pending = True
    center._inbox_watcher_pending = True
    center._inbox_backup_in_progress = True

    center.poll()

    assert center._inbox_preflight_pending is False
    assert center._inbox_watcher_pending is False
    assert center._inbox_backup_in_progress is False
    assert "kapanış serbest" in center.status.value


def test_failed_preflight_reports_ready_without_locking_close(monkeypatch):
    center = _center_for_close()
    center._recent_logs = []
    center.log = _Log()
    center.status = _Value()
    center.runtime = Path("runtime")
    center.root.after = lambda *_args: None
    center._inbox_preflight_pending = True

    center._inbox_finish_preflight((center.runtime, {
        "ready": False,
        "problems": ["test preflight failure"],
    }))

    assert center._inbox_preflight_pending is False
    assert "ön denetim başarısız" in center.status.value
