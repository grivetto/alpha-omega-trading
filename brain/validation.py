"""Brain — verdetto validazione istanza TREND vs GRID (paper, finestra 24h).

Allo scadere delle 24h dalla partenza del trend, il Brain calcola il
confronto A PARITA' DI FINESTRA dai journal dei trade (sell_filled con
ts >= partenza trend) e:
- invia il verdetto su Telegram (via hermes send su mc2);
- scrive config/strategies/trend_validation.json nella repo (committato).
Tutto SOLO stdlib; nessuna dipendenza dai file di health (usa i journal).
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from . import config, hermes_bridge

NODE_DATA = Path("/home/marco/denaro_node_app/node_data")
TREND_DATA = Path("/home/marco/denaro_node_app/node_data_trend")
SYMBOLS = ("SOL", "ETH", "ADA", "XRP")


def _journal_pnl(path: Path, since: float) -> tuple[float, int]:
    tot = n = 0
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if r.get("event") == "sell_filled" and r.get("ts", 0) >= since:
                tot += float(r.get("profit", 0) or 0)
                n += 1
    except Exception:  # noqa: BLE001
        pass
    return tot, n


def window_report() -> dict:
    """Confronto TREND vs GRID paper a parita' di finestra (dai journal)."""
    since = hermes_bridge.TREND_START_TS
    out = {"since": since, "symbols": {}}
    for sym in SYMBOLS:
        tt, tn = _journal_pnl(TREND_DATA / f"paper_default_{sym}_EUR_trades.jsonl", since)
        gt, gn = _journal_pnl(NODE_DATA / f"paper_default_{sym}_EUR_trades.jsonl", since)
        out["symbols"][sym] = {"trend": round(tt, 2), "grid": round(gt, 2),
                               "trend_trades": tn, "grid_trades": gn,
                               "delta": round(tt - gt, 2)}
    out["totals"] = {
        "trend": round(sum(v["trend"] for v in out["symbols"].values()), 2),
        "grid": round(sum(v["grid"] for v in out["symbols"].values()), 2),
        "trend_trades": sum(v["trend_trades"] for v in out["symbols"].values()),
        "grid_trades": sum(v["grid_trades"] for v in out["symbols"].values()),
    }
    return out


def wfa_momentum_signal() -> float:
    """Segnale momentum su finestra LUNGA (900 barre ~37gg): media del ret WFA
    dei migliori candidati momentum su SOL/ETH. Negativo → regime avverso al
    trend: il paper 24h puo' essere una finestra fortunata, il live no."""
    from . import strategy_lab  # import lazy: evita ciclo con la runda
    rets = []
    for sym in ("SOL/EUR", "ETH/EUR"):
        try:
            candles = strategy_lab.fetch_ohlcv_okx(sym, limit=900)
            best = None
            for p in strategy_lab.param_grid_momentum():
                m = strategy_lab.walk_forward_evaluate(candles, p)
                s = strategy_lab.score(m)
                if s > -1e8 and (best is None or s > best[0]):
                    best = (s, m)
            if best:
                rets.append(best[1]["ret"])
        except Exception:  # noqa: BLE001
            continue
    return sum(rets) / len(rets) if rets else 0.0


def verdict(report: dict, wfa_signal: float | None = None) -> str:
    t = report["totals"]["trend"]
    g = report["totals"]["grid"]
    if wfa_signal is None:
        wfa_signal = wfa_momentum_signal()
    if t > 0 and t > g:
        if wfa_signal >= -0.03:
            return ("CONFERMA: il trend batte la griglia in paper (24h) e la "
                    "WFA 37gg sul momentum non e' negativa → pronto per il "
                    "deploy LIVE")
        return ("CONFERMA PARZIALE: paper 24h positivo MA la WFA 37gg sul "
                "momentum e' avversa (" + f"{wfa_signal:.1%}" +
                ") → live SOLO se il mercato entra in trend (Hurst/ADX alto); "
                "intanto resta in paper")
    if t > 0:
        return ("POSITIVO ma sotto la griglia: il trend guadagna, la griglia "
                "di piu' → tieni il trend in paper")
    return ("NON CONFERMA: trend paper non profittevole in 24h → resta "
            "laboratorio (niente live)")


def check_and_report() -> bool:
    """Se le 24h sono scadute e non ancora riportato → verdetto + Telegram."""
    elapsed = time.time() - hermes_bridge.TREND_START_TS
    if elapsed < 24 * 3600:
        return False
    state = config.load_state()
    if state.get("trend_validation_done"):
        return False
    report = window_report()
    wfa = wfa_momentum_signal()   # ~1-2 min (WFA 900 barre su SOL/ETH)
    v = verdict(report, wfa)
    text = ("🧠 Verdetto validazione TREND vs GRID (paper 24h):\n" + v + "\n" +
            f"WFA momentum 37gg: {wfa:.1%}\n" +
            "\n".join(f"{k}: trend={x['trend']:.2f}€ grid={x['grid']:.2f}€"
                      for k, x in report["symbols"].items()) +
            f"\nTOTALE trend={report['totals']['trend']:.2f}€ "
            f"grid={report['totals']['grid']:.2f}€ "
            f"(trade trend={report['totals']['trend_trades']})")
    hermes_bridge.send_telegram(text)
    try:
        p = config.GIT_REPO / "config" / "strategies" / "trend_validation.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"verdict": v, "wfa_signal": wfa,
                                 "report": report, "ts": time.time()},
                                indent=2), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    state["trend_validation_done"] = True
    config.save_state(state)
    print(f"[brain] verdetto validazione trend inviato: {v}")
    return True
