"""
Unified Trading Engine for Alpha-Omega Trading System.

Merges: ShadowGrid v2 (production features) + neo (async performance).

Features:
- Async I/O with aiohttp + WebSocket
- Multiple strategies: Grid, DCA, Scalp, MeanReversion, Momentum, Arbitrage
- Paper/Live mode with identical logic
- Portfolio risk integration
- Redis Streams + SQLite state persistence
- Hot-reload via SIGHUP
- Circular buffers for memory efficiency
- ZeroMQ Pub/Sub for market data distribution
"""
from __future__ import annotations
import asyncio
import logging
import os
import signal
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any, Callable

log = logging.getLogger("alpha_omega.engine")

try:
    import aiohttp
except ImportError:
    log.critical("aiohttp required — pip install aiohttp")
    raise

from .config import Config, load_config_from_env, get_exchange_config, validate_exchange_config
from .types import (
    Signal, Position, Order, Ticker, OHLCV, Trade,
    StrategyType, MarketRegime, RiskLevel, BotStatus
)
from .buffers import (
    OhlcvBuffer, TickBuffer, CircularBuffer,
    compute_atr_adx_rsi, detect_regime, detect_volatility_regime,
    gc_if_heavy, memory_heavy
)
from .state import StateStore, init_state_store, get_state_store
from .exchange import (
    ExchangeAdapter, KrakenAdapter, OKXAdapter,
    create_exchange, Order as ExchangeOrder, Ticker as ExchangeTicker
)


@dataclass
class EngineState:
    """Runtime state of the trading engine."""
    status: BotStatus = BotStatus.STARTING
    symbol: str = ""
    exchange: str = ""
    capital: float = 0.0
    equity: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    drawdown: float = 0.0
    peak_equity: float = 0.0
    daily_loss: float = 0.0
    daily_start_equity: float = 0.0
    
    # Grid state
    grid_anchor: float = 0.0
    grid_levels: List[Dict] = field(default_factory=list)
    open_orders: Dict[str, Order] = field(default_factory=dict)
    positions: Dict[str, Position] = field(default_factory=dict)
    
    # Buffers
    ohlcv: Optional[OhlcvBuffer] = None
    ticks: Optional[TickBuffer] = None
    
    # Indicators
    atr_pct: float = 0.0
    adx: float = 0.0
    rsi: float = 50.0
    regime: MarketRegime = MarketRegime.UNKNOWN
    
    # Risk
    risk_level: RiskLevel = RiskLevel.NORMAL
    kill_switch_armed: bool = False
    
    # Stats
    trades_count: int = 0
    wins: int = 0
    losses: int = 0
    last_trade_ts: int = 0
    
    # Timing
    last_tick_ts: int = 0
    loop_count: int = 0
    start_ts: int = field(default_factory=lambda: int(time.time()))


class UnifiedTradingEngine:
    """
    Motore di trading unificato: ShadowGrid v2 + neo.
    
    Combina:
    - Grid trading ATR-adaptive (da ShadowGrid v2)
    - Multiple strategy support (da neo)
    - Async I/O + WebSocket (da neo)
    - Portfolio risk management (da ShadowGrid v2.1)
    - Redis Streams state sync (da neo)
    - Hot reload via SIGHUP
    - ZeroMQ Pub/Sub per distribuzione dati
    """

    __slots__ = (
        "config", "state", "exchange", "state_store",
        "_strategy", "_strategy_selector", "_risk_manager",
        "_running", "_loop_task", "_ws_task", "_health_task",
        "_zmq_pub", "_shutdown_event", "_signal_handlers_installed",
        "_atr_history"
    )

    def __init__(self, config: Config):
        self.config = config
        self.state = EngineState()
        self.exchange: Optional[ExchangeAdapter] = None
        self.state_store: Optional[StateStore] = None
        self._strategy = None
        self._strategy_selector = None
        self._risk_manager = None
        self._running = False
        self._loop_task: Optional[asyncio.Task] = None
        self._ws_task: Optional[asyncio.Task] = None
        self._health_task: Optional[asyncio.Task] = None
        self._zmq_pub = None
        self._shutdown_event = asyncio.Event()
        self._signal_handlers_installed = False
        
        # Initialize ATR history buffer (used by volatility regime detection)
        self._atr_history: List[float] = []

    async def initialize(self) -> None:
        """Initialize engine components."""
        log.info(f"Initializing engine: {self.config.exchange} {self.config.symbol} capital={self.config.capital} live={self.config.live_mode}")
        
        # Initialize state
        self.state.symbol = self.config.symbol
        self.state.exchange = self.config.exchange
        self.state.capital = self.config.capital
        self.state.equity = self.config.capital
        self.state.peak_equity = self.config.capital
        self.state.daily_start_equity = self.config.capital
        
        # Initialize buffers
        self.state.ohlcv = OhlcvBuffer(maxlen=self.config.ohlcv_window)
        self.state.ticks = TickBuffer(maxlen=self.config.tick_window)
        
        # Initialize exchange
        ex_cfg = get_exchange_config(self.config.exchange)
        if not validate_exchange_config(ex_cfg) and not self.config.live_mode:
            log.warning(f"No valid API keys for {self.config.exchange}, running in paper mode")
        
        # Use sandbox mode for paper trading (real infrastructure validation)
        sandbox_mode = not self.config.live_mode and self.config.use_sandbox
        
        self.exchange = create_exchange(
            self.config.exchange,
            api_key=ex_cfg["api_key"],
            api_secret=ex_cfg["api_secret"],
            passphrase=ex_cfg["passphrase"],
            paper_mode=not self.config.live_mode,
            sandbox_mode=sandbox_mode,
            sandbox_api_key=self.config.sandbox_api_key,
            sandbox_api_secret=self.config.sandbox_api_secret,
            sandbox_passphrase=self.config.sandbox_passphrase,
            rate_limit_rps=5.0,
            rate_limit_burst=10,
        )
        # Start connection pool for REST requests
        await self.exchange.pool.start()
        
        # Initialize state store
        self.state_store = await init_state_store(
            db_path=self.config.db_path,
            redis_url=os.getenv("REDIS_URL"),
            consumer_group="alpha_omega",
            consumer_name=f"engine_{self.config.symbol.replace('/', '_')}"
        )
        
        # Load persisted state
        await self._load_state()
        
        # Initialize strategy
        await self._init_strategy()
        
        # Initialize risk manager if enabled
        if self.config.risk_manager_enabled:
            from ..risk.manager import PortfolioRiskManager
            self._risk_manager = PortfolioRiskManager(
                max_portfolio_dd=self.config.max_portfolio_dd,
                max_daily_loss=self.config.max_daily_loss_pct,
                max_exposure_per_base=self.config.max_exposure_per_base,
                max_correlation=self.config.max_correlation,
                max_positions_per_base=self.config.max_positions_per_base,
                volatility_targeting=self.config.volatility_targeting,
            )
        
        # Initialize ZeroMQ publisher
        await self._init_zmq()
        
        # Install signal handlers
        self._install_signal_handlers()
        
        self.state.status = BotStatus.RUNNING
        log.info("Engine initialized successfully")

    async def _init_strategy(self) -> None:
        """Initialize trading strategy."""
        from ..strategies.grid import GridStrategy
        from ..strategies.selector import StrategySelector
        
        # For now, use GridStrategy as primary
        # Later: StrategySelector for regime-based switching
        self._strategy = GridStrategy(
            symbol=self.config.symbol,
            exchange=self.config.exchange,
            grid_levels=self.config.grid_levels,
            base_spread_pct=self.config.grid_spread,
            per_level=self.config.per_level,
            atr_multiplier=self.config.atr_spread_multiplier,
            min_spread_pct=self.config.min_spread_pct,
            max_spread_pct=self.config.max_spread_pct,
            drift_pct=self.config.drift_pct,
            use_momentum_filter=self.config.use_momentum_filter,
            hybrid_mode=self.config.hybrid_mode,
        )
        
        self._strategy_selector = StrategySelector(
            symbol=self.config.symbol,
            exchange=self.config.exchange,
        )
        log.info(f"Strategy initialized: {type(self._strategy).__name__}")

    async def _init_zmq(self) -> None:
        """Initialize ZeroMQ publisher for market data."""
        try:
            import zmq.asyncio
            ctx = zmq.asyncio.Context()
            self._zmq_pub = ctx.socket(zmq.PUB)
            self._zmq_pub.bind(f"tcp://*:{self.config.zmq_pub_port}")
            log.info(f"ZeroMQ publisher bound to port {self.config.zmq_pub_port}")
        except ImportError:
            log.warning("pyzmq not installed — ZeroMQ publishing disabled")
        except Exception as e:
            log.error(f"Failed to init ZeroMQ: {e}")

    def _install_signal_handlers(self) -> None:
        """Install SIGHUP/SIGTERM handlers for hot reload and graceful shutdown."""
        if self._signal_handlers_installed:
            return
        
        loop = asyncio.get_running_loop()
        
        def handle_sighup():
            log.info("SIGHUP received — hot reload triggered")
            asyncio.create_task(self.hot_reload())
        
        def handle_sigterm():
            log.info("SIGTERM received — graceful shutdown")
            asyncio.create_task(self.stop())
        
        try:
            loop.add_signal_handler(signal.SIGHUP, handle_sighup)
            loop.add_signal_handler(signal.SIGTERM, handle_sigterm)
            self._signal_handlers_installed = True
        except NotImplementedError:
            # Windows doesn't support add_signal_handler
            log.warning("Signal handlers not supported on this platform")

    async def _load_state(self) -> None:
        """Load persisted state from SQLite."""
        if not self.state_store:
            return
        
        try:
            # Load equity curve (last point)
            equity = await self.state_store.get_equity_curve(
                node=self.config.symbol.replace('/', '_'),
                limit=1
            )
            if equity:
                last = equity[0]
                self.state.equity = last.get("total_equity", self.config.capital)
                self.state.realized_pnl = last.get("realized_pnl", 0.0)
                self.state.unrealized_pnl = last.get("unrealized_pnl", 0.0)
                self.state.drawdown = last.get("drawdown", 0.0)
                self.state.peak_equity = self.state.equity + self.state.drawdown
            
            # Load open positions
            positions = await self.state_store.get_open_positions()
            for pos_data in positions:
                pos = Position(
                    symbol=pos_data["symbol"],
                    exchange=pos_data["exchange"],
                    base=pos_data["base"],
                    quote=pos_data["quote"],
                    size=pos_data["size"],
                    entry_price=pos_data["entry_price"],
                    current_price=pos_data["current_price"],
                    unrealized_pnl=pos_data["unrealized_pnl"],
                    realized_pnl=pos_data["realized_pnl"],
                    entry_timestamp=pos_data["entry_ts"],
                    strategy=pos_data["strategy"],
                )
                self.state.positions[pos.symbol] = pos
            
            # Load open orders
            orders = await self.state_store.get_open_orders(self.config.symbol)
            for ord_data in orders:
                order = Order(
                    id=ord_data["id"],
                    symbol=ord_data["symbol"],
                    exchange=ord_data["exchange"],
                    side=ord_data["side"],
                    type=ord_data["type"],
                    price=ord_data["price"],
                    amount=ord_data["amount"],
                    filled=ord_data["filled"],
                    status=ord_data["status"],
                    fee=ord_data["fee"],
                    fee_currency=ord_data["fee_currency"],
                    timestamp=ord_data["created_ts"],
                    strategy=ord_data["strategy"],
                )
                self.state.open_orders[order.id] = order
            
            log.info(f"State loaded: equity={self.state.equity:.2f}, positions={len(self.state.positions)}, orders={len(self.state.open_orders)}")
        except Exception as e:
            log.error(f"Failed to load state: {e}")

    async def _save_state(self) -> None:
        """Save current state to SQLite and Redis Streams."""
        if not self.state_store:
            return
        
        try:
            # Save equity snapshot
            await self.state_store.save_equity({
                "node": self.config.symbol.replace('/', '_'),
                "total_equity": self.state.equity,
                "realized_pnl": self.state.realized_pnl,
                "unrealized_pnl": self.state.unrealized_pnl,
                "drawdown": self.state.drawdown,
                "timestamp": int(time.time()),
            })
            
            # Save positions
            for pos in self.state.positions.values():
                await self.state_store.save_position({
                    "symbol": pos.symbol,
                    "exchange": pos.exchange,
                    "base": pos.base,
                    "quote": pos.quote,
                    "size": pos.size,
                    "entry_price": pos.entry_price,
                    "current_price": pos.current_price,
                    "unrealized_pnl": pos.unrealized_pnl,
                    "realized_pnl": pos.realized_pnl,
                    "entry_timestamp": pos.entry_timestamp,
                    "last_update": int(time.time()),
                    "strategy": pos.strategy,
                })
            
            # Save orders
            for order in self.state.open_orders.values():
                await self.state_store.save_order(order.to_dict())
                
        except Exception as e:
            log.error(f"Failed to save state: {e}")

    # ── Main Loop ────────────────────────────────────────────────────────

    async def run(self) -> None:
        """Main trading loop."""
        if not self.exchange:
            await self.initialize()
        
        self._running = True
        
        # Start WebSocket
        self._ws_task = asyncio.create_task(self.exchange.start_ws([self.config.symbol]))
        
        # Register WS callbacks
        self.exchange.on("ticker", self._on_ticker)
        self.exchange.on("trade", self._on_trade)
        
        # Start health server
        self._health_task = asyncio.create_task(self._health_server())
        
        log.info(f"Engine running: {self.config.symbol} on {self.config.exchange}")
        
        try:
            while self._running and not self._shutdown_event.is_set():
                await self._tick()
                await asyncio.sleep(self.config.cooldown_sec)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            log.exception(f"Engine loop error: {e}")
        finally:
            await self._cleanup()

    async def _tick(self) -> None:
        """Single trading tick: fetch data, compute indicators, generate signals, execute."""
        self.state.loop_count += 1
        self.state.last_tick_ts = int(time.time())
        
        try:
            # 1. Fetch market data
            ticker = await self.exchange.get_ticker(self.config.symbol)
            ohlcv = await self.exchange.get_ohlcv(self.config.symbol, "1m", self.config.ohlcv_window)
            
            # 2. Update buffers
            self._update_buffers(ticker, ohlcv)
            
            # 3. Compute indicators
            self._compute_indicators()
            
            # 4. Detect regime
            self._detect_regime()
            
            # 5. Risk checks
            if not await self._check_risk():
                return
            
            # 6. Generate signals from strategy
            if self.state.ohlcv and self.state.ohlcv.size >= 20:
                signal = await self._strategy.generate_signal(
                    ohlcv=self.state.ohlcv,
                    current_price=ticker.last,
                    atr_pct=self.state.atr_pct,
                    adx=self.state.adx,
                    rsi=self.state.rsi,
                    regime=self.state.regime,
                    equity=self.state.equity,
                    positions=self.state.positions,
                    open_orders=self.state.open_orders,
                )
                
                if signal:
                    await self._execute_signal(signal)
            
            # 7. Manage open orders (check fills, timeouts)
            await self._manage_orders(ticker)
            
            # 8. Update capital from exchange balance (every 60 ticks ~ 1 min)
            if self.state.loop_count % 60 == 0:
                self.state.capital = await self._fetch_exchange_balance()
            
            # 9. Update equity
            self._update_equity(ticker)
            
            # 10. Publish to ZeroMQ
            await self._publish_market_data(ticker)
            
            # 10. Periodic state save (every 10 ticks)
            if self.state.loop_count % 10 == 0:
                await self._save_state()
                gc_if_heavy("periodic save")
                
        except Exception as e:
            log.error(f"Tick error: {e}")
            # Don't crash the loop, just log and continue

    def _update_buffers(self, ticker: ExchangeTicker, ohlcv: List[OHLCV]) -> None:
        """Update circular buffers with new data."""
        if self.state.ohlcv:
            # Add latest candle if new
            if ohlcv:
                latest = ohlcv[-1]
                self.state.ohlcv.append(
                    latest.timestamp, latest.open, latest.high,
                    latest.low, latest.close, latest.volume
                )
        
        if self.state.ticks:
            self.state.ticks.append(ticker.last, ticker.volume, ticker.timestamp, 0)
        
        # Update current price in state
        self.state.equity = self.state.equity  # Will be recalculated in _update_equity

    def _compute_indicators(self) -> None:
        """Compute ATR, ADX, RSI from OHLCV buffer."""
        if self.state.ohlcv and self.state.ohlcv.size >= 20:
            with memory_heavy("ATR/ADX/RSI"):
                self.state.atr_pct, self.state.adx, self.state.rsi = compute_atr_adx_rsi(
                    self.state.ohlcv, period=14
                )

    def _detect_regime(self) -> None:
        """Detect market regime."""
        regime_info = detect_regime(self.state.adx, self.state.rsi)
        try:
            self.state.regime = MarketRegime(regime_info["regime"])
        except ValueError:
            self.state.regime = MarketRegime.UNKNOWN
        
        # Volatility regime
        if hasattr(self, '_atr_history'):
            self._atr_history.append(self.state.atr_pct)
        else:
            self._atr_history = [self.state.atr_pct]
        
        if len(self._atr_history) > 100:
            self._atr_history = self._atr_history[-100:]
        
        if len(self._atr_history) >= 20:
            vol_info = detect_volatility_regime(self.state.atr_pct, self._atr_history)
            # Could adjust grid parameters based on vol_info["action"]

    async def _check_risk(self) -> bool:
        """Check risk limits. Returns True if trading allowed."""
        # Bot-level drawdown
        if self.state.equity > 0:
            current_dd = (self.state.peak_equity - self.state.equity) / self.state.peak_equity
            self.state.drawdown = current_dd
            
            if current_dd >= self.config.max_drawdown_pct:
                self.state.risk_level = RiskLevel.CRITICAL
                self.state.kill_switch_armed = True
                log.critical(f"MAX DRAWDOWN HIT: {current_dd:.2%} >= {self.config.max_drawdown_pct:.2%} — KILL SWITCH ARMED")
                await self._trigger_kill_switch("max_drawdown")
                return False
            elif current_dd >= self.config.max_drawdown_pct * 0.7:
                self.state.risk_level = RiskLevel.WARNING
        
        # Bot-level daily loss - skip if equity not initialized
        if self.state.daily_start_equity > 0 and self.state.equity > 0:
            daily_loss_pct = (self.state.daily_start_equity - self.state.equity) / self.state.daily_start_equity
            self.state.daily_loss = daily_loss_pct
            
            if daily_loss_pct >= self.config.max_daily_loss_pct:
                self.state.risk_level = RiskLevel.CRITICAL
                log.critical(f"DAILY LOSS LIMIT HIT: {daily_loss_pct:.2%} >= {self.config.max_daily_loss_pct:.2%}")
                return False
            elif daily_loss_pct >= self.config.max_daily_loss_pct * 0.7:
                self.state.risk_level = RiskLevel.WARNING
        else:
            self.state.daily_loss = 0.0
        
        # Portfolio-level risk (if risk manager enabled)
        if self._risk_manager:
            risk_ok = await self._risk_manager.check_limits(
                equity=self.state.equity,
                positions=self.state.positions,
                daily_pnl=self.state.realized_pnl + self.state.unrealized_pnl - self.state.daily_start_equity,
            )
            if not risk_ok:
                return False
        
        return True

    async def _execute_signal(self, signal: Signal) -> None:
        """Execute trading signal."""
        if not signal or signal.action == "hold":
            return
        
        # Check order limits
        if len(self.state.open_orders) >= self.config.max_open_orders:
            log.warning(f"Max open orders reached ({self.config.max_open_orders})")
            return
        
        # Create order
        try:
            order = await self.exchange.create_order(
                symbol=self.config.symbol,
                side=signal.side,
                type=signal.order_type,
                amount=signal.amount,
                price=signal.price,
                client_order_id=f"{self.config.symbol}_{int(time.time()*1000)}",
                strategy=signal.strategy or type(self._strategy).__name__,
            )
            
            self.state.open_orders[order.id] = Order(
                id=order.id,
                symbol=order.symbol,
                exchange=order.exchange,
                side=order.side,
                type=order.type,
                price=order.price,
                amount=order.amount,
                filled=order.filled,
                status=order.status,
                fee=order.fee,
                fee_currency=order.fee_currency,
                timestamp=order.timestamp,
                client_order_id=order.client_order_id,
                strategy=order.strategy,
            )
            
            log.info(f"Order created: {order.side} {order.amount} {order.symbol} @ {order.price:.6f} ({order.id})")
            
            # Save order
            if self.state_store:
                await self.state_store.save_order(order.to_dict())
                
        except Exception as e:
            log.error(f"Failed to execute signal: {e}")

    async def _manage_orders(self, ticker: ExchangeTicker) -> None:
        """Check order fills, handle timeouts."""
        to_remove = []
        
        for order_id, order in self.state.open_orders.items():
            if order.status == "filled":
                # Order filled - create position or update existing
                await self._on_order_filled(order, ticker)
                to_remove.append(order_id)
            elif order.status in ("cancelled", "rejected"):
                to_remove.append(order_id)
            elif order.status == "open" and order.type == "limit":
                # Check if limit order should be cancelled (price moved too far)
                # This is simplified - in production, check against grid anchor drift
                pass
        
        for order_id in to_remove:
            del self.state.open_orders[order_id]
            if self.state_store:
                # Update order status in DB
                pass

    async def _on_order_filled(self, order: Order, ticker: ExchangeTicker) -> None:
        """Handle filled order - update position and PnL."""
        # Create or update position
        if order.symbol not in self.state.positions:
            pos = Position(
                symbol=order.symbol,
                exchange=order.exchange,
                base=order.symbol.split("/")[0],
                quote=order.symbol.split("/")[1],
                size=order.filled if order.side == "buy" else -order.filled,
                entry_price=order.price,
                current_price=ticker.last,
                unrealized_pnl=0.0,
                realized_pnl=0.0,
                entry_timestamp=int(time.time()),
                strategy=order.strategy,
            )
            self.state.positions[order.symbol] = pos
        else:
            pos = self.state.positions[order.symbol]
            # Average down/up logic
            if (pos.size > 0 and order.side == "buy") or (pos.size < 0 and order.side == "sell"):
                total_size = abs(pos.size) + order.filled
                pos.entry_price = (pos.entry_price * abs(pos.size) + order.price * order.filled) / total_size
                pos.size = total_size if order.side == "buy" else -total_size
            else:
                # Reducing position - calculate realized PnL
                closed_size = min(abs(pos.size), order.filled)
                pnl = (order.price - pos.entry_price) * closed_size * (1 if pos.size > 0 else -1)
                pos.realized_pnl += pnl
                pos.size += order.filled if order.side == "buy" else -order.filled
                
                if abs(pos.size) < 1e-8:
                    # Position closed
                    del self.state.positions[order.symbol]
                    self.state.trades_count += 1
                    if pnl > 0:
                        self.state.wins += 1
                    else:
                        self.state.losses += 1
                    self.state.last_trade_ts = int(time.time())
                    
                    # Save trade
                    if self.state_store:
                        await self.state_store.save_trade({
                            "trade_id": f"trade_{int(time.time()*1000)}",
                            "symbol": order.symbol,
                            "exchange": order.exchange,
                            "side": "buy" if pos.size > 0 else "sell",
                            "entry_price": pos.entry_price,
                            "exit_price": order.price,
                            "amount": closed_size,
                            "pnl_pct": pnl / (pos.entry_price * closed_size) if pos.entry_price > 0 else 0,
                            "pnl_abs": pnl,
                            "fee": order.fee,
                            "fee_currency": order.fee_currency,
                            "entry_timestamp": pos.entry_timestamp,
                            "exit_timestamp": int(time.time()),
                            "status": "closed",
                            "strategy": order.strategy,
                            "hold_time_seconds": int(time.time()) - pos.entry_timestamp,
                        })
        
        pos.current_price = ticker.last
        pos.unrealized_pnl = (ticker.last - pos.entry_price) * pos.size

    async def _fetch_exchange_balance(self) -> float:
        """Fetch real balance from exchange."""
        if not self.exchange or not self.config.live_mode:
            return self.config.capital
        
        try:
            balance = await self.exchange.fetch_balance()
            if balance and 'free' in balance:
                # Sum all non-zero balances
                total = sum(float(v) for v in balance['free'].values() if v and float(v) > 0)
                return total if total > 0 else self.config.capital
        except Exception as e:
            log.warning(f"Failed to fetch balance: {e}")
        
        return self.config.capital

    def _update_equity(self, ticker: ExchangeTicker) -> None:
        """Recalculate total equity."""
        unrealized = sum(pos.unrealized_pnl for pos in self.state.positions.values())
        self.state.unrealized_pnl = unrealized
        self.state.equity = self.state.capital + self.state.realized_pnl + unrealized
        
        if self.state.equity > self.state.peak_equity:
            self.state.peak_equity = self.state.equity
        
        # Check daily reset
        if time.time() - self.state.start_ts > 86400:
            self.state.daily_start_equity = self.state.equity
            self.state.start_ts = int(time.time())
            self.state.daily_loss = 0.0
            self.state.risk_level = RiskLevel.NORMAL
            self.state.kill_switch_armed = False
            log.info("Daily reset: new day started")

    async def _publish_market_data(self, ticker: ExchangeTicker) -> None:
        """Publish market data to ZeroMQ."""
        if not self._zmq_pub:
            return
        
        try:
            import zmq
            msg = {
                "symbol": self.config.symbol,
                "exchange": self.config.exchange,
                "price": ticker.last,
                "bid": ticker.bid,
                "ask": ticker.ask,
                "volume": ticker.volume,
                "spread_pct": ticker.spread_pct,
                "timestamp": ticker.timestamp,
                "equity": self.state.equity,
                "unrealized_pnl": self.state.unrealized_pnl,
                "drawdown": self.state.drawdown,
                "regime": self.state.regime.value,
                "atr_pct": self.state.atr_pct,
                "adx": self.state.adx,
                "rsi": self.state.rsi,
            }
            await self._zmq_pub.send_json(msg)
        except Exception as e:
            log.debug(f"ZMQ publish error: {e}")

    async def _on_ticker(self, ticker: ExchangeTicker) -> None:
        """WebSocket ticker callback."""
        # Update internal state with real-time price
        pass

    async def _on_trade(self, trade: Dict) -> None:
        """WebSocket trade callback."""
        if self.state.ticks:
            self.state.ticks.append(
                trade["price"], trade["volume"],
                trade["timestamp"], trade["side"]
            )

    async def _health_server(self) -> None:
        """HTTP health endpoint on 127.0.0.1."""
        from aiohttp import web
        
        async def health(request):
            return web.json_response({
                "status": self.state.status.value,
                "symbol": self.config.symbol,
                "exchange": self.config.exchange,
                "equity": round(self.state.equity, 2),
                "realized_pnl": round(self.state.realized_pnl, 2),
                "unrealized_pnl": round(self.state.unrealized_pnl, 2),
                "drawdown_pct": round(self.state.drawdown * 100, 2),
                "daily_loss_pct": round(self.state.daily_loss * 100, 2),
                "risk_level": self.state.risk_level.value,
                "kill_switch": self.state.kill_switch_armed,
                "regime": self.state.regime.value,
                "atr_pct": round(self.state.atr_pct, 2),
                "adx": round(self.state.adx, 1),
                "rsi": round(self.state.rsi, 1),
                "positions": len(self.state.positions),
                "open_orders": len(self.state.open_orders),
                "trades": self.state.trades_count,
                "wins": self.state.wins,
                "losses": self.state.losses,
                "loop_count": self.state.loop_count,
                "uptime_sec": int(time.time()) - self.state.start_ts,
                "last_tick": self.state.last_tick_ts,
                "grid_anchor": self.state.grid_anchor,
                "grid_levels": len(self.state.grid_levels),
            })
        
        async def risk(request):
            if not self._risk_manager:
                return web.json_response({"error": "Risk manager not enabled"}, status=404)
            return web.json_response(self._risk_manager.get_status())
        
        app = web.Application()
        app.router.add_get("/health", health)
        app.router.add_get("/risk", risk)
        
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", self.config.health_port)
        await site.start()
        
        log.info(f"Health server started on 127.0.0.1:{self.config.health_port}")
        
        try:
            while self._running:
                await asyncio.sleep(60)
        except asyncio.CancelledError:
            pass
        finally:
            await runner.cleanup()

    async def _trigger_kill_switch(self, reason: str) -> None:
        """Activate kill switch - close all positions, cancel all orders."""
        log.critical(f"KILL SWITCH TRIGGERED: {reason}")
        
        # Cancel all open orders
        for order_id, order in list(self.state.open_orders.items()):
            try:
                await self.exchange.cancel_order(order_id, order.symbol)
                order.status = "cancelled"
            except Exception as e:
                log.error(f"Failed to cancel order {order_id}: {e}")
        
        # In live mode, would also close positions
        # For now, just stop trading
        self._running = False
        
        # Save kill switch event
        if self.state_store:
            await self.state_store.save_risk_metrics({
                "event": "kill_switch",
                "reason": reason,
                "equity": self.state.equity,
                "drawdown": self.state.drawdown,
                "timestamp": int(time.time()),
            })

    async def hot_reload(self) -> None:
        """Hot reload configuration without restart."""
        log.info("Hot reload initiated")
        
        # Reload config from environment
        new_config = load_config_from_env()
        
        # Update config
        self.config.grid_levels = new_config.grid_levels
        self.config.grid_spread = new_config.grid_spread
        self.config.use_momentum_filter = new_config.use_momentum_filter
        self.config.max_drawdown_pct = new_config.max_drawdown_pct
        self.config.max_daily_loss_pct = new_config.max_daily_loss_pct
        self.config.atr_spread_multiplier = new_config.atr_spread_multiplier
        self.config.min_spread_pct = new_config.min_spread_pct
        self.config.max_spread_pct = new_config.max_spread_pct
        self.config.drift_pct = new_config.drift_pct
        self.config.hybrid_mode = new_config.hybrid_mode
        self.config.cooldown_sec = new_config.cooldown_sec
        
        # Update strategy params
        if self._strategy:
            self._strategy.grid_levels = new_config.grid_levels
            self._strategy.base_spread_pct = new_config.grid_spread
            self._strategy.use_momentum_filter = new_config.use_momentum_filter
            self._strategy.hybrid_mode = new_config.hybrid_mode
        
        log.info("Hot reload completed")

    async def stop(self) -> None:
        """Graceful shutdown."""
        log.info("Stopping engine...")
        self._running = False
        self._shutdown_event.set()
        
        await self._cleanup()
        log.info("Engine stopped")

    async def _cleanup(self) -> None:
        """Cleanup resources."""
        if self._ws_task:
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass
        
        if self._health_task:
            self._health_task.cancel()
            try:
                await self._health_task
            except asyncio.CancelledError:
                pass
        
        if self.exchange:
            await self.exchange.stop_ws()
        
        if self._zmq_pub:
            self._zmq_pub.close()
        
        if self.state_store:
            await self._save_state()
            await self.state_store.close()
        
        self.state.status = BotStatus.STOPPED


# ─── Entry Point ────────────────────────────────────────────────────────

async def main() -> None:
    """Main entry point for running a single bot."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Alpha-Omega Trading Engine")
    parser.add_argument("--symbol", default=os.getenv("SYMBOL", "DOGE/EUR"))
    parser.add_argument("--exchange", default=os.getenv("EXCHANGE", "kraken"))
    parser.add_argument("--capital", type=float, default=float(os.getenv("CAPITAL", "50")))
    parser.add_argument("--live", action="store_true", default=os.getenv("LIVE_MODE", "0") == "1")
    parser.add_argument("--health-port", type=int, default=int(os.getenv("HEALTH_PORT", "8911")))
    args = parser.parse_args()
    
    # Set env vars for config loading
    os.environ["SYMBOL"] = args.symbol
    os.environ["EXCHANGE"] = args.exchange
    os.environ["CAPITAL"] = str(args.capital)
    os.environ["LIVE_MODE"] = "1" if args.live else "0"
    os.environ["HEALTH_PORT"] = str(args.health_port)
    
    config = load_config_from_env()
    engine = UnifiedTradingEngine(config)
    
    try:
        await engine.run()
    except KeyboardInterrupt:
        await engine.stop()


if __name__ == "__main__":
    asyncio.run(main())