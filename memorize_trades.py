#!/usr/bin/env python3
"""
Memorize Trades — Fetches recent filled trades from Binance and stores in memory DB.
Runs every minute alongside collector. Uses Binance myTrades API for precision.

v2: Fee-aware — converts all commission assets (BNB, crypto) to EUR equivalent.
    PnL matching uses FIFO-like sequential pairing per bot/symbol.
"""
import json, os, sys, time, hashlib, hmac, urllib.parse, urllib.request
from pathlib import Path
from datetime import datetime, timezone

BASE = Path(__file__).parent
sys.path.insert(0, str(BASE))
from denaro_memory import DenaroMemory

BINANCE = "https://api.binance.com"
SYMBOLS = ["SOLEUR", "BTCEUR", "ETHEUR", "BNBEUR"]
LOOKBACK_HOURS = 48

BOT_MAP = {
    "SOLEUR": "stellatron",   # nuvola sub-account
    "BTCEUR": "orion",
    "ETHEUR": "orion",
    "BNBEUR": "orion",
    # marco_sol trades on SOLEUR via MARCODG1 sub-account (separate API key, NOT in this DB)
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


def _get_bnb_eur_price():
    """Fetch BNB/EUR price for commission conversion."""
    try:
        with urllib.request.urlopen(f"{BINANCE}/api/v3/ticker/price?symbol=BNBEUR", timeout=5) as r:
            data = json.load(r)
            return float(data.get("price", 0))
    except Exception:
        return 0.0


def _get_eur_prices():
    """Fetch all EUR prices for fee conversion."""
    try:
        with urllib.request.urlopen(f"{BINANCE}/api/v3/ticker/price", timeout=10) as r:
            data = json.load(r)
            return {p["symbol"]: float(p["price"]) for p in data}
    except Exception:
        return {}


def _compute_fee_eur(commission, comm_asset, prices):
    """Convert commission to EUR equivalent.
    
    Binance charges fees in:
    - BNB (if BNB discount enabled, 25% off)
    - The traded asset (e.g., buying SOL, fee in SOL)
    - EUR (rarely, for EUR pairs without BNB discount)
    """
    if commission <= 0 or not comm_asset:
        return 0.0
    
    if comm_asset == "EUR":
        return commission
    if comm_asset == "BNB":
        bnb_eur = prices.get("BNBEUR", 0)
        if bnb_eur > 0:
            return round(commission * bnb_eur, 6)
        return 0.0
    
    # Other crypto: try ASSET+EUR price
    price_key = comm_asset + "EUR"
    asset_eur = prices.get(price_key, 0)
    if asset_eur > 0:
        return round(commission * asset_eur, 6)
    
    # Try USDT conversion
    usdt_key = comm_asset + "USDT"
    asset_usdt = prices.get(usdt_key, 0)
    eur_usdt = prices.get("EURUSDT", 1.0)
    if asset_usdt > 0 and eur_usdt > 0:
        return round(commission * asset_usdt / eur_usdt, 6)
    
    return 0.0


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
        return

    memory = DenaroMemory()
    c = memory._conn_get()
    
    # Fetch prices for fee conversion
    prices = _get_eur_prices()
    bnb_eur = prices.get("BNBEUR", 0)
    print(f"[MEM] BNB/EUR: {bnb_eur:.4f}" if bnb_eur else "[MEM] Prices unavailable")

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

            # v2: convert fee to EUR
            fee_eur = _compute_fee_eur(commission, comm_asset, prices)

            memory.record_trade(
                bot=bot,
                symbol=symbol,
                side=side,
                price=price,
                amount=qty,
                eur_value=quote_qty,
                fee=fee_eur,
                trade_id=tid,
                filled_at=filled_at,
            )
            existing_ids.add(tid)
            new_count += 1

        if new_count:
            print(f"[MEM] {symbol} ({bot}): {new_count} new trades")

    # ── PnL Computation (FIFO-like sequential pairing) ──
    # Only compute PnL for trades that don't have it yet (net_pnl IS NULL)
    for bot_name in ["stellatron", "orion"]:
        rows = c.execute(
            "SELECT id, bot, symbol, side, price, amount, eur_value, fee "
            "FROM trades WHERE bot=? AND net_pnl IS NULL "
            "ORDER BY symbol, filled_at ASC",
            (bot_name,)).fetchall()

        if not rows:
            continue

        by_symbol = {}
        for r in rows:
            sym = r["symbol"]
            if sym not in by_symbol:
                by_symbol[sym] = []
            by_symbol[sym].append(dict(r))

        for sym, trades_list in by_symbol.items():
            open_side = None
            open_info = None

            for t in trades_list:
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
                    c.execute("UPDATE trades SET net_pnl=? WHERE id=?", (0.0, open_info["id"]))
                    open_side = "sell"
                    open_info = dict(t)

                elif side == "buy" and open_side == "sell":
                    # Reversal profit: buy closes a prior sell
                    total_fees = t_fee + (open_info.get("fee", 0) or 0)
                    pnl = open_info["eur_value"] - t["eur_value"] - total_fees
                    c.execute("UPDATE trades SET net_pnl=? WHERE id=?", (round(pnl, 6), t["id"]))
                    c.execute("UPDATE trades SET net_pnl=? WHERE id=?", (0.0, open_info["id"]))
                    open_side = "buy"
                    open_info = dict(t)

                elif side == "buy" and open_side == "buy":
                    # Multiple buys: first buy gets 0 PnL (cost basis only)
                    c.execute("UPDATE trades SET net_pnl=? WHERE id=?", (0.0, open_info["id"]))
                    open_side = "buy"
                    open_info = dict(t)

                elif side == "sell" and open_side == "sell":
                    c.execute("UPDATE trades SET net_pnl=? WHERE id=?", (0.0, open_info["id"]))
                    open_side = "sell"
                    open_info = dict(t)

            c.commit()

    # Update daily PnL summary
    today = datetime.now().strftime("%Y-%m-%d")
    for bot_name in ["stellatron", "orion"]:
        row = c.execute(
            "SELECT COALESCE(SUM(net_pnl),0) as pnl, COUNT(*) as cnt, COALESCE(SUM(fee),0) as fees "
            "FROM trades WHERE bot=? AND filled_at >= ?",
            (bot_name, today + "T00:00:00")).fetchone()
        if row and row["cnt"]:
            memory.update_daily_pnl(bot_name, round(row["pnl"], 4), row["cnt"], round(row["fees"], 4))

    print(f"[MEM] Done — total trades: {memory.summary()['total_trades']}")


if __name__ == "__main__":
    memorize()
