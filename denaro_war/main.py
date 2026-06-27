"""Denaro WAR v5 — State-driven war machine. Sync strategies, real BinanceEngine."""
import json, os, sys, time, signal
from datetime import datetime

# Set up path for imports
sys.path.insert(0, os.path.dirname(__file__))

from engine import BinanceEngine
from ws_engine import WSEngine
from strategies.sync_strategies import Scalper, WhaleTracker, NewsReactor
from strategies.state_engine import StateEngine


def main():
    cfg_path = os.path.join(os.path.dirname(__file__), "config", "war_config.json")
    with open(cfg_path) as f:
        cfg = json.load(f)

    # Use WebSocket engine if available, fallback to REST
    try:
        eng = WSEngine(cfg_path)
        print("  ⚡ WebSocket engine active")
    except Exception as e:
        print(f"  ⚠️ WS engine unavailable ({e}), using REST")
        eng = BinanceEngine(cfg_path)
    total = float(cfg.get("total_capital", 70))
    symbols = cfg.get("symbols", ["SOLUSDC"])

    # Initialize State Engine
    state_eng = StateEngine(lookback_days=20, threshold_pct=5.0)

    # Strategy pools — capital per strategy TYPE (shared across symbols)
    pools = {
        "scalper": total * 0.40,
        "whale_tracker": total * 0.30,
        "news_reactor": total * 0.30,
    }

    print("=" * 50)
    print("  ⚔️  DENARO WAR v5 — STATE ENGINE ⚔️")
    print(f"  Capital: ${total:.0f} | {len(symbols)} symbols")
    print("=" * 50)

    # Create strategy instances for each symbol
    strats = []
    for sym in symbols:
        s_cfg = {"entry_drop": 0.008, "take_profit": 0.004, "stop_loss": 0.02,
                 "atr_spike_threshold": 3.0, "cooldown_after_exit_seconds": 30}
        w_cfg = {"imbalance_threshold": 3.0, "take_profit_bps": 80, "stop_loss_bps": 150}
        n_cfg = {}

        strats.append(("scalper", sym, Scalper(eng, sym, pools["scalper"], s_cfg)))
        strats.append(("whale", sym, WhaleTracker(eng, sym, pools["whale_tracker"], w_cfg)))
        strats.append(("news", sym, NewsReactor(eng, sym, pools["news_reactor"], n_cfg)))

    print(f"  {len(strats)} strategies | State Engine: {state_eng.lookback}d lookback")

    # --- Cancel orphaned orders from previous runs ---
    for sym in symbols:
        try:
            open_orders = eng.open_orders(sym)
            if open_orders:
                print(f"  🧹 Cancelling {len(open_orders)} orphaned orders for {sym}")
                eng.cancel_all(sym)
        except Exception as e:
            print(f"  ⚠️  Could not cancel orders for {sym}: {e}")

    # --- SIGTERM handler for graceful shutdown ---
    _shutdown = {"requested": False}
    def _on_sigterm(sig, frame):
        print("\n  ⚔️  SIGTERM received — graceful shutdown...")
        _shutdown["requested"] = True
    signal.signal(signal.SIGTERM, _on_sigterm)

    cycle = 0
    SLEEP = 0.5  # Fast cycle with WS prices (no API calls for reads)

    while True:
        if _shutdown["requested"]:
            print("  ⚔️  Shutting down WAR machine...")
            for _, sym, _ in strats:
                try:
                    eng.cancel_all(sym)
                except Exception:
                    pass
            sys.exit(0)

        try:
            cycle += 1

            # === DAILY STATE UPDATE (once per ~24 min with 5s cycle) ===
            if cycle % 288 == 1 or not state_eng.state:
                sym = symbols[0]
                try:
                    ohlcv = eng.ohlcv(sym, "1d", limit=25)
                    if ohlcv:
                        p = eng.price(sym)
                        info = state_eng.update(p, ohlcv)
                        strat_signal = state_eng.strategy_signal()
                        print(f"  📊 State: {info['state']} | Strategy: {strat_signal['primary']} "
                              f"| Stickiness: {info['stickiness']:.0%} | "
                              f"Grid={strat_signal['grid']} Scalp={strat_signal['scalper']} Whale={strat_signal['whale']}")
                except Exception as e:
                    print(f"  ⚠️ State update failed: {e}")

            # === RUN STRATEGIES (respecting state) ===
            strat_signal = state_eng.strategy_signal()
            for stype, sym, strat in strats:
                # Disable strategies that don't match market state
                if stype == "scalper" and not strat_signal.get("scalper", True):
                    continue
                if stype == "whale" and not strat_signal.get("whale", True):
                    continue

                try:
                    result = strat.run()
                    if result and "action" in result:
                        print(f"  ⚡ [{sym}] {stype}: {result['action']} "
                              f"@{result.get('price', 0):.4f} "
                              f"{result.get('reason', '')}")
                except Exception as e:
                    print(f"  ❌ [{sym}] {stype}: {str(e)[:80]}")

            # Status every 12s (24 cycles * 0.5s)
            if cycle % 24 == 0:
                tt = sum(s[2].t for s in strats)
                tp = sum(s[2].pnl for s in strats)
                ws_status = "⚡" if getattr(eng, 'ws_alive', False) else "🌐"
                print(f"  {ws_status} C{cycle} | Trades:{tt} | PnL:${tp:+.2f} | State:{state_eng.state}")

            time.sleep(SLEEP)

        except KeyboardInterrupt:
            print("\n  ⚔️  Shutting down WAR machine...")
            break
        except Exception as e:
            print(f"  ! {str(e)[:80]}")
            time.sleep(5)


if __name__ == "__main__":
    main()
