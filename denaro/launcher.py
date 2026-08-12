#!/usr/bin/env python3
"""Denaro v6 — shared launcher used by both `main.py` and `python -m denaro`.

Bootstraps: logging → health server → engine (real or mock) → DenaroCore →
orphan cleanup → signal handlers → orchestrator loop → graceful shutdown.
"""
from __future__ import annotations

import logging
import os
import signal
import sys
import time
from pathlib import Path
from typing import Optional

from .config import DenaroConfig
from .core import DenaroCore
from .logging_setup import setup_logging
from .orchestrator import DenaroOrchestrator

log = logging.getLogger("kraken_v2")


def _load_dotenv() -> None:
    """Load .env into os.environ (first match wins, no override)."""
    for p in [Path(__file__).resolve().parent.parent / ".env",
              Path.home() / "denaro" / ".env",
              Path(".env")]:
        if p.exists():
            try:
                with open(p) as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            v = v.strip().strip('"').strip("'")
                            if k not in os.environ:
                                os.environ[k] = v
            except OSError:
                pass
            break


def _build_engine(cfg: DenaroConfig):
    """Real KrakenEngine or MockKrakenEngine, with credential validation."""
    if cfg.mock_mode:
        from mock_runner import MockKrakenEngine
        engine = MockKrakenEngine(initial_eur=cfg.capital)
        log.info("MOCK_MODE enabled")
        return engine

    env = os.environ
    api_key = env.get("KRAKEN_API") or ""
    api_secret = env.get("KRAKEN_SECRET") or ""
    if not api_key or not api_secret:
        log.critical("KRAKEN_API or KRAKEN_SECRET not found")
        raise SystemExit(1)

    from kraken_engine import KrakenEngine, KrakenPermanentError
    try:
        return KrakenEngine(api_key, api_secret, symbol=cfg.symbol)
    except KrakenPermanentError as e:
        log.critical(f"Kraken credentials invalid: {e}")
        raise SystemExit(1)
    except Exception as e:
        log.critical(f"Engine init: {e}")
        raise SystemExit(1)


def run_main(cfg: Optional[DenaroConfig] = None) -> int:
    """Run the Denaro v6 bot. Returns process exit code."""
    _load_dotenv()
    cfg = cfg if cfg is not None else DenaroConfig.from_env()
    setup_logging(cfg.log_file)

    for w in cfg.validate():
        log.warning(f"Config warning: {w}")
    log.info(f"Starting Denaro v6 | {cfg.symbol} | CAPITAL={cfg.capital}")

    # ── Health server ──
    health = None
    try:
        from enhanced.health_server import HealthServer
        health = HealthServer(port=cfg.health_port)
        health.start()
        health.update(mode="SHADOW" if cfg.shadow_mode else "MOCK" if cfg.mock_mode else "LIVE",
                      max_levels=8, symbol=cfg.symbol)
        health.set_degraded("starting")
    except Exception as e:
        log.warning(f"Health server: {e}")

    # ── Startup notification ──
    try:
        from notifier import notify_startup
        notify_startup(cfg.symbol,
                       "SHADOW" if cfg.shadow_mode else "MOCK" if cfg.mock_mode else "LIVE",
                       cfg.capital)
    except Exception:
        pass

    # ── Engine + core ──
    engine = _build_engine(cfg)
    core = DenaroCore(
        initial_capital=cfg.capital,
        daily_loss_limit=cfg.daily_loss_pct,
        max_drawdown_limit=cfg.max_drawdown_pct,
        max_consecutive_losses=cfg.max_consecutive_losses,
        compound_ratio=cfg.compound_ratio,
        state_path=cfg.core_state_file,
        kelly_cap=cfg.kelly_cap,
        dump_threshold_mult=cfg.dump_threshold_mult,
        dump_volume_ratio=cfg.dump_volume_ratio,
        dump_recovery_cycles=cfg.dump_recovery_cycles,
    )
    log.info(f"Core loaded: {cfg.core_state_file} | DD={cfg.max_drawdown_pct * 100:.0f}% "
             f"DL={cfg.daily_loss_pct * 100:.0f}% CL={cfg.max_consecutive_losses}")

    if not cfg.mock_mode:
        log.info("Cancelling orphan orders...")
        try:
            engine.cancel_all_orders(cfg.symbol)
            log.info("Orphan orders cancelled ✓")
        except Exception as e:
            log.warning(f"Cancel orphans: {e}")

    orchestrator = DenaroOrchestrator(engine, core, cfg)

    shutdown = {"flag": False}

    def _handle(sig, frame):
        if shutdown["flag"]:
            log.warning("Second signal — force exit")
            sys.exit(1)
        log.info(f"Signal {sig} — graceful shutdown...")
        shutdown["flag"] = True

    signal.signal(signal.SIGTERM, _handle)
    signal.signal(signal.SIGINT, _handle)

    try:
        ok = orchestrator.run_forever(shutdown, health=health)
    except KeyboardInterrupt:
        ok = True
    finally:
        if health:
            try:
                health.set_down("shutdown")
                health.stop()
            except Exception:
                pass
        orchestrator.shutdown()

    return 0 if ok else 1
