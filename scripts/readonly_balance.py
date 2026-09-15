#!/usr/bin/env python3
"""readonly_balance.py - saldi e permessi di una chiave OKX (SOLA LETTURA).

Non stampa mai i valori delle chiavi: solo nome variabile, fingerprint e permessi.
Uso: python3 readonly_balance.py [--env ~/atlas/.env] [--fingerprint]
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


def load_env(path: str) -> dict:
    out: dict = {}
    p = Path(path).expanduser()
    if p.exists():
        for line in p.read_text(errors="replace").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default="~/atlas/.env")
    ap.add_argument("--hostname", default="eea.okx.com")
    a = ap.parse_args()
    env = load_env(a.env)
    key = env.get("OKX_API_KEY", "")
    print("file:", a.env)
    print("OKX_API_KEY: presente" if key else "OKX_API_KEY: MANCANTE",
          "| fingerprint:", hashlib.sha256(key.encode()).hexdigest()[:12] if key else "-")
    if not key:
        return 2
    try:
        import ccxt  # type: ignore
    except Exception as e:  # noqa: BLE001
        print("ccxt non disponibile:", e)
        return 3
    ex = ccxt.okx({"apiKey": key, "secret": env.get("OKX_API_SECRET", ""),
                   "password": env.get("OKX_PASSPHRASE", ""), "hostname": a.hostname,
                   "enableRateLimit": True})
    try:
        bal = ex.fetch_balance()
        tot = {k: v for k, v in (bal.get("total") or {}).items() if v and float(v) > 0}
        print("SALDO:", tot)
    except Exception as e:  # noqa: BLE001
        print("fetch_balance errore:", type(e).__name__, str(e)[:200])
    try:
        subs = ex.private_get_users_subaccount_list({})
        names = [s.get("subAcct") for s in (subs.get("data") or [])]
        print("SUBACCOUNT:", names)
        for s in (subs.get("data") or []):
            try:
                res = ex.private_get_asset_subaccount_balances({"subAcct": s.get("subAcct")})
                rows = res.get("data") or []
                print("   ", s.get("subAcct"), {r.get("ccy"): r.get("bal") for r in rows if float(r.get("bal") or 0) > 0})
            except Exception as e:  # noqa: BLE001
                print("   ", s.get("subAcct"), "errore:", type(e).__name__, str(e)[:120])
    except Exception as e:  # noqa: BLE001
        print("subaccount errore:", type(e).__name__, str(e)[:160])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
