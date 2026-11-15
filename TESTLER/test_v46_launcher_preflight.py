import socket
from pathlib import Path

import pytest

from scripts import v46_launcher_preflight as launcher


def test_choose_port_uses_8080_when_free(monkeypatch):
    monkeypatch.setattr(launcher, "available", lambda port: port == 8080)
    monkeypatch.delenv("MOCKUP_PORT", raising=False)
    assert launcher.choose_port() == 8080


def test_choose_port_falls_back_without_touching_owner(monkeypatch):
    monkeypatch.setattr(launcher, "available", lambda port: port == 8081)
    monkeypatch.delenv("MOCKUP_PORT", raising=False)
    assert launcher.choose_port() == 8081


def test_choose_port_reports_occupied_ports(monkeypatch):
    monkeypatch.setattr(launcher, "available", lambda port: False)
    monkeypatch.delenv("MOCKUP_PORT", raising=False)
    with pytest.raises(RuntimeError, match="occupied"):
        launcher.choose_port()
