"""Regression tests for auto_gen_1787967900 AdaptiveTrendGrid."""

from auto_gen_1787967900 import AdaptiveTrendGrid, StrategyConfig, _synthetic_prices, _tick_stream


def test_config_validation_bounds():
    assert StrategyConfig(symbol="SOL/EUR", capital_eur=10.0).validate() == []
    assert "capital_eur must be > 0" in StrategyConfig(symbol="SOL/EUR", capital_eur=0.0).validate()
    assert "max_grid_levels must be >= 1" in StrategyConfig(symbol="SOL/EUR", capital_eur=10.0, max_grid_levels=0).validate()
    assert "vol_weight must be in [0,1]" in StrategyConfig(symbol="SOL/EUR", capital_eur=10.0, vol_weight=2.0).validate()
    assert "fee_pct must be in [0, 0.02)" in StrategyConfig(symbol="SOL/EUR", capital_eur=10.0, fee_pct=0.05).validate()


def test_no_naked_trailing_sell():
    cfg = StrategyConfig(symbol="SOL/EUR", capital_eur=13.5, channel_lookback=3, breakout_mult=0.001, adx_trend_threshold=0.0)
    strat = AdaptiveTrendGrid(cfg)
    for ts, px in enumerate([100.0, 101.0, 102.0, 99.0, 97.0]):
        order = strat.on_tick(px, float(ts))
        assert order is None or order["side"] != "sell", order
    assert strat._st.position_qty == 0.0
    assert strat._st.cash_eur == cfg.capital_eur


def test_simulation_respects_cash_and_inventory():
    cfg = StrategyConfig(symbol="SOL/EUR", capital_eur=13.5, max_grid_levels=8, min_trade_eur=1.0)
    strat = AdaptiveTrendGrid(cfg)
    orders = 0
    max_spend = 0.0
    for px, ts in _tick_stream(_synthetic_prices(3000)):
        order = strat.on_tick(px, ts)
        if order is not None:
            orders += 1
            strat.on_fill(str(order["side"]), float(order["size"]), px, ts)
            assert strat._st.cash_eur >= -1e-9
            assert strat._st.position_qty >= -1e-12
            max_spend = max(max_spend, cfg.capital_eur - strat._st.cash_eur)
    assert 1 <= orders < 200, orders
    assert max_spend <= cfg.capital_eur + 1e-9
    assert strat._st.trades == orders


if __name__ == "__main__":
    test_config_validation_bounds()
    test_no_naked_trailing_sell()
    test_simulation_respects_cash_and_inventory()
    print("ALL TESTS OK")
