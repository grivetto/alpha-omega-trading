#!/usr/bin/env python3
"""
DENARO CONFIG SUPERVISOR - Portfolio Manager & Risk Controller
Inspired by TradingAgents Risk Management team.
Reads market_state.json + grid performance, adjusts grid_config.json dynamically.
Runs every 10 minutes.
"""
import os, sys, json, time, logging, shutil
from datetime import datetime
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))
TMP_DIR = os.path.join(BASE_DIR, ".tmp")
MARKET_STATE_FILE = os.path.join(TMP_DIR, "market_state.json")
GRID_CONFIG_FILE = os.path.join(BASE_DIR, "grid_config.json")
GRID_CONFIG_BACKUP = os.path.join(BASE_DIR, "grid_config.supervisor_backup.json")
LAST_ADJUST_FILE = os.path.join(TMP_DIR, "last_supervisor_adjust.json")

LOG_FILE = os.path.join(BASE_DIR, "config_supervisor.log")
logging.basicConfig(level=logging.INFO, format='%(asctime)s - SUPERVISOR - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()])
logger = logging.getLogger("Supervisor")

MIN_ADJUST_INTERVAL = 300  # Minimum 5 minutes between adjustments

def read_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except: return None

def write_json(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)

def get_performance():
    """Read profit optimizer trades for performance metrics"""
    profit_optimizer_trades_file = os.path.join(BASE_DIR, ".tmp", "profit_optimizer_trades.json")
    if not os.path.exists(profit_optimizer_trades_file):
        return None
    try:
        with open(profit_optimizer_trades_file, 'r') as f:
            trades = json.load(f)
        if not trades:
            return None
        total_trades = len(trades)
        # Use last 10 trades for recent performance (consistent with original logic)
        recent_trades = trades[-10:] if len(trades) >= 10 else trades
        recent_profit = sum(t['profit'] for t in recent_trades)
        avg_profit = recent_profit / len(recent_trades) if recent_trades else 0
        return {
            'total_orders': total_trades,
            'recent_profit': round(recent_profit, 4),
            'avg_profit_per_trade': round(avg_profit, 4)
        }
    except Exception as e:
        logger.error(f"Failed to read profit optimizer trades: {e}")
        return None
def get_portfolio_snapshot():
    """Quick estimate of total portfolio from binance"""
    import hmac, hashlib, urllib.parse
    import requests as rq
    api_key = os.getenv('BINANCE_API_KEY')
    api_secret = os.getenv('BINANCE_API_SECRET')
    if not api_key: return None
    ts = int(time.time() * 1000)
    sig = hmac.new(api_secret.encode(), urllib.parse.urlencode({'timestamp': ts}).encode(), hashlib.sha256).hexdigest()
    bal = rq.get('https://api.binance.com/api/v3/account', params={'timestamp': ts, 'signature': sig},
                  headers={'X-MBX-APIKEY': api_key}, timeout=10)
    if bal.status_code != 200: return None
    data = bal.json()
    pr = rq.get('https://api.binance.com/api/v3/ticker/price', timeout=10)
    prices = {p['symbol']: float(p['price']) for p in pr.json()} if pr.status_code == 200 else {}
    total = 0.0
    details = {}
    for b in data['balances']:
        free = float(b['free'])
        locked = float(b['locked'])
        qty = free + locked
        if qty <= 0: continue
        if b['asset'] == 'EUR':
            total += qty
            details['EUR'] = qty
        elif b['asset'] + 'EUR' in prices:
            val = qty * prices[b['asset'] + 'EUR']
            total += val
            details[b['asset']] = round(val, 2)
    return {'total_eur': round(total, 2), 'details': details}

def calculate_optimal_config(market_state, perf, portfolio):
    """Calculate optimal grid parameters based on market conditions"""
    current = read_json(GRID_CONFIG_FILE)
    if not current:
        logger.error("Cannot read grid_config.json")
        return None

    # Default: keep current values, apply safe adjustments
    opt = current.copy()
    regime = market_state.get('regime', 'NEUTRAL') if market_state else 'NEUTRAL'
    vol_class = market_state.get('volatility', {}).get('class', 'NORMAL') if market_state else 'NORMAL'
    signals = market_state.get('signals', {}) if market_state else {}
    total_eur = portfolio.get('total_eur', 200) if portfolio else 200

    # === Capital-based adjustment ===
    eur_balance = 0.0
    if portfolio:
        details = portfolio.get('details', {})
        if isinstance(details, dict):
            eur_balance = details.get('EUR', 0)
            if isinstance(eur_balance, dict):
                eur_balance = 0
    elif market_state:
        # Estimate from market state
        eur_balance = 80.0
    else:
        eur_balance = 100.0
    max_invest = min(eur_balance * 0.85, 150)
    opt['max_total_invested'] = round(max_invest, 1)

    # === Regime-based adjustments ===
    if regime == 'STRONG_BULL':
        # Uptrend: wider range, higher base, more levels
        opt['grid_range_pct'] = signals.get('suggested_grid_range', 0.012)
        opt['base_order_eur'] = 18.0
        opt['grid_levels'] = 6
        opt['martingale_factor'] = 1.15
        opt['profit_per_grid'] = 0.0025
        logger.info("STRONG_BULL: expanding grid, increasing orders")
    elif regime == 'BULL':
        opt['grid_range_pct'] = signals.get('suggested_grid_range', 0.012)
        opt['base_order_eur'] = 17.0
        opt['grid_levels'] = 5
        opt['martingale_factor'] = 1.15
        opt['profit_per_grid'] = 0.0025
        logger.info("BULL: normal operation")
    elif regime == 'NEUTRAL':
        opt['grid_range_pct'] = signals.get('suggested_grid_range', 0.010)
        opt['base_order_eur'] = 15.0
        opt['grid_levels'] = 5
        opt['martingale_factor'] = 1.12
        opt['profit_per_grid'] = 0.0025
        logger.info("NEUTRAL: standard parameters")
    elif regime == 'BEAR':
        # Downtrend: reduce exposure, tighter grid
        opt['grid_range_pct'] = signals.get('suggested_grid_range', 0.008)
        opt['base_order_eur'] = 12.0
        opt['grid_levels'] = 4
        opt['martingale_factor'] = 1.10
        opt['profit_per_grid'] = 0.0020
        logger.info("BEAR: reducing exposure, tightening grid")
    elif regime == 'STRONG_BEAR':
        # Retrenchment: minimum exposure
        opt['grid_range_pct'] = 0.006
        opt['base_order_eur'] = 10.0
        opt['grid_levels'] = 3
        opt['martingale_factor'] = 1.08
        opt['profit_per_grid'] = 0.0015
        opt['max_total_invested'] = min(opt['max_total_invested'], 60)
        logger.info("STRONG_BEAR: retrenching, minimum exposure")

    # === Volatility-based range adjustment ===
    if vol_class == 'HIGH':
        opt['grid_range_pct'] = round(min(opt['grid_range_pct'] * 1.3, 0.025), 3)
        opt['atr_spacing_factor'] = 3.0
        logger.info(f"HIGH volatility: widened range to {opt['grid_range_pct']*100:.1f}%")
    elif vol_class == 'LOW':
        opt['grid_range_pct'] = round(max(opt['grid_range_pct'] * 0.8, 0.005), 3)
        opt['atr_spacing_factor'] = 2.0
        logger.info(f"LOW volatility: narrowed range to {opt['grid_range_pct']*100:.1f}%")

    # === Profit-based adjustment ===
    if perf and perf.get('total_orders', 0) > 5:
        if perf['recent_profit'] > 0:
            logger.info(f"Positive profit ({perf['recent_profit']:.2f}€), maintaining settings")
        else:
            logger.info(f"Recent losses ({perf['recent_profit']:.2f}€), keeping conservative")

    return opt

def main():
    logger.info("=" * 50)
    logger.info("CONFIG SUPERVISOR RUNNING")

    # Check if we adjusted recently
    last_adjust = read_json(LAST_ADJUST_FILE)
    if last_adjust and time.time() - last_adjust.get('timestamp', 0) < MIN_ADJUST_INTERVAL:
        logger.info(f"Skipped: last adjust was {int((time.time()-last_adjust['timestamp'])/60)}m ago")
        return

    # Gather all inputs
    market_state = read_json(MARKET_STATE_FILE)
    if not market_state:
        logger.warning("Market state not available. Run market_technician.py first.")
    else:
        logger.info(f"Market: {market_state.get('regime', 'N/A')} @ {market_state.get('price', 0)}€")

    perf = get_performance()
    if perf:
        logger.info(f"Grid perf: {perf['total_orders']} orders, recent profit {perf['recent_profit']:.2f}€")

    portfolio = get_portfolio_snapshot()
    if portfolio:
        logger.info(f"Portfolio: {portfolio['total_eur']}€")

    # Calculate optimal config
    opt = calculate_optimal_config(market_state, perf, portfolio)
    if not opt:
        logger.error("Cannot calculate optimal config")
        return

    # Read current config to compare  
    current = read_json(GRID_CONFIG_FILE)
    if not current:
        logger.error("Cannot read current config")
        return

    # Only write if something changed significantly
    changes = []
    for key in ('grid_levels', 'base_order_eur', 'max_total_invested', 'grid_range_pct',
                 'martingale_factor', 'profit_per_grid', 'atr_spacing_factor'):
        if key in opt and key in current:
            diff = abs(opt[key] - current[key]) if isinstance(opt[key], (int, float)) else 0
            threshold = 0.1 if key in ('base_order_eur', 'max_total_invested') else \
                        0.01 if key in ('grid_range_pct', 'profit_per_grid', 'martingale_factor', 'atr_spacing_factor') else 0.5
            if diff > threshold and opt[key] != current[key]:
                changes.append(f"{key}: {current[key]} -> {opt[key]}")

    if changes:
        # Backup current config
        shutil.copy2(GRID_CONFIG_FILE, GRID_CONFIG_BACKUP)
        write_json(GRID_CONFIG_FILE, opt)
        write_json(LAST_ADJUST_FILE, {'timestamp': time.time(), 'changes': changes,
                                       'regime': market_state.get('regime') if market_state else None})
        logger.info(f"Config updated: {' | '.join(changes)}")
    else:
        logger.info("No changes needed")

    logger.info("Supervisor cycle complete")

if __name__ == '__main__':
    main()
