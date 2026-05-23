#!/usr/bin/env python3
"""
Strategy Optimizer — Self-improving parameter engine
Reads trade history from memory DB, analyzes performance vs market conditions,
and outputs optimized parameters for each bot.
"""
import json, os, sys, math, urllib.request
from pathlib import Path
from datetime import datetime, timezone, timedelta

BASE = Path(__file__).parent
sys.path.insert(0, str(BASE))
from denaro_memory import DenaroMemory

BINANCE = "https://api.binance.com"


def fetch_klines(symbol, interval="5m", limit=48):
    url = f"{BINANCE}/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        return [{"time": k[0], "open": float(k[1]), "high": float(k[2]),
                 "low": float(k[3]), "close": float(k[4]), "volume": float(k[5])} for k in data]
    except Exception as e:
        print(f"[OPT] klines error {symbol}: {e}")
        return []


def compute_atr(candles, period=14):
    """ATR as % of price"""
    if len(candles) < period + 1:
        return 0
    trs = []
    for i in range(1, len(candles)):
        h, l, pc = candles[i]["high"], candles[i]["low"], candles[i-1]["close"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    atr = sum(trs[-period:]) / period
    avg_price = candles[-1]["close"]
    return atr / avg_price * 100


# ── Stellatron Optimizer ──
def optimize_stellatron(memory):
    stats = memory.get_trade_stats("stellatron", n=30)
    regime_info = memory.get_current_regime()
    regime = regime_info["regime"]
    volatility = regime_info["volatility"]

    current = memory.get_bot_params("stellatron")
    default = {
        "grid_spacing": 0.003,
        "base_order_eur": 5.5,
        "compound_cap": 1.8,
        "min_grid_levels": 3,
        "max_grid_levels": 6,
    }
    current_params = current["params"] if current["params"] else default

    # Start with current params
    params = dict(current_params)
    changes = []

    # ATR-based dynamic grid spacing: grid_spacing = ATR * 1.5
    candles = fetch_klines("SOLEUR", interval="5m", limit=20)
    atr = compute_atr(candles, period=14)
    if atr > 0:
        atr_spacing = round(atr * 1.5 / 100, 6)
        MIN_SPACING = 0.003
        if atr_spacing < MIN_SPACING:
            atr_spacing = MIN_SPACING
        params["grid_spacing"] = atr_spacing
        changes.append(f"ATR={atr:.3f}% ×1.5 → spacing={atr_spacing:.4f}")
    else:
        # Fallback to volatility-based
        if volatility > 2.0:
            params["grid_spacing"] = min(0.008, params.get("grid_spacing", 0.003) * 1.3)
            changes.append(f"vol={volatility:.1f}% >2% → spacing ↑ x1.3")
        elif volatility < 0.5:
            params["grid_spacing"] = max(0.003, params.get("grid_spacing", 0.003) * 0.8)
            changes.append(f"vol={volatility:.1f}% <0.5% → spacing ↓ x0.8")
        else:
            changes.append(f"vol={volatility:.1f}% normal → spacing unchanged")

        # Fee floor
        if params["grid_spacing"] < MIN_SPACING:
            params["grid_spacing"] = MIN_SPACING
            changes.append(f"fee_floor → min_spacing={MIN_SPACING}")

    # Adjust base order based on win rate
    win_rate = stats.get("win_rate", 50)
    if win_rate > 70 and stats["count"] >= 10:
        params["base_order_eur"] = min(10.0, params.get("base_order_eur", 5.5) * 1.15)
        changes.append(f"win_rate={win_rate:.0f}% >70% → order ↑ x1.15")
    elif win_rate < 40 and stats["count"] >= 10:
        params["base_order_eur"] = max(3.0, params.get("base_order_eur", 5.5) * 0.85)
        changes.append(f"win_rate={win_rate:.0f}% <40% → order ↓ x0.85")

    # Regime-specific adjustments
    if regime == "trending":
        params["max_grid_levels"] = min(4, params.get("max_grid_levels", 6))
        changes.append("regime=trending → max_levels ↓")
    elif regime == "ranging":
        params["max_grid_levels"] = max(6, params.get("max_grid_levels", 6))
        changes.append("regime=ranging → max_levels ↑")
    elif regime == "volatile":
        params["max_grid_levels"] = max(5, params.get("max_grid_levels", 6))
        params["base_order_eur"] = max(3.0, params.get("base_order_eur", 5.5) * 0.8)
        changes.append("regime=volatile → levels ↑, order ↓")
    elif regime == "quiet":
        params["base_order_eur"] = max(3.0, params.get("base_order_eur", 5.5) * 0.85)
        params["max_grid_levels"] = min(4, params.get("max_grid_levels", 6))
        changes.append("regime=quiet → levels ↓, order ↓")

    # Fee floor
    MIN_SPACING = 0.003
    if params["grid_spacing"] < MIN_SPACING:
        params["grid_spacing"] = MIN_SPACING
        changes.append(f"fee_floor → min_spacing={MIN_SPACING}")

    # Round
    params["grid_spacing"] = round(params["grid_spacing"], 4)
    params["base_order_eur"] = round(params["base_order_eur"], 1)

    rationale = "; ".join(changes) if changes else "no change needed"
    score = win_rate if stats["count"] >= 5 else 0
    memory.save_bot_params("stellatron", params, score)

    return {"bot": "stellatron", "params": params, "score": score, "rationale": rationale,
            "stats": stats, "regime": regime}


# ── MarcoSOL Optimizer ──
def optimize_marco_sol(memory):
    stats = memory.get_trade_stats("marco_sol", n=30)
    regime_info = memory.get_current_regime()
    regime = regime_info["regime"]
    volatility = regime_info["volatility"]

    current = memory.get_bot_params("marco_sol")
    default = {"sell_raise": 0.005, "buy_drop": -0.004}
    current_params = current["params"] if current["params"] else default
    params = dict(current_params)
    changes = []

    sr = abs(params.get("sell_raise", 0.005))
    bd = abs(params.get("buy_drop", 0.004))
    FEE_COST = 0.00075 * 2  # 0.15% round-trip fee

    # Adjust spread based on recent trade speed and volatility
    trades = memory.get_recent_trades("marco_sol", limit=20)
    if len(trades) >= 3:
        fill_times = []
        for i in range(1, len(trades)):
            t1 = trades[i-1].get("filled_at", "")
            t2 = trades[i].get("filled_at", "")
            if t1 and t2:
                try:
                    dt1 = datetime.fromisoformat(t1)
                    dt2 = datetime.fromisoformat(t2)
                    diff = abs((dt2 - dt1).total_seconds())
                    if 10 < diff < 86400:
                        fill_times.append(diff)
                except:
                    pass
        if fill_times:
            avg_fill = sum(fill_times) / len(fill_times)
            if avg_fill < 300:
                sr = min(0.012, sr * 1.2)
                bd = min(0.010, bd * 1.2)
                changes.append(f"fast_fill={avg_fill:.0f}s → spread ↑")
            elif avg_fill > 1800:  # fills slower than 30 min → tighten for more action
                sr = max(FEE_COST + 0.0005, sr * 0.8)
                bd = max(FEE_COST + 0.0005, bd * 0.8)
                changes.append(f"slow_fill={avg_fill:.0f}s (>30min) → spread ↓ for more fills")
            else:
                changes.append(f"normal_fill={avg_fill:.0f}s → spread stable")

    # Volatility adjustment
    if volatility > 2.5:
        sr = min(0.015, sr * 1.2)
        bd = min(0.012, bd * 1.2)
        changes.append(f"high_vol={volatility:.1f}% → spread ↑")
    elif volatility < 0.5:
        sr = max(FEE_COST + 0.0005, sr * 0.85)
        bd = max(FEE_COST + 0.0005, bd * 0.85)
        changes.append(f"low_vol={volatility:.1f}% → spread ↓")

    # Fee floor: spread must always exceed round-trip fees + 0.05% buffer
    min_spread = FEE_COST + 0.0005  # 0.20% minimum
    if sr < min_spread:
        sr = min_spread
        changes.append(f"fee_floor → sr={sr:.4f}")
    if bd < min_spread:
        bd = min_spread
        changes.append(f"fee_floor → bd={bd:.4f}")

    params["sell_raise"] = round(sr, 4)
    params["buy_drop"] = round(-bd, 4)

    rationale = "; ".join(changes) if changes else "no change needed"
    memory.save_bot_params("marco_sol", params, stats.get("win_rate", 0))

    return {"bot": "marco_sol", "params": params, "score": stats.get("win_rate", 0),
            "rationale": rationale, "stats": stats, "regime": regime}


# ── ORION Optimizer ──
def optimize_orion(memory):
    stats = memory.get_trade_stats("orion", n=50)
    regime_info = memory.get_current_regime()
    regime = regime_info["regime"]
    volatility = regime_info["volatility"]

    current = memory.get_bot_params("orion")
    default = {
        "BTC/EUR": {"sell_raise": 0.004, "buy_drop": -0.003, "sell_amt": 0.00015, "max_eur": 5},
        "ETH/EUR": {"sell_raise": 0.004, "buy_drop": -0.003, "sell_amt": 0.003, "max_eur": 5},
        "BNB/EUR": {"sell_raise": 0.004, "buy_drop": -0.003, "sell_amt": 0.002, "max_eur": 2},
    }
    current_params = current["params"] if current["params"] else default
    params = dict(current_params)
    changes = []

    # Analyze per-symbol PnL
    trades = memory.get_recent_trades("orion", limit=100)
    symbol_pnl = {}
    for t in trades:
        sym = t.get("symbol", "unknown")
        if sym not in symbol_pnl:
            symbol_pnl[sym] = {"pnl": 0, "count": 0, "wins": 0, "consecutive_losses": 0}
        symbol_pnl[sym]["pnl"] += t.get("net_pnl", 0)
        symbol_pnl[sym]["count"] += 1
        if t.get("net_pnl", 0) > 0:
            symbol_pnl[sym]["wins"] += 1
            symbol_pnl[sym]["consecutive_losses"] = 0
        else:
            symbol_pnl[sym]["consecutive_losses"] = symbol_pnl[sym].get("consecutive_losses", 0) + 1

    for sym, cfg in default.items():
        sp = symbol_pnl.get(sym, {"pnl": 0, "count": 0, "consecutive_losses": 0})
        pair_params = dict(params.get(sym, cfg))

        if sp["count"] >= 3 and sp["consecutive_losses"] >= 3:
            pair_params["paused"] = True
            changes.append(f"{sym}: 3+ consecutive losses → PAUSED")
        elif sp["count"] >= 3 and sp["pnl"] > 0:
            pair_params["paused"] = False
            # Boost size on winners
            pair_params["sell_amt"] = round(min(cfg["sell_amt"] * 1.2, cfg["sell_amt"] * 2), 6)
            pair_params["max_eur"] = min(int(cfg["max_eur"] * 1.3), 10)
            changes.append(f"{sym}: profitable ({sp['pnl']:.4f}€) → size ↑")
        else:
            pair_params["paused"] = False
            changes.append(f"{sym}: no data or neutral → default")

        params[sym] = pair_params

    # Global volatility adjustment
    if volatility > 2.0:
        for sym in default:
            pair_params = params.get(sym, dict(default[sym]))
            pair_params["sell_raise"] = round(min(0.008, pair_params.get("sell_raise", 0.004) * 1.3), 4)
            pair_params["buy_drop"] = round(max(-0.008, pair_params.get("buy_drop", -0.003) * 1.3), 4)
        changes.append(f"high_vol={volatility:.1f}% → all spreads ↑")

    rationale = "; ".join(changes) if changes else "no change needed"
    score = sum(sp.get("pnl", 0) for sp in symbol_pnl.values()) if symbol_pnl else 0
    memory.save_bot_params("orion", params, score)

    return {"bot": "orion", "params": params, "score": round(score, 4),
            "rationale": rationale, "stats": stats, "regime": regime,
            "symbol_pnl": symbol_pnl}


def optimize_all():
    memory = DenaroMemory()
    results = []
    for bot_fn in [optimize_stellatron, optimize_marco_sol, optimize_orion]:
        try:
            result = bot_fn(memory)
            results.append(result)
            p = result["params"]
            print(f"[OPT] {result['bot']}: {json.dumps(p)}")
            print(f"     rationale: {result['rationale']}")
            print(f"     stats: {result.get('stats', {})}")
        except Exception as e:
            print(f"[OPT] Error optimizing: {e}")
            import traceback; traceback.print_exc()
    return results


def export_params_json(results, output_dir=None):
    """Write per-bot params JSON files for remote bots to consume"""
    out = output_dir or BASE
    for r in results:
        bot = r["bot"]
        params = r["params"]
        fname = out / f"params_{bot}.json"
        with open(fname, "w") as f:
            json.dump(params, f, indent=2)
        print(f"[OPT] Exported {fname}")


if __name__ == "__main__":
    results = optimize_all()
    export_params_json(results)
