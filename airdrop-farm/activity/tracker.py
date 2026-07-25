"""Activity tracker - SQLite persistence for idempotency, nonce management, gas tracking."""
import sqlite3
import json
import time
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class ActivityRecord:
    id: Optional[int] = None
    timestamp: float = 0
    wallet_index: int = 0
    wallet_address: str = ""
    chain: str = ""
    strategy: str = ""
    protocol: str = ""
    action: str = ""
    tx_hash: str = ""
    success: bool = False
    gas_used: int = 0
    gas_price_gwei: float = 0
    gas_cost_usd: float = 0
    volume_usd: float = 0
    error: str = ""
    metadata: str = "{}"
    
    def to_dict(self) -> Dict:
        return asdict(self)


class ActivityTracker:
    def __init__(self, db_path: str = "data/activity.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS activities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    wallet_index INTEGER NOT NULL,
                    wallet_address TEXT NOT NULL,
                    chain TEXT NOT NULL,
                    strategy TEXT NOT NULL,
                    protocol TEXT NOT NULL,
                    action TEXT NOT NULL,
                    tx_hash TEXT DEFAULT '',
                    success BOOLEAN NOT NULL,
                    gas_used INTEGER DEFAULT 0,
                    gas_price_gwei REAL DEFAULT 0,
                    gas_cost_usd REAL DEFAULT 0,
                    volume_usd REAL DEFAULT 0,
                    error TEXT DEFAULT '',
                    metadata TEXT DEFAULT '{}'
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_wallet_time 
                ON activities(wallet_index, timestamp)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_chain_strategy 
                ON activities(chain, strategy)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_tx_hash 
                ON activities(tx_hash)
            """)
            
            # Nonce tracking table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS nonces (
                    wallet_address TEXT PRIMARY KEY,
                    chain TEXT NOT NULL,
                    nonce INTEGER NOT NULL DEFAULT 0,
                    updated_at REAL NOT NULL
                )
            """)
            
            # Gas price history
            conn.execute("""
                CREATE TABLE IF NOT EXISTS gas_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chain TEXT NOT NULL,
                    gas_price_gwei REAL NOT NULL,
                    timestamp REAL NOT NULL
                )
            """)
    
    def record(self, record: ActivityRecord) -> int:
        """Record an activity, return row ID."""
        record.timestamp = record.timestamp or time.time()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                INSERT INTO activities 
                (timestamp, wallet_index, wallet_address, chain, strategy, protocol,
                 action, tx_hash, success, gas_used, gas_price_gwei, gas_cost_usd,
                 volume_usd, error, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.timestamp, record.wallet_index, record.wallet_address,
                record.chain, record.strategy, record.protocol, record.action,
                record.tx_hash, record.success, record.gas_used,
                record.gas_price_gwei, record.gas_cost_usd, record.volume_usd,
                record.error, record.metadata
            ))
            return cursor.lastrowid
    
    def get_wallet_stats(self, wallet_index: int, days: int = 30) -> Dict[str, Any]:
        """Get statistics for a wallet."""
        since = time.time() - days * 86400
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT * FROM activities 
                WHERE wallet_index = ? AND timestamp > ?
                ORDER BY timestamp DESC
            """, (wallet_index, since)).fetchall()
        
        if not rows:
            return {"total_actions": 0, "success_rate": 0, "total_gas_usd": 0, "total_volume_usd": 0}
        
        total = len(rows)
        success = sum(1 for r in rows if r["success"])
        gas = sum(r["gas_cost_usd"] for r in rows)
        vol = sum(r["volume_usd"] for r in rows)
        
        by_strategy = {}
        for r in rows:
            s = r["strategy"]
            if s not in by_strategy:
                by_strategy[s] = {"count": 0, "success": 0, "gas": 0, "vol": 0}
            by_strategy[s]["count"] += 1
            if r["success"]: by_strategy[s]["success"] += 1
            by_strategy[s]["gas"] += r["gas_cost_usd"]
            by_strategy[s]["vol"] += r["volume_usd"]
        
        return {
            "total_actions": total,
            "success_rate": success / total if total > 0 else 0,
            "total_gas_usd": round(gas, 2),
            "total_volume_usd": round(vol, 2),
            "by_strategy": {k: {**v, "success_rate": v["success"]/v["count"]} for k, v in by_strategy.items()}
        }
    
    def get_chain_stats(self, chain: str, days: int = 7) -> Dict[str, Any]:
        """Get statistics for a chain."""
        since = time.time() - days * 86400
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT * FROM activities 
                WHERE chain = ? AND timestamp > ?
            """, (chain, since)).fetchall()
        
        if not rows:
            return {"total_actions": 0}
        
        return {
            "total_actions": len(rows),
            "success_rate": sum(r["success"] for r in rows) / len(rows),
            "total_gas_usd": round(sum(r["gas_cost_usd"] for r in rows), 2),
            "total_volume_usd": round(sum(r["volume_usd"] for r in rows), 2)
        }
    
    def get_nonce(self, wallet_address: str, chain: str) -> int:
        """Get current nonce for wallet on chain."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("""
                SELECT nonce FROM nonces 
                WHERE wallet_address = ? AND chain = ?
            """, (wallet_address, chain)).fetchone()
            return row[0] if row else 0
    
    def set_nonce(self, wallet_address: str, chain: str, nonce: int):
        """Update nonce for wallet on chain."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO nonces (wallet_address, chain, nonce, updated_at)
                VALUES (?, ?, ?, ?)
            """, (wallet_address, chain, nonce, time.time()))
    
    def record_gas_price(self, chain: str, gas_price_gwei: float):
        """Record gas price for history."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO gas_history (chain, gas_price_gwei, timestamp)
                VALUES (?, ?, ?)
            """, (chain, gas_price_gwei, time.time()))
    
    def get_avg_gas(self, chain: str, hours: int = 24) -> float:
        """Get average gas price over hours."""
        since = time.time() - hours * 3600
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("""
                SELECT AVG(gas_price_gwei) FROM gas_history
                WHERE chain = ? AND timestamp > ?
            """, (chain, since)).fetchone()
            return row[0] if row and row[0] else 0
    
    def cleanup_old(self, days: int = 90):
        """Remove records older than days."""
        since = time.time() - days * 86400
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM activities WHERE timestamp < ?", (since,))
            conn.execute("DELETE FROM gas_history WHERE timestamp < ?", (since,))


if __name__ == "__main__":
    tracker = ActivityTracker()
    print(f"DB: {tracker.db_path}")
    
    # Test record
    rec = ActivityRecord(
        wallet_index=0,
        wallet_address="0x1234567890123456789012345678901234567890",
        chain="base",
        strategy="airdrop",
        protocol="aerodrome",
        action="swap ETH->AERO",
        tx_hash="0xabc...def",
        success=True,
        gas_used=150000,
        gas_price_gwei=0.5,
        gas_cost_usd=0.85,
        volume_usd=100
    )
    tracker.record(rec)
    print("Recorded:", rec)
    
    print("Stats:", tracker.get_wallet_stats(0))