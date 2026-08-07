#!/usr/bin/env python3
"""
ShadowGrid v2.0 — Adaptive ATR + Momentum-Filtered Grid Bot.

Key Enhancements over v1.1:
1. Dynamic ATR-Based Spread: Grid spread automatically expands/contracts with volatility.
2. Momentum Filter: Pauses NEW buy order placement when market is trending (ADX > 25) or overbought/oversold (RSI outside 40-60).
3. Risk Controls: Hard stop at 15% max drawdown, daily loss limit freeze at 5%.
4. Dynamic Anchor Reset: Re-anchors grid if price drifts > 6%.
5. Performance Logging: Appends execution statistics to CSV for backtesting and reporting.
"""
from __future__ import annotations
import csv
import json
import logging
import math
import os
import signal
import sys
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from logging.handlers import RotatingFileHandler
from pathlib import Path
import threading
from typing import Optional, Tuple, List, Dict

import ccxt

# ─── Configuration from Environment ──────────────────────────────────────
EXCHANGE    = os.environ.get("EXCHANGE", "kraken")
SYMBOL      = os.environ.get("SYMBOL", "DOGE/EUR")
CURRENCY    = os.environ.get("CURRENCY", "EUR")
CAPITAL     = float(os.environ.get("CAPITAL", "100.0"))
LEVELS      = int(os.environ.get("LEVELS", "5"))
PER_LEVEL   = float(os.environ.get("PER_LEVEL", "0.20"))  # 20% capital per level
COOLDOWN    = int(os.environ.get("COOLDOWN", "30"))
FEE_PCT     = float(os.environ.get("FEE_PCT", "0.25"))
HEALTH_PORT = int(os.environ.get("HEALTH_PORT", "8911"))
LOG_FILE    = os.environ.get("LOG_FILE", f"/tmp/shadowgrid_v2_{EXCHANGE.lower()}_{SYMBOL.replace('/', '_').lower()}.log")
STATE_FILE  = os.environ.get("STATE_FILE", f"/tmp/shadowgrid_v2_{EXCHANGE.lower()}_{SYMBOL.replace('/', '_').lower()}_state.json")
CSV_FILE    = os.environ.get("CSV_FILE", f"/tmp/shadowgrid_v2_{EXCHANGE.lower()}_{SYMBOL.replace('/', '_').lower()}_perf.csv")
LIVE_MODE   = int(os.environ.get("LIVE_MODE", "0"))   # 0=paper, 1=live ccxt

# v2 New Config Parameters
USE_MOMENTUM_FILTER    = int(os.environ.get("USE_MOMENTUM_FILTER", "1"))
MAX_DRAWDOWN_PCT       = float(os.environ.get("MAX_DRAWDOWN_PCT", "0.15"))       # 15% hard stop
MAX_DAILY_LOSS_PCT     = float(os.environ.get("MAX_DAILY_LOSS_PCT", "0.05"))     # 5% daily freeze
ATR_SPREAD_MULTIPLIER  = float(os.environ.get("ATR_SPREAD_MULTIPLIER", "0.7"))  # ATR factor
MIN_SPREAD_PCT         = float(os.environ.get("MIN_SPREAD_PCT", "0.2"))          # Min 0.2%
MAX_SPREAD_PCT         = float(os.environ.get("MAX_SPREAD_PCT", "2.5"))          # Max 2.5%
DRIFT_PCT              = float(os.environ.get("DRIFT", "6.0"))                   # Reset grid if drift > 6%
TIMEFRAME              = os.environ.get("TIMEFRAME", "5m")                       # Candle timeframe for indicators

# ─── Logging Setup ────────────────────────────────────────────────────────
log = logging.getLogger("shadowgrid_v2")
log.setLevel(logging.INFO)
fh = RotatingFileHandler(LOG_FILE, maxBytes=3*1024*1024, backupCount=2)
fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
sh = logging.StreamHandler(sys.stdout)
sh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
log.handlers = [fh, sh]


def _make_exchange(live: bool = False):
    cls = getattr(ccxt, EXCHANGE.lower())
    cfg = {"enableRateLimit": True}
    if live:
        cfg["apiKey"] = os.environ.get(f"{EXCHANGE.upper()}_API", "")
        cfg["secret"] = os.environ.get(f"{EXCHANGE.upper()}_SECRET", "")
    return cls(cfg)


def _load_dotenv() -> None:
    for p in [Path(__file__).parent / ".env", Path.home() / "denaro" / ".env", Path.home() / "dev" / "alpha-omega-trading" / ".env"]:
        if p.exists():
            try:
                with open(p) as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            os.environ.setdefault(k.strip(), v.strip())
            except Exception:
                pass


# ─── Technical Indicators ─────────────────────────────────────────────────
def calculate_indicators(ohlcv: List[List[float]]) -> Tuple[float, float, float]:
    """
    Computes (ATR_pct, RSI_14, ADX_14) from OHLCV candles.
    ohlcv format: [[time, open, high, low, close, volume], ...]
    """
    if len(ohlcv) < 30:
        return (0.5, 50.0, 15.0)  # Default safe neutral values

    closes = [c[4] for c in ohlcv]
    highs  = [c[2] for c in ohlcv]
    lows   = [c[3] for c in ohlcv]

    # 1. ATR(14)
    tr_list = []
    for i in range(1, len(ohlcv)):
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
        tr_list.append(tr)
    
    atr14 = sum(tr_list[-14:]) / 14.0
    curr_price = closes[-1]
    atr_pct = (atr14 / curr_price) * 100.0 if curr_price > 0 else 0.5

    # 2. RSI(14)
    gains, losses = [], []
    for i in range(len(closes) - 14, len(closes)):
        diff = closes[i] - closes[i-1]
        gains.append(max(diff, 0.0))
        losses.append(max(-diff, 0.0))
    
    avg_gain = sum(gains) / 14.0
    avg_loss = sum(losses) / 14.0
    if avg_loss == 0:
        rsi14 = 100.0
    else:
        rs = avg_gain / avg_loss
        rsi14 = 100.0 - (100.0 / (1.0 + rs))

    # 3. Simplified ADX(14)
    plus_dm, minus_dm = [], []
    for i in range(len(ohlcv) - 14, len(ohlcv)):
        up_move = highs[i] - highs[i-1]
        down_move = lows[i-1] - lows[i]
        plus_dm.append(up_move if up_move > down_move and up_move > 0 else 0.0)
        minus_dm.append(down_move if down_move > up_move and down_move > 0 else 0.0)
    
    sum_tr = sum(tr_list[-14:]) or 1.0
    pdi = (sum(plus_dm) / sum_tr) * 100.0
    mdi = (sum(minus_dm) / sum_tr) * 100.0
    dx = (abs(pdi - mdi) / (pdi + mdi or 1.0)) * 100.0
    adx14 = dx  # Approximation over last 14 window

    return (atr_pct, rsi14, adx14)


# ─── State Management ─────────────────────────────────────────────────────
class State:
    def __init__(self):
        self.free_cash = CAPITAL
        self.locked_cash = 0.0
        self.coins = 0.0
        self.orders: list[dict] = []
        self.equity_peak = CAPITAL
        self.total_trades = 0
        self.winning_trades = 0
        self.realized_pnl = 0.0
        self.daily_pnl = 0.0
        self.last_day = datetime.now(timezone.utc).day
        self.start_ts = time.time()
        self.last_save = 0
        self._load()

    def _load(self):
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE) as f:
                    d = json.load(f)
                self.free_cash = d.get("free_cash", CAPITAL)
                self.locked_cash = d.get("locked_cash", 0)
                self.coins = d.get("coins", 0)
                self.equity_peak = d.get("equity_peak", CAPITAL)
                self.total_trades = d.get("total_trades", 0)
                self.winning_trades = d.get("winning_trades", 0)
                self.realized_pnl = d.get("realized_pnl", 0)
                self.daily_pnl = d.get("daily_pnl", 0)
                self.orders = d.get("orders", [])
                log.info(f"State loaded: free_cash={self.free_cash:.2f}, trades={self.total_trades}")
            except Exception:
                log.warning("State file corrupt, starting fresh")

    def check_daily_reset(self):
        today = datetime.now(timezone.utc).day
        if today != self.last_day:
            self.last_day = today
            self.daily_pnl = 0.0
            log.info("New calendar day: reset daily_pnl counter")

    def equity(self, price: float = 0) -> float:
        return self.free_cash + self.locked_cash + self.coins * price

    def save(self):
        now = time.time()
        if now - self.last_save < 5:
            return
        self.last_save = now
        try:
            d = {
                "free_cash": round(self.free_cash, 4),
                "locked_cash": round(self.locked_cash, 4),
                "coins": round(self.coins, 8),
                "equity_peak": round(self.equity_peak, 4),
                "total_trades": self.total_trades,
                "winning_trades": self.winning_trades,
                "realized_pnl": round(self.realized_pnl, 4),
                "daily_pnl": round(self.daily_pnl, 4),
                "orders": [{
                    "id": o["id"],
                    "side": o["side"],
                    "price": o["price"],
                    "amount": o["amount"],
                    "cost": o["cost"],
                } for o in self.orders],
            }
            with open(STATE_FILE, "w") as f:
                json.dump(d, f, indent=2)
        except Exception as e:
            log.error(f"Save state failed: {e}")


# ─── Grid Engine v2 ───────────────────────────────────────────────────────
class GridEngineV2:
    def __init__(self, state: State, ex=None, live: bool = False):
        self.state = state
        self.last_price: float = 0.0
        self.cycle_count = 0
        self.ccxt_errors = 0
        self.ex = ex
        self.live = live
        self._anchor = 0.0
        self.current_spread_pct = 0.5
        self.momentum_ok = True
        self.rsi_val = 50.0
        self.adx_val = 15.0
        self.is_frozen = False
        self.freeze_reason = ""
        self._init_csv()

    def _init_csv(self):
        if not os.path.exists(CSV_FILE):
            try:
                with open(CSV_FILE, "w", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow(["timestamp", "price", "equity", "realized_pnl", "drawdown_pct", "spread_pct", "rsi", "adx", "momentum_ok", "trades"])
            except Exception:
                pass

    def update_indicators(self):
        """Fetches OHLCV and computes dynamic spread + momentum filters."""
        try:
            ohlcv = self.ex.fetch_ohlcv(SYMBOL, timeframe=TIMEFRAME, limit=30)
            atr_pct, rsi, adx = calculate_indicators(ohlcv)
            self.rsi_val = rsi
            self.adx_val = adx
            
            # Dynamic spread = ATR * multiplier
            raw_spread = atr_pct * ATR_SPREAD_MULTIPLIER
            self.current_spread_pct = max(MIN_SPREAD_PCT, min(MAX_SPREAD_PCT, raw_spread))

            # Momentum check
            if USE_MOMENTUM_FILTER:
                self.momentum_ok = (40.0 <= rsi <= 60.0) and (adx < 25.0)
            else:
                self.momentum_ok = True
        except Exception as e:
            log.warning(f"Indicator update failed ({e}), keeping default spread={self.current_spread_pct:.2f}%")

    def _build_levels(self, price: float) -> list[dict]:
        levels = []
        spread = self.current_spread_pct / 100.0
        per_level_cash = CAPITAL * PER_LEVEL

        # BUY levels
        for i in range(LEVELS):
            lvl_price = price * (1.0 - spread * (i + 1))
            amount = per_level_cash / lvl_price if lvl_price > 0 else 0
            levels.append({"side": "buy", "price": lvl_price, "amount": amount, "cost": per_level_cash})

        # SELL levels
        for i in range(LEVELS):
            lvl_price = price * (1.0 + spread * (i + 1))
            amount = per_level_cash / price if price > 0 else 0
            levels.append({"side": "sell", "price": lvl_price, "amount": amount, "cost": per_level_cash})

        return levels

    def cycle(self, price: float) -> dict:
        self.last_price = price
        self.cycle_count += 1
        self.state.check_daily_reset()
        events = []

        # 1. Update indicators every 10 cycles
        if self.cycle_count % 10 == 1:
            self.update_indicators()

        equity = self.state.equity(price)
        if equity > self.state.equity_peak:
            self.state.equity_peak = equity

        drawdown_pct = (1.0 - equity / self.state.equity_peak) * 100.0 if self.state.equity_peak > 0 else 0.0

        # 2. Risk Controls Check
        if drawdown_pct >= (MAX_DRAWDOWN_PCT * 100.0):
            self.is_frozen = True
            self.freeze_reason = f"CRITICAL: Max drawdown hit ({drawdown_pct:.1f}% >= {MAX_DRAWDOWN_PCT*100:.1f}%)"
            log.critical(self.freeze_reason)
            return {"event": "FROZEN", "price": price, "equity": equity, "drawdown_pct": drawdown_pct, "orders": len(self.state.orders), "trades": self.state.total_trades}

        if self.state.daily_pnl <= -(CAPITAL * MAX_DAILY_LOSS_PCT):
            self.is_frozen = True
            self.freeze_reason = f"WARNING: Daily loss limit hit ({self.state.daily_pnl:.2f} <= -{CAPITAL*MAX_DAILY_LOSS_PCT:.2f})"
            log.warning(self.freeze_reason)
            return {"event": "DAILY_FREEZE", "price": price, "equity": equity, "drawdown_pct": drawdown_pct, "orders": len(self.state.orders), "trades": self.state.total_trades}

        self.is_frozen = False

        # 3. Anchor & Drift Reset Check
        if self._anchor == 0:
            self._anchor = price
        drift = abs(price - self._anchor) / self._anchor * 100.0 if self._anchor > 0 else 0.0
        if drift > DRIFT_PCT:
            events.append(f"DRIFT {drift:.1f}% > {DRIFT_PCT}% -> Re-anchoring grid")
            self.state.orders = []
            self._anchor = price

        # 4. Fill Simulation / Live Execution
        filled = []
        for i, o in enumerate(self.state.orders):
            if o["side"] == "buy" and price <= o["price"]:
                if self.state.free_cash < o["cost"]:
                    events.append(f"BUY skipped @ {o['price']:.6f} (insufficient cash)")
                    continue
                self.state.free_cash -= o["cost"]
                self.state.coins += o["amount"]
                self.state.total_trades += 1
                events.append(f"BUY filled @ {o['price']:.6f}")
                filled.append(i)
                # Paired sell level
                sell_price = o["price"] * (1.0 + self.current_spread_pct / 100.0)
                sell_amount = o["amount"] * (1.0 - FEE_PCT / 100.0)
                self.state.orders.append({
                    "id": f"s{self.cycle_count}_{len(self.state.orders)}",
                    "side": "sell",
                    "price": sell_price,
                    "amount": sell_amount,
                    "cost": sell_amount * sell_price,
                })
            elif o["side"] == "sell" and price >= o["price"]:
                if self.state.coins >= o["amount"]:
                    revenue = o["amount"] * o["price"]
                    self.state.coins -= o["amount"]
                    self.state.free_cash += revenue
                    buy_price = o["price"] / (1.0 + self.current_spread_pct / 100.0)
                    pnl = revenue - o["amount"] * buy_price
                    self.state.realized_pnl += pnl
                    self.state.daily_pnl += pnl
                    self.state.total_trades += 1
                    if pnl > 0:
                        self.state.winning_trades += 1
                    events.append(f"SELL filled @ {o['price']:.6f} PnL={pnl:+.4f}")
                    filled.append(i)

        for i in reversed(filled):
            self.state.orders.pop(i)

        # 5. Grid Placement (If momentum_ok or target_sells missing)
        target_buys = LEVELS - sum(1 for o in self.state.orders if o["side"] == "buy")
        target_sells = LEVELS - sum(1 for o in self.state.orders if o["side"] == "sell")

        if (target_buys > 0 and self.momentum_ok) or target_sells > 0:
            levels = self._build_levels(price)
            existing_prices = {(o["side"], round(o["price"], 6)) for o in self.state.orders}
            for lvl in levels:
                key = (lvl["side"], round(lvl["price"], 6))
                if key not in existing_prices:
                    if lvl["side"] == "buy" and target_buys > 0 and self.momentum_ok and self.state.free_cash >= lvl["cost"]:
                        self.state.orders.append({
                            "id": f"b{self.cycle_count}_{len(self.state.orders)}",
                            "side": "buy",
                            "price": lvl["price"],
                            "amount": lvl["amount"],
                            "cost": lvl["cost"],
                        })
                        target_buys -= 1
                    elif lvl["side"] == "sell" and target_sells > 0 and self.state.coins >= lvl["amount"]:
                        self.state.orders.append({
                            "id": f"s{self.cycle_count}_{len(self.state.orders)}",
                            "side": "sell",
                            "price": lvl["price"],
                            "amount": lvl["amount"],
                            "cost": lvl["cost"],
                        })
                        target_sells -= 1
        elif not self.momentum_ok and target_buys > 0:
            events.append(f"BUY creation paused by momentum filter (RSI={self.rsi_val:.1f}, ADX={self.adx_val:.1f})")

        # CSV Log
        if self.cycle_count % 30 == 0:
            self._write_csv(price, equity, drawdown_pct)

        return {
            "event": " | ".join(events) if events else "idle",
            "price": price,
            "equity": equity,
            "drawdown_pct": drawdown_pct,
            "orders": len(self.state.orders),
            "trades": self.state.total_trades,
        }

    def _write_csv(self, price: float, equity: float, drawdown_pct: float):
        try:
            with open(CSV_FILE, "a", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    datetime.now(timezone.utc).isoformat(),
                    round(price, 6),
                    round(equity, 2),
                    round(self.state.realized_pnl, 4),
                    round(drawdown_pct, 2),
                    round(self.current_spread_pct, 3),
                    round(self.rsi_val, 1),
                    round(self.adx_val, 1),
                    int(self.momentum_ok),
                    self.state.total_trades,
                ])
        except Exception:
            pass


# ─── Health Handler ───────────────────────────────────────────────────────
class HealthHandler(BaseHTTPRequestHandler):
    engine_ref = None
    state_ref = None

    def do_GET(self):
        engine = self.__class__.engine_ref
        state = self.__class__.state_ref
        price = engine.last_price if engine else 0
        equity = state.equity(price) if state else 0

        if self.path == "/health":
            body = json.dumps({
                "status": "frozen" if (engine and engine.is_frozen) else "healthy",
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "exchange": EXCHANGE,
                "symbol": SYMBOL,
                "equity": round(equity, 2),
                "realized_pnl": round(state.realized_pnl, 4) if state else 0,
                "daily_pnl": round(state.daily_pnl, 4) if state else 0,
                "current_spread_pct": round(engine.current_spread_pct, 3) if engine else 0.5,
                "momentum_ok": engine.momentum_ok if engine else True,
                "rsi": round(engine.rsi_val, 1) if engine else 50.0,
                "adx": round(engine.adx_val, 1) if engine else 15.0,
                "drawdown_pct": round((1.0 - equity / state.equity_peak) * 100, 2) if state and state.equity_peak > 0 else 0,
                "total_trades": state.total_trades if state else 0,
                "port": HEALTH_PORT,
            }, indent=2).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, fmt, *args):
        pass


# ─── Main Entry Point ─────────────────────────────────────────────────────
def main():
    log.info("=== ShadowGrid v2.0 Adaptive ATR + Momentum Filter ===")
    log.info(f"Exchange: {EXCHANGE} | Symbol: {SYMBOL} | Capital: {CAPITAL} {CURRENCY}")
    log.info(f"Config: ATR_Mult={ATR_SPREAD_MULTIPLIER}, Momentum_Filter={bool(USE_MOMENTUM_FILTER)}, Max_DD={MAX_DRAWDOWN_PCT*100}%")

    _load_dotenv()
    ex = _make_exchange(live=bool(LIVE_MODE))
    state = State()
    engine = GridEngineV2(state, ex=ex, live=bool(LIVE_MODE))

    if "--test" in sys.argv:
        log.info("Running single test cycle...")
        try:
            ticker = ex.fetch_ticker(SYMBOL)
            price = ticker.get("last") or ticker.get("close") or 100.0
            res = engine.cycle(price)
            log.info(f"Test cycle result: {res}")
        except Exception as e:
            log.error(f"Test failed: {e}")
        sys.exit(0)

    HealthHandler.engine_ref = engine
    HealthHandler.state_ref = state
    health = HTTPServer(("0.0.0.0", HEALTH_PORT), HealthHandler)
    hthread = threading.Thread(target=health.serve_forever, daemon=True)
    hthread.start()
    log.info(f"Health server on :{HEALTH_PORT}")

    shutdown_flag = False

    def graceful(sig, frame):
        nonlocal shutdown_flag
        log.warning(f"Signal {sig} — graceful shutdown...")
        shutdown_flag = True

    signal.signal(signal.SIGINT, graceful)
    signal.signal(signal.SIGTERM, graceful)

    while not shutdown_flag:
        try:
            ticker = ex.fetch_ticker(SYMBOL)
            price = ticker.get("last") or ticker.get("close")
            if not price or price <= 0:
                log.warning("Invalid price, skipping cycle")
                time.sleep(COOLDOWN)
                continue

            result = engine.cycle(price)
            if result["event"] != "idle" or engine.cycle_count % 10 == 0:
                log.info(f"[{engine.cycle_count:>6d}] price={price:.6f} eq={result['equity']:.2f} "
                         f"spread={engine.current_spread_pct:.2f}% RSI={engine.rsi_val:.1f} ADX={engine.adx_val:.1f} "
                         f"orders={result['orders']} trades={result['trades']} {result['event']}")

            if engine.cycle_count % 60 == 0:
                state.save()

        except Exception as e:
            log.error(f"Cycle error: {e}")
            time.sleep(COOLDOWN)

        for _ in range(int(min(COOLDOWN, 5))):
            if shutdown_flag:
                break
            time.sleep(1)

    state.save()
    health.shutdown()
    log.info("ShadowGrid v2 stopped.")


if __name__ == "__main__":
    main()
