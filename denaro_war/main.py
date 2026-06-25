"""Denaro WAR v4 — Multi-strategy war machine. Last updated: hammer time."""
import json, os, sys, time
from datetime import datetime
from engine import BinanceEngine as Engine
from strategies.scalper import Scalper
from strategies.whale_tracker import WhaleTracker
from strategies.news_reactor import NewsReactor

def main():
    # Load config
    cfg_path = os.path.join(os.path.dirname(__file__), "config", "war_config.json")
    with open(cfg_path) as f:
        cfg = json.load(f)

    eng = Engine(cfg_path)

    total = cfg["total_capital"]
    symbols = cfg["symbols"]  # ["SOLUSDC","ADAUSDC","DOGEUSDC"]
    
    # Capital allocation
    pools = {
        "scalper": total * 0.40,
        "whale_tracker": total * 0.30,
        "news_reactor": total * 0.30,
    }

    print("=" * 50)
    print("  DENARO WAR MACHINE v4")
    print(f"  Capital: ${total:.0f} | {len(symbols)} symbols")
    print("=" * 50)

    # Deploy strategies across all symbols
    strats = []
    for sym in symbols:
        s_cfg = {"entry_drop": 0.008, "atr_spike_threshold": 3.0}
        w_cfg = {"imbalance_threshold": 3.0}
        n_cfg = {}
        strats.append(("scalper", sym, Scalper(eng, sym, pools["scalper"], s_cfg)))
        strats.append(("whale", sym, WhaleTracker(eng, sym, pools["whale_tracker"], w_cfg)))
        strats.append(("news", sym, NewsReactor(eng, sym, pools["news_reactor"], n_cfg)))

    print(f"  {len(strats)} strategies active")
    cycle = 0

    while True:
        try:
            cycle += 1
            for stype, sym, strat in strats:
                result = strat.run()
                if result and "action" in result:
                    print(f"  [{sym}] {stype}: {result['action']} "
                          f"@{result.get('price',0):.2f} x{result.get('qty',0):.4f}")

            if cycle % 30 == 0:
                tt = sum(s[2].t for s in strats)
                tp = sum(s[2].pnl for s in strats)
                print(f"  Cycle {cycle} | Trades: {tt} | PnL: ${tp:+.2f}")

            time.sleep(1)

        except KeyboardInterrupt:
            print("\n  Shutting down...")
            break
        except Exception as e:
            print(f"  ! {str(e)[:80]}")
            time.sleep(5)

if __name__ == "__main__":
    main()
