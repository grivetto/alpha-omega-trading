#!/usr/bin/env python3
"""Regressioni per tools/fleet_integrity.py (flotta Denaro).

Coprono i difetti che rendevano il check inutilizzabile il 26/09:
a) crash su file di aggregazione (lista) nella dir health;
b) falsi allarmi su unit `oneshot` fra due run del proprio timer e su
   `NRestarts` storici (113 e 710 osservati su unit stabili da ~28h).

I test girano senza toccare la macchina: `_run` e' sostituito per la sola
famiglia systemctl e la dir health vera e' neutralizzata.
"""
from __future__ import annotations

import importlib.util
import json
import os
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _carica_modulo():
    spec = importlib.util.spec_from_file_location(
        "fleet_integrity", ROOT / "tools" / "fleet_integrity.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def mod(monkeypatch, tmp_path):
    m = _carica_modulo()
    # un test non deve leggere la health vera della macchina che lo esegue
    monkeypatch.setattr(m, "DIR_HEALTH_NOTE", ())
    monkeypatch.setenv("FLEET_INTEGRITY_STATE", str(tmp_path / "restarts.json"))
    return m


class FakeSystemctl:
    """Sostituisce `_run` per i comandi systemctl; tutto il resto -> ''."""

    def __init__(self, unit_lines=(), props=None, values=None):
        self.unit_lines = list(unit_lines)
        self.props = props or {}      # unit -> {prop: value}
        self.values = values or {}    # (unit, prop) -> valore di `show --value`

    def __call__(self, cmd, timeout=25):
        if "list-units" in cmd:
            return "\n".join(self.unit_lines) + ("\n" if self.unit_lines else "")
        if "show" in cmd:
            unit = cmd[-1]
            if "--value" in cmd:
                prop = cmd[cmd.index("--value") - 1]
                return self.values.get((unit, prop), "")
            out = []
            i = 0
            while i < len(cmd) - 1:
                if cmd[i] == "-p":
                    prop = cmd[i + 1]
                    if prop != "--value":
                        val = self.props.get(unit, {}).get(prop)
                        if val is not None:
                            out.append(f"{prop}={val}")
                    i += 2
                else:
                    i += 1
            return "\n".join(out)
        return ""


# --- check_trading ---------------------------------------------------------------

def test_check_trading_salta_file_lista(mod, tmp_path):
    """trend.json e' una lista: prima crashava (AttributeError su .get)."""
    d = tmp_path
    vecchio = time.time() - 3600
    (d / "trend.json").write_text(json.dumps([{"a": 1}, {"b": 2}]),
                                  encoding="utf-8")
    os.utime(d / "trend.json", (vecchio, vecchio))   # e nemmeno deve allarmare
    (d / "b1.json").write_text(json.dumps(
        {"error": "equity inattendibile", "blocked": True, "total_equity": 0.0}),
        encoding="utf-8")
    e = mod.Esito()
    mod.check_trading(e, dir_health=str(d))          # non deve sollevare
    assert len(e.allarmi) == 1
    assert "b1.json" in e.allarmi[0]["prova"]


def test_check_trading_fossile(mod, tmp_path):
    """Un file per-bot fermo da piu' di max_eta_s e' un allarme."""
    d = tmp_path
    vecchio = time.time() - 3600
    (d / "stale.json").write_text(json.dumps({"error": "", "blocked": False}),
                                  encoding="utf-8")
    os.utime(d / "stale.json", (vecchio, vecchio))
    (d / "fresco.json").write_text(json.dumps({"error": "", "blocked": False}),
                                   encoding="utf-8")
    e = mod.Esito()
    mod.check_trading(e, dir_health=str(d))
    assert len(e.allarmi) == 1
    assert "FOSSILE" in e.allarmi[0]["cosa"]


def test_check_trading_ignora_cache_dashboard(mod, tmp_path):
    """infra_last_good.json e' cache ON-DEMAND del dashboard, non un heartbeat.

    Falso positivo osservato su MARCODG1: ferma da 3h31m perche' nessuno aveva
    aperto la dashboard di notte — non e' un guasto.
    """
    d = tmp_path
    vecchio = time.time() - 3600
    (d / "infra_last_good.json").write_text(
        json.dumps({"nodes": {"mc2": {}}, "last_good": True}), encoding="utf-8")
    os.utime(d / "infra_last_good.json", (vecchio, vecchio))
    e = mod.Esito()
    mod.check_trading(e, dir_health=str(d))
    assert e.allarmi == []


# --- check_systemd ---------------------------------------------------------------

UNITS_BASE = [
    "denaro-watchdog.service loaded inactive dead Watchdog della flotta",
    "denaro-grafana.service  loaded active   running Grafana",
    "denaro-node-pape.service loaded active running Nodo paper",
    "denaro-watchdog.timer   loaded active   waiting Watchdog timer",
]

PROPS_BASE = {
    "denaro-watchdog.service": {"Type": "oneshot", "Result": "success",
                                "NRestarts": "0"},
    "denaro-grafana.service": {"Type": "simple", "Result": "success",
                               "NRestarts": "113"},
    "denaro-node-pape.service": {"Type": "simple", "Result": "success",
                                 "NRestarts": "710"},
    "denaro-watchdog.timer": {"Type": "timer", "Result": "success",
                              "NRestarts": "0"},
}


def test_systemd_oneshot_fra_due_run_non_allarma(mod, monkeypatch):
    """denaro-watchdog inactive/dead dopo un run riuscito: stato normale."""
    monkeypatch.setattr(mod, "_run", FakeSystemctl(UNITS_BASE, PROPS_BASE))
    e = mod.Esito()
    mod.check_systemd(e)
    assert e.allarmi == []


def test_systemd_nrestarts_storici_non_allarmano(mod, monkeypatch):
    """113 e 710 storici su unit attive: il contatore da solo non e' ciclo."""
    monkeypatch.setattr(mod, "_run", FakeSystemctl(UNITS_BASE, PROPS_BASE))
    e = mod.Esito()
    mod.check_systemd(e)
    assert e.allarmi == []


def test_systemd_nrestarts_in_crescita_allarma(mod, monkeypatch, tmp_path):
    """Il ciclo in corso si vede dal DELTA fra due esecuzioni, non dal totale."""
    stato = tmp_path / "restarts.json"
    stato.write_text(json.dumps({"denaro-grafana.service": 100,
                                 "denaro-node-pape.service": 708}),
                     encoding="utf-8")
    monkeypatch.setattr(mod, "_run", FakeSystemctl(UNITS_BASE, PROPS_BASE))
    e = mod.Esito()
    mod.check_systemd(e)          # grafana 100->113 (+13) allarma; pape +2 no
    assert len(e.allarmi) == 1
    assert "NRestarts=113 (era 100)" in e.allarmi[0]["prova"]
    # lo stato viene aggiornato per l'esecuzione successiva
    salvato = json.loads(stato.read_text(encoding="utf-8"))
    assert salvato["denaro-grafana.service"] == 113
    assert salvato["denaro-node-pape.service"] == 710


def test_systemd_unita_giu_allarma(mod, monkeypatch):
    """Unita' failed: allarme; con NRestarts patologico, due reperti."""
    units = UNITS_BASE + ["denaro-node-mc2.service loaded failed failed Nodo"]
    props = dict(PROPS_BASE)
    props["denaro-node-mc2.service"] = {"Type": "simple", "Result": "exit-code",
                                        "NRestarts": "553"}
    monkeypatch.setattr(mod, "_run", FakeSystemctl(units, props))
    e = mod.Esito()
    mod.check_systemd(e)
    prove = [r["prova"] for r in e.allarmi]
    assert any("failed/failed" in p for p in prove)
    assert any("NRestarts=553" in p for p in prove)


def test_systemd_oneshot_fallito_allarma(mod, monkeypatch):
    """Un oneshot che NON ha finito bene non gode dell'esenzione."""
    units = ["denaro-pulizia.service loaded failed failed Pulizia"]
    props = {"denaro-pulizia.service": {"Type": "oneshot",
                                        "Result": "exit-code", "NRestarts": "1"}}
    monkeypatch.setattr(mod, "_run", FakeSystemctl(units, props))
    e = mod.Esito()
    mod.check_systemd(e)
    assert len(e.allarmi) == 1
    assert "failed/failed" in e.allarmi[0]["prova"]


def test_systemd_path_inesistente_allarma(mod, monkeypatch):
    """La causa radice dei restart del 25/09: direttive verso path inesistenti."""
    units = ["denaro-rotto.service loaded active running Rotto"]
    props = {"denaro-rotto.service": {"Type": "simple", "Result": "success",
                                      "NRestarts": "1125"}}
    values = {("denaro-rotto.service", "ExecStart"):
              "/nonexistent-flotta-xyz/venv/bin/python3 -m denaro"}
    monkeypatch.setattr(mod, "_run", FakeSystemctl(units, props, values))
    e = mod.Esito()
    mod.check_systemd(e)
    assert any("ExecStart=/nonexistent-flotta-xyz/venv/bin/python3" in r["prova"]
               for r in e.allarmi)


# --- main ------------------------------------------------------------------------

def test_main_errore_interno_esce_2(mod, monkeypatch, capsys):
    """exit 2 = il check e' rotto; NON deve confondersi con exit 1 (allarmi)."""

    def esplode(*_a, **_k):
        raise RuntimeError("boom del check")

    monkeypatch.setattr(mod, "esegui", esplode)
    rc = mod.main(["--json"])
    assert rc == 2
    out = json.loads(capsys.readouterr().out)
    assert out["esito"] == 2
    assert "boom del check" in out["errore"]
