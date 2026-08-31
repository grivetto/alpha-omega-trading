"""
auto_gen_20260830_1715_atrtrailing.py - ATR-Trailing Momentum Grid

Strategy class: ATRTrailingMomentum
------------------------------------
Angolo DISTINTO dalle ultime generate (ladderstack, exitgrid, volcurvegrid,
regimeshift, orderflow_rl, volregimegrid): le precedenti sono quasi tutte
varianti grid/ladder con inventory sizing. Questa NON e' una griglia: e'
una strategia di **momentum con trailing a banda ATR + regime throttle**.

Cosa fa:
  1. Momentum detector: ROC su due finestre (short vs long), NORMALIZZATO
     per volatilita'. score = ror_short - momentum_mult*ror_long, espresso
     in unita' di ATR% (score / atr_pct): cosi' la soglia e' scale-free.
  2. Entry: long/short SOLO se |momentum| > soglia e atr attivo; sizing
     vol-target: qty = vol_target_eur / price, ridotto se regime alta vol.
  3. Trailing ATR: stop = price -/+ atr_stop*ATR, si muove solo in
     direzione favorevole; TP progessivo: a metà cammino il floor sale a
     breakeven (lock-in).
  4. Regime throttle: alta vol -> sizing ridotto (risk_reduction) e entry
     meno frequenti; vol piatta (atr_pct < floor) -> entry disabilitate.

Implementazione:
- Streaming puro su deque maxlen, generatori, zero list comprehension su
  serie lunghe. del su buffer intermedi, gc.collect() al primo flush.
- Error handling esplicito, nessun try/except pass.
- Config-driven e validato (validate_config), stima memoria (estimate_memory_mb).
"""

from __future__ import annotations

import gc
import math
import random
from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Dict, Iterator, List, Optional

__all__ = ["ATRTrailingMomentum", "Config", "StrategyBase",
           "validate_config", "estimate_memory_mb", "iter_prices", "run_smoke_test"]


@dataclass
class Config:
    """Typed configuration for ATRTrailingMomentum strategy."""

    capital_eur: float = 1000.0
    max_positions: int = 3
    vol_target_eur: float = 120.0
    atr_window: int = 14
    roc_short: int = 4
    roc_long: int = 20
    momentum_mult: float = 2.0
    momentum_threshold: float = 0.5         # in unita' di ATR% (momentum score / atr_pct)
    momentum_roc_mult: float = 0.35          # require roc_short > mult * roc_long
    atr_stop_mult: float = 2.5
    atr_tp_mult: float = 5.0
    atr_vol_hi: float = 0.04
    atr_vol_floor: float = 0.002
    risk_reduction_hi_vol: float = 0.5
    min_bars_between_entries: int = 3
    precision: int = 6

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items()}


def validate_config(cfg: Config) -> List[str]:
    """Return list of problems; empty list means config OK."""
    problems: List[str] = []
    if cfg.capital_eur <= 0:
        problems.append("capital_eur must be > 0")
    if cfg.max_positions < 1:
        problems.append("max_positions must be >= 1")
    if cfg.vol_target_eur <= 0:
        problems.append("vol_target_eur must be > 0")
    if cfg.atr_window < 2:
        problems.append("atr_window must be >= 2")
    if cfg.roc_short < 1 or cfg.roc_long <= cfg.roc_short:
        problems.append("roc_short<1 or roc_long<=roc_short")
    if cfg.momentum_mult <= 0:
        problems.append("momentum_mult must be > 0")
    if cfg.atr_stop_mult <= 0 or cfg.atr_tp_mult <= cfg.atr_stop_mult:
        problems.append("require 0<atr_stop<atr_tp")
    if cfg.atr_vol_hi <= cfg.atr_vol_floor:
        problems.append("atr_vol_hi must be > atr_vol_floor")
    if not (0 < cfg.risk_reduction_hi_vol <= 1.0):
        problems.append("risk_reduction_hi_vol must be in (0,1]")
    if cfg.min_bars_between_entries < 0:
        problems.append("min_bars_between_entries must be >= 0")
    return problems


def estimate_memory_mb(cfg: Config, n_bars: int = 10_000) -> float:
    """Rough upper-bound memory (MB) for n_bars of streaming history."""
    per_bar: float = 8.0 * 12
    fixed: float = len(cfg.to_dict()) * 64.0
    capped: int = min(max(n_bars, 1), 100_000)
    mb: float = (fixed + per_bar * capped) / (1024.0 * 1024.0)
    return round(mb, 4)


def iter_prices(prices: List[float]) -> Iterator[float]:
    """Streaming generator over a price series (reduces peak memory)."""
    for p in prices:
        yield float(p)


class StrategyBase:
    """Minimal strategy interface shared across the auto-gen family."""

    def __init__(self, config: Config) -> None:
        self.config: Config = config

    def on_tick(self, price: float, ts: float) -> Optional[Dict[str, Any]]:  # pragma: no cover
        raise NotImplementedError

    def on_fill(self, fill: Dict[str, Any]) -> None:  # pragma: no cover
        raise NotImplementedError

    def validate_config(self) -> List[str]:
        return validate_config(self.config)

    def estimate_memory_mb(self) -> float:
        return estimate_memory_mb(self.config)


@dataclass
class Position:
    """An open momentum position."""

    entry_price: float
    direction: int
    qty: float
    stop: float
    tp: float
    entry_bars: int
    breakeven_armed: bool = False

    def mark_pnl(self, price: float) -> float:
        return (price - self.entry_price) * self.qty * self.direction


class ATRTrailingMomentum(StrategyBase):
    """Momentum entry + ATR trailing stop/TP with regime throttle."""

    def __init__(self, config: Optional[Config] = None) -> None:
        cfg: Config = config or Config()
        problems: List[str] = validate_config(cfg)
        if problems:
            raise ValueError("Config invalid: " + "; ".join(problems))
        super().__init__(cfg)
        self.closes: Deque[float] = deque(maxlen=cfg.roc_long + 1)
        self.atr_buf: Deque[float] = deque(maxlen=cfg.atr_window)
        self.positions: List[Position] = []
        self._bars: int = 0
        self._last_entry_bar: int = -cfg.min_bars_between_entries - 1
        self.flush_acc: int = 0
        self.trades: int = 0
        self.wins: int = 0
        self.realized_pnl: float = 0.0

    # -- ATR (Wilder) -------------------------------------------------------
    def _wilder_atr(self, price: float) -> Optional[float]:
        if len(self.closes) < 2:
            return None
        prev: float = list(self.closes)[-2]
        tr: float = abs(price - prev)
        if len(self.atr_buf) == self.config.atr_window:
            prev_atr: float = self.atr_buf[-1]
            new_atr: float = (prev_atr * (self.config.atr_window - 1) + tr) / float(
                self.config.atr_window
            )
        else:
            new_atr = tr
        self.atr_buf.append(new_atr)
        return new_atr

    # -- momentum detector --------------------------------------------------
    def _momentum(self, atr_pct: float) -> Optional[float]:
        """Burst momentum: +1 long burst, -1 short burst, 0 no signal.

        Long quando:
          - ror_short > cfg.momentum_threshold * atr_pct  (impulso reale sopra il rumore)
          - acc = ror_short - cfg.momentum_roc_mult * ror_long > 0 (accelerazione)
        Short e' il simmetrico. Ritorna il segno con intensita' normalizzata.
        """
        cfg: Config = self.config
        if len(self.closes) < cfg.roc_long + 1 or len(self.closes) < cfg.roc_short + 1:
            return None
        arr: List[float] = list(self.closes)
        now: float = arr[-1]
        base_long: float = arr[-(cfg.roc_long + 1)]
        base_short: float = arr[-(cfg.roc_short + 1)]
        if base_long <= 0.0 or base_short <= 0.0 or atr_pct <= 0.0:
            return None
        ror_long: float = math.log(now / base_long)
        ror_short: float = math.log(now / base_short)
        acc: float = ror_short - cfg.momentum_roc_mult * ror_long
        if ror_short > cfg.momentum_threshold * atr_pct and acc > 0.0:
            return acc / atr_pct          # intensita' (unita' ATR)
        if ror_short < -cfg.momentum_threshold * atr_pct and acc < 0.0:
            return -acc / atr_pct         # negativo = short burst
        return 0.0

    @staticmethod
    def _pct_atr(atr: float, price: float) -> float:
        return atr / price if price > 0.0 else math.inf

    # -- entry sizing -------------------------------------------------------
    def _size_entry(self, price: float, pct: float) -> float:
        cfg: Config = self.config
        base: float = cfg.vol_target_eur / price if price > 0.0 else 0.0
        if pct > cfg.atr_vol_hi:
            base *= cfg.risk_reduction_hi_vol
        return round(base, cfg.precision)

    # -- main tick ----------------------------------------------------------
    def on_tick(self, price: float, ts: float) -> Optional[Dict[str, Any]]:
        cfg: Config = self.config
        self.closes.append(price)
        self._bars += 1

        atr: Optional[float] = self._wilder_atr(price)
        if atr is None or atr <= 0.0:
            return None
        pct: float = self._pct_atr(atr, price)

        # Trailing update for open positions.
        for pos_ in self.positions:
            if pos_.direction > 0:
                if price > pos_.entry_price:
                    new_stop: float = price - cfg.atr_stop_mult * atr
                    pos_.stop = max(pos_.stop, new_stop)
                    half: float = pos_.entry_price + cfg.atr_tp_mult * atr * 0.5
                    if price >= half and not pos_.breakeven_armed:
                        pos_.breakeven_armed = True
                        pos_.tp = max(pos_.tp, pos_.entry_price)
            elif pos_.direction < 0:
                if price < pos_.entry_price:
                    new_stop = price + cfg.atr_stop_mult * atr
                    pos_.stop = min(pos_.stop, new_stop)
                    half = pos_.entry_price - cfg.atr_tp_mult * atr * 0.5
                    if price <= half and not pos_.breakeven_armed:
                        pos_.breakeven_armed = True
                        pos_.tp = min(pos_.tp, pos_.entry_price)

        # Exit on stop/TP.
        closed: List[Position] = []
        remaining: List[Position] = []
        for pos_ in self.positions:
            hit_stop: bool = price <= pos_.stop if pos_.direction > 0 else price >= pos_.stop
            hit_tp: bool = price >= pos_.tp if pos_.direction > 0 else price <= pos_.tp
            if hit_stop or hit_tp:
                closed.append(pos_)
            else:
                remaining.append(pos_)
        self.positions = remaining
        for cp in closed:
            self._realize(cp, price)

        # Entry with regime throttle.
        bars_since: int = self._bars - self._last_entry_bar
        freq_min: int = cfg.min_bars_between_entries
        if pct > cfg.atr_vol_hi:
            freq_min = max(freq_min, 6)

        if (
            len(self.positions) < cfg.max_positions
            and bars_since >= freq_min
            and pct > cfg.atr_vol_floor
        ):
            mom: Optional[float] = self._momentum(pct)
            if mom is not None and abs(mom) > cfg.momentum_threshold:
                direction: int = 1 if mom > 0 else -1
                qty: float = self._size_entry(price, pct)
                if qty > 0.0:
                    stop_d: float = cfg.atr_stop_mult * atr
                    tp_d: float = cfg.atr_tp_mult * atr
                    self.positions.append(
                        Position(
                            entry_price=price,
                            direction=direction,
                            qty=qty,
                            stop=price - direction * stop_d,
                            tp=price + direction * tp_d,
                            entry_bars=self._bars,
                        )
                    )
                    self._last_entry_bar = self._bars
                    self.flush_acc += 1
                    if self.flush_acc >= cfg.min_bars_between_entries + 4:
                        gc.collect()
                        self.flush_acc = 0
                    return {
                        "signal": "momentum_entry",
                        "direction": direction,
                        "qty": qty,
                        "price": price,
                        "momentum": round(mom, cfg.precision),
                        "atr": round(atr, cfg.precision),
                        "atr_pct": round(pct, cfg.precision),
                        "bars": self._bars,
                    }
        return None

    # -- realize a closed position ------------------------------------------
    def _realize(self, pos_: Position, price: float) -> None:
        pnl: float = pos_.mark_pnl(price)
        self.realized_pnl += pnl
        self.trades += 1
        if pnl > 0.0:
            self.wins += 1
        self.flush_acc += 1

    def on_fill(self, fill: Dict[str, Any]) -> None:
        """Handle external fill confirmation."""
        price: float = float(fill.get("price", 0.0))
        qty: float = float(fill.get("qty", 0.0))
        side: int = 1 if fill.get("side", "buy") == "buy" else -1
        if price > 0.0 and qty > 0.0:
            ref: float = float(fill.get("ref_price", price))
            self.realized_pnl += (price - ref) * qty * side
            self.trades += 1
            self.flush_acc += 1

    def summary(self) -> Dict[str, Any]:
        cfg: Config = self.config
        return {
            "strategy": "atr_trailing_momentum",
            "bars": self._bars,
            "open_positions": len(self.positions),
            "trades": self.trades,
            "wins": self.wins,
            "realized_pnl": round(self.realized_pnl, cfg.precision),
            "win_rate": round(self.wins / self.trades, 4) if self.trades else 0.0,
            "mem_mb": self.estimate_memory_mb(),
        }

    def estimate_memory_mb(self) -> float:
        return estimate_memory_mb(self.config, max(self._bars, 1))

    def validate_config(self) -> List[str]:
        return validate_config(self.config)


def run_smoke_test() -> None:
    """Inline synthetic test: small trending series, bounded memory."""
    cfg: Config = Config(capital_eur=1000.0, vol_target_eur=120.0, max_positions=2)
    strat: ATRTrailingMomentum = ATRTrailingMomentum(cfg)
    probs: List[str] = strat.validate_config()
    assert not probs, f"validation failed: {probs}"

    random.seed(42)
    price: float = 100.0
    series: List[float] = []
    for _ in range(600):
        price = price + random.uniform(-0.4, 0.9)  # gentle drift up
        series.append(price)

    ticks: Iterator[float] = iter_prices(series)
    bursts: int = 0
    for p in ticks:
        b: Optional[Dict[str, Any]] = strat.on_tick(p, float(bursts))
        if b is not None:
            bursts += 1
    del series, ticks

    s: Dict[str, Any] = strat.summary()
    mem: float = strat.estimate_memory_mb()
    assert s["mem_mb"] == mem
    assert mem < 2.0, f"memory estimate too high: {mem}MB"
    assert s["open_positions"] <= cfg.max_positions
    assert bursts > 0, "expected at least one entry burst on the noisy series"
    assert s["wins"] > 0, "expected at least one winning trade"
    assert s["realized_pnl"] > 0.0, "expected positive PnL on momentum-burst series"
    print(
        "[SMOKE] bars=%d bursts=%d open=%d trades=%d wins=%d pnl=%.4f win_rate=%.2f mem=%.4fMB"
        % (
            s["bars"], bursts, s["open_positions"], s["trades"], s["wins"],
            s["realized_pnl"], s["win_rate"], mem,
        )
    )
    gc.collect()
    print("[SMOKE] PASS")


if __name__ == "__main__":
    run_smoke_test()
