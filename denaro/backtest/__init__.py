#!/usr/bin/env python3
"""Denaro — harness di validazione (backtest) con parita' LIVE.

Perche' esiste: il progetto ha storicamente deciso parametri e strategie con
script ad-hoc non versionati, senza mark-to-market dell'inventario. Questo
pacchetto valuta le policy REALI (`denaro.domain.*`, le stesse istanziate da
`denaro.denaro_node.build_policy`) su dati di mercato reali, con fee, minimi
di scambio e curva di equity mark-to-market.

Moduli:
- `data`    — download + cache OHLCV (ccxt, OKX EEA / Kraken)
- `sim`     — exchange simulato deterministico (fill, fee, minimi, locked)
- `runner`  — replica del ciclo `BotTask.tick` bar-by-bar
- `metrics` — metriche ONESTE (equity, drawdown, realized vs unrealized, HODL)
"""
from .data import fetch_ohlcv, make_exchange, load_bars  # noqa: F401
from .metrics import summarize, format_summary  # noqa: F401
from .runner import BacktestConfig, BacktestResult, run_backtest  # noqa: F401
from .sim import SimExchange, SimFill, SimOrder, SimRejection  # noqa: F401

__all__ = [
    "fetch_ohlcv", "make_exchange", "load_bars",
    "SimExchange", "SimFill", "SimOrder", "SimRejection",
    "BacktestConfig", "BacktestResult", "run_backtest",
    "summarize", "format_summary",
]
