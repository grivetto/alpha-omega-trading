"""Test mirati per ChandelierTrendRider — verifica dei bug fix."""
import csv
import math
import os
import random
import tempfile

from chandelier_trend_rider import (
    ChandelierTrendRider,
    ConfigError,
    DataError,
    TrendConfig,
)


def test_ema_seeding():
    """Fix #1: il primo tick deve fare seed ema_fast == ema_slow == price."""
    r = ChandelierTrendRider()
    r._init_capital(1000.0)
    r.on_tick(100.0, high=100.5, low=99.5, ts=1.0)
    assert r.state.ema_fast == 100.0, f"ema_fast={r.state.ema_fast}"
    assert r.state.ema_slow == 100.0, f"ema_slow={r.state.ema_slow}"


def test_classmethod_csv():
    """Fix #2: from_csv_chunked deve essere invocabile sulla classe."""
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "t.csv")
        with open(p, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["ts", "price", "high", "low"])
            base = 100.0
            for i in range(2000):
                drift = 0.01 if i < 1000 else -0.005
                base += drift
                w.writerow([float(i), round(base, 4), round(base + 0.1, 4), round(base - 0.1, 4)])
        rider = ChandelierTrendRider.from_csv_chunked(p)
        assert isinstance(rider, ChandelierTrendRider)


def test_oversell_rejected():
    """Fix #5: sell qty > position deve sollevare DataError (no clamp silenzioso)."""
    r = ChandelierTrendRider()
    r._init_capital(1000.0)
    r.on_fill("buy", 100.0, 1.0, fee=0.0)
    try:
        r.on_fill("sell", 100.0, 2.0, fee=0.0)
        raise AssertionError("attesa DataError su oversell")
    except DataError:
        pass


def test_sell_without_position_rejected():
    r = ChandelierTrendRider()
    r._init_capital(1000.0)
    try:
        r.on_fill("sell", 100.0, 1.0, fee=0.0)
        raise AssertionError("attesa DataError su sell senza posizione")
    except DataError:
        pass


def test_kill_latch_and_rearm():
    """Fix #3: kill-switch = latch permanente, riarmo solo esplicito via rearm()."""
    r = ChandelierTrendRider()
    r._init_capital(1000.0)
    r.state.killed = True
    sig = r.on_tick(100.0, ts=1.0)
    assert sig["action"] == "hold", sig
    assert sig["state"]["killed"] is True
    r.rearm()
    assert r.state.killed is False


def test_full_cycle_equity_ledger():
    """Fix #4: equity mark-to-market incrementale == ledger cash+position indipendente."""
    cfg = TrendConfig(
        ema_fast=8,
        ema_slow=24,
        atr_period=10,
        atr_mult=2.5,
        risk_pct=0.02,
        fee_rate=0.0001,
        min_vol_ratio=0.0001,
        max_vol_ratio=0.5,
        cooldown_ticks=5,
    )
    r = ChandelierTrendRider(cfg)
    r._init_capital(1000.0)

    cash = 1000.0
    pos = 0.0

    rng = random.Random(7)
    p = 100.0
    n = 5000
    prices = []
    for i in range(n):
        drift = 0.006 if i < n // 2 else -0.004
        p = max(1.0, p + drift + rng.gauss(0, 0.15))
        prices.append((p, p + abs(rng.gauss(0, 0.08)), p - abs(rng.gauss(0, 0.08))))

    last = prices[-1][0]
    for ts, (price, high, low) in enumerate(prices):
        sig = r.on_tick(price, high=high, low=low, ts=float(ts))
        if sig["action"] in ("buy", "sell"):
            qty = sig["qty"]
            fee = qty * price * cfg.fee_rate
            if sig["action"] == "buy":
                cash -= qty * price + fee
                pos += qty
            else:
                cash += qty * price - fee
                pos -= qty
                if pos <= 1e-12:
                    pos = 0.0
            r.on_fill(sig["action"], price, qty, fee=fee, ts=float(ts))

    ledger_equity = cash + pos * last
    assert abs(r.state.equity - ledger_equity) < 1e-4, (
        f"equity {r.state.equity} vs ledger {ledger_equity}"
    )
    assert abs(r.state.position - pos) < 1e-12
    assert r.state.trades > 0
    print(
        f"ledger OK: equity={r.state.equity:.4f} ledger={ledger_equity:.4f} "
        f"trades={r.state.trades} pnl={r.state.realized_pnl:.4f}"
    )


def test_config_validation():
    try:
        ChandelierTrendRider(TrendConfig(ema_fast=50, ema_slow=20))
        raise AssertionError("attesa ConfigError su ema_slow <= ema_fast")
    except ConfigError:
        pass
    for kw in [dict(risk_pct=0.5), dict(atr_mult=0.0), dict(fee_rate=0.1)]:
        try:
            ChandelierTrendRider(TrendConfig(**kw))
            raise AssertionError(f"attesa ConfigError per {kw}")
        except ConfigError:
            pass


if __name__ == "__main__":
    test_ema_seeding()
    test_classmethod_csv()
    test_oversell_rejected()
    test_sell_without_position_rejected()
    test_kill_latch_and_rearm()
    test_full_cycle_equity_ledger()
    test_config_validation()
    print("ALL TESTS OK")