#!/usr/bin/env python3
"""
DENARO GRID BOT v3 PRO - Core-Driven
WebSocket-driven grid trading using DenaroCore for stability and efficiency.
"""

import asyncio
import json
import logging
import websockets
import time
from denaro_core import DenaroCore

logging.basicConfig(level=logging.INFO, format='%(asctime)s - GRID-PRO - %(levelname)s - %(message)s')
logger = logging.getLogger("GridBotPro")

class GridBot(DenaroCore):
    def __init__(self):
        super().__init__(bot_name="GridBotPro")
        self.state = {
            "filled_orders": [],
            "total_invested": 0.0,
            "total_profit": 0.0,
            "peak_value": 0.0,
            "grid_active": False,
            "current_price": 0.0,
            "placed_order_ids": [],
            "sync_done": False,
            "last_config_reload": 0,
            "paused": False,
            "pause_reason": ""
        }

    async def on_tick(self, price, client):
        self.state['current_price'] = price
        
        # 1. Dynamic Config Reload
        if time.time() - self.state['last_config_reload'] > self.config.get('config_reload_sec', 600):
            self.load_config()
            self.state['last_config_reload'] = time.time()

        # 2. Out-of-bounds check (Kill Switch)
        if not self.state['paused'] and 'grid_buy_levels' in self.state and self.state['grid_buy_levels']:
            lowest_buy = min(self.state['grid_buy_levels'])
            out_of_bounds_threshold = self.config.get('out_of_bounds_threshold', 0.02)  # 2%
            if price < lowest_buy * (1 - out_of_bounds_threshold):
                self.state['paused'] = True
                self.state['pause_reason'] = f"Price {price}€ dropped below lowest grid level {lowest_buy}€ by more than {out_of_bounds_threshold*100}%"
                logger.warning(f"🚨 KILL SWITCH ACTIVATED: {self.state['pause_reason']}")
                # Cancel all open orders
                for order_id in self.state['placed_order_ids'][:]:
                    try:
                        await asyncio.to_thread(client.cancel_order, order_id, self.config['symbol'])
                        logger.info(f"Cancelled order {order_id}")
                    except Exception as e:
                        logger.error(f"Failed to cancel order {order_id}: {e}")
                self.state['placed_order_ids'] = []
        
        # 3. Peak tracking for Trailing Stop
        if price > self.state['peak_value']:
            self.state['peak_value'] = price
        
        # 4. Resume if price returns within bounds
        if self.state['paused'] and 'grid_buy_levels' in self.state and self.state['grid_buy_levels']:
            lowest_buy = min(self.state['grid_buy_levels'])
            if price >= lowest_buy * (1 - self.config.get('out_of_bounds_threshold', 0.02) / 2):  # 1% below lowest
                self.state['paused'] = False
                self.state['pause_reason'] = ""
                logger.info("🟢 KILL SWITCH DEACTIVATED: Price returned within bounds, resuming grid.")
                # Re-initialize grid
                self.state['grid_active'] = False
        
        # 5. Initial Sync
        if not self.state['sync_done']:
            await self.sync_existing_orders(client, price)
            self.state['sync_done'] = True
        
        # 6. Grid Initialization/Healing (skip if paused)
        if not self.state['paused'] and not self.state['grid_active']:
            await self.init_grid(client, price)
        
        # 5. Trailing Stop Check
        if self.trailing_stop_check(price) == "EXIT":
            logger.warning(f"🚨 TRAILING STOP EXIT @ {price}€")
            await self.close_all_positions(client, price)
            return
        
        # 6. Check Fills
        await self.check_fills(client)
        
        if int(time.time()) % 60 < 5:
            logger.info(f"Price: {price}€ | Invested: {self.state['total_invested']:.2f}€ | Profit: {self.state['total_profit']:.2f}€")

    async def sync_existing_orders(self, client, current_price):
        logger.info("Syncing orders with exchange...")
        try:
            open_orders = await self.sync_orders(self.config['symbol'])
            buy_orders = sorted([o for o in open_orders if o['side'] == 'buy'], key=lambda x: abs(x['price'] - current_price))
            sell_orders = sorted([o for o in open_orders if o['side'] == 'sell'], key=lambda x: abs(x['price'] - current_price))
            
            keep_buys = buy_orders[:self.config['grid_levels']]
            keep_sells = sell_orders[:self.config['grid_levels']]
            cancel_orders = buy_orders[self.config['grid_levels']:] + sell_orders[self.config['grid_levels']:]
            
            for o in cancel_orders:
                try: await asyncio.to_thread(client.cancel_order, o['id'], self.config['symbol'])
                except: pass
            
            self.state['placed_order_ids'] = [o['id'] for o in keep_buys + keep_sells]
            self.state['grid_active'] = len(self.state['placed_order_ids']) > 0
            self.state['total_invested'] = len(keep_buys) * self.config['base_order_eur']
            logger.info(f"Sync complete: {len(keep_buys)} buy / {len(keep_sells)} sell orders")
        except Exception as e:
            logger.error(f"Sync error: {e}")

    async def init_grid(self, client, current_price):
        eur_free = self.get_balance('EUR')
        num_levels = self.config['grid_levels']
        budget = self.config['base_order_eur']
        
        if eur_free < (num_levels * budget * 0.9):
            max_ordable = max(1, int(eur_free / (budget * 1.1)))
            num_levels = min(max_ordable, self.config['grid_levels'])
            if num_levels == 0:
                logger.error("Insufficient EUR for grid")
                self.state['grid_active'] = True 
                return

        # Dynamic ATR-based spacing
        atr = await self.get_atr(self.config['symbol'], timeframe='1h', lookback=14)
        atr_spacing_factor = self.config.get('atr_spacing_factor', 1.0)
        if atr is not None and atr > 0:
            # ATR is in price units, convert to percentage of current price
            atr_pct = atr / current_price
            grid_range = atr_pct * atr_spacing_factor
            logger.info(f"[{self.bot_name}] ATR: {atr:.4f} ({atr_pct:.2%}), grid_range: {grid_range:.2%}")
        else:
            grid_range = self.config["grid_range_pct"]
            logger.warning(f"[{self.bot_name}] Using static grid_range: {grid_range:.2%}")
        
        step = grid_range / self.config["grid_levels"]
        buy_prices = [round(current_price * (1 - (i * step)), 2) for i in range(1, num_levels + 1)]
        sell_prices = [round(bp * (1 + self.config['profit_per_grid']), 2) for bp in buy_prices]
        
        # Store absolute grid levels for re-centering
        self.state['grid_buy_levels'] = buy_prices
        self.state['grid_sell_levels'] = sell_prices
        
        placed = 0
        for bp in reversed(buy_prices):
            if self.state['total_invested'] >= self.config['max_total_invested']: break
            amount = budget / bp
            try:
                order = await asyncio.to_thread(client.create_limit_buy_order, self.config['symbol'], round(amount, 5), bp)
                self.state['placed_order_ids'].append(order['id'])
                self.state['total_invested'] += budget
                placed += 1
                await asyncio.sleep(0.2)
            except Exception as e:
                logger.error(f"BUY fail @ {bp}€: {e}")
        
        self.state['grid_active'] = True
        logger.info(f"Grid initialized: {placed} buy orders")

    def trailing_stop_check(self, current_price):
        if current_price <= 0 or not self.state['filled_orders']: return "HOLD"
        # Auto-breakeven: if price rises above buy price + fees, move stop loss to buy price
        if 'last_buy_price' in self.state:
            buy_price = self.state['last_buy_price']
            fee_pct = 0.00075  # Maker fee with BNB discount
            breakeven_price = buy_price * (1 + fee_pct * 2)  # entry + exit fees
            if current_price > breakeven_price:
                # Move stop loss to breakeven
                stop = breakeven_price
                if current_price < stop:
                    return "EXIT"
                logger.debug(f"Auto-breakeven active: stop={stop:.2f}€")
        
        if self.state['peak_value'] > 0:
            profit_pct = (current_price - self.state['peak_value'] * 0.98) / (self.state['peak_value'] * 0.98) * 100
            if profit_pct >= self.config['trailing_activation_pct']:
                stop = self.state['peak_value'] * (1 - self.config['trailing_stop_pct'] / 100)
                if current_price < stop: return "EXIT"
        return "HOLD"

    async def check_fills(self, client):
        for order_id in self.state['placed_order_ids'][:]:
            try:
                status = await asyncio.to_thread(client.fetch_order, order_id, self.config['symbol'])
                if status['status'] == 'closed':
                    side = status['side']
                    price, amount = float(status['average']), float(status['amount'])
                    if order_id in [o['id'] for o in self.state['filled_orders']]: continue
                    self.state['filled_orders'].append({'id': order_id, 'side': side, 'price': price, 'amount': amount})
                    
                    if side == 'buy':
                        logger.info(f"✅ BUY filled @ {price}€")
                        # Store buy price for auto-breakeven
                        self.state['last_buy_price'] = price
                        # Place corresponding SELL order at absolute sell level
                        if 'grid_sell_levels' in self.state and self.state['grid_sell_levels']:
                            # Find the closest sell price (should be price * (1 + profit_per_grid))
                            target_sell_price = price * (1 + self.config['profit_per_grid'])
                            closest = min(self.state['grid_sell_levels'], key=lambda x: abs(x - target_sell_price))
                            try:
                                amount = self.config['base_order_eur'] / price  # amount bought
                                sell_order = await asyncio.to_thread(client.create_limit_sell_order, self.config['symbol'], round(amount, 5), closest)
                                self.state['placed_order_ids'].append(sell_order['id'])
                                logger.info(f"📈 SELL order placed @ {closest}€")
                            except Exception as e:
                                logger.error(f"Failed to place SELL order @ {closest}€: {e}")
                    else:
                        fee = price * (self.config['base_order_eur']/price) * 0.00075
                        profit = (self.config['profit_per_grid'] * self.config['base_order_eur']) - fee
                        self.state['total_profit'] += profit
                        self.log_trade(self.config['symbol'], 'SELL', price, self.config['base_order_eur']/price, self.config['base_order_eur'], fee, profit)
                        logger.info(f"💰 SELL filled @ {price}€, Profit: {profit:.2f}€")
                        
                        # Grid re-centering: replace the sold level with a new BUY order at original price
                        if 'grid_buy_levels' in self.state and self.state['grid_buy_levels']:
                            # Find the closest original buy price (should be price / (1 + profit_per_grid))
                            target_buy_price = price / (1 + self.config['profit_per_grid'])
                            closest = min(self.state['grid_buy_levels'], key=lambda x: abs(x - target_buy_price))
                            # Place a new BUY order at the original level
                            try:
                                amount = self.config['base_order_eur'] / closest
                                new_order = await asyncio.to_thread(client.create_limit_buy_order, self.config['symbol'], round(amount, 5), closest)
                                self.state['placed_order_ids'].append(new_order['id'])
                                logger.info(f"🔄 Grid re-centered: new BUY order @ {closest}€")
                            except Exception as e:
                                logger.error(f"Failed to place re-centered BUY order @ {closest}€: {e}")
                    self.state['placed_order_ids'].remove(order_id)
            except Exception: pass

    async def close_all_positions(self, client, price):
        try:
            balances = await asyncio.to_thread(client.fetch_balance)
            asset = self.config['symbol'].split('/')[0]
            amount = balances['free'].get(asset, 0)
            if amount > 0.0001:
                await asyncio.to_thread(client.create_market_sell_order, self.config['symbol'], amount)
                logger.info(f"Closed all {asset} positions")
        except Exception as e: logger.error(f"Close error: {e}")

    async def run(self):
        client = self.client
        try:
            ticker = await asyncio.to_thread(client.fetch_ticker, self.config['symbol'])
            self.state['peak_value'] = ticker['last']
            logger.info(f"Starting price: {self.state['peak_value']}€")
        except Exception as e:
            logger.error(f"Initial price error: {e}")
            return
        
        url = f"wss://stream.binance.com:9443/ws/{self.config['symbol_ws']}@ticker"
        async with websockets.connect(url, ping_interval=30) as ws:
            logger.info("WebSocket connected!")
            while True:
                msg = await ws.recv()
                data = json.loads(msg)
                if data.get('e') == '24hrTicker':
                    await self.on_tick(float(data['c']), client)

if __name__ == "__main__":
    bot = GridBot()
    asyncio.run(bot.run())
