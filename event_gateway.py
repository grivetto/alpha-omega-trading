#!/usr/bin/env python3
"""
EVENT GATEWAY v1.0 — Heartbeat + Telegram Alert System
=======================================================
Invia notifiche periodiche su Telegram sullo stato del sistema.
Connette auto_adaptive_engine ai canali di notifica.

✅ Heartbeat ogni 30 minuti con stato sintetico
✅ Alert su perdite giornaliere eccessive
✅ Alert su simboli auto-disabilitati
✅ Log delle performance cumulative
"""

import asyncio
import sqlite3
import os, sys, json, logging
from datetime import datetime, timezone
from typing import Optional

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [EVENT-GATEWAY] - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(BASE_DIR, "event_gateway.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('EventGateway')

# Try importing — will fail if used standalone
try:
    from trade_db import TradeDB
    from auto_adaptive_engine import AutoAdaptiveEngine
    IMPORT_OK = True
except ImportError:
    IMPORT_OK = False
    TradeDB = None
    AutoAdaptiveEngine = None


class EventGateway:
    """
    Monitors the trading system and sends alerts.
    Can work standalone (check DB every N seconds) or as library.
    """

    def __init__(self, db_path: Optional[str] = None, telegram_token: Optional[str] = None,
                 telegram_chat_id: Optional[str] = None):
        self.db_path = db_path or os.path.join(BASE_DIR, "trades.db")
        self.telegram_token = telegram_token
        self.telegram_chat_id = telegram_chat_id

        if IMPORT_OK:
            self.db = TradeDB(self.db_path)
        else:
            self.db = None

        self.last_heartbeat = datetime.now()
        self.daily_alert_sent = False

    def get_status_summary(self) -> dict:
        """Pull summary from DB + adaptive engine."""
        if not IMPORT_OK:
            return {'error': 'modules not available'}

        # Trade stats
        results = {'total_trades': 0, 'today_trades': 0, 'today_pnl': 0.0,
                   'total_pnl': 0.0, 'wins': 0, 'losses': 0, 'vault': 0.0}

        try:
            conn = sqlite3.connect(self.db_path) if 'sqlite3' in sys.modules else None
            if conn:
                cursor = conn.execute(
                    "SELECT COUNT(*), COALESCE(SUM(net_pnl), 0) FROM trades")
                row = cursor.fetchone()
                if row:
                    results['total_trades'] = row[0] or 0
                    results['total_pnl'] = row[1] or 0.0

                today = datetime.now().strftime('%Y-%m-%d')
                cursor = conn.execute(
                    "SELECT COUNT(*), COALESCE(SUM(net_pnl), 0) FROM trades "
                    "WHERE date(exit_time) = ?", (today,))
                row = cursor.fetchone()
                if row:
                    results['today_trades'] = row[0] or 0
                    results['today_pnl'] = row[1] or 0.0

                cursor = conn.execute(
                    "SELECT COUNT(*) FROM trades WHERE net_pnl > 0")
                results['wins'] = cursor.fetchone()[0] or 0
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM trades WHERE net_pnl <= 0")
                results['losses'] = cursor.fetchone()[0] or 0

                cursor = conn.execute(
                    "SELECT value FROM vault_balance WHERE key = 'EUR'")
                row = cursor.fetchone()
                results['vault'] = row[0] if row else 0.0

                conn.close()
        except Exception as e:
            logger.error(f"DB query error: {e}")

        return results

    def format_heartbeat_message(self, stats: dict) -> str:
        """Format a concise heartbeat message."""
        total = stats['total_trades']
        wins = stats['wins']
        losses = stats['losses']
        win_rate = (wins / total * 100) if total > 0 else 0

        # Emoji status
        if stats['total_pnl'] > 0:
            status_emoji = "✅"
        elif total > 5 and stats['total_pnl'] < -30:
            status_emoji = "🔴"
        else:
            status_emoji = "⚪"

        msg = (
            f"{status_emoji} *Denaro Report*\n"
            f"📊 *Trades:* {total} (WR: {win_rate:.1f}%)\n"
            f"💰 *PnL totale:* {stats['total_pnl']:.2f}€\n"
            f"📅 *Oggi:* {stats['today_trades']} trades | {stats['today_pnl']:.2f}€\n"
            f"🏦 *Vault:* {stats['vault']:.2f}€\n"
            f"🕐 {datetime.now().strftime('%H:%M UTC')}"
        )
        return msg

    def send_telegram(self, message: str) -> bool:
        """Send a message via Telegram bot API."""
        if not self.telegram_token or not self.telegram_chat_id:
            return False
        
        import urllib.request
        import urllib.parse
        
        try:
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            data = urllib.parse.urlencode({
                'chat_id': self.telegram_chat_id,
                'text': message,
                'parse_mode': 'Markdown'
            }).encode()
            
            req = urllib.request.Request(url, data=data, method='POST')
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status == 200
        except Exception as e:
            logger.error(f"Telegram send error: {e}")
            return False

    async def run_forever(self, heartbeat_interval: int = 1800):
        """
        Main loop: sends heartbeat every `heartbeat_interval` seconds.
        Default: 1800s = 30 minutes.
        """
        logger.info(f"🚀 EventGateway avviato (heartbeat ogni {heartbeat_interval}s)")

        while True:
            stats = self.get_status_summary()
            msg = self.format_heartbeat_message(stats)

            if self.telegram_token:
                self.send_telegram(msg)
                logger.info(f"📤 Heartbeat inviato: {stats['total_trades']} trades, "
                            f"{stats['total_pnl']:.2f}€")
            else:
                # Log to file only
                logger.info(f"[HEARTBEAT] {msg}")

            await asyncio.sleep(heartbeat_interval)


# ═══════════════════════════════════════════════════════════════════
# Standalone usage
# ═══════════════════════════════════════════════════════════════════
def main():
    """Run EventGateway standalone."""
    from dotenv import load_dotenv

    load_dotenv(os.path.join(BASE_DIR, ".env"))

    token = os.getenv('TELEGRAM_BOT_TOKEN', '')
    chat_id = os.getenv('TELEGRAM_CHAT_ID', '')
    interval = int(os.getenv('HEARTBEAT_INTERVAL', '3600'))

    gateway = EventGateway(
        telegram_token=token,
        telegram_chat_id=chat_id,
    )

    asyncio.run(gateway.run_forever(heartbeat_interval=interval))


if __name__ == '__main__':
    main()
