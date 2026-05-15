import sqlite3
import os
from datetime import datetime
import time


class TradeDB:
    """
    TradeDB — Strato di persistenza centralizzato per Denaro.
    Usa una connessione persistente (singleton) per evitare problemi
    di concorrenza con asyncio su Python >= 3.14.
    """

    _instances = {}  # per evitare connessioni multiple

    def __init__(self, db_path=None):
        if db_path is None:
            db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trades.db")
        self.db_path = os.path.abspath(os.path.realpath(db_path))
        parent = os.path.dirname(self.db_path)
        if parent and not os.path.exists(parent):
            os.makedirs(parent, exist_ok=True)
        self._conn = None
        self._init_db()

    def _get_conn(self):
        """Restituisce una connessione persistente (thread-safe per async single-thread)."""
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, timeout=10, check_same_thread=False)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA busy_timeout=5000")
        return self._conn

    def _init_db(self):
        conn = self._get_conn()
        conn.execute('''CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bot_name TEXT,
            symbol TEXT,
            side TEXT,
            entry_price REAL,
            exit_price REAL,
            quantity REAL,
            entry_time DATETIME,
            exit_time DATETIME,
            gross_pnl REAL,
            fees REAL,
            net_pnl REAL,
            exit_reason TEXT
        )''')
        conn.execute('''CREATE TABLE IF NOT EXISTS bot_state (
            bot_name TEXT PRIMARY KEY,
            is_in_position BOOLEAN,
            entry_price REAL,
            quantity REAL,
            tp REAL,
            sl REAL,
            entry_time DATETIME,
            last_heartbeat DATETIME,
            exchange_name TEXT
        )''')
        conn.execute('''CREATE TABLE IF NOT EXISTS bot_exposure (
            symbol TEXT PRIMARY KEY,
            amount REAL,
            last_updated REAL
        )''')
        conn.execute('''CREATE TABLE IF NOT EXISTS vault_balance (
            key TEXT PRIMARY KEY,
            value REAL,
            updated_at REAL
        )''')
        conn.commit()
        self._migrate_db(conn)

    def _migrate_db(self, conn):
        for col, tbl in [
            ('tp', 'bot_state'),
            ('sl', 'bot_state'),
            ('last_heartbeat', 'bot_state'),
            ('exchange_name', 'bot_state'),
            ('last_updated', 'bot_exposure'),
        ]:
            try:
                conn.execute(f"ALTER TABLE [{tbl}] ADD COLUMN [{col}] REAL")
                conn.commit()
            except sqlite3.OperationalError:
                pass

    def save_trade(self, bot_name, symbol, side, entry_price, exit_price, quantity,
                   entry_time, exit_time, gross_pnl, fees, net_pnl, reason):
        conn = self._get_conn()
        conn.execute('''INSERT INTO trades
            (bot_name, symbol, side, entry_price, exit_price, quantity,
             entry_time, exit_time, gross_pnl, fees, net_pnl, exit_reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (bot_name, symbol, side, entry_price, exit_price, quantity,
              entry_time, exit_time, gross_pnl, fees, net_pnl, reason))
        conn.commit()

    # ── Exposure (SQLite-backed, replaces JSON file) ───
    def upsert_exposure(self, symbol, amount):
        conn = self._get_conn()
        conn.execute('''
            INSERT OR REPLACE INTO bot_exposure (symbol, amount, last_updated)
            VALUES (?, ?, ?)''', (symbol, amount, time.time()))
        conn.commit()

    def remove_exposure(self, symbol):
        conn = self._get_conn()
        conn.execute('DELETE FROM bot_exposure WHERE symbol = ?', (symbol,))
        conn.commit()

    def get_exposure(self):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('SELECT symbol, amount FROM bot_exposure')
        rows = cursor.fetchall()
        total = sum(amount for _, amount in rows)
        positions = {symbol: amount for symbol, amount in rows}
        return {'total': total, 'positions': positions}

    # ── Vault (SQLite-backed, replaces vault.json) ───
    def get_vault_balance(self):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('SELECT value FROM vault_balance WHERE key = ?', ('EUR',))
        row = cursor.fetchone()
        return row[0] if row else 0.0

    def add_to_vault(self, amount):
        conn = self._get_conn()
        conn.execute('''
            INSERT INTO vault_balance (key, value, updated_at)
            VALUES (?, COALESCE((SELECT value FROM vault_balance WHERE key = ?), 0) + ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = value + ?, updated_at = ?
        ''', ('EUR', 'EUR', amount, time.time(), amount, time.time()))
        conn.commit()

    def get_daily_pnl(self):
        today = datetime.now().strftime('%Y-%m-%d')
        conn = self._get_conn()
        res = conn.execute(
            'SELECT SUM(net_pnl) FROM trades WHERE date(exit_time) = ?',
            (today,)).fetchone()
        return res[0] if res[0] else 0.0

    def save_bot_state(self, bot_name, is_in_position, entry_price, quantity,
                       tp, sl, entry_time, exchange_name='binance'):
        conn = self._get_conn()
        conn.execute('''INSERT OR REPLACE INTO bot_state
            (bot_name, is_in_position, entry_price, quantity, tp, sl,
             entry_time, last_heartbeat, exchange_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (bot_name, is_in_position, entry_price, quantity, tp, sl,
             entry_time, time.time(), exchange_name))
        conn.commit()

    def load_bot_state(self, bot_name):
        conn = self._get_conn()
        cursor = conn.execute('''SELECT is_in_position, entry_price, quantity,
            tp, sl, entry_time, last_heartbeat, exchange_name
            FROM bot_state WHERE bot_name = ?''', (bot_name,))
        row = cursor.fetchone()
        if row:
            return {
                'is_in_position': bool(row[0]),
                'entry_price': row[1],
                'quantity': row[2],
                'tp': row[3],
                'sl': row[4],
                'entry_time': row[5],
                'last_heartbeat': row[6],
                'exchange_name': row[7],
            }
        return None

    def get_metrics(self):
        conn = self._get_conn()
        trades = conn.execute('SELECT net_pnl FROM trades').fetchall()
        if not trades:
            return {'win_rate': 0, 'total_profit': 0}
        pnls = [t[0] for t in trades]
        win_rate = (len([p for p in pnls if p > 0]) / len(pnls)) * 100
        total_profit = sum(pnls)
        return {'win_rate': win_rate, 'total_profit': total_profit}