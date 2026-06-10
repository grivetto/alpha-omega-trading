#!/usr/bin/env python3
import asyncio
from ccxt.pro import binance
from .base import BaseStrategy, Side, Signal
import numpy as np

class DynamicGridStrategy(BaseStrategy):
    """Grid that adapts spacing in base on order‑book depth & volatility."""
    def __init__(self, exchange, db, symbol, capital, base_levels=3,
                 min_spacing=0.0002, max_spacing=0.005, price_precision=6, amount_precision=6):
        super().__init__(exchange, db, symbol, capital)
        self.base_levels = base_levels
        self.min_spacing = min_spacing
        self.max_spacing = max_spacing
        self.price_precision = price_precision
        self.amount_precision = amount_precision

    async def _calc_spacing(self):
        """Calcola spacing dinamico basato su depth + volatilità."""
        try:
            depth = await self.exchange.fetch_l2_order_book(self.symbol, limit=10)
            bid = depth['bids'][0][0] if depth['bids'] else 0
            ask = depth['asks'][0][0] if depth['asks'] else 0
            spread = (ask - bid) / ((ask + bid) / 2) if (ask + bid) / 2 != 0 else 0

            # Varia lo spacing con una funzione sigmoide su spread
            spacing = self.min_spacing + (self.max_spacing - self.min_spacing) * \
                      (1 / (1 + np.exp(-10 * (spread - 0.001))))
            return max(self.min_spacing, min(self.max_spacing, spacing))
        except Exception as e:
            self.logger.error(f"Error calculating dynamic spacing for {self.symbol}: {e}")
            return (self.min_spacing + self.max_spacing) / 2 # Fallback to average

    async def _sync_grid(self, desired_orders):
        """Compara gli ordini desiderati con gli ordini attivi e li sincronizza.
        Questa è una versione semplificata che si concentra sulla creazione/aggiornamento.
        La logica completa per cancellare/ricreare deve essere gestita in BaseStrategy.
        """
        current_orders = await self.exchange.fetch_open_orders(self.symbol)
        # Per semplicità, cancelliamo tutti gli ordini esistenti e li ricreiamo
        # In un sistema di produzione, si cercherebbe di fare matching per ridurre cancellazioni
        for order in current_orders:
            try:
                await self.exchange.cancel_order(order['id'], self.symbol)
                self.logger.info(f"Cancelled old order {order['id']} for {self.symbol}")
            except Exception as e:
                self.logger.error(f"Error cancelling order {order['id']}: {e}")

        for side, price in desired_orders:
            amount = await self._size(price, price * (1 - self.take_profit_pct if side == Side.BUY else 1 + self.take_profit_pct))
            if amount > 0:
                try:
                    if side == Side.BUY:
                        order = await self.exchange.create_limit_buy_order(self.symbol, amount, price)
                    else:
                        order = await self.exchange.create_limit_sell_order(self.symbol, amount, price)
                    self.logger.info(f"Placed {side.name} limit order for {self.symbol} at {price} with amount {amount}")
                except Exception as e:
                    self.logger.error(f"Error placing {side.name} limit order for {self.symbol} at {price}: {e}")

    async def run(self):
        """Main loop – crea gli ordini di grid con spacing dinamico."""
        self.logger.info(f"Starting DynamicGridStrategy for {self.symbol} with capital {self.initial_capital}")
        while True:
            try:
                spacing = await self._calc_spacing()
                # Genera livelli di prezzo intorno al prezzo corrente
                ticker = await self.exchange.fetch_ticker(self.symbol)
                price = ticker['last']
                desired_orders = []
                for i in range(1, self.base_levels + 1):
                    buy_price = round(price * (1 - i * spacing), self.price_precision)
                    sell_price = round(price * (1 + i * spacing), self.price_precision)
                    desired_orders.append((Side.BUY, buy_price))
                    desired_orders.append((Side.SELL, sell_price))

                # Crea o aggiorna gli ordini
                await self._sync_grid(desired_orders)
                await asyncio.sleep(self.exchange.rateLimit / 1000) # Rispetta il rate limit

            except Exception as e:
                self.logger.error(f"Error in DynamicGridStrategy run loop for {self.symbol}: {e}")
                await asyncio.sleep(60) # Pausa più lunga in caso di errore grave
