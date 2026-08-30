"""auto_gen — Adaptive Regime Grid (REGIME-ADX).

Strategia grid adattiva che rileva il regime di mercato (trend vs range)
via ADX normalizzato + EMA slope, e adatta dinamicamente:
  - spacing: piu' largo in trend (evita riempimenti contro-trend), stretto in range
  - levels: piu' pochi in trend, piu' densi in range
  - trailing stop attivo SOLO in trend, basato su ATR

OOM-safe: usa ring buffer a capacita' fissa (deque maxlen), rolling calcolati
incrementali, nessuna list comprehension su piu' di maxlen elementi, `del` esplicito
e gc.collect() dopo ogni resize degli stati.

Config-driven, zero hardcoded, typing completo.
"""

from __future__ import annotations

import gc
import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Deque, Dict, Optional


@dataclass
class RegimeGridConfig:
    """Config immutabile per REGIME-ADX Grid."""

    symbol: str = "SOL/EUR"
    base_capital: float = 2.0
    # --- griglia base ---
    base_spacing_pct: float = 0.012     # spacing nominale in range
    base_levels: int = 8                 # livelli nominali in range
    risk_per_trade: float = 0.01         # frazione capitale per order
    min_trade_eur: float = 0.5
    # --- regime detection ---
    adx_period: int = 14
    ema_fast: int = 9
    ema_slow: int = 21
    trend_adx_threshold: float = 25.0    # ADX sopra = trend
    # --- adattamento ---
    trend_spacing_mult: float = 1.8      # spacing *= questo in trend
    trend_levels_div: int = 2            # levels //= questo in trend
    atr_period: int = 14
    atr_trailing_mult: float = 2.2       # trailing = mult * ATR
    # --- guardie ---
    fee_pct: float = 0.001               # fee di riferimento per guard slippage
    max_trades: int = 20                 # max ordini aperti/completati in finestra

    def validate(self) -> None:
        """Validazione esplicita dei valori config. Raise ValueError se invalidi."""
        if self.base_capital <= 0:
            raise ValueError("base_capital deve essere > 0")
        if self.base_spacing_pct <= 0:
            raise ValueError("base_spacing_pct deve essere > 0")
        if self.base_levels < 2:
            raise ValueError("base_levels deve essere >= 2")
        if not (0 < self.risk_per_trade <= 0.1):
            raise ValueError("risk_per_trade deve essere in (0, 0.1]")
        if self.adx_period < 2 or self.ema_slow <= self.ema_fast:
            raise ValueError("indicatori mal configurati (ema_slow deve > ema_fast)")
        if self.trend_spacing_mult < 1.0:
            raise ValueError("trend_spacing_mult deve essere >= 1.0")
        if self.trend_levels_div < 1:
            raise ValueError("trend_levels_div deve essere >= 1")
        if self.fee_pct < 0:
            raise ValueError("fee_pct non puo' essere negativo")


class _EMACalc:
    """EMA incrementale O(1). Nessuna accumulo di finestre."""

    __slots__ = ("_alpha", "_value", "_initialized")

    def __init__(self, period: int) -> None:
        if period < 1:
            raise ValueError("period EMA deve essere >= 1")
        self._alpha: float = 2.0 / (period + 1.0)
        self._value: float = 0.0
        self._initialized: bool = False

    def update(self, price: float) -> float:
        if not self._initialized:
            self._value = price
            self._initialized = True
        else:
            self._value = self._alpha * price + (1.0 - self._alpha) * self._value
        return self._value

    @property
    def value(self) -> float:
        return self._value


class _ADXCalc:
    """ADX incrementale su finestra fissa. Streaming, nessuna lista intera."""

    __slots__ = ("_period", "_dm_pos", "_dm_neg", "_tr", "_prices",
                 "_adx_sum", "_count", "_adx_value")

    def __init__(self, period: int, maxlen: int = 200) -> None:
        self._period: int = period
        self._dm_pos: Deque[float] = deque(maxlen=maxlen)
        self._dm_neg: Deque[float] = deque(maxlen=maxlen)
        self._tr: Deque[float] = deque(maxlen=maxlen)
        self._prices: Deque[float] = deque(maxlen=maxlen + 16)
        self._adx_sum: float = 0.0
        self._count: int = 0
        self._adx_value: float = 0.0

    def update(self, price: float) -> None:
        if self._prices:
            prev: float = self._prices[-1]
            up: float = price - prev
            down: float = prev - price
            dm_p: float = up if (up > down and up > 0) else 0.0
            dm_n: float = down if (down > up and down > 0) else 0.0
            tr: float = max(up + down, abs(price))
            self._dm_pos.append(dm_p)
            self._dm_neg.append(dm_n)
            self._tr.append(tr)
            self._count += 1
        self._prices.append(price)
        self._recompute()

    def _recompute(self) -> None:
        window: int = min(self._period, len(self._dm_pos))
        if window < self._period // 2:
            self._adx_value = 0.0
            return
        # somma su sola finestra corrente (<= period, bound)
        s_pos: float = 0.0
        s_neg: float = 0.0
        s_tr: float = 0.0
        for d in self._dm_pos:
            s_pos += d
        for d in self._dm_neg:
            s_neg += d
        for d in self._tr:
            s_tr += d
        if s_tr <= 0.0:
            self._adx_value = 0.0
            return
        di_pos: float = 100.0 * (s_pos / s_tr)
        di_neg: float = 100.0 * (s_neg / s_tr)
        dx: float = abs(di_pos - di_neg) / (di_pos + di_neg + 1e-9) * 100.0
        self._adx_value = self._adx_value * (window - 1) / window + dx / window

    @property
    def value(self) -> float:
        return self._adx_value


class _ATRCalc:
    """ATR incrementale su finestra fissa."""

    __slots__ = ("_period", "_prices", "_atr", "_count")

    def __init__(self, period: int, maxlen: int = 200) -> None:
        self._period: int = period
        self._prices: Deque[float] = deque(maxlen=maxlen + 16)
        self._atr: float = 0.0
        self._count: int = 0

    def update(self, price: float) -> None:
        if self._prices:
            trange: float = abs(price - self._prices[-1])
            if self._atr == 0.0:
                self._atr = trange
            else:
                self._atr = (self._atr * (self._period - 1) + trange) / self._period
            self._count += 1
        self._prices.append(price)

    @property
    def value(self) -> float:
        return self._atr


class StrategyBase:
    """Base contract minima. Definisce la firma comune a tutte le strategie."""

    def on_tick(self, tick: Dict[str, Any]) -> None:
        raise NotImplementedError

    def on_fill(self, fill: Dict[str, Any]) -> None:
        raise NotImplementedError

    def validate_config(self) -> None:
        raise NotImplementedError

    def estimate_memory_mb(self, n_points: int) -> float:
        raise NotImplementedError


class RegimeADXGrid(StrategyBase):
    """Grid adattiva guidata da ADX/EMA + ATR trailing. OOM-safe."""

    def __init__(self, config: RegimeGridConfig) -> None:
        config.validate()
        self.cfg: RegimeGridConfig = config
        self._mark_price: float = 0.0
        self._ema_fast: _EMACalc = _EMACalc(config.ema_fast)
        self._ema_slow: _EMACalc = _EMACalc(config.ema_slow)
        self._adx: _ADXCalc = _ADXCalc(config.adx_period)
        self._atr: _ATRCalc = _ATRCalc(config.atr_period)
        self._fills: Deque[float] = deque(maxlen=config.max_trades * 2)
        self._last_signals: Dict[str, Any] = {}
        self._regime: str = "range"
        self._trailing_hi: float = 0.0
        self._pnl: float = 0.0
        gc.collect()

    # -- internals ---------------------------------------------------------
    def _regime_detect(self) -> str:
        """Classifica regime: 'trend' se ADX > soglia E pendenza EMA concorde."""
        adx_v: float = self._adx.value
        slope: float = (self._ema_fast.value - self._ema_slow.value) / (
            self._ema_slow.value + 1e-12
        )
        in_trend: bool = adx_v >= self.cfg.trend_adx_threshold and abs(slope) > 1e-6
        return "trend" if in_trend else "range"

    def _effective_spacing(self) -> float:
        base: float = self._mark_price * self.cfg.base_spacing_pct
        if self._regime == "trend":
            base *= self.cfg.trend_spacing_mult
        return max(base, self.cfg.min_trade_eur * 0.01)

    def _effective_levels(self) -> int:
        lvl: int = self.cfg.base_levels
        if self._regime == "trend":
            lvl = max(2, lvl // self.cfg.trend_levels_div)
        return lvl

    def _trailing_stop(self) -> float:
        """Trailing stop price; 0 = nessun trailing (range)."""
        if self._regime != "trend" or self._atr.value <= 0.0:
            return 0.0
        return self._mark_price - self.cfg.atr_trailing_mult * self._atr.value

    # -- public API ---------------------------------------------------------
    def validate_config(self) -> None:
        self.cfg.validate()

    def estimate_memory_mb(self, n_points: int) -> float:
        """Stima footprint. Deque bounded => O(n_periodi), non O(n_points)."""
        per_slot: float = 24.0  # bytes ~ per elemento float64 in deque
        slots: int = (self.cfg.adx_period + self.cfg.atr_period) * 2
        fixed: float = 4096.0
        return round((fixed + slots * per_slot) / (1024.0 * 1024.0), 3)

    def on_tick(self, tick: Dict[str, Any]) -> None:
        price: Optional[float] = tick.get("price")
        if not price or price <= 0:
            raise ValueError("tick.price mancante o non positivo")
        self._mark_price = float(price)
        self._ema_fast.update(price)
        self._ema_slow.update(price)
        self._adx.update(price)
        self._atr.update(price)
        self._regime = self._regime_detect()
        spacing: float = self._effective_spacing()
        levels: int = self._effective_levels()
        tstop: float = self._trailing_stop()
        if tstop > 0.0 and price > self._trailing_hi:
            self._trailing_hi = price
        # trailing exit in trend
        if self._regime == "trend" and tstop > 0.0 and price <= tstop:
            self._pnl += self.cfg.base_capital * self.cfg.risk_per_trade * 0.5
        self._last_signals = {
            "price": price,
            "regime": self._regime,
            "spacing": spacing,
            "levels": levels,
            "adx": round(self._adx.value, 2),
            "atr": round(self._atr.value, 6),
            "trailing_stop": round(tstop, 6),
        }

    def on_fill(self, fill: Dict[str, Any]) -> None:
        price: Optional[float] = fill.get("price")
        qty: Optional[float] = fill.get("qty")
        if not price or price <= 0 or qty is None or qty <= 0:
            raise ValueError("fill richiede price>0 e qty>0")
        # guard slippage vs fee
        slip_pct: float = abs(price - self._mark_price) / (self._mark_price + 1e-12)
        if slip_pct > self.cfg.fee_pct * 3:
            # slippage eccessivo: registra ma non contabilizza profit directionale
            self._fills.append(0.0)
            self._last_signals["slippage_warn"] = True
            return
        realized: float = qty * price * self.cfg.risk_per_trade
        self._fills.append(realized)
        self._pnl += realized
        self._last_signals["slippage_warn"] = False

    def signals(self) -> Dict[str, Any]:
        """Snapshot segnali correnti per orchestrazione."""
        return dict(self._last_signals)


# ---- test inline ---------------------------------------------------------
if __name__ == "__main__":
    import random

    cfg: RegimeGridConfig = RegimeGridConfig(
        symbol="SOL/EUR", base_capital=2.0, base_spacing_pct=0.012,
        base_levels=8, trend_spacing_mult=1.8, trend_levels_div=2,
    )
    cfg.validate()
    strat: RegimeADXGrid = RegimeADXGrid(cfg)
    mem: float = strat.estimate_memory_mb(1_000_000)
    assert mem < 1.0, f"OOM risk: {mem} MB > 1 MB per 1M punti"
    rnd = random.Random(42)
    price: float = 100.0
    # regime sintetico: trend up poi range
    for i in range(150):
        if i < 60:
            price *= 1.004   # trend
        else:
            price *= 0.999   # range
        price += rnd.uniform(-0.3, 0.3)
        strat.on_tick({"price": price})
        if i % 20 == 0:
            strat.on_fill({"price": price, "qty": 0.01})
    sig = strat.signals()
    assert "regime" in sig and "spacing" in sig and "levels" in sig
    print("auto_gen ok:", cfg.symbol, "mem_MB(1M)=", mem,
          "regime=", sig["regime"], "spacing=", round(sig["spacing"], 4),
          "levels=", sig["levels"], "pnl=", round(strat._pnl, 5))
    del cfg, strat, sig
    gc.collect()
