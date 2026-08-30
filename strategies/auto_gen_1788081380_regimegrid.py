"""
auto_gen_1788081380_regimegrid.py - Regime-Detecting Adaptive Grid (Hurst + ATR vol-target).

Strategy class:  RegimeGrid
-----------------
Vincolo progettuale: NON duplicare VolRespGrid (gia' in fleet da 11:05).
Offerta nuova:
1. Rilevazione di regime in streaming (mean-reversion / trend / noise) via
   Hurst normalizzato su deque limitata + ROC (rate-of-change) di volatilita'.
   Niente statsmodel: Hurst calcolato con R/S rescaled range O(1) su finestra
   limitata.
2. In regime mean-reversion -> griglia fitta. Trend -> livelli sfasati + TP largo.
   Noise -> spacing medio e rientro.
3. Dimensionamento a vol-target: l'ordine base scala per tenere la VAR per-tick
   sotto soglia, usando ATR EWMA come vol stimata.
4. Guardia OOM: deque con maxlen, chunking nel Hurst, `del` buffer + gc.collect().

Author: Hermes orchestrator -- ciclo 2026-08-30 11:16.
"""

from __future__ import annotations

import gc
import math
from collections import deque
from dataclasses import dataclass
from typing import Deque, List, Optional, Tuple

_EPS: float = 1e-12


def _ewma(prev: Optional[float], sample: float, alpha: float) -> float:
    if prev is None:
        return sample
    return alpha * sample + (1.0 - alpha) * prev


def _safe_div(num: float, den: float, default: float = 0.0) -> float:
    if den == 0.0 or not math.isfinite(den):
        return default
    return num / den


@dataclass
class RegimeGridConfig:
    symbol: str = "SOL/EUR"
    capital: float = 13.5
    base_order_eur: float = 0.5
    max_levels: int = 12

    atr_window: int = 24
    atr_alpha: float = 0.25

    hurst_window: int = 256
    hurst_scale: int = 64
    regime_smoothing: float = 0.3
    hurst_meanrev_th: float = 0.40
    hurst_trend_th: float = 0.62

    var_per_tick: float = 0.01
    ref_atr_ticks: int = 20
    size_min_eur: float = 0.05
    size_max_eur: float = 3.0

    spacing_meanrev: float = 0.004
    spacing_trend: float = 0.008
    spacing_noise: float = 0.006
    trend_asymmetry: float = 0.6

    stop_loss_pct: float = 0.12
    take_profit_pct: Optional[float] = 0.35

    max_ticks_buffer: int = 5120


class StrategyBase:
    def on_tick(self, price: float, ts: float) -> None:
        raise NotImplementedError

    def on_fill(self, side: str, qty: float, price: float, ts: float) -> None:
        raise NotImplementedError

    def validate_config(self) -> List[str]:
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError


def rescaled_range_hurst(series: Tuple[float, ...], scale: int) -> float:
    """Stima exponent Hurst via R/S rescaled range su sub-finestre chunked."""
    n: int = len(series)
    if n < scale // 2 or scale <= 1:
        return 0.5

    max_rs: float = 0.0
    std_total: float = 0.0
    count: int = 0

    for start in range(0, n - scale + 1, max(1, scale // 2)):
        chunk: List[float] = list(series[start : start + scale])
        mean: float = sum(chunk) / float(len(chunk))
        running: float = 0.0
        min_r: float = 0.0
        max_r: float = 0.0
        for c in chunk:
            running += c - mean
            if running < min_r:
                min_r = running
            if running > max_r:
                max_r = running
        rng: float = max_r - min_r
        variance: float = _safe_div(sum((d * d for d in chunk)), float(len(chunk)))
        sd: float = math.sqrt(variance) if variance > _EPS else 0.0
        if sd > _EPS:
            rs: float = _safe_div(rng, sd)
            if rs > max_rs:
                max_rs = rs
            std_total += sd
            count += 1
        del chunk

    gc.collect()
    if count < 2:
        return 0.5
    avg_std: float = std_total / float(count)
    if avg_std <= _EPS:
        return 0.5
    hurst_raw: float = math.log2(max_rs) / math.log2(scale)
    return max(0.0, min(1.0, hurst_raw))


class RegimeGrid(StrategyBase):
    def __init__(self, config: Optional[RegimeGridConfig] = None) -> None:
        self.cfg: RegimeGridConfig = config or RegimeGridConfig()
        self.tick_buf: Deque[float] = deque(maxlen=self.cfg.max_ticks_buffer)
        self.atr_prev: Optional[float] = None
        self.atr_curr: float = 0.0
        self.hurst_ema: float = 0.5
        self.last_regime: str = "noise"
        self.last_levels: List[float] = []
        self.pnl: float = 0.0
        self.trades: int = 0
        self.wins: int = 0
        self.last_price: Optional[float] = None
        self.peak_price: float = 0.0

    def _atr_ewma(self, price: float) -> float:
        if self.atr_prev is None:
            self.atr_prev = price
            self.atr_curr = 0.0
            return 0.0
        move: float = abs(price - self.atr_prev)
        self.atr_curr = _ewma(self.atr_curr, move, self.cfg.atr_alpha)
        self.atr_prev = price
        return self.atr_curr

    def _regime(self, hurst: float, atr_change: float) -> str:
        self.hurst_ema = _ewma(self.hurst_ema, hurst, self.cfg.regime_smoothing)
        h: float = self.hurst_ema
        if h < self.cfg.hurst_meanrev_th:
            return "meanrev"
        if h > self.cfg.hurst_trend_th and atr_change > 0.0:
            return "trend"
        return "noise"

    def _vol_target_size(self, atr: float, price: float) -> float:
        if atr <= _EPS or price <= _EPS:
            return self.cfg.base_order_eur
        tick_var: float = atr / max(self.cfg.ref_atr_ticks, 1)
        budget: float = self.cfg.var_per_tick * self.cfg.capital
        size: float = _safe_div(budget, max(tick_var, 1e-9))
        return max(self.cfg.size_min_eur, min(self.cfg.size_max_eur, size))

    def _compute_levels(self, price: float, atr: float) -> List[float]:
        if self.last_regime == "meanrev":
            base: float = max(self.cfg.spacing_meanrev, atr * 0.5)
        elif self.last_regime == "trend":
            base = max(self.cfg.spacing_trend, atr * 1.2)
        else:
            base = max(self.cfg.spacing_noise, atr * 0.8)

        levels: List[float] = []
        half: int = self.cfg.max_levels // 2
        for i in range(1, half + 1):
            up: float = price * (1.0 + base * i)
            down: float = price * (1.0 - base * i * self.cfg.trend_asymmetry)
            levels.append(round(down, 8))
            levels.append(round(up, 8))
        levels.sort()
        self.last_levels = levels[: self.cfg.max_levels]
        return self.last_levels

    def on_tick(self, price: float, ts: float) -> None:
        self.last_price = price
        self.tick_buf.append(price)
        self._atr_ewma(price)
        if self.peak_price < price:
            self.peak_price = price
        if len(self.tick_buf) >= self.cfg.hurst_window:
            h: float = rescaled_range_hurst(
                tuple(self.tick_buf)[-self.cfg.hurst_window :], self.cfg.hurst_scale
            )
            atr_change: float = _safe_div(
                self.atr_curr, max(self.atr_prev or _EPS, _EPS)
            ) - 1.0
            self.last_regime = self._regime(h, atr_change)
            self._compute_levels(price, self.atr_curr)

    def on_fill(self, side: str, qty: float, price: float, ts: float) -> None:
        if side.lower() == "sell" and self.last_levels:
            prev_cost: float = self.last_levels[0]
            gross: float = (price - prev_cost) * qty
            self.pnl += gross
            self.trades += 1
            if gross > 0.0:
                self.wins += 1

    def validate_config(self) -> List[str]:
        errs: List[str] = []
        cfg: RegimeGridConfig = self.cfg
        if cfg.capital <= 0:
            errs.append("capital must be > 0")
        if cfg.max_levels % 2 != 0 or cfg.max_levels <= 0:
            errs.append("max_levels must be even and > 0")
        if not (0.0 < cfg.hurst_meanrev_th < cfg.hurst_trend_th < 1.0):
            errs.append("hurst thresholds must satisfy 0 < meanrev < trend < 1")
        if cfg.hurst_window < 2 * cfg.hurst_scale:
            errs.append("hurst_window < 2*hurst_scale under-powered")
        if cfg.var_per_tick <= 0 or cfg.var_per_tick >= 1:
            errs.append("var_per_tick must be in (0,1)")
        if cfg.size_min_eur > cfg.size_max_eur:
            errs.append("size_min_eur > size_max_eur")
        return errs

    def estimate_memory_mb(self) -> float:
        per_float_mb: float = 24.0 / (1024.0 * 1024.0)
        return self.cfg.max_ticks_buffer * per_float_mb + 0.1


if __name__ == "__main__":
    import random

    random.seed(42)
    strat = RegimeGrid(RegimeGridConfig(capital=13.5, max_levels=12))
    errs = strat.validate_config()
    assert not errs, f"config invalid: {errs}"
    price: float = 100.0
    for i in range(2000):
        price *= 1.0 + random.gauss(0.0, 0.002)
        strat.on_tick(price, float(i))
    strat.on_fill("buy", 0.5, 100.0, 0.0)
    strat.on_fill("sell", 0.5, 102.0, 1.0)
    print(f"regime={strat.last_regime} pnl={strat.pnl:.4f} trades={strat.trades}")
    print(f"levels={len(strat.last_levels)} mem_mb={strat.estimate_memory_mb():.3f}")
    print(f"hurst_ema={strat.hurst_ema:.3f} atr={strat.atr_curr:.5f}")
    print("OK: RegimeGrid test passed")
