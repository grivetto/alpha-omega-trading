"""Denaro WAR — Multi-strategy crypto war machine. Brutale. Veloce. Redditizio."""
import json, os, sys, time, random
from datetime import datetime
from engine import WarEngine
from strategies.scalper import Scalper
from strategies.whale_tracker import WhaleTracker
from strategies.news_reactor import NewsReactor

def load_config():
    with open(os.path.join(os.path.dirname(__file__), "config", "war_config.json")) as f:
        return json.load(f)

def color(s, c):
    colors = {"green": "\033[92m", "red": "\033[91m", "yellow": "\033[93m", 
              "blue": "\033[94m", "bold": "\033[1m", "end": "\033[0m"}
    return colors.get(c, "") + s + colors["end"]

def main():
    cfg = load_config()
    key = os.getenv("BINANCE_API_KEY", "").strip() or cfg["exchanges"]["binance"]["api_key"]
    sec = os.getenv("BINANCE_API_SECRET", "").strip() or cfg["exchanges"]["binance"]["api_secret"]
    if not key:
        print("Set BINANCE_API_KEY")
        sys.exit(1)

    eng = WarEngine(key, sec)
    symbols = cfg["symbols"]  # ["SOLUSDC","ADAUSDC","DOGEUSDC"]
    total = cfg["total_capital"]
    
    # Capital allocation
    alloc = cfg["capital_allocator"]
    pools = {}
    for s in alloc["strategy_pool"]:
        pools[s] = total * cfg[s].get("max_capital_pct", 0.33)

    print(color("=" * 60, "blue"))
    print(color("  ⚔️  DENARO WAR MACHINE v4 — LET'S FUCKING GO  ⚔️", "bold"))
    print(color("=" * 60, "blue"))
    print(f"  Capital: ${total:.0f} | Symbols: {symbols}")
    print(f"  Scalper: ${pools.get('scalper',0):.0f} | Whale: ${pools.get('whale_tracker',0):.0f} | News: ${pools.get('news_reactor',0):.0f}")
    print(f"  Risk: {cfg['max_risk_per_trade']*100:.0f}%/trade | Daily loss halt: {cfg['max_daily_loss']*100:.0f}%")
    print()

    # Deploy strategies across ALL symbols
    strats = []
    for sym in symbols:
        base = sym.replace("USDC", "")
        if base not in ("SOL", "ADA", "DOGE"):
            continue
        s_cfg = {
            "atr_period": 14, "atr_spike_threshold": 3.0,
            "entry_drop": 0.008, "take_profit": 0.004, "stop_loss": 0.98,
            "min_order": 5.0, "max_order": min(pools.get("scalper", 30) * 0.4, 15.0),
        }
        w_cfg = {
            "imbalance_threshold": 3.0, "take_profit": 0.008,
            "min_order": 5.0, "max_order": min(pools.get("whale_tracker", 30) * 0.3, 12.0),
            "cooldown": 20,
        }
        n_cfg = {
            "volatility_threshold": 5.0, "price_move_threshold": 0.01,
            "take_profit": 0.015, "min_order": 5.0,
            "max_order": min(pools.get("news_reactor", 30) * 0.5, 15.0),
            "cooldown": 300,
        }
        strats.append(("scalper", sym, Scalper(eng, sym, pools["scalper"], s_cfg)))
        strats.append(("whale", sym, WhaleTracker(eng, sym, pools["whale_tracker"], w_cfg)))
        strats.append(("news", sym, NewsReactor(eng, sym, pools["news_reactor"], n_cfg)))

    print(f"  ⚡ {len(strats)} strategie attive su {len(symbols)} simboli")
    print("  " + "-" * 56)

    cycle = 0; daily_pnl = 0.0; day = datetime.now().strftime("%Y-%m-%d")

    while True:
        try:
            cycle += 1
            for stype, sym, strat in strats:
                result = strat.run()
                if result and "action" in result:
                    icon = {"BUY": color("✅ BUY", "green"), "NEWS_BUY": color("🔥 NEWS", "yellow")}
                    print(f"  {datetime.now().strftime('%H:%M:%S')} [{sym}] {stype}: "
                          f"{icon.get(result['action'], result['action'])} "
                          f"@{result.get('price',0):.2f} x{result.get('qty',0):.4f}")

            # Stats every 5 min
            if cycle % 60 == 0:
                total_trades = sum(s[2].trades for s in strats)
                total_pnl = sum(s[2].pnl for s in strats)
                pnl_str = color(f"${total_pnl:+.2f}", "green" if total_pnl >= 0 else "red")
                print(f"\n  📊 Cycle {cycle} | Trades: {total_trades} | P&L: {pnl_str}")
                daily_pnl = total_pnl
                if abs(daily_pnl) / max(total, 1) > cfg["max_daily_loss"]:
                    print(color("  🛑 DAILY LOSS LIMIT — HALTING", "red"))
                    break

            # Reset daily
            if datetime.now().strftime("%Y-%m-%d") != day:
                day = datetime.now().strftime("%Y-%m-%d")
                daily_pnl = 0.0
                for _, _, s in strats:
                    s.pnl = 0.0
                    s.trades = 0

            time.sleep(cfg["orchestrator"]["check_interval_ms"] / 1000 * 10)

        except KeyboardInterrupt:
            print("\n  Shutting down...")
            break
        except Exception as e:
            print(f"  ❌ {str(e)[:80]}")
            time.sleep(5)

if __name__ == "__main__":
    main()
