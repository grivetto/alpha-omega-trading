#!/usr/bin/env python3
"""
Invia TUTTE le metriche del progetto a Zabbix (trapper API).
- Bot live: SOL (OKX), ADA (OKX) — da health files/snapshot (Kraken rimosso 01/10)
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
NODE_DIR = Path("/home/marco/alpha-omega-trading/node_data")
API = "http://127.0.0.1:1080/api_jsonrpc.php"
# [01/10/26] sicurezza: NIENTE credenziali nel sorgente (repo pubblico).
# Fonti: $ZBX_CRED_FILE (default ~/.zbx_cred, formato "Utente:Password")
# oppure variabili d'ambiente ZBX_USER / ZBX_PASS.
import os
_cred_file = Path(os.environ.get("ZBX_CRED_FILE", str(Path.home() / ".zbx_cred")))
try:
    _zuser, _zpass = _cred_file.read_text().strip().split(":", 1)
except Exception:
    _zuser, _zpass = os.environ.get("ZBX_USER", "Admin"), os.environ.get("ZBX_PASS", "")
USER, PASS = _zuser, _zpass

BOTS = {
    # [01/10/26] PULIZIA: host alpha-omega-bot-*-eur inesistenti da tempo, le
    # rispettive sezioni di push sono state disattivate. Def legacy per memoria.
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

# istanza TREND paper (MARCODG1): node_data_trend/paper_default_*_health.json
TREND_BOTS = {
    "SOL": ("SOL/EUR", "alpha-omega-node-trend", "trend.sol", "paper_default_SOL_EUR_health.json"),
    "ETH": ("ETH/EUR", "alpha-omega-node-trend", "trend.eth", "paper_default_ETH_EUR_health.json"),
    "ADA": ("ADA/EUR", "alpha-omega-node-trend", "trend.ada", "paper_default_ADA_EUR_health.json"),
    "XRP": ("XRP/EUR", "alpha-omega-node-trend", "trend.xrp", "paper_default_XRP_EUR_health.json"),
}
# [rimosso 01/10] TREND LIVE su Kraken — Kraken fuori dal progetto.

# Nodi Denaro remoti (nuvola, mc2): health letti via SSH, push su host dedicati
# + auto-heal remoto (systemctl restart via SSH se health stale).
REMOTE_NODES = {
    "nuvola": {
        "ssh": ["sergio@87.106.3.15", "-p", "22"],
        "data_dir": "/home/sergio/alpha-omega-trading/node_data",
        "live_dir": "/home/sergio/denaro/health",
        "host": "alpha-omega-node-nuvola",
        "unit": "denaro-node-nuvola-trade",
    },
    "mc2": {
        "ssh": ["sergio@127.0.0.1", "-p", "2222"],  # tunnel inverso
        "data_dir": "/home/sergio/denaro/node_data",
        "live_dir": "/home/sergio/denaro/health",
        "host": "alpha-omega-node-mc2",
        "unit": "denaro-node-mc2",
    },
}
# paper (node_data) + live DOGE (health dir, health_path dal config del node)
REMOTE_SYMS = {"ADA": "node.ada", "SOL": "node.sol",
               "XRP": "node.xrp", "DOGE": "node.doge"}

# Servizi Denaro per macchina → item trapper svc.<unit> sugli host macchina
# (MARCODG1, nuvola, mc2). Stato letto con systemctl is-active:
# localmente su MARCODG1, via SSH su nuvola/mc2.
SERVICES = {
    "marcodg1": {
        "host": "MARCODG1",
        "ssh": [],  # locale
        "units": [
            "denaro-node-paper", "denaro-health-marcodg1", "denaro-aggregator-marcodg1",
            "denaro-dashboard-marcodg1", "denaro-node-marcodg1-xrp", "cloudflared-denaro", "zabbix-agent",
            "denaro-landing",
        ],
    },
    "nuvola": {
        "host": "nuvola",
        "ssh": ["sergio@87.106.3.15", "-p", "22"],
        "units": ["denaro-node-nuvola-trade", "denaro-health-nuvola",
                  "zabbix-agent", "zabbix-tunnel"],
    },
    "mc2": {
        "host": "mc2",
        "ssh": ["sergio@127.0.0.1", "-p", "2222"],  # tunnel inverso
        "units": ["denaro-node-mc2", "denaro-feeder-mc2", "denaro-health-mc2", "denaro-dashboard-mc2",
                  "cloudflared-home", "zabbix-agent", "zabbix-tunnel-reverse"],
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
    live_dir = cfg.get("live_dir")
    globs = f"{data_dir}/*_health.json"
    if live_dir:
        globs += f" {live_dir}/*.json"
    cmd = (f"ssh -o BatchMode=yes -o ConnectTimeout=5 {ssh_args} "
           f"'for f in {globs}; do echo ===FILE===; cat \"$f\" 2>/dev/null; echo; done'")
    try:
        r = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, timeout=25)
        bots = {}
        if r.returncode == 0 and r.stdout.strip():
            for block in r.stdout.split("===FILE===")[1:]:
                lines = block.strip().splitlines()
                if not lines:
                    continue
                try:
                    h = json.loads(lines[-1])
                    sym = h.get("symbol")
                    if sym:
                        # health live (doge_nuvola.json) hanno symbol "DOGE/EUR":
                        # stessa chiave dei paper -> merge con priorita' al piu' fresco
                        if sym in bots and h.get("timestamp", 0) <= bots[sym].get("timestamp", 0):
                            continue
                        bots[sym] = h
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
                   f"'for u in {' '.join(units)}; do s=$(systemctl is-active $u 2>/dev/null); if [ $s != active ]; then s=$(XDG_RUNTIME_DIR=/run/user/1000 systemctl --user is-active $u 2>/dev/null); fi; echo $u=$s; done'")
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
        # Auto-heal remoto: DISATTIVATO per mc2/nuvola (19/09: causava heal-loop;
        # dal 25/09 ogni nodo si auto-riavvia con systemd Restart=always).
        if all_stale and node_name not in ("nuvola", "mc2"):
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
        # P5 — telemetria performance (value_type float)
        {"host": host, "key": f"{keybase}.sharpe", "value": h.get("sharpe", 0)},
        {"host": host, "key": f"{keybase}.sortino", "value": h.get("sortino", 0)},
        {"host": host, "key": f"{keybase}.calmar", "value": h.get("calmar", 0)},
        {"host": host, "key": f"{keybase}.profit_factor", "value": h.get("profit_factor", 0)},
        {"host": host, "key": f"{keybase}.win_rate", "value": h.get("win_rate_pct", 0)},
        {"host": host, "key": f"{keybase}.kelly", "value": h.get("kelly", 0)},
        {"host": host, "key": f"{keybase}.hurst", "value": h.get("hurst", 0.5)},
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


CANARY_STATE = Path("/home/marco/hermes_scratch/canary_state.json")


def push_novita(data):
    """[01/10] Metriche dei componenti nuovi: Canary C1 (carry live, locale su
    MARCODG1), Raccolta funding P8 e Fabbrica ×20 (su mc2, letti via tunnel
    inverso :2222). Nessun ordine, sola lettura."""
    now = time.time()
    # Canary (locale)
    try:
        cs = json.loads(CANARY_STATE.read_text())
        c_age = int(now - CANARY_STATE.stat().st_mtime)
    except Exception:
        cs, c_age = {}, 10 ** 9
    try:
        c_delta = float(cs.get("last_delta") or 0)
    except Exception:
        c_delta = 99.0
    ok = 1 if (cs.get("status") == "open" and c_age < 2400 and c_delta <= 1.0
               and float(cs.get("last_pos_ct") or 0) > 0) else 0
    data += [
        {"host": "MARCODG1", "key": "svc.canary", "value": ok},
        {"host": "MARCODG1", "key": "canary.age_s", "value": c_age},
        {"host": "MARCODG1", "key": "canary.upl", "value": round(float(cs.get("last_upl") or 0), 4)},
        {"host": "MARCODG1", "key": "canary.funding", "value": round(float(cs.get("last_funding") or 0), 4)},
        {"host": "MARCODG1", "key": "canary.delta_qty", "value": round(c_delta, 6)},
    ]
    # Raccolta + Fabbrica (mc2 via tunnel inverso)
    racc_age = fab_age = 10 ** 9
    racc_rows = 0
    racc_run_age = 10 ** 9
    hard_ok = 0
    try:
        cmd = ("ssh -o BatchMode=yes -o ConnectTimeout=5 sergio@127.0.0.1 -p 2222 "
               "'{ stat -c %Y /home/sergio/money/data/funding_xperp.jsonl 2>/dev/null || echo 0; "
               "wc -l < /home/sergio/money/data/funding_xperp.jsonl 2>/dev/null || echo 0; "
               "stat -c %Y /home/sergio/money/fabbrica/metrics.prom 2>/dev/null || echo 0; "
               "stat -c %Y /home/sergio/money/data/raccolta_last_run 2>/dev/null || echo 0; "
               "(sudo -n iptables -C INPUT -j MC2HARD >/dev/null 2>&1 && "
               "sudo -n ip6tables -C INPUT -j MC2HARD >/dev/null 2>&1 && echo 1 || echo 0); }'")
        r = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, timeout=25)
        nums = [x for x in r.stdout.split() if x]
        if len(nums) >= 5:
            mt1, rows, mt2, mmt, hard = (int(float(nums[0])), int(float(nums[1])),
                                         int(float(nums[2])), int(float(nums[3])),
                                         int(float(nums[4])))
            racc_age = int(now - mt1) if mt1 > 0 else 10 ** 9
            racc_rows = rows
            fab_age = int(now - mt2) if mt2 > 0 else 10 ** 9
            # [01/10] svc.raccolta = "il collector e' girato" (marker a fine run),
            # non l'eta' del data-file (tra eventi funding: solo duplicati).
            racc_run_age = int(now - mmt) if mmt > 0 else 10 ** 9
            hard_ok = hard
    except Exception:
        pass
    data += [
        {"host": "mc2", "key": "svc.raccolta", "value": 1 if racc_run_age < 21600 else 0},
        {"host": "mc2", "key": "raccolta.rows", "value": racc_rows},
        {"host": "mc2", "key": "raccolta.age_s", "value": racc_age},
        {"host": "mc2", "key": "svc.fabbrica", "value": 1 if fab_age < 120 else 0},
        {"host": "mc2", "key": "fabbrica.tick_age_s", "value": fab_age},
        {"host": "mc2", "key": "mc2.sec.hardening", "value": hard_ok},
    ]


# Officina paper (01/10/26): heartbeat della flotta riconvertita — per nodo,
# numero di bot paper freschi (<300s) e eta' del file piu' vecchio. Se un nodo
# smette di tickare, gli item flotta.paper_* lo dicono (trigger dedicati).
PAPER_WATCH = {
    "MARCODG1": {"ssh": None, "dir": "/home/marco/denaro/health"},
    "mc2": {"ssh": ["sergio@127.0.0.1", "-p", "2222"],
            "dir": "/home/sergio/denaro/health"},
    "nuvola": {"ssh": ["sergio@87.106.3.15", "-p", "22"],
               "dir": "/home/sergio/denaro/health"},
}


def push_flotta_paper(data):
    now = time.time()
    for host, cfg in PAPER_WATCH.items():
        d = cfg["dir"]
        if cfg["ssh"]:
            ssh_args = " ".join(cfg["ssh"])
            cmd = (f"ssh -o BatchMode=yes -o ConnectTimeout=5 {ssh_args} "
                   f"'for f in {d}/*_paper.json; do stat -c %Y \"$f\" 2>/dev/null; done'")
            try:
                r = subprocess.run(["bash", "-c", cmd], capture_output=True,
                                   text=True, timeout=20)
                mts = [int(x) for x in r.stdout.split() if x.strip().isdigit()]
            except Exception:
                mts = []
        else:
            try:
                mts = [int(p.stat().st_mtime) for p in Path(d).glob("*_paper.json")]
            except Exception:
                mts = []
        fresh = sum(1 for m in mts if now - m <= 300)
        oldest = int(now - min(mts)) if mts else 10 ** 9
        data += [
            {"host": host, "key": "flotta.paper_n", "value": fresh},
            {"host": host, "key": "flotta.paper_age_s", "value": oldest},
        ]


def main():
    auth = rpc("user.login", {"username": USER, "password": PASS})
    if not auth:
        print("LOGIN FALLITO")
        return

    data = []

    # ── 1. [rimosso 01/10/26] Bot legacy sol/ada/doge/eth — host inesistenti;
    #     pulizia Zabbix: i 17 host alpha-omega-bot-* sono stati rimossi. ──

    # ── 2. [rimosso 01/10] Bot Kraken — Kraken fuori dal progetto. ──

    # ── 3. Progetto aggregato (da infra_snapshot) ──
    infra = read_json(HEALTH_DIR / "infra_snapshot.json")
    if infra:
        host = "alpha-omega-project"
        prices = infra.get("prices", {})
        data += [
            {"host": host, "key": "project.equity", "value": infra.get("total_equity", 0)},
            # [01/10/26] project.bot_equity rimosso (aggregato flotta storica).
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
        # [01/10/26] project.pnl_total / trades_total / win_rate RIMOSSI:
        # aggregati della flotta storica ormai a zero; item Zabbix eliminati.

    # ── 4. Paper bot v3.3 (RIMOSSO 2026-08-25): i motori paper v3.3 sono stati
    #     fermati/disabilitati (ridondanti) — i paper girano nel Node e sono
    #     pushati nella sezione 5 (node.*). I file paper_state sono congelati.
    # ── 5. [rimosso 01/10/26] Node paper / bot live ATLAS / TREND paper: host
    #     alpha-omega-node-paper/-trend inesistenti; pulizia Zabbix 01/10. ──

    # ── 5b. [rimosso 01/10/26] Bot LIVE ATLAS (health/ada.json ecc.). ──

    # ── 5c. [rimosso 01/10/26] istanza TREND paper (MARCODG1). ──

    # ── 5c-bis. [rimosso 01/10] TREND LIVE Kraken (trend_sol/trend_xrp). ──

    # ── 8. [01/10] Canary C1 · Raccolta P8 · Fabbrica ×20 ──
    push_novita(data)

    # ── 8b. [01/10] Flotta paper (officina): heartbeat per nodo ──
    push_flotta_paper(data)

    # ── 6. [rimosso 01/10/26] push_remote_nodes disattivato: pushava su host
    #     alpha-omega-node-nuvola/-mc2 (inesistenti). Lo stato nodi arriva da
    #     push_services + canary/raccolta/fabbrica qui sotto. ──

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
