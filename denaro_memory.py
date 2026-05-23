#!/usr/bin/env python3
"""
Denaro Memory — Shared SQLite DB for trade memory, regime, and strategy optimization
Runs on mc2. Populated by collector, queried by bots and optimizer.
"""
import json, sqlite3, time, os
from pathlib import Path
from datetime import datetime, timezone

BASE = Path(__file__).parent
DB_PATH = BASE / "denaro_memory.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bot TEXT NOT NULL, symbol TEXT NOT NULL, side TEXT NOT NULL,
    price REAL NOT NULL, amount REAL NOT NULL,
    eur_value REAL NOT NULL, fee REAL DEFAULT 0,
    net_pnl REAL DEFAULT 0,
    market_volatility REAL DEFAULT 0,
    market_regime TEXT DEFAULT 'unknown',
    bot_params TEXT DEFAULT '{}',
    trade_id INTEGER UNIQUE,
    filled_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_trades_trade_id ON trades(trade_id);
CREATE TABLE IF NOT EXISTS daily_pnl (
    day TEXT NOT NULL, bot TEXT NOT NULL,
    pnl REAL DEFAULT 0, trades INTEGER DEFAULT 0,
    fees REAL DEFAULT 0,
    PRIMARY KEY (day, bot)
);
CREATE TABLE IF NOT EXISTS bot_params (
    bot TEXT PRIMARY KEY,
    params TEXT NOT NULL DEFAULT '{}',
    score REAL DEFAULT 0,
    updated_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS regime_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    regime TEXT NOT NULL, volatility REAL DEFAULT 0,
    trend_strength REAL DEFAULT 0, volume_ratio REAL DEFAULT 0,
    details TEXT DEFAULT '{}',
    detected_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS capital_alloc (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bot TEXT NOT NULL, eur_alloc REAL NOT NULL,
    rationale TEXT DEFAULT '',
    decided_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_trades_bot ON trades(bot);
CREATE INDEX IF NOT EXISTS idx_trades_filled ON trades(filled_at);
CREATE INDEX IF NOT EXISTS idx_regime_time ON regime_log(detected_at);
"""


class DenaroMemory:
    def __init__(self, db_path=None):
        self.path = Path(db_path or DB_PATH)
        self._conn = None
        self._init()

    def _conn_get(self):
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.path), timeout=10, check_same_thread=False)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA busy_timeout=5000")
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _init(self):
        c = self._conn_get()
        c.executescript(SCHEMA)
        c.commit()

    # ── Trade Recording ──
    def record_trade(self, bot, symbol, side, price, amount, eur_value,
                     fee=0, net_pnl=0, volatility=0, regime="unknown",
                     params=None, trade_id=None, filled_at=None):
        c = self._conn_get()
        c.execute("""INSERT OR IGNORE INTO trades
            (bot, symbol, side, price, amount, eur_value, fee, net_pnl,
             market_volatility, market_regime, bot_params, trade_id, filled_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,COALESCE(?, datetime('now')))""",
            (bot, symbol, side, price, amount, eur_value, fee, net_pnl,
             volatility, regime, json.dumps(params or {}), trade_id, filled_at))
        c.commit()

    def get_recent_trades(self, bot=None, limit=100):
        c = self._conn_get()
        col_names = [d[0] for d in c.execute("PRAGMA table_info(trades)").fetchall()]
        cols = ", ".join(
            f"COALESCE({c}, 0)" if c == "net_pnl" else c
            for c in col_names
        )
        if bot:
            rows = c.execute(
                f"SELECT {cols} FROM trades WHERE bot=? ORDER BY id DESC LIMIT ?",
                (bot, limit)).fetchall()
        else:
            rows = c.execute(
                f"SELECT {cols} FROM trades ORDER BY id DESC LIMIT ?",
                (limit,)).fetchall()
        return [dict(r) for r in rows]

    def get_trade_stats(self, bot=None, n=50):
        c = self._conn_get()
        where = "WHERE bot=?" if bot else ""
        params = (bot,) if bot else ()
        rows = c.execute(
            f"SELECT net_pnl, market_volatility, market_regime FROM trades "
            f"{where} ORDER BY id DESC LIMIT ?",
            params + (n,)).fetchall()
        if not rows:
            return {"count": 0, "avg_pnl": 0, "win_rate": 0, "total_pnl": 0}
        pnls = [r["net_pnl"] for r in rows if r["net_pnl"] is not None]
        if not pnls:
            return {"count": 0, "avg_pnl": 0, "win_rate": 0, "total_pnl": 0}
        wins = sum(1 for p in pnls if p > 0)
        return {
            "count": len(pnls),
            "avg_pnl": round(sum(pnls)/len(pnls), 4),
            "total_pnl": round(sum(pnls), 4),
            "win_rate": round(wins/len(pnls)*100, 1),
            "avg_volatility": round(sum(r["market_volatility"] for r in rows)/len(rows), 4),
        }

    def get_pnl_by_regime(self, bot=None):
        c = self._conn_get()
        where = "WHERE bot=?" if bot else ""
        params = (bot,) if bot else ()
        rows = c.execute(
            f"SELECT market_regime, COUNT(*) as cnt, "
            f"AVG(net_pnl) as avg_pnl, SUM(CASE WHEN net_pnl>0 THEN 1 ELSE 0 END) as wins "
            f"FROM trades {where} GROUP BY market_regime", params).fetchall()
        return [dict(r) for r in rows]

    # ── Daily PnL ──
    def update_daily_pnl(self, bot, pnl, trades=1, fees=0):
        c = self._conn_get()
        today = datetime.now().strftime("%Y-%m-%d")
        c.execute("""INSERT OR REPLACE INTO daily_pnl (day, bot, pnl, trades, fees)
            VALUES (?,?, COALESCE((SELECT pnl FROM daily_pnl WHERE day=? AND bot=?),0)+?,
            COALESCE((SELECT trades FROM daily_pnl WHERE day=? AND bot=?),0)+?,
            COALESCE((SELECT fees FROM daily_pnl WHERE day=? AND bot=?),0)+?)""",
            (today, bot, today, bot, pnl, today, bot, trades, today, bot, fees))
        c.commit()

    def get_daily_pnl(self, days=7):
        c = self._conn_get()
        rows = c.execute(
            "SELECT day, bot, pnl, trades FROM daily_pnl "
            "ORDER BY day DESC LIMIT ?", (days*10,)).fetchall()
        return [dict(r) for r in rows]

    # ── Regime ──
    def save_regime(self, regime, volatility, trend_strength, volume_ratio, details=None):
        c = self._conn_get()
        c.execute("""INSERT INTO regime_log
            (regime, volatility, trend_strength, volume_ratio, details)
            VALUES (?,?,?,?,?)""",
            (regime, volatility, trend_strength, volume_ratio,
             json.dumps(details or {})))
        c.commit()

    def get_current_regime(self):
        c = self._conn_get()
        row = c.execute(
            "SELECT * FROM regime_log ORDER BY id DESC LIMIT 1").fetchone()
        return dict(row) if row else {"regime": "unknown", "volatility": 0}

    def get_regime_history(self, limit=48):
        c = self._conn_get()
        rows = c.execute(
            "SELECT * FROM regime_log ORDER BY id DESC LIMIT ?",
            (limit,)).fetchall()
        return [dict(r) for r in rows]

    # ── Bot Params ──
    def save_bot_params(self, bot, params, score=0):
        c = self._conn_get()
        c.execute("""INSERT OR REPLACE INTO bot_params (bot, params, score, updated_at)
            VALUES (?,?,?, datetime('now'))""",
            (bot, json.dumps(params), score))
        c.commit()

    def get_bot_params(self, bot):
        c = self._conn_get()
        row = c.execute(
            "SELECT * FROM bot_params WHERE bot=?", (bot,)).fetchone()
        if not row:
            return {"bot": bot, "params": {}, "score": 0}
        d = dict(row)
        d["params"] = json.loads(d["params"])
        return d

    def get_all_bot_params(self):
        c = self._conn_get()
        rows = c.execute("SELECT * FROM bot_params").fetchall()
        return [dict(r) for r in rows]

    # ── Capital Allocation ──
    def save_allocation(self, bot, eur_alloc, rationale=""):
        c = self._conn_get()
        c.execute("""INSERT INTO capital_alloc (bot, eur_alloc, rationale)
            VALUES (?,?,?)""", (bot, eur_alloc, rationale))
        c.commit()

    def get_latest_allocation(self):
        c = self._conn_get()
        rows = c.execute(
            "SELECT bot, eur_alloc, rationale FROM capital_alloc "
            "WHERE id IN (SELECT MAX(id) FROM capital_alloc GROUP BY bot)").fetchall()
        return [dict(r) for r in rows]

    # ── Summary ──
    def summary(self):
        c = self._conn_get()
        trades = c.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
        bots = c.execute("SELECT COUNT(DISTINCT bot) FROM trades").fetchone()[0]
        pnl = c.execute("SELECT COALESCE(SUM(net_pnl),0) FROM trades").fetchone()[0]
        regime = self.get_current_regime()
        return {
            "total_trades": trades,
            "bots_with_trades": bots,
            "total_pnl": round(pnl, 4),
            "current_regime": regime["regime"],
            "current_volatility": regime["volatility"],
        }


if __name__ == "__main__":
    m = DenaroMemory()
    print(json.dumps(m.summary(), indent=2))
