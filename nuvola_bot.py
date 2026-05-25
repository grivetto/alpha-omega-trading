#!/usr/bin/env python3
"""
Denaro — nuvola (Regime-Adaptive Grid Bot)
Trades SOL/EUR on Binance spot with HMM-lite regime detection.
Adjusts grid parameters based on detected market regime.
Uses BNB for fee discount.
"""
import asyncio, json, time, uuid
from datetime import datetime, timezone
from pathlib import Path
import websockets
import ccxt

BASE_DIR = Path(__file__).parent
import sys
sys.path.insert(0, str(BASE_DIR))
from denaro_shared import setup_logger, make_client, fetch_balance, place_limit_order, cancel_all_orders, send_telegram, RegimeClassifier, BotState

logger = setup_logger("NuvolaGrid", "nuvola.log")
CONFIG_PATH = BASE_DIR / "config_nuvola.json"

DEFAULT_CONFIG = {
    "symbol": "SOL/EUR",
    "base_order_eur": 8.0,
    "max_invested_eur": 30.0,
    "fee_rate": 0.00075,
    "regime": {
        "bull": {"grid_levels": 6, "spacing_pct": 0.015, "profit_pct": 0.004, "max_invested": 40.0},
        "bear": {"grid_levels": 2, "spacing_pct": 0.025, "profit_pct": 0.006, "max_invested": 10.0},
        "choppy": {"grid_levels": 4, "spacing_pct": 0.008, "profit_pct": 0.003, "max_invested": 20.0},
        "neutral": {"grid_levels": 3, "spacing_pct": 0.012, "profit_pct": 0.004, "max_invested": 20.0},
        "volatile": {"grid_levels": 3, "spacing_pct": 0.03, "profit_pct": 0.008, "max_invested": 15.0},
        "unknown": {"grid_levels": 2, "spacing_pct": 0.01, "profit_pct": 0.004, "max_invested": 15.0},
    },
    "regime_check_interval": 300,
    "fill_check_interval": 10,
    "report_interval": 3600,
    "portfolio_floor": 45.0,
    "max_drawdown_pct": 8.0,
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

async def get_portfolio_value(client, symbol):
    b = await fetch_balance(client)
    eur = b["free"].get("EUR", 0)
    base_asset = symbol.split("/")[0]
    crypto = b["free"].get(base_asset, 0) + b["used"].get(base_asset, 0)
    try:
        ticker = await asyncio.to_thread(client.fetch_ticker, symbol)
        price = ticker["last"]
    except Exception:
        price = 0
    return eur + crypto * price, eur, crypto

async def manage_grid(client, config, regime_params, state, current_price):
    symbol = config["symbol"]
    base_asset = symbol.split("/")[0]
    b = await fetch_balance(client)
    eur_free = b["free"].get("EUR", 0)
    crypto_free = b["free"].get(base_asset, 0)
    existing = await asyncio.to_thread(client.fetch_open_orders, symbol)
    existing_buys = len([o for o in existing if o["side"] == "buy"])
    existing_sells = len([o for o in existing if o["side"] == "sell"])

    total_invested = sum(float(o.get("cost", 0) or 0) for o in existing if o["side"] == "buy")
    total_invested += sum(float(o.get("cost", 0) or 0) for o in existing if o["side"] == "sell")

    max_inv = regime_params.get("max_invested", config.get("max_invested_eur", 30))
    if total_invested >= max_inv:
        return

    levels = regime_params.get("grid_levels", 3)
    spacing = regime_params.get("spacing_pct", 0.01)
    profit_pct = regime_params.get("profit_pct", 0.004)

    budget = config["base_order_eur"]
    max_new = int((eur_free - 5) / budget) if eur_free > 5 else 0
    levels = min(levels, max_new)

    if levels <= 0:
        return

    step = spacing / levels if levels > 0 else spacing
    buy_prices = [round(current_price * (1 - (i + 1) * step), 2) for i in range(levels)]
    sell_prices = [round(bp * (1 + profit_pct), 2) for bp in buy_prices]

    placed = 0
    for bp, sp in zip(buy_prices, sell_prices):
        if existing_buys > 0 or total_invested >= max_inv:
            break
        amount = budget / bp
        o = await place_limit_order(client, "buy", symbol, bp, amount)
        if o:
            state.set("trades", state.get("trades", 0) + 1)
            total_invested += budget
            existing_buys += 1
            placed += 1
            logger.info(f"  BUY {bp} x {amount:.4f} ({budget:.1f}EUR) | regime={regime_params.get('_regime','?')}")
        await asyncio.sleep(0.3)

    if placed > 0:
        state.save()
        logger.info(f"Grid placed: {placed} buys @ {symbol}")

async def check_fills_and_recycle(client, config, state):
    symbol = config["symbol"]
    base_asset = symbol.split("/")[0]
    try:
        orders = await asyncio.to_thread(client.fetch_open_orders, symbol)
        closed_buys = []
        closed_sells = []

        filled = await asyncio.to_thread(
            client.fetch_my_trades, symbol, limit=20
        )
        recent_trades = [t for t in filled if t.get("order") and datetime.fromisoformat(t["datetime"].replace("Z", "+00:00")) if t]

        closed_order_ids = state.get("closed_order_ids", [])

        for t in filled:
            oid = str(t.get("order", ""))
            if not oid or oid in closed_order_ids:
                continue
            side = t.get("side", "")
            price = float(t.get("price", 0))
            amount = float(t.get("qty", 0))
            cost = float(t.get("cost", 0))
            fee = float(t.get("fee", {}).get("cost", 0)) if isinstance(t.get("fee"), dict) else 0

            if side == "buy" and amount > 0:
                logger.info(f"FILL BUY {price} x {amount:.4f} = {cost:.2f}EUR")
                target_sell = price * (1 + config.get("regime", {}).get(state.get("regime", "neutral"), {}).get("profit_pct", 0.004))
                sell_amount = amount
                o = await place_limit_order(client, "sell", symbol, round(target_sell, 2), sell_amount)
                if o:
                    logger.info(f"  SELL placed @ {target_sell:.2f}")
                closed_order_ids.append(oid)

            elif side == "sell" and amount > 0:
                logger.info(f"FILL SELL {price} x {amount:.4f} = {cost:.2f}EUR")
                pnl = cost - (cost / (1 + config.get("regime", {}).get(state.get("regime", "neutral"), {}).get("profit_pct", 0.004)))
                profit = pnl - fee
                state.set("pnl", state.get("pnl", 0) + profit)
                closed_order_ids.append(oid)

        state.set("closed_order_ids", closed_order_ids[-500:])
        state.save()
    except Exception as e:
        logger.debug(f"Fill check: {e}")

async def main():
    config = load_config()
    client = make_client()
    rc = RegimeClassifier()
    state = BotState("nuvola_grid")
    symbol = config["symbol"]

    try:
        ticker = await asyncio.to_thread(client.fetch_ticker, symbol)
        current_price = ticker["last"]
    except Exception as e:
        logger.error(f"Initial price: {e}")
        return

    logger.info(f"Starting nuvola grid @ {symbol} = {current_price}")
    await send_telegram(logger, f"✅ Nuvola Grid started | {symbol} @ {current_price:.2f}")

    ws_url = f"wss://stream.binance.com:9443/ws/{symbol.lower().replace('/', '')}@ticker"
    last_regime_check = 0
    last_fill_check = 0
    last_report = 0
    peak_portfolio = 0

    try:
        async with websockets.connect(ws_url, ping_interval=30) as ws:
            logger.info("WebSocket connected")
            while True:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=60)
                    data = json.loads(msg)
                    if data.get("e") != "24hrTicker":
                        continue
                    current_price = float(data["c"])

                    # Regime check
                    if time.time() - last_regime_check > config["regime_check_interval"]:
                        regime, conf = await rc.classify(client, symbol, "1h")
                        state.set("regime", regime)
                        state.set("regime_confidence", conf)
                        state.set("regime_updated", datetime.now(timezone.utc).isoformat())
                        state.save()
                        logger.info(f"Regime: {regime} (confidence={conf:.2f})")
                        last_regime_check = time.time()

                    regime = state.get("regime", "unknown")
                    rparams = config["regime"].get(regime, config["regime"]["neutral"])
                    rparams["_regime"] = regime

                    # Portfolio monitoring
                    port_val, eur_free, crypto_free = await get_portfolio_value(client, symbol)
                    if port_val > peak_portfolio:
                        peak_portfolio = port_val
                    drawdown = ((peak_portfolio - port_val) / peak_portfolio * 100) if peak_portfolio > 0 else 0
                    floor = config.get("portfolio_floor", 45)
                    max_dd = config.get("max_drawdown_pct", 8)
                    if port_val < floor or drawdown > max_dd:
                        logger.warning(f"KILL: portfolio={port_val:.2f} floor={floor} dd={drawdown:.1f}%")
                        await cancel_all_orders(client, symbol)
                        peak_portfolio = 0
                        await send_telegram(logger, f"🚨 KILL nuvola: port={port_val:.2f} dd={drawdown:.1f}%")
                        await asyncio.sleep(300)

                    # Grid management
                    if time.time() - state.get("last_grid_placement", 0) > 60:
                        await manage_grid(client, config, rparams, state, current_price)
                        state.set("last_grid_placement", time.time())

                    # Fill check
                    if time.time() - last_fill_check > config["fill_check_interval"]:
                        await check_fills_and_recycle(client, config, state)
                        last_fill_check = time.time()

                    # Report
                    if time.time() - last_report > config["report_interval"]:
                        pnl = state.get("pnl", 0)
                        trades = state.get("trades", 0)
                        logger.info(f"REPORT | regime={regime} pnl={pnl:.2f} trades={trades} port={port_val:.2f} eur={eur_free:.2f}")
                        await send_telegram(logger, f"📊 Nuvola | {regime} | PnL={pnl:.2f}€ | trades={trades} | port={port_val:.2f}€")
                        last_report = time.time()

                except (websockets.exceptions.ConnectionClosed, asyncio.TimeoutError):
                    logger.warning("WS disconnected, reconnecting...")
                    await asyncio.sleep(5)
                    break
                except Exception as e:
                    logger.error(f"Tick: {e}")
                    await asyncio.sleep(1)
    except Exception as e:
        logger.error(f"Fatal: {e}")
        await send_telegram(logger, f"🔴 Nuvola crash: {e}")

if __name__ == "__main__":
    asyncio.run(main())
