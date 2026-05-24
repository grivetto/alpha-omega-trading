#!/usr/bin/env python3
"""
Denaro — MARCODG1 (Trend Grid + Reversal)
Trades ADA/EUR on Binance spot.
Primary strategy: Grid trading with trend filter.
If ADA volatility too low, switches to SOL/EUR backup.
Uses BNB for fee discount.
"""
import asyncio, json, time, uuid
from datetime import datetime, timezone
from pathlib import Path
import websockets, ccxt

BASE_DIR = Path(__file__).parent
import sys
sys.path.insert(0, str(BASE_DIR))
from denaro_shared import setup_logger, make_client, fetch_balance, place_limit_order, cancel_all_orders, send_telegram, RegimeClassifier, BotState

logger = setup_logger("MarcoGrid", "marcodg1.log")
CONFIG_PATH = BASE_DIR / "config_marcodg1.json"

DEFAULT_CONFIG = {
    "primary_symbol": "ADA/EUR",
    "backup_symbol": "SOL/EUR",
    "base_order_eur": 7.0,
    "max_invested_eur": 25.0,
    "min_volatility_pct": 0.5,
    "fee_rate": 0.00075,
    "regime": {
        "bull": {"grid_levels": 5, "spacing_pct": 0.012, "profit_pct": 0.005, "max_invested": 30.0},
        "bear": {"grid_levels": 2, "spacing_pct": 0.02, "profit_pct": 0.007, "max_invested": 8.0},
        "choppy": {"grid_levels": 3, "spacing_pct": 0.006, "profit_pct": 0.003, "max_invested": 15.0},
        "neutral": {"grid_levels": 3, "spacing_pct": 0.01, "profit_pct": 0.004, "max_invested": 18.0},
        "volatile": {"grid_levels": 2, "spacing_pct": 0.025, "profit_pct": 0.008, "max_invested": 12.0},
        "unknown": {"grid_levels": 2, "spacing_pct": 0.01, "profit_pct": 0.004, "max_invested": 12.0},
    },
    "pair_switch_cooldown": 14400,
    "regime_check_interval": 300,
    "fill_check_interval": 15,
    "report_interval": 3600,
    "portfolio_floor": 35.0,
    "max_drawdown_pct": 10.0,
}

def load_config():
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            cfg = json.load(f)
        for k, v in DEFAULT_CONFIG.items():
            if k not in cfg:
                cfg[k] = v
        return cfg
    return DEFAULT_CONFIG.copy()

async def get_volatility(client, symbol):
    try:
        ohlcv = await asyncio.to_thread(client.fetch_ohlcv, symbol, "1h", limit=24)
        if len(ohlcv) < 2:
            return 0
        closes = [c[4] for c in ohlcv]
        highs = [c[2] for c in ohlcv]
        lows = [c[3] for c in ohlcv]
        atr = sum(max(h - l, abs(h - pc), abs(l - pc)) for h, l, pc in zip(highs, lows, [0] + closes[:-1])) / len(closes)
        atr_pct = atr / closes[-1] * 100 if closes[-1] > 0 else 0
        return atr_pct
    except Exception:
        return 0

async def get_portfolio_value(client, symbol):
    b = await fetch_balance(client)
    eur = b["free"].get("EUR", 0)
    base_symbol = symbol.split("/")[0]
    crypto = b["free"].get(base_symbol, 0) + b["used"].get(base_symbol, 0)
    try:
        ticker = await asyncio.to_thread(client.fetch_ticker, symbol)
        price = ticker["last"]
    except Exception:
        price = 0
    return eur + crypto * price, eur, crypto

async def manage_grid(client, config, rparams, state, symbol, current_price):
    base_asset = symbol.split("/")[0]
    b = await fetch_balance(client)
    eur_free = b["free"].get("EUR", 0)
    existing = await asyncio.to_thread(client.fetch_open_orders, symbol)
    existing_buys = len([o for o in existing if o["side"] == "buy"])
    total_inv = sum(float(o.get("cost", 0) or 0) for o in existing)
    max_inv = rparams.get("max_invested", config["max_invested_eur"])
    if total_inv >= max_inv or eur_free < config["base_order_eur"] * 1.1:
        return
    levels = rparams.get("grid_levels", 3)
    spacing = rparams.get("spacing_pct", 0.01)
    profit_pct = rparams.get("profit_pct", 0.004)
    budget = config["base_order_eur"]
    max_new = max(0, int((eur_free - 5) / budget))
    levels = min(levels, max_new)
    if levels <= 0:
        return
    step = spacing / levels
    buy_prices = [round(current_price * (1 - (i + 1) * step), 4) for i in range(levels)]
    placed = 0
    for bp in buy_prices:
        amount = budget / bp
        o = await place_limit_order(client, "buy", symbol, bp, amount)
        if o:
            placed += 1
            total_inv += budget
            logger.info(f"  BUY {bp} x {amount:.4f} ({budget:.1f}EUR) | {symbol}")
        await asyncio.sleep(0.3)
    if placed:
        logger.info(f"Grid placed: {placed} buys @ {symbol}")

async def check_fills_and_recycle(client, config, state, symbol):
    try:
        filled = await asyncio.to_thread(client.fetch_my_trades, symbol, limit=15)
        closed_ids = state.get("closed_order_ids", [])
        regime = state.get("regime", "neutral")
        profit_pct = config["regime"].get(regime, {}).get("profit_pct", 0.004)
        for t in filled:
            oid = str(t.get("order", ""))
            if not oid or oid in closed_ids:
                continue
            side = t.get("side", "")
            price = float(t.get("price", 0))
            amount = float(t.get("qty", 0))
            cost = float(t.get("cost", 0))
            fee = float(t.get("fee", {}).get("cost", 0)) if isinstance(t.get("fee"), dict) else 0
            if side == "buy" and amount > 0:
                target = round(price * (1 + profit_pct), 4)
                o = await place_limit_order(client, "sell", symbol, target, amount)
                if o:
                    logger.info(f"  SELL {target} | {symbol}")
                closed_ids.append(oid)
            elif side == "sell" and amount > 0:
                pnl = cost - (cost / (1 + profit_pct))
                profit = pnl - fee
                state["pnl"] = state.get("pnl", 0) + profit
                closed_ids.append(oid)
                logger.info(f"  PnL: {profit:.4f}EUR | {symbol}")
        state["closed_order_ids"] = closed_ids[-500:]
        state.save()
    except Exception as e:
        logger.debug(f"Fill check: {e}")

async def main():
    config = load_config()
    client = make_client()
    rc = RegimeClassifier()
    state = BotState("marcodg1_grid")
    active_symbol = config["primary_symbol"]
    last_pair_switch = 0
    last_regime_check = 0
    last_fill_check = 0
    last_report = 0
    peak_portfolio = 0

    try:
        ticker = await asyncio.to_thread(client.fetch_ticker, active_symbol)
        current_price = ticker["last"]
    except Exception as e:
        logger.error(f"Initial price: {e}")
        return

    logger.info(f"Starting MARCODG1 grid @ {active_symbol} = {current_price}")
    await send_telegram(logger, f"✅ MARCODG1 started | {active_symbol} @ {current_price:.4f}")

    ws_url = f"wss://stream.binance.com:9443/ws/{active_symbol.lower().replace('/', '')}@ticker"

    while True:
        try:
            async with websockets.connect(ws_url, ping_interval=30) as ws:
                while True:
                    msg = await asyncio.wait_for(ws.recv(), timeout=60)
                    data = json.loads(msg)
                    if data.get("e") != "24hrTicker":
                        continue
                    current_price = float(data["c"])

                    if time.time() - last_regime_check > config["regime_check_interval"]:
                        regime, conf = await rc.classify(client, active_symbol, "1h")
                        state.set("regime", regime)
                        state.save()
                        logger.info(f"Regime: {regime} (conf={conf:.2f}) | {active_symbol}")
                        vol = await get_volatility(client, active_symbol)
                        logger.info(f"Volatility: {vol:.2f}% | {active_symbol}")
                        min_vol = config["min_volatility_pct"]
                        if vol < min_vol and active_symbol == config["primary_symbol"] and time.time() - last_pair_switch > config["pair_switch_cooldown"]:
                            await cancel_all_orders(client, active_symbol)
                            active_symbol = config["backup_symbol"]
                            ws_url = f"wss://stream.binance.com:9443/ws/{active_symbol.lower().replace('/', '')}@ticker"
                            last_pair_switch = time.time()
                            logger.info(f"SWITCHED to {active_symbol} (vol={vol:.2f}% < {min_vol}%)")
                            await send_telegram(logger, f"🔄 MARCODG1 switched to {active_symbol}")
                            break
                        last_regime_check = time.time()

                    rparams = config["regime"].get(state.get("regime", "neutral"), config["regime"]["neutral"])
                    port_val, eur_free, crypto_free = await get_portfolio_value(client, active_symbol)
                    if port_val > peak_portfolio:
                        peak_portfolio = port_val
                    drawdown = ((peak_portfolio - port_val) / peak_portfolio * 100) if peak_portfolio > 0 else 0
                    floor = config.get("portfolio_floor", 35)
                    max_dd = config.get("max_drawdown_pct", 10)
                    if port_val < floor or drawdown > max_dd:
                        logger.warning(f"KILL: port={port_val:.2f} floor={floor} dd={drawdown:.1f}%")
                        await cancel_all_orders(client, active_symbol)
                        await send_telegram(logger, f"🚨 KILL MARCODG1: port={port_val:.2f} dd={drawdown:.1f}%")
                        await asyncio.sleep(300)

                    if time.time() - state.get("last_grid", 0) > 60:
                        await manage_grid(client, config, rparams, state, active_symbol, current_price)
                        state.set("last_grid", time.time())

                    if time.time() - last_fill_check > config["fill_check_interval"]:
                        await check_fills_and_recycle(client, config, state, active_symbol)
                        last_fill_check = time.time()

                    if time.time() - last_report > config["report_interval"]:
                        pnl = state.get("pnl", 0)
                        trades = state.get("trades", 0)
                        base_asset = active_symbol.split("/")[0]
                        logger.info(f"REPORT | {active_symbol} | {state.get('regime','?')} | pnl={pnl:.2f} | trades={trades} | port={port_val:.2f} | eur={eur_free:.2f} {base_asset}={crypto_free:.4f}")
                        await send_telegram(logger, f"📊 MARCODG1 | {active_symbol} {state.get('regime','?')} | PnL={pnl:.2f}€ | trades={trades}")
                        last_report = time.time()

        except (websockets.exceptions.ConnectionClosed, asyncio.TimeoutError):
            logger.warning("WS disconnected, reconnecting...")
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"Fatal: {e}")
            await send_telegram(logger, f"🔴 MARCODG1 crash: {e}")
            await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(main())
