#!/usr/bin/env python3
"""
DENARO V3 - Micro Scalper
Ultra-tight grid (0.15% spacing) for maximum fill frequency on ADA.
Designed for high-frequency micro-profits on ranging markets.
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
        logging.FileHandler('micro_scalper.log'),
    ],
    force=True,
)
logger = logging.getLogger("MicroScalper")


class MicroScalper:
    def __init__(self, symbol="ADA/EUR"):
        self.exchange = None
        self.symbol = symbol
        self.asset = symbol.split("/")[0]

        # Ultra-tight grid config
        self.grid_levels = 8
        self.grid_spacing = 0.0015   # 0.15% - ultra tight
        self.profit_pct = 0.002      # 0.2% per scalp
        self.base_order_eur = 5.5    # Minimum viable order
        self.max_invested = 50.0     # Cap exposure
        self.rebalance_sec = 120     # Rebalance every 2 minutes

        # State
        self.buy_orders = {}
        self.sell_orders = {}
        self.total_invested = 0
        self.center_price = 0
        self.last_rebalance = 0
        self.total_profit = 0
        self.fills = 0
        self.trades_file = ".tmp/micro_trades.json"
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
        logger.info(f"Micro Scalper connected | {self.symbol}")

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
        await self.cancel_all()
        self.center_price = price
        self.last_rebalance = time.time()

        bal = await self.get_balance()
        eur_free = bal['EUR_free']
        asset_free = bal['asset_free']

        order_eur = self.base_order_eur
        min_cost = 5.0

        if eur_free < min_cost:
            logger.info(f"Insufficient capital: EUR_free={eur_free:.2f}")
            return

        half = self.grid_levels // 2
        logger.info(f"Micro grid rebuild @ {price} | EUR={eur_free:.2f} | "
                    f"{self.asset}={asset_free:.2f} | order={order_eur:.2f} EUR")

        # Buy orders below price
        for i in range(1, half + 1):
            buy_price = round(price * (1 - i * self.grid_spacing), 6)
            this_order_eur = order_eur

            if self.total_invested + this_order_eur > self.max_invested:
                break
            if this_order_eur > eur_free * 0.85:
                break

            amount = round(this_order_eur / buy_price, 3)
            if amount < 0.001:
                continue
            if amount * buy_price < min_cost:
                continue

            try:
                order = await self.exchange.create_order(self.symbol, 'limit', 'buy', amount, buy_price)
                self.buy_orders[order['id']] = {'price': buy_price, 'amount': amount, 'eur': this_order_eur}
                self.total_invested += this_order_eur
                eur_free -= this_order_eur
                logger.info(f"BUY #{i} @ {buy_price} ({amount} {self.asset})")
            except Exception as e:
                logger.error(f"Buy failed @ {buy_price}: {e}")

        # Sell orders above price
        if asset_free * price >= min_cost:
            for i in range(1, half + 1):
                sell_price = round(price * (1 + i * self.grid_spacing), 6)
                sell_amount = round(min(asset_free * 0.15, order_eur / sell_price), 3)

                if sell_amount * sell_price < min_cost:
                    continue
                if sell_amount < 0.001:
                    break

                try:
                    order = await self.exchange.create_order(self.symbol, 'limit', 'sell', sell_amount, sell_price)
                    self.sell_orders[order['id']] = {'price': sell_price, 'amount': sell_amount}
                    asset_free -= sell_amount
                    logger.info(f"SELL #{i} @ {sell_price} ({sell_amount} {self.asset})")
                except Exception as e:
                    logger.error(f"Sell failed @ {sell_price}: {e}")

        logger.info(f"Micro grid placed: {len(self.buy_orders)} buys, {len(self.sell_orders)} sells, "
                    f"invested={self.total_invested:.2f}")

    async def check_fills(self, price):
        open_orders = await self.exchange.fetch_open_orders(self.symbol)
        open_ids = set(o['id'] for o in open_orders)

        # Check buy fills
        for order_id in list(self.buy_orders.keys()):
            if order_id not in open_ids:
                buy_info = self.buy_orders.pop(order_id)
                self.total_invested -= buy_info['eur']

                # Place sell order above fill price
                sell_price = round(buy_info['price'] * (1 + self.profit_pct), 6)
                sell_amount = round(buy_info['amount'] * 0.997, 3)

                if sell_amount < 0.001:
                    continue

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
                buy_price = round(sell_info['price'] * (1 - self.profit_pct), 6)
                buy_eur = self.base_order_eur
                amount = round(buy_eur / buy_price, 3)

                bal = await self.get_balance()
                if amount * buy_price <= bal['EUR_free'] * 0.9 and buy_eur >= 5.0:
                    try:
                        order = await self.exchange.create_order(self.symbol, 'limit', 'buy', amount, buy_price)
                        self.buy_orders[order['id']] = {'price': buy_price, 'amount': amount, 'eur': buy_eur}
                        self.total_invested += buy_eur
                        self.fills += 1

                        profit = self.profit_pct * buy_eur
                        fee_cost = buy_eur * 0.0015  # ~0.15% round trip
                        net_profit = profit - fee_cost
                        self.total_profit += net_profit
                        self._record_trade(net_profit)

                        logger.info(f"Sell filled @ {sell_info['price']} -> buy @ {buy_price} | "
                                    f"net={net_profit:.4f} | total={self.total_profit:.4f}")
                    except Exception as e:
                        logger.error(f"Buy placement failed: {e}")

    def needs_rebalance(self, price):
        if not self.center_price:
            return True
        dist = abs(price - self.center_price) / self.center_price
        if dist > self.grid_spacing * 6:
            return True
        if time.time() - self.last_rebalance > self.rebalance_sec:
            return True
        return False

    async def run(self):
        await self.connect()
        logger.info(f"Micro Scalper started | {self.symbol} | {self.grid_levels} levels | "
                    f"spacing={self.grid_spacing*100:.2f}% | profit={self.profit_pct*100:.2f}%")

        try:
            while True:
                try:
                    price = await self.get_price()
                    if price <= 0:
                        await asyncio.sleep(2)
                        continue

                    if self.needs_rebalance(price):
                        await self.place_grid(price)
                    else:
                        await self.check_fills(price)

                    # Status every 30 seconds
                    if int(time.time()) % 30 < 2:
                        bal = await self.get_balance()
                        logger.info(f"Price={price} | Buys={len(self.buy_orders)} | "
                                    f"Sells={len(self.sell_orders)} | invested={self.total_invested:.2f} | "
                                    f"profit={self.total_profit:.4f} | fills={self.fills} | "
                                    f"EUR_free={bal['EUR_free']:.2f}")

                    await asyncio.sleep(3)

                except Exception as e:
                    logger.error(f"Loop error: {e}", exc_info=True)
                    await asyncio.sleep(5)

        except KeyboardInterrupt:
            logger.info("Shutdown requested")
        finally:
            await self.close()

    def _record_trade(self, net_profit):
        try:
            os.makedirs(".tmp", exist_ok=True)
            trades = []
            if os.path.exists(self.trades_file):
                with open(self.trades_file, 'r') as f:
                    trades = json.load(f)
            trades.append({'net_profit': net_profit, 'time': time.time()})
            trades = trades[-200:]
            with open(self.trades_file, 'w') as f:
                json.dump(trades, f, indent=2)
        except Exception as e:
            logger.error(f"Trade record error: {e}")

    def _load_state(self):
        try:
            if os.path.exists(self.trades_file):
                with open(self.trades_file, 'r') as f:
                    trades = json.load(f)
                self.total_profit = sum(t.get('net_profit', t.get('profit', 0)) for t in trades)
                self.fills = len(trades)
        except Exception:
            pass


if __name__ == "__main__":
    symbol = sys.argv[1] if len(sys.argv) > 1 else "ADA/EUR"
    bot = MicroScalper(symbol)
    asyncio.run(bot.run())
