#!/usr/bin/env python3
"""kraken_audit.py - saldi e ordini aperti Kraken (SOLA LETTURA).

Verifica in particolare se esistono ordini di vendita aperti "orfani" (bot disabilitato, ordini vivi).

Uso: python3 kraken_audit.py [--env ~/denaro_node_app/.env] [--json]
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
    ap.add_argument("--env", default="~/denaro_node_app/.env")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    env = load_env(a.env)
    key = env.get("KRAKEN_API_KEY", "")
    secret = env.get("KRAKEN_API_SECRET") or env.get("KRAKEN_SECRET") or ""
    print("file:", a.env, "| KRAKEN_API_KEY:", "presente" if key else "MANCANTE",
          "| KRAKEN_API_SECRET:", "presente" if secret else "MANCANTE")
    if not key or not secret:
        return 2
    import ccxt  # type: ignore
    ex = ccxt.kraken({"apiKey": key, "secret": secret, "enableRateLimit": True})
    out: dict = {}
    try:
        bal = ex.fetch_balance()
        out["total"] = {k: v for k, v in (bal.get("total") or {}).items() if v and float(v) > 0}
        out["free"] = {k: v for k, v in (bal.get("free") or {}).items() if v and float(v) > 0}
        print("TOTAL:", json.dumps(out["total"], ensure_ascii=False))
        print("FREE :", json.dumps(out["free"], ensure_ascii=False))
        locked = {k: round(float(out["total"].get(k, 0)) - float(out["free"].get(k, 0)), 10)
                  for k in out["total"] if float(out["total"].get(k, 0)) - float(out["free"].get(k, 0)) > 0}
        out["bloccato_in_ordini"] = locked
        print("BLOCCATO in ordini aperti:", json.dumps(locked, ensure_ascii=False))
    except Exception as e:  # noqa: BLE001
        print("fetch_balance errore:", type(e).__name__, str(e)[:200])
    try:
        oo = ex.fetch_open_orders()
        out["ordini_aperti"] = [{"symbol": o.get("symbol"), "id": o.get("id"), "side": o.get("side"),
                                 "price": o.get("price"), "amount": o.get("amount"),
                                 "filled": o.get("filled"), "status": o.get("status")} for o in oo]
        print(f"ORDINI APERTI: {len(oo)}")
        for o in out["ordini_aperti"]:
            print("  ", json.dumps(o, ensure_ascii=False))
    except Exception as e:  # noqa: BLE001
        print("fetch_open_orders errore:", type(e).__name__, str(e)[:200])
    try:
        t = ex.fetch_ticker("XRP/EUR")
        out["xrp_eur"] = t.get("last")
        print("XRP/EUR ultimo:", t.get("last"))
    except Exception as e:  # noqa: BLE001
        print("ticker errore:", type(e).__name__, str(e)[:160])
    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
