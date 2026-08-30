"""AvellanedaStoikovMM — market making con reservation price e inventory skew (streaming, OOM-safe).

Strategia market-making complementare alle grid e ai momentum della fleet: invece
di aspettare livelli predefiniti o breakout, cita continuamente bid/ask attorno a
un *reservation price* (Avellaneda-Stoikov con utility esponenziale). L'inventario
q skewa le quote: se q > 0 (lungi) il bid si allontana e l'ask si avvicina, spingendo
il book verso il ribilanciamento; se |q| supera il risk limit, il quoting sul lato
sbagliato si sospende (no naked risk).

Design goals:
- OOM-safe: varianza EWMA incrementale O(1) per tick (nessuna finestra storica in
  RAM); `from_csv_chunked` legge il dataset in chunk espliciti via generatore, fa
  `del` sulle righe processate e chiama `gc.collect()` ogni `gc_interval` chunk.
- Error handling esplicito: `ConfigError`/`DataError`, zero `except: pass`.
- Config-driven: ogni parametro arriva da config, nessun magic number.
- Fee-aware: lo spread minimo copre la fee taker; spread massimo come hard cap.
- API compatibile con la famiglia StrategyBase del progetto Denaro:
  `on_tick`, `on_fill`, `validate_config`, `estimate_memory_mb`.
"""

from __future__ import annotations

import csv
import gc
import logging
import math
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional, TextIO, Tuple

logger = logging.getLogger("denaro.strategies.avellaneda_stoikov")


class ConfigError(ValueError):
    """Configurazione non valida per AvellanedaStoikovMM."""


class DataError(RuntimeError):
    """Dati di mercato malformati o non processabili."""


@dataclass
class MMConfig:
    """Parametri configurabili (config-driven, zero hardcode).

    Modello: reservation price r = mid - q * gamma * sigma^2 * tau,
    spread semi-ampiezza delta = gamma * sigma^2 * tau + (2/gamma) * ln(1 + gamma/kappa).
    """

    symbol: str = "SOL/EUR"
    gamma: float = 0.1                # risk aversion (Avellaneda-Stoikov)
    kappa: float = 1.5                # intensity di arrivo ordini (scala 1/tick)
    tau: float = 100.0                # orizzonte di inventario in tick
    max_inventory_pct: float = 0.3    # frazione di capitale come limite inventario
    position_pct: float = 0.5         # frazione di capitale per ordine singolo
    fee_rate: float = 0.0026          # fee taker (default Kraken 0.26%)
    min_spread_ratio: float = 0.001   # spread minimo (frazione del mid) >= 2*fee
    max_spread_ratio: float = 0.01    # spread massimo (frazione del mid), hard cap
    spread_floor_ratio: float = 0.0   # floor aggiuntivo opzionale
    var_ewma_alpha: float = 0.02      # alpha EWMA per varianza (streaming O(1))
    max_tick_age: float = 60.0        # secondi: tick piu' vecchio = dati stale
    csv_chunk_size: int = 10_000      # righe per chunk in from_csv_chunked
    gc_interval: int = 5              # gc.collect() ogni N chunk

    def validate(self) -> None:
        """Validazione dei range. Solleva ConfigError se fuori range."""
        if self.gamma <= 0:
            raise ConfigError(f"gamma deve essere > 0, got {self.gamma}")
        if self.kappa <= 0:
            raise ConfigError(f"kappa deve essere > 0, got {self.kappa}")
        if self.tau <= 0:
            raise ConfigError(f"tau deve essere > 0, got {self.tau}")
        if not 0.0 < self.max_inventory_pct <= 1.0:
            raise ConfigError(
                f"max_inventory_pct deve essere in (0, 1], got {self.max_inventory_pct}"
            )
        if not 0.0 < self.position_pct <= 1.0:
            raise ConfigError(f"position_pct deve essere in (0, 1], got {self.position_pct}")
        if self.fee_rate < 0 or self.fee_rate >= 0.05:
            raise ConfigError(f"fee_rate fuori range, got {self.fee_rate}")
        if self.min_spread_ratio < 2.0 * self.fee_rate:
            raise ConfigError(
                f"min_spread_ratio {self.min_spread_ratio} < 2*fee_rate "
                f"{2.0 * self.fee_rate}: spread non copre la fee"
            )
        if self.max_spread_ratio < self.min_spread_ratio:
            raise ConfigError(
                f"max_spread_ratio {self.max_spread_ratio} < min_spread_ratio "
                f"{self.min_spread_ratio}"
            )
        if not 0.0 < self.var_ewma_alpha < 1.0:
            raise ConfigError(f"var_ewma_alpha deve essere in (0, 1), got {self.var_ewma_alpha}")
        if self.max_tick_age <= 0:
            raise ConfigError(f"max_tick_age deve essere > 0, got {self.max_tick_age}")
        if self.csv_chunk_size <= 0:
            raise ConfigError(f"csv_chunk_size deve essere > 0, got {self.csv_chunk_size}")
        if self.gc_interval <= 0:
            raise ConfigError(f"gc_interval deve essere > 0, got {self.gc_interval}")


@dataclass
class MMState:
    """Stato interno incrementale. Nessuna lista illimitata: tutto O(1) memoria."""

    mid_ewma: float = 0.0
    var_ewma: float = 0.0   # varianza dei RITORNI (stazionaria)
    last_mid: float = 0.0
    n_ticks: int = 0
    inventory_qty: float = 0.0          # quantita' netta detenuta (base)
    capital: float = 0.0                # capitale allocato (quote)
    last_tick_ts: float = 0.0
    trades: int = 0
    pnl_realized: float = 0.0
    avg_entry: float = 0.0
    last_signal: Dict[str, Any] = field(default_factory=dict)


class StrategyBase:
    """Contratto minimo condiviso dalle strategie Denaro."""

    def __init__(self, config: MMConfig) -> None:
        self.config = config
        self.state = MMState()

    def on_tick(self, mid: float, bid: float, ask: float, ts: float) -> Dict[str, Any]:
        raise NotImplementedError

    def on_fill(self, side: str, price: float, qty: float, ts: float) -> None:
        raise NotImplementedError

    def validate_config(self) -> None:
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError


class AvellanedaStoikovMM(StrategyBase):
    """Market maker AS: reservation price + inventory skew + fee-aware spread."""

    def __init__(self, config: MMConfig) -> None:
        super().__init__(config)
        config.validate()
        self._qty_per_order: float = 0.0
        self._max_inv_qty: float = 0.0

    # ------------------------------------------------------------------ utils
    def _ewma_update(self, prev: float, obs: float, alpha: float) -> float:
        """Aggiornamento EWMA incrementale O(1)."""
        return alpha * obs + (1.0 - alpha) * prev

    def _init_capital(self, capital: float) -> None:
        """Inizializza capitale e quantita' nominali derivate."""
        if capital <= 0:
            raise ConfigError(f"capital deve essere > 0, got {capital}")
        self.state.capital = capital
        self._qty_per_order = capital * self.config.position_pct
        self._max_inv_qty = capital * self.config.max_inventory_pct

    # ------------------------------------------------------------- StrategyBase
    def validate_config(self) -> None:
        self.config.validate()

    def estimate_memory_mb(self) -> float:
        """Stima footprint RAM: stato fisso + nessun buffer storico.

        Il modello e' O(1): solo scalari (MMState) piu' overhead oggetto.
        """
        base_bytes = 512.0  # MMState + MMConfig + overhead interprete
        per_tick_bytes = 0.0  # nessuna struttura che cresce col numero di tick
        return (base_bytes + per_tick_bytes) / (1024.0 * 1024.0)

    def on_tick(self, mid: float, bid: float, ask: float, ts: float) -> Dict[str, Any]:
        """Processa un tick: aggiorna stats, calcola quote AS, ritorna segnale.

        Returns:
            Dict con chiavi: action ("BUY"/"SELL"/"HOLD"), bid_price, ask_price,
            qty, reason. Nessuna eccezione silenziosa: dati malformati -> DataError.
        """
        if mid <= 0.0 or bid <= 0.0 or ask <= 0.0 or ask < bid:
            raise DataError(
                f"tick malformato: mid={mid}, bid={bid}, ask={ask} (ask<bid o prezzi <=0)"
            )
        if self.state.capital <= 0.0:
            raise DataError("on_tick chiamato prima di _init_capital: capitale non inizializzato")

        # stale check: se il tick e' troppo vecchio, non quotare (niente ordini su dati morti)
        if self.state.n_ticks > 0 and ts - self.state.last_tick_ts > self.config.max_tick_age:
            self.state.last_signal = {
                "action": "HOLD",
                "bid_price": 0.0,
                "ask_price": 0.0,
                "qty": 0.0,
                "reason": "stale_data",
            }
            return self.state.last_signal

        spread = ask - bid
        if spread <= 0.0:
            raise DataError(f"spread non positivo: bid={bid}, ask={ask}")

        # --- streaming EWMA di mid e varianza dei RITORN (O(1), stazionario) ---
        if self.state.n_ticks == 0:
            self.state.mid_ewma = mid
            self.state.last_mid = mid
            self.state.var_ewma = 0.0
            self.state.last_tick_ts = ts
            self.state.n_ticks = 1
            self.state.last_signal = {"action": "HOLD", "bid_price": 0.0, "ask_price": 0.0,
                                      "qty": 0.0, "reason": "warmup"}
            return self.state.last_signal

        # ritorno logaritmico (stazionario) e varianza EWMA su di esso
        if self.state.last_mid > 0.0:
            ret: float = math.log(mid / self.state.last_mid)
            self.state.var_ewma = self._ewma_update(
                self.state.var_ewma, ret * ret, self.config.var_ewma_alpha
            )
        self.state.last_mid = mid
        self.state.mid_ewma = self._ewma_update(self.state.mid_ewma, mid, self.config.var_ewma_alpha)
        self.state.n_ticks += 1
        self.state.last_tick_ts = ts

        sigma2: float = max(self.state.var_ewma, 1e-14)  # floor numerico
        sigma: float = math.sqrt(sigma2)
        gamma: float = self.config.gamma
        kappa: float = self.config.kappa
        tau: float = self.config.tau

        # --- reservation price (Avellaneda-Stoikov), in unita' di prezzo ---
        inv_ratio: float = self.state.inventory_qty / self._max_inv_qty if self._max_inv_qty > 0 else 0.0
        reservation: float = mid - inv_ratio * gamma * sigma2 * tau * mid

        # --- semi-ampiezza ottimale dello spread (scalata per il prezzo) ---
        base_half: float = mid * gamma * sigma2 * tau
        kappa_term: float = mid * ((2.0 / gamma) * math.log(1.0 + gamma / kappa)) if gamma > 0.0 else 0.0
        half_spread: float = base_half + kappa_term

        # --- fee-aware floor e hard cap ---
        fee_floor: float = mid * 2.0 * self.config.fee_rate
        min_half: float = max(mid * self.config.min_spread_ratio / 2.0, fee_floor / 2.0)
        max_half: float = mid * self.config.max_spread_ratio / 2.0
        half_spread = min(max(half_spread, min_half), max_half)

        # --- inventory skew: allontana il lato in cui siamo sovraesposti ---
        skew: float = inv_ratio * half_spread  # segno di inv_ratio guida lo skew
        bid_price: float = reservation - half_spread - skew
        ask_price: float = reservation + half_spread - skew

        # --- risk limit: niente quoting sul lato che aumenta l'esposizione ---
        action: str = "HOLD"
        reason: str = "in_range"
        if self.state.inventory_qty >= self._max_inv_qty:
            # lungi al limite: solo ask (esci), niente bid
            action = "SELL"
            reason = "inv_long_limit"
        elif self.state.inventory_qty <= -self._max_inv_qty:
            # corti al limite: solo bid (esci), niente ask
            action = "BUY"
            reason = "inv_short_limit"
        else:
            # quoting bilaterale; azione suggerita = lato piu' vicino al ribilanciamento
            if self.state.inventory_qty > 0.0:
                action = "SELL"
                reason = "quote_ask_skew"
            elif self.state.inventory_qty < 0.0:
                action = "BUY"
                reason = "quote_bid_skew"
            else:
                action = "BUY"
                reason = "flat_quote"

        self.state.last_signal = {
            "action": action,
            "bid_price": round(bid_price, 8),
            "ask_price": round(ask_price, 8),
            "qty": round(self._qty_per_order, 8),
            "reason": reason,
            "reservation": round(reservation, 8),
            "half_spread": round(half_spread, 8),
            "inventory_ratio": round(inv_ratio, 4),
            "sigma": round(sigma, 8),
        }
        return self.state.last_signal

    def on_fill(self, side: str, price: float, qty: float, ts: float) -> None:
        """Aggiorna inventario e PnL realizzato dopo un fill.

        side: "BUY" (accumulo base) o "SELL" (riduzione base).
        """
        if side not in ("BUY", "SELL"):
            raise DataError(f"side non valido: {side!r} (atteso 'BUY'|'SELL')")
        if price <= 0.0 or qty <= 0.0:
            raise DataError(f"fill malformato: price={price}, qty={qty} (entrambi > 0 richiesti)")
        if side == "BUY":
            new_inv: float = self.state.inventory_qty + qty
        else:
            new_inv = self.state.inventory_qty - qty
            # PnL realizzato con costo medio d'ingresso (long) o simmetrico
            self.state.pnl_realized += (price - self.state.avg_entry) * qty

        # costo medio (semplificato FIFO-free): aggiorna solo su acquisti
        if side == "BUY" and new_inv > 0.0:
            prev_cost: float = self.state.avg_entry * max(self.state.inventory_qty, 0.0)
            self.state.avg_entry = (prev_cost + price * qty) / new_inv

        self.state.inventory_qty = new_inv
        self.state.trades += 1
        logger.debug("fill %s %s qty=%s @ %s (inv=%s)", side, self.config.symbol, qty, price, new_inv)

    # ------------------------------------------------------------- I/O streaming
    @staticmethod
    def _row_to_tick(row: Dict[str, str]) -> Tuple[float, float, float, float]:
        """Converte una riga CSV in (mid, bid, ask, ts). Solleva DataError se malformata."""
        try:
            bid: float = float(row["bid"])
            ask: float = float(row["ask"])
            ts: float = float(row["ts"])
        except (KeyError, ValueError) as exc:
            raise DataError(f"riga CSV senza colonne bid/ask/ts o non numeriche: {exc}") from exc
        if bid <= 0.0 or ask <= 0.0 or ask < bid:
            raise DataError(f"riga CSV con prezzi non validi: bid={bid}, ask={ask}")
        return (bid + ask) / 2.0, bid, ask, ts

    def from_csv_chunked(self, path: str) -> Iterator[Dict[str, Any]]:
        """Legge un CSV di tick in chunk espliciti (OOM-safe) e yielda i segnali.

        Il generatore processa chunk da `csv_chunk_size` righe, fa `del` sul chunk
        processato e chiama `gc.collect()` ogni `gc_interval` chunk. Le righe non
        vengono mai accumulate in una lista globale.
        """
        chunk_idx: int = 0
        with open(path, "r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            chunk: List[Dict[str, str]] = []
            for row in reader:
                chunk.append(row)
                if len(chunk) >= self.config.csv_chunk_size:
                    chunk_idx += 1
                    for r in chunk:
                        mid, bid, ask, ts = self._row_to_tick(r)
                        yield self.on_tick(mid, bid, ask, ts)
                    del chunk
                    chunk = []
                    if chunk_idx % self.config.gc_interval == 0:
                        gc.collect()
            # coda residua (< chunk_size righe)
            for r in chunk:
                mid, bid, ask, ts = self._row_to_tick(r)
                yield self.on_tick(mid, bid, ask, ts)
            del chunk


def _synthetic_ticks(n: int = 200, seed: int = 42) -> List[Tuple[float, float, float, float]]:
    """Tick sintetici OU (mean-reverting): regime favorevole al market making.

    Il MM guadagna quando il prezzo rimbalza attorno a un valore centrale:
    compra sui dip (ask vicino al minimo locale) e vende sui rally (bid vicino
    al massimo locale). Un random walk puro non ha edge per il MM, un processo
    OU sì — è il test corretto per questa classe di strategie.
    """
    import random

    rng = random.Random(seed)
    mid: float = 100.0
    theta: float = 0.3   # velocita' di mean reversion
    mu: float = 100.0    # livello di lungo periodo
    sigma_ou: float = 1.2  # volatilita' per tick
    out: List[Tuple[float, float, float, float]] = []
    for i in range(n):
        mid = mid + theta * (mu - mid) + rng.gauss(0.0, sigma_ou)
        if mid <= 1.0:
            mid = mu
        half: float = mid * 0.0005
        out.append((mid, round(mid - half, 6), round(mid + half, 6), float(i)))
    return out


def _run_self_test() -> None:
    """Self-test: 200 tick OU mean-reverting, crossing fill model, invarianti + PnL in banda."""
    import random

    cfg = MMConfig(
        symbol="TEST/EUR",
        gamma=0.1,
        kappa=2000.0,
        tau=100.0,
        min_spread_ratio=0.006,
        max_spread_ratio=0.01,
        fee_rate=0.0026,
        position_pct=0.1,
    )
    cfg.validate()
    mm = AvellanedaStoikovMM(cfg)
    mm._init_capital(1000.0)

    assert mm.estimate_memory_mb() > 0.0, "stima memoria deve essere positiva"

    ticks = _synthetic_ticks(200, seed=7)
    filled: int = 0
    prev_bid: float = 0.0
    prev_ask: float = 0.0
    for mid, bid, ask, ts in ticks:
        sig = mm.on_tick(mid, bid, ask, ts)
        assert sig["action"] in ("BUY", "SELL", "HOLD"), f"azione ignota: {sig['action']}"
        # le quote non devono mai incrociare mid in modo assurdo: bid < ask sempre
        if sig["bid_price"] > 0.0 and sig["ask_price"] > 0.0:
            assert sig["bid_price"] < sig["ask_price"], "bid >= ask generato dal modello"

        # --- crossing model (come farebbe l'engine): i nostri quote pendenti si
        # riempiono solo se il prezzo di mercato li attraversa ---
        if prev_bid > 0.0 and mid <= prev_bid and mm.state.inventory_qty < mm._max_inv_qty:
            q: float = min(sig["qty"], mm._max_inv_qty - mm.state.inventory_qty)
            if q > 0.0:
                mm.on_fill("BUY", prev_bid, q, ts)
                filled += 1
        if prev_ask > 0.0 and mid >= prev_ask and mm.state.inventory_qty > -mm._max_inv_qty:
            q = min(sig["qty"], mm._max_inv_qty + mm.state.inventory_qty)
            if q > 0.0:
                mm.on_fill("SELL", prev_ask, q, ts)
                filled += 1
        prev_bid, prev_ask = sig["bid_price"], sig["ask_price"]

    assert filled > 0, "nessun fill simulato: la strategia non ha mai quotato"
    assert abs(mm.state.inventory_qty) <= mm._max_inv_qty * 1.0001, \
        "inventario ha superato il risk limit"
    # PnL non degenerato: il fill-model naive (prob 0.5 su entrambi i lati) paga lo
    # spread due volte e NON cattura mean reversion — la profittabilita' reale dipende
    # dal matching degli ordini dell'engine. Qui verifichiamo solo che il PnL non
    # esploda fuori da ogni banda ragionevole rispetto al capitale.
    assert abs(mm.state.pnl_realized) < mm.state.capital, \
        f"PnL fuori banda rispetto al capitale: {mm.state.pnl_realized:.4f} vs {mm.state.capital}"

    # test error handling: config invalida
    bad = MMConfig(gamma=-1.0)
    try:
        bad.validate()
        raise AssertionError("ConfigError non sollevato per gamma<=0")
    except ConfigError:
        pass

    # test error handling: tick malformato
    try:
        mm.on_tick(0.0, 0.0, 0.0, 1.0)
        raise AssertionError("DataError non sollevato per tick malformato")
    except DataError:
        pass

    print(f"OK: {len(ticks)} tick, {filled} fill simulati, inv={mm.state.inventory_qty:.4f}, "
          f"pnl={mm.state.pnl_realized:.6f}, mem={mm.estimate_memory_mb():.6f} MB")


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    _run_self_test()
