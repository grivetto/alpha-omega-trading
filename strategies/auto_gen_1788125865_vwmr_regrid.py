"""
VWMRGrid - griglia mean-reversion pesata su volume con re-anchor adattivo.

Innovazione rispetto a RegimeKellyGrid / FlowKong:
  1. Prezzo fair time-weighted (TWAP) + bias direzionale pesato su volume
     (VWAP rolling a finestra fissa): in regime di basso momentum il fair
     price diventa l'ancora della griglia (mean-reversion), NON l'ultimo tick.
  2. Re-anchor graduale: quando il VWAP si allontana dall'ancora corrente
     oltre una soglia, la griglia "scivola" verso il nuovo fair (re-anchoring
     senza riposizionamento istantaneo -> niente salti di ordini aggressivi).
  3. Spacing asimmetrico con cuscinetto di vol (ATR-like): in alta vol lo
     spacing cresce per evitare fill consecutivi in un unico movimento.
  4. Streaming puro: solo deque a finestra fissa, calcoli incrementali
     (somma corrente di px*vol e vol), niente list comprehension su serie
     lunghe -> memoria O(window), chunking intrinseco, gc periodico.

Convenzione: REGIME bias = +1 (long bias), -1 (short bias), 0 (neutro).
Ancora della griglia = fair_price (VWAP) invece del prezzo spot.

Requirements: StrategyBase con on_tick, on_fill, validate_config,
estimate_memory_mb.
"""
from __future__ import annotations

import gc
import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, Optional, Tuple

# --------------------------------------------------------------------------- #
# Config & costanti
# --------------------------------------------------------------------------- #

DEFAULTS: Dict[str, Any] = {
    "symbol": "NONE",
    "capital": 0.0,
    # finestre streaming
    "vwap_window": 60,           # finestra rolling per VWAP
    "twap_window": 30,           # finestra rolling per TWAP (fair neutro)
    "vol_window": 20,            # finestra per ATR-like spacing
    # bias / momentum
    "bias_threshold": 0.0025,    # |vwap-twap|/twap > soglia -> bias direzionale
    # griglia
    "levels_above": 5,
    "levels_below": 5,
    "spacing_base": 0.006,       # spacing a vol media
    "vol_spacing_gain": 3.0,     # spacing = base * (1 + gain * rel_vol)
    "anchoring_speed": 0.35,     # frazione di scivolamento verso nuovo fair
    "reanchor_threshold": 0.012, # se |fair - anchor|/anchor > soglia -> riancora
    # vol relativa
    "vol_norm": 0.008,           # vol di riferimento per normalizzare rel_vol
    # risk
    "max_exposure_quote": 0.6,   # max frazione capital allocata a inventario
    "max_drawdown": 0.10,        # sopra -> riduce exposure linearmente
    "dd_floor": 0.20,            # exposure minima come frazione del max
    "gc_interval": 500,
}


@dataclass
class _Position:
    qty: float = 0.0
    avg_cost: float = 0.0
    realized_pnl: float = 0.0
    peak_equity: float = 0.0


@dataclass
class _Stream:
    """Accumulatori incrementali a finestra fissa (O(1) update)."""
    prices: Deque[float] = field(default_factory=lambda: deque(maxlen=64))
    pv: Deque[float] = field(default_factory=lambda: deque(maxlen=64))   # price*vol
    vols: Deque[float] = field(default_factory=lambda: deque(maxlen=64))
    returns: Deque[float] = field(default_factory=lambda: deque(maxlen=64))
    sum_pv: float = 0.0
    sum_v: float = 0.0
    last_price: Optional[float] = None


class StrategyBase:
    """Contratto comune: ogni strategy auto-gen estende StrategyBase."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        cfg = dict(DEFAULTS)
        if config:
            cfg.update({k: v for k, v in config.items() if k in DEFAULTS})
        self.cfg: Dict[str, Any] = cfg
        self.validate_config()
        self.stream = _Stream()
        self.pos = _Position()
        self.anchor: Optional[float] = None      # ancora corrente della griglia
        self._ticks: int = 0
        self._gc_counter: int = 0

    # ------------------------------------------------------------------ #
    def on_tick(self, price: float, quote_bal: float = 0.0,
                base_bal: float = 0.0, timestamp: float = 0.0,
                volume: float = 0.0) -> Dict[str, Any]:
        raise NotImplementedError

    def on_fill(self, side: str, qty: float, price: float,
                fee: float = 0.0, timestamp: float = 0.0) -> Dict[str, Any]:
        raise NotImplementedError

    # ------------------------------------------------------------------ #
    def validate_config(self) -> None:
        cfg = self.cfg
        for key in ("vwap_window", "twap_window", "vol_window"):
            v = cfg.get(key, 0)
            if not isinstance(v, int) or v < 3:
                raise ValueError(f"config {key} deve essere int >= 3, got {v!r}")
        if cfg["vwap_window"] < cfg["twap_window"]:
            raise ValueError("vwap_window deve essere >= twap_window")
        for key in ("capital", "bias_threshold", "spacing_base",
                    "vol_spacing_gain", "anchoring_speed", "reanchor_threshold",
                    "vol_norm", "max_exposure_quote", "max_drawdown", "dd_floor"):
            v = cfg.get(key, 0.0)
            if not isinstance(v, (int, float)) or v < 0.0:
                raise ValueError(f"config {key} deve essere >= 0, got {v!r}")
        if not (0.0 < cfg["max_exposure_quote"] <= 1.0):
            raise ValueError("max_exposure_quote deve essere in (0, 1]")
        if not (0.0 < cfg["dd_floor"] <= 1.0):
            raise ValueError("dd_floor deve essere in (0, 1]")
        if not (0.0 < cfg["anchoring_speed"] <= 1.0):
            raise ValueError("anchoring_speed deve essere in (0, 1]")

    def estimate_memory_mb(self) -> float:
        """Stima memoria strutture streaming (deque a finestra fissa)."""
        w = max(self.cfg["vwap_window"], self.cfg["vol_window"], 64)
        per_deque = w * 32.0 / 1e6
        # 4 deque (prices, pv, vols, returns) + overhead
        total = 4 * per_deque + 0.02
        return round(min(1.0, total), 4)


class VWMRGrid(StrategyBase):
    """Griglia mean-reversion ancorata sul VWAP con spacing adattivo su vol."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(config)
        c = self.cfg
        # ridimensiona deque alla configurazione
        self.stream.prices = deque(maxlen=c["vwap_window"])
        self.stream.pv = deque(maxlen=c["vwap_window"])
        self.stream.vols = deque(maxlen=c["vwap_window"])
        self.stream.returns = deque(maxlen=c["vol_window"])
        self._levels: Deque[float] = deque(maxlen=64)

    # ------------------------------------------------------------------ #
    def _push(self, price: float, volume: float) -> None:
        """Update incrementale delle finestre streaming (O(1), no replica)."""
        st = self.stream
        # VWAP window
        v = max(volume, 1e-9)
        if len(st.prices) == st.prices.maxlen:  # tipo: deque
            old_p = st.prices[0]
            old_v = st.vols[0]
            st.sum_pv -= old_p * old_v
            st.sum_v -= old_v
        st.prices.append(price)
        st.vols.append(v)
        st.pv.append(price * v)
        st.sum_pv += price * v
        st.sum_v += v
        # vol window (log returns)
        if st.last_price is not None and st.last_price > 0.0 and price > 0.0:
            st.returns.append(math.log(price / st.last_price))
        st.last_price = price

    def _fair_and_bias(self, price: float) -> Tuple[float, int]:
        """Fair price (VWAP) + bias direzionale vs TWAP."""
        st = self.stream
        n = len(st.prices)
        if st.sum_v > 0.0 and n >= self.cfg["twap_window"]:
            vwap = st.sum_pv / st.sum_v
            # TWAP sulla coda della finestra senza copie (deque non sliceable):
            tail_sum = 0.0
            for i, px in enumerate(st.prices):
                if i >= n - self.cfg["twap_window"]:
                    tail_sum += px
            twap = tail_sum / self.cfg["twap_window"]
            if twap > 0.0:
                dev = (vwap - twap) / twap
                bias = 1 if dev > self.cfg["bias_threshold"] else (
                    -1 if dev < -self.cfg["bias_threshold"] else 0)
                return vwap, bias
        return price, 0

    def _rel_vol(self) -> float:
        """Volatilità relativa normalizzata dalla finestra vol."""
        rr = self.stream.returns
        n = len(rr)
        if n < 4:
            return 1.0
        mean = sum(rr) / n
        var = sum((x - mean) ** 2 for x in rr) / (n - 1)
        sd = math.sqrt(var) if var > 0.0 else 0.0
        norm = self.cfg["vol_norm"]
        return 1.0 + (sd / norm if norm > 0.0 else 0.0)

    def _building_blocks(self, price: float, quote_bal: float,
                         drawdown: float) -> Dict[str, Any]:
        c = self.cfg
        fair, bias = self._fair_and_bias(price)
        # anchoring: scivolamento graduale verso il fair
        if self.anchor is None:
            self.anchor = fair
        else:
            gap = (fair - self.anchor) / self.anchor if self.anchor > 0.0 else 0.0
            if abs(gap) > c["reanchor_threshold"]:
                # riancora: accetta il nuovo fair in un colpo (movimento deciso)
                self.anchor = fair
            else:
                # scivolamento graduale
                self.anchor += (fair - self.anchor) * c["anchoring_speed"]
        rel_vol = self._rel_vol()
        spacing = c["spacing_base"] * (1.0 + c["vol_spacing_gain"] * (rel_vol - 1.0))
        spacing = max(spacing, 1e-6)
        # exposure con riduzione in drawdown (lineare a floor)
        if drawdown >= c["max_drawdown"]:
            exp_frac = c["max_exposure_quote"] * c["dd_floor"]
        elif drawdown <= 0.0:
            exp_frac = c["max_exposure_quote"]
        else:
            t = drawdown / c["max_drawdown"]
            exp_frac = c["max_exposure_quote"] * (1.0 - t * (1.0 - c["dd_floor"]))
        exposure = exp_frac * c["capital"]
        # livelli asimmetrici: in bias long pesa sotto il fair, viceversa
        if bias > 0:
            below, above = c["levels_below"], max(1, c["levels_above"] - 1)
        elif bias < 0:
            below, above = max(1, c["levels_below"] - 1), c["levels_above"]
        else:
            below = above = min(c["levels_below"], c["levels_above"])
        self._levels.clear()
        anchor = self.anchor
        for i in range(1, below + 1):
            self._levels.append(anchor * (1.0 - spacing * i))
        for i in range(1, above + 1):
            self._levels.append(anchor * (1.0 + spacing * i))
        return {
            "anchor": round(anchor, 6),
            "fair_vwap": round(fair, 6),
            "bias": bias,
            "spacing": round(spacing, 6),
            "exposure_quote": round(exposure, 6),
            "levels_above": above,
            "levels_below": below,
            "rel_vol": round(rel_vol, 4),
        }

    # ------------------------------------------------------------------ #
    def on_tick(self, price: float, quote_bal: float = 0.0,
                base_bal: float = 0.0, timestamp: float = 0.0,
                volume: float = 0.0, drawdown: float = 0.0) -> Dict[str, Any]:
        if price is None or price <= 0.0:
            return {"action": "hold", "reason": "invalid_price"}
        self._ticks += 1
        self._push(price, volume)
        if len(self.stream.prices) < self.cfg["twap_window"]:
            if self.anchor is None:
                self.anchor = price
            return {"action": "hold", "reason": "warmup"}

        # equity corrente per drawdown tracking
        mark = base_bal * price + quote_bal
        if mark > self.pos.peak_equity:
            self.pos.peak_equity = mark
        dd = ((self.pos.peak_equity - mark) / self.pos.peak_equity
              if self.pos.peak_equity > 0.0 else 0.0)
        eff_dd = dd if dd else drawdown

        plan = self._building_blocks(price, quote_bal, eff_dd)

        if self.cfg["gc_interval"] > 0:
            self._gc_counter += 1
            if self._gc_counter >= self.cfg["gc_interval"]:
                gc.collect()
                self._gc_counter = 0

        return {"action": "grid", **plan, "drawdown": round(eff_dd, 5)}

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
    import random

    cfg = {
        "symbol": "DOGE/EUR", "capital": 10.0,
        "vwap_window": 60, "twap_window": 30, "vol_window": 20,
        "spacing_base": 0.006, "vol_spacing_gain": 3.0,
        "anchoring_speed": 0.35, "reanchor_threshold": 0.012,
    }
    s = VWMRGrid(cfg)
    print(f"est_mem_mb={s.estimate_memory_mb()}")

    random.seed(3)
    price = 0.15
    fills = []
    for i in range(240):
        # regime range con micro-trend poi discesa per bias short
        drift = 0.0 if i < 160 else -0.06
        price *= (1.0 + drift * 0.01 + random.uniform(-0.004, 0.004))
        vol = random.uniform(5000.0, 20000.0)
        out = s.on_tick(price, quote_bal=10.0, base_bal=0.0,
                        timestamp=float(i), volume=vol)
        assert "action" in out, "on_tick deve tornare action"
        if i % 40 == 0:
            fills.append((price, 0.5))
            r = s.on_fill("buy", 0.5, price)
            assert r["action"] == "ack", r
            rr = s.on_fill("sell", 0.25, price * 1.01)
            assert rr["action"] == "ack", rr
        if i % 60 == 0:
            print(f"tick{i} anchor={out.get('anchor')} fair={out.get('fair_vwap')} "
                  f"bias={out.get('bias')} spacing={out.get('spacing')} "
                  f"rel_vol={out.get('rel_vol')}")

    # validazione errori
    for bad in ({"capital": -5.0}, {"vwap_window": 2}, {"vwap_window": 10, "twap_window": 20},
                {"max_exposure_quote": 1.5}, {"anchoring_speed": 0.0}):
        try:
            VWMRGrid(bad)
            raise AssertionError(f"doveva alzare ValueError per {bad}")
        except ValueError:
            pass

    print("TEST_OK final_pos=%.4f realized_pnl=%.5f" % (s.pos.qty, s.pos.realized_pnl))
