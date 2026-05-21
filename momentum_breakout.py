#!/usr/bin/env python3
"""
DENARO V3 - Momentum Breakout Bot
Detects volume spikes + price breakouts, enters fast, exits on reversal.
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
        logging.FileHandler('momentum_breakout.log'),
    ],
    force=True,
)
logger = logging.getLogger("MomentumBreakout")


class MomentumBreakout:
    def __init__(self, symbol="SOL/EUR"):
        self.exchange = None
        self.symbol = symbol
        self.asset = symbol.split("/")[0]

        # Breakout config
        self.candle_interval = '3m'
        self.lookback_periods = 20
        self.volume_multiplier = 2.5     # Volume must be 2.5x average
        self.price_change_pct = 0.008    # 0.8% price change in 3 candles
        self.rsi_confirm = 55            # RSI must be > 55 for bullish momentum

        # Trading config
        self.order_size_eur = 8.0
        self.take_profit_pct = 0.02      # 2% take profit
        self.stop_loss_pct = 0.015       # 1.5% stop loss
        self.trailing_stop_pct = 0.01    # 1% trailing stop
        self.max_positions = 3
        self.cooldown_after_exit = 30    # Seconds cooldown after exit

        # State
        self.positions = []
        self.total_profit = 0
        self.trades = 0
        self.wins = 0
        self.last_exit_time = 0
        self.trades_file = ".tmp/momentum_trades.json"
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
        logger.info(f"Momentum Breakout connected | {self.symbol}")

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
        return {
            'open': [c[1] for c in ohlcv],
            'high': [c[2] for c in ohlcv],
            'low': [c[3] for c in ohlcv],
            'close': [c[4] for c in ohlcv],
            'volume': [c[5] for c in ohlcv],
        }

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
        return 100 - (100 / (1 + rs))

    def detect_breakout(self, candles):
        closes = candles['close']
        volumes = candles['volume']

        if len(closes) < self.lookback_periods + 3:
            return False, 0, 0

        # Average volume (excluding last 3 candles)
        avg_volume = sum(volumes[-self.lookback_periods-3:-3]) / self.lookback_periods
        current_volume = volumes[-1]

        # Volume spike check
        if current_volume < avg_volume * self.volume_multiplier:
            return False, 0, 0

        # Price momentum (last 3 candles)
        price_change = (closes[-1] - closes[-4]) / closes[-4]
        if price_change < self.price_change_pct:
            return False, 0, 0

        # RSI confirmation
        rsi = self.calculate_rsi(closes)
        if rsi < self.rsi_confirm:
            return False, 0, 0

        return True, price_change, rsi

    async def buy(self, price, reason="Breakout"):
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
                'highest_price': price,
                'stop_loss': round(price * (1 - self.stop_loss_pct), 6),
                'take_profit': round(price * (1 + self.take_profit_pct), 6),
            })
            logger.info(f"BUY @ {price} | amount={amount} | reason={reason} | positions={len(self.positions)}")
            return True
        except Exception as e:
            logger.error(f"Buy failed: {e}")
            return False

    async def sell(self, position, price, reason="Exit"):
        try:
            sell_amount = round(position['amount'] * 0.997, 3)
            if sell_amount < 0.001:
                self.positions.remove(position)
                return False

            order = await self.exchange.create_order(self.symbol, 'limit', 'sell', sell_amount, price)
            profit = (price - position['buy_price']) * position['amount']
            self.total_profit += profit
            self.trades += 1
            if profit > 0:
                self.wins += 1

            self.positions.remove(position)
            self._record_trade(profit)
            self.last_exit_time = time.time()

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
                # Position filled, manage exits
                pos['highest_price'] = max(pos['highest_price'], current_price)

                # Stop loss
                if current_price <= pos['stop_loss']:
                    await self.sell(pos, current_price, "Stop loss")
                    continue

                # Trailing stop
                trailing_stop = round(pos['highest_price'] * (1 - self.trailing_stop_pct), 6)
                if current_price <= trailing_stop and current_price > pos['buy_price']:
                    await self.sell(pos, current_price, f"Trailing stop @{current_price}")
                    continue

                # Take profit
                if current_price >= pos['take_profit']:
                    await self.sell(pos, current_price, "Take profit")
                    continue

    async def run(self):
        await self.connect()
        logger.info(f"Momentum Breakout started | vol={self.volume_multiplier}x | "
                    f"price={self.price_change_pct*100:.1f}% | RSI>{self.rsi_confirm}")

        try:
            while True:
                try:
                    # Cooldown after exit
                    if time.time() - self.last_exit_time < self.cooldown_after_exit:
                        await asyncio.sleep(2)
                        continue

                    # Get candles
                    candles = await self.get_candles(50)
                    current_price = candles['close'][-1]

                    # Check existing positions
                    await self.check_positions(current_price)

                    # Detect breakout
                    is_breakout, price_change, rsi = self.detect_breakout(candles)

                    if is_breakout and len(self.positions) < self.max_positions:
                        buy_price = round(current_price * 1.001, 2)  # Slightly above market
                        await self.buy(buy_price, f"Breakout +{price_change*100:.1f}% RSI={rsi:.1f}")

                    # Status
                    if int(time.time()) % 30 < 2:
                        win_rate = (self.wins / self.trades * 100) if self.trades > 0 else 0
                        logger.info(f"Price={current_price} | positions={len(self.positions)} | "
                                    f"trades={self.trades} | wins={self.wins} ({win_rate:.0f}%) | "
                                    f"profit={self.total_profit:.4f}")

                    await asyncio.sleep(5)

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
    symbol = sys.argv[1] if len(sys.argv) > 1 else "SOL/EUR"
    bot = MomentumBreakout(symbol)
    asyncio.run(bot.run())
