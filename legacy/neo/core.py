"""
core.py — Asyncio main loop.

Orchestra:
  - Exchange feed (OHLCV + ticker)
  - Resource monitor (background)
  - Strategy execution
  - State persistence
  - Health server

Loop lifecycle:
  1. Avvia sessioni, WS, monitor
  2. Ogni cooldown_sec: fetch → analizza → execute → save
  3. Graceful shutdown su SIGINT/SIGTERM
"""
from __future__ import annotations
import asyncio, logging, os, signal, time, gc
from typing import Optional

from neo.custom_types import Config, SafeModeLevel
from neo.exchange import ExchangeAdapter
from neo.memory import OhlcvBuffer, TickBuffer, memory_heavy, gc_if_heavy
from neo.monitor import ResourceMonitor
from neo.strategies import GridStrategy, DCAStrategy, ScalpStrategy, StrategySelector
from neo.state import StateStore

log = logging.getLogger("denaro-neo")


class TradingCore:
    """
    Core loop asincrono.
    Tutte le I/O sono non-bloccanti, la memoria è bufferizzata.
    """

    __slots__ = (
        "config", "exchange", "monitor", "store",
        "_ohlcv", "_tick", "_selector",
        "_running", "_loop_interval"
    )

    def __init__(self, config: Config):
        self.config = config
        self.exchange = ExchangeAdapter(
            rate_limit=10.0,
            burst=20,
        )
        self.monitor = ResourceMonitor(
            interval=5.0,
            callback=self._on_safe_mode_change,
        )
        self.store: Optional[StateStore] = None

        # Buffer circolari — maxlen rigidi, mai liste infinite
        self._ohlcv = OhlcvBuffer(maxlen=config.ohlcv_window)
        self._tick = TickBuffer(maxlen=config.tick_window)

        # Strategy
        self._selector = StrategySelector()
        self._selector.register("grid", GridStrategy(config.symbol))
        self._selector.register("dca", DCAStrategy(config.symbol))
        self._selector.register("scalp", ScalpStrategy(config.symbol))

        self._running = False
        self._loop_interval = config.cooldown_sec

    # ── Lifeycle ─────────────────────────────────────────────────────────

    async def start(self) -> None:
        log.info("Starting denaro-neo...")
        self._running = True

        # 1. Exchange session
        await self.exchange.start()

        # 2. State store
        self.store = await StateStore.create(self.config.db_path)

        # 3. Background tasks
        asyncio.create_task(self.monitor.run())
        asyncio.create_task(self._feed_loop())
        asyncio.create_task(self._health_server())

        log.info("Denaro-neo started")

    async def stop(self) -> None:
        log.info("Shutting down denaro-neo...")
        self._running = False
        await self.exchange.stop()
        if self.store:
            await self.store.close()
        gc.collect()
        log.info("Denaro-neo stopped")

    # ── Background feed loop ─────────────────────────────────────────────

    async def _feed_loop(self) -> None:
        """Fetch OHLCV ogni 5 minuti + ticker ogni ciclo."""
        last_fetch = 0.0
        while self._running:
            now = time.time()
            try:
                price = await self._fetch_price()
                if price > 0:
                    self._tick.append(price, 0, int(now), 0)

                if now - last_fetch > 300:  # ogni 5 min
                    await self._fetch_ohlcv()
                    last_fetch = now

            except Exception:
                log.exception("Feed error")
            await asyncio.sleep(5)

    async def _fetch_price(self) -> float:
        """Legge prezzo last trade da WS (o REST fallback)."""
        try:
            r = await self.exchange.get("https://api.kraken.com/0/public/Ticker?pair=DOGEEUR")
            return float(r.get("result", {}).get("XDOGZEUR", {}).get("c", [0])[0])
        except Exception:
            return 0.0

    async def _fetch_ohlcv(self) -> None:
        """Fetch OHLCV 1h, 24 candele, in OhlcvBuffer."""
        try:
            r = await self.exchange.get(
                "https://api.kraken.com/0/public/OHLC?pair=DOGEEUR&interval=60"
            )
            candles = r.get("result", {}).get("XDOGZEUR", [])
            for c in candles[-24:]:
                self._ohlcv.append(
                    int(c[0]), float(c[1]), float(c[2]),
                    float(c[3]), float(c[4]), float(c[5])
                )
        except Exception:
            log.debug("OHLCV fetch failed")

    # ── Main strategy loop ───────────────────────────────────────────────

    async def _execute_cycle(self) -> None:
        """Ciclo principale di trading."""
        if not self.monitor.can_trade:
            log.warning("Safe mode: trade blocked")
            return

        price = self._ohlcv.last_close
        if price <= 0:
            return

        # Calcola ATR usando close array — float32, zero copie
        with memory_heavy("ATR"):
            closes = self._ohlcv.close_array("f")
            atr_pct = self._calculate_atr(closes)

        # Seleziona strategia
        mom_1h = self._ohlcv.close[-1] - self._ohlcv.close[-2] if self._ohlcv.size >= 2 else 0
        strategy_name = self._selector.select(atr_pct, mom_1h, 0.0)
        log.info(f"Cycle: price={price:.6f} atr={atr_pct*100:.2f}% strategy={strategy_name}")

        # Esegui strategia
        strategy = self._selector._strategies.get(strategy_name)
        if strategy:
            signal = await strategy.analyze(
                price, self._ohlcv, 0, 0, self.monitor.state.safe_level
            )
            if signal:
                log.info(f"Signal: {signal.reason}")

        # Persistenza accodata
        if self.store:
            await self.store.execute(
                "INSERT OR REPLACE INTO state (key, value, updated_ts) VALUES (?, ?, ?)",
                ("last_cycle", f"{price:.6f}", int(time.time()))
            )

    @staticmethod
    def _calculate_atr(closes: "array.array") -> float:
        """ATR veloce su close array — float32, niente Pandas."""
        if len(closes) < 14:
            return 0.0
        diffs = [abs(closes[i] - closes[i - 1]) for i in range(1, len(closes))]
        atr = sum(diffs[-14:]) / 14
        atr_pct = atr / closes[-1] if closes[-1] > 0 else 0
        return atr_pct

    # ── Health server ────────────────────────────────────────────────────

    async def _health_server(self) -> None:
        """HTTP health endpoint minimale (asyncio, zero dipendenze)."""
        import asyncio

        async def handler(reader, writer):
            try:
                data = await reader.read(1024)
                path = data.decode().split()[1] if data else "/"
                if path == "/health":
                    body = f'{{"status":"ok","rss_mb":{self.monitor.state.rss_mb:.1f},"safe_level":{self.monitor.state.safe_level.value}}}'
                else:
                    body = '{"error":"not found"}'
                response = f"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {len(body)}\r\n\r\n{body}"
                writer.write(response.encode())
                await writer.drain()
            finally:
                writer.close()

        server = await asyncio.start_unix_server(handler, path="/tmp/denaro-neo.sock")
        log.info(f"Health server ready (unix socket)")

    # ── Safe mode callback ───────────────────────────────────────────────

    def _on_safe_mode_change(self, level: SafeModeLevel) -> None:
        if level >= SafeModeLevel.SAFE:
            log.warning(f"Safe mode {level.name}: clearing caches")
            self._tick.clear()
            gc_if_heavy("safe_mode_clear")
