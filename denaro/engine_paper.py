#!/usr/bin/env python3
"""
Alpha-Omega PAPER TRADE Engine v1.0 — simulazione del grid trading con prezzi REALI.

Simula esattamente la strategia del motore live (grid: buy sotto il prezzo, sell a +TP),
ma SENZA toccare soldi reali:
- Legge prezzi reali da OKX EEA (ticker + OHLCV)
- Simula i fill quando il prezzo tocca i livelli
- Tiene lo stato in memoria + persistenza su file JSON
- Report P&L, trades, win rate

Uso: python engine_paper.py --symbol ADA/EUR --capital 500 --levels 3 --buy-dist 1.5 --tp 2.0
"""
import argparse
import json
import sys
import time
from pathlib import Path

import ccxt

FEE = 0.001  # 0.1% per lato

STATE_DIR = Path(__file__).resolve().parent / "paper_state"


class PaperGrid:
    def __init__(self, symbol, capital, levels, buy_dist, tp, interval=60):
        self.symbol = symbol
        self.capital = capital
        self.levels = levels
        self.buy_dist = buy_dist / 100.0
        self.tp = tp / 100.0
        self.interval = interval
        self.ex = ccxt.okx({'enableRateLimit': True, 'hostname': 'eea.okx.com'})
        self.base, self.quote = symbol.split('/')

        self.cash = capital
        self.asset = 0.0
        self.buys = []    # [{price, amount}]
        self.sells = []   # [{price, amount}]
        self.total_pnl = 0.0
        self.trades = 0
        self.wins = 0
        self.losses = 0
        self.volume = 0.0
        self.peak_equity = capital
        self.max_dd = 0.0
        self.start_ts = time.time()

        self._load_state()
        self._load_market()

    def _load_market(self):
        self.ex.load_markets()
        m = self.ex.market(self.symbol)
        lim = m.get('limits', {}).get('amount', {})
        self.min_amount = float(lim.get('min', 0) or 0)
        self.amount_prec = m.get('precision', {}).get('amount', 1e-8)
        self.price_prec = m.get('precision', {}).get('price', 1e-4)

    def _round_amt(self, a):
        if self.amount_prec and self.amount_prec < 1:
            a = round(a // self.amount_prec * self.amount_prec, 10)
        else:
            a = round(a, 8)
        if self.min_amount and a < self.min_amount:
            a = self.min_amount
        return a

    def _round_price(self, p):
        if self.price_prec and self.price_prec < 1:
            return round(p // self.price_prec * self.price_prec, 10)
        return round(p, 6)

    def _state_file(self):
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        name = self.symbol.replace('/', '_')
        return STATE_DIR / f"{name}_paper.json"

    def _save_state(self):
        data = {
            'symbol': self.symbol, 'cash': self.cash, 'asset': self.asset,
            'buys': self.buys, 'sells': self.sells,
            'total_pnl': self.total_pnl, 'trades': self.trades,
            'wins': self.wins, 'losses': self.losses, 'volume': self.volume,
            'peak_equity': self.peak_equity, 'max_dd': self.max_dd,
            'start_ts': self.start_ts,
        }
        self._state_file().write_text(json.dumps(data))

    def _load_state(self):
        f = self._state_file()
        if f.exists():
            try:
                d = json.loads(f.read_text())
                self.cash = d.get('cash', self.capital)
                self.asset = d.get('asset', 0.0)
                self.buys = d.get('buys', [])
                self.sells = d.get('sells', [])
                self.total_pnl = d.get('total_pnl', 0.0)
                self.trades = d.get('trades', 0)
                self.wins = d.get('wins', 0)
                self.losses = d.get('losses', 0)
                self.volume = d.get('volume', 0.0)
                self.peak_equity = d.get('peak_equity', self.capital)
                self.max_dd = d.get('max_dd', 0.0)
                self.start_ts = d.get('start_ts', time.time())
                print(f"Stato ripristinato: {self.trades} trades, PnL {self.total_pnl:.2f}")
            except Exception:
                pass

    def equity(self, price):
        return self.cash + self.asset * price

    def place_grid(self, price):
        per_level = self.capital / self.levels
        for lvl in range(self.levels):
            dist = self.buy_dist + (lvl * 0.005)
            bp = self._round_price(price * (1 - dist))
            amt = self._round_amt(per_level / bp)
            if amt > 0:
                self.buys.append({'price': bp, 'amount': amt})
        print(f"GRID: {len(self.buys)} buy sotto {price:.4f}")

    def tick(self, price):
        # 1) Fill buy
        filled = []
        for b in self.buys:
            if price <= b['price']:
                cost = b['amount'] * b['price'] * (1 + FEE)
                if cost <= self.cash:
                    self.cash -= cost
                    self.asset += b['amount']
                    sp = self._round_price(b['price'] * (1 + self.tp))
                    self.sells.append({'price': sp, 'amount': b['amount']})
                    self.volume += b['amount'] * b['price']
                    print(f"  ✅ BUY FILLED: {b['amount']} @ {b['price']} -> SELL @ {sp}")
                    filled.append(b)
        for b in filled:
            self.buys.remove(b)

        # 2) Fill sell
        filled_sells = []
        for s in self.sells:
            if price >= s['price']:
                proceeds = s['amount'] * s['price'] * (1 - FEE)
                self.cash += proceeds
                self.asset -= s['amount']
                cost_orig = s['amount'] * (s['price'] / (1 + self.tp)) * (1 + FEE)
                pnl = proceeds - cost_orig
                self.total_pnl += pnl
                self.trades += 1
                if pnl > 0:
                    self.wins += 1
                else:
                    self.losses += 1
                print(f"  💰 SELL FILLED: {s['amount']} @ {s['price']} PnL={pnl:.4f}€")
                filled_sells.append(s)
        for s in filled_sells:
            self.sells.remove(s)

        # 3) Re-grid se capitale libero e pochi buy
        per_level_needed = self.capital / self.levels
        if self.cash >= per_level_needed and len(self.buys) < self.levels:
            self.buys = []
            self.place_grid(price)

        # 4) Drawdown
        eq = self.equity(price)
        if eq > self.peak_equity:
            self.peak_equity = eq
        dd = (self.peak_equity - eq) / self.peak_equity if self.peak_equity > 0 else 0
        self.max_dd = max(self.max_dd, dd)

        self._save_state()

    def run_loop(self):
        print(f"=== PAPER TRADE | {self.symbol} | capital={self.capital} | "
              f"levels={self.levels} | dist={self.buy_dist*100:.1f}% | TP={self.tp*100:.1f}% ===")
        if not self.buys and not self.sells:
            t = self.ex.fetch_ticker(self.symbol)
            self.place_grid(t['last'])
        while True:
            try:
                t = self.ex.fetch_ticker(self.symbol)
                price = float(t['last'])
                self.tick(price)
                eq = self.equity(price)
                pnl_pct = (eq - self.capital) / self.capital * 100
                print(f"STATUS | price={price:.5f} | equity={eq:.2f} ({pnl_pct:+.2f}%) | "
                      f"cash={self.cash:.2f} | asset={self.asset:.4f} | "
                      f"buys={len(self.buys)} | sells={len(self.sells)} | "
                      f"PnL={self.total_pnl:.4f} | trades={self.trades} | "
                      f"WR={self.wins/(self.wins+self.losses)*100:.0f}%" if (self.wins+self.losses) else "")
            except Exception as e:
                print(f"tick error: {e}")
            time.sleep(self.interval)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--symbol', required=True)
    ap.add_argument('--capital', type=float, required=True)
    ap.add_argument('--levels', type=int, default=3)
    ap.add_argument('--buy-dist', type=float, default=1.5)
    ap.add_argument('--tp', type=float, default=2.0)
    ap.add_argument('--interval', type=int, default=60)
    ap.add_argument('--once', action='store_true', help='Un solo tick (test)')
    args = ap.parse_args()

    pg = PaperGrid(args.symbol, args.capital, args.levels, args.buy_dist, args.tp, args.interval)
    if args.once:
        t = pg.ex.fetch_ticker(args.symbol)
        pg.tick(float(t['last']))
        eq = pg.equity(float(t['last']))
        print(f"ONCE: equity={eq:.2f} trades={pg.trades} pnl={pg.total_pnl:.4f}")
        sys.exit(0)
    pg.run_loop()
