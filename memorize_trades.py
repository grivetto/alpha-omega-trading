#!/usr/bin/env python3
"""
Memorize Trades — Fetches recent filled trades from Binance and stores in memory DB.
Runs every minute alongside collector. Uses Binance myTrades API for precision.
"""
import json, os, sys, time, hashlib, hmac, urllib.parse
from pathlib import Path
from datetime import datetime, timezone

BASE = Path(__file__).parent
sys.path.insert(0, str(BASE))
from denaro_memory import DenaroMemory

BINANCE = "https://api.binance.com"
SYMBOLS = ["ADAUSDT", "SOLEUR", "SOLUSDT", "BTCEUR", "ETHUSDT", "BNBEUR"]
LOOKBACK_HOURS = 48

BOT_MAP = {
    "ADAUSDT": "stellatron",
    "SOLEUR": "marco_sol",
    "SOLUSDT": "marco_sol",
    "BTCEUR": "orion",
    "ETHUSDT": "orion",
    "BNBEUR": "orion",
}


def get_credentials():
    key = secret = ""
    env_paths = [BASE / ".env", Path("/home/sergio/denaro/.env")]
    for ep in env_paths:
        if ep.exists():
            for line in ep.read_text().splitlines():
                if line.startswith("BINANCE_API_KEY="):
                    key = line.split("=", 1)[1].strip()
                elif line.startswith("BINANCE_API_SECRET="):
                    secret = line.split("=", 1)[1].strip()
                if key and secret:
                    return key, secret
    from dotenv import load_dotenv
    load_dotenv(env_paths[0])
    return os.getenv("BINANCE_API_KEY", ""), os.getenv("BINANCE_API_SECRET", "")


def fetch_my_trades(symbol, key, secret, limit=100):
    ts = int(time.time() * 1000)
    params = {"symbol": symbol, "limit": limit, "timestamp": ts}
    q = urllib.parse.urlencode(params)
    sig = hmac.new(secret.encode(), q.encode(), hashlib.sha256).hexdigest()
    params["signature"] = sig
    import requests
    try:
        r = requests.get(f"{BINANCE}/api/v3/myTrades",
            params=params, headers={"X-MBX-APIKEY": key}, timeout=10)
        if r.status_code == 200:
            return r.json()
        print(f"[MEM] myTrades {symbol}: HTTP {r.status_code}")
        return []
    except Exception as e:
        print(f"[MEM] Error fetching {symbol}: {e}")
        return []


def compute_net_pnl(trades_list):
    """Simple PnL estimate: sum quoteQty of sells - sum quoteQty of buys"""
    buy_total = sum(float(t["quoteQty"]) for t in trades_list if t.get("isBuyer"))
    sell_total = sum(float(t["quoteQty"]) for t in trades_list if not t.get("isBuyer"))
    return sell_total - buy_total


def memorize():
    key, secret = get_credentials()
    if not key or not secret:
        print("[MEM] No API credentials")
        # Fallback: log from collector data
        return

    memory = DenaroMemory()
    c = memory._conn_get()

    for symbol in SYMBOLS:
        bot = BOT_MAP.get(symbol, "unknown")
        trades = fetch_my_trades(symbol, key, secret)
        if not trades:
            continue

        # Get existing trade_ids for this symbol
        existing_ids = {
            r[0] for r in c.execute(
                "SELECT trade_id FROM trades WHERE symbol=? AND trade_id IS NOT NULL",
                (symbol,)).fetchall()
        }

        new_count = 0
        for t in trades:
            tid = t.get("id")
            if tid in existing_ids:
                continue

            is_buyer = t.get("isBuyer", True)
            side = "buy" if is_buyer else "sell"
            price = float(t.get("price", 0))
            qty = float(t.get("qty", 0))
            quote_qty = float(t.get("quoteQty", 0))
            commission = float(t.get("commission", 0))
            comm_asset = t.get("commissionAsset", "BNB")
            filled_ts = t.get("time", 0) // 1000
            filled_at = datetime.fromtimestamp(filled_ts, tz=timezone.utc).isoformat() if filled_ts else None

            memory.record_trade(
                bot=bot,
                symbol=symbol,
                side=side,
                price=price,
                amount=qty,
                eur_value=quote_qty,
                fee=commission if comm_asset == "EUR" else 0,
                trade_id=tid,
                filled_at=filled_at,
            )
            existing_ids.add(tid)
            new_count += 1

        if new_count:
            print(f"[MEM] {symbol} ({bot}): {new_count} new trades")

    # ── PnL Computation ──
    # Reversal pattern (marco_sol, orion): sell→buy cycle.
    # Profit realized at BUY: profit = prior_sell_value - buy_value - fees.
    # Grid pattern (stellatron): buy→sell cycle.
    # Profit realized at SELL: profit = sell_value - prior_buy_value - fees.
    for bot_name in ["stellatron", "marco_sol", "orion"]:
        rows = c.execute(
            "SELECT id, bot, symbol, side, price, amount, eur_value, fee "
            "FROM trades WHERE bot=? "
            "ORDER BY symbol, filled_at ASC",
            (bot_name,)).fetchall()

        by_symbol = {}
        for r in rows:
            sym = r["symbol"]
            if sym not in by_symbol:
                by_symbol[sym] = []
            by_symbol[sym].append(dict(r))

        for sym, trades in by_symbol.items():
            open_side = None
            open_info = None

            for t in trades:
                side = t["side"]
                t_fee = t.get("fee", 0) or 0

                if open_side is None:
                    open_side = side
                    open_info = dict(t)
                    continue

                if side == "sell" and open_side == "buy":
                    # Grid profit: sell closes a prior buy
                    total_fees = t_fee + (open_info.get("fee", 0) or 0)
                    pnl = t["eur_value"] - open_info["eur_value"] - total_fees
                    c.execute("UPDATE trades SET net_pnl=? WHERE id=?", (round(pnl, 6), t["id"]))
                    open_side = "sell"
                    open_info = dict(t)

                elif side == "buy" and open_side == "sell":
                    # Reversal profit: buy closes a prior sell
                    total_fees = t_fee + (open_info.get("fee", 0) or 0)
                    pnl = open_info["eur_value"] - t["eur_value"] - total_fees
                    c.execute("UPDATE trades SET net_pnl=? WHERE id=?", (round(pnl, 6), t["id"]))
                    open_side = "buy"
                    open_info = dict(t)

                elif side == "buy" and open_side == "buy":
                    c.execute("UPDATE trades SET net_pnl=? WHERE id=?", (0.0, open_info["id"]))
                    open_side = "buy"
                    open_info = dict(t)

                elif side == "sell" and open_side == "sell":
                    c.execute("UPDATE trades SET net_pnl=? WHERE id=?", (0.0, open_info["id"]))
                    open_side = "sell"
                    open_info = dict(t)

            c.commit()

    # Update daily PnL summary
    for bot_name in ["stellatron", "marco_sol", "orion"]:
        today = datetime.now().strftime("%Y-%m-%d")
        row = c.execute(
            "SELECT COALESCE(SUM(net_pnl),0) as pnl, COUNT(*) as cnt, COALESCE(SUM(fee),0) as fees "
            "FROM trades WHERE bot=? AND filled_at >= ?",
            (bot_name, today)).fetchone()
        if row and row["cnt"]:
            memory.update_daily_pnl(bot_name, round(row["pnl"], 4), row["cnt"], round(row["fees"], 4))

    print(f"[MEM] Done — total trades: {memory.summary()['total_trades']}")


if __name__ == "__main__":
    memorize()
