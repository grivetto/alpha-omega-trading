#!/usr/bin/env python3
"""fee_ledger.py - ledger dei trade con FEE REALI, lette dai FILL del conto (append-only).

Perche' cosi': il ledger interno dei bot (node_data/okx_default_*_trades.jsonl) non registra le fee,
e gli order_id che contiene NON appartengono al conto main (OKX risponde 51603 Order does not exist
sul main). Quindi le fee vanno lette dove i fill esistono davvero: `fetch_my_trades` sul conto del bot.

Produce:
  - riepilogo per simbolo: fill, controvalore, fee reali (per valuta), periodo;
  - righe append-only in node_data/recon_ledger.jsonl (una per fill), con fonte_exchange;
  - confronto con il PnL dichiarato dai bot in state.json.

Uso:
  python3 fee_ledger.py --env ~/alpha-omega-trading/.env --apply
  python3 fee_ledger.py --env ~/alpha-omega-trading/.env            # solo lettura
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

NODE_DATA = Path("/home/sergio/alpha-omega-trading/node_data")
RECON = NODE_DATA / "recon_ledger.jsonl"
STABLES = {"EUR", "USDT", "USDC", "USD", "DAI", "TUSD", "PYUSD"}


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


def iso(ms) -> str:
    try:
        return datetime.fromtimestamp(float(ms) / 1000, timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    except Exception:  # noqa: BLE001
        return "n/d"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default="~/alpha-omega-trading/.env")
    ap.add_argument("--symbol", action="append", default=[])
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--hostname", default="eea.okx.com")
    a = ap.parse_args()
    symbols = a.symbol or ["DOGE/EUR", "SOL/EUR"]
    env = load_env(a.env)
    if not env.get("OKX_API_KEY"):
        print("credenziali OKX mancanti in", a.env)
        return 2
    key_fp = hashlib.sha256(env["OKX_API_KEY"].encode()).hexdigest()[:12]
    print("conto (fingerprint chiave):", key_fp)

    import ccxt  # type: ignore
    ex = ccxt.okx({"apiKey": env["OKX_API_KEY"], "secret": env["OKX_API_SECRET"],
                   "password": env.get("OKX_PASSPHRASE", ""), "hostname": a.hostname,
                   "enableRateLimit": True})

    rows_out, summary = [], {}
    for sym in symbols:
        sym_file = sym.replace("/", "_")
        stf = NODE_DATA / f"okx_default_{sym_file}_state.json"
        declared = {}
        if stf.exists():
            try:
                d = json.loads(stf.read_text())
                declared = {"pnl_dichiarato": d.get("total_pnl"), "trades": d.get("total_trades"),
                            "equity_dichiarata": d.get("peak_equity")}
            except Exception:  # noqa: BLE001
                pass
        try:
            trades = ex.fetch_my_trades(sym, limit=a.limit)
        except Exception as e:  # noqa: BLE001
            print(f"  {sym}: errore fetch_my_trades {type(e).__name__}: {str(e)[:140]}")
            summary[sym] = {"errore": str(e)[:140], **declared}
            continue
        fees_by_cur: dict = {}
        notional = 0.0
        n_sell = n_buy = 0
        for t in trades:
            fee = t.get("fee") or {}
            fcur = (fee.get("currency") or "").upper()
            fcost = float(fee.get("cost") or 0)
            if fcur:
                fees_by_cur[fcur] = round(fees_by_cur.get(fcur, 0) + fcost, 10)
            cost = float(t.get("cost") or 0)
            notional += cost
            if t.get("side") == "sell":
                n_sell += 1
            elif t.get("side") == "buy":
                n_buy += 1
            rows_out.append({
                "order_id": t.get("order"), "trade_id": t.get("id"), "symbol": sym,
                "side": t.get("side"), "amount": t.get("amount"), "price": t.get("price"),
                "cost": round(cost, 8), "fee": round(fcost, 10), "fee_currency": fcur,
                "ts": iso(t.get("timestamp")), "fonte_exchange": "okx.fetch_my_trades",
                "acct_fp": key_fp,
            })
        summary[sym] = {"fill": len(trades), "vendite": n_sell, "acquisti": n_buy,
                        "controvalore": round(notional, 4), "fee_per_valuta": fees_by_cur, **declared}
        print(f"== {sym} ==")
        print(f"  fill: {len(trades)} (vendite {n_sell} / acquisti {n_buy}) | controvalore {round(notional,4)}")
        print(f"  FEE reali per valuta: {json.dumps(fees_by_cur, ensure_ascii=False)}")
        if trades:
            tsmin = min(t.get("timestamp") or 0 for t in trades)
            tsmax = max(t.get("timestamp") or 0 for t in trades)
            print(f"  periodo: {iso(tsmin)} -> {iso(tsmax)}")
        if declared:
            print(f"  PnL dichiarato dal bot: {declared.get('pnl_dichiarato')} su {declared.get('trades')} trade")
            fee_eur = sum(v for k, v in fees_by_cur.items() if k in STABLES)
            if fee_eur:
                quota = (round(fee_eur / declared["pnl_dichiarato"] * 100, 1)
                         if declared.get("pnl_dichiarato") else "n/d")
                print(f"  fee in EUR: {round(fee_eur,6)} | fee / PnL dichiarato: {quota}%")

    if a.apply:
        NODE_DATA.mkdir(parents=True, exist_ok=True)
        with RECON.open("a", encoding="utf-8") as fh:
            for row in rows_out:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"\nledger riconciliato: {len(rows_out)} righe appese a {RECON}")
    else:
        print("\n(--dry: nessuna scrittura)")
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
