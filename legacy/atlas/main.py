"""ATLAS Main Entry Point - Application lifecycle and dependency injection."""
from __future__ import annotations

import asyncio
import logging
import os
import re
import sys
from pathlib import Path

import yaml
from aiohttp import web

from atlas.core.config import settings
from atlas.core.lifecycle import GracefulShutdown
from atlas.core.events import EventBus
from atlas.connector.ccxt_adapter import CCXTAdapter
from atlas.portfolio.manager import ExchangeRegistry, PortfolioManager
from atlas.strategy.engine import StrategyEngine
from atlas.execution.router import ExecutionRouter
from atlas.observability.logging import configure_logging

logger = logging.getLogger(__name__)

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"

# OKX EEA hostname mapping (extra.eea: true -> hostname)
EEA_HOSTNAMES = {"okx": "eea.okx.com"}


def _load_dotenv(path: Path) -> None:
    """Load .env into os.environ (no overwrite of existing vars)."""
    if not path.exists():
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            if key and key not in os.environ:
                os.environ[key] = value


def _env_substitute(value):
    """Recursively substitute ${VAR} placeholders with environment values."""
    if isinstance(value, str):
        pattern = re.compile(r"\$\{([A-Z0-9_]+)\}")
        def repl(match):
            return os.environ.get(match.group(1), match.group(0))
        return pattern.sub(repl, value)
    if isinstance(value, dict):
        return {k: _env_substitute(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_env_substitute(v) for v in value]
    return value


def _load_yaml_env(path: Path) -> dict:
    """Load YAML with ${VAR} environment substitution."""
    with open(path) as f:
        data = yaml.safe_load(f)
    return _env_substitute(data)


class AtlasApplication:
    """Main application class managing lifecycle and components."""

    def __init__(self):
        self.shutdown = GracefulShutdown(timeout=10.0)
        self._running = False
        self._tasks: set[asyncio.Task] = set()
        self._health_runner: web.AppRunner | None = None

        # Core components
        self.event_bus = EventBus()
        self.exchange_registry = ExchangeRegistry()
        self.portfolio_manager: PortfolioManager | None = None
        self.strategy_engine: StrategyEngine | None = None
        self.execution_router: ExecutionRouter | None = None

    async def _init_exchanges(self) -> None:
        """Initialize exchange connectors from config/exchanges.yaml."""
        ex_data = _load_yaml_env(CONFIG_DIR / "exchanges.yaml")

        for ex_config in ex_data.get("exchanges", []):
            name = ex_config["name"]
            hostname = ""
            extra = ex_config.get("extra") or {}
            if extra.get("eea") and name in EEA_HOSTNAMES:
                hostname = EEA_HOSTNAMES[name]
                logger.info(f"Using EEA hostname for {name}: {hostname}")

            adapter = CCXTAdapter(
                exchange_id=name,
                api_key=ex_config.get("api_key", ""),
                api_secret=ex_config.get("api_secret", ""),
                passphrase=ex_config.get("passphrase", "") or "",
                sandbox=ex_config.get("sandbox", False),
                testnet=ex_config.get("testnet", False),
                rate_limit_rps=ex_config.get("rate_limit_rps", 5.0),
                rate_limit_burst=ex_config.get("rate_limit_burst", 10),
                hostname=hostname,
            )
            try:
                await adapter.connect()
                self.exchange_registry.register(name, adapter)
                logger.info(f"Exchange connected: {name}")
            except Exception as e:
                logger.error(f"Exchange {name} connection FAILED: {e}")
                # Don't crash the whole bot on one bad exchange

    async def _init_strategies(self) -> None:
        """Register strategies from config/strategies.yaml."""
        strat_data = _load_yaml_env(CONFIG_DIR / "strategies.yaml")
        for strat_config in strat_data.get("strategies", []):
            if not strat_config.get("enabled", True):
                continue
            if not self.strategy_engine:
                continue
            await self.strategy_engine.add_strategy(strat_config)
            logger.info(f"Strategy configured: {strat_config['strategy_id']}")

    async def initialize(self) -> None:
        """Initialize all components."""
        logger.info(f"Initializing ATLAS trading bot env={settings.env}")

        # Load .env into os.environ so YAML ${VAR} substitution works
        _load_dotenv(Path(__file__).resolve().parent.parent / ".env")

        await self._init_exchanges()

        # Portfolio manager (risk engine)
        self.portfolio_manager = PortfolioManager(
            exchange_registry=self.exchange_registry,
            risk_config=settings.risk,
        )
        await self.portfolio_manager.initialize()

        # Execution router
        self.execution_router = ExecutionRouter(
            exchange_registry=self.exchange_registry,
            portfolio_manager=self.portfolio_manager,
            event_bus=self.event_bus,
        )

        # Strategy engine
        self.strategy_engine = StrategyEngine(
            exchange_registry=self.exchange_registry,
            portfolio_manager=self.portfolio_manager,
            execution_router=self.execution_router,
            event_bus=self.event_bus,
        )

        await self._init_strategies()

        # Start event bus
        await self.event_bus.start()

        logger.info("Components initialized")

    async def _health_handler(self, request: web.Request) -> web.Response:
        return web.json_response({
            "status": "healthy",
            "service": "atlas-engine",
            "exchanges": self.exchange_registry.names,
            "strategies": self.strategy_engine.strategy_ids if self.strategy_engine else [],
        })

    async def _ready_handler(self, request: web.Request) -> web.Response:
        ready = (
            self._running
            and len(self.exchange_registry.names) > 0
            and self.portfolio_manager is not None
            and self.strategy_engine is not None
        )
        return web.json_response({
            "ready": ready,
            "service": "atlas-engine",
        })

    async def _start_health_server(self) -> None:
        """Start health check HTTP server."""
        app = web.Application()
        app.router.add_get("/health", self._health_handler)
        app.router.add_get("/ready", self._ready_handler)

        self._health_runner = web.AppRunner(app)
        await self._health_runner.setup()
        # Dual-stack esplicito: bind IPv4 (0.0.0.0) E IPv6 (::).
        # Il watchdog controlla 127.0.0.1:8080 -> senza bind IPv4 non lo vede mai.
        started_hosts = []
        for host in ("0.0.0.0", "::"):
            try:
                site = web.TCPSite(self._health_runner, host, settings.health_port)
                await site.start()
                started_hosts.append(host)
            except Exception as e:
                logger.warning(f"Health server bind fallito su {host}: {e}")
        if not started_hosts:
            raise RuntimeError("Nessun indirizzo disponibile per il health server")
        logger.info(f"Health server started on {started_hosts}:{settings.health_port}")

    async def start(self) -> None:
        """Start the main trading loop."""
        self._running = True
        self.shutdown.register_signal_handlers()

        await self._start_health_server()

        if self.strategy_engine:
            await self.strategy_engine.start()

        logger.info("ATLAS started successfully")

        await self.shutdown.wait_for_shutdown()

        await self.stop()

    async def stop(self) -> None:
        """Graceful shutdown."""
        if not self._running:
            return

        self._running = False
        logger.info("Shutting down ATLAS...")

        if self.strategy_engine:
            await self.strategy_engine.stop()

        await self.event_bus.stop()

        if self._health_runner:
            await self._health_runner.cleanup()

        for adapter in self.exchange_registry.all():
            await adapter.disconnect()

        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

        logger.info("ATLAS stopped")


async def main() -> None:
    """Main entry point."""
    app = AtlasApplication()

    try:
        await app.initialize()
        await app.start()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    except Exception as e:
        logger.exception("Fatal error: %s", e)
        sys.exit(1)
    finally:
        await app.stop()


if __name__ == "__main__":
    asyncio.run(main())
