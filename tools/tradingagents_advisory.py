#!/usr/bin/env python3
"""TradingAgents advisory runner — Denaro (log-only, NESSUN ordine).

Esegue la pipeline multi-agente di TradingAgents (analisti -> dibattito
ricercatori -> trader -> risk team -> portfolio manager) per una lista di
asset e salva il verdetto (rating 5-tier + report) in:
  - logs/tradingagents/advisory/<data>_<ticker>.json   (record completo)
  - logs/tradingagents/advisory.jsonl                  (una riga di riepilogo per asset)

SICUREZZA: non legge chiavi di exchange e non può inviare ordini — è un
layer di ricerca/advisory per il progetto Denaro. Richiede le chiavi LLM in
config/.env_tradingagents (gitignored).

Uso (dalla radice del repo):
  tradingagents/.venv/bin/python tools/tradingagents_advisory.py --check
  tradingagents/.venv/bin/python tools/tradingagents_advisory.py \
      --tickers BTC-USD,ETH-USD --date 2026-09-24

Le coppie Denaro in stile 'BTC/EUR' vengono normalizzate sul mercato di
riferimento 'BTC-USD' (direzione equivalente, dati più liquidi).
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import sys
import time
from datetime import date as _date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ENV_FILE = REPO / "config" / ".env_tradingagents"
OUT_DIR = REPO / "logs" / "tradingagents" / "advisory"


def _load_env() -> None:
    """Carica config/.env_tradingagents PRIMA di importare tradingagents.

    DEFAULT_CONFIG applica gli override TRADINGAGENTS_* a import-time, quindi
    l'ordine conta. override=False: variabili gia' presenti nello shell
    vincono sul file (utile per test mirati); il file riempie il resto.
    """
    from dotenv import load_dotenv

    if not ENV_FILE.exists():
        sys.exit(f"ERRORE: manca {ENV_FILE}")
    load_dotenv(ENV_FILE, override=False)
    if not os.environ.get("DEEPSEEK_API_KEY"):
        sys.exit("ERRORE: DEEPSEEK_API_KEY assente in config/.env_tradingagents")


_load_env()

from langchain_core.callbacks import BaseCallbackHandler  # noqa: E402
from tradingagents.default_config import DEFAULT_CONFIG  # noqa: E402
from tradingagents.graph.trading_graph import TradingAgentsGraph  # noqa: E402

CRYPTO_SUFFIXES = ("-USD", "-USDT", "-USDC", "-BTC", "-ETH")


class TokenStats(BaseCallbackHandler):
    """Conta chiamate LLM e token per run (controllo costi)."""

    def __init__(self) -> None:
        self.llm_calls = 0
        self.tokens_in = 0
        self.tokens_out = 0

    def on_chat_model_start(self, *args, **kwargs) -> None:
        self.llm_calls += 1

    def on_llm_start(self, *args, **kwargs) -> None:
        self.llm_calls += 1

    def on_llm_end(self, response, **kwargs) -> None:
        try:
            generation = response.generations[0][0]
        except (IndexError, TypeError):
            return
        message = getattr(generation, "message", None)
        usage = getattr(message, "usage_metadata", None) if message is not None else None
        if usage:
            self.tokens_in += usage.get("input_tokens", 0) or 0
            self.tokens_out += usage.get("output_tokens", 0) or 0


def normalize_ticker(raw: str) -> str:
    """'btc/eur' -> 'BTC-USD' (mercato di riferimento); 'btc-usd' -> 'BTC-USD'."""
    t = raw.strip().upper()
    if "/" in t:
        base = t.split("/", 1)[0]
        return f"{base}-USD"
    return t


def asset_type_for(ticker: str) -> str:
    return "crypto" if ticker.endswith(CRYPTO_SUFFIXES) else "stock"


def safe_name(ticker: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", ticker)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--tickers", help="es. 'BTC-USD,ETH-USD' oppure coppie Denaro 'BTC/EUR,ETH/EUR'")
    parser.add_argument("--date", default=_date.today().isoformat(), help="YYYY-MM-DD (default: oggi)")
    parser.add_argument("--analysts", default=None, help="csv: market,news,social[,fundamentals]; default auto per asset")
    parser.add_argument("--check", action="store_true", help="stampa la config risolta ed esce (nessuna chiamata LLM)")
    args = parser.parse_args()

    cfg = DEFAULT_CONFIG.copy()

    if args.check:
        print("provider    :", cfg["llm_provider"])
        print("deep_think  :", cfg["deep_think_llm"])
        print("quick_think :", cfg["quick_think_llm"])
        print("language    :", cfg["output_language"])
        print("rounds      : debate=%s risk=%s" % (cfg["max_debate_rounds"], cfg["max_risk_discuss_rounds"]))
        print("results_dir :", cfg["results_dir"])
        print("cache_dir   :", cfg["data_cache_dir"])
        print("memory      :", cfg["memory_log_path"])
        print("key DeepSeek:", "presente" if os.environ.get("DEEPSEEK_API_KEY") else "ASSENTE")
        print("key Jev     :", "presente" if os.environ.get("TYPESAFE_API_KEY") else "assente")
        return 0

    if not args.tickers:
        parser.error("--tickers obbligatorio (oppure usa --check)")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.date):
        parser.error(f"--date deve essere YYYY-MM-DD, ricevuto {args.date!r}")

    tickers = [normalize_ticker(t) for t in args.tickers.split(",") if t.strip()]
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    lock_path = OUT_DIR / ".lock"
    lock_file = open(lock_path, "w")
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        sys.exit(f"advisory già in esecuzione (lock attivo su {lock_path})")

    jsonl_path = REPO / "logs" / "tradingagents" / "advisory.jsonl"
    failures = 0

    for ticker in tickers:
        atype = asset_type_for(ticker)
        if args.analysts:
            analysts = tuple(a.strip().lower() for a in args.analysts.split(",") if a.strip())
        elif atype == "crypto":
            analysts = ("market", "news", "social")
        else:
            analysts = ("market", "news", "social", "fundamentals")

        stats = TokenStats()
        print(f"[advisory] {ticker} {args.date} analysts={','.join(analysts)} ...", flush=True)
        started = time.time()
        try:
            graph = TradingAgentsGraph(selected_analysts=analysts, debug=False, config=cfg, callbacks=[stats])
            state, signal = graph.propagate(ticker, args.date, asset_type=atype)
        except Exception as exc:  # un asset rotto non deve fermare gli altri
            failures += 1
            print(f"[advisory] {ticker}: ERRORE {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
            with open(jsonl_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps({
                    "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                    "ticker": ticker,
                    "trade_date": args.date,
                    "error": f"{type(exc).__name__}: {exc}",
                }, ensure_ascii=False) + "\n")
            continue

        duration = round(time.time() - started, 1)
        record = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "ticker": ticker,
            "asset_type": atype,
            "trade_date": args.date,
            "signal": signal,
            "analysts": list(analysts),
            "provider": cfg["llm_provider"],
            "models": {"deep": cfg["deep_think_llm"], "quick": cfg["quick_think_llm"]},
            "language": cfg["output_language"],
            "stats": {"llm_calls": stats.llm_calls, "tokens_in": stats.tokens_in, "tokens_out": stats.tokens_out},
            "duration_s": duration,
            "reports": {
                "market": state.get("market_report", ""),
                "news": state.get("news_report", ""),
                "sentiment": state.get("sentiment_report", ""),
                "investment_plan": state.get("investment_plan", ""),
                "trader_plan": state.get("trader_investment_plan", ""),
            },
            "final_decision": state.get("final_trade_decision", ""),
        }

        out_file = OUT_DIR / f"{args.date}_{safe_name(ticker)}.json"
        out_file.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

        with open(jsonl_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "ts": record["ts"],
                "ticker": ticker,
                "trade_date": args.date,
                "signal": signal,
                "llm_calls": stats.llm_calls,
                "tokens_in": stats.tokens_in,
                "tokens_out": stats.tokens_out,
                "duration_s": duration,
                "file": str(out_file),
            }, ensure_ascii=False) + "\n")

        print(
            f"[advisory] {ticker}: signal={signal}  calls={stats.llm_calls} "
            f"tok_in={stats.tokens_in} tok_out={stats.tokens_out}  {duration}s -> {out_file}"
        )

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
