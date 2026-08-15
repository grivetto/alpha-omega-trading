"""
state.py — Persistenza SQLite asincrona con WAL per Alpha-Omega.

- aiosqlite per I/O non bloccante
- WAL mode per letture/scritture concorrenti
- Queue di scrittura per evitare lock contention
- Schema migration automatica

Principio: nessuna I/O bloccante nel loop principale.
Tutte le writes sono accodate e processate in background.
"""
from __future__ import annotations
import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Optional, List, Dict, Any

log = logging.getLogger("alpha_omega.state")

try:
    import aiosqlite
except ImportError:
    log.critical("aiosqlite required — pip install aiosqlite")
    raise


_SCHEMA = """
CREATE TABLE IF NOT EXISTS trades (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol      TEXT NOT NULL,
    side        TEXT NOT NULL,
    entry_price REAL NOT NULL,
    exit_price  REAL,
    amount      REAL NOT NULL,
    pnl_pct     REAL,
    pnl_abs     REAL,
    entry_ts    INTEGER NOT NULL,
    exit_ts     INTEGER,
    status      TEXT NOT NULL DEFAULT 'open',
    strategy    TEXT NOT NULL DEFAULT 'grid'
);

CREATE TABLE IF NOT EXISTS orders (
    id          TEXT PRIMARY KEY,
    symbol      TEXT NOT NULL,
    side        TEXT NOT NULL,
    price       REAL NOT NULL,
    amount      REAL NOT NULL,
    filled      REAL NOT NULL DEFAULT 0,
    status      TEXT NOT NULL DEFAULT 'pending',
    created_ts  INTEGER NOT NULL,
    updated_ts  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS state (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    updated_ts  INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);
CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status);
CREATE INDEX IF NOT EXISTS idx_orders_status  ON orders(status);
"""


class StateStore:
    """
    SQLite async con WAL e write queue.
    Le writes sono bufferizzate e flushate ogni ~1s o quando la queue
    supera 100 elementi — mai una write per trade.

    Uso:
        store = await StateStore.create("denaro_neo.db")
        await store.queue_write("INSERT INTO trades ...", params)
        await store.flush()  # opzionale, flush automatico ogni 1s
        await store.close()
    """

    __slots__ = (
        "_db", "_queue", "_flush_interval",
        "_flush_threshold", "_flush_task", "_closed"
    )

    def __init__(self, db_path: str = "denaro_neo.db"):
        self._db: Optional[aiosqlite.Connection] = None
        self._queue: List[tuple[str, tuple]] = []
        self._flush_interval: float = 1.0
        self._flush_threshold: int = 100
        self._flush_task: Optional[asyncio.Task] = None
        self._closed = False

    @classmethod
    async def create(cls, db_path: str = "denaro_neo.db") -> StateStore:
        self = cls(db_path)
        # Crea directory se non esiste
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        self._db = await aiosqlite.connect(
            db_path,
            timeout=10.0,       # timeout lock
            check_same_thread=False,
        )
        self._db.row_factory = aiosqlite.Row

        # WAL mode — letture e scritture NON bloccanti
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute("PRAGMA synchronous=NORMAL")
        await self._db.execute("PRAGMA busy_timeout=5000")
        await self._db.execute("PRAGMA cache_size=-4000")  # 4MB cache

        # Schema migration
        await self._db.executescript(_SCHEMA)
        await self._db.commit()

        # Background flush task
        self._flush_task = asyncio.create_task(self._flush_loop())
        log.info(f"State store ready: {db_path} (WAL)")
        return self

    # Write queue

    async def execute(self, sql: str, params: tuple = ()) -> None:
        """Write accodata (non bloccante)."""
        if self._closed:
            return
        self._queue.append((sql, params))
        if len(self._queue) >= self._flush_threshold:
            await self._flush()

    async def executemany(self, sql: str, params_list: List[tuple]) -> None:
        """Multiple writes accodate."""
        if self._closed:
            return
        for params in params_list:
            self._queue.append((sql, params))
        if len(self._queue) >= self._flush_threshold:
            await self._flush()

    async def _flush(self) -> None:
        """Flush queue sul DB."""
        if not self._queue or not self._db:
            return
        batch = self._queue
        self._queue = []
        try:
            for sql, params in batch:
                await self._db.execute(sql, params)
            await self._db.commit()
        except Exception as e:
            log.error(f"State flush failed: {e}")
            # Re-accoda in caso di fallimento
            self._queue = batch + self._queue
            self._queue = self._queue[:1000]  # cap a 1000 per non OOM

    async def _flush_loop(self) -> None:
        """Background flush ogni _flush_interval secondi."""
        while not self._closed:
            await asyncio.sleep(self._flush_interval)
            try:
                await self._flush()
            except Exception:
                log.exception("Background flush error")

    # Letture (non accodate, accesso diretto)

    async def fetch_one(self, sql: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        if not self._db:
            return None
        cursor = await self._db.execute(sql, params)
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def fetch_all(self, sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
        if not self._db:
            return []
        cursor = await self._db.execute(sql, params)
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    # State key-value

    async def set_state(self, key: str, value: str) -> None:
        await self.execute(
            "INSERT OR REPLACE INTO state (key, value, updated_ts) VALUES (?, ?, ?)",
            (key, value, int(time.time()))
        )

    async def get_state(self, key: str) -> Optional[str]:
        row = await self.fetch_one("SELECT value FROM state WHERE key = ?", (key,))
        return row["value"] if row else None

    async def set_json(self, key: str, value: dict) -> None:
        await self.set_state(key, json.dumps(value))

    async def get_json(self, key: str) -> Optional[dict]:
        val = await self.get_state(key)
        return json.loads(val) if val else None

    # Methods for engine state loading

    async def get_equity_curve(self, node: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get equity curve data for a node."""
        # Query trades table for equity curve data
        rows = await self.fetch_all(
            """
            SELECT 
                COALESCE(SUM(pnl_abs), 0) as total_pnl,
                COALESCE(SUM(CASE WHEN pnl_abs > 0 THEN pnl_abs ELSE 0 END), 0) as realized_pnl,
                0 as unrealized_pnl,
                0 as drawdown,
                COALESCE(SUM(amount * exit_price), 0) as total_equity,
                MAX(exit_ts) as timestamp
            FROM trades 
            WHERE status = 'closed' AND exit_ts IS NOT NULL
            ORDER BY exit_ts DESC
            LIMIT ?
            """,
            (limit,)
        )
        return rows

    async def get_open_positions(self) -> List[Dict[str, Any]]:
        """Get all open positions."""
        rows = await self.fetch_all(
            """
            SELECT 
                symbol, '' as exchange, side, '' as base, '' as quote,
                amount as size, entry_price, exit_price as current_price,
                pnl_abs as unrealized_pnl, 0 as realized_pnl,
                entry_ts, strategy
            FROM trades 
            WHERE status = 'open'
            """)
        return rows

    async def get_open_orders(self, symbol: str) -> List[Dict[str, Any]]:
        """Get open orders for a symbol."""
        rows = await self.fetch_all(
            """
            SELECT 
                id, symbol, '' as exchange, side, 'limit' as type,
                price, amount, filled, status, 0 as fee, '' as fee_currency,
                created_ts, '' as strategy
            FROM orders 
            WHERE symbol = ? AND status IN ('pending', 'open', 'partial')
            """,
            (symbol,)
        )
        return rows

    async def save_equity(self, data: Dict[str, Any]) -> None:
        """Save equity snapshot to state table."""
        import json
        key = f"equity_{data.get('node', 'unknown')}"
        await self.set_json(key, data)

    async def save_position(self, data: Dict[str, Any]) -> None:
        """Save position to state table."""
        import json
        key = f"position_{data.get('symbol', 'unknown')}"
        await self.set_json(key, data)

    async def save_risk_metrics(self, data: Dict[str, Any]) -> None:
        """Persist a risk event (e.g. kill switch) to the state table."""
        import time as _t
        key = f"risk_{data.get('event', 'event')}_{int(_t.time() * 1000)}"
        await self.set_json(key, data)

    async def close(self) -> None:
        """Close the state store."""
        self._closed = True
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        await self._flush()
        if self._db:
            await self._db.close()
            self._db = None


# Global state store instance
_state_store: Optional[StateStore] = None


async def init_state_store(db_path: str = "denaro_neo.db", redis_url: Optional[str] = None, consumer_group: str = "alpha_omega", consumer_name: str = "engine") -> StateStore:
    """Initialize global state store.
    
    Args:
        db_path: SQLite database path
        redis_url: Redis connection URL (optional, for future Redis Streams support)
        consumer_group: Redis consumer group name (optional)
        consumer_name: Redis consumer name (optional)
    """
    global _state_store
    _state_store = await StateStore.create(db_path)
    return _state_store


async def get_state_store() -> Optional[StateStore]:
    """Get global state store instance."""
    return _state_store


async def close_state_store() -> None:
    """Close global state store."""
    global _state_store
    if _state_store:
        await _state_store.close()
        _state_store = None