#!/usr/bin/env python3
"""Validate API keys on this machine — Kraken and OKX ONLY.

Reads KRAKEN_*/OKX_* variables from ~/denaro/.env (plus any extra env file
paths passed as argv), then performs a live ccxt check (balance + ticker).
Prints masked key ids and OK/FAIL per exchange. Exits non-zero on failure.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import ccxt

EXTRA_ENV_FILES = [a for a in sys.argv[1:] if a.startswith("/")]


def load_env_vars() -> dict:
    env: dict = {}
    candidates = [Path.home() / "denaro" / ".env"] + [Path(p) for p in EXTRA_ENV_FILES]
    for p in candidates:
        if p and p.exists():
            for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def mask(key: str) -> str:
    return f"{key[:6]}...{key[-4:]}" if key and len(key) > 12 else "(set?)"


def check_exchange(name: str, exchange_cls, cfg: dict, symbol: str) -> bool:
    ok = False
    try:
        ex = exchange_cls({"apiKey": cfg.get("apiKey", ""),
                           "secret": cfg.get("secret", ""),
                           "password": cfg.get("password", ""),
                           "enableRateLimit": True, "timeout": 15000})
        ex.load_markets()
        bal = ex.fetch_balance()
        total = bal.get("total", {})
        ticker = ex.fetch_ticker(symbol)
        price = float(ticker["last"]) if ticker.get("last") else 0.0
        print(f"  {name}: AUTH OK  api={mask(cfg.get('apiKey',''))} "
              f"price={symbol}={price:.6f} "
              f"balances={ {k: round(v, 4) for k, v in list(total.items())[:6] if v} }")
        ok = True
    except Exception as e:
        msg = str(e).replace("\n", " ")[:200]
        print(f"  {name}: AUTH FAIL  api={mask(cfg.get('apiKey',''))} error={msg}")
    return ok


def main() -> int:
    env = load_env_vars()
    results = []

    kraken_key = env.get("KRAKEN_API_KEY") or env.get("KRAKEN_API") or ""
    kraken_secret = env.get("KRAKEN_API_SECRET") or env.get("KRAKEN_SECRET") or ""
    if kraken_key and kraken_secret:
        print("== KRAKEN ==")
        results.append(("kraken", check_exchange(
            "kraken", ccxt.kraken,
            {"apiKey": kraken_key, "secret": kraken_secret},
            env.get("SYMBOL", "DOGE/EUR"))))
    else:
        print("== KRAKEN: no keys found in env ==")
        results.append(("kraken", False))

    okx_key = env.get("OKX_API_KEY") or ""
    okx_secret = env.get("OKX_API_SECRET") or ""
    okx_pass = env.get("OKX_PASSPHRASE") or env.get("OKX_PASSPHRASE_KEY") or ""
    if okx_key and okx_secret and okx_pass:
        print("== OKX ==")
        results.append(("okx", check_exchange(
            "okx", ccxt.okx,
            {"apiKey": okx_key, "secret": okx_secret, "password": okx_pass},
            "BTC/USDT")))
    else:
        print("== OKX: incomplete keys (need API_KEY+SECRET+PASSPHRASE) ==")
        results.append(("okx", False))

    bad = [n for n, ok in results if not ok]
    print(f"\nRESULT: {'ALL OK' if not bad else 'FAILED: ' + ','.join(bad)}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
