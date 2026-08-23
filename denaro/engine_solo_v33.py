#!/usr/bin/env python3
"""
Alpha-Omega SOLO Engine v3.3 — CONSOLIDATO (2026-08-23)

Versione consolidata del motore di trading singolo. Fix applicati rispetto a v3.2:
- EEA endpoint obbligatorio per OKX (hostname eea.okx.com) — senza questo le chiavi EU
  falliscono con 50119 "API key doesn't exist"
- Capitale effettivo = min(capital_config, free_balance) — evita che il bot resti fermo
  quando il saldo libero è sotto il capitale configurato (bug v3.2: richiedeva free >= capital)
- Precisione prezzo/quantità dal mercato (load_markets) invece di round fisso
- PnL file configurabile via env (PNL_FILE)
- No dipendenze oltre a ccxt + python-dotenv

Comportamento:
- Grid di N livelli buy sotto il prezzo (distanza crescente: -1.0%, -1.5%, -2.0%...)
- Alla fill di un buy, piazza un sell limit a +profit_target%
- Stato ricostruito dall'exchange a ogni riavvio (nessuna persistenza locale richiesta)
"""
import os
import sys
import time
import json
import logging
import argparse
from datetime import datetime
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger('solo')

load_dotenv()

TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT = os.getenv('TELEGRAM_CHAT_ID')
PNL_FILE = os.getenv('PNL_FILE', os.path.expanduser('~/denaro/pnl_log.jsonl'))


def tg_send(msg: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT:
        return
    try:
        import urllib.request, urllib.parse
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = urllib.parse.urlencode({'chat_id': TELEGRAM_CHAT, 'text': msg, 'parse_mode': 'HTML'}).encode()
        urllib.request.urlopen(url, data=data, timeout=10)
    except Exception as e:
        log.warning(f'TG send failed: {e}')


def log_pnl(record: dict):
    try:
        with open(PNL_FILE, 'a') as f:
            f.write(json.dumps(record) + '\n')
    except Exception as e:
        log.warning(f'PnL log failed: {e}')


def create_exchange(exchange_id: str):
    import ccxt
    if exchange_id == 'kraken':
        api_key = os.getenv('KRAKEN_API_KEY')
        api_secret = os.getenv('KRAKEN_API_SECRET')
        if not api_key or not api_secret:
            raise RuntimeError('Missing KRAKEN_API_KEY or KRAKEN_API_SECRET')
        return ccxt.kraken({'apiKey': api_key, 'secret': api_secret, 'enableRateLimit': True,
                            'options': {'defaultType': 'spot'}})
    elif exchange_id == 'okx':
        api_key = os.getenv('OKX_API_KEY')
        api_secret = os.getenv('OKX_API_SECRET')
        password = os.getenv('OKX_PASSPHRASE')
        if not api_key or not api_secret or not password:
            raise RuntimeError('Missing OKX credentials')
        eea = os.getenv('OKX_EEA', '').lower() == 'true'
        config = {'apiKey': api_key, 'secret': api_secret, 'password': password,
                  'enableRateLimit': True, 'options': {'defaultType': 'spot'}}
        if eea:
            # CRITICO: chiavi EU funzionano SOLO su eea.okx.com
            config['hostname'] = 'eea.okx.com'
            log.info('Using OKX EEA endpoint (eea.okx.com)')
        return ccxt.okx(config)
    else:
        raise ValueError(f'Unsupported exchange: {exchange_id}')


def fetch_free_balance(exchange):
    bal = exchange.fetch_balance()
    free = bal.get('free', {})
    total = bal.get('total', {})
    for qc in ['EUR', 'USDT', 'USD', 'GBP']:
        if qc in free and free[qc]:
            return float(free[qc]), qc, float(total.get(qc, 0))
    f = sum(float(v) for v in free.values() if v and float(v) > 0)
    t = sum(float(v) for v in total.values() if v and float(v) > 0)
    return f, 'MIX', t


def calculate_total_equity(exchange, base_quote='EUR'):
    bal = exchange.fetch_balance()
    total = bal.get('total', {})
    equity = 0.0
    for asset, amount in total.items():
        if not amount or float(amount) <= 0:
            continue
        if asset == base_quote:
            equity += float(amount)
        else:
            try:
                pair = f"{asset}/{base_quote}"
                ticker = exchange.fetch_ticker(pair)
                equity += float(amount) * float(ticker['last'])
            except Exception:
                try:
                    pair = f"{asset}/USDT"
                    ticker = exchange.fetch_ticker(pair)
                    eur_ticker = exchange.fetch_ticker(f"USDT/{base_quote}")
                    equity += float(amount) * float(ticker['last']) * float(eur_ticker['last'])
                except Exception:
                    continue
    return equity


class SoloEngine:
    def __init__(self, exchange_id, symbol, capital, profit_target=1.5,
                 buy_distance=1.0, grid_levels=3, interval=60, health_file=None):
        self.exchange_id = exchange_id
        self.symbol = symbol
        self.capital = capital
        self.profit_target = profit_target / 100.0
        self.buy_distance = buy_distance / 100.0
        self.grid_levels = grid_levels
        self.interval = interval
        self._health_file = health_file
        self.exchange = create_exchange(exchange_id)
        self.open_buys = {}
        self.open_sells = {}
        self.total_profit = 0.0
        self.total_trades = 0
        self.wins = 0
        self.losses = 0
        self.volume = 0.0
        self._max_dd = 0.0
        self._peak_equity = 0.0
        self._start_ts = time.time()
        self.base = symbol.split('/')[0]
        self.quote = symbol.split('/')[1] if '/' in symbol else 'EUR'
        self._markets = {}
        self._load_market_specs()
        tg_send(f"🚀 <b>SOLO Engine v3.3 (consolidato)</b>\n{exchange_id.upper()} | {symbol} | "
                f"Capital €{capital} | Grid {grid_levels} levels | Buy dist -{buy_distance}%")
        self._rebuild_state_from_exchange()

    def _load_market_specs(self):
        """Carica min amount e precision dal mercato reale."""
        try:
            self._markets = self.exchange.load_markets()
            m = self._markets.get(self.symbol, {})
            lim = m.get('limits', {}).get('amount', {})
            self.min_amount = float(lim.get('min', 0) or 0)
            self.amount_precision = m.get('precision', {}).get('amount', 1e-8)
            self.price_precision = m.get('precision', {}).get('price', 1e-4)
            log.info(f"Market {self.symbol}: min_amount={self.min_amount} "
                     f"amount_prec={self.amount_precision} price_prec={self.price_precision}")
        except Exception as e:
            log.warning(f"load_markets failed ({e}) — using defaults")
            self.min_amount = 0
            self.amount_precision = 1e-8
            self.price_precision = 1e-4

    def _round_amount(self, amount):
        """Arrotonda alla precisione del mercato, rispettando il minimo."""
        if self.amount_precision and self.amount_precision < 1:
            amt = round(amount // self.amount_precision * self.amount_precision, 10)
        else:
            amt = round(amount, 8)
        if self.min_amount and amt < self.min_amount:
            amt = self.min_amount
        return amt

    def _round_price(self, price):
        if self.price_precision and self.price_precision < 1:
            return round(price // self.price_precision * self.price_precision, 10)
        return round(price, 4)

    def _rebuild_state_from_exchange(self):
        try:
            log.info("Rebuilding state from exchange...")
            orders = self.exchange.fetch_open_orders(self.symbol)
            for o in orders:
                oid = o['id']
                side = o['side']
                amount = float(o['amount'])
                price = float(o['price'])
                if side == 'buy':
                    self.open_buys[oid] = {'amount': amount, 'price': price,
                                           'timestamp': time.time(), 'level': 0}
                    log.info(f"Restored BUY: {oid} | {amount} @ {price}")
                else:
                    self.open_sells[oid] = {'amount': amount, 'entry_price': price * 0.99,
                                            'target_price': price, 'timestamp': time.time()}
                    log.info(f"Restored SELL: {oid} | {amount} @ {price}")
            log.info(f"State rebuilt: {len(self.open_buys)} buys, {len(self.open_sells)} sells")
        except Exception as e:
            log.warning(f"State rebuild failed: {e}")

    def check_orders(self):
        try:
            filled_buys = []
            for oid, info in list(self.open_buys.items()):
                try:
                    o = self.exchange.fetch_order(oid, self.symbol)
                    st = o.get('status', 'open')
                    if st in ('closed', 'filled'):
                        log.info(f'BUY FILLED: {oid} | {info["amount"]} {self.base} @ {info["price"]}')
                        filled_buys.append((oid, info))
                        tg_send(f"✅ <b>BUY FILLED</b>\n{self.symbol}: {info['amount']} @ €{info['price']}")
                        log_pnl({'event': 'buy_filled', 'symbol': self.symbol, 'exchange': self.exchange_id,
                                 'amount': info['amount'], 'price': info['price'],
                                 'time': datetime.utcnow().isoformat()})
                    elif st in ('canceled', 'expired', 'rejected'):
                        log.warning(f'BUY CANCELED: {oid}')
                        del self.open_buys[oid]
                except Exception as e:
                    log.debug(f'Check buy err {oid}: {e}')
            for oid, info in filled_buys:
                del self.open_buys[oid]
                self._place_sell(info['amount'], info['price'])

            for oid, info in list(self.open_sells.items()):
                try:
                    o = self.exchange.fetch_order(oid, self.symbol)
                    st = o.get('status', 'open')
                    if st in ('closed', 'filled'):
                        profit = info['amount'] * (info['target_price'] - info['entry_price'])
                        self.total_profit += profit
                        self.total_trades += 1
                        if profit >= 0:
                            self.wins += 1
                        else:
                            self.losses += 1
                        self.volume += info['amount'] * info['target_price']
                        log.info(f'SELL FILLED: {oid} | Profit: +{profit:.4f} {self.quote} | '
                                 f'Total PnL: {self.total_profit:.4f}')
                        tg_send(f"💰 <b>PROFIT</b>\n{self.symbol}: +€{profit:.4f}\n"
                                f"Total PnL: €{self.total_profit:.4f}\nTrades: {self.total_trades}")
                        log_pnl({'event': 'sell_filled', 'symbol': self.symbol, 'exchange': self.exchange_id,
                                 'amount': info['amount'], 'entry': info['entry_price'],
                                 'exit': info['target_price'], 'profit': profit,
                                 'total_pnl': self.total_profit, 'time': datetime.utcnow().isoformat()})
                        del self.open_sells[oid]
                    elif st in ('canceled', 'expired', 'rejected'):
                        log.warning(f'SELL CANCELED: {oid}')
                        del self.open_sells[oid]
                except Exception as e:
                    log.debug(f'Check sell err {oid}: {e}')
        except Exception as e:
            log.error(f'Check orders error: {e}')

    def _place_sell(self, amount, entry_price):
        target = self._round_price(entry_price * (1 + self.profit_target))
        o = place_order(self.exchange, self.symbol, 'sell', self._round_amount(amount), target)
        if o:
            self.open_sells[o['id']] = {'amount': amount, 'entry_price': entry_price,
                                        'target_price': target, 'timestamp': time.time()}
            tg_send(f"📈 <b>SELL PLACED</b>\n{self.symbol}: {amount} @ €{target} "
                    f"(+{self.profit_target*100:.1f}%)")

    def _place_grid(self):
        try:
            t = self.exchange.fetch_ticker(self.symbol)
            price = float(t['last'])
            free_eq, qc, _ = fetch_free_balance(self.exchange)

            # FIX v3.3: capitale effettivo = min(config, saldo libero)
            effective_capital = min(self.capital, free_eq)
            if effective_capital <= 0:
                log.warning(f'No free capital ({free_eq:.2f} {qc}) — grid skipped')
                return

            per_level = effective_capital / self.grid_levels
            placed = 0
            for level in range(self.grid_levels):
                distance = self.buy_distance + (level * 0.005)
                buy_price = self._round_price(price * (1 - distance))
                if buy_price <= 0:
                    continue
                amount = self._round_amount(per_level / buy_price)
                if amount <= 0:
                    continue
                notional = amount * buy_price
                if notional < per_level * 0.8:
                    log.warning(f'Level {level}: notional {notional:.2f} too small vs per_level {per_level:.2f}')
                    continue
                o = place_order(self.exchange, self.symbol, 'buy', amount, buy_price)
                if o:
                    self.open_buys[o['id']] = {'amount': amount, 'price': buy_price,
                                               'timestamp': time.time(), 'level': level}
                    placed += 1

            if placed > 0:
                tg_send(f"🛒 <b>GRID PLACED</b>\n{self.symbol}: {placed} orders | "
                        f"-{self.buy_distance*100:.1f}% to "
                        f"-{(self.buy_distance + (self.grid_levels-1)*0.005)*100:.1f}% | "
                        f"capital €{effective_capital:.2f}")
        except Exception as e:
            log.error(f'Place grid error: {e}')

    def tick(self):
        self.check_orders()
        free_eq, _, _ = fetch_free_balance(self.exchange)
        total_eq = calculate_total_equity(self.exchange, self.quote)
        # Drawdown tracking
        if total_eq > self._peak_equity:
            self._peak_equity = total_eq
        if self._peak_equity > 0:
            dd = (self._peak_equity - total_eq) / self._peak_equity
            self._max_dd = max(self._max_dd, dd)
        # FIX v3.3: basta che il saldo libero copra UN livello, non tutto il capitale
        per_level_needed = self.capital / self.grid_levels
        if free_eq >= per_level_needed and len(self.open_buys) < self.grid_levels:
            self._place_grid()
        log.info(f'STATUS | Free: {free_eq:.2f} | Total Equity: {total_eq:.2f} | '
                 f'Buys: {len(self.open_buys)} | Sells: {len(self.open_sells)} | '
                 f'PnL: {self.total_profit:.4f} | Trades: {self.total_trades} | '
                 f'DD: {self._max_dd*100:.1f}%')
        self._write_health(free_eq, total_eq)

    def _write_health(self, free_eq: float, total_eq: float) -> None:
        """Scrive un file JSON di health per il monitoraggio esterno."""
        health_file = getattr(self, '_health_file', None)
        if not health_file:
            return
        try:
            payload = {
                "symbol": self.symbol,
                "exchange": self.exchange_id,
                "status": "running",
                "capital": self.capital,
                "free_quote": round(free_eq, 4),
                "total_equity": round(total_eq, 4),
                "buys": len(self.open_buys),
                "sells": len(self.open_sells),
                "pnl": round(self.total_profit, 6),
                "trades": self.total_trades,
                "wins": self.wins,
                "losses": self.losses,
                "volume": round(self.volume, 4),
                "drawdown": round(self._max_dd, 4),
                "uptime": round(time.time() - self._start_ts, 0),
                "timestamp": time.time(),
                "ts_iso": datetime.utcnow().isoformat(),
            }
            tmp = health_file + ".tmp"
            with open(tmp, "w") as f:
                json.dump(payload, f)
            os.replace(tmp, health_file)
        except Exception as e:
            log.debug(f"health write failed: {e}")

    def run_loop(self, interval=60):
        log.info('=' * 70)
        log.info(f'SOLO ENGINE v3.3 | {self.exchange_id} | {self.symbol} | '
                 f'TP: {self.profit_target*100:.1f}% | Grid: {self.grid_levels} levels | '
                 f'Buy dist: -{self.buy_distance*100:.1f}%')
        log.info('=' * 70)
        free_eq, qc, tot = fetch_free_balance(self.exchange)
        total_eq = calculate_total_equity(self.exchange, self.quote)
        log.info(f'Starting: free={free_eq:.4f} {qc} | total={tot:.4f} | equity={total_eq:.2f}')
        if free_eq <= 0 and total_eq <= 0:
            log.error('Zero free equity. Exiting.')
            tg_send(f"⚠️ <b>ENGINE STOPPED</b>\n{self.symbol}: zero free equity")
            return
        tg_send(f"🚀 <b>Engine v3.3 started</b>\n{self.exchange_id.upper()} | {self.symbol}\n"
                f"Total Equity: €{total_eq:.2f} | Free: €{free_eq:.2f}")
        iteration = 0
        while True:
            iteration += 1
            log.info(f'--- Tick #{iteration} ---')
            try:
                self.tick()
            except Exception as e:
                log.error(f'Tick error: {e}')
                tg_send(f"❌ <b>TICK ERROR</b>\n{self.symbol}: {str(e)[:200]}")
            time.sleep(interval)


def place_order(exchange, symbol, side, amount, price):
    try:
        if side == 'buy':
            o = exchange.create_limit_buy_order(symbol, amount, price)
        else:
            o = exchange.create_limit_sell_order(symbol, amount, price)
        log.info(f'ORDER PLACED: {o["id"]} | {side.upper()} {amount} {symbol} @ {price}')
        return o
    except Exception as e:
        log.error(f'Order failed: {e}')
        return None


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Alpha-Omega SOLO Engine v3.3 (consolidato)')
    parser.add_argument('--exchange', required=True, choices=['kraken', 'okx'])
    parser.add_argument('--symbol', required=True)
    parser.add_argument('--capital', type=float, default=5.0)
    parser.add_argument('--profit-target', type=float, default=1.5, help='Profit target %%')
    parser.add_argument('--buy-distance', type=float, default=1.0, help='Buy distance below market %%')
    parser.add_argument('--grid-levels', type=int, default=3, help='Number of grid levels')
    parser.add_argument('--interval', type=int, default=60)
    parser.add_argument('--loop', action='store_true')
    parser.add_argument('--health-file', default=None, help='Path JSON per health endpoint')
    args = parser.parse_args()
    if args.loop:
        SoloEngine(args.exchange, args.symbol, args.capital,
                   args.profit_target, args.buy_distance, args.grid_levels,
                   health_file=args.health_file).run_loop(args.interval)
    else:
        # Dry-run: mostra cosa verrebbe piazzato senza creare ordini
        eng = SoloEngine(args.exchange, args.symbol, args.capital,
                         args.profit_target, args.buy_distance, args.grid_levels)
        t = eng.exchange.fetch_ticker(args.symbol)
        price = float(t['last'])
        free_eq, qc, tot = fetch_free_balance(eng.exchange)
        effective = min(args.capital, free_eq)
        per_level = effective / args.grid_levels
        print(f"DRY-RUN {args.exchange} {args.symbol} price={price} free={free_eq:.2f} {qc}")
        for level in range(args.grid_levels):
            distance = args.buy_distance / 100.0 + (level * 0.005)
            bp = eng._round_price(price * (1 - distance))
            amt = eng._round_amount(per_level / bp)
            sp = eng._round_price(bp * (1 + args.profit_target / 100.0))
            print(f"  L{level}: BUY {amt} @ {bp} (≈{amt*bp:.2f}€) -> SELL @ {sp}")
        eng.exchange.close()
        sys.exit(0)
