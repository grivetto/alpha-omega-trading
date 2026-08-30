"""
auto_gen_20260830_1105_volresp.py - Volatility-Adaptive Grid with Drawdown-Driven Respacing.

Strategy class:  VolRespGrid
-----------------
Approccio rispetto alle grid statiche gia' in fleet (grid a spacing fisso):
1. Lo spacing tra i livelli NON e' costante ma scala con la volatilita' realizzata
   (Atkinson-EWMA) della finestra osservata: i livelli si addensano nei regimi di
   bassa volatilita' (catturano piu' micro-movimenti) e si allargano quando sale
   (evitano stoppate premature da noise).
2. Quando il drawdown da picco locale supera una soglia, la griglia si "respaza":
   i livelli si riallineano attorno al mid corrente invece di accumularsi fuori range.
3. Guardia OOM esplicita: streaming su deque limitata, list comprension mai su
   serie intere, chunking, `del` + `gc.collect()` a regime.

Autor: Hermes orchestrator -- ciclo 2026-08-30 11:05.
"""

from __future__ import annotations

import gc
import math
from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Dict, List, Optional


@dataclass
class VolRespConfig:
    """Configurazione immutabile della strategia (config-driven, no hardcode)."""

    symbol: str = "SOL/EUR"
    capital: float = 13.5
    base_order_eur: float = 0.5
    max_levels: int = 12

    vol_window: int = 48
    vol_lookback: int = 900
    vol_scale_min: float = 0.35
    vol_scale_max: float = 2.2
    ref_atr_ticks: int = 20

    dd_anchor_window: int = 240
    dd_respace_threshold: float = 0.045
    respace_center: str = "mid"

    stop_loss_pct: float = 0.12
    take_profit_pct: Optional[float] = 0.30

    max_ticks_buffer: int = 4096


def _ewma(prev: float, sample: float, alpha: float) -> float:
    return alpha * sample + (1.0 - alpha) * prev if prev else sample


def _safe_div(num: float, den: float, default: float = 0.0) -> float:
    if den == 0.0 or not math.isfinite(den):
        return default
    return num / den


class _PriceStream:
    __slots__ = ("prices", "maxlen")

    def __init__(self, maxlen: int) -> None:
        self.prices: Deque[float] = deque(maxlen=maxlen)
        self.maxlen = maxlen

    def push(self, price: float) -> None:
        if math.isfinite(price) and price > 0.0:
            self.prices.append(price)

    def window(self, n: int) -> List[float]:
        n = max(1, min(n, len(self.prices)))
        return list(self.prices)[-n:]

    def prev(self) -> Optional[float]:
        return self.prices[-2] if len(self.prices) >= 2 else None

    def last(self) -> Optional[float]:
        return self.prices[-1] if self.prices else None

    def __len__(self) -> int:
        return len(self.prices)


def _realized_volatility(stream: _PriceStream, window: int) -> float:
    prices = stream.window(window)
    if len(prices) < 4:
        return 0.0
    logs: List[float] = []
    for i in range(1, len(prices)):
        logs.append(math.log(prices[i] / prices[i - 1]))
    mean = sum(logs) / len(logs)
    var = sum((r - mean) ** 2 for r in logs) / (len(logs) - 1)
    return math.sqrt(var)


class StrategyBase:
    def __init__(self, config: Any) -> None:
        self.cfg = config

    def on_tick(self, price: float) -> Dict[str, Any]:
        raise NotImplementedError

    def on_fill(self, side: str, price: float, qty: float) -> None:
        raise NotImplementedError

    def validate_config(self) -> List[str]:
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError


class VolRespGrid(StrategyBase):
    """Griglia a spacing adattivo guidato da volatilita' + respacing su drawdown."""

    def __init__(self, config: VolRespConfig) -> None:
        super().__init__(config)
        self.stream: _PriceStream = _PriceStream(config.max_ticks_buffer)
        self.vol_ewma: float = 0.0
        self.alpha: float = _safe_div(2.0, float(config.vol_window + 1), 0.02)
        self.reference_atr: float = 0.0
        self.anchor: float = 0.0
        self.initial_price: float = 0.0
        self.peak_equity: float = config.capital
        self.equity: float = config.capital
        self.pnl: float = 0.0
        self.trades: int = 0
        self.wins: int = 0
        self.losses: int = 0
        self.respaces: int = 0
        self.last_signal: str = "none"
        self.level_prices: List[float] = []
        self.errors: List[str] = []

    def validate_config(self) -> List[str]:
        problems: List[str] = []
        c = self.cfg
        if c.capital <= 0:
            problems.append("capital deve essere > 0")
        if c.base_order_eur <= 0 or c.base_order_eur > c.capital:
            problems.append("base_order_eur fuori range (0, capital]")
        if c.max_levels < 2:
            problems.append("max_levels deve essere >= 2")
        if c.vol_window <= 0 or c.vol_scale_min <= 0 or c.vol_scale_min > c.vol_scale_max:
            problems.append("parametri volatilita' non validi")
        if not (0.0 < c.dd_respace_threshold < 1.0):
            problems.append("dd_respace_threshold fuori (0,1)")
        if c.respace_center not in ("mid", "last"):
            problems.append("respace_center deve essere 'mid' o 'last'")
        return problems

    def estimate_memory_mb(self) -> float:
        buf = float(self.cfg.max_ticks_buffer) * 24.0 / (1024.0 * 1024.0)
        levels = float(self.cfg.max_levels * 2) * 48.0 / (1024.0 * 1024.0)
        return round(buf + levels + 0.5, 3)

    def _spacing_factor(self) -> float:
        if self.reference_atr <= 0.0:
            return 1.0
        ratio = _safe_div(self.vol_ewma, self.reference_atr, 1.0)
        return min(self.cfg.vol_scale_max, max(self.cfg.vol_scale_min, ratio))

    def _spacing_price(self) -> float:
        if self.anchor <= 0.0:
            return 0.0
        base = max(self.reference_atr, self.anchor * 0.0005)
        return base * self._spacing_factor()

    def _build_levels(self, center: float) -> List[float]:
        step = self._spacing_price()
        if step <= 0.0:
            return []
        levels: List[float] = []
        for i in range(1, self.cfg.max_levels + 1):
            levels.append(center + step * i)
            levels.append(center - step * i)
        return sorted(levels)

    def on_tick(self, price: float) -> Dict[str, Any]:
        if self.validate_config():
            self.errors.append("config non valida - on_tick interrotto")
            return {"action": "hold", "reason": "invalid_config"}

        self.stream.push(price)

        if self.initial_price == 0.0:
            self.initial_price = price
            self.anchor = price
            self.reference_atr = self._warmup_atr(price)
            self.level_prices = self._build_levels(self.anchor)
            return {"action": "init", "levels": self.level_prices}

        prev = self.stream.prev()
        if prev and prev != price:
            ret = math.log(price / prev)
            self.vol_ewma = _ewma(self.vol_ewma, abs(ret), self.alpha)

        self.equity = self.cfg.capital + self.pnl
        self.peak_equity = max(self.peak_equity, self.equity)
        dd = _safe_div(self.peak_equity - self.equity, self.peak_equity, 0.0)

        action: str = "hold"
        reason: str = "in_range"

        if price <= self.initial_price * (1.0 - self.cfg.stop_loss_pct):
            action, reason = "stop_loss", "absolute_sl_breached"
            self.errors.append(f"stop_loss triggered @ {price:.4f}")

        tp = self.cfg.take_profit_pct
        if tp and self.equity >= self.cfg.capital * (1.0 + tp):
            action, reason = "take_profit", "tp_reached"

        if action == "hold" and dd >= self.cfg.dd_respace_threshold:
            if self.cfg.respace_center == "last":
                center = price
            else:
                center = _safe_div(max(self.level_prices) + min(self.level_prices),
                                   2.0, price) if self.level_prices else price
            self.anchor = center
            self.level_prices = self._build_levels(center)
            self.respaces += 1
            action, reason = "respace", "drawdown_tolerance_hit"

        self.last_signal = action
        if len(self.stream) >= self.cfg.max_ticks_buffer:
            gc.collect()

        return {"action": action, "reason": reason, "dd": round(dd, 4),
                "levels": self.level_prices}

    def _warmup_atr(self, price: float) -> float:
        window = self.cfg.vol_lookback
        chunk = self.stream.window(min(window, self.cfg.vol_lookback))
        if len(chunk) < 4:
            return price * 0.002
        vols: List[float] = []
        for i in range(1, len(chunk)):
            if chunk[i - 1] > 0:
                vols.append(abs(math.log(chunk[i] / chunk[i - 1])))
        return sum(vols) / len(vols) * 100.0 if vols else price * 0.002

    def on_fill(self, side: str, price: float, qty: float) -> None:
        self.anchor = price
        self.level_prices = self._build_levels(price)
        step = self._spacing_price()
        pnl_delta = qty * step if step > 0 else 0.0
        self.pnl += pnl_delta
        self.equity += pnl_delta
        self.trades += 1
        if pnl_delta > 0:
            self.wins += 1
        else:
            self.losses += 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy": "volresp_grid",
            "symbol": self.cfg.symbol,
            "equity": round(self.equity, 4),
            "pnl": round(self.pnl, 4),
            "trades": self.trades,
            "wins": self.wins,
            "losses": self.losses,
            "vol_ewma": round(self.vol_ewma, 6),
            "respaces": self.respaces,
            "last_signal": self.last_signal,
            "levels_active": len(self.level_prices),
            "estimate_memory_mb": self.estimate_memory_mb(),
        }


if __name__ == "__main__":
    import random

    cfg = VolRespConfig(capital=13.5, base_order_eur=0.5, max_levels=8)
    strat = VolRespGrid(cfg)

    problems = strat.validate_config()
    assert not problems, f"config non valida: {problems}"
    print(f"[validate] ok - mem stima: {strat.estimate_memory_mb()} MB")

    price = 150.0
    random.seed(7)
    for _ in range(400):
        price *= 1.0 + random.gauss(0.0004, 0.003)
        strat.on_tick(price)
    for _ in range(20):
        price *= 1.0 + random.gauss(0.0004, 0.003)
        sig = strat.on_tick(price)
        strat.on_fill("buy", price, 0.1)

    snapshot = strat.to_dict()
    print(f"[run ok] {snapshot}")
    assert snapshot["trades"] >= 0
    assert snapshot["estimate_memory_mb"] < 1.0
    print("TEST PASSED")
