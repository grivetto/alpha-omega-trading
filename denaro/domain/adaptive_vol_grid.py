"""AdaptiveVolGrid — griglia mean-reversion a spacing adattivo ATR (streaming, OOM-safe).

Improvement diretto sul grid statico oggi deployato su tutta la fleet (mc2, nuvola,
marcodg1): invece di livelli a distanza fissa, lo spacing della griglia scala con la
volatilita' corrente (ATR Wilder incrementale). In regime di bassa volatilita' la
griglia si stringe e cattura piu' micro-mean-reversion; in regime alto si allarga e
evita fill prematuri seguiti da drawdown. La griglia si ri-centra sul prezzo quando
il mercato fa un regime shift oltre la banda, senza mai inseguire il prezzo tick per
tick (re-center con hysteresis).

Design goals:
- OOM-safe: ATR incrementale O(1), nessuna finestra storica in RAM; `from_csv_chunked`
  legge in chunk espliciti via generatore, `del` sulle righe processate e
  `gc.collect()` ogni `gc_interval` chunk.
- Error handling esplicito: `ConfigError`/`DataError`, zero `except: pass`.
- Config-driven: ogni parametro da config, nessun magic number.
- API compatibile StrategyBase: `on_tick`, `on_fill`, `validate_config`,
  `estimate_memory_mb`.
"""

from __future__ import annotations

import csv
import gc
import logging
import math
from dataclasses import dataclass
from typing import Any, Dict, Iterator, List, Optional, TextIO

from .grid import GridDecision, GridLevel

logger = logging.getLogger("denaro.strategies.adaptive_vol_grid")


class ConfigError(ValueError):
    """Configurazione non valida per AdaptiveVolGrid."""


class DataError(RuntimeError):
    """Dati di mercato malformati o non processabili."""


@dataclass
class GridConfig:
    """Parametri configurabili (config-driven, zero hardcode).

    Modello: spacing = atr_mult * ATR(period) (Wilder); livelli buy sotto il
    prezzo corrente, take-profit a avg_entry + tp_atr_mult * ATR; la griglia
    si ri-centra quando |price - center| > recenter_band_pct * price.
    """

    symbol: str = "SOL/EUR"
    capital: float = 13.5                # capitale allocato (EUR)
    levels: int = 4                      # numero di livelli buy sotto il prezzo
    atr_period: int = 14                 # periodo ATR (Wilder)
    atr_mult: float = 0.5                # spacing = atr_mult * ATR
    tp_atr_mult: float = 1.5             # take-profit = avg_entry + tp_atr_mult * ATR
    min_spacing_pct: float = 0.002       # floor spacing (% prezzo): mercato morto
    max_spacing_pct: float = 0.05        # cap spacing (% prezzo): vol estrema
    fee_rate: float = 0.0026             # fee taker (default Kraken 0.26%)
    max_drawdown: float = 0.10           # kill-switch: flat sotto questo drawdown
    max_position_pct: float = 0.95       # cap esposizione (frazione capitale)
    recenter_band_pct: float = 0.03      # banda di ri-centraggio (% prezzo)
    cooldown_ticks: int = 5              # tick di pausa dopo un fill
    min_vol_ratio: float = 0.0005        # floor ATR/price operativo
    max_vol_ratio: float = 0.10          # cap ATR/price operativo
    max_tick_age: float = 60.0           # secondi: tick piu' vecchio = stale
    csv_chunk_size: int = 10_000         # righe per chunk in from_csv_chunked
    gc_interval: int = 5                 # gc.collect() ogni N chunk

    def validate(self) -> None:
        """Validazione dei range. Solleva ConfigError se fuori range."""
        if self.capital <= 0.0:
            raise ConfigError(f"capital deve essere > 0, got {self.capital}")
        if not 1 <= self.levels <= 50:
            raise ConfigError(f"levels deve essere in [1, 50], got {self.levels}")
        if self.atr_period < 2:
            raise ConfigError(f"atr_period deve essere >= 2, got {self.atr_period}")
        if self.atr_mult <= 0.0:
            raise ConfigError(f"atr_mult deve essere > 0, got {self.atr_mult}")
        if self.tp_atr_mult <= 0.0:
            raise ConfigError(f"tp_atr_mult deve essere > 0, got {self.tp_atr_mult}")
        if not 0.0 < self.min_spacing_pct < self.max_spacing_pct <= 0.20:
            raise ConfigError(
                "range spacing non valido: "
                f"min {self.min_spacing_pct}, max {self.max_spacing_pct}"
            )
        if self.fee_rate < 0.0 or self.fee_rate >= 0.05:
            raise ConfigError(f"fee_rate fuori range, got {self.fee_rate}")
        if not 0.0 < self.max_drawdown <= 1.0:
            raise ConfigError(
                f"max_drawdown deve essere in (0, 1], got {self.max_drawdown}"
            )
        if not 0.0 < self.max_position_pct <= 1.0:
            raise ConfigError(
                f"max_position_pct deve essere in (0, 1], got {self.max_position_pct}"
            )
        if not 0.0 < self.recenter_band_pct <= 0.20:
            raise ConfigError(
                f"recenter_band_pct deve essere in (0, 0.20], got {self.recenter_band_pct}"
            )
        if self.cooldown_ticks < 0:
            raise ConfigError(f"cooldown_ticks deve essere >= 0, got {self.cooldown_ticks}")
        if self.min_vol_ratio <= 0.0 or self.min_vol_ratio >= self.max_vol_ratio:
            raise ConfigError(
                f"range vol non valido: min {self.min_vol_ratio}, max {self.max_vol_ratio}"
            )
        if self.max_tick_age <= 0.0:
            raise ConfigError(f"max_tick_age deve essere > 0, got {self.max_tick_age}")
        if self.csv_chunk_size <= 0:
            raise ConfigError(f"csv_chunk_size deve essere > 0, got {self.csv_chunk_size}")
        if self.gc_interval <= 0:
            raise ConfigError(f"gc_interval deve essere > 0, got {self.gc_interval}")


class StrategyBase:
    """Interfaccia base della famiglia StrategyBase del progetto Denaro."""

    def __init__(self, config: GridConfig) -> None:
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
class _GridState:
    """Stato incrementale O(1) — nessuna finestra storica in RAM."""

    atr: float = 0.0
    prev_close: Optional[float] = None
    center: float = 0.0
    cash: float = 0.0
    equity: float = 0.0
    peak_equity: float = 0.0
    position_qty: float = 0.0
    avg_entry: float = 0.0
    realized_pnl: float = 0.0
    trades: int = 0
    wins: int = 0
    cooldown: int = 0
    killed: bool = False
    last_ts: float = 0.0
    ticks: int = 0


class AdaptiveVolGrid(StrategyBase):
    """Griglia mean-reversion a spacing adattivo ATR con ri-centraggio a banda."""

    def __init__(self, config: Optional[GridConfig] = None, min_amount: float = 0.0) -> None:
        super().__init__(config or GridConfig())
        self.min_amount = max(0.0, float(min_amount))
        self.state = _GridState()
        self.state.cash = self.config.capital
        self.state.equity = self.config.capital
        self.state.peak_equity = self.config.capital

    # ------------------------------------------------------------- internals
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

    def _spacing(self, price: float) -> float:
        """Spacing assoluto = atr_mult * ATR, clampato a bande % prezzo."""
        atr_based = self.config.atr_mult * self.state.atr
        floor = self.config.min_spacing_pct * price
        cap = self.config.max_spacing_pct * price
        return max(floor, min(atr_based, cap))

    def _vol_ratio(self, price: float) -> float:
        """ATR/price: filtro regime di volatilita' operativa."""
        return self.state.atr / price if price > 0.0 else math.inf

    def _drawdown(self) -> float:
        """Drawdown corrente rispetto al picco di equity."""
        if self.state.peak_equity <= 0.0:
            return 0.0
        return (self.state.peak_equity - self.state.equity) / self.state.peak_equity

    def _mark_to_market(self, price: float) -> float:
        """Equity = cash + posizione valutata al prezzo corrente (niente doppio conteggio)."""
        return self.state.cash + self.state.position_qty * price

    def _fee_ok(self, price: float) -> bool:
        """Skip se TP o spacing non coprono il round-trip di fee (anti-bleed)."""
        return (
            self.config.tp_atr_mult * self.state.atr > 2.0 * self.config.fee_rate * price
            and self._spacing(price) > 2.0 * self.config.fee_rate * price
        )

    def _signal(
        self, action: str, price: float, reason: str, qty: float = 0.0
    ) -> Dict[str, Any]:
        return {
            "action": action,
            "qty": qty if action in ("buy", "sell") else 0.0,
            "price": price,
            "reason": reason,
            "state": {
                "position_qty": self.state.position_qty,
                "equity": round(self.state.equity, 6),
                "drawdown": round(self._drawdown(), 6),
                "atr": round(self.state.atr, 6),
                "center": round(self.state.center, 6),
                "killed": self.state.killed,
            },
        }

    def _buy_qty(self, price: float) -> float:
        """Qty per livello: quota capitale per livello / prezzo, cap esposizione."""
        per_level = self.config.capital / float(self.config.levels)
        qty = per_level / price if price > 0.0 else 0.0
        max_qty = self.config.max_position_pct * self.state.equity / price if price > 0.0 else 0.0
        return min(qty, max_qty)

    # ------------------------------------------------------- Node Policy adapter
    def on_price(self, price: float) -> None:
        """Aggiorna ATR e centro usando il tick fornito dal Node orchestrator."""
        if price <= 0.0:
            raise DataError(f"prezzo non valido: {price}")
        self.state.ticks += 1
        self._update_atr(price, price, price)
        if self.state.center == 0.0:
            self.state.center = price
        band = self.config.recenter_band_pct * price
        if abs(price - self.state.center) > band:
            self.state.center = price

    def sell_target(self, entry_price: float) -> float:
        """Target adattivo che copre sempre almeno le fee round-trip."""
        if entry_price <= 0.0:
            raise DataError(f"entry price non valido: {entry_price}")
        atr_target = self.config.tp_atr_mult * self.state.atr
        fee_floor = entry_price * self.config.fee_rate * 2.2
        return entry_price + max(atr_target, fee_floor)

    def decide(
        self,
        price: float,
        open_buys: Dict[str, dict],
        open_sells: Dict[str, dict],
        cash: float,
        capital_config: float,
        free_balance: float,
        now: float,
        free_asset: float = 0.0,
    ) -> GridDecision:
        """Adatta la strategia streaming al contratto idempotente del Node."""
        del open_sells, now, free_asset
        decision = GridDecision()
        if price <= 0.0:
            decision.reason = "prezzo non valido"
            return decision
        if self.state.atr <= 0.0:
            decision.reason = "ATR non inizializzato"
            return decision
        if not self._fee_ok(price):
            decision.reason = "spacing/TP non coprono le fee"
            return decision

        occupied_levels = {
            int(order.get("level", -1)) for order in open_buys.values()
        }
        missing_levels = [
            level for level in range(self.config.levels)
            if level not in occupied_levels
        ]
        if not missing_levels:
            decision.reason = "griglia completa"
            return decision

        available = max(0.0, min(float(cash), float(capital_config), float(free_balance)))
        per_level = available / max(1, len(missing_levels))
        spacing = self._spacing(price)
        for level in missing_levels:
            buy_price = price - (level + 1) * spacing
            if buy_price <= 0.0:
                continue
            amount = per_level / buy_price
            if amount <= 0.0 or amount < self.min_amount:
                continue
            decision.to_place.append(
                GridLevel(
                    buy_price=round(buy_price, 8),
                    amount=round(amount, 8),
                    level=level,
                )
            )
        decision.reason = "griglia adattiva" if decision.to_place else "capitale insufficiente"
        return decision

    # ------------------------------------------------------------- API public
    def on_tick(
        self,
        price: float,
        high: Optional[float] = None,
        low: Optional[float] = None,
        ts: float = 0.0,
    ) -> Dict[str, Any]:
        """Processa un tick OHLC-minimo. Ritorna il segnale di trading.

        Returns:
            Dict con action in {"buy", "sell", "hold"}, qty, price, reason e stato.
        """
        if price <= 0.0:
            raise DataError(f"prezzo non valido: {price}")
        if ts > 0.0 and self.state.last_ts > 0.0:
            if ts - self.state.last_ts > self.config.max_tick_age:
                raise DataError(f"tick stale: delta {ts - self.state.last_ts:.1f}s")
        h = high if high is not None else price
        l = low if low is not None else price

        self.state.ticks += 1
        self.state.last_ts = ts if ts > 0.0 else self.state.last_ts
        self._update_atr(h, l, price)

        # primo tick: centra la griglia sul prezzo corrente
        if self.state.center == 0.0:
            self.state.center = price

        self.state.equity = self._mark_to_market(price)
        self.state.peak_equity = max(self.state.peak_equity, self.state.equity)

        # kill-switch drawdown: flat e niente nuovi ingressi
        if self._drawdown() >= self.config.max_drawdown:
            self.state.killed = True
            if self.state.position_qty > 0.0:
                return self._signal(
                    "sell", price, "kill-switch drawdown", qty=self.state.position_qty
                )
            return self._signal("hold", price, "killed: drawdown >= max_drawdown")

        # cooldown post-fill
        if self.state.cooldown > 0:
            self.state.cooldown -= 1
            return self._signal("hold", price, "cooldown")

        vol = self._vol_ratio(price)
        if not (self.config.min_vol_ratio <= vol <= self.config.max_vol_ratio):
            return self._signal(
                "hold", price, f"vol ratio {vol:.5f} fuori range operativo"
            )

        spacing = self._spacing(price)
        if not self._fee_ok(price):
            return self._signal(
                "hold", price, f"spacing {spacing:.6f}/TP non coprono le fee"
            )

        # ri-centraggio con hysteresis: solo se il prezzo esce dalla banda
        band = self.config.recenter_band_pct * price
        if abs(price - self.state.center) > band:
            self.state.center = price

        # griglia: buy quando price scende sotto center - k*spacing
        for k in range(1, self.config.levels + 1):
            level_buy = self.state.center - k * spacing
            if price <= level_buy:
                qty = self._buy_qty(price)
                if qty > 0.0:
                    return self._signal(
                        "buy", price, f"livello grid {k}: buy <= {level_buy:.6f}", qty=qty
                    )

        # take-profit adattivo: vendi se price >= avg_entry + tp_atr_mult * ATR
        if self.state.position_qty > 0.0 and self.state.avg_entry > 0.0:
            tp_price = self.state.avg_entry + self.config.tp_atr_mult * self.state.atr
            if price >= tp_price:
                return self._signal(
                    "sell", price, f"take-profit >= {tp_price:.6f}",
                    qty=self.state.position_qty,
                )

        return self._signal("hold", price, "nessun livello toccato")

    def on_fill(
        self,
        side: str,
        price: float,
        qty: float,
        fee: float = 0.0,
        ts: float = 0.0,
    ) -> None:
        """Registra un fill e aggiorna posizione/equity/PnL."""
        if side not in ("buy", "sell"):
            raise DataError(f"side non valido: {side}")
        if price <= 0.0 or qty <= 0.0:
            raise DataError(f"fill non valido: price={price}, qty={qty}")
        if fee < 0.0:
            raise DataError(f"fee negativa: {fee}")

        if side == "buy":
            total_qty = self.state.position_qty + qty
            if total_qty > 0.0:
                self.state.avg_entry = (
                    self.state.position_qty * self.state.avg_entry + qty * price
                ) / total_qty
            self.state.position_qty = total_qty
            self.state.cash -= qty * price + fee
        else:
            if self.state.position_qty > 0.0:
                pnl = (price - self.state.avg_entry) * qty - fee
                self.state.realized_pnl += pnl
                self.state.trades += 1
                if pnl > 0.0:
                    self.state.wins += 1
                self.state.position_qty = max(0.0, self.state.position_qty - qty)
                self.state.cash += qty * price - fee
                self.state.cooldown = self.config.cooldown_ticks
                self.state.killed = False
                if self.state.position_qty == 0.0:
                    self.state.avg_entry = 0.0
                    # griglia ri-centrata dopo ciclo completo
                    self.state.center = price
        self.state.equity = self._mark_to_market(price)
        self.state.peak_equity = max(self.state.peak_equity, self.state.equity)

    def validate_config(self) -> None:
        self.config.validate()

    def estimate_memory_mb(self) -> float:
        """Stato O(1): ATR, center, ~15 float + dict segnale. < 0.1 MB."""
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
            "position_qty": self.state.position_qty,
            "center": round(self.state.center, 6),
            "atr": round(self.state.atr, 6),
        }

    # ------------------------------------------------------------ batch/CSV
    @classmethod
    def from_csv_chunked(
        cls, path: str, config: Optional[GridConfig] = None
    ) -> "AdaptiveVolGrid":
        """Esegue la strategia su un CSV (ts,price[,high,low]) in chunk OOM-safe.

        Usa un generatore per le righe, processa chunk espliciti da
        `csv_chunk_size`, fa `del` sul chunk processato e `gc.collect()` ogni
        `gc_interval` chunk. Ritorna l'istanza con lo stato finale.
        """
        cfg = config or GridConfig()
        grid = cls(cfg)

        def _rows(fh: TextIO) -> Iterator[List[str]]:
            reader = csv.DictReader(fh)
            for row in reader:
                yield row

        chunk: List[Dict[str, str]] = []
        with open(path, "r", newline="", encoding="utf-8") as fh:
            for i, row in enumerate(_rows(fh)):
                chunk.append(row)
                if len(chunk) >= cfg.csv_chunk_size:
                    grid._process_chunk(chunk)
                    del chunk
                    chunk = []
                    if (i // cfg.csv_chunk_size) % cfg.gc_interval == 0:
                        gc.collect()
            if chunk:
                grid._process_chunk(chunk)
                del chunk
                gc.collect()
        return grid

    def _process_chunk(self, chunk: List[Dict[str, str]]) -> None:
        """Processa un chunk di righe CSV (helper di from_csv_chunked)."""
        for row in chunk:
            try:
                ts = float(row.get("ts", 0.0))
                price = float(row["price"])
                high = float(row.get("high", price))
                low = float(row.get("low", price))
            except (KeyError, ValueError) as exc:
                raise DataError(f"riga CSV malformata: {row!r}") from exc
            sig = self.on_tick(price, high=high, low=low, ts=ts)
            if sig["action"] in ("buy", "sell"):
                qty = sig["qty"] if sig["qty"] > 0.0 else self._buy_qty(price)
                if qty > 0.0:
                    fee = qty * price * self.config.fee_rate
                    self.on_fill(sig["action"], price, qty, fee=fee, ts=ts)


if __name__ == "__main__":
    # Test inline con dati sintetici piccoli (range oscillante + drift).
    import random

    logging.basicConfig(level=logging.WARNING)

    cfg = GridConfig(
        capital=13.5,
        levels=4,
        atr_period=10,
        atr_mult=0.5,
        tp_atr_mult=1.5,
        fee_rate=0.0026,
        max_drawdown=0.15,
        cooldown_ticks=3,
    )
    grid = AdaptiveVolGrid(cfg)

    rng = random.Random(7)
    price = 95.0
    mean = 95.0
    n_buys = n_sells = 0
    for i in range(12000):
        # processo OU (Ornstein-Uhlenbeck): oscillazioni ampie attorno a una
        # media lentamente variabile — regime nativo di una griglia mean-reversion
        pull = 0.012 * (mean - price)
        price = max(50.0, price + pull + rng.gauss(0.0, 0.8))
        if i % 500 == 0:
            mean = price + rng.gauss(0.0, 0.4)
        high = price + abs(rng.gauss(0, 0.25))
        low = price - abs(rng.gauss(0, 0.25))
        sig = grid.on_tick(price, high=high, low=low, ts=float(i))
        if sig["action"] == "buy":
            grid.on_fill("buy", price, sig["qty"], fee=price * sig["qty"] * cfg.fee_rate)
            n_buys += 1
        elif sig["action"] == "sell":
            grid.on_fill("sell", price, sig["qty"], fee=price * sig["qty"] * cfg.fee_rate)
            n_sells += 1

    s = grid.stats()
    assert s["trades"] > 0, f"attesi trade, got {s}"
    assert n_buys > 0 and n_sells > 0, f"attesi ingressi ed uscite: buys={n_buys} sells={n_sells}"
    assert s["equity"] > 0.0, f"equity deve restare positiva, got {s['equity']}"
    assert grid.estimate_memory_mb() < 1.0

    # validate_config deve rifiutare config non valide
    bad = GridConfig(levels=0)
    try:
        AdaptiveVolGrid(bad)
        raise AssertionError("attesa ConfigError su levels=0")
    except ConfigError:
        pass

    print(
        f"TEST OK: trades={s['trades']} wins={s['wins']} pnl={s['realized_pnl']:.4f} "
        f"equity={s['equity']:.2f} dd={s['drawdown']:.4f} buys={n_buys} sells={n_sells} "
        f"mem={grid.estimate_memory_mb()}MB"
    )
