#!/usr/bin/env python3
"""Denaro — download e cache dei dati OHLCV per il backtest.

I dati vengono salvati in CSV sotto `backtest_data/` (gitignorato) cosi' che
un backtest sia RIPRODUCIBILE senza rete e senza dipendere dall'uptime
dell'exchange.

Uso:
    bars = load_bars("okx", "SOL/EUR", "5m", days=90)
"""
from __future__ import annotations

import csv
import os
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

DEFAULT_CACHE = Path(os.getenv("DENARO_BACKTEST_DATA", "backtest_data"))
MS_DAY = 86_400_000


def make_exchange(name: str, eea: bool = True):
    """Client ccxt PUBBLICO (nessuna chiave) per il download dei dati."""
    import ccxt

    name = name.lower()
    if name == "okx":
        cfg = {"enableRateLimit": True}
        if eea:
            cfg["hostname"] = "eea.okx.com"  # vincolo chiavi EU, vale anche in public
        return ccxt.okx(cfg)
    if name == "kraken":
        return ccxt.kraken({"enableRateLimit": True})
    if name == "binance":
        return ccxt.binance({"enableRateLimit": True})
    raise ValueError(f"exchange non supportato per il backtest: {name}")


def timeframe_ms(exchange, timeframe: str) -> int:
    return int(exchange.parse_timeframe(timeframe)) * 1000


def _cache_path(cache_dir: Path, exchange_name: str, symbol: str,
                timeframe: str) -> Path:
    stem = f"{exchange_name}_{symbol.replace('/', '-')}_{timeframe}.csv"
    return cache_dir / stem


def _read_csv(path: Path) -> List[list]:
    out: List[list] = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.reader(f):
            if not row or row[0] == "ts":
                continue
            out.append([int(row[0]), float(row[1]), float(row[2]),
                        float(row[3]), float(row[4]), float(row[5])])
    return out


def _write_csv(path: Path, bars: Sequence[Sequence[float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".csv.tmp")
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["ts", "open", "high", "low", "close", "volume"])
        for b in bars:
            w.writerow([int(b[0]), f"{b[1]:.10f}", f"{b[2]:.10f}",
                        f"{b[3]:.10f}", f"{b[4]:.10f}", f"{b[5]:.6f}"])
    os.replace(tmp, path)


def fetch_ohlcv(exchange_name: str, symbol: str, timeframe: str,
                since_ms: int, until_ms: Optional[int] = None,
                cache_dir: Optional[Path] = None, refresh: bool = False,
                limit: int = 300, verbose: bool = False) -> List[list]:
    """OHLCV paginati, con cache su disco. Ritorna [[ts,o,h,l,c,v], ...]."""
    cache_dir = Path(cache_dir or DEFAULT_CACHE)
    path = _cache_path(cache_dir, exchange_name, symbol, timeframe)
    until_ms = until_ms or int(time.time() * 1000)

    cached: List[list] = []
    if path.exists() and not refresh:
        try:
            cached = [b for b in _read_csv(path) if since_ms <= b[0] <= until_ms]
        except Exception:
            cached = []
        # cache completa per la finestra richiesta? (margine: 2 barre)
        ex = make_exchange(exchange_name)
        tf = timeframe_ms(ex, timeframe)
        if cached and cached[-1][0] >= until_ms - 2 * tf:
            return cached

    ex = make_exchange(exchange_name)
    tf = timeframe_ms(ex, timeframe)
    start = since_ms
    if cached:
        # riprendi dalla coda della cache (ri-scarica l'ultima barra: puo' essere parziale)
        start = max(since_ms, cached[-1][0])
    bars: List[list] = list(cached)
    cursor = start
    guard = 0
    while cursor < until_ms:
        guard += 1
        if guard > 5000:
            break
        chunk = ex.fetch_ohlcv(symbol, timeframe, since=cursor, limit=limit)
        if not chunk:
            break
        bars.extend([list(b) for b in chunk])
        last = int(chunk[-1][0])
        if last <= cursor:
            break
        cursor = last + tf
        if verbose and guard % 25 == 0:
            print(f"  ... {symbol} {timeframe}: {len(bars)} barre")

    # dedup + ordina
    seen = {}
    for b in bars:
        seen[int(b[0])] = [int(b[0]), float(b[1]), float(b[2]),
                           float(b[3]), float(b[4]), float(b[5])]
    out = [seen[k] for k in sorted(seen) if since_ms <= k <= until_ms]
    _write_csv(path, out)
    return out


def load_bars(exchange_name: str, symbol: str, timeframe: str = "5m",
              days: int = 90, cache_dir: Optional[Path] = None,
              refresh: bool = False, until_ms: Optional[int] = None,
              verbose: bool = False) -> List[list]:
    """Helper: ultimi `days` giorni di barre (cache-aware)."""
    until_ms = until_ms or int(time.time() * 1000)
    return fetch_ohlcv(exchange_name, symbol, timeframe,
                       since_ms=until_ms - days * MS_DAY,
                       until_ms=until_ms, cache_dir=cache_dir,
                       refresh=refresh, verbose=verbose)


_SPECS_CACHE: Dict[str, dict] = {}


def market_specs(exchange_name: str, symbol: str,
                 fallback_min_notional: float = 0.0) -> dict:
    """Minimi e precisioni REALI del mercato (ccxt load_markets, no chiavi).

    Usare i vincoli veri dell'exchange e' essenziale: buona parte della
    storia del progetto e' fatta di ordini mai piazzati perche' sotto il
    minimo di scambio (Kraken SOL 0.06, OKX min_notional ~1 EUR).

    Il risultato e' in cache per (exchange, symbol): un grid search esegue
    decine di run e senza cache ogni run aprirebbe un client + load_markets.
    """
    key = f"{exchange_name}:{symbol}"
    if key in _SPECS_CACHE:
        return dict(_SPECS_CACHE[key])
    import ccxt
    ex = make_exchange(exchange_name)
    try:
        market = ex.load_markets().get(symbol) or {}
        limits = market.get("limits", {}) or {}
        amount_lim = limits.get("amount", {}) or {}
        cost_lim = limits.get("cost", {}) or {}
        prec = market.get("precision", {}) or {}
        min_amount = float(amount_lim.get("min") or 0.0)
        min_notional = float(cost_lim.get("min") or 0.0)
        amount_precision = prec.get("amount")
        price_precision = prec.get("price")
        # ccxt a volte espone la precisione come NUMERO DI DECIMALI (int)
        def _to_step(p: object) -> float:
            if p is None:
                return 0.0
            p = float(p)
            return 10 ** (-int(p)) if p >= 1 else p
        specs = {
            "min_amount": min_amount,
            "min_notional": min_notional or float(fallback_min_notional or 0.0),
            "amount_precision": _to_step(amount_precision) or 1e-8,
            "price_precision": _to_step(price_precision) or 1e-8,
            "contract_size": float(market.get("contractSize") or 0.0),
        }
        _SPECS_CACHE[key] = dict(specs)
        return dict(specs)
    finally:
        try:
            ex.close()
        except Exception:  # noqa: BLE001
            pass
