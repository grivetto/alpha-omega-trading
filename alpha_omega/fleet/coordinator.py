"""
Fleet Coordinator for Alpha-Omega Trading System.

Multi-bot orchestration:
- Spawn/manage multiple UnifiedTradingEngine instances
- Hot reload via SIGHUP
- Graceful scaling (add/remove bots)
- Health monitoring and auto-restart
- Capital rebalancing across bots
- ZeroMQ subscription for market data aggregation
"""
from __future__ import annotations
import asyncio
import json
import logging
import os
import signal
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

log = logging.getLogger("alpha_omega.fleet.coordinator")

try:
    import zmq.asyncio
except ImportError:
    log.warning("pyzmq not installed — fleet coordination limited")
    zmq = None

from ..core.config import Config, FleetConfig, PairConfig, load_config_from_env, load_fleet_config, save_fleet_config
from ..core.engine import UnifiedTradingEngine
from ..risk.manager import PortfolioRiskManager


@dataclass
class BotInstance:
    """Running bot instance info."""
    config: Config
    engine: UnifiedTradingEngine
    task: Optional[asyncio.Task] = None
    status: str = "starting"  # starting, running, stopping, stopped, error
    last_health_check: int = 0
    restart_count: int = 0
    error_message: str = ""


class FleetCoordinator:
    """
    Coordinates multiple trading bots as a fleet.
    
    Features:
    - Load fleet config and spawn bots per pair
    - Hot reload config via SIGHUP
    - Graceful scale up/down
    - Health monitoring with auto-restart
    - Capital rebalancing
    - ZeroMQ market data aggregation
    - Portfolio risk management across fleet
    """

    __slots__ = (
        "fleet_config", "bots", "risk_manager", "_running",
        "_zmq_ctx", "_zmq_sub", "_zmq_task", "_health_task",
        "_rebalance_task", "_shutdown_event", "_signal_handlers_installed"
    )

    def __init__(self, fleet_config_path: str):
        self.fleet_config = load_fleet_config(fleet_config_path)
        self.bots: Dict[str, BotInstance] = {}
        self.risk_manager = PortfolioRiskManager(
            max_portfolio_dd=self.fleet_config.risk_params.get("max_portfolio_dd", 0.20),
            max_daily_loss=self.fleet_config.risk_params.get("max_daily_loss", 0.05),
            max_exposure_per_base=self.fleet_config.risk_params.get("max_exposure_per_base", 0.30),
            max_correlation=self.fleet_config.risk_params.get("max_correlation", 0.7),
            max_positions_per_base=self.fleet_config.risk_params.get("max_positions_per_base", 2),
        )
        self._running = False
        self._zmq_ctx = None
        self._zmq_sub = None
        self._zmq_task = None
        self._health_task = None
        self._rebalance_task = None
        self._shutdown_event = asyncio.Event()
        self._signal_handlers_installed = False
        
        log.info(f"FleetCoordinator initialized: {len(self.fleet_config.pairs)} Kraken pairs, {len(self.fleet_config.okx_pairs)} OKX pairs")

    async def initialize(self) -> None:
        """Initialize fleet: spawn all bots."""
        # Spawn bots for Kraken pairs
        for pair_config in self.fleet_config.pairs:
            await self._spawn_bot(pair_config)
        
        # Spawn bots for OKX pairs
        for pair_config in self.fleet_config.okx_pairs:
            await self._spawn_bot(pair_config)
        
        # Start ZeroMQ subscriber for market data aggregation
        await self._start_zmq_subscriber()
        
        # Start health monitoring
        self._health_task = asyncio.create_task(self._health_monitor())
        
        # Start capital rebalancing
        self._rebalance_task = asyncio.create_task(self._rebalance_loop())
        
        # Install signal handlers
        self._install_signal_handlers()
        
        self._running = True
        log.info(f"Fleet initialized with {len(self.bots)} bots")

    async def _spawn_bot(self, pair_config: PairConfig) -> None:
        """Spawn a bot for a pair configuration."""
        bot_id = f"{pair_config.exchange}_{pair_config.symbol.replace('/', '_')}"
        
        if bot_id in self.bots:
            log.warning(f"Bot {bot_id} already exists, skipping")
            return
        
        # Create bot config from fleet config
        base_config = load_config_from_env()
        
        # Override with pair-specific config
        bot_config = base_config
        bot_config.symbol = pair_config.symbol
        bot_config.exchange = pair_config.exchange
        bot_config.capital = pair_config.capital
        bot_config.health_port = pair_config.port
        bot_config.grid_levels = pair_config.grid_levels
        bot_config.grid_spread = pair_config.spread_pct / 100.0
        bot_config.max_drawdown_pct = pair_config.max_drawdown_pct
        bot_config.max_daily_loss_pct = pair_config.max_daily_loss_pct
        bot_config.use_momentum_filter = pair_config.use_momentum_filter
        bot_config.hybrid_mode = pair_config.hybrid_mode
        
        if pair_config.state_file:
            bot_config.state_file = pair_config.state_file
        if pair_config.log_file:
            bot_config.log_file = pair_config.log_file
        
        # Create engine
        engine = UnifiedTradingEngine(bot_config)
        
        # Create bot instance
        bot = BotInstance(config=bot_config, engine=engine)
        self.bots[bot_id] = bot
        
        # Start engine
        bot.task = asyncio.create_task(engine.run())
        bot.status = "running"
        
        log.info(f"Spawned bot: {bot_id} ({pair_config.exchange} {pair_config.symbol} port={pair_config.port} capital={pair_config.capital})")

    async def _start_zmq_subscriber(self) -> None:
        """Start ZeroMQ subscriber to aggregate market data from all bots."""
        if not zmq:
            return
        
        try:
            self._zmq_ctx = zmq.asyncio.Context()
            self._zmq_sub = self._zmq_ctx.socket(zmq.SUB)
            
            # Subscribe to all bot publishers
            # In practice, bots publish to different ports, we'd connect to each
            # For now, subscribe to a common fleet port
            self._zmq_sub.connect(f"tcp://localhost:{self.fleet_config.risk_params.get('zmq_fleet_port', 5556)}")
            self._zmq_sub.setsockopt(zmq.SUBSCRIBE, b"")
            
            self._zmq_task = asyncio.create_task(self._zmq_listener())
            log.info("ZeroMQ fleet subscriber started")
        except Exception as e:
            log.error(f"Failed to start ZMQ subscriber: {e}")

    async def _zmq_listener(self) -> None:
        """Listen for market data from bots."""
        while self._running:
            try:
                msg = await self._zmq_sub.recv_json()
                # Aggregate market data, update risk manager
                # Could forward to monitoring dashboard
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.debug(f"ZMQ listener error: {e}")
                await asyncio.sleep(1)

    async def _health_monitor(self) -> None:
        """Monitor bot health and auto-restart failed bots."""
        while self._running:
            try:
                for bot_id, bot in list(self.bots.items()):
                    # Check if task is done (crashed)
                    if bot.task and bot.task.done():
                        try:
                            await bot.task
                        except Exception as e:
                            bot.status = "error"
                            bot.error_message = str(e)
                            log.error(f"Bot {bot_id} crashed: {e}")
                            
                            # Auto-restart if not too many restarts
                            if bot.restart_count < 3:
                                log.info(f"Auto-restarting bot {bot_id} (attempt {bot.restart_count + 1})")
                                await self._restart_bot(bot_id)
                            else:
                                log.critical(f"Bot {bot_id} exceeded max restarts, marking stopped")
                                bot.status = "stopped"
                    
                    bot.last_health_check = int(time.time())
            
            except Exception as e:
                log.error(f"Health monitor error: {e}")
            
            await asyncio.sleep(30)  # Check every 30 seconds

    async def _restart_bot(self, bot_id: str) -> None:
        """Restart a specific bot."""
        if bot_id not in self.bots:
            return
        
        bot = self.bots[bot_id]
        
        # Stop old engine
        try:
            await bot.engine.stop()
        except Exception:
            pass
        
        # Create new engine with same config
        engine = UnifiedTradingEngine(bot.config)
        bot.engine = engine
        bot.task = asyncio.create_task(engine.run())
        bot.status = "running"
        bot.restart_count += 1
        bot.error_message = ""
        
        log.info(f"Bot {bot_id} restarted (count: {bot.restart_count})")

    async def _rebalance_loop(self) -> None:
        """Periodic capital rebalancing across fleet."""
        while self._running:
            try:
                await asyncio.sleep(3600)  # Every hour
                
                if not self._running:
                    break
                
                await self._rebalance_capital()
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"Rebalance loop error: {e}")
                await asyncio.sleep(60)

    async def _rebalance_capital(self) -> None:
        """Rebalance capital based on performance and risk."""
        # Collect equity from all bots
        total_equity = 0.0
        bot_equities = {}
        
        for bot_id, bot in self.bots.items():
            equity = bot.engine.state.equity if bot.engine and bot.engine.state else 0
            bot_equities[bot_id] = equity
            total_equity += equity
        
        if total_equity <= 0:
            return
        
        log.info(f"Fleet rebalance: total equity = {total_equity:.2f}")
        
        # Check portfolio risk
        all_positions = {}
        for bot_id, bot in self.bots.items():
            if bot.engine and bot.engine.state:
                all_positions.update(bot.engine.state.positions)
        
        await self.risk_manager.check_limits(total_equity, all_positions, 0)
        
        # Could implement dynamic capital allocation here
        # For now, just log

    def _install_signal_handlers(self) -> None:
        """Install SIGHUP/SIGTERM handlers."""
        if self._signal_handlers_installed:
            return
        
        loop = asyncio.get_running_loop()
        
        def handle_sighup():
            log.info("SIGHUP received — fleet hot reload")
            asyncio.create_task(self.hot_reload())
        
        def handle_sigterm():
            log.info("SIGTERM received — fleet graceful shutdown")
            asyncio.create_task(self.stop())
        
        try:
            loop.add_signal_handler(signal.SIGHUP, handle_sighup)
            loop.add_signal_handler(signal.SIGTERM, handle_sigterm)
            self._signal_handlers_installed = True
        except NotImplementedError:
            log.warning("Signal handlers not supported on this platform")

    async def hot_reload(self) -> None:
        """Hot reload fleet configuration."""
        log.info("Fleet hot reload initiated")
        
        # Reload fleet config
        # In practice, would reload from file
        # For now, signal all bots to hot reload
        for bot_id, bot in self.bots.items():
            try:
                await bot.engine.hot_reload()
            except Exception as e:
                log.error(f"Failed to hot reload bot {bot_id}: {e}")
        
        log.info("Fleet hot reload completed")

    async def scale_up(self, pair_config: PairConfig) -> bool:
        """Add a new bot to the fleet."""
        bot_id = f"{pair_config.exchange}_{pair_config.symbol.replace('/', '_')}"
        
        if bot_id in self.bots:
            log.warning(f"Bot {bot_id} already exists")
            return False
        
        await self._spawn_bot(pair_config)
        
        # Add to fleet config
        if pair_config.exchange == "kraken":
            self.fleet_config.pairs.append(pair_config)
        else:
            self.fleet_config.okx_pairs.append(pair_config)
        log.info(f"Scaled up: added {bot_id}")
        return True

    async def scale_down(self, bot_id: str) -> bool:
        """Remove a bot from the fleet."""
        if bot_id not in self.bots:
            return False
        
        bot = self.bots[bot_id]
        bot.status = "stopping"
        
        try:
            await bot.engine.stop()
        except Exception as e:
            log.error(f"Error stopping bot {bot_id}: {e}")
        
        if bot.task:
            bot.task.cancel()
            try:
                await bot.task
            except asyncio.CancelledError:
                pass
        
        del self.bots[bot_id]
        bot.status = "stopped"
        
        log.info(f"Scaled down: removed {bot_id}")
        return True

    async def stop(self) -> None:
        """Graceful fleet shutdown."""
        log.info("Stopping fleet...")
        self._running = False
        self._shutdown_event.set()
        
        # Stop all bots
        for bot_id, bot in self.bots.items():
            bot.status = "stopping"
            try:
                await bot.engine.stop()
            except Exception as e:
                log.error(f"Error stopping bot {bot_id}: {e}")
        
        # Cancel tasks
        for bot_id, bot in self.bots.items():
            if bot.task:
                bot.task.cancel()
                try:
                    await bot.task
                except asyncio.CancelledError:
                    pass
                # Stop monitoring
        for task in [self._health_task, self._rebalance_task, self._zmq_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        # Close ZMQ
        if self._zmq_sub:
            self._zmq_sub.close()
        if self._zmq_ctx:
            self._zmq_ctx.term()
                log.info("Fleet stopped")

    def get_fleet_status(self) -> Dict[str, Any]:
        """Get fleet-wide status."""
        total_equity = 0.0
        total_realized = 0.0
        total_unrealized = 0.0
        total_positions = 0
        total_orders = 0
        total_trades = 0
        
        bots_status = {}
        
        for bot_id, bot in self.bots.items():
            if bot.engine and bot.engine.state:
                state = bot.engine.state
                total_equity += state.equity
                total_realized += state.realized_pnl
                total_unrealized += state.unrealized_pnl
                total_positions += len(state.positions)
                total_orders += len(state.open_orders)
                total_trades += state.trades_count
                                bots_status[bot_id] = {
                    "status": bot.status,
                    "equity": round(state.equity, 2),
                    "realized_pnl": round(state.realized_pnl, 2),
                    "unrealized_pnl": round(state.unrealized_pnl, 2),
                    "drawdown_pct": round(state.drawdown * 100, 2),
                    "positions": len(state.positions),
                    "open_orders": len(state.open_orders),
                    "trades": state.trades_count,
                    "restart_count": bot.restart_count,
                    "last_health": bot.last_health_check,
                }
            else:
                bots_status[bot_id] = {
                    "status": bot.status,
                    "error": bot.error_message,
                }
                return {
            "fleet_equity": round(total_equity, 2),
            "fleet_realized_pnl": round(total_realized, 2),
            "fleet_unrealized_pnl": round(total_unrealized, 2),
            "total_positions": total_positions,
            "total_open_orders": total_orders,
            "total_trades": total_trades,
            "active_bots": len([b for b in self.bots.values() if b.status == "running"]),
            "total_bots": len(self.bots),
            "risk_status": self.risk_manager.get_status(),
            "bots": bots_status,
        }

    def get_bot_status(self, bot_id: str) -> Optional[Dict[str, Any]]:
        """Get status of specific bot."""
        if bot_id not in self.bots:
            return None
        
        bot = self.bots[bot_id]
        if not bot.engine or not bot.engine.state:
            return {"status": bot.status, "error": bot.error_message}
        
        state = bot.engine.state
        return {
            "bot_id": bot_id,
            "status": bot.status,
            "symbol": bot.config.symbol,
            "exchange": bot.config.exchange,
            "capital": bot.config.capital,
            "equity": round(state.equity, 2),
            "realized_pnl": round(state.realized_pnl, 2),
            "unrealized_pnl": round(state.unrealized_pnl, 2),
            "drawdown_pct": round(state.drawdown * 100, 2),
            "daily_loss_pct": round(state.daily_loss * 100, 2),
            "risk_level": state.risk_level.value if hasattr(state.risk_level, 'value') else str(state.risk_level),
            "kill_switch": state.kill_switch_armed,
            "regime": state.regime.value if hasattr(state.regime, 'value') else str(state.regime),
            "atr_pct": round(state.atr_pct, 2),
            "adx": round(state.adx, 1),
            "rsi": round(state.rsi, 1),
            "positions": len(state.positions),
            "open_orders": len(state.open_orders),
            "trades": state.trades_count,
            "wins": state.wins,
            "losses": state.losses,
            "loop_count": state.loop_count,
            "uptime_sec": int(time.time()) - state.start_ts,
            "grid_anchor": state.grid_anchor,
            "restart_count": bot.restart_count,
        }


async def main() -> None:
    """Main entry point for fleet coordinator."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Alpha-Omega Fleet Coordinator")
    parser.add_argument("--config", default=os.getenv("FLEET_CONFIG", "fleet_config.json"))
    args = parser.parse_args()
    
    coordinator = FleetCoordinator(args.config)
    
    try:
        await coordinator.initialize()
        
        # Keep running
        while coordinator._running:
            await asyncio.sleep(60)
                        # Print status periodically
            status = coordinator.get_fleet_status()
            log.info(f"Fleet status: equity={status['fleet_equity']:.2f}, bots={status['active_bots']}/{status['total_bots']}, positions={status['total_positions']}")
    
    except KeyboardInterrupt:
        await coordinator.stop()
    except Exception as e:
        log.exception(f"Fleet coordinator error: {e}")
        await coordinator.stop()


if __name__ == "__main__":
    asyncio.run(main())