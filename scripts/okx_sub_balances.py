#!/usr/bin/env python3
"""okx_sub_balances.py - saldi per sub-account OKX con la chiave del conto MAIN (SOLA LETTURA).

Uso: python3 okx_sub_balances.py [--env ~/atlas-legacy-20260901/.env] [--json]
"""
from __future__ import annotations

import argparse
import json
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
    ap.add_argument("--env", default="~/atlas-legacy-20260901/.env")
    ap.add_argument("--hostname", default="eea.okx.com")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    env = load_env(a.env)
    import ccxt  # type: ignore
    ex = ccxt.okx({"apiKey": env.get("OKX_API_KEY", ""), "secret": env.get("OKX_API_SECRET", ""),
                   "password": env.get("OKX_PASSPHRASE", ""), "hostname": a.hostname,
                   "enableRateLimit": True})
    subs = []
    try:
        subs = (ex.private_get_users_subaccount_list({}) or {}).get("data") or []
    except Exception as e:  # noqa: BLE001
        print("errore lista sub-account:", type(e).__name__, str(e)[:160])
    result = {}
    for s in subs:
        name = s.get("subAcct")
        try:
            res = ex.private_get_asset_subaccount_balances({"subAcct": name})
            rows = res.get("data") or []
            tot = {r.get("ccy"): float(r.get("bal") or 0) for r in rows if float(r.get("bal") or 0) > 0}
            result[name] = tot
            print(f"  {name:12s} -> {json.dumps(tot, ensure_ascii=False)}")
        except Exception as e:  # noqa: BLE001
            result[name] = {"errore": f"{type(e).__name__}: {str(e)[:120]}"}
            print(f"  {name:12s} -> errore {type(e).__name__}: {str(e)[:120]}")
    try:
        bal = ex.fetch_balance()
        main = {k: v for k, v in (bal.get("total") or {}).items() if v and float(v) > 0}
        result["_main"] = main
        print("  MAIN        ->", json.dumps(main, ensure_ascii=False))
    except Exception as e:  # noqa: BLE001
        print("  MAIN -> errore:", type(e).__name__, str(e)[:160])
    if a.json:
        print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
