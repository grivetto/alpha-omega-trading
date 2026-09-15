#!/usr/bin/env python3
"""equity_full.py - equity TOTALE della flotta (OKX + Kraken) in EUR, sola lettura.

Sorgente primaria: l'aggregatore completo (di norma http://[::1]:8912/api/infra.json da mc2),
che riporta i saldi reali per conto. I prezzi vengono chiesti a OKX (spot EUR) con fallback USDT.
Confronta il totale con l'equity dichiarata dai bot e con i valori dell'aggregatore.

Uso: python3 equity_full.py [--url "http://[::1]:8912/api/infra.json"] [--json]
"""
from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path

STABLES = {"EUR", "USDT", "USDC", "DAI", "USD", "TUSD", "PYUSD"}
NODE_DATA = Path("/home/sergio/alpha-omega-trading/node_data")


def fetch(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read().decode())


def price_eur(ex, ccy: str) -> float | None:
    if ccy in STABLES:
        return 1.0
    for pair in (f"{ccy}/EUR", f"{ccy}/USDT"):
        try:
            t = ex.fetch_ticker(pair)
            p = float(t.get("last") or t.get("close") or 0)
            if not p:
                continue
            if pair.endswith("USDT"):
                usd = float((ex.fetch_ticker("EUR/USDT") or {}).get("last") or 1)
                p = p / usd if usd else p
            return p
        except Exception:  # noqa: BLE001
            continue
    return None


def declared() -> dict:
    out = {}
    for f in NODE_DATA.glob("okx_default_*_state.json"):
        try:
            d = json.loads(f.read_text())
            out[f.name.split("okx_default_")[1].replace("_state.json", "")] = {
                "pnl": d.get("total_pnl"), "trades": d.get("total_trades"),
                "equity": d.get("peak_equity")}
        except Exception:  # noqa: BLE001
            pass
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://[::1]:8912/api/infra.json")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    import ccxt  # type: ignore
    ex = ccxt.okx({"enableRateLimit": True})

    d = fetch(a.url)
    balances = d.get("balances") or {}
    rows, total = [], 0.0
    for acct, info in balances.items():
        if not isinstance(info, dict) or not info.get("ok"):
            rows.append({"conto": acct, "errore": str(info)[:120]})
            continue
        funds = info.get("total") or {}
        acct_val = 0.0
        for ccy, qty in funds.items():
            try:
                qty = float(qty)
            except Exception:  # noqa: BLE001
                continue
            if qty <= 0:
                continue
            p = price_eur(ex, ccy)
            if p is None:
                rows.append({"conto": acct, "ccy": ccy, "qty": qty, "prezzo_eur": None})
                continue
            val = qty * p
            acct_val += val
            rows.append({"conto": acct, "ccy": ccy, "qty": qty, "prezzo_eur": round(p, 6),
                         "valore_eur": round(val, 6)})
        total += acct_val

    dec = declared()
    dec_equity = sum((v.get("equity") or 0) for v in dec.values())
    dec_pnl = sum((v.get("pnl") or 0) for v in dec.values())
    out = {"url": a.url, "ts_aggregatore": d.get("ts_iso"), "righe": rows,
           "equity_reale_totale_eur": round(total, 4),
           "bot_equity_aggregatore": d.get("bot_equity"), "kraken_equity_aggregatore": d.get("kraken_equity"),
           "equity_dichiarata_bot_eur": dec_equity, "pnl_dichiarato_bot_eur": round(dec_pnl, 6),
           "bot_dichiarano": dec}
    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    else:
        print("== EQUITY TOTALE (sola lettura) ==", d.get("ts_iso"))
        for r in rows:
            if "errore" in r:
                print(f"  {r['conto']}: ERRORE {r['errore']}")
            elif r.get("prezzo_eur") is None:
                print(f"  {r['conto']}: {r['ccy']} {r['qty']} -> prezzo non disponibile")
            else:
                print(f"  {r['conto']:16s} {r['ccy']:6s} {r['qty']:<18} x {r['prezzo_eur']:<10} = {r['valore_eur']} EUR")
        print(f"  TOTALE REALE: {round(total, 4)} EUR")
        print(f"  Aggregatore dichiara: bot_equity={d.get('bot_equity')} kraken_equity={d.get('kraken_equity')}")
        print("  Bot (state.json):")
        for k, v in dec.items():
            print(f"    {k}: pnl={v['pnl']} trades={v['trades']} equity={v['equity']}")
        print(f"  equity dichiarata totale: {dec_equity} EUR | pnl dichiarato: {round(dec_pnl, 6)} EUR")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
