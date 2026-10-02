#!/usr/bin/env python3
"""Watchdog alert Denaro sul canale Telegram di progetto (@DenaroAlertBot) — zero silenzi.

Modalità:
  check    (default) — mc2: container docker attesi, unit utente critiche, disco.
  carry    — MARCODG1 via ssh: raggiungibilità, monitor canary fermo, anomalie canary,
             (i servizi core li copre fleet_integrity centrale quando abilitato).
  digest   — riepilogo giornaliero (sempre inviato): capitale, flotta, canary.
  selftest — invia allarme di prova + rientro (verifica end-to-end della catena).

Cron (mc2):
  */5   watch_alerts.py check
  */15  watch_alerts.py carry
  0 9   watch_alerts.py digest

Anti-spam e retry: tools/alert_lib.py (max 1 messaggio/ora per chiave + spool).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from alert_lib import flush_spool, gestisci, invia_o_spool  # noqa: E402

CONTAINERS = ["agent-zero", "zabbix-web", "zabbix-server", "zabbix-db", "freellmapi-freellmapi-1"]
UNITS = ["fabbrica-tick.timer", "hermes-gateway.service", "denaro-node-mc2.service"]
DISCO_MAX_PCT = 90.0
MONITOR_FERMO_S = 1800  # il cron canary gira ogni 10': oltre 30' = monitor fermo


def docker_stati() -> dict:
    try:
        out = subprocess.run(["docker", "ps", "-a", "--format", "{{.Names}}|{{.Status}}"],
                             capture_output=True, text=True, timeout=30)
        d = {}
        for ln in (out.stdout or "").splitlines():
            if "|" in ln:
                nome, stato = ln.split("|", 1)
                d[nome.strip()] = stato.strip()
        return d
    except Exception:  # noqa: BLE001
        return {}


def unit_stato(unit: str) -> str:
    try:
        r = subprocess.run(["systemctl", "--user", "is-active", unit],
                           capture_output=True, text=True, timeout=15)
        return (r.stdout or "").strip() or "unknown"
    except Exception:  # noqa: BLE001
        return "unknown"


def check_locale() -> int:
    cambi = 0
    stati = docker_stati()
    for c in CONTAINERS:
        s = stati.get(c)
        problema = not (s and s.startswith("Up"))
        cambi += gestisci(f"cont:{c}", problema,
                          f"⚠️ mc2 · container {c}: {s or 'assente'}",
                          f"✅ mc2 · container {c} rientrato")
    for u in UNITS:
        st = unit_stato(u)
        cambi += gestisci(f"unit:{u}", st != "active",
                          f"⚠️ mc2 · unit {u}: {st}",
                          f"✅ mc2 · unit {u} di nuovo attiva")
    try:
        du = shutil.disk_usage("/")
        pct = du.used / du.total * 100.0
        cambi += gestisci("disk:mc2", pct > DISCO_MAX_PCT,
                          f"⚠️ mc2 · disco al {pct:.0f}%",
                          f"✅ mc2 · disco rientrato ({pct:.0f}%)")
    except Exception:  # noqa: BLE001
        pass
    return cambi


def _ssh(cmd: str, timeout: int = 40) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "MARCODG1", cmd],
        capture_output=True, text=True, timeout=timeout)


def check_carry() -> int:
    cambi = 0
    r = _ssh("true", 20)
    raggiungibile = r.returncode == 0
    cambi += gestisci("carry:marcodg1", not raggiungibile,
                      "⚠️ MARCODG1 irraggiungibile (ssh)",
                      "✅ MARCODG1 di nuovo raggiungibile")
    if not raggiungibile:
        return cambi
    # 1) monitor fermo? (il cron scrive canary.log ogni 10'; il mio ssh no)
    r2 = _ssh("stat -c %Y /home/marco/canary/canary.log 2>/dev/null || echo n/d", 20)
    try:
        eta = time.time() - float(r2.stdout.strip())
    except Exception:  # noqa: BLE001
        eta = None
    fermo = eta is None or eta > MONITOR_FERMO_S
    cambi += gestisci("carry:monitor", fermo,
                      f"⚠️ canary · monitor fermo ({'n/d' if eta is None else format(eta / 60, '.0f') + ' min'})",
                      "✅ canary · monitor di nuovo attivo")
    # 2) anomalie canary (status sola lettura)
    r3 = _ssh("cd /home/marco/canary && /home/marco/alpha-omega-trading/venv/bin/python "
              "canary_carry.py status --quiet", 60)
    out = (r3.stdout or "").strip()
    anomalia = ("ANOMALIE" in out) or (r3.returncode != 0)
    if "ANOMALIE" in out:
        dettaglio = "ANOMALIE" + out.split("ANOMALIE", 1)[1][:160]
    else:
        dettaglio = (out[:160] or f"exit {r3.returncode}")
    cambi += gestisci("carry:anomalia", anomalia,
                      f"⚠️ canary C1: {dettaglio}",
                      "✅ canary C1: nessuna anomalia")
    return cambi


def digest() -> int:
    righe = ["🫀 Denaro — check giornaliero"]
    try:
        d = json.loads(urllib.request.urlopen("http://127.0.0.1:8912/infra.json", timeout=10).read())
        eq = ((d.get("equity_breakdown") or {}).get("OKX main") or {}).get("eur")
        if eq is not None:
            righe.append(f"Capitale OKX main: {eq:.2f} €")
        bots = d.get("bots") or {}
        run = sum(1 for b in bots.values() if isinstance(b, dict) and b.get("status") == "running")
        righe.append(f"Flotta: {run} running / {len(bots)} voci")
    except Exception as e:  # noqa: BLE001
        righe.append(f"(aggregatore non leggibile: {type(e).__name__})")
    r = _ssh("cd /home/marco/canary && /home/marco/alpha-omega-trading/venv/bin/python "
             "canary_carry.py status --quiet", 60)
    if r.returncode == 0 and (r.stdout or "").strip():
        righe.append("Canary: " + (r.stdout or "").strip().splitlines()[0][:170])
    ok = invia_o_spool("\n".join(righe))
    print("digest inviato:", ok)
    return 0 if ok else 1


def selftest() -> int:
    ok1 = invia_o_spool("⚠️ TEST alert push — se leggi questo, la catena d'allarme funziona (1/2).")
    ok2 = invia_o_spool("✅ TEST rientro — catena verificata (2/2). D'ora in poi arrivano solo eventi veri.")
    print("selftest:", ok1, ok2)
    return 0 if (ok1 and ok2) else 1


def main(argv: list[str]) -> int:
    flush_spool()
    mode = argv[0] if argv else "check"
    if mode == "check":
        cambi = check_locale()
    elif mode == "carry":
        cambi = check_carry()
    elif mode == "digest":
        return digest()
    elif mode == "selftest":
        return selftest()
    else:
        print("modi: check | carry | digest | selftest")
        return 2
    print(f"{mode}: {cambi} messaggi inviati")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
