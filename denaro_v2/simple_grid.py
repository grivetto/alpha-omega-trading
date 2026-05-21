#!/usr/bin/env python3
"""
DENARO V2 - Simple Grid Bot
Reliable, production-ready grid trading bot.
"""
import asyncio
import ccxt.async_support as ccxt
import logging
import os
import sys
import time
import json

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('denaro_v2.log'),
    ],
    force=True,
)
logger = logging.getLogger("DenaroV2")


class SimpleGridBot:
    """Simple, reliable grid trading bot."""

    def __init__(self):
        self.exchange = None
        self.symbol = "SOL/EUR"
        self.grid_levels = 5
        self.grid_spacing = 0.005  # 0.5%
        self.order_size_eur = 6.0  # Above 5 EUR minimum
        self.profit_pct = 0.004  # 0.4% per grid
        self.max_invested = 30.0

        self.buy_orders = {}  # order_id -> {price, amount, eur}
        self.sell_orders = {}  # order_id -> {price, amount}
        self.total_invested = 0
        self.total_profit = 0
        self.fills = 0
        self.center_price = 0
        self.last_rebalance = 0

    async def connect(self):
        """Connect to exchange."""
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
        logger.info("Connected to Binance")

    async def close(self):
        if self.exchange:
            await self.exchange.close()

    async def get_balance(self):
        bal = await self.exchange.fetch_balance()
        eur = bal.get("EUR", {})
        sol = bal.get("SOL", {})
        return {
            'EUR_free': eur.get('free', 0) or 0,
            'EUR_used': eur.get('used', 0) or 0,
            'SOL_free': sol.get('free', 0) or 0,
        }

    async def get_price(self):
        ticker = await self.exchange.fetch_ticker(self.symbol)
        return ticker.get('last', 0)

    async def cancel_all(self):
        orders = await self.exchange.fetch_open_orders(self.symbol)
        for o in orders:
            try:
                await self.exchange.cancel_order(o['id'], self.symbol)
            except Exception:
                pass
        self.buy_orders = {}
        self.sell_orders = {}
        self.total_invested = 0
        logger.info("All orders canceled")

    async def place_grid(self, price):
        """Place grid orders."""
        await self.cancel_all()

        self.center_price = price
        self.last_rebalance = time.time()

        bal = await self.get_balance()
        eur_free = bal['EUR_free']
        sol_free = bal['SOL_free']

        logger.info(f"Placing grid @ {price} | EUR={eur_free:.2f} SOL={sol_free:.4f}")

        half = self.grid_levels // 2

        # Buy orders below price
        for i in range(1, half + 1):
            buy_price = round(price * (1 - i * self.grid_spacing), 2)
            order_eur = self.order_size_eur

            if self.total_invested + order_eur > self.max_invested:
                break
            if order_eur > eur_free * 0.85:
                break

            amount = round(order_eur / buy_price, 3)  # SOL precision is 0.001
            if amount < 0.001:
                continue

            try:
                order = await self.exchange.create_order(self.symbol, 'limit', 'buy', amount, buy_price)
                self.buy_orders[order['id']] = {'price': buy_price, 'amount': amount, 'eur': order_eur}
                self.total_invested += order_eur
                eur_free -= order_eur
                logger.info(f"BUY #{i} @ {buy_price} ({amount} SOL, {order_eur} EUR)")
            except Exception as e:
                logger.error(f"Buy failed @ {buy_price}: {e}")

        # Sell orders above price
        for i in range(1, half + 1):
            sell_price = round(price * (1 + i * self.grid_spacing), 2)
            sell_amount = round(min(sol_free * 0.3, self.order_size_eur / sell_price), 3)

            sell_notional = sell_amount * sell_price
            if sell_notional < 5.0:
                continue
            if sell_amount < 0.001:
                break

            try:
                order = await self.exchange.create_order(self.symbol, 'limit', 'sell', sell_amount, sell_price)
                self.sell_orders[order['id']] = {'price': sell_price, 'amount': sell_amount}
                sol_free -= sell_amount
                logger.info(f"SELL #{i} @ {sell_price} ({sell_amount} SOL)")
            except Exception as e:
                logger.error(f"Sell failed @ {sell_price}: {e}")

        logger.info(f"Grid placed: {len(self.buy_orders)} buys, {len(self.sell_orders)} sells, invested={self.total_invested:.2f}")

    async def check_fills(self, price):
        """Check for filled orders and replace them."""
        open_orders = await self.exchange.fetch_open_orders(self.symbol)
        open_ids = set(o['id'] for o in open_orders)

        # Check buy fills
        for order_id in list(self.buy_orders.keys()):
            if order_id not in open_ids:
                # Order was filled or canceled
                buy_info = self.buy_orders.pop(order_id)
                self.total_invested -= buy_info['eur']

                # Place sell order above fill price
                sell_price = round(buy_info['price'] * (1 + self.profit_pct), 2)
                sell_amount = round(buy_info['amount'] * 0.997, 3)

                try:
                    order = await self.exchange.create_order(self.symbol, 'limit', 'sell', sell_amount, sell_price)
                    self.sell_orders[order['id']] = {'price': sell_price, 'amount': sell_amount}
                    self.fills += 1
                    logger.info(f"Buy filled @ {buy_info['price']} -> sell @ {sell_price}")
                except Exception as e:
                    logger.error(f"Sell placement failed: {e}")

        # Check sell fills
        for order_id in list(self.sell_orders.keys()):
            if order_id not in open_ids:
                sell_info = self.sell_orders.pop(order_id)

                # Place buy order below fill price
                buy_price = round(sell_info['price'] * (1 - self.profit_pct), 2)
                buy_eur = self.order_size_eur
                amount = round(buy_eur / buy_price, 3)

                bal = await self.get_balance()
                if amount * buy_price <= bal['EUR_free'] * 0.9:
                    try:
                        order = await self.exchange.create_order(self.symbol, 'limit', 'buy', amount, buy_price)
                        self.buy_orders[order['id']] = {'price': buy_price, 'amount': amount, 'eur': buy_eur}
                        self.total_invested += buy_eur
                        self.fills += 1

                        profit = self.profit_pct * buy_eur
                        self.total_profit += profit
                        logger.info(f"Sell filled @ {sell_info['price']} -> buy @ {buy_price} | profit={profit:.4f}")
                    except Exception as e:
                        logger.error(f"Buy placement failed: {e}")

    def needs_rebalance(self, price):
        if not self.center_price:
            return True
        dist = abs(price - self.center_price) / self.center_price
        if dist > self.grid_spacing * 3:
            return True
        if time.time() - self.last_rebalance > 300:
            return True
        return False

    async def run(self):
        """Main loop."""
        await self.connect()
        logger.info("Grid Bot started")

        try:
            while True:
                try:
                    price = await self.get_price()
                    if price <= 0:
                        await asyncio.sleep(3)
                        continue

                    if self.needs_rebalance(price):
                        await self.place_grid(price)
                    else:
                        await self.check_fills(price)

                    # Status every 30 seconds
                    if int(time.time()) % 30 < 3:
                        bal = await self.get_balance()
                        logger.info(f"Price={price} | Buys={len(self.buy_orders)} | Sells={len(self.sell_orders)} | "
                                    f"invested={self.total_invested:.2f} | profit={self.total_profit:.4f} | "
                                    f"fills={self.fills} | EUR_free={bal['EUR_free']:.2f}")

                    await asyncio.sleep(3)

                except Exception as e:
                    logger.error(f"Loop error: {e}", exc_info=True)
                    await asyncio.sleep(10)

        except KeyboardInterrupt:
            logger.info("Shutdown requested")
        finally:
            await self.close()


if __name__ == "__main__":
    bot = SimpleGridBot()
    asyncio.run(bot.run())
