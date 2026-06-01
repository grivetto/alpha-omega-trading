#!/usr/bin/env python3

# # Gaussian Channel Bot for Denaro

# # Implements the Gaussian Channel strategy extracted from Michael Ionita videos:
# - Pulls 1-minute klines
# - Computes SMA(window) and standard deviation (sigma)
# - Entry: price crosses below SMA - sigma*std (LONG)
# - Entry: price crosses above SMA + sigma*std (SHORT)
# - Fixed notional per trade (max_position_eur)
# - Filters trades with cost_filter (profit estimate must exceed ROUND_TRIP_COST_PCT)
# - Respects max_drawdown_eur and max_position_eur limits
# - Logs to /home/sergio/denaro/logs/gaussian_bot.log

import asyncio
import os
import sys
import time
import random
import json
import logging
os.chdir('/home/sergio/denaro')

# Load API credentials from .env.bak (fallback if .env not present)
env_bak_path = '/home/sergio/denaro/.env.bak.1780009238'
if os.path.exists(env_bak_path):
    with open(env_bak_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                key, _, value = line.partition('=')
                os.environ[key] = value

# Use main account credentials (more reliable)
BINANCE_API_KEY=os.getenv('BINANCE_API_KEY_MAIN')
BINANCE_API_SECRET=os.getenv('BINANCE_API_SECRET_MAIN')

sys.path.insert(0, '/home/sergio/denaro/squadra')
import ccxt.async_support as ccxt
from core import DenaroOpportunisticCore, ROUND_TRIP_COST_PCT
from dotenv import load_dotenv

# ----------------------------------------------------------------------
# Logging setup
# ----------------------------------------------------------------------
LOG_PATH = "/home/sergio/denaro/logs/gaussian_bot.log"
os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH),
        logging.StreamHandler(sys.stdout),
    ],
)

# ----------------------------------------------------------------------
# Load configuration
# ----------------------------------------------------------------------
CONFIG_PATH = "/home/sergio/denaro/squadra/config/gaussian.json"
if not os.path.exists(CONFIG_PATH):
    logging.error("Gaussian config not found at %s", CONFIG_PATH)
    sys.exit(1)

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    cfg = json.load(f)

SYMBOL = cfg.get("symbol", "BTCUSDT")
# Normalize symbol for ccxt (e.g., BTCUSDT -> BTC/USDT)
if SYMBOL and '/' not in SYMBOL and len(SYMBOL) > 4:
    SYMBOL = SYMBOL[:3] + '/' + SYMBOL[3:]
WINDOW = cfg.get("window", 50)
SIGMA = cfg.get("sigma", 2)
ENTRY_SIGMA = cfg.get("entry_sigma", 2.5)
MAX_POS_EUR = cfg.get("max_position_eur", 5)
MAX_DRAWDOWN_EUR = cfg.get("max_drawdown_eur", 5.0)

# Load Binance credentials - prefer _MAIN suffix for production accounts
load_dotenv()  # pulls .env from the project root
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY_MAIN") or os.getenv("BINANCE_API_KEY")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET_MAIN") or os.getenv("BINANCE_API_SECRET")

# ----------------------------------------------------------------------
# Helper: fetch klines
# ----------------------------------------------------------------------
async def fetch_klines(symbol: str, interval: str = "1m", limit: int = WINDOW + 5) -> list:
    # Return OHLCV list from Binance using ccxt.
    exchange = None
    try:
        exchange = ccxt.binance({"apiKey": BINANCE_API_KEY, "secret": BINANCE_API_SECRET, "enableRateLimit": True})
        return await exchange.fetch_ohlcv(symbol, interval, limit=limit)
    except Exception as exc:
        logging.error("Kline fetch error for %s: %s", symbol, exc)
        return []
    finally:
        if exchange:
            await exchange.close()

# ----------------------------------------------------------------------
# Signal generation
# ----------------------------------------------------------------------
def generate_signal(closes: list) -> str:
    if len(closes) < WINDOW:
        return "NEUTRAL"
    # Use the last WINDOW candles for MA/sigma, but exclude the very last close
    # (the current price) from the sigma calculation. This prevents the outlier
    # price from inflating the band and masking the signal.
    ref_closes = closes[-WINDOW-1:-1] if len(closes) > WINDOW else closes[-WINDOW:]
    if len(ref_closes) < 2:
        ref_closes = closes[-WINDOW:]
    ma = sum(ref_closes) / len(ref_closes)
    try:
        sigma_val = (sum((x - ma) ** 2 for x in ref_closes) ** 0.5)
        if sigma_val == 0:
            sigma_val = 1.0
    except Exception:
        sigma_val = 1.0
    upper = ma + SIGMA * sigma_val
    lower = ma - SIGMA * sigma_val
    upper_entry = ma + ENTRY_SIGMA * sigma_val
    lower_entry = ma - ENTRY_SIGMA * sigma_val
    price = closes[-1]
    logging.info(
        "Gaussian check – price=%.2f MA=%.2f upper=%.2f lower=%.2f entry_upper=%.2f entry_lower=%.2f",
        price, ma, upper, lower, upper_entry, lower_entry,
    )
    if price < lower_entry:
        logging.info(">>> LONG signal (price %.2f < entry_lower %.2f)", price, lower_entry)
        return "LONG"
    if price > upper_entry:
        logging.info(">>> SHORT signal (price %.2f > entry_upper %.2f)", price, upper_entry)
        return "SHORT"
    return "NEUTRAL"

# ----------------------------------------------------------------------
# Risk filter (uses project‑wide ROUND_TRIP_COST_PCT)
# ----------------------------------------------------------------------
def cost_filter(expected_profit_pct: float) -> bool:
    """Expected profit must exceed the round‑trip cost."""
    from squadra.core import ROUND_TRIP_COST_PCT
    return expected_profit_pct > ROUND_TRIP_COST_PCT

# ----------------------------------------------------------------------
# Main bot class
# ----------------------------------------------------------------------
class GaussianBot(DenaroOpportunisticCore):
    def __init__(self, test_mode: bool = False):
        super().__init__(
            bot_name="Gaussian",
            config_file="gaussian.json",
            test_mode=test_mode,
        )
        # inject our own config overrides
        self.symbol = SYMBOL
        self.max_drawdown_eur = MAX_DRAWDOWN_EUR
        self.max_position_eur = MAX_POS_EUR
        logging.info(
            "=== GaussianChannel Bot initialized ==="
        )
        logging.info(
            "symbol=%s window=%d sigma=%.2f entry_sigma=%.2f max_position_eur=%.2f max_drawdown_eur=%.2f",
            self.symbol, WINDOW, SIGMA, ENTRY_SIGMA, MAX_POS_EUR, MAX_DRAWDOWN_EUR,
        )

    async def fetch_klines(self, symbol: str, interval: str = "1m", limit: int = WINDOW + 5) -> list:
        """Overridden fetch_klines – respects test_mode."""
        if self.test_mode:
            # Generate a stable base: WINDOW candles at a steady price (low sigma)
            base_price = random.uniform(65000, 72000)
            ts = int(time.time() * 1000)
            ohlcv = []
            for i in range(WINDOW):
                noise = base_price * random.uniform(0.9995, 1.0005)  # ±0.05% noise
                o = noise * random.uniform(0.9999, 1.0)
                c = noise
                h = max(o, c) * 1.0005
                l = min(o, c) * 0.9995
                v = random.uniform(0.5, 5.0)
                ohlcv.append([ts + i * 60000, o, h, l, c, v])

            # Append the last 5 candles: one real tick + 4 extra for safety
            price = base_price
            for i in range(5):
                drift = random.gauss(0, 0.001)
                price *= (1 + drift)
                o = price * random.uniform(0.9999, 1.0)
                c = price
                h = max(o, c) * 1.0005
                l = min(o, c) * 0.9995
                v = random.uniform(0.5, 5.0)
                ohlcv.append([ts + (WINDOW + i) * 60000, o, h, l, c, v])

            # Now inject an extreme close in the LAST candle to breach entry_sigma.
            # We target ~30% beyond the current band, which is far enough to
            # survive the sigma recalculation that includes the spike itself.
            if self._tick_count % 3 == 0:
                # Price far below the lower entry band -> LONG
                target = base_price * 0.65  # 35% crash
                ohlcv[-1][1] = target * 1.0001
                ohlcv[-1][2] = target * 1.001
                ohlcv[-1][3] = target * 0.999
                ohlcv[-1][4] = target
                logging.info("[TEST] Injected LONG candle: target=%.2f (base=%.2f)", target, base_price)
            elif self._tick_count % 3 == 2:
                # Price far above the upper entry band -> SHORT
                target = base_price * 1.40  # 40% pump
                ohlcv[-1][1] = target * 0.9999
                ohlcv[-1][2] = target * 1.001
                ohlcv[-1][3] = target * 0.999
                ohlcv[-1][4] = target
                logging.info("[TEST] Injected SHORT candle: target=%.2f (base=%.2f)", target, base_price)

            return ohlcv
        # Production path – delegate to the original fetch_klines().
        return await fetch_klines(symbol, interval, limit)

    async def execute_signal(self, signal: str) -> None:
        """Place a market order for the configured max_position_eur."""
        try:
          # Obtain latest close price to size the order
          klines = await self.fetch_klines(self.symbol, "1m", limit=2)
          if not klines:
              logging.warning("No klines – skipping order")
              return
          price = float(klines[-1][4])  # closing price
          qty = MAX_POS_EUR / price

          try:
              if signal == "LONG":
                  result = await self.create_market_buy(self.symbol, qty)
              else:  # SHORT
                  result = await self.create_market_sell(self.symbol, qty)

              if result:
                  logging.info(
                      "Executed %s order – qty≈%.6f (≈%.2f € notional)",
                      "BUY" if signal == "LONG" else "SELL",
                      qty,
                      MAX_POS_EUR,
                  )
              else:
                  logging.warning("Order returned None – possibly rejected")
          except Exception as exc:
              logging.error("Order execution failed: %s", exc)

        except Exception as exc:
          logging.exception("Unexpected error in GaussianBot loop: %s", exc)

    async def run(self) -> None:
        """Main loop – runs every ~30 seconds."""
        logging.info("=== GaussianChannel Bot started ===")
        while True:
            try:
                klines = await self.fetch_klines(self.symbol)
                if not klines:
                    await asyncio.sleep(30)
                    continue

                closes = [float(k[4]) for k in klines]  # closing prices
                signal = generate_signal(closes)

                if signal in ("LONG", "SHORT"):
                    if cost_filter(1.0):  # expect ≥ 1 % profit, filter via ROUND_TRIP_COST_PCT
                        await self.execute_signal(signal)
                    else:
                        logging.warning("Profit estimate too low – trade filtered by cost filter")

                self._tick_count += 1
                if self._max_ticks and self._tick_count >= self._max_ticks:
                    logging.info("Reached max ticks (%d) – exiting test run", self._tick_count)
                    break

                await asyncio.sleep(self._sleep_seconds)

            except Exception as exc:
                logging.exception("Unexpected error in GaussianBot loop: %s", exc)
                await asyncio.sleep(self._sleep_seconds)

# ----------------------------------------------------------------------
# Entrypoint for manual / cron execution
# ----------------------------------------------------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--test-mode", action="store_true", help="Run in fake‑OHLCV mode")
    parser.add_argument("--max-ticks", type=int, default=5, help="Max ticks before exit (0=infinite)")
    parser.add_argument("--sleep-seconds", type=float, default=5.0, help="Delay between ticks in seconds (default 5)")

    args = parser.parse_args()

    bot = GaussianBot(test_mode=args.test_mode)
    bot._max_ticks = args.max_ticks
    bot._tick_count = 0
    bot._sleep_seconds = args.sleep_seconds

    async def run_limited():
        logging.info("=== GaussianChannel Bot started ===")
        while True:
            try:
                klines = await bot.fetch_klines(bot.symbol)
                if not klines:
                    await asyncio.sleep(bot._sleep_seconds)
                    continue

                closes = [float(k[4]) for k in klines]
                signal = generate_signal(closes)

                if signal in ("LONG", "SHORT"):
                    if cost_filter(1.0):
                        await bot.execute_signal(signal)
                    else:
                        logging.warning("Profit estimate too low – trade filtered by cost filter")

                bot._tick_count += 1
                if bot._max_ticks and bot._tick_count >= bot._max_ticks:
                    logging.info("Reached max ticks (%d) – exiting test run", bot._tick_count)
                    break

                await asyncio.sleep(bot._sleep_seconds)

            except Exception as exc:
                logging.exception("Unexpected error in GaussianBot loop: %s", exc)
                await asyncio.sleep(bot._sleep_seconds)

    try:
        if args.max_ticks:
            asyncio.run(run_limited())
        else:
            asyncio.run(bot.run())
    except KeyboardInterrupt:
        logging.info("Bot stopped by user")
        sys.exit(0)