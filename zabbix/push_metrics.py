#!/usr/bin/env python3
"""
Invia TUTTE le metriche del progetto a Zabbix (trapper API).
- Bot live: SOL (OKX), ADA (OKX), Kraken (nuvola) — da health files/snapshot
- Progetto aggregato: equity totale, PnL, prezzi — da infra_snapshot
- Paper trade 500€: ADA/SOL/XRP — da paper_state
Eseguito ogni minuto via cron.
"""
import json
import time
import urllib.request
from pathlib import Path

BASE = Path("/home/marco/denaro")
HEALTH_DIR = BASE / "health"
PAPER_DIR = BASE / "paper_state"
NODE_DIR = Path("/home/marco/denaro_node_app/node_data")
API = "http://127.0.0.1:1080/api_jsonrpc.php"
USER = "Admin"
PASS = "zabbix"

BOTS = {
    "sol": ("alpha-omega-bot-sol-eur", "bot.sol"),
    "ada": ("alpha-omega-bot-ada-eur", "bot.ada"),
}

# Node paper (M7): health scritti dal Node asincrono in node_data/
NODE_BOTS = {
    "ADA": ("ADA/EUR", "alpha-omega-node-paper", "node.ada"),
    "SOL": ("SOL/EUR", "alpha-omega-node-paper", "node.sol"),
    "XRP": ("XRP/EUR", "alpha-omega-node-paper", "node.xrp"),
}


def rpc(method, params, auth=None):
    body = {"jsonrpc": "2.0", "method": method, "params": params, "id": 1}
    if auth:
        body["auth"] = auth
    req = urllib.request.Request(API, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            out = json.loads(resp.read())
    except Exception as e:
        print(f"RPC error: {e}")
        return None
    if "error" in out:
        print(f"RPC {method} error: {out['error'].get('data', out['error'])}")
        return None
    return out.get("result")


def read_json(p):
    try:
        return json.loads(Path(p).read_text())
    except Exception:
        return None


def is_stale(ts: float, max_age: float = 150.0) -> bool:
    """True se il timestamp e' vecchio (bot morto / health file congelato)."""
    if not ts:
        return True
    return (time.time() - ts) > max_age


def file_mtime(p: Path) -> float:
    try:
        return p.stat().st_mtime
    except Exception:
        return 0.0


# --- AUTO-HEAL locale (sostituisce i trigger Zabbix, piu' affidabile) --------
# Health stale > HEAL_STALE_S → riavvio dell'unit systemd locale.
# Rate-limit: stessa unit non riavviata piu' di una volta ogni HEAL_COOLDOWN_S.
HEAL_STALE_S = 180.0
HEAL_COOLDOWN_S = 600.0
HEAL_STATE_FILE = Path("/tmp/denaro_heal_state.json")
HEAL_UNITS = {
    # dopo il cutover, TUTTI i bot live/paper girano nel Node (denaro-node-paper)
    HEALTH_DIR / "ada.json": "denaro-node-paper",
    HEALTH_DIR / "sol.json": "denaro-node-paper",
    HEALTH_DIR / "sol_kraken.json": "denaro-node-paper",
    PAPER_DIR / "ADA_EUR_paper.json": "denaro-paper-ada",
    PAPER_DIR / "SOL_EUR_paper.json": "denaro-paper-sol",
    PAPER_DIR / "XRP_EUR_paper.json": "denaro-paper-xrp",
    NODE_DIR / "ADA_EUR_health.json": "denaro-node-paper",
    NODE_DIR / "SOL_EUR_health.json": "denaro-node-paper",
    NODE_DIR / "XRP_EUR_health.json": "denaro-node-paper",
}


def _load_heal_state() -> dict:
    try:
        return json.loads(HEAL_STATE_FILE.read_text())
    except Exception:
        return {}


def _save_heal_state(state: dict) -> None:
    try:
        HEAL_STATE_FILE.write_text(json.dumps(state))
    except Exception:
        pass


def heal_if_stale() -> None:
    """Riavvia le unit il cui health/state e' congelato (bot morto)."""
    now = time.time()
    state = _load_heal_state()
    for source, unit in HEAL_UNITS.items():
        if unit not in state:
            state[unit] = 0.0
        if now - state[unit] < HEAL_COOLDOWN_S:
            continue  # rate-limit: riavvio recente
        ts = read_json(source).get("timestamp", 0) if source.suffix == ".json" and "health" in source.name else 0
        age = now - ts if ts else 0
        if source.suffix == ".json" and "paper" in source.name:
            age = now - file_mtime(source)
        if age > HEAL_STALE_S:
            import subprocess
            r = subprocess.run(["sudo", "systemctl", "restart", unit],
                               capture_output=True, text=True, timeout=30)
            state[unit] = now
            _save_heal_state(state)
            print(f"HEAL: {unit} riavviato (health stale {int(age)}s) rc={r.returncode}")
    _save_heal_state(state)


def main():
    auth = rpc("user.login", {"username": USER, "password": PASS})
    if not auth:
        print("LOGIN FALLITO")
        return

    data = []

    # ── 1. Bot OKX (sol, ada) ──
    for name, (host, prefix) in BOTS.items():
        h = read_json(HEALTH_DIR / f"{name}.json")
        # Auto-heal: status=0 se l'health file e' congelato (>150s)
        if not h or is_stale(h.get("timestamp", 0)):
            data.append({"host": host, "key": f"{prefix}.status", "value": 0})
            continue
        running = 1 if h.get("status") == "running" else 0
        data += [
            {"host": host, "key": f"{prefix}.status", "value": running},
            {"host": host, "key": f"{prefix}.equity", "value": h.get("total_equity", 0)},
            {"host": host, "key": f"{prefix}.free", "value": h.get("free_quote", 0)},
            {"host": host, "key": f"{prefix}.buys", "value": h.get("buys", 0)},
            {"host": host, "key": f"{prefix}.sells", "value": h.get("sells", 0)},
            {"host": host, "key": f"{prefix}.pnl", "value": h.get("pnl", 0)},
            {"host": host, "key": f"{prefix}.trades", "value": h.get("trades", 0)},
            {"host": host, "key": f"{prefix}.wins", "value": h.get("wins", 0)},
            {"host": host, "key": f"{prefix}.losses", "value": h.get("losses", 0)},
            {"host": host, "key": f"{prefix}.volume", "value": h.get("volume", 0)},
            {"host": host, "key": f"{prefix}.drawdown", "value": h.get("drawdown", 0)},
            {"host": host, "key": f"{prefix}.uptime", "value": h.get("uptime", 0)},
        ]

    # ── 2. Bot Kraken (ora LOCALE nel Node: health/sol_kraken.json;
    #      fallback retro-compatibile allo snapshot da nuvola) ──
    kraken_h = read_json(HEALTH_DIR / "sol_kraken.json")
    if kraken_h is None:
        snap = read_json(HEALTH_DIR / "kraken_snapshot.json")
        if snap and snap.get("bot"):
            kraken_h = snap["bot"]
    if kraken_h and not is_stale(kraken_h.get("timestamp", 0)):
        h = kraken_h
        host = "alpha-omega-bot-kraken"
        prefix = "bot.kraken"
        running = 1 if h.get("status") == "running" else 0
        data += [
            {"host": host, "key": f"{prefix}.status", "value": running},
            {"host": host, "key": f"{prefix}.equity", "value": h.get("total_equity", 0)},
            {"host": host, "key": f"{prefix}.free", "value": h.get("free_quote", 0)},
            {"host": host, "key": f"{prefix}.buys", "value": h.get("buys", 0)},
            {"host": host, "key": f"{prefix}.sells", "value": h.get("sells", 0)},
            {"host": host, "key": f"{prefix}.pnl", "value": h.get("pnl", 0)},
            {"host": host, "key": f"{prefix}.trades", "value": h.get("trades", 0)},
            {"host": host, "key": f"{prefix}.wins", "value": h.get("wins", 0)},
            {"host": host, "key": f"{prefix}.losses", "value": h.get("losses", 0)},
            {"host": host, "key": f"{prefix}.volume", "value": h.get("volume", 0)},
            {"host": host, "key": f"{prefix}.drawdown", "value": h.get("drawdown", 0)},
            {"host": host, "key": f"{prefix}.uptime", "value": h.get("uptime", 0)},
        ]
    else:
        data.append({"host": "alpha-omega-bot-kraken", "key": "bot.kraken.status", "value": 0})

    # ── 3. Progetto aggregato (da infra_snapshot) ──
    infra = read_json(HEALTH_DIR / "infra_snapshot.json")
    if infra:
        host = "alpha-omega-project"
        prices = infra.get("prices", {})
        data += [
            {"host": host, "key": "project.equity", "value": infra.get("total_equity", 0)},
            {"host": host, "key": "project.bot_equity", "value": infra.get("bot_equity", 0)},
            {"host": host, "key": "project.kraken_equity", "value": infra.get("kraken_equity", 0)},
        ]
        # Prezzi live
        for sym, key in [("SOL/EUR", "sol_eur"), ("ADA/EUR", "ada_eur"),
                         ("XRP/EUR", "xrp_eur"), ("DOGE/EUR", "doge_eur")]:
            t = prices.get(sym)
            if t and t.get("last"):
                data.append({"host": host, "key": f"price.{key}", "value": t["last"]})
                if t.get("pct24h") is not None:
                    data.append({"host": host, "key": f"price.{key}_24h",
                                 "value": round(t["pct24h"], 3)})
        # PnL e trades totali dai bot
        bots = infra.get("bots", {})
        pnl_tot = sum(b.get("pnl", 0) for b in bots.values() if b.get("status") == "running")
        tr_tot = sum(b.get("trades", 0) for b in bots.values() if b.get("status") == "running")
        wins = sum(b.get("wins", 0) for b in bots.values() if b.get("status") == "running")
        losses = sum(b.get("losses", 0) for b in bots.values() if b.get("status") == "running")
        wr = round(wins / (wins + losses) * 100, 1) if (wins + losses) else 0
        data += [
            {"host": host, "key": "project.pnl_total", "value": round(pnl_tot, 4)},
            {"host": host, "key": "project.trades_total", "value": tr_tot},
            {"host": host, "key": "project.win_rate", "value": wr},
        ]

    # ── 4. Paper bot (da paper_state; staleness via mtime del file) ──
    # Equity reale = cash + asset × prezzo corrente (prezzi da infra_snapshot,
    # definito nella sezione 3; senza prezzo si usa solo cash)
    paper_prices = (infra or {}).get("prices", {})
    for pair in ("ada", "sol", "xrp"):
        p = PAPER_DIR / f"{pair.upper()}_EUR_paper.json"
        st = read_json(p)
        host = f"alpha-omega-paper-{pair}"
        prefix = f"paper.{pair}"
        if not st or is_stale(file_mtime(p)):
            data.append({"host": host, "key": f"{prefix}.status", "value": 0})
            continue
        t = paper_prices.get(f"{pair.upper()}/EUR") or {}
        last = t.get("last") or 0
        equity = st.get("cash", 0) + st.get("asset", 0) * last
        data += [
            {"host": host, "key": f"{prefix}.status", "value": 1},
            {"host": host, "key": f"{prefix}.equity", "value": round(equity, 2)},
            {"host": host, "key": f"{prefix}.cash", "value": round(st.get("cash", 0), 2)},
            {"host": host, "key": f"{prefix}.buys", "value": len(st.get("buys", []))},
            {"host": host, "key": f"{prefix}.sells", "value": len(st.get("sells", []))},
            {"host": host, "key": f"{prefix}.pnl", "value": round(st.get("total_pnl", 0), 4)},
            {"host": host, "key": f"{prefix}.trades", "value": st.get("trades", 0)},
            {"host": host, "key": f"{prefix}.wins", "value": st.get("wins", 0)},
            {"host": host, "key": f"{prefix}.losses", "value": st.get("losses", 0)},
        ]

    # ── 5. Node paper (M7 — da node_data health; staleness via timestamp) ──
    for name, (symbol, host, prefix) in NODE_BOTS.items():
        h = read_json(NODE_DIR / f"{symbol.replace('/', '_')}_health.json")
        if not h or is_stale(h.get("timestamp", 0)):
            data.append({"host": host, "key": f"{prefix}.status", "value": 0})
            continue
        running = 1 if h.get("status") == "running" else 0
        data += [
            {"host": host, "key": f"{prefix}.status", "value": running},
            {"host": host, "key": f"{prefix}.equity", "value": h.get("total_equity", 0)},
            {"host": host, "key": f"{prefix}.buys", "value": h.get("buys", 0)},
            {"host": host, "key": f"{prefix}.sells", "value": h.get("sells", 0)},
            {"host": host, "key": f"{prefix}.pnl", "value": h.get("pnl", 0)},
            {"host": host, "key": f"{prefix}.trades", "value": h.get("trades", 0)},
        ]

    # Push
    clock = int(time.time())
    for d in data:
        d["clock"] = clock
    result = rpc("history.push", data, auth)
    if result is not None and result.get("response") == "success":
        print(f"PUSH OK: {len(data)} valori inviati")
    else:
        print(f"PUSH FALLITO: {result}")

    # Auto-heal locale (dopo il push, per non ritardarlo)
    heal_if_stale()


if __name__ == "__main__":
    main()
