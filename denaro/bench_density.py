#!/usr/bin/env python3
"""bench_density.py — misura il footprint del Node a densita' N bot (M8).

Obiettivo KPI del blueprint: >= 20 bot paper su MARCODG1 con RSS totale
<= 800 MB e zero OOM (oggi 7 bot processi separati ≈ 820 MB).

Uso (su macchina Linux):
    python -m denaro.bench_density --bots 20 --seconds 15

Misura: RSS del processo, CPU, bot attivi, ordini totali piazzati.
Nessuna rete: i bot paper usano un prezzo sintetico.
"""
from __future__ import annotations

import argparse
import asyncio
import time
from pathlib import Path
from typing import Dict

from denaro.application.orchestrator import BotConfig, BotTask, TradeOrchestrator
from denaro.application.supervisor import ResourceSupervisor
from denaro.domain.grid import GridParams, GridPolicy
from denaro.domain.risk import RiskManager
from denaro.infrastructure.exchanges.paper import PaperExchange


def read_rss_mb() -> float:
    """RSS del processo corrente (Linux /proc/self/status); 0 se non disponibile."""
    try:
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return float(line.split()[1]) / 1024.0
    except Exception:
        pass
    return 0.0


class _StaticFeed:
    """Prezzo sintetico costante per tutti i bot (nessuna rete)."""

    def fetch_ticker(self, symbol: str) -> dict:
        return {"last": 100.0}


async def run_density(n_bots: int, seconds: float, tick_interval: float,
                      data_dir: Path) -> Dict[str, float]:
    orchestrator = TradeOrchestrator(supervisor=ResourceSupervisor())
    start = time.monotonic()
    for i in range(n_bots):
        symbol = f"P{i:03d}/EUR"
        ex = PaperExchange(symbol, capital=100.0)
        cfg = BotConfig(symbol=symbol, capital=100.0, levels=3,
                        buy_distance=0.01, profit_target=0.015,
                        tick_interval=tick_interval,
                        fee=0.001,
                        state_path=data_dir / f"{i}_state.json",
                        journal_path=data_dir / f"{i}_trades.jsonl",
                        health_path=data_dir / f"{i}_health.json")
        policy = GridPolicy(GridParams(levels=3, buy_distance=0.01,
                                       profit_target=0.015))
        risk = RiskManager()
        bot = BotTask(cfg, ex, policy, risk, price_source=lambda: 100.0)
        orchestrator.add_bot(bot)
    setup_s = time.monotonic() - start

    rss0 = read_rss_mb()
    await orchestrator.start_all()
    await asyncio.sleep(seconds)
    await orchestrator.stop_all()
    rss1 = read_rss_mb()

    total_orders = sum(len(b.state.open_buys) + len(b.state.open_sells)
                       for b in orchestrator.bots.values())
    return {
        "n_bots": n_bots,
        "setup_s": round(setup_s, 3),
        "rss0_mb": round(rss0, 1),
        "rss1_mb": round(rss1, 1),
        "rss_delta_mb": round(max(0.0, rss1 - rss0), 1),
        "per_bot_mb": round(max(0.0, rss1 - rss0) / n_bots, 2),
        "open_orders": total_orders,
        "tick_interval": tick_interval,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark densita' del Node")
    parser.add_argument("--bots", type=int, default=20)
    parser.add_argument("--seconds", type=float, default=15.0)
    parser.add_argument("--tick", type=float, default=5.0)
    parser.add_argument("--data-dir", default="/tmp/denaro_bench")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    result = asyncio.run(run_density(args.bots, args.seconds, args.tick, data_dir))
    print("=== DENARO DENSITY BENCHMARK ===")
    for k, v in result.items():
        print(f"  {k}: {v}")
    per = result["per_bot_mb"]
    print(f"  -> ~{per} MB per bot (processo separato v3.3: ~117 MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
