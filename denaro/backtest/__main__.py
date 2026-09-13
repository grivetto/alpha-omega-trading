#!/usr/bin/env python3
"""Denaro — CLI del backtest onesto.

Esempi:
    # una singola config su dati reali
    python -m denaro.backtest --exchange okx --symbol SOL/EUR --days 90 \
        --capital 12.7 --levels 3 --buy-distance 0.01 --profit-target 0.015

    # tutti i bot live di un node config (stessa factory della produzione)
    python -m denaro.backtest --config config/node_mc2.yaml --days 90

    # grid search dei parametri, ordinata per rendimento mark-to-market
    python -m denaro.backtest --config config/node.yaml --bot SOL/EUR --days 90 \
        --sweep levels=2,3,4 --sweep profit_target=0.01,0.015,0.02
"""
from __future__ import annotations

import argparse
import itertools
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from .data import load_bars, market_specs
from .metrics import format_summary, summarize
from .runner import BacktestConfig, run_backtest


def _load_overrides(path: Optional[str]) -> Dict[str, Any]:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _apply_overrides(bot: dict, data: dict) -> dict:
    try:
        from ..denaro_node import _OVERRIDE_KEYS
    except Exception:  # pragma: no cover
        return bot
    key = f"{bot.get('mode', 'paper')}:{bot['symbol']}"
    ov = data.get(key) or data.get(bot["symbol"])
    if not isinstance(ov, dict):
        return bot
    merged = dict(bot)
    merged.update({k: v for k, v in ov.items() if k in _OVERRIDE_KEYS})
    return merged


def load_node_bots(path: str) -> List[dict]:
    import yaml
    cfg = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    ov = _load_overrides(cfg.get("overrides_file"))
    bots = []
    for b in cfg.get("bots", []):
        b = _apply_overrides(b, ov)
        if not b.get("enabled", True):
            continue
        bots.append(b)
    return bots


def _exchange_for_bot(bot: dict, fallback: str) -> str:
    mode = bot.get("mode", "paper")
    if mode in ("okx", "kraken", "binance"):
        return mode
    return fallback  # i bot paper usano i prezzi dell'hub (OKX EEA)


def run_one(bot: dict, exchange: str, args) -> Dict[str, Any]:
    symbol = bot["symbol"]
    fee = float(bot.get("fee", args.fee))
    specs = market_specs(exchange, symbol, fallback_min_notional=args.min_notional)
    min_amount = float(bot.get("min_amount", specs["min_amount"]))
    min_notional = float(bot.get("min_notional", specs["min_notional"]))
    import time as _t
    until_ms = (int(_t.time() * 1000) - int(getattr(args, "end_days_ago", 0) or 0) * 86_400_000)
    bars = load_bars(exchange, symbol, args.timeframe, days=args.days,
                     until_ms=until_ms, refresh=args.refresh, verbose=args.verbose)
    capital = float(bot.get("capital", args.capital))
    cfg = BacktestConfig(
        symbol=symbol,
        capital=capital,
        cash=float(bot.get("cash", getattr(args, "cash", 0.0)) or capital),
        bot=bot,
        fee=fee,
        min_amount=min_amount,
        min_notional=min_notional,
        amount_precision=float(bot.get("amount_precision", specs["amount_precision"])),
        price_precision=float(bot.get("price_precision", specs["price_precision"])),
        initial_asset=float(bot.get("initial_asset", args.initial_asset)),
        slippage=float(bot.get("slippage", args.slippage)),
        stop_loss_pct=float(bot.get("stop_loss_pct", 0.0)),
        daily_loss_limit=float(bot.get("daily_loss_limit", 0.05)),
        max_drawdown_limit=float(bot.get("max_drawdown_limit", 0.15)),
        weekly_loss_limit=float(bot.get("weekly_loss_limit", 0.20)),
    )
    res = run_backtest(cfg, bars)
    s = summarize(res)
    s["strategy"] = bot.get("strategy", "grid")
    s["mode"] = bot.get("mode", "paper")
    s["exchange"] = exchange
    s["levels"] = bot.get("levels", 3)
    s["buy_distance"] = bot.get("buy_distance", 0.01)
    s["profit_target"] = bot.get("profit_target", 0.015)
    s["fee"] = fee
    return s


def _apply_sweep_params(bot: dict, params: Dict[str, float]) -> dict:
    b = dict(bot)
    for k, v in params.items():
        b[k] = v
    return b


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Denaro — backtest onesto")
    ap.add_argument("--config", help="node config YAML (bot multipli)")
    ap.add_argument("--bot", help="filtra un simbolo dal config")
    ap.add_argument("--exchange", default="okx", choices=["okx", "kraken", "binance"])
    ap.add_argument("--symbol", default="SOL/EUR")
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--timeframe", default="5m")
    ap.add_argument("--capital", type=float, default=100.0)
    ap.add_argument("--levels", type=int, default=3)
    ap.add_argument("--buy-distance", type=float, default=0.01)
    ap.add_argument("--profit-target", type=float, default=0.015)
    ap.add_argument("--strategy", default="grid")
    ap.add_argument("--fee", type=float, default=0.001)
    ap.add_argument("--min-notional", type=float, default=0.0)
    ap.add_argument("--initial-asset", type=float, default=0.0)
    ap.add_argument("--cash", type=float, default=0.0,
                    help="liquidita' iniziale reale del conto (default = capitale del bot); "
                         "serve quando il bot condivide il conto con altri")
    ap.add_argument("--end-days-ago", type=int, default=0,
                    help="sposta la finestra indietro di N giorni (studio multi-regime)")
    ap.add_argument("--slippage", type=float, default=0.0005)
    ap.add_argument("--sell-levels", type=int, default=0)
    ap.add_argument("--sell-distance", type=float, default=0.02)
    ap.add_argument("--sell-step", type=float, default=0.01)
    ap.add_argument("--stop-loss", type=float, default=0.0)
    ap.add_argument("--sweep", action="append", default=[],
                    help="chiave=v1,v2,... (ripetibile) → grid search")
    ap.add_argument("--json", help="salva i risultati in JSON")
    ap.add_argument("--refresh", action="store_true", help="riscarica i dati")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)

    # costruisci la lista dei bot da testare
    if args.config:
        bots = load_node_bots(args.config)
        if args.bot:
            bots = [b for b in bots if b["symbol"] == args.bot]
        if not bots:
            print("nessun bot da testare", file=sys.stderr)
            return 1
    else:
        bots = [{
            "symbol": args.symbol, "capital": args.capital, "levels": args.levels,
            "buy_distance": args.buy_distance, "profit_target": args.profit_target,
            "strategy": args.strategy, "fee": args.fee,
            "sell_levels": args.sell_levels, "sell_distance": args.sell_distance,
            "sell_step": args.sell_step,
            "stop_loss_pct": args.stop_loss, "mode": args.exchange,
        }]

    sweep: Dict[str, List[float]] = {}
    for spec in args.sweep:
        k, _, v = spec.partition("=")
        vals: List[float] = []
        for x in v.split(","):
            x = x.strip()
            vals.append(int(x) if x.isdigit() else float(x))
        sweep[k] = vals

    results: List[Dict[str, Any]] = []
    for bot in bots:
        exchange = _exchange_for_bot(bot, args.exchange)
        if sweep:
            keys = list(sweep)
            for combo in itertools.product(*(sweep[k] for k in keys)):
                params = dict(zip(keys, combo))
                b2 = _apply_sweep_params(bot, params)
                try:
                    s = run_one(b2, exchange, args)
                except Exception as e:  # noqa: BLE001
                    print(f"  [skip] {b2['symbol']} {params}: {e}", file=sys.stderr)
                    continue
                s["sweep"] = params
                results.append(s)
        else:
            s = run_one(bot, exchange, args)
            results.append(s)
            print(format_summary(s, title=f"{bot['symbol']} ({exchange}, "
                                          f"{bot.get('strategy', 'grid')})"))

    if sweep and results:
        rows = sorted(results, key=lambda r: -r["return_pct"])
        print("\n" + "=" * 100)
        print("GRID SEARCH — ordinato per rendimento mark-to-market")
        print("=" * 100)
        hdr = (f"{'symbol':10} {'strategy':9} {'params':38} {'ret%':>8} "
               f"{'hodl%':>8} {'maxDD%':>7} {'cicli':>6} {'fee%':>6} {'ord':>5}")
        print(hdr)
        for r in rows:
            p = ",".join(f"{k}={v}" for k, v in r.get("sweep", {}).items())
            print(f"{r['symbol']:10} {r['strategy']:9} {p:38} "
                  f"{r['return_pct']:>8.3f} {r['hodl_all_in_pct']:>8.3f} "
                  f"{r['max_drawdown_pct']:>7.2f} {r['cycles']:>6} "
                  f"{r['fees_pct_of_capital']:>6.2f} {r['orders_placed']:>5}")

    if args.json:
        Path(args.json).write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"\nrisultati salvati in {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
