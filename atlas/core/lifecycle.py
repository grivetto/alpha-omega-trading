"""ATLAS Core Lifecycle - Graceful shutdown management."""
from __future__ import annotations

import asyncio
import signal
from typing import Any


class GracefulShutdown:
    """Manages graceful shutdown with signal handling."""
    
    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout
        self._shutdown_event = asyncio.Event()
        self._tasks: set[asyncio.Task] = set()
    
    def register_signal_handlers(self) -> None:
        """Register SIGTERM and SIGINT handlers."""
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                loop.add_signal_handler(sig, self._shutdown_event.set)
            except NotImplementedError:
                # Windows doesn't support add_signal_handler
                pass
    
    def _shutdown_event_set(self) -> None:
        """Internal method to set shutdown event."""
        self._shutdown_event.set()
    
    async def wait_for_shutdown(self) -> None:
        """Wait for shutdown signal."""
        await self._shutdown_event.wait()
    
    def create_task(self, coro: Any) -> asyncio.Task:
        """Create a tracked task."""
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task
    
    async def shutdown(self) -> None:
        """Cancel all tracked tasks."""
        if not self._tasks:
            return
        
        for task in self._tasks:
            task.cancel()
        
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
