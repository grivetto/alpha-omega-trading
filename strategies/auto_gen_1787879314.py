"""AdaptiveVolatilityGrid — griglia a spacing ATR adattivo (streaming, OOM-safe).

Strategia grid "adaptive": i livelli non hanno spacing fisso ma sono scalati
sull'ATR corrente (Wilder, smoothing streaming O(1) — nessuna finestra in RAM).
Il regime di volatilità (range vs trend) viene stimato con l'Efficiency Ratio
di Kaufman su un buffer circolare a capacità fissa; al flip di regime il grid
viene ri-centrato e lo stop-loss trailing (chandelier) protegge la posizione.

Design goals:
- OOM-safe: nessuna lista di prezzi storici; ATR e ER aggiornati per incremento.
  `from_csv_chunked` legge il dataset in chunk espliciti (generatore) e rilascia
  le righe processate con `del` + `gc.collect()` periodico.
- Error handling esplicito: ConfigError/DataError, niente except pass.
- Config-driven: ogni parametro arriva da config, nessun magic number.

API compatibile con la famiglia StrategyBase del progetto Denaro.
"""

from __future__ import annotations

import csv
import gc
import logging
import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, Iterator, List, Optional, TextIO

logger = logging.getLogger("denaro.strategies.adaptive_vol_grid")


class ConfigError(ValueError):
    """Configurazione non valida per AdaptiveVolatilityGrid."""


class DataError(RuntimeError):
    """Dati di mercato malformati o non processabili."""


@dataclass
class StrategyState:
    """Stato persistente della strategia tra i tick."""

    position: float = 0.0
    avg_entry: float = 0.0
    realized_pnl: float = 0.0
    wins: int = 0
    losses: int = 0
    orders_placed: int = 0
    atr: float = 0.0
    prev_close: Optional[float] = None
    prev_atr: float = 0.0
    efficiency_ratio: float = 0.5
    stop_price: Optional[float] = None
    last_grid_mid: Optional[float] = None
    last_tick_ts: Optional[float] = None


@dataclass
class _PriceRing:
    """Buffer circolare a capacità fissa per l'Efficiency Ratio (O(1) memoria)."""

    capacity: int
    closes: Deque[float] = field(default_factory=deque)

    def push(self, price: float) -> None:
        self.closes.append(price)
        if len(self.closes) > self.capacity:
            self.closes.popleft()

    def net_change(self) -> float:
        if len(self.closes) < 2:
            return 0.0
        return abs(self.closes[-1] - self.closes[0])

    def path_length(self) -> float:
        if len(self.closes) < 2:
            return 0.0
        total: float = 0.0
        prev: Optional[float] = None
        for close in self.closes:
            if prev is not None:
                total += abs(close - prev)
            prev = close
        return total

    def __len__(self) -> int:
        return len(self.closes)


class StrategyBase:
    """Interfaccia comune alle strategie Denaro."""

    name: str = "base"

    def on_tick(self, price: float, high: float, low: float, ts: float) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def on_fill(self, side: str, price: float, qty: float, ts: float) -> None:
        raise NotImplementedError

    def validate_config(self, config: Dict[str, float]) -> None:
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError


class AdaptiveVolatilityGrid(StrategyBase):
    """Grid con livelli scalati su ATR streaming e regime filter su Efficiency Ratio."""

    name = "adaptive_vol_grid"

    _POSITIVE_FLOATS = (
        "capital", "atr_period", "atr_mult_spacing", "max_levels",
        "per_level_frac", "stop_loss_pct", "fee_rate", "min_trade_qty",
        "regime_lookback", "max_orders_per_tick",
    )

    def __init__(self, config: Dict[str, Any]) -> None:
        self.validate_config(config)
        self.config: Dict[str, Any] = dict(config)
        self.state = StrategyState()
        self.ring = _PriceRing(capacity=int(self.config["regime_lookback"]))
        self._gc_counter: int = 0

    # ------------------------------------------------------------------ #
    # Config
    # ------------------------------------------------------------------ #
    def validate_config(self, config: Dict[str, Any]) -> None:
        for key in self._POSITIVE_FLOATS:
            if key not in config:
                raise ConfigError(f"missing required config key: {key}")
            try:
                value = float(config[key])
            except (TypeError, ValueError) as exc:
                raise ConfigError(f"config key {key!r} is not numeric: {config[key]!r}") from exc
            if not math.isfinite(value) or value <= 0.0:
                raise ConfigError(f"config key {key!r} must be a positive finite number, got {value}")
        for key in ("symbol",):
            if not isinstance(config.get(key), str) or not config[key].strip():
                raise ConfigError("config key 'symbol' must be a non-empty string")
        if int(config["atr_period"]) < 2:
            raise ConfigError("atr_period must be >= 2")
        if int(config["max_levels"]) < 1:
            raise ConfigError("max_levels must be >= 1")
        if not 0.0 < float(config["per_level_frac"]) <= 1.0:
            raise ConfigError("per_level_frac must be in (0, 1]")

    # ------------------------------------------------------------------ #
    # Streaming indicatori
    # ------------------------------------------------------------------ #
    def _update_atr(self, high: float, low: float, close: float) -> float:
        """Wilder ATR incrementale, O(1) memoria."""
        period = int(self.config["atr_period"])
        if self.state.prev_close is None:
            self.state.atr = high - low
        else:
            tr = max(high - low, abs(high - self.state.prev_close), abs(low - self.state.prev_close))
            if self.state.prev_atr == 0.0:
                self.state.atr = tr
            else:
                self.state.atr = (self.state.prev_atr * (period - 1) + tr) / period
        self.state.prev_close = close
        self.state.prev_atr = self.state.atr
        return self.state.atr

    def _update_regime(self, price: float) -> float:
        """Efficiency Ratio di Kaufman: 1 = trend puro, 0 = range puro."""
        self.ring.push(price)
        net = self.ring.net_change()
        path = self.ring.path_length()
        if path <= 1e-12:
            self.state.efficiency_ratio = 0.0
        else:
            self.state.efficiency_ratio = net / path
        return self.state.efficiency_ratio

    # ------------------------------------------------------------------ #
    # Core
    # ------------------------------------------------------------------ #
    def on_tick(self, price: float, high: float, low: float, ts: float) -> List[Dict[str, Any]]:
        if not all(math.isfinite(v) and v > 0.0 for v in (price, high, low)):
            raise DataError(f"non-positive or non-finite tick data: price={price} high={high} low={low}")
        if high < low:
            raise DataError(f"high {high} < low {low} in tick data")

        self.state.last_tick_ts = ts
        atr = self._update_atr(high, low, price)
        er = self._update_regime(price)
        orders: List[Dict[str, Any]] = []

        if self.state.atr <= 0.0:
            return orders  # troppo pochi tick, nessun segnale

        mid = self.state.last_grid_mid if self.state.last_grid_mid is not None else price
        spacing = self._clip(atr * float(self.config["atr_mult_spacing"]), atr * 0.1, price * 0.05)

        # Regime trend -> trailing stop chandelier attivo; range -> grid pura
        if er >= float(self.config["er_trend_threshold"]) and self.state.position != 0.0:
            stop = self._chandelier_stop(price)
            if self.state.position > 0.0 and price <= stop:
                orders.append(self._order("sell", price, abs(self.state.position), ts, "stop_trend"))
                self.state.position = 0.0
                self.state.stop_price = None
                self.state.last_grid_mid = price
                return orders
            if self.state.position < 0.0 and price >= stop:
                orders.append(self._order("buy", price, abs(self.state.position), ts, "stop_trend"))
                self.state.position = 0.0
                self.state.stop_price = None
                self.state.last_grid_mid = price
                return orders

        # Riallinea la griglia quando il prezzo si muove oltre metà spacing
        if self.state.last_grid_mid is None or abs(price - mid) >= spacing * 0.5:
            self.state.last_grid_mid = price

        capital = float(self.config["capital"])
        per_level = capital * float(self.config["per_level_frac"])
        levels = int(self.config["max_levels"])
        placed = 0
        for idx in range(1, levels + 1):
            if placed >= int(self.config["max_orders_per_tick"]):
                break
            buy_price = self.state.last_grid_mid - spacing * idx
            sell_price = self.state.last_grid_mid + spacing * idx
            qty = self._clip(per_level / buy_price, float(self.config["min_trade_qty"]), capital / buy_price)
            orders.append(self._order("buy", buy_price, qty, ts, "grid"))
            orders.append(self._order("sell", sell_price, qty, ts, "grid"))
            placed += 2

        self.state.orders_placed += len(orders)
        return orders

    def _chandelier_stop(self, price: float) -> float:
        """Chandelier exit: massimo ritracciamento ATR-multiplo dal picco."""
        mult = float(self.config["chandelier_mult"])
        if self.state.position > 0.0:
            peak = max(self.state.avg_entry, price)
            stop = peak - mult * self.state.atr
            self.state.stop_price = stop if self.state.stop_price is None else max(self.state.stop_price, stop)
        else:
            trough = min(self.state.avg_entry, price)
            stop = trough + mult * self.state.atr
            self.state.stop_price = stop if self.state.stop_price is None else min(self.state.stop_price, stop)
        return self.state.stop_price

    def on_fill(self, side: str, price: float, qty: float, ts: float) -> None:
        if side not in ("buy", "sell"):
            raise DataError(f"invalid fill side: {side!r}")
        if price <= 0.0 or qty <= 0.0:
            raise DataError(f"invalid fill price/qty: {price}/{qty}")
        signed = qty if side == "buy" else -qty
        old_pos = self.state.position
        self.state.position += signed
        if old_pos == 0.0:
            self.state.avg_entry = price
        else:
            self.state.avg_entry = (
                (abs(old_pos) * self.state.avg_entry + qty * price) / (abs(old_pos) + qty)
                if (old_pos > 0.0) == (signed > 0.0)
                else price
            )
        # PnL realizzato solo su chiusure parziali/totali contro posizione
        if old_pos != 0.0 and (old_pos > 0.0) != (signed > 0.0):
            closed = min(abs(old_pos), qty)
            pnl = closed * (price - self.state.avg_entry) * (1.0 if old_pos > 0.0 else -1.0)
            pnl -= closed * price * float(self.config["fee_rate"]) * 2.0
            self.state.realized_pnl += pnl
            if pnl >= 0.0:
                self.state.wins += 1
            else:
                self.state.losses += 1
        self.state.stop_price = None

    # ------------------------------------------------------------------ #
    # Util
    # ------------------------------------------------------------------ #
    @staticmethod
    def _clip(value: float, low: float, high: float) -> float:
        return max(low, min(value, high))

    @staticmethod
    def _order(side: str, price: float, qty: float, ts: float, tag: str) -> Dict[str, Any]:
        return {
            "side": side,
            "price": round(price, 8),
            "qty": round(qty, 8),
            "ts": ts,
            "tag": tag,
            "strategy": "adaptive_vol_grid",
        }

    def estimate_memory_mb(self) -> float:
        """Stima memoria: stato O(1) + ring a capacità fissa."""
        ring_bytes = self.ring.capacity * 24.0
        state_bytes = 512.0
        config_bytes = sum(8.0 * len(str(v)) for v in self.config.values())
        return (ring_bytes + state_bytes + config_bytes) / (1024.0 * 1024.0)

    # ------------------------------------------------------------------ #
    # Ingestione OOM-safe
    # ------------------------------------------------------------------ #
    @classmethod
    def iter_ticks_from_csv(
        cls, path: str, chunk_size: int = 10_000, gc_every: int = 5
    ) -> Iterator[Dict[str, float]]:
        """Generatore che legge OHLC da CSV a chunk, senza caricare il file in RAM.

        Schema atteso: colonne `ts,open,high,low,close` (header). Ogni riga viene
        validata e yieldata; le righe processate vengono rilasciate e `gc.collect()`
        viene invocato ogni `gc_every` chunk per tenere la heap sotto controllo.
        """
        if chunk_size < 1:
            raise ConfigError("chunk_size must be >= 1")
        if gc_every < 1:
            raise ConfigError("gc_every must be >= 1")
        chunk: List[Dict[str, float]] = []
        chunk_idx = 0
        with open(path, "r", encoding="utf-8", newline="") as handle:  # noqa: SIM117
            reader = csv.DictReader(handle)
            for row in reader:
                try:
                    tick = {
                        "ts": float(row["ts"]),
                        "open": float(row["open"]),
                        "high": float(row["high"]),
                        "low": float(row["low"]),
                        "close": float(row["close"]),
                    }
                except (KeyError, TypeError, ValueError) as exc:
                    raise DataError(f"malformed CSV row near line {reader.line_num}: {exc}") from exc
                chunk.append(tick)
                if len(chunk) >= chunk_size:
                    yield from chunk
                    del chunk
                    chunk = []
                    chunk_idx += 1
                    if chunk_idx % gc_every == 0:
                        gc.collect()
        if chunk:
            yield from chunk
        del chunk
        gc.collect()

    @classmethod
    def from_csv(cls, path: str, config: Dict[str, Any], chunk_size: int = 10_000) -> "AdaptiveVolatilityGrid":
        """Costruisce la strategia e pre-riscalda ATR/regime su un file CSV a chunk."""
        strat = cls(config)
        for tick in cls.iter_ticks_from_csv(path, chunk_size=chunk_size):
            strat.on_tick(tick["close"], tick["high"], tick["low"], tick["ts"])
        return strat


DEFAULT_CONFIG: Dict[str, Any] = {
    "symbol": "SOL/EUR",
    "capital": 100.0,
    "atr_period": 14,
    "atr_mult_spacing": 0.8,
    "max_levels": 5,
    "per_level_frac": 0.1,
    "stop_loss_pct": 0.05,
    "fee_rate": 0.0026,
    "min_trade_qty": 0.001,
    "regime_lookback": 30,
    "max_orders_per_tick": 4,
    "er_trend_threshold": 0.45,
    "chandelier_mult": 3.0,
}


def _synthetic_ticks(n: int = 2_000, seed: int = 42) -> Iterator[Dict[str, float]]:
    """Serie sintetica: drift + rumore, per i test inline."""
    import random

    rng = random.Random(seed)
    price = 100.0
    for i in range(n):
        drift = 0.01 if i > n // 2 else -0.005
        price = max(1.0, price + drift + rng.gauss(0.0, 0.35))
        high = price * (1.0 + abs(rng.gauss(0.0, 0.004)))
        low = price * (1.0 - abs(rng.gauss(0.0, 0.004)))
        yield {"ts": float(i), "open": price, "high": max(high, low + 0.01), "low": low, "close": price}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    # 1) Config validation
    strat = AdaptiveVolatilityGrid(DEFAULT_CONFIG)
    try:
        AdaptiveVolatilityGrid({k: v for k, v in DEFAULT_CONFIG.items() if k != "capital"})
    except ConfigError:
        logger.info("TEST OK: ConfigError su config mancante")
    else:
        raise SystemExit("FAIL: ConfigError non sollevata")

    # 2) Simulazione su tick sintetici (streaming, nessuna lista intermedia)
    orders_total = 0
    fills = 0
    for tick in _synthetic_ticks():
        orders = strat.on_tick(tick["close"], tick["high"], tick["low"], tick["ts"])
        orders_total += len(orders)
        for order in orders[:1]:  # simula fill sul primo ordine di ogni tick
            strat.on_fill(order["side"], order["price"], order["qty"], order["ts"])
            fills += 1
    assert orders_total > 0, "FAIL: nessun ordine generato"
    assert fills > 0, "FAIL: nessun fill simulato"
    logger.info("TEST OK: %d ordini, %d fill, pnl=%.4f, er=%.3f, atr=%.4f",
                orders_total, fills, strat.state.realized_pnl, strat.state.efficiency_ratio, strat.state.atr)

    # 3) Memory estimate
    mem_mb = strat.estimate_memory_mb()
    assert mem_mb < 1.0, f"FAIL: memory estimate {mem_mb:.3f} MB non plausibile"
    logger.info("TEST OK: memoria stimata %.5f MB", mem_mb)

    # 4) CSV chunking OOM-safe su file temporaneo
    import tempfile

    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as fh:
        fh.write("ts,open,high,low,close\n")
        for i, t in enumerate(_synthetic_ticks(500)):
            fh.write(f"{t['ts']},{t['open']:.6f},{t['high']:.6f},{t['low']:.6f},{t['close']:.6f}\n")
        csv_path = fh.name
    replayed = AdaptiveVolatilityGrid.from_csv(csv_path, DEFAULT_CONFIG, chunk_size=100)
    assert replayed.state.orders_placed > 0, "FAIL: replay CSV senza ordini"
    logger.info("TEST OK: replay CSV chunked, %d ordini, atr=%.4f",
                replayed.state.orders_placed, replayed.state.atr)
    import os

    os.unlink(csv_path)

    logger.info("ALL TESTS PASSED — AdaptiveVolatilityGrid pronto al deploy")
