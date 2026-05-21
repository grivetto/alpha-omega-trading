#!/usr/bin/env python3
"""
DENARO V3 - Ultra Aggressive Grid Bot
15 levels, 0.25% spacing, dynamic order sizing, auto-compounding
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
        logging.FileHandler('denaro_v3.log'),
    ],
    force=True,
)
logger = logging.getLogger("DenaroV3")


class DenaroV3:
    def __init__(self, symbol="SOL/EUR"):
        self.exchange = None
        self.symbol = symbol
        self.asset = symbol.split("/")[0]

        # Adaptive grid config - tuned per asset
        self.base_order_eur = 6.0
        self.max_invested = 100.0

        # Symbol-specific optimization
        if "ADA" in self.asset:
            self.grid_spacing = 0.004  # 0.4% - optimized for fee efficiency
            self.profit_pct = 0.005    # 0.5% target
            self.min_grid_levels = 3
            self.max_grid_levels = 7
        elif "SOL" in self.asset:
            self.grid_spacing = 0.003  # 0.3% - SOL has better spread
            self.profit_pct = 0.004    # 0.4% target
            self.min_grid_levels = 3
            self.max_grid_levels = 5
        else:
            self.grid_spacing = 0.003
            self.profit_pct = 0.004
            self.min_grid_levels = 3
            self.max_grid_levels = 5

        # Fee structure (with BNB burn 25% discount)
        self.fee_rate = 0.00075  # 0.075% per side
        self.round_trip_fee_pct = self.fee_rate * 2  # 0.15%

        # Compounding
        self.total_profit = 0
        self.total_fees_paid = 0
        self.compound_factor = 1.0
        self.fills = 0
        self.trades_file = ".tmp/v3_trades.json"

        # State
        self.buy_orders = {}
        self.sell_orders = {}
        self.total_invested = 0
        self.center_price = 0
        self.last_rebalance = 0

        # Load compounding state
        self._load_state()

    async def connect(self):
        api_key = ""
        api_secret = ""

        # Try loading from .env file directly
        for env_path in [
            "/home/sergio/denaro/.env",
            os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"),
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
            # Fallback to environment variables
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
        logger.info(f"Connected to Binance | {self.symbol} | key={api_key[:8]}...")

    async def close(self):
        if self.exchange:
            await self.exchange.close()

    async def get_balance(self):
        bal = await self.exchange.fetch_balance()
        eur = bal.get("EUR", {})
        asset = bal.get(self.asset, {})
        return {
            'EUR_free': eur.get('free', 0) or 0,
            'EUR_used': eur.get('used', 0) or 0,
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

        # Calculate optimal grid levels based on available capital
        order_eur = self.base_order_eur * self.compound_factor
        min_cost = 5.5  # Buffer above 5 EUR minimum

        # Adaptive grid sizing
        max_possible_orders = int(eur_free * 0.85 / order_eur)
        grid_levels = max(self.min_grid_levels, min(self.max_grid_levels, max_possible_orders))

        # Skip if insufficient capital for even 1 order
        if eur_free < min_cost:
            logger.info(f"Insufficient capital: EUR_free={eur_free:.2f} < {min_cost:.2f} (need for 1 order)")
            return

        logger.info(f"Grid rebuild @ {price} | EUR={eur_free:.2f} | {self.asset}={asset_free:.4f} | "
                    f"order={order_eur:.2f} EUR | levels={grid_levels} | compound={self.compound_factor:.2f}x")

        half = grid_levels // 2

        # Buy orders below price
        for i in range(1, half + 1):
            buy_price = round(price * (1 - i * self.grid_spacing), 2)
            this_order_eur = order_eur * (1 + i * 0.05)  # Slightly larger at lower levels

            if self.total_invested + this_order_eur > self.max_invested:
                break
            if this_order_eur > eur_free * 0.85:
                break
            if this_order_eur < min_cost:
                break

            amount = round(this_order_eur / buy_price, 3)
            if amount < 0.001:
                continue

            # Verify notional
            notional = amount * buy_price
            if notional < min_cost:
                continue

            try:
                order = await self.exchange.create_order(self.symbol, 'limit', 'buy', amount, buy_price)
                self.buy_orders[order['id']] = {'price': buy_price, 'amount': amount, 'eur': this_order_eur}
                self.total_invested += this_order_eur
                eur_free -= this_order_eur
                logger.info(f"BUY #{i} @ {buy_price} ({amount} {self.asset}, {this_order_eur:.2f} EUR)")
            except Exception as e:
                logger.error(f"Buy failed @ {buy_price}: {e}")

        # Sell orders above price (only if we have meaningful asset balance)
        min_asset_value = 5.0  # Minimum EUR value to place a sell
        asset_value = asset_free * price

        if asset_value < min_asset_value:
            logger.info(f"Skipping sell orders: {self.asset}={asset_free:.4f} (value={asset_value:.2f} EUR < {min_asset_value})")
        else:
            for i in range(1, half + 1):
                sell_price = round(price * (1 + i * self.grid_spacing), 2)
                sell_amount = round(min(asset_free * 0.2, order_eur / sell_price), 3)

                sell_notional = sell_amount * sell_price
                if sell_notional < min_cost:
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

        logger.info(f"Grid placed: {len(self.buy_orders)} buys, {len(self.sell_orders)} sells, invested={self.total_invested:.2f}")

    async def check_fills(self, price):
        open_orders = await self.exchange.fetch_open_orders(self.symbol)
        open_ids = set(o['id'] for o in open_orders)

        # Fetch recent trades to verify actual fills
        trades = await self.exchange.fetch_my_trades(self.symbol, limit=20)
        filled_order_ids = set(t.get('order') or t.get('info', {}).get('orderId') for t in trades)

        # Check buy fills
        for order_id in list(self.buy_orders.keys()):
            if order_id not in open_ids:
                # Verify it actually filled, not just canceled
                if order_id not in filled_order_ids:
                    # Order was canceled, not filled - remove from tracking
                    buy_info = self.buy_orders.pop(order_id)
                    self.total_invested -= buy_info['eur']
                    logger.info(f"Buy order canceled (not filled) @ {buy_info['price']}")
                    continue

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
                if order_id not in filled_order_ids:
                    sell_info = self.sell_orders.pop(order_id)
                    logger.info(f"Sell order canceled (not filled) @ {sell_info['price']}")
                    continue

                sell_info = self.sell_orders.pop(order_id)

                # Place buy order below fill price
                buy_price = round(sell_info['price'] * (1 - self.profit_pct), 2)
                buy_eur = self.base_order_eur * self.compound_factor
                amount = round(buy_eur / buy_price, 3)

                bal = await self.get_balance()
                if amount * buy_price <= bal['EUR_free'] * 0.9 and buy_eur >= 5.0:
                    try:
                        order = await self.exchange.create_order(self.symbol, 'limit', 'buy', amount, buy_price)
                        self.buy_orders[order['id']] = {'price': buy_price, 'amount': amount, 'eur': buy_eur}
                        self.total_invested += buy_eur
                        self.fills += 1

                        profit = self.profit_pct * buy_eur
                        fee_cost = buy_eur * self.round_trip_fee_pct
                        net_profit = profit - fee_cost
                        self.total_profit += net_profit
                        self.total_fees_paid += fee_cost
                        self._record_trade(net_profit)
                        self._update_compound()
                        logger.info(f"Sell filled @ {sell_info['price']} -> buy @ {buy_price} | "
                                    f"gross={profit:.4f} fee={fee_cost:.4f} net={net_profit:.4f} | "
                                    f"total_net={self.total_profit:.4f}")
                    except Exception as e:
                        logger.error(f"Buy placement failed: {e}")

    def needs_rebalance(self, price):
        if not self.center_price:
            return True
        dist = abs(price - self.center_price) / self.center_price
        if dist > self.grid_spacing * 4:
            return True
        if time.time() - self.last_rebalance > 180:  # 3 min
            return True
        return False

    def _record_trade(self, net_profit):
        try:
            os.makedirs(".tmp", exist_ok=True)
            trades = []
            if os.path.exists(self.trades_file):
                with open(self.trades_file, 'r') as f:
                    trades = json.load(f)
            trades.append({'net_profit': net_profit, 'time': time.time()})
            trades = trades[-100:]  # Keep last 100
            with open(self.trades_file, 'w') as f:
                json.dump(trades, f, indent=2)
        except Exception as e:
            logger.error(f"Trade record error: {e}")

    def _update_compound(self):
        """Increase order size as net profit grows"""
        if self.total_profit >= 2:  # Lower threshold for faster compounding
            self.compound_factor = 1.0 + (self.total_profit / 50)  # +2% per 1 EUR net profit
            self.compound_factor = min(self.compound_factor, 1.8)  # Cap at 1.8x
            logger.info(f"Compound factor updated: {self.compound_factor:.2f}x (net_profit={self.total_profit:.2f})")

    def _load_state(self):
        try:
            if os.path.exists(self.trades_file):
                with open(self.trades_file, 'r') as f:
                    trades = json.load(f)
                self.total_profit = sum(t.get('net_profit', t.get('profit', 0)) for t in trades)
                self.fills = len(trades)
                self._update_compound()
        except Exception:
            pass

    async def run(self):
        await self.connect()
        spacing_pct = self.grid_spacing * 100
        profit_pct = self.profit_pct * 100
        logger.info(f"Denaro V3 started | {self.symbol} | levels={self.min_grid_levels}-{self.max_grid_levels} | "
                    f"spacing={spacing_pct:.1f}% | profit={profit_pct:.1f}% | fee={self.round_trip_fee_pct*100:.2f}%")

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
                        spacing_pct = self.grid_spacing * 100
                        profit_pct = self.profit_pct * 100
                        logger.info(f"Price={price} | Buys={len(self.buy_orders)} | Sells={len(self.sell_orders)} | "
                                    f"invested={self.total_invested:.2f} | net_profit={self.total_profit:.4f} | "
                                    f"fees_paid={self.total_fees_paid:.4f} | fills={self.fills} | "
                                    f"EUR_free={bal['EUR_free']:.2f} | compound={self.compound_factor:.2f}x | "
                                    f"spacing={spacing_pct:.1f}% profit={profit_pct:.1f}%")

                    await asyncio.sleep(2)

                except Exception as e:
                    logger.error(f"Loop error: {e}", exc_info=True)
                    await asyncio.sleep(5)

        except KeyboardInterrupt:
            logger.info("Shutdown requested")
        finally:
            await self.close()


if __name__ == "__main__":
    symbol = sys.argv[1] if len(sys.argv) > 1 else "SOL/EUR"
    bot = DenaroV3(symbol)
    asyncio.run(bot.run())
