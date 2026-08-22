"""ATLAS DCA Strategy - Dollar Cost Averaging con dip-acceleration e failover gate.

Strategia complementare alla Grid:
- Acquisti periodici a importo fisso (DCA classico)
- Se il prezzo scende sotto il massimo recente di X% (dip), accelera con importo maggiorato
- Failover gate: se configurato un URL di health del nodo primario, NON piazza mai
  quando il primario e' vivo (evita doppio trading sullo stesso account)
"""
from __future__ import annotations

import asyncio
import logging
import time
import urllib.request
from typing import Dict, List

from atlas.connector.models import Ticker
from atlas.execution.models import OrderRequest, OrderSide, OrderType, TimeInForce

logger = logging.getLogger(__name__)


class DCAStrategy:
    """DCA strategy: periodic buys, dip-accelerated, failover-aware."""

    def __init__(self, strategy_id: str, symbols: List[str], exchanges: List[str], params: dict, event_bus=None):
        self.strategy_id = strategy_id
        self.symbols = symbols
        self.exchanges = exchanges
        self.params = params
        self.event_bus = event_bus

        self._interval_min = int(params.get("interval_min", 60))           # min tra acquisti
        self._order_value_eur = float(params.get("order_value_eur", 10.0)) # valore per acquisto
        self._dip_pct = float(params.get("dip_pct", 0.03))                 # soglia dip (3%)
        self._dip_multiplier = float(params.get("dip_multiplier", 2.0))    # x2 su dip
        self._max_value_eur = float(params.get("max_value_eur", 15.0))     # cap per acquisto
        self._failover_url = params.get("failover_url", "")                # health del nodo primario
        self._failover_timeout = float(params.get("failover_timeout", 5.0))
        self._last_buy_time: Dict[str, int] = {}
        self._high_watermark: Dict[str, float] = {}
        self._running = False
        self._levels = 1  # dedup generico: max 1 ordine open per symbol

    def _primario_vivo(self) -> bool:
        """True se il nodo primario risponde (=> questo nodo NON deve tradare)."""
        if not self._failover_url:
            return False
        try:
            with urllib.request.urlopen(self._failover_url, timeout=self._failover_timeout) as resp:
                return resp.status == 200
        except Exception:
            return False

    def _order_value(self, symbol: str, current_price: float) -> float:
        """Importo dell'acquisto: base, x2 se in dip (prezzo sotto high watermark)."""
        hwm = self._high_watermark.get(symbol, current_price)
        self._high_watermark[symbol] = max(hwm, current_price)

        drop = (hwm - current_price) / hwm if hwm > 0 else 0.0
        if drop >= self._dip_pct:
            value = min(self._order_value_eur * self._dip_multiplier, self._max_value_eur)
            logger.info(f"DCA {symbol}: DIP {drop:.1%} -> order value {value:.2f} EUR")
            return value
        return self._order_value_eur

    async def on_tick(self, symbol: str, exchange: str, ticker: Ticker) -> List[OrderRequest]:
        """Genera ordine DCA se e' il momento e il primario e' giu'."""
        key = f"{exchange}:{symbol}"
        now = int(time.time())

        # Throttle: un acquisto ogni interval_min
        last = self._last_buy_time.get(key, 0)
        if now - last < self._interval_min * 60:
            return []
        self._last_buy_time[key] = now

        # Failover gate: se il primario e' vivo, questo nodo NON trade
        if self._primario_vivo():
            logger.debug(f"DCA {key}: nodo primario vivo, failover inattivo")
            return []

        if ticker.last <= 0:
            return []

        value = self._order_value(symbol, ticker.last)
        amount = value / ticker.last

        logger.info(f"DCA signal: {key} buy {amount:.8f} ({value:.2f} EUR) @ {ticker.last:.2f}")
        return [
            OrderRequest(
                symbol=symbol,
                side=OrderSide.BUY,
                type=OrderType.MARKET,
                amount=amount,
                price=None,
                time_in_force=TimeInForce.IOC,
                exchange=exchange,
                strategy_id=self.strategy_id,
            )
        ]
