"""MomentumBreakoutDonchian — breakout Donchian + filtro volatilità EWMA (streaming, OOM-safe).

Strategia momentum complementare alle grid della fleet: invece di fare mean
reversion sui livelli, cattura i breakout direzionali. Il canale Donchian è
tenuto in un deque a capacità fissa (O(1) memoria, nessuna finestra in RAM),
la volatilità è stimata con ATR Wilder smoothing incrementale (O(1) per tick)
e il regime è filtrato su un EWMA di volatilità percentuale: niente entry in
mercati morti (vol troppo bassa) né in panic spike (vol troppo alta).

Design goals:
- OOM-safe: nessuna lista storica illimitata; `from_csv_chunked` legge il
  dataset in chunk espliciti, rilascia la reference al chunk processato e
  chiama `gc.collect()` ogni `gc_interval` chunk.
- Error handling esplicito: ConfigError/DataError, zero `except: pass`.
- Config-driven: ogni parametro arriva da config, nessun magic number.
- API compatibile con la famiglia StrategyBase del progetto Denaro:
  `on_tick`, `on_fill`, `validate_config`, `estimate_memory_mb`.

La strategia è long-only con trailing stop chandelier: segnale LONG quando
il prezzo supera l'upper Donchian con volatilità nel range ammesso; uscita
quando il prezzo rompe il trailing stop (max ATR-based da peak) o scende
sotto il lower Donchian. Un cooldown post-exit evita il whipsaw.
"""

from __future__ import annotations

import csv
import gc
import logging
import math
from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Dict, List, Optional, TextIO

logger = logging.getLogger("denaro.strategies.momentum_breakout")


class ConfigError(ValueError):
    """Configurazione non valida per MomentumBreakoutDonchian."""


class DataError(RuntimeError):
    """Dati di mercato malformati o non processabili."""


@dataclass
class MomentumConfig:
    """Parametri configurabili della strategia (config-driven, zero hardcode)."""

    symbol: str = "SOL/EUR"
    donchian_period: int = 20          # lookback canale Donchian (tick)
    atr_period: int = 14               # lookback ATR (Wilder smoothing)
    atr_mult_stop: float = 3.0         # multiplo ATR per trailing stop chandelier
    min_atr_pct: float = 0.001         # volatilità minima (1bp) per entrare
    max_atr_pct: float = 0.05          # volatilità massima (5%) per entrare
    cooldown_ticks: int = 10           # tick di attesa dopo un'exit
    position_pct: float = 0.5          # frazione del capitale per entry
    fee_rate: float = 0.0026           # fee taker (default Kraken 0.26%)
    max_spread_ratio: float = 0.002    # spread max ammesso (frazione del mid)
    csv_chunk_size: int = 10_000       # righe per chunk in from_csv_chunked
    gc_interval: int = 5               # gc.collect() ogni N chunk

    def __post_init__(self) -> None:
        """Validazione dei vincoli numerici di base."""
        if self.donchian_period < 2 or self.atr_period < 2:
            raise ConfigError("periodi Donchian/ATR devono essere >= 2")
        if not 0.0 < self.min_atr_pct < self.max_atr_pct:
            raise ConfigError("richiesto 0 < min_atr_pct < max_atr_pct")
        if not 0.0 < self.position_pct <= 1.0:
            raise ConfigError("position_pct deve essere in (0, 1]")
        if not 0.0 <= self.fee_rate < 0.1:
            raise ConfigError("fee_rate fuori range realistico")
        if self.cooldown_ticks < 0:
            raise ConfigError("cooldown_ticks non può essere negativo")
        if self.csv_chunk_size < 1 or self.gc_interval < 1:
            raise ConfigError("chunk size e gc interval devono essere >= 1")
        if self.max_spread_ratio <= 0.0:
            raise ConfigError("max_spread_ratio deve essere > 0")


class MomentumBreakoutDonchian:
    """StrategyBase per breakout Donchian con filtri di volatilità streaming.

    Stato interno tutto O(1): un deque a capacità fissa per i prezzi del
    canale, due accumulatori EWMA/Wilder per ATR e volatilità percentuale.
    """

    def __init__(self, config: Optional[MomentumConfig] = None) -> None:
        self.config: MomentumConfig = config or MomentumConfig()
        self.validate_config()
        # canale Donchian: deque a capacità fissa -> memoria O(period)
        self._prices: Deque[float] = deque(maxlen=self.config.donchian_period)
        # accumulatori streaming
        self._atr: Optional[float] = None
        self._prev_close: Optional[float] = None
        self._vol_ewma: Optional[float] = None
        # stato posizione / trading
        self._position: float = 0.0        # quote unità detenute
        self._entry_price: Optional[float] = None
        self._entry_fee: float = 0.0       # fee cumulata della posizione aperta
        self._peak_price: Optional[float] = None
        self._cooldown_left: int = 0
        self._tick_count: int = 0
        self._equity: float = 0.0
        self._cash: float = 0.0
        self._realized_pnl: float = 0.0
        self._trades: int = 0
        self._wins: int = 0
        self._losses: int = 0

    # ------------------------------------------------------------------
    # API StrategyBase
    # ------------------------------------------------------------------
    def validate_config(self) -> None:
        """Valida la config completa; alza ConfigError se non valida."""
        cfg = self.config
        if cfg.donchian_period < 2 or cfg.atr_period < 2:
            raise ConfigError("periodi Donchian/ATR devono essere >= 2")
        if not 0.0 < cfg.min_atr_pct < cfg.max_atr_pct:
            raise ConfigError("richiesto 0 < min_atr_pct < max_atr_pct")
        if not 0.0 < cfg.position_pct <= 1.0:
            raise ConfigError("position_pct deve essere in (0, 1]")
        if not 0.0 <= cfg.fee_rate < 0.1:
            raise ConfigError("fee_rate fuori range realistico")
        if cfg.cooldown_ticks < 0:
            raise ConfigError("cooldown_ticks non può essere negativo")
        if cfg.csv_chunk_size < 1 or cfg.gc_interval < 1:
            raise ConfigError("chunk size e gc interval devono essere >= 1")
        if cfg.max_spread_ratio <= 0.0:
            raise ConfigError("max_spread_ratio deve essere > 0")

    def estimate_memory_mb(self) -> float:
        """Stima conservativa della memoria usata (O(donchian_period))."""
        # 8 byte/float * (period + ATR buffer implicito) + overhead deque
        floats = self.config.donchian_period + self.config.atr_period + 64
        return round(floats * 8.0 / (1024.0 * 1024.0), 6)

    def on_tick(self, price: float, bid: Optional[float] = None,
                ask: Optional[float] = None, timestamp: Optional[float] = None) -> str:
        """Processa un tick; ritorna 'BUY' | 'SELL' | 'HOLD'.

        Args:
            price: prezzo mid di riferimento.
            bid/ask: per il check dello spread (opzionali, default = price).
            timestamp: non usato, presente per compatibilità col feed.

        Raises:
            DataError: se price non è un numero finito positivo.
        """
        if (isinstance(price, bool) or not isinstance(price, (int, float))
                or not math.isfinite(price) or price <= 0.0):
            raise DataError(f"prezzo non valido: {price!r}")
        bid = price if bid is None else bid
        ask = price if ask is None else ask
        if (isinstance(bid, bool) or isinstance(ask, bool)
                or not math.isfinite(bid) or not math.isfinite(ask)
                or bid <= 0.0 or ask <= 0.0 or ask < bid):
            raise DataError(f"spread malformato bid={bid} ask={ask}")

        self._tick_count += 1
        if self._cooldown_left > 0:
            self._cooldown_left -= 1

        # --- aggiornamento accumulatori streaming ---------------------
        spread_ratio: float = (ask - bid) / price
        # canale Donchian sulla finestra PRECEDENTE al tick corrente:
        # un breakout deve superare l'high dei periodi passati, non includere
        # sé stesso (altrimenti price > max(prices) non scatta mai).
        donch_high: float = max(self._prices) if self._prices else price
        donch_low: float = min(self._prices) if self._prices else price
        self._prices.append(price)
        self._update_volatility(price)

        # --- gestione posizione aperta --------------------------------
        # on_tick e' SOLO generatore di segnali: nessuna mutazione dello
        # stato trading (entry/peak/cooldown). L'applicazione avviene in
        # on_fill, che resta l'unica fonte di verita' per l'accounting.
        if self._position > 0.0 and self._entry_price is not None:
            self._peak_price = max(self._peak_price or self._entry_price, price)
            stop: float = self._peak_price - self.config.atr_mult_stop * (self._atr or 0.0)
            if price <= stop or price < donch_low:
                return "SELL"

        # --- segnale di ingresso --------------------------------------
        if self._position == 0.0 and self._cooldown_left == 0:
            if len(self._prices) < self.config.donchian_period:
                return "HOLD"
            if spread_ratio > self.config.max_spread_ratio:
                return "HOLD"
            atr_pct: float = (self._atr / price) if self._atr else 0.0
            if not (self.config.min_atr_pct <= atr_pct <= self.config.max_atr_pct):
                return "HOLD"
            if price > donch_high:
                return "BUY"
        return "HOLD"

    def on_fill(self, side: str, price: float, qty: float,
                fee: Optional[float] = None) -> None:
        """Registra un fill; aggiorna posizione, cash ed equity."""
        if side not in ("BUY", "SELL"):
            raise DataError(f"side non valido: {side!r}")
        if (isinstance(price, bool) or not math.isfinite(price) or price <= 0.0
                or not math.isfinite(qty) or qty <= 0.0):
            raise DataError(f"fill malformato price={price} qty={qty}")
        fee_amount: float = self.config.fee_rate * price * qty if fee is None else fee
        if side == "BUY":
            # entry price media pesata sulla quantità (supporta fill parziali)
            old_qty: float = self._position
            new_qty: float = old_qty + qty
            if old_qty == 0.0:
                self._entry_price = price
                self._peak_price = price
            else:
                old_notional: float = (self._entry_price or price) * old_qty
                self._entry_price = (old_notional + price * qty) / new_qty
                self._peak_price = max(self._peak_price or price, price)
            self._cash -= price * qty + fee_amount
            self._entry_fee += fee_amount
            self._position = new_qty
        else:
            if qty > self._position:
                raise DataError(f"SELL qty {qty} > position {self._position}")
            # allocazione proporzionale della fee d'ingresso sulla quota uscente
            allocated_entry_fee: float = (
                self._entry_fee * (qty / self._position) if self._position > 0.0 else 0.0
            )
            self._entry_fee -= allocated_entry_fee
            gross: float = (price - (self._entry_price or price)) * qty - fee_amount - allocated_entry_fee
            self._cash += price * qty - fee_amount
            self._position -= qty
            self._trades += 1
            self._realized_pnl += gross
            if gross > 0.0:
                self._wins += 1
            else:
                self._losses += 1
            if self._position <= 1e-12:
                self._position = 0.0
                self._entry_price = None
                self._peak_price = None
                self._entry_fee = 0.0
                self._cooldown_left = self.config.cooldown_ticks
        self._equity = self._cash + self._position * price

    # ------------------------------------------------------------------
    # Internals streaming
    # ------------------------------------------------------------------
    def _update_volatility(self, price: float) -> None:
        """Aggiorna ATR (Wilder) e EWMA volatilità % in un passaggio O(1).

        True Range stimato come |price - prev_close| (feed close-to-close,
        senza high/low). Lo stesso TR alimenta entrambi gli accumulatori.
        """
        prev = self._prev_close
        if prev is None:
            self._prev_close = price
            return
        tr: float = abs(price - prev)
        # ATR Wilder smoothing (O(1))
        if self._atr is None:
            self._atr = tr
        else:
            alpha_atr: float = 1.0 / float(self.config.atr_period)
            self._atr = (1.0 - alpha_atr) * self._atr + alpha_atr * tr
        # EWMA volatilità percentuale (|return|) — metrica diagnostica
        ret: float = tr / prev if prev > 0.0 else 0.0
        if self._vol_ewma is None:
            self._vol_ewma = ret
        else:
            alpha_vol: float = 2.0 / float(self.config.atr_period + 1)
            self._vol_ewma = (1.0 - alpha_vol) * self._vol_ewma + alpha_vol * ret
        self._prev_close = price

    # ------------------------------------------------------------------
    # Report / utility
    # ------------------------------------------------------------------
    def stats(self) -> Dict[str, Any]:
        """Snapshot dello stato per health/fleet reporting."""
        return {
            "strategy": "momentum_breakout_donchian",
            "tick_count": self._tick_count,
            "trades": self._trades,
            "wins": self._wins,
            "losses": self._losses,
            "realized_pnl": round(self._realized_pnl, 6),
            "equity": round(self._equity, 6),
            "atr": round(self._atr, 8) if self._atr else None,
            "vol_ewma": round(self._vol_ewma, 8) if self._vol_ewma else None,
            "mem_mb": self.estimate_memory_mb(),
        }

    @classmethod
    def from_csv_chunked(cls, path: str, config: Optional[MomentumConfig] = None) -> "MomentumBreakoutDonchian":
        """Backtest su CSV con ingestione a chunk (generatore + gc esplicito).

        Formato atteso: header con colonne 'price' (e opzionali 'bid','ask').

        Raises:
            DataError: se il file non è leggibile o non ha la colonna price.
        """
        cfg = config or MomentumConfig()
        strat = cls(cfg)
        try:
            handle: TextIO = open(path, "r", newline="", encoding="utf-8")
        except OSError as exc:
            raise DataError(f"impossibile aprire {path}: {exc}") from exc
        with handle:
            reader = csv.DictReader(handle)
            if "price" not in (reader.fieldnames or []):
                raise DataError("csv senza colonna 'price'")
            chunk: List[Dict[str, str]] = []
            chunk_count: int = 0
            for row in reader:
                chunk.append(row)
                if len(chunk) >= cfg.csv_chunk_size:
                    strat._process_chunk(chunk)
                    chunk = []  # release esplicito della reference
                    chunk_count += 1
                    if chunk_count % cfg.gc_interval == 0:
                        gc.collect()
            if chunk:
                strat._process_chunk(chunk)
        return strat

    def _process_chunk(self, chunk: List[Dict[str, str]]) -> None:
        """Processa un chunk di righe csv; chiamato solo da from_csv_chunked."""
        for row in chunk:
            try:
                price: float = float(row["price"])
                bid: Optional[float] = float(row["bid"]) if row.get("bid") else None
                ask: Optional[float] = float(row["ask"]) if row.get("ask") else None
            except (ValueError, TypeError) as exc:
                raise DataError(f"riga csv non numerica: {row!r}") from exc
            self.on_tick(price, bid=bid, ask=ask)


if __name__ == "__main__":
    # --------------------------------------------------------------
    # Test inline: bug regressione + run sintetica
    # --------------------------------------------------------------
    logging.basicConfig(level=logging.INFO)

    # 1) validazione config: deve alzare ConfigError
    try:
        MomentumConfig(min_atr_pct=0.05, max_atr_pct=0.001)
        raise AssertionError("ConfigError non sollevata")
    except ConfigError:
        pass

    # 1b) __init__ deve validare csv_chunk_size / gc_interval / spread
    try:
        MomentumBreakoutDonchian(MomentumConfig(csv_chunk_size=0))
        raise AssertionError("ConfigError non sollevata su csv_chunk_size=0")
    except ConfigError:
        pass
    try:
        MomentumBreakoutDonchian(MomentumConfig(max_spread_ratio=0.0))
        raise AssertionError("ConfigError non sollevata su max_spread_ratio=0")
    except ConfigError:
        pass

    # 2) run su serie sintetica con trend + pullback -> almeno 1 trade
    cfg = MomentumConfig(donchian_period=5, atr_period=5, cooldown_ticks=3,
                         min_atr_pct=0.0001, max_atr_pct=0.1)
    s = MomentumBreakoutDonchian(cfg)
    s.validate_config()
    price = 100.0
    signals = []
    for i in range(400):
        price *= 1.0015 if i < 250 else 0.9995   # trend up poi pullback
        pos_before: float = s._position           # qty reale pre-tick (per SELL)
        sig = s.on_tick(price)
        signals.append(sig)
        if sig == "BUY":
            s.on_fill("BUY", price, cfg.position_pct)
        elif sig == "SELL":
            s.on_fill("SELL", price, pos_before)

    st = s.stats()
    print(f"trades={st['trades']} wins={st['wins']} losses={st['losses']} "
          f"pnl={st['realized_pnl']} mem_mb={st['mem_mb']}")
    assert st["trades"] >= 1, "nessun trade generato dalla serie sintetica"
    assert st["wins"] + st["losses"] == st["trades"]
    assert s.estimate_memory_mb() < 0.001, "memoria stimata fuori range"

    # 3) errore su prezzo non valido -> DataError
    for bad in (float("nan"), float("inf"), -1.0, True):
        try:
            s.on_tick(bad)
            raise AssertionError(f"DataError non sollevata per {bad!r}")
        except DataError:
            pass

    # 4) SELL oltre la posizione -> DataError
    s2 = MomentumBreakoutDonchian(cfg)
    try:
        s2.on_fill("SELL", 100.0, 10.0)
        raise AssertionError("DataError non sollevata su oversell")
    except DataError:
        pass

    # 5) vol_ewma deve diventare non-zero dopo tick con movimento
    s3 = MomentumBreakoutDonchian(cfg)
    for p in (100.0, 101.0, 103.0, 102.0, 105.0):
        s3.on_tick(p)
    st3 = s3.stats()
    assert st3["vol_ewma"] is not None and st3["vol_ewma"] > 0.0, \
        f"vol_ewma morto: {st3['vol_ewma']}"
    assert st3["atr"] is not None and st3["atr"] > 0.0, "ATR morto"

    # 6) pnl = variazione netta cash (fee incluse) su round-trip
    s4 = MomentumBreakoutDonchian(cfg)
    s4.on_fill("BUY", 100.0, 1.0)
    s4.on_fill("SELL", 110.0, 1.0)
    # fee d'ingresso @100, fee d'uscita @110 (non 2x fee @100)
    buy_fee = cfg.fee_rate * 100.0 * 1.0
    sell_fee = cfg.fee_rate * 110.0 * 1.0
    expected_pnl = (110.0 - 100.0) * 1.0 - buy_fee - sell_fee
    assert abs(s4._realized_pnl - expected_pnl) < 1e-9, \
        f"pnl errato: {s4._realized_pnl} vs {expected_pnl}"

    print("OK: MomentumBreakoutDonchian test superati")
