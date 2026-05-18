#!/usr/bin/env python3
"""
DENARO GRID BOT v3.8 — Core-Driven
WebSocket-driven grid trading using DenaroCore for stability and efficiency.

Changes from v3:
- AdaptiveTrendFilter replaces binary TrendFilter (never fully pauses)
- Trailing stop: fixed impossible condition, now state-based
- ProfitOptimizer: actually APPLIES and PERSISTS adjustments
- orig_level_idx: now tracked when placing orders
- profit_pct: replaced with direct config access
- Risk factor scales order sizes dynamically
- Stale order cleanup on startup
"""

import asyncio
import json
import logging
import os
import websockets
import time
from denaro_core import DenaroCore
from denaro_strategies import AdaptiveTrendFilter, VolatilityGrid, MartingaleLite, IntelligentRebalancer, ProfitOptimizer

logging.basicConfig(level=logging.INFO, format='%(asctime)s - GRID-PRO - %(levelname)s - %(message)s')
logger = logging.getLogger("GridBotPro")


class GridBot(DenaroCore):
    def __init__(self):
        super().__init__(bot_name="GridBotPro")
        self.config = self.load_config()
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
            "pause_reason": "",
            "trailing_stop_level": None,
        }
        # Initialize v5 Strategies
        self.trend_filter = AdaptiveTrendFilter(self.config)
        self.vol_grid = VolatilityGrid(self.config)
        self.martingale = MartingaleLite(self.config)
        self.rebalancer = IntelligentRebalancer(self.config)
        self.optimizer = ProfitOptimizer(self.config, config_path=self._config_path)

    def _config_path(self):
        return os.path.join(os.path.dirname(__file__) or ".", "grid_config.json")

    async def on_tick(self, price, client):
        self.state['current_price'] = price

        # 1. Dynamic Config Reload (less frequent: 600s)
        if time.time() - self.state['last_config_reload'] > self.config.get('config_reload_sec', 600):
            self.load_config()
            self.state['last_config_reload'] = time.time()

        # 6. Apply optimizer's adjusted base order size
        adj_multiplier, adjusted_base = self.optimizer.get_adjustment(self.config['base_order_eur'])
        effective_base = adjusted_base
        risk_factor = 1.0

        # NEW: Kelly Criterion for position sizing
        win_prob = 0.52  # Assumed win rate from historical RSI + ATR combo
        payout_ratio = 0.008  # 0.8% profit target per trade
        f_star = max(0.01, min(0.15, (payout_ratio * win_prob - (1 - win_prob)) / payout_ratio))
        eur_free = await self.get_balance('EUR')
        effective_base = float(f_star * eur_free)

        # 7. Adaptive Trend Filter — NEVER fully pauses
        # Returns risk_factor [0.2..1.0], scales order sizes
        risk_factor = self.trend_filter.get_risk_factor(client, self.config['symbol'], price)
        trend_label = self.trend_filter.get_trend_label(risk_factor)

        # Apply risk factor to effective base — downsize in bad conditions but NEVER zero
        effective_base = self.config['base_order_eur'] * risk_factor * adj_multiplier

        # 3. Kill Switch — only for catastrophic price drops (>5% below lowest grid level)
        kill_threshold = 0.05  # 5% — wider than v3's 2%
        if not self.state['paused'] and 'grid_buy_levels' in self.state and self.state['grid_buy_levels']:
            lowest_buy = min(self.state['grid_buy_levels'])
            if price < lowest_buy * (1 - kill_threshold):
                self.state['paused'] = True
                self.state['pause_reason'] = f"Kill switch: price {price}€ < {lowest_buy * (1 - kill_threshold):.2f}€"
                logger.warning(f"🚨 KILL SWITCH: {self.state['pause_reason']}")
                # Cancel only non-fill orders, keep filled positions
                for order_id in self.state['placed_order_ids'][:]:
                    try:
                        await asyncio.to_thread(client.cancel_order, order_id, self.config['symbol'])
                    except:
                        pass
                self.state['placed_order_ids'] = []

        # 4. Resume if price returns within bounds
        if self.state['paused'] and 'grid_buy_levels' in self.state and self.state['grid_buy_levels']:
            lowest_buy = min(self.state['grid_buy_levels'])
            if price >= lowest_buy * (1 - kill_threshold / 2):
                self.state['paused'] = False
                self.state['pause_reason'] = ""
                self.state['grid_active'] = False
                logger.info("🟢 Kill switch deactivated: resuming grid.")

        # 5. Peak tracking for Trailing Stop (updated every tick)
        if price > self.state['peak_value']:
            self.state['peak_value'] = price

        # 6. Trailing Stop — FIXED: state-based, not impossible condition
        trailing_action = self.trailing_stop_check(price)
        if trailing_action == "EXIT":
            logger.warning(f"🚨 TRAILING STOP EXIT @ {price}€")
            await self.close_all_positions(client, price)
            self.state['grid_active'] = False
            return

        # 7. Initial Sync
        if not self.state['sync_done']:
            await self.sync_existing_orders(client, price)
            self.state['sync_done'] = True

        # 8. Rebalance check
        if not self.state['paused'] and self.state['grid_active'] and 'grid_buy_levels' in self.state:
            if self.rebalancer.needs_rebalance(price, self.state['grid_buy_levels'], self.config):
                logger.info("🔄 Rebalancing grid...")
                self.state['grid_active'] = False
                self.rebalancer.mark_rebalanced()

        # 9. Grid Initialization/Healing
        if not self.state['paused'] and not self.state['grid_active']:
            await self.init_grid(client, price, effective_base)

        # 10. Check Fills
        await self.check_fills(client, effective_base)

        # 11. Periodic status log
        if int(time.time()) % 60 < 5:
            logger.info(
                f"Price: {price}€ | Risk: {risk_factor:.2f} | "
                f"Invested: {self.state['total_invested']:.2f}€ | "
                f"Profit: {self.state['total_profit']:.2f}€ | "
                f"Base: {effective_base:.2f}€ | Trend: {trend_label}"
            )

    async def init_grid(self, client, current_price, base_eur):
        eur_free = await self.get_balance('EUR')
        num_levels = self.config['grid_levels']

        # Martingale: calculate total budget needed
        mart_total = self.martingale.get_total_for_levels(num_levels)
        budget_eur = max(base_eur, min(mart_total, self.config['max_total_invested'] - self.state['total_invested']))

        if eur_free < (budget_eur * 0.9):
            # Scale down levels based on available EUR
            for n in range(num_levels, 0, -1):
                if self.martingale.get_total_for_levels(n) <= eur_free * 0.9:
                    num_levels = n
                    break
            else:
                num_levels = max(1, int(eur_free / (base_eur * 1.1)))
            if num_levels == 0:
                logger.error("Insufficient EUR for grid")
                self.state['grid_active'] = True
                return

        # Volatility-adaptive grid spacing
        atr = await self.get_atr(self.config['symbol'], timeframe='1h', lookback=14)
        grid_range_pct, profit_pct = self.vol_grid.get_spacing(atr, current_price)
        logger.info(f"🔄 Grid init: ATR={atr:.4f} ({atr / current_price * 100:.2f}%), "
                     f"range={grid_range_pct:.2%}, profit={profit_pct:.2%}, levels={num_levels}, base={base_eur:.2f}€")

        step = grid_range_pct / max(num_levels, 1)
        buy_prices = [round(current_price * (1 - (i * step)), 2) for i in range(1, num_levels + 1)]
        sell_prices = [round(bp * (1 + profit_pct), 2) for bp in buy_prices]

        # Store absolute grid levels for re-centering
        self.state['grid_buy_levels'] = buy_prices
        self.state['grid_sell_levels'] = sell_prices

        placed = 0
        for i, bp in enumerate(reversed(buy_prices)):
            if self.state['total_invested'] >= self.config['max_total_invested']:
                break
            order_eur = min(self.martingale.get_size(i),
                            self.config['max_total_invested'] - self.state['total_invested'])

            # Skip if price is too close to current (would fill immediately at bad price)
            if abs(bp - current_price) / current_price < 0.001:
                logger.info(f"⏭ Skipping buy level {bp}€ (too close to current price)")
                continue

            try:
                amount = order_eur / bp
                order = await asyncio.to_thread(
                    client.create_limit_buy_order,
                    self.config['symbol'],
                    round(amount, 5),
                    bp
                )
                # Store level index for profit calculation
                level_idx = len(buy_prices) - 1 - i  # Reverse index
                order['_level_idx'] = level_idx
                self.state['placed_order_ids'].append(order['id'])
                self.state['total_invested'] += order_eur
                placed += 1
                logger.info(f"📉 BUY order placed @ {bp}€ ({order_eur:.2f}€, level {level_idx})")
                await asyncio.sleep(0.3)  # Space out orders
            except Exception as e:
                logger.error(f"BUY fail @ {bp}€: {e}")

        self.state['grid_active'] = placed > 0
        logger.info(f"Grid initialized: {placed} buy orders placed")

        # ── Range Trading: also place SELL orders above market using free SOL ──
        try:
            balances = await asyncio.to_thread(client.fetch_balance)
            asset = self.config['symbol'].split('/')[0]
            asset_free = balances['free'].get(asset, 0)
            if asset_free > 0.01:
                per_sell = 0.05  # Use 0.05 per sell level
                sell_levels = 3
                max_use = min(asset_free, per_sell * sell_levels)
                num_sells = int(max_use / per_sell)
                for i in range(num_sells):
                    sell_pct = (i + 1) * 0.004  # 0.4%, 0.8%, 1.2% above market
                    sell_price = round(current_price * (1 + sell_pct), 2)
                    try:
                        order = await asyncio.to_thread(
                            client.create_limit_sell_order,
                            self.config['symbol'],
                            round(per_sell, 5),
                            sell_price
                        )
                        # Mark with clientOrderId prefix for tracking
                        self.state['placed_order_ids'].append(order['id'])
                        logger.info(f"📈 RANGE SELL @ {sell_price}€ (+{sell_pct * 100:.1f}%) {per_sell} {asset}")
                    except Exception as e:
                        logger.error(f"RANGE SELL fail @ {sell_price}€: {e}")
                    await asyncio.sleep(0.2)
        except Exception as e:
            logger.warning(f"Range sell init failed: {e}")

    def trailing_stop_check(self, current_price):
        """FIXED: State-based trailing stop with persistent stop level"""
        if current_price <= 0 or not self.state['filled_orders']:
            return "HOLD"

        # Auto-breakeven: if price rises above buy price + fees, move stop loss to buy price
        if 'last_buy_price' in self.state and self.state['last_buy_price'] > 0:
            buy_price = self.state['last_buy_price']
            fee_pct = 0.00075  # Maker fee with BNB discount
            breakeven_price = buy_price * (1 + fee_pct * 2)  # entry + exit fees

            # Initialize trailing stop at breakeven if not set
            if self.state['trailing_stop_level'] is None:
                if current_price > breakeven_price:
                    self.state['trailing_stop_level'] = breakeven_price
                    logger.info(f"🎯 Trailing stop initialized at breakeven: {breakeven_price:.2f}€")

        # Trailing stop based on peak
        if self.state['peak_value'] > 0:
            # Activation threshold: price must rise 1% above peak * 0.98
            activation_threshold = self.state['peak_value'] * (1 + self.config.get('trailing_activation_pct', 0.01))
            if current_price >= activation_threshold:
                # Set trailing stop at 2% below peak
                new_stop = self.state['peak_value'] * (1 - self.config.get('trailing_stop_pct', 0.02))
                # Only move stop UP, never down
                if self.state['trailing_stop_level'] is None or new_stop > self.state['trailing_stop_level']:
                    self.state['trailing_stop_level'] = new_stop

        # Check if price dropped below trailing stop
        if self.state['trailing_stop_level'] is not None:
            if current_price < self.state['trailing_stop_level']:
                logger.warning(f"🚨 Trailing stop triggered: {current_price:.2f}€ < {self.state['trailing_stop_level']:.2f}€")
                return "EXIT"

        return "HOLD"

    async def check_fills(self, client, effective_base=15.0):
        """FIXED: Proper amount tracking, martingale profit calc, order cleanup"""
        for order_id in self.state['placed_order_ids'][:]:
            try:
                status = await asyncio.to_thread(client.fetch_order, order_id, self.config['symbol'])
                if status.get('status') == 'closed':
                    side = status['side']
                    price = float(status.get('average', 0))
                    amount_val = float(status.get('amount', 0))

                    if price <= 0 or amount_val <= 0:
                        continue

                    # Skip if already recorded
                    existing = [o for o in self.state['filled_orders'] if o.get('id') == order_id]
                    if existing:
                        continue

                    self.state['filled_orders'].append({
                        'id': order_id,
                        'side': side,
                        'price': price,
                        'amount': amount_val
                    })

                    if side == 'buy':
                        logger.info(f"✅ BUY filled @ {price}€ x {amount_val:.4f}")
                        # Store buy price for auto-breakeven
                        self.state['last_buy_price'] = price

                        # Find the corresponding sell level and place sell order
                        if 'grid_sell_levels' in self.state and self.state['grid_sell_levels']:
                            target_sell_price = price * (1 + self.config['profit_per_grid'])
                            if self.state['grid_sell_levels']:
                                closest = min(self.state['grid_sell_levels'], key=lambda x: abs(x - target_sell_price))
                                sell_amount = amount_val  # Sell same amount we bought
                                try:
                                    sell_order = await asyncio.to_thread(
                                        client.create_limit_sell_order,
                                        self.config['symbol'],
                                        round(sell_amount, 5),
                                        closest
                                    )
                                    self.state['placed_order_ids'].append(sell_order['id'])
                                    logger.info(f"📈 SELL order placed @ {closest}€ for {sell_amount:.4f}")
                                except Exception as e:
                                    logger.error(f"Failed to place SELL order @ {closest}€: {e}")

                    elif side == 'sell':
                        # FIX: Proper fee calculation — no more 'in dir()' hack
                        fee_rate = 0.00075  # Maker fee
                        fee = price * amount_val * fee_rate

                        # FIX: Find original buy level for martingale profit calculation
                        orig_eur = effective_base  # Default
                        if 'grid_buy_levels' in self.state and self.state['grid_buy_levels']:
                            # Calculate what buy price this sell corresponds to
                            buy_price_est = price / (1 + self.config['profit_per_grid'])
                            try:
                                closest_bp = min(self.state['grid_buy_levels'],
                                                key=lambda x: abs(x - buy_price_est))
                                level_i = self.state['grid_buy_levels'].index(closest_bp)
                                orig_eur = self.martingale.get_size(level_i)
                            except (ValueError, IndexError):
                                pass  # Use default effective_base

                        profit = (self.config['profit_per_grid'] * orig_eur) - fee
                        self.state['total_profit'] += profit
                        self.log_trade(
                            self.config['symbol'], 'SELL', price, amount_val,
                            orig_eur, fee, profit
                        )
                        # Track for optimizer — profit may be negative
                        self.optimizer.add_trade(profit)
                        logger.info(f"💰 SELL filled @ {price}€ | Amount: {amount_val:.4f} | "
                                   f"Profit: {profit:.4f}€ | Total: {self.state['total_profit']:.2f}€")

                    # Remove from placed orders regardless of side
                    if order_id in self.state['placed_order_ids']:
                        self.state['placed_order_ids'].remove(order_id)

            except Exception as e:
                logger.error(f"Fill check error for order {order_id}: {e}")

    async def sync_existing_orders(self, client, current_price):
        logger.info("Syncing orders with exchange...")
        try:
            open_orders = await self.sync_orders(self.config['symbol'])
            # Separate buy and sell orders
            buy_orders = sorted(
                [o for o in open_orders if o['side'] == 'buy'],
                key=lambda x: abs(float(x['price']) - current_price)
            )
            sell_orders_from_grid = [
                o for o in open_orders
                if o['side'] == 'sell'
            ]

            # Cancel excess buy orders beyond grid levels
            num_levels = self.config.get('grid_levels', 5)
            keep_buys = buy_orders[:num_levels]
            cancel_orders_e = buy_orders[num_levels:]

            for o in cancel_orders_e:
                try:
                    await asyncio.to_thread(client.cancel_order, o['id'], self.config['symbol'])
                    logger.info(f"Cancelled excess buy order {o['id']} @ {o['price']}")
                except Exception:
                    pass

            self.state['placed_order_ids'] = [o['id'] for o in keep_buys + sell_orders_from_grid]

            # Calculate actual invested from filled amounts
            total_invested = sum(float(o['price']) * float(o['amount']) for o in keep_buys)
            self.state['total_invested'] = total_invested

            self.state['grid_active'] = len(keep_buys) > 0
            logger.info(
                f"Sync complete: {len(keep_buys)} buy orders, {len(sell_orders_from_grid)} sell orders | "
                f"Invested: {self.state['total_invested']:.2f}€"
            )
        except Exception as e:
            logger.error(f"Sync error: {e}")

    async def close_all_positions(self, client, price):
        try:
            balances = await asyncio.to_thread(client.fetch_balance)
            asset = self.config['symbol'].split('/')[0]
            amount = balances['free'].get(asset, 0)
            if amount > 0.0001:
                await asyncio.to_thread(client.create_market_sell_order, self.config['symbol'], amount)
                logger.info(f"Closed all {asset} positions at {price}€")
        except Exception as e:
            logger.error(f"Close error: {e}")

    async def run(self):
        client = self.client
        try:
            ticker = await asyncio.to_thread(client.fetch_ticker, self.config['symbol'])
            self.state['peak_value'] = ticker['last']
            logger.info(f"Starting {self.config['symbol']} @ {self.state['peak_value']}€")
        except Exception as e:
            logger.error(f"Initial price error: {e}")
            return

        # WebSocket connection with reconnection
        ws_url = f"wss://stream.binance.com:9443/ws/{self.config.get('symbol_ws', 'soleur')}@ticker"
        while True:
            try:
                async with websockets.connect(ws_url, ping_interval=30) as ws:
                    logger.info("WebSocket connected!")
                    while True:
                        raw = await ws.recv()
                        msg = json.loads(raw) if isinstance(raw, str) else raw
                        if msg.get('e') == '24hrTicker':
                            await self.on_tick(float(msg['c']), client)
            except websockets.exceptions.ConnectionClosed:
                logger.warning("WebSocket disconnected. Reconnecting in 5s...")
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"WebSocket error: {e}. Reconnecting in 10s...")
                await asyncio.sleep(10)


if __name__ == "__main__":
    bot = GridBot()
    asyncio.run(bot.run())