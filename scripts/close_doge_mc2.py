#!/usr/bin/env python3
"""Chiusura posizione DOGE su OKX sub-account mc2sub1 (GO utente: 3 si).

--dry-run (default): mostra saldo e ordini aperti, NON esegue nulla.
--close: cancella ordini aperti DOGE/EUR e market-sell tutto il DOGE.

MAI stampare chiavi API — solo nomi variabili e saldi.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ccxt  # noqa: E402


def load_env(path: Path) -> dict:
    env = {}
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--close", action="store_true", help="esegue la chiusura (default: dry-run)")
    args = ap.parse_args()

    env = load_env(Path("/home/sergio/denaro_node_app/.env"))
    if not env.get("OKX_API_KEY"):
        print("ERRORE: OKX_API_KEY assente da /home/sergio/denaro_node_app/.env")
        sys.exit(1)

    ex = ccxt.okx({
        "apiKey": env["OKX_API_KEY"],
        "secret": env.get("OKX_API_SECRET", ""),
        "password": env.get("OKX_PASSPHRASE", ""),
    })
    if env.get("OKX_EEA", "false").lower() in ("1", "true"):
        ex.urls["api"]["public"] = "https://eea.okx.com/api/v5"
        ex.urls["api"]["private"] = "https://eea.okx.com/api/v5"
    ex.enableRateLimit = True

    # OKX v5: il parametro per il sub-account e' "subAcct" (non "subAccount")
    params = {"subAcct": "mc2sub1"}

    # 1) Saldo sub-account (read-only)
    doge = 0.0
    try:
        bal = ex.fetch_balance(params=params)
        total = dict(bal.get("total", {}) or {})
        non_zero = {k: v for k, v in total.items() if v and float(v) > 1e-9}
        print(f"BALANCE mc2sub1 (non-zero): {non_zero}")
        doge = float(non_zero.get("DOGE", 0) or 0)
        if doge <= 0 and not non_zero:
            print("NESSUN SALDO su mc2sub1 — nulla da chiudere")
            sys.exit(0)
    except Exception as e:
        print(f"fetch_balance mc2sub1 FAILED: {type(e).__name__}: {e}")
        print("(la chiave principale potrebbe non avere permessi sub-account: chiusura manuale richiesta)")
        sys.exit(2)

    # 2) Ordini aperti DOGE/EUR (read-only)
    try:
        orders = ex.fetch_open_orders("DOGE/EUR", params=params)
        print(f"OPEN ORDERS DOGE/EUR: {len(orders)}")
        for o in orders:
            print(f"  {o['side']} {o['amount']} @ {o['price']} id={o['id']}")
    except Exception as e:
        print(f"fetch_open_orders FAILED: {e}")
        orders = []

    if not args.close:
        print("\nDRY-RUN: nessuna azione eseguita. Rilanciare con --close per chiudere.")
        sys.exit(0)

    # 3) CLOSE: cancella ordini aperti, poi market-sell
    if orders:
        try:
            ex.cancel_all_orders("DOGE/EUR", params=params)
            print(f"CANCELLATI {len(orders)} ordini aperti")
        except Exception as e:
            print(f"cancel_all_orders FAILED: {type(e).__name__}: {e}")

    if doge > 0:
        try:
            ticker = ex.fetch_ticker("DOGE/EUR")
            px = ticker["last"]
            print(f"MARKET SELL {doge:.8f} DOGE @ ~{px}")
            order = ex.create_order("DOGE/EUR", "market", "sell", doge, params=params)
            print(f"ORDINE: id={order.get('id')} status={order.get('status')}")
        except Exception as e:
            print(f"create_order FAILED: {type(e).__name__}: {e}")
            sys.exit(3)

    # 4) Verifica finale (read-only)
    try:
        bal2 = ex.fetch_balance(params=params)
        total2 = dict(bal2.get("total", {}) or {})
        final = {k: round(float(v), 8) for k, v in total2.items() if v and float(v) > 1e-9}
        print(f"BALANCE FINALE mc2sub1: {final}")
    except Exception as e:
        print(f"verifica finale FAILED: {e}")


if __name__ == "__main__":
    main()
