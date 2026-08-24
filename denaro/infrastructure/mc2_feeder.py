#!/usr/bin/env python3
"""mc2_feeder.py — Data Feeder Centralizzato ZeroMQ (requisito 1 ATLAS v6).

Gira sulla macchina coordinatrice MC2: UNA connessione WebSocket multiplexed
per exchange (Kraken, OKX) e distribuisce i dati standardizzati (ticker +
OHLCV) ai nodi operativi (MARCODG1, nuvola) via ZeroMQ Pub/Sub.

Obiettivi:
- eliminare le WS ridondanti: ogni nodo NON apre piu' la propria connessione
  per lo stesso exchange → -90% di API weight e latenza < 10ms intra-lan
- un unico punto di raccolta OHLCV (candle 1h) per il regime filter ADX/ATR
- standardizzazione del payload: {symbol, price, bid, ask, ts, ...}

Deploy (su mc2, venv /home/sergio/denaro/venv):
    python -m denaro.infrastructure.mc2_feeder --config config/feeder.yaml

ZeroMQ PUB su tcp://0.0.0.0:5557 (ticker) e tcp://0.0.0.0:5558 (ohlcv).
I nodi si collegano con i subscriber (zmq_market_source.py).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import signal
import time
from typing import Any, Dict, List, Optional, Set

log = logging.getLogger("denaro.feeder")

try:
    import zmq
    import zmq.asyncio as zmq_async
except Exception:  # noqa: BLE001 - import opzionale
    zmq = None
    zmq_async = None

# Topic ZeroMQ
TOPIC_TICKER = b"ticker."
TOPIC_OHLCV = b"ohlcv."

# Simboli predefiniti (configurabili da --symbols)
DEFAULT_SYMBOLS = ["SOL/EUR", "ADA/EUR", "XRP/EUR", "DOGE/EUR", "ETH/EUR"]

# porta PUB ticker/ohlcv
TICKER_PORT = 5557
OHLCV_PORT = 5558
OHLCV_TIMEFRAME = "1h"
OHLCV_LIMIT = 200
OHLCV_REFRESH_S = 60.0      # refresh candle ogni 60s (REST) + WS ticker live


class ExchangeFeeder:
    """Una WS per exchange (ccxt.pro watch_ticker) + OHLCV REST periodico."""

    __slots__ = ("name", "pro", "rest", "symbols", "pub_ticker", "pub_ohlcv",
                 "_tasks", "_running")

    def __init__(self, name: str, pro: Any, rest: Any, symbols: List[str],
                 pub_ticker: Any, pub_ohlcv: Any) -> None:
        self.name = name
        self.pro = pro
        self.rest = rest
        self.symbols = symbols
        self.pub_ticker = pub_ticker
        self.pub_ohlcv = pub_ohlcv
        self._tasks: List[asyncio.Task] = []
        self._running = False

    async def start(self) -> None:
        self._running = True
        if self.pro is not None:
            load = getattr(self.pro, "load_markets", None)
            if load:
                try:
                    if asyncio.iscoroutinefunction(load):
                        await load()
                    else:
                        load()
                except Exception as e:  # noqa: BLE001
                    log.warning("%s load_markets fallito: %s", self.name, e)
        for symbol in self.symbols:
            if self.pro is not None:
                self._tasks.append(asyncio.create_task(self._ws_ticker(symbol)))
            # fallback REST ticker: il WS ccxt.pro puo' non emettere eventi su
            # alcuni exchange → il polling garantisce il flusso PUB ticker
            self._tasks.append(asyncio.create_task(self._rest_ticker(symbol)))
            self._tasks.append(asyncio.create_task(self._ohlcv_loop(symbol)))
        log.info("%s feeder avviato: %d simboli, %d task",
                 self.name, len(self.symbols), len(self._tasks))

    async def stop(self) -> None:
        self._running = False
        for t in self._tasks:
            t.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

    # --- ticker WS ------------------------------------------------------------

    async def _ws_ticker(self, symbol: str) -> None:
        """watch_ticker in loop (ccxt.pro coroutine) → PUB ticker."""
        retries = 0
        while self._running:
            try:
                ticker = await self.pro.watch_ticker(symbol)
                payload = {
                    "exchange": self.name,
                    "symbol": symbol,
                    "last": ticker.get("last"),
                    "bid": ticker.get("bid"),
                    "ask": ticker.get("ask"),
                    "pct24h": ticker.get("percentage"),
                    "ts": time.time(),
                }
                self.pub_ticker.send_multipart(
                    [TOPIC_TICKER + symbol.encode(), json.dumps(payload).encode()])
                retries = 0
            except asyncio.CancelledError:
                return
            except Exception as e:  # noqa: BLE001
                retries += 1
                log.warning("%s ws ticker %s: %s (retry %d)",
                            self.name, symbol, type(e).__name__, retries)
                await asyncio.sleep(min(2 ** retries, 30))

    # --- ticker REST fallback -------------------------------------------------

    async def _rest_ticker(self, symbol: str) -> None:
        """Polling ticker REST (5s) → PUB ticker (garanzia di flusso)."""
        while self._running:
            try:
                t = await asyncio.to_thread(self.rest.fetch_ticker, symbol)
                payload = {
                    "exchange": self.name,
                    "symbol": symbol,
                    "last": t.get("last"),
                    "bid": t.get("bid"),
                    "ask": t.get("ask"),
                    "pct24h": t.get("percentage"),
                    "ts": time.time(),
                }
                self.pub_ticker.send_multipart(
                    [TOPIC_TICKER + symbol.encode(), json.dumps(payload).encode()])
            except asyncio.CancelledError:
                return
            except Exception as e:  # noqa: BLE001
                log.warning("%s rest ticker %s: %s", self.name, symbol, e)
            await asyncio.sleep(5.0)

    # --- OHLCV periodico ------------------------------------------------------

    async def _ohlcv_loop(self, symbol: str) -> None:
        """Candle 1h via REST → PUB ohlcv per il regime filter.

        NB: ccxt 4.5.x ha un bug su fetch_ohlcv (OKX ritorna 0 candle, Kraken
        fallisce il parsing del timeframe) → usiamo le RAW API pubbliche.
        """
        while self._running:
            try:
                ohlcv = await asyncio.to_thread(
                    self._fetch_ohlcv_raw, symbol)
                if ohlcv:
                    payload = {"exchange": self.name, "symbol": symbol,
                               "timeframe": OHLCV_TIMEFRAME,
                               "ohlcv": [[float(x) for x in row] for row in ohlcv],
                               "ts": time.time()}
                    self.pub_ohlcv.send_multipart(
                        [TOPIC_OHLCV + symbol.encode(), json.dumps(payload).encode()])
            except Exception as e:  # noqa: BLE001
                log.warning("%s ohlcv %s: %s", self.name, symbol, e)
            await asyncio.sleep(OHLCV_REFRESH_S)

    def _fetch_ohlcv_raw(self, symbol: str) -> List[List[float]]:
        """OHLCV 1h dalle RAW API (bypassa il bug fetch_ohlcv di ccxt 4.5.x)."""
        try:
            m = self.rest.market(symbol)
            inst = m["id"]
        except Exception:
            return []
        if self.name == "okx":
            r = self.rest.publicGetMarketHistoryCandles(
                {"instId": inst, "bar": "1H", "limit": str(OHLCV_LIMIT)})
            data = r.get("data") if isinstance(r, dict) else r
            # OKX: [ts, o, h, l, c, vol, ...] — ts in ms
            return [[int(row[0]) / 1000.0, float(row[1]), float(row[2]),
                     float(row[3]), float(row[4]), float(row[5])]
                    for row in (data or [])]
        if self.name == "kraken":
            r = self.rest.publicGetOHLC({"pair": inst, "interval": 60})
            data = r.get("result") if isinstance(r, dict) else r or {}
            rows = data.get(inst, []) if isinstance(data, dict) else []
            # Kraken: [ts, o, h, l, c, vwap, vol, count] — ts in s
            return [[float(row[0]), float(row[1]), float(row[2]),
                     float(row[3]), float(row[4]), float(row[6])]
                    for row in rows[-OHLCV_LIMIT:]]
        return []


class MC2Feeder:
    """Coordina i feeder per exchange e la vita del processo."""

    __slots__ = ("symbols", "exchanges", "ctx", "pub_ticker", "pub_ohlcv",
                 "feeders", "_tasks")

    def __init__(self, symbols: Optional[List[str]] = None,
                 exchanges: Optional[List[str]] = None) -> None:
        if zmq is None:
            raise RuntimeError("pyzmq non installato: pip install pyzmq")
        self.symbols = symbols or DEFAULT_SYMBOLS
        self.exchanges = exchanges or ["okx", "kraken"]
        self.ctx = zmq_async.Context()
        self.pub_ticker = self.ctx.socket(zmq.PUB)
        self.pub_ticker.bind(f"tcp://0.0.0.0:{TICKER_PORT}")
        self.pub_ohlcv = self.ctx.socket(zmq.PUB)
        self.pub_ohlcv.bind(f"tcp://0.0.0.0:{OHLCV_PORT}")
        self.feeders: List[ExchangeFeeder] = []
        self._tasks: List[asyncio.Task] = []

    def build_exchange(self, name: str) -> tuple:
        """(pro, rest) per un exchange. ccxt.pro per WS; ccxt per REST."""
        import ccxt
        pro = getattr(ccxt, "pro", None)
        if name == "okx":
            rest_cfg = {"enableRateLimit": True, "hostname": "eea.okx.com"}
            pro_cfg = {"hostname": "eea.okx.com", "enableRateLimit": True}
            rest = ccxt.okx(rest_cfg)
            rest.load_markets()
            return (pro.okx(pro_cfg) if pro else None), rest
        if name == "kraken":
            rest = ccxt.kraken({"enableRateLimit": True})
            rest.load_markets()
            return (pro.kraken({"enableRateLimit": True}) if pro else None), rest
        raise ValueError(f"exchange non supportato: {name}")

    async def start(self) -> None:
        for name in self.exchanges:
            try:
                pro, rest = self.build_exchange(name)
            except Exception as e:  # noqa: BLE001
                log.error("exchange %s non inizializzabile: %s", name, e)
                continue
            feeder = ExchangeFeeder(name, pro, rest, self.symbols,
                                    self.pub_ticker, self.pub_ohlcv)
            self.feeders.append(feeder)
            self._tasks.append(asyncio.create_task(feeder.start()))
        log.info("MC2Feeder: %d exchange, %d simboli, PUB :%d/:%d",
                 len(self.feeders), len(self.symbols), TICKER_PORT, OHLCV_PORT)

    async def stop(self) -> None:
        for f in self.feeders:
            await f.stop()
        self.pub_ticker.close()
        self.pub_ohlcv.close()
        self.ctx.term()


async def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="MC2 ZeroMQ Data Feeder")
    parser.add_argument("--symbols", nargs="*", default=DEFAULT_SYMBOLS)
    parser.add_argument("--exchanges", nargs="*", default=["okx", "kraken"])
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO,
                        format="%(asctime)s %(name)s %(levelname)s %(message)s")
    feeder = MC2Feeder(symbols=args.symbols, exchanges=args.exchanges)

    loop = asyncio.get_event_loop()
    stop = asyncio.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            pass

    try:
        await feeder.start()
        log.info("feeder pronto — in attesa (Ctrl+C per fermare)")
        await stop.wait()
    finally:
        await feeder.stop()


if __name__ == "__main__":
    asyncio.run(main())
