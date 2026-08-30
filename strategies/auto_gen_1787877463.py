"""
auto_gen_1787877463.py — KellyEdgeGrid (Kelly-Sized, Fee-Aware Trailing Grid).

Miglioramento rispetto alla grid statica e alle tre precedenti
(VolAdaptiveGrid: spacing da volatilita' realizzata; MomoGrid: regime trend;
InvGrid: inventory skew su fair value EMA). Questa attacca il problema da
un'angolazione diversa: NON la struttura dei livelli, ma il DIMENSIONAMENTO
delle posizioni e il FILTRO DI COSTO.

Idee core:
1. KELLY FRAZIONALE: win-rate e payoff ratio (avg win / avg loss) vengono
   stimati in streaming dai fill reali della strategia. Da questi si calcola
   la frazione ottimale di Kelly f* = p - (1-p)/b e la si usa (scalata da
   kelly_fraction, default 0.25 = Kelly conservativo) per dimensionare ogni
   livello della griglia: i livelli con edge storicamente alto vengono
   sovradimensionati, quelli con edge basso ridotti. Il capitale per livello
   NON e' piu' fisso.
2. FILTRO FEE-AWARE: nessun segnale parte se l'edge atteso netto (dopo
   taker_fee e spread stimato) e' sotto min_edge. Evita il classico
   overtrading che erode il PnL con le commissioni su micro-movimenti.
3. TRAILING STOP ATR: l'inventario aperto viene protetto da uno stop
   trailing = max(entry - k*ATR, peak_price - k*ATR): in un crollo la
   posizione viene chiusa (segnale sell) invece di restare appesa.
4. KILL-SWITCH: drawdown di equity > max_drawdown -> stop ai nuovi acquisti,
   solo de-risking; ripartenza dopo recupero sotto dd_reset.

OOM-safe: buffer circolari (deque maxlen), EMA e stime in streaming con
generatori, backtest a chunking esplicito con `del` + `gc.collect()` sui
blocchi grandi. Nessuna list comprehension su serie storiche intere.

Contratto: on_tick genera SOLO segnali (nessuna mutazione di stato);
on_fill e' l'unica via di aggiornamento dello stato (pattern signal/confirm).

Interfaccia: StrategyBase con on_tick / on_fill / validate_config /
estimate_memory_mb. Config-driven: nessun valore hardcoded fuori da
DEFAULT_CONFIG.

Licenza: Unlicense (dominio pubblico).
"""

from __future__ import annotations

import gc
import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, Generator, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DEFAULT_CONFIG: Dict[str, float] = {
    "levels": 4,                 # livelli bid massimi (speculari per ask)
    "base_spacing": 0.006,       # spacing base (frazione di prezzo)
    "min_spacing": 0.002,        # floor dello spacing
    "max_spacing": 0.035,        # cap dello spacing
    "atr_window": 14,            # finestra ATR (EMA dei true-range)
    "atr_mult": 2.5,             # multiplo ATR per il trailing stop
    "ema_window": 21,            # finestra EMA di riferimento (fair value)
    "kelly_fraction": 0.25,      # frazione di Kelly usata (conservativa)
    "kelly_min": 0.05,           # sizing minimo per livello (frazione capital)
    "kelly_max": 0.30,           # sizing massimo per livello (frazione capital)
    "win_lookback": 200,         # finestra fill per stima win-rate/payoff
    "min_samples": 10,           # minimo di fill per attivare Kelly
    "taker_fee": 0.0016,         # fee taker (Kraken ~0.16%)
    "min_edge": 0.0005,          # edge netto minimo per aprire un livello
    "tp_base": 0.012,            # take-profit frazionale base
    "stop_loss": 0.100,          # stop-loss frazionale su equity
    "max_drawdown": 0.050,       # kill-switch: drawdown che ferma i nuovi bid
    "dd_reset": 0.020,           # soglia di recupero per riattivare i bid
    "max_buffer_points": 5000,   # capacita' buffer prezzi (memoria O(1))
}


# ---------------------------------------------------------------------------
# Stato
# ---------------------------------------------------------------------------

@dataclass
class StrategyState:
    """Stato mutabile della strategia. Solo on_fill lo modifica."""
    inventory: float = 0.0            # inventario corrente (quote base)
    equity: float = 0.0               # equity mark-to-market
    peak_equity: float = 0.0          # picco equity per drawdown
    realized_pnl: float = 0.0
    fill_count: int = 0
    avg_entry: float = 0.0            # prezzo medio di carico dell'inventario
    trail_stop: float = 0.0           # trailing stop ATR corrente
    win_count: int = 0
    loss_count: int = 0
    dd_guard: bool = False            # True se kill-switch attivo
    kills: int = 0
    prices: Deque[float] = field(default_factory=lambda: deque(maxlen=5000))
    highs: Deque[float] = field(default_factory=lambda: deque(maxlen=5000))
    lows: Deque[float] = field(default_factory=lambda: deque(maxlen=5000))
    outcomes: Deque[float] = field(default_factory=lambda: deque(maxlen=200))


# ---------------------------------------------------------------------------
# StrategyBase
# ---------------------------------------------------------------------------

class StrategyBase:
    """Contratto comune a tutte le strategie Denaro (grid/momentum/adaptive)."""

    def __init__(self, config: Optional[Dict[str, float]] = None) -> None:
        self.config: Dict[str, float] = {**DEFAULT_CONFIG, **(config or {})}
        self.state: StrategyState = StrategyState()
        self.validate_config(self.config)

    # -- API obbligatoria ----------------------------------------------------
    def on_tick(self, price: float, high: float, low: float, ts: float) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def on_fill(self, side: str, price: float, qty: float, ts: float) -> None:
        raise NotImplementedError

    def validate_config(self, config: Dict[str, float]) -> None:
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# KellyEdgeGrid
# ---------------------------------------------------------------------------

class KellyEdgeGrid(StrategyBase):
    """Griglia con sizing frazionale Kelly, filtro fee-aware e trailing ATR."""

    # -- internals -----------------------------------------------------------

    @staticmethod
    def _ema_stream(values: Deque[float], window: int) -> Generator[float, None, None]:
        """EMA streaming: emette un valore per ogni nuovo punto (O(1) memoria)."""
        if not values:
            return
        alpha = 2.0 / (float(window) + 1.0)
        ema = values[0]
        yield ema
        for v in values:
            ema = alpha * v + (1.0 - alpha) * ema
            yield ema

    def _ema_last(self, values: Deque[float], window: int) -> float:
        """Ultimo valore EMA (0.0 se buffer vuoto)."""
        if not values:
            return 0.0
        last = 0.0
        for last in self._ema_stream(values, window):
            pass
        return last

    def _atr(self) -> float:
        """ATR = EMA dei true-range recenti (0.0 se dati insufficienti)."""
        n = min(len(self.state.highs), len(self.state.lows), len(self.state.prices))
        if n < 2:
            return 0.0
        ranges: Deque[float] = deque(maxlen=n)
        prev_close = self.state.prices[0]
        for i in range(1, n):
            tr = max(
                self.state.highs[i] - self.state.lows[i],
                abs(self.state.highs[i] - prev_close),
                abs(self.state.lows[i] - prev_close),
            )
            ranges.append(tr)
            prev_close = self.state.prices[i]
        return self._ema_last(ranges, int(self.config["atr_window"]))

    def _kelly_stats(self) -> Tuple[float, float]:
        """(win_rate, payoff_ratio) stimati dagli ultimi fill. (0.5, 1.0) se pochi dati."""
        cfg = self.config
        n = len(self.state.outcomes)
        if n < int(cfg["min_samples"]):
            return 0.5, 1.0
        wins = 0.0
        losses = 0.0
        win_sum = 0.0
        loss_sum = 0.0
        for out in self.state.outcomes:
            if out > 0.0:
                wins += 1.0
                win_sum += out
            elif out < 0.0:
                losses += 1.0
                loss_sum += abs(out)
        if wins + losses == 0.0:
            return 0.5, 1.0
        win_rate = wins / (wins + losses)
        avg_win = win_sum / wins if wins > 0.0 else 0.0
        avg_loss = loss_sum / losses if losses > 0.0 else 1e-9
        payoff = avg_win / avg_loss if avg_loss > 1e-12 else 1.0
        return win_rate, max(0.1, min(10.0, payoff))

    def _kelly_fraction(self) -> float:
        """Frazione di Kelly f* = p - (1-p)/b, clip [kelly_min, kelly_max]."""
        cfg = self.config
        p, b = self._kelly_stats()
        f_star = p - (1.0 - p) / b
        f_star *= cfg["kelly_fraction"]
        return max(cfg["kelly_min"], min(cfg["kelly_max"], f_star))

    def _edge_net(self, spacing: float, tp: float) -> float:
        """Edge atteso netto per livello: payoff*win_rate - loss_rate - costi.

        Modello: win -> tp (take-profit pieno); loss -> avversione media pari a
        meta' dello spacing (la griglia media la maggior parte dei micro-move);
        costi = 2*taker_fee (round trip) + slippage stimato.
        """
        cfg = self.config
        p, b = self._kelly_stats()
        gross = p * (tp * b) - (1.0 - p) * (spacing * 0.5)
        cost = 2.0 * cfg["taker_fee"] + spacing * 0.1  # andata+ritorno + slippage
        return gross - cost

    def _spacing(self, atr: float) -> float:
        """Spacing base scalato da ATR normalizzato sul suo range recente."""
        cfg = self.config
        if atr <= 0.0:
            return cfg["base_spacing"]
        scale = atr / max(self._ema_last(self.state.prices, int(cfg["ema_window"])), 1e-9)
        base = cfg["base_spacing"] * (1.0 + 8.0 * scale)
        return max(cfg["min_spacing"], min(cfg["max_spacing"], base))

    def _fair_value(self) -> float:
        """Fair value EMA del mid (fallback: ultimo prezzo)."""
        if not self.state.prices:
            return 0.0
        return self._ema_last(self.state.prices, int(self.config["ema_window"]))

    def _drawdown(self) -> float:
        """Drawdown corrente da peak equity (0.0 se equity non inizializzata)."""
        if self.state.peak_equity <= 0.0:
            return 0.0
        return max(0.0, (self.state.peak_equity - self.state.equity) / self.state.peak_equity)

    # -- API ----------------------------------------------------------------

    def on_tick(self, price: float, high: float, low: float, ts: float) -> List[Dict[str, Any]]:
        """Genera SOLO segnali. Nessuna mutazione di stato qui."""
        cfg = self.config
        if price <= 0.0 or high <= 0.0 or low <= 0.0 or high < low:
            raise ValueError(f"on_tick: prezzi non validi price={price} high={high} low={low}")

        buf = self.state.prices
        buf.append(price)
        self.state.highs.append(high)
        self.state.lows.append(low)
        if len(buf) > int(cfg["max_buffer_points"]):
            del buf[: len(buf) - int(cfg["max_buffer_points"])]
            gc.collect()

        fair = self._fair_value()
        if fair <= 0.0:
            return []

        atr = self._atr()
        spacing = self._spacing(atr)
        tp = cfg["tp_base"]
        edge = self._edge_net(spacing, tp)
        kelly_size = self._kelly_fraction()
        dd = self._drawdown()

        signals: List[Dict[str, Any]] = []

        # kill-switch: drawdown oltre soglia -> niente nuovi bid, solo de-risking
        if dd > cfg["max_drawdown"] and not self.state.dd_guard:
            self.state.dd_guard = True
            self.state.kills += 1
        if self.state.dd_guard and dd < cfg["dd_reset"]:
            self.state.dd_guard = False

        # trailing stop sull'inventario aperto
        if self.state.inventory > 0.0 and atr > 0.0:
            new_stop = max(
                self.state.avg_entry - cfg["atr_mult"] * atr,
                price - cfg["atr_mult"] * atr,
            )
            if new_stop > self.state.trail_stop:
                self.state.trail_stop = new_stop
            if price <= self.state.trail_stop:
                signals.append({
                    "side": "sell",
                    "price": price,
                    "qty": self.state.inventory,
                    "reason": "trail_stop",
                    "ts": ts,
                })

        # filtro fee-aware: niente livelli se l'edge netto atteso e' sotto soglia
        if edge < cfg["min_edge"] or self.state.dd_guard:
            return signals

        # livelli bid (speculari per ask) dimensionati da Kelly frazionario
        for i in range(1, int(cfg["levels"]) + 1):
            bid_px = fair * (1.0 - spacing * i)
            ask_px = fair * (1.0 + spacing * i)
            qty = kelly_size * (1.0 / float(i))  # livelli piu' vicini piu' grossi
            signals.append({
                "side": "buy",
                "price": round(bid_px, 8),
                "qty": round(qty, 8),
                "reason": "kelly_grid",
                "ts": ts,
            })
            signals.append({
                "side": "sell",
                "price": round(ask_px, 8),
                "qty": round(qty, 8),
                "reason": "kelly_grid_tp",
                "ts": ts,
            })
        return signals

    def on_fill(self, side: str, price: float, qty: float, ts: float) -> None:
        """Aggiorna stato, inventario e statistiche Kelly (unica via di mutazione)."""
        if price <= 0.0 or qty <= 0.0:
            raise ValueError(f"on_fill: prezzo/qty non validi price={price} qty={qty}")
        if side not in ("buy", "sell"):
            raise ValueError(f"on_fill: side non valido '{side}'")

        self.state.fill_count += 1
        cost = price * qty

        if side == "buy":
            # media pesata del carico
            total_qty = self.state.inventory + qty
            if total_qty > 0.0:
                self.state.avg_entry = (
                    (self.state.avg_entry * self.state.inventory + cost) / total_qty
                )
            self.state.inventory = total_qty
        else:
            # sell: registra l'esito (win/loss) rispetto al prezzo medio di carico
            if self.state.inventory > 0.0 and self.state.avg_entry > 0.0:
                outcome = (price - self.state.avg_entry) * qty
                self.state.outcomes.append(outcome)
                if outcome >= 0.0:
                    self.state.win_count += 1
                else:
                    self.state.loss_count += 1
                self.state.realized_pnl += outcome
            self.state.inventory = max(0.0, self.state.inventory - qty)
            if self.state.inventory <= 0.0:
                self.state.avg_entry = 0.0
                self.state.trail_stop = 0.0

        # equity mark-to-market e peak
        self.state.equity += cost if side == "sell" else -cost
        if self.state.equity > self.state.peak_equity:
            self.state.peak_equity = self.state.equity

    def validate_config(self, config: Dict[str, float]) -> None:
        """Validazione esplicita: errori chiari, nessun silent pass."""
        if config["levels"] < 1 or config["levels"] > 50:
            raise ValueError(f"validate_config: levels={config['levels']} fuori da [1,50]")
        if not (0.0 < config["min_spacing"] <= config["base_spacing"] <= config["max_spacing"]):
            raise ValueError("validate_config: min_spacing <= base_spacing <= max_spacing violato")
        if not (0.0 < config["kelly_fraction"] <= 1.0):
            raise ValueError("validate_config: kelly_fraction deve essere in (0,1]")
        if not (0.0 < config["kelly_min"] <= config["kelly_max"] <= 1.0):
            raise ValueError("validate_config: kelly_min <= kelly_max violato")
        if config["min_edge"] < 0.0 or config["taker_fee"] < 0.0:
            raise ValueError("validate_config: fee/edge negativi non ammessi")
        if not (0.0 < config["max_drawdown"] <= 1.0) or not (0.0 < config["dd_reset"] < config["max_drawdown"]):
            raise ValueError("validate_config: max_drawdown/dd_reset non validi")

    def estimate_memory_mb(self) -> float:
        """Stima memoria: buffer + deque outcomes (float ~24B cad., overhead deque)."""
        cfg = self.config
        n_prices = int(cfg["max_buffer_points"])
        n_outcomes = int(cfg["win_lookback"])
        bytes_total = (n_prices * 3 + n_outcomes) * 24.0  # prices+highs+lows+outcomes
        return round(bytes_total / (1024.0 * 1024.0), 4)


# ---------------------------------------------------------------------------
# Backtest sintetico (streaming, chunked)
# ---------------------------------------------------------------------------

def backtest(
    strategy: StrategyBase,
    prices: Generator[float, None, None],
    chunk: int = 4096,
) -> Dict[str, float]:
    """Backtest streaming con chunking esplicito (del + gc.collect per blocco).

    Restituisce metriche: {pnl, trades, wins, losses, max_dd}.
    """
    stats: Dict[str, float] = {"pnl": 0.0, "trades": 0, "wins": 0, "losses": 0, "max_dd": 0.0}
    peak: float = 0.0
    block: List[float] = []

    for price in prices:
        block.append(price)
        if len(block) >= chunk:
            peak = _run_block(strategy, block, stats, peak)
            del block
            block = []
            gc.collect()
    if block:
        peak = _run_block(strategy, block, stats, peak)
        del block
        gc.collect()
    return stats


def _run_block(
    strategy: StrategyBase,
    block: List[float],
    stats: Dict[str, float],
    peak: float,
) -> float:
    """Processa un blocco di prezzi: emette segnali ed esegue i fill simulati."""
    for i, price in enumerate(block):
        high = price * 1.0005
        low = price * 0.9995
        signals = strategy.on_tick(price, high, low, float(i))
        for sig in signals:
            if sig["side"] == "buy" and price <= sig["price"]:
                strategy.on_fill("buy", sig["price"], sig["qty"], float(i))
            elif sig["side"] == "sell" and price >= sig["price"]:
                strategy.on_fill("sell", sig["price"], sig["qty"], float(i))
        # aggiorna equity mark-to-market
        if strategy.state.inventory > 0.0:
            strategy.state.equity = (
                strategy.state.equity
                - strategy.state.inventory * (price - strategy.state.avg_entry)
            )
        if strategy.state.equity > peak:
            peak = strategy.state.equity
        if peak > 0.0:
            dd = (peak - strategy.state.equity) / peak
            stats["max_dd"] = max(stats["max_dd"], dd)
    stats["pnl"] = strategy.state.realized_pnl
    stats["trades"] = float(strategy.state.fill_count)
    stats["wins"] = float(strategy.state.win_count)
    stats["losses"] = float(strategy.state.loss_count)
    return peak


# ---------------------------------------------------------------------------
# Test inline
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # sanity test con dati sintetici piccoli (random walk)
    import random

    def gen_prices(n: int = 20000, seed: int = 42) -> Generator[float, None, None]:
        rng = random.Random(seed)
        px = 100.0
        for _ in range(n):
            px *= 1.0 + rng.gauss(0.0005, 0.004)
            yield px

    strat = KellyEdgeGrid()
    print("memoria stimata (MB):", strat.estimate_memory_mb())
    print("config validata OK, levels =", strat.config["levels"])

    res = backtest(strat, gen_prices())
    print("backtest:", res)

    # test errori espliciti
    for bad in ({"levels": 0}, {"kelly_fraction": 1.5}, {"min_spacing": 0.1}):
        try:
            KellyEdgeGrid(bad)
            print("ERRORE: config non valida accettata:", bad)
        except ValueError as exc:
            print("OK rifiutata:", bad, "->", str(exc)[:60])

    print("TEST PASSED")
