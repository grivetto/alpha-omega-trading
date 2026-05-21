#!/usr/bin/env python3
"""
DENARO V3 - Spread Scalper
Exploits bid/ask spread in real-time for micro-profits
"""
import asyncio
import ccxt.async_support as ccxt
import logging
import os
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('spread_scalper.log'),
    ],
    force=True,
)
logger = logging.getLogger("SpreadScalper")


class SpreadScalper:
    def __init__(self, symbol="SOL/EUR"):
        self.exchange = None
        self.symbol = symbol
        self.asset = symbol.split("/")[0]

        # Config
        self.min_spread_pct = 0.08  # 0.08% minimum spread to trade
        self.order_size_eur = 5.0
        self.target_profit_pct = 0.04  # 0.04% per scalp
        self.max_positions = 3
        self.cooldown_sec = 5

        # State
        self.positions = []
        self.total_profit = 0
        self.scalps = 0
        self.last_trade = 0

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
        logger.info(f"Spread Scalper connected | {self.symbol}")

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

    async def run(self):
        await self.connect()
        logger.info(f"Spread Scalper started | min_spread={self.min_spread_pct}%")

        try:
            while True:
                try:
                    # Check cooldown
                    if time.time() - self.last_trade < self.cooldown_sec:
                        await asyncio.sleep(0.5)
                        continue

                    # Max positions check
                    if len(self.positions) >= self.max_positions:
                        await asyncio.sleep(1)
                        continue

                    # Get order book
                    ob = await self.exchange.fetch_order_book(self.symbol, limit=5)
                    if not ob.get('bids') or not ob.get('asks'):
                        await asyncio.sleep(1)
                        continue

                    best_bid = ob['bids'][0][0]
                    best_ask = ob['asks'][0][0]

                    if best_bid <= 0 or best_ask <= 0:
                        await asyncio.sleep(1)
                        continue

                    spread_pct = (best_ask - best_bid) / best_bid * 100

                    if spread_pct < self.min_spread_pct:
                        await asyncio.sleep(0.5)
                        continue

                    # Spread is wide enough - scalp it
                    bal = await self.get_balance()
                    if bal['EUR_free'] < self.order_size_eur:
                        await asyncio.sleep(2)
                        continue

                    # Buy at bid
                    amount = round(self.order_size_eur / best_bid, 3)
                    if amount < 0.001:
                        await asyncio.sleep(1)
                        continue

                    try:
                        buy_order = await self.exchange.create_order(self.symbol, 'limit', 'buy', amount, best_bid)
                        logger.info(f"SCALP BUY @ {best_bid} | spread={spread_pct:.3f}%")

                        # Immediately place sell at ask
                        sell_price = round(best_ask * (1 - self.target_profit_pct * 0.1), 2)  # Slightly below ask for faster fill
                        sell_amount = round(amount * 0.997, 3)

                        sell_order = await self.exchange.create_order(self.symbol, 'limit', 'sell', sell_amount, sell_price)
                        self.positions.append({
                            'buy_id': buy_order['id'],
                            'sell_id': sell_order['id'],
                            'buy_price': best_bid,
                            'sell_price': sell_price,
                            'amount': amount,
                            'time': time.time(),
                        })
                        self.last_trade = time.time()

                    except Exception as e:
                        logger.error(f"Scalp failed: {e}")

                    # Check filled positions
                    await self._check_positions()

                    # Status
                    if int(time.time()) % 30 < 2:
                        logger.info(f"Spread={spread_pct:.3f}% | positions={len(self.positions)} | "
                                    f"scalps={self.scalps} | profit={self.total_profit:.4f}")

                    await asyncio.sleep(1)

                except Exception as e:
                    logger.error(f"Loop error: {e}", exc_info=True)
                    await asyncio.sleep(3)

        except KeyboardInterrupt:
            logger.info("Shutdown requested")
        finally:
            await self.close()

    async def _check_positions(self):
        open_orders = await self.exchange.fetch_open_orders(self.symbol)
        open_ids = set(o['id'] for o in open_orders)

        for pos in list(self.positions):
            # If sell order is filled, position is closed
            if pos['sell_id'] not in open_ids:
                self.positions.remove(pos)
                profit = (pos['sell_price'] - pos['buy_price']) * pos['amount']
                self.total_profit += profit
                self.scalps += 1
                logger.info(f"SCALP CLOSED | buy={pos['buy_price']} sell={pos['sell_price']} | profit={profit:.4f}")


if __name__ == "__main__":
    symbol = sys.argv[1] if len(sys.argv) > 1 else "SOL/EUR"
    bot = SpreadScalper(symbol)
    asyncio.run(bot.run())
