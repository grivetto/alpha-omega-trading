#!/usr/bin/env python3
"""Test di dominio Denaro — grid, risk, indicators (puri, senza I/O).

Esecuzione:
    python -B -m unittest denaro.tests.test_domain -v
"""
import unittest

from denaro.domain import GridParams, GridPolicy, RiskManager
from denaro.domain.indicators import (AdvancedIndicators, atr_percent, clamp,
                                      historical_var, volatility_regime)
from denaro.domain.types import CBState, CoreState, Trend


def make_policy(**kw) -> GridPolicy:
    params = GridParams(**kw)
    return GridPolicy(
        params=params,
        round_price=lambda p: round(p, 4),
        round_amount=lambda a: round(a, 8),
    )


class TestGridPlan(unittest.TestCase):
    """Invarianti di pianificazione e riconciliazione."""

    def test_plan_grid_piazza_esattamente_il_numero_di_livelli(self):
        pol = make_policy(levels=3, buy_distance=0.01, profit_target=0.02)
        plan = pol.plan_grid(price=100.0, capital=30.0)
        self.assertEqual(len(plan), 3)
        prices = [l.buy_price for l in plan]
        # distanze crescenti: 1%, 1.5%, 2% sotto il prezzo
        self.assertAlmostEqual(prices[0], 99.0, places=3)
        self.assertAlmostEqual(prices[1], 98.5, places=3)
        self.assertAlmostEqual(prices[2], 98.0, places=3)
        # notional per livello = capitale/livelli
        for l in plan:
            self.assertAlmostEqual(l.notional, 10.0, places=3)
        # TP: sell target > buy price
        self.assertGreater(pol.sell_target(prices[0]), prices[0])

    def test_effective_capital_min(self):
        pol = make_policy()
        self.assertEqual(pol.effective_capital(50.0, 20.0), 20.0)
        self.assertEqual(pol.effective_capital(50.0, 80.0), 50.0)
        self.assertEqual(pol.effective_capital(50.0, 0.0), 0.0)

    def test_griglia_piena_non_riposiziona(self):
        """Invariante: con la griglia piena, nessun nuovo ordine."""
        pol = make_policy(levels=3, buy_distance=0.01)
        open_buys = {
            "b1": {"price": 99.0, "amount": 0.1, "timestamp": 1000.0, "notional": 9.9, "level": 0},
            "b2": {"price": 98.5, "amount": 0.1, "timestamp": 1000.0, "notional": 9.85, "level": 1},
            "b3": {"price": 98.0, "amount": 0.1, "timestamp": 1000.0, "notional": 9.8, "level": 2},
        }
        d = pol.decide(price=100.0, open_buys=open_buys, open_sells={},
                       cash=0.0, capital_config=30.0, free_balance=0.0, now=2000.0)
        self.assertEqual(d.to_place, [])
        self.assertEqual(d.to_cancel, [])

    def test_re_grid_piazza_solo_i_mancanti(self):
        """FIX C7: con 2 buy aperti su 3, piazza UN livello, non tutta la griglia."""
        pol = make_policy(levels=3, buy_distance=0.01)
        open_buys = {
            "b1": {"price": 99.0, "amount": 0.1, "timestamp": 1000.0, "notional": 9.9, "level": 0},
            "b2": {"price": 98.5, "amount": 0.1, "timestamp": 1000.0, "notional": 9.85, "level": 1},
        }
        d = pol.decide(price=100.0, open_buys=open_buys, open_sells={},
                       cash=0.0, capital_config=30.0, free_balance=10.0, now=2000.0)
        # esattamente 1 nuovo livello (il terzo), niente cancellazioni
        self.assertEqual(len(d.to_place), 1)
        self.assertEqual(d.to_cancel, [])
        # il nuovo livello e' il piu' lontano (livello 2: -2%)
        self.assertAlmostEqual(d.to_place[0].buy_price, 98.0, places=3)

    def test_invariante_mai_sopra_grid_levels(self):
        """In ogni scenario, buy aperti + nuovi - cancellati <= levels."""
        pol = make_policy(levels=3, buy_distance=0.01)
        scenarios = [
            ({}, 30.0),                                   # griglia vuota
            ({"b1": {"price": 99.0, "amount": 0.1, "timestamp": 1.0, "notional": 9.9}}, 20.0),
            ({"b1": {"price": 99.0, "amount": 0.1, "timestamp": 1.0, "notional": 9.9},
              "b2": {"price": 98.5, "amount": 0.1, "timestamp": 1.0, "notional": 9.85}}, 10.0),
        ]
        for buys, free in scenarios:
            d = pol.decide(price=100.0, open_buys=buys, open_sells={},
                           cash=0.0, capital_config=30.0, free_balance=free, now=2000.0)
            total = len(buys) + len(d.to_place) - len(d.to_cancel)
            self.assertLessEqual(total, 3, f"violazione invariante: {total}")

    def test_buy_stantio_viene_cancellato(self):
        """Un buy troppo lontano dal prezzo (deriva > retarget) viene cancellato
        e il suo posto rioccupato — mai piu' di `levels` aperti."""
        pol = make_policy(levels=3, buy_distance=0.01, retarget_factor=1.5)
        # b1 a -10% dal prezzo: deriva 11% >> 1.5*1% → stantio
        open_buys = {
            "b1": {"price": 90.0, "amount": 0.1, "timestamp": 1000.0, "notional": 9.0, "level": 0},
            "b2": {"price": 98.5, "amount": 0.1, "timestamp": 1000.0, "notional": 9.85, "level": 1},
        }
        d = pol.decide(price=100.0, open_buys=open_buys, open_sells={},
                       cash=0.0, capital_config=30.0, free_balance=10.0, now=2000.0)
        self.assertIn("b1", d.to_cancel)
        # 2 aperti - 1 cancellato = 1 → piazza 2 nuovi, totale <= 3
        self.assertEqual(len(d.to_place), 2)
        total = 2 + len(d.to_place) - len(d.to_cancel)
        self.assertLessEqual(total, 3)

    def test_buy_vecchio_viene_cancellato(self):
        pol = make_policy(levels=3, buy_distance=0.01, max_order_age_s=3600.0)
        open_buys = {
            "b1": {"price": 99.0, "amount": 0.1, "timestamp": 100.0, "notional": 9.9, "level": 0},  # vecchissimo
        }
        d = pol.decide(price=100.0, open_buys=open_buys, open_sells={},
                       cash=0.0, capital_config=30.0, free_balance=20.0, now=7200.0)
        self.assertIn("b1", d.to_cancel)

    def test_saldo_insufficiente_non_piazza(self):
        pol = make_policy(levels=3, buy_distance=0.01)
        d = pol.decide(price=100.0, open_buys={}, open_sells={},
                       cash=0.0, capital_config=30.0, free_balance=1.0, now=2000.0)
        self.assertEqual(d.to_place, [])


class TestRiskManager(unittest.TestCase):
    """Circuit breaker, Kelly, sizing, compounding."""

    def _state(self, equity=100.0) -> CoreState:
        s = CoreState(initial_capital=equity, current_capital=equity,
                      peak_capital=equity, day_start_capital=equity)
        return s

    def test_daily_loss_apre_il_breaker(self):
        rm = RiskManager(daily_loss_limit=0.05)
        s = self._state(100.0)
        # -6% in giornata → OPEN
        opened = rm.check_circuit_breaker(s, 94.0, now=1_000_000.0)
        self.assertTrue(opened)
        self.assertEqual(s.cb.state, CBState.OPEN)
        self.assertIn("daily_loss", s.cb.reason)
        self.assertEqual(s.sizing_multiplier, 0.0)

    def test_drawdown_apre_il_breaker(self):
        rm = RiskManager(max_drawdown_limit=0.15)
        s = self._state(100.0)
        # stessi day/now per evitare il daily reset; day_start basso → niente
        # daily loss: il drawdown dal peak (16%) deve aprire il breaker
        s.last_daily_reset = 1_000_000.0
        s.day_start_capital = 80.0
        rm.check_circuit_breaker(s, 100.0, now=1_000_100.0)   # peak
        opened = rm.check_circuit_breaker(s, 84.0, now=1_000_200.0)  # dd 16% > 15%
        self.assertTrue(opened)
        self.assertIn("drawdown", s.cb.reason)

    def test_recupero_da_open_a_closed(self):
        rm = RiskManager(daily_loss_limit=0.05, max_drawdown_limit=0.15)
        s = self._state(100.0)
        rm.check_circuit_breaker(s, 100.0, now=1_000_000.0)
        rm.check_circuit_breaker(s, 80.0, now=1_000_100.0)   # OPEN (dd 20%)
        self.assertEqual(s.cb.state, CBState.OPEN)
        # recupero: equity 98.5 → dd 1.5% < 7.5% e daily -1.5% > -2.5% → CLOSED
        rm.check_circuit_breaker(s, 98.5, now=1_000_200.0)
        self.assertEqual(s.cb.state, CBState.CLOSED)

    def test_kelly_bound(self):
        rm = RiskManager(kelly_cap=0.50, kelly_floor=0.05)
        s = self._state(100.0)
        s.trade_results = [0.02] * 20 + [-0.01] * 5  # 80% WR
        k = rm.calculate_kelly(s)
        self.assertGreaterEqual(k, rm.kelly_floor)
        self.assertLessEqual(k, rm.kelly_cap)

    def test_kelly_zero_in_dump(self):
        rm = RiskManager()
        s = self._state(100.0)
        s.regime.dump_mode = True
        self.assertEqual(rm.kelly_fraction(s), 0.0)

    def test_position_size_vaR_cap(self):
        rm = RiskManager()
        s = self._state(100.0)
        size = rm.position_size(s, 100.0)
        self.assertGreaterEqual(size, 0.0)
        self.assertLessEqual(size, 100.0)

    def test_compounding_bull(self):
        rm = RiskManager(compound_threshold=1.0, compound_ratio=0.5)
        s = self._state(100.0)
        s.regime.trend = Trend.BULL
        s.regime.trend_strength = 0.8
        s.regime.regime_confidence = 0.9
        new_base = rm.compound_profits(s, 110.0)
        self.assertGreater(new_base, 100.0)
        self.assertLessEqual(new_base, 110.0)

    def test_compounding_bloccato_in_dump(self):
        rm = RiskManager(compound_threshold=1.0, compound_ratio=0.5)
        s = self._state(100.0)
        s.regime.dump_mode = True
        self.assertEqual(rm.compound_profits(s, 110.0), 100.0)


class TestIndicators(unittest.TestCase):
    def test_atr_insufficiente_ritorna_zero(self):
        self.assertEqual(atr_percent([[1, 1, 1, 1, 1, 1]] * 5, period=14), 0.0)

    def test_atr_percent(self):
        ohlcv = [[i, i, i + 1.0, i - 1.0, i, 100] for i in range(20)]
        atr = atr_percent(ohlcv, period=14)
        self.assertGreater(atr, 0.0)
        self.assertLess(atr, 0.2)

    def test_volatility_regime(self):
        self.assertEqual(volatility_regime(0.0005), "low")
        self.assertEqual(volatility_regime(0.002), "normal")
        self.assertEqual(volatility_regime(0.006), "high")
        self.assertEqual(volatility_regime(0.02), "extreme")

    def test_historical_var_default(self):
        self.assertEqual(historical_var([1.0, 1.01]), (0.02, 0.035, 0.03))

    def test_clamp(self):
        self.assertEqual(clamp(5, 0, 10), 5)
        self.assertEqual(clamp(-1, 0, 10), 0)
        self.assertEqual(clamp(15, 0, 10), 10)

    def test_rsi_overbought(self):
        prices = [float(i) for i in range(40)]
        r = AdvancedIndicators.rsi(prices, period=14)
        self.assertEqual(r.signal, "overbought")

    def test_rsi_insufficiente(self):
        r = AdvancedIndicators.rsi([1.0, 2.0], period=14)
        self.assertEqual(r.signal, "neutral")

    def test_bollinger_squeeze_su_prezzi_piatti(self):
        prices = [10.0] * 25
        bb = AdvancedIndicators.bollinger_bands(prices, period=20)
        self.assertEqual(bb.signal, "squeeze")


if __name__ == "__main__":
    unittest.main()
