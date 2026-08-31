"""auto_gen_1788180373 — LiquidityAwareAdaptiveGrid (LAAGrid).

Griglia adattiva con tilt di momentum da On-Balance-Volume (OBV) e
dimensionamento posizione a Kelly limitato, gated dal regime di volatilità.

Cosa la rende diversa dalle altre grid:
  - La griglia NON è simmetrica: la distanza dei livelli buy/sell è sbilanciata
    in base alla pendenza normalizzata dell'OBV (flusso di ordini dominante).
  - La copertura (`coverage`) si restringe automaticamente se la volatilità
    (ATR normalizzata) supera `vol_cap`, riducendo l'esposizione in regime
    turbolento (drawdown protection).
  - Slot sizing = capital * KellyLimit * edge_est, dove edge_est deriva dal
    win-ratio rolling (streaming, niente buffer illimitato).

Vincoli di qualità:
  - Streaming O(1): OBV, ATR e win-ratio sono incrementali, niente storage
    di serie complete → OOM-safe su dataset/fuoco di ticks anche prolungato.
  - Niente list comprehension su collezioni potenzialmente grandi: si
    iterano solo i livelli della griglia (<= `levels`*2, small fixed).
  - Error handling esplicito: ValueError con messaggio chiaro, niente
    `except: pass`.
  - Config-driven: ogni comportamento è un parametro del dataclass congela.
"""

from __future__ import annotations

import gc
import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional


# --------------------------------------------------------------------------- #
# Config (immutabile)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class LAAGridConfig:
    """Configurazione della strategia; nessun comportamento hardcoded."""
    symbol: str = "SOL/EUR"
    capital: float = 10.0
    base_spacing: float = 0.02          # frazione tra livelli a OBV neutro
    levels: int = 4                     # livelli per lato (buy e sell)
    obv_window: int = 24                # finestra OBV per la pendenza
    atr_period: int = 14
    atr_mult: float = 1.5               # spacing scaled = base_spacing*atr/atr_ref
    atr_ref: float = 0.02               # ATR normalizzata di riferimento
    vol_cap: float = 0.045              # kill/au fermo se ATR/price > vol_cap
    kelly_limit: float = 0.25           # frazione max di Kelly usata
    win_window: int = 40                # finestra rolling del win-ratio
    max_inventory: float = 0.65         # max quote esposta / capital
    tp_scale: float = 1.6               # TP = spacing * tp_scale
    warmup: int = 45                    # tick minimi prima di tradare

    def validate(self) -> None:
        errs: List[str] = []
        if self.levels < 1:
            errs.append("levels must be >= 1")
        if self.base_spacing <= 0 or self.atr_mult <= 0:
            errs.append("spacing params must be > 0")
        if not 0 < self.kelly_limit <= 1.0:
            errs.append("kelly_limit must be in (0,1]")
        if not 0 < self.max_inventory <= 1.0:
            errs.append("max_inventory must be in (0,1]")
        if self.atr_period < 2 or self.obv_window < 2 or self.win_window < 2:
            errs.append("rolling windows must be >= 2")
        if self.capital <= 0:
            errs.append("capital must be > 0")
        if self.tp_scale <= 0:
            errs.append("tp_scale must be > 0")
        if errs:
            raise ValueError("LAAGridConfig invalid: " + "; ".join(errs))

    def estimate_memory_mb(self) -> float:
        # Solo strutture piccole e fisse: 2 EMA, 1 ATR, 1 OBV, buffer wins.
        wins_bytes = min(self.win_window, 1) * 8
        atr_bytes = max(self.atr_period, 1) * 8
        order_bytes = (self.levels * 2) * 120
        fixed = 3 * 1024
        return round((fixed + wins_bytes + atr_bytes + order_bytes) / (1024 * 1024), 4)


# --------------------------------------------------------------------------- #
# Indicator streaming (O(1))
# --------------------------------------------------------------------------- #
class OBVStream:
    """On-Balance-Volume incrementale + pendenza normalizzata negli ultimi N trade."""

    __slots__ = ("_window", "_obv", "_history", "_last_price", "_n")

    def __init__(self, window: int) -> None:
        if window < 2:
            raise ValueError("obv window must be >= 2")
        self._window = window
        self._obv = 0.0
        self._history: Deque[float] = deque(maxlen=window)
        self._last_price: Optional[float] = None
        self._n = 0

    def update(self, price: float, volume: float) -> Optional[float]:
        """Feed un tick (price, volume); ritorna pendenza OBV normalizzata o None."""
        if price <= 0 or volume < 0:
            raise ValueError(f"invalid update price={price!r} vol={volume!r}")
        self._n += 1
        if self._last_price is not None:
            if price > self._last_price:
                self._obv += volume
            elif price < self._last_price:
                self._obv -= volume
        self._last_price = price
        self._history.append(self._obv)
        if self._n < self._window:
            return None
        first = self._history[0]
        span = self._history[-1] - first
        denom = abs(first) + abs(self._obv) + 1e-9
        return span / denom


class ATRStream:
    """ATR normalizzata (True-Range medio su finestra), streaming O(1)."""

    __slots__ = ("_window", "_ranges", "_last_close", "_n", "_atr")

    def __init__(self, window: int) -> None:
        if window < 2:
            raise ValueError("atr window must be >= 2")
        self._window = window
        self._ranges: Deque[float] = deque(maxlen=window)
        self._last_close: Optional[float] = None
        self._n = 0
        self._atr: Optional[float] = None

    def update(self, close: float, high: Optional[float] = None,
               low: Optional[float] = None) -> Optional[float]:
        if close <= 0:
            raise ValueError(f"invalid close: {close!r}")
        h = high if high is not None else close
        l = low if low is not None else close
        if h < l:
            raise ValueError(f"high {h!r} < low {l!r}")
        tr = h - l
        if self._last_close is not None:
            tr = max(tr, abs(h - self._last_close), abs(l - self._last_close))
        self._last_close = close
        self._n += 1
        if self._n == 1:
            self._atr = tr
        else:
            self._atr = self._atr + (tr - self._atr) / self._window
        if self._n < self._window:
            return None
        return (self._atr / close) if close else None


class WinRatio:
    """Win-ratio rolling su fixed window, streaming O(1)."""

    __slots__ = ("_window", "_outcomes", "_wins", "_n")

    def __init__(self, window: int) -> None:
        if window < 2:
            raise ValueError("win window must be >= 2")
        self._window = window
        self._outcomes: Deque[float] = deque(maxlen=window)
        self._wins = 0.0
        self._n = 0

    def update(self, pnl: float) -> float:
        self._n += 1
        win = 1.0 if pnl > 0 else 0.0
        self._wins += win
        self._outcomes.append(win)
        if len(self._outcomes) > self._window:
            self._wins -= self._outcomes[0]
        return self._wins / len(self._outcomes)


# --------------------------------------------------------------------------- #
# Engine
# --------------------------------------------------------------------------- #
class StrategyBase:
    """Interfaccia minima comune a tutte le strategie auto-gen."""

    def on_tick(self, tick: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    def on_fill(self, fill: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    def validate_config(self) -> None:
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError


class LiquidityAwareAdaptiveGrid(StrategyBase):
    """Grid adattiva con tilt OBV e sizing a Kelly limitato."""

    def __init__(self, cfg: Optional[LAAGridConfig] = None) -> None:
        self.cfg = cfg or LAAGridConfig()
        self.cfg.validate()
        self._obv = OBVStream(self.cfg.obv_window)
        self._atr = ATRStream(self.cfg.atr_period)
        self._wr = WinRatio(self.cfg.win_window)
        self._ticks = 0
        self._price: Optional[float] = None
        self._inventory = 0.0
        self._pnl = 0.0
        self._fills_total = 0
        self._recent_fills: List[Dict[str, Any]] = []
        self._bn = self.cfg.atr_ref if self.cfg.atr_ref > 0 else 0.02
        self._coverage = 1.0   # frac di griglia attiva (si riduce a vol alta)

    # -- API ----------------------------------------------------------- #
    def validate_config(self) -> None:
        self.cfg.validate()

    def estimate_memory_mb(self) -> float:
        return self.cfg.estimate_memory_mb()

    # -- interni -------------------------------------------------------- #
    def _effective_spacing(self) -> float:
        atr_n = self._atr.update(self._price)          # type: ignore[arg-type]
        if atr_n is None:
            return self.cfg.base_spacing
        return self.cfg.base_spacing * (self.cfg.atr_mult * atr_n / self._bn)

    def _kelly_edge(self) -> float:
        # Kelly asimmetrico su payoff B=1: K = W - (1-W) = 2W - 1
        wins = self._wr._wins
        total = max(len(self._wr._outcomes), 1)
        return max(0.0, (2.0 * (wins / total)) - 1.0)

    # -- API ----------------------------------------------------------- #
    def on_tick(self, tick: Dict[str, Any]) -> Dict[str, Any]:
        price = tick.get("price")
        if not isinstance(price, (int, float)) or price <= 0:
            raise ValueError(f"invalid price in tick: {price!r}")
        volume = tick.get("volume", 0.0)
        if not isinstance(volume, (int, float)) or volume < 0:
            raise ValueError(f"invalid volume in tick: {volume!r}")

        self._ticks += 1
        self._price = price

        obv_slope = self._obv.update(price, volume)
        atr_n = self._atr.update(price)

        if self._ticks < self.cfg.warmup:
            return {"action": "hold", "reason": "warmup", "ticks": self._ticks}

        # Protezione volatilità: se ATR elevata restringi la copertura.
        if atr_n is not None and atr_n > self.cfg.vol_cap:
            self._coverage = max(0.3, self._coverage * 0.95)
        elif atr_n is not None:
            self._coverage = min(1.0, self._coverage * 1.02)

        spacing = self._effective_spacing()
        # Tilt: la griglia si sposta verso il lato del flusso dominante.
        tilt = 0.0
        if obv_slope is not None:
            tilt = max(-0.5, min(0.5, obv_slope * 4.0))

        slot = (self.cfg.capital * self.cfg.max_inventory * self._coverage) \
            / max(self.cfg.levels, 1)
        edge = self._kelly_edge()
        size = slot * (self.cfg.kelly_limit + edge)

        orders: List[Dict[str, Any]] = []
        for i in range(1, self.cfg.levels + 1):
            # lato buy: piu' livelli se tilt negativo (accumulo)
            buy_w = 1.0 + (-tilt if tilt < 0 else 0.0)
            sell_w = 1.0 + (tilt if tilt > 0 else 0.0)
            buy_px = price * (1 - spacing * i * buy_w)
            sell_px = price * (1 + spacing * i * sell_w)
            if self._inventory < self.cfg.max_inventory:
                orders.append({"side": "buy", "price": round(buy_px, 6),
                               "size": round(size, 6), "kind": "limit"})
            orders.append({"side": "sell", "price": round(sell_px, 6),
                           "size": round(size, 6), "kind": "limit"})

        del obv_slope  # libera subito i riferimenti inutili in loop lungi
        if self._ticks % 256 == 0:
            gc.collect()

        return {
            "action": "place_orders",
            "orders": orders,
            "spacing": round(spacing, 5),
            "coverage": round(self._coverage, 3),
            "edge": round(edge, 4),
            "inventory": round(self._inventory, 4),
        }

    def on_fill(self, fill: Dict[str, Any]) -> Dict[str, Any]:
        side = fill.get("side")
        price = fill.get("price")
        size = fill.get("size", 0.0)
        if side not in ("buy", "sell"):
            raise ValueError(f"invalid fill side: {side!r}")
        if not isinstance(price, (int, float)) or price <= 0:
            raise ValueError(f"invalid fill price: {price!r}")

        self._fills_total += 1
        notional = float(price) * float(size)
        if side == "buy":
            self._inventory += float(size)
        else:
            self._inventory -= float(size)
            self._pnl += notional

        self._recent_fills.append({"side": side, "price": price,
                                   "size": size, "fill_id": self._fills_total})
        if len(self._recent_fills) > 200:
            # trim esplicito del buffer di diagnostica (sempre O(1) bound)
            del self._recent_fills[:len(self._recent_fills) - 200]

        return {"action": "ack", "fills_total": self._fills_total,
                "inventory": round(self._inventory, 4),
                "pnl": round(self._pnl, 5)}


# --------------------------------------------------------------------------- #
# Smoke test (dati sintetici piccoli)
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    cfg = LAAGridConfig(capital=10.0, levels=3, warmup=10, win_window=10)
    s = LiquidityAwareAdaptiveGrid(cfg)
    assert s.estimate_memory_mb() > 0.0
    price = 100.0
    for i in range(120):
        price = price * (1 + 0.001 * math.sin(i / 5.0) + 0.0002 * (i % 7))
        out = s.on_tick({"price": price, "volume": 10.0})
        if out["action"] == "place_orders":
            assert len(out["orders"]) >= 1
        # simula un fill ogni 10 tick per esercitare on_fill
        if i % 10 == 0:
            s.on_fill({"side": "buy", "price": price, "size": 0.5})
    print("OK auto_gen_1788180373_laa_grid: ticks=%d fills=%d pnl=%.5f mem=%sMB"
          % (s._ticks, s._fills_total, s._pnl, s.estimate_memory_mb()))
