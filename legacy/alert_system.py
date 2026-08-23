#!/usr/bin/env python3
"""
Alert System - Notification infrastructure for ShadowGrid Fleet.

Features:
- Telegram bot integration (reuses airdrop-farm telegram_bot.py)
- Email notifications (SMTP)
- Drawdown alerts (warning/critical)
- Daily loss alerts
- Bot health alerts (crash, restart, stuck)
- Pair rotation alerts
- Kill switch notifications
- Rate limiting and deduplication
"""

from __future__ import annotations
import asyncio
import json
import logging
import os
import smtplib
import threading
import time
from collections import defaultdict
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from typing import Dict, List, Optional, Callable
import requests

log = logging.getLogger("alert_system")
log.setLevel(logging.INFO)
sh = logging.StreamHandler()
sh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
log.handlers = [sh]


class AlertChannel:
    """Base class for alert channels."""
    def send(self, subject: str, message: str, priority: str = "normal") -> bool:
        raise NotImplementedError


class TelegramChannel(AlertChannel):
    """Telegram bot alert channel."""
    
    def __init__(self, bot_token: str, chat_id: str, parse_mode: str = "HTML"):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.parse_mode = parse_mode
        self.api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        self.last_sent: Dict[str, float] = {}
        self.min_interval = 60  # seconds between same alert
    
    def send(self, subject: str, message: str, priority: str = "normal") -> bool:
        # Rate limiting per subject
        key = f"{subject}:{message[:50]}"
        now = time.time()
        if key in self.last_sent and now - self.last_sent[key] < self.min_interval:
            return False
        
        # Priority emoji
        priority_emoji = {"critical": "🚨", "warning": "⚠️", "info": "ℹ️", "normal": "📢"}.get(priority, "📢")
        
        text = f"{priority_emoji} <b>{subject}</b>\n\n{message}"
        
        try:
            response = requests.post(
                self.api_url,
                json={
                    "chat_id": self.chat_id,
                    "text": text,
                    "parse_mode": self.parse_mode,
                    "disable_web_page_preview": True,
                },
                timeout=10
            )
            if response.status_code == 200:
                self.last_sent[key] = now
                log.info(f"Telegram alert sent: {subject}")
                return True
            else:
                log.error(f"Telegram alert failed: {response.status_code} {response.text}")
                return False
        except Exception as e:
            log.error(f"Telegram alert exception: {e}")
            return False


class EmailChannel(AlertChannel):
    """Email alert channel via SMTP."""
    
    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        username: str,
        password: str,
        from_addr: str,
        to_addrs: List[str],
        use_tls: bool = True,
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.from_addr = from_addr
        self.to_addrs = to_addrs
        self.use_tls = use_tls
        self.last_sent: Dict[str, float] = {}
        self.min_interval = 300  # 5 minutes between same email
    
    def send(self, subject: str, message: str, priority: str = "normal") -> bool:
        key = f"{subject}:{message[:50]}"
        now = time.time()
        if key in self.last_sent and now - self.last_sent[key] < self.min_interval:
            return False
        
        priority_prefix = {"critical": "[CRITICAL]", "warning": "[WARNING]", "info": "[INFO]"}.get(priority, "")
        
        msg = MIMEMultipart()
        msg["From"] = self.from_addr
        msg["To"] = ", ".join(self.to_addrs)
        msg["Subject"] = f"{priority_prefix} ShadowGrid Fleet: {subject}"
        
        body = f"""
ShadowGrid Fleet Alert
====================

{message}

---
Time: {datetime.now().isoformat()}
Priority: {priority.upper()}
"""
        msg.attach(MIMEText(body, "plain"))
        
        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)
            self.last_sent[key] = now
            log.info(f"Email alert sent: {subject}")
            return True
        except Exception as e:
            log.error(f"Email alert failed: {e}")
            return False


class LogChannel(AlertChannel):
    """Local log file alert channel (always enabled)."""
    
    def __init__(self, log_file: str = "/tmp/shadowgrid_alerts.log"):
        self.log_file = Path(log_file)
        self.logger = logging.getLogger("shadowgrid.alerts")
        self.logger.setLevel(logging.INFO)
        fh = logging.FileHandler(self.log_file)
        fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        self.logger.handlers = [fh]
    
    def send(self, subject: str, message: str, priority: str = "normal") -> bool:
        level = {"critical": logging.CRITICAL, "warning": logging.WARNING, "info": logging.INFO}.get(priority, logging.INFO)
        self.logger.log(level, f"{subject}: {message}")
        return True


class AlertSystem:
    """Central alert system with multiple channels and deduplication."""
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.channels: List[AlertChannel] = []
        self.alert_history: List[Dict] = []
        self.max_history = 1000
        self.lock = threading.RLock()
        
        # Always add log channel
        self.channels.append(LogChannel())
        
        # Initialize Telegram if configured
        self._init_telegram()
        
        # Initialize Email if configured
        self._init_email()
        
        log.info(f"AlertSystem initialized with {len(self.channels)} channels")
    
    def _init_telegram(self):
        """Initialize Telegram channel from config or env."""
        bot_token = self.config.get("telegram_bot_token") or os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = self.config.get("telegram_chat_id") or os.getenv("TELEGRAM_CHAT_ID")
        
        if bot_token and chat_id:
            self.channels.append(TelegramChannel(bot_token, chat_id))
            log.info("Telegram channel enabled")
        else:
            log.info("Telegram not configured (set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)")
    
    def _init_email(self):
        """Initialize Email channel from config or env."""
        smtp_host = self.config.get("smtp_host") or os.getenv("SMTP_HOST")
        smtp_port = int(self.config.get("smtp_port", 587) or os.getenv("SMTP_PORT", 587))
        username = self.config.get("smtp_username") or os.getenv("SMTP_USERNAME")
        password = self.config.get("smtp_password") or os.getenv("SMTP_PASSWORD")
        from_addr = self.config.get("smtp_from") or os.getenv("SMTP_FROM")
        to_addrs = self.config.get("smtp_to", [])
        if isinstance(to_addrs, str):
            to_addrs = [a.strip() for a in to_addrs.split(",")]
        
        if all([smtp_host, username, password, from_addr, to_addrs]):
            self.channels.append(EmailChannel(smtp_host, smtp_port, username, password, from_addr, to_addrs))
            log.info("Email channel enabled")
        else:
            log.info("Email not configured (set SMTP_* env vars)")
    
    def send_alert(
        self,
        subject: str,
        message: str,
        priority: str = "normal",
        tags: Optional[List[str]] = None,
    ) -> bool:
        """Send alert through all channels."""
        with self.lock:
            alert_record = {
                "timestamp": datetime.now().isoformat(),
                "subject": subject,
                "message": message,
                "priority": priority,
                "tags": tags or [],
            }
            self.alert_history.append(alert_record)
            if len(self.alert_history) > self.max_history:
                self.alert_history = self.alert_history[-self.max_history:]
        
        success = False
        for channel in self.channels:
            try:
                if channel.send(subject, message, priority):
                    success = True
            except Exception as e:
                log.error(f"Channel {channel.__class__.__name__} failed: {e}")
        
        return success
    
    # Convenience methods for common alerts
    
    def alert_portfolio_dd(self, current_dd: float, max_dd: float, equity: float, peak: float):
        """Alert for portfolio drawdown."""
        pct = current_dd * 100
        if pct >= max_dd * 100:
            priority = "critical"
            subject = f"PORTFOLIO DRAWDOWN CRITICAL: {pct:.1f}%"
        elif pct >= max_dd * 100 * 0.7:  # 70% of limit
            priority = "warning"
            subject = f"Portfolio Drawdown Warning: {pct:.1f}%"
        else:
            return False
        
        message = (
            f"Current DD: {pct:.1f}% (limit: {max_dd:.0%})\n"
            f"Equity: {equity:.2f}€ (Peak: {peak:.2f}€)\n"
            f"Loss: {peak - equity:.2f}€"
        )
        return self.send_alert(subject, message, priority, tags=["dd", "portfolio"])
    
    def alert_daily_loss(self, daily_loss: float, max_loss: float, day_start_equity: float, current_equity: float):
        """Alert for daily loss limit."""
        pct = daily_loss * 100
        if pct >= max_loss * 100:
            priority = "critical"
            subject = f"DAILY LOSS LIMIT HIT: {pct:.1f}%"
        elif pct >= max_loss * 100 * 0.7:
            priority = "warning"
            subject = f"Daily Loss Warning: {pct:.1f}%"
        else:
            return False
        
        message = (
            f"Today's loss: {pct:.1f}% (limit: {max_loss:.0%})\n"
            f"Day start: {day_start_equity:.2f}€\n"
            f"Current: {current_equity:.2f}€\n"
            f"Loss: {day_start_equity - current_equity:.2f}€"
        )
        return self.send_alert(subject, message, priority, tags=["daily_loss", "portfolio"])
    
    def alert_bot_crashed(self, symbol: str, exchange: str, restart_count: int):
        """Alert for bot crash/restart."""
        if restart_count == 1:
            priority = "warning"
            subject = f"Bot Restarted: {exchange}:{symbol}"
        elif restart_count <= 3:
            priority = "warning"
            subject = f"Bot Restarted #{restart_count}: {exchange}:{symbol}"
        else:
            priority = "critical"
            subject = f"BOT REPEATEDLY CRASHING: {exchange}:{symbol} (#{restart_count})"
        
        message = f"Symbol: {symbol}\nExchange: {exchange}\nRestart count: {restart_count}"
        return self.send_alert(subject, message, priority, tags=["bot", "crash", exchange.lower(), symbol])
    
    def alert_bot_stuck(self, symbol: str, exchange: str, last_activity_minutes: int):
        """Alert for bot with no activity."""
        subject = f"Bot Stuck: {exchange}:{symbol}"
        message = f"No trades for {last_activity_minutes} minutes\nSymbol: {symbol}\nExchange: {exchange}"
        return self.send_alert(subject, message, "warning", tags=["bot", "stuck", exchange.lower(), symbol])
    
    def alert_kill_switch(self, reason: str, equity: float):
        """Alert for kill switch activation."""
        subject = "KILL SWITCH ACTIVATED"
        message = f"Reason: {reason}\nCurrent equity: {equity:.2f}€\nAll positions will be closed."
        return self.send_alert(subject, message, "critical", tags=["kill_switch", "emergency"])
    
    def alert_pair_rotation(self, removed: List[str], added: List[str], reason: str = "Scheduled rotation"):
        """Alert for pair rotation."""
        subject = f"Pair Rotation: {len(removed)} out, {len(added)} in"
        message = f"Reason: {reason}\n\nRemoved:\n" + "\n".join(f"  - {p}" for p in removed)
        message += f"\n\nAdded:\n" + "\n".join(f"  - {p}" for p in added)
        return self.send_alert(subject, message, "info", tags=["pair_rotation"])
    
    def alert_volatility_regime(self, symbol: str, regime: str, action: str, ratio: float):
        """Alert for volatility regime change."""
        if regime in ("high", "extreme"):
            priority = "warning"
        else:
            priority = "info"
        subject = f"Volatility Regime: {symbol} = {regime.upper()}"
        message = f"Symbol: {symbol}\nRegime: {regime}\nATR Ratio: {ratio:.2f}\nAction: {action}"
        return self.send_alert(subject, message, priority, tags=["volatility", "regime", symbol])
    
    def alert_exposure_limit(self, base: str, current: float, limit: float):
        """Alert for exposure limit breach."""
        subject = f"Exposure Limit: {base} at {current:.1%}"
        message = f"Base currency: {base}\nCurrent exposure: {current:.1%}\nLimit: {limit:.0%}"
        return self.send_alert(subject, message, "warning", tags=["exposure", "limit", base])
    
    def get_history(self, limit: int = 100, tags: Optional[List[str]] = None) -> List[Dict]:
        """Get alert history, optionally filtered by tags."""
        with self.lock:
            history = self.alert_history[-limit:]
            if tags:
                history = [a for a in history if any(t in a.get("tags", []) for t in tags)]
            return history


# Global instance
_alert_system: Optional[AlertSystem] = None


def get_alert_system() -> Optional[AlertSystem]:
    return _alert_system


def init_alert_system(config: Optional[Dict] = None) -> AlertSystem:
    global _alert_system
    _alert_system = AlertSystem(config)
    return _alert_system
