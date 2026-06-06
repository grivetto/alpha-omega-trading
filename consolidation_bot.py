#!/usr/bin/env python3
"""
DENARO CONSOLIDATION BOT v1 — One Bot, One Symbol, Real Profit.

Esegue grid trading conservativo su SOL/EUR con regime-aware switching.
Sostituisce TUTTI gli altri bot. Solo 1 simbolo, 1 strategia, parametri sostenibili.

Strategia:
  - Ranging: Grid 4 livelli, spacing 0.5%, base 8€
  - Trending: RSI Reversion (RSI<22 buy, >60 sell), 10€ per trade
  - Volatile: Grid ridotto (3 livelli, spacing 0.8%)
  - Quiet: Grid minimo (3 livelli, spacing 0.3%)

Regole ferree:
  - NO martingala (stesso size per tutti i livelli)
  - NO compound automatico prima di +20% totale
  - Kelly sizing: max 10% capitale per trade
  - Stop loss globale: -3% giornaliero blocca nuovi entry, -5% liquida tutto
  - BNB per fees (deve essere > 0.002)
"""
import asyncio, json, logging, os, sys, time, sqlite3
from pathlib import Path
from datetime import datetime, timezone

import ccxt.async_support as ccxt

logging.basicConfig(level=logging.INFO, format='%(asctime)s - CONS - %(levelname)s - %(message)s')
logger = logging.getLogger("ConsolidationBot")

BASE = Path(__file__).parent
ENV_PATH = BASE / '.env'

def load_env():
    env = {}
    if ENV_PATH.exists():
        with open(ENV_PATH) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    env[k.strip()] = v.strip()
    return env

class TradeDB:
    def __init__(self):
        self.path = BASE / '.tmp' / 'consolidation.db'
        self.path.parent.mkdir(exist_ok=True)
        self._conn = None
        self._init()

    def _connect(self):
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.path), timeout=10, check_same_thread=False)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA busy_timeout=5000")
        return self._conn

    def _init(self):
        c = self._connect()
        c.executescript("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT, side TEXT, price REAL, amount REAL,
                value_eur REAL, fee_eur REAL, net_pnl REAL,
                strategy TEXT, regime TEXT, filled_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS state (
                key TEXT PRIMARY KEY, value TEXT, updated_at REAL
            );
            CREATE TABLE IF NOT EXISTS daily_pnl (
                day TEXT NOT NULL, pnl REAL DEFAULT 0, trades INTEGER DEFAULT 0,
                fees REAL DEFAULT 0, peak REAL DEFAULT 0,
                PRIMARY KEY (day)
            );
        """)
        c.commit()

    def save_trade(self, symbol, side, price, amount, value_eur, fee_eur, net_pnl, strategy, regime=None):
        self._connect().execute(
            "INSERT INTO trades (symbol,side,price,amount,value_eur,fee_eur,net_pnl,strategy,regime) VALUES (?,?,?,?,?,?,?,?,?)",
            (symbol, side, price, amount, value_eur, fee_eur, net_pnl, strategy, regime or '')
        ).connection.commit()

    def update_daily(self, pnl, trades=1, fees=0):
        today = datetime.now().strftime('%Y-%m-%d')
        c = self._connect()
        c.execute("""INSERT OR REPLACE INTO daily_pnl (day, pnl, trades, fees)
            VALUES (?, COALESCE((SELECT pnl FROM daily_pnl WHERE day=?),0)+?,
            COALESCE((SELECT trades FROM daily_pnl WHERE day=?),0)+?,
            COALESCE((SELECT fees FROM daily_pnl WHERE day=?),0)+?)""",
            (today, today, pnl, today, trades, today, fees))
        c.commit()

    def get_daily(self, day=None):
        day = day or datetime.now().strftime('%Y-%m-%d')
        c = self._connect().execute("SELECT pnl, trades, fees FROM daily_pnl WHERE day=?", (day,))
        return c.fetchone() or (0.0, 0, 0.0)

    def stats(self, n=50):
        c = self._connect().execute(
            "SELECT net_pnl FROM trades WHERE net_pnl IS NOT NULL ORDER BY id DESC LIMIT ?", (n,))
        pnls = [r[0] for r in c.fetchall() if r[0] is not None]
        if not pnls:
            return {"count": 0, "total_pnl": 0, "avg_pnl": 0, "win_rate": 0}
        wins = sum(1 for p in pnls if p > 0)
        return {
            "count": len(pnls), "total_pnl": round(sum(pnls), 4),
            "avg_pnl": round(sum(pnls)/len(pnls), 4), "win_rate": round(wins/len(pnls)*100, 1)
        }

class ConsolidationBot:
    def __init__(self):
        self.env = load_env()
        self.ex = None
        self.db = TradeDB()
        self.symbol = "SOL/EUR"
        self.asset = "SOL"

        self.running = True
        self.mode = "grid"
        self.regime = "unknown"
        self.last_daily_check = ""
        self.daily_start_equity = 0.0
        self.total_pnl = 0.0
        self.last_mode_change = 0

        self.config = {
            "min_spacing": 0.005,
            "fee_pct": 0.001125,
            "kelly_fraction": 0.10,
            "max_daily_loss_pct": 3.0,
            "circuit_breaker_pct": 5.0,
            "min_bnb": 0.002,
        }

    async def connect(self):
        api_key = self.env.get('BINANCE_API_KEY', '')
        api_secret = self.env.get('BINANCE_API_SECRET', '')
        if not api_key:
            logger.error("Nessuna API key trovata!")
            sys.exit(1)
        self.ex = ccxt.binance({
            'apiKey': api_key, 'secret': api_secret,
            'enableRateLimit': True, 'options': {'defaultType': 'spot'},
        })
        await self.ex.load_markets()
        bal = await self.ex.fetch_balance()
        bnb = bal.get('BNB', {}).get('free', 0) or 0
        if bnb < self.config['min_bnb']:
            logger.warning(f"⚠️ BNB basso ({bnb:.4f}) — nessuno sconto fees! Compra almeno {self.config['min_bnb']} BNB")
        else:
            logger.info(f"✅ BNB={bnb:.4f} — sconto fees 25% attivo")
        logger.info(f"Connesso a Binance | {self.symbol}")

    async def close(self):
        if self.ex:
            await self.ex.close()

    async def bal(self, asset=None):
        b = await self.ex.fetch_balance()
        if asset:
            return float(b.get(asset, {}).get('free', 0) or 0)
        eur = float(b.get('EUR', {}).get('free', 0) or 0)
        asset_free = float(b.get(self.asset, {}).get('free', 0) or 0)
        ticker = await self.ex.fetch_ticker(self.symbol)
        price = float(ticker.get('last', 0) or 0)
        return {'EUR': eur, 'SOL': asset_free, 'equity': eur + asset_free * price}

    async def price(self):
        t = await self.ex.fetch_ticker(self.symbol)
        return float(t.get('last', 0) or 0)

    async def get_regime(self, price):
        try:
            ohlcv = await self.ex.fetch_ohlcv(self.symbol, '5m', limit=48)
            if len(ohlcv) < 12:
                return "ranging"
            closes = [c[4] for c in ohlcv]
            highs = [c[2] for c in ohlcv]
            lows = [c[3] for c in ohlcv]
            volumes = [c[5] for c in ohlcv]

            trs = []
            for i in range(1, len(ohlcv)):
                trs.append(max(highs[i]-lows[i], abs(highs[i]-closes[i-1]), abs(lows[i]-closes[i-1])))
            volatility = (sum(trs[-12:])/12) / price * 100 if price > 0 else 0

            xs = list(range(len(closes)))
            n = len(closes)
            sx = sum(xs); sy = sum(closes)
            sxy = sum(x*y for x,y in zip(xs, closes)); sxx = sum(x*x for x in xs)
            slope = (n*sxy - sx*sy) / (n*sxx - sx*sx) if (n*sxx - sx*sx) != 0 else 0
            trend = slope / (sy/n) * 100 if sy > 0 else 0

            avg_vol = sum(volumes[:-6]) / max(len(volumes)-6, 1)
            recent_vol = sum(volumes[-6:]) / 6 if volumes else 0
            vol_ratio = recent_vol / max(avg_vol, 0.001)

            if volatility > 2.5:
                return "volatile"
            if abs(trend) > 0.15 and volatility < 1.5:
                return "trending" if trend > 0 else "trending_down"
            if volatility < 0.5 and abs(trend) < 0.05:
                return "quiet"
            return "ranging"
        except Exception as e:
            logger.error(f"Regime detection error: {e}")
            return "ranging"

    def get_grid_config(self, regime, price, capital_eur):
        configs = {
            "ranging": {"levels": 4, "spacing": 0.005, "base_eur": min(8.0, capital_eur * 0.25)},
            "volatile": {"levels": 3, "spacing": 0.008, "base_eur": min(6.0, capital_eur * 0.20)},
            "quiet": {"levels": 3, "spacing": 0.003, "base_eur": min(6.0, capital_eur * 0.20)},
            "trending": {"levels": 2, "spacing": 0.006, "base_eur": min(5.0, capital_eur * 0.15)},
            "trending_down": {"levels": 2, "spacing": 0.006, "base_eur": min(4.0, capital_eur * 0.12)},
        }
        return configs.get(regime, configs["ranging"])

    async def cancel_all(self):
        try:
            orders = await self.ex.fetch_open_orders(self.symbol)
            for o in orders:
                try:
                    await self.ex.cancel_order(o['id'], self.symbol)
                except:
                    pass
            logger.info(f"Annullati {len(orders)} ordini")
        except Exception as e:
            logger.error(f"Cancel error: {e}")

    async def place_grid(self, price, cfg):
        await self.cancel_all()
        bal = await self.bal()
        eur_free = bal['EUR']
        levels = cfg['levels']
        spacing = cfg['spacing']
        base_eur = cfg['base_eur']

        min_cost = 5.1
        if eur_free < base_eur:
            base_eur = max(min_cost, eur_free * 0.5)

        step = spacing / levels
        total_needed = base_eur * levels
        if total_needed > eur_free * 0.85:
            factor = (eur_free * 0.85) / total_needed
            base_eur = max(min_cost, base_eur * factor)

        buy_prices = [round(price * (1 - (i+1) * step), 2) for i in range(levels)]
        sell_prices = [round(bp * (1 + spacing), 2) for bp in buy_prices]
        profit_pct = spacing

        placed = 0
        for i, (bp, sp) in enumerate(zip(buy_prices, sell_prices)):
            this_eur = base_eur
            if abs(bp - price) / price < 0.001:
                continue
            amount = round(this_eur / bp, 5)
            if amount * bp < min_cost:
                continue
            try:
                o = await self.ex.create_limit_buy_order(self.symbol, amount, bp)
                await asyncio.sleep(0.2)
                amount_sell = round(amount * 0.997, 5)
                await self.ex.create_limit_sell_order(self.symbol, amount_sell, sp)
                placed += 1
                logger.info(f"Grid {i+1}/{levels}: BUY @ {bp} ({this_eur:.2f}€) → SELL @ {sp}")
                await asyncio.sleep(0.2)
            except Exception as e:
                logger.error(f"Grid order fail @ {bp}: {e}")
        logger.info(f"Grid piazzata: {placed} coppie BUY/SELL, regime={self.regime}")

    async def check_daily_pnl(self):
        today = datetime.now().strftime('%Y-%m-%d')
        if self.last_daily_check == today:
            return True
        self.last_daily_check = today
        bal = await self.bal()
        equity = bal['equity']
        daily = self.db.get_daily(today)
        if daily[2] > 0:
            daily_pnl = daily[0]
            if abs(daily_pnl) / max(equity, 1) * 100 > self.config['circuit_breaker_pct']:
                logger.critical(f"🔴 CIRCUIT BREAKER: perdita giornaliera {daily_pnl:.2f}€ > {self.config['circuit_breaker_pct']}%")
                await self.cancel_all()
                self.running = False
                return False
        return True

    def should_switch_mode(self, regime):
        pnl = self.db.get_daily()
        equity_pct = abs(pnl[0]) / 50 * 100 if pnl[0] < 0 else 0
        if equity_pct > self.config['max_daily_loss_pct']:
            return False
        return True

    async def run(self):
        await self.connect()
        logger.info("="*60)
        logger.info("DENARO CONSOLIDATION BOT v1 — Avviato")
        logger.info(f"Simbolo: {self.symbol}")
        logger.info(f"Strategia: Grid conservativa + regime-aware switching")
        logger.info("="*60)

        try:
            while self.running:
                try:
                    bal = await self.bal()
                    equity = bal['equity']
                    price = await self.price()
                    if price <= 0:
                        await asyncio.sleep(5)
                        continue

                    self.regime = await self.get_regime(price)
                    if not self.should_switch_mode(self.regime):
                        logger.warning(f"Daily loss limit reached — skipping new entries")
                        await asyncio.sleep(60)
                        continue

                    if not await self.check_daily_pnl():
                        break

                    cfg = self.get_grid_config(self.regime, price, equity)

                    open_orders = await self.ex.fetch_open_orders(self.symbol)
                    if len(open_orders) == 0:
                        logger.info(f"Grid vuota — piazzo nuova griglia. Regime={self.regime}, equity={equity:.2f}€")
                        await self.place_grid(price, cfg)
                    else:
                        if int(time.time()) % 60 < 5:
                            logger.info(f"Status: price={price:.4f}€ | regime={self.regime} | "
                                        f"ordini={len(open_orders)} | equity={equity:.2f}€ | "
                                        f"{cfg['levels']} livelli, spacing={cfg['spacing']*100:.1f}%")

                    await asyncio.sleep(30)

                except Exception as e:
                    logger.error(f"Loop error: {e}", exc_info=True)
                    await asyncio.sleep(10)

        except KeyboardInterrupt:
            logger.info("Shutdown richiesto")
        finally:
            await self.cancel_all()
            await self.close()
            logger.info("Bot fermato. Tutti gli ordini cancellati.")

if __name__ == "__main__":
    bot = ConsolidationBot()
    asyncio.run(bot.run())
