#!/usr/bin/env python3
"""Probe OKX keys on live AND sandbox (demo) — 50119 often means demo keys."""
import sys
from pathlib import Path

import ccxt


def load_env() -> dict:
    env = {}
    p = Path.home() / "denaro" / ".env"
    if p.exists():
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def probe(label: str, sandbox: bool) -> None:
    key = env.get("OKX_API_KEY", "")
    secret = env.get("OKX_API_SECRET", "")
    passphrase = env.get("OKX_PASSPHRASE", "")
    try:
        ex = ccxt.okx({"apiKey": key, "secret": secret, "password": passphrase,
                       "enableRateLimit": True, "timeout": 15000, "sandbox": sandbox})
        ex.load_markets()
        bal = ex.fetch_balance()
        total = {k: round(v, 4) for k, v in bal.get("total", {}).items() if v}
        print(f"OKX {label}: AUTH OK balances={total}")
    except Exception as e:
        msg = str(e).replace("\n", " ")[:160]
        print(f"OKX {label}: FAIL {msg}")


env = load_env()
print("OKX key present:", bool(env.get("OKX_API_KEY")))
probe("LIVE", sandbox=False)
probe("SANDBOX", sandbox=True)
