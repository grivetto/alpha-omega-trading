#!/usr/bin/env python3
"""equity_recon.py - equity reale del conto OKX a prezzi di mercato (SOLA LETTURA).

Legge saldi e prezzi spot, calcola il controvalore EUR per asset e il totale, poi confronta con
l'equity dichiarata dai bot (state.json dei bot mc2).

Uso: python3 equity_recon.py [--env ~/atlas-legacy-20260901/.env] [--json]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

NODE_DATA = Path("/home/sergio/alpha-omega-trading/node_data")
STABLES = {"EUR", "USDT", "USDC", "DAI", "USD"}


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


def bot_declared() -> dict:
    out = {}
    for f in NODE_DATA.glob("okx_default_*_state.json"):
        try:
            d = json.loads(f.read_text())
            out[f.name.replace("okx_default_", "").replace("_state.json", "")] = {
                "pnl": d.get("total_pnl"), "trades": d.get("total_trades"),
                "peak_equity": d.get("peak_equity")}
        except Exception:  # noqa: BLE001
            pass
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
    bal = ex.fetch_balance()
    totals = {k: float(v) for k, v in (bal.get("total") or {}).items() if v and float(v) > 0}

    rows, equity = [], 0.0
    missing = []
    for ccy, qty in sorted(totals.items()):
        if ccy in STABLES:
            price = 1.0
        else:
            price = None
            for pair in (f"{ccy}/EUR", f"{ccy}/USDT"):
                try:
                    t = ex.fetch_ticker(pair)
                    price = float(t.get("last") or t.get("close") or 0) or None
                    if price and pair.endswith("USDT"):
                        usd = ex.fetch_ticker("EUR/USDT")
                        price = price / float(usd.get("last") or 1)
                    break
                except Exception:  # noqa: BLE001
                    continue
        if price is None:
            missing.append(ccy)
            continue
        val = qty * price
        equity += val
        rows.append({"ccy": ccy, "qty": qty, "prezzo_eur": round(price, 6), "valore_eur": round(val, 6)})

    declared = bot_declared()
    declared_equity = sum((v.get("peak_equity") or 0) for v in declared.values())
    declared_pnl = sum((v.get("pnl") or 0) for v in declared.values())
    out = {"conto": a.env, "righe": rows, "equity_reale_eur": round(equity, 6),
           "asset_senza_prezzo": missing,
           "bot_dichiarano": declared, "equity_dichiarata_bot_eur": declared_equity,
           "pnl_dichiarato_bot_eur": round(declared_pnl, 6),
           "differenza_equity_eur": round(equity - declared_equity, 6)}
    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    else:
        print("== EQUITY REALE (OKX, sola lettura) ==")
        for r in rows:
            print(f"  {r['ccy']:5s} {r['qty']:<20} x {r['prezzo_eur']:<12} = {r['valore_eur']} EUR")
        if missing:
            print("  senza prezzo:", missing)
        print(f"  TOTALE equity reale: {round(equity, 6)} EUR")
        print("\n== DICHIARATO DAI BOT ==")
        for k, v in declared.items():
            print(f"  {k}: pnl={v['pnl']} trades={v['trades']} equity_dichiarata={v['peak_equity']}")
        print(f"  equity dichiarata totale: {declared_equity} EUR | pnl dichiarato: {round(declared_pnl, 6)} EUR")
        print(f"\n  DIFFERENZA equity (reale - dichiarata): {round(equity - declared_equity, 6)} EUR")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
