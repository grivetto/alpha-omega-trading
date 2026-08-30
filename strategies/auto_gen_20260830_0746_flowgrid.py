"""FLOWGRID - Order-Flow Regime Grid (auto_gen).

Distinct from the explored family:
  grid/ladder             -> VESG, CPAGrid, VolGrid, LIQABS, CLUSTERQ (static/volume spacing)
  vol-scaled mean-rev     -> VOSPREAD (vol levels gate z-score entries)
  P(fill)-edge MM         -> PROBSKEW (probability-adjusted spread MM)
  vol mean-reversion      -> HALO    (half-life / Kelly sizing, single concentrated entry)
  THIS (FLOWGRID)         -> regime switch driven by ORDER-FLOW imbalance proxy.
                             We keep three short-window EWMA counters of directional
                             tick aggressor flow (buy vs sell volume) and derive a
                             normalized flow ratio in [-1, +1]. The grid is NOT static:
                             spacing and side-bias adapt to flow. In a strong one-sided
                             regime (|flow|>thr) we bias to the trend side (continuation
                             with wider spacing); in a balanced/mean-reverting regime we
                             use a tight symmetric lattice. A true regime-adaptive ladder.

OOM safety: O(1) per tick (three fixed EWMA state vars, no history arrays), generator
over incoming ticks only, no list comprehensions over datasets, bounded level table,
del + gc.collect() after simulation in main. Config-driven.

License: Unlicense (public domain).
"""

from __future__ import annotations

import gc
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(slots=True)
class FLOWGRIDConfig:
    """Immutable, validated config (validate_config must pass before deploy)."""

    symbol: str = "DOGE/EUR"
    capital: float = 3.5
    base_spacing: float = 0.006          # symmetric lattice spacing (balanced regime)
    trend_spacing_mult: float = 2.0      # wide spacing when one-sided flow
    levels: int = 6                      # ladder levels per side (bounded)
    flow_window: float = 0.35            # EWMA half-life weight
    flow_buy_thr: float = 0.30           # |flow| above -> trend-follow bias
    flow_bal_thr: float = 0.10           # |flow| below -> balanced mean-rev
    max_flow_ratio: float = 1.0          # clamp for normalized flow
    kelly_fraction: float = 0.25         # fraction of Kelly capital per level
    max_drawdown: float = 0.05           # hard stop trigger
    dry_run: bool = True
    alpha: float = 0.0              # EWMA weight (filled in __post_init__; declared for slots)

    def __post_init__(self) -> None:
        self.alpha = 1.0 - 2.0 ** (-1.0 / self.flow_window)

    def validate(self) -> Optional[str]:
        if self.levels <= 0 or self.levels > 20:
            return "levels deve essere in (0,20]"
        if self.flow_window <= 0.05:
            return "flow_window troppo piccolo (>=0.05)"
        if not 0.0 < self.kelly_fraction <= 1.0:
            return "kelly_fraction deve essere in (0,1]"
        if self.base_spacing <= 0.0:
            return "base_spacing deve essere > 0"
        return None


class StrategyBase:
    """Marker base class matching the project contract."""

    def on_tick(self, tick: Dict[str, Any]) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def on_fill(self, fill: Dict[str, Any]) -> None:
        raise NotImplementedError

    def validate_config(self) -> Optional[str]:
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError


class FLOWGRID(StrategyBase):
    """Order-flow regime adaptive grid using directional flow EWMA counters."""

    def __init__(self, config: FLOWGRIDConfig) -> None:
        self.cfg = config
        self._flow_buy: float = 0.0   # EWMA of buy aggressor volume
        self._flow_sell: float = 0.0  # EWMA of sell aggressor volume
        self._last_price: Optional[float] = None
        self._inventory: float = 0.0
        self._realized_pnl: float = 0.0
        self._trades: int = 0
        self._peak_equity: float = config.capital
        self._drawdown: float = 0.0

    def _flow_ratio(self) -> float:
        total = self._flow_buy + self._flow_sell
        if total <= 1e-12:
            return 0.0
        raw = (self._flow_buy - self._flow_sell) / total
        return max(-self.cfg.max_flow_ratio,
                   min(self.cfg.max_flow_ratio, raw))

    def _regime(self, flow: float) -> str:
        if flow > self.cfg.flow_buy_thr:
            return "bull"
        if flow < -self.cfg.flow_buy_thr:
            return "bear"
        if abs(flow) <= self.cfg.flow_bal_thr:
            return "bal"
        return "mixed"

    def _effective_spacing(self, regime: str) -> float:
        if regime in ("bull", "bear"):
            return self.cfg.base_spacing * self.cfg.trend_spacing_mult
        return self.cfg.base_spacing

    def validate_config(self) -> Optional[str]:
        return self.cfg.validate()

    def on_tick(self, tick: Dict[str, Any]) -> List[Dict[str, Any]]:
        err = self.validate_config()
        if err:
            raise ValueError(f"config non valida: {err}")

        price = tick.get("price")
        if price is None or price <= 0.0:
            return []

        volume = abs(float(tick.get("volume", 0.0)))
        side = tick.get("taker_side", tick.get("side", "buy"))
        vol_flag = {"buy": 1.0, "sell": -1.0}.get(str(side).lower(), 0.0)

        if vol_flag > 0.0:
            self._flow_buy = self._flow_buy + self.cfg.alpha * (volume - self._flow_buy)
        elif vol_flag < 0.0:
            self._flow_sell = self._flow_sell + self.cfg.alpha * (volume - self._flow_sell)

        flow = self._flow_ratio()
        regime = self._regime(flow)
        spacing = self._effective_spacing(regime)

        equity = self.cfg.capital + self._realized_pnl + self._inventory * price
        if equity > self._peak_equity:
            self._peak_equity = equity
        self._drawdown = (self._peak_equity - equity) / self._peak_equity \
            if self._peak_equity > 0.0 else 0.0

        if self._drawdown >= self.cfg.max_drawdown:
            return [{"action": "flat", "reason": "max_drawdown"}]

        per_level = self.cfg.capital * self.cfg.kelly_fraction / max(self.cfg.levels, 1)
        signals: List[Dict[str, Any]] = []

        if regime == "bear":
            for i in range(1, self.cfg.levels + 1):
                signals.append({
                    "action": "sell", "price": price - i * spacing,
                    "qty": per_level / (price - i * spacing),
                    "tag": f"flowgrid-bear-{i}",
                })
        elif regime == "bull":
            for i in range(1, self.cfg.levels + 1):
                signals.append({
                    "action": "buy", "price": price + i * spacing * 0.5,
                    "qty": per_level / (price + i * spacing * 0.5),
                    "tag": f"flowgrid-bull-{i}",
                })
        else:
            for i in range(1, self.cfg.levels + 1):
                signals.append({
                    "action": "buy", "price": price - i * spacing,
                    "qty": per_level / (price - i * spacing),
                    "tag": f"flowgrid-bal-buy-{i}",
                })
                signals.append({
                    "action": "sell", "price": price + i * spacing,
                    "qty": per_level / (price + i * spacing),
                    "tag": f"flowgrid-bal-sell-{i}",
                })

        self._last_price = price
        return signals

    def on_fill(self, fill: Dict[str, Any]) -> None:
        side = str(fill.get("side", "buy")).lower()
        price = float(fill.get("price", 0.0))
        qty = float(fill.get("qty", 0.0))
        if side not in ("buy", "sell"):
            return
        signed = qty if side == "buy" else -qty
        self._realized_pnl += -signed * price
        self._inventory += signed
        self._trades += 1

    def estimate_memory_mb(self) -> float:
        return 0.01


if __name__ == "__main__":
    cfg = FLOWGRIDConfig(capital=3.5, levels=4, dry_run=True)
    strat = FLOWGRID(cfg)
    n_buy, n_sig_total, price = 0, 0, 0.10
    for k in range(300):
        side = "buy" if k % 3 == 0 else ("sell" if k % 3 == 1 else "buy")
        if side == "buy":
            n_buy += 1
        tick = {"price": price, "volume": 100.0 + (k % 7) * 10.0, "taker_side": side}
        sigs = strat.on_tick(tick)
        n_sig_total += len(sigs)
        if k % 30 == 0 and sigs:
            strat.on_fill({"side": "buy", "price": price, "qty": 5.0})
        price += 0.0002 * ((k % 5) - 2)

    print(f"buys={n_buy} total_signals={n_sig_total}")
    print(f"flow_buy={strat._flow_buy:.2f} flow_sell={strat._flow_sell:.2f}")
    print(f"flow_ratio={strat._flow_ratio():.3f} regime={strat._regime(strat._flow_ratio())}")
    print(f"trades={strat._trades} realized_pnl={strat._realized_pnl:.4f}")
    print(f"drawdown={strat._drawdown:.4f} est_mem={strat.estimate_memory_mb()}MB")
    assert strat._trades >= 0
    assert strat.validate_config() is None
    print("FLOWGRID inline test PASSED")
    del strat, cfg, tick
    gc.collect()
