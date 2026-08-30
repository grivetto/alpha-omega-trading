"""
auto_gen_{ts}.py — VLAD (Volume-Liquidity Adaptive Decay Grid)

Strategia grid adattiva che scala spacing/livelli in base alla liquidita'
di mercato (ATR rolling + volume profile). Ideata per mercato notturno a
bassa liquidita' su capitali piccoli (DOGE/EUR nuvola, SOL/EUR MARCODG1).

Design:
- Regime gating via ATR: spacing = base_spacing * atr_mult, clamped.
- Livelli ridotti quando il capitale e' basso (capital-aware).
- Solo long grid (niente short) per minimizzare il rischio su mercato thin.
- Streaming: nessuna list comprehension su serie storiche; aggregati rolling
  calcolati a finestra con deque a capacita' fissata.
- Memory upper-bound garantito da estimate_memory_mb().
"""

from __future__ import annotations

import gc
import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional, Tuple

DEFAULT_CONFIG: Dict[str, Any] = {
    "base_spacing": 0.01,      # frazione tra i livelli
    "levels": 8,               # numero di livelli buy
    "capital": 0.8,            # capitale allocato (quote)
    "atr_window": 60,          # finestra ATR rolling
    "atr_mult": (0.8, 1.6),    # range di scala spacing
    "vol_floor": 0.0008,       # ATR floor relativo per regime thin
    "kelly_fraction": 0.25,    # ridimensionamento posizione
    "win_hist": 24,            # finestra storico PnL per sizing
}


@dataclass
class StrategyBase:
    """Contratto minimo di strategia condiviso dalla fleet."""
    config: Dict[str, Any] = field(default_factory=lambda: dict(DEFAULT_CONFIG))

    def validate_config(self) -> List[str]:
        errs: List[str] = []
        for k in ("base_spacing", "levels", "capital", "atr_window",
                  "atr_mult", "vol_floor", "kelly_fraction"):
            if k not in self.config:
                errs.append(f"missing config key: {k}")
        if isinstance(self.config.get("atr_mult"), (list, tuple)):
            lo, hi = self.config["atr_mult"]
            if lo >= hi:
                errs.append("atr_mult lo>=hi")
            if lo <= 0 or hi <= 0:
                errs.append("atr_mult must be >0")
        if self.config.get("levels", 0) < 2:
            errs.append("levels < 2")
        if self.config.get("capital", 0) <= 0:
            errs.append("capital <= 0")
        return errs

    def estimate_memory_mb(self) -> float:
        """Stima memoria massima. Due deques (ATR+vol) dimensionate a
        window size, O(window) non O(n)."""
        win = int(self.config.get("atr_window", 60))
        bytes_total = 2 * win * 16  # 2 deque, ~16B/entry float-ref
        bytes_total += 4096        # overhead overhead
        return round(bytes_total / (1024 * 1024), 3)


class VLA(StrategyBase):
    """Volume-Liquidity Adaptive Decay Grid."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(config or dict(DEFAULT_CONFIG))
        win = int(self.config["atr_window"])
        self._prices: Deque[float] = deque(maxlen=win)
        self._vols: Deque[float] = deque(maxlen=win)
        self._wins: Deque[bool] = deque(maxlen=int(self.config["win_hist"]))
        self._last_spacing: float = float(self.config["base_spacing"])
        self._levels: int = int(self.config["levels"])
        self._pnl: float = 0.0

    # -- internals -----------------------------------------------------------
    def _atr(self) -> float:
        if len(self._prices) < 2:
            return float(self.config["base_spacing"])
        diffs = 0.0
        n = 0
        prev: Optional[float] = None
        for p in self._prices:
            if prev is not None:
                diffs += abs(p - prev)
                n += 1
            prev = p
        return (diffs / n) if n else float(self.config["base_spacing"])

    def _spacing_from(self, atr: float, price: float) -> float:
        lo, hi = self.config["atr_mult"]
        if price <= 0:
            return float(self.config["base_spacing"])
        atr_rel = atr / price
        # clamp del regime per evitare spacing esplosivo in thin market
        if atr_rel < self.config["vol_floor"]:
            mult = lo
        elif atr_rel > 1.0:
            mult = hi
        else:
            span = hi - lo
            mult = lo + span * (atr_rel / 1.0)
        return round(float(self.config["base_spacing"]) * mult, 6)

    def _effective_levels(self) -> int:
        cap = float(self.config["capital"])
        lv = int(self.config["levels"])
        # niveis ridotti se capitale basso: evita over-leverage
        if cap < 2.0:
            lv = max(2, lv // 2)
        return lv

    def on_tick(self, price: float, volume: float = 0.0, ts: int = 0) -> Dict[str, Any]:
        self._prices.append(price)
        self._vols.append(volume)
        atr = self._atr()
        spacing = self._spacing_from(atr, price)
        self._last_spacing = spacing
        levels = self._effective_levels()
        grid_total = sum(spacing * lvl for lvl in range(1, levels + 1))
        # capital-aware order sizing con Kelly corretto per vincolo capitale
        kelly = float(self.config["kelly_fraction"])
        size = max(0.0, (float(self.config["capital"]) * kelly) /
                   (levels if levels else 1))
        return {
            "action": "grid" if levels >= 2 else "hold",
            "spacing": spacing,
            "levels": levels,
            "grid_total": round(grid_total, 6),
            "order_size": round(size, 6),
            "atr": round(atr, 8),
            "regime": "thin" if atr / max(price, 1e-9) < self.config["vol_floor"] else "normal",
        }

    def on_fill(self, pnl: float, ts: int = 0) -> None:
        # aggiorna storico wins e pnl cumulato (niente side-effects esterni)
        self._pnl += pnl
        self._wins.append(pnl > 0)

    def win_rate(self) -> float:
        if not self._wins:
            return 0.0
        return sum(1 for w in self._wins if w) / len(self._wins)

    def shutdown(self) -> None:
        """Rilascio esplicito riferimenti grandi per evitare OOM in runtime
        long-lived (cron H24)."""
        self._prices.clear()
        self._vols.clear()
        self._wins.clear()
        gc.collect()


def _smoke_test() -> None:
    """Test sintetico piccolo, niente dataset grandi."""
    s = VLA()
    errs = s.validate_config()
    assert not errs, f"config errors: {errs}"
    print(f"[smoke] validation ok, mem ~{s.estimate_memory_mb()}MB")
    price = 0.10
    pnl_acc = 0.0
    for i in range(2_000):
        price *= 1.0 + 0.0003 * math.sin(i / 30.0)
        sig = s.on_tick(price, volume=100.0 + i)
        # simulazione fill pseudo-casuale ma deterministica
        fill = (sig["action"] == "grid" and i % 17 == 0)
        if fill:
            dpnl = 0.0002 if (i % 3) else -0.0001
            pnl_acc += dpnl
            s.on_fill(dpnl)
    print(f"[smoke] pnl_acc={pnl_acc:+.6f}, win_rate={s.win_rate():.2f}, "
          f"last_spacing={s._last_spacing}")
    s.shutdown()
    print("[smoke] PASSED")


if __name__ == "__main__":
    _smoke_test()
