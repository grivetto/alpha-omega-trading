"""
Early Warning System – monitors market anomalies and triggers defensive mode.
"""
import asyncio, logging
from typing import Dict

class EarlyWarningSystem:
    def __init__(self, orchestrator):
        self.orchestrator = orchestrator
        self.logger = logging.getLogger("EarlyWarning")
        # thresholds (can be tuned via config)
        self.volatility_threshold = 0.15  # 15% price swing in short window
        self.liquidity_threshold = 0.005  # 0.5% depth book
        self.risk_score_limit = 0.8

    async def _calculate_volatility(self) -> float:
        """Return recent volatility as % range of last 10 candles."""
        try:
            ohlcv = await self.orchestrator.exchange.fetch_ohlcv(self.orchestrator.bots[0].symbol, "5m", limit=10)
            if not ohlcv:
                return 0.0
            highs = [c[2] for c in ohlcv]
            lows = [c[3] for c in ohlcv]
            max_h = max(highs)
            min_l = min(lows)
            if min_l == 0:
                return 0.0
            return (max_h - min_l) / min_l
        except Exception as e:
            self.logger.debug(f"Volatility calc error: {e}")
            return 0.0

    async def _calculate_liquidity(self) -> float:
        """Very rough liquidity proxy: order book depth relative to price."""
        try:
            # use first bot symbol for reference
            symbol = self.orchestrator.bots[0].symbol
            orderbook = await self.orchestrator.exchange.fetch_order_book(symbol, limit=20)
            bid = orderbook.get("bids", [])
            ask = orderbook.get("asks", [])
            if not bid or not ask:
                return 0.0
            # compute total volume on both sides
            total_volume = sum([b[1] for b in bid]) + sum([a[1] for a in ask])
            price_mid = (bid[0][0] + ask[0][0]) / 2
            if price_mid == 0:
                return 0.0
            # relative depth as % of price
            return total_volume / price_mid
        except Exception as e:
            self.logger.debug(f"Liquidity calc error: {e}")
            return 0.0

    async def _calculate_risk_score(self) -> float:
        """Combine volatility and liquidity into a simple risk score (0‑1)."""
        vol = await self._calculate_volatility()
        liq = await self._calculate_liquidity()
        # normalize: high volatility -> high risk, low liquidity -> high risk
        vol_score = min(vol / self.volatility_threshold, 1.0)
        # assume liquidity threshold is a max acceptable depth; lower depth -> higher risk
        liq_score = 1.0 - min(liq / self.liquidity_threshold, 1.0)
        return (vol_score + liq_score) / 2.0

    async def check_market_conditions(self):
        """Periodic check; activate defensive mode if needed."""
        score = await self._calculate_risk_score()
        self.logger.debug(f"EarlyWarning risk score: {score:.2f}")
        if score >= self.risk_score_limit:
            self.logger.warning("EarlyWarning: high risk detected – activating defensive mode")
            await self.orchestrator.activate_defensive_mode()
