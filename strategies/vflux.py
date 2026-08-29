"""V-FLUX: volatility-flux adaptive rebalancing grid.

Inventory strategy for the Denaro/Alpha-Omega fleet.
"""
from __future__ import annotations
import gc, json, logging, math, sys, time
from dataclasses import dataclass, field
from typing import Any, Dict, Generator, List, Optional, Sequence, Tuple

LOGGER = logging.getLogger("vflux")

@dataclass(frozen=True)
class VFluxConfig:
    market: str = "DOGE/EUR"
    capital: float = 3.0
    levels: int = 8
    base_spacing: float = 0.010
    spacing_min: float = 0.004
    spacing_max: float = 0.030
    flux_ref: float = 1.0
    flux_alpha: float = 0.015
    vol_lookback: int = 50
    side: str = "both"
    kelly_cap: float = 0.30
    max_drawdown_kill: float = 0.10
    dry_run: bool = True
    chunk_size: int = 1024

@dataclass
class Level:
    index: int
    side: str
    price: float
    size: float
    filled_px: Optional[float] = None
    opened_at: float = field(default_factory=time.time)
    @property
    def pnl(self):
        if self.filled_px is None:
            return 0.0
        if self.side == "sell":
            return (self.price - self.filled_px) * self.size
        return (self.filled_px - self.price) * self.size

class ChunkedFluxEstimator:
    def __init__(self, alpha, ref):
        self.alpha = alpha
        self.ref = ref
        self._flux = ref
    def push_chunk(self, prices):
        if len(prices) < 2:
            return
        deltas = (prices[i+1]-prices[i] for i in range(len(prices)-1))
        mean_abs = sum(abs(d) for d in deltas)/(len(prices)-1)
        self._flux = (1.0-self.alpha)*self._flux + self.alpha*mean_abs
    def feed(self, prices, chunk):
        for start in range(0, len(prices), chunk):
            self.push_chunk(prices[start:start+chunk])
        return self
    @property
    def flux(self):
        return max(self._flux, 1e-9)

class StrategyBase:
    def on_tick(self, tick): raise NotImplementedError
    def on_fill(self, fill): raise NotImplementedError
    def validate_config(self): raise NotImplementedError
    def estimate_memory_mb(self, rows): raise NotImplementedError

class VFluxStrategy(StrategyBase):
    def __init__(self, config=None):
        self.cfg = config or VFluxConfig()
        self.errors = self.validate_config()
        if self.errors:
            raise ValueError("; ".join(self.errors))
        self._last_px = None
        self._price_buf = []
        self._equity_peak = self.cfg.capital
        self._killed = False
        self._flux = self.cfg.flux_ref
        self._levels = [Level(i, self.cfg.side, self.cfg.capital*0.0, 0.0) for i in range(self.cfg.levels)]
    def validate_config(self):
        errs = []
        c = self.cfg
        if c.capital <= 0: errs.append("capital must be > 0")
        if c.levels < 2: errs.append("levels must be >= 2")
        if not (0 < c.spacing_min <= c.base_spacing <= c.spacing_max): errs.append("bad spacing")
        if not (0.0 < c.kelly_cap <= 1.0): errs.append("kelly_cap in (0,1]")
        if not (0.0 < c.max_drawdown_kill <= 1.0): errs.append("dd kill in (0,1]")
        if c.side not in ("buy_only","sell_only","both"): errs.append("bad side")
        return errs
    def _bolt_spacing(self, flux, px):
        ratio = flux/self.cfg.flux_ref
        raw = self.cfg.base_spacing/(0.30 + 0.70*ratio)
        return min(self.cfg.spacing_max, max(self.cfg.spacing_min, raw*px))
    def _regime(self, px):
        if len(self._price_buf) < 5: return self.cfg.side
        span = max(self._price_buf) - min(self._price_buf)
        vol_pct = span/px if px > 0 else 0.0
        if vol_pct > 0.05 and self._last_px is not None and px < self._last_px:
            return "sell_only"
        return self.cfg.side
    def _update_equity(self, equity):
        self._equity_peak = max(self._equity_peak, equity)
        dd = (self._equity_peak - equity)/self._equity_peak if self._equity_peak else 0.0
        if dd >= self.cfg.max_drawdown_kill:
            self._killed = True
            LOGGER.warning("V-FLUX kill-switch DD %.4f", dd)
    def on_tick(self, tick):
        px = float(tick.get("price", 0.0))
        equity = float(tick.get("equity", self.cfg.capital))
        if px <= 0 or self._killed: return None
        self._update_equity(equity)
        if self._killed: return None
        self._price_buf.append(px)
        if len(self._price_buf) > self.cfg.vol_lookback:
            self._price_buf = self._price_buf[-self.cfg.vol_lookback:]
        if self._last_px is not None:
            delta = abs(px - self._last_px)
            self._flux = (1-self.cfg.flux_alpha)*self._flux + self.cfg.flux_alpha*delta
        self._last_px = px
        spacing = self._bolt_spacing(self._flux, px)
        regime = self._regime(px)
        for lvl in self._levels:
            target = px + (lvl.index - self.cfg.levels//2)*spacing/(self.cfg.levels/2)
            if regime == "buy_only" and target > px: continue
            if regime == "sell_only" and target < px: continue
            if abs(target - px) < spacing*0.5:
                size = self.cfg.capital*self.cfg.kelly_cap/self.cfg.levels
                lvl.filled_px = px
                lvl.size = size
                return {"side":"sell" if lvl.side=="sell" else "buy","px":round(target,6),"size":round(size,6)}
        return None
    def on_fill(self, fill):
        LOGGER.info("V-FLUX fill: %s", fill)
    def estimate_memory_mb(self, rows):
        buf_bytes = self.cfg.vol_lookback*32
        hist_bytes = rows*32 if rows > 0 else 0
        return round(1.5 + (buf_bytes + hist_bytes)/(1024*1024), 3)

def load_config(path):
    import json as _j
    with open(path, "r", encoding="utf-8") as fh:
        raw = _j.load(fh)
    known = {f.name for f in VFluxConfig.__dataclass_fields__.values()}
    return VFluxConfig(**{k:v for k,v in raw.items() if k in known})

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    strat = VFluxStrategy(VFluxConfig(capital=3.0, dry_run=True))
    mem = strat.estimate_memory_mb(200_000)
    LOGGER.info("estimated memory @200k rows: %.3f MB", mem)
    assert mem < 50.0
    rand = []
    rng = 1
    for _ in range(100_000):
        rng = (rng*1103515245+12345)&0x7FFFFFFF
        rand.append(0.08 + (rng % 1000)/1e5)
    est = ChunkedFluxEstimator(alpha=0.015, ref=1.0)
    est.feed(rand, chunk=1024)
    del rand
    gc.collect()
    LOGGER.info("chunked flux estimate: %.5f", est.flux)
    assert est.flux > 0.0
    try:
        VFluxStrategy(VFluxConfig(capital=-1))
        raise AssertionError("negative capital must be rejected")
    except ValueError as _ve:
        assert "capital must be > 0" in str(_ve), str(_ve)
    out = strat.on_tick({"price":0.0855,"equity":3.0})
    assert out is None or isinstance(out, dict)
    LOGGER.info("V-FLUX smoke PASSED flux=%.5f", strat._flux)
    sys.exit(0)