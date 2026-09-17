#!/usr/bin/env python3
"""Lo stato del repo deve dire "non lo so", non zero, quando non risponde."""
from __future__ import annotations

from denaro import infra_repo


class _Ok:
    returncode = 0
    stdout = "abc1234" + chr(10) + "2" + chr(10)


class _Ko:
    returncode = 1
    stdout = ""


def test_parsing(monkeypatch):
    monkeypatch.setattr(infra_repo.subprocess, "run", lambda *a, **k: _Ok())
    out = infra_repo.stato_repo()
    assert set(out) == {"marcodg1", "mc2", "nuvola"}
    for v in out.values():
        assert v == {"head": "abc1234", "dirty": 2}


def test_lettura_fallita_non_e_zero(monkeypatch):
    """Un timeout non deve sembrare "repo pulito"."""
    monkeypatch.setattr(infra_repo.subprocess, "run", lambda *a, **k: _Ko())
    out = infra_repo.stato_repo()
    assert all(v["dirty"] is None for v in out.values())


def test_eccezione_non_e_zero(monkeypatch):
    def _boom(*a, **k):
        raise OSError("rete giu")
    monkeypatch.setattr(infra_repo.subprocess, "run", _boom)
    out = infra_repo.stato_repo()
    assert all(v["dirty"] is None for v in out.values())


def test_comando_ssh_usa_batchmode():
    cmd = " ".join(infra_repo._ssh_cmd(["utente@host", "-p", "22"], "/repo"))
    assert "BatchMode=yes" in cmd and "/repo" in cmd


def test_comando_locale_cita_il_repo():
    cmd = " ".join(infra_repo._git_cmd("/repo"))
    assert "rev-parse" in cmd and "status --porcelain" in cmd