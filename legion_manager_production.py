#!/usr/bin/env python3
"""
LEGION MANAGER PRODUCTION v4.2 — Denaro Core Trading Engine
============================================================
FIXES v4.1 → v4.2:
  ✅ CRITICAL: SCALP vol spike bug — rimosso confronto candle incompleta vs avg (sempre false)
  ✅ CRITICAL: Boost mai attivo — last_trade_time=0 → time.time() (boost parte subito)
  ✅ CRITICAL: Volume filter — confrontava volume 24h (WS) vs volume 1m (OHLCV) (oranges vs apples)
  ✅ CRITICAL: Soglie segnali rilassate per ranging (DIP_BUY 0.15%, MOMENTUM 1 uptick, RSI più larghi)
  ✅ FIX: Breakeven buffer 0.2% (era 0.4%) — blocca profitti prima
  ✅ FIX: MIN_VOLUME_MULT=1.0 (era 1.5) — non blocca volumi normali
"""

import asyncio
import ccxt.async_support as ccxt
import os, json, time, logging, sys
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

import pandas as pd
import numpy as np
import websockets

# ── pandas_ta fallback ──────────────────────────────────────────────
try:
    import pandas_ta as ta
    HAS_PANDAS_TA = True
except ImportError:
    HAS_PANDAS_TA = False

from exchange_multi import ExchangeRouter
from trade_db import TradeDB
from auto_adaptive_engine import AutoAdaptiveEngine  # self-learning module


# ═══════════════════════════════════════════════════════════════════
# Native indicators (fallback when pandas_ta unavailable)
# ═══════════════════════════════════════════════════════════════════
EPSILON = 1e-10  # prevents division-by-zero in RSI

def np_rsi(series: pd.Series, length: int = 14) -> pd.Series:
    """RSI with epsilon protection against div-by-zero."""
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1/length, min_periods=length).mean()
    avg_loss = loss.ewm(alpha=1/length, min_periods=length).mean()
    avg_loss = avg_loss.replace(0, EPSILON)  # FIX: no div-by-zero
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.clip(0, 100)  # FIX: clamp to [0, 100]


def np_atr(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14) -> pd.Series:
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.ewm(alpha=1/length, min_periods=length).mean()


def np_ema(series: pd.Series, length: int = 50) -> pd.Series:
    return series.ewm(span=length, adjust=False).mean()


# ═══════════════════════════════════════════════════════════════════
# Config & Constants
# ═══════════════════════════════════════════════════════════════════
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

# ── Logger FIX: single handler, no duplicate lines ───────────
log_file = os.path.join(BASE_DIR, "legion_production.log")
_handler = logging.FileHandler(log_file)
_handler.setFormatter(logging.Formatter('%(asctime)s - [LEGION-PROD] - %(message)s'))

logging.basicConfig(
    level=logging.DEBUG if os.getenv('DEBUG_LOG', '').lower() == 'true' else logging.INFO,
    handlers=[_handler],          # only file handler — no StreamHandler to avoid duplication
)
logger = logging.getLogger('LegionProd')

FEE_RATE = 0.001           # Binance spot taker: 0.1% per side
FEE_RT = FEE_RATE * 2      # Round-trip: 0.2%
MIN_NOTIONAL = 10.0        # Binance minimum order value (EUR/USDT pairs)
INITIAL_CAPITAL = max(float(os.getenv('INITIAL_CAPITAL', '0')), 225.0)  # v5.0: actual EUR balance

# Risk limits
MAX_GLOBAL_EXPOSURE = float(os.getenv('MAX_GLOBAL_EXPOSURE', '200.0'))
MAX_CONCURRENT_POSITIONS = int(os.getenv('MAX_CONCURRENT_POSITIONS', '4'))
DAILY_LOSS_LIMIT_PCT = float(os.getenv('DAILY_LOSS_LIMIT_PCT', '-3.0'))
PER_SYMBOL_MAX_EUR = float(os.getenv('PER_SYMBOL_MAX_EUR', '30.0'))

# Volume filter
MIN_VOLUME_MULT = float(os.getenv('MIN_VOLUME_MULT', '1.0'))  # BUGFIX: era 1.5 — bloccava tutto in ranging
VOLUME_WINDOW = 20  # candles for average volume

# Indicator lengths
RSI_LENGTH = int(os.getenv('RSI_LENGTH', '9'))        # fast RSI for scalping
EMA_LENGTH = int(os.getenv('EMA_LENGTH', '20'))       # fast EMA
ATR_LENGTH = int(os.getenv('ATR_LENGTH', '7'))        # fast ATR
OHLCV_LIMIT = int(os.getenv('OHLCV_LIMIT', '100'))

# Strategy parameters
TP_ATR_MULT = float(os.getenv('TP_ATR_MULT', '8.0'))
SL_ATR_MULT = float(os.getenv('SL_ATR_MULT', '3.0'))
MIN_TP_PCT = float(os.getenv('MIN_TP_PCT', '0.003'))  # 0.3% minimo TP (copre fee 0.2% + 0.1% profitto)
MIN_SL_PCT = float(os.getenv('MIN_SL_PCT', '0.0015'))  # 0.15% minimo SL
TRAILING_ACTIVATION = float(os.getenv('TRAILING_ACTIVATION', '3.0'))
BREAKEVEN_BUFFER = float(os.getenv('BREAKEVEN_BUFFER', '0.002'))  # v4.2: 0.2% (era 0.4%) — blocca profitti prima

# Trading hours filter
TRADING_HOURS_START = int(os.getenv('TRADING_HOURS_START', '6'))
TRADING_HOURS_END = int(os.getenv('TRADING_HOURS_END', '22'))

# v4.2: Signal aggression parameters — RELAXATI per mercato range-bound
DIP_BUY_THRESHOLD = float(os.getenv('DIP_BUY_THRESHOLD', '0.0015'))  # 0.15% (era 0.3% — troppo per ranging)
DIP_BUY_THRESHOLD_5 = float(os.getenv('DIP_BUY_THRESHOLD_5', '0.0025'))  # 0.25% (era 0.5%)
RSI_OVERSOLD = float(os.getenv('RSI_OVERSOLD', '50'))  # era 40 — RSI <50 è già un mini-dip
SCALP_RSI_MAX = float(os.getenv('SCALP_RSI_MAX', '55'))  # era 45 — RSI <55 per più entry

# v4.1: Time-decay — after N idle minutes, widen signals
IDLE_MINUTES_BOOST = int(os.getenv('IDLE_MINUTES_BOOST', '5'))  # after 5 min idle
BOOST_FACTOR = float(os.getenv('BOOST_FACTOR', '1.5'))  # multiply thresholds by 1.5x

# Strategy modes
STRATEGY_MODES = ['DIP_BUY', 'MOMENTUM', 'MEAN_REVERSION', 'SCALP']


# ═══════════════════════════════════════════════════════════════════
# Symbol definitions (14 core Binance pairs — reduced from 28)
# ═══════════════════════════════════════════════════════════════════
SYMBOLS_WS = [
    'btceur', 'etheur', 'xrpeur', 'soleur', 'dogeeur',
    'bnbeur', 'adaeur', 'suieur', 'etceur', 'maticeur',
    'ftmeur', 'unieur', 'zileur', 'wifeur'
]
# v5.0: MiCA fix — Binance Italia/EU account only supports EUR pairs
SYMBOLS_CCXT = [s.upper().replace('EUR', '/EUR').replace('USDT', '/USDT') for s in SYMBOLS_WS]

MAX_ACTIVE_SYMBOLS = 12


# ═══════════════════════════════════════════════════════════════════
# Market regime detection
# ═══════════════════════════════════════════════════════════════════
class MarketRegime:
    """Detects trending / ranging / volatile regimes using ADX + ATR."""
    def __init__(self):
        self.cache = {}
        self.cache_ttl = 300

    def classify(self, ohlcv_df: pd.DataFrame) -> str:
        if ohlcv_df is None or len(ohlcv_df) < 30:
            return 'RANGING'
        closes = ohlcv_df['close']
        highs = ohlcv_df['high']
        lows = ohlcv_df['low']
        atr_val = np_atr(highs, lows, closes, length=14).iloc[-1]
        atr_pct = (atr_val / closes.iloc[-1]) * 100 if closes.iloc[-1] > 0 else 0
        range_5 = closes.iloc[-5:].max() - closes.iloc[-5:].min()
        range_20 = closes.iloc[-20:].max() - closes.iloc[-20:].min()
        if range_20 > 0:
            adx_approx = (range_5 / range_20) * 100
        else:
            adx_approx = 25
        if atr_pct > 2.5:
            return 'VOLATILE'
        elif adx_approx > 40:
            return 'TRENDING'
        else:
            return 'RANGING'


# ═══════════════════════════════════════════════════════════════════
# ExposureGuard — SQLite-backed
# ═══════════════════════════════════════════════════════════════════
class ExposureGuard:
    def __init__(self, db: TradeDB):
        self.db = db

    def get_exposure(self) -> dict:
        return self.db.get_exposure()

    async def update_exposure(self, symbol: str, amount: float, action: str) -> None:
        if action == 'open':
            self.db.upsert_exposure(symbol, amount)
        elif action == 'close':
            self.db.remove_exposure(symbol)


# ═══════════════════════════════════════════════════════════════════
# PriceFeed — WebSocket Binance
# ═══════════════════════════════════════════════════════════════════
class PriceFeed:
    def __init__(self):
        self.prices: dict[str, float] = {}
        self.volumes: dict[str, float] = {}
        self.active = True
        self.last_heartbeat = time.time()

    async def start(self):
        streams = "/".join([f"{s}@ticker" for s in SYMBOLS_WS])
        url = f"wss://stream.binance.com:9443/stream?streams={streams}"
        while self.active:
            try:
                async with websockets.connect(
                    url,
                    ping_interval=180,
                    ping_timeout=600,
                    open_timeout=10,
                    close_timeout=10
                ) as ws:
                    logger.info("✅ WebSocket connesso a Binance !ticker@arr")
                    while self.active:
                        data = await ws.recv()
                        payload = json.loads(data)
                        d = payload.get('data', {})
                        s = d.get('s', '').lower()
                        if s in SYMBOLS_WS:
                            self.prices[s] = float(d.get('c', 0))
                            self.volumes[s] = float(d.get('v', 0))
                            self.last_heartbeat = time.time()
            except Exception as e:
                logger.error(f"❌ WebSocket Error: {e}. Reconnecting in 10s...")
                await asyncio.sleep(10)


# ═══════════════════════════════════════════════════════════════════
# RiskManager — centralized risk control
# ═══════════════════════════════════════════════════════════════════
class RiskManager:
    def __init__(self, db: TradeDB, exposure_guard: ExposureGuard, adaptive_engine=None):
        self.db = db
        self.exposure_guard = exposure_guard
        self.adaptive_engine = adaptive_engine
        self.max_exposure = MAX_GLOBAL_EXPOSURE
        self.max_positions = MAX_CONCURRENT_POSITIONS
        self.daily_loss_limit = DAILY_LOSS_LIMIT_PCT
        self._balance_cache = {}
        self._balance_ts = 0
        self._rate_limit_sem = asyncio.Semaphore(5)
        # v4.2: BUGFIX — init last_trade_time to now so boost is active on first boot
        self.last_trade_time = time.time()  # was 0.0 — boost never activated

    def get_total_eur(self) -> float:
        return self._balance_cache.get('total_eur', 0.0)

    def authorize_trade(self, symbol: str, amount: float, side: str = 'BUY') -> tuple[bool, str]:
        exp = self.exposure_guard.get_exposure()
        if exp['total'] + amount > self.max_exposure:
            return False, f"exposure {exp['total']}+{amount} > {self.max_exposure}"
        if len(exp['positions']) >= self.max_positions:
            return False, f"max positions ({self.max_positions}) reached"
        if symbol in exp['positions']:
            return False, f"{symbol} already in position"
        if self.adaptive_engine:
            if not self.adaptive_engine.should_trade_symbol(symbol):
                return False, f"{symbol} disabled by adaptive engine"
        daily_pnl = self.db.get_daily_pnl()
        if daily_pnl != 0:
            daily_pnl_pct = (daily_pnl / INITIAL_CAPITAL) * 100
            if daily_pnl_pct <= self.daily_loss_limit:
                return False, f"daily loss limit ({daily_pnl_pct:.1f}%)"
        return True, "OK"

    async def is_trading_hours(self) -> bool:
        hour = datetime.now(timezone.utc).hour
        if TRADING_HOURS_START <= hour < TRADING_HOURS_END:
            return True
        return False

    def record_trade(self):
        """Called when a trade opens or closes to update idle timer."""
        self.last_trade_time = time.time()

    def get_idle_boost(self) -> float:
        """Returns multiplier for signal thresholds based on idle time.
        1.0 = normal, up to BOOST_FACTOR after IDLE_MINUTES_BOOST."""
        # v4.2: removed ==0 guard — now always initialized to time.time()
        idle_seconds = time.time() - self.last_trade_time
        idle_minutes = idle_seconds / 60
        if idle_minutes >= IDLE_MINUTES_BOOST:
            # Linearly increase from 1.0 to BOOST_FACTOR
            boost = 1.0 + (BOOST_FACTOR - 1.0) * min(1.0, (idle_minutes - IDLE_MINUTES_BOOST) / IDLE_MINUTES_BOOST)
            return boost
        return 1.0


# ═══════════════════════════════════════════════════════════════════
# LegionBot — single-symbol trading bot
# ═══════════════════════════════════════════════════════════════════
class LegionBot:
    def __init__(self, exchange, symbol_ws: str, symbol_ccxt: str,
                 db: TradeDB, exposure_guard: ExposureGuard,
                 adaptive_engine=None, exchange_name: str = 'binance'):
        self.exchange = exchange
        self.exchange_name = exchange_name
        self.symbol_ws = symbol_ws
        self.symbol_ccxt = symbol_ccxt
        self.db = db
        self.exposure_guard = exposure_guard
        self.adaptive = adaptive_engine
        self.regime_detector = MarketRegime()

        # Position state
        self.position = False
        self.buy_price = 0.0
        self.qty = 0.0
        self.current_tp = 0.0
        self.current_sl = 0.0
        self.entry_time: float = 0.0
        self.highest_price = 0.0
        self.trailing_active = False

        # Indicator data
        self.ohlcv_data: pd.DataFrame | None = None
        self.ohlcv_1h: pd.DataFrame | None = None
        self.regime = 'RANGING'

        # Error tracking
        self.consecutive_errors = 0
        self.last_error_time = 0
        self.max_backoff = 60
        self._skip_until = 0

        # v4.1: Symbol blacklist for "not permitted" errors
        self._blocked = False

        self.load_state()

    # ── Error backoff ─────────────────────────────────────────
    def _should_skip(self) -> bool:
        if self._blocked:
            return True  # permanently skip blocked symbols
        if time.time() < self._skip_until:
            return True
        return False

    def _record_error(self, error_str: str = ''):
        """v4.1: Auto-blacklist symbols with 'not permitted' errors."""
        if 'not permitted' in error_str.lower() or 'symbol is not permitted' in error_str.lower():
            self._blocked = True
            logger.warning(f'⛔ {self.symbol_ccxt} BLACKLISTED: symbol not permitted for this account')
            return
        self.consecutive_errors += 1
        backoff = min(self.max_backoff, 2 ** self.consecutive_errors)
        self._skip_until = time.time() + backoff
        self.last_error_time = time.time()

    def _record_success(self):
        self.consecutive_errors = 0

    # ── State persistence (SQLite) ────────────────────────────
    def load_state(self):
        state = self.db.load_bot_state(self.symbol_ws)
        if state and state.get('is_in_position'):
            self.position = True
            self.buy_price = float(state.get('entry_price', 0) or 0)
            self.qty = float(state.get('quantity', 0) or 0)
            self.current_tp = float(state.get('tp', 0) or 0)
            self.current_sl = float(state.get('sl', 0) or 0)
            raw_et = state.get('entry_time')
            try:
                self.entry_time = float(raw_et) if raw_et else time.time()
            except (TypeError, ValueError):
                self.entry_time = time.time()
            self.highest_price = self.buy_price
            logger.info(f'🔄 Restored {self.symbol_ccxt}: {self.qty} @ {self.buy_price}')
        else:
            self.position = False
            self.reset_position_state()

    def reset_position_state(self):
        self.position = False
        self.buy_price = 0.0
        self.qty = 0.0
        self.current_tp = 0.0
        self.current_sl = 0.0
        self.entry_time = time.time()
        self.highest_price = 0.0
        self.trailing_active = False

    def save_state(self):
        self.db.save_bot_state(
            bot_name=self.symbol_ws,
            is_in_position=self.position,
            entry_price=self.buy_price,
            quantity=self.qty,
            tp=self.current_tp,
            sl=self.current_sl,
            entry_time=self.entry_time if self.entry_time else time.time(),
            exchange_name=self.exchange_name,
        )

    # ── Indicators ────────────────────────────────────────────
    async def init_indicators(self):
        try:
            ohlcv_1h = await self.exchange.fetch_ohlcv(
                self.symbol_ccxt, timeframe='1h', limit=100
            )
            self.ohlcv_1h = pd.DataFrame(
                ohlcv_1h, columns=['ts', 'open', 'high', 'low', 'close', 'vol']
            )
            ohlcv_1m = await self.exchange.fetch_ohlcv(
                self.symbol_ccxt, timeframe='1m', limit=OHLCV_LIMIT
            )
            self.ohlcv_data = pd.DataFrame(
                ohlcv_1m, columns=['ts', 'open', 'high', 'low', 'close', 'vol']
            )
            logger.info(f'📊 {self.symbol_ccxt}: {len(ohlcv_1m)} candles 1m loaded')
        except Exception as e:
            logger.error(f'❌ init_indicators {self.symbol_ccxt}: {e}')

    async def refresh_ohlcv(self):
        try:
            ohlcv = await self.exchange.fetch_ohlcv(
                self.symbol_ccxt, timeframe='1m', limit=OHLCV_LIMIT
            )
            self.ohlcv_data = pd.DataFrame(
                ohlcv, columns=['ts', 'open', 'high', 'low', 'close', 'vol']
            )
        except Exception as e:
            logger.debug(f'refresh OHLCV {self.symbol_ccxt}: {e}')

    def calculate_rsi(self) -> float:
        if self.ohlcv_data is None or len(self.ohlcv_data) < RSI_LENGTH + 1:
            return 50.0
        closes = self.ohlcv_data['close']
        try:
            if HAS_PANDAS_TA:
                rsi_series = ta.rsi(closes, length=RSI_LENGTH)
            else:
                rsi_series = np_rsi(closes, length=RSI_LENGTH)
            val = rsi_series.iloc[-1]
            if pd.isna(val):
                return 50.0
            return float(max(0.0, min(100.0, val)))
        except Exception:
            return 50.0

    def calculate_ema(self) -> float:
        if self.ohlcv_data is None or len(self.ohlcv_data) < EMA_LENGTH:
            return 0.0
        closes = self.ohlcv_data['close']
        try:
            if HAS_PANDAS_TA:
                ema_series = ta.ema(closes, length=EMA_LENGTH)
            else:
                ema_series = np_ema(closes, length=EMA_LENGTH)
            val = ema_series.iloc[-1]
            return float(val) if not pd.isna(val) else 0.0
        except Exception:
            return 0.0

    def calculate_atr(self) -> float:
        if self.ohlcv_data is None or len(self.ohlcv_data) < ATR_LENGTH + 1:
            return 0.0
        try:
            if HAS_PANDAS_TA:
                result = ta.atr(self.ohlcv_data['high'], self.ohlcv_data['low'],
                                self.ohlcv_data['close'], length=ATR_LENGTH)
            else:
                result = np_atr(self.ohlcv_data['high'], self.ohlcv_data['low'],
                                self.ohlcv_data['close'], length=ATR_LENGTH)
            if result is None or result.empty:
                return 0.0
            val = result.iloc[-1]
            return float(val) if not pd.isna(val) else 0.0
        except Exception:
            return 0.0

    def check_volume_filter(self, price_feed) -> tuple[bool, float]:
        """v4.2: Returns (ok, vol_ratio). BUGFIX: compares 1m candle volumes properly.
        No longer compares 24h WS volume vs 1m candle average (apples vs oranges)."""
        if self.ohlcv_data is None or len(self.ohlcv_data) < VOLUME_WINDOW:
            return True, 0.0
        vols = self.ohlcv_data['vol'].iloc[-VOLUME_WINDOW:]
        avg_vol = vols.mean()
        if avg_vol <= 0:
            return True, 0.0
        # v4.2: Use last COMPLETE candle volume for comparison
        last_complete_vol = vols.iloc[-2] if len(vols) >= 2 else vols.iloc[-1]
        vol_ratio = last_complete_vol / avg_vol
        return vol_ratio >= MIN_VOLUME_MULT, vol_ratio

    # ── v4.1: Strategy signals with debug logging and time-decay boost ─────
    def _boost_threshold(self, base: float, boost: float) -> float:
        """Apply time-decay boost to a threshold. Larger boost = easier to trigger."""
        return base / boost  # e.g., 0.003 / 1.5 = 0.002 => easier to trigger

    def signal_dip_buy(self, price: float, rsi: float, ema: float, vol_ok: bool,
                       vol_ratio: float, boost: float = 1.0) -> tuple[bool, str]:
        """v4.1: DIP_BUY with relaxed thresholds and time-decay boost."""
        if not vol_ok:
            logger.debug(f'  {self.symbol_ccxt} DIP_BUY skip: vol_ok=False (ratio={vol_ratio:.1f})')
            return False, 'low_volume'
        if self.ohlcv_data is None or len(self.ohlcv_data) < 5:
            return False, 'no_data'

        closes = self.ohlcv_data['close'].values
        drop_3 = (closes[-1] - closes[-3]) / closes[-3] if len(closes) >= 3 else 0
        drop_5 = (closes[-1] - closes[-5]) / closes[-5] if len(closes) >= 5 else 0

        # v4.1: Apply time-decay boost to thresholds
        dip_3_thresh = self._boost_threshold(DIP_BUY_THRESHOLD, boost)
        dip_5_thresh = self._boost_threshold(DIP_BUY_THRESHOLD_5, boost)
        rsi_thresh = self._boost_threshold(RSI_OVERSOLD, boost)

        significant_drop = drop_3 <= -dip_3_thresh or drop_5 <= -dip_5_thresh
        rsi_low = rsi < rsi_thresh

        if not significant_drop:
            logger.debug(f'  {self.symbol_ccxt} DIP_BUY: drop_3={drop_3*100:.2f}% drop_5={drop_5*100:.2f}% '
                         f'(need <-{dip_3_thresh*100:.2f}% / <-{dip_5_thresh*100:.2f}%) boost={boost:.1f}x')
        if not rsi_low:
            logger.debug(f'  {self.symbol_ccxt} DIP_BUY: RSI={rsi:.1f} (need <{rsi_thresh:.0f})')

        if significant_drop and rsi_low:
            logger.info(f'  ✅ {self.symbol_ccxt} DIP_BUY triggered! drop={drop_3*100:.2f}% RSI={rsi:.1f} boost={boost:.1f}x')
            return True, 'dip_buy'
        return False, f'no_signal(drop={drop_3*100:.2f}% rsi={rsi:.1f})'

    def signal_momentum(self, price: float, rsi: float, ema: float, vol_ok: bool,
                        vol_ratio: float, boost: float = 1.0) -> tuple[bool, str]:
        """v4.2: MOMENTUM — very relaxed: price near EMA + RSI neutral is enough to trigger."""
        if not vol_ok or ema <= 0:
            return False, 'vol_ema'
        if self.ohlcv_data is None or len(self.ohlcv_data) < 3:
            return False, 'no_data'

        closes = self.ohlcv_data['close'].values

        # v4.2: EMA margin very small (0.1%) — near the EMA is good enough
        ema_margin = self._boost_threshold(0.001, boost)  # era 0.002 — ora 0.1%
        above_ema = price > ema * (1 + ema_margin)

        # v4.2: Wide RSI range for ranging markets
        rsi_low = self._boost_threshold(40, boost)  # era 50 — RSI 35+ is fine
        rsi_high = min(80, 65 * boost)  # era 75 — but upper cap stays
        rsi_ok = rsi_low < rsi < rsi_high

        # v4.2: REMOVED 3-consecutive closes requirement — too strict for ranging
        # Instead, just check last close > previous (mild uptick)
        mild_up = len(closes) >= 2 and closes[-1] >= closes[-2]

        if not above_ema:
            logger.debug(f'  {self.symbol_ccxt} MOMENTUM: price={price:.4f} ema={ema:.4f} (need >{ema*(1+ema_margin):.4f})')
        if not rsi_ok:
            logger.debug(f'  {self.symbol_ccxt} MOMENTUM: RSI={rsi:.1f} (need {rsi_low:.0f}-{rsi_high:.0f})')
        if not mild_up:
            logger.debug(f'  {self.symbol_ccxt} MOMENTUM: no uptick (close={closes[-1]} prev={closes[-2]})')
        if above_ema and rsi_ok and mild_up:
            logger.info(f'  ✅ {self.symbol_ccxt} MOMENTUM triggered! RSI={rsi:.1f} price/ema={price/ema:.3f}')
            return True, 'momentum'
        return False, 'no_signal'

    def signal_mean_reversion(self, price: float, rsi: float, ema: float, vol_ok: bool,
                               vol_ratio: float, boost: float = 1.0) -> tuple[bool, str]:
        """v4.2: MEAN_REVERSION — RSI<35 + near 20-period low."""
        if not vol_ok:
            return False, 'low_volume'
        if self.ohlcv_data is None or len(self.ohlcv_data) < 20:
            return False, 'no_data'

        closes = self.ohlcv_data['close'].values

        # v4.2: Raise RSI threshold from 25 to 35 (was too extreme)
        rsi_thresh = self._boost_threshold(35, boost)
        rsi_oversold = rsi < rsi_thresh

        low_20 = min(closes[-20:])
        near_margin = self._boost_threshold(0.005, boost)
        near_low = (price - low_20) / low_20 < near_margin

        if rsi_oversold and near_low:
            logger.info(f'  ✅ {self.symbol_ccxt} MEAN_REV triggered! RSI={rsi:.1f} near_low={near_margin*100:.1f}%')
            return True, 'mean_reversion'
        return False, 'no_signal'

    def signal_scalp(self, price: float, rsi: float, ema: float, vol_ok: bool,
                      vol_ratio: float, boost: float = 1.0) -> tuple[bool, str]:
        """v4.2: SCALP — quick entry on small pullback. No vol spike check (BUGFIX)."""
        if not vol_ok:
            return False, 'low_volume'
        if self.ohlcv_data is None or len(self.ohlcv_data) < 3:
            return False, 'no_data'

        closes = self.ohlcv_data['close'].values

        # RSI below SCALP_RSI_MAX (default 55) with boost
        rsi_max = self._boost_threshold(SCALP_RSI_MAX, boost)
        rsi_cool = rsi < rsi_max

        # Price just dipped: current close < previous close
        dipped = len(closes) >= 2 and closes[-1] < closes[-2]

        # BUGFIX v4.2: REMOVED the second vol_spike check that compared incomplete
        # candle volume (vols[-1]) with complete candles average.
        # vol_ok from check_volume_filter already handles overall volume health.

        if not rsi_cool:
            logger.debug(f'  {self.symbol_ccxt} SCALP: RSI={rsi:.1f} (need <{rsi_max:.0f})')
        if not dipped:
            logger.debug(f'  {self.symbol_ccxt} SCALP: no dip (close={closes[-1]} prev={closes[-2]})')

        if rsi_cool and dipped:
            logger.info(f'  ✅ {self.symbol_ccxt} SCALP triggered! RSI={rsi:.1f} dip {closes[-2]:.4f}->{closes[-1]:.4f}')
            return True, 'scalp'
        return False, 'no_signal'

    # ── Trailing stop + breakeven ─────────────────────────────
    def update_trailing_stop(self, price: float, atr: float):
        if not self.position:
            return
        if price > self.highest_price:
            self.highest_price = price
        profit_pct = (self.highest_price - self.buy_price) / self.buy_price

        # Breakeven
        if profit_pct >= BREAKEVEN_BUFFER and not self.trailing_active:
            new_sl = self.buy_price * (1 + FEE_RT)
            if new_sl < self.current_sl or self.current_sl == 0:
                self.current_sl = new_sl
                logger.info(f'🔒 {self.symbol_ccxt} BREAKEVEN: SL moved to {new_sl:.4f}')
                self.trailing_active = True
                self.save_state()

        # Trailing stop
        if profit_pct >= (atr * TRAILING_ACTIVATION) / self.buy_price:
            trail_distance = atr * SL_ATR_MULT
            trailing_sl = self.highest_price - trail_distance
            if trailing_sl > self.current_sl:
                self.current_sl = trailing_sl
                logger.info(f'🔄 {self.symbol_ccxt} TRAILING: SL raised to {trailing_sl:.4f}')
                self.save_state()

    # ── Core update loop ──────────────────────────────────────
    async def update(self, price_feed: PriceFeed, risk_manager: RiskManager,
                     total_balance_eur: float) -> None:
        if self._should_skip():
            return

        try:
            price = price_feed.prices.get(self.symbol_ws)
            if price is None or price <= 0:
                return

            # Refresh OHLCV every 60 seconds
            if self.ohlcv_data is not None and len(self.ohlcv_data) > 0:
                last_ts = self.ohlcv_data['ts'].iloc[-1]
                if time.time() * 1000 - last_ts > 60000:
                    await self.refresh_ohlcv()

            # Calculate indicators once per cycle
            rsi = self.calculate_rsi()
            ema = self.calculate_ema()
            atr = self.calculate_atr()
            vol_ok, vol_ratio = self.check_volume_filter(price_feed)

            if atr <= 0:
                return

            # ═════════════════════════════════════════════════
            # POSITION MANAGEMENT
            # ═════════════════════════════════════════════════
            if self.position and self.qty > 0:
                self.update_trailing_stop(price, atr)

                hit_tp = price >= self.current_tp
                hit_sl = price <= self.current_sl

                if hit_tp or hit_sl:
                    try:
                        order = await self.exchange.create_market_sell_order(
                            self.symbol_ccxt, self.qty)

                        sell_price = float(order.get('price', 0))
                        if sell_price <= 0:
                            sell_price = price

                        gross_pnl = (sell_price - self.buy_price) * self.qty
                        fees = (self.buy_price + sell_price) * self.qty * FEE_RATE
                        net_pnl = gross_pnl - fees
                        pnl_pct = (sell_price / self.buy_price) - 1 - FEE_RT

                        reason = 'take_profit' if hit_tp else 'stop_loss'
                        if self.trailing_active:
                            reason = 'trailing_stop'

                        entry_ts = self.entry_time if self.entry_time else time.time()
                        entry_iso = datetime.fromtimestamp(entry_ts, tz=timezone.utc).isoformat()

                        self.db.save_trade(
                            bot_name='Legion', symbol=self.symbol_ccxt, side='BUY',
                            entry_price=self.buy_price, exit_price=sell_price,
                            quantity=self.qty,
                            entry_time=entry_iso,
                            exit_time=datetime.now().isoformat(),
                            gross_pnl=gross_pnl, fees=fees, net_pnl=net_pnl,
                            reason=reason)

                        # Feed trade result to adaptive engine
                        if self.adaptive:
                            self.adaptive.record_trade(
                                self.symbol_ccxt, net_pnl, pnl_pct,
                                'win' if net_pnl > 0 else 'loss'
                            )

                        # Vault: 20% of winning profits
                        if net_pnl > 0:
                            vault_amount = net_pnl * 0.20
                            self.db.add_to_vault(vault_amount)

                        logger.info(
                            f'⚔️ {self.symbol_ccxt} CLOSED [{self.exchange_name}] '
                            f'Exit: {sell_price:.4f} | PnL: {pnl_pct*100:.2f}% '
                            f'| Net: {net_pnl:.2f}€ | Reason: {reason}')

                        await self.exposure_guard.update_exposure(self.symbol_ws, 0, 'close')
                        self.reset_position_state()
                        self.save_state()
                        self._record_success()
                        risk_manager.record_trade()

                    except Exception as e:
                        logger.error(f'❌ Sell Error {self.symbol_ccxt}: {e}')
                        self._record_error(str(e))

            # ═════════════════════════════════════════════════
            # ENTRY LOGIC (only if not in position)
            # ═════════════════════════════════════════════════
            elif not self.position:
                trading_ok = await risk_manager.is_trading_hours()
                if not trading_ok:
                    return

                allowed, reason = risk_manager.authorize_trade(
                    self.symbol_ws, PER_SYMBOL_MAX_EUR)
                if not allowed:
                    return

                # v4.1: Get time-decay boost
                boost = risk_manager.get_idle_boost()

                # Detect regime and pick strategy
                self.regime = self.regime_detector.classify(self.ohlcv_data)

                entry_signal = False
                strategy_used = 'NONE'
                signal_reason = ''

                if self.regime == 'VOLATILE':
                    entry_signal, signal_reason = self.signal_dip_buy(
                        price, rsi, ema, vol_ok, vol_ratio, boost)
                    strategy_used = 'DIP_BUY'
                elif self.regime == 'TRENDING':
                    entry_signal, signal_reason = self.signal_momentum(
                        price, rsi, ema, vol_ok, vol_ratio, boost)
                    strategy_used = 'MOMENTUM'
                else:
                    # RANGING: try all signals — DIP_BUY, MEAN_REVERSION, SCALP
                    entry_signal, signal_reason = self.signal_dip_buy(
                        price, rsi, ema, vol_ok, vol_ratio, boost)
                    if entry_signal:
                        strategy_used = 'DIP_BUY'
                    else:
                        entry_signal, signal_reason = self.signal_mean_reversion(
                            price, rsi, ema, vol_ok, vol_ratio, boost)
                        if entry_signal:
                            strategy_used = 'MEAN_REV'
                        else:
                            entry_signal, signal_reason = self.signal_scalp(
                                price, rsi, ema, vol_ok, vol_ratio, boost)
                            if entry_signal:
                                strategy_used = 'SCALP'
                            else:
                                # v4.1: In ranging with boost, also try momentum (even without trend)
                                if boost > 1.2:
                                    entry_signal, signal_reason = self.signal_momentum(
                                        price, rsi, ema, vol_ok, vol_ratio, boost)
                                    if entry_signal:
                                        strategy_used = 'MOMENTUM(BOOST)'

                if entry_signal:
                    # Position sizing with Kelly Criterion
                    base_risk_pct = 0.01  # 1% default
                    if self.adaptive:
                        win_rate = self.adaptive.get_symbol_win_rate(self.symbol_ccxt)
                        if win_rate is not None and len(self.adaptive.trade_history.get(self.symbol_ccxt, [])) >= 10:
                            avg_win = self.adaptive.get_avg_win(self.symbol_ccxt)
                            avg_loss = self.adaptive.get_avg_loss(self.symbol_ccxt)
                            if avg_loss is not None and avg_win is not None and avg_loss > 0:
                                b = avg_win / avg_loss if avg_win > 0 else 0
                                if b > 0 and win_rate > 0:
                                    kelly = win_rate - ((1 - win_rate) / b)
                                    kelly = max(0.005, min(0.02, kelly * 0.25))
                                    base_risk_pct = kelly

                    risk_amount = max(5.0, total_balance_eur * base_risk_pct)
                    risk_amount = min(PER_SYMBOL_MAX_EUR, risk_amount)

                    # Compute SL-based position size
                    sl_price = price - (atr * SL_ATR_MULT)
                    sl_dist = (price - sl_price) / price if sl_price < price else 0.02
                    sl_dist = max(0.005, min(0.05, sl_dist))

                    size_eur = risk_amount / sl_dist if sl_dist > 0 else risk_amount

                    # MIN_NOTIONAL guard
                    if size_eur < MIN_NOTIONAL:
                        size_eur = MIN_NOTIONAL

                    # Cap at available balance (95% to leave room for fees)
                    size_eur = min(size_eur, total_balance_eur * 0.95)
                    # Cap at PER_SYMBOL_MAX_EUR
                    size_eur = min(size_eur, PER_SYMBOL_MAX_EUR)

                    try:
                        order = await self.exchange.create_market_buy_order_with_cost(
                            self.symbol_ccxt, size_eur)

                        self.qty = float(order.get('filled', 0))
                        if self.qty <= 0:
                            self.qty = size_eur / price

                        self.buy_price = float(order.get('price', 0))
                        if self.buy_price <= 0:
                            self.buy_price = price

                        # Dynamic TP/SL based on ATR with percentage floor
                        tp_atr = self.buy_price + (atr * TP_ATR_MULT)
                        tp_min = self.buy_price * (1 + MIN_TP_PCT)
                        self.current_tp = max(tp_atr, tp_min)
                        sl_atr = self.buy_price - (atr * SL_ATR_MULT)
                        sl_min = self.buy_price * (1 - MIN_SL_PCT)
                        self.current_sl = min(sl_atr, sl_min)

                        if self.regime == 'VOLATILE':
                            self.current_sl = min(
                                self.buy_price - (atr * SL_ATR_MULT * 1.2),
                                self.buy_price * (1 - MIN_SL_PCT)
                            )

                        self.entry_time = time.time()
                        self.highest_price = self.buy_price
                        self.trailing_active = False
                        self.position = True
                        self.save_state()

                        await self.exposure_guard.update_exposure(
                            self.symbol_ws, size_eur, 'open')

                        pnl_at_targets = (
                            f"TP: {(self.current_tp/self.buy_price-1)*100:.2f}% "
                            f"SL: {(self.current_sl/self.buy_price-1)*100:.2f}%"
                        )

                        logger.info(
                            f'⚔️ {self.symbol_ccxt} OPEN [{self.exchange_name}] '
                            f'{strategy_used} | Entry: {self.buy_price:.4f} '
                            f'| Size: {size_eur:.2f}€ | {pnl_at_targets}')

                        self._record_success()
                        risk_manager.record_trade()

                    except Exception as e:
                        logger.error(f'❌ Buy Error {self.symbol_ccxt}: {e}')
                        self._record_error(str(e))

            # ── Heartbeat ─────────────────────────────────────
            self.save_state()

        except Exception as e:
            logger.error(f'❌ Update Error {self.symbol_ccxt}: {e}')
            self._record_error(str(e))


# ═══════════════════════════════════════════════════════════════════
# Main entry point
# ═══════════════════════════════════════════════════════════════════
async def main():
    router = ExchangeRouter.from_env()
    await router.initialize()

    active_exchanges = router.get_active_exchanges()
    logger.info(f"📡 Exchange attivi: {active_exchanges}")

    if not active_exchanges:
        logger.error("❌ NESSUN EXCHANGE ATTIVO. Verifica .env API keys.")
        logger.error("   BINANCE_API_KEY e BINANCE_API_SECRET devono essere popolate.")
        logger.error("   Il bot terminerà tra 10 secondi.")
        await asyncio.sleep(10)
        return

    default_exchange = await router.get_exchange_instance('binance')
    if default_exchange is None and active_exchanges:
        default_exchange = list(router.exchanges.values())[0]

    if default_exchange is None:
        logger.error("❌ Nessun exchange disponibile. Exit.")
        return

    db = TradeDB(os.path.join(BASE_DIR, "trades.db"))
    exposure_guard = ExposureGuard(db)

    adaptive = AutoAdaptiveEngine(db)
    adaptive.load_history()

    risk_manager = RiskManager(db, exposure_guard, adaptive_engine=adaptive)
    feed = PriceFeed()

    # Build bots for all symbols
    bots = []
    volume_rank = {}

    symbols_with_exchange = []
    for i, s in enumerate(SYMBOLS_WS):
        ccxt_sym = SYMBOLS_CCXT[i]
        exch_name = router.get_exchange_for_symbol(ccxt_sym)
        exchange = (await router.get_exchange_instance(exch_name)
                    if exch_name else default_exchange)
        if exchange is None:
            continue
        symbols_with_exchange.append((s, ccxt_sym, exchange, exch_name or 'binance'))

    # Initialize indicators first to rank by volume
    temp_bots = []
    for s, ccxt_sym, exchange, exch_name in symbols_with_exchange:
        bot = LegionBot(exchange, s, ccxt_sym, db, exposure_guard,
                       adaptive_engine=adaptive, exchange_name=exch_name)
        await bot.init_indicators()
        temp_bots.append(bot)

        # Rank by 24h volume (from OHLCV data)
        if bot.ohlcv_data is not None and len(bot.ohlcv_data) > 0:
            avg_vol = bot.ohlcv_data['vol'].mean()
            volume_rank[bot.symbol_ws] = avg_vol

    # Keep only MAX_ACTIVE_SYMBOLS highest-volume pairs
    sorted_symbols = sorted(volume_rank.items(), key=lambda x: -x[1]) if volume_rank else []
    active_pairs = {s for s, v in sorted_symbols[:MAX_ACTIVE_SYMBOLS]}

    if len(active_pairs) < 6:
        active_pairs = {tb.symbol_ws for tb in temp_bots}

    # Also include any pair that has an active position (must restore)
    for tb in temp_bots:
        if tb.position:
            active_pairs.add(tb.symbol_ws)

    bots = [tb for tb in temp_bots if tb.symbol_ws in active_pairs]

    logger.info(f'🔝 Top {len(bots)} pairs by volume (from {len(temp_bots)} total)')
    for b in bots:
        vol_val = volume_rank.get(b.symbol_ws, 0)
        logger.info(f'   {b.symbol_ws:<12} vol: {vol_val:.0f}  pos: {b.position}')

    asyncio.create_task(feed.start())

    # Wait for first price data
    logger.info("⏳ Attesa primo prezzo WebSocket...")
    for _ in range(30):
        if len(feed.prices) > 3:
            break
        await asyncio.sleep(1)
    logger.info(f'✅ Dati prezzo ricevuti per {len(feed.prices)} simboli')

    logger.info(f'🚀 LegionManager PROD v4.2 avviato. {len(bots)} bot attivi.')

    # Centralized balance fetch (once per cycle, shared across bots)
    last_balance_fetch = 0
    total_balance = INITIAL_CAPITAL

    ohlcv_refresh_counter = 0

    try:
        while True:
            # Fetch total balance once per 60 seconds
            now = time.time()
            if now - last_balance_fetch > 60:
                try:
                    bal = await default_exchange.fetch_balance()
                    total_balance = float(bal.get('EUR', {}).get('free', 0) or 0)
                    if total_balance <= 0:
                        total_balance = INITIAL_CAPITAL
                    last_balance_fetch = now
                except Exception as e:
                    logger.error(f"❌ Balance fetch: {e}")
                    if total_balance > 0:
                        # Keep last known balance — don't fall back to 0
                        pass

            # Adaptive engine auto-adjusts every cycle
            adaptive.update_daily_stats()

            # Run bot updates
            await asyncio.gather(*(
                bot.update(feed, risk_manager, total_balance) for bot in bots
            ))

            # Periodic report (every 60 iterations = ~60 seconds)
            ohlcv_refresh_counter += 1
            if ohlcv_refresh_counter % 60 == 0:
                open_positions = sum(1 for b in bots if b.position)
                total_exp = exposure_guard.get_exposure()
                metrics = adaptive.summary()
                blocked = sum(1 for b in bots if b._blocked)
                boost = risk_manager.get_idle_boost()
                logger.info(
                    f'📊 Posizioni aperte: {open_positions}/{len(bots)} | '
                    f'Exposure: {total_exp["total"]:.1f}€ | '
                    f'Win rate: {metrics["overall_win_rate"]:.1f}% | '
                    f'Profit: {metrics["total_profit"]:.2f}€ | '
                    f'Blocked: {blocked} | Boost: {boost:.1f}x')

            await asyncio.sleep(1)

    except asyncio.CancelledError:
        logger.info("🛑 LegionManager fermato.")
    except Exception as e:
        logger.error(f'❌ Errore critico: {e}')
        import traceback
        logger.error(traceback.format_exc())
    finally:
        await router.close_all()
        logger.info("🏁 Connessioni exchange chiuse.")


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Terminato da tastiera.")
    except Exception as e:
        logger.error(f"Avvio fallito: {e}")
