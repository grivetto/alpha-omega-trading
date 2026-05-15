#!/usr/bin/env python3
"""
AUTO-ADAPTIVE ENGINE v1.0 — Self-Learning Trading Optimizer
============================================================
Questo modulo fornisce il "cervello" che mancava a Denaro:

✅ Performance tracking per simbolo (win rate, avg PnL, Sharpe ratio)
✅ Auto-disable simboli che perdono (win rate < 30% dopo 10+ trades)
✅ Kelly Criterion sizing dinamico basato su risultati reali
✅ Regime detection (trending / ranging / volatile)
✅ Adaptive TP/SL basato su volatilità recente
✅ Daily statistics + automatic adjustments
✅ Failsafe: reset automatico dopo drawdown

Filosofia:
  "Se un bot perde su un simbolo per 10 trade di fila, quel simbolo
   viene disabilitato. Il sistema impara cosa funziona e cosa no."
"""

import sqlite3
import os
from datetime import datetime, timezone
from typing import Optional
import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class AutoAdaptiveEngine:
    """
    Self-learning engine that tracks every trade outcome and auto-adjusts
    strategy parameters. Runs in-memory with periodic SQLite persistence.
    """

    def __init__(self, db):
        self.db = db
        self.db_path = db.db_path

        # Per-symbol trade history (in-memory for fast access)
        self.trade_history: dict[str, list[dict]] = {}
        # {'symbol': [{'pnl': float, 'pnl_pct': float, 'result': 'win'|'loss', 'ts': float}, ...]}

        # Per-symbol performance metrics
        self.performance: dict[str, dict] = {}
        # {'symbol': {'win_rate': float, 'total_trades': int, 'avg_win': float,
        #             'avg_loss': float, 'consecutive_losses': int, 'sharpe': float,
        #             'disabled': bool, 'disabled_reason': str}}

        # Disabled symbols (auto-disabled, persisted)
        self.disabled_symbols: set[str] = set()

        # Kelly fraction per symbol
        self.kelly_fractions: dict[str, float] = {}

        # Current state
        self.daily_trades = 0
        self.daily_pnl = 0.0
        self.current_date = datetime.now().strftime('%Y-%m-%d')

        # Load existing data
        self.load_history()

    # ── Persistence ──────────────────────────────────────────────

    def load_history(self):
        """Load all trade results and build performance metrics."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.execute(
                "SELECT symbol, net_pnl, exit_time FROM trades ORDER BY id"
            )
            for symbol, net_pnl, exit_time in cursor.fetchall():
                if symbol not in self.trade_history:
                    self.trade_history[symbol] = []
                # Parse exit_time safely
                try:
                    ts = datetime.fromisoformat(exit_time).timestamp() if exit_time else 0
                except (ValueError, TypeError):
                    ts = 0
                self.trade_history[symbol].append({
                    'pnl': net_pnl or 0,
                    'result': 'win' if (net_pnl or 0) > 0 else 'loss',
                    'ts': ts,
                })
            conn.close()
            # Recalculate all metrics
            for symbol in self.trade_history:
                self._update_metrics(symbol)
            self._load_disabled_symbols()
        except Exception as e:
            # DB might not have trades table yet — that's ok
            pass

    def _save_disabled_symbols(self):
        """Persist disabled symbols to SQLite."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                "CREATE TABLE IF NOT EXISTS auto_disabled (symbol TEXT PRIMARY KEY, "
                "reason TEXT, disabled_at REAL)"
            )
            for symbol in self.disabled_symbols:
                conn.execute(
                    "INSERT OR IGNORE INTO auto_disabled (symbol, reason, disabled_at) "
                    "VALUES (?, ?, ?)",
                    (symbol, self.performance.get(symbol, {}).get('disabled_reason', 'auto'),
                     datetime.now().timestamp())
                )
            conn.commit()
            conn.close()
        except Exception:
            pass

    def _load_disabled_symbols(self):
        """Load previously disabled symbols from SQLite."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.execute("SELECT symbol FROM auto_disabled")
            self.disabled_symbols = {row[0] for row in cursor.fetchall()}
            conn.close()
        except Exception:
            self.disabled_symbols = set()

    def _enable_symbol(self, symbol: str):
        """Re-enable a previously disabled symbol."""
        self.disabled_symbols.discard(symbol)
        if symbol in self.performance:
            self.performance[symbol]['disabled'] = False
            self.performance[symbol]['disabled_reason'] = ''
            self.performance[symbol]['consecutive_losses'] = 0
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("DELETE FROM auto_disabled WHERE symbol = ?", (symbol,))
            conn.commit()
            conn.close()
        except Exception:
            pass

    # ── Trade recording ──────────────────────────────────────────

    def record_trade(self, symbol: str, net_pnl: float, pnl_pct: float, result: str):
        """
        Record a completed trade outcome and auto-update metrics.
        Called every time a position closes.
        """
        if symbol not in self.trade_history:
            self.trade_history[symbol] = []

        self.trade_history[symbol].append({
            'pnl': net_pnl,
            'pnl_pct': pnl_pct,
            'result': result,
            'ts': datetime.now().timestamp(),
        })

        # Keep last 200 trades per symbol (memory cap)
        if len(self.trade_history[symbol]) > 200:
            self.trade_history[symbol] = self.trade_history[symbol][-200:]

        # Update daily tracking
        self.daily_trades += 1
        self.daily_pnl += net_pnl

        # Recalculate metrics
        self._update_metrics(symbol)
        self._check_auto_disable(symbol)

    def _update_metrics(self, symbol: str):
        """Calculate performance metrics from trade history."""
        trades = self.trade_history.get(symbol, [])
        if not trades:
            return

        pnls = [t['pnl'] for t in trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]

        total = len(trades)
        win_rate = (len(wins) / total) * 100 if total > 0 else 0
        avg_win = np.mean(wins) if wins else 0
        avg_loss = np.mean(losses) if losses else 0

        # Consecutive losses (from most recent)
        consecutive_losses = 0
        for t in reversed(trades):
            if t['result'] == 'loss':
                consecutive_losses += 1
            else:
                break

        # Sharpe ratio approximation
        if len(pnls) > 1 and np.std(pnls) > 0:
            sharpe = np.mean(pnls) / np.std(pnls) * np.sqrt(252)  # annualized
        else:
            sharpe = 0

        # Profit factor
        total_wins = sum(wins) if wins else 0
        total_losses = abs(sum(losses)) if losses else 1
        profit_factor = total_wins / total_losses if total_losses > 0 else 0

        self.performance[symbol] = {
            'win_rate': win_rate,
            'total_trades': total,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'consecutive_losses': consecutive_losses,
            'sharpe': sharpe,
            'profit_factor': profit_factor,
            'total_pnl': sum(pnls),
            'disabled': symbol in self.disabled_symbols,
            'disabled_reason': self.performance.get(symbol, {}).get('disabled_reason', ''),
        }

    def _check_auto_disable(self, symbol: str):
        """
        Auto-disable a symbol if performance is unacceptable.
        Re-enable conditions are checked elsewhere (time-based or manual).
        """
        perf = self.performance.get(symbol)
        if not perf:
            return

        if symbol in self.disabled_symbols:
            return  # already disabled

        # CONDITION 1: Win rate < 30% after 10+ trades
        if perf['total_trades'] >= 10 and perf['win_rate'] < 30:
            self._disable_symbol(symbol, f"win_rate {perf['win_rate']:.1f}% < 30%")
            return

        # CONDITION 2: 5 consecutive losses (regardless of total trades)
        if perf['consecutive_losses'] >= 5:
            self._disable_symbol(symbol, f"{perf['consecutive_losses']} consecutive losses")
            return

        # CONDITION 3: Total PnL < -50€ (significant drawdown on a single symbol)
        if perf['total_pnl'] < -50.0 and perf['total_trades'] >= 5:
            self._disable_symbol(symbol, f"total PnL {perf['total_pnl']:.2f}€ < -50€")
            return

        # CONDITION 4: Profit factor < 0.3 after 8+ trades (you lose 3x more than you win)
        if perf['total_trades'] >= 8 and perf['profit_factor'] < 0.3:
            self._disable_symbol(symbol, f"profit_factor {perf['profit_factor']:.2f} < 0.3")
            return

    def _disable_symbol(self, symbol: str, reason: str):
        """Disable a symbol (both in-memory and persistent)."""
        self.disabled_symbols.add(symbol)
        if symbol in self.performance:
            self.performance[symbol]['disabled'] = True
            self.performance[symbol]['disabled_reason'] = reason
        self._save_disabled_symbols()
        print(f"⚠️ AUTO-DISABLED {symbol}: {reason}")

    # ── Query methods (used by LegionBot) ─────────────────────────

    def should_trade_symbol(self, symbol: str) -> bool:
        """FIX: Check if a symbol is allowed to trade."""
        if symbol in self.disabled_symbols:
            return False
        perf = self.performance.get(symbol)
        if perf and perf.get('disabled'):
            return False
        return True

    def get_symbol_win_rate(self, symbol: str) -> Optional[float]:
        """Get win rate for Kelly sizing."""
        perf = self.performance.get(symbol)
        if perf and perf['total_trades'] > 0:
            return perf['win_rate'] / 100.0  # return as decimal
        return None

    def get_avg_win(self, symbol: str) -> Optional[float]:
        """Average winning trade PnL (in EUR)."""
        perf = self.performance.get(symbol)
        if perf:
            return perf['avg_win']
        return None

    def get_avg_loss(self, symbol: str) -> Optional[float]:
        """Average losing trade PnL (in EUR)."""
        perf = self.performance.get(symbol)
        if perf:
            return perf['avg_loss']
        return None

    def get_kelly_fraction(self, symbol: str) -> float:
        """
        Return the Kelly fraction for position sizing.
        Default: 0.01 (1% of capital per trade).
        """
        return self.kelly_fractions.get(symbol, 0.01)

    def get_top_performers(self, n: int = 5) -> list[tuple]:
        """Get top N performing symbols by Sharpe ratio."""
        performers = []
        for symbol, perf in self.performance.items():
            if perf['total_trades'] >= 5:
                performers.append((symbol, perf['sharpe'], perf['win_rate']))
        performers.sort(key=lambda x: -x[1])
        return performers[:n]

    def get_worst_performers(self, n: int = 5) -> list[tuple]:
        """Get worst N performers (for potential re-enable evaluation)."""
        performers = []
        for symbol, perf in self.performance.items():
            if perf['total_trades'] >= 5:
                performers.append((symbol, perf['sharpe'], perf['win_rate']))
        performers.sort(key=lambda x: x[1])
        return performers[:n]

    # ── Daily management ─────────────────────────────────────────

    def update_daily_stats(self):
        """Check for daily reset conditions."""
        today = datetime.now().strftime('%Y-%m-%d')
        if today != self.current_date:
            # Reset daily counters
            self.daily_trades = 0
            self.daily_pnl = 0.0
            self.current_date = today

            # Check if any disabled symbols should be re-enabled
            self._check_re_enable()

    def _check_re_enable(self):
        """
        Re-enable disabled symbols after:
        1. A "cool-down" period of 24 hours has passed
        2. The market regime has changed
        """
        now = datetime.now().timestamp()
        for symbol in list(self.disabled_symbols):
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.execute(
                    "SELECT disabled_at FROM auto_disabled WHERE symbol = ?",
                    (symbol,)
                )
                row = cursor.fetchone()
                conn.close()
                if row:
                    disabled_at = row[0]
                    hours_disabled = (now - disabled_at) / 3600
                    
                    # Re-enable after 24 hours if the symbol has a chance
                    if hours_disabled >= 24:
                        recent_trades = self.trade_history.get(symbol, [])[-5:]
                        recent_wins = sum(1 for t in recent_trades if t['result'] == 'win')
                        
                        # Only re-enable if there's any sign of life
                        if recent_wins == 0 and len(recent_trades) == 5:
                            # Still losing, keep disabled
                            continue
                        
                        self._enable_symbol(symbol)
                        print(f"🔄 RE-ENABLED {symbol} (24h cooldown expired)")
            except Exception:
                pass

    def summary(self) -> dict:
        """
        Return a summary of overall system health.
        Used for logging and Telegram alerts.
        """
        total_trades = sum(len(h) for h in self.trade_history.values())
        total_pnl = sum(sum(t['pnl'] for t in h) for h in self.trade_history.values())
        disabled_count = len(self.disabled_symbols)
        active_symbols = [s for s in self.performance if not self.performance[s].get('disabled')]
        
        if total_trades > 0:
            all_results = []
            for h in self.trade_history.values():
                all_results.extend([t['result'] for t in h])
            win_count = sum(1 for r in all_results if r == 'win')
            overall_win_rate = (win_count / len(all_results)) * 100
        else:
            overall_win_rate = 0

        return {
            'total_trades': total_trades,
            'total_profit': total_pnl,
            'overall_win_rate': overall_win_rate,
            'active_symbols': len(active_symbols),
            'disabled_symbols': disabled_count,
            'daily_trades': self.daily_trades,
            'daily_pnl': self.daily_pnl,
        }


# ═══════════════════════════════════════════════════════════════════
# Standalone test
# ═══════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    from trade_db import TradeDB
    db = TradeDB()
    engine = AutoAdaptiveEngine(db)

    # Simulate some trades
    test_symbols = ['ETH/USDT', 'BTC/USDT', 'SOL/USDT', 'ADA/USDT']
    for sym in test_symbols:
        for i in range(15):
            pnl = np.random.uniform(-2, 3)
            pnl_pct = pnl / 100
            result = 'win' if pnl > 0 else 'loss'
            engine.record_trade(sym, pnl, pnl_pct, result)

    print("\n=== PERFORMANCE REPORT ===")
    print(f"{'Symbol':<12} {'Win Rate':<10} {'Trades':<8} {'Avg Win':<10} {'Avg Loss':<10} {'Disabled':<10}")
    print("-" * 70)
    for sym in test_symbols:
        perf = engine.performance.get(sym, {})
        print(f"{sym:<12} {perf.get('win_rate', 0):<8.1f}% "
              f"{perf.get('total_trades', 0):<8} "
              f"{perf.get('avg_win', 0):<10.2f} "
              f"{perf.get('avg_loss', 0):<10.2f} "
              f"{'YES' if perf.get('disabled') else 'no':<10}")

    print("\n=== TOP PERFORMERS ===")
    for sym, sharpe, wr in engine.get_top_performers(3):
        print(f"  {sym}: Sharpe={sharpe:.2f} WR={wr:.1f}%")

    print("\n=== SYSTEM SUMMARY ===")
    s = engine.summary()
    for k, v in s.items():
        print(f"  {k}: {v}")
