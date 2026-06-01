#!/usr/bin/env python3
"""
Simple back‑test for the Gaussian Channel bot.

- Reads configuration from /home/sergio/denaro/squadra/config/gaussian.json
- Downloads historical 1‑minute klines for SYMBOL (default BTCUSDT) from Binance
- Computes a rolling SMA and standard deviation over a configurable window
- Generates LONG/SHORT/NEUTRAL signals when price exits the SMA ± sigma*std band
- Simulates fixed‑size trades (€5 notional per trade) with a fixed exit after
  `exit_bars` (default 5) or when an opposite signal appears
- Calculates basic performance metrics: total return, max drawdown, win rate
- Writes a JSON report to /home/sergio/denaro/reports/gaussian_backtest_report.json
"""

import json
import sys
import time
from datetime import datetime
from statistics import mean, stdev
from typing import List, Tuple

import requests

# ----------------------------------------------------------------------
# Load configuration
# ----------------------------------------------------------------------
CONFIG_PATH = "/home/sergio/denaro/squadra/config/gaussian.json"
if not os.path.exists(CONFIG_PATH):
    sys.stderr.write("Config file not found\n")
    sys.exit(1)

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    cfg = json.load(f)

SYMBOL = cfg.get("symbol", "BTCUSDT")
WINDOW = cfg.get("window", 50)                # look‑back period for channel
SIGMA = cfg.get("sigma", 2)                   # standard‑deviation multiplier
ENTRY_SIGMA = cfg.get("entry_sigma", 2.5)     # sigma threshold for entry
MAX_POS_EUR = cfg.get("max_position_eur", 5)  # notional per trade (unused in back‑test)
MAX_DRAWDOWN_EUR = cfg.get("max_drawdown_eur", 5.0)

# ----------------------------------------------------------------------
# Binance public REST – historical klines
# ----------------------------------------------------------------------
BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"
HEADERS = {"Accept": "APPLICATION/json"}

def fetch_klines(symbol: str, interval: str = "1m", limit: int = 500) -> List[List]:
    """Return list of klines (Open‑High‑Low‑Close‑...)."""
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    try:
        r = requests.get(BINANCE_KLINES_URL, params=params, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        sys.stderr.write(f"Error fetching klines: {e}\n")
        sys.exit(1)


# ----------------------------------------------------------------------
# Signal generation
# ----------------------------------------------------------------------
def generate_signal(prices: List[float]) -> Tuple[str, float]:
    """
    Return (signal, price) where signal is one of 'LONG', 'SHORT', 'NEUTRAL'
    and price is the current price used for the signal.
    """
    if len(prices) < WINDOW:
        return "NEUTRAL", prices[-1] if prices else 0.0

    ma = mean(prices[-WINDOW:])
    try:
        sigma_val = stdev(prices[-WINDOW:])
        if sigma_val == 0:
            sigma_val = 1.0
    except Exception:
        sigma_val = 1.0

    upper = ma + SIGMA * sigma_val
    lower = ma - SIGMA * sigma_val
    cur = prices[-1]

    if cur < lower:
        return "LONG", cur
    if cur > upper:
        return "SHORT", cur
    return "NEUTRAL", cur


# ----------------------------------------------------------------------
# Back‑test engine
# ----------------------------------------------------------------------
def backtest(klines: List[List]) -> dict:
    """
    Run the back‑test and return a dict with performance metrics.
    """
    # Extract close prices (index 4)
    close_prices = [float(k[4]) for k in klines]

    signals = []
    for i in range(WINDOW - 1, len(close_prices)):
        # Use a moving window of the last WINDOW points up to i (inclusive)
        window_prices = close_prices[i - WINDOW + 1 : i + 1]
        sig, price = generate_signal(window_prices)
        signals.append((i, sig, price))

    # Simulate trades
    position = None          # None or dict with 'side', 'entry_price', 'entry_idx'
    trade_log = []           # list of dicts with trade details
    cash = 0.0               # cumulative PnL in EUR
    peak_value = 0.0         # for drawdown calc
    max_drawdown = 0.0
    wins = 0
    total_trades = 0

    EXIT_BARS = 5  # max holding period in bars

    for idx, sig, price in signals:
        # Check if we need to close an existing position due to exit_bars
        if position:
            age = idx - position["entry_idx"]
            if age >= EXIT_BARS:
                # Close at current price
                exit_price = price
                profit = (exit_price - position["entry_price"]) * (
                    position["size"] / position["entry_price"]
                )
                cash += profit
                trade_log.append(
                    {
                        "type": "close",
                        "side": position["side"],
                        "entry_price": position["entry_price"],
                        "exit_price": exit_price,
                        "size": position["size"],
                        "profit": profit,
                    }
                )
                total_trades += 1
                if profit > 0:
                    wins += 1
                position = None

        # Entry logic
        if sig in ("LONG", "SHORT") and not position:
            # Fixed notional of MAX_POS_EUR EUR
            # For simplicity, assume we buy/sell 1 unit of the base asset;
            # the notional is approximated by entry_price * 1.
            size = MAX_POS_EUR / price  # quantity that costs ~MAX_POS_EUR
            position = {
                "side": sig,
                "entry_price": price,
                "size": size,
                "entry_idx": idx,
            }
            entry_peak = price
            peak_value = max(peak_value, cash + entry_peak)  # rough equity estimate

        # Track equity for drawdown
        equity = cash
        drawdown = peak_value - equity
        if drawdown > max_drawdown:
            max_drawdown = drawdown

    # Final equity & drawdown after last bar
    equity = cash
    drawdown = peak_value - equity
    if drawdown > max_drawdown:
        max_drawdown = drawdown

    # ------------------------------------------------------------------
    # Performance summary
    # ------------------------------------------------------------------
    report = {
        "symbol": SYMBOL,
        "window": WINDOW,
        "sigma": SIGMA,
        "entry_sigma": ENTRY_SIGMA,
        "total_trades": total_trades,
        "wins": wins,
        "win_rate_pct": (wins / total_trades * 100) if total_trades else 0.0,
        "total_pnl_eur": round(cash, 2),
        "max_drawdown_eur": round(max_drawdown, 2),
        "final_equity_eur": round(cash, 2),
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }

    # Write report
    report_path = "/home/sergio/denaro/reports/gaussian_backtest_report.json"
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    return report


# ----------------------------------------------------------------------
# Main entry point
# ----------------------------------------------------------------------
if __name__ == "__main__":
    import os

    klines = fetch_klines(SYMBOL, interval="1m", limit=500)
    report = backtest(klines)
    print("Back‑test report written to /home/sergio/denaro/reports/gaussian_backtest_report.json")
    print(json.dumps(report, indent=2))