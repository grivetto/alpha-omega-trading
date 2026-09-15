#!/usr/bin/env python3
"""okx_subaccounts.py - elenco sub-account e saldi OKX (SOLA LETTURA).

Usa la chiave del conto MAIN (che puo' elencare i sub-account) e stampa, per ogni sub-account,
i saldi reali. Nessun trasferimento, nessun ordine: solo endpoint di lettura.

Uso: python3 okx_subaccounts.py [--env ~/alpha-omega-trading/.env] [--hostname eea.okx.com]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_env(path: str) -> dict:
    out: dict = {}
    p = Path(path).expanduser()
    if not p.exists():
        return out
    for line in p.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default="~/alpha-omega-trading/.env")
    ap.add_argument("--hostname", default="eea.okx.com")
    a = ap.parse_args()
    env = load_env(a.env)
    missing = [k for k in ("OKX_API_KEY", "OKX_API_SECRET", "OKX_PASSPHRASE") if not env.get(k)]
    if missing:
        print("credenziali mancanti:", missing)
        return 2
    try:
        import ccxt  # type: ignore
    except Exception as e:  # noqa: BLE001
        print("ccxt non disponibile:", e)
        return 3

    ex = ccxt.okx({"apiKey": env["OKX_API_KEY"], "secret": env["OKX_API_SECRET"],
                   "password": env["OKX_PASSPHRASE"], "hostname": a.hostname, "enableRateLimit": True})

    print("== SUB-ACCOUNT (sola lettura) ==")
    subs: list[dict] = []
    for method, params in (("private_get_users_subaccount_list", {}),
                           ("privateGetUsersSubaccountList", {})):
        fn = getattr(ex, method, None)
        if fn is None:
            continue
        try:
            res = fn(params)
            subs = res.get("data") or [] if isinstance(res, dict) else []
            break
        except Exception as e:  # noqa: BLE001
            print(f"  {method}: errore {type(e).__name__}: {str(e)[:160]}")
    if not subs:
        print("  nessun sub-account restituito (o endpoint non disponibile su questa chiave)")
    for s in subs:
        name = s.get("subAcct") or s.get("label") or "?"
        print(f"  sub-account: {name} | enabled={s.get('enable')} | tipo={s.get('type')} | "
              f"creato={s.get('ts')}")

    print("\n== SALDI PER SUB-ACCOUNT ==")
    for s in subs:
        name = s.get("subAcct") or s.get("label") or "?"
        try:
            res = ex.private_get_asset_subaccount_balances({"subAcct": name})
            rows = (res.get("data") or []) if isinstance(res, dict) else []
            tot = {r.get("ccy"): r.get("bal") for r in rows if float(r.get("bal") or 0) > 0}
            print(f"  {name}: {json.dumps(tot, ensure_ascii=False)}")
        except Exception as e:  # noqa: BLE001
            print(f"  {name}: errore {type(e).__name__}: {str(e)[:160]}")

    print("\n== SALDO CONTO PRINCIPALE ==")
    try:
        bal = ex.fetch_balance()
        tot = {k: v for k, v in (bal.get("total") or {}).items() if v and v > 0}
        print("  total:", json.dumps(tot, ensure_ascii=False, default=str))
    except Exception as e:  # noqa: BLE001
        print("  errore:", type(e).__name__, str(e)[:200])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
