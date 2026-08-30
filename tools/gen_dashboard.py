#!/usr/bin/env python3
"""Genera /var/www/denaro/data/combined.json da infra.json (MARCODG1 aggregatore).

La fonte autoritativa è infra.json servito da MARCODG1:8912 (infra_aggregator.py),
che aggrega bot, saldi, prezzi ed errori di TUTTI i nodi.

Portafoglio reale: dedup per fingerprint di asset (un account Kraken condiviso tra
più nodi NON si conta due volte). Stima conservativa = OKX main + OKX marcosub1
+ OKX mc2sub1 + OKX nuvolasub1 (sub distinti) + 1× Kraken (account unico).
"""
import json
import shlex
import subprocess
import time
from pathlib import Path

OUT_DIR = Path("/var/www/denaro/data")
OUT_DIR.mkdir(parents=True, exist_ok=True)
HISTORY = OUT_DIR / "history.json"
STALE_S = 900

AGG_SSH = "MARCODG1"
AGG_URL = "http://127.0.0.1:8912/infra.json"

# Chiave canonica per il "Portafoglio Totale (reale)".
# Pesata in EUR con prezzi Binance (USDT→EUR), come fa l'auditor in /tmp/portfolio_audit.py.
OKX_BINANCE_SYMBOLS = {
    "ADA": "ADAUSDT", "DOGE": "DOGEUSDT", "ETH": "ETHUSDT",
    "SOL": "SOLUSDT", "XRP": "XRPUSDT", "BTC": "BTCUSDT",
}


def node_of(bot_key: str) -> str:
    k = bot_key.lower()
    if k.startswith("mc2"):
        return "mc2"
    if k.startswith("nuvola"):
        return "nuvola"
    return "MARCODG1"


def fetch_infra():
    cmd = f"curl -sk --max-time 8 {AGG_URL}"
    r = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", AGG_SSH, cmd],
        capture_output=True, text=True, timeout=25,
    )
    if r.returncode != 0 or not r.stdout.strip():
        raise RuntimeError(f"infra.json fetch failed: {r.stderr.strip()[:120]}")
    try:
        return json.loads(r.stdout)
    except Exception as e:
        raise RuntimeError(f"infra.json JSON parse error: {e}")


def fetch_binance_prices() -> dict[str, float]:
    """Restituisce {asset: eur_price} tramite ticker Binance."""
    out: dict[str, float] = {"EUR": 1.0, "USD": 0.0}
    try:
        r = subprocess.run(
            ["curl", "-s", "-m", "8", "https://api.binance.com/api/v3/ticker/price?symbol=EURUSDT"],
            capture_output=True, text=True, timeout=10,
        )
        data = json.loads(r.stdout) if r.stdout else {}
        eur_usdt = float(data.get("price") or 0.0)
        if eur_usdt > 0:
            out["USD"] = 1.0 / eur_usdt
    except Exception:
        pass
    for asset, symbol in OKX_BINANCE_SYMBOLS.items():
        try:
            r = subprocess.run(
                ["curl", "-s", "-m", "8", f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"],
                capture_output=True, text=True, timeout=10,
            )
            data = json.loads(r.stdout) if r.stdout else {}
            usdt = float(data.get("price") or 0.0)
            if usdt > 0 and out["USD"] > 0:
                out[asset] = usdt * out["USD"]
        except Exception:
            pass
    return out


def collect_balances(infra: dict) -> list[dict]:
    """Ciascun elemento: {'exchange','account','assets': {asset: amount}, 'source'}.

    L'aggregatore espone balances con chiavi tipo 'denaro (main)', 'alpha (marcosub1)',
    'kraken (nuvola)'. Interpreto l'etichetta per exchange/uid.
    """
    out: list[dict] = []
    bal = infra.get("balances") or {}
    for label, payload in bal.items():
        if not isinstance(payload, dict) or not payload.get("ok"):
            continue
        lname = label.lower()
        if "kraken" in lname:
            exchange = "kraken"
        elif "okx" in lname or "denaro" in lname or "alpha" in lname or "nuvola" in lname or "marco" in lname or "mc2" in lname:
            exchange = "okx"
        else:
            exchange = lname.split()[0] if lname else "?"
        # totale degli asset (no free): la fonte piu' conservativa
        total = (payload or {}).get("total") or {}
        assets: dict[str, float] = {}
        for asset, amount in total.items():
            try:
                a = float(amount)
            except (TypeError, ValueError):
                continue
            if abs(a) <= 1e-12:
                continue
            norm_asset = "BTC" if asset in ("XBT", "XXBT") else (
                "USD" if asset in ("USD", "ZUSD") else asset
            )
            assets[norm_asset] = assets.get(norm_asset, 0.0) + a
        if assets:
            out.append({
                "exchange": exchange, "account": label,
                "assets": assets, "source": f"infra.balances.{label}",
            })
    return out


def fingerprint(account: dict) -> tuple:
    return tuple(sorted(
        (a, round(amount, 9)) for a, amount in account["assets"].items()
    ))


def value_in_eur(assets: dict[str, float], prices: dict[str, float]) -> float:
    total = 0.0
    for asset, amount in assets.items():
        if asset in prices and prices[asset] > 0:
            total += amount * prices[asset]
    return total


def build_portfolio(infra: dict, prices: dict[str, float]) -> dict:
    accounts = collect_balances(infra)
    # Dedup per fingerprint (es. Kraken visto da mc2/nuvola/MARCODG1 = 1 sola riga)
    seen: dict[tuple, dict] = {}
    for acc in accounts:
        fp = fingerprint(acc)
        if fp in seen:
            seen[fp]["hosts"] = seen[fp].get("hosts", [seen[fp]["source"]]) + [acc["source"]]
            continue
        acc["hosts"] = [acc["source"]]
        seen[fp] = acc
    deduped = list(seen.values())

    breakdown: list[dict] = []
    grand_total = 0.0
    for acc in deduped:
        eur = value_in_eur(acc["assets"], prices)
        grand_total += eur
        breakdown.append({
            "exchange": acc["exchange"],
            "account": acc["account"],
            "label": f"{acc['exchange'].upper()} {acc['account'][:8]}",
            "assets": {
                a: {"amount": round(amount, 8), "eur": round(amount * prices.get(a, 0.0), 4)}
                for a, amount in acc["assets"].items()
                if prices.get(a, 0.0) > 0
            },
            "total_eur": round(eur, 4),
            "hosts": acc.get("hosts", [acc["source"]]),
        })
    breakdown.sort(key=lambda r: -r["total_eur"])
    return {
        "total_eur": round(grand_total, 4),
        "by_account": breakdown,
        "as_of": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "prices_used": {a: round(p, 6) for a, p in prices.items() if p > 0},
        "warning": None if deduped else "nessun dato",
    }


def fetch_portfolio_via_aggregator(prices: dict[str, float]) -> dict:
    """Aggrega da infra.json con dedup + conversione in EUR."""
    cache = Path("/tmp/portfolio_cache.json")
    now = time.time()
    if cache.exists():
        try:
            c = json.loads(cache.read_text())
            if now - c.get("ts", 0) < 300 and c.get("prices") == prices:
                return c.get("data")
        except Exception:
            pass
    try:
        infra = fetch_infra()
        data = build_portfolio(infra, prices)
        cache.write_text(json.dumps({"ts": now, "data": data, "prices": prices}))
        return data
    except Exception as e:
        if cache.exists():
            try:
                c = json.loads(cache.read_text())
                d = c.get("data", {}) or {}
                d["warning"] = f"cache stale: {str(e)[:80]}"
                return d
            except Exception:
                pass
        return {"total_eur": None, "by_account": [], "warning": f"errore: {str(e)[:120]}"}


def slim(b, node, mode):
    return {
        "node": node, "symbol": b.get("symbol"), "mode": mode,
        "status": b.get("status") or "unknown",
        "capital": b.get("capital"),
        "total_equity": b.get("total_equity"),
        "pnl": b.get("pnl"), "trades": b.get("trades"),
        "wins": b.get("wins"), "losses": b.get("losses"),
        "drawdown": b.get("drawdown"),
        "error": b.get("error", "") or b.get("regime_error", ""),
        "timestamp": b.get("timestamp"),
        "age_s": None,
        "strategy": b.get("strategy"),
        "win_rate_pct": b.get("win_rate_pct"),
        "profit_factor": b.get("profit_factor"),
        "volume": b.get("volume"),
        "free_quote": b.get("free_quote"),
        "source": b.get("_file", "infra.json"),
    }


def main():
    now = time.time()
    infra = fetch_infra()

    bots_src = infra.get("node_bots") or infra.get("bots") or {}
    live, paper, stale = [], [], []
    for key, b in bots_src.items():
        if not isinstance(b, dict) or not b.get("symbol"):
            continue
        node = node_of(key)
        mode = "PAPER" if ("paper" in str(key).lower()) else "LIVE"
        b = dict(b)
        b["_file"] = f"infra.json:{key}"
        ts = float(b.get("timestamp") or 0)
        age = now - ts if ts and (now - ts) > 0 else 0
        status = (b.get("status") or "unknown").lower()
        if status not in ("running", "stale", "blocked", "stopped", "error"):
            status = "unknown"
        if not b.get("error"):
            err = (infra.get("node_errors") or {}).get(key)
            if err:
                b["error"] = err
                if status == "running":
                    status = "blocked"
        b["status"] = status
        rec = slim(b, node, mode)
        rec["age_s"] = round(age, 1) if age else None
        if status == "stale" or (age and age > STALE_S and status == "running"):
            if rec["status"] != "stale":
                rec["status"] = "stale"
                rec["error"] = (rec["error"] or "") + f" stale health age={int(age)}s"
            stale.append(rec)
        (paper if mode == "PAPER" else live).append(rec)

    live.sort(key=lambda x: (x["node"], x["symbol"]))
    paper.sort(key=lambda x: (x["node"], x["symbol"]))

    history = {}
    if HISTORY.exists():
        try:
            history = json.loads(HISTORY.read_text())
        except Exception:
            history = {}
    for b in live + paper:
        key = f"{b['node']}:{b['symbol']}:{b['mode']}"
        entry = history.setdefault(key, {"points": []})
        if b["status"] == "running" and b["total_equity"] is not None:
            entry["points"].append({
                "t": int(now),
                "eq": round(float(b["total_equity"]), 4),
                "pnl": round(float(b["pnl"] or 0), 4),
            })
            entry["points"] = entry["points"][-240:]
    HISTORY.write_text(json.dumps(history))

    prices = fetch_binance_prices()
    portfolio = fetch_portfolio_via_aggregator(prices)

    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "live": live,
        "paper": paper,
        "history": history,
        "counts": {"live": len(live), "paper": len(paper)},
        "running_counts": {
            "live": sum(1 for b in live if b["status"] == "running"),
            "paper": sum(1 for b in paper if b["status"] == "running"),
        },
        "stale": stale,
        "portfolio": portfolio,
        "aggregate": {
            "total_equity": infra.get("total_equity"),
            "bot_equity": infra.get("bot_equity"),
            "kraken_equity": infra.get("kraken_equity"),
            "node_total_pnl": infra.get("node_total_pnl"),
            "node_total_trades": infra.get("node_total_trades"),
            "node_win_rate": infra.get("node_win_rate"),
        },
    }
    (OUT_DIR / "combined.json").write_text(json.dumps(payload, indent=1))
    print(f"OK: {len(live)} live ({payload['running_counts']['live']} running), "
          f"{len(paper)} paper, stale={len(stale)}, "
          f"portfolio_total={portfolio.get('total_eur')} EUR, accounts={len(portfolio.get('by_account', []))}")


if __name__ == "__main__":
    main()
