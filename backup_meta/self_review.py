#!/usr/bin/env python3
"""
Self-Review System — Denaro Self-Improving Trading Agent

Reads trade history, scores bots against defined goals,
generates recommendations for parameter changes.

Loosely inspired by the Hermes self-improving agent pattern:
  "Define goal → execute → score → analyze → adjust → repeat"
"""
import json, math, os, sys, sqlite3, urllib.request
from pathlib import Path
from datetime import datetime, timezone, timedelta

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE))
DB_PATH = BASE / "trades.db"
META_DIR = BASE / "meta"
REVIEWS_DIR = META_DIR / "reviews"

# Goal thresholds per bot
BOT_GOALS = {
    "stellatron": {
        "win_rate_target": 60.0, "win_rate_fail": 40.0, "weight_win_rate": 25,
        "sharpe_target": 1.0, "sharpe_fail": 0.3, "weight_sharpe": 30,
        "dd_target": 8.0, "dd_fail": 15.0, "weight_dd": 20,
        "trades_per_day_target": 12.0, "trades_per_day_target_max": 20.0,
        "trades_per_day_fail": 2.0, "trades_per_day_fail_max": 40.0, "weight_trades": 10,
        "profit_30d_target": 5.0, "profit_30d_fail": -3.0, "weight_profit": 15,
    },
    "orion": {
        "win_rate_target": 55.0, "win_rate_fail": 35.0, "weight_win_rate": 20,
        "sharpe_target": 0.8, "sharpe_fail": 0.2, "weight_sharpe": 25,
        "dd_target": 10.0, "dd_fail": 18.0, "weight_dd": 20,
        "profit_factor_target": 1.5, "profit_factor_fail": 1.0, "weight_profit_factor": 20,
        "profit_30d_target": 8.0, "profit_30d_fail": -5.0, "weight_profit": 15,
    },
    "marco_sol": {
        "win_rate_target": 55.0, "win_rate_fail": 35.0, "weight_win_rate": 25,
        "sharpe_target": 0.8, "sharpe_fail": 0.2, "weight_sharpe": 25,
        "dd_target": 10.0, "dd_fail": 15.0, "weight_dd": 20,
        "trades_per_day_target": 15.0, "trades_per_day_target_max": 30.0,
        "trades_per_day_fail": 2.0, "trades_per_day_fail_max": 50.0, "weight_trades": 10,
        "profit_30d_target": 5.0, "profit_30d_fail": -4.0, "weight_profit": 20,
    },
}

def get_trades(days=30):
    """Fetch trades from last N days"""
    if not DB_PATH.exists():
        print(f"[REVIEW] No trades DB at {DB_PATH}")
        return []
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM trades WHERE exit_time IS NOT NULL AND exit_time >= ? "
        "AND gross_pnl IS NOT NULL ORDER BY exit_time",
        (cutoff,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def group_by_bot(trades):
    bots = {}
    for t in trades:
        name = t.get("bot_name") or t.get("bot") or "unknown"
        if name not in bots:
            bots[name] = []
        bots[name].append(t)
    return bots

def metric_score(value, target, fail, invert=False, target_max=None, fail_max=None):
    """
    Score a metric 0-100.
    100 = at or beyond target
    50 = midway between fail and target
    0 = at or beyond fail threshold

    If invert=True, lower is better (e.g. drawdown).
    If target_max/fail_max provided, the metric has a ceiling (e.g. trades/day).
    """
    # Handle range metrics (e.g. trades/day should be in a window)
    if target_max is not None:
        # Two-sided: too high or too low is bad
        if value < fail:
            return 0
        if value < target:
            # Between fail and target
            return 50 + 50 * (value - fail) / (target - fail)
        if value <= target_max:
            return 100  # Sweet spot
        if value <= fail_max:
            return 50 + 50 * (value - target_max) / (fail_max - target_max)
        # Above fail_max
        return max(0, 50 - 50 * (value - fail_max) / (fail_max - 0))
    
    if invert:
        # Lower is better
        if value <= target:
            return 100
        if value >= fail:
            return 0
        return 100 * (fail - value) / (fail - target)
    else:
        # Higher is better
        if value >= target:
            return 100
        if value <= fail:
            return 0
        return 100 * (value - fail) / (target - fail)

def compute_sharpe(pnls, risk_free=0.0):
    """Approximate daily Sharpe from PnL list"""
    if len(pnls) < 2:
        return 0.0
    mean_pnl = sum(pnls) / len(pnls)
    var = sum((p - mean_pnl) ** 2 for p in pnls) / len(pnls)
    if var == 0:
        return 0.0
    daily_sharpe = (mean_pnl - risk_free) / math.sqrt(var)
    # Annualize? Not needed — we use raw as relative measure
    return daily_sharpe

def compute_drawdown(pnls):
    """Calculate max drawdown from cumulative PnL"""
    if not pnls:
        return 0.0
    cum = 0
    peak = 0
    dd = 0
    for p in pnls:
        cum += p
        peak = max(peak, cum)
        if peak > 0:
            dd = max(dd, (peak - cum) / abs(peak) * 100)
    return dd

def compute_profit_factor(trades):
    gross_profit = sum(t["gross_pnl"] for t in trades if t["gross_pnl"] > 0)
    gross_loss = abs(sum(t["gross_pnl"] for t in trades if t["gross_pnl"] < 0))
    if gross_loss == 0:
        return gross_profit > 0 and 99.0 or 0.0
    return gross_profit / gross_loss

def score_bot(bot_name, trades, days=30):
    """Score a single bot against its goals"""
    goals = BOT_GOALS.get(bot_name)
    if not goals:
        return {"score": None, "reason": f"No goals defined for {bot_name}"}

    if len(trades) == 0:
        return {"score": 0, "reason": "No trades in period", "breakdown": {}}

    pnls = [t["gross_pnl"] for t in trades if t.get("gross_pnl") is not None]
    wins = sum(1 for t in trades if t["gross_pnl"] and t["gross_pnl"] > 0)
    losses = sum(1 for t in trades if t["gross_pnl"] and t["gross_pnl"] < 0)
    total_trades = len(trades)
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0

    # Time span for trades/day
    if len(trades) >= 2:
        times = [datetime.fromisoformat(str(t["exit_time"])) for t in trades if t.get("exit_time")]
        if times:
            span_days = max((max(times) - min(times)).total_seconds() / 86400, 1)
        else:
            span_days = days
    else:
        span_days = days
    
    trades_per_day = total_trades / span_days
    sharpe = compute_sharpe(pnls)
    dd = compute_drawdown(pnls)
    total_pnl = sum(pnls)
    total_fees = sum(t.get("fees", 0) or 0 for t in trades)

    breakdown = {}
    
    # Win Rate
    wr_score = metric_score(win_rate, goals["win_rate_target"], goals["win_rate_fail"])
    breakdown["win_rate"] = {"value": f"{win_rate:.1f}%", "score": wr_score, "weight": goals["weight_win_rate"]}

    # Sharpe
    sh_score = metric_score(sharpe, goals["sharpe_target"], goals["sharpe_fail"])
    breakdown["sharpe"] = {"value": f"{sharpe:.3f}", "score": sh_score, "weight": goals["weight_sharpe"]}

    # Drawdown
    dd_score = metric_score(dd, goals["dd_target"], goals["dd_fail"], invert=True)
    breakdown["drawdown"] = {"value": f"{dd:.1f}%", "score": dd_score, "weight": goals["weight_dd"]}

    # Profit factor (orion-specific)
    if "profit_factor_target" in goals:
        pf = compute_profit_factor(trades)
        pf_score = metric_score(pf, goals["profit_factor_target"], goals["profit_factor_fail"])
        breakdown["profit_factor"] = {"value": f"{pf:.2f}", "score": pf_score, "weight": goals["weight_profit_factor"]}

    # Trades per day (range)
    if "trades_per_day_target" in goals:
        td_score = metric_score(trades_per_day,
            goals["trades_per_day_target"], goals["trades_per_day_fail"],
            target_max=goals.get("trades_per_day_target_max"),
            fail_max=goals.get("trades_per_day_fail_max"))
        breakdown["trades_per_day"] = {"value": f"{trades_per_day:.1f}", "score": td_score, "weight": goals["weight_trades"]}

    # Profit 30d
    if "profit_30d_target" in goals:
        profit_pct = (total_pnl / 100) * 100 if total_pnl != 0 else 0  # rough, needs capital reference
        # XXX: we use gross PnL as rough indicator since we don't track per-bot capital
        profit_score = metric_score(total_pnl, goals["profit_30d_target"], goals["profit_30d_fail"])
        breakdown["profit_30d"] = {"value": f"€{total_pnl:+.2f}", "score": profit_score, "weight": goals["weight_profit"]}

    # Composite score
    total_weight = sum(v["weight"] for v in breakdown.values())
    weighted_sum = sum(v["score"] * v["weight"] for v in breakdown.values())
    composite = round(weighted_sum / total_weight) if total_weight > 0 else 0

    return {
        "score": composite,
        "trades": total_trades,
        "wins": wins,
        "losses": losses,
        "win_rate": f"{win_rate:.1f}%",
        "sharpe": f"{sharpe:.3f}",
        "drawdown": f"{dd:.1f}%",
        "total_pnl": f"€{total_pnl:+.2f}",
        "total_fees": f"€{total_fees:+.2f}",
        "breakdown": breakdown,
        "recommendation": generate_recommendation(bot_name, composite, breakdown),
    }

def _has_issue(issues, keyword):
    for issue in issues:
        if keyword in issue:
            return True
    return False

def generate_recommendation(bot_name, score, breakdown):
    """Produce a human-readable recommendation based on scores"""
    if score >= 75:
        return "✅ Tutto OK. Mantieni parametri attuali."
    
    issues = []
    for metric, data in breakdown.items():
        if data["score"] < 50:
            issues.append(f"⬇ {metric} ({data['value']} score={data['score']})")
    
    if score >= 50:
        base = "🟡 Attenzione: "
        recs = []
        if _has_issue(issues, "win_rate"):
            recs.append("riduci sizing, aumenta spread grid")
        if _has_issue(issues, "sharpe"):
            recs.append("verifica regime di mercato, riduci frequenza")
        if _has_issue(issues, "drawdown"):
            recs.append("tighten stop-loss, riduci esposizione")
        if _has_issue(issues, "trades_per_day"):
            recs.append("rivedi trigger di ingresso")
        if _has_issue(issues, "profit_factor"):
            recs.append("taglia perdenti prima, lascia correre vincenti")
        return base + ", ".join(recs) if recs else base + "monitora prossima review"
    
    base = "🔴 Intervento necessario: "
    recs = ["stop bot se non già fermo"]
    if _has_issue(issues, "win_rate"):
        recs.append("revisione completa strategia")
    if _has_issue(issues, "drawdown"):
        recs.append("drawdown fuori controllo — riduci capitale del 50%")
    if _has_issue(issues, "sharpe"):
        recs.append("parametri non validi per mercato attuale — backtest nuove configurazioni")
    if _has_issue(issues, "profit_30d"):
        recs.append("perdita prolungata — pausa di 48h")
    return base + ", ".join(recs)

def run_review(days=30):
    """Full review run: fetch trades, score all bots, generate report"""
    REVIEWS_DIR.mkdir(parents=True, exist_ok=True)
    
    trades = get_trades(days=days)
    if not trades:
        print("[REVIEW] No trades found. Generating empty report.")
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        report_path = REVIEWS_DIR / f"review_{datetime.now().strftime('%Y%m%d_%H%M')}.md"
        report_path.write_text(f"# Review Report — {now}\n\nNo trade data available.\n")
        return report_path

    by_bot = group_by_bot(trades)
    
    results = {}
    for bot_name, bot_trades in sorted(by_bot.items()):
        results[bot_name] = score_bot(bot_name, bot_trades, days=days)
    
    # Generate report
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = []
    lines.append(f"# 📊 Self-Review Report — {now}")
    lines.append(f"\n> Periodo: ultimi {days} giorni | Trade analizzati: {len(trades)}")
    lines.append("")
    
    for bot_name, res in sorted(results.items()):
        score = res.get("score")
        if score is None:
            lines.append(f"\n## {bot_name}")
            lines.append(f"\n_No goals defined_")
            continue
        
        # Emoji status
        if score >= 75: status = "✅ Verde"
        elif score >= 50: status = "🟡 Giallo"
        elif score >= 30: status = "🟠 Arancione"
        else: status = "🔴 Rosso"
        
        lines.append(f"\n## {bot_name} — Score: {score}/100 {status}")
        lines.append(f"| Metrica | Valore | Score | Peso |")
        lines.append(f"|---------|--------|-------|------|")
        for metric, data in res.get("breakdown", {}).items():
            emoji = "✅" if data["score"] >= 75 else "🟡" if data["score"] >= 50 else "🔴"
            lines.append(f"| {metric} | {data['value']} | {emoji} {data['score']}/100 | {data['weight']}% |")
        
        lines.append(f"\n**Trades:** {res.get('trades', 0)} ({res.get('wins', 0)}W / {res.get('losses', 0)}L)")
        lines.append(f"**Win Rate:** {res.get('win_rate', 'N/A')}")
        lines.append(f"**Sharpe Ratio:** {res.get('sharpe', 'N/A')}")
        lines.append(f"**Max Drawdown:** {res.get('drawdown', 'N/A')}")
        lines.append(f"**PnL Netto:** {res.get('total_pnl', 'N/A')}")
        lines.append(f"**Fee Totali:** {res.get('total_fees', 'N/A')}")
        lines.append(f"\n**Raccomandazione:** {res.get('recommendation', 'N/A')}")
    
    # Summary section
    lines.append("\n---")
    lines.append("\n## Riepilogo")
    lines.append("\n| Bot | Score | Status | Raccomandazione |")
    lines.append("|-----|-------|--------|-----------------|")
    for bot_name, res in sorted(results.items()):
        score = res.get("score")
        if score is None:
            continue
        if score >= 75: status = "✅"
        elif score >= 50: status = "🟡"
        elif score >= 30: status = "🟠"
        else: status = "🔴"
        rec = res.get("recommendation", "N/A").split(". ")[0] if res.get("recommendation") else "N/A"
        lines.append(f"| {bot_name} | {score}/100 | {status} | {rec} |")
    
    lines.append("\n\n---")
    lines.append(f"\n_Generato da self_review.py — {now}_")
    
    content = "\n".join(lines)
    report_path = REVIEWS_DIR / f"review_{datetime.now().strftime('%Y%m%d_%H%M')}.md"
    report_path.write_text(content)
    print(f"[REVIEW] Report salvato: {report_path}")
    return report_path

def get_metric(param_name, bot_name):
    """Read last N values of a specific metric from review history"""
    if not REVIEWS_DIR.exists():
        return []
    reports = sorted(REVIEWS_DIR.glob("review_*.md"))
    values = []
    for rp in reports[-14:]:  # last 2 weeks max
        text = rp.read_text()
        for line in text.split("\n"):
            if param_name in line and bot_name in line[:100]:
                # Try to extract value
                pass
    return values

if __name__ == "__main__":
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    report_path = run_review(days=days)
    print(f"\nReport: {report_path}")
    
    # Show overview
    content = report_path.read_text()
    for line in content.split("\n"):
        if "Score:" in line and "/100" in line:
            print(f"  {line.strip()}")
