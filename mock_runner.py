#!/usr/bin/env python3
"""
Mock Kraken Engine — simula orderbook, fill probabilistici, balance.
Usato da MOCK_MODE per testare la griglia senza toccare Kraken reale.
Compatibile con l'interfaccia attesa da main.py (CCXT-like).
"""
import time, random, math
from pathlib import Path
from typing import Dict, List, Optional


class MockKrakenEngine:
    """Simula completamente Kraken REST API con state tracking realistico."""

    def __init__(self, initial_eur=100.0, initial_doge=0.0, start_price=0.064):
        self.eur_balance = initial_eur
        self.doge_balance = initial_doge
        self.base_price = start_price
        self._orders: Dict[str, dict] = {}
        self._next_id = 1000
        self._volatility = 0.0005
        self._trend = 0.0
        self._cycle = 0
        self._fill_probability = 0.08
        self.ws_connected = False

    @property
    def ex(self):
        return self

    def fetch_ticker(self, symbol: str) -> float:
        self._cycle += 1
        drift = self._trend * 0.0001
        noise = random.gauss(0, self._volatility)
        self.base_price *= (1 + drift + noise)
        self.base_price = max(0.001, min(2.0, self.base_price))
        self._trend += random.uniform(-0.02, 0.02)
        self._trend = max(-1.0, min(1.0, self._trend))
        return self.base_price

    def fetch_balance(self, asset: str = None) -> dict | float:
        """CCXT-compatible: returns dict when called without args, float when asset specified."""
        if asset is None:
            return {"total": {"EUR": self.eur_balance, "DOGE": self.doge_balance},
                    "free": {"EUR": self.eur_balance, "DOGE": self.doge_balance}}
        if asset.upper() == "EUR":
            return self.eur_balance
        if asset.upper() == "DOGE":
            return self.doge_balance
        return 0.0

    def fetch_ohlcv(self, symbol: str, timeframe: str = "1h", limit: int = 15):
        ohlcv = []
        price = self.base_price * 0.95
        for i in range(limit):
            high = price * (1 + random.uniform(0, 0.015))
            low = price * (1 - random.uniform(0, 0.015))
            ohlcv.append([
                int((time.time() - (limit - i) * 3600) * 1000),
                price, high, low,
                price * (1 + random.uniform(-0.005, 0.005)),
                100000 * random.uniform(0.5, 2.0),
            ])
            price = ohlcv[-1][4]
        return ohlcv

    def get_microstructure(self) -> dict:
        p = self.base_price
        return {
            "bid": p * 0.999, "ask": p * 1.001,
            "bid_vol": random.uniform(1000, 5000),
            "ask_vol": random.uniform(1000, 5000),
            "cum_bid": random.uniform(5000, 20000),
            "cum_ask": random.uniform(5000, 20000),
            "price": p,
        }

    def fetch_open_orders(self, symbol: str) -> list:
        result = []
        for oid, order in list(self._orders.items()):
            if random.random() < self._fill_probability * 0.2:
                if order["_side"] == "buy":
                    self.eur_balance -= order["_amount"] * order["_price"]
                    self.doge_balance += order["_amount"] * 0.998
                else:
                    self.eur_balance += order["_amount"] * order["_price"] * 0.998
                    self.doge_balance -= order["_amount"]
                del self._orders[oid]
                continue
            result.append({
                "id": oid, "symbol": symbol, "side": order["_side"],
                "price": order["_price"], "amount": order["_amount"],
                "filled": 0.0, "status": "open",
            })
        return result

    def create_limit_buy_order(self, symbol: str, amount: float, price: float) -> Optional[dict]:
        oid = str(self._next_id)
        self._next_id += 1
        self._orders[oid] = {"_side": "buy", "_price": price, "_amount": amount, "_time": time.time()}
        return {"id": oid, "symbol": symbol, "side": "buy", "amount": amount, "price": price}

    def create_limit_sell_order(self, symbol: str, amount: float, price: float) -> Optional[dict]:
        oid = str(self._next_id)
        self._next_id += 1
        self._orders[oid] = {"_side": "sell", "_price": price, "_amount": amount, "_time": time.time()}
        return {"id": oid, "symbol": symbol, "side": "sell", "amount": amount, "price": price}

    def cancel_all_orders(self, symbol: str) -> None:
        self._orders.clear()

    def round_price(self, price: float) -> float:
        return round(price, 7)

    def round_amount(self, amount: float) -> float:
        return round(amount, 8)


def run_mock_test(cycles: int = 100, verbose: bool = True) -> dict:
    """
    Esegue la griglia Denaro con MockKrakenEngine per N cicli.
    Ritorna statistiche: trades totali, PnL, Kelly finale, win rate.
    """
    import os, sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))

    from denaro_core import DenaroCore, CBState
    from main import TradingEngine, CAPITAL, LEVELS, COOLDOWN

    STATE_FILE = Path("/tmp/kraken_state_mock.json")
    if STATE_FILE.exists():
        STATE_FILE.unlink()

    import main as main_mod
    engine = MockKrakenEngine(initial_eur=CAPITAL, start_price=0.064)
    core = DenaroCore(initial_capital=CAPITAL, state_path=STATE_FILE)

    # Reset state clean
    core.state.perf.total_trades = 0
    core.state.perf.win_trades = 0
    core.state.perf.loss_trades = 0
    core.state.perf.total_pnl_pct = 0.0
    core.state.perf.daily_pnl_pct = 0.0
    core.state.perf.consecutive_wins = 0
    core.state.perf.consecutive_losses = 0
    core.state.perf.last_trade_ts = 0.0
    core.state.cb.state = CBState.CLOSED
    core.state.cb.reason = ""
    core.state.cb.since = 0.0
    core.state.cb.daily_loss_pct = 0.0
    core.state.cb.consecutive_losses = 0
    core.state.current_capital = CAPITAL
    core.state.initial_capital = CAPITAL
    core.state.peak_capital = CAPITAL
    core.state.day_start_capital = CAPITAL
    core._save_state()

    main_mod.SHADOW_MODE = False
    main_mod.DRY_RUN = False

    # Properly initialize TradingEngine (not __new__ bypass)
    grid = TradingEngine.__new__(TradingEngine)
    grid.eng = engine
    grid.core = core
    grid.state = {"levels": []}
    grid._last_ohlcv_fetch = 0.0
    grid._started_at = time.time()
    grid._error_count = 0
    grid._last_perf_log = 0.0

    fills_log = []
    cycle_log = []

    for cycle in range(1, cycles + 1):
        if cycle == 1 or cycle % 5 == 0:
            try:
                ohlcv = engine.fetch_ohlcv("DOGE/EUR", "1h", limit=15)
                core.calculate_atr(ohlcv)
                grid._last_ohlcv_fetch = time.time()
            except Exception:
                pass

        pre_trades = core.state.perf.total_trades

        try:
            grid.run()
        except Exception as e:
            if verbose:
                print(f"  ! Cycle {cycle}: {type(e).__name__}: {e}")
            continue

        post_trades = core.state.perf.total_trades
        equity = engine.eur_balance + engine.doge_balance * engine.base_price
        pnl_pct = (equity - CAPITAL) / CAPITAL * 100

        if post_trades > pre_trades:
            fills_log.append(f"CYCLE {cycle}: {post_trades - pre_trades} FILL(s) | Eq={equity:.2f} PnL={pnl_pct:+.2f}%")

        cycle_log.append({
            "cycle": cycle, "price": engine.base_price, "equity": equity,
            "pnl_pct": pnl_pct, "trades": post_trades,
            "kelly": core.kelly_fraction, "eur_bal": engine.eur_balance,
            "doge_bal": engine.doge_balance, "levels": len(grid.state.get("levels", [])),
        })

        if verbose and cycle % 10 == 0:
            print(f"  [{cycle:3d}/{cycles}] price={engine.base_price:.6f} "
                  f"eq={equity:.2f} pnl={pnl_pct:+.2f}% "
                  f"trades={core.state.perf.total_trades} "
                  f"win={core.state.perf.win_rate*100:.0f}% "
                  f"kelly={core.kelly_fraction*100:.0f}% "
                  f"lvls={len(grid.state.get('levels', []))}")

        time.sleep(0.05)

    final_equity = engine.eur_balance + engine.doge_balance * engine.base_price
    final_pnl = (final_equity - CAPITAL) / CAPITAL * 100

    result = {
        "cycles": cycles,
        "total_trades": core.state.perf.total_trades,
        "win_trades": core.state.perf.win_trades,
        "loss_trades": core.state.perf.loss_trades,
        "win_rate": core.state.perf.win_rate,
        "final_pnl_pct": final_pnl,
        "final_kelly": core.kelly_fraction,
        "final_equity": final_equity,
        "initial_capital": CAPITAL,
        "fills_log": fills_log,
        "cycle_log": cycle_log,
    }

    try:
        STATE_FILE.unlink()
    except OSError:
        pass

    return result


if __name__ == "__main__":
    print("=" * 60)
    print("DENARO MOCK TEST — 100 cycles with simulated fills")
    print("=" * 60)
    result = run_mock_test(cycles=100, verbose=True)

    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"  Cycles:           {result['cycles']}")
    print(f"  Total trades:     {result['total_trades']}")
    print(f"  Wins:             {result['win_trades']}")
    print(f"  Losses:           {result['loss_trades']}")
    print(f"  Win rate:         {result['win_rate']*100:.1f}%")
    print(f"  Final equity:     {result['final_equity']:.2f}")
    print(f"  Final PnL:        {result['final_pnl_pct']:+.2f}%")
    print(f"  Final Kelly:      {result['final_kelly']*100:.0f}%")
    print(f"  Initial capital:  {result['initial_capital']:.2f}")

    ok = True
    if result["total_trades"] == 0:
        print("\nFAIL: Zero trades after 100 cycles — fill simulation broken")
        ok = False
    elif result["total_trades"] < 5:
        print(f"\nWARN: Only {result['total_trades']} trades — fill rate too low")
    else:
        print(f"\nPASS: {result['total_trades']} trades, Kelly={result['final_kelly']*100:.0f}%")

    if result["final_kelly"] == 0.25:
        print("WARN: Kelly never moved from 0.25 — trade recording may be broken")

    if result["fills_log"]:
        print(f"\nFill samples ({len(result['fills_log'])} total):")
        for entry in result["fills_log"][:10]:
            print(f"  {entry}")
        if len(result["fills_log"]) > 10:
            print(f"  ... and {len(result['fills_log']) - 10} more")
