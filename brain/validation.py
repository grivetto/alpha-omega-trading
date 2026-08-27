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


def verdict(report: dict) -> str:
    t = report["totals"]["trend"]
    g = report["totals"]["grid"]
    if t > 0 and t > g:
        return ("CONFERMA: il trend batte la griglia in paper (24h) → "
                "pronto per il deploy LIVE")
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
    v = verdict(report)
    text = ("🧠 Verdetto validazione TREND vs GRID (paper 24h):\n" + v + "\n" +
            "\n".join(f"{k}: trend={x['trend']:.2f}€ grid={x['grid']:.2f}€"
                      for k, x in report["symbols"].items()) +
            f"\nTOTALE trend={report['totals']['trend']:.2f}€ "
            f"grid={report['totals']['grid']:.2f}€ "
            f"(trade trend={report['totals']['trend_trades']})")
    hermes_bridge.send_telegram(text)
    try:
        p = config.GIT_REPO / "config" / "strategies" / "trend_validation.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"verdict": v, "report": report,
                                 "ts": time.time()}, indent=2),
                     encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    state["trend_validation_done"] = True
    config.save_state(state)
    print(f"[brain] verdetto validazione trend inviato: {v}")
    return True
