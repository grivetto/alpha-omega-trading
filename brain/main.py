"""Brain Alpha-Omega — main loop.

Ciclo (ogni ~60s):
  1. collect_all()  → stato macchine/unit/bot/processi
  2. repair()       → riavvii con rate-limit (auto-healing)
  3. zabbix push    → stato + contatori (trigger/alert)
  4. Hermes cycle   → digest in inbox, invocazione headless, lettura outbox
  5. Strategy lab   → backtest + promozione paper/live (ogni 6h)
  6. git commit     → registry + override committati e pushati

Uso: python -m brain.main [--once]
"""
from __future__ import annotations

import json
import subprocess
import sys
import threading
import time

from . import config, checks, hermes_bridge, repair, sshutil, strategy_lab, zabbix_push

# ── git ──────────────────────────────────────────────────────────────────────

def git_commit_if_possible(message: str) -> bool:
    repo = config.GIT_REPO
    try:
        r = subprocess.run(["git", "-C", str(repo), "rev-parse",
                            "--is-inside-work-tree"],
                           capture_output=True, text=True, timeout=10)
        if r.returncode != 0:
            return False
        subprocess.run(["git", "-C", str(repo), "add",
                        "config/strategies/registry.json",
                        "config/strategy_overrides.json"],
                       capture_output=True, timeout=10)
        r = subprocess.run(["git", "-C", str(repo), "commit", "-m", message],
                           capture_output=True, text=True, timeout=15)
        if r.returncode == 0:
            subprocess.run(["git", "-C", str(repo), "push"],
                           capture_output=True, timeout=40)
            print(f"[git] committato: {message}")
            return True
    except Exception as e:  # noqa: BLE001
        print(f"[git] errore: {e}")
    return False

# ── strategy lab: promozione ────────────────────────────────────────────────

_NODE_KEYS = {"strategy", "levels", "buy_distance", "profit_target",
              "sell_levels", "sell_distance", "sell_step", "stop_loss_pct"}


def _to_node_params(p: dict) -> dict:
    out = {k: v for k, v in p.items() if k in _NODE_KEYS}
    if "stop_loss" in p and "stop_loss_pct" not in out:
        out["stop_loss_pct"] = p["stop_loss"]
    return out


def _load_node_yaml():
    import yaml
    with open("/home/marco/denaro_node_app/config/node.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _live_params_from_yaml(sym: str) -> dict | None:
    try:
        cfg = _load_node_yaml()
        for b in cfg.get("bots", []):
            if (b.get("symbol") == sym and b.get("mode") != "paper"
                    and b.get("enabled", True)):
                return {"strategy": b.get("strategy", "grid"),
                        "buy_distance": b.get("buy_distance", 0.01),
                        "profit_target": b.get("profit_target", 0.015),
                        "levels": b.get("levels", 3),
                        "sell_levels": b.get("sell_levels", 0),
                        "sell_distance": b.get("sell_distance", 0.02),
                        "sell_step": b.get("sell_step", 0.01),
                        "stop_loss": b.get("stop_loss_pct", 0.0)}
    except Exception as e:  # noqa: BLE001
        print(f"[brain] node.yaml non leggibile: {e}")
    return None


def _paper_health_path(sym: str) -> str:
    for (m, k), (unit, path) in config.BOTS.items():
        if m == "marcodg1" and k == f"paper:{sym}":
            return path
    return ""


def promote_candidates(reg: dict) -> bool:
    """Top candidato batte i parametri live correnti → promuovi a PAPER."""
    changed = False
    for sym, sreg in reg.get("symbols", {}).items():
        cand = sreg.get("best_candidate")
        if not cand or sreg.get("paper"):
            continue
        live = sreg.get("live") or _live_params_from_yaml(sym)
        if not live:
            continue
        try:
            candles = strategy_lab.load_or_fetch(sym)
            m_live = strategy_lab.backtest_grid(candles, live,
                                                strategy_lab.FEES["okx"])
            m_cand = cand["metrics"]
        except Exception as e:  # noqa: BLE001
            print(f"[brain] backtest confronto {sym}: {e}")
            continue
        if m_live["trades"] < strategy_lab.MIN_TRADES:
            continue
        if (m_cand["ret"] >= m_live["ret"] * config.PROMOTE_MARGIN
                and m_cand["max_dd"] <= m_live["max_dd"] * 1.5 + 0.05):
            sreg["paper"] = {"params": cand["params"],
                             "started": time.time(),
                             "baseline_ret": round(m_live["ret"], 4)}
            changed = True
            print(f"[brain] {sym}: candidato promosso a PAPER "
                  f"(ret {m_cand['ret']:.3f} vs live {m_live['ret']:.3f})")
    return changed


def validate_paper(reg: dict) -> bool:
    """Dopo 24h di paper: pnl > 0 → LIVE; altrimenti → scartato."""
    changed = False
    for sym, sreg in reg.get("symbols", {}).items():
        paper = sreg.get("paper")
        if not paper:
            continue
        if time.time() - paper["started"] < config.PAPER_VALIDATE_H * 3600:
            continue
        path = _paper_health_path(sym)
        h = {}
        if path:
            files = sshutil.read_json_files("marcodg1", [path])
            h = files.get(path) or {}
        pnl_now = h.get("pnl", 0) if h else None
        reason = f"paper pnl {pnl_now} dopo {int(config.PAPER_VALIDATE_H)}h"
        if pnl_now is not None and pnl_now > 0:
            sreg["live"] = {"mode": "okx", "params": paper["params"],
                            "promoted_ts": time.time()}
            sreg["history"].append({**paper, "status": "promoted_live",
                                    "reason": reason})
            print(f"[brain] {sym}: candidato promosso a LIVE ({reason})")
            hermes_bridge.send_telegram(
                f"🧠 Brain: strategia promossa a LIVE per {sym} ({reason})")
        else:
            sreg["history"].append({**paper, "status": "retired",
                                    "reason": reason or "pnl non disponibile"})
            print(f"[brain] {sym}: candidato SCARTATO ({reason})")
        sreg["paper"] = None
        changed = True
    return changed


def write_overrides(reg: dict) -> dict:
    """Scrive strategy_overrides.json (paper in validazione + live promossi)
    e lo deploya nella config dir del nodo su MARCODG1."""
    ov: dict = {}
    for sym, sreg in reg.get("symbols", {}).items():
        if sreg.get("paper"):
            ov[f"paper:{sym}"] = _to_node_params(sreg["paper"]["params"])
        if sreg.get("live"):
            ov[f"{sreg['live']['mode']}:{sym}"] = _to_node_params(
                sreg["live"]["params"])
    config.OVERRIDES_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.OVERRIDES_PATH.write_text(json.dumps(ov, indent=2), encoding="utf-8")
    if ov:
        sshutil.run("marcodg1",
                    f"cp {config.OVERRIDES_PATH} "
                    f"/home/marco/denaro_node_app/config/strategy_overrides.json")
    return ov


def strategy_cycle() -> None:
    reg = strategy_lab.load_registry()
    try:
        summary = strategy_lab.run_round()
        print(f"[brain] runda backtest: {json.dumps(summary)[:400]}")
    except Exception as e:  # noqa: BLE001
        print(f"[brain] runda backtest FALLITA: {e}")
    changed = promote_candidates(reg)
    changed = validate_paper(reg) or changed
    ov = write_overrides(reg)
    strategy_lab.save_registry(reg)
    if ov or changed:
        repair.restart_unit("marcodg1", "denaro-node-paper",
                            "strategie aggiornate (override)")
        git_commit_if_possible(
            "brain: runda strategie — registry + override aggiornati")
    else:
        git_commit_if_possible("brain: runda strategie (nessun cambio)")

# ── loop principale ──────────────────────────────────────────────────────────

def _hermes_worker() -> None:
    """Ciclo Hermes in THREAD separato: il watchdog non deve MAI bloccarsi su
    un'operazione lenta (LLM headless con timeout fino a 600s). Il worker
    rilegge l'ultimo stato salvato da config.save_state() per il digest."""
    last = time.time() - config.HERMES_INTERVAL_S  # primo giro subito
    outbox_snap = hermes_bridge.read_outbox()
    while True:
        try:
            if time.time() - last >= config.HERMES_INTERVAL_S:
                state = config.load_state()
                outbox_snap, ex = hermes_bridge.exchange_cycle(state, outbox_snap)
                last = time.time()
                if ex:
                    print(f"[brain] scambio Hermes: ok={ex.get('ok')} "
                          f"reply={bool(ex.get('new_reply'))}")
        except Exception as e:  # noqa: BLE001
            print(f"[brain] Hermes errore: {e}")
        time.sleep(30)


def main() -> None:
    once = "--once" in sys.argv
    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    zabbix_push.login()
    zabbix_push.ensure_items()
    zabbix_push.ensure_triggers()
    outbox_snap = hermes_bridge.read_outbox()
    last_hermes = time.time() - config.HERMES_INTERVAL_S  # primo giro subito
    last_strategy = 0.0
    print("[brain] avviato")

    while True:
        t0 = time.time()
        try:
            state = checks.collect_all()
            repairs = repair.repair(state)
            for rp in repairs:
                if not rp.get("ok"):
                    hermes_bridge.send_telegram(
                        f"⚠️ Brain: riparazione FALLITA su {rp.get('machine')} "
                        f"({rp.get('unit')}) — {rp.get('reason')}")
            hermes_age = None
            mt = hermes_bridge.outbox_mtime()
            if mt:
                hermes_age = round(t0 - mt, 1)
            zabbix_push.push(state, repairs, hermes_age)
            config.save_state({"ts": t0,
                               "machines": {k: {"ok": v.get("ok"),
                                                "units_down": [u for u, s in v.get("units", {}).items() if s != "active"],
                                                "bots_down": [b for b, x in v.get("bots", {}).items() if x.get("stale")]}
                                            for k, v in state.items() if not k.startswith("_")},
                               "repairs": repairs})

            if time.time() - last_hermes >= config.HERMES_INTERVAL_S:
                outbox_snap, ex = hermes_bridge.exchange_cycle(
                    state, outbox_snap)
                last_hermes = time.time()
                if ex:
                    print(f"[brain] scambio Hermes: ok={ex.get('ok')} "
                          f"reply={bool(ex.get('new_reply'))}")

            if time.time() - last_strategy >= config.STRATEGY_INTERVAL_S:
                strategy_cycle()
                last_strategy = time.time()
        except Exception as e:  # noqa: BLE001
            print(f"[brain] ciclo errore: {e}")
            time.sleep(20)
        if once:
            break
        elapsed = time.time() - t0
        time.sleep(max(5.0, config.UNIT_CHECK_LOOP_S - elapsed))


if __name__ == "__main__":
    main()
