"""Brain — riparazione automatica con rate-limit e log.

Regole:
- unit systemd inattiva → systemctl restart (start se mai partita).
- bot stale (health congelato) o status != running → restart dell'unit ospite.
- error persistente nel health → segnalazione (mai restart da solo: il bot
  puo' essere bloccato da preflight/circuit-breaker in modo legittimo).
- rate-limit per unit (cooldown + max/ora), persistenze su file.
"""
from __future__ import annotations

import json
import time

from . import config, sshutil

_state: dict = {}
_last_save = 0.0


def _load() -> None:
    global _state
    try:
        _state.update(json.loads(config.REPAIR_LOG.parent.joinpath(
            "repair_state.json").read_text(encoding="utf-8")))
    except Exception:  # noqa: BLE001
        pass


def _save() -> None:
    global _last_save
    try:
        config.REPAIR_LOG.parent.mkdir(parents=True, exist_ok=True)
        config.REPAIR_LOG.parent.joinpath("repair_state.json").write_text(
            json.dumps(_state), encoding="utf-8")
        _last_save = time.time()
    except Exception:  # noqa: BLE001
        pass


def _log(machine: str, unit: str, action: str, detail: str, ok: bool) -> None:
    try:
        config.REPAIR_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(config.REPAIR_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": time.time(), "machine": machine,
                                "unit": unit, "action": action,
                                "detail": detail, "ok": ok}) + "\n")
    except Exception:  # noqa: BLE001
        pass


def _allowed(unit: str) -> bool:
    now = time.time()
    rec = _state.setdefault(unit, {"last": 0.0, "count": 0, "hour": 0})
    if now - rec["last"] < config.REPAIR_COOLDOWN_S:
        return False
    hour = int(now // 3600)
    if rec.get("hour") != hour:
        rec["hour"], rec["count"] = hour, 0
    return rec["count"] < config.REPAIR_MAX_PER_HOUR


def _mark(unit: str) -> None:
    now = time.time()
    rec = _state.setdefault(unit, {"last": 0.0, "count": 0, "hour": 0})
    rec["last"] = now
    rec["count"] = rec.get("count", 0) + 1
    _save()


def restart_unit(machine: str, unit: str, reason: str) -> bool:
    if not _allowed(unit):
        _log(machine, unit, "restart", f"SKIP rate-limit ({reason})", False)
        return False
    rc, out = sshutil.run_sudo(machine, f"systemctl restart {unit}", timeout=40)
    ok = rc == 0
    if ok:
        _mark(unit)
    _log(machine, unit, "restart", f"{reason} rc={rc} {out[:200]}", ok)
    return ok


def repair(state: dict) -> list[dict]:
    """Esegue le riparazioni necessarie. Ritorna la lista delle azioni."""
    _load()
    actions: list[dict] = []

    for machine, ms in state.items():
        if machine.startswith("_"):
            continue
        for unit, status in ms.get("units", {}).items():
            if status != "active":
                ok = restart_unit(machine, unit, f"unit {status}")
                actions.append({"machine": machine, "unit": unit,
                                "action": "restart_unit", "ok": ok,
                                "reason": f"unit {status}"})
        # bot stale → restart dell'unit ospite (una volta per unit per giro)
        restarted = set()
        for bot_key, b in ms.get("bots", {}).items():
            unit = b["unit"]
            if unit in restarted:
                continue
            if b.get("stale") or b.get("status") not in ("running",):
                ok = restart_unit(machine, unit,
                                  f"bot {bot_key} stale/status={b.get('status')} age={b.get('age')}s")
                actions.append({"machine": machine, "unit": unit,
                                "action": "restart_unit_bot", "ok": ok,
                                "reason": f"bot {bot_key}"})
                restarted.add(unit)
    _save()
    return actions
