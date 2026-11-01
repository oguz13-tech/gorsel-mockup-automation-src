"""V4.9.4 safe, visible GUI exit regressions (no real user data)."""
from __future__ import annotations
import sys
from pathlib import Path
from unittest.mock import Mock
import types
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'MERKEZ'))
import merkez as appmod


class FakeTop:
    def winfo_exists(self):
        return True


class FakeProc:
    def __init__(self, active=True):
        self.active=active
        self.terminate=Mock()
        self.wait=Mock(return_value=0)
        self.pid=1234
    def poll(self):
        return None if self.active else 0


def center(monkeypatch):
    obj=appmod.Center.__new__(appmod.Center)
    obj._closing=False
    obj.running=False
    obj.batch_windows=[]
    obj.root=Mock()
    obj.root.winfo_children.return_value=[]
    obj.editor_proc=None
    obj.inbox_watcher=Mock()
    obj.ham_design_watcher=Mock()
    obj.review_button=Mock()
    obj.tools_button=Mock()
    obj._log=Mock()
    obj.status=Mock()
    obj.editor_port=8080
    monkeypatch.setattr(appmod.tk,'Toplevel',FakeTop)
    monkeypatch.setattr(appmod.messagebox,'showinfo',Mock())
    monkeypatch.setattr(appmod.messagebox,'showerror',Mock())
    monkeypatch.setattr(appmod.messagebox,'askyesno',Mock(return_value=False))
    return obj


def test_idle_exit_stops_watchers_and_returns_to_batch(monkeypatch):
    c=center(monkeypatch)
    c.close()
    c.inbox_watcher.stop.assert_called_once()
    c.ham_design_watcher.stop.assert_called_once()
    c.root.destroy.assert_called_once()
    assert c._closing is True
    c.close()
    c.root.destroy.assert_called_once()


def test_active_batch_cannot_be_killed(monkeypatch):
    c=center(monkeypatch)
    c.batch_windows=[types.SimpleNamespace(worker=types.SimpleNamespace(is_alive=lambda:True))]
    c.close()
    c.root.destroy.assert_not_called()
    c.inbox_watcher.stop.assert_not_called()


def test_active_daily_cannot_be_killed(monkeypatch):
    c=center(monkeypatch);c.running=True
    c.close();c.root.destroy.assert_not_called()


def test_open_editor_window_must_be_saved_first(monkeypatch):
    c=center(monkeypatch)
    c.root.winfo_children.return_value=[FakeTop()]
    c.close();c.root.destroy.assert_not_called()


def test_local_flask_exit_requires_explicit_approval(monkeypatch):
    c=center(monkeypatch);c.editor_proc=FakeProc()
    c.close();c.root.destroy.assert_not_called()
    appmod.messagebox.askyesno.assert_called_once()


def test_rejected_verified_server_shutdown_preserves_ui(monkeypatch):
    c=center(monkeypatch);c.editor_proc=FakeProc()
    appmod.messagebox.askyesno.return_value=True
    c.stop_legacy_editor=Mock(return_value=False)
    c.close()
    c.stop_legacy_editor.assert_called_once_with(confirmed=True)
    c.root.destroy.assert_not_called()


def test_successful_authenticated_server_exit(monkeypatch):
    c=center(monkeypatch);c.editor_proc=FakeProc()
    appmod.messagebox.askyesno.return_value=True
    c.stop_legacy_editor=Mock(return_value=True)
    c.close()
    c.stop_legacy_editor.assert_called_once_with(confirmed=True)
    c.root.destroy.assert_called_once()


def test_server_identity_mismatch_does_not_terminate_unknown_process(monkeypatch):
    c=center(monkeypatch);c.editor_proc=FakeProc()
    c.editor_identity=('runtime','code','token')
    monkeypatch.setitem(sys.modules,'legacy_manager',types.SimpleNamespace(
        server_identity_diagnostic=lambda *a,**k:{'ready':False,'reason':'UNKNOWN_OWNER'}))
    stopped=c.stop_legacy_editor(confirmed=True)
    assert stopped is False
    c.editor_proc.terminate.assert_not_called()
    c.root.destroy.assert_not_called()
    appmod.messagebox.showerror.assert_called_once()


def test_watcher_failure_does_not_silently_destroy(monkeypatch):
    c=center(monkeypatch)
    c.inbox_watcher.stop.side_effect=RuntimeError('watcher timeout')
    c.close()
    assert c._closing is False
    c.root.destroy.assert_not_called()
    appmod.messagebox.showerror.assert_called_once()


def test_buttons_bound_to_safe_exit_and_version_literal():
    gui=(Path(__file__).resolve().parents[1]/'MERKEZ/premium_dashboard_v489.py').read_text('utf8')
    legacy=(Path(__file__).resolve().parents[1]/'MERKEZ/merkez.py').read_text('utf8')
    assert "'⏻  Programı Kapat', app.close" in gui
    assert "'⏻   PROGRAMI KAPAT', app.close" in gui
    assert "text='⏻  PROGRAMI GÜVENLE KAPAT',command=self.close" in legacy
    from version_v47 import VERSION
    assert VERSION in gui
