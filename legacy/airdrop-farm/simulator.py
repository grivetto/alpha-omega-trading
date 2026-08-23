#!/usr/bin/env python3
"""
Airdrop Farm — Monte Carlo Simulator
Virtual capital: 250 EUR
Horizons: 5 Aug 2026 (deployment day) and full 12-month farming.
Self-contained, no external API. Parameters from DESIGN.md probability table.
"""
import random
from dataclasses import dataclass

random.seed()

CAPITAL = 250.0
N_SIMS = 10_000

# Budget allocation from DESIGN.md (scaled: design was 100 EUR, user now uses 250 virtual)
ALLOC = {
    "airdrop":     250 * 0.47,   # 117.5
    "hyperliquid": 250 * 0.30,   # 75
    "yield":       250 * 0.10,   # 25
    "monad":       250 * 0.08,   # 20
    "launchpad":   250 * 0.05,   # 12.5
}

DAYS_TO_AUG5 = 12          # 24 Jul -> 5 Aug 2026
DAYS_FULL    = 365         # 12-month farming horizon


@dataclass
class SimResult:
    final: float
    airdrop_gain: float
    other_gain: float


def sim_airdrop(budget: float, months: float) -> tuple:
    """4 chains, 10 wallets. Gas is a certain cost; airdrops probabilistic."""
    gas_cost = budget * 0.55          # most of airdrop budget is gas
    reserve  = budget * 0.45
    gain = 0.0
    # Per-chain airdrop distribution over the horizon (per wallet avg, 10 wallets)
    # Based on DESIGN.md scenarios
    for _ in range(4):  # 4 chains
        r = random.random()
        if r < 0.45:    # nothing / dust
            payout = random.uniform(0, 50)
        elif r < 0.75:  # small
            payout = random.uniform(200, 1_500)
        elif r < 0.90:  # medium
            payout = random.uniform(1_500, 6_000)
        else:           # large
            payout = random.uniform(6_000, 25_000)
        # payout scales with months of activity (half-credit before launch)
        scale = min(1.0, months / 8.0)
        gain += payout * scale * random.uniform(0.5, 1.2)
    return gain - gas_cost, reserve


def sim_hyperliquid(budget: float, months: float) -> float:
    """Yield 2-4% APY (near certain) + S3 points (uncertain, lognormal-ish)."""
    apy = random.uniform(0.02, 0.04)
    yield_gain = budget * apy * (months / 12.0)
    r = random.random()
    if r < 0.50:
        points = 0.0
    elif r < 0.80:
        points = budget * random.uniform(0.1, 0.8)
    else:
        points = budget * random.uniform(1.0, 4.0)
    return yield_gain + points


def sim_yield(budget: float, months: float) -> float:
    apy = random.uniform(0.03, 0.05)
    return budget * apy * (months / 12.0)


def sim_monad(budget: float, months: float) -> float:
    gas = budget * 0.8
    r = random.random()
    retro = random.uniform(50, 800) if r > 0.70 else 0.0
    return retro - gas


def sim_launchpad(budget: float) -> float:
    r = random.random()
    if r < 0.5:
        return budget * random.uniform(-0.4, 0.0)
    return budget * random.uniform(0.2, 2.0)


def run_one(months: float) -> SimResult:
    a_gain, a_reserve = sim_airdrop(ALLOC["airdrop"], months)
    # pre-Aug5: solo yield virtuale su stable (3% APY pro-rata) + no gas speso
    if months <= DAYS_TO_AUG5 / 30.0:
        stable_yield = CAPITAL * 0.03 * (months / 12.0)
        return SimResult(final=CAPITAL + stable_yield,
                         airdrop_gain=0.0, other_gain=stable_yield)
    other = (sim_hyperliquid(ALLOC["hyperliquid"], months)
             + sim_yield(ALLOC["yield"], months)
             + sim_monad(ALLOC["monad"], months)
             + sim_launchpad(ALLOC["launchpad"]))
    return SimResult(final=CAPITAL + a_gain + other,
                     airdrop_gain=a_gain, other_gain=other)


def json_report(months: float, label: str) -> dict:
    import json as _j  # noqa
    finals = sorted(run_one(months).final for _ in range(N_SIMS))
    p = lambda q: round(finals[int(q * (N_SIMS - 1))], 2)
    return {
        "label": label, "months": months,
        "p10": p(0.10), "p25": p(0.25), "median": p(0.50),
        "p75": p(0.75), "p90": p(0.90), "mean": round(sum(finals)/N_SIMS, 2),
        "prob_profit": round(sum(1 for f in finals if f > CAPITAL)/N_SIMS*100, 2),
        "prob_10x": round(sum(1 for f in finals if f > CAPITAL*10)/N_SIMS*100, 2),
    }


def report(months: float, label: str):
    finals = sorted(run_one(months).final for _ in range(N_SIMS))
    p = lambda q: finals[int(q * (N_SIMS - 1))]
    prob_profit = sum(1 for f in finals if f > CAPITAL) / N_SIMS
    prob_lose50 = sum(1 for f in finals if f < CAPITAL * 0.5) / N_SIMS
    prob_big    = sum(1 for f in finals if f > CAPITAL * 10) / N_SIMS
    print(f"\n=== {label} ({months:.1f} mesi) — {N_SIMS} simulazioni, capitale €{CAPITAL:.0f} ===")
    print(f"  P10 (pessimo):      €{p(0.10):>10,.0f}")
    print(f"  P25:                €{p(0.25):>10,.0f}")
    print(f"  Mediana:            €{p(0.50):>10,.0f}")
    print(f"  P75:                €{p(0.75):>10,.0f}")
    print(f"  P90 (ottimo):       €{p(0.90):>10,.0f}")
    print(f"  Media:              €{sum(finals)/N_SIMS:>10,.0f}")
    print(f"  P(profitto):        {prob_profit*100:>9.1f}%")
    print(f"  P(perdere >50%):    {prob_lose50*100:>9.1f}%")
    print(f"  P(>10x, €2.5K+):    {prob_big*100:>9.1f}%")


if __name__ == "__main__":
    import sys, json as _json
    if "--json" in sys.argv:
        out = {}
        for months, label in [(DAYS_TO_AUG5/30.0, "aug5"), (6, "m6"), (12, "m12")]:
            d = json_report(months, label)
            for k, v in d.items():
                if k not in ("label", "months"):
                    out[f"{label}.{k}"] = v
        print(_json.dumps(out))
    else:
        print("Airdrop Farm — Monte Carlo — capitale virtuale €250")
        report(DAYS_TO_AUG5 / 30.0, "Oggi → 5 agosto 2026")
        report(6,  "6 mesi di farming")
        report(12, "12 mesi di farming")
