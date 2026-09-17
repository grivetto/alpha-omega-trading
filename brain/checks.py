"""Brain — raccolta dello stato: unit systemd, health dei bot, processi."""
from __future__ import annotations

import time

from . import config, sshutil


def check_units(machine: str) -> dict[str, str]:
    """systemctl is-active per ogni unit della macchina: {unit: active|...}."""
    units = config.UNITS.get(machine, [])
    if not units:
        return {}
    cmd = "for u in " + " ".join(units) + "; do echo \"$u=$(systemctl is-active $u 2>/dev/null)\"; done"
    rc, out = sshutil.run(machine, cmd)
    states = {}
    for line in out.splitlines():
        if "=" in line:
            u, s = line.split("=", 1)
            states[u.strip()] = s.strip()
    return states


def check_processes(machine: str) -> dict[str, bool]:
    """pgrep -f per i processi critici: {pattern: alive}. Pattern con [] per
    evitare che pgrep matchi la riga di comando della query stessa."""
    out = {}
    for pat in config.PROCESSES.get(machine, []):
        rc, _ = sshutil.run(machine, f"pgrep -f '{pat}' >/dev/null 2>&1")
        out[pat] = rc == 0
    return out


def check_bots(machine: str) -> dict[str, dict]:
    """Health dei bot della macchina: {bot_key: {status, age, error, ...}}."""
    now = time.time()
    bots = {k: v for k, v in config.BOTS.items() if k[0] == machine}
    if not bots:
        return {}
    paths = [v[1] for v in bots.values()]
    files = sshutil.read_json_files(machine, list(dict.fromkeys(paths)))
    result = {}
    for (m, bot_key), (unit, path) in bots.items():
        h = files.get(path) or {}
        ts = h.get("timestamp") or 0
        age = (now - ts) if ts else float("inf")
        result[bot_key] = {
            "unit": unit,
            "status": h.get("status", "unknown"),
            "age": round(age, 1),
            "stale": age > config.HEALTH_STALE_S,
            "error": h.get("error", "") or "",
            "strategy": h.get("strategy", ""),
            "equity": h.get("total_equity", 0),
            "pnl": h.get("pnl", 0),
            "cap_available": h.get("cap_available", 0),
            "stop_loss": bool(h.get("stop_loss_triggered")),
        }
    return result


def collect_all() -> dict:
    """Stato completo: {machine: {units, bots, processes, ok, ts}}."""
    state = {}
    for machine in config.MACHINES:
        units = check_units(machine)
        bots = check_bots(machine)
        procs = check_processes(machine)
        unit_ok = all(s == "active" for s in units.values()) if units else False
        bots_ok = all(not b["stale"] and b["status"] == "running"
                      for b in bots.values()) if bots else False
        procs_ok = all(alive for alive in procs.values()) if procs else False
        state[machine] = {
            "units": units, "bots": bots, "processes": procs,
            "ok": bool(unit_ok and bots_ok and procs_ok),
            "units_ok": bool(unit_ok), "bots_ok": bool(bots_ok),
            "procs_ok": bool(procs_ok),
            "ts": time.time(),
        }
    state["_ts"] = time.time()
    return state
