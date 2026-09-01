#!/bin/bash
# Funding per l'istanza TREND live: master -> trendsub1 (da eseguire SOLO
# quando il sub-account esiste e la validazione paper ha confermato).
# NB: il master deve avere il permesso "Sub-Account" e "Transfer".
# Uso: bash _fund_trend.sh <importo_EUR>
set -e
AMOUNT="${1:-15}"
cd /home/marco/denaro_node_app
/home/marco/denaro/venv/bin/python - <<PY
import os, sys
from pathlib import Path
env = {}
for line in Path(".env").read_text().splitlines():
    line = line.strip()
    if line and "=" in line and not line.startswith("#"):
        k, _, v = line.partition("=")
        env[k.strip()] = v.strip().strip('"').strip("'")
import ccxt
# la master key con Transfer: cercala tra i prefissi comuni
key = env.get("MASTER_OKX_API_KEY") or env.get("OKX_API_KEY")
sec = env.get("MASTER_OKX_API_SECRET") or env.get("OKX_API_SECRET")
ph = env.get("MASTER_OKX_PASSPHRASE") or env.get("OKX_PASSPHRASE")
if not (key and sec and ph):
    print("ERRORE: chiave master non trovata nel .env — aggiungi MASTER_OKX_API_*")
    sys.exit(1)
ex = ccxt.okx({"apiKey": key, "secret": sec, "password": ph,
               "hostname": "eea.okx.com", "enableRateLimit": True})
amount = float("$AMOUNT")
r = ex.transfer("EUR", amount, "master", "trendsub1")
print("TRANSFER:", r)
PY
