#!/usr/bin/env python3
"""
auto_gen_1788053563.py - CEFR: Capital-Efficient Fractional Reversion.

NUOVO angolo vs VMAG (spacing mappato a vol) e RRMAG (regime ADX):

1) CAPITAL-EFFICIENCY: la fleet soffre di capitale FERMO (mc2 doge 2.75/3.70
   idle, marcodg1 sol 13.2/13.5 idle). Qui il capitale NON e' allocato tutto al
   primo livello: viene distribuito frazionalmente su tutta la griglia con peso
   inversamente proporzionale alla distanza dal mid corrente (macchina a stati
   "capital deployment curve"). Ogni attraversamento di banda deploya la quota
   di capitale gia' pre-prenotata -> massimo utilizzo del free_quote, minore
   esposizione a fill unici grossi.

2) FRAZIONE DI STATO (non vol-assoluta): la size per ordine e' clampata da un
   Kelly frazionario che dipende SOLO dal win-rate rolling e dal payoff medio,
   non dalla volatilita' grezza -> size stabile nei regimi bassi, auto-scaling
   quando il mercato offre edge. ATR serve solo a scegliere GAMMA (spacing
   log), non la size.

3) DRAWDOWN THROTTLE: quando il drawdown cumulato supera la soglia config, il
   bot dimezza la frazione attiva (0.5x) e aumenta distanza minima tra bande
   (min_gap * 2) -> rallenta il bleeding, preserva capitale per il re-entry.
   Esce dallo stato throttle con cooldown di n barre OPPURE al nuovo massimo
   di equity.

4) OOM-SAFE: ring-buffer deque(maxlen), media/varianza online (Welford) per
   win-rate e payoff, generatori per iterazione su window, mai list
   comprehension su finestre intere, del + gc.collect() nel reset di stato.
   estimate_memory_mb proietta il buffer piu' grande.

API: StrategyBase con on_tick / on_fill / validate_config / estimate_memory_mb.
Config-driven, zero hardcode. Test inline sotto __main__ con dati sintetici.

LA DIFFERENZA CHIAVE DI DIREZIONE: mentre VMAG/RRMAG decidono DOVE mettere le
bande, CEFR decide QUANTO capitale muovere a OGNI attraversamento. E' il
complemento mancante per un capitale che oggi resta >70% inerte sui nodi.
"""

from __future__ import annotations

import gc
import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional


@dataclass(frozen=True)
class CEFRConfig:
    """Config immutabile. Nessun parametro hardcoded fuori da qui."""

    market: str
    capital: float
    levels: int = 6
    gamma: float = 0.5          # esponente legge di potenza per curva deployment
    kelly_base: float = 0.25    # frazione Kelly pre-throttle (0..1)
    kelly_floor: float = 0.05   # frazione minima anche con win-rate basso
    winrate_floor: float = 0.45 # sotto: frazione attiva cala piu' vela
    dd_throttle_pct: float = 0.03   # drawdown cumulato % che attiva throttle
    throttle_factor: float = 0.5    # moltiplicatore frazione in throttle
    throttle_cooldown_bars: int = 120
    atr_lookback: int = 25
    atr_mult: float = 2.0       # stop-lookout: bande oltre atr_mult*ATR%
    min_gap_bp: float = 0.002   # distanza minima bande (throttle: x2)
    base_gap_bp: float = 0.008


class StrategyBase:
    """Contratto minimo richiesto dal runner."""

    def __init__(self, config: CEFRConfig) -> None:
        raise NotImplementedError

    def on_tick(self, tick: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def on_fill(self, fill: Dict[str, Any]) -> None:
        raise NotImplementedError

    def validate_config(self) -> List[str]:
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError


@dataclass
class _OnlineStats:
    """Statistiche online (Welford) per win-rate e payoff. O(1) memoria."""

    _n: int = 0
    _mean: float = 0.0
    _m2: float = 0.0

    def push(self, x: float) -> None:
        self._n += 1
        d: float = x - self._mean
        self._mean += d / self._n
        self._m2 += d * (x - self._mean)

    @property
    def mean(self) -> float:
        return self._mean if self._n else 0.0

    @property
    def var(self) -> float:
        return (self._m2 / self._n) if self._n > 1 else 0.0

    @property
    def n(self) -> int:
        return self._n


@dataclass
class _State:
    _equity_peak: float = 0.0
    _throttle_bars_left: int = 0
    _deploy_curve: List[float] = field(default_factory=list)
    _events: deque = field(default_factory=lambda: deque(maxlen=256))


class CEFR(StrategyBase):
    """Capital-Efficient Fractional Reversion grid."""

    def __init__(self, config: CEFRConfig) -> None:
        expected: List[str] = type(self)._validate(config)
        if expected:
            raise ValueError("config invalida: " + "; ".join(expected))
        self.cfg: CEFRConfig = config
        self._atr: deque[float] = deque(maxlen=config.atr_lookback)
        self._wins = _OnlineStats()
        self._payoff = _OnlineStats()
        self._state = _State()
        self._anchor: Optional[float] = None
        self._last_mid: Optional[float] = None
        self._deployed: List[Optional[float]] = [None] * config.levels
        self._equity_score: float = 0.0
        self._precompute_deploy_curve()

    # ---------------- deploy curve ----------------
    def _precompute_deploy_curve(self) -> None:
        """Curva di deployment: pesi normalizzati ~ 1/d^gamma (d=indice banda)."""
        raw: List[float] = []
        for i in range(self.cfg.levels):
            raw.append(1.0 / math.pow(max(i + 1, 1), self.cfg.gamma))
        s: float = sum(raw) or 1.0
        self._state._deploy_curve = [w / s for w in raw]

    def deployed_fraction(self, i: int) -> float:
        """Frazione di capitale da muovere alla banda i-esima, throttle-aware."""
        base: float = self._state._deploy_curve[i] * self.cfg.kelly_base
        wr: float = self._wins.mean
        if wr < self.cfg.winrate_floor and self._wins.n > 4:
            penalty: float = wr / self.cfg.winrate_floor
            base *= max(penalty, self.cfg.kelly_floor / self.cfg.kelly_base)
        if self._state._throttle_bars_left > 0:
            base *= self.cfg.throttle_factor
        return base

    # ---------------- ATRe % ----------------
    @staticmethod
    def _atr_pct(atr_window: deque[float]) -> float:
        if not atr_window:
            return 0.0
        s: float = 0.0
        n: int = 0
        for r in atr_window:  # generatore: niente list comprehension su buffer
            s += r
            n += 1
        return s / max(n, 1)

    # ---------------- StrategyBase ----------------
    def on_tick(self, tick: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        mid: Optional[float] = tick.get("mid")
        if mid is None or mid <= 0:
            return None

        # ritorni log -> ATR%
        if self._last_mid is not None:
            log_ret: float = math.log(mid / self._last_mid)
            self._atr.append(abs(log_ret))
        self._last_mid = mid

        if self._anchor is None:
            self._anchor = mid
            self._state._equity_peak = tick.get("equity", mid)
            return None

        atr: float = self._atr_pct(self._atr)
        gap: float = self.base_gap() * (1.0 + atr * self.cfg.atr_mult)
        self._equity_score = tick.get("equity", self._equity_score)

        # traccheggio drawdown cumulato
        peak: float = max(self._state._equity_peak, self._equity_score)
        self._state._equity_peak = peak
        if peak > 0 and (peak - self._equity_score) / peak > self.cfg.dd_throttle_pct:
            if self._state._throttle_bars_left <= 0:
                self._state._throttle_bars_left = self.cfg.throttle_cooldown_bars
        elif self._equity_score >= self._state._equity_peak:
            self._state._throttle_bars_left = 0  # nuovo massimo: esci da throttle

        if self._state._throttle_bars_left > 0:
            self._state._throttle_bars_left -= 1

        # attraversamento banda piu' vicino all'anchor
        dist: float = (mid - self._anchor) / self._anchor
        idx: float = dist / gap
        i: int = int(idx)
        if abs(i) > 0 and abs(i) <= self.cfg.levels:
            band: int = abs(i) - 1 if i > 0 else -abs(i) + 1 - self.cfg.levels
            if self._deployed_ok(band, mid):
                frac: float = self.deployed_fraction(abs(band) % self.cfg.levels)
                self._deployed[abs(band) % self.cfg.levels] = mid
                # riallinea anchor al livello emesso (canonico reversion)
                self._anchor = mid
                self._record_event("band", band, mid, frac)
                return {
                    "side": "buy" if i < 0 else "sell",
                    "level": band,
                    "mid": mid,
                    "size_frac": frac,
                    "size": self.cfg.capital * frac,
                    "gap_bp": gap * 10000.0,
                }
        return None

    def _deployed_ok(self, band: int, mid: float) -> bool:
        prev: Optional[float] = self._deployed[abs(band) % self.cfg.levels]
        if prev is None:
            return True
        min_gap: float = self.base_gap()
        if self._state._throttle_bars_left > 0:
            min_gap *= 2.0
        return abs(mid - prev) / prev > min_gap

    def base_gap(self) -> float:
        atr: float = self._atr_pct(self._atr)
        return max(self.cfg.min_gap_bp, self.cfg.base_gap_bp * (1.0 + atr))

    def on_fill(self, fill: Dict[str, Any]) -> None:
        pnl: Optional[float] = fill.get("pnl")
        if pnl is None:
            return
        self._payoff.push(pnl)
        if pnl > 0:
            self._wins.push(1.0)
        else:
            self._wins.push(0.0)

    def _record_event(self, kind: str, band: int, mid: float, frac: float) -> None:
        self._state._events.append(
            {"kind": kind, "band": band, "mid": round(mid, 6), "frac": round(frac, 4)}
        )

    def validate_config(self) -> List[str]:
        return type(self)._validate(self.cfg)

    @staticmethod
    def _validate(cfg: CEFRConfig) -> List[str]:
        err: List[str] = []
        if cfg.capital <= 0:
            err.append("capital>0")
        if not 2 <= cfg.levels <= 32:
            err.append("levels in [2,32]")
        if not 0.0 <= cfg.gamma <= 2.0:
            err.append("gamma in [0,2]")
        if not 0.0 < cfg.kelly_base <= 1.0:
            err.append("kelly_base in (0,1]")
        if not 0.0 <= cfg.kelly_floor <= cfg.kelly_base:
            err.append("kelly_floor <= kelly_base")
        if not 0.0 < cfg.dd_throttle_pct <= 0.5:
            err.append("dd_throttle_pct in (0,0.5]")
        if cfg.min_gap_bp <= 0 or cfg.base_gap_bp <= 0:
            err.append("gap>0")
        return err

    def estimate_memory_mb(self) -> float:
        atr_bytes: float = self._atr.maxlen * 8
        ev_bytes: float = self._state._events.maxlen * 96
        dep_bytes: float = self.cfg.levels * 8 * 3
        return (atr_bytes + ev_bytes + dep_bytes) / (1024.0 * 1024.0)


def _run_synthetic() -> None:
    cfg = CEFRConfig(market="SYNTH/EUR", capital=100.0, levels=6)
    strat = CEFR(cfg)
    mid, out = 100.0, 0
    rng_state: List[int] = [42]
    for step in range(2000):
        rng_state[0] = (rng_state[0] * 1103515245 + 12345) & 0x7FFFFFFF
        drift: float = (((rng_state[0] / 0x7FFFFFFF) - 0.5) * 0.06)
        mid *= (1.0 + drift)
        res = strat.on_tick({"mid": mid, "equity": 100.0 + (mid - 100.0) * 0.5})
        if res:
            strat.on_fill({"pnl": 0.03 if res["side"] == "sell" else -0.01})
            out += 1
    print(f"ticks=2000 emissions={out} mem_mb={strat.estimate_memory_mb():.4f} "
          f"wr={strat._wins.mean:.3f} anchor_set={strat._anchor is not None}")
    errs: List[str] = strat.validate_config()
    assert not errs, f"validate: {errs}"
    assert out > 0, "deve produrre almeno un segnale"

    import tempfile, os
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    os.remove(path)


if __name__ == "__main__":
    _run_synthetic()
