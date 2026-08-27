#!/usr/bin/env python3
"""
Alpha-Omega Infra Aggregator — raccoglie lo stato di TUTTA l'infrastruttura
e lo espone come JSON per la dashboard web.

Dati raccolti:
- Bot trading (SOL/EUR, ADA/EUR) da health files
- Saldi OKX reali (entrambi i conti) via ccxt
- Prezzi correnti SOL/ADA
- Stato nodi (nuvola, mc2) via SSH ping
- Stato Zabbix (container + web)
- Stato tunnel Zabbix

Endpoints (HTTP):
  GET /infra.json  → tutto (usato dalla dashboard)
  GET /health      → stato aggregato bot (compatibile zabbix_fleet)
"""
import json
import os
import socket
import subprocess
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

HEALTH_DIR = Path(os.getenv("HEALTH_DIR", "/home/marco/denaro/health"))
NODE_DIR = Path(os.getenv("NODE_DIR", "/home/marco/denaro_node_app/node_data"))
PORT = int(os.getenv("AGG_PORT", "8912"))
HOST = os.getenv("AGG_HOST", "127.0.0.1")

# Nodi remoti che eseguono il Node Denaro (paper/live). L'aggregator gira su
# MARCODG1 e li legge via SSH (stesso meccanismo di zabbix_state).
# remote_data_dir: cartella node_data sul nodo remoto.
REMOTE_NODES = {
    "nuvola": {
        "ssh": ["sergio@87.106.3.15", "-p", "22"],
        "data_dir": "/home/sergio/denaro_node_app/node_data",
        "unit": "denaro-node-nuvola",
    },
    "mc2": {
        "ssh": ["sergio@127.0.0.1", "-p", "2222"],  # tunnel inverso
        "data_dir": "/home/sergio/denaro_node_app/node_data",
        "unit": "denaro-node-mc2",
    },
}

# Conti OKX (per saldi reali)
ENV_FILES = {
    "denaro (main)": "/home/marco/denaro/.env",
    "alpha (marcosub1)": "/home/marco/alpha-omega-trading/.env",
}

NODES = {
    "nuvola": ("87.106.3.15", 22),
    "mc2": ("127.0.0.1", 2222),   # via tunnel inverso (autossh -R 2222 su MARCODG1)
    "marcodg1": ("127.0.0.1", 22),
}


def load_env(path):
    env = {}
    p = Path(path)
    if p.exists():
        for line in p.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


_remote_cache = {}
_REMOTE_TTL = 30.0  # secondi


def fetch_remote_json(host, remote_path, cmd=None):
    """Legge un JSON da una macchina remota via SSH, con cache TTL (30s)."""
    cache_key = f"{host}:{remote_path}:{cmd}"
    now = time.time()
    hit = _remote_cache.get(cache_key)
    if hit and now - hit[0] < _REMOTE_TTL:
        return hit[1]
    try:
        if cmd:
            full = f"ssh -o BatchMode=yes -o ConnectTimeout=5 {host} {cmd}"
            r = subprocess.run(["bash", "-c", full], capture_output=True, text=True, timeout=25)
            if r.returncode != 0 or not r.stdout.strip():
                return None
            val = json.loads(r.stdout.strip().splitlines()[-1])
        else:
            full = f"ssh -o BatchMode=yes -o ConnectTimeout=5 {host} cat {remote_path}"
            r = subprocess.run(["bash", "-c", full], capture_output=True, text=True, timeout=15)
            if r.returncode != 0 or not r.stdout.strip():
                return None
            val = json.loads(r.stdout.strip())
        _remote_cache[cache_key] = (now, val)
        return val
    except Exception:
        return None


_balance_cache = {}
_BAL_TTL = 20.0


def fetch_okx_balance(env):
    try:
        key = env.get("OKX_API_KEY", "")[:10]
        now = time.time()
        hit = _balance_cache.get(key)
        if hit and now - hit[0] < _BAL_TTL:
            return hit[1]
        import ccxt
        ex = ccxt.okx({
            "apiKey": env.get("OKX_API_KEY", ""),
            "secret": env.get("OKX_API_SECRET", ""),
            "password": env.get("OKX_PASSPHRASE", ""),
            "enableRateLimit": True,
            "hostname": "eea.okx.com",
        })
        b = ex.fetch_balance()
        total = {k: round(v, 6) for k, v in b.get("total", {}).items() if v and v > 0}
        free = {k: round(v, 6) for k, v in b.get("free", {}).items() if v and v > 0}
        val = {"ok": True, "total": total, "free": free}
        _balance_cache[key] = (now, val)
        return val
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


_price_cache = {}
_PRICE_TTL = 15.0


def fetch_prices():
    try:
        now = time.time()
        hit = _price_cache.get("prices")
        if hit and now - hit[0] < _PRICE_TTL:
            return hit[1]
        import ccxt
        ex = ccxt.okx({"enableRateLimit": True, "hostname": "eea.okx.com"})
        prices = {}
        for s in ("SOL/EUR", "ADA/EUR", "XRP/EUR", "DOGE/EUR"):
            try:
                t = ex.fetch_ticker(s)
                prices[s] = {"last": t["last"], "bid": t.get("bid"), "ask": t.get("ask"),
                             "pct24h": t.get("percentage")}
            except Exception:
                prices[s] = None
        _price_cache["prices"] = (now, prices)
        return prices
    except Exception as e:
        return {"error": str(e)[:200]}


def ping_host(host, port, timeout=4):
    try:
        s = socket.create_connection((host, port), timeout=timeout)
        s.close()
        return True
    except Exception:
        return False


def docker_state():
    try:
        r = subprocess.run(["docker", "ps", "--format", "{{.Names}}|{{.Status}}"],
                           capture_output=True, text=True, timeout=10)
        containers = {}
        for line in r.stdout.strip().splitlines():
            if "|" in line:
                name, status = line.split("|", 1)
                containers[name] = status
        return containers
    except Exception as e:
        return {"error": str(e)[:200]}


def zabbix_state():
    """Stato dei container Zabbix — che girano su MC2, letti via tunnel SSH
    (127.0.0.1:2222 -> porta 22 di mc2). Fallback: web check via tunnel 1080."""
    z = {}
    try:
        r = subprocess.run(
            ["ssh", "-p", "2222", "-o", "BatchMode=yes", "-o", "ConnectTimeout=6",
             "-o", "StrictHostKeyChecking=accept-new", "sergio@127.0.0.1",
             "docker ps --format '{{.Names}}|{{.Status}}'"],
            capture_output=True, text=True, timeout=15)
        found = False
        for line in r.stdout.splitlines():
            if "|" in line:
                name, status = line.split("|", 1)
                if name in ("zabbix-web", "zabbix-server", "zabbix-db"):
                    z[name] = status
                    found = True
        if not found:
            z = {"tunnel": "nessun container zabbix da mc2",
                 "stderr": r.stderr.strip()[:100]}
    except Exception as e:
        z = {"ssh_error": str(e)[:100]}
    # Web reachable (tunnel 1080 su mc2)
    try:
        import urllib.request
        with urllib.request.urlopen("http://127.0.0.1:1080/", timeout=5) as r:
            z["web_http"] = r.status
    except Exception as e:
        z["web_http"] = str(e)[:100]
    return z


def system_state():
    try:
        r = subprocess.run(["uptime"], capture_output=True, text=True, timeout=5)
        load = r.stdout.strip()
        mem = subprocess.run(["free", "-m"], capture_output=True, text=True, timeout=5)
        mem_line = [l for l in mem.stdout.splitlines() if l.startswith("Mem:")][0]
        parts = mem_line.split()
        return {"uptime": load, "mem_total_mb": parts[1], "mem_used_mb": parts[2],
                "mem_free_mb": parts[3]}
    except Exception as e:
        return {"error": str(e)[:200]}


def collect_node_bots():
    """Tutti i health del Node — paper (node_data/*_health.json) + live
    (health_path espliciti: health/ada.json, sol.json, sol_kraken.json)."""
    bots = {}
    try:
        for p in sorted(NODE_DIR.glob("*_health.json")):
            try:
                h = json.loads(p.read_text())
                bots[h.get("symbol", p.stem)] = h
            except Exception:
                continue
    except Exception:
        pass
    live = {
        "okx:ADA/EUR": HEALTH_DIR / "ada.json",
        "okx:SOL/EUR": HEALTH_DIR / "sol.json",
        "kraken:SOL/EUR": HEALTH_DIR / "sol_kraken.json",
    }
    for key, p in live.items():
        try:
            h = json.loads(p.read_text())
            if h.get("timestamp"):
                bots[key] = h
        except Exception:
            continue
    # Nodi remoti: chiavi "nuvola:paper:ADA/EUR", "mc2:paper:ADA/EUR" ecc.
    for node_name, cfg in REMOTE_NODES.items():
        for sym, h in fetch_remote_node_bots(node_name).items():
            bots[f"{node_name}:{sym}"] = h
    return bots


def fetch_remote_node_bots(node_name):
    """Legge i *_health.json del Node remoto via SSH (con cache TTL)."""
    cfg = REMOTE_NODES.get(node_name)
    if not cfg:
        return {}
    data_dir = cfg["data_dir"]
    cache_key = f"remote_node:{node_name}"
    now = time.time()
    hit = _remote_cache.get(cache_key)
    if hit and now - hit[0] < _REMOTE_TTL:
        return hit[1]
    ssh_args = " ".join(cfg["ssh"])
    cmd = (f"ssh -o BatchMode=yes -o ConnectTimeout=5 {ssh_args} "
           f"'for f in {data_dir}/*_health.json; do echo ===FILE===; cat \"$f\"; echo; done'")
    try:
        r = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, timeout=20)
        bots = {}
        if r.returncode == 0 and r.stdout.strip():
            blocks = r.stdout.split("===FILE===")
            for block in blocks[1:]:
                lines = block.strip().splitlines()
                if not lines:
                    continue
                try:
                    h = json.loads(lines[-1])
                    sym = h.get("symbol", "unknown")
                    bots[sym] = h
                except Exception:
                    continue
        _remote_cache[cache_key] = (now, bots)
        return bots
    except Exception:
        return {}


def read_trend():
    """Serie storica equity (aggiornata da infra_snapshot via cron)."""
    try:
        return json.loads((HEALTH_DIR / "trend.json").read_text())
    except Exception:
        return []


# Servizi Denaro per macchina (stesso set di push_metrics.py) → dashboard
SERVICE_UNITS = {
    "marcodg1": {
        "ssh": [],
        "units": [
            "denaro-node-paper", "denaro-node-trend", "denaro-node-trend-live",
            "denaro-health-marcodg1", "denaro-aggregator-marcodg1",
            "denaro-brain", "zabbix-agent",
        ],
    },
    "nuvola": {
        "ssh": ["sergio@87.106.3.15", "-p", "22"],
        "units": ["denaro-node-nuvola", "denaro-health-nuvola",
                  "zabbix-agent", "zabbix-tunnel"],
    },
    "mc2": {
        "ssh": ["sergio@127.0.0.1", "-p", "2222"],  # tunnel inverso
        "units": ["denaro-node-mc2", "denaro-feeder-mc2", "denaro-health-mc2",
                  "zabbix-agent", "zabbix-tunnel-reverse"],
    },
}


def collect_services():
    """Stato dei servizi Denaro per macchina (systemctl is-active)."""
    out = {}
    for node_name, cfg in SERVICE_UNITS.items():
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
        out[node_name] = {
            "units": {u: (1 if states.get(u) == "active" else 0) for u in units},
            "all_active": all(states.get(u) == "active" for u in units),
        }
    return out


def write_trend(points):
    try:
        (HEALTH_DIR / "trend.json").write_text(json.dumps(points))
    except Exception:
        pass


def collect():
    data = {"generated": time.time(), "ts_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}

    # 1) Bot health files
    bots = {}
    for name in ("sol", "ada"):
        p = HEALTH_DIR / f"{name}.json"
        if p.exists():
            try:
                bots[name] = json.loads(p.read_text())
            except Exception:
                bots[name] = {"status": "error"}
        else:
            bots[name] = {"status": "no_file"}
    # 1b) Bot Kraken (ora LOCALE nel Node: health/sol_kraken.json;
    #      fallback retro-compatibile allo snapshot da nuvola)
    kraken = None
    snap = None
    snap_path = HEALTH_DIR / "kraken_snapshot.json"
    kraken_path = HEALTH_DIR / "sol_kraken.json"
    if kraken_path.exists():
        try:
            kraken = json.loads(kraken_path.read_text())
        except Exception:
            kraken = None
    if not kraken:
        if snap_path.exists():
            try:
                snap = json.loads(snap_path.read_text())
                kraken = snap.get("bot")
            except Exception:
                kraken = None
    if kraken:
        bots["sol_kraken"] = kraken
    data["bots"] = bots

    # 2) Saldi OKX reali + Kraken (da snapshot locale)
    balances = {}
    for label, path in ENV_FILES.items():
        env = load_env(path)
        if env.get("OKX_API_KEY"):
            balances[label] = fetch_okx_balance(env)
        else:
            balances[label] = {"ok": False, "error": "no key"}
    if snap_path.exists() and snap:
        balances["kraken (nuvola)"] = {
            "ok": True,
            "total": snap.get("balance", {}),
            "total_eur": snap.get("total_eur", 0),
        }
    data["balances"] = balances

    # 3) Prezzi
    data["prices"] = fetch_prices()

    # 4) Nodi
    nodes = {}
    for name, (host, port) in NODES.items():
        nodes[name] = {"reachable": ping_host(host, port), "host": host}
    data["nodes"] = nodes

    # 5) Zabbix + tunnel
    data["zabbix"] = zabbix_state()
    data["docker"] = docker_state()

    # 6) Sistema
    data["system"] = system_state()

    # 8) Node (Fase 3) — tutti i bot (paper + live) + aggregati
    node_bots = collect_node_bots()
    data["node_bots"] = node_bots

    # 7) CAPITALE TOTALE REALE = somma dei bot LIVE del Node (okx:* + kraken:*),
    #    escludendo i paper virtuali (ADA/EUR, SOL/EUR, XRP/EUR locali e remoti).
    #    NB: i vecchi health file (health/sol.json ecc.) e il kraken_snapshot.json
    #    da nuvola sono obsoleti — il Node scrive i valori live aggiornati.
    okx_eq = sum(b.get("total_equity", 0) for k, b in node_bots.items()
                 if k.startswith("okx:") and b.get("status") == "running")
    kraken_eq = sum(b.get("total_equity", 0) for k, b in node_bots.items()
                    if k.startswith("kraken:") and b.get("status") == "running")
    data["bot_equity"] = round(okx_eq, 2)
    data["kraken_equity"] = round(kraken_eq, 2)
    data["total_equity"] = round(okx_eq + kraken_eq, 2)

    node_running = [b for b in node_bots.values() if b.get("status") == "running"]
    data["node_total_pnl"] = round(sum(b.get("pnl", 0) for b in node_running), 4)
    data["node_total_trades"] = sum(b.get("trades", 0) for b in node_running)
    wins = sum(b.get("wins", 0) for b in node_running)
    losses = sum(b.get("losses", 0) for b in node_running)
    data["node_win_rate"] = round(wins / (wins + losses) * 100, 1) if (wins + losses) else 0
    data["node_errors"] = {sym: b.get("error", "")
                           for sym, b in node_bots.items() if b.get("error")}

    # 8b) Totali PER NODO: marcodg1 (locale) + nuvola + mc2 (via SSH)
    node_totals = {}
    all_node_names = ["marcodg1"] + list(REMOTE_NODES.keys())
    remote_prefixes = tuple(f"{n}:" for n in REMOTE_NODES)
    for node_name in all_node_names:
        if node_name == "marcodg1":
            nb = {k: v for k, v in node_bots.items()
                  if not k.startswith(remote_prefixes)}
        else:
            prefix = f"{node_name}:"
            nb = {k: v for k, v in node_bots.items() if k.startswith(prefix)}
        running = [b for b in nb.values() if b.get("status") == "running"]
        node_totals[node_name] = {
            "bots": len(nb),
            "running": len(running),
            "pnl": round(sum(b.get("pnl", 0) for b in running), 4),
            "trades": sum(b.get("trades", 0) for b in running),
            "equity": round(sum(b.get("total_equity", 0) for b in running), 2),
            "reachable": (node_name == "marcodg1"
                          or any(h.get("timestamp") for h in nb.values())),
        }
    data["node_totals"] = node_totals
    data["services"] = collect_services()
    data["trend"] = read_trend()[-240:]
    return data


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, payload):
        body = json.dumps(payload, indent=1).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0].rstrip("/")
        try:
            if path in ("/infra.json", "/api/infra.json", ""):
                # Preferisce lo snapshot pre-generato (istantaneo); fallback live
                snap_path = HEALTH_DIR / "infra_snapshot.json"
                if snap_path.exists():
                    try:
                        payload = json.loads(snap_path.read_text())
                        payload["cached"] = True
                        payload["cached_age"] = round(time.time() - payload.get("generated", 0), 1)
                        self._send(200, payload)
                        return
                    except Exception:
                        pass
                self._send(200, collect())
            elif path == "/health":
                bots = {}
                for name in ("sol", "ada"):
                    p = HEALTH_DIR / f"{name}.json"
                    if p.exists():
                        try:
                            bots[name] = json.loads(p.read_text())
                        except Exception:
                            pass
                ok = len(bots) > 0 and all(b.get("status") == "running" for b in bots.values())
                self._send(200, {"status": "healthy" if ok else "degraded",
                                 "timestamp": time.time(), "bots": bots})
            else:
                self._send(404, {"status": "not_found"})
        except Exception as e:
            self._send(500, {"status": "error", "error": str(e)})

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    print(f"Infra aggregator on {HOST}:{PORT}")
    HTTPServer((HOST, PORT), Handler).serve_forever()
