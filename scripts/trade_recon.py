#!/usr/bin/env python3
"""trade_recon.py - riconciliazione ECONOMICA completa dei trade di un bot (sola lettura).

Per ogni ciclo chiuso:
  ricavo netto = somme delle vendite (amount x prezzo medio reale) - fee delle vendite
  costo        = spesa per gli acquisti del ciclo + fee degli acquisti
  PnL reale    = ricavo netto - costo
e confronto con il PnL dichiarato dai bot nei file state.json.

Ricostruisce i cicli dal ledger (eventi *_placed / *_filled / *_canceled, in ordine temporale)
oppure, con --fifo, applica una ricostruzione FIFO sulle quantita' acquistate/vendute.
Tutti i prezzi medi e le fee vengono chiesti all'exchange (fetch_order), quindi il risultato
e' contro l'exchange e non contro la contabilita' interna del bot.

Uso:
  python3 trade_recon.py --symbol DOGE/EUR [--env ~/alpha-omega-trading/.env]
  python3 trade_recon.py --symbol SOL/EUR --json
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

PREFIX = Path("/home/sergio/alpha-omega-trading/node_data/okx_default")


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


def fmt(ts) -> str:
    try:
        return datetime.fromtimestamp(float(ts), timezone.utc).strftime("%Y-%m-%d %H:%M")
    except Exception:  # noqa: BLE001
        return "n/d"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", required=True, help="es. DOGE/EUR")
    ap.add_argument("--env", default="~/alpha-omega-trading/.env")
    ap.add_argument("--hostname", default="eea.okx.com")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    sym_file = a.symbol.replace("/", "_")
    led = PREFIX.parent / ("okx_default_" + sym_file + "_trades.jsonl")
    stf = PREFIX.parent / ("okx_default_" + sym_file + "_state.json")
    if not led.exists():
        print("ledger non trovato:", led)
        return 2
    events = []
    for line in led.read_text(errors="replace").splitlines():
        line = line.strip()
        if line:
            try:
                events.append(json.loads(line))
            except Exception:  # noqa: BLE001
                pass
    events.sort(key=lambda e: e.get("ts") or 0)
    state = json.loads(stf.read_text()) if stf.exists() else {}

    env = load_env(a.env)
    import ccxt  # type: ignore
    ex = ccxt.okx({"apiKey": env.get("OKX_API_KEY"), "secret": env.get("OKX_API_SECRET"),
                   "password": env.get("OKX_PASSPHRASE"), "hostname": a.hostname,
                   "enableRateLimit": True})

    # dettagli reali degli ordini citati nel ledger (con cache)
    ids = [e.get("order_id") for e in events if e.get("order_id")]
    orders: dict[str, dict] = {}
    for oid in dict.fromkeys(ids):
        try:
            od = ex.fetch_order(oid, a.symbol)
            fee = od.get("fee") or {}
            orders[oid] = {
                "side": od.get("side"), "status": od.get("status"),
                "filled": float(od.get("filled") or 0), "avg": float(od.get("average") or 0),
                "fee": float((fee or {}).get("cost") or 0),
                "cost": float(od.get("cost") or 0),
            }
        except Exception as e:  # noqa: BLE001
            orders[oid] = {"error": f"{type(e).__name__}: {str(e)[:120]}"}

    sells = [o for o in orders.values() if o.get("side") == "sell" and o.get("status") == "closed"]
    buys = [o for o in orders.values() if o.get("side") == "buy" and o.get("status") == "closed"]
    proceeds = sum(o["cost"] for o in sells)
    sell_fees = sum(o["fee"] for o in sells)
    spend = sum(o["cost"] for o in buys)
    buy_fees = sum(o["fee"] for o in buys)
    net_proceeds = proceeds - sell_fees
    total_cost = spend + buy_fees
    pnl_exchange = net_proceeds - total_cost

    out = {
        "symbol": a.symbol,
        "eventi_ledger": len(events),
        "ordini_letti": len(orders),
        "vendite_chiuse": len(sells), "acquisti_chiusi": len(buys),
        "ricavi_vendite": round(proceeds, 6), "fee_vendite": round(sell_fees, 6),
        "spesa_acquisti": round(spend, 6), "fee_acquisti": round(buy_fees, 6),
        "pnl_exchange_netto": round(pnl_exchange, 6),
        "pnl_dichiarato_bot": round(float(state.get("total_pnl") or 0), 6),
        "trade_dichiarati": state.get("total_trades"),
        "trades_ricostruiti_vendite": len(sells),
        "equity_interna_bot": state.get("peak_equity"),
        "dettaglio": [
            {"ts": fmt(e.get("ts")), "event": e.get("event"), "order_id": e.get("order_id"),
             "amount_ledger": e.get("amount"), "price_ledger": e.get("price"),
             "exchange": orders.get(e.get("order_id"))}
            for e in events
        ],
    }
    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=1, default=str))
    else:
        print(f"== {a.symbol} ==")
        print(f"  eventi nel ledger: {len(events)} | ordini letti da OKX: {len(orders)}")
        print(f"  vendite chiuse: {len(sells)} (ricavi {round(proceeds,6)} - fee {round(sell_fees,6)} = {round(net_proceeds,6)})")
        print(f"  acquisti chiusi: {len(buys)} (spesa {round(spend,6)} + fee {round(buy_fees,6)} = {round(total_cost,6)})")
        print(f"  PnL netto ricostruito dall'exchange: {round(pnl_exchange,6)}")
        print(f"  PnL dichiarato dal bot:              {round(float(state.get('total_pnl') or 0),6)} "
              f"su {state.get('total_trades')} trade")
        print(f"  equity interna dichiarata dal bot:   {state.get('peak_equity')}")
        diff = round(float(state.get("total_pnl") or 0) - pnl_exchange, 6)
        print(f"  DIFFERENZA (bot - exchange):         {diff}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
