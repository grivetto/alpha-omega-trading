#!/usr/bin/env python3
"""
Capital Manager — Dynamic capital allocation across bots
Runs every 30 minutes. Reads performance from memory DB,
decides how to distribute EUR across Stellatron, MarcoSOL, ORION.
"""
import json, os, sys
from pathlib import Path
from datetime import datetime, timezone

BASE = Path(__file__).parent
sys.path.insert(0, str(BASE))
from denaro_memory import DenaroMemory


def allocate():
    memory = DenaroMemory()
    regime_info = memory.get_current_regime()
    regime = regime_info["regime"]

    bots = ["stellatron", "marco_sol", "orion"]
    perf = {}
    total_score = 0

    for bot in bots:
        stats = memory.get_trade_stats(bot, n=20)
        if stats["count"] >= 3:
            win_rate = stats["win_rate"]
            avg_pnl = stats["avg_pnl"]
            # Score formula: win rate + profitability + minimum activity bonus
            score = (win_rate / 100.0) * 0.5 + max(0, avg_pnl * 50) * 0.3 + 0.2
        else:
            score = 0.33  # neutral for new bots
        perf[bot] = {"score": score, "stats": stats}
        total_score += score

        # Minimum EUR reserve (never allocate this — keeps powder dry)
    min_eur_reserve = 20.0
    deployable_eur = 200.0  # 220 - 20 reserve

    allocations = {}
    reserve_rationale = f"reserve={min_eur_reserve}€ kept aside"

    if total_score > 0:
        for bot in bots:
            weight = perf[bot]["score"] / total_score
            if regime == "volatile":
                weight = min(weight, 0.4)
            elif regime == "quiet":
                weight = max(weight, 0.2)

            alloc = round(deployable_eur * weight, 2)
            alloc = max(5.0, min(alloc, deployable_eur * 0.6))
            allocations[bot] = alloc
    else:
        equal = round(deployable_eur / len(bots), 2)
        for bot in bots:
            allocations[bot] = equal

    for bot, alloc in allocations.items():
        rationale = f"{reserve_rationale}, score={perf[bot]['score']:.2f}, regime={regime}"
        memory.save_allocation(bot, alloc, rationale)

    print(f"[CAP] Allocations: {json.dumps(allocations)} (reserve={min_eur_reserve}€, regime={regime})")
    return allocations


if __name__ == "__main__":
    allocate()
