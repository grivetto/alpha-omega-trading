"""Telegram bot for alerts and monitoring."""
import requests
import time
from typing import Optional
from dataclasses import dataclass


@dataclass
class TelegramConfig:
    bot_token: str = ""
    chat_id: str = ""
    enabled: bool = True


class TelegramBot:
    def __init__(self, config: TelegramConfig):
        self.config = config
        self.base_url = f"https://api.telegram.org/bot{config.bot_token}" if config.bot_token else None
        self._last_message_time = 0
        self._rate_limit = 1.0  # 1 message per second max
    
    def send(self, text: str, parse_mode: str = "HTML") -> bool:
        """Send a message to Telegram."""
        if not self.config.enabled or not self.config.bot_token or not self.config.chat_id:
            return False
        
        # Rate limiting
        elapsed = time.time() - self._last_message_time
        if elapsed < self._rate_limit:
            time.sleep(self._rate_limit - elapsed)
        
        try:
            payload = {
                "chat_id": self.config.chat_id,
                "text": text,
                "parse_mode": parse_mode,
                "disable_web_page_preview": True
            }
            resp = requests.post(f"{self.base_url}/sendMessage", json=payload, timeout=10)
            self._last_message_time = time.time()
            
            if resp.status_code == 200:
                return True
            else:
                print(f"⚠️ Telegram send failed: {resp.status_code} {resp.text}")
                return False
        except Exception as e:
            print(f"⚠️ Telegram send error: {e}")
            return False
    
    def send_status(self, status: dict):
        """Send formatted status update."""
        lines = [
            f"📊 <b>Airdrop Farm Status</b>",
            f"🔄 Running: {'✅' if status['running'] else '❌'}",
            f"⏱️ Uptime: {status['uptime_hours']:.1f}h",
            f"💰 Virtual: €{status['config']['budget_virtual']}",
            f"💵 Real: €{status['config']['budget_real']}",
            f"🧪 Dry run: {status['config']['dry_run']}",
            "",
            f"👛 Wallets: {len(status['wallets'])}"
        ]
        for w in status['wallets']:
            cooldown = " ⏸️" if w['in_cooldown'] else ""
            lines.append(
                f"  #{w['index']} <code>{w['address']}</code> "
                f"next={w['next_action_in_min']:.0f}m "
                f"actions={w['daily_actions']} fails={w['consecutive_failures']}{cooldown}"
            )
        
        return self.send("\n".join(lines))
    
    def send_alert(self, title: str, message: str, level: str = "info"):
        """Send alert with emoji prefix."""
        emojis = {
            "info": "ℹ️",
            "warning": "⚠️",
            "error": "❌",
            "success": "✅",
            "critical": "🚨"
        }
        emoji = emojis.get(level, "ℹ️")
        text = f"{emoji} <b>{title}</b>\n{message}"
        return self.send(text)
    
    def send_daily_summary(self, stats: dict):
        """Send daily summary report."""
        lines = [
            f"📅 <b>Daily Summary</b>",
            f"📈 Total actions: {stats.get('total_actions', 0)}",
            f"✅ Success rate: {stats.get('success_rate', 0)*100:.1f}%",
            f"⛽ Total gas: ${stats.get('total_gas_usd', 0):.2f}",
            f"💰 Total volume: ${stats.get('total_volume_usd', 0):.2f}",
            "",
            "<b>By Strategy:</b>"
        ]
        for strat, s in stats.get('by_strategy', {}).items():
            lines.append(
                f"  {strat}: {s['count']} actions, "
                f"{s['success']}/{s['count']} success, "
                f"${s['gas']:.2f} gas, ${s['vol']:.2f} vol"
            )
        
        return self.send("\n".join(lines))


if __name__ == "__main__":
    import os
    bot = TelegramBot(TelegramConfig(
        bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
        chat_id=os.getenv("TELEGRAM_CHAT_ID", ""),
        enabled=True
    ))
    
    if bot.config.bot_token and bot.config.chat_id:
        bot.send("🤖 <b>Test message</b> - Airdrop Farm bot is online!")
        print("Test message sent")
    else:
        print("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID to test")