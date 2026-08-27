#!/usr/bin/env python3
"""CHECK ORDINI ACCIDENTALI — SOLO LETTURA.

Verifica se l'avvio accidentale di ATLAS (import run senza guardia, sandbox
false) ha piazzato ordini reali su Kraken/OKX tra le 18:2x e il kill.

Nessun ordine viene creato/cancellato. Stampa solo:
- open orders per exchange
- saldo totale per exchange (senza stampare chiavi)
- ticker BTC/EUR (conferma connettivita')
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ccxt  # noqa: E402


def _load_env(path: Path) -> dict:
    env = {}
    if path.exists():
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def check_exchange(name: str, ex: ccxt.Exchange) -> None:
    print(f"\n=== {name.upper()} ===")
    try:
        markets = ex.load_markets()
        print(f"markets: {len(markets)}")
    except Exception as e:
        print(f"load_markets FAILED: {e}")
        return
    try:
        orders = ex.fetch_open_orders()
        print(f"OPEN ORDERS: {len(orders)}")
        for o in orders:
            print(f"  {o['symbol']} {o['side']} {o['amount']} @ {o['price']} id={o['id']} ts={o.get('timestamp')}")
    except Exception as e:
        print(f"fetch_open_orders FAILED: {e}")
    try:
        # Fill avvenuti nelle ultime ~2h (finestra dell'incidente)
        since = ex.milliseconds() - 2 * 60 * 60 * 1000
        trades = ex.fetch_my_trades(since=since)
        print(f"TRADES (ultime 2h): {len(trades)}")
        for t in trades:
            print(f"  {t['symbol']} {t['side']} {t['amount']} @ {t['price']} fee={t.get('fee')} id={t['id']} ts={t.get('timestamp')}")
    except Exception as e:
        print(f"fetch_my_trades FAILED: {e}")
    try:
        bal = ex.fetch_balance()
        total = bal.get("total", {})
        non_zero = {k: v for k, v in total.items() if v and v > 1e-9}
        print(f"BALANCE (non-zero): {non_zero}")
    except Exception as e:
        print(f"fetch_balance FAILED: {e}")


def main() -> None:
    env = _load_env(Path(__file__).resolve().parent.parent / ".env")
    keys = {k: v for k, v in env.items() if "KEY" in k or "SECRET" in k or "PASSPHRASE" in k}
    print(f"chiavi caricate da .env: {sorted(keys.keys())}")

    # Kraken
    if env.get("KRAKEN_API_KEY"):
        ex = ccxt.kraken({"apiKey": env["KRAKEN_API_KEY"], "secret": env.get("KRAKEN_API_SECRET", "")})
        ex.enableRateLimit = True
        check_exchange("kraken", ex)
    else:
        print("\n=== KRAKEN: nessuna chiave ===")

    # OKX (EEA)
    if env.get("OKX_API_KEY"):
        ex = ccxt.okx({
            "apiKey": env["OKX_API_KEY"],
            "secret": env.get("OKX_API_SECRET", ""),
            "password": env.get("OKX_PASSPHRASE", ""),
        })
        if env.get("OKX_EEA", "false").lower() in ("1", "true"):
            # Override pulito dell'endpoint EEA (OKX Europe)
            ex.urls["api"]["public"] = "https://eea.okx.com/api/v5"
            ex.urls["api"]["private"] = "https://eea.okx.com/api/v5"
        ex.enableRateLimit = True
        check_exchange("okx", ex)
    else:
        print("\n=== OKX: nessuna chiave ===")


if __name__ == "__main__":
    main()
