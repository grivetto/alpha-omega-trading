"""
RegimeKellyGrid - griglia adattiva con regime detection e sizing frazionario.

Novità rispetto alle strategie precedenti (volimbalance, regimeswitch):
  1. Rilevamento regime combinato: DR (directional ratio, proxy ADX) + vol EWMA
     su due finestre (fast/slow) -> stato {trend_up, trend_dn, range}.
  2. Sizing posizione frazionario: base sul drawdown corrente riduce
     l'esposizione (inverso di Kelly, saturato), evita over-leverage in drawdown.
  3. Resizing dinamico della griglia: in trend lo spacing si allarga e la griglia
     si sbilancia verso la direzione; in range lo spacing torna stretto.
  4. Streaming puro: solo deque a finestra fissa, nessuna list comprehension
     su serie lunghe -> memoria O(window), chunking intrinseco.

Convenzione valori: REGIME = +1 (trend_up), -1 (trend_dn), 0 (range).
ROI/equity totali tracciati in modo incrementale (niente repliche della storia).

Requirements: StrategyBase con on_tick, on_fill, validate_config, estimate_memory_mb.
"""
from __future__ import annotations

import gc
import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, Optional

# --------------------------------------------------------------------------- #
# Config & costanti
# --------------------------------------------------------------------------- #

DEFAULTS: Dict[str, Any] = {
    "symbol": "NONE",
    "capital": 0.0,
    # regime tuning
    "dr_period": 14,          # finestra directional ratio
    "dr_threshold": 0.22,     # sopra -> trend, sotto -> range
    "vol_fast": 12,           # vol EWMA fast
    "vol_slow": 48,           # vol EWMA slow
    "vol_regime_mult": 1.35,  # fast/slow > mult -> regime di alta vol
    "trend_levels_above": 5,
    "trend_levels_below": 2,
    "range_levels": 4,
    "spacing_trend": 0.012,   # spacing largo in trend
    "spacing_range": 0.005,   # spacing stretto in range
    # sizing / risk
    "base_capital": 10.0,     # riferimento per capital-normalizzato
    "kelly_fraction": 0.35,   # frazione kelly aggressiva ma non esplosiva
    "max_inventory": 0.6,     # max frazione base detenuta
    "max_drawdown": 0.10,     # sopra -> riduce sizing linearmente a floor
    "drawdown_floor": 0.15,   # sizing minimo come frazione del kelly
    "gc_interval": 500,
}


@dataclass
class _Position:
    qty: float = 0.0
    avg_cost: float = 0.0
    realized_pnl: float = 0.0
    peak_equity: float = 0.0


@dataclass
class _RegimeState:
    dr: float = 0.0
    vol_ratio: float = 1.0
    direction: int = 0          # +1 up, -1 dn
    high_vol: bool = False
    mode: str = "range"         # trend_up | trend_dn | range
    n: int = 0
    _hist: Deque[float] = field(default_factory=lambda: deque(maxlen=400))


class StrategyBase:
    """Contratto comune: ogni strategy auto-gen estende StrategyBase."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        cfg = dict(DEFAULTS)
        if config:
            cfg.update({k: v for k, v in config.items() if k in DEFAULTS})
        self.cfg: Dict[str, Any] = cfg
        self.validate_config()
        self.regime = _RegimeState()
        self.pos = _Position()
        self.last_price: Optional[float] = None
        self._ticks: int = 0
        self._gc_counter: int = 0
        self._recompute_regime(model=None) if hasattr(self, "_recompute_regime") else None

    # --- hook di default (overridabili) ----------------------------------- #
    def on_tick(self, price: float, quote_bal: float = 0.0,
                base_bal: float = 0.0, timestamp: float = 0.0) -> Dict[str, Any]:
        raise NotImplementedError

    def on_fill(self, side: str, qty: float, price: float,
                fee: float = 0.0, timestamp: float = 0.0) -> Dict[str, Any]:
        raise NotImplementedError

    # ------------------------------------------------------------------ #
    def validate_config(self) -> None:
        cfg = self.cfg
        for key in ("dr_period", "vol_fast", "vol_slow"):
            v = cfg.get(key, 0)
            if not isinstance(v, int) or v < 2:
                raise ValueError(f"config {key} deve essere int >= 2, got {v!r}")
        for key in ("capital", "dr_threshold", "vol_regime_mult",
                    "spacing_trend", "spacing_range", "kelly_fraction",
                    "max_inventory", "max_drawdown", "drawdown_floor"):
            v = cfg.get(key, 0.0)
            if not isinstance(v, (int, float)) or v < 0.0:
                raise ValueError(f"config {key} deve essere >= 0, got {v!r}")
        if cfg["max_inventory"] <= 0.0 or cfg["max_inventory"] > 1.0:
            raise ValueError("max_inventory deve essere in (0, 1]")
        if not (0.0 <= cfg["kelly_fraction"] <= 1.0):
            raise ValueError("kelly_fraction deve essere in [0, 1]")
        if not (0.0 < cfg["drawdown_floor"] <= 1.0):
            raise ValueError("drawdown_floor deve essere in (0, 1]")

    def estimate_memory_mb(self) -> float:
        """Stima memoria della struttura dati principale (deque window)."""
        # regime._hist maxlen=400, drift windows dentro _RegimeState via deque
        # stima conservativa: 800 float * 32B + overhead ~ 0.1MB, satura a 1MB
        return round(min(1.0, 0.08 + (self.regime._hist.maxlen or 0) * 32.0 / 1e6), 4)


class RegimeKellyGrid(StrategyBase):
    """Griglia adattiva con regime detection e sizing frazionario anti-drawdown."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(config)
        c = self.cfg
        # buffer streaming a finestra fissa
        self._dr_hist: Deque[float] = deque(maxlen=c["dr_period"] * 2)
        self._fast_hist: Deque[float] = deque(maxlen=c["vol_fast"])
        self._slow_hist: Deque[float] = deque(maxlen=c["vol_slow"])
        self._last: Optional[float] = None
        self.regime._hist = deque(maxlen=400)  # sostituisce default
        self._levels: Deque[float] = deque(maxlen=32)
        self._refill_trigger: bool = False

    # ------------------------------------------------------------------ #
    def _ewma(self, hist: Deque[float], new: float, alpha: float) -> float:
        if not hist:
            hist.append(new)
            return new
        prev = hist[-1]
        acc = alpha * new + (1.0 - alpha) * prev
        hist.append(acc)
        return acc

    def _update_dr(self, price: float) -> None:
        """ADX-like directional ratio, streaming su finestra fissa.

        Accumula movimenti up/dn normalizzati sul prezzo, poi valuta
        |sum_up - sum_dn| / (sum_up + sum_dn) sulla finestra (0..1).
        """
        if self._last is not None and price > 0.0 and self._last > 0.0:
            tr = (price + self._last) / 2.0
            if tr > 0.0:
                up = max(price - self._last, 0.0) / tr
                dn = max(self._last - price, 0.0) / tr
                self._dr_hist.append((up, dn))
        self._last = price

    def _update_vol(self, price: float) -> None:
        if self._last is not None and price > 0.0 and self._last > 0.0:
            ret = math.log(price / self._last)
        else:
            ret = 0.0
        # vol EWMA su due finestre -> ratio
        self._ewma(self._fast_hist, ret, 2.0 / (self.cfg["vol_fast"] + 1.0))
        self._ewma(self._slow_hist, ret, 2.0 / (self.cfg["vol_slow"] + 1.0))

    def _regime_mode(self) -> str:
        c = self.cfg
        if len(self._dr_hist) < c["dr_period"]:
            return "range"
        sum_up = 0.0
        sum_dn = 0.0
        n = len(self._dr_hist) if len(self._dr_hist) > 0 else 1
        for up, dn in self._dr_hist:
            sum_up += up
            sum_dn += dn
        total = sum_up + sum_dn
        dr = abs(sum_up - sum_dn) / total if total > 0.0 else 0.0
        fast = self._fast_hist[-1] if self._fast_hist else 0.0
        slow = self._slow_hist[-1] if self._slow_hist else 1e-12
        self.regime.dr = dr
        self.regime.vol_ratio = fast / slow if slow else 1.0
        self.regime.high_vol = self.regime.vol_ratio > c["vol_regime_mult"]
        if dr > c["dr_threshold"]:
            direction = 1 if (sum_up - sum_dn) >= 0.0 else -1
            self.regime.direction = direction
            self.regime.mode = "trend_up" if direction > 0 else "trend_dn"
        else:
            self.regime.direction = 0
            self.regime.mode = "range"
        return self.regime.mode

    def _sizing(self, drawdown: float) -> float:
        """Sizing frazionario: riduce lineaarmente con il drawdown."""
        c = self.cfg
        if drawdown <= 0.0:
            return c["kelly_fraction"]
        if drawdown >= c["max_drawdown"]:
            return c["kelly_fraction"] * c["drawdown_floor"]
        # interpolazione lineare da full a floor
        t = drawdown / c["max_drawdown"]
        kelly = c["kelly_fraction"] * (1.0 - t * (1.0 - c["drawdown_floor"]))
        return max(kelly, c["kelly_fraction"] * c["drawdown_floor"])

    def _build_levels(self, price: float, qty_quote: float,
                      drawdown: float) -> Dict[str, Any]:
        c = self.cfg
        mode = self.regime.mode
        kelly = self._sizing(drawdown)
        if mode.startswith("trend"):
            above, below = c["trend_levels_above"], c["trend_levels_below"]
            spacing = c["spacing_trend"]
            if mode == "trend_dn":
                above, below = below, above  # sbilancia verso il basso
        else:
            above = below = c["range_levels"]
            spacing = c["spacing_range"]
        self._levels.clear()
        for i in range(1, below + 1):
            self._levels.append(price * (1.0 - spacing * i))
        for i in range(1, above + 1):
            self._levels.append(price * (1.0 + spacing * i))
        exposure = min(kelly, c["max_inventory"]) * qty_quote
        return {
            "mode": mode,
            "kelly": round(kelly, 4),
            "exposure_quote": round(exposure, 6),
            "levels_above": above,
            "levels_below": below,
            "spacing": spacing,
        }

    # ------------------------------------------------------------------ #
    def on_tick(self, price: float, quote_bal: float = 0.0,
                base_bal: float = 0.0, timestamp: float = 0.0,
                drawdown: float = 0.0) -> Dict[str, Any]:
        if price is None or price <= 0.0:
            return {"action": "hold", "reason": "invalid_price"}
        self._ticks += 1
        if self._last is None:
            self._last = price
            return {"action": "hold", "reason": "warmup"}
        self._update_dr(price)
        self._update_vol(price)
        mode = self._regime_mode()

        # equity corrente per drawdown tracking
        mark = base_bal * price + quote_bal
        if mark > self.pos.peak_equity:
            self.pos.peak_equity = mark
        dd = (self.pos.peak_equity - mark) / self.pos.peak_equity if self.pos.peak_equity > 0 else 0.0

        qty_quote = self.cfg["capital"]
        plan = self._build_levels(price, qty_quote, dd if dd else drawdown)

        # memoria: gc periodico
        if self.cfg["gc_interval"] > 0:
            self._gc_counter += 1
            if self._gc_counter >= self.cfg["gc_interval"]:
                gc.collect()
                self._gc_counter = 0

        return {"action": "grid", **plan, "drawdown": round(dd, 5)}

    def on_fill(self, side: str, qty: float, price: float,
                fee: float = 0.0, timestamp: float = 0.0) -> Dict[str, Any]:
        if qty <= 0.0 or price <= 0.0:
            return {"action": "reject", "reason": "invalid_fill"}
        side = side.lower()
        if side == "buy":
            cost = qty * price
            if self.pos.qty > 0.0:
                prev_cost = self.pos.qty * self.pos.avg_cost
                self.pos.qty += qty
                self.pos.avg_cost = (prev_cost + cost) / self.pos.qty
            else:
                self.pos.qty = qty
                self.pos.avg_cost = price
        elif side == "sell":
            if qty > self.pos.qty:
                return {"action": "reject", "reason": "short_not_allowed"}
            self.pos.realized_pnl += (price - self.pos.avg_cost) * qty - fee
            self.pos.qty -= qty
        else:
            return {"action": "reject", "reason": f"unknown_side:{side}"}
        return {
            "action": "ack",
            "side": side,
            "qty": qty,
            "realized_pnl": round(self.pos.realized_pnl, 8),
            "position": round(self.pos.qty, 8),
        }


# --------------------------------------------------------------------------- #
# Test inline con dati sintetici piccoli
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    cfg = {
        "symbol": "DOGE/EUR", "capital": 10.0,
        "dr_period": 14, "vol_fast": 12, "vol_slow": 48,
        "spacing_trend": 0.012, "spacing_range": 0.005,
        "levels_below_default": 4,
    }
    s = RegimeKellyGrid(cfg)
    mem = s.estimate_memory_mb()
    print(f"est_mem_mb={mem}")

    import random
    random.seed(7)
    price = 100.0
    buys_raw = []
    for i in range(120):
        drift = 0.12 if i > 40 else -0.12   # simula regime up dopo warmup dn
        price *= (1.0 + drift * 0.01 + random.uniform(-0.004, 0.004))
        out = s.on_tick(price, quote_bal=10.0, base_bal=0.0, timestamp=float(i))
        assert "action" in out, "on_tick deve tornare action"
        if i % 25 == 0:
            buys_raw.append((price, 0.5))
        print(f"tick{i} mode={s.regime.mode} kelly={out.get('kelly')} "
              f"above={out.get('levels_above')} below={out.get('levels_below')}")

    for p, q in buys_raw:
        r = s.on_fill("buy", q, p)
        assert r["action"] == "ack", r
        rr = s.on_fill("sell", q * 0.5, p * 1.02)
        assert rr["action"] == "ack", rr

    # validazione errori
    try:
        RegimeKellyGrid({"capital": -5.0})
        raise AssertionError("doveva alzare ValueError per capital negativo")
    except ValueError:
        pass
    try:
        RegimeKellyGrid({"dr_period": 1})
        raise AssertionError("doveva alzare ValueError per dr_period<2")
    except ValueError:
        pass

    print("TEST_OK final_pos=%.4f realized_pnl=%.5f" % (s.pos.qty, s.pos.realized_pnl))
