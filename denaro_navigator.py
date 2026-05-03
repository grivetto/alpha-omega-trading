#!/usr/bin/env python3
"""
DENARO GRID BOT v4 — Navigator (Layer 2)
B.L.A.S.T. Protocol — Phase A: Architect
Self-healing grid trading with ATR-dynamic spacing, full accounting, and kill switch.
"""

import asyncio
import json
import logging
import time
import uuid
import websockets
from datetime import datetime, timezone
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
from tools.state_manager import read_state, write_state, STATE_FILE
from tools.portfolio_tracker import get_portfolio_summary
from tools.telegram_alert import format_report

# ─── Setup ────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [v4] %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler("/home/sergio/denaro/grid_v4.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("GridBotV4")

BOT_DIR = Path(__file__).parent
CONFIG_PATH = BOT_DIR / "grid_config_v4.json"
STATE_FILE = BOT_DIR / ".tmp" / "gridbotv4_state.json"
DB_PATH = BOT_DIR / "trades.db"

load_dotenv(BOT_DIR / ".env")


# ─── Config ───────────────────────────────────────────────────────────────────

DEFAULT_CONFIG = {
    "symbol": "SOL/EUR",
    "symbol_ws": "soleur",
    "grid_levels": 3,
    "base_order_eur": 50.0,
    "max_total_invested": 150.0,
    "min_order_eur": 10.0,
    "atr_timeframe": "15m",
    "atr_lookback": 14,
    "atr_spacing_factor": 0.5,
    "atr_min_spacing_pct": 0.003,
    "atr_max_spacing_pct": 0.02,
    "profit_per_grid_pct": 0.003,
    "fee_rate": 0.00075,
    "kill_switch": {
        "max_drawdown_pct": 3.0,
        "out_of_bounds_pct": 0.025,
        "trailing_stop_pct": 1.5,
        "trailing_activation_pct": 2.0,
    },
    "report_hours_start": 6,
    "report_hours_end": 23,
    "report_min_drawdown_alert": 0.5,
}


def load_config():
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            cfg = json.load(f)
        # Merge with defaults
        for k, v in DEFAULT_CONFIG.items():
            if k not in cfg:
                cfg[k] = v
        return cfg
    return DEFAULT_CONFIG.copy()


# ─── State Factory ─────────────────────────────────────────────────────────────

def fresh_state():
    return {
        "bot_name": "GridBotV4",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "grid": {
            "buy_levels": [],
            "sell_levels": [],
            "active": False,
        },
        "orders": {
            "open_buy_ids": [],
            "open_sell_ids": [],
            "filled": [],
        },
        "accounting": {
            "peak_portfolio_eur": 0,
            "current_portfolio_eur": 0,
            "total_invested_eur": 0,
            "total_fees_eur": 0,
            "net_pnl_eur": 0,
            "drawdown_pct": 0,
            "win_count": 0,
            "loss_count": 0,
            "round_trips": 0,
            "base_order_eur": 0,
        },
        "risk": {
            "kill_switch_triggered": False,
            "kill_switch_reason": "",
            "kill_switch_confirm_ticks": 0,
            "paused": False,
            "pause_reason": "",
            "last_resume_price": 0,
        },
        "atr": {
            "current": 0,
            "current_pct": 0,
            "grid_spacing_pct": 0,
            "calculated_at": "",
        },
        "last_report_sent": 0,
        "last_fill_check": 0,
        "last_rebalance_check": 0,
        "last_atr_update": 0,
        "ticks_processed": 0,
        "kill_switch_triggered_at": None,
    }


# ─── Binance Client ────────────────────────────────────────────────────────────

import ccxt

def make_client():
    import os
    return ccxt.binance({
        'apiKey': os.getenv('BINANCE_API_KEY'),
        'secret': os.getenv('BINANCE_API_SECRET'),
        'enableRateLimit': True,
        'options': {'defaultType': 'spot', 'defaultFeeCurrency': 'BNB'},
    })


# ─── ATR Calculation ───────────────────────────────────────────────────────────

async def fetch_atr(client, symbol, timeframe, lookback):
    try:
        ohlcv = client.fetch_ohlcv(symbol, timeframe=timeframe, limit=lookback + 1)
        if len(ohlcv) < lookback:
            return None
        trs = []
        for i in range(1, len(ohlcv)):
            high, low, prev = ohlcv[i][2], ohlcv[i][3], ohlcv[i-1][4]
            tr = max(high - low, abs(high - prev), abs(low - prev))
            trs.append(tr)
        return sum(trs) / len(trs)
    except Exception as e:
        logger.error(f"ATR fetch error: {e}")
        return None


# ─── Grid Logic ───────────────────────────────────────────────────────────────

def compute_grid_levels(current_price, atr, atr_pct, config):
    """Compute buy/sell levels based on ATR-dynamic spacing."""
    factor = config['atr_spacing_factor']
    spacing_pct = max(
        config['atr_min_spacing_pct'],
        min(atr_pct * factor, config['atr_max_spacing_pct'])
    )
    num_levels = config['grid_levels']
    step = spacing_pct / num_levels

    buy_levels = [round(current_price * (1 - (i * step)), 2) for i in range(1, num_levels + 1)]
    profit = config['profit_per_grid_pct']
    sell_levels = [round(bp * (1 + profit), 2) for bp in buy_levels]
    return buy_levels, sell_levels, spacing_pct


# ─── Order Management ──────────────────────────────────────────────────────────

async def place_order(client, side, symbol, price, amount):
    """Place a limit order, return order dict or None."""
    try:
        if side == "buy":
            order = client.create_limit_buy_order(symbol, round(amount, 5), round(price, 2))
        else:
            order = client.create_limit_sell_order(symbol, round(amount, 5), round(price, 2))
        return {
            "order_id": order['id'],
            "side": side,
            "price": float(order['price']),
            "amount": float(order['amount']),
            "symbol": order['symbol'],
            "status": "open",
            "filled_at": None,
        }
    except ccxt.InsufficientFunds:
        logger.error(f"Insufficient funds for {side} @ {price}")
        return None
    except Exception as e:
        logger.error(f"Order failed {side} @ {price}: {e}")
        return None


async def cancel_order(client, order_id, symbol):
    try:
        client.cancel_order(order_id, symbol)
        return True
    except Exception as e:
        logger.debug(f"Cancel {order_id}: {e}")
        return False


async def check_order_status(client, order, symbol):
    """Check if order is filled, return updated order dict."""
    try:
        status = client.fetch_order(order['order_id'], symbol)
        if status['status'] == 'closed':
            order['status'] = 'filled'
            order['filled_price'] = float(status.get('average', status['price']))
            order['filled_amount'] = float(status.get('filled', order['amount']))
            order['filled_at'] = datetime.now(timezone.utc).isoformat()
        return order
    except ccxt.OrderNotFound:
        order['status'] = 'unknown'
        return order
    except Exception as e:
        logger.debug(f"Order check {order['order_id']}: {e}")
        return order


# ─── Accounting ───────────────────────────────────────────────────────────────

def init_db():
    """Ensure DB tables exist."""
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bot_instance TEXT, strategy TEXT, symbol TEXT,
            side TEXT, order_id TEXT, price REAL, amount REAL,
            cost_eur REAL, fee_eur REAL, fee_currency TEXT DEFAULT 'EUR',
            pnl_eur REAL, grid_level INTEGER, round_trip_id TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS round_trips (
            id TEXT PRIMARY KEY, symbol TEXT,
            buy_order_id TEXT, buy_price REAL, buy_amount REAL, buy_fee_eur REAL, buy_time TEXT,
            sell_order_id TEXT, sell_price REAL, sell_amount REAL, sell_fee_eur REAL, sell_time TEXT,
            pnl_eur REAL, duration_sec INTEGER, bot_instance TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS daily_stats (
            date TEXT PRIMARY KEY, bot_instance TEXT, symbol TEXT,
            opening_price REAL, closing_price REAL,
            trades_count INTEGER, round_trips INTEGER,
            volume_eur REAL, fees_eur REAL, pnl_eur REAL,
            drawdown_pct REAL, peak_portfolio REAL, end_portfolio REAL
        )
    """)
    conn.commit()
    conn.close()


def log_trade(trade_record):
    """Log a filled trade to SQLite."""
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO trades
        (bot_instance, strategy, symbol, side, order_id, price, amount,
         cost_eur, fee_eur, fee_currency, pnl_eur, grid_level, round_trip_id, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        trade_record.get('bot_instance', 'GridBotV4'),
        trade_record.get('strategy', 'grid'),
        trade_record.get('symbol', 'SOL/EUR'),
        trade_record.get('side'),
        trade_record.get('order_id'),
        trade_record.get('price'),
        trade_record.get('amount'),
        trade_record.get('cost_eur', 0),
        trade_record.get('fee_eur', 0),
        'EUR',
        trade_record.get('pnl_eur'),
        trade_record.get('grid_level'),
        trade_record.get('round_trip_id'),
        trade_record.get('filled_at', datetime.now(timezone.utc).isoformat()),
    ))
    conn.commit()
    conn.close()


def log_round_trip(rt_record):
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT OR REPLACE INTO round_trips
        (id, symbol, buy_order_id, buy_price, buy_amount, buy_fee_eur, buy_time,
         sell_order_id, sell_price, sell_amount, sell_fee_eur, sell_time,
         pnl_eur, duration_sec, bot_instance)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        rt_record['id'], rt_record['symbol'],
        rt_record.get('buy_order_id'), rt_record.get('buy_price'),
        rt_record.get('buy_amount'), rt_record.get('buy_fee_eur'),
        rt_record.get('buy_time'),
        rt_record.get('sell_order_id'), rt_record.get('sell_price'),
        rt_record.get('sell_amount'), rt_record.get('sell_fee_eur'),
        rt_record.get('sell_time'),
        rt_record.get('pnl_eur'), rt_record.get('duration_sec'),
        rt_record.get('bot_instance', 'GridBotV4'),
    ))
    conn.commit()
    conn.close()


# ─── Kill Switch ──────────────────────────────────────────────────────────────

async def evaluate_risk(state, portfolio_summary, config, current_price):
    """
    Evaluate all kill switch conditions.
    Returns (kill_triggered: bool, reason: str, action: str)
    """
    ksw = config['kill_switch']
    risk = state['risk']
    acc = state['accounting']

    # ─── Kill Switch Clearance: require 3 consecutive ticks above floor+buffer.
    # FIX v2: also account for pending order cost when checking clearance.
    # If placing a new order would immediately re-trigger the kill switch,
    # do NOT clear — this prevents the kill→clear→order→kill flicker loop. ─
    if risk.get('kill_switch_triggered') and not risk.get('kill_switch_recovery_pending'):
        portfolio_floor = ksw.get('portfolio_floor', 0)
        eur_floor = ksw.get('eur_floor', 0)
        current_portfolio = portfolio_summary.get('total_eur', 0)
        eur_free_val = portfolio_summary.get('eur_free', portfolio_summary.get('total_eur', 0))

        primary_floor = portfolio_floor if portfolio_floor > 0 else eur_floor
        primary_value = current_portfolio if portfolio_floor > 0 else eur_free_val
        stable_buffer = 5.0 if portfolio_floor > 0 else 5.0

        if primary_floor > 0 and primary_value >= primary_floor + stable_buffer:
            # ─── NEW: projected cost check ───
            # Simulate what happens if we place grid orders after clearance
            budget = config.get('base_order_eur', 10)
            levels = config.get('grid_levels', 1)
            pending_cost = pending_cost if 'pending_cost' in dir() else 0
            # Compute how many levels would be placed given current EUR free
            if eur_floor > 0:
                available = eur_free_val - pending_cost - eur_floor - stable_buffer
            else:
                available = eur_free_val - pending_cost
            would_place = min(levels, max(0, int(available / budget))) if budget > 0 else 0
            projected_cost = would_place * budget
            # Clearance passes only if EUR would stay >= floor after placing orders
            if eur_floor > 0 and (eur_free_val - pending_cost - projected_cost) < eur_floor:
                risk['kill_switch_confirm_ticks'] = 0  # block clearance
            elif primary_value >= primary_floor + stable_buffer:
                risk['kill_switch_confirm_ticks'] = risk.get('kill_switch_confirm_ticks', 0) + 1
            else:
                risk['kill_switch_confirm_ticks'] = 0
        else:
            risk['kill_switch_confirm_ticks'] = 0
        if risk['kill_switch_confirm_ticks'] >= 3:
            risk['kill_switch_recovery_pending'] = True
            risk['recovery_price'] = current_price
            return False, "", "resume_pending"
        return False, "", "hold"

    if risk.get('kill_switch_triggered') and risk.get('kill_switch_recovery_pending'):
        # Kill switch cleared but recovery pending — wait for price to stabilize
        # before re-enabling grid placement
        return False, "", "hold"

    # Drawdown check — skip if max_drawdown_pct is 0 (eur_floor is primary protection)
    peak = acc.get('peak_portfolio_eur', portfolio_summary.get('peak_eur', 0))
    current = portfolio_summary.get('total_eur', 0)
    drawdown = ((peak - current) / peak * 100) if peak > 0 else 0

    if ksw.get('max_drawdown_pct', 0) > 0 and drawdown > ksw['max_drawdown_pct'] and not risk.get('kill_switch_triggered'):
        return True, f"Drawdown {drawdown:.2f}% exceeds {ksw['max_drawdown_pct']}% limit", "kill"

    # Portfolio floor check — NEW: protects entire crypto+EUR value
    portfolio_floor = ksw.get('portfolio_floor', 0)
    if portfolio_floor > 0:
        current_portfolio = portfolio_summary.get('total_eur', 0)
        if current_portfolio < portfolio_floor and not risk.get('kill_switch_triggered'):
            return True, f"Portfolio {current_portfolio:.2f} below floor €{portfolio_floor:.2f}", "kill"

    # EUR floor check — secondary capital protection
    eur_floor = ksw.get('eur_floor', 0)
    if eur_floor > 0:
        eur_free = portfolio_summary.get('eur_free', portfolio_summary.get('total_eur', 0))
        if eur_free < eur_floor and not risk.get('kill_switch_triggered'):
            return True, f"EUR free {eur_free:.2f} below floor €{eur_floor:.2f}", "kill"

    # Out-of-bounds check
    if state['grid']['buy_levels']:
        lowest = min(state['grid']['buy_levels'])
        if current_price < lowest * (1 - ksw['out_of_bounds_pct']):
            return True, f"Price {current_price} below grid + {ksw['out_of_bounds_pct']*100}%", "kill"

    return False, "", "ok"


async def execute_kill_switch(state, client, config, reason):
    """Cancel all orders, pause bot, log kill event."""
    logger.warning(f"🚨 KILL SWITCH: {reason}")
    state['risk']['kill_switch_triggered'] = True
    state['risk']['kill_switch_reason'] = reason
    state['risk']['kill_switch_triggered_at'] = datetime.now(timezone.utc).isoformat()
    state['risk']['kill_switch_confirm_ticks'] = 0
    state['risk']['kill_switch_recovery_pending'] = False
    state['grid']['active'] = False

    # Cancel all open orders
    for oid in state['orders']['open_buy_ids'] + state['orders']['open_sell_ids']:
        await cancel_order(client, oid, config['symbol'])
    state['orders']['open_buy_ids'] = []
    state['orders']['open_sell_ids'] = []

    save_state(state)

    # Alert immediately
    await send_telegram_alert(state, market_data={"last": 0, "atr": 0, "atr_pct": 0}, alert_type="kill_switch", reason=reason)


async def send_telegram_alert(state, market_data, alert_type, reason=""):
    """Send alert to Telegram if conditions met."""
    from tools.telegram_alert import send_alert
    import os
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    if not token or not chat_id:
        return

    if alert_type == "kill_switch":
        text = (
            f"🚨 KILL SWITCH ATTIVATO\n"
            f"Ragione: {reason}\n"
            f"Portfolio: €{state['accounting'].get('total_eur', 0):.2f}\n"
            f"Ora: {datetime.now(timezone.utc).isoformat()[:19]}Z"
        )
    elif alert_type == "report":
        text = format_report(state, market_data)
    elif alert_type == "status":
        text = f"GridBotV4 — {reason}"

    try:
        import urllib.request
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = json.dumps({"chat_id": chat_id, "text": text}).encode()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
        logger.info(f"Telegram alert sent: {alert_type}")
    except Exception as e:
        logger.error(f"Telegram error: {e}")


# ─── Main Bot ─────────────────────────────────────────────────────────────────

async def main_loop():
    config = load_config()
    client = make_client()
    init_db()

    # Load or initialize state
    raw_state = read_state()
    if raw_state and raw_state.get('bot_name') == 'GridBotV4':
        # Merge recovered state with fresh defaults (defensive against partial states)
        defaults = fresh_state()
        for k, v in defaults.items():
            if k not in raw_state:
                raw_state[k] = v
            elif isinstance(v, dict):
                for sk, sv in v.items():
                    if sk not in raw_state[k]:
                        raw_state[k][sk] = sv
        state = raw_state
        logger.info("State recovered from disk")
        # Validate critical values — override if corrupted (NaN, 0, unreasonably small)
        peak = state.get('accounting', {}).get('peak_portfolio_eur', 0)
        if not peak or peak < 10:  # Corrupted or from test — will recalculate from real balance
            logger.info(f"Peak {peak} appears corrupted — will recalculate from balance")
            state.get('accounting', {})['peak_portfolio_eur'] = 0  # Flag for recalculation
        # If eur_floor is primary protection, clear any stale kill switch from previous runs
        if config.get('kill_switch', {}).get('mode') == 'eur_floor':
            state['risk']['kill_switch_triggered'] = False
            state['risk']['kill_switch_recovery_pending'] = False
            state['risk']['kill_switch_reason'] = ''
            logger.info("eur_floor mode active — cleared any stale kill switch state")
        # ─── Sync recovered order IDs with exchange ─────────────────────────────────
        # Remove order IDs that no longer exist on the exchange (stale from crashed runs)
        try:
            open_orders = client.fetch_open_orders(config['symbol'])
            live_ids = {str(o['id']) for o in open_orders}
            stale_buys = [oid for oid in state['orders']['open_buy_ids'] if oid not in live_ids]
            stale_sells = [oid for oid in state['orders']['open_sell_ids'] if oid not in live_ids]
            if stale_buys or stale_sells:
                logger.warning(f"Stale orders purged from state: {len(stale_buys)} buys, {len(stale_sells)} sells")
                state['orders']['open_buy_ids'] = [oid for oid in state['orders']['open_buy_ids'] if oid in live_ids]
                state['orders']['open_sell_ids'] = [oid for oid in state['orders']['open_sell_ids'] if oid in live_ids]
        except Exception as e:
            logger.warning(f"Order sync check failed: {e} — will sync on next tick")
    else:
        state = fresh_state()
        save_state(state)

    # Set base_order_eur from config
    state['accounting']['base_order_eur'] = config['base_order_eur']

    # Initial price and ATR
    try:
        ticker = client.fetch_ticker(config['symbol'])
        current_price = ticker['last']
    except Exception as e:
        logger.error(f"Cannot fetch initial price: {e}")
        return

    # Initialize peak from actual portfolio — also reset if stored peak is wildly inflated
    # (e.g., recovered from a previous session with more capital, or a calculation error)
    bal = client.fetch_balance()
    eur_bal = bal['free'].get('EUR', 0)
    sol_bal = bal['free'].get('SOL', 0) + bal.get('used', {}).get('SOL', 0)
    try:
        sol_ticker = client.fetch_ticker(config['symbol'])
        sol_price = sol_ticker['last']
    except:
        sol_price = current_price
    actual_portfolio = eur_bal + sol_bal * sol_price
    stored_peak = state['accounting'].get('peak_portfolio_eur', 0)
    # Reset peak if: missing, too low (corrupted), OR too high (stale high-water mark)
    if not stored_peak or stored_peak < actual_portfolio * 0.5 or stored_peak > actual_portfolio * 1.5:
        logger.info(f"Peak reset: stored={stored_peak:.2f}, actual={actual_portfolio:.2f} — recalibrating")
        state['accounting']['peak_portfolio_eur'] = actual_portfolio

    atr = await fetch_atr(client, config['symbol'], config['atr_timeframe'], config['atr_lookback'])
    if atr:
        state['atr']['current'] = atr
        state['atr']['current_pct'] = atr / current_price
        state['atr']['calculated_at'] = datetime.now(timezone.utc).isoformat()

    # Sync open orders from exchange
    await sync_with_exchange(state, client, config, current_price)

    # Main WebSocket loop
    ws_url = f"wss://stream.binance.com:9443/ws/{config['symbol_ws']}@ticker"
    logger.info(f"Connecting to {ws_url}")

    async with websockets.connect(ws_url, ping_interval=30) as ws:
        logger.info("WebSocket connected")
        last_report_check = time.time()
        last_atr_refresh = time.time()
        last_rebalance_check = time.time()

        while True:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=60)
                data = json.loads(msg)
                if data.get('e') != '24hrTicker':
                    continue

                current_price = float(data['c'])
                state['ticks_processed'] += 1

                # Refresh ATR every 5 minutes
                if time.time() - last_atr_refresh > 300:
                    atr = await fetch_atr(client, config['symbol'], config['atr_timeframe'], config['atr_lookback'])
                    if atr:
                        state['atr']['current'] = atr
                        state['atr']['current_pct'] = atr / current_price
                        state['atr']['calculated_at'] = datetime.now(timezone.utc).isoformat()
                    last_atr_refresh = time.time()

                # Refresh portfolio every tick — use full portfolio_tracker
                # This includes ALL crypto assets, not just SOL
                try:
                    from tools.portfolio_tracker import get_balances, get_portfolio_summary
                    raw_balances = get_balances(client)
                    portfolio_dict = get_portfolio_summary(raw_balances, state)
                    total_eur = portfolio_dict['total_eur']
                    eur_free = portfolio_dict['eur_free']
                except Exception as e:
                    # Fallback to manual calculation if tracker fails
                    bal = client.fetch_balance()
                    eur_free = bal['free'].get('EUR', 0)
                    sol_free = bal['free'].get('SOL', 0)
                    sol_locked = bal.get('used', {}).get('SOL', 0)
                    total_sol = sol_free + sol_locked
                    total_eur = eur_free + total_sol * current_price
                    portfolio_dict = {
                        "total_eur": total_eur,
                        "eur_free": eur_free,
                        "peak_eur": state['accounting'].get('peak_portfolio_eur', total_eur),
                        "drawdown_pct": 0,
                    }

                peak = state['accounting'].get('peak_portfolio_eur', 0)
                if peak <= 0 or peak < total_eur * 0.7:
                    peak = total_eur
                drawdown = ((peak - total_eur) / peak * 100) if peak > 0 else 0

                state['accounting']['current_portfolio_eur'] = total_eur
                state['accounting']['drawdown_pct'] = drawdown

                if total_eur > peak:
                    state['accounting']['peak_portfolio_eur'] = total_eur
                    peak = total_eur
                killed, reason, action = await evaluate_risk(state, portfolio_dict, config, current_price)
                if killed and not state['risk']['kill_switch_triggered']:
                    await execute_kill_switch(state, client, config, reason)
                elif action == "resume_pending" and state['risk'].get('kill_switch_recovery_pending'):
                    state['risk']['kill_switch_triggered'] = False
                    state['risk']['kill_switch_recovery_pending'] = False
                    state['risk']['kill_switch_reason'] = ""
                    state['grid']['active'] = False
                    logger.info(f"🟢 Kill switch cleared. Resuming at {current_price}")
                    await send_telegram_alert(state, {"last": current_price, "atr": state['atr']['current'], "atr_pct": state['atr']['current_pct']}, "status", f"Recovery at €{current_price}")
                    save_state(state)

                # Grid management
                if not state['risk']['kill_switch_triggered']:
                    await manage_grid(state, client, config, current_price, eur_free, total_eur)

                # Check fills every 10 seconds
                if time.time() - state.get('last_fill_check', 0) > 10:
                    await check_fills(state, client, config)
                    state['last_fill_check'] = time.time()

                # Rebalance check every 5 minutes
                if time.time() - last_rebalance_check > 300:
                    await rebalance_check(state, client, config, current_price)
                    last_rebalance_check = time.time()

                # Hourly report (6:00-23:00 only)
                if time.time() - last_report_check > 3600:
                    hour = datetime.now().hour
                    if config['report_hours_start'] <= hour <= config['report_hours_end']:
                        await send_telegram_alert(state, {"last": current_price, "atr": state['atr']['current'], "atr_pct": state['atr']['current_pct'], "timestamp": datetime.now(timezone.utc).isoformat()}, "report")
                        last_report_check = time.time()
                    else:
                        last_report_check = time.time()

                save_state(state)

                if state['ticks_processed'] % 100 == 0:
                    logger.info(f"Ticks: {state['ticks_processed']} | Price: {current_price} | Drawdown: {portfolio_dict.get('drawdown_pct', 0):.2f}% | EUR free: {portfolio_dict.get('eur_free', 0):.2f} | Grid active: {state['grid']['active']}")

            except websockets.exceptions.ConnectionClosed:
                logger.warning("WebSocket closed, reconnecting...")
                await asyncio.sleep(5)
                break
            except Exception as e:
                import traceback
                logger.error(f"Tick error: {e}\n{traceback.format_exc()[:500]}")


async def sync_with_exchange(state, client, config, current_price):
    """Sync local state with open orders on exchange."""
    try:
        open_orders = client.fetch_open_orders(config['symbol'])
        buys = [o for o in open_orders if o['side'] == 'buy']
        sells = [o for o in open_orders if o['side'] == 'sell']
        state['orders']['open_buy_ids'] = [o['id'] for o in buys]
        state['orders']['open_sell_ids'] = [o['id'] for o in sells]
        state['grid']['active'] = len(open_orders) > 0
        logger.info(f"Sync: {len(buys)} buys / {len(sells)} sells on exchange")
    except Exception as e:
        logger.error(f"Sync error: {e}")


async def manage_grid(state, client, config, current_price, eur_free, total_eur):
    """Initialize or maintain the grid with EUR floor protection.
    
    eur_free: pure EUR balance (from balance['free']['EUR'])
    total_eur: EUR + SOL value (from balance computation in main loop)
    """
    eur_floor = config['kill_switch'].get('eur_floor', 0)
    budget = config['base_order_eur']

    # ─── Sync with exchange FIRST — floor check must use live order data ───────────
    try:
        open_orders = client.fetch_open_orders(config['symbol'])
        buys = [o for o in open_orders if o['side'] == 'buy']
        sells = [o for o in open_orders if o['side'] == 'sell']
        state['orders']['open_buy_ids'] = [str(o['id']) for o in buys]
        state['orders']['open_sell_ids'] = [str(o['id']) for o in sells]
        state['grid']['active'] = len(open_orders) > 0
    except Exception as e:
        logger.warning(f"Grid sync failed: {e}")
        return

    if state['grid']['active']:
        # If grid is active, verify portfolio won't violate floor
        portfolio_floor = config['kill_switch'].get('portfolio_floor', 0)
        eur_floor = config['kill_switch'].get('eur_floor', 0)
        primary_floor = portfolio_floor if portfolio_floor > 0 else eur_floor

        if primary_floor > 0 and total_eur < primary_floor:
            logger.warning(f"⚠️ Portfolio {total_eur:.2f} below floor €{primary_floor:.2f} — cancelling all buys")
            for oid in list(state['orders']['open_buy_ids']):
                try:
                    client.cancel_order(oid, config['symbol'])
                except:
                    pass
            state['orders']['open_buy_ids'] = []
            state['grid']['active'] = False
            state['grid']['buy_levels'] = []
            save_state(state)
        return

    # ─── Place new grid ───
    atr = state['atr']['current']
    atr_pct = state['atr']['current_pct']
    buy_levels, sell_levels, spacing = compute_grid_levels(current_price, atr, atr_pct, config)
    state['grid']['buy_levels'] = buy_levels
    state['grid']['sell_levels'] = sell_levels
    state['atr']['grid_spacing_pct'] = spacing

    # Count already pending buys (from this session's state)
    pending_buys = len(state['orders']['open_buy_ids'])
    pending_cost = pending_buys * budget

    # EUR floor protection for NEW orders only:
    # After placing new_orders, total_eur (including SOL) must stay >= floor + buffer
    safety_buffer = 2.0
    effective_floor = eur_floor + safety_buffer if eur_floor > 0 else 0

    if effective_floor > 0:
        available_for_new = total_eur - pending_cost - effective_floor
        max_new_levels = int(available_for_new / budget)
    else:
        max_new_levels = int(eur_free / (budget * 1.1))

    num_to_place = min(config.get('grid_levels', 1), max_new_levels)

    # HARD GUARD: never place if it would violate eur_floor immediately.
    # Use num_to_place (not max_new_levels) — num_to_place is capped by grid_levels
    # while max_new_levels reflects ALL possible levels from total_eur.
    if num_to_place >= 1 and eur_floor > 0:
        eur_after_placement = eur_free - (num_to_place * budget)
        if eur_after_placement < eur_floor:
            logger.warning(f"EUR floor hard-guard: EUR after {num_to_place} orders = {eur_after_placement:.2f} < floor {eur_floor:.2f} — blocked")
            num_to_place = 0

    if num_to_place < 1:
        logger.warning(f"Insufficient EUR {eur_free:.2f} to place grid")
        return

    logger.info(f"Placing {num_to_place} buy level(s) | EUR free: {eur_free:.2f} | pending: {pending_buys} | floor: {eur_floor:.2f} | spacing: {spacing:.3%}")
    placed_this_tick = []
    for i, bp in enumerate(reversed(buy_levels[:num_to_place])):
        amount = budget / bp
        order = await place_order(client, "buy", config['symbol'], bp, amount)
        if order:
            placed_this_tick.append(order['order_id'])
            state['orders']['open_buy_ids'].append(order['order_id'])
            state['accounting']['total_invested_eur'] += budget
            logger.info(f"  BUY {bp}€ | {amount:.5f} SOL | €{budget:.2f}")

    state['grid']['active'] = True
    save_state(state)


async def check_fills(state, client, config):
    """Check all open orders for fills, handle round trips."""
    all_ids = list(state['orders']['open_buy_ids']) + list(state['orders']['open_sell_ids'])
    for oid in all_ids:
        try:
            status = client.fetch_order(oid, config['symbol'])
            if status['status'] != 'closed':
                continue

            # Find and update order
            order = None
            for o in state['orders'].get('recent_orders', []):
                if o.get('order_id') == oid:
                    order = o
                    break

            side = status['side']
            price = float(status.get('average', status['price']))
            amount = float(status.get('filled', status.get('amount', 0)))
            cost = price * amount
            fee = cost * config['fee_rate']
            filled_at = datetime.now(timezone.utc).isoformat()

            if side == 'buy':
                # Create pending round-trip record
                rt_id = str(uuid.uuid4())
                rt = {
                    'id': rt_id,
                    'symbol': config['symbol'],
                    'buy_order_id': oid,
                    'buy_price': price,
                    'buy_amount': amount,
                    'buy_fee_eur': fee,
                    'buy_time': filled_at,
                    'bot_instance': 'GridBotV4',
                }
                state['orders']['pending_buys'] = state['orders'].get('pending_buys', {})
                state['orders']['pending_buys'][oid] = rt

                # Place corresponding sell
                target_sell_price = price * (1 + config['profit_per_grid_pct'])
                sell_amount = amount
                sell_order = await place_order(client, "sell", config['symbol'], round(target_sell_price, 2), sell_amount)
                if sell_order:
                    state['orders']['open_sell_ids'].append(sell_order['order_id'])
                    logger.info(f"  📈 SELL placed @ {round(target_sell_price, 2)}€ for BUY {price}€")

                logger.info(f"  ✅ BUY filled @ {price}€ | {amount:.5f} SOL")

            elif side == 'sell':
                # Complete round-trip
                buy_oid = status.get('info', {}).get('linked_order_id') or status.get('clientOrderId', '')
                # Find matching buy from pending
                pending_buys = state['orders'].get('pending_buys', {})
                matched_rt = None
                for boid, rt in list(pending_buys.items()):
                    if abs(rt['buy_price'] - price / (1 + config['profit_per_grid_pct'])) < 0.1:
                        matched_rt = rt
                        del pending_buys[boid]
                        break

                if matched_rt:
                    pnl = (price - matched_rt['buy_price']) * amount - matched_rt['buy_fee_eur'] - fee
                    rt_record = {
                        **matched_rt,
                        'sell_order_id': oid,
                        'sell_price': price,
                        'sell_amount': amount,
                        'sell_fee_eur': fee,
                        'sell_time': filled_at,
                        'pnl_eur': pnl,
                        'duration_sec': int((datetime.fromisoformat(filled_at) - datetime.fromisoformat(matched_rt['buy_time'])).total_seconds()),
                    }
                    log_round_trip(rt_record)

                    state['accounting']['net_pnl_eur'] += pnl
                    state['accounting']['total_fees_eur'] += matched_rt['buy_fee_eur'] + fee
                    state['accounting']['round_trips'] += 1
                    if pnl > 0:
                        state['accounting']['win_count'] += 1
                    else:
                        state['accounting']['loss_count'] += 1

                    logger.info(f"  💰 ROUND TRIP complete | P&L: €{pnl:.4f}")

                # Re-center: place new buy at original level
                if matched_rt:
                    new_buy_price = matched_rt['buy_price']
                    new_amount = matched_rt['buy_amount']
                    new_order = await place_order(client, "buy", config['symbol'], new_buy_price, new_amount)
                    if new_order:
                        state['orders']['open_buy_ids'].append(new_order['order_id'])
                        logger.info(f"  🔄 GRID RECENTER: BUY @ {new_buy_price}€")

            # Remove from open
            if oid in state['orders']['open_buy_ids']:
                state['orders']['open_buy_ids'].remove(oid)
            if oid in state['orders']['open_sell_ids']:
                state['orders']['open_sell_ids'].remove(oid)

            save_state(state)

        except ccxt.OrderNotFound:
            # Zombie order — remove from tracking
            if oid in state['orders']['open_buy_ids']:
                state['orders']['open_buy_ids'].remove(oid)
            if oid in state['orders']['open_sell_ids']:
                state['orders']['open_sell_ids'].remove(oid)
            logger.warning(f"  🧹 Zombie order {oid} removed")
        except Exception as e:
            logger.debug(f"Fill check {oid}: {e}")


async def rebalance_check(state, client, config, current_price):
    """Check for stale orders and re-balance if needed."""
    # Check if grid is too far from current price
    if state['grid']['buy_levels'] and current_price < min(state['grid']['buy_levels']) * 0.95:
        logger.warning(f"Price {current_price} dropped below grid range — re-centering")
        state['grid']['active'] = False
        state['risk']['paused'] = True
        state['risk']['pause_reason'] = "Grid out of range"
        save_state(state)


def save_state(state):
    write_state(state)


# ─── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logger.info("GridBotV4 starting...")
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        logger.info("GridBotV4 stopped by user")
    except Exception as e:
        logger.error(f"Fatal: {e}")
        raise
