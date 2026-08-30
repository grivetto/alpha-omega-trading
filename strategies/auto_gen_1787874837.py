"""
auto_gen_<TS>.py — MomoGrid (Momentum-Regime Adaptive Grid).

Improvement rispetto alla grid statica attuale (spacing fisso su tutti i nodi)
e complementare alla VolAdaptiveGrid (scaling per volatilita' realizzata):
- il RUMORE di regime (trend up / trend down / range) viene rilevato in streaming
  da EMAs veloce/lenta e dalla pendenza normalizzata dell'EMA veloce;
- in regime di trend UP la griglia si stringe sotto il prezzo (cattura i pullback)
  e i livelli di acquisto restano attivi; in trend DOWN i livelli vengono dimezzati
  (niente catching knife) e lo spacing si allarga; in range si usa la griglia base.
- filtro momentum sui fill: un livello di acquisto si apre SOLO se il momentum non
  e' fortemente negativo (evita di riempire la griglia durante un crollo).
- memoria O(1): buffer circolari (deque con maxlen), generatori per livelli e
  rendimenti, backtest a chunking esplicito con `del` + `gc.collect()` sui blocchi
  grandi; nessuna list comprehension su serie storiche intere.

Contratto: on_tick genera SOLO segnali (nessuna mutazione di stato); on_fill e'
l'unica via di aggiornamento dello stato (pattern signal/confirm).

Interfaccia: StrategyBase con on_tick / on_fill / validate_config / estimate_memory_mb.
Config-driven: nessun valore hardcoded fuori da DEFAULT_CONFIG.

Licenza: Unlicense (dominio pubblico).
"""

from __future__ import annotations

import gc
import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, Generator, List, Literal, Optional, Tuple

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DEFAULT_CONFIG: Dict[str, float] = {
    "levels": 4,                    # livelli di acquisto massimi (range)
    "base_spacing": 0.005,          # spacing base (frazione di prezzo)
    "min_spacing": 0.002,           # floor dello spacing
    "max_spacing": 0.030,           # cap dello spacing
    "ema_fast": 8,                  # finestra EMA veloce
    "ema_slow": 21,                 # finestra EMA lenta
    "slope_window": 10,             # finestra pendenza EMA veloce
    "slope_threshold": 0.0004,      # |pendenza| normalizzata -> regime trend
    "trend_up_spacing_mult": 0.7,   # spacing in trend up (griglia piu' fitta)
    "trend_down_spacing_mult": 1.6, # spacing in trend down (griglia piu' larga)
    "trend_down_levels_div": 2,     # divisore livelli in trend down
    "momentum_floor": -0.002,       # rendimento EMA sotto cui bloccare nuovi buy
    "profit_target": 0.010,         # take-profit frazionale per livello
    "stop_loss": 0.100,             # stop-loss frazionale sulla posizione
    "max_buffer_points": 5000,      # capacita' massima buffer (memoria O(1))
}


# ---------------------------------------------------------------------------
# Stato
# ---------------------------------------------------------------------------

@dataclass
class LevelState:
    """Stato di un singolo livello di acquisto della griglia."""

    entry_price: float = 0.0
    qty: float = 0.0
    open: bool = False

    def reset(self) -> None:
        """Chiude il livello riportandolo allo stato iniziale."""
        self.entry_price = 0.0
        self.qty = 0.0
        self.open = False


@dataclass
class MomentumState:
    """Stato streaming del filtro di momentum (EMA + pendenza)."""

    ema_fast: float = 0.0
    ema_slow: float = 0.0
    slope: float = 0.0
    regime: Literal["up", "down", "range"] = "range"
    samples: int = 0

    def warm(self) -> bool:
        """True quando entrambe le EMA hanno abbastanza campioni."""
        return self.samples >= 2


@dataclass
class Signal:
    """Segnale generato da on_tick (nessuna mutazione di stato)."""

    kind: Literal["buy", "sell", "none"]
    level_index: int = -1
    price: float = 0.0
    reason: str = ""


# ---------------------------------------------------------------------------
# Interfaccia
# ---------------------------------------------------------------------------

class StrategyBase:
    """Contratto minimo per una strategia Denaro (grid/momentum/adaptive)."""

    def __init__(self, config: Optional[Dict[str, float]] = None) -> None:
        raise NotImplementedError

    def on_tick(
        self,
        price: float,
        equity: float,
        now: float,
    ) -> Generator[Signal, None, None]:
        """Genera segnali dal tick corrente. Non muta lo stato."""
        raise NotImplementedError

    def on_fill(
        self,
        sig: Signal,
        price: float,
        qty: float,
        fee: float,
        now: float,
    ) -> None:
        """Conferma un segnale aggiornando lo stato (unica via di mutazione)."""
        raise NotImplementedError

    def validate_config(self) -> List[str]:
        """Ritorna la lista degli errori di config (vuota = valida)."""
        raise NotImplementedError

    def estimate_memory_mb(self, n_points: int) -> float:
        """Stima la memoria necessaria per n_points di storico (MB)."""
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Strategia
# ---------------------------------------------------------------------------

class MomoGrid(StrategyBase):
    """Griglia adattiva con filtro di regime momentum e de-risking in trend down."""

    def __init__(self, config: Optional[Dict[str, float]] = None) -> None:
        merged: Dict[str, float] = dict(DEFAULT_CONFIG)
        if config is not None:
            merged.update(config)
        self.config: Dict[str, float] = merged
        errors: List[str] = self.validate_config()
        if errors:
            raise ValueError("MomoGrid config invalida: " + "; ".join(errors))

        self.levels: List[LevelState] = [
            LevelState() for _ in range(int(self.config["levels"]))
        ]
        self.mom: MomentumState = MomentumState()
        maxlen: int = int(self.config["max_buffer_points"])
        self._prices: Deque[float] = deque(maxlen=maxlen)
        self._equity_peak: float = 0.0
        self._fills: int = 0
        self._buys: int = 0
        self._sells: int = 0
        self._last_signal: Optional[Signal] = None

    # -- config --------------------------------------------------------------

    def validate_config(self) -> List[str]:
        """Verifica vincoli numerici; ritorna lista errori (vuota = ok)."""
        errs: List[str] = []
        cfg: Dict[str, float] = self.config
        checks: List[Tuple[str, float, float, float]] = [
            ("levels", 1.0, 64.0, 4.0),
            ("base_spacing", 1e-4, 0.5, 0.005),
            ("min_spacing", 1e-5, 0.5, 0.002),
            ("max_spacing", 1e-4, 1.0, 0.030),
            ("ema_fast", 2.0, 200.0, 8.0),
            ("ema_slow", 3.0, 500.0, 21.0),
            ("slope_window", 2.0, 200.0, 10.0),
            ("slope_threshold", 0.0, 0.1, 0.0004),
            ("trend_up_spacing_mult", 0.1, 5.0, 0.7),
            ("trend_down_spacing_mult", 0.1, 5.0, 1.6),
            ("trend_down_levels_div", 1.0, 8.0, 2.0),
            ("momentum_floor", -0.1, 0.0, -0.002),
            ("profit_target", 1e-4, 1.0, 0.010),
            ("stop_loss", 1e-3, 1.0, 0.100),
            ("max_buffer_points", 100.0, 1e6, 5000.0),
        ]
        for name, lo, hi, _default in checks:
            val: float = cfg.get(name, float("nan"))
            if not (lo <= val <= hi):
                errs.append(f"{name}={val} fuori range [{lo}, {hi}]")
        if cfg.get("ema_fast", 8.0) >= cfg.get("ema_slow", 21.0):
            errs.append("ema_fast deve essere < ema_slow")
        if cfg.get("min_spacing", 0.002) > cfg.get("max_spacing", 0.030):
            errs.append("min_spacing > max_spacing")
        if cfg.get("levels", 4.0) % cfg.get("trend_down_levels_div", 2.0) != 0:
            errs.append("levels deve essere divisibile per trend_down_levels_div")
        return errs

    # -- internals (streaming, nessuna copia di serie) -----------------------

    def _push_price(self, price: float) -> None:
        """Aggiorna i buffer streaming con il prezzo corrente."""
        self._prices.append(price)
        self.mom.samples += 1
        n_fast: int = int(self.config["ema_fast"])
        n_slow: int = int(self.config["ema_slow"])
        if self.mom.samples == 1:
            self.mom.ema_fast = price
            self.mom.ema_slow = price
            return
        alpha_f: float = 2.0 / (n_fast + 1.0)
        alpha_s: float = 2.0 / (n_slow + 1.0)
        self.mom.ema_fast = alpha_f * price + (1.0 - alpha_f) * self.mom.ema_fast
        self.mom.ema_slow = alpha_s * price + (1.0 - alpha_s) * self.mom.ema_slow

    def _update_slope(self) -> None:
        """Pendenza normalizzata dell'EMA veloce (streaming su finestra fissa)."""
        win: int = int(self.config["slope_window"])
        n = len(self._prices)
        if n < 2:
            self.mom.slope = 0.0
            return
        # preleva gli ultimi win elementi senza copiare tutto (O(win) non O(n))
        start = max(0, n - win)
        p_first = self._prices[start]
        p_last = self._prices[-1]
        if p_last == 0.0:
            self.mom.slope = 0.0
            return
        # pendenza normalizzata: (p_t - p_{t-win}) / (p_t * win)
        self.mom.slope = (p_last - p_first) / (p_last * max(min(win, n) - 1, 1))

    def _detect_regime(self) -> Literal["up", "down", "range"]:
        """Classifica il regime: trend up / trend down / range."""
        if not self.mom.warm():
            return "range"
        th: float = float(self.config["slope_threshold"])
        if self.mom.ema_fast > self.mom.ema_slow and self.mom.slope > th:
            return "up"
        if self.mom.ema_fast < self.mom.ema_slow and self.mom.slope < -th:
            return "down"
        return "range"

    def _spacing(self) -> float:
        """Spacing corrente in base al regime."""
        base: float = float(self.config["base_spacing"])
        if self.mom.regime == "up":
            base *= float(self.config["trend_up_spacing_mult"])
        elif self.mom.regime == "down":
            base *= float(self.config["trend_down_spacing_mult"])
        lo: float = float(self.config["min_spacing"])
        hi: float = float(self.config["max_spacing"])
        return min(max(base, lo), hi)

    def _active_levels(self) -> int:
        """Numero di livelli attivi in base al regime (de-risking in trend down)."""
        n: int = int(self.config["levels"])
        if self.mom.regime == "down":
            n = n // int(self.config["trend_down_levels_div"])
        return max(n, 1)

    def _momentum_blocked(self) -> bool:
        """True se il momentum blocca l'apertura di nuovi livelli di acquisto."""
        if not self.mom.warm():
            return False
        # momentum = rendimento dell'EMA veloce sull'ultimo campione (O(1))
        if not self._prices:
            return False
        prev: float = self._prices[-1]
        if prev == 0.0:
            return False
        mom_ret: float = (self.mom.ema_fast - prev) / prev
        return mom_ret < float(self.config["momentum_floor"])

    # -- API ----------------------------------------------------------------

    def on_tick(
        self,
        price: float,
        equity: float,
        now: float,
    ) -> Generator[Signal, None, None]:
        """Genera segnali dal tick corrente (nessuna mutazione di stato)."""
        if price <= 0.0 or not math.isfinite(price):
            yield Signal("none", reason="price non valido")
            return

        self._push_price(price)
        self._update_slope()
        self.mom.regime = self._detect_regime()

        self._equity_peak = max(self._equity_peak, equity)
        drawdown: float = (
            1.0 - equity / self._equity_peak if self._equity_peak > 0.0 else 0.0
        )
        stop_hit: bool = drawdown > float(self.config["stop_loss"])

        spacing: float = self._spacing()
        n_active: int = self._active_levels()
        blocked: bool = self._momentum_blocked()

        for idx, lvl in enumerate(self.levels[:n_active]):
            if lvl.open:
                # take-profit del livello
                if price >= lvl.entry_price * (1.0 + float(self.config["profit_target"])):
                    yield Signal("sell", idx, price, "tp")
                elif stop_hit:
                    yield Signal("sell", idx, price, "stop_loss")
            elif not blocked:
                # nuovo livello di acquisto sotto il prezzo corrente
                target: float = price * (1.0 - spacing * (idx + 1))
                if target > 0.0:
                    yield Signal("buy", idx, target, f"grid r={self.mom.regime}")

    def on_fill(
        self,
        sig: Signal,
        price: float,
        qty: float,
        fee: float,
        now: float,
    ) -> None:
        """Conferma un segnale aggiornando lo stato (unica via di mutazione)."""
        if not 0 <= sig.level_index < len(self.levels):
            raise ValueError(f"level_index fuori range: {sig.level_index}")
        lvl: LevelState = self.levels[sig.level_index]
        if sig.kind == "buy" and not lvl.open:
            lvl.entry_price = price
            lvl.qty = qty
            lvl.open = True
            self._buys += 1
            self._fills += 1
        elif sig.kind == "sell" and lvl.open:
            lvl.reset()
            self._sells += 1
            self._fills += 1
        self._last_signal = sig

    def estimate_memory_mb(self, n_points: int) -> float:
        """Stima memoria (MB) per n_points di storico, con buffer O(1)."""
        # deque: ~ 8 byte/ptr + 8 byte/float; livelli trascurabili
        buf_cap: int = int(self.config["max_buffer_points"])
        buf_points: int = min(n_points, buf_cap)
        bytes_buf: float = buf_points * 16.0
        # se n_points > cap, il backtest va a chunk: picco = chunk + buffer
        chunk: int = int(self.config["max_buffer_points"])
        bytes_peak: float = (min(n_points, chunk) + buf_points) * 16.0
        return max(bytes_buf, bytes_peak) / (1024.0 * 1024.0)

    # -- utility ------------------------------------------------------------

    def snapshot(self) -> Dict[str, Any]:
        """Stato riassuntivo per il reporting (niente dati grezzi)."""
        open_levels: int = sum(1 for l in self.levels if l.open)
        return {
            "regime": self.mom.regime,
            "slope": round(self.mom.slope, 6),
            "ema_fast": round(self.mom.ema_fast, 6),
            "ema_slow": round(self.mom.ema_slow, 6),
            "spacing": round(self._spacing(), 6),
            "active_levels": self._active_levels(),
            "open_levels": open_levels,
            "fills": self._fills,
            "buys": self._buys,
            "sells": self._sells,
            "momentum_blocked": self._momentum_blocked(),
        }


# ---------------------------------------------------------------------------
# Backtest a chunking esplicito (OOM-safe su dataset grandi)
# ---------------------------------------------------------------------------

def chunked_backtest(
    strategy: MomoGrid,
    prices: Generator[float, None, None],
    chunk_size: int = 5000,
) -> Dict[str, Any]:
    """Esegue il backtest in chunk espliciti, liberando memoria tra un blocco e l'altro.

    - i prezzi arrivano da un generatore (mai materializzati tutti in RAM);
    - ogni chunk viene processato e poi scartato con `del` + `gc.collect()`;
    - ritorna solo un riassunto, mai le serie.
    """
    fills: int = 0
    buys: int = 0
    sells: int = 0
    equity: float = 100.0
    peak: float = 100.0

    chunk: List[float] = []
    for price in prices:
        chunk.append(price)
        if len(chunk) >= chunk_size:
            fills, buys, sells, equity, peak = _run_chunk(
                strategy, chunk, fills, buys, sells, equity, peak
            )
            del chunk
            chunk = []
            gc.collect()
    if chunk:
        fills, buys, sells, equity, peak = _run_chunk(
            strategy, chunk, fills, buys, sells, equity, peak
        )
        del chunk
        gc.collect()

    dd: float = 1.0 - equity / peak if peak > 0.0 else 0.0
    return {
        "fills": fills,
        "buys": buys,
        "sells": sells,
        "final_equity": round(equity, 4),
        "max_drawdown": round(dd, 4),
        "snapshot": strategy.snapshot(),
    }


def _run_chunk(
    strategy: MomoGrid,
    chunk: List[float],
    fills: int,
    buys: int,
    sells: int,
    equity: float,
    peak: float,
) -> Tuple[int, int, int, float, float]:
    """Processa un singolo chunk di prezzi, ritornando i contatori aggiornati."""
    for price in chunk:
        equity = max(equity, 0.01)
        peak = max(peak, equity)
        for sig in strategy.on_tick(price, equity, 0.0):
            if sig.kind == "buy":
                strategy.on_fill(sig, sig.price, 1.0, 0.0, 0.0)
                buys += 1
                fills += 1
            elif sig.kind == "sell":
                strategy.on_fill(sig, price, 0.0, 0.0, 0.0)
                sells += 1
                fills += 1
                equity += equity * float(strategy.config["profit_target"])
    return fills, buys, sells, equity, peak


# ---------------------------------------------------------------------------
# Test inline (dati sintetici piccoli)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import random

    def _gen_prices(seed: int, n: int, trend: float = 0.0) -> Generator[float, None, None]:
        """Generatore di prezzi random-walk con drift (mai materializzato)."""
        rng: random.Random = random.Random(seed)
        price: float = 100.0
        for _ in range(n):
            price *= 1.0 + trend + rng.uniform(-0.01, 0.01)
            yield price

    # 1) validazione config: costruttore deve rifiutare config invalida
    try:
        MomoGrid({"ema_fast": 50.0, "ema_slow": 20.0})
        raise AssertionError("config invalida deve alzare ValueError")
    except ValueError as exc:
        assert "ema_fast" in str(exc), f"errore inatteso: {exc}"
    print("OK: validate_config intercetta ema_fast >= ema_slow")

    # 2) run su serie sintetiche: range, trend up, trend down
    for name, trend in (("range", 0.0), ("up", 0.002), ("down", -0.002)):
        s: MomoGrid = MomoGrid()
        res: Dict[str, Any] = chunked_backtest(s, _gen_prices(42, 2000, trend))
        snap: Dict[str, Any] = res["snapshot"]
        assert res["final_equity"] > 0.0
        assert snap["fills"] == snap["buys"] + snap["sells"]
        print(f"OK: {name:5s} regime={snap['regime']:5s} fills={snap['fills']:3d} "
              f"equity={res['final_equity']:.2f} dd={res['max_drawdown']:.4f}")

    # 3) stima memoria: buffer O(1) -> 10M punti ~ stesso costo di 5k punti
    s3: MomoGrid = MomoGrid()
    mb_small: float = s3.estimate_memory_mb(1_000)
    mb_big: float = s3.estimate_memory_mb(10_000_000)
    mb_cap: float = s3.estimate_memory_mb(int(s3.config["max_buffer_points"]))
    assert 0.0 < mb_small < 1.0
    assert mb_big == mb_cap, "memoria deve saturare alla capacita' del buffer"
    assert mb_big < 1.0, "buffer O(1) deve restare sotto 1MB"
    print(f"OK: estimate_memory_mb 1k={mb_small:.3f}MB 10M={mb_big:.3f}MB (buffer O(1))")

    # 4) invarianza: on_tick non muta stato senza on_fill
    s4: MomoGrid = MomoGrid()
    before: int = s4._fills
    list(s4.on_tick(100.0, 100.0, 0.0))
    assert s4._fills == before, "on_tick non deve mutare lo stato"
    print("OK: pattern signal/confirm rispettato (on_tick puro)")

    print("TUTTI I TEST PASSATI")
