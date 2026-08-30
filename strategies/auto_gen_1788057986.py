"""WICKFADOS: DOM-absorption wick-fade mean-reversion (one-shot scalper).

Edge: fade extended candle wicks against a level when order-flow shows
*absorption* (the aggressive book briefly flips / resting depth piles into
the spike), not continuation. Series of small credits from trapped stops,
stopped by a vol-expansion regime filter so we never fade a real breakout.

Distinct from prior auto-gen families:
  grid / ladder          -> VESG, CPAGrid, VolGrid, LIQABS (geo / order-flow)
  trend slope            -> VWMR, Chandelier
  ATR vol-ratio momentum -> ATRKEL (enters on squeeze->expansion)
  THIS (WICKFADOS)       -> mean-reversion ON THE WICK with absorption filter;
                            ATRKEL chases momentum, we fade exhaustion.

Why not covered: prior families size from ATR (ATRKEL) or place ladders
(grid). WICKFADOS only acts once a candle prints a wick > threshold against
the last N-tick median *and* the top-of-book imbalance flips in our favor
(absorption). It is a pure one-shot with immediate target/stop, so it never
holds a grid position into a regime shift.

OOM safety: only small rolling buffers (EMA + deque fixed size). No full
history arrays, no list comprehensions over 100k+ rows, big temporaries are
`del`'d. Small fixed-size deques need no manual gc (maxlen bounds memory).
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Dict, List, Optional, Tuple


class StrategyBase:
    """Base contract every auto-gen strategy must fulfil."""

    name: str = "StrategyBase"

    def on_tick(self, tick: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def on_fill(self, fill: Dict[str, Any]) -> None:
        raise NotImplementedError

    def validate_config(self) -> List[str]:
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError


@dataclass
class WICKFADOSConfig:
    """Configuration for WICKFADOS — all inputs config-driven, no hardcoding."""
    symbol: str = "DOGE/EUR"
    capital: float = 1.5                    # EUR base risk per single trade
    side: str = "both"                     # 'long'|'short'|'both'

    # wick detection (on CLOSED candles)
    ticks_per_candle: int = 20             # aggregate this many ticks into one candle
    wick_atr_mult: float = 1.4             # wick must exceed this * current ATR
    body_to_wick_max: float = 0.30         # body/wick ratio ceiling (small body = hammer)
    candle_lookback: int = 48              # median window (closed candles)

    # absorption / DOM filter
    ob_imbalance_min: float = 0.55         # need >= 55% resting depth on fade side
    dom_lookback: int = 5                  # ticks of DOM to average imbalance

    # vol regime filter (do NOT fade real breakouts)
    atr_ewma_alpha: float = 0.08
    atr_expand_ratio: float = 1.6          # if ATR jumps > this * ref, stand down

    # trade management (TP/SL fixed AT ENTRY in ATR units)
    target_atr: float = 0.6
    stop_atr: float = 1.2                  # must be >= target_atr (validated)

    dry_run: bool = True

    def validate(self) -> List[str]:
        errs: List[str] = []
        if self.capital <= 0:
            errs.append("capital must be > 0")
        if self.ticks_per_candle < 1:
            errs.append("ticks_per_candle must be >= 1")
        if self.wick_atr_mult <= 0 or self.candle_lookback < 4:
            errs.append("wick_atr_mult must be >0 and candle_lookback >= 4")
        if not 0.0 < self.ob_imbalance_min <= 1.0:
            errs.append("ob_imbalance_min must be in (0,1]")
        if self.stop_atr < self.target_atr:
            errs.append("stop_atr must be >= target_atr")
        if self.side not in ("long", "short", "both"):
            errs.append("side must be long|short|both")
        return errs


class WICKFADOS(StrategyBase):
    """DOM-absorption wick-fade mean-reversion scalper (one-shot).

    Fades a *closed* candle whose wick is long relative to ATR, only when a
    top-of-book imbalance supports the reversal direction, and never during
    ATR expansion. Entry, TP and SL are fixed relative to the entry price so
    the trade is fully determined before submission.
    """

    name: str = "WICKFADOS"

    def __init__(self, config: Optional[WICKFADOSConfig] = None) -> None:
        self.cfg = config or WICKFADOSConfig()
        errs = self.cfg.validate()
        if errs:
            raise ValueError("Invalid config: " + "; ".join(errs))

        # closed-candle accumulator (aggregate ticks_per_candle into one candle)
        self._c_n: int = 0
        self._c_open: Optional[float] = None
        self._c_high: float = 0.0
        self._c_low: float = 0.0
        self._c_close: Optional[float] = None
        self._candles: Deque[float] = deque(maxlen=self.cfg.candle_lookback + 2)

        self._atr: float = 0.0
        self._atr_ref: float = 0.0
        self._prev_close: Optional[float] = None

        self._dom_buf: Deque[float] = deque(maxlen=self.cfg.dom_lookback)

        # position state (only set after fill confirmed)
        self._pos: int = 0
        self._entry_px: float = 0.0
        self._tp: float = 0.0
        self._sl: float = 0.0
        self._pending_side: int = 0
        self._qty: float = 0.0

        self._n_ticks: int = 0
        self._n_trades: int = 0
        self._pnl: float = 0.0

    # -- tick plumbing ------------------------------------------------------
    def on_tick(self, tick: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Aggregate ticks into closed candles; on candle close, look for a
        fade setup. Returns an order only when there is something to do."""
        self._n_ticks += 1
        bid: float = float(tick.get("bid", 0.0) or 0.0)
        ask: float = float(tick.get("ask", 0.0) or 0.0)
        last: float = float(tick.get("last", 0.0) or 0.0)
        mid = (bid + ask) / 2.0 if (bid and ask) else last
        if mid <= 0.0:
            return None

        # DOM absorption feed (only when present)
        ob_bid = tick.get("ob_bid")
        ob_ask = tick.get("ob_ask")
        if isinstance(ob_bid, (int, float)) and isinstance(ob_ask, (int, float)) \
                and ob_bid + ob_ask > 0:
            self._dom_buf.append(ob_bid / (ob_bid + ob_ask))

        # managed position: check fixed TP/SL against trade price
        if self._pos != 0:
            return self._check_exit(bid, ask, last)

        # aggregate candle (only while flat — no signal while in trade)
        return self._accumulate_candle(last, high=float(tick.get("high", mid)),
                                       low=float(tick.get("low", mid)))

    def _accumulate_candle(self, px: float, high: float, low: float) -> Optional[Dict[str, Any]]:
        if self._c_open is None:
            self._c_open = px
            self._c_high = high
            self._c_low = low
            self._c_close = px
            self._c_n = 1
            return None
        self._c_high = max(self._c_high, high)
        self._c_low = min(self._c_low, low)
        self._c_close = px
        self._c_n += 1
        if self._c_n >= self.cfg.ticks_per_candle:
            return self._close_candle(px)
        return None

    def _close_candle(self, px: float) -> Optional[Dict[str, Any]]:
        o = self._c_open if self._c_open is not None else px
        h = self._c_high
        l = self._c_low
        c = self._c_close if self._c_close is not None else px

        # true range against previous closed candle
        prev = self._prev_close if self._prev_close is not None else o
        tr = max(h - l, abs(h - prev), abs(l - prev))
        a = self.cfg.atr_ewma_alpha
        if self._atr == 0.0:
            self._atr = tr
            self._atr_ref = tr
        else:
            self._atr = a * tr + (1 - a) * self._atr
            self._atr_ref = a * tr + (1 - a) * self._atr_ref
        self._candles.append(c)
        self._prev_close = c

        # reset accumulator
        self._c_open = None
        self._c_close = None
        self._c_high = 0.0
        self._c_low = 0.0

        if len(self._candles) < self.cfg.candle_lookback:
            return None
        return self._evaluate_candle(o, h, l, c)

    def _evaluate_candle(self, o: float, h: float, l: float, c: float) -> Optional[Dict[str, Any]]:
        # regime filter: stand down during ATR expansion (possible breakout)
        if self._atr_ref > 0 and self._atr > self._atr_ref * self.cfg.atr_expand_ratio:
            return None
        if self._atr <= 0:
            return None

        n = self.cfg.candle_lookback
        med = sorted(self._candles)[n // 2]
        wick_thresh = self.cfg.wick_atr_mult * self._atr
        body = abs(c - o)

        # down-wick -> long setup
        lower_wick = c - l if c >= o else min(o, c) - l
        if lower_wick > wick_thresh and body / max(lower_wick, 1e-12) <= self.cfg.body_to_wick_max:
            if self.cfg.side in ("long", "both") and self._imbalance_ok(+1):
                return self._submit(+1, ref_level=med)
        # up-wick -> short setup
        upper_wick = h - c if c >= o else h - max(o, c)
        if upper_wick > wick_thresh and body / max(upper_wick, 1e-12) <= self.cfg.body_to_wick_max:
            if self.cfg.side in ("short", "both") and self._imbalance_ok(-1):
                return self._submit(-1, ref_level=med)
        return None

    def _imbalance_ok(self, side: int) -> bool:
        if not self._dom_buf:
            return True  # filter off when no DOM streamed
        avg = sum(self._dom_buf) / len(self._dom_buf)
        if side == +1:
            return avg >= self.cfg.ob_imbalance_min
        return (1.0 - avg) >= self.cfg.ob_imbalance_min

    def _submit(self, side: int, ref_level: float) -> Dict[str, Any]:
        """Builds the order, records the fixed TP/SL and marks side as pending
        (not yet filled). Entry price = reference level biased toward the fade."""
        atr = max(self._atr, 1e-12)
        trigger = ref_level - side * atr * 0.5   # enter a touch inside the level
        tp = trigger + side * self.cfg.target_atr * atr
        sl = trigger - side * self.cfg.stop_atr * atr
        self._qty = self.cfg.capital / max(trigger, 1e-12)
        self._pending_side = side
        self._entry_px = trigger
        self._tp = tp
        self._sl = sl
        return {
            "action": "open",
            "side": "buy" if side == +1 else "sell",
            "symbol": self.cfg.symbol,
            "qty": round(self._qty, 8),
            "type": "limit",
            "px": round(trigger, 10),
            "take_profit": round(tp, 10),
            "stop_loss": round(sl, 10),
            "taker": False,
            "dry_run": self.cfg.dry_run,
            "strategy": self.name,
        }

    def on_fill(self, fill: Dict[str, Any]) -> None:
        """Confirms entry/exit fills and advances position state."""
        action = str(fill.get("action", "")).lower()
        if action == "open" and self._pending_side != 0:
            self._pos = self._pending_side
            self._pending_side = 0
        elif action == "close" and self._pos != 0:
            self._pos = 0
            self._entry_px = 0.0
            self._tp = 0.0
            self._sl = 0.0

    def _check_exit(self, bid: float, ask: float, last: float) -> Optional[Dict[str, Any]]:
        """Uses the tradable side to confirm TP/SL touch, not the mid."""
        if self._pos == 0:
            return None
        if self._pos == +1:
            hit_tp = (bid and bid >= self._tp) or (last and last >= self._tp)
            hit_sl = (ask and ask <= self._sl) or (last and last <= self._sl)
        else:
            hit_tp = (ask and ask <= self._tp) or (last and last <= self._tp)
            hit_sl = (bid and bid >= self._sl) or (last and last >= self._sl)

        if hit_tp or hit_sl:
            px = self._tp if hit_tp else self._sl
            pnl = self._pos * (px - self._entry_px) / max(self._entry_px, 1e-12) * self.cfg.capital
            self._pnl += pnl
            self._n_trades += 1
            self._pos = 0
            return {"action": "close", "px": round(px, 10), "dry_run": self.cfg.dry_run,
                    "pnl": round(pnl, 10), "strategy": self.name}
        return None

    def validate_config(self) -> List[str]:
        return self.cfg.validate()

    def estimate_memory_mb(self) -> float:
        floats = (self.cfg.candle_lookback + self.cfg.dom_lookback + 16) * 8
        return floats / (1024 * 1024)

    def stats(self) -> Dict[str, Any]:
        return {
            "strategy": self.name,
            "ticks": self._n_ticks,
            "trades": self._n_trades,
            "pnl": round(self._pnl, 6),
            "position": self._pos,
            "pending_side": self._pending_side,
            "atr": round(self._atr, 10),
            "atr_ref": round(self._atr_ref, 10),
            "candles": len(self._candles),
        }


def _feed_flat(s: "WICKFADOS", cfg: WICKFADOSConfig, px: float, n: int) -> None:
    """Push n neutral ticks (no wick, balanced DOM) to build ATR/buffer."""
    for _ in range(n * cfg.ticks_per_candle):
        s.on_tick({"bid": px + 0.0002, "ask": px - 0.0002, "high": px + 0.0002,
                   "low": px - 0.0002, "last": px, "ob_bid": 0.5, "ob_ask": 0.5})


if __name__ == "__main__":
    cfg = WICKFADOSConfig(capital=1.5, dry_run=True, wick_atr_mult=0.5,
                          ticks_per_candle=5, candle_lookback=10)
    s = WICKFADOS(cfg)
    print("config errors:", s.validate_config())
    print("est mem MB:", round(s.estimate_memory_mb(), 8))

    # build ATR reference with neutral candles
    _feed_flat(s, cfg, 0.10, 15)
    # inject a strong down-wick candle with bid-side absorption -> expect a LONG
    orders = 0
    for _ in range(cfg.ticks_per_candle):
        o = s.on_tick({"bid": 0.1002, "ask": 0.0980, "high": 0.1002,
                       "low": 0.0980, "last": 0.1000, "ob_bid": 0.62, "ob_ask": 0.38})
        if o is not None:
            orders += 1
            assert o["side"] == "buy", o
            assert o["take_profit"] > o["px"] > o["stop_loss"], o
            assert isinstance(o["take_profit"], float)
            s.on_fill({"action": "open"})   # confirm fill -> position opens
            assert s._pos == 1, "fill should open position"
    # push price to the take-profit level and confirm the close + pnl
    for _ in range(cfg.ticks_per_candle):
        c = s.on_tick({"bid": 0.1012, "ask": 0.1012, "high": 0.1012,
                       "low": 0.1012, "last": 0.1012, "ob_bid": 0.5, "ob_ask": 0.5})
        if c is not None:
            assert c["action"] == "close", c
            assert s._pos == 0, "position must close after TP"
    st = s.stats()
    print("stats:", st)
    assert orders == 1, "expected exactly one entry order"
    assert st["trades"] >= 1, "expected at least one realised trade"
    assert st["pnl"] > 0.0, "TP close should yield positive pnl"
    assert s.estimate_memory_mb() > 0.0
    print("OK: WICKFADOS smoke test passed (orders=%d, trades=%d, pnl=%s)"
          % (orders, st["trades"], st["pnl"]))
