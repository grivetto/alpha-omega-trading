#!/usr/bin/env python3
"""
DENARO V3 - Volume Spike Hunter
Detects sudden volume increases and trades the momentum
"""
import asyncio
import ccxt.async_support as ccxt
import logging
import os
import sys
import time
import statistics

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('volume_hunter.log'),
    ],
    force=True,
)
logger = logging.getLogger("VolumeHunter")


class VolumeSpikeHunter:
    def __init__(self, symbols=None):
        self.exchange = None
        self.symbols = symbols or ["SOL/EUR", "ETH/EUR", "BTC/EUR", "ADA/EUR"]

        # Config
        self.vol_threshold = 3.0  # Volume must be 3x average
        self.order_size_eur = 5.0
        self.tp_pct = 0.005  # 0.5% take profit
        self.sl_pct = 0.003  # 0.3% stop loss
        self.max_hold_sec = 120  # 2 minutes max
        self.lookback_candles = 20

        # State
        self.positions = {}
        self.total_profit = 0
        self.trades = 0
        self.volume_history = {sym: [] for sym in self.symbols}

    async def connect(self):
        api_key = os.environ.get("BINANCE_API_KEY", "")
        api_secret = os.environ.get("BINANCE_API_SECRET", "")

        if not api_key:
            env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")
            if os.path.exists(env_path):
                with open(env_path) as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            os.environ[k.strip()] = v.strip()
                api_key = os.environ.get("BINANCE_API_KEY", "")
                api_secret = os.environ.get("BINANCE_API_SECRET", "")

        self.exchange = ccxt.binance({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
            'options': {'defaultType': 'spot'},
        })
        await self.exchange.load_markets()
        logger.info(f"Volume Hunter connected | monitoring {len(self.symbols)} pairs")

    async def close(self):
        if self.exchange:
            await self.exchange.close()

    async def get_balance(self):
        bal = await self.exchange.fetch_balance()
        return bal.get("EUR", {}).get("free", 0) or 0

    async def run(self):
        await self.connect()
        logger.info(f"Volume Hunter started | threshold={self.vol_threshold}x")

        try:
            while True:
                try:
                    eur_free = await self.get_balance()

                    for symbol in self.symbols:
                        # Skip if already in position for this symbol
                        if symbol in self.positions:
                            await self._manage_position(symbol)
                            continue

                        # Skip if not enough EUR
                        if eur_free < self.order_size_eur:
                            continue

                        # Fetch recent candles
                        ohlcv = await self.exchange.fetch_ohlcv(symbol, '1m', limit=self.lookback_candles + 1)
                        if len(ohlcv) < self.lookback_candles:
                            continue

                        volumes = [c[5] for c in ohlcv]
                        current_vol = volumes[-1]
                        avg_vol = statistics.mean(volumes[:-1])

                        if avg_vol <= 0:
                            continue

                        vol_ratio = current_vol / avg_vol

                        if vol_ratio >= self.vol_threshold:
                            # Volume spike detected!
                            closes = [c[4] for c in ohlcv]
                            price = closes[-1]
                            prev_price = closes[-2]
                            direction = "UP" if price > prev_price else "DOWN"

                            # Only trade if price moving with volume
                            if direction == "UP":
                                await self._enter_long(symbol, price, vol_ratio)
                            else:
                                # For spot, we can't short - skip
                                logger.info(f"Volume spike DOWN on {symbol} - skipping (spot only)")

                    await asyncio.sleep(3)

                except Exception as e:
                    logger.error(f"Loop error: {e}", exc_info=True)
                    await asyncio.sleep(5)

        except KeyboardInterrupt:
            logger.info("Shutdown requested")
        finally:
            await self.close()

    async def _enter_long(self, symbol, price, vol_ratio):
        """Enter long position on volume spike"""
        try:
            asset = symbol.split("/")[0]
            amount = round(self.order_size_eur / price, 3)
            if amount < 0.001:
                return

            # Buy at market
            order = await self.exchange.create_order(symbol, 'market', 'buy', amount)
            fill_price = order.get('average', price)

            # Place TP order
            tp_price = round(fill_price * (1 + self.tp_pct), 2)
            tp_amount = round(amount * 0.997, 3)
            tp_order = await self.exchange.create_order(symbol, 'limit', 'sell', tp_amount, tp_price)

            self.positions[symbol] = {
                'entry_price': fill_price,
                'amount': amount,
                'tp_id': tp_order['id'],
                'tp_price': tp_price,
                'time': time.time(),
                'vol_ratio': vol_ratio,
            }

            logger.info(f"VOLUME SPIKE ENTRY {symbol} @ {fill_price} | vol={vol_ratio:.1f}x | TP={tp_price}")

        except Exception as e:
            logger.error(f"Entry failed {symbol}: {e}")

    async def _manage_position(self, symbol):
        """Manage open position"""
        pos = self.positions.get(symbol)
        if not pos:
            return

        # Check time stop
        hold_time = time.time() - pos['time']
        if hold_time > self.max_hold_sec:
            await self._exit_position(symbol, "TIME")
            return

        # Check current price
        ticker = await self.exchange.fetch_ticker(symbol)
        current_price = ticker.get('last', 0)
        if current_price <= 0:
            return

        # Check TP/SL
        pnl = (current_price - pos['entry_price']) / pos['entry_price']

        # Take profit
        if pnl >= self.tp_pct:
            await self._exit_position(symbol, "TP")
            return

        # Stop loss
        if pnl <= -self.sl_pct:
            await self._exit_position(symbol, "SL")
            return

    async def _exit_position(self, symbol, reason):
        """Exit position"""
        pos = self.positions.pop(symbol, None)
        if not pos:
            return

        try:
            # Cancel TP order
            try:
                await self.exchange.cancel_order(pos['tp_id'], symbol)
            except Exception:
                pass

            # Market sell
            order = await self.exchange.create_order(symbol, 'market', 'sell', pos['amount'])
            exit_price = order.get('average', pos['entry_price'])

            pnl = (exit_price - pos['entry_price']) * pos['amount']
            self.total_profit += pnl
            self.trades += 1

            logger.info(f"EXIT {symbol} | reason={reason} | entry={pos['entry_price']} exit={exit_price} | pnl={pnl:.4f}")

        except Exception as e:
            logger.error(f"Exit failed {symbol}: {e}")


if __name__ == "__main__":
    symbols = sys.argv[1:] if len(sys.argv) > 1 else ["SOL/EUR", "ETH/EUR"]
    bot = VolumeSpikeHunter(symbols)
    asyncio.run(bot.run())
