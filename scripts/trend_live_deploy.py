#!/usr/bin/env python3
"""Deploy LIVE istanza TREND su Kraken (sub-account).

Fasi (dopo che l'utente ha: (1) abilitato il permesso "Subaccounts" sulla
chiave master, (2) fornito l'email per il sub-account, (3) creato l'API key
del sub-account e messa nel .env come TRENDSUB_KRAKEN_API_KEY/SECRET):
  a) Crea il sub-account "trendsub" via API (CreateSubaccount);
  b) Trasferisce EUR dal master al sub (AccountTransfer);
  c) Deploya config/node_trend_live_kraken.yaml + unit systemd + avvio;
  d) Verifica ordini/health.

Uso: python scripts/trend_live_deploy.py <email> [importo_eur]
ESEMPIO: python scripts/trend_live_deploy.py sergio@example.com 40
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def _load_env(path: Path) -> dict:
    env = {}
    try:
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip().strip('"').strip("'")
    except Exception:
        pass
    return env


def k_private(ex, method: str, params: dict) -> dict:
    """Chiamata privata Kraken con firma HMAC via ccxt."""
    path = "/0/private/" + method
    req = ex.sign(path, "private", "POST", params,
                  {"Content-Type": "application/x-www-form-urlencoded"}, None)
    body = req.get("body", {})
    data = body.encode() if isinstance(body, str) else urllib.parse.urlencode(body).encode()
    r = urllib.request.Request("https://api.kraken.com" + path, data=data,
                               headers=req["headers"])
    try:
        with urllib.request.urlopen(r, timeout=25) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {"error": [f"HTTP {e.code}"], "body": e.read().decode()[:200]}


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    email = sys.argv[1]
    amount = float(sys.argv[2]) if len(sys.argv) > 2 else 40.0

    import ccxt
    env = _load_env(Path("/home/marco/denaro_node_app/.env"))
    key = env.get("KRAKEN_API_KEY") or env.get("KRAKEN_KEY")
    sec = env.get("KRAKEN_API_SECRET") or env.get("KRAKEN_SECRET")
    if not (key and sec):
        print("ERRORE: chiave master Kraken non trovata nel .env")
        return 1
    ex = ccxt.kraken({"apiKey": key, "secret": sec, "enableRateLimit": True})

    # a) crea il sub-account
    r = k_private(ex, "CreateSubaccount", {"username": "trendsub", "email": email})
    print("CreateSubaccount:", r)
    if r.get("error"):
        return 1

    # b) trasferimento EUR master -> trendsub
    t = k_private(ex, "AccountTransfer",
                  {"asset": "EUR", "amount": str(amount),
                   "from": "master", "to": "trendsub"})
    print("AccountTransfer:", t)
    if t.get("error"):
        return 1

    # c) deploy config + unit
    cfg = Path("/home/marco/denaro_node_app/config/node_trend_live_kraken.yaml")
    if not cfg.exists():
        print("ERRORE: config/node_trend_live_kraken.yaml mancante")
        return 1
    unit = """[Unit]
Description=Denaro Node — istanza TREND LIVE (momentum su sub Kraken)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=marco
ExecStart=/home/marco/denaro/venv/bin/python -m denaro.denaro_node --config config/node_trend_live_kraken.yaml
WorkingDirectory=/home/marco/denaro_node_app
EnvironmentFile=/home/marco/denaro_node_app/.env
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""
    with open("/tmp/denaro-node-trend-live.service", "w") as f:
        f.write(unit)
    for cmd in (["sudo", "-n", "tee", "/etc/systemd/system/denaro-node-trend-live.service"],
                ):
        pass
    subprocess.run(["sudo", "-n", "bash", "-c",
                    "tee /etc/systemd/system/denaro-node-trend-live.service >/dev/null < /tmp/denaro-node-trend-live.service"],
                   check=True)
    subprocess.run(["sudo", "-n", "systemctl", "daemon-reload"], check=True)
    subprocess.run(["sudo", "-n", "systemctl", "enable", "--now",
                    "denaro-node-trend-live"], check=True)
    print("unit denaro-node-trend-live avviata")
    return 0


if __name__ == "__main__":
    sys.exit(main())
