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
PORT = int(os.getenv("AGG_PORT", "8912"))
HOST = os.getenv("AGG_HOST", "127.0.0.1")

# Conti OKX (per saldi reali)
ENV_FILES = {
    "denaro (main)": "/home/marco/denaro/.env",
    "alpha (marcosub1)": "/home/marco/alpha-omega-trading/.env",
}

NODES = {
    "nuvola": ("87.106.3.15", 22),
    "mc2": ("192.168.1.99", 22),
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
    containers = docker_state()
    z = {}
    for name in ("zabbix-web", "zabbix-server", "zabbix-db"):
        z[name] = containers.get(name, "DOWN")
    # Web reachable?
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
    # 1b) Bot Kraken su nuvola (da snapshot locale aggiornato via cron/scp)
    kraken = None
    snap_path = HEALTH_DIR / "kraken_snapshot.json"
    if snap_path.exists():
        try:
            snap = json.loads(snap_path.read_text())
            kraken = snap.get("bot")
        except Exception:
            snap = None
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

    # 7) Totali — somma bot OKX + saldo Kraken (per riflettere tutto il capitale)
    bot_eq = 0.0
    for name, b in bots.items():
        if name == "sol_kraken":
            continue
        if b.get("status") == "running":
            bot_eq += b.get("total_equity", 0)
    kraken_eur = 0.0
    if balances.get("kraken (nuvola)") and balances["kraken (nuvola)"].get("total_eur"):
        kraken_eur = balances["kraken (nuvola)"]["total_eur"]
    data["bot_equity"] = round(bot_eq, 2)
    data["kraken_equity"] = round(kraken_eur, 2)
    data["total_equity"] = round(bot_eq + kraken_eur, 2)
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
