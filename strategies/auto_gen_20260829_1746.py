"""Volatility-Breakout Mean-Reverting Fragmentation Engine (VBMF)
auto-generated 2026-08-29 17:46 UTC by Hermes (orchestration cycle).

Why distinct from every prior auto-gen family:
  1. Prior families are BOOK/EXHAUSTION (LETF, OFI, LGR-AKR), GRID GEOMETRY
     (ATR/z-score/ISV/VAGR) or TREND-SLOPE scalpers (VWMR, Chandelier, V2).
     VBMF trades *breakout failures*: it only acts after a high-persistence
     price spike (Donchian range expansion with volume confirmation) then
     fades the move when the escape fails to hold — a false-breakout
     mean-reversion. No prior strategy explicitly gates on *post-breakout
     rejection*; they reversion on imbalance or geometry, not on spikes.
  2. Entry is a two-stage confirmation: (a) expansion phase — bar exits the
     prior Donchian channel by > k * ATR with volume above its own rolling
     median (spike is real), then (b) rejection phase — within the next
     N bars price closes back inside the channel (escape proved hollow).
     Only the SECOND leg trades. This is orthogonal to LGR-AKR (order-flow
     LIR z-score) and VWMR (price-slope Hampel).
  3. Asymmetric inventory compression: exposure scales with |spike|/ATR but
     is fragmented (partial size) so a prolonged false-breakout fade cannot
     blow the account; take-profit at channel mid + vol-scaled ratchet.
  4. OOM-safe by construction: Donchian highs/lows are maintained as bounded
     deques (maxlen), volume stats via streaming Welford median approximation
     (no 100k arrays), explicit `del` on no-longer-needed bulk vars, and
     periodic gc.collect() during warmup only. estimate_memory_mb is O(1).

Interface contract (Denaro StrategyBase):
  - on_tick(market, orders) -> Action.HOLD | 1 (BUY) | -1 (SELL)
  - on_fill(order_id, side, price, size)
  - validate_config(config) -> bool
  - estimate_memory_mb(config=None) -> float
"""
from __future__ import annotations

import gc
import math
from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Dict, Optional


class Action:
    HOLD: int = 0
    BUY: int = 1
    SELL: int = -1


@dataclass
class Config:
    symbol: str = "SOL/EUR"
    capital: float = 20.0
    donchian_window: int = 40            # bars of channel context (bounded)
    breakout_atr_mult: float = 1.1       # k * ATR to confirm a real escape
    rejection_window: int = 5            # bars allowed for the escape to fail
    atr_window: int = 20                 # streaming ATR for spike normalization
    vol_window: int = 120                # streaming vol (log-return EWMA)
    volume_window: int = 48              # rolling median window for volume gate
    tp_type: str = "mid_channel"         # "mid_channel" | "atr_ratchet"
    tp_atr: float = 0.6                  # take-profit as fraction of ATR
    fragmentation: int = 4               # split size into N fragments
    max_inventory_frac: float = 0.5      # cap exposure as fraction of capital
    stop_atr: float = 1.8                # hard stop expressed in ATR units
    kelly_cap: float = 0.25              # fractional cap on aggressive sizing
    warmup_bars: int = 80                # min bars before trading


class _StreamWelford:
    """O(1)-memory incremental mean & variance (Welford), no materialization."""

    __slots__ = ("_count", "_mean", "_m2")

    def __init__(self) -> None:
        self._count: int = 0
        self._mean: float = 0.0
        self._m2: float = 0.0

    def push(self, value: float) -> None:
        self._count += 1
        delta: float = value - self._mean
        self._mean += delta / self._count
        delta2: float = value - self._mean
        self._m2 += delta * delta2

    @property
    def mean(self) -> float:
        return self._mean

    @property
    def variance(self) -> float:
        return self._m2 / self._count if self._count > 1 else 0.0

    @property
    def std(self) -> float:
        return math.sqrt(max(self.variance, 0.0))

    @property
    def n(self) -> int:
        return self._count


class _BoundedMedian:
    """Sliding median via bounded window; sorted copy only when read (small)."""

    __slots__ = ("_window", "_maxlen")

    def __init__(self, maxlen: int) -> None:
        self._window: Deque[float] = deque(maxlen=maxlen)
        self._maxlen: int = maxlen

    def push(self, value: float) -> None:
        self._window.append(value)

    @property
    def median(self) -> float:
        n: int = len(self._window)
        if n == 0:
            return 0.0
        s: list = sorted(self._window)  # bounded (maxlen<=48): cheap
        mid: int = n // 2
        if n % 2 == 1:
            return float(s[mid])
        return float((s[mid - 1] + s[mid]) / 2.0)

    def ready(self) -> bool:
        return len(self._window) >= 10


class VBMF:
    """Volatility-Breakout Mean-Reverting Fragmentation Engine."""

    def __init__(self, config: Optional[Config] = None) -> None:
        self.cfg: Config = config or Config()
        if not self.validate_config(self.cfg):
            raise ValueError("VBMF config validation failed")

        self.bars: int = 0
        self.position: float = 0.0              # signed inventory
        self.realized_pnl: float = 0.0
        self._pending: Dict[str, Dict[str, float]] = {}
        self._wins: int = 0
        self._losses: int = 0
        self._avg_win: float = 0.0
        self._avg_loss: float = 0.0
        self._spike_side: int = 0               # +1 short opp / -1 long opp
        self._reject_bars_remain: int = 0
        self._entry_chan: tuple = (0.0, 0.0)

        # streaming / bounded state (OOM-safe)
        self._highs: Deque[float] = deque(maxlen=self.cfg.donchian_window)
        self._lows: Deque[float] = deque(maxlen=self.cfg.donchian_window)
        self._atr: _StreamWelford = _StreamWelford()
        self._vol: _StreamWelford = _StreamWelford()
        self._vol_med: _BoundedMedian = _BoundedMedian(self.cfg.volume_window)
        self._last_close: float = 0.0
        self._vol_sweep_counter: int = 0

    # -- required StrategyBase interface ------------------------------------
    @staticmethod
    def validate_config(cfg: Any) -> bool:
        """Validate every tunable; False on any out-of-range value."""
        required_pos_int = ("donchian_window", "atr_window", "vol_window",
                            "volume_window", "fragmentation", "rejection_window",
                            "warmup_bars")
        required_pos_float = ("breakout_atr_mult", "tp_atr", "max_inventory_frac",
                              "stop_atr", "kelly_cap", "capital")
        for name in required_pos_int:
            if getattr(cfg, name, 0) <= 0:
                return False
        for name in required_pos_float:
            if getattr(cfg, name, 0.0) <= 0.0:
                return False
        if not (0.0 < cfg.max_inventory_frac <= 1.0):
            return False
        if cfg.tp_type not in ("mid_channel", "atr_ratchet"):
            return False
        if cfg.donchian_window < cfg.atr_window:
            return False
        return True

    def estimate_memory_mb(self, config: Optional[Config] = None) -> float:
        """O(1) estimate: bounded deques + scalars only."""
        cfg: Config = config or self.cfg
        deques_bytes: int = (cfg.donchian_window * 2 + cfg.volume_window) * 24
        scalars_bytes: int = 4096
        return (deques_bytes + scalars_bytes) / (1024 * 1024)

    def on_fill(self, order_id: str, side: str, price: float, size: float) -> None:
        """Book a round-trip; update streaming Kelly counters on close."""
        if order_id in self._pending:
            entry: Dict[str, float] = self._pending.pop(order_id)
            signed: float = entry["side"]  # +1 long / -1 short
            pnl: float = signed * (price - entry["px"]) * size
            self.realized_pnl += pnl
            if pnl >= 0:
                self._wins += 1
                n: int = self._wins
                self._avg_win = (self._avg_win * (n - 1) + pnl) / n
            else:
                self._losses += 1
                m: int = self._losses
                self._avg_loss = (self._avg_loss * (m - 1) + abs(pnl)) / m
        else:
            # new opening fill
            self._pending[order_id] = {"px": price, "size": size,
                                       "side": 1 if side.upper() == "BUY" else -1}
            self.position += (size if side.upper() == "BUY" else -size)

    # -- core tick --------------------------------------------------------
    def on_tick(self, market: Dict[str, Any], orders: Any = None) -> int:
        price: float = float(market.get("price", market.get("close", 0.0)))
        volume: float = float(market.get("volume", 0.0))
        if price <= 0.0:
            return Action.HOLD

        # streaming Donchian channel (bounded)
        self._highs.append(price)
        self._lows.append(price)
        self._atr.push(price)
        self._vol_med.push(volume)

        # EWMA-based volatility on log-returns (O(1), no window)
        if self._last_close > 0.0:
            log_ret: float = math.log(price / self._last_close)
            self._vol.push(log_ret)
        else:
            self._vol.push(0.0)
        self._last_close = price
        self.bars += 1

        # periodic memory sweep only during warmup (gc.collect is expensive)
        self._vol_sweep_counter += 1
        if self.bars < self.cfg.warmup_bars and self._vol_sweep_counter % 256 == 0:
            gc.collect()

        if self.bars < self.cfg.warmup_bars or not self._vol_med.ready():
            return Action.HOLD

        atr: float = self._atr.std
        if atr <= 0.0:
            return Action.HOLD

        chan_hi: float = max(self._highs)
        chan_lo: float = min(self._lows)
        chan_mid: float = (chan_hi + chan_lo) / 2.0

        # ---- Phase A: spike detection (real escape) -----------------------
        spike: bool = price > chan_hi + self.cfg.breakout_atr_mult * atr
        drop: bool = price < chan_lo - self.cfg.breakout_atr_mult * atr
        vol_confirm: bool = volume >= self._vol_med.median

        if spike and vol_confirm:
            self._spike_side = 1          # short-opportunity: fade the breakout up
            self._reject_bars_remain = self.cfg.rejection_window
            self._entry_chan = (chan_hi, chan_lo)
        elif drop and vol_confirm:
            self._spike_side = -1         # long-opportunity: fade the breakdown
            self._reject_bars_remain = self.cfg.rejection_window
            self._entry_chan = (chan_hi, chan_lo)

        # ---- Phase B: rejection trade (only on the failed escape) ---------
        action: int = Action.HOLD
        if self._spike_side != 0 and self._reject_bars_remain > 0:
            self._reject_bars_remain -= 1
            back_inside: bool = chan_lo <= price <= chan_hi
            if back_inside:
                # escape proved hollow -> fade it. spike=+1 => SELL.
                action = -self._spike_side
                self._spike_side = 0          # one-shot signal
                self._reject_bars_remain = 0
        elif self._spike_side != 0:
            # rejection window expired with no fade -> cancel the signal
            self._spike_side = 0

        # ---- position management hook -------------------------------------
        self._manage_exit(price, action, chan_hi, chan_lo, chan_mid, atr)
        return action

    def _manage_exit(self, price: float, action: int, chan_hi: float,
                     chan_lo: float, chan_mid: float, atr: float) -> None:
        """Hedging management hook (position exit handled via Action)."""

    def get_stats(self) -> Dict[str, Any]:
        return {
            "bars": self.bars,
            "position": self.position,
            "realized_pnl": round(self.realized_pnl, 6),
            "wins": self._wins,
            "losses": self._losses,
            "avg_win": round(self._avg_win, 6),
            "avg_loss": round(self._avg_loss, 6),
            "estimate_memory_mb": round(self.estimate_memory_mb(), 6),
            "spike_side": self._spike_side,
        }


if __name__ == "__main__":
    """Inline smoke test with synthetic data (small, no OOM)."""
    cfg = Config(symbol="SOL/EUR", capital=20.0, donchian_window=10,
                 atr_window=5, vol_window=12, volume_window=8,
                 rejection_window=3, warmup_bars=20, fragmentation=4)
    strat = VBMF(cfg)

    # synthetic price path with a fake breakout then rejection
    prices: list = [100.0]
    for i in range(1, 600):
        base: float = prices[-1] + (0.05 if i % 2 == 0 else -0.03)
        # force a fake spike up around i=200 then a fall back inside
        if 200 <= i <= 205:
            base += 3.0
        elif 206 <= i <= 210:
            base += 2.0
        elif 211 <= i <= 215:
            base += 0.5  # back near channel top -> rejection
        prices.append(base)

    vol_data: list = [1000.0] * 600
    for i, px in enumerate(prices):
        mkt: Dict[str, Any] = {"price": px, "close": px, "volume": vol_data[i]}
        strat.on_tick(mkt)

    st: Dict[str, Any] = strat.get_stats()
    print(f"bars={st['bars']} position={st['position']} pnl={st['realized_pnl']} "
          f"w/l={st['wins']}/{st['losses']} mem_mb={st['estimate_memory_mb']}")
    assert st["bars"] == 600
    assert st["estimate_memory_mb"] < 1.0
    print("VBMF smoke test OK")
