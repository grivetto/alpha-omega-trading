#!/usr/bin/env python3
"""okx_recon.py - riconciliazione SOLA LETTURA tra il ledger locale dei bot e l'exchange OKX.

Cosa fa (nessun ordine, nessun trasferimento, solo endpoint di lettura):
  1) legge i trade registrati dai bot: /home/sergio/alpha-omega-trading/node_data/okx_default_*_trades.jsonl
  2) per ogni ordine "filled" chiede a OKX il dettaglio (fetch_order) e raccoglie fee e stato reali
  3) chiede i saldi del conto (fetch_balance) per dare l'equity reale
  4) confronta il PnL dichiarato dai bot (state.json) con i fill e le fee reali dell'exchange

Credenziali: lette da file .env (nome variabile stampato, MAI il valore).
Uso:
  python3 okx_recon.py --env ~/alpha-omega-trading/.env [--no-network]
  python3 okx_recon.py --env ~/atlas/.env --subaccount
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

TRADES_GLOB = "/home/sergio/alpha-omega-trading/node_data/okx_default_{sym}_trades.jsonl"
STATE_GLOB = "/home/sergio/alpha-omega-trading/node_data/okx_default_{sym}_state.json"
PREFIX = "/home/sergio/alpha-omega-trading/node_data/okx_default_"
SYMBOLS = ["DOGE_EUR", "SOL_EUR"]


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


def read_ledger(sym: str) -> list[dict]:
    p = Path(PREFIX + sym + "_trades.jsonl")
    rows = []
    if not p.exists():
        return rows
    for line in p.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:  # noqa: BLE001
            rows.append({"event": "parse_error", "raw": line[:120]})
    return rows


def read_state(sym: str) -> dict:
    p = Path(PREFIX + sym + "_state.json")
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except Exception:  # noqa: BLE001
        return {}


def fmt_ts(ts: float | None) -> str:
    if not ts:
        return "n/d"
    return datetime.fromtimestamp(float(ts), timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default="~/alpha-omega-trading/.env")
    ap.add_argument("--hostname", default="eea.okx.com")
    ap.add_argument("--no-network", action="store_true")
    ap.add_argument("--max-orders", type=int, default=40)
    a = ap.parse_args()

    env = load_env(a.env)
    need = ["OKX_API_KEY", "OKX_API_SECRET", "OKX_PASSPHRASE"]
    present = {k: (k in env and bool(env[k])) for k in need}
    print("== CREDENZIALI ==")
    print("  file:", a.env)
    for k, ok in present.items():
        val = env.get(k, "")
        print(f"  {k}: {'presente' if ok else 'MANCANTE'}" + (f" ({val[:4]}…{val[-2:]})" if ok and len(val) > 8 else ""))

    print("\n== LEDGER LOCALE ==")
    all_orders: list[dict] = []
    for sym in SYMBOLS:
        rows = read_ledger(sym)
        st = read_state(sym)
        c = Counter(r.get("event") for r in rows)
        print(f"  {sym}: {len(rows)} eventi {dict(c)}")
        print(f"     state: pnl dichiarato={st.get('total_pnl')} trades={st.get('total_trades')} "
              f"wins={st.get('wins')} losses={st.get('losses')} peak_eq={st.get('peak_equity')} "
              f"max_dd={st.get('max_dd')}")
        for r in rows:
            if r.get("event") in ("sell_filled", "buy_filled") and r.get("order_id"):
                all_orders.append({"symbol": sym.replace("_", "/"), **r})

    print(f"\n  ordini 'filled' con order_id nel ledger: {len(all_orders)}")
    for o in all_orders[:10]:
        print(f"    {o['symbol']} {o['event']} id={o['order_id']} amount={o.get('amount')} "
              f"price={o.get('price')} ts={fmt_ts(o.get('ts'))}")

    if a.no_network:
        print("\n(--no-network: nessuna chiamata all'exchange)")
        return 0
    if not all(present.values()):
        print("\nCredenziali incomplete: impossibile interrogare OKX. Nulla e' stato eseguito.")
        return 2
    try:
        import ccxt  # type: ignore
    except Exception as e:  # noqa: BLE001
        print("\nccxt non disponibile in questo Python:", e)
        return 3

    ex = ccxt.okx({
        "apiKey": env["OKX_API_KEY"], "secret": env["OKX_API_SECRET"],
        "password": env["OKX_PASSPHRASE"], "hostname": a.hostname, "enableRateLimit": True,
    })
    print("\n== SALDI REALI (OKX, sola lettura) ==")
    try:
        bal = ex.fetch_balance()
        tot = {k: v for k, v in (bal.get("total") or {}).items() if v and v > 0}
        print("  total:", json.dumps(tot, ensure_ascii=False, default=str)[:600])
        free = {k: v for k, v in (bal.get("free") or {}).items() if v and v > 0}
        print("  free :", json.dumps(free, ensure_ascii=False, default=str)[:400])
    except Exception as e:  # noqa: BLE001
        print("  errore fetch_balance:", type(e).__name__, str(e)[:300])

    print("\n== DETTAGLIO ORDINI FILLED PRESSO L'EXCHANGE ==")
    fee_total = 0.0
    checked = 0
    for o in all_orders[: a.max_orders]:
        try:
            od = ex.fetch_order(o["order_id"], o["symbol"])
            checked += 1
            fee = od.get("fee") or {}
            cost = fee.get("cost")
            if isinstance(cost, (int, float)):
                fee_total += float(cost)
            print(f"  {o['symbol']} id={o['order_id']} status={od.get('status')} "
                  f"filled={od.get('filled')} avg={od.get('average')} fee={cost} "
                  f"({(fee.get('currency') if isinstance(fee, dict) else '')})")
        except Exception as e:  # noqa: BLE001
            print(f"  {o['symbol']} id={o['order_id']}: errore {type(e).__name__}: {str(e)[:160]}")

    print(f"\n  ordini verificati: {checked} | fee totali lette: {fee_total}")

    print("\n== CONFRONTO ==")
    pnl_declared = sum((read_state(s) or {}).get("total_pnl") or 0 for s in SYMBOLS)
    trades_declared = sum((read_state(s) or {}).get("total_trades") or 0 for s in SYMBOLS)
    print(f"  PnL dichiarato dai bot: {round(pnl_declared, 6)} su {trades_declared} trade chiusi")
    print(f"  fee reali lette sull'exchange (sugli ordini verificati): {round(fee_total, 6)}")
    print(f"  PnL al netto delle fee lette: {round(pnl_declared - fee_total, 6)}")
    print("  Nota: il confronto e' completo solo se tutti i fill del ledger sono presenti "
          "nell'order history dell'exchange.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
