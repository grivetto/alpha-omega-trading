"""Test P5 — telemetria: calcolo Sharpe/Sortino/Calmar/ProfitFactor/WinRate."""
from denaro.domain.types import PerfMetrics


def test_recalc_ratios_positive():
    perf = PerfMetrics()
    results_pct = [1.0, 2.0, -0.5, 1.5, -1.0, 0.5, 2.5, -0.8, 1.8, 0.9,
                   1.1, -0.4, 0.7]
    for r in results_pct:
        perf.update(r / 100.0)
    perf.recalc_ratios([r / 100.0 for r in results_pct],
                       peak_capital=110.0, current_capital=105.0,
                       initial_capital=100.0)
    assert perf.win_rate > 0.5
    assert perf.profit_factor > 1.0
    assert perf.avg_win > perf.avg_loss
    assert perf.sharpe_ratio != 0.0
    assert perf.sortino_ratio != 0.0


def test_recalc_ratios_insufficient_samples():
    perf = PerfMetrics()
    for r in (1.0, -0.5):
        perf.update(r / 100.0)
    perf.recalc_ratios([0.01, -0.005], 110.0, 105.0, 100.0)
    # meno di 5 trade: i ratio restano a zero (niente divisioni per zero)
    assert perf.sharpe_ratio == 0.0
    assert perf.profit_factor == 0.0
