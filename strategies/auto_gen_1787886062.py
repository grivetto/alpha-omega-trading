"""ChandelierTrendRider — trend-following con chandelier exit ATR e filtro di regime (streaming, OOM-safe).

Strategia trend complementare a grid/momentum/MM della fleet: invece di fare mean
reversion (grid) o breakout (Donchian) o quoting continuo (A-S), segue la direzione
del trend con EMA fast/slow e protegge il profitto con un *chandelier exit* (trailing
stop = extreme price since entry -/+ ATR * mult). L'ingresso avviene solo a regime
confermato (pendenza EMA > 0 + vol ratio nel range operativo), la size deriva dal
rischio (risk_pct * equity / stop_distance) con cap di esposizione, e un kill-switch
su drawdown mette il sistema flat. Fee-aware: stop troppo stretto rispetto alle fee
=> niente trade (evita il bleed da fee in mercato morto).

Design goals:
- OOM-safe: EMA e ATR (Wilder) incrementali O(1) per tick, nessuna finestra storica
  in RAM; `from_csv_chunked` legge in chunk espliciti via generatore, fa `del` sulle
  righe processate e `gc.collect()` ogni `gc_interval` chunk.
- Error handling esplicito: `ConfigError`/`DataError`, zero `except: pass`.
- Config-driven: ogni parametro arriva da config, nessun magic number.
- API compatibile con la famiglia StrategyBase del progetto Denaro:
  `on_tick`, `on_fill`, `validate_config`, `estimate_memory_mb`.

Invariante: strategia long-only (`position >= 0`). Kill-switch = latch permanente
fino a chiamata esplicita di `rearm()`.
"""

from __future__ import annotations

import csv
import gc
import logging
import math
from dataclasses import dataclass
from typing import Any, Dict, Iterator, List, Optional, TextIO

logger = logging.getLogger("denaro.strategies.chandelier_trend")


class ConfigError(ValueError):
    """Configurazione non valida per ChandelierTrendRider."""


class DataError(RuntimeError):
    """Dati di mercato malformati o non processabili."""


@dataclass
class TrendConfig:
    """Parametri configurabili (config-driven, zero hardcode).

    Modello: trend = EMA_fast vs EMA_slow; stop trailing (long) =
    highest_high_since_entry - atr_mult * ATR; size = risk_pct * equity / stop_distance.
    """

    symbol: str = "SOL/EUR"
    ema_fast: int = 20                 # periodo EMA veloce
    ema_slow: int = 60                 # periodo EMA lenta
    atr_period: int = 14               # periodo ATR (Wilder)
    atr_mult: float = 3.0              # multiplo ATR per chandelier exit
    risk_pct: float = 0.02             # rischio per trade (frazione equity)
    max_drawdown: float = 0.15         # kill-switch: flat sotto questo drawdown
    fee_rate: float = 0.0026           # fee taker (default Kraken 0.26%)
    min_vol_ratio: float = 0.002       # floor ATR/price: mercato morto => no trade
    max_vol_ratio: float = 0.10        # cap ATR/price: volatilita' estrema => no trade
    max_position_pct: float = 0.5      # cap esposizione (frazione equity)
    cooldown_ticks: int = 50           # tick di pausa dopo un exit
    min_trend_gap_ticks: int = 3       # tick minimi di pendenza EMA confermata
    max_tick_age: float = 60.0         # secondi: tick piu' vecchio = dati stale
    csv_chunk_size: int = 10_000       # righe per chunk in from_csv_chunked
    gc_interval: int = 5               # gc.collect() ogni N chunk

    def validate(self) -> None:
        """Validazione dei range. Solleva ConfigError se fuori range."""
        if self.ema_fast < 2:
            raise ConfigError(f"ema_fast deve essere >= 2, got {self.ema_fast}")
        if self.ema_slow <= self.ema_fast:
            raise ConfigError(
                f"ema_slow ({self.ema_slow}) deve essere > ema_fast ({self.ema_fast})"
            )
        if self.atr_period < 2:
            raise ConfigError(f"atr_period deve essere >= 2, got {self.atr_period}")
        if self.atr_mult <= 0:
            raise ConfigError(f"atr_mult deve essere > 0, got {self.atr_mult}")
        if not 0.0 < self.risk_pct <= 0.25:
            raise ConfigError(f"risk_pct deve essere in (0, 0.25], got {self.risk_pct}")
        if not 0.0 < self.max_drawdown <= 1.0:
            raise ConfigError(
                f"max_drawdown deve essere in (0, 1], got {self.max_drawdown}"
            )
        if self.fee_rate < 0 or self.fee_rate >= 0.05:
            raise ConfigError(f"fee_rate fuori range, got {self.fee_rate}")
        if self.min_vol_ratio <= 0 or self.min_vol_ratio >= self.max_vol_ratio:
            raise ConfigError(
                f"range vol non valido: min {self.min_vol_ratio}, max {self.max_vol_ratio}"
            )
        if not 0.0 < self.max_position_pct <= 1.0:
            raise ConfigError(
                f"max_position_pct deve essere in (0, 1], got {self.max_position_pct}"
            )
        if self.cooldown_ticks < 0:
            raise ConfigError(f"cooldown_ticks deve essere >= 0, got {self.cooldown_ticks}")
        if self.min_trend_gap_ticks < 1:
            raise ConfigError(
                f"min_trend_gap_ticks deve essere >= 1, got {self.min_trend_gap_ticks}"
            )
        if self.max_tick_age <= 0:
            raise ConfigError(f"max_tick_age deve essere > 0, got {self.max_tick_age}")
        if self.csv_chunk_size <= 0:
            raise ConfigError(f"csv_chunk_size deve essere > 0, got {self.csv_chunk_size}")
        if self.gc_interval <= 0:
            raise ConfigError(f"gc_interval deve essere > 0, got {self.gc_interval}")


class StrategyBase:
    """Interfaccia base della famiglia StrategyBase del progetto Denaro."""

    def __init__(self, config: TrendConfig) -> None:
        self.config = config
        self.validate_config()

    def on_tick(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        raise NotImplementedError

    def on_fill(self, *args: Any, **kwargs: Any) -> None:
        raise NotImplementedError

    def validate_config(self) -> None:
        self.config.validate()

    def estimate_memory_mb(self) -> float:
        return 0.0


@dataclass
class _TrendState:
    """Stato incrementale O(1) — nessuna finestra storica in RAM."""

    ema_fast: float = 0.0
    ema_slow: float = 0.0
    atr: float = 0.0
    prev_close: Optional[float] = None
    last_price: float = 0.0            # ultimo prezzo di mark (per MTM incrementale)
    trend_up: bool = False
    trend_gap: int = 0                 # tick consecutivi con pendenza confermata
    position: float = 0.0              # qty (sempre >= 0: long-only)
    entry_price: float = 0.0
    stop_price: float = 0.0
    extreme_high: float = 0.0          # highest high since entry (long)
    equity: float = 0.0
    peak_equity: float = 0.0
    trades: int = 0
    wins: int = 0
    realized_pnl: float = 0.0
    cooldown: int = 0
    killed: bool = False
    last_ts: float = 0.0
    ticks: int = 0

    def reset(self) -> None:
        self.__init__()


class ChandelierTrendRider(StrategyBase):
    """Trend follower con chandelier exit ATR e kill-switch su drawdown."""

    def __init__(self, config: Optional[TrendConfig] = None) -> None:
        super().__init__(config or TrendConfig())
        self.state = _TrendState()
        self._alpha_fast = 2.0 / (self.config.ema_fast + 1.0)
        self._alpha_slow = 2.0 / (self.config.ema_slow + 1.0)

    # ------------------------------------------------------------------ utils
    def _init_capital(self, capital: float) -> None:
        """Inizializza equity/peak al primo tick con capitale noto."""
        self.state.equity = capital
        self.state.peak_equity = capital

    def _update_ema(self, price: float) -> None:
        """Aggiorna EMA fast/slow (smoothing EWMA streaming O(1)).

        Il seeding avviene sul PRIMO tick (ticks == 0), quindi il primo tick
        allinea ema_fast == ema_slow == price. Chiamare PRIMA di incrementare
        `ticks`.
        """
        if self.state.ticks == 0:
            self.state.ema_fast = price
            self.state.ema_slow = price
        else:
            self.state.ema_fast = (
                self._alpha_fast * price
                + (1.0 - self._alpha_fast) * self.state.ema_fast
            )
            self.state.ema_slow = (
                self._alpha_slow * price
                + (1.0 - self._alpha_slow) * self.state.ema_slow
            )

    def _update_atr(self, high: float, low: float, close: float) -> None:
        """ATR di Wilder incrementale (streaming O(1), niente finestra)."""
        prev = self.state.prev_close
        if prev is not None:
            tr = max(high - low, abs(high - prev), abs(low - prev))
            period = float(self.config.atr_period)
            if self.state.atr == 0.0:
                self.state.atr = tr
            else:
                self.state.atr = (self.state.atr * (period - 1.0) + tr) / period
        self.state.prev_close = close

    def _vol_ratio(self, price: float) -> float:
        """ATR/price: filtro regime di volatilita' operativa."""
        return self.state.atr / price if price > 0.0 else math.inf

    def _trend_ok(self) -> bool:
        """Regime long confermato: EMA fast > slow persistente per N tick consecutivi.

        Nota: filtro di crossover-persistenza (ema_fast > ema_slow), non pendenza
        dell'EMA. L'intento e' identico: confermare la direzione del trend prima
        di entrare.
        """
        if self.state.ema_fast > self.state.ema_slow:
            self.state.trend_gap = min(
                self.state.trend_gap + 1, self.config.min_trend_gap_ticks
            )
        else:
            self.state.trend_gap = 0
        return self.state.trend_gap >= self.config.min_trend_gap_ticks

    def _stop_distance(self) -> float:
        """Distanza stop = atr_mult * ATR (chandelier)."""
        return self.config.atr_mult * self.state.atr

    def _size_position(self, price: float) -> float:
        """Size risk-based: risk_pct * equity / stop_distance, capped."""
        stop_dist = self._stop_distance()
        if stop_dist <= 0.0:
            return 0.0
        risk_amount = self.config.risk_pct * self.state.equity
        qty = risk_amount / stop_dist
        max_qty = (
            self.config.max_position_pct * self.state.equity / price
            if price > 0.0
            else 0.0
        )
        return min(qty, max_qty)

    def _fee_ok(self, price: float) -> bool:
        """Skip se lo stop non copre il round-trip di fee (anti-bleed)."""
        return self._stop_distance() > 2.0 * self.config.fee_rate * price

    def _drawdown(self) -> float:
        """Drawdown corrente rispetto al picco di equity."""
        if self.state.peak_equity <= 0.0:
            return 0.0
        return (self.state.peak_equity - self.state.equity) / self.state.peak_equity

    def _mark_to_market(self, price: float) -> float:
        """Marca l'equity al prezzo corrente (incrementale da last_price).

        Ritorna e aggiorna `state.equity`. Gestisce correttamente i fill
        asincroni a prezzo diverso dall'ultimo tick.
        """
        if self.state.position != 0.0 and self.state.last_price > 0.0:
            self.state.equity += self.state.position * (price - self.state.last_price)
        self.state.last_price = price
        return self.state.equity

    # ------------------------------------------------------------ API public
    def on_tick(
        self,
        price: float,
        high: Optional[float] = None,
        low: Optional[float] = None,
        ts: float = 0.0,
    ) -> Dict[str, Any]:
        """Processa un tick OHLC-minimo. Ritorna il segnale di trading.

        Returns:
            Dict con action in {"buy", "sell", "hold"}, qty, reason e stato.
        """
        if price <= 0.0:
            raise DataError(f"prezzo non valido: {price}")
        if ts > 0.0 and self.state.last_ts > 0.0:
            if ts - self.state.last_ts > self.config.max_tick_age:
                raise DataError(f"tick stale: delta {ts - self.state.last_ts:.1f}s")
        h = high if high is not None else price
        l = low if low is not None else price
        if h < l:
            raise DataError(f"high ({h}) < low ({l})")

        self.state.last_ts = ts if ts > 0.0 else self.state.last_ts
        self._update_ema(price)
        self._update_atr(h, l, price)
        self.state.ticks += 1

        if self.state.equity == 0.0:
            raise DataError("equity non inizializzata: chiamare on_fill o init capital")

        self.state.equity = self._mark_to_market(price)
        self.state.peak_equity = max(self.state.peak_equity, self.state.equity)

        # kill-switch (latch permanente fino a rearm())
        if self.state.killed:
            if self.state.position > 0.0:
                # un fill di liquidazione puo' essere stato perso: riemetti il sell
                return self._signal(
                    "sell", price, "killed: liquidazione posizione residua",
                    qty=self.state.position,
                )
            return self._signal("hold", price, "killed: sistema flat, rearm() per riattivare")

        if self._drawdown() >= self.config.max_drawdown:
            if self.state.position != 0.0:
                self.state.killed = True
                return self._signal(
                    "sell", price, "kill-switch drawdown: liquidazione",
                    qty=abs(self.state.position),
                )
            self.state.killed = True
            return self._signal("hold", price, "killed: drawdown >= max_drawdown")

        # cooldown post-exit: blocca SOLO nuovi ingressi, mai la gestione stop
        if self.state.position == 0.0 and self.state.cooldown > 0:
            self.state.cooldown -= 1
            return self._signal("hold", price, "cooldown")

        vol = self._vol_ratio(price)
        if not (self.config.min_vol_ratio <= vol <= self.config.max_vol_ratio):
            return self._signal(
                "hold", price, f"vol ratio {vol:.5f} fuori range operativo"
            )

        trend_long = self._trend_ok()

        if self.state.position == 0.0:
            if trend_long and self._fee_ok(price):
                qty = self._size_position(price)
                if qty > 0.0:
                    return self._signal(
                        "buy", price, "regime long confermato + fee ok", qty=qty
                    )
            return self._signal("hold", price, "flat, attesa regime")

        # long aperto: chandelier exit (trailing stop)
        self.state.extreme_high = max(self.state.extreme_high, h)
        self.state.stop_price = self.state.extreme_high - self._stop_distance()
        if price <= self.state.stop_price:
            return self._signal(
                "sell", price, "chandelier exit long", qty=self.state.position
            )
        return self._signal("hold", price, "in long, stop trailing attivo")

    def rearm(self) -> None:
        """Riattiva il sistema dopo un kill-switch (scelta manuale esplicita)."""
        self.state.killed = False

    def _signal(
        self, action: str, price: float, reason: str, qty: float = 0.0
    ) -> Dict[str, Any]:
        return {
            "action": action,
            "qty": qty if action in ("buy", "sell") else 0.0,
            "price": price,
            "reason": reason,
            "state": {
                "position": self.state.position,
                "equity": round(self.state.equity, 6),
                "drawdown": round(self._drawdown(), 6),
                "atr": round(self.state.atr, 6),
                "trend_gap": self.state.trend_gap,
                "killed": self.state.killed,
            },
        }

    def on_fill(
        self,
        side: str,
        price: float,
        qty: float,
        fee: float = 0.0,
        ts: float = 0.0,
    ) -> None:
        """Registra un fill e aggiorna posizione/equity/PnL.

        Long-only: `buy` apre/aggiunge, `sell` chiude/riduce. Un `sell` con
        qty > posizione (o senza posizione) solleva DataError.
        """
        if side not in ("buy", "sell"):
            raise DataError(f"side non valido: {side}")
        if price <= 0.0 or qty <= 0.0:
            raise DataError(f"fill non valido: price={price}, qty={qty}")
        if fee < 0.0:
            raise DataError(f"fee negativa: {fee}")

        # mark-to-market della posizione esistente al prezzo di fill (asincrono)
        self._mark_to_market(price)

        if side == "buy":
            if self.state.position == 0.0:
                self.state.entry_price = price
                self.state.position = qty
                self.state.extreme_high = price
            else:
                # add-on long: media prezzo ponderata
                total_qty = self.state.position + qty
                self.state.entry_price = (
                    self.state.position * self.state.entry_price + qty * price
                ) / total_qty
                self.state.position = total_qty
                self.state.extreme_high = max(self.state.extreme_high, price)
        else:
            if self.state.position <= 0.0:
                raise DataError(
                    f"sell senza posizione long: position={self.state.position}"
                )
            if qty > self.state.position:
                raise DataError(
                    f"sell qty {qty} > position {self.state.position}"
                )
            pnl = (price - self.state.entry_price) * qty - fee
            self.state.realized_pnl += pnl
            self.state.trades += 1
            if pnl > 0.0:
                self.state.wins += 1
            self.state.position -= qty
            if self.state.position == 0.0:
                self.state.entry_price = 0.0
                self.state.extreme_high = 0.0
                self.state.cooldown = self.config.cooldown_ticks

        self.state.equity = max(0.0, self.state.equity - fee)
        self.state.peak_equity = max(self.state.peak_equity, self.state.equity)
        if ts > 0.0:
            self.state.last_ts = max(self.state.last_ts, ts)

    def validate_config(self) -> None:
        self.config.validate()

    def estimate_memory_mb(self) -> float:
        """Stato O(1): due EMA, ATR, ~20 float + dict segnale. < 0.1 MB."""
        return 0.02

    def stats(self) -> Dict[str, Any]:
        """Riepilogo statistiche per il reporting fleet."""
        return {
            "trades": self.state.trades,
            "wins": self.state.wins,
            "realized_pnl": round(self.state.realized_pnl, 6),
            "equity": round(self.state.equity, 6),
            "drawdown": round(self._drawdown(), 6),
            "killed": self.state.killed,
            "position": self.state.position,
        }

    # ------------------------------------------------------------ batch/CSV
    @classmethod
    def from_csv_chunked(
        cls, path: str, config: Optional[TrendConfig] = None
    ) -> "ChandelierTrendRider":
        """Esegue la strategia su un CSV (ts,price[,high,low]) in chunk OOM-safe.

        Usa un generatore per le righe, processa chunk espliciti da
        `csv_chunk_size`, fa `del` sul chunk processato e `gc.collect()` ogni
        `gc_interval` chunk. Ritorna l'istanza con lo stato finale.
        """
        cfg = config or TrendConfig()
        rider = cls(cfg)
        rider._init_capital(1000.0)

        def _rows(fh: TextIO) -> Iterator[Dict[str, str]]:
            reader = csv.DictReader(fh)
            for row in reader:
                yield row

        chunk: List[Dict[str, str]] = []
        with open(path, "r", newline="", encoding="utf-8") as fh:
            for i, row in enumerate(_rows(fh)):
                chunk.append(row)
                if len(chunk) >= cfg.csv_chunk_size:
                    rider._process_chunk(chunk)
                    del chunk
                    chunk = []
                    if (i // cfg.csv_chunk_size) % cfg.gc_interval == 0:
                        gc.collect()
            if chunk:
                rider._process_chunk(chunk)
                del chunk
                gc.collect()
        return rider

    def _process_chunk(self, chunk: List[Dict[str, str]]) -> None:
        """Processa un chunk di righe CSV (helper di from_csv_chunked)."""
        for row in chunk:
            try:
                ts = float(row.get("ts", 0.0))
                price = float(row["price"])
                high = float(row.get("high", price))
                low = float(row.get("low", price))
            except (KeyError, ValueError, TypeError) as exc:
                raise DataError(f"riga CSV malformata: {row!r}") from exc
            sig = self.on_tick(price, high=high, low=low, ts=ts)
            if sig["action"] in ("buy", "sell"):
                qty = sig["qty"] if sig["qty"] > 0.0 else self._size_position(price)
                if qty > 0.0:
                    fee = qty * price * self.config.fee_rate
                    self.on_fill(sig["action"], price, qty, fee=fee, ts=ts)


if __name__ == "__main__":
    # Test inline con dati sintetici piccoli (trend up + rumore, poi flat).
    import random

    logging.basicConfig(level=logging.WARNING)

    cfg = TrendConfig(
        ema_fast=8,
        ema_slow=24,
        atr_period=10,
        atr_mult=2.5,
        risk_pct=0.02,
        min_vol_ratio=0.001,
        max_vol_ratio=0.15,
        cooldown_ticks=5,
        fee_rate=0.0005,  # fee ridotta SOLO nel test: ATR sintetico piccolo => anti-bleed
    )
    rider = ChandelierTrendRider(cfg)
    rider._init_capital(1000.0)

    rng = random.Random(42)
    price = 100.0
    n_buys = n_sells = 0
    for i in range(3000):
        drift = 0.008 if i < 1500 else -0.004
        price = max(1.0, price + drift + rng.gauss(0, 0.15))
        high = price + abs(rng.gauss(0, 0.08))
        low = price - abs(rng.gauss(0, 0.08))
        sig = rider.on_tick(price, high=high, low=low, ts=float(i))
        if sig["action"] == "buy":
            rider.on_fill("buy", price, sig["qty"], fee=price * sig["qty"] * cfg.fee_rate)
            n_buys += 1
        elif sig["action"] == "sell":
            rider.on_fill("sell", price, sig["qty"], fee=price * sig["qty"] * cfg.fee_rate)
            n_sells += 1

    s = rider.stats()
    assert s["trades"] > 0, f"attesi trade, got {s}"
    assert n_buys > 0 and n_sells > 0, f"attesi ingressi ed uscite: buys={n_buys} sells={n_sells}"
    assert s["equity"] > 0.0, f"equity deve restare positiva, got {s['equity']}"
    assert rider.estimate_memory_mb() < 1.0

    # validate_config deve rifiutare config non valide
    bad = TrendConfig(ema_fast=50, ema_slow=20)
    try:
        ChandelierTrendRider(bad)
        raise AssertionError("attesa ConfigError su ema_slow <= ema_fast")
    except ConfigError:
        pass

    print(f"TEST OK: trades={s['trades']} wins={s['wins']} pnl={s['realized_pnl']:.4f} "
          f"equity={s['equity']:.2f} dd={s['drawdown']:.4f} buys={n_buys} sells={n_sells} "
          f"mem={rider.estimate_memory_mb()}MB")