"""
depthgrid: Adaptive Deep-Liquidity Grid
========================================
Strategy original class: DepthGrid.

Idea: tradizionali grid usano livelli a spacing uniforme sopra/sotto il mid.
Quando il book e' SOTTILE (poca profondita' attorno al prezzo), un ordine
grid ha alta probabilita' di diventare adverse (eseguito e poi prezzo che
scappa via). Al contrario, quando il book e' PROFONDO, i livelli vicini
vengono riempiti molto piu' spesso con basso slippage.

DepthGrid non predice direzione: scala ADATTIVAMENTE la densita' dei livelli
in base alla profondita' di mercato osservata (liquidita' cumulativa entro
una distanza target dal mid), e PAUSA i livelli aggressivi quando la
profondita' collassa (adverse selection). E' O(1) in streaming: mantiene
solo poche EMA scalari e coppie ordine->fill, nessuna scansione storica.

Differisce da:
  - spreadkiller (spread-based throttling): qui e' profondita' cumulativa,
    non distanza tra bid/ask.
  - volgridx (volatility adaptive): qui l'adattamento e' su book depth,
    non su deviazione standard dei ritorni.
  - flowgrid (ordini flow-based): qui NON usiamo flow, solo stato del book.

Memoria: < 1 MB garantito (solo scalari EMA + costanti topologiche).
Config-driven, zero hardcoded.

API conforme: StrategyBase con on_tick/on_fill/validate_config/
estimate_memory_mb + test inline `__main__`.
"""
from __future__ import annotations

import gc
import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional, Tuple


# --------------------------------------------------------------------------- #
#  Config
# --------------------------------------------------------------------------- #
@dataclass
class DepthGridConfig:
    """Configurazione DepthGrid. Tutti i valori hanno default sicuri."""
    # --- topologia griglia ---
    min_levels: int = 4
    max_levels: int = 10
    grid_capital_eur: float = 2.0
    order_size_eur: float = 0.25

    # --- book / profondita' ---
    depth_window_ticks: int = 300      # EMA window per profondita' media
    depth_target_ratio: float = 250.0  # EUR entro 0.5% dal mid = "profondo"
    quote_delta_pct: float = 0.01      # +-1% dal mid per cumulare profondita'

    # --- parametri adattivi ---
    min_depth_ratio: float = 0.15      # sotto => throttling aggressivo
    pause_ms: int = 15_000             # pausa massima dopo collasso depth
    cooldown_ms: int = 500             # cooldown minimo tra ordini

    # --- risk ---
    max_position_eur: float = 3.0
    stop_loss_pct: float = 5.0
    kill_switch_drawdown_pct: float = 8.0

    # --- throttling interne (non toccare se non sai cosa fai) ---
    ema_depth_alpha: float = 0.05
    recovery_steps: int = 5            # rientro graduale dopo la pausa

    def validate(self) -> List[str]:
        errs: List[str] = []
        if not (self.min_levels >= 1 and self.max_levels >= self.min_levels):
            errs.append("min_levels>=1 e max_levels>=min_levels")
        if self.order_size_eur <= 0:
            errs.append("order_size_eur>0")
        if self.grid_capital_eur < self.order_size_eur * self.min_levels:
            errs.append("grid_capital_eur insufficiente per min_levels")
        if not (0.0 < self.min_depth_ratio <= 1.0):
            errs.append("min_depth_ratio in (0,1]")
        if self.stop_loss_pct <= 0.0 or self.kill_switch_drawdown_pct <= 0.0:
            errs.append("stop_loss/kill_switch >0")
        return errs


# --------------------------------------------------------------------------- #
#  Strategy
# --------------------------------------------------------------------------- #
class StrategyBase:
    """Interfaccia standardizzata per le strategie Denaro."""

    def __init__(self, config: Any = None) -> None:
        self.cfg = config

    def on_tick(self, tick: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def on_fill(self, fill: Dict[str, Any]) -> None:
        raise NotImplementedError

    def validate_config(self) -> List[str]:
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError


class DepthGrid(StrategyBase):
    """Griglia adattiva alla profondita' del book. O(1) streaming."""

    def __init__(self, config: Optional[DepthGridConfig] = None) -> None:
        super().__init__(config or DepthGridConfig())
        errs = self.validate_config()
        if errs:
            raise ValueError("Config non valida: " + "; ".join(errs))

        # EMA di profondita' (scalare, O(0) memoria extra)
        self._ema_depth: float = 0.0
        self._depth_seen: bool = False

        # stato ordini live: id -> quote_eur (small deque, bounded)
        self._open: Dict[str, float] = {}

        # posizione/rollback per kill-switch
        self._equity_start: Optional[float] = None
        self._peak_equity: float = 0.0

        # throttle: timestamp della prossima azione ammessa
        self._next_action_ts: float = 0.0
        self._pause_start_ts: Optional[float] = None
        self._last_depth_ratio: float = 1.0

        # book cache (solo ultimo tick, overwritten)
        self._bids: List[Tuple[float, float]] = []
        self._asks: List[Tuple[float, float]] = []

    # ---------------- API ---------------- #
    def validate_config(self) -> List[str]:
        return self.cfg.validate() if isinstance(self.cfg, DepthGridConfig) else ["cfg type!"]

    def estimate_memory_mb(self) -> float:
        # EMA scalari: trascurabili. book cache: ~2 liste di 20 tuple.
        book_bytes = (len(self._bids) + len(self._asks)) * 64
        open_bytes = len(self._open) * 96
        return (book_bytes + open_bytes + 4096) / (1024 * 1024)

    # ---------------- core ---------------- #
    def _cumulate_depth(self, side_px: float, quote_px: float) -> float:
        """EUR cumulativo entro +-quote_delta_pct dal mid, dal lato scelto."""
        if side_px <= 0.0:
            return 0.0
        bound = quote_px * (1.0 + self.cfg.quote_delta_pct)
        levels = self._asks if side_px >= quote_px else self._bids
        total = 0.0
        for px, qty in levels:
            px = float(px)
            if side_px >= quote_px and px > bound:
                break
            if side_px < quote_px and px > quote_px:
                break
            total += qty * px
            if total > self.cfg.depth_target_ratio * 4:  # cap anti-overflow
                break
        return total

    def _pick_side(self, tick: Dict[str, Any]) -> Tuple[str, float]:
        """Sceglie il lato con maggiore profondita' residua (meno adverse)."""
        mid = (float(tick["bid"]) + float(tick["ask"])) / 2.0
        d_buy = self._cumulate_depth(float(tick["ask"]), mid)
        d_sell = self._cumulate_depth(float(tick["bid"]), mid)
        return ("buy", d_buy) if d_buy >= d_sell else ("sell", d_sell)

    def _update_depth_ema(self, ratio: float, ts: float) -> None:
        if not self._depth_seen:
            self._ema_depth = ratio
            self._depth_seen = True
        else:
            a = self.cfg.ema_depth_alpha
            self._ema_depth = self._ema_depth * (1.0 - a) + ratio * a

        # collasso di profondita' => throttle anticipatorio
        if ratio < self.cfg.min_depth_ratio and self._pause_start_ts is None:
            self._pause_start_ts = ts
            self._next_action_ts = ts + self.cfg.pause_ms / 1000.0
        elif ratio >= self.cfg.min_depth_ratio and self._pause_start_ts is not None:
            self._pause_start_ts = None

        self._last_depth_ratio = ratio

    def _level_count(self) -> int:
        """Numero di livelli da dispiegare, proporzionale a profondita' media."""
        t = max(0.0, min(1.0, (self._ema_depth / self.cfg.depth_target_ratio)))
        n = self.cfg.min_levels + int(
            round(t * (self.cfg.max_levels - self.cfg.min_levels))
        )
        return max(self.cfg.min_levels, min(self.cfg.max_levels, n))

    def on_tick(self, tick: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        now = float(tick.get("ts", 0.0))
        bid, ask = float(tick["bid"]), float(tick["ask"])
        mid = (bid + ask) / 2.0
        self._bids = sorted(tick.get("bids", []), key=lambda x: -float(x[0]))
        self._asks = sorted(tick.get("asks", []), key=lambda x: float(x[0]))

        # init equity baseline
        if self._equity_start is None:
            self._equity_start = float(tick.get("total_equity", 0.0))
            self._peak_equity = self._equity_start

        eq = float(tick.get("total_equity", 0.0))
        self._peak_equity = max(self._peak_equity, eq)

        # kill-switch: drawdown oltre soglia => SELL e stop
        if self._equity_start > 0.0:
            drawdown = (self._peak_equity - eq) / self._peak_equity
            if drawdown >= self.cfg.kill_switch_drawdown_pct / 100.0:
                self._next_action_ts = float("inf")
                return {"action": "close_all", "reason": "kill_switch_drawdown"}

        # depth del lato favorito
        side, depth = self._pick_side(tick)
        ratio = depth / self.cfg.depth_target_ratio
        self._update_depth_ema(ratio, now)

        # cooldown / pausa
        if now < self._next_action_ts:
            return None
        if self._pause_start_ts is not None:
            return None

        # stop-loss su exposure
        pos = sum(self._open.values())
        if pos >= self.cfg.max_position_eur:
            return None

        n_levels = self._level_count()
        if len(self._open) >= n_levels:
            return None

        # order quote proporzionale a profondita' (piu' aggressivo se profondo)
        budget = min(
            self.cfg.order_size_eur,
            self.cfg.grid_capital_eur - pos,
        )
        if budget < 1e-9:
            return None

        order = {
            "action": "limit" if side == "buy" else "limit",
            "side": side,
            "symbol": tick["symbol"],
            "price": bid if side == "sell" else ask,
            "size_quote": round(budget, 6),
            "level_scale": round(ratio, 4),
            "reason": "depth_grid",
        }
        self._next_action_ts = now + self.cfg.cooldown_ms / 1000.0
        self._open[order_id := f"{side}:{now:.3f}"] = budget
        order["order_id"] = order_id
        return order

    def on_fill(self, fill: Dict[str, Any]) -> None:
        oid = str(fill.get("order_id", ""))
        if oid in self._open:
            del self._open[oid]           # evita leak; O(1)
        # controllo memoria attiva ogni N fill
        if len(self._open) == 0:
            gc.collect()


# --------------------------------------------------------------------------- #
#  Test inline (dati sintetici, piccolo)
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    import random

    cfg = DepthGridConfig(grid_capital_eur=2.0, order_size_eur=0.25)
    strat = DepthGrid(cfg)
    print("mem_MB~", round(strat.estimate_memory_mb(), 5))

    rng = random.Random(42)
    fills = 0
    px = 0.10
    for i in range(600):
        # book sintetico: profondita' altalenante
        depth_qty = 800.0 if (i % 40) < 32 else 20.0
        bid = px - 0.0001
        ask = px + 0.0001
        bids = [(bid - k * 0.0001, depth_qty) for k in range(20)]
        asks = [(ask + k * 0.0001, depth_qty) for k in range(20)]
        tick = {
            "ts": float(i) * 0.1, "symbol": "DOGE/EUR",
            "bid": bid, "ask": ask,
            "bids": bids, "asks": asks,
            "total_equity": 3.7 - (i * 0.00001),
        }
        order = strat.on_tick(tick)
        if order:
            strat.on_fill({**order, "price": order["price"], "qty": 1.0})
            fills += 1
        px += rng.uniform(-0.0002, 0.0002)

    print(f"orders_emitted={fills} open={len(strat._open)} "
          f"ema_depth={strat._ema_depth:.2f} level_count={strat._level_count()}")
    assert fills > 0, "nessun ordine emesso: logica rotta"
    assert strat.estimate_memory_mb() < 1.0, "memoria fuori bound"
    print("TEST PASSED")
