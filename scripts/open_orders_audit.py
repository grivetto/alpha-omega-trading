#!/usr/bin/env python3
"""open_orders_audit.py - ordini APERTI reali sugli exchange vs quelli tracciati dai bot (SOLA LETTURA).

Serve a trovare ordini "orfani": aperti sull'exchange ma non piu' gestiti da nessun bot attivo.
Nessun ordine viene creato, modificato o cancellato.

Uso: python3 open_orders_audit.py [--json]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ENV_CANDIDATES = [
    ("okx-main-legacy", "/home/sergio/atlas-legacy-20260901/.env"),
    ("okx-mc2", "/home/sergio/alpha-omega-trading/.env"),
    ("kraken-atlas", "/home/sergio/atlas/.env"),
]
STATE_DIRS = [
    Path("/home/sergio/alpha-omega-trading/node_data"),
    Path("/home/marco/denaro/node_data"),
]
SYMBOLS_OKX = ["DOGE/EUR", "SOL/EUR"]
SYMBOLS_KRAKEN = ["SOL/EUR", "XRP/EUR", "ADA/EUR"]


def load_env(path: str) -> dict:
    out: dict = {}
    p = Path(path)
    if p.exists():
        for line in p.read_text(errors="replace").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def open_orders_okx(env: dict, hostname: str = "eea.okx.com") -> list[dict]:
    import ccxt  # type: ignore
    ex = ccxt.okx({"apiKey": env.get("OKX_API_KEY", ""), "secret": env.get("OKX_API_SECRET", ""),
                   "password": env.get("OKX_PASSPHRASE", ""), "hostname": hostname, "enableRateLimit": True})
    out = []
    for sym in SYMBOLS_OKX:
        try:
            for o in ex.fetch_open_orders(sym):
                out.append({"exchange": "okx", "symbol": sym, "id": o.get("id"), "side": o.get("side"),
                            "price": o.get("price"), "amount": o.get("amount"),
                            "filled": o.get("filled"), "status": o.get("status")})
        except Exception as e:  # noqa: BLE001
            out.append({"exchange": "okx", "symbol": sym, "error": f"{type(e).__name__}: {str(e)[:120]}"})
    return out


def open_orders_kraken(env: dict) -> list[dict]:
    import ccxt  # type: ignore
    ex = ccxt.kraken({"apiKey": env.get("KRAKEN_API_KEY", ""), "secret": env.get("KRAKEN_API_SECRET", ""),
                      "enableRateLimit": True})
    out = []
    try:
        for o in ex.fetch_open_orders():
            out.append({"exchange": "kraken", "symbol": o.get("symbol"), "id": o.get("id"),
                        "side": o.get("side"), "price": o.get("price"), "amount": o.get("amount"),
                        "filled": o.get("filled"), "status": o.get("status")})
    except Exception as e:  # noqa: BLE001
        out.append({"exchange": "kraken", "symbol": "*", "error": f"{type(e).__name__}: {str(e)[:150]}"})
    return out


def bot_tracked() -> dict:
    """Ordini aperti tracciati dai bot (open_buys/open_sells negli state)."""
    tracked: dict = {}
    for d in STATE_DIRS:
        if not d.exists():
            continue
        for f in d.glob("*_state.json"):
            try:
                st = json.loads(f.read_text())
            except Exception:  # noqa: BLE001
                continue
            for kind in ("open_buys", "open_sells"):
                for oid, info in (st.get(kind) or {}).items():
                    tracked[str(oid)] = {"file": str(f), "kind": kind, "info": info}
    return tracked


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    report: dict = {"ordini_aperti": {}, "tracciati_dai_bot": bot_tracked()}

    for name, path in ENV_CANDIDATES:
        env = load_env(path)
        if not env:
            continue
        if name.startswith("okx"):
            rows = open_orders_okx(env)
        else:
            rows = open_orders_kraken(env)
        report["ordini_aperti"][name] = rows
        print(f"== {name} ({path}) ==")
        if not rows:
            print("  nessun ordine aperto")
        for r in rows:
            if r.get("error"):
                print(f"  errore: {r['error']}")
            else:
                print(f"  {r['exchange']} {r['symbol']} {r['side']} id={r['id']} "
                      f"price={r['price']} amount={r['amount']} filled={r['filled']}")

    print("\n== ORDINI APERTI TRACCIATI DAI BOT (state.json) ==")
    tr = report["tracciati_dai_bot"]
    if not tr:
        print("  nessuno")
    for oid, info in tr.items():
        print(f"  {oid} {info['kind']} da {Path(info['file']).name}: {json.dumps(info['info'], ensure_ascii=False)[:160]}")

    # orfani: aperti sull'exchange ma non presenti negli state dei bot
    opened_ids = {str(r.get("id")) for rows in report["ordini_aperti"].values() for r in rows if r.get("id")}
    orfani = sorted(opened_ids - set(tr.keys()))
    report["orfani"] = orfani
    print(f"\n== ORDINI ORFANI (aperti sull'exchange, non tracciati da nessun bot): {len(orfani)} ==")
    for oid in orfani:
        for rows in report["ordini_aperti"].values():
            for r in rows:
                if str(r.get("id")) == oid:
                    print(f"  {r['exchange']} {r['symbol']} {r['side']} id={oid} price={r['price']} amount={r['amount']}")
    if a.json:
        print(json.dumps(report, ensure_ascii=False, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
