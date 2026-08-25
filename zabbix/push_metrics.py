#!/usr/bin/env python3
"""
Invia TUTTE le metriche del progetto a Zabbix (trapper API).
- Bot live: SOL (OKX), ADA (OKX), Kraken — da health files/snapshot
- Progetto aggregato: equity totale, PnL, prezzi — da infra_snapshot
- Paper trade 500€: ADA/SOL/XRP — da paper_state
- Nodi Denaro remoti (nuvola, mc2): health via SSH + auto-heal remoto
Eseguito ogni minuto via cron.
"""
import json
import subprocess
import time
import urllib.request
from pathlib import Path

BASE = Path("/home/marco/denaro")
HEALTH_DIR = BASE / "health"
NODE_DIR = Path("/home/marco/denaro_node_app/node_data")
API = "http://127.0.0.1:1080/api_jsonrpc.php"
USER = "Admin"
PASS = "zabbix"

BOTS = {
    "sol": ("alpha-omega-bot-sol-eur", "bot.sol"),
    "ada": ("alpha-omega-bot-ada-eur", "bot.ada"),
    "doge": ("alpha-omega-bot-doge-eur", "bot.doge"),
    "eth": ("alpha-omega-bot-eth-eur", "bot.eth"),
}

# Node paper (M7): health scritti dal Node asincrono in node_data/
NODE_BOTS = {
    "ADA": ("ADA/EUR", "alpha-omega-node-paper", "node.ada", "paper_default_ADA_EUR_health.json"),
    "SOL": ("SOL/EUR", "alpha-omega-node-paper", "node.sol", "paper_default_SOL_EUR_health.json"),
    "XRP": ("XRP/EUR", "alpha-omega-node-paper", "node.xrp", "paper_default_XRP_EUR_health.json"),
    "DOGE": ("DOGE/EUR", "alpha-omega-node-paper", "node.doge", "paper_default_DOGE_EUR_health.json"),
    "ETH": ("ETH/EUR", "alpha-omega-node-paper", "node.eth", "paper_default_ETH_EUR_health.json"),
}

# Nodi Denaro remoti (nuvola, mc2): health letti via SSH, push su host dedicati
# + auto-heal remoto (systemctl restart via SSH se health stale).
REMOTE_NODES = {
    "nuvola": {
        "ssh": ["sergio@87.106.3.15", "-p", "22"],
        "data_dir": "/home/sergio/denaro_node_app/node_data",
        "host": "alpha-omega-node-nuvola",
        "unit": "denaro-node-nuvola",
    },
    "mc2": {
        "ssh": ["sergio@127.0.0.1", "-p", "2222"],  # tunnel inverso
        "data_dir": "/home/sergio/denaro_node_app/node_data",
        "host": "alpha-omega-node-mc2",
        "unit": "denaro-node-mc2",
    },
}
REMOTE_SYMS = {"ADA": "node.ada", "SOL": "node.sol", "XRP": "node.xrp"}

# Servizi Denaro per macchina → item trapper svc.<unit> sugli host macchina
# (MARCODG1, nuvola, mc2). Stato letto con systemctl is-active:
# localmente su MARCODG1, via SSH su nuvola/mc2.
SERVICES = {
    "marcodg1": {
        "host": "MARCODG1",
        "ssh": [],  # locale
        "units": [
            "denaro-node-paper", "denaro-health-marcodg1", "denaro-aggregator-marcodg1",
            "denaro-paper-ada", "denaro-paper-sol", "denaro-paper-xrp",
        ],
    },
    "nuvola": {
        "host": "nuvola",
        "ssh": ["sergio@87.106.3.15", "-p", "22"],
        "units": ["denaro-node-nuvola", "zabbix-tunnel"],
    },
    "mc2": {
        "host": "mc2",
        "ssh": ["sergio@127.0.0.1", "-p", "2222"],  # tunnel inverso
        "units": ["denaro-node-mc2", "zabbix-tunnel-reverse"],
    },
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


# --- Nodi remoti (nuvola, mc2) ------------------------------------------------

def fetch_remote_health(node_name):
    """Legge i *_health.json del Node remoto via SSH.
    Ritorna {symbol: health_dict}. Fallisce in silenzio -> {}."""
    cfg = REMOTE_NODES.get(node_name)
    if not cfg:
        return {}
    ssh_args = " ".join(cfg["ssh"])
    data_dir = cfg["data_dir"]
    cmd = (f"ssh -o BatchMode=yes -o ConnectTimeout=5 {ssh_args} "
           f"'for f in {data_dir}/*_health.json; do echo ===FILE===; cat \"$f\"; echo; done'")
    try:
        r = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, timeout=20)
        bots = {}
        if r.returncode == 0 and r.stdout.strip():
            for block in r.stdout.split("===FILE===")[1:]:
                lines = block.strip().splitlines()
                if not lines:
                    continue
                try:
                    h = json.loads(lines[-1])
                    bots[h.get("symbol", "unknown")] = h
                except Exception:
                    continue
        return bots
    except Exception:
        return {}


def push_services(data):
    """Pusha lo stato dei servizi Denaro per macchina (systemctl is-active).
    MARCODG1: locale. nuvola/mc2: via SSH. 1 = active, 0 = non attivo."""
    for node_name, cfg in SERVICES.items():
        host = cfg["host"]
        units = cfg["units"]
        if cfg["ssh"]:
            ssh_args = " ".join(cfg["ssh"])
            cmd = (f"ssh -o BatchMode=yes -o ConnectTimeout=5 {ssh_args} "
                   f"'for u in {' '.join(units)}; do s=$(systemctl is-active $u 2>/dev/null); echo $u=$s; done'")
            try:
                r = subprocess.run(["bash", "-c", cmd], capture_output=True,
                                   text=True, timeout=20)
                states = {}
                for line in r.stdout.splitlines():
                    if "=" in line:
                        u, s = line.split("=", 1)
                        states[u.strip()] = s.strip()
            except Exception:
                states = {}
        else:
            states = {}
            for u in units:
                try:
                    r = subprocess.run(["systemctl", "is-active", u],
                                       capture_output=True, text=True, timeout=10)
                    states[u] = r.stdout.strip()
                except Exception:
                    states[u] = ""
        for u in units:
            val = 1 if states.get(u) == "active" else 0
            data.append({"host": host, "key": f"svc.{u}", "value": val})


def push_remote_nodes(data, auth):
    """Pusha le metriche dei nodi remoti e fa auto-heal remoto se stale."""
    now = time.time()
    for node_name, cfg in REMOTE_NODES.items():
        host = cfg["host"]
        prefix = f"node.{node_name}"
        bots = fetch_remote_health(node_name)
        all_stale = True
        for sym, keybase in REMOTE_SYMS.items():
            h = bots.get(f"{sym}/EUR")
            if not h or is_stale(h.get("timestamp", 0)):
                data.append({"host": host, "key": f"{keybase}.status", "value": 0})
                continue
            all_stale = False
            running = 1 if h.get("status") == "running" else 0
            data += [
                {"host": host, "key": f"{keybase}.status", "value": running},
                {"host": host, "key": f"{keybase}.equity", "value": h.get("total_equity", 0)},
                {"host": host, "key": f"{keybase}.buys", "value": h.get("buys", 0)},
                {"host": host, "key": f"{keybase}.sells", "value": h.get("sells", 0)},
                {"host": host, "key": f"{keybase}.pnl", "value": h.get("pnl", 0)},
                {"host": host, "key": f"{keybase}.trades", "value": h.get("trades", 0)},
            ]
            _push_atlas_metrics(data, host, keybase, h)
        # Auto-heal remoto: nodo intero morto -> systemctl restart via SSH
        if all_stale:
            _heal_remote(node_name, cfg)
        # Stato aggregato del nodo (comodita' dashboard/Zabbix)
        data.append({"host": host, "key": f"{prefix}.status",
                     "value": 1 if (bots and not all_stale) else 0})


def _push_atlas_metrics(data, host, keybase, h):
    """Pusha le metriche ATLAS v6 da un health dict (regime, adx, atr, risk).
    Usata per bot live, node paper locale e nodi remoti — keybase es.
    'node.ada' o 'bot.sol'."""
    if not h:
        return
    regime_map = {"range": 0, "trend_bull": 1, "trend_bear": 2}
    strat = (h.get("strategy") or "").lower()
    strat_val = {"grid": 0, "momentum": 1, "meanrev": 2, "meanreversion": 2,
                 "adaptive": 3, "adaptiveengine": 3}.get(strat, -1)
    data += [
        {"host": host, "key": f"{keybase}.regime",
         "value": regime_map.get(h.get("regime", ""), -1)},
        {"host": host, "key": f"{keybase}.adx", "value": h.get("adx", 0)},
        {"host": host, "key": f"{keybase}.atr_pct", "value": h.get("atr_pct", 0)},
        {"host": host, "key": f"{keybase}.rsi", "value": h.get("rsi", 0)},
        {"host": host, "key": f"{keybase}.ema200", "value": h.get("ema200", 0)},
        {"host": host, "key": f"{keybase}.strategy", "value": strat_val},
        {"host": host, "key": f"{keybase}.stop_loss", "value": int(bool(h.get("stop_loss_triggered")))},
        {"host": host, "key": f"{keybase}.cap_locked", "value": h.get("cap_locked", 0)},
        {"host": host, "key": f"{keybase}.cap_available", "value": h.get("cap_available", 0)},
    ]


_HEAL_STATE = {}


def _heal_remote(node_name, cfg):
    """Riavvia l'unit systemd del nodo remoto via SSH (rate-limit 600s)."""
    now = time.time()
    last = _HEAL_STATE.get(node_name, 0.0)
    if now - last < 600.0:
        return
    ssh_args = " ".join(cfg["ssh"])
    cmd = (f"ssh -o BatchMode=yes -o ConnectTimeout=6 {ssh_args} "
           f"sudo systemctl restart {cfg['unit']}")
    try:
        r = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, timeout=30)
        _HEAL_STATE[node_name] = now
        print(f"HEAL REMOTO: {node_name} ({cfg['unit']}) riavviato rc={r.returncode}")
    except Exception as e:
        print(f"HEAL REMOTO {node_name} ERRORE: {e}")


# --- AUTO-HEAL locale (sostituisce i trigger Zabbix, piu' affidabile) --------
# Health stale > HEAL_STALE_S → riavvio dell'unit systemd locale.
# Rate-limit: stessa unit non riavviata piu' di una volta ogni HEAL_COOLDOWN_S.
HEAL_STALE_S = 180.0
HEAL_COOLDOWN_S = 600.0
HEAL_STATE_FILE = Path("/tmp/denaro_heal_state.json")
HEAL_UNITS = {
    # dopo il cutover, TUTTI i bot live/paper girano nel Node (denaro-node-paper).
    # File attuali del Node (paths_for: paper_default_{SYM}_EUR_health.json).
    # NB: i residui pre-refactor (ADA_EUR_health.json) e i paper v3.3 (paper_state)
    # sono congelati e NON vanno referenziati (falsi riavvii).
    HEALTH_DIR / "ada.json": "denaro-node-paper",
    HEALTH_DIR / "sol.json": "denaro-node-paper",
    HEALTH_DIR / "sol_kraken.json": "denaro-node-paper",
    NODE_DIR / "paper_default_ADA_EUR_health.json": "denaro-node-paper",
    NODE_DIR / "paper_default_SOL_EUR_health.json": "denaro-node-paper",
    NODE_DIR / "paper_default_XRP_EUR_health.json": "denaro-node-paper",
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

    # ── 4. Paper bot v3.3 (RIMOSSO 2026-08-25): i motori paper v3.3 sono stati
    #     fermati/disabilitati (ridondanti) — i paper girano nel Node e sono
    #     pushati nella sezione 5 (node.*). I file paper_state sono congelati.
    # ── 5. Node paper (M7 — da node_data health; staleness via timestamp) ──
    for name, (symbol, host, prefix, fname) in NODE_BOTS.items():
        h = read_json(NODE_DIR / fname)
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
        # ATLAS v6: regime/ADX/ATR/risk
        _push_atlas_metrics(data, host, prefix, h)

    # ── 5b. Bot LIVE (da health_path v3.3: health/ada.json ecc.) — ATLAS v6 ──
    for name, (host, prefix) in BOTS.items():
        h = read_json(HEALTH_DIR / f"{name}.json")
        if h and not is_stale(h.get("timestamp", 0)):
            _push_atlas_metrics(data, host, prefix, h)
    kraken_h = read_json(HEALTH_DIR / "sol_kraken.json")
    if kraken_h and not is_stale(kraken_h.get("timestamp", 0)):
        _push_atlas_metrics(data, "alpha-omega-bot-kraken", "bot.kraken", kraken_h)

    # ── 6. Nodi Denaro remoti (nuvola, mc2) + auto-heal remoto ──
    push_remote_nodes(data, auth)

    # ── 7. Servizi Denaro per macchina (systemctl is-active) ──
    push_services(data)

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
