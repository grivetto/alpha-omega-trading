#!/usr/bin/env python3
"""
DENARO V3 - RSI Mean Reversion Bot
Buy oversold, sell on recovery. High-frequency on ranging markets.
"""
import asyncio
import ccxt.async_support as ccxt
import logging
import os
import sys
import time
import json
from collections import deque

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('rsi_reversion.log'),
    ],
    force=True,
)
logger = logging.getLogger("RSIReversion")


class RSIReversion:
    def __init__(self, symbol="ADA/EUR"):
        self.exchange = None
        self.symbol = symbol
        self.asset = symbol.split("/")[0]

        # RSI config
        self.rsi_period = 14
        self.rsi_buy_threshold = 25    # Buy when RSI < 25 (oversold)
        self.rsi_sell_threshold = 55   # Sell when RSI > 55 (recovery)
        self.rsi_extreme_sell = 70     # Force sell when RSI > 70

        # Trading config
        self.order_size_eur = 8.0
        self.take_profit_pct = 0.015   # 1.5% take profit
        self.stop_loss_pct = 0.02      # 2% stop loss
        self.max_positions = 5
        self.candle_interval = '5m'
        self.candles_needed = 50

        # State
        self.positions = []
        self.total_profit = 0
        self.trades = 0
        self.wins = 0
        self.price_history = deque(maxlen=200)
        self.trades_file = ".tmp/rsi_trades.json"
        self._load_state()

    async def connect(self):
        api_key = ""
        api_secret = ""

        for env_path in [
            "/home/sergio/denaro/.env",
            os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"),
        ]:
            if os.path.exists(env_path):
                with open(env_path) as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("BINANCE_API_KEY="):
                            api_key = line.split("=", 1)[1].strip()
                        elif line.startswith("BINANCE_API_SECRET="):
                            api_secret = line.split("=", 1)[1].strip()
                if api_key:
                    break

        if not api_key:
            api_key = os.environ.get("BINANCE_API_KEY", "").strip()
            api_secret = os.environ.get("BINANCE_API_SECRET", "").strip()

        if not api_key:
            logger.error("No API keys found!")
            sys.exit(1)

        self.exchange = ccxt.binance({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
            'options': {'defaultType': 'spot'},
        })
        await self.exchange.load_markets()
        logger.info(f"RSI Reversion connected | {self.symbol}")

    async def close(self):
        if self.exchange:
            await self.exchange.close()

    async def get_balance(self):
        bal = await self.exchange.fetch_balance()
        eur = bal.get("EUR", {})
        asset = bal.get(self.asset, {})
        return {
            'EUR_free': eur.get('free', 0) or 0,
            'asset_free': asset.get('free', 0) or 0,
        }

    async def get_candles(self, limit=50):
        ohlcv = await self.exchange.fetch_ohlcv(self.symbol, self.candle_interval, limit=limit)
        return [c[4] for c in ohlcv]  # Close prices

    def calculate_rsi(self, prices, period=14):
        if len(prices) < period + 1:
            return 50

        gains = []
        losses = []
        for i in range(1, len(prices)):
            diff = prices[i] - prices[i-1]
            gains.append(max(0, diff))
            losses.append(max(0, -diff))

        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period

        if avg_loss == 0:
            return 100

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    async def buy(self, price, reason="RSI oversold"):
        bal = await self.get_balance()
        if bal['EUR_free'] < self.order_size_eur:
            return False

        amount = round(self.order_size_eur / price, 3)
        min_notional = 5.0
        if amount * price < min_notional:
            return False

        try:
            order = await self.exchange.create_order(self.symbol, 'limit', 'buy', amount, price)
            self.positions.append({
                'id': order['id'],
                'buy_price': price,
                'amount': amount,
                'eur_invested': amount * price,
                'time': time.time(),
                'stop_loss': round(price * (1 - self.stop_loss_pct), 6),
                'take_profit': round(price * (1 + self.take_profit_pct), 6),
            })
            logger.info(f"BUY @ {price} | amount={amount} | reason={reason} | positions={len(self.positions)}")
            return True
        except Exception as e:
            logger.error(f"Buy failed: {e}")
            return False

    async def sell(self, position, price, reason="Take profit"):
        try:
            sell_amount = round(position['amount'] * 0.997, 3)
            order = await self.exchange.create_order(self.symbol, 'limit', 'sell', sell_amount, price)
            profit = (price - position['buy_price']) * position['amount']
            self.total_profit += profit
            self.trades += 1
            if profit > 0:
                self.wins += 1

            self.positions.remove(position)
            self._record_trade(profit)

            logger.info(f"SELL @ {price} | buy={position['buy_price']} | profit={profit:.4f} | "
                        f"total={self.total_profit:.4f} | reason={reason}")
            return True
        except Exception as e:
            logger.error(f"Sell failed: {e}")
            return False

    async def check_positions(self, current_price):
        open_orders = await self.exchange.fetch_open_orders(self.symbol)
        open_ids = set(o['id'] for o in open_orders)

        for pos in list(self.positions):
            if pos['id'] not in open_ids:
                # Position filled, now manage exit
                # Check if we should exit immediately
                rsi = self.calculate_rsi(list(self.price_history))

                if current_price >= pos['take_profit']:
                    await self.sell(pos, current_price, "Take profit")
                elif current_price <= pos['stop_loss']:
                    await self.sell(pos, current_price, "Stop loss")
                elif rsi >= self.rsi_extreme_sell:
                    await self.sell(pos, current_price, "RSI overbought")
                elif rsi >= self.rsi_sell_threshold:
                    # Scale out - sell half
                    half_amount = round(pos['amount'] * 0.5 * 0.997, 3)
                    if half_amount > 0.001:
                        try:
                            await self.exchange.create_order(
                                self.symbol, 'limit', 'sell', half_amount, current_price
                            )
                            pos['amount'] = round(pos['amount'] - half_amount, 3)
                            profit = (current_price - pos['buy_price']) * half_amount
                            self.total_profit += profit
                            self.trades += 1
                            if profit > 0:
                                self.wins += 1
                            logger.info(f"PARTIAL SELL @ {current_price} | profit={profit:.4f} | remaining={pos['amount']}")
                        except Exception as e:
                            logger.error(f"Partial sell failed: {e}")

    async def run(self):
        await self.connect()
        logger.info(f"RSI Reversion started | RSI buy<{self.rsi_buy_threshold} sell>{self.rsi_sell_threshold}")

        try:
            while True:
                try:
                    # Get candles and calculate RSI
                    closes = await self.get_candles(self.candles_needed)
                    if len(closes) < self.rsi_period + 1:
                        await asyncio.sleep(5)
                        continue

                    for c in closes:
                        self.price_history.append(c)

                    rsi = self.calculate_rsi(closes, self.rsi_period)
                    current_price = closes[-1]

                    # Check existing positions
                    await self.check_positions(current_price)

                    # Buy signal: RSI oversold
                    if rsi < self.rsi_buy_threshold and len(self.positions) < self.max_positions:
                        buy_price = round(current_price * 0.999, 6)  # Slightly below market
                        await self.buy(buy_price, f"RSI={rsi:.1f}")

                    # Status
                    if int(time.time()) % 30 < 2:
                        win_rate = (self.wins / self.trades * 100) if self.trades > 0 else 0
                        logger.info(f"Price={current_price} | RSI={rsi:.1f} | positions={len(self.positions)} | "
                                    f"trades={self.trades} | wins={self.wins} ({win_rate:.0f}%) | "
                                    f"profit={self.total_profit:.4f}")

                    await asyncio.sleep(10)

                except Exception as e:
                    logger.error(f"Loop error: {e}", exc_info=True)
                    await asyncio.sleep(5)

        except KeyboardInterrupt:
            logger.info("Shutdown requested")
        finally:
            await self.close()

    def _record_trade(self, profit):
        try:
            os.makedirs(".tmp", exist_ok=True)
            trades = []
            if os.path.exists(self.trades_file):
                with open(self.trades_file, 'r') as f:
                    trades = json.load(f)
            trades.append({'profit': profit, 'time': time.time()})
            trades = trades[-100:]
            with open(self.trades_file, 'w') as f:
                json.dump(trades, f, indent=2)
        except Exception as e:
            logger.error(f"Trade record error: {e}")

    def _load_state(self):
        try:
            if os.path.exists(self.trades_file):
                with open(self.trades_file, 'r') as f:
                    trades = json.load(f)
                self.total_profit = sum(t.get('profit', 0) for t in trades)
                self.trades = len(trades)
        except Exception:
            pass


if __name__ == "__main__":
    symbol = sys.argv[1] if len(sys.argv) > 1 else "ADA/EUR"
    bot = RSIReversion(symbol)
    asyncio.run(bot.run())
