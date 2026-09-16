#!/usr/bin/env python3
"""Test di regressione della revisione esterna del 2026-09-15.

Ogni test qui corrisponde a un difetto trovato dal revisore e blocca la sua
reintroduzione. I riferimenti (C2, A12, A21, M1, M14, M15, M19) sono quelli
del report in `docs/16_revisione_esterna.md`.

Nota: si usa una directory dentro il repo (`.pytmp`) invece di `tempfile`,
perche' alcune sandbox di esecuzione negano la scrittura nelle directory
temporanee di sistema e falserebbero l'esito.
"""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from denaro.application.portfolio import PortfolioManager
from denaro.domain.momentum import MomentumParams, MomentumPolicy
from denaro.domain.risk import _DAY_SEC, _DEFAULT_VAR_95_1H, RiskManager, _week_start_ts
from denaro.domain.types import CBState, CoreState, Trend
from denaro.infrastructure.rate_limiter import RateLimiterRegistry
from denaro.infrastructure.storage import AtomicFile

_REPO_TMP = Path(__file__).resolve().parents[2] / ".pytmp" / "review_fixes"


# ── C2: il rate limiter deve essere realmente centralizzato ──────────────────

def test_c2_register_riusa_lo_stesso_bucket():
    """Due bot dello stesso exchange devono condividere UN solo budget API.

    Prima `register` creava sempre un TokenBucket nuovo: N bot => N bucket =>
    il limite effettivo era N volte quello configurato.
    """
    reg = RateLimiterRegistry()
    a = reg.register("okx", capacity=10.0, refill_rate=1.0)
    b = reg.register("okx", capacity=10.0, refill_rate=1.0)
    assert a is b, "register deve restituire il bucket esistente, non ricrearlo"


def test_c2_il_budget_e_condiviso_tra_i_chiamanti():
    reg = RateLimiterRegistry()
    adapter_1 = reg.register("okx", capacity=3.0, refill_rate=1.0)
    adapter_2 = reg.register("okx", capacity=3.0, refill_rate=1.0)
    for _ in range(3):
        assert adapter_1.try_acquire(1.0, now=0.0)
    # il secondo adapter NON ha un budget indipendente
    assert not adapter_2.try_acquire(1.0, now=0.0)
    assert adapter_2.available == pytest.approx(0.0, abs=1e-9)


def test_c2_exchange_diversi_hanno_bucket_diversi():
    reg = RateLimiterRegistry()
    okx = reg.register("okx", capacity=5.0, refill_rate=1.0)
    kraken = reg.register("kraken", capacity=5.0, refill_rate=1.0)
    assert okx is not kraken


# ── A21: il preflight deve valutare il totale dei livelli ───────────────────

def test_a21_preflight_blocca_se_il_totale_dei_livelli_supera_il_free():
    pm = PortfolioManager()
    pm.update(free=10.0, open_orders=[])
    ok, reason, _ = pm.preflight("SOL/EUR", min_notional=1.0, per_level=4.0,
                                 price=84.0, free=10.0, n_levels=3)
    assert ok is False
    assert "12.0000 > free reale 10.0000" in reason


def test_a21_preflight_consente_se_il_totale_rientra():
    pm = PortfolioManager()
    pm.update(free=10.0, open_orders=[])
    ok, _, _ = pm.preflight("SOL/EUR", min_notional=1.0, per_level=4.0,
                            price=84.0, free=10.0, n_levels=2)
    assert ok is True


def test_a21_default_n_levels_1_preserva_il_comportamento_storico():
    pm = PortfolioManager()
    pm.update(free=10.0, open_orders=[])
    ok, _, _ = pm.preflight("SOL/EUR", min_notional=1.0, per_level=4.0,
                            price=84.0, free=10.0)
    assert ok is True


# ── M1: AtomicFile deve essere durevole oltre che atomico ───────────────────

def test_m1_scrittura_lascia_contenuto_esatto_e_nessun_tmp():
    _REPO_TMP.mkdir(parents=True, exist_ok=True)
    f = AtomicFile(_REPO_TMP / "state.json")
    f.write_json({"equity": 48.1, "pnl": -0.30})
    assert f.read_json_or(None) == {"equity": 48.1, "pnl": -0.30}
    residui = [p for p in _REPO_TMP.iterdir() if p.suffix == ".tmp"]
    assert residui == []


def test_m1_sovrascrittura_non_corrompe_il_file_precedente():
    _REPO_TMP.mkdir(parents=True, exist_ok=True)
    f = AtomicFile(_REPO_TMP / "risk.json")
    f.write_json({"initial_capital": 100.0})
    f.write_json({"initial_capital": 120.0})
    assert f.read_json_or(None) == {"initial_capital": 120.0}


# ── A12: il cap VaR non deve sparire quando la VaR non e' popolata ─────────

def test_a12_position_size_cappato_anche_senza_var():
    rm = RiskManager()
    st = CoreState(initial_capital=100.0, current_capital=100.0, peak_capital=100.0)
    st.kelly_fraction = 0.5
    st.sizing_multiplier = 1.0
    st.regime.dump_mode = False
    # BULL con forza 0.0 non attiva ne' il boost (>0.6) ne' il taglio BEAR:
    # il regime resta neutro rispetto a Kelly.
    st.regime.trend = Trend.BULL
    st.regime.trend_strength = 0.0
    st.regime.volatility_regime = "normal"
    st.regime.volume_regime = "normal"
    st.regime.combined_signal = "neutral"
    st.regime.signal_confidence = 1.0
    # Il default di CoreState e' 0.02: la VaR nulla va forzata, ed e' il caso
    # reale quando il VaR engine non ha ancora prodotto campioni.
    st.var.var_95_1h = 0.0

    size = rm.position_size(st, capital=100.0)
    # con var_95_1h = 0 il vecchio codice dava un cap di 2e8 x capitale.
    tetto = 100.0 * 0.02 / _DEFAULT_VAR_95_1H
    assert size <= tetto + 1e-6, f"cap VaR assente: {size} > {tetto}"
    assert size == pytest.approx(tetto)


# ── M14/M15: le baseline di rischio non devono avvelenarsi ─────────────────

def test_m14_reset_giornaliero_usa_l_equity_corrente_non_il_massimo():
    """Dopo un rialzo la baseline non deve restare alta.

    Con `max()` il giorno seguente si partiva gia' 'in perdita': e' l'origine
    documentata del weekly_loss_-99% spurio.
    """
    rm = RiskManager(daily_loss_limit=0.99, weekly_loss_limit=0.99,
                     max_drawdown_limit=0.99)
    now = time.time()
    st = CoreState(initial_capital=100.0, current_capital=100.0, peak_capital=100.0,
                   day_start_capital=100.0, week_start_capital=100.0,
                   last_daily_reset=now - 2 * _DAY_SEC,
                   last_weekly_reset=_week_start_ts(now))
    rm.check_circuit_breaker(st, 90.0, now)
    assert st.day_start_capital == pytest.approx(90.0)


def test_m15_baseline_a_zero_non_fa_esplodere_il_rapporto():
    rm = RiskManager(daily_loss_limit=0.99, weekly_loss_limit=0.99,
                     max_drawdown_limit=0.99)
    now = time.time()
    # NB: initial_capital resta > 0. Con initial_capital=0 il clamp "30x" di
    # check_circuit_breaker azzera l'equity e il guard non verrebbe esercitato.
    st = CoreState(initial_capital=100.0, current_capital=100.0, peak_capital=100.0,
                   day_start_capital=0.0, week_start_capital=0.0,
                   last_daily_reset=now,
                   last_weekly_reset=_week_start_ts(now))
    blocked = rm.check_circuit_breaker(st, 50.0, now)
    assert st.cb.state != CBState.OPEN
    assert blocked is False
    assert st.week_start_capital == pytest.approx(50.0)
    assert st.day_start_capital == pytest.approx(50.0)


# ── M19: rsi_confirm deve avere effetto ────────────────────────────────────

def _fed_policy(rsi_confirm: float) -> MomentumPolicy:
    p = MomentumPolicy(MomentumParams(fast_period=2, slow_period=3,
                                      history=60, min_history=5,
                                      rsi_confirm=rsi_confirm))
    for i in range(40):
        p.on_price(100.0 + i)
    return p


def test_m19_rsi_confirm_alto_impedisce_il_segnale_bullish():
    assert _fed_policy(101.0)._signal() == "neutral"


def test_m19_rsi_confirm_zero_consente_il_segnale_bullish():
    assert _fed_policy(0.0)._signal() == "bullish"


# ── C7: equity inattendibile ⇒ tick saltato, nessun valore sostitutivo ─────

def _bare_task(capital: float = 12.0, symbol: str = "SOL/EUR"):
    """BotTask minimale per esercitare _guard_equity senza I/O reale.

    Si scrivono i test in forma sincrona con asyncio.run(): il venv di
    produzione non ha pytest-asyncio installato (pytest segnala "Unknown
    config option: asyncio_mode"), quindi un @pytest.mark.asyncio verrebbe
    ignorato in silenzio.
    """
    from types import SimpleNamespace
    from denaro.application.orchestrator import BotTask

    task = BotTask.__new__(BotTask)
    task.cfg = SimpleNamespace(capital=capital, symbol=symbol)
    task.ex = object()          # non e' un PaperExchange -> ramo live
    task._price_source = None
    task._last_error = ""
    return task


def test_c7_equity_inattendibile_ritorna_none_e_non_sostituisce():
    """Su lettura fuori range NON si restituisce un valore inventato.

    Prima si proseguiva con l'ultimo valore valido o, in mancanza, con
    `cfg.capital`: drawdown, circuit breaker e stop-loss venivano calcolati su
    un numero stabile e falso. Osservato dal vivo su mc2 ("equity sospetta
    0.0852 per SOL/EUR -> uso 12.0000") con 0.0005 EUR liberi reali.
    """
    import asyncio

    task = _bare_task()
    res = asyncio.run(task._guard_equity(0.0852))   # 0,7% del capitale
    assert res is None, "un'equity inattendibile non deve produrre un valore"
    assert "inattendibile" in task._last_error


def test_c7_equity_fuori_range_alto_ritorna_none():
    import asyncio

    task = _bare_task()
    assert asyncio.run(task._guard_equity(500.0)) is None    # oltre 30x
    assert asyncio.run(task._guard_equity(float("nan"))) is None


def test_c7_equity_plausibile_viene_restituita():
    import asyncio

    task = _bare_task()
    assert asyncio.run(task._guard_equity(12.0)) == 12.0
    assert asyncio.run(task._guard_equity(40.0)) == 40.0
