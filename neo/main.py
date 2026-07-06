#!/usr/bin/env python3
"""
denaro-neo — Entry point.
Memory-first async trading bot.

Usage:
    python main.py                    # Default config
    python main.py --symbol SOL/EUR   # Custom pair
"""
from __future__ import annotations
import asyncio, logging, os, signal, sys, time
from pathlib import Path

# Load .env
for p in [Path(__file__).parent / ".env", Path.home() / "denaro" / ".env"]:
    if p.exists():
        with open(p) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    v = v.strip().strip('"').strip("'")
                    if k not in os.environ:
                        os.environ[k] = v
        break

from neo.types import Config
from neo.core import TradingCore


def setup_logging(level: str = "WARNING") -> None:
    """Log a bassa verbosità — solo warning/error in produzione."""
    root = logging.getLogger()
    root.setLevel(getattr(logging, level, logging.WARNING))

    # File handler con rotazione
    fh = logging.handlers.RotatingFileHandler(
        "denaro-neo.log", maxBytes=1_000_000, backupCount=2
    )
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root.addHandler(fh)

    # Stderr handler — solo ERROR
    sh = logging.StreamHandler(sys.stderr)
    sh.setLevel(logging.ERROR)
    sh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    root.addHandler(sh)


def main() -> None:
    # Config da env
    config = Config(
        symbol=os.environ.get("SYMBOL", "DOGE/EUR"),
        capital=float(os.environ.get("CAPITAL", "100.0")),
        grid_levels=int(os.environ.get("LEVELS", "5")),
        grid_spread=float(os.environ.get("SPREAD", "0.025")),
        cooldown_sec=int(os.environ.get("COOLDOWN", "30")),
        log_level=os.environ.get("LOG_LEVEL", "WARNING"),
    )

    setup_logging(config.log_level)
    log = logging.getLogger("denaro-neo.main")
    log.info(f"Starting denaro-neo | {config.symbol} | {config.capital} EUR")

    core = TradingCore(config)

    # Signal handler
    shutdown = {"flag": False}

    def _handle(sig, frame):
        if shutdown["flag"]:
            log.warning("Second signal — force exit")
            sys.exit(1)
        log.info(f"Signal {sig} — graceful shutdown...")
        shutdown["flag"] = True

    signal.signal(signal.SIGTERM, _handle)
    signal.signal(signal.SIGINT, _handle)

    # Event loop
    async def _run():
        await core.start()
        while not shutdown["flag"]:
            try:
                await core._execute_cycle()
            except Exception:
                log.exception("Cycle error")
            await asyncio.sleep(config.cooldown_sec)
        await core.stop()

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        pass

    log.info("Denaro-neo stopped.")


if __name__ == "__main__":
    main()
