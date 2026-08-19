"""ATLAS Main Entry Point - Application lifecycle and dependency injection."""
from __future__ import annotations

import asyncio
import logging
import signal
import sys
from contextlib import asynccontextmanager
from typing import AsyncIterator

import structlog

from atlas.core.config import settings
from atlas.core.lifecycle import GracefulShutdown
from atlas.observability.logging import configure_logging


# Configure structured logging
configure_logging(json_output=settings.log_json, level=settings.log_level)
logger = structlog.get_logger(__name__)


class AtlasApplication:
    """Main application class managing lifecycle and components."""
    
    def __init__(self):
        self.shutdown = GracefulShutdown(timeout=10.0)
        self._running = False
        self._tasks: set[asyncio.Task] = set()
    
    async def initialize(self) -> None:
        """Initialize all components."""
        logger.info("Initializing ATLAS trading bot", version="0.1.0", env=settings.env)
        # TODO: Initialize connectors, strategies, portfolio manager, etc.
        logger.info("Components initialized")
    
    async def start(self) -> None:
        """Start the main trading loop."""
        self._running = True
        self.shutdown.register_signal_handlers()
        
        # TODO: Start market data streams, strategy engine, execution engine
        
        logger.info("ATLAS started successfully")
        
        # Wait for shutdown signal
        await self.shutdown.wait_for_shutdown()
        
        await self.stop()
    
    async def stop(self) -> None:
        """Graceful shutdown."""
        if not self._running:
            return
        
        self._running = False
        logger.info("Shutting down ATLAS...")
        
        # Cancel all tasks
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
        logger.exception("Fatal error", error=str(e))
        sys.exit(1)
    finally:
        await app.stop()


if __name__ == "__main__":
    asyncio.run(main())
