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
import shlex
import socket
import subprocess
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

HEALTH_DIR = Path(os.getenv("HEALTH_DIR", "/home/marco/denaro/health"))
NODE_DIR = Path(os.getenv("NODE_DIR", "/home/marco/alpha-omega-trading/node_data"))
PORT = int(os.getenv("AGG_PORT", "8912"))
HOST = os.getenv("AGG_HOST", "127.0.0.1")

# Nodi remoti che eseguono il Node Denaro (paper/live). L'aggregator gira su
# MARCODG1 e li legge via SSH (stesso meccanismo di zabbix_state).
# remote_data_dir: cartella node_data sul nodo remoto.
REMOTE_NODES = {
    "nuvola": {
        "ssh": ["sergio@87.106.3.15", "-p", "22"],
        "data_dir": "/home/sergio/alpha-omega-trading/node_data",
        "unit": "denaro-node-nuvola",
    },
    "mc2": {
        "ssh": ["sergio@127.0.0.1", "-p", "2222"],  # tunnel inverso
        "data_dir": "/home/sergio/denaro/health",
        "unit": "denaro-node-mc2",
    },
}

# Conti OKX letti dai .env LOCALI a MARCODG1: label -> (path, prefisso chiavi).
# Il prefisso seleziona le chiavi del subaccount (es. MARCOSUB1_OKX_API_KEY);
# senza prefisso si usano le chiavi del conto master.
ENV_FILES = {
    "OKX main": ("/home/marco/denaro/.env", ""),
    "OKX marcosub1": ("/home/marco/alpha-omega-trading/.env", "MARCOSUB1_"),
}

# Sub-account con chiavi IP-bound: il .env deve essere letto SULLA macchina di
# origine. label -> (ssh_target, ssh_port, remote_env_path, remote_python)
REMOTE_ENV_SOURCES = {
    "OKX mc2sub1": ("sergio@127.0.0.1", 2222, "/home/sergio/alpha-omega-trading/.env", "/usr/bin/python3"),
    "OKX nuvolasub1": ("sergio@87.106.3.15", 22, "/home/sergio/denaro/.env", "/home/sergio/denaro/venv/bin/python"),
}

# Kraken: piu' chiavi API possono puntare allo STESSO conto -> si deduplica per
# fingerprint della chiave, altrimenti il capitale verrebbe contato piu' volte.
KRAKEN_ENV_FILES = [
    ("/home/marco/denaro/.env", "KRAKEN_API_KEY", "KRAKEN_API_SECRET"),
    ("/home/marco/alpha-omega-trading/.env", "TRENDSUB_KRAKEN_API_KEY", "TRENDSUB_KRAKEN_API_SECRET"),
    ("/home/marco/alpha-omega-trading/.env", "NUVOLASUB1_KRAKEN_API_KEY", "NUVOLASUB1_KRAKEN_API_SECRET"),
]

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

# Dopo quanti secondi un health file e' considerato VECCHIO. Un bot ticka ogni
# 30 s: 5 minuti di silenzio significano che quel bot non sta lavorando.
# Serve a non presentare come "running" un nodo spento giorni prima.
BOT_STALE_S = 300.0


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


def fetch_kraken_balance(env, key_attr="KRAKEN_API_KEY", secret_attr="KRAKEN_API_SECRET"):
    """Saldo Kraken LIVE (ccxt)."""
    try:
        key = env.get(key_attr, "")[:10]
        now = time.time()
        hit = _balance_cache.get("kraken:" + key)
        if hit and now - hit[0] < _BAL_TTL:
            return hit[1]
        import ccxt
        ex = ccxt.kraken({
            "apiKey": env.get(key_attr, ""),
            "secret": env.get(secret_attr, ""),
            "enableRateLimit": True,
        })
        b = ex.fetch_balance()
        total = {k: round(v, 6) for k, v in b.get("total", {}).items() if v and v > 0}
        val = {"ok": True, "total": total,
               "free": {k: round(v, 6) for k, v in b.get("free", {}).items() if v and v > 0}}
        _balance_cache["kraken:" + key] = (now, val)
        return val
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


def _acct_fp(*parts):
    """Fingerprint non reversibile di una chiave API: serve a deduplicare gli account."""
    import hashlib
    return hashlib.md5("|".join(p or "" for p in parts).encode()).hexdigest()[:12]


def _remote_okx_snippet(env_path):
    """Snippet Python eseguito SUL nodo di origine per leggere il saldo OKX."""
    return (
        "import json\n"
        "env = {}\n"
        "for line in open(" + repr(env_path) + "):\n"
        "    if '=' in line and not line.strip().startswith('#'):\n"
        "        k, v = line.strip().split('=', 1)\n"
        "        env[k.strip()] = v.strip().strip(chr(34)).strip(chr(39))\n"
        "import ccxt\n"
        "ex = ccxt.okx({'apiKey': env.get('OKX_API_KEY'), 'secret': env.get('OKX_API_SECRET'),"
        " 'password': env.get('OKX_PASSPHRASE'), 'hostname': 'eea.okx.com'})\n"
        "b = ex.fetch_balance()\n"
        "print(json.dumps({'ok': True, 'total': b.get('total', {}), 'free': b.get('free', {})}))\n"
    )


def fetch_remote_okx_balance(ssh_target, ssh_port, remote_env, remote_python="/usr/bin/python3", ttl=30.0):
    """Saldo OKX di un subaccount con chiavi IP-bound, letto sul nodo di origine."""
    cache_key = "remoteokx:%s:%s" % (ssh_target, remote_env)
    now = time.time()
    hit = _balance_cache.get(cache_key)
    if hit and now - hit[0] < ttl:
        return hit[1]
    try:
        # NB: niente "bash -c" locale: passando l'argv direttamente a ssh, il
        # quoting sopravvive al doppio parsing (locale + shell remota).
        cmd = ["ssh", "-p", str(ssh_port), "-o", "BatchMode=yes", "-o", "ConnectTimeout=6",
               ssh_target, remote_python, "-c", shlex.quote(_remote_okx_snippet(remote_env))]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
        if r.returncode != 0 or not r.stdout.strip():
            return None
        val = json.loads(r.stdout.strip().splitlines()[-1])
        if val.get("ok"):
            val["total"] = {k: v for k, v in (val.get("total") or {}).items() if v and float(v) > 0}
            val["acct"] = _acct_fp(ssh_target, remote_env)
            _balance_cache[cache_key] = (now, val)
        return val
    except Exception:
        return None


_EUR_FIAT = {"EUR"}
_EUR_STABLES = {"USDC", "USDT", "USD", "DAI", "TUSD", "BUSD", "USDE"}
_rate_cache = {}
_RATE_TTL = 60.0


def fetch_eur_rate(cur, _depth=0):
    """Quanto vale 1 unita' della valuta indicata in EUR (cache 60s)."""
    if cur in _EUR_FIAT:
        return 1.0
    now = time.time()
    hit = _rate_cache.get(cur)
    if hit and now - hit[0] < _RATE_TTL:
        return hit[1]
    rate = None
    pairs = [("%s/EUR" % cur, False), ("EUR/%s" % cur, True)]
    if cur not in _EUR_STABLES and _depth < 2:
        pairs += [("%s/USDT" % cur, False), ("%s/USDC" % cur, False)]
    try:
        import ccxt
        ex = ccxt.okx({"enableRateLimit": True, "hostname": "eea.okx.com"})
        for pair, invert in pairs:
            try:
                last = float(ex.fetch_ticker(pair)["last"])
            except Exception:
                continue
            if not last:
                continue
            if pair.endswith("/EUR"):
                rate = last
            elif invert:
                rate = 1.0 / last
            else:
                base_rate = fetch_eur_rate(pair.split("/")[1], _depth + 1)
                rate = last * base_rate if base_rate else None
            if rate:
                break
    except Exception:
        rate = None
    _rate_cache[cur] = (now, rate)
    return rate


def balance_eur(balances):
    """Valorizza in EUR i saldi reali deduplicando gli account identici.

    Ritorna (totale_eur, dettaglio_per_etichetta, quote_non_valutate).
    """
    seen = []
    detail = {}
    total = 0.0
    unpriced = []
    for label, bal in balances.items():
        if not isinstance(bal, dict) or not bal.get("ok"):
            err = bal.get("error", "") if isinstance(bal, dict) else "n/d"
            detail[label] = {"ok": False, "eur": None, "error": str(err)[:80]}
            continue
        fp = bal.get("acct") or label
        if fp in seen:
            detail[label] = {"ok": True, "eur": None, "dedup": True}
            continue
        seen.append(fp)
        tot = 0.0
        for cur, amt in (bal.get("total") or {}).items():
            try:
                amt = float(amt)
            except Exception:
                continue
            if amt <= 0:
                continue
            rate = fetch_eur_rate(cur)
            if rate is None:
                unpriced.append("%s:%s" % (label, cur))
                continue
            tot += amt * rate
        detail[label] = {"ok": True, "eur": round(tot, 2)}
        total += tot
    return round(total, 2), detail, unpriced


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
                h["mode"] = "paper"
                bots[h.get("symbol", p.stem)] = h
            except Exception:
                continue
    except Exception:
        pass
    # istanza TREND paper (MARCODG1): node_data_trend/paper_default_*
    try:
        trend_dir = NODE_DIR.parent / "node_data_trend"
        for p in sorted(trend_dir.glob("*_health.json")):
            try:
                h = json.loads(p.read_text())
                h["mode"] = "paper"
                bots[f"trend:{h.get('symbol', p.stem)}"] = h
            except Exception:
                continue
    except Exception:
        pass
    live = {
        "okx:ADA/EUR": HEALTH_DIR / "ada.json",
        "okx:SOL/EUR": HEALTH_DIR / "sol.json",
        "okx:DOGE/EUR": HEALTH_DIR / "doge.json",
        "okx:ETH/EUR": HEALTH_DIR / "eth.json",
        "kraken:SOL/EUR": HEALTH_DIR / "sol_kraken.json",
        "trend-live:SOL/EUR": HEALTH_DIR / "trend_sol_kraken.json",
        "trend-live:XRP/EUR": HEALTH_DIR / "trend_xrp_kraken.json",
        "mc2:okx:DOGE/EUR": HEALTH_DIR / "doge_mc2.json",
        "mc2:okx:SOL/EUR": HEALTH_DIR / "sol_mc2.json",
    }
    for key, p in live.items():
        try:
            h = json.loads(p.read_text())
            if h.get("timestamp"):
                h["mode"] = "live"
                bots[key] = h
        except Exception:
            continue
    # ── mc2 (LIVE OKX): i suoi health vivono su mc2, non su MARCODG1 ──────
    # Il glob generico dei nodi remoti perde questi file o li confonde con i
    # fossili (*_nuvola.json, stesso symbol ma fermi da giorni): li leggiamo
    # PER NOME, che e' l'unica cosa che distingue un bot vivo da un residuo.
    _mcfg = REMOTE_NODES.get("mc2")
    if _mcfg:
        _ssh = " ".join(_mcfg["ssh"])
        # 2026-09-17: mc2 e' passato dalla griglia al TREND GIORNALIERO su
        # 5 asset. I nomi sono espliciti perche' il glob generico perde
        # questi file o li confonde con i fossili.
        for _fn in ("btc_mc2.json", "eth_mc2.json", "sol_mc2.json",
                    "xrp_mc2.json", "doge_mc2.json"):
            _rp = _mcfg["data_dir"].rstrip("/") + "/" + _fn
            _cmd = ("ssh -o BatchMode=yes -o ConnectTimeout=5 " + _ssh +
                    " 'cat " + _rp + " 2>/dev/null'")
            try:
                _r = subprocess.run(["bash", "-c", _cmd], capture_output=True,
                                    text=True, timeout=15)
                if _r.returncode == 0 and _r.stdout.strip():
                    _h = json.loads(_r.stdout.strip().splitlines()[-1])
                    _sym = _h.get("symbol", "")
                    if _sym:
                        _h["mode"] = "live"
                        bots["mc2:okx:" + _sym] = _h
            except Exception:
                continue

    # ── Bot LIVE nuovi (2026-09-17) ────────────────────────────────────────
    # nuvola  : momentum SOL/EUR su nuvolasub1 -> health su nuvola
    # marcodg1: mean-reversion XRP/EUR su marcosub1 -> health locale
    # Ognuno scrive in una dir dedicata (node_data_trade / node_data_xrp) che
    # il collector generico non guarda: li leggiamo per path esplicito.
    _extra_live = [
        ("nuvola:okx:SOL/EUR",   "ssh",  "nuvola",  "/home/sergio/denaro/health/sol_nuvola_live.json"),
        ("marcodg1:okx:XRP/EUR", "file", None,      "/home/marco/denaro/health/xrp_marcodg1_live.json"),
    ]
    for _k, _kind, _alias, _path in _extra_live:
        try:
            if _kind == "file":
                _raw = Path(_path).read_text()
            else:
                _pr = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5",
                                      _alias, "cat " + _path],
                                     capture_output=True, text=True, timeout=15)
                _raw = _pr.stdout if _pr.returncode == 0 else ""
            if _raw.strip():
                _h = json.loads(_raw.strip().splitlines()[-1])
                _h["mode"] = "live"
                bots[_k] = _h
        except Exception:
            continue

    # Nodi remoti: chiavi "nuvola:paper:ADA/EUR", "mc2:paper:ADA/EUR" ecc.
    for node_name, cfg in REMOTE_NODES.items():
        for sym, h in fetch_remote_node_bots(node_name).items():
            h.setdefault("mode", "paper")
            bots[f"{node_name}:{sym}"] = h
    # Freschezza REALE: un health file vecchio non e' un bot che sta lavorando.
    # Prima la dashboard mostrava come "running" nodi spenti da giorni (es.
    # trend_sol_kraken.json fermo al 24 agosto, nuvola da 23 ore).
    now = time.time()
    for _key, h in bots.items():
        if not isinstance(h, dict):
            continue
        try:
            ts = float(h.get("timestamp") or 0.0)
        except (TypeError, ValueError):
            ts = 0.0
        age = (now - ts) if ts else None
        h["age_s"] = round(age, 1) if age is not None else None
        h["stale"] = (age is None) or (age > BOT_STALE_S)
        h.setdefault("mode", "paper")
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
           f"'for f in {data_dir}/*_health.json {data_dir}/*.json; do if [ -f \"$f\" ]; then echo ===FILE===; cat \"$f\"; echo; fi; done'")
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
        # istanza TREND paper sul remoto: node_data_trend/*_health.json
        trend_dir = data_dir.rsplit("/", 1)[0] + "/node_data_trend"
        cmd2 = (f"ssh -o BatchMode=yes -o ConnectTimeout=5 {ssh_args} "
                f"'for f in {trend_dir}/*_health.json; do echo ===FILE===; cat \"$f\"; echo; done'")
        try:
            r2 = subprocess.run(["bash", "-c", cmd2], capture_output=True,
                                text=True, timeout=20)
            if r2.returncode == 0 and r2.stdout.strip():
                for block in r2.stdout.split("===FILE===")[1:]:
                    lines = block.strip().splitlines()
                    if not lines:
                        continue
                    try:
                        h = json.loads(lines[-1])
                        bots[f"trend:{h.get('symbol', 'unknown')}"] = h
                    except Exception:
                        continue
        except Exception:
            pass
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
            "denaro-node-marcodg1-xrp", "denaro-node-trend", "denaro-node-paper",
            "denaro-health-marcodg1", "denaro-aggregator-marcodg1",
            "zabbix-agent",
        ],
    },
    "nuvola": {
        "ssh": ["sergio@87.106.3.15", "-p", "22"],
        "units": ["denaro-node-nuvola-trade", "denaro-health-nuvola",
                  "zabbix-agent", "zabbix-tunnel"],
    },
    "mc2": {
        "ssh": ["sergio@127.0.0.1", "-p", "2222"],  # tunnel inverso
        "units": ["denaro-node-mc2", "denaro-feeder-mc2", "denaro-health-mc2",
                  "denaro-aggregator-mc2", "denaro-dashboard-mc2",
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

    # 1) Bot health files (I 4 BOT REALI ATTIVI)
    bots = {}
    live_bots_map = {
        "trend-live:SOL/EUR": HEALTH_DIR / "trend_sol_kraken.json",
        "trend-live:XRP/EUR": HEALTH_DIR / "trend_xrp_kraken.json",
        "mc2:okx:BTC/EUR": Path("/home/sergio/denaro/health/btc_mc2.json"),
        "mc2:okx:ETH/EUR": Path("/home/sergio/denaro/health/eth_mc2.json"),
        "mc2:okx:SOL/EUR": Path("/home/sergio/denaro/health/sol_mc2.json"),
        "mc2:okx:XRP/EUR": Path("/home/sergio/denaro/health/xrp_mc2.json"),
        "mc2:okx:DOGE/EUR": Path("/home/sergio/denaro/health/doge_mc2.json"),
    }
    for bot_id, p in live_bots_map.items():
        if p.exists():
            try:
                bots[bot_id] = json.loads(p.read_text())
            except Exception:
                bots[bot_id] = {"status": "error"}
        else:
            # Prova a leggere via SSH se il path e' su mc2 remoto
            if "mc2:" in bot_id:
                try:
                    r = subprocess.run(["ssh", "-p", "2222", "-o", "BatchMode=yes", "-o", "ConnectTimeout=4",
                                        "sergio@127.0.0.1", f"cat {p}"],
                                       capture_output=True, text=True, timeout=5)
                    if r.returncode == 0 and r.stdout.strip():
                        bots[bot_id] = json.loads(r.stdout.strip())
                    else:
                        bots[bot_id] = {"status": "no_file"}
                except Exception:
                    bots[bot_id] = {"status": "no_file"}
            else:
                bots[bot_id] = {"status": "no_file"}
    data["bots"] = bots

    # 2) Saldi REALI: OKX main + subaccount (locale e via SSH) + Kraken
    balances = {}

    # 2a) conti con .env locale su MARCODG1
    for label, (path, prefix) in ENV_FILES.items():
        env = load_env(path)
        acct = {k[len(prefix):]: v for k, v in env.items() if k.startswith(prefix)} if prefix else env
        if acct.get("OKX_API_KEY"):
            balances[label] = fetch_okx_balance(acct)
        else:
            balances[label] = {"ok": False, "error": "no key"}

    # 2b) sub-account con chiavi IP-bound: letti sul nodo di origine via SSH
    for label, (ssh_target, ssh_port, remote_env, remote_py) in REMOTE_ENV_SOURCES.items():
        res = fetch_remote_okx_balance(ssh_target, ssh_port, remote_env, remote_py)
        balances[label] = res if res else {"ok": False, "error": "ssh/ccxt fallito"}

    # 2c) Kraken: una sola voce per conto reale (dedup per fingerprint chiave)
    for path, key_attr, sec_attr in KRAKEN_ENV_FILES:
        e = load_env(path)
        k, s = e.get(key_attr), e.get(sec_attr)
        if not k or not s:
            continue
        r = fetch_kraken_balance({key_attr: k, sec_attr: s}, key_attr, sec_attr)
        if r.get("ok"):
            if not any(v.get("acct") and v.get("acct") == r.get("acct")
                       for kk, v in balances.items() if kk.lower().startswith("kraken")):
                balances["kraken"] = r
            break

    data["balances"] = balances

    # Capitale reale valorizzato dai saldi (account deduplicati)
    real_total, equity_detail, unpriced = balance_eur(balances)
    data["equity_breakdown"] = equity_detail
    data["equity_unpriced"] = unpriced

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

    # 7) CAPITALE TOTALE REALE = somma dei SALDI reali (account deduplicati).
    #    Prima esistevano due costanti hardcoded (24.0 e 25.47): con 75 EUR
    #    investiti la dashboard mostrava sempre 24 EUR.
    okx_eq = sum(b.get("total_equity", 0) for k, b in node_bots.items()
                 if "mc2:okx" in k and b.get("status") == "running"
                 and not b.get("stale"))
    kraken_eq = sum(b.get("total_equity", 0) for k, b in node_bots.items()
                    if "trend-live" in k and b.get("status") == "running"
                    and not b.get("stale"))
    data["bot_equity"] = round(okx_eq, 2)
    data["kraken_equity"] = round(kraken_eq, 2)
    if real_total > 0:
        data["total_equity"] = round(real_total, 2)
        data["equity_source"] = "balances"
    else:
        data["total_equity"] = round(okx_eq + kraken_eq, 2)
        data["equity_source"] = "bots"

    # ONESTA' DELLA TELEMETRIA (2026-09-16). Due difetti osservati dal vivo:
    #  1) il PnL dei bot PAPER (equity virtuali, capitali da 100-300 EUR) veniva
    #     sommato al PnL reale: la dashboard mostrava +26,44 EUR mentre il
    #     risultato realizzato era circa -0,30 EUR;
    #  2) i bot con health vecchio (nodi spenti) contavano come "running".
    # Ora: "running" = vivo, non stale e recente; paper e live separati.
    live_running = [b for b in node_bots.values()
                    if b.get("status") == "running" and not b.get("stale")
                    and b.get("mode") == "live"]
    paper_running = [b for b in node_bots.values()
                     if b.get("status") == "running" and not b.get("stale")
                     and b.get("mode") != "live"]
    node_running = live_running
    data["node_total_pnl"] = round(sum(b.get("pnl", 0) for b in live_running), 4)
    data["node_paper_pnl"] = round(sum(b.get("pnl", 0) for b in paper_running), 4)
    data["node_live_bots"] = len(live_running)
    data["node_paper_bots"] = len(paper_running)
    data["node_stale_bots"] = sorted(k for k, b in node_bots.items()
                                     if isinstance(b, dict) and b.get("stale"))
    data["node_total_trades"] = sum(b.get("trades", 0) for b in live_running)
    wins = sum(b.get("wins", 0) for b in live_running)
    losses = sum(b.get("losses", 0) for b in live_running)
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
