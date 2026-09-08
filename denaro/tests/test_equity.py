"""Test per denaro.domain.equity — metriche oneste su curva di equity.

Scenari che devono essere veri se il punto 1 (telemetria anti-truffa) tiene:
1. un calo 100->80->risalita 90 produce max drawdown 20% e return -10%;
2. serie corta (pochi campioni e <5 giorni) => warm=False (niente numeri truffa);
3. sampling sporco (equity<=0 o salto >50x) NON entra nella serie;
4. persistenza (extend/ricarica) conserva metrics.
"""
from denaro.domain.equity import EquityTracker, MIN_ROWS


def test_max_drawdown_and_return():
    t = EquityTracker()
    seq = [100.0, 105.0, 110.0, 115.0, 120.0, 120.0, 118.0, 114.0,
           110.0, 106.0, 100.0, 96.0, 96.0, 99.0, 102.0, 105.0, 108.0]
    # pad to above MIN_ROWS using flat tail so warm is driven by n not days
    while len(seq) < MIN_ROWS + 5:
        seq.append(seq[-1])
    for i, eq in enumerate(seq):
        t.append(10_000_000 + i * 3600, float(eq))
    ev = t.evaluate()
    # return: last/first
    assert abs(ev["eq_return_pct"] - 8.0) < 1e-6, ev
    # mdd: peak 120 -> trough 96 = 20%
    assert abs(ev["eq_max_dd"] - 20.0) < 1e-3, ev
    assert ev["eq_n"] == len(seq)
    assert ev["eq_warm"] is True


def test_short_series_not_warm():
    t = EquityTracker()
    for i, eq in enumerate([100.0, 101.0, 100.5, 99.9]):
        t.append(10_000_000 + i * 3600, eq)
    ev = t.evaluate()
    assert ev["eq_n"] == 4
    assert ev["eq_warm"] is False  # pochi campioni e < un giorno


def test_dirty_samples_ignored():
    t = EquityTracker()
    t.append(0.0, -5.0)          # equity negativa
    t.append(1.0, 100.0)
    t.append(2.0, 6000.0)        # salto 60x -> lettura sporca, scartata
    assert t.evaluate()["eq_n"] == 1  # 100 solo


def test_max_drawdown_order_independent_of_first_peak_low():
    # se il primo campione è alto e poi scende costantemente
    t = EquityTracker()
    for i, eq in enumerate([1000.0, 900.0, 800.0, 720.0]):
        t.append(i * 3600, eq)
    assert abs(t.max_drawdown() - 0.28) < 1e-9  # (1000-720)/1000


def test_extend_roundtrip_preserves_metrics():
    t = EquityTracker()
    seq = [100.0]
    # gentle saw
    for k in range(1, MIN_ROWS + 3):
        seq.append(seq[-1] + (0.2 if k % 2 else -0.1))
    raw = []
    for i, eq in enumerate(seq):
        ts = 2_000_000_000 + i * 3600
        t.append(ts, eq)
        raw.append((ts, eq))
    ev1 = t.evaluate()

    t2 = EquityTracker()
    t2.extend(raw)                # simulazione ricarica da persistenza
    ev2 = t2.evaluate()
    assert ev2["eq_max_dd"] == ev1["eq_max_dd"]
    assert abs(ev2["eq_return_pct"] - ev1["eq_return_pct"]) < 1e-9
    assert ev2["eq_sharpe"] == ev1["eq_sharpe"]
    assert ev2["eq_warm"] == ev1["eq_warm"]
