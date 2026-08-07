#!/usr/bin/env python3
"""
ShadowGrid v2.1 - Multi-Exchange Adaptive Grid Trading Bot

Features:
- ATR-adaptive spread (ATR(14) * multiplier, clamped)
- Momentum filter (ADX < 25, RSI 40-60) for grid entry
- HYBRID mode: scalper directional in trending markets (ADX > 25)
- Risk management: max 15% drawdown, 5% daily loss limit
- Dynamic grid re-anchoring (6% drift)
- Multi-exchange: Kraken + OKX with passphrase/EEA support
- Paper/Live mode per exchange
- Performance CSV logging
- Health HTTP endpoint
- State persistence
"""

import os
import sys
import json
import time
import signal
import logging
import argparse
import math
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from http.server import HTTPServer, BaseHTTPRequestHandler

import ccxt

# ============================================================
# CONFIGURATION FROM ENV
# ============================================================
EXCHANGE = os.getenv("EXCHANGE", "kraken").lower()
SYMBOL = os.getenv("SYMBOL", "DOGE/EUR")
CAPITAL = float(os.getenv("CAPITAL", "100"))
LEVELS = int(os.getenv("LEVELS", "5"))
SPREAD_PCT = float(os.getenv("SPREAD_PCT", "0.5"))  # base fallback
PER_LEVEL = float(os.getenv("PER_LEVEL", "0.2"))
COOLDOWN = int(os.getenv("COOLDOWN", "30"))
FEE_PCT = float(os.getenv("FEE_PCT", "0.2"))
HEALTH_PORT = int(os.getenv("HEALTH_PORT", "8910"))
LOG_FILE = os.getenv("LOG_FILE", "/tmp/shadowgrid_v2.log")
STATE_FILE = os.getenv("STATE_FILE", f"/tmp/shadowgrid_{SYMBOL.replace('/', '_')}_state.json")
LIVE_MODE = os.getenv("LIVE_MODE", "0") == "1"
DRIFT_PCT = float(os.getenv("DRIFT_PCT", "6.0"))

# NEW v2.1 features
USE_MOMENTUM_FILTER = os.getenv("USE_MOMENTUM_FILTER", "1") == "1"
MAX_DRAWDOWN_PCT = float(os.getenv("MAX_DRAWDOWN_PCT", "0.15"))
MAX_DAILY_LOSS_PCT = float(os.getenv("MAX_DAILY_LOSS_PCT", "0.05"))
ATR_SPREAD_MULTIPLIER = float(os.getenv("ATR_SPREAD_MULTIPLIER", "0.7"))
MIN_SPREAD_PCT = float(os.getenv("MIN_SPREAD_PCT", "0.2"))
MAX_SPREAD_PCT = float(os.getenv("MAX_SPREAD_PCT", "2.5"))
HYBRID_MODE = os.getenv("HYBRID_MODE", "0") == "1"  # NEW: scalper in trend

# Exchange-specific keys
KRAKEN_API_KEY = os.getenv("KRAKEN_API_KEY", "")
KRAKEN_API_SECRET = os.getenv("KRAKEN_API_SECRET", "")
OKX_API_KEY = os.getenv("OKX_API", "")
OKX_API_SECRET = os.getenv("OKX_SECRET", "")
OKX_PASSPHRASE = os.getenv("OKX_PASSPHRASE", "")

# ============================================================
# LOGGING SETUP
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.getLogger("shadowgrid")

# ============================================================
# STATE MANAGEMENT
# ============================================================
def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            log.warning(f"Failed to load state: {e}")
    return {
        "equity": CAPITAL,
        "realized_pnl": 0.0,
        "trades_count": 0,
        "wins": 0,
        "losses": 0,
        "open_orders": {},
        "grid_anchor": None,
        "grid_levels": [],
        "daily_loss": 0.0,
        "day_start_equity": CAPITAL,
        "last_day": datetime.now(timezone.utc).date().isoformat(),
    }


def save_state(state: dict):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        log.error(f"Failed to save state: {e}")


# ============================================================
# EXCHANGE INITIALIZATION
# ============================================================
def create_exchange(exchange_name: str = None) -> ccxt.Exchange:
    """Create exchange instance with proper credentials."""
    ex_name = (exchange_name or EXCHANGE).lower()
    
    if ex_name == "kraken":
        config = {
            'enableRateLimit': True,
            'options': {
                'fetchMinOrderAmounts': False,
            }
        }
        if LIVE_MODE and KRAKEN_API_KEY and KRAKEN_API_SECRET:
            config['apiKey'] = KRAKEN_API_KEY
            config['secret'] = KRAKEN_API_SECRET
            log.info("Kraken: LIVE mode with API keys")
        else:
            log.info("Kraken: PAPER mode (no API keys or LIVE_MODE=0)")
        return ccxt.kraken(config)
    
    elif ex_name == "okx":
        config = {
            'enableRateLimit': True,
        }
        # OKX requires passphrase for EEA compliance
        if LIVE_MODE and OKX_API_KEY and OKX_API_SECRET:
            config['apiKey'] = OKX_API_KEY
            config['secret'] = OKX_API_SECRET
            config['password'] = OKX_PASSPHRASE  # CRITICAL for OKX EEA
            log.info("OKX: LIVE mode with API keys + passphrase")
        else:
            # Paper mode: still need public access for tickers
            log.info("OKX: PAPER mode (public endpoints only)")
        return ccxt.okx(config)
    
    else:
        raise ValueError(f"Unsupported exchange: {ex_name}")


# ============================================================
# TECHNICAL INDICATORS
# ============================================================
def compute_indicators(ohlcv: List[List[float]]) -> Tuple[float, float, float]:
    """Compute ATR(14), RSI(14), ADX(14) from OHLCV data."""
    if len(ohlcv) < 15:
        return 0.0, 50.0, 0.0
    
    closes = [c[4] for c in ohlcv]
    highs = [c[2] for c in ohlcv]
    lows = [c[3] for c in ohlcv]
    
    # True Range & ATR(14)
    tr_values = []
    for i in range(1, len(ohlcv)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i-1]),
            abs(lows[i] - closes[i-1])
        )
        tr_values.append(tr)
    atr = sum(tr_values[-14:]) / min(14, len(tr_values))
    atr_pct = (atr / closes[-1]) * 100 if closes[-1] > 0 else 0.0
    
    # RSI(14)
    gains = []
    losses = []
    for i in range(1, min(15, len(closes))):
        diff = closes[-i] - closes[-i-1]
        if diff > 0:
            gains.append(diff)
            losses.append(0.0)
        else:
            gains.append(0.0)
            losses.append(abs(diff))
    avg_gain = sum(gains) / len(gains) if gains else 0.0
    avg_loss = sum(losses) / len(losses) if losses else 0.0
    rs = avg_gain / avg_loss if avg_loss > 0 else 100.0
    rsi = 100 - (100 / (1 + rs))
    
    # ADX(14) - simplified using DI+/DI-
    plus_di = 0.0
    minus_di = 0.0
    tr_sum = 0.0
    for i in range(1, min(15, len(ohlcv))):
        up_move = highs[-i] - highs[-i-1]
        down_move = lows[-i-1] - lows[-i]
        tr = max(highs[-i] - lows[-i],
                 abs(highs[-i] - closes[-i-1]),
                 abs(lows[-i] - closes[-i-1]))
        tr_sum += tr
        if up_move > down_move and up_move > 0:
            plus_di += up_move
        elif down_move > up_move and down_move > 0:
            minus_di += down_move
    
    if tr_sum > 0:
        plus_di = (plus_di / tr_sum) * 100
        minus_di = (minus_di / tr_sum) * 100
        dx = abs(plus_di - minus_di) / (plus_di + minus_di) * 100 if (plus_di + minus_di) > 0 else 0
    else:
        dx = 0.0
    adx = dx  # simplified single-period ADX
    
    return atr_pct, rsi, adx


# ============================================================
# GRID BUILDING
# ============================================================
def build_levels(anchor_price: float, spread_pct: float, levels: int, per_level: float) -> List[Dict]:
    """Build grid levels around anchor price."""
    half_spread = spread_pct / 200.0  # convert to decimal
    grid = []
    for i in range(-levels, levels + 1):
        if i == 0:
            continue
        price = anchor_price * (1 + i * half_spread)
        side = "buy" if i < 0 else "sell"
        grid.append({
            "price": round(price, 6),
            "side": side,
            "amount": round(per_level * CAPITAL / price, 6),
            "filled": False,
            "order_id": None
        })
    return grid


def compute_dynamic_spread(atr_pct: float) -> float:
    """Compute spread from ATR with clamping."""
    spread = atr_pct * ATR_SPREAD_MULTIPLIER
    return max(MIN_SPREAD_PCT, min(MAX_SPREAD_PCT, spread))


# ============================================================
# HEALTH SERVER
# ============================================================
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            response = json.dumps({
                "status": "healthy",
                "symbol": SYMBOL,
                "exchange": EXCHANGE,
                "mode": "live" if LIVE_MODE else "paper",
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            self.wfile.write(response.encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass

def start_health_server(port: int):
    server = HTTPServer(('0.0.0.0', port), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    log.info(f"Health server started on port {port}")
    return server


# ============================================================
# MAIN TRADING LOGIC
# ============================================================
class ShadowGridBot:
    def __init__(self):
        self.exchange = create_exchange()
        self.state = load_state()
        self.running = True
        self.cycle_count = 0
        self.last_reanchor = time.time()
        
        # Initialize grid anchor
        if self.state.get("grid_anchor") is None:
            ticker = self.exchange.fetch_ticker(SYMBOL)
            self.state["grid_anchor"] = ticker['last']
            self.state["grid_levels"] = build_levels(
                self.state["grid_anchor"], SPREAD_PCT, LEVELS, PER_LEVEL
            )
            save_state(self.state)
        
        # Daily loss tracking
        today = datetime.now(timezone.utc).date().isoformat()
        if self.state.get("last_day") != today:
            self.state["daily_loss"] = 0.0
            self.state["day_start_equity"] = self.state.get("equity", CAPITAL)
            self.state["last_day"] = today
            save_state(self.state)
    
    def check_risk_limits(self) -> bool:
        """Check if risk limits are breached."""
        equity = self.state.get("equity", CAPITAL)
        drawdown = (CAPITAL - equity) / CAPITAL if CAPITAL > 0 else 0
        if drawdown >= MAX_DRAWDOWN_PCT:
            log.critical(f"MAX DRAWDOWN BREACHED: {drawdown*100:.2f}% >= {MAX_DRAWDOWN_PCT*100:.0f}%")
            return False
        
        daily_loss = self.state.get("daily_loss", 0.0)
        day_start = self.state.get("day_start_equity", CAPITAL)
        if day_start > 0 and daily_loss >= MAX_DAILY_LOSS_PCT * day_start:
            log.critical(f"DAILY LOSS LIMIT: {daily_loss:.2f} >= {MAX_DAILY_LOSS_PCT*100:.0f}% of {day_start:.2f}")
            return False
        
        return True
    
    def fetch_market_data(self) -> Tuple[float, float, float, float, float]:
        """Fetch ticker and compute indicators. Returns (price, atr_pct, rsi, adx, spread)."""
        ticker = self.exchange.fetch_ticker(SYMBOL)
        price = ticker['last']
        
        # Fetch OHLCV for indicators
        ohlcv = self.exchange.fetch_ohlcv(SYMBOL, timeframe='15m', limit=20)
        atr_pct, rsi, adx = compute_indicators(ohlcv)
        
        spread = compute_dynamic_spread(atr_pct) if atr_pct > 0 else SPREAD_PCT
        
        return price, atr_pct, rsi, adx, spread
    
    def check_momentum(self, rsi: float, adx: float) -> Tuple[bool, str]:
        """Check momentum filter. Returns (ok, reason)."""
        if not USE_MOMENTUM_FILTER:
            return True, "disabled"
        
        if adx > 25:
            return False, f"ADX {adx:.1f} > 25 (strong trend)"
        if rsi < 40 or rsi > 60:
            return False, f"RSI {rsi:.1f} outside [40,60]"
        return True, f"RSI {rsi:.1f}, ADX {adx:.1f}"
    
    def check_hybrid_signal(self, rsi: float, adx: float, price: float, anchor: float) -> Tuple[str, float]:
        """Hybrid mode: return (direction, tp_multiplier) for trend scalping."""
        if not HYBRID_MODE or adx <= 25:
            return "none", 1.0
        
        # Trend direction from price vs anchor and RSI
        price_vs_anchor = (price - anchor) / anchor
        
        if rsi > 55 and price_vs_anchor > 0:
            return "long", 1.5  # Long bias in uptrend
        elif rsi < 45 and price_vs_anchor < 0:
            return "short", 1.5  # Short bias in downtrend
        return "none", 1.0
    
    def place_orders(self, price: float, spread: float, momentum_ok: bool, hybrid_dir: str):
        """Place grid orders based on current state."""
        if not self.check_risk_limits():
            return
        
        # Cancel stale orders
        for level in self.state["grid_levels"]:
            if level["order_id"] and not level["filled"]:
                try:
                    self.exchange.cancel_order(level["order_id"], SYMBOL)
                except Exception:
                    pass
        
        # Rebuild levels if spread changed significantly
        current_spread = spread
        anchor = self.state["grid_anchor"]
        
        # Check re-anchor condition (6% drift)
        drift = abs(price - anchor) / anchor * 100
        if drift >= DRIFT_PCT:
            log.info(f"RE-ANCHOR: price drifted {drift:.2f}% from {anchor:.6f} to {price:.6f}")
            self.state["grid_anchor"] = price
            anchor = price
            self.state["grid_levels"] = build_levels(anchor, current_spread, LEVELS, PER_LEVEL)
        
        # If in hybrid trend mode, allow directional scalping
        if not momentum_ok and hybrid_dir != "none":
            log.info(f"HYBRID MODE: {hybrid_dir.upper()} trend scalping active (ADX>25)")
            # Place single directional order with tighter TP
            side = "buy" if hybrid_dir == "long" else "sell"
            offset = spread / 200.0 * 0.5  # half spread for scalping
            order_price = price * (1 - offset) if side == "buy" else price * (1 + offset)
            amount = PER_LEVEL * CAPITAL / price
            
            try:
                if LIVE_MODE:
                    order = self.exchange.create_limit_order(SYMBOL, side, amount, order_price)
                    log.info(f"HYBRID {side.upper()} @ {order_price:.6f} amount={amount:.6f} id={order['id']}")
                else:
                    log.info(f"HYBRID PAPER {side.upper()} @ {order_price:.6f} amount={amount:.6f}")
            except Exception as e:
                log.error(f"Hybrid order failed: {e}")
            return
        
        # Normal grid mode (only if momentum OK)
        if not momentum_ok:
            log.info(f"MOMENTUM BLOCK: Grid frozen - {hybrid_dir}")
            return
        
        # Place grid orders
        for level in self.state["grid_levels"]:
            if level["filled"]:
                continue
            
            side = level["side"]
            order_price = level["price"]
            amount = level["amount"]
            
            # Check if price is near our level (within 0.1%)
            if side == "buy" and price <= order_price * 1.001:
                try:
                    if LIVE_MODE:
                        order = self.exchange.create_limit_order(SYMBOL, "buy", amount, order_price)
                        level["order_id"] = order['id']
                    else:
                        level["order_id"] = f"paper_{int(time.time()*1000)}"
                    log.info(f"GRID BUY @ {order_price:.6f} amount={amount:.6f}")
                except Exception as e:
                    log.error(f"Grid buy failed: {e}")
            elif side == "sell" and price >= order_price * 0.999:
                try:
                    if LIVE_MODE:
                        order = self.exchange.create_limit_order(SYMBOL, "sell", amount, order_price)
                        level["order_id"] = order['id']
                    else:
                        level["order_id"] = f"paper_{int(time.time()*1000)}"
                    log.info(f"GRID SELL @ {order_price:.6f} amount={amount:.6f}")
                except Exception as e:
                    log.error(f"Grid sell failed: {e}")
    
    def check_fills(self):
        """Check for filled orders and update state."""
        for level in self.state["grid_levels"]:
            if not level["order_id"] or level["filled"]:
                continue
            
            try:
                if LIVE_MODE:
                    order = self.exchange.fetch_order(level["order_id"], SYMBOL)
                    if order['status'] == 'closed':
                        level["filled"] = True
                        filled_price = order['average'] or level["price"]
                        filled_amount = order['filled'] or level["amount"]
                        cost = filled_price * filled_amount
                        fee = cost * FEE_PCT / 100
                        
                        if level["side"] == "buy":
                            self.state["equity"] -= cost + fee
                        else:
                            self.state["equity"] += cost - fee
                            # Realized PnL on sell
                            buy_price = self.state["grid_anchor"] * (1 - SPREAD_PCT/200.0)
                            pnl = (filled_price - buy_price) * filled_amount - fee
                            self.state["realized_pnl"] += pnl
                            if pnl > 0:
                                self.state["wins"] += 1
                            else:
                                self.state["losses"] += 1
                            
                            # Update daily loss tracking
                            day_start = self.state.get("day_start_equity", CAPITAL)
                            self.state["daily_loss"] = day_start - self.state["equity"]
                        
                        self.state["trades_count"] += 1
                        log.info(f"FILL {level['side'].upper()} @ {filled_price:.6f} PnL={pnl:.4f} Equity={self.state['equity']:.2f}")
                else:
                    # Paper mode: simulate fills when price crosses level
                    ticker = self.exchange.fetch_ticker(SYMBOL)
                    current_price = ticker['last']
                    if level["side"] == "buy" and current_price <= level["price"] * 1.001:
                        level["filled"] = True
                        cost = level["price"] * level["amount"]
                        fee = cost * FEE_PCT / 100
                        self.state["equity"] -= cost + fee
                        log.info(f"PAPER FILL BUY @ {level['price']:.6f} Equity={self.state['equity']:.2f}")
                    elif level["side"] == "sell" and current_price >= level["price"] * 0.999:
                        level["filled"] = True
                        cost = level["price"] * level["amount"]
                        fee = cost * FEE_PCT / 100
                        self.state["equity"] += cost - fee
                        buy_price = self.state["grid_anchor"] * (1 - SPREAD_PCT/200.0)
                        pnl = (level["price"] - buy_price) * level["amount"] - fee
                        self.state["realized_pnl"] += pnl
                        if pnl > 0:
                            self.state["wins"] += 1
                        else:
                            self.state["losses"] += 1
                        day_start = self.state.get("day_start_equity", CAPITAL)
                        self.state["daily_loss"] = day_start - self.state["equity"]
                        self.state["trades_count"] += 1
                        log.info(f"PAPER FILL SELL @ {level['price']:.6f} PnL={pnl:.4f} Equity={self.state['equity']:.2f}")
            except Exception as e:
                log.debug(f"Fill check error: {e}")
    
    def log_performance(self):
        """Log performance to CSV."""
        perf_file = f"/tmp/shadowgrid_v2_{SYMBOL.replace('/', '_')}_perf.csv"
        write_header = not os.path.exists(perf_file)
        
        equity = self.state.get("equity", CAPITAL)
        realized = self.state.get("realized_pnl", 0.0)
        trades = self.state.get("trades_count", 0)
        wins = self.state.get("wins", 0)
        win_rate = wins / trades * 100 if trades > 0 else 0
        drawdown = (CAPITAL - equity) / CAPITAL * 100 if CAPITAL > 0 else 0
        
        with open(perf_file, "a") as f:
            if write_header:
                f.write("timestamp,equity,realized_pnl,trades,win_rate,drawdown_pct,spread_used,momentum_ok\n")
            f.write(f"{datetime.now(timezone.utc).isoformat()},{equity:.4f},{realized:.4f},{trades},{win_rate:.2f},{drawdown:.2f},{SPREAD_PCT},{USE_MOMENTUM_FILTER}\n")
    
    def run_cycle(self):
        """Execute one trading cycle."""
        self.cycle_count += 1
        
        try:
            price, atr_pct, rsi, adx, spread = self.fetch_market_data()
            momentum_ok, momentum_reason = self.check_momentum(rsi, adx)
            hybrid_dir, tp_mult = self.check_hybrid_signal(rsi, adx, price, self.state["grid_anchor"])
            
            log.info(f"Cycle {self.cycle_count}: {SYMBOL} @ {price:.6f} | ATR={atr_pct:.2f}% RSI={rsi:.1f} ADX={adx:.1f} | Spread={spread:.2f}% | Momentum={'OK' if momentum_ok else 'BLOCK'}({momentum_reason}) | Hybrid={hybrid_dir.upper()}")
            
            self.check_fills()
            self.place_orders(price, spread, momentum_ok, hybrid_dir)
            
            # Log performance every 30 cycles
            if self.cycle_count % 30 == 0:
                self.log_performance()
            
            save_state(self.state)
            
        except Exception as e:
            log.error(f"Cycle error: {e}")
    
    def run(self):
        """Main loop."""
        log.info(f"=== ShadowGrid v2.1 Starting ===")
        log.info(f"Symbol: {SYMBOL} | Exchange: {EXCHANGE} | Mode: {'LIVE' if LIVE_MODE else 'PAPER'}")
        log.info(f"Capital: {CAPITAL} | Levels: {LEVELS} | Base Spread: {SPREAD_PCT}%")
        log.info(f"Momentum Filter: {'ON' if USE_MOMENTUM_FILTER else 'OFF'} | Hybrid Mode: {'ON' if HYBRID_MODE else 'OFF'}")
        log.info(f"Max Drawdown: {MAX_DRAWDOWN_PCT*100:.0f}% | Max Daily Loss: {MAX_DAILY_LOSS_PCT*100:.0f}%")
        log.info(f"Health server: http://0.0.0.0:{HEALTH_PORT}/health")
        
        start_health_server(HEALTH_PORT)
        
        while self.running:
            self.run_cycle()
            time.sleep(COOLDOWN)
        
        log.info("ShadowGrid stopped")


def signal_handler(signum, frame):
    log.info(f"Signal {signum} received, shutting down...")
    sys.exit(0)


def main():
    parser = argparse.ArgumentParser(description="ShadowGrid v2.1 - Adaptive Grid Trading Bot")
    parser.add_argument("--test", action="store_true", help="Run one cycle and exit")
    args = parser.parse_args()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    bot = ShadowGridBot()
    
    if args.test:
        log.info("TEST MODE: Running single cycle")
        bot.run_cycle()
        log.info("TEST MODE: Complete")
    else:
        bot.run()

if __name__ == "__main__":
    main()
